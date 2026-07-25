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
from app.strategy.dealing_ranges import (
    DealingRange,
    DealingRangeCollection,
    DealingRangeDetectionError,
    DealingRangeDetectionErrorReason,
    DealingRangeDetector,
    DealingRangeDirection,
    DealingRangeFinder,
    DealingRangePolicy,
    DealingRangePriceLocation,
    DealingRangeSet,
    RangeDirection,
    RangeLocation,
    RangePolicy,
    detect_dealing_ranges,
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


def bullish_swings(
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ConfirmedSwingSet:
    series = create_series(
        highs=["105", "100", "108", "110", "107"],
        lows=["95", "90", "96", "100", "97"],
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )

    return create_swing_set(
        series,
        [
            (1, SwingKind.LOW),
            (3, SwingKind.HIGH),
        ],
    )


def bearish_swings() -> ConfirmedSwingSet:
    series = create_series(
        highs=["105", "110", "108", "100", "107"],
        lows=["95", "100", "96", "90", "97"],
    )

    return create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.LOW),
        ],
    )


def multi_range_swings() -> ConfirmedSwingSet:
    series = create_series(
        highs=[
            "105",
            "100",
            "108",
            "110",
            "107",
            "104",
            "106",
        ],
        lows=[
            "95",
            "90",
            "96",
            "100",
            "97",
            "92",
            "96",
        ],
    )

    return create_swing_set(
        series,
        [
            (1, SwingKind.LOW),
            (3, SwingKind.HIGH),
            (5, SwingKind.LOW),
        ],
    )


def detected_bullish_range() -> DealingRange:
    return DealingRangeDetector().detect(bullish_swings()).ranges[0]


def test_default_policy_is_conservative() -> None:
    policy = DealingRangePolicy()

    assert policy.minimum_range_size == Decimal("0")
    assert policy.maximum_anchor_gap == 100


@pytest.mark.parametrize(
    "overrides",
    [
        {"minimum_range_size": "-0.01"},
        {"minimum_range_size": "NaN"},
        {"minimum_range_size": "Infinity"},
        {"minimum_range_size": True},
        {"maximum_anchor_gap": 0},
        {"maximum_anchor_gap": True},
        {"maximum_anchor_gap": 100_001},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        DealingRangePolicy(**overrides)


def test_bullish_dealing_range_is_detected() -> None:
    result = DealingRangeDetector().detect(bullish_swings())

    assert result.count == 1
    assert len(result.bullish) == 1
    assert result.bearish == ()

    dealing_range = result.ranges[0]

    assert dealing_range.direction == (DealingRangeDirection.BULLISH)
    assert dealing_range.is_bullish is True
    assert dealing_range.is_bearish is False


def test_bearish_dealing_range_is_detected() -> None:
    result = DealingRangeDetector().detect(bearish_swings())

    assert result.count == 1
    assert result.bullish == ()
    assert len(result.bearish) == 1
    assert result.ranges[0].direction == (DealingRangeDirection.BEARISH)


def test_same_kind_consecutive_swings_are_ignored() -> None:
    series = create_series(
        highs=["105", "110", "108", "112", "107"],
        lows=["95", "100", "96", "101", "97"],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
        ],
    )

    result = DealingRangeDetector().detect(swings)

    assert result.ranges == ()


def test_only_consecutive_opposite_swings_form_ranges() -> None:
    result = DealingRangeDetector().detect(multi_range_swings())

    assert result.count == 2
    assert result.ranges[0].first_index == 1
    assert result.ranges[0].second_index == 3
    assert result.ranges[1].first_index == 3
    assert result.ranges[1].second_index == 5


def test_exact_minimum_range_size_is_rejected() -> None:
    policy = DealingRangePolicy(minimum_range_size="20")

    result = DealingRangeDetector(policy).detect(bullish_swings())

    assert result.ranges == ()


def test_range_above_minimum_size_is_detected() -> None:
    policy = DealingRangePolicy(minimum_range_size="19.99")

    result = DealingRangeDetector(policy).detect(bullish_swings())

    assert result.count == 1


def test_exact_maximum_anchor_gap_is_allowed() -> None:
    policy = DealingRangePolicy(maximum_anchor_gap=2)

    result = DealingRangeDetector(policy).detect(bullish_swings())

    assert result.count == 1


def test_anchor_gap_above_maximum_is_rejected() -> None:
    policy = DealingRangePolicy(maximum_anchor_gap=1)

    result = DealingRangeDetector(policy).detect(bullish_swings())

    assert result.ranges == ()


def test_range_metrics_are_exact() -> None:
    dealing_range = detected_bullish_range()

    assert dealing_range.origin_price == Decimal("90")
    assert dealing_range.terminal_price == Decimal("110")
    assert dealing_range.lower_bound == Decimal("90")
    assert dealing_range.upper_bound == Decimal("110")
    assert dealing_range.size == Decimal("20")
    assert dealing_range.equilibrium == Decimal("100")
    assert dealing_range.anchor_gap == 2


def test_premium_and_discount_bounds_are_exact() -> None:
    dealing_range = detected_bullish_range()

    assert dealing_range.discount_lower_bound == Decimal("90")
    assert dealing_range.discount_upper_bound == Decimal("100")
    assert dealing_range.premium_lower_bound == Decimal("100")
    assert dealing_range.premium_upper_bound == Decimal("110")


def test_price_classification_includes_boundaries() -> None:
    dealing_range = detected_bullish_range()

    assert dealing_range.classify_price("90") == (DealingRangePriceLocation.DISCOUNT)
    assert dealing_range.classify_price("99.99") == (DealingRangePriceLocation.DISCOUNT)
    assert dealing_range.classify_price("100") == (DealingRangePriceLocation.EQUILIBRIUM)
    assert dealing_range.classify_price("100.01") == (DealingRangePriceLocation.PREMIUM)
    assert dealing_range.classify_price("110") == (DealingRangePriceLocation.PREMIUM)


def test_price_outside_range_is_classified() -> None:
    dealing_range = detected_bullish_range()

    assert dealing_range.classify_price("89.99") == (DealingRangePriceLocation.BELOW_RANGE)
    assert dealing_range.classify_price("110.01") == (DealingRangePriceLocation.ABOVE_RANGE)


def test_normalized_position_is_exact() -> None:
    dealing_range = detected_bullish_range()

    assert dealing_range.normalized_position("90") == Decimal("0")
    assert dealing_range.normalized_position("100") == Decimal("0.5")
    assert dealing_range.normalized_position("110") == Decimal("1")


def test_contains_price_and_distance_are_available() -> None:
    dealing_range = detected_bullish_range()

    assert dealing_range.contains_price("90") is True
    assert dealing_range.contains_price("100") is True
    assert dealing_range.contains_price("110") is True
    assert dealing_range.contains_price("111") is False
    assert dealing_range.distance_from("80") == Decimal("10")
    assert dealing_range.distance_from("100") == Decimal("0")
    assert dealing_range.distance_from("120") == Decimal("10")


def test_confirmation_uses_second_confirmed_swing() -> None:
    dealing_range = detected_bullish_range()

    assert dealing_range.first_index == 1
    assert dealing_range.second_index == 3
    assert dealing_range.confirmation_index == 4
    assert dealing_range.confirmed_at == (dealing_range.second_anchor.confirmed_at)


def test_range_preserves_market_context() -> None:
    result = DealingRangeDetector().detect(
        bullish_swings(
            timeframe=TimeframeName.H1,
            broker_symbol="XAUUSD.pro",
        )
    )
    dealing_range = result.ranges[0]

    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1
    assert result.source is result.swings.source
    assert dealing_range.broker_symbol == "XAUUSD.pro"
    assert dealing_range.timeframe == TimeframeName.H1


def test_stable_id_is_deterministic() -> None:
    dealing_range = detected_bullish_range()

    assert dealing_range.stable_id == ("XAUUSDm:M5:BULLISH:1:3")


def test_multiple_ranges_are_ordered() -> None:
    result = DealingRangeDetector().detect(multi_range_swings())

    assert [dealing_range.confirmation_index for dealing_range in result.ranges] == [4, 6]
    assert result.latest is result.ranges[-1]
    assert result.latest_bullish is result.bullish[-1]
    assert result.latest_bearish is result.bearish[-1]


def test_direction_filters_are_available() -> None:
    result = DealingRangeDetector().detect(multi_range_swings())

    assert result.by_direction(DealingRangeDirection.BULLISH) == result.bullish
    assert result.by_direction(DealingRangeDirection.BEARISH) == result.bearish


def test_invalid_direction_filter_is_rejected() -> None:
    result = DealingRangeDetector().detect(bullish_swings())

    with pytest.raises(ValueError):
        result.by_direction("INVALID")


def test_confirmation_lookup_is_available() -> None:
    result = DealingRangeDetector().detect(bullish_swings())
    dealing_range = result.ranges[0]

    assert result.confirmed_at_index(4) == (dealing_range,)
    assert result.confirmed_at_index(3) == ()


def test_range_is_not_available_before_confirmation() -> None:
    result = DealingRangeDetector().detect(bullish_swings())
    dealing_range = result.ranges[0]

    assert result.available_at(3) == ()
    assert result.available_at(4) == (dealing_range,)
    assert result.available_at(100) == (dealing_range,)


def test_containing_ranges_are_available() -> None:
    result = DealingRangeDetector().detect(multi_range_swings())

    containing = result.containing("100")

    assert containing == result.ranges


def test_latest_containing_range_is_selected() -> None:
    result = DealingRangeDetector().detect(multi_range_swings())

    assert result.latest_containing("100") is (result.ranges[-1])
    assert result.latest_containing("200") is None


def test_anchor_pair_lookup_is_available() -> None:
    result = DealingRangeDetector().detect(multi_range_swings())

    assert result.for_anchor_pair(1, 3) is (result.ranges[0])
    assert result.for_anchor_pair(3, 5) is (result.ranges[1])
    assert result.for_anchor_pair(1, 5) is None


def test_empty_swing_set_returns_empty_result() -> None:
    series = create_series(
        highs=["105", "106", "107"],
        lows=["95", "96", "97"],
    )
    swings = create_swing_set(series, [])

    result = DealingRangeDetector().detect(swings)

    assert result.count == 0
    assert result.ranges == ()
    assert result.latest is None
    assert result.latest_bullish is None
    assert result.latest_bearish is None


def test_invalid_swing_set_type_is_fail_safe() -> None:
    with pytest.raises(
        DealingRangeDetectionError,
        match="INVALID_SWING_SET",
    ) as captured:
        DealingRangeDetector().detect("invalid")

    assert captured.value.reason == (DealingRangeDetectionErrorReason.INVALID_SWING_SET)


def test_detector_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="DealingRangePolicy",
    ):
        DealingRangeDetector(policy="invalid")


def test_manual_range_rejects_same_kind_anchors() -> None:
    series = create_series(
        highs=["105", "110", "108", "112", "107"],
        lows=["95", "100", "96", "101", "97"],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
        ],
    )

    with pytest.raises(
        ValueError,
        match="opposite swing kinds",
    ):
        DealingRange(
            direction=DealingRangeDirection.BEARISH,
            first_anchor=swings.points[0],
            second_anchor=swings.points[1],
        )


def test_manual_range_rejects_unordered_anchors() -> None:
    swings = bullish_swings()

    with pytest.raises(
        ValueError,
        match="precede",
    ):
        DealingRange(
            direction=DealingRangeDirection.BEARISH,
            first_anchor=swings.points[1],
            second_anchor=swings.points[0],
        )


def test_manual_range_rejects_symbol_mismatch() -> None:
    first = bullish_swings()
    second = bullish_swings(broker_symbol="XAUUSD")

    with pytest.raises(
        ValueError,
        match="same broker symbol",
    ):
        DealingRange(
            direction=DealingRangeDirection.BULLISH,
            first_anchor=first.points[0],
            second_anchor=second.points[1],
        )


def test_manual_range_rejects_wrong_direction() -> None:
    swings = bullish_swings()

    with pytest.raises(
        ValueError,
        match="anchor sequence",
    ):
        DealingRange(
            direction=DealingRangeDirection.BEARISH,
            first_anchor=swings.points[0],
            second_anchor=swings.points[1],
        )


def test_manual_set_rejects_foreign_anchors() -> None:
    swings = bullish_swings()
    foreign = bullish_swings(broker_symbol="XAUUSD")
    foreign_range = DealingRange(
        direction=DealingRangeDirection.BULLISH,
        first_anchor=foreign.points[0],
        second_anchor=foreign.points[1],
    )

    with pytest.raises(
        ValueError,
        match="source swing set",
    ):
        DealingRangeSet(
            swings=swings,
            policy=DealingRangePolicy(),
            ranges=(foreign_range,),
        )


def test_manual_set_rejects_nonconsecutive_anchors() -> None:
    series = create_series(
        highs=[
            "105",
            "100",
            "108",
            "110",
            "107",
            "104",
            "106",
            "112",
            "108",
        ],
        lows=[
            "95",
            "90",
            "96",
            "100",
            "97",
            "92",
            "96",
            "102",
            "98",
        ],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.LOW),
            (3, SwingKind.HIGH),
            (5, SwingKind.LOW),
            (7, SwingKind.HIGH),
        ],
    )
    nonconsecutive = DealingRange(
        direction=DealingRangeDirection.BULLISH,
        first_anchor=swings.points[0],
        second_anchor=swings.points[3],
    )

    with pytest.raises(
        ValueError,
        match="consecutive",
    ):
        DealingRangeSet(
            swings=swings,
            policy=DealingRangePolicy(),
            ranges=(nonconsecutive,),
        )


def test_manual_set_rejects_minimum_size_violation() -> None:
    swings = bullish_swings()
    dealing_range = DealingRange(
        direction=DealingRangeDirection.BULLISH,
        first_anchor=swings.points[0],
        second_anchor=swings.points[1],
    )

    with pytest.raises(
        ValueError,
        match="minimum size",
    ):
        DealingRangeSet(
            swings=swings,
            policy=DealingRangePolicy(minimum_range_size="20"),
            ranges=(dealing_range,),
        )


def test_manual_set_rejects_duplicate_ranges() -> None:
    result = DealingRangeDetector().detect(bullish_swings())
    dealing_range = result.ranges[0]

    with pytest.raises(
        ValueError,
        match="Duplicate",
    ):
        DealingRangeSet(
            swings=result.swings,
            policy=result.policy,
            ranges=(dealing_range, dealing_range),
        )


def test_range_is_immutable() -> None:
    dealing_range = detected_bullish_range()

    with pytest.raises(FrozenInstanceError):
        dealing_range.direction = DealingRangeDirection.BEARISH


def test_set_is_immutable() -> None:
    result = DealingRangeDetector().detect(bullish_swings())

    with pytest.raises(FrozenInstanceError):
        result.ranges = ()


def test_function_api_delegates() -> None:
    result = detect_dealing_ranges(bullish_swings())

    assert result.count == 1


def test_detector_alias_methods_delegate() -> None:
    detector = DealingRangeDetector()
    swings = bullish_swings()

    assert detector.evaluate(swings) == detector.detect(swings)
    assert detector.find(swings) == detector.detect(swings)


def test_public_aliases_are_preserved() -> None:
    assert DealingRangeCollection is DealingRangeSet
    assert DealingRangeFinder is DealingRangeDetector
    assert RangeDirection is DealingRangeDirection
    assert RangeLocation is DealingRangePriceLocation
    assert RangePolicy is DealingRangePolicy
