from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
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
from app.strategy.position_sizing_handoff import (
    PositionSizingHandoffDecision,
    StrategyPositionSizingHandoffFactory,
)
from app.strategy.position_sizing_specification import (
    BrokerSizingSpecification,
    PositionSizingSpecification,
    PositionSizingSpecificationBlocker,
    PositionSizingSpecificationDecision,
    PositionSizingSpecificationError,
    PositionSizingSpecificationErrorReason,
    PositionSizingSpecificationPolicy,
    PositionSizingSpecificationReason,
    PositionSizingSpecificationStatus,
    SizingSpecification,
    SizingSpecificationBlocker,
    SizingSpecificationDecision,
    SizingSpecificationGate,
    SizingSpecificationPolicy,
    SizingSpecificationReason,
    SizingSpecificationStatus,
    StrategyPositionSizingSpecificationGate,
    evaluate_position_sizing_specification,
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


def test_default_policy_is_strict() -> None:
    policy = PositionSizingSpecificationPolicy()

    assert policy.require_symbol_match is True
    assert policy.require_non_stale_snapshot is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"require_symbol_match": 1},
        {"require_non_stale_snapshot": 1},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        PositionSizingSpecificationPolicy(**overrides)


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PositionSizingSpecificationPolicy",
    ):
        StrategyPositionSizingSpecificationGate(policy="invalid")


def test_invalid_handoff_is_fail_safe() -> None:
    with pytest.raises(
        PositionSizingSpecificationError,
        match="INVALID_HANDOFF_DECISION",
    ) as captured:
        StrategyPositionSizingSpecificationGate().evaluate("invalid")

    assert captured.value.reason == (
        PositionSizingSpecificationErrorReason.INVALID_HANDOFF_DECISION
    )


def test_created_handoff_requires_specification() -> None:
    with pytest.raises(
        PositionSizingSpecificationError,
        match="INVALID_SPECIFICATION",
    ):
        StrategyPositionSizingSpecificationGate().evaluate(bullish_handoff())


def test_invalid_specification_type_is_fail_safe() -> None:
    with pytest.raises(
        PositionSizingSpecificationError,
        match="INVALID_SPECIFICATION",
    ):
        StrategyPositionSizingSpecificationGate().evaluate(
            bullish_handoff(),
            "invalid",
        )


def test_blocked_handoff_needs_no_specification() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(blocked_handoff())

    assert decision.is_blocked is True
    assert decision.specification is None
    assert decision.reason == (PositionSizingSpecificationReason.HANDOFF_BLOCKED)
    assert decision.blockers == (PositionSizingSpecificationBlocker.HANDOFF_BLOCKED,)


def test_bullish_specification_is_ready() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(),
    )

    assert decision.status == (PositionSizingSpecificationStatus.READY)
    assert decision.reason == (PositionSizingSpecificationReason.READY)
    assert decision.blockers == ()
    assert decision.is_ready is True


def test_bearish_specification_is_ready() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bearish_handoff(),
        sizing_specification(),
    )

    assert decision.is_ready is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)


def test_symbol_mismatch_is_fail_safe() -> None:
    with pytest.raises(
        PositionSizingSpecificationError,
        match="broker symbol",
    ):
        StrategyPositionSizingSpecificationGate().evaluate(
            bullish_handoff(),
            sizing_specification(broker_symbol="XAUUSD"),
        )


def test_symbol_mismatch_can_be_allowed() -> None:
    policy = PositionSizingSpecificationPolicy(require_symbol_match=False)

    decision = StrategyPositionSizingSpecificationGate(policy).evaluate(
        bullish_handoff(),
        sizing_specification(broker_symbol="XAUUSD"),
    )

    assert decision.is_ready is True


def test_stale_specification_is_fail_safe() -> None:
    with pytest.raises(
        PositionSizingSpecificationError,
        match="cannot predate",
    ):
        StrategyPositionSizingSpecificationGate().evaluate(
            bullish_handoff(),
            sizing_specification(observed_at=(OBSERVED_AT - timedelta(seconds=1))),
        )


def test_stale_specification_can_be_allowed() -> None:
    policy = PositionSizingSpecificationPolicy(require_non_stale_snapshot=False)

    decision = StrategyPositionSizingSpecificationGate(policy).evaluate(
        bullish_handoff(),
        sizing_specification(observed_at=(OBSERVED_AT - timedelta(seconds=1))),
    )

    assert decision.is_ready is True


def test_same_time_specification_is_ready() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(observed_at=OBSERVED_AT),
    )

    assert decision.is_ready is True


def test_decision_preserves_handoff() -> None:
    handoff = bullish_handoff()
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        handoff,
        sizing_specification(),
    )

    assert decision.handoff_decision is handoff
    assert decision.handoff is handoff.handoff_required


def test_decision_preserves_metadata() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(),
    )

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.blocker_count == 0


def test_specification_value_per_price_unit() -> None:
    specification = sizing_specification(
        tick_size=Decimal("0.01"),
        tick_value=Decimal("1"),
    )

    assert specification.value_per_price_unit == (Decimal("1") / Decimal("0.01"))


def test_specification_points_per_tick() -> None:
    specification = sizing_specification(
        point_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
    )

    assert specification.points_per_tick == Decimal("10")


def test_specification_volume_slot_count() -> None:
    specification = sizing_specification(
        volume_min=Decimal("0.01"),
        volume_max=Decimal("0.05"),
        volume_step=Decimal("0.01"),
    )

    assert specification.volume_slot_count == 5


def test_ready_decision_can_calculate_volume() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(),
    )

    assert decision.can_calculate_volume is True
    assert decision.specification_required is decision.specification


def test_decision_is_explicitly_non_executable() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(),
    )

    assert decision.is_executable is False
    assert decision.specification_required.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "volume",
        "lot_size",
        "normalized_volume",
        "order_request",
        "broker_ticket",
        "send_order",
    ],
)
def test_decision_contains_no_execution_output(
    attribute_name: str,
) -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(),
    )

    assert not hasattr(decision, attribute_name)


@pytest.mark.parametrize(
    "overrides",
    [
        {"observed_at": "invalid"},
        {
            "observed_at": datetime(
                2026,
                7,
                26,
                20,
                0,
            )
        },
        {"broker_symbol": ""},
        {"digits": -1},
        {"digits": True},
        {"point_size": Decimal("0")},
        {"tick_size": Decimal("0")},
        {"tick_value": Decimal("0")},
        {"contract_size": Decimal("0")},
        {"volume_min": Decimal("0")},
        {"volume_max": Decimal("0")},
        {"volume_step": Decimal("0")},
    ],
)
def test_invalid_specification_is_rejected(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "observed_at": OBSERVED_AT,
        "broker_symbol": "XAUUSDm",
        "digits": 2,
        "point_size": Decimal("0.01"),
        "tick_size": Decimal("0.01"),
        "tick_value": Decimal("1"),
        "contract_size": Decimal("100"),
        "volume_min": Decimal("0.01"),
        "volume_max": Decimal("100"),
        "volume_step": Decimal("0.01"),
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        PositionSizingSpecification(**values)


def test_volume_min_cannot_exceed_max() -> None:
    with pytest.raises(
        ValueError,
        match="volume_min",
    ):
        sizing_specification(
            volume_min=Decimal("1"),
            volume_max=Decimal("0.5"),
        )


def test_volume_step_cannot_exceed_max() -> None:
    with pytest.raises(
        ValueError,
        match="volume_step",
    ):
        sizing_specification(
            volume_max=Decimal("0.5"),
            volume_step=Decimal("1"),
        )


def test_volume_min_must_align_with_step() -> None:
    with pytest.raises(
        ValueError,
        match="volume_min",
    ):
        sizing_specification(
            volume_min=Decimal("0.015"),
            volume_step=Decimal("0.01"),
        )


def test_volume_max_must_align_with_step() -> None:
    with pytest.raises(
        ValueError,
        match="volume_max",
    ):
        sizing_specification(
            volume_max=Decimal("100.005"),
            volume_step=Decimal("0.01"),
        )


def test_tick_size_must_align_with_point() -> None:
    with pytest.raises(
        ValueError,
        match="tick_size",
    ):
        sizing_specification(
            point_size=Decimal("0.03"),
            tick_size=Decimal("0.05"),
        )


def test_specification_stable_id_is_deterministic() -> None:
    specification = sizing_specification()

    assert specification.stable_id == (
        f"{OBSERVED_AT.isoformat()}:"
        "XAUUSDm:"
        "DIGITS[2]:"
        "POINT[0.01]:"
        "TICK_SIZE[0.01]:"
        "TICK_VALUE[1]:"
        "CONTRACT[100]:"
        "VOLUME_MIN[0.01]:"
        "VOLUME_MAX[100]:"
        "VOLUME_STEP[0.01]"
    )


def test_equivalent_decimal_scales_share_spec_id() -> None:
    baseline = sizing_specification()
    scaled = sizing_specification(
        point_size=Decimal("0.010"),
        tick_size=Decimal("0.0100"),
        tick_value=Decimal("1.00"),
        contract_size=Decimal("100.00"),
        volume_min=Decimal("0.010"),
        volume_max=Decimal("100.00"),
        volume_step=Decimal("0.0100"),
    )

    assert scaled.stable_id == baseline.stable_id


def test_ready_decision_stable_id_is_deterministic() -> None:
    handoff = bullish_handoff()
    specification = sizing_specification()
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        handoff,
        specification,
    )

    assert decision.stable_id == (
        f"{handoff.stable_id}:"
        "POSITION_SIZING_SPECIFICATION:"
        "READY:READY:NONE:"
        f"{specification.stable_id}"
    )


def test_blocked_decision_stable_id_lists_blocker() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(blocked_handoff())

    assert decision.stable_id.endswith(
        "POSITION_SIZING_SPECIFICATION:BLOCKED:HANDOFF_BLOCKED:HANDOFF_BLOCKED:NO_SPECIFICATION"
    )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PositionSizingSpecificationStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PositionSizingSpecificationReason.HANDOFF_BLOCKED),
        )


def test_manual_decision_rejects_missing_specification() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(),
    )

    with pytest.raises(
        PositionSizingSpecificationError,
        match="INVALID_SPECIFICATION",
    ):
        replace(
            decision,
            specification=None,
        )


def test_manual_blocked_decision_rejects_specification() -> None:
    blocked = StrategyPositionSizingSpecificationGate().evaluate(blocked_handoff())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            specification=sizing_specification(),
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(blocked_handoff())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PositionSizingSpecificationBlocker.HANDOFF_BLOCKED,
                PositionSizingSpecificationBlocker.HANDOFF_BLOCKED,
            ),
        )


def test_specification_is_immutable() -> None:
    specification = sizing_specification()

    with pytest.raises(FrozenInstanceError):
        specification.tick_value = Decimal("2")


def test_decision_is_immutable() -> None:
    decision = StrategyPositionSizingSpecificationGate().evaluate(
        bullish_handoff(),
        sizing_specification(),
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PositionSizingSpecificationStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = PositionSizingSpecificationPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.require_symbol_match = False


def test_evaluation_is_deterministic() -> None:
    gate = StrategyPositionSizingSpecificationGate()
    handoff = bullish_handoff()
    specification = sizing_specification()

    assert gate.evaluate(
        handoff,
        specification,
    ) == gate.evaluate(
        handoff,
        specification,
    )


def test_function_api_delegates() -> None:
    decision = evaluate_position_sizing_specification(
        bullish_handoff(),
        sizing_specification(),
    )

    assert decision.is_ready is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategyPositionSizingSpecificationGate()
    handoff = bullish_handoff()
    specification = sizing_specification()

    assert gate.assess(
        handoff,
        specification,
    ) == gate.evaluate(
        handoff,
        specification,
    )
    assert gate.check(
        handoff,
        specification,
    ) == gate.evaluate(
        handoff,
        specification,
    )


def test_public_aliases_are_preserved() -> None:
    assert BrokerSizingSpecification is PositionSizingSpecification
    assert SizingSpecification is PositionSizingSpecification
    assert SizingSpecificationBlocker is PositionSizingSpecificationBlocker
    assert SizingSpecificationDecision is PositionSizingSpecificationDecision
    assert SizingSpecificationGate is StrategyPositionSizingSpecificationGate
    assert SizingSpecificationPolicy is PositionSizingSpecificationPolicy
    assert SizingSpecificationReason is PositionSizingSpecificationReason
    assert SizingSpecificationStatus is PositionSizingSpecificationStatus
