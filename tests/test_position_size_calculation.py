from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.timeframes import get_timeframe_spec
from app.strategy.analysis_pipeline import (
    MultiTimeframeAnalysisPipeline,
)
from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiTimeframeContextBuilder,
)
from app.strategy.position_size_calculation import (
    PositionSizeCalculationBlocker,
    PositionSizeCalculationDecision,
    PositionSizeCalculationError,
    PositionSizeCalculationErrorReason,
    PositionSizeCalculationPolicy,
    PositionSizeCalculationReason,
    PositionSizeCalculationStatus,
    PositionSizeCalculator,
    PositionSizeDecision,
    PositionSizeMetrics,
    PositionSizePolicy,
    PositionSizeReason,
    PositionSizeRoundingMode,
    PositionSizeStatus,
    SizingCalculationBlocker,
    SizingCalculationDecision,
    SizingCalculationPolicy,
    SizingCalculationReason,
    SizingCalculationStatus,
    SizingMetrics,
    StrategyPositionSizeCalculator,
    StrategySizingCalculator,
    calculate_strategy_position_size,
)
from app.strategy.position_sizing_handoff import (
    PositionSizingHandoffDecision,
    StrategyPositionSizingHandoffFactory,
)
from app.strategy.position_sizing_specification import (
    PositionSizingSpecification,
    StrategyPositionSizingSpecificationGate,
)
from app.strategy.price_planning_admission import (
    StrategyPricePlanningAdmissionGate,
)
from app.strategy.price_planning_blueprint import (
    StrategyPricePlanningBlueprintFactory,
)
from app.strategy.price_reference_availability import (
    PriceReferenceAvailabilityItem,
    PriceReferenceAvailabilitySnapshot,
    StrategyPriceReferenceAvailabilityGate,
)
from app.strategy.price_reference_plan import (
    PriceReferenceRole,
    StrategyPriceReferencePlanFactory,
)
from app.strategy.price_reference_resolution import (
    PriceReferenceValueObservation,
    PriceReferenceValueSnapshot,
    StrategyPriceReferenceResolutionGate,
)
from app.strategy.reward_risk_analysis import (
    StrategyRewardRiskAnalysisGate,
)
from app.strategy.risk_budget_admission import (
    StrategyRiskBudgetAdmissionGate,
    StrategyRiskBudgetSnapshot,
)
from app.strategy.setup_candidate import (
    StrategySetupCandidateFactory,
)
from app.strategy.setup_candidate_quality import (
    StrategySetupCandidateQualityGate,
)
from app.strategy.setup_qualification import (
    StrategySetupQualificationGate,
)

OBSERVED_AT = datetime(
    2026,
    7,
    26,
    20,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    timeframe: TimeframeName,
    *,
    count: int = 8,
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    first_open = OBSERVED_AT - duration * count
    candles: list[ClosedCandle] = []

    for index in range(count):
        open_time = first_open + duration * index

        if index % 2 == 0:
            open_price = Decimal("100")
            close_price = Decimal("101")
        else:
            open_price = Decimal("101")
            close_price = Decimal("100")

        candles.append(
            ClosedCandle(
                broker_symbol="XAUUSDm",
                timeframe=timeframe,
                open_time=open_time,
                observed_at=open_time + duration,
                open=open_price,
                high=Decimal("102"),
                low=Decimal("98"),
                close=close_price,
                tick_volume=1000,
                spread=20,
                real_volume=0,
            )
        )

    return ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=timeframe,
        candles=tuple(candles),
    )


@lru_cache(maxsize=1)
def neutral_context():
    mapping = {timeframe: create_series(timeframe) for timeframe in GOLD_TIMEFRAME_HIERARCHY}

    return MultiTimeframeContextBuilder().build(mapping)


def handoff_decision_for(
    direction: DirectionalPermissionDirection,
    *,
    blocked: bool = False,
) -> PositionSizingHandoffDecision:
    if direction == DirectionalPermissionDirection.BULLISH:
        selected_bias = MarketStructureBias.BULLISH
        entry_value = Decimal("2350")
        stop_value = Decimal("2340")
        target_value = Decimal("2370")
    elif direction == DirectionalPermissionDirection.BEARISH:
        selected_bias = MarketStructureBias.BEARISH
        entry_value = Decimal("2350")
        stop_value = Decimal("2360")
        target_value = Decimal("2325")
    else:
        raise ValueError("Direction must be resolved.")

    context = replace(
        neutral_context(),
        structure_biases=tuple(
            (
                timeframe,
                (
                    selected_bias
                    if timeframe
                    in {
                        TimeframeName.H4,
                        TimeframeName.H1,
                        TimeframeName.M15,
                    }
                    else MarketStructureBias.NEUTRAL
                ),
            )
            for timeframe in GOLD_TIMEFRAME_HIERARCHY
        ),
    )
    analysis = MultiTimeframeAnalysisPipeline().evaluate_context(context)
    qualification = StrategySetupQualificationGate().evaluate(analysis)
    candidate = StrategySetupCandidateFactory().generate(qualification).candidate_required
    quality = StrategySetupCandidateQualityGate().evaluate(candidate)
    admission = StrategyPricePlanningAdmissionGate().evaluate(quality)
    blueprint = StrategyPricePlanningBlueprintFactory().generate(admission)
    plan_decision = StrategyPriceReferencePlanFactory().generate(blueprint)
    plan = plan_decision.plan_required
    availability = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        PriceReferenceAvailabilitySnapshot(
            plan=plan,
            items=tuple(
                PriceReferenceAvailabilityItem(
                    requirement=requirement,
                    available=True,
                )
                for requirement in plan.requirements
            ),
        ),
    )
    values = {
        PriceReferenceRole.ENTRY: entry_value,
        PriceReferenceRole.STOP: stop_value,
        PriceReferenceRole.TARGET: target_value,
    }
    resolution = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        PriceReferenceValueSnapshot(
            plan=plan,
            observations=tuple(
                PriceReferenceValueObservation(
                    requirement=requirement,
                    value=values[requirement.role],
                )
                for requirement in (
                    availability.selected_entry,
                    availability.selected_stop,
                    availability.selected_target,
                )
                if requirement is not None
            ),
        ),
    )
    reward_risk = StrategyRewardRiskAnalysisGate().evaluate(resolution)
    risk_admission = StrategyRiskBudgetAdmissionGate().evaluate(
        reward_risk,
        StrategyRiskBudgetSnapshot(
            observed_at=OBSERVED_AT,
            account_equity=Decimal("10000"),
            proposed_risk_amount=Decimal("100"),
            current_aggregate_risk_amount=Decimal("0"),
            realized_daily_loss_amount=Decimal("0"),
            open_gold_positions=0,
            kill_switch_active=blocked,
        ),
    )

    return StrategyPositionSizingHandoffFactory().generate(risk_admission)


@lru_cache(maxsize=1)
def bullish_handoff() -> PositionSizingHandoffDecision:
    return handoff_decision_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_handoff() -> PositionSizingHandoffDecision:
    return handoff_decision_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_handoff() -> PositionSizingHandoffDecision:
    return handoff_decision_for(
        DirectionalPermissionDirection.BULLISH,
        blocked=True,
    )


def sizing_specification(
    *,
    observed_at: datetime = OBSERVED_AT,
    broker_symbol: str = "XAUUSDm",
    digits: int = 2,
    point_size: Decimal = Decimal("0.01"),
    tick_size: Decimal = Decimal("0.01"),
    tick_value: Decimal = Decimal("1"),
    contract_size: Decimal = Decimal("100"),
    volume_min: Decimal = Decimal("0.01"),
    volume_max: Decimal = Decimal("100"),
    volume_step: Decimal = Decimal("0.01"),
) -> PositionSizingSpecification:
    return PositionSizingSpecification(
        observed_at=observed_at,
        broker_symbol=broker_symbol,
        digits=digits,
        point_size=point_size,
        tick_size=tick_size,
        tick_value=tick_value,
        contract_size=contract_size,
        volume_min=volume_min,
        volume_max=volume_max,
        volume_step=volume_step,
    )


def specification_decision_for(
    direction: DirectionalPermissionDirection,
    *,
    blocked: bool = False,
    tick_size: Decimal = Decimal("0.01"),
    tick_value: Decimal = Decimal("1"),
    volume_min: Decimal = Decimal("0.01"),
    volume_max: Decimal = Decimal("100"),
    volume_step: Decimal = Decimal("0.01"),
):
    handoff = (
        blocked_handoff()
        if blocked
        else (
            bullish_handoff()
            if direction == DirectionalPermissionDirection.BULLISH
            else bearish_handoff()
        )
    )
    gate = StrategyPositionSizingSpecificationGate()

    if blocked:
        return gate.evaluate(handoff)

    return gate.evaluate(
        handoff,
        sizing_specification(
            tick_size=tick_size,
            tick_value=tick_value,
            volume_min=volume_min,
            volume_max=volume_max,
            volume_step=volume_step,
        ),
    )


@lru_cache(maxsize=1)
def bullish_specification_decision():
    return specification_decision_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_specification_decision():
    return specification_decision_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_specification_decision():
    return specification_decision_for(
        DirectionalPermissionDirection.BULLISH,
        blocked=True,
    )


def test_default_policy_uses_floor_rounding() -> None:
    policy = PositionSizeCalculationPolicy()

    assert policy.rounding_mode == (PositionSizeRoundingMode.FLOOR)
    assert policy.cap_to_maximum_volume is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"rounding_mode": "FLOOR"},
        {"cap_to_maximum_volume": 1},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        PositionSizeCalculationPolicy(**overrides)


def test_calculator_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PositionSizeCalculationPolicy",
    ):
        StrategyPositionSizeCalculator(policy="invalid")


def test_invalid_specification_decision_is_fail_safe() -> None:
    with pytest.raises(
        PositionSizeCalculationError,
        match="INVALID_SPECIFICATION_DECISION",
    ) as captured:
        StrategyPositionSizeCalculator().calculate("invalid")

    assert captured.value.reason == (
        PositionSizeCalculationErrorReason.INVALID_SPECIFICATION_DECISION
    )


def test_blocked_specification_blocks_calculation() -> None:
    decision = StrategyPositionSizeCalculator().calculate(blocked_specification_decision())

    assert decision.status == (PositionSizeCalculationStatus.BLOCKED)
    assert decision.reason == (PositionSizeCalculationReason.SPECIFICATION_BLOCKED)
    assert decision.blockers == (PositionSizeCalculationBlocker.SPECIFICATION_BLOCKED,)
    assert decision.metrics is None


def test_bullish_position_size_is_calculated() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert decision.status == (PositionSizeCalculationStatus.CALCULATED)
    assert decision.reason == (PositionSizeCalculationReason.CALCULATED)
    assert decision.blockers == ()
    assert decision.is_calculated is True


def test_bearish_position_size_is_calculated() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bearish_specification_decision())

    assert decision.is_calculated is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)


def test_default_risk_per_volume_unit_is_exact() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert decision.metrics is not None
    assert decision.metrics.risk_per_volume_unit == (Decimal("1000"))


def test_default_raw_volume_is_exact() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert decision.raw_volume == Decimal("0.1")


def test_default_normalized_volume_is_exact() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert decision.normalized_volume == Decimal("0.10")
    assert decision.calculated_volume_required == Decimal("0.10")


def test_exact_risk_is_fully_utilized() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert decision.actual_risk_amount == Decimal("100")
    assert decision.unused_risk_amount == Decimal("0")
    assert decision.risk_utilization_percent == Decimal("100")


def test_volume_is_normalized_downward() -> None:
    specification_decision = specification_decision_for(
        DirectionalPermissionDirection.BULLISH,
        tick_value=Decimal("0.8"),
    )

    decision = StrategyPositionSizeCalculator().calculate(specification_decision)

    assert decision.raw_volume == Decimal("0.125")
    assert decision.normalized_volume == Decimal("0.12")
    assert decision.actual_risk_amount == Decimal("96")
    assert decision.unused_risk_amount == Decimal("4")
    assert decision.risk_utilization_percent == Decimal("96")


def test_normalized_risk_never_exceeds_approved_risk() -> None:
    decision = StrategyPositionSizeCalculator().calculate(
        specification_decision_for(
            DirectionalPermissionDirection.BULLISH,
            tick_value=Decimal("0.8"),
        )
    )

    assert decision.handoff is not None
    assert decision.actual_risk_amount is not None
    assert decision.actual_risk_amount <= decision.handoff.approved_risk_amount


def test_raw_volume_below_minimum_is_blocked() -> None:
    decision = StrategyPositionSizeCalculator().calculate(
        specification_decision_for(
            DirectionalPermissionDirection.BULLISH,
            tick_value=Decimal("20"),
        )
    )

    assert decision.is_blocked is True
    assert decision.reason == (PositionSizeCalculationReason.BELOW_MINIMUM_VOLUME)
    assert decision.blockers == (PositionSizeCalculationBlocker.BELOW_MINIMUM_VOLUME,)
    assert decision.raw_volume == Decimal("0.005")


def test_blocked_volume_cannot_be_required() -> None:
    decision = StrategyPositionSizeCalculator().calculate(
        specification_decision_for(
            DirectionalPermissionDirection.BULLISH,
            tick_value=Decimal("20"),
        )
    )

    with pytest.raises(
        ValueError,
        match="No calculated position volume",
    ):
        _ = decision.calculated_volume_required


def test_above_maximum_volume_is_capped_by_default() -> None:
    decision = StrategyPositionSizeCalculator().calculate(
        specification_decision_for(
            DirectionalPermissionDirection.BULLISH,
            volume_max=Decimal("0.05"),
        )
    )

    assert decision.is_calculated is True
    assert decision.raw_volume == Decimal("0.1")
    assert decision.normalized_volume == Decimal("0.05")
    assert decision.actual_risk_amount == Decimal("50")
    assert decision.metrics is not None
    assert decision.metrics.capped_to_maximum is True


def test_maximum_capping_can_be_disabled() -> None:
    policy = PositionSizeCalculationPolicy(cap_to_maximum_volume=False)
    decision = StrategyPositionSizeCalculator(policy).calculate(
        specification_decision_for(
            DirectionalPermissionDirection.BULLISH,
            volume_max=Decimal("0.05"),
        )
    )

    assert decision.is_blocked is True
    assert decision.reason == (PositionSizeCalculationReason.ABOVE_MAXIMUM_VOLUME)
    assert decision.blockers == (PositionSizeCalculationBlocker.ABOVE_MAXIMUM_VOLUME,)


def test_exact_maximum_volume_is_allowed() -> None:
    decision = StrategyPositionSizeCalculator().calculate(
        specification_decision_for(
            DirectionalPermissionDirection.BULLISH,
            volume_max=Decimal("0.10"),
        )
    )

    assert decision.is_calculated is True
    assert decision.normalized_volume == Decimal("0.10")
    assert decision.metrics is not None
    assert decision.metrics.capped_to_maximum is False


def test_larger_tick_size_changes_volume_exactly() -> None:
    decision = StrategyPositionSizeCalculator().calculate(
        specification_decision_for(
            DirectionalPermissionDirection.BULLISH,
            tick_size=Decimal("0.10"),
            tick_value=Decimal("1"),
        )
    )

    assert decision.metrics is not None
    assert decision.metrics.risk_per_volume_unit == (Decimal("100"))
    assert decision.raw_volume == Decimal("1")


def test_decision_preserves_handoff_and_specification() -> None:
    specification_decision = bullish_specification_decision()
    decision = StrategyPositionSizeCalculator().calculate(specification_decision)

    assert decision.specification_decision is specification_decision
    assert decision.handoff is (specification_decision.handoff)
    assert decision.specification is (specification_decision.specification)


def test_decision_preserves_metadata() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.blocker_count == 0


def test_decision_is_explicitly_non_executable() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert decision.is_executable is False
    assert decision.can_continue_to_size_validation is True


@pytest.mark.parametrize(
    "attribute_name",
    [
        "order_type",
        "order_request",
        "broker_ticket",
        "send_order",
        "order_send",
        "position_ticket",
    ],
)
def test_decision_contains_no_execution_output(
    attribute_name: str,
) -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert not hasattr(decision, attribute_name)


@pytest.mark.parametrize(
    "overrides",
    [
        {"risk_per_volume_unit": Decimal("0")},
        {"raw_volume": Decimal("0")},
        {"normalized_volume": Decimal("-1")},
        {"actual_risk_amount": Decimal("-1")},
        {"unused_risk_amount": Decimal("-1")},
        {"risk_utilization_percent": Decimal("-1")},
        {"risk_utilization_percent": Decimal("101")},
        {"capped_to_maximum": 1},
    ],
)
def test_invalid_direct_metrics_are_rejected(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "risk_per_volume_unit": Decimal("1000"),
        "raw_volume": Decimal("0.1"),
        "normalized_volume": Decimal("0.1"),
        "actual_risk_amount": Decimal("100"),
        "unused_risk_amount": Decimal("0"),
        "risk_utilization_percent": Decimal("100"),
        "capped_to_maximum": False,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        PositionSizeMetrics(**values)


def test_metrics_stable_id_is_deterministic() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert decision.metrics is not None
    assert decision.metrics.stable_id == (
        "RISK_PER_VOLUME[1000]:"
        "RAW_VOLUME[0.1]:"
        "NORMALIZED_VOLUME[0.1]:"
        "ACTUAL_RISK[100]:"
        "UNUSED_RISK[0]:"
        "UTILIZATION_PCT[100]:"
        "NOT_CAPPED"
    )


def test_calculated_stable_id_is_deterministic() -> None:
    specification_decision = bullish_specification_decision()
    decision = StrategyPositionSizeCalculator().calculate(specification_decision)

    assert decision.stable_id == (
        f"{specification_decision.stable_id}:"
        "POSITION_SIZE_CALCULATION:"
        "CALCULATED:CALCULATED:NONE:"
        f"{decision.metrics.stable_id}"
    )


def test_equivalent_decimal_scales_share_metric_ids() -> None:
    baseline = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())
    scaled_specification = sizing_specification(
        tick_size=Decimal("0.0100"),
        tick_value=Decimal("1.00"),
        volume_min=Decimal("0.010"),
        volume_max=Decimal("100.00"),
        volume_step=Decimal("0.0100"),
    )
    scaled_decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        scaled_specification,
    )
    scaled = StrategyPositionSizeCalculator().calculate(scaled_decision)

    assert baseline.metrics is not None
    assert scaled.metrics is not None
    assert scaled.metrics.stable_id == baseline.metrics.stable_id
    assert scaled.stable_id == baseline.stable_id


def test_blocked_stable_id_lists_blocker() -> None:
    decision = StrategyPositionSizeCalculator().calculate(blocked_specification_decision())

    assert decision.stable_id.endswith(
        "POSITION_SIZE_CALCULATION:"
        "BLOCKED:SPECIFICATION_BLOCKED:"
        "SPECIFICATION_BLOCKED:NO_SIZE_METRICS"
    )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PositionSizeCalculationStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PositionSizeCalculationReason.BELOW_MINIMUM_VOLUME),
        )


def test_manual_decision_rejects_wrong_metrics() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    assert decision.metrics is not None
    modified_metrics = replace(
        decision.metrics,
        normalized_volume=Decimal("0.09"),
        actual_risk_amount=Decimal("90"),
        unused_risk_amount=Decimal("10"),
        risk_utilization_percent=Decimal("90"),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            metrics=modified_metrics,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPositionSizeCalculator().calculate(
        specification_decision_for(
            DirectionalPermissionDirection.BULLISH,
            tick_value=Decimal("20"),
        )
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PositionSizeCalculationBlocker.BELOW_MINIMUM_VOLUME,
                PositionSizeCalculationBlocker.BELOW_MINIMUM_VOLUME,
            ),
        )


def test_metrics_are_immutable() -> None:
    metrics = StrategyPositionSizeCalculator().calculate(bullish_specification_decision()).metrics

    assert metrics is not None

    with pytest.raises(FrozenInstanceError):
        metrics.normalized_volume = Decimal("0.09")


def test_decision_is_immutable() -> None:
    decision = StrategyPositionSizeCalculator().calculate(bullish_specification_decision())

    with pytest.raises(FrozenInstanceError):
        decision.status = PositionSizeCalculationStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = PositionSizeCalculationPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.cap_to_maximum_volume = False


def test_calculation_is_deterministic() -> None:
    calculator = StrategyPositionSizeCalculator()
    specification_decision = bullish_specification_decision()

    assert calculator.calculate(specification_decision) == calculator.calculate(
        specification_decision
    )


def test_function_api_delegates() -> None:
    decision = calculate_strategy_position_size(bullish_specification_decision())

    assert decision.is_calculated is True


def test_calculator_alias_methods_delegate() -> None:
    calculator = StrategyPositionSizeCalculator()
    specification_decision = bullish_specification_decision()

    assert calculator.evaluate(specification_decision) == calculator.calculate(
        specification_decision
    )
    assert calculator.size(specification_decision) == calculator.calculate(specification_decision)


def test_public_aliases_are_preserved() -> None:
    assert PositionSizeCalculator is StrategyPositionSizeCalculator
    assert PositionSizeDecision is PositionSizeCalculationDecision
    assert PositionSizePolicy is PositionSizeCalculationPolicy
    assert PositionSizeReason is PositionSizeCalculationReason
    assert PositionSizeStatus is PositionSizeCalculationStatus
    assert SizingCalculationBlocker is PositionSizeCalculationBlocker
    assert SizingCalculationDecision is PositionSizeCalculationDecision
    assert SizingCalculationPolicy is PositionSizeCalculationPolicy
    assert SizingCalculationReason is PositionSizeCalculationReason
    assert SizingCalculationStatus is PositionSizeCalculationStatus
    assert SizingMetrics is PositionSizeMetrics
    assert StrategySizingCalculator is StrategyPositionSizeCalculator
