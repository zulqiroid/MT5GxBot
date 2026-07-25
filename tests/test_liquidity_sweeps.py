from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.timeframes import get_timeframe_spec
from app.strategy.liquidity import (
    LiquidityPool,
    LiquidityPoolPolicy,
    LiquidityPoolSet,
    LiquiditySide,
)
from app.strategy.liquidity_sweeps import (
    LiquiditySweep,
    LiquiditySweepDetectionError,
    LiquiditySweepDetector,
    LiquiditySweepErrorReason,
    LiquiditySweepEvent,
    LiquiditySweepPolicy,
    LiquiditySweepSet,
    LiquiditySweepSnapshot,
    SweepDetector,
    SweepPolicy,
    detect_liquidity_sweeps,
)
from app.strategy.swings import (
    ConfirmedSwingPoint,
    ConfirmedSwingSet,
    SwingDetectionPolicy,
    SwingKind,
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
    rows: list[tuple[str, str, str]],
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    candles: list[ClosedCandle] = []

    for index, (close, high, low) in enumerate(rows):
        open_time = START + duration * index

        candles.append(
            ClosedCandle(
                broker_symbol=broker_symbol,
                timeframe=timeframe,
                open_time=open_time,
                observed_at=open_time + duration,
                open=close,
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


def create_swing_set(
    series: ClosedCandleSeries,
    specifications: list[tuple[int, SwingKind]],
) -> ConfirmedSwingSet:
    policy = SwingDetectionPolicy(
        left_bars=1,
        right_bars=1,
    )
    order = {
        SwingKind.HIGH: 0,
        SwingKind.LOW: 1,
    }

    points = tuple(
        ConfirmedSwingPoint(
            index=index,
            kind=kind,
            candle=series.candles[index],
            confirmed_by_index=index + 1,
            confirmed_at=series.candles[index + 1].close_time,
        )
        for index, kind in sorted(
            specifications,
            key=lambda value: (
                value[0],
                order[value[1]],
            ),
        )
    )

    return ConfirmedSwingSet(
        source=series,
        policy=policy,
        points=points,
    )


def create_buy_side_pool_set(
    *,
    sweep_close: str = "99.50",
    sweep_high: str = "101.00",
    sweep_low: str = "98.50",
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> LiquidityPoolSet:
    series = create_series(
        [
            ("90", "95", "85"),
            ("95", "100", "90"),
            ("94", "97", "91"),
            ("96", "100.20", "92"),
            ("95", "98", "91"),
            (sweep_close, sweep_high, sweep_low),
            ("98", "100", "96"),
        ],
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
        ],
    )
    pool = LiquidityPool(
        side=LiquiditySide.BUY_SIDE,
        touches=swings.highs,
    )

    return LiquidityPoolSet(
        swings=swings,
        policy=LiquidityPoolPolicy(),
        pools=(pool,),
    )


def create_sell_side_pool_set(
    *,
    sweep_close: str = "90.50",
    sweep_high: str = "92",
    sweep_low: str = "88.50",
) -> LiquidityPoolSet:
    series = create_series(
        [
            ("100", "105", "95"),
            ("95", "100", "90"),
            ("96", "101", "93"),
            ("94", "99", "89.80"),
            ("95", "100", "92"),
            (sweep_close, sweep_high, sweep_low),
            ("93", "97", "91"),
        ]
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.LOW),
            (3, SwingKind.LOW),
        ],
    )
    pool = LiquidityPool(
        side=LiquiditySide.SELL_SIDE,
        touches=swings.lows,
    )

    return LiquidityPoolSet(
        swings=swings,
        policy=LiquidityPoolPolicy(),
        pools=(pool,),
    )


def test_default_policy_requires_close_reclaim() -> None:
    policy = LiquiditySweepPolicy()

    assert policy.minimum_penetration == Decimal("0")
    assert policy.require_close_back_inside is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"minimum_penetration": "-0.01"},
        {"minimum_penetration": "NaN"},
        {"minimum_penetration": "Infinity"},
        {"require_close_back_inside": 1},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        LiquiditySweepPolicy(**overrides)


def test_buy_side_liquidity_sweep_is_detected() -> None:
    result = LiquiditySweepDetector().detect(create_buy_side_pool_set())

    assert result.count == 1
    assert len(result.buy_side_sweeps) == 1
    assert result.sell_side_sweeps == ()

    event = result.events[0]

    assert event.side == LiquiditySide.BUY_SIDE
    assert event.is_buy_side_sweep is True
    assert event.implied_direction == "BEARISH"


def test_sell_side_liquidity_sweep_is_detected() -> None:
    result = LiquiditySweepDetector().detect(create_sell_side_pool_set())

    assert result.count == 1
    assert result.buy_side_sweeps == ()
    assert len(result.sell_side_sweeps) == 1

    event = result.events[0]

    assert event.is_sell_side_sweep is True
    assert event.implied_direction == "BULLISH"


def test_pool_cannot_be_swept_on_confirmation_candle() -> None:
    pool_set = create_buy_side_pool_set()
    source = pool_set.swings.source
    pool = pool_set.pools[0]
    candles = list(source.candles)

    confirmation = candles[pool.confirmation_index]

    candles[pool.confirmation_index] = ClosedCandle(
        broker_symbol=confirmation.broker_symbol,
        timeframe=confirmation.timeframe,
        open_time=confirmation.open_time,
        observed_at=confirmation.close_time,
        open="99",
        high="101",
        low="91",
        close="99",
        tick_volume=1000,
        spread=20,
        real_volume=0,
    )

    updated_series = ClosedCandleSeries(
        broker_symbol=source.broker_symbol,
        timeframe=source.timeframe,
        candles=tuple(candles),
    )
    updated_swings = ConfirmedSwingSet(
        source=updated_series,
        policy=pool_set.swings.policy,
        points=tuple(
            ConfirmedSwingPoint(
                index=point.index,
                kind=point.kind,
                candle=updated_series.candles[point.index],
                confirmed_by_index=(point.confirmed_by_index),
                confirmed_at=updated_series.candles[point.confirmed_by_index].close_time,
            )
            for point in pool_set.swings.points
        ),
    )
    updated_pool = LiquidityPool(
        side=pool.side,
        touches=updated_swings.highs,
    )
    updated_pool_set = LiquidityPoolSet(
        swings=updated_swings,
        policy=pool_set.policy,
        pools=(updated_pool,),
    )

    result = LiquiditySweepDetector().detect(updated_pool_set)

    assert result.events[0].index == 5


def test_exact_boundary_touch_is_not_a_sweep() -> None:
    result = LiquiditySweepDetector().detect(create_buy_side_pool_set(sweep_high="100.20"))

    assert result.events == ()


def test_exact_minimum_penetration_is_not_a_sweep() -> None:
    policy = LiquiditySweepPolicy(minimum_penetration="0.80")

    result = LiquiditySweepDetector(policy).detect(create_buy_side_pool_set(sweep_high="101.00"))

    assert result.events == ()


def test_penetration_above_minimum_is_detected() -> None:
    policy = LiquiditySweepPolicy(minimum_penetration="0.79")

    result = LiquiditySweepDetector(policy).detect(create_buy_side_pool_set(sweep_high="101.00"))

    assert result.count == 1


def test_buy_side_close_must_return_inside() -> None:
    result = LiquiditySweepDetector().detect(
        create_buy_side_pool_set(
            sweep_close="100.50",
            sweep_high="101.00",
        )
    )

    assert result.events == ()


def test_sell_side_close_must_return_inside() -> None:
    result = LiquiditySweepDetector().detect(
        create_sell_side_pool_set(
            sweep_close="89.50",
            sweep_low="88.50",
        )
    )

    assert result.events == ()


def test_wick_only_mode_allows_outside_close() -> None:
    policy = LiquiditySweepPolicy(require_close_back_inside=False)

    result = LiquiditySweepDetector(policy).detect(
        create_buy_side_pool_set(
            sweep_close="100.50",
            sweep_high="101.00",
        )
    )

    assert result.count == 1
    assert result.events[0].closed_back_inside is False


def test_swept_pool_does_not_generate_repeat_event() -> None:
    pool_set = create_buy_side_pool_set()
    source = pool_set.swings.source
    candles = list(source.candles)

    last = candles[6]
    candles[6] = ClosedCandle(
        broker_symbol=last.broker_symbol,
        timeframe=last.timeframe,
        open_time=last.open_time,
        observed_at=last.close_time,
        open="99",
        high="102",
        low="97",
        close="99",
        tick_volume=1000,
        spread=20,
        real_volume=0,
    )

    series = ClosedCandleSeries(
        broker_symbol=source.broker_symbol,
        timeframe=source.timeframe,
        candles=tuple(candles),
    )
    swings = ConfirmedSwingSet(
        source=series,
        policy=pool_set.swings.policy,
        points=tuple(
            ConfirmedSwingPoint(
                index=point.index,
                kind=point.kind,
                candle=series.candles[point.index],
                confirmed_by_index=(point.confirmed_by_index),
                confirmed_at=series.candles[point.confirmed_by_index].close_time,
            )
            for point in pool_set.swings.points
        ),
    )
    pool = LiquidityPool(
        side=LiquiditySide.BUY_SIDE,
        touches=swings.highs,
    )
    rebuilt = LiquidityPoolSet(
        swings=swings,
        policy=pool_set.policy,
        pools=(pool,),
    )

    result = LiquiditySweepDetector().detect(rebuilt)

    assert result.count == 1
    assert result.events[0].index == 5


def test_event_exposes_exact_sweep_context() -> None:
    result = LiquiditySweepDetector().detect(create_buy_side_pool_set())
    event = result.events[0]

    assert event.index == 5
    assert event.boundary == Decimal("100.20")
    assert event.extreme_price == Decimal("101.00")
    assert event.penetration == Decimal("0.80")
    assert event.liquidity_level == Decimal("100.10")
    assert event.closed_back_inside is True
    assert event.confirmed_at == event.candle.close_time
    assert event.stable_id.endswith(":SWEEP:5")


def test_result_preserves_market_context() -> None:
    result = LiquiditySweepDetector().detect(
        create_buy_side_pool_set(
            timeframe=TimeframeName.H1,
            broker_symbol="XAUUSD.pro",
        )
    )

    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1


def test_result_exposes_swept_and_unswept_pools() -> None:
    result = LiquiditySweepDetector().detect(create_buy_side_pool_set())

    assert result.swept_pools == (result.pool_set.pools[0],)
    assert result.unswept_pools == ()
    assert result.was_swept(result.pool_set.pools[0]) is True


def test_no_sweep_preserves_unswept_pool() -> None:
    result = LiquiditySweepDetector().detect(create_buy_side_pool_set(sweep_high="100.20"))

    assert result.swept_pools == ()
    assert result.unswept_pools == result.pool_set.pools
    assert result.latest is None


def test_side_and_index_filters_are_available() -> None:
    result = LiquiditySweepDetector().detect(create_buy_side_pool_set())

    assert result.events_for_side(LiquiditySide.BUY_SIDE) == result.events
    assert result.events_for_side(LiquiditySide.SELL_SIDE) == ()
    assert result.events_at(5) == result.events
    assert result.events_at(4) == ()


def test_invalid_side_filter_is_rejected() -> None:
    result = LiquiditySweepDetector().detect(create_buy_side_pool_set())

    with pytest.raises(ValueError):
        result.events_for_side("INVALID")


def test_was_swept_requires_pool_type() -> None:
    result = LiquiditySweepDetector().detect(create_buy_side_pool_set())

    with pytest.raises(ValueError):
        result.was_swept("invalid")


def test_empty_pool_set_returns_empty_snapshot() -> None:
    series = create_series(
        [
            ("90", "95", "85"),
            ("91", "96", "86"),
            ("92", "97", "87"),
        ]
    )
    swings = create_swing_set(series, [])
    pool_set = LiquidityPoolSet(
        swings=swings,
        policy=LiquidityPoolPolicy(),
        pools=(),
    )

    result = LiquiditySweepDetector().detect(pool_set)

    assert result.count == 0
    assert result.events == ()
    assert result.unswept_pools == ()


def test_deepest_buy_side_pool_is_selected() -> None:
    series = create_series(
        [
            ("90", "95", "85"),
            ("95", "100", "90"),
            ("94", "97", "91"),
            ("96", "100.20", "92"),
            ("95", "105", "91"),
            ("104", "105.20", "92"),
            ("106", "110", "98"),
            ("99", "108", "97"),
        ]
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
            (4, SwingKind.HIGH),
            (5, SwingKind.HIGH),
        ],
    )
    lower_pool = LiquidityPool(
        side=LiquiditySide.BUY_SIDE,
        touches=(
            swings.highs[0],
            swings.highs[1],
        ),
    )
    higher_pool = LiquidityPool(
        side=LiquiditySide.BUY_SIDE,
        touches=(
            swings.highs[2],
            swings.highs[3],
        ),
    )
    pool_set = LiquidityPoolSet(
        swings=swings,
        policy=LiquidityPoolPolicy(),
        pools=(lower_pool, higher_pool),
    )

    result = LiquiditySweepDetector().detect(pool_set)

    assert result.count == 1
    assert result.events[0].index == 7
    assert result.events[0].pool == higher_pool
    assert result.unswept_pools == (lower_pool,)


def test_ambiguous_two_sided_sweep_is_fail_safe() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("95", "100", "90"),
            ("96", "98", "92"),
            ("95", "100.20", "89.80"),
            ("96", "98", "92"),
            ("95", "101", "89"),
            ("96", "98", "92"),
        ]
    )

    swing_policy = SwingDetectionPolicy(
        left_bars=1,
        right_bars=1,
        allow_dual_swings=True,
    )

    points = tuple(
        ConfirmedSwingPoint(
            index=index,
            kind=kind,
            candle=series.candles[index],
            confirmed_by_index=index + 1,
            confirmed_at=series.candles[index + 1].close_time,
        )
        for index, kind in (
            (1, SwingKind.HIGH),
            (1, SwingKind.LOW),
            (3, SwingKind.HIGH),
            (3, SwingKind.LOW),
        )
    )

    swings = ConfirmedSwingSet(
        source=series,
        policy=swing_policy,
        points=points,
    )

    buy_pool = LiquidityPool(
        side=LiquiditySide.BUY_SIDE,
        touches=swings.highs,
    )
    sell_pool = LiquidityPool(
        side=LiquiditySide.SELL_SIDE,
        touches=swings.lows,
    )

    pool_set = LiquidityPoolSet(
        swings=swings,
        policy=LiquidityPoolPolicy(price_tolerance="0.50"),
        pools=(buy_pool, sell_pool),
    )

    with pytest.raises(
        LiquiditySweepDetectionError,
        match="AMBIGUOUS_SWEEP",
    ) as captured:
        LiquiditySweepDetector().detect(pool_set)

    assert captured.value.reason == (LiquiditySweepErrorReason.AMBIGUOUS_SWEEP)
    assert captured.value.candle_index == 5


def test_invalid_pool_set_type_is_fail_safe() -> None:
    with pytest.raises(
        LiquiditySweepDetectionError,
        match="INVALID_POOL_SET",
    ) as captured:
        LiquiditySweepDetector().detect("invalid")

    assert captured.value.reason == (LiquiditySweepErrorReason.INVALID_POOL_SET)


def test_detector_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="LiquiditySweepPolicy",
    ):
        LiquiditySweepDetector(policy="invalid")


def test_event_rejects_confirmation_candle() -> None:
    pool_set = create_buy_side_pool_set()
    pool = pool_set.pools[0]

    with pytest.raises(
        ValueError,
        match="after",
    ):
        LiquiditySweepEvent(
            index=pool.confirmation_index,
            pool=pool,
            candle=pool_set.swings.source.candles[pool.confirmation_index],
        )


def test_event_rejects_nonpenetrating_candle() -> None:
    pool_set = create_buy_side_pool_set(sweep_high="100.20")
    pool = pool_set.pools[0]

    with pytest.raises(
        ValueError,
        match="trade above",
    ):
        LiquiditySweepEvent(
            index=5,
            pool=pool,
            candle=pool_set.swings.source.candles[5],
        )


def test_snapshot_rejects_duplicate_pool_sweeps() -> None:
    pool_set = create_buy_side_pool_set()
    pool = pool_set.pools[0]
    source = pool_set.swings.source

    first = LiquiditySweepEvent(
        index=5,
        pool=pool,
        candle=source.candles[5],
    )

    second_candle = ClosedCandle(
        broker_symbol=source.broker_symbol,
        timeframe=source.timeframe,
        open_time=source.candles[6].open_time,
        observed_at=source.candles[6].close_time,
        open="99",
        high="102",
        low="97",
        close="99",
        tick_volume=1000,
        spread=20,
        real_volume=0,
    )

    expanded_series = ClosedCandleSeries(
        broker_symbol=source.broker_symbol,
        timeframe=source.timeframe,
        candles=(
            *source.candles[:6],
            second_candle,
        ),
    )
    expanded_swings = ConfirmedSwingSet(
        source=expanded_series,
        policy=pool_set.swings.policy,
        points=tuple(
            ConfirmedSwingPoint(
                index=point.index,
                kind=point.kind,
                candle=expanded_series.candles[point.index],
                confirmed_by_index=(point.confirmed_by_index),
                confirmed_at=expanded_series.candles[point.confirmed_by_index].close_time,
            )
            for point in pool_set.swings.points
        ),
    )
    expanded_pool = LiquidityPool(
        side=LiquiditySide.BUY_SIDE,
        touches=expanded_swings.highs,
    )
    expanded_pool_set = LiquidityPoolSet(
        swings=expanded_swings,
        policy=pool_set.policy,
        pools=(expanded_pool,),
    )
    first = LiquiditySweepEvent(
        index=5,
        pool=expanded_pool,
        candle=expanded_series.candles[5],
    )
    second = LiquiditySweepEvent(
        index=6,
        pool=expanded_pool,
        candle=expanded_series.candles[6],
    )

    with pytest.raises(
        ValueError,
        match="more than once",
    ):
        LiquiditySweepSnapshot(
            pool_set=expanded_pool_set,
            policy=LiquiditySweepPolicy(),
            events=(first, second),
        )


def test_event_is_immutable() -> None:
    event = LiquiditySweepDetector().detect(create_buy_side_pool_set()).events[0]

    with pytest.raises(FrozenInstanceError):
        event.index = 6


def test_snapshot_is_immutable() -> None:
    result = LiquiditySweepDetector().detect(create_buy_side_pool_set())

    with pytest.raises(FrozenInstanceError):
        result.events = ()


def test_function_api_delegates() -> None:
    result = detect_liquidity_sweeps(create_buy_side_pool_set())

    assert result.count == 1


def test_detector_alias_methods_delegate() -> None:
    detector = LiquiditySweepDetector()
    pool_set = create_buy_side_pool_set()

    assert detector.evaluate(pool_set) == detector.detect(pool_set)
    assert detector.find(pool_set) == detector.detect(pool_set)


def test_public_aliases_are_preserved() -> None:
    assert LiquiditySweep is LiquiditySweepEvent
    assert LiquiditySweepSet is LiquiditySweepSnapshot
    assert SweepDetector is LiquiditySweepDetector
    assert SweepPolicy is LiquiditySweepPolicy
