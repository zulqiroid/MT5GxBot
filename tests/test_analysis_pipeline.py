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
    AnalysisPipeline,
    AnalysisPipelineBuildError,
    AnalysisPipelineErrorReason,
    AnalysisPipelinePolicy,
    AnalysisPipelineSnapshot,
    AnalysisPipelineStage,
    AnalysisPolicy,
    AnalysisSnapshot,
    GoldAnalysisPipeline,
    MultiTimeframeAnalysisPipeline,
    MultiTimeframeAnalysisSnapshot,
    StrategyAnalysisPipeline,
    build_analysis_pipeline,
)
from app.strategy.context_freshness import (
    ContextFreshnessPolicy,
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
    MultiTimeframeContextBuildError,
    MultiTimeframeContextCounts,
    MultiTimeframeContextErrorReason,
    MultiTimeframeContextPolicy,
    MultiTimeframeContextSnapshot,
)
from app.strategy.strategy_readiness import (
    CompositeStrategyReadinessGate,
    StrategyReadinessBlocker,
    StrategyReadinessPolicy,
    StrategyReadinessReason,
    StrategyReadinessStatus,
)

OBSERVED_AT = datetime(
    2026,
    7,
    25,
    20,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    timeframe: TimeframeName,
    *,
    end_at: datetime = OBSERVED_AT,
    broker_symbol: str = "XAUUSDm",
    count: int = 24,
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
    broker_symbol: str = "XAUUSDm",
) -> dict[TimeframeName, ClosedCandleSeries]:
    return {
        timeframe: create_series(
            timeframe,
            end_at=(h4_end_at if timeframe == TimeframeName.H4 else OBSERVED_AT),
            broker_symbol=broker_symbol,
        )
        for timeframe in GOLD_TIMEFRAME_HIERARCHY
    }


def pipeline_policy() -> AnalysisPipelinePolicy:
    context_policy = MultiTimeframeContextPolicy()
    readiness_policy = StrategyReadinessPolicy()

    return AnalysisPipelinePolicy(
        context_policy=context_policy,
        readiness_policy=readiness_policy,
    )


def neutral_context(
    *,
    h4_end_at: datetime = OBSERVED_AT,
) -> MultiTimeframeContextSnapshot:
    policy = pipeline_policy()

    return MultiTimeframeContextBuilder(policy.context_policy).build(
        series_map(h4_end_at=h4_end_at)
    )


def with_biases(
    context: MultiTimeframeContextSnapshot,
    biases: dict[
        TimeframeName,
        MarketStructureBias,
    ],
) -> MultiTimeframeContextSnapshot:
    return replace(
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


def bullish_context(
    *,
    stale_h4: bool = False,
) -> MultiTimeframeContextSnapshot:
    context = neutral_context(
        h4_end_at=(OBSERVED_AT - timedelta(hours=8) if stale_h4 else OBSERVED_AT)
    )

    return with_biases(
        context,
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
        },
    )


def bearish_context() -> MultiTimeframeContextSnapshot:
    return with_biases(
        neutral_context(),
        {
            TimeframeName.H4: (MarketStructureBias.BEARISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
            TimeframeName.M15: (MarketStructureBias.BEARISH),
        },
    )


def test_default_policy_contains_nested_policies() -> None:
    policy = AnalysisPipelinePolicy()

    assert isinstance(
        policy.context_policy,
        MultiTimeframeContextPolicy,
    )
    assert isinstance(
        policy.readiness_policy,
        StrategyReadinessPolicy,
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("context_policy", "invalid"),
        ("readiness_policy", "invalid"),
    ],
)
def test_invalid_nested_policy_is_rejected(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        AnalysisPipelinePolicy(**{field_name: value})


def test_pipeline_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="AnalysisPipelinePolicy",
    ):
        MultiTimeframeAnalysisPipeline(policy="invalid")


def test_neutral_series_builds_blocked_snapshot() -> None:
    snapshot = MultiTimeframeAnalysisPipeline(pipeline_policy()).build(series_map())

    assert isinstance(
        snapshot,
        AnalysisPipelineSnapshot,
    )
    assert snapshot.is_blocked is True
    assert snapshot.status == (StrategyReadinessStatus.BLOCKED)
    assert snapshot.reason == (StrategyReadinessReason.DIRECTION_BLOCKED)
    assert snapshot.blockers == (StrategyReadinessBlocker.DIRECTION_BLOCKED,)


def test_ready_bullish_context_can_be_evaluated() -> None:
    snapshot = MultiTimeframeAnalysisPipeline(pipeline_policy()).evaluate_context(bullish_context())

    assert snapshot.is_ready is True
    assert snapshot.can_analyze_setup is True
    assert snapshot.direction == (DirectionalPermissionDirection.BULLISH)
    assert snapshot.is_bullish is True
    assert snapshot.is_bearish is False


def test_ready_bearish_context_can_be_evaluated() -> None:
    snapshot = MultiTimeframeAnalysisPipeline(pipeline_policy()).evaluate_context(bearish_context())

    assert snapshot.is_ready is True
    assert snapshot.direction == (DirectionalPermissionDirection.BEARISH)
    assert snapshot.is_bearish is True


def test_stale_bullish_context_is_blocked() -> None:
    snapshot = MultiTimeframeAnalysisPipeline(pipeline_policy()).evaluate_context(
        bullish_context(stale_h4=True)
    )

    assert snapshot.is_blocked is True
    assert snapshot.reason == (StrategyReadinessReason.STALE_CONTEXT)
    assert snapshot.blockers == (StrategyReadinessBlocker.STALE_CONTEXT,)
    assert snapshot.stale_timeframes == (TimeframeName.H4,)


def test_snapshot_exposes_component_decisions() -> None:
    snapshot = MultiTimeframeAnalysisPipeline(pipeline_policy()).evaluate_context(bullish_context())

    assert snapshot.freshness is (snapshot.readiness.freshness)
    assert snapshot.directional is (snapshot.readiness.directional)
    assert snapshot.is_fresh is True
    assert snapshot.alignment_score == Decimal("0.75")


def test_snapshot_preserves_market_metadata() -> None:
    snapshot = MultiTimeframeAnalysisPipeline(pipeline_policy()).evaluate_context(bullish_context())

    assert snapshot.broker_symbol == "XAUUSDm"
    assert snapshot.observed_at == OBSERVED_AT
    assert snapshot.timeframes == (GOLD_TIMEFRAME_HIERARCHY)
    assert isinstance(
        snapshot.counts,
        MultiTimeframeContextCounts,
    )


def test_snapshot_stable_id_is_deterministic() -> None:
    snapshot = MultiTimeframeAnalysisPipeline(pipeline_policy()).evaluate_context(bullish_context())

    assert snapshot.stable_id == (f"{snapshot.context.stable_id}:ANALYSIS_PIPELINE:READY:READY")


def test_invalid_context_is_fail_safe() -> None:
    with pytest.raises(
        AnalysisPipelineBuildError,
        match="INVALID_CONTEXT",
    ) as captured:
        MultiTimeframeAnalysisPipeline(pipeline_policy()).evaluate_context("invalid")

    assert captured.value.reason == (AnalysisPipelineErrorReason.INVALID_CONTEXT)
    assert captured.value.stage == (AnalysisPipelineStage.READINESS)


def test_context_policy_mismatch_is_fail_safe() -> None:
    foreign_context = MultiTimeframeContextBuilder().build(series_map())
    changed_context_policy = MultiTimeframeContextPolicy(minimum_aligned_timeframes=4)
    policy = AnalysisPipelinePolicy(context_policy=changed_context_policy)

    with pytest.raises(
        AnalysisPipelineBuildError,
        match="INVALID_CONTEXT",
    ):
        MultiTimeframeAnalysisPipeline(policy).evaluate_context(foreign_context)


def test_context_build_failure_is_wrapped() -> None:
    mapping = series_map()
    del mapping[TimeframeName.M5]

    with pytest.raises(
        AnalysisPipelineBuildError,
        match="CONTEXT_BUILD_FAILED",
    ) as captured:
        MultiTimeframeAnalysisPipeline(pipeline_policy()).build(mapping)

    assert captured.value.stage == (AnalysisPipelineStage.CONTEXT)
    assert isinstance(
        captured.value.context_error,
        MultiTimeframeContextBuildError,
    )
    assert captured.value.context_error.reason == MultiTimeframeContextErrorReason.MISSING_TIMEFRAME


def test_readiness_failure_is_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.strategy.analysis_pipeline as module

    def fail_evaluation(
        self: object,
        context: MultiTimeframeContextSnapshot,
    ) -> object:
        raise ValueError("synthetic readiness failure")

    monkeypatch.setattr(
        module.CompositeStrategyReadinessGate,
        "evaluate",
        fail_evaluation,
    )

    with pytest.raises(
        AnalysisPipelineBuildError,
        match="READINESS_EVALUATION_FAILED",
    ) as captured:
        MultiTimeframeAnalysisPipeline(pipeline_policy()).evaluate_context(bullish_context())

    assert captured.value.stage == (AnalysisPipelineStage.READINESS)
    assert isinstance(
        captured.value.__cause__,
        ValueError,
    )


def test_build_as_of_uses_shared_observation_time() -> None:
    mapping = series_map()
    selected_time = OBSERVED_AT - timedelta(hours=1)

    snapshot = MultiTimeframeAnalysisPipeline(pipeline_policy()).build_as_of(
        mapping,
        selected_time,
    )

    assert snapshot.observed_at == selected_time
    assert all(context.as_of_time <= selected_time for context in snapshot.context.contexts)


def test_invalid_build_as_of_time_is_wrapped() -> None:
    with pytest.raises(
        AnalysisPipelineBuildError,
        match="CONTEXT_BUILD_FAILED",
    ) as captured:
        MultiTimeframeAnalysisPipeline(pipeline_policy()).build_as_of(
            series_map(),
            datetime(2026, 7, 25, 20, 0),
        )

    assert captured.value.stage == (AnalysisPipelineStage.CONTEXT)


def test_custom_readiness_policy_is_respected() -> None:
    policy = AnalysisPipelinePolicy(
        context_policy=(MultiTimeframeContextPolicy()),
        readiness_policy=StrategyReadinessPolicy(
            directional_policy=(
                DirectionalPermissionPolicy(allow_neutral_execution_timeframe=(False))
            )
        ),
    )
    context = MultiTimeframeContextBuilder(policy.context_policy).build(series_map())
    context = with_biases(
        context,
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
        },
    )

    snapshot = MultiTimeframeAnalysisPipeline(policy).evaluate_context(context)

    assert snapshot.is_blocked is True
    assert snapshot.reason == (StrategyReadinessReason.DIRECTION_BLOCKED)


def test_custom_freshness_policy_is_respected() -> None:
    policy = AnalysisPipelinePolicy(
        context_policy=(MultiTimeframeContextPolicy()),
        readiness_policy=StrategyReadinessPolicy(
            freshness_policy=ContextFreshnessPolicy(
                maximum_lag_candles=(
                    (TimeframeName.H4, 2),
                    (TimeframeName.H1, 1),
                    (TimeframeName.M15, 1),
                    (TimeframeName.M5, 1),
                )
            )
        ),
    )
    context = MultiTimeframeContextBuilder(policy.context_policy).build(
        series_map(h4_end_at=(OBSERVED_AT - timedelta(hours=8)))
    )
    context = with_biases(
        context,
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
        },
    )

    snapshot = MultiTimeframeAnalysisPipeline(policy).evaluate_context(context)

    assert snapshot.is_ready is True


def test_manual_snapshot_rejects_foreign_readiness() -> None:
    policy = pipeline_policy()
    context = bullish_context()
    readiness = CompositeStrategyReadinessGate(policy.readiness_policy).evaluate(context)
    foreign_context = bearish_context()
    foreign_readiness = CompositeStrategyReadinessGate(policy.readiness_policy).evaluate(
        foreign_context
    )

    with pytest.raises(
        ValueError,
        match="analysis context",
    ):
        AnalysisPipelineSnapshot(
            policy=policy,
            context=context,
            readiness=foreign_readiness,
        )

    assert readiness.context == context


def test_manual_snapshot_rejects_context_policy_mismatch() -> None:
    policy = pipeline_policy()
    context = bullish_context()
    readiness = CompositeStrategyReadinessGate(policy.readiness_policy).evaluate(context)
    changed_policy = replace(
        policy,
        context_policy=(MultiTimeframeContextPolicy(minimum_aligned_timeframes=4)),
    )

    with pytest.raises(
        ValueError,
        match="Context policy",
    ):
        AnalysisPipelineSnapshot(
            policy=changed_policy,
            context=context,
            readiness=readiness,
        )


def test_manual_snapshot_rejects_readiness_policy_mismatch() -> None:
    policy = pipeline_policy()
    context = bullish_context()
    readiness = CompositeStrategyReadinessGate(policy.readiness_policy).evaluate(context)
    changed_policy = replace(
        policy,
        readiness_policy=StrategyReadinessPolicy(
            directional_policy=(DirectionalPermissionPolicy(minimum_aligned_timeframes=4))
        ),
    )

    with pytest.raises(
        ValueError,
        match="Readiness policy",
    ):
        AnalysisPipelineSnapshot(
            policy=changed_policy,
            context=context,
            readiness=readiness,
        )


def test_snapshot_is_immutable() -> None:
    snapshot = MultiTimeframeAnalysisPipeline(pipeline_policy()).evaluate_context(bullish_context())

    with pytest.raises(FrozenInstanceError):
        snapshot.context = neutral_context()


def test_policy_is_immutable() -> None:
    policy = pipeline_policy()

    with pytest.raises(FrozenInstanceError):
        policy.context_policy = MultiTimeframeContextPolicy()


def test_pipeline_is_deterministic() -> None:
    pipeline = MultiTimeframeAnalysisPipeline(pipeline_policy())
    context = bullish_context()

    assert pipeline.evaluate_context(context) == pipeline.evaluate_context(context)


def test_function_api_delegates() -> None:
    snapshot = build_analysis_pipeline(
        series_map(),
        pipeline_policy(),
    )

    assert snapshot.is_blocked is True


def test_pipeline_alias_methods_delegate() -> None:
    pipeline = MultiTimeframeAnalysisPipeline(pipeline_policy())
    mapping = series_map()

    assert pipeline.build_latest(mapping) == pipeline.build(mapping)
    assert pipeline.evaluate(mapping) == pipeline.build(mapping)


def test_public_aliases_are_preserved() -> None:
    assert AnalysisPipeline is MultiTimeframeAnalysisPipeline
    assert AnalysisPolicy is AnalysisPipelinePolicy
    assert AnalysisSnapshot is AnalysisPipelineSnapshot
    assert GoldAnalysisPipeline is MultiTimeframeAnalysisPipeline
    assert MultiTimeframeAnalysisSnapshot is AnalysisPipelineSnapshot
    assert StrategyAnalysisPipeline is MultiTimeframeAnalysisPipeline
