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
    PricePlanningAdmissionDecision,
    StrategyPricePlanningAdmissionGate,
)
from app.strategy.price_planning_blueprint import (
    PlanningBlueprint,
    PlanningBlueprintBlocker,
    PlanningBlueprintDecision,
    PlanningBlueprintFactory,
    PlanningBlueprintPolicy,
    PlanningBlueprintReason,
    PlanningBlueprintStatus,
    PlanningReferenceSource,
    PriceBlueprintFactory,
    PricePlanningBlueprint,
    PricePlanningBlueprintBlocker,
    PricePlanningBlueprintDecision,
    PricePlanningBlueprintError,
    PricePlanningBlueprintErrorReason,
    PricePlanningBlueprintPolicy,
    PricePlanningBlueprintReason,
    PricePlanningBlueprintStatus,
    PricePlanningReferenceSource,
    StrategyPricePlanningBlueprintFactory,
    generate_price_planning_blueprint,
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


def admission_for(
    direction: DirectionalPermissionDirection,
    *,
    blocked: bool = False,
) -> PricePlanningAdmissionDecision:
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

    return StrategyPricePlanningAdmissionGate().evaluate(quality)


@lru_cache(maxsize=1)
def bullish_admission() -> PricePlanningAdmissionDecision:
    return admission_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_admission() -> PricePlanningAdmissionDecision:
    return admission_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_admission() -> PricePlanningAdmissionDecision:
    return admission_for(
        DirectionalPermissionDirection.BULLISH,
        blocked=True,
    )


def test_default_entry_priority() -> None:
    policy = PricePlanningBlueprintPolicy()

    assert policy.entry_source_priority == (
        PricePlanningReferenceSource.OPTIMAL_TRADE_ENTRY_ZONE,
        PricePlanningReferenceSource.FAIR_VALUE_GAP,
        PricePlanningReferenceSource.ORDER_BLOCK,
    )


def test_default_stop_source() -> None:
    policy = PricePlanningBlueprintPolicy()

    assert policy.stop_reference_source == (PricePlanningReferenceSource.PROTECTED_SWING)


def test_default_target_priority() -> None:
    policy = PricePlanningBlueprintPolicy()

    assert policy.target_source_priority == (
        PricePlanningReferenceSource.LIQUIDITY_POOL,
        PricePlanningReferenceSource.DEALING_RANGE_EXTREME,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"entry_source_priority": []},
        {"entry_source_priority": ()},
        {"entry_source_priority": ("FAIR_VALUE_GAP",)},
        {
            "entry_source_priority": (
                PricePlanningReferenceSource.FAIR_VALUE_GAP,
                PricePlanningReferenceSource.FAIR_VALUE_GAP,
            )
        },
        {"entry_source_priority": (PricePlanningReferenceSource.LIQUIDITY_POOL,)},
        {"stop_reference_source": "PROTECTED_SWING"},
        {"stop_reference_source": (PricePlanningReferenceSource.ORDER_BLOCK)},
        {"target_source_priority": []},
        {"target_source_priority": ()},
        {"target_source_priority": ("LIQUIDITY_POOL",)},
        {
            "target_source_priority": (
                PricePlanningReferenceSource.LIQUIDITY_POOL,
                PricePlanningReferenceSource.LIQUIDITY_POOL,
            )
        },
        {"target_source_priority": (PricePlanningReferenceSource.ORDER_BLOCK,)},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        PricePlanningBlueprintPolicy(**overrides)


def test_factory_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PricePlanningBlueprintPolicy",
    ):
        StrategyPricePlanningBlueprintFactory(policy="invalid")


def test_invalid_admission_is_fail_safe() -> None:
    with pytest.raises(
        PricePlanningBlueprintError,
        match="INVALID_ADMISSION",
    ) as captured:
        StrategyPricePlanningBlueprintFactory().generate("invalid")

    assert captured.value.reason == (PricePlanningBlueprintErrorReason.INVALID_ADMISSION)


def test_bullish_blueprint_is_created() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(bullish_admission())

    assert decision.status == (PricePlanningBlueprintStatus.CREATED)
    assert decision.reason == (PricePlanningBlueprintReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_blueprint is True


def test_bearish_blueprint_is_created() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(bearish_admission())

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.blueprint_required.is_bearish is True


def test_blocked_admission_produces_no_blueprint() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(blocked_admission())

    assert decision.is_blocked is True
    assert decision.has_blueprint is False
    assert decision.blueprint is None
    assert decision.reason == (PricePlanningBlueprintReason.ADMISSION_BLOCKED)
    assert decision.blockers == (PricePlanningBlueprintBlocker.ADMISSION_BLOCKED,)


def test_blueprint_required_rejects_blocked_result() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(blocked_admission())

    with pytest.raises(
        ValueError,
        match="No price-planning blueprint",
    ):
        _ = decision.blueprint_required


def test_custom_source_priorities_are_preserved() -> None:
    policy = PricePlanningBlueprintPolicy(
        entry_source_priority=(
            PricePlanningReferenceSource.ORDER_BLOCK,
            PricePlanningReferenceSource.FAIR_VALUE_GAP,
        ),
        target_source_priority=(
            PricePlanningReferenceSource.DEALING_RANGE_EXTREME,
            PricePlanningReferenceSource.LIQUIDITY_POOL,
        ),
    )

    blueprint = (
        StrategyPricePlanningBlueprintFactory(policy)
        .generate(bullish_admission())
        .blueprint_required
    )

    assert blueprint.entry_sources == (
        PricePlanningReferenceSource.ORDER_BLOCK,
        PricePlanningReferenceSource.FAIR_VALUE_GAP,
    )
    assert blueprint.target_sources == (
        PricePlanningReferenceSource.DEALING_RANGE_EXTREME,
        PricePlanningReferenceSource.LIQUIDITY_POOL,
    )


def test_blueprint_uses_m15_and_m5_roles() -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    assert blueprint.setup_timeframe == TimeframeName.M15
    assert blueprint.execution_timeframe == TimeframeName.M5


def test_blueprint_preserves_candidate() -> None:
    admission = bullish_admission()
    blueprint = StrategyPricePlanningBlueprintFactory().generate(admission).blueprint_required

    assert blueprint.admission is admission
    assert blueprint.candidate is admission.candidate


def test_blueprint_preserves_metadata() -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    assert blueprint.broker_symbol == "XAUUSDm"
    assert blueprint.observed_at == OBSERVED_AT
    assert blueprint.quality_score == Decimal("42.50")


def test_blueprint_preserves_quality_tier() -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    assert blueprint.quality_tier.value == "ACCEPTABLE"


def test_blueprint_is_explicitly_non_executable() -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    assert blueprint.is_executable is False


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
def test_blueprint_contains_no_execution_fields(
    attribute_name: str,
) -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    assert not hasattr(blueprint, attribute_name)


def test_blueprint_id_is_deterministic() -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    assert blueprint.blueprint_id.endswith(
        "BULLISH:M15:M5:"
        "ENTRY[OPTIMAL_TRADE_ENTRY_ZONE,"
        "FAIR_VALUE_GAP,ORDER_BLOCK]:"
        "STOP[PROTECTED_SWING]:"
        "TARGET[LIQUIDITY_POOL,"
        "DEALING_RANGE_EXTREME]"
    )


def test_blueprint_stable_id_is_deterministic() -> None:
    admission = bullish_admission()
    blueprint = StrategyPricePlanningBlueprintFactory().generate(admission).blueprint_required

    assert blueprint.stable_id == (
        f"{admission.stable_id}:PRICE_PLANNING_BLUEPRINT:{blueprint.blueprint_id}"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    admission = bullish_admission()
    decision = StrategyPricePlanningBlueprintFactory().generate(admission)

    assert decision.stable_id == (
        f"{admission.stable_id}:BLUEPRINT_GENERATION:CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_lists_blocker() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(blocked_admission())

    assert decision.stable_id.endswith(
        "BLUEPRINT_GENERATION:BLOCKED:ADMISSION_BLOCKED:ADMISSION_BLOCKED"
    )


def test_direct_blueprint_rejects_blocked_admission() -> None:
    policy = PricePlanningBlueprintPolicy()

    with pytest.raises(
        ValueError,
        match="admitted",
    ):
        PricePlanningBlueprint(
            admission=blocked_admission(),
            policy=policy,
            direction=(DirectionalPermissionDirection.BULLISH),
            setup_timeframe=TimeframeName.M15,
            execution_timeframe=TimeframeName.M5,
            entry_sources=policy.entry_source_priority,
            stop_source=policy.stop_reference_source,
            target_sources=policy.target_source_priority,
        )


def test_direct_blueprint_rejects_wrong_direction() -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        replace(
            blueprint,
            direction=DirectionalPermissionDirection.BEARISH,
        )


def test_direct_blueprint_rejects_wrong_setup_timeframe() -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="setup timeframe",
    ):
        replace(
            blueprint,
            setup_timeframe=TimeframeName.H1,
        )


def test_direct_blueprint_rejects_wrong_sources() -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    with pytest.raises(
        ValueError,
        match="entry sources",
    ):
        replace(
            blueprint,
            entry_sources=(PricePlanningReferenceSource.ORDER_BLOCK,),
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(bullish_admission())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PricePlanningBlueprintStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(bullish_admission())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PricePlanningBlueprintReason.ADMISSION_BLOCKED),
        )


def test_manual_decision_rejects_missing_blueprint() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(bullish_admission())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            blueprint=None,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(blocked_admission())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PricePlanningBlueprintBlocker.ADMISSION_BLOCKED,
                PricePlanningBlueprintBlocker.ADMISSION_BLOCKED,
            ),
        )


def test_blueprint_is_immutable() -> None:
    blueprint = (
        StrategyPricePlanningBlueprintFactory().generate(bullish_admission()).blueprint_required
    )

    with pytest.raises(FrozenInstanceError):
        blueprint.direction = DirectionalPermissionDirection.BEARISH


def test_decision_is_immutable() -> None:
    decision = StrategyPricePlanningBlueprintFactory().generate(bullish_admission())

    with pytest.raises(FrozenInstanceError):
        decision.status = PricePlanningBlueprintStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = PricePlanningBlueprintPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.stop_reference_source = PricePlanningReferenceSource.ORDER_BLOCK


def test_generation_is_deterministic() -> None:
    factory = StrategyPricePlanningBlueprintFactory()
    admission = bullish_admission()

    assert factory.generate(admission) == factory.generate(admission)


def test_function_api_delegates() -> None:
    decision = generate_price_planning_blueprint(bullish_admission())

    assert decision.is_created is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategyPricePlanningBlueprintFactory()
    admission = bullish_admission()

    assert factory.build(admission) == factory.generate(admission)
    assert factory.evaluate(admission) == factory.generate(admission)


def test_public_aliases_are_preserved() -> None:
    assert PlanningBlueprint is PricePlanningBlueprint
    assert PlanningBlueprintBlocker is PricePlanningBlueprintBlocker
    assert PlanningBlueprintDecision is PricePlanningBlueprintDecision
    assert PlanningBlueprintFactory is StrategyPricePlanningBlueprintFactory
    assert PlanningBlueprintPolicy is PricePlanningBlueprintPolicy
    assert PlanningBlueprintReason is PricePlanningBlueprintReason
    assert PlanningBlueprintStatus is PricePlanningBlueprintStatus
    assert PlanningReferenceSource is PricePlanningReferenceSource
    assert PriceBlueprintFactory is StrategyPricePlanningBlueprintFactory
