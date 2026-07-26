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
from app.strategy.position_sizing_handoff import (
    PositionSizingHandoff,
    PositionSizingHandoffBlocker,
    PositionSizingHandoffDecision,
    PositionSizingHandoffError,
    PositionSizingHandoffErrorReason,
    PositionSizingHandoffFactory,
    PositionSizingHandoffReason,
    PositionSizingHandoffStatus,
    SizingHandoff,
    SizingHandoffBlocker,
    SizingHandoffDecision,
    SizingHandoffFactory,
    SizingHandoffReason,
    SizingHandoffStatus,
    StrategyPositionSizingHandoff,
    StrategyPositionSizingHandoffFactory,
    generate_position_sizing_handoff,
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
    RiskBudgetAdmissionDecision,
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


def risk_admission_for(
    direction: DirectionalPermissionDirection,
    *,
    blocked: bool = False,
    decimal_scale: bool = False,
) -> RiskBudgetAdmissionDecision:
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
    blueprint_decision = StrategyPricePlanningBlueprintFactory().generate(admission)
    plan_decision = StrategyPriceReferencePlanFactory().generate(blueprint_decision)
    plan = plan_decision.plan_required
    availability_snapshot = PriceReferenceAvailabilitySnapshot(
        plan=plan,
        items=tuple(
            PriceReferenceAvailabilityItem(
                requirement=requirement,
                available=True,
            )
            for requirement in plan.requirements
        ),
    )
    availability = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        availability_snapshot,
    )
    role_values = {
        PriceReferenceRole.ENTRY: entry_value,
        PriceReferenceRole.STOP: stop_value,
        PriceReferenceRole.TARGET: target_value,
    }
    observations = tuple(
        PriceReferenceValueObservation(
            requirement=requirement,
            value=role_values[requirement.role],
        )
        for requirement in (
            availability.selected_entry,
            availability.selected_stop,
            availability.selected_target,
        )
        if requirement is not None
    )
    resolution = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        PriceReferenceValueSnapshot(
            plan=plan,
            observations=observations,
        ),
    )
    reward_risk = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    scale = Decimal("1.00") if decimal_scale else Decimal("1")

    snapshot = StrategyRiskBudgetSnapshot(
        observed_at=OBSERVED_AT,
        account_equity=Decimal("10000") * scale,
        proposed_risk_amount=Decimal("100") * scale,
        current_aggregate_risk_amount=Decimal("0") * scale,
        realized_daily_loss_amount=Decimal("0") * scale,
        open_gold_positions=0,
        kill_switch_active=blocked,
    )

    return StrategyRiskBudgetAdmissionGate().evaluate(
        reward_risk,
        snapshot,
    )


@lru_cache(maxsize=1)
def bullish_admission() -> RiskBudgetAdmissionDecision:
    return risk_admission_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_admission() -> RiskBudgetAdmissionDecision:
    return risk_admission_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_admission() -> RiskBudgetAdmissionDecision:
    return risk_admission_for(
        DirectionalPermissionDirection.BULLISH,
        blocked=True,
    )


def test_invalid_risk_admission_is_fail_safe() -> None:
    with pytest.raises(
        PositionSizingHandoffError,
        match="INVALID_RISK_ADMISSION",
    ) as captured:
        StrategyPositionSizingHandoffFactory().generate("invalid")

    assert captured.value.reason == (PositionSizingHandoffErrorReason.INVALID_RISK_ADMISSION)


def test_bullish_handoff_is_created() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(bullish_admission())

    assert decision.status == (PositionSizingHandoffStatus.CREATED)
    assert decision.reason == (PositionSizingHandoffReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_handoff is True
    assert decision.handoff_required.is_bullish is True


def test_bearish_handoff_is_created() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(bearish_admission())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.handoff_required.is_bearish is True


def test_blocked_admission_produces_no_handoff() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(blocked_admission())

    assert decision.is_blocked is True
    assert decision.handoff is None
    assert decision.has_handoff is False
    assert decision.reason == (PositionSizingHandoffReason.RISK_BUDGET_BLOCKED)
    assert decision.blockers == (PositionSizingHandoffBlocker.RISK_BUDGET_BLOCKED,)


def test_handoff_required_rejects_blocked_result() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(blocked_admission())

    with pytest.raises(
        ValueError,
        match="No position-sizing handoff",
    ):
        _ = decision.handoff_required


def test_handoff_preserves_risk_admission() -> None:
    risk_admission = bullish_admission()
    handoff = StrategyPositionSizingHandoffFactory().generate(risk_admission).handoff_required

    assert handoff.risk_admission is risk_admission


def test_handoff_preserves_metadata() -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    assert handoff.broker_symbol == "XAUUSDm"
    assert handoff.observed_at == OBSERVED_AT
    assert handoff.account_equity == Decimal("10000")


def test_handoff_preserves_approved_risk() -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    assert handoff.approved_risk_amount == Decimal("100")


def test_handoff_preserves_price_context() -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    assert handoff.entry_value == Decimal("2350")
    assert handoff.stop_value == Decimal("2340")
    assert handoff.target_value == Decimal("2370")


def test_handoff_preserves_reward_risk_context() -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    assert handoff.risk_distance == Decimal("10")
    assert handoff.reward_distance == Decimal("20")
    assert handoff.reward_risk_ratio == Decimal("2")


def test_handoff_is_explicitly_non_executable() -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    assert handoff.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "volume",
        "lot_size",
        "normalized_volume",
        "tick_value",
        "tick_size",
        "volume_step",
        "order_request",
        "broker_ticket",
    ],
)
def test_handoff_contains_no_sizing_or_execution_output(
    attribute_name: str,
) -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    assert not hasattr(handoff, attribute_name)


def test_handoff_id_is_deterministic() -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    assert handoff.handoff_id == (
        "XAUUSDm:BULLISH:"
        "RISK_AMOUNT[100]:"
        "ENTRY[2350]:"
        "STOP[2340]:"
        "TARGET[2370]:"
        "RISK_DISTANCE[10]:"
        "REWARD_DISTANCE[20]:"
        "RR[2]"
    )


def test_handoff_stable_id_is_deterministic() -> None:
    risk_admission = bullish_admission()
    handoff = StrategyPositionSizingHandoffFactory().generate(risk_admission).handoff_required

    assert handoff.stable_id == (
        f"{risk_admission.stable_id}:POSITION_SIZING_HANDOFF:{handoff.handoff_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    risk_admission = bullish_admission()
    decision = StrategyPositionSizingHandoffFactory().generate(risk_admission)

    assert decision.stable_id == (
        f"{risk_admission.stable_id}:POSITION_SIZING_HANDOFF_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_lists_blocker() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(blocked_admission())

    assert decision.stable_id.endswith(
        "POSITION_SIZING_HANDOFF_GENERATION:BLOCKED:RISK_BUDGET_BLOCKED:RISK_BUDGET_BLOCKED"
    )


def test_equivalent_decimal_scales_share_ids() -> None:
    baseline = StrategyPositionSizingHandoffFactory().generate(bullish_admission())
    scaled = StrategyPositionSizingHandoffFactory().generate(
        risk_admission_for(
            DirectionalPermissionDirection.BULLISH,
            decimal_scale=True,
        )
    )

    assert scaled.handoff_required.handoff_id == baseline.handoff_required.handoff_id
    assert scaled.stable_id == baseline.stable_id


def test_direct_handoff_rejects_blocked_admission() -> None:
    admitted = bullish_admission()
    baseline = StrategyPositionSizingHandoffFactory().generate(admitted).handoff_required

    with pytest.raises(
        ValueError,
        match="admitted",
    ):
        replace(
            baseline,
            risk_admission=blocked_admission(),
        )


def test_direct_handoff_rejects_wrong_risk_amount() -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    with pytest.raises(
        ValueError,
        match="approved_risk_amount",
    ):
        replace(
            handoff,
            approved_risk_amount=Decimal("99"),
        )


def test_direct_handoff_rejects_wrong_direction() -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        replace(
            handoff,
            direction=DirectionalPermissionDirection.BEARISH,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("entry_value", Decimal("2351")),
        ("stop_value", Decimal("2339")),
        ("target_value", Decimal("2371")),
        ("risk_distance", Decimal("11")),
        ("reward_distance", Decimal("21")),
        ("reward_risk_ratio", Decimal("3")),
    ],
)
def test_direct_handoff_rejects_wrong_analysis_values(
    field_name: str,
    value: Decimal,
) -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        replace(
            handoff,
            **{field_name: value},
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(bullish_admission())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PositionSizingHandoffStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(bullish_admission())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PositionSizingHandoffReason.RISK_BUDGET_BLOCKED),
        )


def test_manual_decision_rejects_missing_handoff() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(bullish_admission())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            handoff=None,
        )


def test_manual_decision_rejects_unexpected_handoff() -> None:
    blocked = StrategyPositionSizingHandoffFactory().generate(blocked_admission())
    created_handoff = (
        StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            handoff=created_handoff,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(blocked_admission())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PositionSizingHandoffBlocker.RISK_BUDGET_BLOCKED,
                PositionSizingHandoffBlocker.RISK_BUDGET_BLOCKED,
            ),
        )


def test_handoff_is_immutable() -> None:
    handoff = StrategyPositionSizingHandoffFactory().generate(bullish_admission()).handoff_required

    with pytest.raises(FrozenInstanceError):
        handoff.approved_risk_amount = Decimal("50")


def test_decision_is_immutable() -> None:
    decision = StrategyPositionSizingHandoffFactory().generate(bullish_admission())

    with pytest.raises(FrozenInstanceError):
        decision.status = PositionSizingHandoffStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPositionSizingHandoffFactory()
    risk_admission = bullish_admission()

    assert factory.generate(risk_admission) == factory.generate(risk_admission)


def test_function_api_delegates() -> None:
    decision = generate_position_sizing_handoff(bullish_admission())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPositionSizingHandoffFactory()
    risk_admission = bullish_admission()

    assert factory.build(risk_admission) == factory.generate(risk_admission)
    assert factory.evaluate(risk_admission) == factory.generate(risk_admission)


def test_public_aliases_are_preserved() -> None:
    assert PositionSizingHandoff is StrategyPositionSizingHandoff
    assert PositionSizingHandoffFactory is StrategyPositionSizingHandoffFactory
    assert SizingHandoff is StrategyPositionSizingHandoff
    assert SizingHandoffBlocker is PositionSizingHandoffBlocker
    assert SizingHandoffDecision is PositionSizingHandoffDecision
    assert SizingHandoffFactory is StrategyPositionSizingHandoffFactory
    assert SizingHandoffReason is PositionSizingHandoffReason
    assert SizingHandoffStatus is PositionSizingHandoffStatus
