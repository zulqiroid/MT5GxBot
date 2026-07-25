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
    PricePlanningBlueprintDecision,
    PricePlanningReferenceSource,
    StrategyPricePlanningBlueprintFactory,
)
from app.strategy.price_reference_plan import (
    DirectionalPriceReferencePlan,
    DirectionalReferencePlan,
    PlanningReferencePlanDecision,
    PlanningReferencePlanFactory,
    PlanningReferencePlanPolicy,
    PriceReferencePlanBlocker,
    PriceReferencePlanDecision,
    PriceReferencePlanError,
    PriceReferencePlanErrorReason,
    PriceReferencePlanFactory,
    PriceReferencePlanPolicy,
    PriceReferencePlanReason,
    PriceReferencePlanStatus,
    PriceReferenceRelation,
    PriceReferenceRequirement,
    PriceReferenceRole,
    PriceReferenceSelectionMode,
    ReferencePlanBlocker,
    ReferencePlanReason,
    ReferencePlanStatus,
    ReferenceRequirement,
    StrategyPriceReferencePlanFactory,
    generate_price_reference_plan,
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


def blueprint_decision_for(
    direction: DirectionalPermissionDirection,
    *,
    blocked: bool = False,
) -> PricePlanningBlueprintDecision:
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

    return StrategyPricePlanningBlueprintFactory().generate(admission)


@lru_cache(maxsize=1)
def bullish_blueprint_decision() -> PricePlanningBlueprintDecision:
    return blueprint_decision_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_blueprint_decision() -> PricePlanningBlueprintDecision:
    return blueprint_decision_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_blueprint_decision() -> PricePlanningBlueprintDecision:
    return blueprint_decision_for(
        DirectionalPermissionDirection.BULLISH,
        blocked=True,
    )


def test_default_policy_uses_execution_stop() -> None:
    policy = PriceReferencePlanPolicy()

    assert policy.stop_on_execution_timeframe is True


def test_default_policy_uses_setup_targets() -> None:
    policy = PriceReferencePlanPolicy()

    assert policy.targets_on_setup_timeframe is True


def test_default_selection_mode() -> None:
    policy = PriceReferencePlanPolicy()

    assert policy.selection_mode == (PriceReferenceSelectionMode.FIRST_AVAILABLE)


@pytest.mark.parametrize(
    "overrides",
    [
        {"stop_on_execution_timeframe": 1},
        {"targets_on_setup_timeframe": 1},
        {"selection_mode": "FIRST_AVAILABLE"},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        PriceReferencePlanPolicy(**overrides)


def test_factory_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PriceReferencePlanPolicy",
    ):
        StrategyPriceReferencePlanFactory(policy="invalid")


def test_invalid_blueprint_decision_is_fail_safe() -> None:
    with pytest.raises(
        PriceReferencePlanError,
        match="INVALID_BLUEPRINT_DECISION",
    ) as captured:
        StrategyPriceReferencePlanFactory().generate("invalid")

    assert captured.value.reason == (PriceReferencePlanErrorReason.INVALID_BLUEPRINT_DECISION)


def test_bullish_plan_is_created() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision())

    assert decision.status == (PriceReferencePlanStatus.CREATED)
    assert decision.reason == (PriceReferencePlanReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_plan is True


def test_bearish_plan_is_created() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(bearish_blueprint_decision())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.plan_required.is_bearish is True


def test_blocked_blueprint_produces_no_plan() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(blocked_blueprint_decision())

    assert decision.is_blocked is True
    assert decision.has_plan is False
    assert decision.plan is None
    assert decision.reason == (PriceReferencePlanReason.BLUEPRINT_BLOCKED)
    assert decision.blockers == (PriceReferencePlanBlocker.BLUEPRINT_BLOCKED,)


def test_plan_required_rejects_blocked_result() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(blocked_blueprint_decision())

    with pytest.raises(
        ValueError,
        match="No directional price-reference plan",
    ):
        _ = decision.plan_required


def test_entry_source_priority_is_preserved() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert tuple(requirement.source for requirement in plan.entry_requirements) == (
        PricePlanningReferenceSource.OPTIMAL_TRADE_ENTRY_ZONE,
        PricePlanningReferenceSource.FAIR_VALUE_GAP,
        PricePlanningReferenceSource.ORDER_BLOCK,
    )
    assert tuple(requirement.priority for requirement in plan.entry_requirements) == (1, 2, 3)


def test_stop_source_is_preserved() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert plan.stop_requirement.source == (PricePlanningReferenceSource.PROTECTED_SWING)
    assert plan.stop_requirement.priority == 1


def test_target_source_priority_is_preserved() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert tuple(requirement.source for requirement in plan.target_requirements) == (
        PricePlanningReferenceSource.LIQUIDITY_POOL,
        PricePlanningReferenceSource.DEALING_RANGE_EXTREME,
    )
    assert tuple(requirement.priority for requirement in plan.target_requirements) == (1, 2)


def test_bullish_relations_are_directional() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert all(
        requirement.relation == PriceReferenceRelation.ENTRY_DISCOUNT
        for requirement in plan.entry_requirements
    )
    assert plan.stop_requirement.relation == (PriceReferenceRelation.STOP_BELOW_ENTRY)
    assert all(
        requirement.relation == PriceReferenceRelation.TARGET_ABOVE_ENTRY
        for requirement in plan.target_requirements
    )


def test_bearish_relations_are_directional() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bearish_blueprint_decision()).plan_required

    assert all(
        requirement.relation == PriceReferenceRelation.ENTRY_PREMIUM
        for requirement in plan.entry_requirements
    )
    assert plan.stop_requirement.relation == (PriceReferenceRelation.STOP_ABOVE_ENTRY)
    assert all(
        requirement.relation == PriceReferenceRelation.TARGET_BELOW_ENTRY
        for requirement in plan.target_requirements
    )


def test_default_entry_timeframe_is_m15() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert all(
        requirement.timeframe == TimeframeName.M15 for requirement in plan.entry_requirements
    )


def test_default_stop_timeframe_is_m5() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert plan.stop_requirement.timeframe == (TimeframeName.M5)


def test_default_target_timeframe_is_m15() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert all(
        requirement.timeframe == TimeframeName.M15 for requirement in plan.target_requirements
    )


def test_stop_can_use_setup_timeframe() -> None:
    policy = PriceReferencePlanPolicy(stop_on_execution_timeframe=False)

    plan = (
        StrategyPriceReferencePlanFactory(policy)
        .generate(bullish_blueprint_decision())
        .plan_required
    )

    assert plan.stop_requirement.timeframe == (TimeframeName.M15)


def test_targets_can_use_execution_timeframe() -> None:
    policy = PriceReferencePlanPolicy(targets_on_setup_timeframe=False)

    plan = (
        StrategyPriceReferencePlanFactory(policy)
        .generate(bullish_blueprint_decision())
        .plan_required
    )

    assert all(
        requirement.timeframe == TimeframeName.M5 for requirement in plan.target_requirements
    )


def test_plan_preserves_blueprint_and_candidate() -> None:
    blueprint_decision = bullish_blueprint_decision()
    plan = StrategyPriceReferencePlanFactory().generate(blueprint_decision).plan_required

    assert plan.blueprint is (blueprint_decision.blueprint_required)
    assert plan.candidate is plan.blueprint.candidate


def test_plan_preserves_metadata() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert plan.broker_symbol == "XAUUSDm"
    assert plan.observed_at == OBSERVED_AT
    assert plan.quality_score == Decimal("42.50")
    assert plan.quality_tier.value == "ACCEPTABLE"


def test_plan_is_explicitly_non_executable() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert plan.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "entry_price",
        "stop_loss",
        "take_profit",
        "volume",
        "lot_size",
        "order_type",
        "order_request",
        "broker_ticket",
    ],
)
def test_plan_contains_no_price_or_execution_fields(
    attribute_name: str,
) -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert not hasattr(plan, attribute_name)


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "role": "ENTRY",
            "source": (PricePlanningReferenceSource.FAIR_VALUE_GAP),
            "priority": 1,
            "relation": (PriceReferenceRelation.ENTRY_DISCOUNT),
            "timeframe": TimeframeName.M15,
        },
        {
            "role": PriceReferenceRole.ENTRY,
            "source": (PricePlanningReferenceSource.LIQUIDITY_POOL),
            "priority": 1,
            "relation": (PriceReferenceRelation.ENTRY_DISCOUNT),
            "timeframe": TimeframeName.M15,
        },
        {
            "role": PriceReferenceRole.ENTRY,
            "source": (PricePlanningReferenceSource.FAIR_VALUE_GAP),
            "priority": 0,
            "relation": (PriceReferenceRelation.ENTRY_DISCOUNT),
            "timeframe": TimeframeName.M15,
        },
        {
            "role": PriceReferenceRole.ENTRY,
            "source": (PricePlanningReferenceSource.FAIR_VALUE_GAP),
            "priority": 1,
            "relation": (PriceReferenceRelation.TARGET_ABOVE_ENTRY),
            "timeframe": TimeframeName.M15,
        },
        {
            "role": PriceReferenceRole.ENTRY,
            "source": (PricePlanningReferenceSource.FAIR_VALUE_GAP),
            "priority": 1,
            "relation": (PriceReferenceRelation.ENTRY_DISCOUNT),
            "timeframe": "M15",
        },
    ],
)
def test_invalid_requirement_is_rejected(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        PriceReferenceRequirement(**kwargs)


def test_requirement_stable_id_is_deterministic() -> None:
    requirement = (
        StrategyPriceReferencePlanFactory()
        .generate(bullish_blueprint_decision())
        .plan_required.entry_requirements[0]
    )

    assert requirement.stable_id == ("ENTRY:1:OPTIMAL_TRADE_ENTRY_ZONE:ENTRY_DISCOUNT:M15")


def test_plan_id_is_deterministic() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert plan.plan_id.startswith(plan.blueprint.blueprint_id)
    assert "MODE[FIRST_AVAILABLE]" in plan.plan_id
    assert "ENTRY_DISCOUNT" in plan.plan_id
    assert "STOP_BELOW_ENTRY" in plan.plan_id
    assert "TARGET_ABOVE_ENTRY" in plan.plan_id


def test_plan_stable_id_is_deterministic() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    assert plan.stable_id == (f"{plan.blueprint.stable_id}:PRICE_REFERENCE_PLAN:{plan.plan_id}")


def test_created_decision_stable_id_is_deterministic() -> None:
    blueprint_decision = bullish_blueprint_decision()
    decision = StrategyPriceReferencePlanFactory().generate(blueprint_decision)

    assert decision.stable_id == (
        f"{blueprint_decision.stable_id}:REFERENCE_PLAN_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_lists_blocker() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(blocked_blueprint_decision())

    assert decision.stable_id.endswith(
        "REFERENCE_PLAN_GENERATION:BLOCKED:BLUEPRINT_BLOCKED:BLUEPRINT_BLOCKED"
    )


def test_direct_plan_rejects_wrong_direction() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        replace(
            plan,
            direction=DirectionalPermissionDirection.BEARISH,
        )


def test_direct_plan_rejects_wrong_requirements() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    with pytest.raises(
        ValueError,
        match="requirements",
    ):
        replace(
            plan,
            requirements=plan.requirements[:-1],
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PriceReferencePlanStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PriceReferencePlanReason.BLUEPRINT_BLOCKED),
        )


def test_manual_decision_rejects_missing_plan() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            plan=None,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(blocked_blueprint_decision())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PriceReferencePlanBlocker.BLUEPRINT_BLOCKED,
                PriceReferencePlanBlocker.BLUEPRINT_BLOCKED,
            ),
        )


def test_requirement_is_immutable() -> None:
    requirement = (
        StrategyPriceReferencePlanFactory()
        .generate(bullish_blueprint_decision())
        .plan_required.entry_requirements[0]
    )

    with pytest.raises(FrozenInstanceError):
        requirement.priority = 2


def test_plan_is_immutable() -> None:
    plan = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision()).plan_required

    with pytest.raises(FrozenInstanceError):
        plan.direction = DirectionalPermissionDirection.BEARISH


def test_decision_is_immutable() -> None:
    decision = StrategyPriceReferencePlanFactory().generate(bullish_blueprint_decision())

    with pytest.raises(FrozenInstanceError):
        decision.status = PriceReferencePlanStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = PriceReferencePlanPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.stop_on_execution_timeframe = False


def test_generation_is_deterministic() -> None:
    factory = StrategyPriceReferencePlanFactory()
    blueprint_decision = bullish_blueprint_decision()

    assert factory.generate(blueprint_decision) == factory.generate(blueprint_decision)


def test_function_api_delegates() -> None:
    decision = generate_price_reference_plan(bullish_blueprint_decision())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPriceReferencePlanFactory()
    blueprint_decision = bullish_blueprint_decision()

    assert factory.build(blueprint_decision) == factory.generate(blueprint_decision)
    assert factory.evaluate(blueprint_decision) == factory.generate(blueprint_decision)


def test_public_aliases_are_preserved() -> None:
    assert DirectionalReferencePlan is DirectionalPriceReferencePlan
    assert PlanningReferencePlanDecision is PriceReferencePlanDecision
    assert PlanningReferencePlanFactory is StrategyPriceReferencePlanFactory
    assert PlanningReferencePlanPolicy is PriceReferencePlanPolicy
    assert PriceReferencePlanFactory is StrategyPriceReferencePlanFactory
    assert ReferencePlanBlocker is PriceReferencePlanBlocker
    assert ReferencePlanReason is PriceReferencePlanReason
    assert ReferencePlanStatus is PriceReferencePlanStatus
    assert ReferenceRequirement is PriceReferenceRequirement
