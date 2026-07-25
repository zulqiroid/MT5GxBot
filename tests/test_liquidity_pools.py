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
    LiquidityDetectionError,
    LiquidityDetectionErrorReason,
    LiquidityDetector,
    LiquidityPolicy,
    LiquidityPool,
    LiquidityPoolCollection,
    LiquidityPoolDetector,
    LiquidityPoolPolicy,
    LiquidityPoolSet,
    LiquiditySide,
    detect_liquidity_pools,
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
    highs: list[str],
    lows: list[str],
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    if len(highs) != len(lows):
        raise ValueError("High and low lists must have equal length.")

    duration = get_timeframe_spec(timeframe).duration
    candles: list[ClosedCandle] = []

    for index, (high, low) in enumerate(zip(highs, lows, strict=True)):
        high_price = Decimal(high)
        low_price = Decimal(low)
        midpoint = (high_price + low_price) / Decimal("2")
        open_time = START + duration * index

        candles.append(
            ClosedCandle(
                broker_symbol=broker_symbol,
                timeframe=timeframe,
                open_time=open_time,
                observed_at=open_time + duration,
                open=midpoint,
                high=high_price,
                low=low_price,
                close=midpoint,
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
    *,
    allow_dual_swings: bool = False,
) -> ConfirmedSwingSet:
    policy = SwingDetectionPolicy(
        left_bars=1,
        right_bars=1,
        allow_dual_swings=allow_dual_swings,
    )
    side_order = {
        SwingKind.HIGH: 0,
        SwingKind.LOW: 1,
    }

    ordered = sorted(
        specifications,
        key=lambda value: (
            value[0],
            side_order[value[1]],
        ),
    )

    points = tuple(
        ConfirmedSwingPoint(
            index=index,
            kind=kind,
            candle=series.candles[index],
            confirmed_by_index=index + 1,
            confirmed_at=series.candles[index + 1].close_time,
        )
        for index, kind in ordered
    )

    return ConfirmedSwingSet(
        source=series,
        policy=policy,
        points=points,
    )


def high_pool_swings() -> ConfirmedSwingSet:
    series = create_series(
        highs=[
            "90",
            "100",
            "94",
            "100.20",
            "95",
            "110",
            "96",
            "97",
        ],
        lows=[
            "80",
            "85",
            "82",
            "84",
            "81",
            "83",
            "79",
            "80",
        ],
    )

    return create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
            (5, SwingKind.HIGH),
        ],
    )


def low_pool_swings() -> ConfirmedSwingSet:
    series = create_series(
        highs=[
            "110",
            "108",
            "109",
            "107",
            "108",
            "106",
            "107",
            "108",
        ],
        lows=[
            "90",
            "80",
            "88",
            "80.20",
            "87",
            "70",
            "86",
            "85",
        ],
    )

    return create_swing_set(
        series,
        [
            (1, SwingKind.LOW),
            (3, SwingKind.LOW),
            (5, SwingKind.LOW),
        ],
    )


def mixed_pool_swings() -> ConfirmedSwingSet:
    series = create_series(
        highs=[
            "90",
            "100",
            "94",
            "100.20",
            "95",
            "110",
            "96",
            "97",
        ],
        lows=[
            "80",
            "85",
            "75",
            "84",
            "75.20",
            "83",
            "70",
            "80",
        ],
    )

    return create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (2, SwingKind.LOW),
            (3, SwingKind.HIGH),
            (4, SwingKind.LOW),
        ],
    )


def test_default_policy_is_conservative() -> None:
    policy = LiquidityPoolPolicy()

    assert policy.price_tolerance == Decimal("0.50")
    assert policy.minimum_touches == 2
    assert policy.maximum_touch_gap == 100


@pytest.mark.parametrize(
    "overrides",
    [
        {"price_tolerance": "-0.01"},
        {"price_tolerance": "NaN"},
        {"minimum_touches": 1},
        {"minimum_touches": True},
        {"minimum_touches": 101},
        {"maximum_touch_gap": 0},
        {"maximum_touch_gap": True},
        {"maximum_touch_gap": 100_001},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        LiquidityPoolPolicy(**overrides)


def test_equal_highs_create_buy_side_liquidity() -> None:
    result = LiquidityPoolDetector().detect(high_pool_swings())

    assert result.count == 1
    assert len(result.buy_side) == 1
    assert result.sell_side == ()

    pool = result.buy_side[0]

    assert pool.side == LiquiditySide.BUY_SIDE
    assert pool.source_kind == SwingKind.HIGH
    assert pool.touch_count == 2
    assert pool.touch_prices == (
        Decimal("100"),
        Decimal("100.20"),
    )


def test_equal_lows_create_sell_side_liquidity() -> None:
    result = LiquidityPoolDetector().detect(low_pool_swings())

    assert result.count == 1
    assert result.buy_side == ()
    assert len(result.sell_side) == 1
    assert result.sell_side[0].side == (LiquiditySide.SELL_SIDE)
    assert result.sell_side[0].source_kind == SwingKind.LOW


def test_price_tolerance_is_inclusive() -> None:
    policy = LiquidityPoolPolicy(price_tolerance="0.20")

    result = LiquidityPoolDetector(policy).detect(high_pool_swings())

    assert result.count == 1


def test_prices_outside_tolerance_do_not_cluster() -> None:
    policy = LiquidityPoolPolicy(price_tolerance="0.19")

    result = LiquidityPoolDetector(policy).detect(high_pool_swings())

    assert result.pools == ()


def test_zero_tolerance_detects_exact_levels_only() -> None:
    series = create_series(
        highs=[
            "90",
            "100",
            "95",
            "100",
            "96",
            "100.01",
            "97",
        ],
        lows=[
            "80",
            "85",
            "82",
            "84",
            "81",
            "83",
            "80",
        ],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
            (5, SwingKind.HIGH),
        ],
    )
    policy = LiquidityPoolPolicy(price_tolerance="0")

    result = LiquidityPoolDetector(policy).detect(swings)

    assert result.count == 1
    assert result.pools[0].touch_prices == (
        Decimal("100"),
        Decimal("100"),
    )


def test_minimum_touch_requirement_is_enforced() -> None:
    policy = LiquidityPoolPolicy(minimum_touches=3)

    result = LiquidityPoolDetector(policy).detect(high_pool_swings())

    assert result.pools == ()


def test_three_matching_touches_form_one_pool() -> None:
    series = create_series(
        highs=[
            "90",
            "100",
            "95",
            "100.10",
            "96",
            "99.90",
            "97",
        ],
        lows=[
            "80",
            "85",
            "82",
            "84",
            "81",
            "83",
            "80",
        ],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
            (5, SwingKind.HIGH),
        ],
    )
    policy = LiquidityPoolPolicy(minimum_touches=3)

    result = LiquidityPoolDetector(policy).detect(swings)

    assert result.count == 1
    assert result.pools[0].touch_count == 3


def test_buy_and_sell_side_pools_remain_separate() -> None:
    result = LiquidityPoolDetector().detect(mixed_pool_swings())

    assert result.count == 2
    assert len(result.buy_side) == 1
    assert len(result.sell_side) == 1


def test_maximum_touch_gap_splits_distant_levels() -> None:
    policy = LiquidityPoolPolicy(maximum_touch_gap=1)

    result = LiquidityPoolDetector(policy).detect(high_pool_swings())

    assert result.pools == ()


def test_outlier_does_not_block_later_matching_touch() -> None:
    series = create_series(
        highs=[
            "90",
            "100",
            "95",
            "110",
            "96",
            "100.20",
            "97",
        ],
        lows=[
            "80",
            "85",
            "82",
            "84",
            "81",
            "83",
            "80",
        ],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
            (5, SwingKind.HIGH),
        ],
    )

    result = LiquidityPoolDetector().detect(swings)

    assert result.count == 1
    assert result.pools[0].touch_prices == (
        Decimal("100"),
        Decimal("100.20"),
    )


def test_pool_level_is_exact_decimal_average() -> None:
    pool = LiquidityPoolDetector().detect(high_pool_swings()).pools[0]

    assert pool.level == Decimal("100.10")


def test_pool_bounds_and_span_are_exposed() -> None:
    pool = LiquidityPoolDetector().detect(high_pool_swings()).pools[0]

    assert pool.lower_bound == Decimal("100")
    assert pool.upper_bound == Decimal("100.20")
    assert pool.price_span == Decimal("0.20")
    assert pool.contains_price("100.10") is True
    assert pool.contains_price("101") is False
    assert pool.distance_from("99") == Decimal("1.10")


def test_pool_confirmation_uses_latest_touch() -> None:
    pool = LiquidityPoolDetector().detect(high_pool_swings()).pools[0]

    assert pool.first_index == 1
    assert pool.last_index == 3
    assert pool.confirmation_index == 4
    assert pool.confirmed_at == (pool.latest_touch.confirmed_at)


def test_pool_preserves_market_context() -> None:
    series = create_series(
        highs=[
            "90",
            "100",
            "95",
            "100.20",
            "96",
        ],
        lows=[
            "80",
            "85",
            "82",
            "84",
            "81",
        ],
        timeframe=TimeframeName.H1,
        broker_symbol="XAUUSD.pro",
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
        ],
    )

    pool = LiquidityPoolDetector().detect(swings).pools[0]

    assert pool.broker_symbol == "XAUUSD.pro"
    assert pool.timeframe == TimeframeName.H1
    assert pool.stable_id == ("XAUUSD.pro:H1:BUY_SIDE:1:3")


def test_pool_set_is_ordered_by_confirmation() -> None:
    result = LiquidityPoolDetector().detect(mixed_pool_swings())

    confirmation_indexes = [pool.confirmation_index for pool in result.pools]

    assert confirmation_indexes == sorted(confirmation_indexes)


def test_empty_swing_set_returns_empty_pool_set() -> None:
    series = create_series(
        highs=["90", "91", "92"],
        lows=["80", "81", "82"],
    )
    swings = create_swing_set(series, [])

    result = LiquidityPoolDetector().detect(swings)

    assert result.count == 0
    assert result.pools == ()
    assert result.latest is None
    assert result.latest_buy_side is None
    assert result.latest_sell_side is None


def test_side_filters_and_latest_properties() -> None:
    result = LiquidityPoolDetector().detect(mixed_pool_swings())

    assert result.by_side(LiquiditySide.BUY_SIDE) == result.buy_side
    assert result.by_side(LiquiditySide.SELL_SIDE) == result.sell_side
    assert result.latest is result.pools[-1]
    assert result.latest_buy_side is result.buy_side[-1]
    assert result.latest_sell_side is result.sell_side[-1]


def test_invalid_side_filter_is_rejected() -> None:
    result = LiquidityPoolDetector().detect(mixed_pool_swings())

    with pytest.raises(ValueError):
        result.by_side("INVALID")


def test_confirmed_by_filters_pool_confirmation() -> None:
    result = LiquidityPoolDetector().detect(high_pool_swings())
    pool = result.pools[0]

    assert result.confirmed_by(pool.confirmation_index) == (pool,)
    assert result.confirmed_by(0) == ()


def test_nearest_buy_side_above_is_selected() -> None:
    series = create_series(
        highs=[
            "90",
            "100",
            "95",
            "100.20",
            "96",
            "110",
            "97",
            "110.10",
            "98",
        ],
        lows=[
            "80",
            "85",
            "82",
            "84",
            "81",
            "83",
            "80",
            "82",
            "79",
        ],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
            (5, SwingKind.HIGH),
            (7, SwingKind.HIGH),
        ],
    )

    result = LiquidityPoolDetector().detect(swings)

    nearest = result.nearest_buy_side_above("105")

    assert nearest is not None
    assert nearest.level == Decimal("110.05")


def test_nearest_sell_side_below_is_selected() -> None:
    series = create_series(
        highs=[
            "120",
            "118",
            "119",
            "117",
            "118",
            "116",
            "117",
            "115",
            "116",
        ],
        lows=[
            "110",
            "100",
            "108",
            "100.20",
            "107",
            "90",
            "106",
            "90.10",
            "105",
        ],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.LOW),
            (3, SwingKind.LOW),
            (5, SwingKind.LOW),
            (7, SwingKind.LOW),
        ],
    )

    result = LiquidityPoolDetector().detect(swings)

    nearest = result.nearest_sell_side_below("95")

    assert nearest is not None
    assert nearest.level == Decimal("90.05")


def test_nearest_lookup_returns_none_without_candidate() -> None:
    result = LiquidityPoolDetector().detect(high_pool_swings())

    assert result.nearest_buy_side_above("200") is None
    assert result.nearest_sell_side_below("50") is None


def test_invalid_swing_set_type_is_fail_safe() -> None:
    with pytest.raises(
        LiquidityDetectionError,
        match="INVALID_SWING_SET",
    ) as captured:
        LiquidityPoolDetector().detect("invalid")

    assert captured.value.reason == (LiquidityDetectionErrorReason.INVALID_SWING_SET)


def test_pool_is_immutable() -> None:
    pool = LiquidityPoolDetector().detect(high_pool_swings()).pools[0]

    with pytest.raises(FrozenInstanceError):
        pool.side = LiquiditySide.SELL_SIDE


def test_pool_set_is_immutable() -> None:
    result = LiquidityPoolDetector().detect(high_pool_swings())

    with pytest.raises(FrozenInstanceError):
        result.pools = ()


def test_manual_pool_rejects_mixed_swing_kinds() -> None:
    swings = mixed_pool_swings()
    high = swings.highs[0]
    low = swings.lows[0]

    with pytest.raises(
        ValueError,
        match="HIGH swing points",
    ):
        LiquidityPool(
            side=LiquiditySide.BUY_SIDE,
            touches=(high, low),
        )


def test_manual_pool_rejects_unordered_touches() -> None:
    swings = high_pool_swings()
    first, second = swings.highs[:2]

    with pytest.raises(
        ValueError,
        match="ordered",
    ):
        LiquidityPool(
            side=LiquiditySide.BUY_SIDE,
            touches=(second, first),
        )


def test_manual_pool_rejects_symbol_mismatch() -> None:
    first_swings = high_pool_swings()

    other_series = create_series(
        highs=["90", "100", "95"],
        lows=["80", "85", "82"],
        broker_symbol="XAUUSD",
    )
    other_swings = create_swing_set(
        other_series,
        [(1, SwingKind.HIGH)],
    )

    with pytest.raises(
        ValueError,
        match="same broker symbol",
    ):
        LiquidityPool(
            side=LiquiditySide.BUY_SIDE,
            touches=(
                first_swings.highs[0],
                other_swings.highs[0],
            ),
        )


def test_pool_set_rejects_price_span_above_policy() -> None:
    swings = high_pool_swings()
    pool = LiquidityPool(
        side=LiquiditySide.BUY_SIDE,
        touches=swings.highs[:2],
    )
    policy = LiquidityPoolPolicy(price_tolerance="0.10")

    with pytest.raises(
        ValueError,
        match="price tolerance",
    ):
        LiquidityPoolSet(
            swings=swings,
            policy=policy,
            pools=(pool,),
        )


def test_pool_set_rejects_reused_touch() -> None:
    series = create_series(
        highs=[
            "90",
            "100",
            "95",
            "100.10",
            "96",
            "100.20",
            "97",
        ],
        lows=[
            "80",
            "85",
            "82",
            "84",
            "81",
            "83",
            "80",
        ],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
            (5, SwingKind.HIGH),
        ],
    )
    first_pool = LiquidityPool(
        side=LiquiditySide.BUY_SIDE,
        touches=(
            swings.highs[0],
            swings.highs[1],
        ),
    )
    second_pool = LiquidityPool(
        side=LiquiditySide.BUY_SIDE,
        touches=(
            swings.highs[0],
            swings.highs[2],
        ),
    )

    ordered = tuple(
        sorted(
            (first_pool, second_pool),
            key=lambda pool: (
                pool.confirmation_index,
                pool.first_index,
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="multiple liquidity pools",
    ):
        LiquidityPoolSet(
            swings=swings,
            policy=LiquidityPoolPolicy(),
            pools=ordered,
        )


def test_function_api_delegates() -> None:
    result = detect_liquidity_pools(high_pool_swings())

    assert result.count == 1


def test_detector_alias_methods_delegate() -> None:
    detector = LiquidityPoolDetector()
    swings = high_pool_swings()

    assert detector.evaluate(swings) == detector.detect(swings)
    assert detector.find(swings) == detector.detect(swings)


def test_public_aliases_are_preserved() -> None:
    assert LiquidityDetector is LiquidityPoolDetector
    assert LiquidityPolicy is LiquidityPoolPolicy
    assert LiquidityPoolCollection is LiquidityPoolSet


def test_detector_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="LiquidityPoolPolicy",
    ):
        LiquidityPoolDetector(policy="invalid")
