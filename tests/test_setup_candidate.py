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
    CandidateDecision,
    CandidateFactory,
    CandidateGenerationBlocker,
    CandidateGenerationReason,
    CandidateGenerationStatus,
    CandidatePolicy,
    SetupCandidate,
    SetupCandidateError,
    SetupCandidateErrorReason,
    SetupCandidateFactory,
    SetupCandidateGenerationBlocker,
    SetupCandidateGenerationDecision,
    SetupCandidateGenerationReason,
    SetupCandidateGenerationStatus,
    SetupCandidatePolicy,
    StrategySetupCandidate,
    StrategySetupCandidateFactory,
    generate_setup_candidate,
)
from app.strategy.setup_qualification import (
    SetupQualificationStatus,
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
def neutral_analysis():
    mapping = {timeframe: create_series(timeframe) for timeframe in GOLD_TIMEFRAME_HIERARCHY}
    context = MultiTimeframeContextBuilder().build(mapping)

    return MultiTimeframeAnalysisPipeline().evaluate_context(context)


def analysis_with_direction(
    direction: DirectionalPermissionDirection,
):
    if direction == DirectionalPermissionDirection.BULLISH:
        bias = MarketStructureBias.BULLISH
    elif direction == DirectionalPermissionDirection.BEARISH:
        bias = MarketStructureBias.BEARISH
    else:
        bias = MarketStructureBias.NEUTRAL

    context = replace(
        neutral_analysis().context,
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
                    else MarketStructureBias.NEUTRAL
                ),
            )
            for timeframe in GOLD_TIMEFRAME_HIERARCHY
        ),
    )

    return MultiTimeframeAnalysisPipeline().evaluate_context(context)


@lru_cache(maxsize=1)
def bullish_qualification():
    return StrategySetupQualificationGate().evaluate(
        analysis_with_direction(DirectionalPermissionDirection.BULLISH)
    )


@lru_cache(maxsize=1)
def bearish_qualification():
    return StrategySetupQualificationGate().evaluate(
        analysis_with_direction(DirectionalPermissionDirection.BEARISH)
    )


@lru_cache(maxsize=1)
def blocked_qualification():
    return StrategySetupQualificationGate().evaluate(neutral_analysis())


def test_default_policy_has_zero_evidence_minimum() -> None:
    policy = SetupCandidatePolicy()

    assert policy.minimum_total_evidence == 0


@pytest.mark.parametrize(
    "minimum",
    [-1, True, "1", Decimal("1")],
)
def test_invalid_policy_is_rejected(
    minimum: object,
) -> None:
    with pytest.raises(ValueError):
        SetupCandidatePolicy(minimum_total_evidence=minimum)


def test_factory_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="SetupCandidatePolicy",
    ):
        StrategySetupCandidateFactory(policy="invalid")


def test_invalid_qualification_is_fail_safe() -> None:
    with pytest.raises(
        SetupCandidateError,
        match="INVALID_QUALIFICATION",
    ) as captured:
        StrategySetupCandidateFactory().generate("invalid")

    assert captured.value.reason == (SetupCandidateErrorReason.INVALID_QUALIFICATION)


def test_bullish_candidate_is_generated() -> None:
    decision = StrategySetupCandidateFactory().generate(bullish_qualification())

    assert decision.status == (SetupCandidateGenerationStatus.GENERATED)
    assert decision.reason == (SetupCandidateGenerationReason.GENERATED)
    assert decision.blockers == ()
    assert decision.is_generated is True
    assert decision.has_candidate is True


def test_bearish_candidate_is_generated() -> None:
    decision = StrategySetupCandidateFactory().generate(bearish_qualification())

    assert decision.is_generated is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.candidate_required.is_bearish is True


def test_blocked_qualification_produces_no_candidate() -> None:
    qualification = blocked_qualification()
    decision = StrategySetupCandidateFactory().generate(qualification)

    assert qualification.status == (SetupQualificationStatus.BLOCKED)
    assert decision.is_blocked is True
    assert decision.has_candidate is False
    assert decision.candidate is None
    assert decision.reason == (SetupCandidateGenerationReason.QUALIFICATION_BLOCKED)
    assert decision.blockers == (SetupCandidateGenerationBlocker.QUALIFICATION_BLOCKED,)


def test_candidate_required_rejects_blocked_result() -> None:
    decision = StrategySetupCandidateFactory().generate(blocked_qualification())

    with pytest.raises(
        ValueError,
        match="No setup candidate",
    ):
        _ = decision.candidate_required


def test_total_evidence_threshold_can_block() -> None:
    qualification = bullish_qualification()
    baseline = StrategySetupCandidate(qualification)
    policy = SetupCandidatePolicy(minimum_total_evidence=(baseline.total_evidence + 1))

    decision = StrategySetupCandidateFactory(policy).generate(qualification)

    assert decision.is_blocked is True
    assert decision.reason == (SetupCandidateGenerationReason.INSUFFICIENT_TOTAL_EVIDENCE)
    assert decision.blockers == (SetupCandidateGenerationBlocker.INSUFFICIENT_TOTAL_EVIDENCE,)


def test_exact_total_evidence_threshold_is_allowed() -> None:
    qualification = bullish_qualification()
    baseline = StrategySetupCandidate(qualification)
    policy = SetupCandidatePolicy(minimum_total_evidence=(baseline.total_evidence))

    decision = StrategySetupCandidateFactory(policy).generate(qualification)

    assert decision.is_generated is True


def test_candidate_preserves_symbol_and_time() -> None:
    candidate = StrategySetupCandidateFactory().generate(bullish_qualification()).candidate_required

    assert candidate.broker_symbol == "XAUUSDm"
    assert candidate.observed_at == OBSERVED_AT


def test_candidate_preserves_direction() -> None:
    candidate = StrategySetupCandidateFactory().generate(bullish_qualification()).candidate_required

    assert candidate.direction == (DirectionalPermissionDirection.BULLISH)
    assert candidate.is_bullish is True
    assert candidate.is_bearish is False


def test_candidate_uses_m15_and_m5_roles() -> None:
    candidate = StrategySetupCandidateFactory().generate(bullish_qualification()).candidate_required

    assert candidate.setup_timeframe == TimeframeName.M15
    assert candidate.execution_timeframe == TimeframeName.M5


def test_candidate_preserves_evidence_objects() -> None:
    qualification = bullish_qualification()
    candidate = StrategySetupCandidateFactory().generate(qualification).candidate_required

    assert candidate.setup_evidence is qualification.setup_evidence
    assert candidate.execution_evidence is qualification.execution_evidence
    assert candidate.total_evidence == (qualification.total_evidence)


def test_candidate_is_explicitly_non_executable() -> None:
    candidate = StrategySetupCandidateFactory().generate(bullish_qualification()).candidate_required

    assert candidate.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "entry_price",
        "stop_loss",
        "take_profit",
        "volume",
        "lot_size",
        "order_type",
        "broker_ticket",
    ],
)
def test_candidate_contains_no_execution_fields(
    attribute_name: str,
) -> None:
    candidate = StrategySetupCandidateFactory().generate(bullish_qualification()).candidate_required

    assert not hasattr(candidate, attribute_name)


def test_candidate_id_is_deterministic() -> None:
    candidate = StrategySetupCandidateFactory().generate(bullish_qualification()).candidate_required

    assert candidate.candidate_id == (f"XAUUSDm:{OBSERVED_AT.isoformat()}:BULLISH:M15:M5")


def test_candidate_stable_id_is_deterministic() -> None:
    qualification = bullish_qualification()
    candidate = StrategySetupCandidateFactory().generate(qualification).candidate_required

    assert candidate.stable_id == (
        f"{qualification.stable_id}:SETUP_CANDIDATE:{candidate.candidate_id}"
    )


def test_generated_decision_stable_id_is_deterministic() -> None:
    qualification = bullish_qualification()
    decision = StrategySetupCandidateFactory().generate(qualification)

    assert decision.stable_id == (
        f"{qualification.stable_id}:CANDIDATE_GENERATION:GENERATED:GENERATED:NONE"
    )


def test_blocked_decision_stable_id_lists_blocker() -> None:
    decision = StrategySetupCandidateFactory().generate(blocked_qualification())

    assert decision.stable_id.endswith(
        "CANDIDATE_GENERATION:BLOCKED:QUALIFICATION_BLOCKED:QUALIFICATION_BLOCKED"
    )


def test_direct_candidate_rejects_blocked_qualification() -> None:
    with pytest.raises(
        ValueError,
        match="qualified",
    ):
        StrategySetupCandidate(blocked_qualification())


def test_direct_candidate_requires_qualification_type() -> None:
    with pytest.raises(
        ValueError,
        match="SetupQualificationDecision",
    ):
        StrategySetupCandidate("invalid")


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategySetupCandidateFactory().generate(bullish_qualification())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=SetupCandidateGenerationStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategySetupCandidateFactory().generate(bullish_qualification())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(SetupCandidateGenerationReason.QUALIFICATION_BLOCKED),
        )


def test_manual_decision_rejects_missing_candidate() -> None:
    decision = StrategySetupCandidateFactory().generate(bullish_qualification())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            candidate=None,
        )


def test_manual_decision_rejects_unexpected_candidate() -> None:
    blocked = StrategySetupCandidateFactory().generate(blocked_qualification())
    valid_candidate = StrategySetupCandidate(bullish_qualification())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            blocked,
            candidate=valid_candidate,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategySetupCandidateFactory().generate(blocked_qualification())

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                SetupCandidateGenerationBlocker.QUALIFICATION_BLOCKED,
                SetupCandidateGenerationBlocker.QUALIFICATION_BLOCKED,
            ),
        )


def test_candidate_is_immutable() -> None:
    candidate = StrategySetupCandidateFactory().generate(bullish_qualification()).candidate_required

    with pytest.raises(FrozenInstanceError):
        candidate.qualification = blocked_qualification()


def test_decision_is_immutable() -> None:
    decision = StrategySetupCandidateFactory().generate(bullish_qualification())

    with pytest.raises(FrozenInstanceError):
        decision.status = SetupCandidateGenerationStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = SetupCandidatePolicy()

    with pytest.raises(FrozenInstanceError):
        policy.minimum_total_evidence = 1


def test_generation_is_deterministic() -> None:
    factory = StrategySetupCandidateFactory()
    qualification = bullish_qualification()

    assert factory.generate(qualification) == factory.generate(qualification)


def test_function_api_delegates() -> None:
    decision = generate_setup_candidate(bullish_qualification())

    assert decision.is_generated is True


def test_factory_alias_methods_delegate() -> None:
    factory = StrategySetupCandidateFactory()
    qualification = bullish_qualification()

    assert factory.build(qualification) == factory.generate(qualification)
    assert factory.evaluate(qualification) == factory.generate(qualification)


def test_public_aliases_are_preserved() -> None:
    assert CandidateDecision is SetupCandidateGenerationDecision
    assert CandidateFactory is StrategySetupCandidateFactory
    assert CandidateGenerationBlocker is SetupCandidateGenerationBlocker
    assert CandidateGenerationReason is SetupCandidateGenerationReason
    assert CandidateGenerationStatus is SetupCandidateGenerationStatus
    assert CandidatePolicy is SetupCandidatePolicy
    assert SetupCandidate is StrategySetupCandidate
    assert SetupCandidateFactory is StrategySetupCandidateFactory
