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
    StrategyOrderIntentBlueprintFactory,
    StrategyOrderSide,
)
from app.strategy.order_intent_execution_lock import (
    StrategyExecutionBoundaryLockFactory,
)
from app.strategy.planning_package import (
    AnalyticalPlanningPackage,
    PlanningPackage,
    PlanningPackageBlocker,
    PlanningPackageDecision,
    PlanningPackageFactory,
    PlanningPackageReason,
    PlanningPackageStatus,
    StrategyPlanningPackage,
    StrategyPlanningPackageBlocker,
    StrategyPlanningPackageDecision,
    StrategyPlanningPackageError,
    StrategyPlanningPackageErrorReason,
    StrategyPlanningPackageFactory,
    StrategyPlanningPackageReason,
    StrategyPlanningPackageStatus,
    generate_strategy_planning_package,
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


@lru_cache(maxsize=1)
def bullish_execution_lock():
    return StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())


@lru_cache(maxsize=1)
def bearish_execution_lock():
    return StrategyExecutionBoundaryLockFactory().generate(bearish_order_intent())


@lru_cache(maxsize=1)
def blocked_execution_lock():
    return StrategyExecutionBoundaryLockFactory().generate(blocked_order_intent())


def test_invalid_execution_lock_is_fail_safe() -> None:
    with pytest.raises(
        StrategyPlanningPackageError,
        match="INVALID_EXECUTION_LOCK_DECISION",
    ) as captured:
        StrategyPlanningPackageFactory().generate("invalid")

    assert captured.value.reason == (
        StrategyPlanningPackageErrorReason.INVALID_EXECUTION_LOCK_DECISION
    )


def test_bullish_package_is_created() -> None:
    decision = StrategyPlanningPackageFactory().generate(bullish_execution_lock())

    assert decision.status == (StrategyPlanningPackageStatus.CREATED)
    assert decision.reason == (StrategyPlanningPackageReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_package is True


def test_bearish_package_is_created() -> None:
    decision = StrategyPlanningPackageFactory().generate(bearish_execution_lock())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.package_required.side == StrategyOrderSide.SELL


def test_blocked_lock_produces_no_package() -> None:
    decision = StrategyPlanningPackageFactory().generate(blocked_execution_lock())

    assert decision.is_blocked is True
    assert decision.package is None
    assert decision.has_package is False
    assert decision.reason == (StrategyPlanningPackageReason.EXECUTION_LOCK_BLOCKED)
    assert decision.blockers == (StrategyPlanningPackageBlocker.EXECUTION_LOCK_BLOCKED,)


def test_package_required_rejects_blocked_result() -> None:
    decision = StrategyPlanningPackageFactory().generate(blocked_execution_lock())

    with pytest.raises(
        ValueError,
        match="No strategy-planning package",
    ):
        _ = decision.package_required


def test_package_preserves_complete_lineage() -> None:
    execution_lock = bullish_execution_lock()
    package = StrategyPlanningPackageFactory().generate(execution_lock).package_required

    assert package.execution_lock is execution_lock
    assert package.order_intent is execution_lock.order_intent
    assert package.sized_plan is package.order_intent.sized_plan
    assert package.position_size is package.sized_plan.position_size
    assert package.sizing_specification is package.position_size.specification_decision
    assert package.sizing_handoff is package.sizing_specification.handoff_decision
    assert package.risk_admission is package.sizing_handoff.risk_admission


def test_package_preserves_domain_objects() -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    assert package.lock is (package.execution_lock.lock_required)
    assert package.blueprint is (package.order_intent.blueprint_required)
    assert package.plan is (package.sized_plan.plan_required)
    assert package.handoff is (package.sizing_handoff.handoff_required)
    assert package.specification is (package.sizing_specification.specification_required)
    assert package.metrics is package.position_size.metrics


def test_package_preserves_metadata() -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    assert package.broker_symbol == "XAUUSDm"
    assert package.observed_at == OBSERVED_AT
    assert package.direction == (DirectionalPermissionDirection.BULLISH)
    assert package.side == StrategyOrderSide.BUY


def test_package_preserves_prices_and_volume() -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    assert package.entry_price == Decimal("2350")
    assert package.stop_loss == Decimal("2340")
    assert package.take_profit == Decimal("2370")
    assert package.volume == Decimal("0.10")


def test_package_preserves_risk_values() -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    assert package.approved_risk_amount == Decimal("100")
    assert package.actual_risk_amount == Decimal("100")
    assert package.unused_risk_amount == Decimal("0")
    assert package.reward_risk_ratio == Decimal("2")
    assert package.risk_utilization_percent == Decimal("100")


def test_package_has_seven_components() -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    assert package.component_count == 7
    assert package.is_complete is True
    assert package.is_locked is True


def test_package_never_authorizes_execution() -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    assert package.execution_authorized is False
    assert package.has_broker_request is False
    assert package.can_build_broker_request is False
    assert package.can_submit_order is False
    assert package.is_executable is False


def test_decision_never_authorizes_execution() -> None:
    decision = StrategyPlanningPackageFactory().generate(bullish_execution_lock())

    assert decision.execution_authorized is False
    assert decision.has_broker_request is False
    assert decision.can_submit_order is False
    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "request",
        "request_dict",
        "order_request",
        "order_type",
        "type_filling",
        "type_time",
        "deviation",
        "magic_number",
        "broker_ticket",
        "authorize",
        "unlock",
        "submit",
        "send",
        "send_order",
        "order_send",
    ],
)
def test_package_contains_no_execution_surface(
    attribute_name: str,
) -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    assert not hasattr(package, attribute_name)


def test_package_id_is_deterministic() -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    assert package.package_id == (
        "XAUUSDm:BUY:"
        "ENTRY[2350]:"
        "STOP[2340]:"
        "TARGET[2370]:"
        "VOLUME[0.1]:"
        "APPROVED_RISK[100]:"
        "ACTUAL_RISK[100]:"
        "RR[2]:"
        "EXECUTION_LOCKED"
    )


def test_package_stable_id_is_deterministic() -> None:
    execution_lock = bullish_execution_lock()
    package = StrategyPlanningPackageFactory().generate(execution_lock).package_required

    assert package.stable_id == (
        f"{execution_lock.stable_id}:STRATEGY_PLANNING_PACKAGE:{package.package_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    execution_lock = bullish_execution_lock()
    decision = StrategyPlanningPackageFactory().generate(execution_lock)

    assert decision.stable_id == (
        f"{execution_lock.stable_id}:STRATEGY_PLANNING_PACKAGE_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    execution_lock = blocked_execution_lock()
    decision = StrategyPlanningPackageFactory().generate(execution_lock)

    assert decision.stable_id == (
        f"{execution_lock.stable_id}:"
        "STRATEGY_PLANNING_PACKAGE_GENERATION:"
        "BLOCKED:EXECUTION_LOCK_BLOCKED:"
        "EXECUTION_LOCK_BLOCKED"
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "order_intent",
        "sized_plan",
        "position_size",
        "sizing_specification",
        "sizing_handoff",
        "risk_admission",
    ],
)
def test_direct_package_rejects_foreign_lineage(
    field_name: str,
) -> None:
    bullish = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required
    bearish = StrategyPlanningPackageFactory().generate(bearish_execution_lock()).package_required

    with pytest.raises(
        ValueError,
        match="exact strategy lineage",
    ):
        replace(
            bullish,
            **{field_name: getattr(bearish, field_name)},
        )


def test_direct_package_rejects_blocked_lock() -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    with pytest.raises(
        ValueError,
        match="locked execution-boundary",
    ):
        replace(
            package,
            execution_lock=blocked_execution_lock(),
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningPackageFactory().generate(bullish_execution_lock())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=StrategyPlanningPackageStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningPackageFactory().generate(bullish_execution_lock())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(StrategyPlanningPackageReason.EXECUTION_LOCK_BLOCKED),
        )


def test_manual_decision_rejects_missing_package() -> None:
    decision = StrategyPlanningPackageFactory().generate(bullish_execution_lock())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            package=None,
        )


def test_manual_decision_rejects_unexpected_package() -> None:
    blocked = StrategyPlanningPackageFactory().generate(blocked_execution_lock())
    created_package = (
        StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            package=created_package,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningPackageFactory().generate(blocked_execution_lock())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                StrategyPlanningPackageBlocker.EXECUTION_LOCK_BLOCKED,
                StrategyPlanningPackageBlocker.EXECUTION_LOCK_BLOCKED,
            ),
        )


def test_package_is_immutable() -> None:
    package = StrategyPlanningPackageFactory().generate(bullish_execution_lock()).package_required

    with pytest.raises(FrozenInstanceError):
        package.execution_lock = bearish_execution_lock()


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningPackageFactory().generate(bullish_execution_lock())

    with pytest.raises(FrozenInstanceError):
        decision.status = StrategyPlanningPackageStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyPlanningPackageFactory()
    execution_lock = bullish_execution_lock()

    assert factory.generate(execution_lock) == factory.generate(execution_lock)


def test_function_api_delegates() -> None:
    decision = generate_strategy_planning_package(bullish_execution_lock())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPlanningPackageFactory()
    execution_lock = bullish_execution_lock()

    assert factory.build(execution_lock) == factory.generate(execution_lock)
    assert factory.evaluate(execution_lock) == factory.generate(execution_lock)


def test_public_aliases_are_preserved() -> None:
    assert AnalyticalPlanningPackage is StrategyPlanningPackage
    assert PlanningPackage is StrategyPlanningPackage
    assert PlanningPackageBlocker is StrategyPlanningPackageBlocker
    assert PlanningPackageDecision is StrategyPlanningPackageDecision
    assert PlanningPackageFactory is StrategyPlanningPackageFactory
    assert PlanningPackageReason is StrategyPlanningPackageReason
    assert PlanningPackageStatus is StrategyPlanningPackageStatus
