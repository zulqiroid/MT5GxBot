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
    PriceReferenceResolutionDecision,
    PriceReferenceResolutionPolicy,
    PriceReferenceValueObservation,
    PriceReferenceValueSnapshot,
    StrategyPriceReferenceResolutionGate,
)
from app.strategy.reward_risk_analysis import (
    RewardRiskAnalysisBlocker,
    RewardRiskAnalysisDecision,
    RewardRiskAnalysisError,
    RewardRiskAnalysisErrorReason,
    RewardRiskAnalysisPolicy,
    RewardRiskAnalysisReason,
    RewardRiskAnalysisStatus,
    RewardRiskBlocker,
    RewardRiskDecision,
    RewardRiskGate,
    RewardRiskMetrics,
    RewardRiskPolicy,
    RewardRiskReason,
    RewardRiskStatus,
    StrategyRewardRiskAnalysisGate,
    StrategyRewardRiskGate,
    evaluate_reward_risk,
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


def resolution_for(
    direction: DirectionalPermissionDirection,
    *,
    entry_value: Decimal | None,
    stop_value: Decimal | None,
    target_value: Decimal | None,
    waived_roles: tuple[PriceReferenceRole, ...] = (),
    validate_directional_order: bool = True,
    upstream_blocked: bool = False,
) -> PriceReferenceResolutionDecision:
    plan_decision = (
        blocked_plan_decision()
        if upstream_blocked
        else (
            bullish_plan_decision()
            if direction == DirectionalPermissionDirection.BULLISH
            else bearish_plan_decision()
        )
    )

    if plan_decision.is_blocked:
        availability = StrategyPriceReferenceAvailabilityGate().evaluate(plan_decision)

        return StrategyPriceReferenceResolutionGate().evaluate(availability)

    plan = plan_decision.plan_required
    availability_policy = PriceReferenceAvailabilityPolicy(
        require_entry_reference=(PriceReferenceRole.ENTRY not in waived_roles),
        require_stop_reference=(PriceReferenceRole.STOP not in waived_roles),
        require_target_reference=(PriceReferenceRole.TARGET not in waived_roles),
    )
    availability_snapshot = PriceReferenceAvailabilitySnapshot(
        plan=plan,
        items=tuple(
            PriceReferenceAvailabilityItem(
                requirement=requirement,
                available=(requirement.role not in waived_roles),
            )
            for requirement in plan.requirements
        ),
    )
    availability = StrategyPriceReferenceAvailabilityGate(availability_policy).evaluate(
        plan_decision,
        availability_snapshot,
    )
    role_values = {
        PriceReferenceRole.ENTRY: entry_value,
        PriceReferenceRole.STOP: stop_value,
        PriceReferenceRole.TARGET: target_value,
    }
    selected_requirements = (
        availability.selected_entry,
        availability.selected_stop,
        availability.selected_target,
    )
    observations = tuple(
        PriceReferenceValueObservation(
            requirement=requirement,
            value=role_values[requirement.role],
        )
        for requirement in selected_requirements
        if (requirement is not None and role_values[requirement.role] is not None)
    )
    value_snapshot = PriceReferenceValueSnapshot(
        plan=plan,
        observations=observations,
    )

    return StrategyPriceReferenceResolutionGate(
        PriceReferenceResolutionPolicy(validate_directional_order=(validate_directional_order))
    ).evaluate(
        availability,
        value_snapshot,
    )


@lru_cache(maxsize=1)
def bullish_two_to_one_resolution() -> PriceReferenceResolutionDecision:
    return resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
    )


@lru_cache(maxsize=1)
def bearish_two_point_five_resolution() -> PriceReferenceResolutionDecision:
    return resolution_for(
        DirectionalPermissionDirection.BEARISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2360"),
        target_value=Decimal("2325"),
    )


def test_default_policy_requires_two_to_one() -> None:
    policy = RewardRiskAnalysisPolicy()

    assert policy.minimum_reward_risk == Decimal("2")


@pytest.mark.parametrize(
    "value",
    [
        2,
        "2",
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_invalid_policy_is_rejected(
    value: object,
) -> None:
    with pytest.raises(ValueError):
        RewardRiskAnalysisPolicy(minimum_reward_risk=value)


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="RewardRiskAnalysisPolicy",
    ):
        StrategyRewardRiskAnalysisGate(policy="invalid")


def test_invalid_resolution_is_fail_safe() -> None:
    with pytest.raises(
        RewardRiskAnalysisError,
        match="INVALID_RESOLUTION_DECISION",
    ) as captured:
        StrategyRewardRiskAnalysisGate().evaluate("invalid")

    assert captured.value.reason == (RewardRiskAnalysisErrorReason.INVALID_RESOLUTION_DECISION)


def test_bullish_two_to_one_is_qualified() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    assert decision.status == (RewardRiskAnalysisStatus.QUALIFIED)
    assert decision.reason == (RewardRiskAnalysisReason.QUALIFIED)
    assert decision.blockers == ()
    assert decision.is_qualified is True


def test_bearish_ratio_is_qualified() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bearish_two_point_five_resolution())

    assert decision.is_qualified is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.reward_risk_ratio == (Decimal("2.5"))


def test_bullish_distances_are_exact() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    assert decision.risk_distance == Decimal("10")
    assert decision.reward_distance == Decimal("20")
    assert decision.reward_risk_ratio == Decimal("2")


def test_bearish_distances_are_exact() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bearish_two_point_five_resolution())

    assert decision.risk_distance == Decimal("10")
    assert decision.reward_distance == Decimal("25")
    assert decision.reward_risk_ratio == Decimal("2.5")


def test_exact_custom_threshold_is_qualified() -> None:
    policy = RewardRiskAnalysisPolicy(minimum_reward_risk=Decimal("2.5"))

    decision = StrategyRewardRiskAnalysisGate(policy).evaluate(bearish_two_point_five_resolution())

    assert decision.is_qualified is True


def test_ratio_below_minimum_is_blocked() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2365"),
    )

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.is_blocked is True
    assert decision.reason == (RewardRiskAnalysisReason.BELOW_MINIMUM_REWARD_RISK)
    assert decision.blockers == (RewardRiskAnalysisBlocker.BELOW_MINIMUM_REWARD_RISK,)
    assert decision.reward_risk_ratio == (Decimal("1.5"))


def test_custom_lower_threshold_can_qualify() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2365"),
    )
    policy = RewardRiskAnalysisPolicy(minimum_reward_risk=Decimal("1.5"))

    decision = StrategyRewardRiskAnalysisGate(policy).evaluate(resolution)

    assert decision.is_qualified is True


def test_blocked_resolution_is_blocked() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=None,
        stop_value=None,
        target_value=None,
        upstream_blocked=True,
    )

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.RESOLUTION_BLOCKED)
    assert decision.metrics is None
    assert decision.blockers == (RewardRiskAnalysisBlocker.RESOLUTION_BLOCKED,)


def test_missing_entry_value_blocks() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=None,
        stop_value=Decimal("2340"),
        target_value=Decimal("2370"),
        waived_roles=(PriceReferenceRole.ENTRY,),
    )

    assert resolution.is_resolved is True

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.ENTRY_VALUE_MISSING)
    assert decision.blockers == (RewardRiskAnalysisBlocker.ENTRY_VALUE_MISSING,)


def test_missing_stop_value_blocks() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=None,
        target_value=Decimal("2370"),
        waived_roles=(PriceReferenceRole.STOP,),
    )

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.STOP_VALUE_MISSING)


def test_missing_target_value_blocks() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=None,
        waived_roles=(PriceReferenceRole.TARGET,),
    )

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.TARGET_VALUE_MISSING)


def test_multiple_missing_values_preserve_order() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=None,
        stop_value=None,
        target_value=None,
        waived_roles=(
            PriceReferenceRole.ENTRY,
            PriceReferenceRole.STOP,
            PriceReferenceRole.TARGET,
        ),
    )

    assert resolution.is_resolved is True

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.MULTIPLE_VALUES_MISSING)
    assert decision.blockers == (
        RewardRiskAnalysisBlocker.ENTRY_VALUE_MISSING,
        RewardRiskAnalysisBlocker.STOP_VALUE_MISSING,
        RewardRiskAnalysisBlocker.TARGET_VALUE_MISSING,
    )


def test_invalid_bullish_risk_distance_blocks() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2360"),
        target_value=Decimal("2370"),
        validate_directional_order=False,
    )

    assert resolution.is_resolved is True

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.INVALID_RISK_DISTANCE)


def test_invalid_bullish_reward_distance_blocks() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2345"),
        validate_directional_order=False,
    )

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.INVALID_REWARD_DISTANCE)


def test_multiple_invalid_distances_preserve_order() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2360"),
        target_value=Decimal("2340"),
        validate_directional_order=False,
    )

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.MULTIPLE_DISTANCES_INVALID)
    assert decision.blockers == (
        RewardRiskAnalysisBlocker.INVALID_RISK_DISTANCE,
        RewardRiskAnalysisBlocker.INVALID_REWARD_DISTANCE,
    )


def test_invalid_bearish_risk_distance_blocks() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BEARISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2325"),
        validate_directional_order=False,
    )

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.INVALID_RISK_DISTANCE)


def test_invalid_bearish_reward_distance_blocks() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BEARISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2360"),
        target_value=Decimal("2370"),
        validate_directional_order=False,
    )

    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert decision.reason == (RewardRiskAnalysisReason.INVALID_REWARD_DISTANCE)


def test_metrics_preserve_prices() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    assert decision.entry_value == Decimal("2350")
    assert decision.stop_value == Decimal("2340")
    assert decision.target_value == Decimal("2370")
    assert decision.has_metrics is True


def test_decision_preserves_metadata() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.blocker_count == 0


def test_decision_preserves_policy_threshold() -> None:
    policy = RewardRiskAnalysisPolicy(minimum_reward_risk=Decimal("1.75"))
    decision = StrategyRewardRiskAnalysisGate(policy).evaluate(bullish_two_to_one_resolution())

    assert decision.minimum_reward_risk == (Decimal("1.75"))


def test_decision_is_explicitly_non_executable() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    assert decision.is_executable is False
    assert decision.can_continue_to_risk_admission is True


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
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    assert not hasattr(decision, attribute_name)


@pytest.mark.parametrize(
    "overrides",
    [
        {"direction": "BULLISH"},
        {"entry_value": Decimal("0")},
        {"stop_value": Decimal("-1")},
        {"target_value": Decimal("NaN")},
        {"risk_distance": Decimal("0")},
        {"reward_distance": Decimal("0")},
        {"reward_risk_ratio": Decimal("0")},
    ],
)
def test_invalid_direct_metrics_are_rejected(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "direction": (DirectionalPermissionDirection.BULLISH),
        "entry_value": Decimal("2350"),
        "stop_value": Decimal("2340"),
        "target_value": Decimal("2370"),
        "risk_distance": Decimal("10"),
        "reward_distance": Decimal("20"),
        "reward_risk_ratio": Decimal("2"),
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        RewardRiskMetrics(**values)


def test_metrics_reject_wrong_risk_distance() -> None:
    with pytest.raises(
        ValueError,
        match="risk_distance",
    ):
        RewardRiskMetrics(
            direction=(DirectionalPermissionDirection.BULLISH),
            entry_value=Decimal("2350"),
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
            risk_distance=Decimal("11"),
            reward_distance=Decimal("20"),
            reward_risk_ratio=Decimal("2"),
        )


def test_metrics_reject_wrong_ratio() -> None:
    with pytest.raises(
        ValueError,
        match="reward_risk_ratio",
    ):
        RewardRiskMetrics(
            direction=(DirectionalPermissionDirection.BULLISH),
            entry_value=Decimal("2350"),
            stop_value=Decimal("2340"),
            target_value=Decimal("2370"),
            risk_distance=Decimal("10"),
            reward_distance=Decimal("20"),
            reward_risk_ratio=Decimal("3"),
        )


def test_metrics_stable_id_is_deterministic() -> None:
    metrics = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution()).metrics

    assert metrics is not None
    assert metrics.stable_id == (
        "BULLISH:ENTRY[2350]:STOP[2340]:TARGET[2370]:RISK[10]:REWARD[20]:RR[2]"
    )


def test_qualified_stable_id_is_deterministic() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    assert decision.stable_id.startswith(
        f"{decision.resolution.stable_id}:REWARD_RISK_ANALYSIS:QUALIFIED:QUALIFIED:NONE:"
    )
    assert decision.stable_id.endswith("RR[2]")


def test_blocked_stable_id_lists_blocker() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2365"),
    )
    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    assert "BELOW_MINIMUM_REWARD_RISK" in decision.stable_id
    assert "RR[1.5]" in decision.stable_id


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=RewardRiskAnalysisStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_metrics() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    assert decision.metrics is not None

    modified = replace(
        decision.metrics,
        target_value=Decimal("2380"),
        reward_distance=Decimal("30"),
        reward_risk_ratio=Decimal("3"),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            metrics=modified,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    resolution = resolution_for(
        DirectionalPermissionDirection.BULLISH,
        entry_value=Decimal("2350"),
        stop_value=Decimal("2340"),
        target_value=Decimal("2365"),
    )
    decision = StrategyRewardRiskAnalysisGate().evaluate(resolution)

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                RewardRiskAnalysisBlocker.BELOW_MINIMUM_REWARD_RISK,
                RewardRiskAnalysisBlocker.BELOW_MINIMUM_REWARD_RISK,
            ),
        )


def test_metrics_are_immutable() -> None:
    metrics = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution()).metrics

    assert metrics is not None

    with pytest.raises(FrozenInstanceError):
        metrics.risk_distance = Decimal("11")


def test_decision_is_immutable() -> None:
    decision = StrategyRewardRiskAnalysisGate().evaluate(bullish_two_to_one_resolution())

    with pytest.raises(FrozenInstanceError):
        decision.status = RewardRiskAnalysisStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = RewardRiskAnalysisPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.minimum_reward_risk = Decimal("3")


def test_evaluation_is_deterministic() -> None:
    gate = StrategyRewardRiskAnalysisGate()
    resolution = bullish_two_to_one_resolution()

    assert gate.evaluate(resolution) == gate.evaluate(resolution)


def test_function_api_delegates() -> None:
    decision = evaluate_reward_risk(bullish_two_to_one_resolution())

    assert decision.is_qualified is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategyRewardRiskAnalysisGate()
    resolution = bullish_two_to_one_resolution()

    assert gate.qualify(resolution) == gate.evaluate(resolution)
    assert gate.analyze(resolution) == gate.evaluate(resolution)


def test_public_aliases_are_preserved() -> None:
    assert RewardRiskBlocker is RewardRiskAnalysisBlocker
    assert RewardRiskDecision is RewardRiskAnalysisDecision
    assert RewardRiskGate is StrategyRewardRiskAnalysisGate
    assert RewardRiskPolicy is RewardRiskAnalysisPolicy
    assert RewardRiskReason is RewardRiskAnalysisReason
    assert RewardRiskStatus is RewardRiskAnalysisStatus
    assert StrategyRewardRiskGate is StrategyRewardRiskAnalysisGate
