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
from app.strategy.order_intent_blueprint import (
    OrderIntentExecutionState,
    OrderIntentProtectionMode,
    StrategyOrderIntentBlueprintFactory,
    StrategyOrderSide,
)
from app.strategy.order_intent_execution_lock import (
    AnalyticalExecutionLock,
    ExecutionBoundaryBarrier,
    ExecutionBoundaryBarrierType,
    ExecutionBoundaryDecision,
    ExecutionBoundaryFactory,
    ExecutionBoundaryLock,
    ExecutionBoundaryLockDecision,
    ExecutionBoundaryLockError,
    ExecutionBoundaryLockErrorReason,
    ExecutionBoundaryLockReason,
    ExecutionBoundaryLockStatus,
    ExecutionLockBarrier,
    ExecutionLockDecision,
    ExecutionLockFactory,
    ExecutionLockReason,
    ExecutionLockStatus,
    StrategyExecutionBoundaryLock,
    StrategyExecutionBoundaryLockFactory,
    generate_execution_boundary_lock,
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
    StrategySizedTradePlanFactory,
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


@lru_cache(maxsize=1)
def bullish_sized_plan():
    return StrategySizedTradePlanFactory().generate(bullish_calculation())


@lru_cache(maxsize=1)
def bearish_sized_plan():
    return StrategySizedTradePlanFactory().generate(bearish_calculation())


@lru_cache(maxsize=1)
def blocked_sized_plan():
    return StrategySizedTradePlanFactory().generate(blocked_calculation())


@lru_cache(maxsize=1)
def bullish_order_intent():
    return StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan())


@lru_cache(maxsize=1)
def bearish_order_intent():
    return StrategyOrderIntentBlueprintFactory().generate(bearish_sized_plan())


@lru_cache(maxsize=1)
def blocked_order_intent():
    return StrategyOrderIntentBlueprintFactory().generate(blocked_sized_plan())


def test_invalid_order_intent_is_fail_safe() -> None:
    with pytest.raises(
        ExecutionBoundaryLockError,
        match="INVALID_ORDER_INTENT_DECISION",
    ) as captured:
        StrategyExecutionBoundaryLockFactory().generate("invalid")

    assert captured.value.reason == (ExecutionBoundaryLockErrorReason.INVALID_ORDER_INTENT_DECISION)


def test_bullish_intent_is_locked() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())

    assert decision.status == (ExecutionBoundaryLockStatus.LOCKED)
    assert decision.reason == (ExecutionBoundaryLockReason.LOCKED_ANALYTICAL_ONLY)
    assert decision.is_locked is True
    assert decision.is_blocked is False
    assert decision.has_lock is True


def test_bearish_intent_is_locked() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bearish_order_intent())

    assert decision.is_locked is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.lock_required.side == StrategyOrderSide.SELL


def test_blocked_intent_produces_no_lock() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(blocked_order_intent())

    assert decision.status == (ExecutionBoundaryLockStatus.BLOCKED)
    assert decision.reason == (ExecutionBoundaryLockReason.ORDER_INTENT_BLOCKED)
    assert decision.is_blocked is True
    assert decision.lock is None
    assert decision.has_lock is False
    assert decision.barriers == (ExecutionBoundaryBarrier.ORDER_INTENT_BLOCKED,)


def test_lock_required_rejects_blocked_result() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(blocked_order_intent())

    with pytest.raises(
        ValueError,
        match="No execution-boundary lock",
    ):
        _ = decision.lock_required


def test_lock_preserves_order_intent() -> None:
    order_intent = bullish_order_intent()
    lock = StrategyExecutionBoundaryLockFactory().generate(order_intent).lock_required

    assert lock.order_intent is order_intent
    assert lock.blueprint is order_intent.blueprint_required


def test_lock_preserves_metadata() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    assert lock.broker_symbol == "XAUUSDm"
    assert lock.observed_at == OBSERVED_AT
    assert lock.direction == (DirectionalPermissionDirection.BULLISH)
    assert lock.side == StrategyOrderSide.BUY


def test_all_required_barriers_are_present() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    assert lock.barriers == (
        ExecutionBoundaryBarrier.ANALYTICAL_ONLY,
        ExecutionBoundaryBarrier.BROKER_REQUEST_ABSENT,
        ExecutionBoundaryBarrier.EXECUTION_AUTHORIZATION_ABSENT,
        ExecutionBoundaryBarrier.BROKER_STOP_REQUIRED,
    )
    assert lock.barrier_count == 4


def test_decision_preserves_required_barriers() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())

    assert decision.barriers == (
        ExecutionBoundaryBarrier.ANALYTICAL_ONLY,
        ExecutionBoundaryBarrier.BROKER_REQUEST_ABSENT,
        ExecutionBoundaryBarrier.EXECUTION_AUTHORIZATION_ABSENT,
        ExecutionBoundaryBarrier.BROKER_STOP_REQUIRED,
    )
    assert decision.barrier_count == 4


def test_broker_stop_remains_required() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    assert lock.blueprint.requires_broker_stop is True
    assert lock.blueprint.has_protective_stop is True
    assert lock.blueprint.protection_mode == (OrderIntentProtectionMode.BROKER_STOP_REQUIRED)


def test_analytical_state_is_preserved() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    assert lock.blueprint.execution_state == (OrderIntentExecutionState.ANALYTICAL_ONLY)


def test_lock_never_authorizes_execution() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    assert lock.execution_authorized is False
    assert lock.has_broker_request is False
    assert lock.can_build_broker_request is False
    assert lock.can_submit_order is False
    assert lock.is_executable is False


def test_decision_never_authorizes_execution() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())

    assert decision.execution_authorized is False
    assert decision.has_broker_request is False
    assert decision.can_build_broker_request is False
    assert decision.can_submit_order is False
    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "unlock",
        "authorize",
        "authorization_token",
        "request",
        "request_dict",
        "order_request",
        "action",
        "order_type",
        "type_filling",
        "type_time",
        "deviation",
        "magic_number",
        "broker_ticket",
        "send",
        "submit",
        "send_order",
        "order_send",
    ],
)
def test_lock_contains_no_execution_surface(
    attribute_name: str,
) -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    assert not hasattr(lock, attribute_name)


def test_lock_id_is_deterministic() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    assert lock.lock_id == (
        "XAUUSDm:BUY:"
        "EXECUTION_LOCK:"
        "ANALYTICAL_ONLY,"
        "BROKER_REQUEST_ABSENT,"
        "EXECUTION_AUTHORIZATION_ABSENT,"
        "BROKER_STOP_REQUIRED"
    )


def test_lock_stable_id_is_deterministic() -> None:
    order_intent = bullish_order_intent()
    lock = StrategyExecutionBoundaryLockFactory().generate(order_intent).lock_required

    assert lock.stable_id == (f"{order_intent.stable_id}:EXECUTION_BOUNDARY_LOCK:{lock.lock_id}")


def test_locked_decision_stable_id_is_deterministic() -> None:
    order_intent = bullish_order_intent()
    decision = StrategyExecutionBoundaryLockFactory().generate(order_intent)

    assert decision.stable_id == (
        f"{order_intent.stable_id}:"
        "EXECUTION_BOUNDARY_LOCK_DECISION:"
        "LOCKED:LOCKED_ANALYTICAL_ONLY:"
        "ANALYTICAL_ONLY,"
        "BROKER_REQUEST_ABSENT,"
        "EXECUTION_AUTHORIZATION_ABSENT,"
        "BROKER_STOP_REQUIRED"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    order_intent = blocked_order_intent()
    decision = StrategyExecutionBoundaryLockFactory().generate(order_intent)

    assert decision.stable_id == (
        f"{order_intent.stable_id}:"
        "EXECUTION_BOUNDARY_LOCK_DECISION:"
        "BLOCKED:ORDER_INTENT_BLOCKED:"
        "ORDER_INTENT_BLOCKED"
    )


def test_direct_lock_rejects_blocked_intent() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    with pytest.raises(
        ValueError,
        match="created",
    ):
        replace(
            lock,
            order_intent=blocked_order_intent(),
        )


def test_direct_lock_rejects_foreign_blueprint() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    with pytest.raises(
        ValueError,
        match="must match",
    ):
        replace(
            lock,
            blueprint=(bearish_order_intent().blueprint_required),
        )


def test_direct_lock_requires_tuple_barriers() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    with pytest.raises(
        ValueError,
        match="tuple",
    ):
        replace(
            lock,
            barriers=list(lock.barriers),
        )


def test_direct_lock_rejects_raw_barriers() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    with pytest.raises(
        ValueError,
        match="ExecutionBoundaryBarrier",
    ):
        replace(
            lock,
            barriers=(
                "ANALYTICAL_ONLY",
                "BROKER_REQUEST_ABSENT",
                "EXECUTION_AUTHORIZATION_ABSENT",
                "BROKER_STOP_REQUIRED",
            ),
        )


def test_direct_lock_rejects_missing_barrier() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    with pytest.raises(
        ValueError,
        match="all safety barriers",
    ):
        replace(
            lock,
            barriers=lock.barriers[:-1],
        )


def test_direct_lock_rejects_reordered_barriers() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    with pytest.raises(
        ValueError,
        match="deterministic order",
    ):
        replace(
            lock,
            barriers=tuple(reversed(lock.barriers)),
        )


def test_manual_decision_rejects_raw_status() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())

    with pytest.raises(
        ValueError,
        match="ExecutionBoundaryLockStatus",
    ):
        replace(
            decision,
            status="LOCKED",
        )


def test_manual_decision_rejects_raw_reason() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())

    with pytest.raises(
        ValueError,
        match="ExecutionBoundaryLockReason",
    ):
        replace(
            decision,
            reason="LOCKED_ANALYTICAL_ONLY",
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=ExecutionBoundaryLockStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(ExecutionBoundaryLockReason.ORDER_INTENT_BLOCKED),
        )


def test_manual_decision_rejects_missing_lock() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            lock=None,
        )


def test_manual_decision_rejects_unexpected_lock() -> None:
    blocked = StrategyExecutionBoundaryLockFactory().generate(blocked_order_intent())
    created_lock = (
        StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            lock=created_lock,
        )


def test_manual_decision_rejects_duplicate_barriers() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(blocked_order_intent())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            barriers=(
                ExecutionBoundaryBarrier.ORDER_INTENT_BLOCKED,
                ExecutionBoundaryBarrier.ORDER_INTENT_BLOCKED,
            ),
        )


def test_lock_is_immutable() -> None:
    lock = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent()).lock_required

    with pytest.raises(FrozenInstanceError):
        lock.barriers = ()


def test_decision_is_immutable() -> None:
    decision = StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())

    with pytest.raises(FrozenInstanceError):
        decision.status = ExecutionBoundaryLockStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyExecutionBoundaryLockFactory()
    order_intent = bullish_order_intent()

    assert factory.generate(order_intent) == factory.generate(order_intent)


def test_function_api_delegates() -> None:
    decision = generate_execution_boundary_lock(bullish_order_intent())

    assert decision.is_locked is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyExecutionBoundaryLockFactory()
    order_intent = bullish_order_intent()

    assert factory.build(order_intent) == factory.generate(order_intent)
    assert factory.evaluate(order_intent) == factory.generate(order_intent)


def test_public_aliases_are_preserved() -> None:
    assert AnalyticalExecutionLock is StrategyExecutionBoundaryLock
    assert ExecutionBoundaryBarrierType is ExecutionBoundaryBarrier
    assert ExecutionBoundaryDecision is ExecutionBoundaryLockDecision
    assert ExecutionBoundaryFactory is StrategyExecutionBoundaryLockFactory
    assert ExecutionBoundaryLock is StrategyExecutionBoundaryLock
    assert ExecutionLockBarrier is ExecutionBoundaryBarrier
    assert ExecutionLockDecision is ExecutionBoundaryLockDecision
    assert ExecutionLockFactory is StrategyExecutionBoundaryLockFactory
    assert ExecutionLockReason is ExecutionBoundaryLockReason
    assert ExecutionLockStatus is ExecutionBoundaryLockStatus
