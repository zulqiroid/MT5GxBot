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
    DealingRangeDetector,
    DealingRangeDirection,
    DealingRangePriceLocation,
    DealingRangeSet,
)
from app.strategy.ote_zones import (
    OTE,
    OptimalTradeEntryCollection,
    OptimalTradeEntryDetectionError,
    OptimalTradeEntryDetectionErrorReason,
    OptimalTradeEntryDetector,
    OptimalTradeEntryPolicy,
    OptimalTradeEntryPriceLocation,
    OptimalTradeEntryZone,
    OptimalTradeEntryZoneSet,
    OTECollection,
    OTEDetector,
    OTEDirection,
    OTELocation,
    OTEPolicy,
    OTESet,
    OTEZone,
    detect_optimal_trade_entry_zones,
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


def bullish_range_set(
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> DealingRangeSet:
    series = create_series(
        highs=["105", "100", "108", "110", "107"],
        lows=["95", "90", "96", "100", "97"],
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.LOW),
            (3, SwingKind.HIGH),
        ],
    )

    return DealingRangeDetector().detect(swings)


def bearish_range_set() -> DealingRangeSet:
    series = create_series(
        highs=["105", "110", "108", "100", "107"],
        lows=["95", "100", "96", "90", "97"],
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.LOW),
        ],
    )

    return DealingRangeDetector().detect(swings)


def multi_range_set() -> DealingRangeSet:
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
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.LOW),
            (3, SwingKind.HIGH),
            (5, SwingKind.LOW),
        ],
    )

    return DealingRangeDetector().detect(swings)


def detected_bullish_zone() -> OptimalTradeEntryZone:
    return OptimalTradeEntryDetector().detect(bullish_range_set()).zones[0]


def detected_bearish_zone() -> OptimalTradeEntryZone:
    return OptimalTradeEntryDetector().detect(bearish_range_set()).zones[0]


def test_default_policy_uses_standard_ote_band() -> None:
    policy = OptimalTradeEntryPolicy()

    assert policy.shallow_retracement == Decimal("0.62")
    assert policy.deep_retracement == Decimal("0.79")
    assert policy.retracement_span == Decimal("0.17")


@pytest.mark.parametrize(
    "overrides",
    [
        {"shallow_retracement": "-0.01"},
        {"shallow_retracement": "0.49"},
        {"shallow_retracement": "1.01"},
        {"shallow_retracement": "NaN"},
        {"shallow_retracement": True},
        {"deep_retracement": "-0.01"},
        {"deep_retracement": "1.01"},
        {"deep_retracement": "Infinity"},
        {
            "shallow_retracement": "0.79",
            "deep_retracement": "0.79",
        },
        {
            "shallow_retracement": "0.80",
            "deep_retracement": "0.79",
        },
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        OptimalTradeEntryPolicy(**overrides)


def test_bullish_ote_zone_is_detected() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())

    assert result.count == 1
    assert len(result.bullish) == 1
    assert result.bearish == ()

    zone = result.zones[0]

    assert zone.direction == (DealingRangeDirection.BULLISH)
    assert zone.is_bullish is True
    assert zone.is_bearish is False


def test_bearish_ote_zone_is_detected() -> None:
    result = OptimalTradeEntryDetector().detect(bearish_range_set())

    assert result.count == 1
    assert result.bullish == ()
    assert len(result.bearish) == 1

    zone = result.zones[0]

    assert zone.direction == (DealingRangeDirection.BEARISH)
    assert zone.is_bearish is True


def test_bullish_ote_prices_are_exact() -> None:
    zone = detected_bullish_zone()

    assert zone.shallow_price == Decimal("97.60")
    assert zone.deep_price == Decimal("94.20")
    assert zone.lower_bound == Decimal("94.20")
    assert zone.upper_bound == Decimal("97.60")
    assert zone.size == Decimal("3.40")


def test_bearish_ote_prices_are_exact() -> None:
    zone = detected_bearish_zone()

    assert zone.shallow_price == Decimal("102.40")
    assert zone.deep_price == Decimal("105.80")
    assert zone.lower_bound == Decimal("102.40")
    assert zone.upper_bound == Decimal("105.80")
    assert zone.size == Decimal("3.40")


def test_midpoint_and_entry_price_are_exact() -> None:
    bullish = detected_bullish_zone()
    bearish = detected_bearish_zone()

    assert bullish.midpoint == Decimal("95.90")
    assert bullish.entry_price == Decimal("95.90")
    assert bearish.midpoint == Decimal("104.10")
    assert bearish.entry_price == Decimal("104.10")
    assert bullish.midpoint_retracement == Decimal("0.705")


def test_bullish_zone_remains_in_discount() -> None:
    zone = detected_bullish_zone()

    assert zone.dealing_range_location == (DealingRangePriceLocation.DISCOUNT)
    assert zone.upper_bound < zone.dealing_range.equilibrium


def test_bearish_zone_remains_in_premium() -> None:
    zone = detected_bearish_zone()

    assert zone.dealing_range_location == (DealingRangePriceLocation.PREMIUM)
    assert zone.lower_bound > zone.dealing_range.equilibrium


def test_zone_boundaries_are_included() -> None:
    zone = detected_bullish_zone()

    assert zone.contains_price("94.20") is True
    assert zone.contains_price("95.90") is True
    assert zone.contains_price("97.60") is True
    assert zone.contains_price("97.61") is False


def test_price_location_is_deterministic() -> None:
    zone = detected_bullish_zone()

    assert zone.classify_price("94.19") == (OptimalTradeEntryPriceLocation.BELOW_ZONE)
    assert zone.classify_price("94.20") == (OptimalTradeEntryPriceLocation.IN_ZONE)
    assert zone.classify_price("97.60") == (OptimalTradeEntryPriceLocation.IN_ZONE)
    assert zone.classify_price("97.61") == (OptimalTradeEntryPriceLocation.ABOVE_ZONE)


def test_bullish_retracement_is_measured_from_high() -> None:
    zone = detected_bullish_zone()

    assert zone.retracement_for_price(zone.shallow_price) == Decimal("0.62")
    assert zone.retracement_for_price(zone.deep_price) == Decimal("0.79")


def test_bearish_retracement_is_measured_from_low() -> None:
    zone = detected_bearish_zone()

    assert zone.retracement_for_price(zone.shallow_price) == Decimal("0.62")
    assert zone.retracement_for_price(zone.deep_price) == Decimal("0.79")


def test_normalized_zone_position_is_exact() -> None:
    zone = detected_bullish_zone()

    assert zone.normalized_zone_position(zone.lower_bound) == Decimal("0")
    assert zone.normalized_zone_position(zone.midpoint) == Decimal("0.5")
    assert zone.normalized_zone_position(zone.upper_bound) == Decimal("1")


def test_distance_from_zone_is_available() -> None:
    zone = detected_bullish_zone()

    assert zone.distance_from("90") == Decimal("4.20")
    assert zone.distance_from("95") == Decimal("0")
    assert zone.distance_from("100") == Decimal("2.40")


def test_zone_uses_dealing_range_confirmation() -> None:
    zone = detected_bullish_zone()

    assert zone.confirmation_index == 4
    assert zone.confirmed_at == (zone.dealing_range.confirmed_at)


def test_zone_preserves_market_context() -> None:
    result = OptimalTradeEntryDetector().detect(
        bullish_range_set(
            timeframe=TimeframeName.H1,
            broker_symbol="XAUUSD.pro",
        )
    )
    zone = result.zones[0]

    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1
    assert result.source is result.dealing_ranges.source
    assert zone.broker_symbol == "XAUUSD.pro"
    assert zone.timeframe == TimeframeName.H1


def test_stable_id_is_deterministic() -> None:
    zone = detected_bullish_zone()

    assert zone.stable_id == ("XAUUSDm:M5:BULLISH:1:3:OTE:0.62:0.79")


def test_custom_retracement_band_is_supported() -> None:
    policy = OptimalTradeEntryPolicy(
        shallow_retracement="0.65",
        deep_retracement="0.80",
    )

    zone = OptimalTradeEntryDetector(policy).detect(bullish_range_set()).zones[0]

    assert zone.shallow_price == Decimal("97.00")
    assert zone.deep_price == Decimal("94.00")
    assert zone.size == Decimal("3.00")


def test_multiple_zones_are_ordered() -> None:
    result = OptimalTradeEntryDetector().detect(multi_range_set())

    assert result.count == 2
    assert [zone.confirmation_index for zone in result.zones] == [4, 6]
    assert result.latest is result.zones[-1]
    assert result.latest_bullish is result.bullish[-1]
    assert result.latest_bearish is result.bearish[-1]


def test_direction_filters_are_available() -> None:
    result = OptimalTradeEntryDetector().detect(multi_range_set())

    assert result.by_direction(DealingRangeDirection.BULLISH) == result.bullish
    assert result.by_direction(DealingRangeDirection.BEARISH) == result.bearish


def test_invalid_direction_filter_is_rejected() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())

    with pytest.raises(ValueError):
        result.by_direction("INVALID")


def test_confirmation_lookup_is_available() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())
    zone = result.zones[0]

    assert result.confirmed_at_index(4) == (zone,)
    assert result.confirmed_at_index(3) == ()


def test_zone_is_not_available_before_confirmation() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())
    zone = result.zones[0]

    assert result.available_at(3) == ()
    assert result.available_at(4) == (zone,)
    assert result.available_at(100) == (zone,)


def test_containing_zone_lookup_is_available() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())
    zone = result.zones[0]

    assert result.containing("95") == (zone,)
    assert result.containing("100") == ()


def test_latest_containing_zone_is_available() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())

    assert result.latest_containing("95") is (result.zones[0])
    assert result.latest_containing("100") is None


def test_dealing_range_lookup_is_available() -> None:
    ranges = multi_range_set()
    result = OptimalTradeEntryDetector().detect(ranges)

    assert result.for_dealing_range(ranges.ranges[0]) is result.zones[0]
    assert result.for_dealing_range(ranges.ranges[1]) is result.zones[1]


def test_dealing_range_lookup_requires_type() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())

    with pytest.raises(ValueError):
        result.for_dealing_range("invalid")


def test_nearest_bullish_zone_below_is_selected() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())

    nearest = result.nearest_bullish_below("100")

    assert nearest is result.zones[0]


def test_nearest_bearish_zone_above_is_selected() -> None:
    result = OptimalTradeEntryDetector().detect(bearish_range_set())

    nearest = result.nearest_bearish_above("100")

    assert nearest is result.zones[0]


def test_nearest_lookup_returns_none_without_candidate() -> None:
    bullish = OptimalTradeEntryDetector().detect(bullish_range_set())
    bearish = OptimalTradeEntryDetector().detect(bearish_range_set())

    assert bullish.nearest_bullish_below("90") is None
    assert bearish.nearest_bearish_above("110") is None


def test_empty_dealing_range_set_returns_empty_result() -> None:
    series = create_series(
        highs=["105", "106", "107"],
        lows=["95", "96", "97"],
    )
    swings = create_swing_set(series, [])
    ranges = DealingRangeDetector().detect(swings)

    result = OptimalTradeEntryDetector().detect(ranges)

    assert result.count == 0
    assert result.zones == ()
    assert result.latest is None
    assert result.latest_bullish is None
    assert result.latest_bearish is None


def test_invalid_dealing_range_set_is_fail_safe() -> None:
    with pytest.raises(
        OptimalTradeEntryDetectionError,
        match="INVALID_DEALING_RANGE_SET",
    ) as captured:
        OptimalTradeEntryDetector().detect("invalid")

    assert captured.value.reason == (
        OptimalTradeEntryDetectionErrorReason.INVALID_DEALING_RANGE_SET
    )


def test_detector_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="OptimalTradeEntryPolicy",
    ):
        OptimalTradeEntryDetector(policy="invalid")


def test_zone_requires_dealing_range_type() -> None:
    with pytest.raises(
        ValueError,
        match="DealingRange",
    ):
        OptimalTradeEntryZone(
            dealing_range="invalid",
            shallow_retracement=Decimal("0.62"),
            deep_retracement=Decimal("0.79"),
        )


@pytest.mark.parametrize(
    ("shallow", "deep"),
    [
        ("0.49", "0.79"),
        ("0.62", "0.62"),
        ("0.80", "0.79"),
        ("0.62", "1.01"),
    ],
)
def test_zone_rejects_invalid_retracement_band(
    shallow: str,
    deep: str,
) -> None:
    dealing_range = bullish_range_set().ranges[0]

    with pytest.raises(ValueError):
        OptimalTradeEntryZone(
            dealing_range=dealing_range,
            shallow_retracement=Decimal(shallow),
            deep_retracement=Decimal(deep),
        )


def test_manual_set_rejects_policy_mismatch() -> None:
    ranges = bullish_range_set()
    zone = OptimalTradeEntryZone(
        dealing_range=ranges.ranges[0],
        shallow_retracement=Decimal("0.65"),
        deep_retracement=Decimal("0.80"),
    )

    with pytest.raises(
        ValueError,
        match="configured policy",
    ):
        OptimalTradeEntryZoneSet(
            dealing_ranges=ranges,
            policy=OptimalTradeEntryPolicy(),
            zones=(zone,),
        )


def test_manual_set_requires_zone_for_every_range() -> None:
    ranges = multi_range_set()
    policy = OptimalTradeEntryPolicy()
    first_zone = OptimalTradeEntryZone(
        dealing_range=ranges.ranges[0],
        shallow_retracement=(policy.shallow_retracement),
        deep_retracement=(policy.deep_retracement),
    )

    with pytest.raises(
        ValueError,
        match="exactly one OTE zone",
    ):
        OptimalTradeEntryZoneSet(
            dealing_ranges=ranges,
            policy=policy,
            zones=(first_zone,),
        )


def test_manual_set_rejects_foreign_range() -> None:
    ranges = bullish_range_set()
    foreign_ranges = bullish_range_set(broker_symbol="XAUUSD")
    policy = OptimalTradeEntryPolicy()
    foreign_zone = OptimalTradeEntryZone(
        dealing_range=foreign_ranges.ranges[0],
        shallow_retracement=(policy.shallow_retracement),
        deep_retracement=(policy.deep_retracement),
    )

    with pytest.raises(
        ValueError,
        match="source dealing-range set",
    ):
        OptimalTradeEntryZoneSet(
            dealing_ranges=ranges,
            policy=policy,
            zones=(foreign_zone,),
        )


def test_manual_set_rejects_out_of_order_zones() -> None:
    result = OptimalTradeEntryDetector().detect(multi_range_set())

    with pytest.raises(
        ValueError,
        match="ordered",
    ):
        OptimalTradeEntryZoneSet(
            dealing_ranges=result.dealing_ranges,
            policy=result.policy,
            zones=tuple(reversed(result.zones)),
        )


def test_manual_set_rejects_duplicate_zones() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())
    zone = result.zones[0]

    with pytest.raises(
        ValueError,
        match="Duplicate",
    ):
        OptimalTradeEntryZoneSet(
            dealing_ranges=result.dealing_ranges,
            policy=result.policy,
            zones=(zone, zone),
        )


def test_zone_is_immutable() -> None:
    zone = detected_bullish_zone()

    with pytest.raises(FrozenInstanceError):
        zone.shallow_retracement = Decimal("0.65")


def test_zone_set_is_immutable() -> None:
    result = OptimalTradeEntryDetector().detect(bullish_range_set())

    with pytest.raises(FrozenInstanceError):
        result.zones = ()


def test_function_api_delegates() -> None:
    result = detect_optimal_trade_entry_zones(bullish_range_set())

    assert result.count == 1


def test_detector_alias_methods_delegate() -> None:
    detector = OptimalTradeEntryDetector()
    ranges = bullish_range_set()

    assert detector.evaluate(ranges) == detector.detect(ranges)
    assert detector.find(ranges) == detector.detect(ranges)


def test_public_aliases_are_preserved() -> None:
    assert OTE is OptimalTradeEntryZone
    assert OTEZone is OptimalTradeEntryZone
    assert OTESet is OptimalTradeEntryZoneSet
    assert OTECollection is OptimalTradeEntryZoneSet
    assert OptimalTradeEntryCollection is OptimalTradeEntryZoneSet
    assert OTEDetector is OptimalTradeEntryDetector
    assert OTEPolicy is OptimalTradeEntryPolicy
    assert OTELocation is OptimalTradeEntryPriceLocation
    assert OTEDirection is DealingRangeDirection
