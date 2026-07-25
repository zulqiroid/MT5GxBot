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
from app.strategy.displacement import DisplacementPolicy
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiContext,
    MultiContextBuilder,
    MultiContextCounts,
    MultiContextPolicy,
    MultiTimeframeAlignment,
    MultiTimeframeContext,
    MultiTimeframeContextBuilder,
    MultiTimeframeContextBuildError,
    MultiTimeframeContextCounts,
    MultiTimeframeContextErrorReason,
    MultiTimeframeContextPolicy,
    MultiTimeframeContextSnapshot,
    TimeframeAlignment,
    build_multi_timeframe_context,
)
from app.strategy.strategy_context import (
    StrategyContextBuildError,
    StrategyContextErrorReason,
    StrategyContextPolicy,
)
from app.strategy.swings import SwingDetectionPolicy

START = datetime(
    2026,
    7,
    20,
    0,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    timeframe: TimeframeName,
    *,
    count: int = 8,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    candles: list[ClosedCandle] = []

    for index in range(count):
        open_time = START + duration * index

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
    broker_symbol: str = "XAUUSDm",
) -> dict[TimeframeName, ClosedCandleSeries]:
    return {
        timeframe: create_series(
            timeframe,
            broker_symbol=broker_symbol,
        )
        for timeframe in GOLD_TIMEFRAME_HIERARCHY
    }


def context_policy() -> StrategyContextPolicy:
    return StrategyContextPolicy(
        swing_policy=SwingDetectionPolicy(
            left_bars=1,
            right_bars=1,
        ),
        displacement_policy=DisplacementPolicy(
            lookback_candles=2,
        ),
    )


def multi_policy(
    *,
    minimum_aligned_timeframes: int = 3,
) -> MultiTimeframeContextPolicy:
    return MultiTimeframeContextPolicy(
        context_policy=context_policy(),
        minimum_aligned_timeframes=(minimum_aligned_timeframes),
    )


def built_snapshot() -> MultiTimeframeContextSnapshot:
    return MultiTimeframeContextBuilder(multi_policy()).build(series_map())


def with_biases(
    snapshot: MultiTimeframeContextSnapshot,
    biases: dict[
        TimeframeName,
        MarketStructureBias,
    ],
) -> MultiTimeframeContextSnapshot:
    structure_biases = tuple(
        (
            context.timeframe,
            MarketStructureBias(
                biases.get(
                    context.timeframe,
                    MarketStructureBias.NEUTRAL,
                )
            ),
        )
        for context in snapshot.contexts
    )

    return replace(
        snapshot,
        structure_biases=structure_biases,
    )


def test_default_policy_uses_gold_hierarchy() -> None:
    policy = MultiTimeframeContextPolicy()

    assert policy.required_timeframes == (
        TimeframeName.H4,
        TimeframeName.H1,
        TimeframeName.M15,
        TimeframeName.M5,
    )
    assert policy.minimum_aligned_timeframes == 3
    assert isinstance(
        policy.context_policy,
        StrategyContextPolicy,
    )


@pytest.mark.parametrize(
    "required_timeframes",
    [
        (
            TimeframeName.H1,
            TimeframeName.H4,
            TimeframeName.M15,
            TimeframeName.M5,
        ),
        (
            TimeframeName.H4,
            TimeframeName.H1,
            TimeframeName.M15,
        ),
        (
            TimeframeName.H4,
            TimeframeName.H1,
            TimeframeName.M15,
            TimeframeName.H4,
        ),
        ("H4", "H1", "M15", "M5"),
    ],
)
def test_invalid_timeframe_hierarchy_is_rejected(
    required_timeframes: tuple[object, ...],
) -> None:
    with pytest.raises(ValueError):
        MultiTimeframeContextPolicy(required_timeframes=required_timeframes)


@pytest.mark.parametrize(
    "minimum",
    [0, True, 5],
)
def test_invalid_alignment_minimum_is_rejected(
    minimum: object,
) -> None:
    with pytest.raises(ValueError):
        MultiTimeframeContextPolicy(minimum_aligned_timeframes=minimum)


def test_invalid_context_policy_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="StrategyContextPolicy",
    ):
        MultiTimeframeContextPolicy(context_policy="invalid")


def test_builder_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="MultiTimeframeContextPolicy",
    ):
        MultiTimeframeContextBuilder(policy="invalid")


def test_invalid_series_map_type_is_fail_safe() -> None:
    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="INVALID_SERIES_MAP",
    ) as captured:
        MultiTimeframeContextBuilder(multi_policy()).build("invalid")

    assert captured.value.reason == (MultiTimeframeContextErrorReason.INVALID_SERIES_MAP)


def test_missing_timeframe_is_fail_safe() -> None:
    mapping = series_map()
    del mapping[TimeframeName.M5]

    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="MISSING_TIMEFRAME",
    ) as captured:
        MultiTimeframeContextBuilder(multi_policy()).build(mapping)

    assert captured.value.timeframe == TimeframeName.M5


def test_unexpected_timeframe_is_fail_safe() -> None:
    mapping = series_map()
    mapping["M1"] = create_series(TimeframeName.M5)

    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="UNEXPECTED_TIMEFRAME",
    ):
        MultiTimeframeContextBuilder(multi_policy()).build(mapping)


def test_mapping_value_requires_closed_series() -> None:
    mapping = series_map()
    mapping[TimeframeName.M5] = "invalid"

    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="INVALID_SERIES_MAP",
    ) as captured:
        MultiTimeframeContextBuilder(multi_policy()).build(mapping)

    assert captured.value.timeframe == TimeframeName.M5


def test_series_timeframe_must_match_key() -> None:
    mapping = series_map()
    mapping[TimeframeName.M5] = create_series(TimeframeName.M15)

    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="TIMEFRAME_MISMATCH",
    ) as captured:
        MultiTimeframeContextBuilder(multi_policy()).build(mapping)

    assert captured.value.timeframe == TimeframeName.M5


def test_all_timeframes_require_same_symbol() -> None:
    mapping = series_map()
    mapping[TimeframeName.M5] = create_series(
        TimeframeName.M5,
        broker_symbol="XAUUSD.pro",
    )

    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="SYMBOL_MISMATCH",
    ):
        MultiTimeframeContextBuilder(multi_policy()).build(mapping)


def test_non_gold_symbol_is_rejected() -> None:
    mapping = series_map(broker_symbol="EURUSD")

    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="UNSUPPORTED_SYMBOL",
    ):
        MultiTimeframeContextBuilder(multi_policy()).build(mapping)


def test_broker_gold_suffix_is_supported() -> None:
    snapshot = MultiTimeframeContextBuilder(multi_policy()).build(
        series_map(broker_symbol="XAUUSD.pro")
    )

    assert snapshot.broker_symbol == "XAUUSD.pro"


def test_complete_hierarchy_is_built_in_order() -> None:
    snapshot = built_snapshot()

    assert snapshot.timeframes == (
        TimeframeName.H4,
        TimeframeName.H1,
        TimeframeName.M15,
        TimeframeName.M5,
    )
    assert len(snapshot.contexts) == 4


def test_build_uses_latest_available_observation_time() -> None:
    mapping = series_map()
    snapshot = MultiTimeframeContextBuilder(multi_policy()).build(mapping)

    expected = max(series.candles[-1].close_time for series in mapping.values())

    assert snapshot.observed_at == expected


def test_no_context_contains_future_candle() -> None:
    snapshot = built_snapshot()

    assert all(context.as_of_time <= snapshot.observed_at for context in snapshot.contexts)


def test_build_as_of_truncates_each_timeframe() -> None:
    mapping = series_map()
    observed_at = START + get_timeframe_spec(TimeframeName.H4).duration * 4

    snapshot = MultiTimeframeContextBuilder(multi_policy()).build_as_of(
        mapping,
        observed_at,
    )

    assert snapshot.h4.source.count == 4
    assert snapshot.h1.source.count == 8
    assert snapshot.m15.source.count == 8
    assert snapshot.m5.source.count == 8
    assert snapshot.observed_at == observed_at


def test_naive_as_of_time_is_rejected() -> None:
    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="INVALID_AS_OF_TIME",
    ):
        MultiTimeframeContextBuilder(multi_policy()).build_as_of(
            series_map(),
            datetime(2026, 7, 21),
        )


def test_early_as_of_time_is_fail_safe() -> None:
    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="INSUFFICIENT_HISTORY",
    ) as captured:
        MultiTimeframeContextBuilder(multi_policy()).build_as_of(
            series_map(),
            START + timedelta(minutes=10),
        )

    assert captured.value.timeframe == TimeframeName.H4


def test_context_lookup_is_available() -> None:
    snapshot = built_snapshot()

    assert snapshot.context_for(TimeframeName.H4) is snapshot.contexts[0]
    assert snapshot.context_for(TimeframeName.M5) is snapshot.contexts[-1]


def test_invalid_context_lookup_is_rejected() -> None:
    with pytest.raises(ValueError):
        built_snapshot().context_for("M1")


def test_timeframe_role_views_are_available() -> None:
    snapshot = built_snapshot()

    assert snapshot.higher_timeframe_contexts == (
        snapshot.h4,
        snapshot.h1,
    )
    assert snapshot.setup_context is snapshot.m15
    assert snapshot.execution_context is snapshot.m5


def test_neutral_context_has_neutral_alignment() -> None:
    snapshot = built_snapshot()

    assert snapshot.alignment == (MultiTimeframeAlignment.NEUTRAL)
    assert snapshot.aligned_direction == (MultiTimeframeAlignment.NEUTRAL)
    assert snapshot.neutral_timeframes == (GOLD_TIMEFRAME_HIERARCHY)


def test_three_bullish_timeframes_align_bullishly() -> None:
    snapshot = with_biases(
        built_snapshot(),
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
        },
    )

    assert snapshot.alignment == (MultiTimeframeAlignment.BULLISH)
    assert snapshot.bullish_timeframes == (
        TimeframeName.H4,
        TimeframeName.H1,
        TimeframeName.M15,
    )


def test_alignment_below_minimum_remains_neutral() -> None:
    snapshot = with_biases(
        built_snapshot(),
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
        },
    )

    assert snapshot.alignment == (MultiTimeframeAlignment.NEUTRAL)


def test_three_bearish_timeframes_align_bearishly() -> None:
    snapshot = with_biases(
        built_snapshot(),
        {
            TimeframeName.H4: (MarketStructureBias.BEARISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
            TimeframeName.M15: (MarketStructureBias.BEARISH),
        },
    )

    assert snapshot.alignment == (MultiTimeframeAlignment.BEARISH)


def test_opposite_directional_biases_are_mixed() -> None:
    snapshot = with_biases(
        built_snapshot(),
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
            TimeframeName.M15: (MarketStructureBias.BULLISH),
        },
    )

    assert snapshot.alignment == (MultiTimeframeAlignment.MIXED)
    assert snapshot.has_directional_conflict is True


def test_full_alignment_is_reported() -> None:
    snapshot = with_biases(
        built_snapshot(),
        {timeframe: MarketStructureBias.BULLISH for timeframe in GOLD_TIMEFRAME_HIERARCHY},
    )

    assert snapshot.is_fully_aligned is True
    assert snapshot.alignment_score == Decimal("1")


def test_alignment_score_is_exact() -> None:
    snapshot = with_biases(
        built_snapshot(),
        {
            TimeframeName.H4: (MarketStructureBias.BEARISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
            TimeframeName.M15: (MarketStructureBias.BEARISH),
        },
    )

    assert snapshot.alignment_score == Decimal("0.75")


def test_higher_timeframes_can_align_bullishly() -> None:
    snapshot = with_biases(
        built_snapshot(),
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BULLISH),
        },
    )

    assert snapshot.higher_timeframe_alignment == (MultiTimeframeAlignment.BULLISH)
    assert snapshot.higher_timeframes_aligned is True


def test_higher_timeframe_conflict_is_mixed() -> None:
    snapshot = with_biases(
        built_snapshot(),
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
            TimeframeName.H1: (MarketStructureBias.BEARISH),
        },
    )

    assert snapshot.higher_timeframe_alignment == (MultiTimeframeAlignment.MIXED)
    assert snapshot.higher_timeframes_aligned is False


def test_one_neutral_higher_timeframe_is_neutral() -> None:
    snapshot = with_biases(
        built_snapshot(),
        {
            TimeframeName.H4: (MarketStructureBias.BULLISH),
        },
    )

    assert snapshot.higher_timeframe_alignment == (MultiTimeframeAlignment.NEUTRAL)


def test_latest_close_and_lag_are_available() -> None:
    snapshot = built_snapshot()

    assert snapshot.latest_close_for(TimeframeName.H4) == snapshot.h4.as_of_time
    assert snapshot.lag_for(TimeframeName.H4) == (snapshot.observed_at - snapshot.h4.as_of_time)
    assert snapshot.lag_for(TimeframeName.H4) >= timedelta(0)


def test_aggregate_counts_match_context_sums() -> None:
    snapshot = built_snapshot()
    counts = snapshot.counts

    assert isinstance(
        counts,
        MultiTimeframeContextCounts,
    )
    assert counts.context_count == 4
    assert counts.swing_points == sum(context.counts.swing_points for context in snapshot.contexts)
    assert counts.total_patterns == sum(
        context.counts.total_patterns for context in snapshot.contexts
    )
    assert counts.total_lifecycle_events == sum(
        context.counts.total_lifecycle_events for context in snapshot.contexts
    )


def test_snapshot_stable_id_is_deterministic() -> None:
    snapshot = built_snapshot()

    assert snapshot.stable_id == (f"XAUUSDm:MULTI_TIMEFRAME:{snapshot.observed_at.isoformat()}")


def test_context_build_failure_is_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.strategy.multi_timeframe_context as module

    context_error = StrategyContextBuildError(
        StrategyContextErrorReason.PIPELINE_STAGE_FAILED,
        "synthetic context failure",
    )

    def fail_build(
        self: object,
        series: ClosedCandleSeries,
    ) -> object:
        raise context_error

    monkeypatch.setattr(
        module.StrategyContextBuilder,
        "build",
        fail_build,
    )

    with pytest.raises(
        MultiTimeframeContextBuildError,
        match="CONTEXT_BUILD_FAILED",
    ) as captured:
        MultiTimeframeContextBuilder(multi_policy()).build(series_map())

    assert captured.value.timeframe == TimeframeName.H4
    assert captured.value.context_error is context_error
    assert captured.value.__cause__ is context_error


def test_snapshot_rejects_wrong_context_order() -> None:
    snapshot = built_snapshot()

    with pytest.raises(
        ValueError,
        match="ordered",
    ):
        replace(
            snapshot,
            contexts=tuple(reversed(snapshot.contexts)),
        )


def test_snapshot_rejects_symbol_mismatch() -> None:
    snapshot = built_snapshot()
    foreign = MultiTimeframeContextBuilder(multi_policy()).build(
        series_map(broker_symbol="XAUUSD.pro")
    )

    contexts = (
        foreign.contexts[0],
        *snapshot.contexts[1:],
    )

    with pytest.raises(
        ValueError,
        match="same broker symbol",
    ):
        replace(
            snapshot,
            contexts=contexts,
        )


def test_snapshot_rejects_context_policy_mismatch() -> None:
    snapshot = built_snapshot()
    changed_policy = MultiTimeframeContextPolicy(
        context_policy=replace(
            context_policy(),
            displacement_policy=DisplacementPolicy(lookback_candles=3),
        )
    )

    with pytest.raises(
        ValueError,
        match="context policy",
    ):
        replace(
            snapshot,
            policy=changed_policy,
        )


def test_snapshot_rejects_future_context() -> None:
    snapshot = built_snapshot()

    with pytest.raises(
        ValueError,
        match="after observed_at",
    ):
        replace(
            snapshot,
            observed_at=(snapshot.contexts[-1].as_of_time - timedelta(seconds=1)),
        )


def test_snapshot_is_immutable() -> None:
    snapshot = built_snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.contexts = ()


def test_policy_is_immutable() -> None:
    policy = multi_policy()

    with pytest.raises(FrozenInstanceError):
        policy.minimum_aligned_timeframes = 4


def test_counts_are_immutable() -> None:
    counts = built_snapshot().counts

    with pytest.raises(FrozenInstanceError):
        counts.context_count = 0


def test_build_is_deterministic() -> None:
    builder = MultiTimeframeContextBuilder(multi_policy())
    mapping = series_map()

    assert builder.build(mapping) == builder.build(mapping)


def test_function_api_delegates() -> None:
    snapshot = build_multi_timeframe_context(
        series_map(),
        multi_policy(),
    )

    assert snapshot.timeframes == (GOLD_TIMEFRAME_HIERARCHY)


def test_builder_alias_methods_delegate() -> None:
    builder = MultiTimeframeContextBuilder(multi_policy())
    mapping = series_map()

    assert builder.build_latest(mapping) == builder.build(mapping)
    assert builder.evaluate(mapping) == builder.build(mapping)


def test_public_aliases_are_preserved() -> None:
    assert MultiContext is MultiTimeframeContextSnapshot
    assert MultiTimeframeContext is MultiTimeframeContextSnapshot
    assert MultiContextBuilder is MultiTimeframeContextBuilder
    assert MultiContextCounts is MultiTimeframeContextCounts
    assert MultiContextPolicy is MultiTimeframeContextPolicy
    assert TimeframeAlignment is MultiTimeframeAlignment
