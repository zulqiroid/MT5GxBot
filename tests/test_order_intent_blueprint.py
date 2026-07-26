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
    AnalyticalOrderIntent,
    OrderIntentBlocker,
    OrderIntentBlueprint,
    OrderIntentBlueprintBlocker,
    OrderIntentBlueprintDecision,
    OrderIntentBlueprintError,
    OrderIntentBlueprintErrorReason,
    OrderIntentBlueprintFactory,
    OrderIntentBlueprintReason,
    OrderIntentBlueprintStatus,
    OrderIntentDecision,
    OrderIntentExecutionMode,
    OrderIntentExecutionState,
    OrderIntentFactory,
    OrderIntentProtectionMode,
    OrderIntentReason,
    OrderIntentSide,
    OrderIntentStatus,
    StrategyOrderIntentBlueprint,
    StrategyOrderIntentBlueprintFactory,
    StrategyOrderSide,
    generate_order_intent_blueprint,
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


def test_invalid_sized_plan_is_fail_safe() -> None:
    with pytest.raises(
        OrderIntentBlueprintError,
        match="INVALID_SIZED_PLAN_DECISION",
    ) as captured:
        StrategyOrderIntentBlueprintFactory().generate("invalid")

    assert captured.value.reason == (OrderIntentBlueprintErrorReason.INVALID_SIZED_PLAN_DECISION)


def test_bullish_plan_creates_buy_intent() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan())

    assert decision.status == (OrderIntentBlueprintStatus.CREATED)
    assert decision.reason == (OrderIntentBlueprintReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_blueprint is True
    assert decision.blueprint_required.side == StrategyOrderSide.BUY


def test_bearish_plan_creates_sell_intent() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(bearish_sized_plan())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.blueprint_required.side == StrategyOrderSide.SELL


def test_blocked_plan_produces_no_blueprint() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(blocked_sized_plan())

    assert decision.is_blocked is True
    assert decision.blueprint is None
    assert decision.has_blueprint is False
    assert decision.reason == (OrderIntentBlueprintReason.SIZED_PLAN_BLOCKED)
    assert decision.blockers == (OrderIntentBlueprintBlocker.SIZED_PLAN_BLOCKED,)


def test_blueprint_required_rejects_blocked_result() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(blocked_sized_plan())

    with pytest.raises(
        ValueError,
        match="No order-intent blueprint",
    ):
        _ = decision.blueprint_required


def test_blueprint_preserves_sized_plan() -> None:
    sized_plan = bullish_sized_plan()
    blueprint = StrategyOrderIntentBlueprintFactory().generate(sized_plan).blueprint_required

    assert blueprint.sized_plan is sized_plan
    assert blueprint.plan is sized_plan.plan_required


def test_blueprint_preserves_metadata() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    assert blueprint.broker_symbol == "XAUUSDm"
    assert blueprint.observed_at == OBSERVED_AT
    assert blueprint.direction == (DirectionalPermissionDirection.BULLISH)


def test_blueprint_preserves_prices() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    assert blueprint.entry_price == Decimal("2350")
    assert blueprint.stop_loss == Decimal("2340")
    assert blueprint.take_profit == Decimal("2370")


def test_blueprint_preserves_volume() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    assert blueprint.volume == Decimal("0.10")


def test_blueprint_preserves_risk_context() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    assert blueprint.approved_risk_amount == Decimal("100")
    assert blueprint.actual_risk_amount == Decimal("100")
    assert blueprint.unused_risk_amount == Decimal("0")
    assert blueprint.reward_risk_ratio == Decimal("2")
    assert blueprint.risk_utilization_percent == Decimal("100")


def test_broker_stop_is_mandatory() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    assert blueprint.protection_mode == (OrderIntentProtectionMode.BROKER_STOP_REQUIRED)
    assert blueprint.requires_broker_stop is True
    assert blueprint.has_protective_stop is True


def test_blueprint_is_explicitly_analytical_only() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    assert blueprint.execution_state == (OrderIntentExecutionState.ANALYTICAL_ONLY)
    assert blueprint.can_submit_order is False
    assert blueprint.has_broker_request is False
    assert blueprint.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "order_type",
        "type_time",
        "time_in_force",
        "filling_mode",
        "deviation",
        "magic_number",
        "order_request",
        "broker_ticket",
        "send_order",
        "order_send",
        "submit",
    ],
)
def test_blueprint_contains_no_execution_fields(
    attribute_name: str,
) -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    assert not hasattr(blueprint, attribute_name)


def test_buy_intent_preserves_price_order() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    assert blueprint.stop_loss < blueprint.entry_price < blueprint.take_profit


def test_sell_intent_preserves_price_order() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bearish_sized_plan()).blueprint_required
    )

    assert blueprint.take_profit < blueprint.entry_price < blueprint.stop_loss


def test_intent_id_is_deterministic() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    assert blueprint.intent_id == (
        "XAUUSDm:BUY:"
        "ENTRY[2350]:"
        "STOP[2340]:"
        "TARGET[2370]:"
        "VOLUME[0.1]:"
        "APPROVED_RISK[100]:"
        "ACTUAL_RISK[100]:"
        "UNUSED_RISK[0]:"
        "RR[2]:"
        "UTILIZATION_PCT[100]:"
        "PROTECTION[BROKER_STOP_REQUIRED]:"
        "EXECUTION[ANALYTICAL_ONLY]"
    )


def test_blueprint_stable_id_is_deterministic() -> None:
    sized_plan = bullish_sized_plan()
    blueprint = StrategyOrderIntentBlueprintFactory().generate(sized_plan).blueprint_required

    assert blueprint.stable_id == (
        f"{sized_plan.stable_id}:ORDER_INTENT_BLUEPRINT:{blueprint.intent_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    sized_plan = bullish_sized_plan()
    decision = StrategyOrderIntentBlueprintFactory().generate(sized_plan)

    assert decision.stable_id == (
        f"{sized_plan.stable_id}:ORDER_INTENT_BLUEPRINT_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_lists_blocker() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(blocked_sized_plan())

    assert decision.stable_id.endswith(
        "ORDER_INTENT_BLUEPRINT_GENERATION:BLOCKED:SIZED_PLAN_BLOCKED:SIZED_PLAN_BLOCKED"
    )


def test_equivalent_decimal_scales_share_intent_ids() -> None:
    baseline = StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan())

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
    scaled_sized_plan = StrategySizedTradePlanFactory().generate(scaled_calculation)
    scaled = StrategyOrderIntentBlueprintFactory().generate(scaled_sized_plan)

    assert scaled.blueprint_required.intent_id == baseline.blueprint_required.intent_id
    assert scaled.stable_id == baseline.stable_id


def test_direct_blueprint_rejects_blocked_plan() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="created sized trade plan",
    ):
        replace(
            blueprint,
            sized_plan=blocked_sized_plan(),
        )


def test_direct_blueprint_rejects_wrong_side() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="side",
    ):
        replace(
            blueprint,
            side=StrategyOrderSide.SELL,
        )


def test_direct_blueprint_rejects_raw_side() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="StrategyOrderSide",
    ):
        replace(
            blueprint,
            side="BUY",
        )


def test_direct_blueprint_requires_protection_mode() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="OrderIntentProtectionMode",
    ):
        replace(
            blueprint,
            protection_mode="BROKER_STOP_REQUIRED",
        )


def test_direct_blueprint_requires_analytical_state() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="OrderIntentExecutionState",
    ):
        replace(
            blueprint,
            execution_state="ANALYTICAL_ONLY",
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
def test_direct_blueprint_rejects_wrong_values(
    field_name: str,
    value: Decimal,
) -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        replace(
            blueprint,
            **{field_name: value},
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=OrderIntentBlueprintStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(OrderIntentBlueprintReason.SIZED_PLAN_BLOCKED),
        )


def test_manual_decision_rejects_missing_blueprint() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            blueprint=None,
        )


def test_manual_decision_rejects_unexpected_blueprint() -> None:
    blocked = StrategyOrderIntentBlueprintFactory().generate(blocked_sized_plan())
    created_blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            blueprint=created_blueprint,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(blocked_sized_plan())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                OrderIntentBlueprintBlocker.SIZED_PLAN_BLOCKED,
                OrderIntentBlueprintBlocker.SIZED_PLAN_BLOCKED,
            ),
        )


def test_blueprint_is_immutable() -> None:
    blueprint = (
        StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan()).blueprint_required
    )

    with pytest.raises(FrozenInstanceError):
        blueprint.volume = Decimal("0.09")


def test_decision_is_immutable() -> None:
    decision = StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan())

    with pytest.raises(FrozenInstanceError):
        decision.status = OrderIntentBlueprintStatus.BLOCKED


def test_generation_is_deterministic() -> None:
    factory = StrategyOrderIntentBlueprintFactory()
    sized_plan = bullish_sized_plan()

    assert factory.generate(sized_plan) == factory.generate(sized_plan)


def test_function_api_delegates() -> None:
    decision = generate_order_intent_blueprint(bullish_sized_plan())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyOrderIntentBlueprintFactory()
    sized_plan = bullish_sized_plan()

    assert factory.build(sized_plan) == factory.generate(sized_plan)
    assert factory.evaluate(sized_plan) == factory.generate(sized_plan)


def test_public_aliases_are_preserved() -> None:
    assert AnalyticalOrderIntent is StrategyOrderIntentBlueprint
    assert OrderIntentBlueprint is StrategyOrderIntentBlueprint
    assert OrderIntentBlueprintFactory is StrategyOrderIntentBlueprintFactory
    assert OrderIntentBlocker is OrderIntentBlueprintBlocker
    assert OrderIntentDecision is OrderIntentBlueprintDecision
    assert OrderIntentExecutionMode is OrderIntentExecutionState
    assert OrderIntentFactory is StrategyOrderIntentBlueprintFactory
    assert OrderIntentReason is OrderIntentBlueprintReason
    assert OrderIntentSide is StrategyOrderSide
    assert OrderIntentStatus is OrderIntentBlueprintStatus
