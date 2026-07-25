from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.timeframes import get_timeframe_spec
from app.strategy.analysis_pipeline import (
    AnalysisPipelinePolicy,
    AnalysisPipelineSnapshot,
    MultiTimeframeAnalysisPipeline,
)
from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
    DirectionalPermissionPolicy,
)
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiTimeframeContextBuilder,
)
from app.strategy.setup_qualification import (
    QualificationBlocker,
    QualificationDecision,
    QualificationGate,
    QualificationPolicy,
    QualificationReason,
    QualificationStatus,
    SetupEligibilityGate,
    SetupEvidence,
    SetupEvidenceCounts,
    SetupQualificationBlocker,
    SetupQualificationDecision,
    SetupQualificationError,
    SetupQualificationErrorReason,
    SetupQualificationPolicy,
    SetupQualificationReason,
    SetupQualificationStatus,
    StrategySetupQualificationGate,
    evaluate_setup_qualification,
)
from app.strategy.strategy_readiness import (
    StrategyReadinessPolicy,
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
    end_at: datetime = OBSERVED_AT,
    broker_symbol: str = "XAUUSDm",
    count: int = 8,
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    first_open = end_at - duration * count
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
                broker_symbol=broker_symbol,
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
        broker_symbol=broker_symbol,
        timeframe=timeframe,
        candles=tuple(candles),
    )


def series_map(
    *,
    h4_end_at: datetime = OBSERVED_AT,
) -> dict[TimeframeName, ClosedCandleSeries]:
    return {
        timeframe: create_series(
            timeframe,
            end_at=(h4_end_at if timeframe == TimeframeName.H4 else OBSERVED_AT),
        )
        for timeframe in GOLD_TIMEFRAME_HIERARCHY
    }


def analysis_policy(
    *,
    directional_policy: (DirectionalPermissionPolicy | None) = None,
) -> AnalysisPipelinePolicy:
    return AnalysisPipelinePolicy(
        readiness_policy=StrategyReadinessPolicy(
            directional_policy=(directional_policy or DirectionalPermissionPolicy())
        )
    )


def build_analysis(
    biases: dict[
        TimeframeName,
        MarketStructureBias,
    ],
    *,
    policy: AnalysisPipelinePolicy | None = None,
    stale_h4: bool = False,
) -> AnalysisPipelineSnapshot:
    selected_policy = policy or analysis_policy()
    context = MultiTimeframeContextBuilder(selected_policy.context_policy).build(
        series_map(h4_end_at=(OBSERVED_AT - timedelta(hours=8) if stale_h4 else OBSERVED_AT))
    )
    context = replace(
        context,
        structure_biases=tuple(
            (
                timeframe,
                biases.get(
                    timeframe,
                    MarketStructureBias.NEUTRAL,
                ),
            )
            for timeframe in GOLD_TIMEFRAME_HIERARCHY
        ),
    )

    return MultiTimeframeAnalysisPipeline(selected_policy).evaluate_context(context)


def bullish_analysis(
    *,
    setup_bias: MarketStructureBias = (MarketStructureBias.BULLISH),
    execution_bias: MarketStructureBias = (MarketStructureBias.NEUTRAL),
    policy: AnalysisPipelinePolicy | None = None,
    stale_h4: bool = False,
) -> AnalysisPipelineSnapshot:
    return build_analysis(
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M15: setup_bias,
            TimeframeName.M5: execution_bias,
        },
        policy=policy,
        stale_h4=stale_h4,
    )


def bearish_analysis() -> AnalysisPipelineSnapshot:
    return build_analysis(
        {
            TimeframeName.H4: (MarketStructureBias.BEARISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
            TimeframeName.M15: (MarketStructureBias.BEARISH),
        }
    )


def test_default_policy_is_conservative() -> None:
    policy = SetupQualificationPolicy()

    assert policy.allow_neutral_setup_timeframe is False
    assert policy.allow_opposing_setup_timeframe is False
    assert policy.allow_neutral_execution_timeframe is True
    assert policy.allow_opposing_execution_timeframe is False
    assert policy.minimum_setup_evidence == 0
    assert policy.minimum_execution_evidence == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"allow_neutral_setup_timeframe": 1},
        {"allow_opposing_setup_timeframe": 1},
        {"allow_neutral_execution_timeframe": 1},
        {"allow_opposing_execution_timeframe": 1},
        {"minimum_setup_evidence": -1},
        {"minimum_setup_evidence": True},
        {"minimum_execution_evidence": -1},
        {"minimum_execution_evidence": True},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        SetupQualificationPolicy(**overrides)


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="SetupQualificationPolicy",
    ):
        StrategySetupQualificationGate(policy="invalid")


def test_invalid_analysis_is_fail_safe() -> None:
    with pytest.raises(
        SetupQualificationError,
        match="INVALID_ANALYSIS",
    ) as captured:
        StrategySetupQualificationGate().evaluate("invalid")

    assert captured.value.reason == (SetupQualificationErrorReason.INVALID_ANALYSIS)


def test_ready_bullish_analysis_is_qualified() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis())

    assert decision.status == (SetupQualificationStatus.QUALIFIED)
    assert decision.reason == (SetupQualificationReason.QUALIFIED)
    assert decision.blockers == ()
    assert decision.is_qualified is True
    assert decision.can_generate_setup_candidate is True
    assert decision.is_bullish is True


def test_ready_bearish_analysis_is_qualified() -> None:
    decision = StrategySetupQualificationGate().evaluate(bearish_analysis())

    assert decision.is_qualified is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.is_bearish is True


def test_unresolved_direction_is_blocked() -> None:
    analysis = build_analysis({})

    decision = StrategySetupQualificationGate().evaluate(analysis)

    assert decision.is_blocked is True
    assert decision.reason == (SetupQualificationReason.DIRECTION_UNRESOLVED)
    assert decision.blockers == (SetupQualificationBlocker.DIRECTION_UNRESOLVED,)


def test_stale_directional_analysis_is_blocked() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis(stale_h4=True))

    assert decision.reason == (SetupQualificationReason.STALE_CONTEXT)
    assert decision.blockers == (SetupQualificationBlocker.STALE_CONTEXT,)


def test_stale_unresolved_analysis_preserves_both() -> None:
    analysis = build_analysis(
        {},
        stale_h4=True,
    )

    decision = StrategySetupQualificationGate().evaluate(analysis)

    assert decision.reason == (SetupQualificationReason.MULTIPLE_BLOCKERS)
    assert decision.blockers == (
        SetupQualificationBlocker.STALE_CONTEXT,
        SetupQualificationBlocker.DIRECTION_UNRESOLVED,
    )


def test_neutral_setup_timeframe_is_blocked() -> None:
    analysis = bullish_analysis(
        setup_bias=MarketStructureBias.NEUTRAL,
        execution_bias=MarketStructureBias.BULLISH,
    )

    decision = StrategySetupQualificationGate().evaluate(analysis)

    assert analysis.is_ready is True
    assert decision.reason == (SetupQualificationReason.SETUP_TIMEFRAME_NEUTRAL)


def test_neutral_setup_can_be_allowed() -> None:
    analysis = bullish_analysis(
        setup_bias=MarketStructureBias.NEUTRAL,
        execution_bias=MarketStructureBias.BULLISH,
    )
    policy = SetupQualificationPolicy(allow_neutral_setup_timeframe=True)

    decision = StrategySetupQualificationGate(policy).evaluate(analysis)

    assert decision.is_qualified is True


def test_opposing_setup_timeframe_is_blocked() -> None:
    relaxed_directional = DirectionalPermissionPolicy(allow_opposing_setup_timeframe=True)
    selected_policy = analysis_policy(directional_policy=relaxed_directional)
    analysis = bullish_analysis(
        setup_bias=MarketStructureBias.BEARISH,
        execution_bias=MarketStructureBias.BULLISH,
        policy=selected_policy,
    )

    decision = StrategySetupQualificationGate().evaluate(analysis)

    assert analysis.is_ready is True
    assert decision.reason == (SetupQualificationReason.SETUP_TIMEFRAME_CONFLICT)


def test_opposing_setup_can_be_allowed() -> None:
    relaxed_directional = DirectionalPermissionPolicy(allow_opposing_setup_timeframe=True)
    selected_policy = analysis_policy(directional_policy=relaxed_directional)
    analysis = bullish_analysis(
        setup_bias=MarketStructureBias.BEARISH,
        execution_bias=MarketStructureBias.BULLISH,
        policy=selected_policy,
    )
    policy = SetupQualificationPolicy(allow_opposing_setup_timeframe=True)

    decision = StrategySetupQualificationGate(policy).evaluate(analysis)

    assert decision.is_qualified is True


def test_neutral_execution_is_allowed_by_default() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis())

    assert decision.execution_bias == (MarketStructureBias.NEUTRAL)
    assert decision.is_qualified is True


def test_neutral_execution_can_be_blocked() -> None:
    policy = SetupQualificationPolicy(allow_neutral_execution_timeframe=False)

    decision = StrategySetupQualificationGate(policy).evaluate(bullish_analysis())

    assert decision.reason == (SetupQualificationReason.EXECUTION_TIMEFRAME_NEUTRAL)


def test_opposing_execution_is_blocked() -> None:
    relaxed_directional = DirectionalPermissionPolicy(allow_opposing_execution_timeframe=True)
    selected_policy = analysis_policy(directional_policy=relaxed_directional)
    analysis = bullish_analysis(
        execution_bias=MarketStructureBias.BEARISH,
        policy=selected_policy,
    )

    decision = StrategySetupQualificationGate().evaluate(analysis)

    assert analysis.is_ready is True
    assert decision.reason == (SetupQualificationReason.EXECUTION_TIMEFRAME_CONFLICT)


def test_opposing_execution_can_be_allowed() -> None:
    relaxed_directional = DirectionalPermissionPolicy(allow_opposing_execution_timeframe=True)
    selected_policy = analysis_policy(directional_policy=relaxed_directional)
    analysis = bullish_analysis(
        execution_bias=MarketStructureBias.BEARISH,
        policy=selected_policy,
    )
    policy = SetupQualificationPolicy(allow_opposing_execution_timeframe=True)

    decision = StrategySetupQualificationGate(policy).evaluate(analysis)

    assert decision.is_qualified is True


def test_setup_evidence_matches_m15_context() -> None:
    analysis = bullish_analysis()
    decision = StrategySetupQualificationGate().evaluate(analysis)
    counts = analysis.context.m15.counts

    assert decision.setup_evidence == (
        SetupEvidenceCounts(
            liquidity_sweeps=counts.liquidity_sweeps,
            fair_value_gaps=counts.fair_value_gaps,
            displacement_impulses=(counts.displacement_impulses),
            order_blocks=counts.order_blocks,
            dealing_ranges=counts.dealing_ranges,
            optimal_trade_entry_zones=(counts.optimal_trade_entry_zones),
        )
    )


def test_execution_evidence_matches_m5_context() -> None:
    analysis = bullish_analysis()
    decision = StrategySetupQualificationGate().evaluate(analysis)
    counts = analysis.context.m5.counts

    assert decision.execution_evidence.total == (
        counts.liquidity_sweeps
        + counts.fair_value_gaps
        + counts.displacement_impulses
        + counts.order_blocks
        + counts.dealing_ranges
        + counts.optimal_trade_entry_zones
    )


def test_custom_setup_evidence_minimum_blocks() -> None:
    analysis = bullish_analysis()
    baseline = StrategySetupQualificationGate().evaluate(analysis)
    policy = SetupQualificationPolicy(minimum_setup_evidence=(baseline.setup_evidence.total + 1))

    decision = StrategySetupQualificationGate(policy).evaluate(analysis)

    assert decision.reason == (SetupQualificationReason.INSUFFICIENT_SETUP_EVIDENCE)


def test_custom_execution_evidence_minimum_blocks() -> None:
    analysis = bullish_analysis()
    baseline = StrategySetupQualificationGate().evaluate(analysis)
    policy = SetupQualificationPolicy(
        minimum_execution_evidence=(baseline.execution_evidence.total + 1)
    )

    decision = StrategySetupQualificationGate(policy).evaluate(analysis)

    assert decision.reason == (SetupQualificationReason.INSUFFICIENT_EXECUTION_EVIDENCE)


def test_multiple_evidence_blockers_preserve_order() -> None:
    analysis = bullish_analysis()
    baseline = StrategySetupQualificationGate().evaluate(analysis)
    policy = SetupQualificationPolicy(
        minimum_setup_evidence=(baseline.setup_evidence.total + 1),
        minimum_execution_evidence=(baseline.execution_evidence.total + 1),
    )

    decision = StrategySetupQualificationGate(policy).evaluate(analysis)

    assert decision.reason == (SetupQualificationReason.MULTIPLE_BLOCKERS)
    assert decision.blockers == (
        SetupQualificationBlocker.INSUFFICIENT_SETUP_EVIDENCE,
        SetupQualificationBlocker.INSUFFICIENT_EXECUTION_EVIDENCE,
    )


def test_timeframe_roles_are_explicit() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis())

    assert decision.setup_timeframe == TimeframeName.M15
    assert decision.execution_timeframe == TimeframeName.M5
    assert decision.setup_bias == (MarketStructureBias.BULLISH)


def test_decision_preserves_metadata() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis())

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.blocker_count == 0
    assert decision.total_evidence == (
        decision.setup_evidence.total + decision.execution_evidence.total
    )


def test_qualified_stable_id_is_deterministic() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis())

    assert decision.stable_id == (
        f"{decision.analysis.stable_id}:SETUP_QUALIFICATION:QUALIFIED:BULLISH:QUALIFIED:NONE"
    )


def test_blocked_stable_id_lists_blockers() -> None:
    decision = StrategySetupQualificationGate().evaluate(build_analysis({}))

    assert decision.stable_id.endswith(
        "SETUP_QUALIFICATION:BLOCKED:NONE:DIRECTION_UNRESOLVED:DIRECTION_UNRESOLVED"
    )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            status=SetupQualificationStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis())

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            reason=(SetupQualificationReason.ANALYSIS_NOT_READY),
        )


def test_manual_decision_rejects_wrong_evidence() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis())
    modified = replace(
        decision.setup_evidence,
        fair_value_gaps=(decision.setup_evidence.fair_value_gaps + 1),
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        replace(
            decision,
            setup_evidence=modified,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategySetupQualificationGate().evaluate(build_analysis({}))

    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        replace(
            decision,
            blockers=(
                SetupQualificationBlocker.DIRECTION_UNRESOLVED,
                SetupQualificationBlocker.DIRECTION_UNRESOLVED,
            ),
        )


def test_evidence_is_immutable() -> None:
    evidence = StrategySetupQualificationGate().evaluate(bullish_analysis()).setup_evidence

    with pytest.raises(FrozenInstanceError):
        evidence.order_blocks = 10


def test_decision_is_immutable() -> None:
    decision = StrategySetupQualificationGate().evaluate(bullish_analysis())

    with pytest.raises(FrozenInstanceError):
        decision.status = SetupQualificationStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = SetupQualificationPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.minimum_setup_evidence = 1


def test_evaluation_is_deterministic() -> None:
    gate = StrategySetupQualificationGate()
    analysis = bullish_analysis()

    assert gate.evaluate(analysis) == gate.evaluate(analysis)


def test_function_api_delegates() -> None:
    decision = evaluate_setup_qualification(bullish_analysis())

    assert decision.is_qualified is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategySetupQualificationGate()
    analysis = bullish_analysis()

    assert gate.check(analysis) == gate.evaluate(analysis)
    assert gate.qualify(analysis) == gate.evaluate(analysis)


def test_public_aliases_are_preserved() -> None:
    assert QualificationBlocker is SetupQualificationBlocker
    assert QualificationDecision is SetupQualificationDecision
    assert QualificationPolicy is SetupQualificationPolicy
    assert QualificationReason is SetupQualificationReason
    assert QualificationStatus is SetupQualificationStatus
    assert QualificationGate is StrategySetupQualificationGate
    assert SetupEligibilityGate is StrategySetupQualificationGate
    assert SetupEvidence is SetupEvidenceCounts
