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
    PlanningAdmissionBlocker,
    PlanningAdmissionDecision,
    PlanningAdmissionGate,
    PlanningAdmissionPolicy,
    PlanningAdmissionReason,
    PlanningAdmissionStatus,
    PricePlanningAdmissionBlocker,
    PricePlanningAdmissionDecision,
    PricePlanningAdmissionError,
    PricePlanningAdmissionErrorReason,
    PricePlanningAdmissionPolicy,
    PricePlanningAdmissionReason,
    PricePlanningAdmissionStatus,
    PricePlanningGate,
    StrategyPricePlanningAdmissionGate,
    evaluate_price_planning_admission,
)
from app.strategy.setup_candidate import (
    StrategySetupCandidate,
    StrategySetupCandidateFactory,
)
from app.strategy.setup_candidate_quality import (
    SetupCandidateQualityDecision,
    SetupCandidateQualityPolicy,
    SetupCandidateQualityStatus,
    SetupCandidateQualityTier,
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


def candidate_for(
    direction: DirectionalPermissionDirection,
    *,
    execution_aligned: bool = False,
) -> StrategySetupCandidate:
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
                    if (
                        timeframe
                        in {
                            TimeframeName.H4,
                            TimeframeName.H1,
                            TimeframeName.M15,
                        }
                        or (execution_aligned and timeframe == TimeframeName.M5)
                    )
                    else MarketStructureBias.NEUTRAL
                ),
            )
            for timeframe in GOLD_TIMEFRAME_HIERARCHY
        ),
    )
    analysis = MultiTimeframeAnalysisPipeline().evaluate_context(context)
    qualification = StrategySetupQualificationGate().evaluate(analysis)

    return StrategySetupCandidateFactory().generate(qualification).candidate_required


@lru_cache(maxsize=1)
def acceptable_quality() -> SetupCandidateQualityDecision:
    return StrategySetupCandidateQualityGate().evaluate(
        candidate_for(DirectionalPermissionDirection.BULLISH)
    )


@lru_cache(maxsize=1)
def strong_quality() -> SetupCandidateQualityDecision:
    return StrategySetupCandidateQualityGate().evaluate(
        candidate_for(
            DirectionalPermissionDirection.BULLISH,
            execution_aligned=True,
        )
    )


@lru_cache(maxsize=1)
def blocked_quality() -> SetupCandidateQualityDecision:
    policy = SetupCandidateQualityPolicy(minimum_score=Decimal("43"))

    return StrategySetupCandidateQualityGate(policy).evaluate(
        candidate_for(DirectionalPermissionDirection.BULLISH)
    )


@lru_cache(maxsize=1)
def weak_accepted_quality() -> SetupCandidateQualityDecision:
    policy = SetupCandidateQualityPolicy(
        alignment_weight=Decimal("20"),
        setup_evidence_weight=Decimal("40"),
        execution_evidence_weight=Decimal("30"),
        execution_bias_weight=Decimal("10"),
        minimum_score=Decimal("0"),
    )

    return StrategySetupCandidateQualityGate(policy).evaluate(
        candidate_for(DirectionalPermissionDirection.BULLISH)
    )


@lru_cache(maxsize=1)
def premium_quality() -> SetupCandidateQualityDecision:
    policy = SetupCandidateQualityPolicy(
        alignment_weight=Decimal("90"),
        setup_evidence_weight=Decimal("0"),
        execution_evidence_weight=Decimal("0"),
        execution_bias_weight=Decimal("10"),
        minimum_score=Decimal("0"),
    )

    return StrategySetupCandidateQualityGate(policy).evaluate(
        candidate_for(
            DirectionalPermissionDirection.BULLISH,
            execution_aligned=True,
        )
    )


def test_default_policy_requires_acceptable_tier() -> None:
    policy = PricePlanningAdmissionPolicy()

    assert policy.minimum_tier == (SetupCandidateQualityTier.ACCEPTABLE)


def test_policy_rejects_raw_string_tier() -> None:
    with pytest.raises(
        ValueError,
        match="SetupCandidateQualityTier",
    ):
        PricePlanningAdmissionPolicy(minimum_tier="ACCEPTABLE")


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PricePlanningAdmissionPolicy",
    ):
        StrategyPricePlanningAdmissionGate(policy="invalid")


def test_invalid_quality_decision_is_fail_safe() -> None:
    with pytest.raises(
        PricePlanningAdmissionError,
        match="INVALID_QUALITY_DECISION",
    ) as captured:
        StrategyPricePlanningAdmissionGate().evaluate("invalid")

    assert captured.value.reason == (PricePlanningAdmissionErrorReason.INVALID_QUALITY_DECISION)


def test_default_acceptable_quality_is_admitted() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(acceptable_quality())

    assert decision.status == (PricePlanningAdmissionStatus.ADMITTED)
    assert decision.reason == (PricePlanningAdmissionReason.ADMITTED)
    assert decision.blockers == ()
    assert decision.is_admitted is True
    assert decision.can_plan_prices is True


def test_blocked_quality_is_blocked() -> None:
    quality = blocked_quality()
    decision = StrategyPricePlanningAdmissionGate().evaluate(quality)

    assert quality.status == (SetupCandidateQualityStatus.BLOCKED)
    assert decision.is_blocked is True
    assert decision.reason == (PricePlanningAdmissionReason.QUALITY_BLOCKED)
    assert decision.blockers == (PricePlanningAdmissionBlocker.QUALITY_BLOCKED,)


def test_weak_accepted_quality_is_blocked() -> None:
    quality = weak_accepted_quality()
    decision = StrategyPricePlanningAdmissionGate().evaluate(quality)

    assert quality.is_accepted is True
    assert quality.tier == SetupCandidateQualityTier.WEAK
    assert decision.reason == (PricePlanningAdmissionReason.QUALITY_TIER_BELOW_MINIMUM)
    assert decision.blockers == (PricePlanningAdmissionBlocker.QUALITY_TIER_BELOW_MINIMUM,)


def test_weak_tier_can_be_admitted_explicitly() -> None:
    policy = PricePlanningAdmissionPolicy(minimum_tier=SetupCandidateQualityTier.WEAK)

    decision = StrategyPricePlanningAdmissionGate(policy).evaluate(weak_accepted_quality())

    assert decision.is_admitted is True


def test_strong_quality_meets_strong_requirement() -> None:
    policy = PricePlanningAdmissionPolicy(minimum_tier=SetupCandidateQualityTier.STRONG)

    decision = StrategyPricePlanningAdmissionGate(policy).evaluate(strong_quality())

    assert decision.is_admitted is True
    assert decision.tier == SetupCandidateQualityTier.STRONG


def test_acceptable_quality_fails_strong_requirement() -> None:
    policy = PricePlanningAdmissionPolicy(minimum_tier=SetupCandidateQualityTier.STRONG)

    decision = StrategyPricePlanningAdmissionGate(policy).evaluate(acceptable_quality())

    assert decision.is_blocked is True
    assert decision.reason == (PricePlanningAdmissionReason.QUALITY_TIER_BELOW_MINIMUM)


def test_premium_requirement_blocks_strong_quality() -> None:
    policy = PricePlanningAdmissionPolicy(minimum_tier=SetupCandidateQualityTier.PREMIUM)

    decision = StrategyPricePlanningAdmissionGate(policy).evaluate(strong_quality())

    assert decision.is_blocked is True


def test_premium_quality_meets_premium_requirement() -> None:
    policy = PricePlanningAdmissionPolicy(minimum_tier=SetupCandidateQualityTier.PREMIUM)

    decision = StrategyPricePlanningAdmissionGate(policy).evaluate(premium_quality())

    assert decision.is_admitted is True
    assert decision.tier == (SetupCandidateQualityTier.PREMIUM)


def test_decision_preserves_quality_and_candidate() -> None:
    quality = acceptable_quality()
    decision = StrategyPricePlanningAdmissionGate().evaluate(quality)

    assert decision.quality is quality
    assert decision.candidate is quality.candidate


def test_decision_preserves_metadata() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(acceptable_quality())

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.blocker_count == 0


def test_decision_preserves_direction_score_and_tier() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(acceptable_quality())

    assert decision.direction == (DirectionalPermissionDirection.BULLISH)
    assert decision.score == Decimal("42.50")
    assert decision.tier == (SetupCandidateQualityTier.ACCEPTABLE)
    assert decision.minimum_tier == (SetupCandidateQualityTier.ACCEPTABLE)


def test_admission_is_explicitly_non_executable() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(acceptable_quality())

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
def test_admission_contains_no_execution_fields(
    attribute_name: str,
) -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(acceptable_quality())

    assert not hasattr(decision, attribute_name)


def test_admitted_stable_id_is_deterministic() -> None:
    quality = acceptable_quality()
    decision = StrategyPricePlanningAdmissionGate().evaluate(quality)

    assert decision.stable_id == (
        f"{quality.stable_id}:PRICE_PLANNING_ADMISSION:ADMITTED:ADMITTED:ACCEPTABLE:ACCEPTABLE:NONE"
    )


def test_quality_blocked_stable_id_lists_blocker() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(blocked_quality())

    assert decision.stable_id.endswith(
        "PRICE_PLANNING_ADMISSION:BLOCKED:QUALITY_BLOCKED:ACCEPTABLE:ACCEPTABLE:QUALITY_BLOCKED"
    )


def test_tier_blocked_stable_id_lists_blocker() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(weak_accepted_quality())

    assert decision.stable_id.endswith(
        "PRICE_PLANNING_ADMISSION:"
        "BLOCKED:QUALITY_TIER_BELOW_MINIMUM:"
        "WEAK:ACCEPTABLE:"
        "QUALITY_TIER_BELOW_MINIMUM"
    )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(acceptable_quality())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=PricePlanningAdmissionStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(acceptable_quality())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(PricePlanningAdmissionReason.QUALITY_BLOCKED),
        )


def test_manual_decision_rejects_wrong_blockers() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(acceptable_quality())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            blockers=(PricePlanningAdmissionBlocker.QUALITY_BLOCKED,),
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(blocked_quality())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                PricePlanningAdmissionBlocker.QUALITY_BLOCKED,
                PricePlanningAdmissionBlocker.QUALITY_BLOCKED,
            ),
        )


def test_decision_is_immutable() -> None:
    decision = StrategyPricePlanningAdmissionGate().evaluate(acceptable_quality())

    with pytest.raises(FrozenInstanceError):
        decision.status = PricePlanningAdmissionStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = PricePlanningAdmissionPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.minimum_tier = SetupCandidateQualityTier.PREMIUM


def test_evaluation_is_deterministic() -> None:
    gate = StrategyPricePlanningAdmissionGate()
    quality = acceptable_quality()

    assert gate.evaluate(quality) == gate.evaluate(quality)


def test_function_api_delegates() -> None:
    decision = evaluate_price_planning_admission(acceptable_quality())

    assert decision.is_admitted is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategyPricePlanningAdmissionGate()
    quality = acceptable_quality()

    assert gate.admit(quality) == gate.evaluate(quality)
    assert gate.check(quality) == gate.evaluate(quality)


def test_public_aliases_are_preserved() -> None:
    assert PlanningAdmissionBlocker is PricePlanningAdmissionBlocker
    assert PlanningAdmissionDecision is PricePlanningAdmissionDecision
    assert PlanningAdmissionGate is StrategyPricePlanningAdmissionGate
    assert PlanningAdmissionPolicy is PricePlanningAdmissionPolicy
    assert PlanningAdmissionReason is PricePlanningAdmissionReason
    assert PlanningAdmissionStatus is PricePlanningAdmissionStatus
    assert PricePlanningGate is StrategyPricePlanningAdmissionGate
