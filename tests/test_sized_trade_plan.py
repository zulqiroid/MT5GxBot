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
    StrategyPositionSizeCalculator,
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
from app.strategy.sized_trade_plan import (
    SizedPositionPlan,
    SizedPositionPlanDecision,
    SizedTradePlan,
    SizedTradePlanBlocker,
    SizedTradePlanDecision,
    SizedTradePlanError,
    SizedTradePlanErrorReason,
    SizedTradePlanFactory,
    SizedTradePlanReason,
    SizedTradePlanStatus,
    StrategySizedTradePlan,
    StrategySizedTradePlanFactory,
    TradePlanBlocker,
    TradePlanDecision,
    TradePlanFactory,
    TradePlanReason,
    TradePlanStatus,
    generate_sized_trade_plan,
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


@lru_cache(maxsize=1)
def bullish_calculation():
    return StrategyPositionSizeCalculator().calculate(bullish_specification_decision())


@lru_cache(maxsize=1)
def bearish_calculation():
    return StrategyPositionSizeCalculator().calculate(bearish_specification_decision())


@lru_cache(maxsize=1)
def blocked_calculation():
    return StrategyPositionSizeCalculator().calculate(blocked_specification_decision())


def test_invalid_position_size_is_fail_safe() -> None:
    with pytest.raises(
        SizedTradePlanError,
        match="INVALID_POSITION_SIZE_DECISION",
    ) as captured:
        StrategySizedTradePlanFactory().generate("invalid")

    assert captured.value.reason == (SizedTradePlanErrorReason.INVALID_POSITION_SIZE_DECISION)


def test_bullish_sized_plan_is_created() -> None:
    decision = StrategySizedTradePlanFactory().generate(bullish_calculation())

    assert decision.status == SizedTradePlanStatus.CREATED
    assert decision.reason == SizedTradePlanReason.CREATED
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_plan is True
    assert decision.plan_required.is_bullish is True


def test_bearish_sized_plan_is_created() -> None:
    decision = StrategySizedTradePlanFactory().generate(bearish_calculation())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.plan_required.is_bearish is True


def test_blocked_calculation_produces_no_plan() -> None:
    decision = StrategySizedTradePlanFactory().generate(blocked_calculation())

    assert decision.is_blocked is True
    assert decision.plan is None
    assert decision.has_plan is False
    assert decision.reason == (SizedTradePlanReason.POSITION_SIZE_BLOCKED)
    assert decision.blockers == (SizedTradePlanBlocker.POSITION_SIZE_BLOCKED,)


def test_plan_required_rejects_blocked_result() -> None:
    decision = StrategySizedTradePlanFactory().generate(blocked_calculation())

    with pytest.raises(
        ValueError,
        match="No sized trade plan",
    ):
        _ = decision.plan_required


def test_plan_preserves_position_size_decision() -> None:
    calculation = bullish_calculation()
    plan = StrategySizedTradePlanFactory().generate(calculation).plan_required

    assert plan.position_size is calculation


def test_plan_preserves_handoff_and_specification() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert plan.handoff is (bullish_calculation().handoff)
    assert plan.specification is (bullish_calculation().specification)


def test_bullish_prices_are_preserved() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert plan.entry_price == Decimal("2350")
    assert plan.stop_loss == Decimal("2340")
    assert plan.take_profit == Decimal("2370")
    assert plan.stop_loss < plan.entry_price < plan.take_profit


def test_bearish_prices_are_preserved() -> None:
    plan = StrategySizedTradePlanFactory().generate(bearish_calculation()).plan_required

    assert plan.entry_price == Decimal("2350")
    assert plan.stop_loss == Decimal("2360")
    assert plan.take_profit == Decimal("2325")
    assert plan.take_profit < plan.entry_price < plan.stop_loss


def test_calculated_volume_is_preserved() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert plan.volume == Decimal("0.10")


def test_risk_values_are_preserved() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert plan.approved_risk_amount == Decimal("100")
    assert plan.actual_risk_amount == Decimal("100")
    assert plan.unused_risk_amount == Decimal("0")
    assert plan.risk_utilization_percent == Decimal("100")


def test_reward_risk_context_is_preserved() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert plan.risk_distance == Decimal("10")
    assert plan.reward_distance == Decimal("20")
    assert plan.reward_risk_ratio == Decimal("2")


def test_plan_preserves_metadata() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert plan.broker_symbol == "XAUUSDm"
    assert plan.observed_at == OBSERVED_AT


def test_plan_volume_matches_broker_step() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    quotient = plan.volume / plan.specification.volume_step

    assert quotient == quotient.to_integral_value()
    assert plan.specification.volume_min <= plan.volume <= plan.specification.volume_max


def test_actual_risk_never_exceeds_approved_risk() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert plan.actual_risk_amount <= plan.approved_risk_amount


def test_plan_is_explicitly_non_executable() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert plan.is_executable is False
    assert plan.has_broker_request is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "order_type",
        "time_in_force",
        "filling_mode",
        "deviation",
        "magic_number",
        "order_request",
        "broker_ticket",
        "send_order",
        "order_send",
    ],
)
def test_plan_contains_no_execution_fields(
    attribute_name: str,
) -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert not hasattr(plan, attribute_name)


def test_plan_id_is_deterministic() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    assert plan.plan_id == (
        "XAUUSDm:BULLISH:"
        "ENTRY[2350]:"
        "STOP[2340]:"
        "TARGET[2370]:"
        "VOLUME[0.1]:"
        "APPROVED_RISK[100]:"
        "ACTUAL_RISK[100]:"
        "UNUSED_RISK[0]:"
        "RR[2]:"
        "UTILIZATION_PCT[100]"
    )


def test_plan_stable_id_is_deterministic() -> None:
    calculation = bullish_calculation()
    plan = StrategySizedTradePlanFactory().generate(calculation).plan_required

    assert plan.stable_id == (f"{calculation.stable_id}:SIZED_TRADE_PLAN:{plan.plan_id}")


def test_created_decision_stable_id_is_deterministic() -> None:
    calculation = bullish_calculation()
    decision = StrategySizedTradePlanFactory().generate(calculation)

    assert decision.stable_id == (
        f"{calculation.stable_id}:SIZED_TRADE_PLAN_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_lists_blocker() -> None:
    decision = StrategySizedTradePlanFactory().generate(blocked_calculation())

    assert decision.stable_id.endswith(
        "SIZED_TRADE_PLAN_GENERATION:BLOCKED:POSITION_SIZE_BLOCKED:POSITION_SIZE_BLOCKED"
    )


def test_equivalent_decimal_scales_share_plan_ids() -> None:
    baseline = StrategySizedTradePlanFactory().generate(bullish_calculation())
    scaled_specification = sizing_specification(
        tick_size=Decimal("0.0100"),
        tick_value=Decimal("1.00"),
        volume_min=Decimal("0.010"),
        volume_max=Decimal("100.00"),
        volume_step=Decimal("0.0100"),
    )
    scaled_specification_decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        scaled_specification,
    )
    scaled_calculation = StrategyPositionSizeCalculator().calculate(scaled_specification_decision)
    scaled = StrategySizedTradePlanFactory().generate(scaled_calculation)

    assert scaled.plan_required.plan_id == baseline.plan_required.plan_id
    assert scaled.stable_id == baseline.stable_id


def test_direct_plan_rejects_blocked_calculation() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    with pytest.raises(
        ValueError,
        match="calculated",
    ):
        replace(
            plan,
            position_size=blocked_calculation(),
        )


def test_direct_plan_rejects_wrong_direction() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        replace(
            plan,
            direction=DirectionalPermissionDirection.BEARISH,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("entry_price", Decimal("2351")),
        ("stop_loss", Decimal("2339")),
        ("take_profit", Decimal("2371")),
        ("volume", Decimal("0.09")),
        ("approved_risk_amount", Decimal("99")),
        ("actual_risk_amount", Decimal("99")),
        ("unused_risk_amount", Decimal("1")),
        ("reward_risk_ratio", Decimal("3")),
        (
            "risk_utilization_percent",
            Decimal("99"),
        ),
    ],
)
def test_direct_plan_rejects_wrong_values(
    field_name: str,
    value: Decimal,
) -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        replace(
            plan,
            **{field_name: value},
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategySizedTradePlanFactory().generate(bullish_calculation())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=SizedTradePlanStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategySizedTradePlanFactory().generate(bullish_calculation())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(SizedTradePlanReason.POSITION_SIZE_BLOCKED),
        )


def test_manual_decision_rejects_missing_plan() -> None:
    decision = StrategySizedTradePlanFactory().generate(bullish_calculation())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            plan=None,
        )


def test_manual_decision_rejects_unexpected_plan() -> None:
    blocked = StrategySizedTradePlanFactory().generate(blocked_calculation())
    created_plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            plan=created_plan,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategySizedTradePlanFactory().generate(blocked_calculation())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                SizedTradePlanBlocker.POSITION_SIZE_BLOCKED,
                SizedTradePlanBlocker.POSITION_SIZE_BLOCKED,
            ),
        )


def test_plan_is_immutable() -> None:
    plan = StrategySizedTradePlanFactory().generate(bullish_calculation()).plan_required

    with pytest.raises(FrozenInstanceError):
        plan.volume = Decimal("0.09")


def test_decision_is_immutable() -> None:
    decision = StrategySizedTradePlanFactory().generate(bullish_calculation())

    with pytest.raises(FrozenInstanceError):
        decision.status = SizedTradePlanStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategySizedTradePlanFactory()
    calculation = bullish_calculation()

    assert factory.generate(calculation) == factory.generate(calculation)


def test_function_api_delegates() -> None:
    decision = generate_sized_trade_plan(bullish_calculation())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategySizedTradePlanFactory()
    calculation = bullish_calculation()

    assert factory.build(calculation) == factory.generate(calculation)
    assert factory.evaluate(calculation) == factory.generate(calculation)


def test_public_aliases_are_preserved() -> None:
    assert SizedPositionPlan is StrategySizedTradePlan
    assert SizedPositionPlanDecision is SizedTradePlanDecision
    assert SizedTradePlan is StrategySizedTradePlan
    assert SizedTradePlanFactory is StrategySizedTradePlanFactory
    assert TradePlanBlocker is SizedTradePlanBlocker
    assert TradePlanDecision is SizedTradePlanDecision
    assert TradePlanFactory is StrategySizedTradePlanFactory
    assert TradePlanReason is SizedTradePlanReason
    assert TradePlanStatus is SizedTradePlanStatus
