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
    PriceReferenceAvailabilityBlocker,
    PriceReferenceAvailabilityDecision,
    PriceReferenceAvailabilityError,
    PriceReferenceAvailabilityErrorReason,
    PriceReferenceAvailabilityItem,
    PriceReferenceAvailabilityPolicy,
    PriceReferenceAvailabilityReason,
    PriceReferenceAvailabilitySnapshot,
    PriceReferenceAvailabilityStatus,
    ReferenceAvailabilityBlocker,
    ReferenceAvailabilityDecision,
    ReferenceAvailabilityGate,
    ReferenceAvailabilityItem,
    ReferenceAvailabilityPolicy,
    ReferenceAvailabilityReason,
    ReferenceAvailabilitySnapshot,
    ReferenceAvailabilityStatus,
    StrategyPriceReferenceAvailabilityGate,
    evaluate_price_reference_availability,
)
from app.strategy.price_reference_plan import (
    PriceReferencePlanDecision,
    PriceReferenceRole,
    StrategyPriceReferencePlanFactory,
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
    blocked: bool = False,
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
        if blocked
        else SetupCandidateQualityPolicy()
    )
    quality = StrategySetupCandidateQualityGate(quality_policy).evaluate(candidate)
    admission = StrategyPricePlanningAdmissionGate().evaluate(quality)
    blueprint_decision = StrategyPricePlanningBlueprintFactory().generate(admission)

    return StrategyPriceReferencePlanFactory().generate(blueprint_decision)


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
        blocked=True,
    )


def availability_snapshot(
    plan_decision: PriceReferencePlanDecision,
    *,
    unavailable_roles: tuple[PriceReferenceRole, ...] = (),
    unavailable_priorities: tuple[
        tuple[PriceReferenceRole, int],
        ...,
    ] = (),
) -> PriceReferenceAvailabilitySnapshot:
    plan = plan_decision.plan_required

    return PriceReferenceAvailabilitySnapshot(
        plan=plan,
        items=tuple(
            PriceReferenceAvailabilityItem(
                requirement=requirement,
                available=(
                    requirement.role not in unavailable_roles
                    and (
                        requirement.role,
                        requirement.priority,
                    )
                    not in unavailable_priorities
                ),
            )
            for requirement in plan.requirements
        ),
    )


def test_default_policy_requires_all_roles() -> None:
    policy = PriceReferenceAvailabilityPolicy()

    assert policy.require_entry_reference is True
    assert policy.require_stop_reference is True
    assert policy.require_target_reference is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"require_entry_reference": 1},
        {"require_stop_reference": 1},
        {"require_target_reference": 1},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        PriceReferenceAvailabilityPolicy(**overrides)


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PriceReferenceAvailabilityPolicy",
    ):
        StrategyPriceReferenceAvailabilityGate(policy="invalid")


def test_invalid_plan_decision_is_fail_safe() -> None:
    with pytest.raises(
        PriceReferenceAvailabilityError,
        match="INVALID_PLAN_DECISION",
    ) as captured:
        StrategyPriceReferenceAvailabilityGate().evaluate("invalid")

    assert captured.value.reason == (PriceReferenceAvailabilityErrorReason.INVALID_PLAN_DECISION)


def test_created_plan_requires_availability() -> None:
    with pytest.raises(
        PriceReferenceAvailabilityError,
        match="INVALID_AVAILABILITY",
    ):
        StrategyPriceReferenceAvailabilityGate().evaluate(bullish_plan_decision())


def test_invalid_availability_type_is_fail_safe() -> None:
    with pytest.raises(
        PriceReferenceAvailabilityError,
        match="INVALID_AVAILABILITY",
    ):
        StrategyPriceReferenceAvailabilityGate().evaluate(
            bullish_plan_decision(),
            "invalid",
        )


def test_all_available_is_ready() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(plan_decision)

    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    assert decision.status == (PriceReferenceAvailabilityStatus.READY)
    assert decision.reason == (PriceReferenceAvailabilityReason.READY)
    assert decision.blockers == ()
    assert decision.is_ready is True
    assert decision.can_resolve_prices is True


def test_bearish_plan_can_be_ready() -> None:
    plan_decision = bearish_plan_decision()
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        availability_snapshot(plan_decision),
    )

    assert decision.is_ready is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)


def test_blocked_upstream_plan_is_blocked() -> None:
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(blocked_plan_decision())

    assert decision.is_blocked is True
    assert decision.availability is None
    assert decision.reason == (PriceReferenceAvailabilityReason.PLAN_BLOCKED)
    assert decision.blockers == (PriceReferenceAvailabilityBlocker.PLAN_BLOCKED,)


def test_entry_selects_first_available_priority() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_priorities=((PriceReferenceRole.ENTRY, 1),),
    )

    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    assert decision.is_ready is True
    assert decision.selected_entry is not None
    assert decision.selected_entry.priority == 2


def test_target_selects_first_available_priority() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_priorities=((PriceReferenceRole.TARGET, 1),),
    )

    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    assert decision.is_ready is True
    assert decision.selected_target is not None
    assert decision.selected_target.priority == 2


def test_stop_requirement_is_selected() -> None:
    plan_decision = bullish_plan_decision()
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        availability_snapshot(plan_decision),
    )

    assert decision.selected_stop is not None
    assert decision.selected_stop.role == (PriceReferenceRole.STOP)
    assert decision.selected_stop.priority == 1


def test_no_entry_reference_blocks() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.ENTRY,),
    )

    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    assert decision.reason == (PriceReferenceAvailabilityReason.ENTRY_REFERENCE_UNAVAILABLE)
    assert decision.blockers == (PriceReferenceAvailabilityBlocker.ENTRY_REFERENCE_UNAVAILABLE,)


def test_no_stop_reference_blocks() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.STOP,),
    )

    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    assert decision.reason == (PriceReferenceAvailabilityReason.STOP_REFERENCE_UNAVAILABLE)


def test_no_target_reference_blocks() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.TARGET,),
    )

    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    assert decision.reason == (PriceReferenceAvailabilityReason.TARGET_REFERENCE_UNAVAILABLE)


def test_multiple_missing_roles_preserve_order() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_roles=(
            PriceReferenceRole.ENTRY,
            PriceReferenceRole.STOP,
            PriceReferenceRole.TARGET,
        ),
    )

    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    assert decision.reason == (PriceReferenceAvailabilityReason.MULTIPLE_REFERENCES_UNAVAILABLE)
    assert decision.blockers == (
        PriceReferenceAvailabilityBlocker.ENTRY_REFERENCE_UNAVAILABLE,
        PriceReferenceAvailabilityBlocker.STOP_REFERENCE_UNAVAILABLE,
        PriceReferenceAvailabilityBlocker.TARGET_REFERENCE_UNAVAILABLE,
    )


def test_entry_requirement_can_be_waived() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.ENTRY,),
    )
    policy = PriceReferenceAvailabilityPolicy(require_entry_reference=False)

    decision = StrategyPriceReferenceAvailabilityGate(policy).evaluate(plan_decision, snapshot)

    assert decision.is_ready is True
    assert decision.selected_entry is None


def test_stop_requirement_can_be_waived() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.STOP,),
    )
    policy = PriceReferenceAvailabilityPolicy(require_stop_reference=False)

    decision = StrategyPriceReferenceAvailabilityGate(policy).evaluate(plan_decision, snapshot)

    assert decision.is_ready is True
    assert decision.selected_stop is None


def test_target_requirement_can_be_waived() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.TARGET,),
    )
    policy = PriceReferenceAvailabilityPolicy(require_target_reference=False)

    decision = StrategyPriceReferenceAvailabilityGate(policy).evaluate(plan_decision, snapshot)

    assert decision.is_ready is True
    assert decision.selected_target is None


def test_snapshot_rejects_missing_item() -> None:
    plan = bullish_plan_decision().plan_required
    items = tuple(
        PriceReferenceAvailabilityItem(
            requirement=requirement,
            available=True,
        )
        for requirement in plan.requirements[:-1]
    )

    with pytest.raises(
        ValueError,
        match="exact order",
    ):
        PriceReferenceAvailabilitySnapshot(
            plan=plan,
            items=items,
        )


def test_snapshot_rejects_reordered_items() -> None:
    snapshot = availability_snapshot(bullish_plan_decision())

    with pytest.raises(
        ValueError,
        match="exact order",
    ):
        replace(
            snapshot,
            items=tuple(reversed(snapshot.items)),
        )


def test_snapshot_rejects_foreign_plan() -> None:
    bullish_snapshot = availability_snapshot(bullish_plan_decision())
    bearish_plan = bearish_plan_decision().plan_required

    with pytest.raises(
        ValueError,
        match="exact order",
    ):
        replace(
            bullish_snapshot,
            plan=bearish_plan,
        )


def test_gate_rejects_foreign_snapshot() -> None:
    bullish_plan = bullish_plan_decision()
    bearish_snapshot = availability_snapshot(bearish_plan_decision())

    with pytest.raises(
        PriceReferenceAvailabilityError,
        match="does not reference",
    ):
        StrategyPriceReferenceAvailabilityGate().evaluate(
            bullish_plan,
            bearish_snapshot,
        )


def test_item_requires_requirement_type() -> None:
    with pytest.raises(
        ValueError,
        match="PriceReferenceRequirement",
    ):
        PriceReferenceAvailabilityItem(
            requirement="invalid",
            available=True,
        )


def test_item_requires_strict_boolean() -> None:
    requirement = bullish_plan_decision().plan_required.requirements[0]

    with pytest.raises(ValueError):
        PriceReferenceAvailabilityItem(
            requirement=requirement,
            available=1,
        )


def test_snapshot_availability_views() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_priorities=((PriceReferenceRole.ENTRY, 1),),
    )

    assert len(snapshot.unavailable_items) == 1
    assert len(snapshot.available_items) == len(snapshot.items) - 1


def test_snapshot_first_available_rejects_raw_role() -> None:
    snapshot = availability_snapshot(bullish_plan_decision())

    with pytest.raises(ValueError):
        snapshot.first_available("ENTRY")


def test_decision_preserves_metadata() -> None:
    plan_decision = bullish_plan_decision()
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        availability_snapshot(plan_decision),
    )

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.blocker_count == 0


def test_decision_is_explicitly_non_executable() -> None:
    plan_decision = bullish_plan_decision()
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        availability_snapshot(plan_decision),
    )

    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "entry_price",
        "stop_loss",
        "take_profit",
        "volume",
        "lot_size",
        "order_request",
        "broker_ticket",
    ],
)
def test_decision_contains_no_price_or_execution_fields(
    attribute_name: str,
) -> None:
    plan_decision = bullish_plan_decision()
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        availability_snapshot(plan_decision),
    )

    assert not hasattr(decision, attribute_name)


def test_item_stable_id_is_deterministic() -> None:
    snapshot = availability_snapshot(bullish_plan_decision())
    item = snapshot.items[0]

    assert item.stable_id == (f"{item.requirement.stable_id}:AVAILABLE")


def test_snapshot_stable_id_is_deterministic() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(plan_decision)

    assert snapshot.stable_id.startswith(plan_decision.plan_required.stable_id)
    assert "REFERENCE_AVAILABILITY:" in (snapshot.stable_id)


def test_ready_decision_stable_id_is_deterministic() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(plan_decision)
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    assert decision.stable_id.startswith(
        f"{plan_decision.stable_id}:REFERENCE_AVAILABILITY_DECISION:READY:READY:NONE:"
    )


def test_blocked_decision_stable_id_lists_blocker() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.STOP,),
    )
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    assert "STOP_REFERENCE_UNAVAILABLE" in decision.stable_id


def test_manual_decision_rejects_wrong_status() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(plan_decision)
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PriceReferenceAvailabilityStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_selection() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(plan_decision)
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            selected_entry=decision.selected_target,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(
        plan_decision,
        unavailable_roles=(PriceReferenceRole.STOP,),
    )
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision, snapshot)

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PriceReferenceAvailabilityBlocker.STOP_REFERENCE_UNAVAILABLE,
                PriceReferenceAvailabilityBlocker.STOP_REFERENCE_UNAVAILABLE,
            ),
        )


def test_item_is_immutable() -> None:
    item = availability_snapshot(bullish_plan_decision()).items[0]

    with pytest.raises(FrozenInstanceError):
        item.available = False


def test_snapshot_is_immutable() -> None:
    snapshot = availability_snapshot(bullish_plan_decision())

    with pytest.raises(FrozenInstanceError):
        snapshot.items = ()


def test_decision_is_immutable() -> None:
    plan_decision = bullish_plan_decision()
    decision = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        availability_snapshot(plan_decision),
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PriceReferenceAvailabilityStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = PriceReferenceAvailabilityPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.require_stop_reference = False


def test_evaluation_is_deterministic() -> None:
    gate = StrategyPriceReferenceAvailabilityGate()
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(plan_decision)

    assert gate.evaluate(
        plan_decision,
        snapshot,
    ) == gate.evaluate(
        plan_decision,
        snapshot,
    )


def test_function_api_delegates() -> None:
    plan_decision = bullish_plan_decision()
    decision = evaluate_price_reference_availability(
        plan_decision,
        availability_snapshot(plan_decision),
    )

    assert decision.is_ready is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategyPriceReferenceAvailabilityGate()
    plan_decision = bullish_plan_decision()
    snapshot = availability_snapshot(plan_decision)

    assert gate.assess(
        plan_decision,
        snapshot,
    ) == gate.evaluate(
        plan_decision,
        snapshot,
    )
    assert gate.check(
        plan_decision,
        snapshot,
    ) == gate.evaluate(
        plan_decision,
        snapshot,
    )


def test_public_aliases_are_preserved() -> None:
    assert ReferenceAvailabilityBlocker is PriceReferenceAvailabilityBlocker
    assert ReferenceAvailabilityDecision is PriceReferenceAvailabilityDecision
    assert ReferenceAvailabilityGate is StrategyPriceReferenceAvailabilityGate
    assert ReferenceAvailabilityItem is PriceReferenceAvailabilityItem
    assert ReferenceAvailabilityPolicy is PriceReferenceAvailabilityPolicy
    assert ReferenceAvailabilityReason is PriceReferenceAvailabilityReason
    assert ReferenceAvailabilitySnapshot is PriceReferenceAvailabilitySnapshot
    assert ReferenceAvailabilityStatus is PriceReferenceAvailabilityStatus
