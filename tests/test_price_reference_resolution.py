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
from app.strategy.price_planning_admission import (
    StrategyPricePlanningAdmissionGate,
)
from app.strategy.price_planning_blueprint import (
    StrategyPricePlanningBlueprintFactory,
)
from app.strategy.price_reference_availability import (
    PriceReferenceAvailabilityDecision,
    PriceReferenceAvailabilityItem,
    PriceReferenceAvailabilityPolicy,
    PriceReferenceAvailabilitySnapshot,
    StrategyPriceReferenceAvailabilityGate,
)
from app.strategy.price_reference_plan import (
    PriceReferencePlanDecision,
    PriceReferenceRole,
    StrategyPriceReferencePlanFactory,
)
from app.strategy.price_reference_resolution import (
    PriceReferenceResolutionBlocker,
    PriceReferenceResolutionDecision,
    PriceReferenceResolutionError,
    PriceReferenceResolutionErrorReason,
    PriceReferenceResolutionPolicy,
    PriceReferenceResolutionReason,
    PriceReferenceResolutionStatus,
    PriceReferenceValueObservation,
    PriceReferenceValueSnapshot,
    ReferenceResolutionBlocker,
    ReferenceResolutionDecision,
    ReferenceResolutionGate,
    ReferenceResolutionPolicy,
    ReferenceResolutionReason,
    ReferenceResolutionStatus,
    ReferenceValueObservation,
    ReferenceValueSnapshot,
    StrategyPriceReferenceResolutionGate,
    evaluate_price_reference_resolution,
)
from app.strategy.setup_candidate import (
    StrategySetupCandidateFactory,
)
from app.strategy.setup_candidate_quality import (
    SetupCandidateQualityPolicy,
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


def plan_decision_for(
    direction: DirectionalPermissionDirection,
    *,
    upstream_blocked: bool = False,
) -> PriceReferencePlanDecision:
    if direction == DirectionalPermissionDirection.BULLISH:
        selected_bias = MarketStructureBias.BULLISH
    elif direction == DirectionalPermissionDirection.BEARISH:
        selected_bias = MarketStructureBias.BEARISH
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
    quality_policy = (
        SetupCandidateQualityPolicy(minimum_score=Decimal("43"))
        if upstream_blocked
        else SetupCandidateQualityPolicy()
    )
    quality = StrategySetupCandidateQualityGate(quality_policy).evaluate(candidate)
    admission = StrategyPricePlanningAdmissionGate().evaluate(quality)
    blueprint = StrategyPricePlanningBlueprintFactory().generate(admission)

    return StrategyPriceReferencePlanFactory().generate(blueprint)


@lru_cache(maxsize=1)
def bullish_plan_decision() -> PriceReferencePlanDecision:
    return plan_decision_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_plan_decision() -> PriceReferencePlanDecision:
    return plan_decision_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_plan_decision() -> PriceReferencePlanDecision:
    return plan_decision_for(
        DirectionalPermissionDirection.BULLISH,
        upstream_blocked=True,
    )


def availability_decision(
    plan_decision: PriceReferencePlanDecision,
    *,
    unavailable_roles: tuple[PriceReferenceRole, ...] = (),
    policy: PriceReferenceAvailabilityPolicy | None = None,
) -> PriceReferenceAvailabilityDecision:
    if plan_decision.is_blocked:
        return StrategyPriceReferenceAvailabilityGate(policy).evaluate(plan_decision)

    plan = plan_decision.plan_required
    snapshot = PriceReferenceAvailabilitySnapshot(
        plan=plan,
        items=tuple(
            PriceReferenceAvailabilityItem(
                requirement=requirement,
                available=(requirement.role not in unavailable_roles),
            )
            for requirement in plan.requirements
        ),
    )

    return StrategyPriceReferenceAvailabilityGate(policy).evaluate(
        plan_decision,
        snapshot,
    )


@lru_cache(maxsize=1)
def bullish_availability() -> PriceReferenceAvailabilityDecision:
    return availability_decision(bullish_plan_decision())


@lru_cache(maxsize=1)
def bearish_availability() -> PriceReferenceAvailabilityDecision:
    return availability_decision(bearish_plan_decision())


@lru_cache(maxsize=1)
def blocked_availability() -> PriceReferenceAvailabilityDecision:
    return availability_decision(blocked_plan_decision())


def value_snapshot(
    decision: PriceReferenceAvailabilityDecision,
    *,
    entry_value: Decimal | None,
    stop_value: Decimal | None,
    target_value: Decimal | None,
    include_non_selected: bool = False,
) -> PriceReferenceValueSnapshot:
    plan = decision.plan

    if plan is None:
        raise ValueError("Decision has no plan.")

    values = {
        PriceReferenceRole.ENTRY: entry_value,
        PriceReferenceRole.STOP: stop_value,
        PriceReferenceRole.TARGET: target_value,
    }
    selected = {
        decision.selected_entry,
        decision.selected_stop,
        decision.selected_target,
    }
    observations: list[PriceReferenceValueObservation] = []

    for requirement in plan.requirements:
        value = values[requirement.role]

        if value is None:
            continue

        if include_non_selected or requirement in selected:
            observations.append(
                PriceReferenceValueObservation(
                    requirement=requirement,
                    value=value,
                )
            )

    return PriceReferenceValueSnapshot(
        plan=plan,
        observations=tuple(observations),
    )


def test_default_policy_validates_directional_order() -> None:
    assert PriceReferenceResolutionPolicy().validate_directional_order is True


def test_policy_requires_strict_boolean() -> None:
    with pytest.raises(ValueError):
        PriceReferenceResolutionPolicy(validate_directional_order=1)


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PriceReferenceResolutionPolicy",
    ):
        StrategyPriceReferenceResolutionGate(policy="invalid")


def test_invalid_availability_decision_is_fail_safe() -> None:
    with pytest.raises(
        PriceReferenceResolutionError,
        match="INVALID_AVAILABILITY_DECISION",
    ) as captured:
        StrategyPriceReferenceResolutionGate().evaluate("invalid")

    assert captured.value.reason == (
        PriceReferenceResolutionErrorReason.INVALID_AVAILABILITY_DECISION
    )


def test_invalid_snapshot_type_is_fail_safe() -> None:
    with pytest.raises(
        PriceReferenceResolutionError,
        match="INVALID_OBSERVATIONS",
    ):
        StrategyPriceReferenceResolutionGate().evaluate(
            bullish_availability(),
            "invalid",
        )


def test_ready_availability_requires_snapshot() -> None:
    with pytest.raises(
        PriceReferenceResolutionError,
        match="INVALID_OBSERVATIONS",
    ):
        StrategyPriceReferenceResolutionGate().evaluate(bullish_availability())


def test_blocked_availability_needs_no_snapshot() -> None:
    decision = StrategyPriceReferenceResolutionGate().evaluate(blocked_availability())

    assert decision.is_blocked is True
    assert decision.observations is None
    assert decision.reason == (PriceReferenceResolutionReason.AVAILABILITY_BLOCKED)
    assert decision.blockers == (PriceReferenceResolutionBlocker.AVAILABILITY_BLOCKED,)


def test_bullish_values_are_resolved() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )

    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.status == (PriceReferenceResolutionStatus.RESOLVED)
    assert decision.reason == (PriceReferenceResolutionReason.RESOLVED)
    assert decision.blockers == ()
    assert decision.is_resolved is True


def test_bearish_values_are_resolved() -> None:
    availability = bearish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2360"),
        target_value=Decimal("2325"),
    )

    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.is_resolved is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)


def test_values_are_preserved_exactly() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350.25"),
        stop_value=Decimal("2341.10"),
        target_value=Decimal("2375.75"),
    )
    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.entry_value == Decimal("2350.25")
    assert decision.stop_value == Decimal("2341.10")
    assert decision.target_value == Decimal("2375.75")
    assert decision.has_entry_value is True
    assert decision.has_stop_value is True
    assert decision.has_target_value is True


def test_missing_entry_value_blocks() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=None,
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )
    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.reason == (PriceReferenceResolutionReason.ENTRY_VALUE_MISSING)
    assert decision.blockers == (PriceReferenceResolutionBlocker.ENTRY_VALUE_MISSING,)


def test_missing_stop_value_blocks() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=None,
        target_value=Decimal("2370"),
    )
    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.reason == (PriceReferenceResolutionReason.STOP_VALUE_MISSING)


def test_missing_target_value_blocks() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=None,
    )
    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.reason == (PriceReferenceResolutionReason.TARGET_VALUE_MISSING)


def test_multiple_missing_values_preserve_order() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=None,
        stop_value=None,
        target_value=None,
    )
    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.reason == (PriceReferenceResolutionReason.MULTIPLE_VALUES_MISSING)
    assert decision.blockers == (
        PriceReferenceResolutionBlocker.ENTRY_VALUE_MISSING,
        PriceReferenceResolutionBlocker.STOP_VALUE_MISSING,
        PriceReferenceResolutionBlocker.TARGET_VALUE_MISSING,
    )


@pytest.mark.parametrize(
    ("entry_value", "stop_value", "target_value"),
    [
        (
            Decimal("2350"),
            Decimal("2350"),
            Decimal("2370"),
        ),
        (
            Decimal("2350"),
            Decimal("2360"),
            Decimal("2370"),
        ),
        (
            Decimal("2350"),
            Decimal("2340"),
            Decimal("2350"),
        ),
        (
            Decimal("2350"),
            Decimal("2340"),
            Decimal("2330"),
        ),
    ],
)
def test_invalid_bullish_order_blocks(
    entry_value: Decimal,
    stop_value: Decimal,
    target_value: Decimal,
) -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=entry_value,
        stop_value=stop_value,
        target_value=target_value,
    )
    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.reason == (PriceReferenceResolutionReason.DIRECTIONAL_ORDER_INVALID)
    assert decision.blockers == (PriceReferenceResolutionBlocker.DIRECTIONAL_ORDER_INVALID,)


@pytest.mark.parametrize(
    ("entry_value", "stop_value", "target_value"),
    [
        (
            Decimal("2350"),
            Decimal("2350"),
            Decimal("2325"),
        ),
        (
            Decimal("2350"),
            Decimal("2340"),
            Decimal("2325"),
        ),
        (
            Decimal("2350"),
            Decimal("2360"),
            Decimal("2350"),
        ),
        (
            Decimal("2350"),
            Decimal("2360"),
            Decimal("2370"),
        ),
    ],
)
def test_invalid_bearish_order_blocks(
    entry_value: Decimal,
    stop_value: Decimal,
    target_value: Decimal,
) -> None:
    availability = bearish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=entry_value,
        stop_value=stop_value,
        target_value=target_value,
    )
    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.is_blocked is True
    assert decision.reason == (PriceReferenceResolutionReason.DIRECTIONAL_ORDER_INVALID)


def test_directional_validation_can_be_disabled() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2360"),
        target_value=Decimal("2340"),
    )
    policy = PriceReferenceResolutionPolicy(validate_directional_order=False)

    decision = StrategyPriceReferenceResolutionGate(policy).evaluate(availability, snapshot)

    assert decision.is_resolved is True


def test_waived_entry_role_needs_no_entry_value() -> None:
    plan_decision = bullish_plan_decision()
    availability = availability_decision(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.ENTRY,),
        policy=PriceReferenceAvailabilityPolicy(require_entry_reference=False),
    )
    snapshot = value_snapshot(
        availability,
        entry_value=None,
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )

    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.is_resolved is True
    assert decision.entry_value is None


def test_waived_stop_role_needs_no_stop_value() -> None:
    plan_decision = bullish_plan_decision()
    availability = availability_decision(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.STOP,),
        policy=PriceReferenceAvailabilityPolicy(require_stop_reference=False),
    )
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=None,
        target_value=Decimal("2370"),
    )

    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.is_resolved is True
    assert decision.stop_value is None


def test_waived_target_role_needs_no_target_value() -> None:
    plan_decision = bullish_plan_decision()
    availability = availability_decision(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.TARGET,),
        policy=PriceReferenceAvailabilityPolicy(require_target_reference=False),
    )
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=None,
    )

    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.is_resolved is True
    assert decision.target_value is None


@pytest.mark.parametrize(
    "value",
    [
        2350,
        "2350",
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_observation_rejects_invalid_value(
    value: object,
) -> None:
    requirement = bullish_availability().selected_entry

    assert requirement is not None

    with pytest.raises(ValueError):
        PriceReferenceValueObservation(
            requirement=requirement,
            value=value,
        )


def test_observation_requires_requirement_type() -> None:
    with pytest.raises(
        ValueError,
        match="PriceReferenceRequirement",
    ):
        PriceReferenceValueObservation(
            requirement="invalid",
            value=Decimal("2350"),
        )


def test_snapshot_rejects_non_tuple_observations() -> None:
    plan = bullish_availability().plan

    assert plan is not None

    with pytest.raises(ValueError):
        PriceReferenceValueSnapshot(
            plan=plan,
            observations=[],
        )


def test_snapshot_rejects_duplicate_requirements() -> None:
    availability = bullish_availability()
    requirement = availability.selected_entry
    plan = availability.plan

    assert requirement is not None
    assert plan is not None

    observation = PriceReferenceValueObservation(
        requirement=requirement,
        value=Decimal("2350"),
    )

    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        PriceReferenceValueSnapshot(
            plan=plan,
            observations=(
                observation,
                observation,
            ),
        )


def test_snapshot_rejects_foreign_requirement() -> None:
    bullish_plan = bullish_availability().plan
    bearish_requirement = bearish_availability().selected_entry

    assert bullish_plan is not None
    assert bearish_requirement is not None

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        PriceReferenceValueSnapshot(
            plan=bullish_plan,
            observations=(
                PriceReferenceValueObservation(
                    requirement=bearish_requirement,
                    value=Decimal("2350"),
                ),
            ),
        )


def test_gate_rejects_foreign_snapshot() -> None:
    bullish = bullish_availability()
    bearish = bearish_availability()
    snapshot = value_snapshot(
        bearish,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2360"),
        target_value=Decimal("2325"),
    )

    with pytest.raises(
        PriceReferenceResolutionError,
        match="does not reference",
    ):
        StrategyPriceReferenceResolutionGate().evaluate(
            bullish,
            snapshot,
        )


def test_snapshot_lookup_methods() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )
    entry = availability.selected_entry

    assert entry is not None
    assert snapshot.value_for(entry) == Decimal("2350")
    assert snapshot.observation_for(entry) is not None


def test_snapshot_lookup_rejects_invalid_requirement() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )

    with pytest.raises(ValueError):
        snapshot.value_for("invalid")


def test_non_selected_observations_are_allowed() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
        include_non_selected=True,
    )

    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.is_resolved is True
    assert len(snapshot.observations) == len(snapshot.plan.requirements)


def test_decision_preserves_metadata() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )
    decision = StrategyPriceReferenceResolutionGate().evaluate(availability, snapshot)

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.blocker_count == 0


def test_decision_is_explicitly_non_executable() -> None:
    availability = bullish_availability()
    decision = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        value_snapshot(
            availability,
            entry_value=Decimal("2350"),
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
        ),
    )

    assert decision.is_executable is False
    assert decision.can_continue_to_reward_risk_analysis is True


@pytest.mark.parametrize(
    "attribute_name",
    [
        "volume",
        "lot_size",
        "risk_amount",
        "order_type",
        "order_request",
        "broker_ticket",
    ],
)
def test_decision_contains_no_execution_fields(
    attribute_name: str,
) -> None:
    availability = bullish_availability()
    decision = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        value_snapshot(
            availability,
            entry_value=Decimal("2350"),
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
        ),
    )

    assert not hasattr(decision, attribute_name)


def test_observation_stable_id_is_deterministic() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )
    observation = snapshot.observations[0]

    assert observation.stable_id == (
        f"{observation.requirement.stable_id}:VALUE[{observation.value}]"
    )


def test_snapshot_stable_id_is_deterministic() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )

    assert snapshot.stable_id.startswith(snapshot.plan.stable_id)
    assert "REFERENCE_VALUES:" in snapshot.stable_id


def test_resolved_stable_id_is_deterministic() -> None:
    availability = bullish_availability()
    decision = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        value_snapshot(
            availability,
            entry_value=Decimal("2350"),
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
        ),
    )

    assert decision.stable_id.endswith("REFERENCE_RESOLUTION:RESOLVED:RESOLVED:NONE:2350:2340:2370")


def test_blocked_stable_id_lists_blocker() -> None:
    availability = bullish_availability()
    decision = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        value_snapshot(
            availability,
            entry_value=None,
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
        ),
    )

    assert "ENTRY_VALUE_MISSING" in decision.stable_id


def test_manual_decision_rejects_wrong_status() -> None:
    availability = bullish_availability()
    decision = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        value_snapshot(
            availability,
            entry_value=Decimal("2350"),
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
        ),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PriceReferenceResolutionStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_value() -> None:
    availability = bullish_availability()
    decision = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        value_snapshot(
            availability,
            entry_value=Decimal("2350"),
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
        ),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            entry_value=Decimal("2351"),
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    availability = bullish_availability()
    decision = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        value_snapshot(
            availability,
            entry_value=None,
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
        ),
    )

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PriceReferenceResolutionBlocker.ENTRY_VALUE_MISSING,
                PriceReferenceResolutionBlocker.ENTRY_VALUE_MISSING,
            ),
        )


def test_observation_is_immutable() -> None:
    availability = bullish_availability()
    requirement = availability.selected_entry

    assert requirement is not None

    observation = PriceReferenceValueObservation(
        requirement=requirement,
        value=Decimal("2350"),
    )

    with pytest.raises(FrozenInstanceError):
        observation.value = Decimal("2351")


def test_snapshot_is_immutable() -> None:
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.observations = ()


def test_decision_is_immutable() -> None:
    availability = bullish_availability()
    decision = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        value_snapshot(
            availability,
            entry_value=Decimal("2350"),
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
        ),
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PriceReferenceResolutionStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = PriceReferenceResolutionPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.validate_directional_order = False


def test_evaluation_is_deterministic() -> None:
    gate = StrategyPriceReferenceResolutionGate()
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )

    assert gate.evaluate(
        availability,
        snapshot,
    ) == gate.evaluate(
        availability,
        snapshot,
    )


def test_function_api_delegates() -> None:
    availability = bullish_availability()
    decision = evaluate_price_reference_resolution(
        availability,
        value_snapshot(
            availability,
            entry_value=Decimal("2350"),
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
        ),
    )

    assert decision.is_resolved is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategyPriceReferenceResolutionGate()
    availability = bullish_availability()
    snapshot = value_snapshot(
        availability,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )

    assert gate.resolve(
        availability,
        snapshot,
    ) == gate.evaluate(
        availability,
        snapshot,
    )
    assert gate.check(
        availability,
        snapshot,
    ) == gate.evaluate(
        availability,
        snapshot,
    )


def test_public_aliases_are_preserved() -> None:
    assert ReferenceResolutionBlocker is PriceReferenceResolutionBlocker
    assert ReferenceResolutionDecision is PriceReferenceResolutionDecision
    assert ReferenceResolutionGate is StrategyPriceReferenceResolutionGate
    assert ReferenceResolutionPolicy is PriceReferenceResolutionPolicy
    assert ReferenceResolutionReason is PriceReferenceResolutionReason
    assert ReferenceResolutionStatus is PriceReferenceResolutionStatus
    assert ReferenceValueObservation is PriceReferenceValueObservation
    assert ReferenceValueSnapshot is PriceReferenceValueSnapshot
