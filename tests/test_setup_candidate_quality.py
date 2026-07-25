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
from app.strategy.setup_candidate import (
    StrategySetupCandidate,
    StrategySetupCandidateFactory,
)
from app.strategy.setup_candidate_quality import (
    CandidateQualityBlocker,
    CandidateQualityComponents,
    CandidateQualityDecision,
    CandidateQualityGate,
    CandidateQualityPolicy,
    CandidateQualityReason,
    CandidateQualityStatus,
    CandidateQualityTier,
    SetupCandidateQualityBlocker,
    SetupCandidateQualityComponents,
    SetupCandidateQualityDecision,
    SetupCandidateQualityError,
    SetupCandidateQualityErrorReason,
    SetupCandidateQualityPolicy,
    SetupCandidateQualityReason,
    SetupCandidateQualityStatus,
    SetupCandidateQualityTier,
    SetupQualityGate,
    StrategySetupCandidateQualityGate,
    evaluate_setup_candidate_quality,
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
        bias = MarketStructureBias.BULLISH
    elif direction == DirectionalPermissionDirection.BEARISH:
        bias = MarketStructureBias.BEARISH
    else:
        raise ValueError("Direction must be resolved.")

    context = replace(
        neutral_context(),
        structure_biases=tuple(
            (
                timeframe,
                (
                    bias
                    if timeframe
                    in {
                        TimeframeName.H4,
                        TimeframeName.H1,
                        TimeframeName.M15,
                    }
                    or (execution_aligned and timeframe == TimeframeName.M5)
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
def bullish_candidate() -> StrategySetupCandidate:
    return candidate_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def aligned_bullish_candidate() -> StrategySetupCandidate:
    return candidate_for(
        DirectionalPermissionDirection.BULLISH,
        execution_aligned=True,
    )


@lru_cache(maxsize=1)
def bearish_candidate() -> StrategySetupCandidate:
    return candidate_for(DirectionalPermissionDirection.BEARISH)


def test_default_policy_weights_total_one_hundred() -> None:
    policy = SetupCandidateQualityPolicy()

    assert policy.alignment_weight == Decimal("50")
    assert policy.setup_evidence_weight == Decimal("25")
    assert policy.execution_evidence_weight == Decimal("15")
    assert policy.execution_bias_weight == Decimal("10")
    assert (
        policy.alignment_weight
        + policy.setup_evidence_weight
        + policy.execution_evidence_weight
        + policy.execution_bias_weight
        == Decimal("100")
    )


def test_default_policy_thresholds() -> None:
    policy = SetupCandidateQualityPolicy()

    assert policy.setup_evidence_target == 1
    assert policy.execution_evidence_target == 1
    assert policy.minimum_score == Decimal("40")


@pytest.mark.parametrize(
    "overrides",
    [
        {"alignment_weight": 50},
        {"alignment_weight": "50"},
        {"alignment_weight": Decimal("-1")},
        {"alignment_weight": Decimal("101")},
        {"minimum_score": 40},
        {"minimum_score": Decimal("-1")},
        {"minimum_score": Decimal("101")},
        {"setup_evidence_target": 0},
        {"setup_evidence_target": True},
        {"execution_evidence_target": 0},
        {"execution_evidence_target": True},
    ],
)
def test_invalid_policy_values_are_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        SetupCandidateQualityPolicy(**overrides)


def test_weights_must_total_exactly_one_hundred() -> None:
    with pytest.raises(
        ValueError,
        match="exactly 100",
    ):
        SetupCandidateQualityPolicy(alignment_weight=Decimal("49"))


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="SetupCandidateQualityPolicy",
    ):
        StrategySetupCandidateQualityGate(policy="invalid")


def test_invalid_candidate_is_fail_safe() -> None:
    with pytest.raises(
        SetupCandidateQualityError,
        match="INVALID_CANDIDATE",
    ) as captured:
        StrategySetupCandidateQualityGate().evaluate("invalid")

    assert captured.value.reason == (SetupCandidateQualityErrorReason.INVALID_CANDIDATE)


def test_neutral_execution_candidate_is_accepted() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())

    assert decision.status == (SetupCandidateQualityStatus.ACCEPTED)
    assert decision.reason == (SetupCandidateQualityReason.ACCEPTED)
    assert decision.blockers == ()
    assert decision.is_accepted is True
    assert decision.can_continue_to_price_planning is True


def test_default_neutral_execution_score_is_exact() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())

    assert decision.components.alignment == (Decimal("37.50"))
    assert decision.components.setup_evidence == (Decimal("0"))
    assert decision.components.execution_evidence == Decimal("0")
    assert decision.components.execution_bias == (Decimal("5.0"))
    assert decision.score == Decimal("42.50")


def test_default_neutral_candidate_is_acceptable() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())

    assert decision.tier == (SetupCandidateQualityTier.ACCEPTABLE)


def test_aligned_execution_candidate_is_strong() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(aligned_bullish_candidate())

    assert decision.score == Decimal("60")
    assert decision.tier == (SetupCandidateQualityTier.STRONG)
    assert decision.is_accepted is True


def test_bearish_candidate_is_scored() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bearish_candidate())

    assert decision.is_accepted is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.score == Decimal("42.50")


def test_score_below_custom_minimum_is_blocked() -> None:
    policy = SetupCandidateQualityPolicy(minimum_score=Decimal("43"))

    decision = StrategySetupCandidateQualityGate(policy).evaluate(bullish_candidate())

    assert decision.status == (SetupCandidateQualityStatus.BLOCKED)
    assert decision.reason == (SetupCandidateQualityReason.BELOW_MINIMUM_SCORE)
    assert decision.blockers == (SetupCandidateQualityBlocker.BELOW_MINIMUM_SCORE,)


def test_exact_custom_minimum_is_accepted() -> None:
    policy = SetupCandidateQualityPolicy(minimum_score=Decimal("42.50"))

    decision = StrategySetupCandidateQualityGate(policy).evaluate(bullish_candidate())

    assert decision.is_accepted is True


def test_custom_alignment_only_scoring_is_exact() -> None:
    policy = SetupCandidateQualityPolicy(
        alignment_weight=Decimal("100"),
        setup_evidence_weight=Decimal("0"),
        execution_evidence_weight=Decimal("0"),
        execution_bias_weight=Decimal("0"),
        minimum_score=Decimal("0"),
    )

    decision = StrategySetupCandidateQualityGate(policy).evaluate(bullish_candidate())

    assert decision.score == Decimal("75.00")
    assert decision.tier == (SetupCandidateQualityTier.STRONG)


def test_premium_tier_is_available() -> None:
    policy = SetupCandidateQualityPolicy(
        alignment_weight=Decimal("90"),
        setup_evidence_weight=Decimal("0"),
        execution_evidence_weight=Decimal("0"),
        execution_bias_weight=Decimal("10"),
        minimum_score=Decimal("0"),
    )

    decision = StrategySetupCandidateQualityGate(policy).evaluate(aligned_bullish_candidate())

    assert decision.score == Decimal("100")
    assert decision.tier == (SetupCandidateQualityTier.PREMIUM)


def test_weak_tier_is_available() -> None:
    policy = SetupCandidateQualityPolicy(
        alignment_weight=Decimal("20"),
        setup_evidence_weight=Decimal("40"),
        execution_evidence_weight=Decimal("30"),
        execution_bias_weight=Decimal("10"),
        minimum_score=Decimal("0"),
    )

    decision = StrategySetupCandidateQualityGate(policy).evaluate(bullish_candidate())

    assert decision.score == Decimal("20.00")
    assert decision.tier == (SetupCandidateQualityTier.WEAK)
    assert decision.is_accepted is True


def test_components_sum_to_score() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())

    assert decision.components.total == decision.score


def test_components_reject_negative_values() -> None:
    with pytest.raises(ValueError):
        SetupCandidateQualityComponents(
            alignment=Decimal("-1"),
            setup_evidence=Decimal("0"),
            execution_evidence=Decimal("0"),
            execution_bias=Decimal("0"),
        )


def test_components_reject_total_above_one_hundred() -> None:
    with pytest.raises(
        ValueError,
        match="cannot exceed 100",
    ):
        SetupCandidateQualityComponents(
            alignment=Decimal("50"),
            setup_evidence=Decimal("30"),
            execution_evidence=Decimal("20"),
            execution_bias=Decimal("10"),
        )


def test_decision_preserves_candidate() -> None:
    candidate = bullish_candidate()
    decision = StrategySetupCandidateQualityGate().evaluate(candidate)

    assert decision.candidate is candidate


def test_decision_preserves_metadata() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.blocker_count == 0


def test_accepted_stable_id_is_deterministic() -> None:
    candidate = bullish_candidate()
    decision = StrategySetupCandidateQualityGate().evaluate(candidate)

    assert decision.stable_id == (
        f"{candidate.stable_id}:CANDIDATE_QUALITY:ACCEPTED:ACCEPTABLE:42.50:NONE"
    )


def test_blocked_stable_id_lists_blocker() -> None:
    policy = SetupCandidateQualityPolicy(minimum_score=Decimal("43"))
    decision = StrategySetupCandidateQualityGate(policy).evaluate(bullish_candidate())

    assert decision.stable_id.endswith(
        "CANDIDATE_QUALITY:BLOCKED:ACCEPTABLE:42.50:BELOW_MINIMUM_SCORE"
    )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=SetupCandidateQualityStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(SetupCandidateQualityReason.BELOW_MINIMUM_SCORE),
        )


def test_manual_decision_rejects_wrong_tier() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            tier=SetupCandidateQualityTier.PREMIUM,
        )


def test_manual_decision_rejects_wrong_components() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())
    modified = replace(
        decision.components,
        execution_bias=Decimal("6"),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            components=modified,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    policy = SetupCandidateQualityPolicy(minimum_score=Decimal("43"))
    decision = StrategySetupCandidateQualityGate(policy).evaluate(bullish_candidate())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                SetupCandidateQualityBlocker.BELOW_MINIMUM_SCORE,
                SetupCandidateQualityBlocker.BELOW_MINIMUM_SCORE,
            ),
        )


def test_components_are_immutable() -> None:
    components = StrategySetupCandidateQualityGate().evaluate(bullish_candidate()).components

    with pytest.raises(FrozenInstanceError):
        components.alignment = Decimal("0")


def test_decision_is_immutable() -> None:
    decision = StrategySetupCandidateQualityGate().evaluate(bullish_candidate())

    with pytest.raises(FrozenInstanceError):
        decision.status = SetupCandidateQualityStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = SetupCandidateQualityPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.minimum_score = Decimal("50")


def test_evaluation_is_deterministic() -> None:
    gate = StrategySetupCandidateQualityGate()
    candidate = bullish_candidate()

    assert gate.evaluate(candidate) == gate.evaluate(candidate)


def test_function_api_delegates() -> None:
    decision = evaluate_setup_candidate_quality(bullish_candidate())

    assert decision.is_accepted is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategySetupCandidateQualityGate()
    candidate = bullish_candidate()

    assert gate.score(candidate) == gate.evaluate(candidate)
    assert gate.assess(candidate) == gate.evaluate(candidate)


def test_public_aliases_are_preserved() -> None:
    assert CandidateQualityBlocker is SetupCandidateQualityBlocker
    assert CandidateQualityComponents is SetupCandidateQualityComponents
    assert CandidateQualityDecision is SetupCandidateQualityDecision
    assert CandidateQualityGate is StrategySetupCandidateQualityGate
    assert CandidateQualityPolicy is SetupCandidateQualityPolicy
    assert CandidateQualityReason is SetupCandidateQualityReason
    assert CandidateQualityStatus is SetupCandidateQualityStatus
    assert CandidateQualityTier is SetupCandidateQualityTier
    assert SetupQualityGate is StrategySetupCandidateQualityGate
