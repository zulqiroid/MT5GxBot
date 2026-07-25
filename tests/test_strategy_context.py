from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.timeframes import get_timeframe_spec
from app.strategy.dealing_ranges import (
    DealingRangePolicy,
    DealingRangeSet,
)
from app.strategy.displacement import (
    DisplacementPolicy,
    DisplacementSet,
)
from app.strategy.fair_value_gaps import (
    FairValueGapPolicy,
    FairValueGapSet,
)
from app.strategy.fvg_mitigation import (
    FairValueGapMitigationPolicy,
    FairValueGapMitigationSnapshot,
)
from app.strategy.liquidity import (
    LiquidityPoolPolicy,
    LiquidityPoolSet,
)
from app.strategy.liquidity_sweeps import (
    LiquiditySweepPolicy,
    LiquiditySweepSnapshot,
)
from app.strategy.market_structure import (
    MarketStructurePolicy,
    MarketStructureSnapshot,
)
from app.strategy.order_block_lifecycle import (
    OrderBlockLifecyclePolicy,
    OrderBlockLifecycleSnapshot,
)
from app.strategy.order_blocks import (
    OrderBlockPolicy,
    OrderBlockSet,
)
from app.strategy.ote_zones import (
    OptimalTradeEntryPolicy,
    OptimalTradeEntryZoneSet,
)
from app.strategy.strategy_context import (
    ContextBuilder,
    ContextCounts,
    ContextPolicy,
    MarketContext,
    StrategyContext,
    StrategyContextBuilder,
    StrategyContextBuildError,
    StrategyContextCounts,
    StrategyContextErrorReason,
    StrategyContextPolicy,
    StrategyContextSnapshot,
    StrategyContextStage,
    StrategySnapshot,
    build_strategy_context,
)
from app.strategy.swings import (
    ConfirmedSwingSet,
    SwingDetectionPolicy,
)

START = datetime(
    2026,
    7,
    25,
    12,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    rows: list[tuple[str, str, str, str]],
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    candles: list[ClosedCandle] = []

    for index, (open_, high, low, close) in enumerate(rows):
        open_time = START + duration * index

        candles.append(
            ClosedCandle(
                broker_symbol=broker_symbol,
                timeframe=timeframe,
                open_time=open_time,
                observed_at=open_time + duration,
                open=open_,
                high=high,
                low=low,
                close=close,
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


def strategy_series(
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    return create_series(
        [
            ("100", "102", "98", "101"),
            ("101", "102", "99", "100"),
            ("100", "102", "96", "97"),
            ("97", "110", "97", "109"),
            ("109", "112", "106", "111"),
            ("111", "113", "108", "109"),
            ("109", "111", "103", "104"),
            ("104", "106", "100", "101"),
            ("101", "103", "95", "96"),
            ("96", "100", "94", "99"),
        ],
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )


def context_policy() -> StrategyContextPolicy:
    return StrategyContextPolicy(
        swing_policy=SwingDetectionPolicy(
            left_bars=1,
            right_bars=1,
        ),
        market_structure_policy=(MarketStructurePolicy()),
        liquidity_pool_policy=LiquidityPoolPolicy(
            price_tolerance="0.50",
            minimum_touches=2,
            maximum_touch_gap=100,
        ),
        liquidity_sweep_policy=LiquiditySweepPolicy(),
        fair_value_gap_policy=FairValueGapPolicy(),
        fvg_mitigation_policy=(FairValueGapMitigationPolicy()),
        displacement_policy=DisplacementPolicy(
            lookback_candles=2,
        ),
        order_block_policy=OrderBlockPolicy(),
        order_block_lifecycle_policy=(OrderBlockLifecyclePolicy()),
        dealing_range_policy=DealingRangePolicy(),
        optimal_trade_entry_policy=(OptimalTradeEntryPolicy()),
    )


def built_context() -> StrategyContextSnapshot:
    return StrategyContextBuilder(context_policy()).build(strategy_series())


def test_default_policy_contains_all_pipeline_policies() -> None:
    policy = StrategyContextPolicy()

    assert isinstance(
        policy.swing_policy,
        SwingDetectionPolicy,
    )
    assert isinstance(
        policy.market_structure_policy,
        MarketStructurePolicy,
    )
    assert isinstance(
        policy.liquidity_pool_policy,
        LiquidityPoolPolicy,
    )
    assert isinstance(
        policy.liquidity_sweep_policy,
        LiquiditySweepPolicy,
    )
    assert isinstance(
        policy.fair_value_gap_policy,
        FairValueGapPolicy,
    )
    assert isinstance(
        policy.fvg_mitigation_policy,
        FairValueGapMitigationPolicy,
    )
    assert isinstance(
        policy.displacement_policy,
        DisplacementPolicy,
    )
    assert isinstance(
        policy.order_block_policy,
        OrderBlockPolicy,
    )
    assert isinstance(
        policy.order_block_lifecycle_policy,
        OrderBlockLifecyclePolicy,
    )
    assert isinstance(
        policy.dealing_range_policy,
        DealingRangePolicy,
    )
    assert isinstance(
        policy.optimal_trade_entry_policy,
        OptimalTradeEntryPolicy,
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("swing_policy", "invalid"),
        ("market_structure_policy", "invalid"),
        ("liquidity_pool_policy", "invalid"),
        ("liquidity_sweep_policy", "invalid"),
        ("fair_value_gap_policy", "invalid"),
        ("fvg_mitigation_policy", "invalid"),
        ("displacement_policy", "invalid"),
        ("order_block_policy", "invalid"),
        ("order_block_lifecycle_policy", "invalid"),
        ("dealing_range_policy", "invalid"),
        ("optimal_trade_entry_policy", "invalid"),
    ],
)
def test_invalid_nested_policy_is_rejected(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        StrategyContextPolicy(**{field_name: value})


def test_minimum_history_uses_strictest_component() -> None:
    policy = context_policy()

    assert policy.minimum_history == 3

    larger = replace(
        policy,
        displacement_policy=DisplacementPolicy(lookback_candles=5),
    )

    assert larger.minimum_history == 6


def test_builder_requires_context_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="StrategyContextPolicy",
    ):
        StrategyContextBuilder(policy="invalid")


def test_invalid_series_type_is_fail_safe() -> None:
    with pytest.raises(
        StrategyContextBuildError,
        match="INVALID_SERIES",
    ) as captured:
        StrategyContextBuilder(context_policy()).build("invalid")

    assert captured.value.reason == (StrategyContextErrorReason.INVALID_SERIES)
    assert captured.value.stage is None


def test_insufficient_history_is_fail_safe() -> None:
    series = create_series(
        [
            ("100", "102", "98", "101"),
            ("101", "102", "99", "100"),
        ]
    )

    with pytest.raises(
        StrategyContextBuildError,
        match="INSUFFICIENT_HISTORY",
    ) as captured:
        StrategyContextBuilder(context_policy()).build(series)

    assert captured.value.reason == (StrategyContextErrorReason.INSUFFICIENT_HISTORY)


@pytest.mark.parametrize(
    "index",
    [-1, 10, True, "4"],
)
def test_invalid_as_of_index_is_fail_safe(
    index: object,
) -> None:
    with pytest.raises(
        StrategyContextBuildError,
        match="INVALID_AS_OF_INDEX",
    ) as captured:
        StrategyContextBuilder(context_policy()).build_as_of(
            strategy_series(),
            index,
        )

    assert captured.value.reason == (StrategyContextErrorReason.INVALID_AS_OF_INDEX)


def test_context_builds_complete_pipeline() -> None:
    context = built_context()

    assert isinstance(
        context.swings,
        ConfirmedSwingSet,
    )
    assert isinstance(
        context.market_structure,
        MarketStructureSnapshot,
    )
    assert isinstance(
        context.liquidity_pools,
        LiquidityPoolSet,
    )
    assert isinstance(
        context.liquidity_sweeps,
        LiquiditySweepSnapshot,
    )
    assert isinstance(
        context.fair_value_gaps,
        FairValueGapSet,
    )
    assert isinstance(
        context.fvg_mitigation,
        FairValueGapMitigationSnapshot,
    )
    assert isinstance(
        context.displacements,
        DisplacementSet,
    )
    assert isinstance(
        context.order_blocks,
        OrderBlockSet,
    )
    assert isinstance(
        context.order_block_lifecycle,
        OrderBlockLifecycleSnapshot,
    )
    assert isinstance(
        context.dealing_ranges,
        DealingRangeSet,
    )
    assert isinstance(
        context.optimal_trade_entry_zones,
        OptimalTradeEntryZoneSet,
    )


def test_pipeline_produces_expected_core_patterns() -> None:
    counts = built_context().counts

    assert counts.swing_points == 2
    assert counts.displacement_impulses == 1
    assert counts.order_blocks == 1
    assert counts.dealing_ranges == 1
    assert counts.optimal_trade_entry_zones == 1
    assert counts.fair_value_gaps >= 2


def test_context_preserves_market_context() -> None:
    context = StrategyContextBuilder(context_policy()).build(
        strategy_series(
            timeframe=TimeframeName.H1,
            broker_symbol="XAUUSD.pro",
        )
    )

    assert context.broker_symbol == "XAUUSD.pro"
    assert context.timeframe == TimeframeName.H1
    assert context.last_closed_candle.broker_symbol == "XAUUSD.pro"


def test_context_uses_same_source_through_pipeline() -> None:
    context = built_context()

    assert context.swings.source == context.source
    assert context.fair_value_gaps.source == context.source
    assert context.displacements.source == context.source
    assert context.liquidity_pools.swings == context.swings
    assert context.liquidity_sweeps.pool_set == context.liquidity_pools
    assert context.fvg_mitigation.gap_set == context.fair_value_gaps
    assert context.order_blocks.displacements == context.displacements
    assert context.order_block_lifecycle.order_blocks == context.order_blocks
    assert context.dealing_ranges.swings == context.swings
    assert context.optimal_trade_entry_zones.dealing_ranges == context.dealing_ranges


def test_context_counts_are_immutable_and_exact() -> None:
    context = built_context()
    counts = context.counts

    assert isinstance(counts, StrategyContextCounts)
    assert counts.total_patterns >= 7
    assert counts.total_lifecycle_events >= 1

    with pytest.raises(FrozenInstanceError):
        counts.swing_points = 0


def test_as_of_metadata_uses_latest_closed_candle() -> None:
    context = built_context()

    assert context.as_of_index == 9
    assert context.as_of_time == (context.source.candles[9].close_time)
    assert context.last_close_price == Decimal("99")
    assert context.stable_id == ("XAUUSDm:M5:CONTEXT:9")


def test_active_component_views_are_available() -> None:
    context = built_context()

    assert context.active_fair_value_gaps == (context.fvg_mitigation.active_gaps)
    assert context.active_order_blocks == (context.order_block_lifecycle.active_blocks)
    assert context.unswept_liquidity_pools == (context.liquidity_sweeps.unswept_pools)


def test_latest_component_views_are_available() -> None:
    context = built_context()

    assert context.latest_swing is (context.swings.points[-1])
    assert context.latest_fair_value_gap is (context.fair_value_gaps.latest)
    assert context.latest_displacement is (context.displacements.latest)
    assert context.latest_order_block is (context.order_blocks.latest)
    assert context.latest_dealing_range is (context.dealing_ranges.latest)
    assert context.latest_optimal_trade_entry_zone is context.optimal_trade_entry_zones.latest


def test_build_as_of_truncates_source() -> None:
    series = strategy_series()
    context = StrategyContextBuilder(context_policy()).build_as_of(series, 4)

    assert context.source.count == 5
    assert context.as_of_index == 4
    assert context.source.candles == (series.candles[:5])


def test_build_as_of_prevents_future_range_lookahead() -> None:
    builder = StrategyContextBuilder(context_policy())
    series = strategy_series()

    early = builder.build_as_of(series, 4)
    complete = builder.build(series)

    assert early.dealing_ranges.count == 0
    assert early.optimal_trade_entry_zones.count == 0
    assert complete.dealing_ranges.count == 1
    assert complete.optimal_trade_entry_zones.count == 1


def test_build_as_of_latest_matches_full_context() -> None:
    builder = StrategyContextBuilder(context_policy())
    series = strategy_series()

    complete = builder.build(series)
    latest = builder.build_as_of(
        series,
        series.count - 1,
    )

    assert latest.source == complete.source
    assert latest.counts == complete.counts
    assert latest.stable_id == complete.stable_id


def test_build_is_deterministic() -> None:
    builder = StrategyContextBuilder(context_policy())
    series = strategy_series()

    assert builder.build(series) == builder.build(series)


def test_pipeline_stage_failure_is_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.strategy.strategy_context as module

    def fail_detection(
        series: ClosedCandleSeries,
    ) -> FairValueGapSet:
        raise ValueError("synthetic FVG failure")

    monkeypatch.setattr(
        module.FairValueGapDetector,
        "detect",
        lambda self, series: fail_detection(series),
    )

    with pytest.raises(
        StrategyContextBuildError,
        match="PIPELINE_STAGE_FAILED",
    ) as captured:
        StrategyContextBuilder(context_policy()).build(strategy_series())

    assert captured.value.reason == (StrategyContextErrorReason.PIPELINE_STAGE_FAILED)
    assert captured.value.stage == (StrategyContextStage.FAIR_VALUE_GAPS)
    assert isinstance(captured.value.__cause__, ValueError)


def test_snapshot_rejects_foreign_fvg_source() -> None:
    context = built_context()
    early = StrategyContextBuilder(context_policy()).build_as_of(strategy_series(), 4)

    with pytest.raises(
        ValueError,
        match="Fair value gap source",
    ):
        replace(
            context,
            fair_value_gaps=early.fair_value_gaps,
        )


def test_snapshot_rejects_wrong_component_type() -> None:
    context = built_context()

    with pytest.raises(
        ValueError,
        match="ConfirmedSwingSet",
    ):
        replace(
            context,
            swings="invalid",
        )


def test_snapshot_rejects_policy_mismatch() -> None:
    context = built_context()
    changed_policy = replace(
        context.policy,
        liquidity_sweep_policy=LiquiditySweepPolicy(minimum_penetration="0.10"),
    )

    with pytest.raises(
        ValueError,
        match="liquidity sweep policy",
    ):
        replace(
            context,
            policy=changed_policy,
        )


def test_context_is_immutable() -> None:
    context = built_context()

    with pytest.raises(FrozenInstanceError):
        context.source = strategy_series()


def test_policy_is_immutable() -> None:
    policy = context_policy()

    with pytest.raises(FrozenInstanceError):
        policy.swing_policy = SwingDetectionPolicy()


def test_function_api_delegates() -> None:
    context = build_strategy_context(
        strategy_series(),
        context_policy(),
    )

    assert context.counts.order_blocks == 1


def test_builder_alias_methods_delegate() -> None:
    builder = StrategyContextBuilder(context_policy())
    series = strategy_series()

    assert builder.build_latest(series) == builder.build(series)
    assert builder.evaluate(series) == builder.build(series)


def test_public_aliases_are_preserved() -> None:
    assert ContextBuilder is StrategyContextBuilder
    assert ContextCounts is StrategyContextCounts
    assert ContextPolicy is StrategyContextPolicy
    assert MarketContext is StrategyContextSnapshot
    assert StrategyContext is StrategyContextSnapshot
    assert StrategySnapshot is StrategyContextSnapshot
