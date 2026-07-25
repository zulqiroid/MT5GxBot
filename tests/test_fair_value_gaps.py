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
from app.strategy.fair_value_gaps import (
    FVG,
    FairValueGap,
    FairValueGapDetectionError,
    FairValueGapDetectionErrorReason,
    FairValueGapDetector,
    FairValueGapDirection,
    FairValueGapPolicy,
    FairValueGapSet,
    FVGDetector,
    FVGDirection,
    FVGPolicy,
    FVGSet,
    detect_fair_value_gaps,
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


def bullish_series(
    *,
    third_low: str = "106",
    middle_open: str = "103",
    middle_close: str = "112",
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    return create_series(
        [
            ("100", "105", "99", "102"),
            (
                middle_open,
                "113",
                "102",
                middle_close,
            ),
            ("111", "116", third_low, "114"),
        ],
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )


def bearish_series(
    *,
    third_high: str = "104",
) -> ClosedCandleSeries:
    return create_series(
        [
            ("110", "111", "105", "108"),
            ("107", "108", "97", "98"),
            ("99", third_high, "95", "96"),
        ]
    )


def detected_bullish_gap() -> FairValueGap:
    return FairValueGapDetector().detect(bullish_series()).gaps[0]


def detected_bearish_gap() -> FairValueGap:
    return FairValueGapDetector().detect(bearish_series()).gaps[0]


def test_default_policy_requires_displacement_confirmation() -> None:
    policy = FairValueGapPolicy()

    assert policy.minimum_gap_size == Decimal("0")
    assert policy.require_middle_direction is True
    assert policy.minimum_middle_body_ratio == Decimal("0.50")


@pytest.mark.parametrize(
    "overrides",
    [
        {"minimum_gap_size": "-0.01"},
        {"minimum_gap_size": "NaN"},
        {"minimum_gap_size": "Infinity"},
        {"require_middle_direction": 1},
        {"minimum_middle_body_ratio": "-0.01"},
        {"minimum_middle_body_ratio": "1.01"},
        {"minimum_middle_body_ratio": "NaN"},
        {"minimum_middle_body_ratio": True},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        FairValueGapPolicy(**overrides)


def test_bullish_fvg_is_detected() -> None:
    result = FairValueGapDetector().detect(bullish_series())

    assert result.count == 1
    assert len(result.bullish) == 1
    assert result.bearish == ()

    gap = result.bullish[0]

    assert gap.direction == (FairValueGapDirection.BULLISH)
    assert gap.is_bullish is True
    assert gap.is_bearish is False


def test_bearish_fvg_is_detected() -> None:
    result = FairValueGapDetector().detect(bearish_series())

    assert result.count == 1
    assert result.bullish == ()
    assert len(result.bearish) == 1
    assert result.bearish[0].direction == (FairValueGapDirection.BEARISH)


def test_exact_boundary_touch_is_not_an_fvg() -> None:
    result = FairValueGapDetector().detect(bullish_series(third_low="105"))

    assert result.gaps == ()


def test_exact_minimum_gap_size_is_rejected() -> None:
    policy = FairValueGapPolicy(minimum_gap_size="1")

    result = FairValueGapDetector(policy).detect(bullish_series())

    assert result.gaps == ()


def test_gap_above_minimum_size_is_detected() -> None:
    policy = FairValueGapPolicy(minimum_gap_size="0.99")

    result = FairValueGapDetector(policy).detect(bullish_series())

    assert result.count == 1


def test_wrong_middle_direction_is_blocked() -> None:
    result = FairValueGapDetector().detect(
        bullish_series(
            middle_open="112",
            middle_close="103",
        )
    )

    assert result.gaps == ()


def test_middle_direction_check_can_be_disabled() -> None:
    policy = FairValueGapPolicy(require_middle_direction=False)

    result = FairValueGapDetector(policy).detect(
        bullish_series(
            middle_open="112",
            middle_close="103",
        )
    )

    assert result.count == 1


def test_low_middle_body_ratio_is_blocked() -> None:
    result = FairValueGapDetector().detect(
        bullish_series(
            middle_open="103",
            middle_close="104",
        )
    )

    assert result.gaps == ()


def test_exact_middle_body_ratio_is_allowed() -> None:
    result = FairValueGapDetector().detect(
        bullish_series(
            middle_open="103",
            middle_close="108.5",
        )
    )

    assert result.count == 1
    assert result.gaps[0].middle_body_ratio == Decimal("0.5")


def test_first_and_third_candle_direction_is_irrelevant() -> None:
    series = create_series(
        [
            ("104", "105", "99", "100"),
            ("103", "113", "102", "112"),
            ("115", "116", "106", "111"),
        ]
    )

    result = FairValueGapDetector().detect(series)

    assert result.count == 1


def test_confirmation_uses_third_closed_candle() -> None:
    gap = detected_bullish_gap()

    assert gap.first_index == 0
    assert gap.middle_index == 1
    assert gap.confirmation_index == 2
    assert gap.confirmed_at == (gap.third_candle.close_time)


def test_gap_preserves_market_context() -> None:
    result = FairValueGapDetector().detect(
        bullish_series(
            timeframe=TimeframeName.H1,
            broker_symbol="XAUUSD.pro",
        )
    )
    gap = result.gaps[0]

    assert gap.broker_symbol == "XAUUSD.pro"
    assert gap.timeframe == TimeframeName.H1
    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1


def test_gap_bounds_size_and_midpoint_are_exact() -> None:
    bullish = detected_bullish_gap()
    bearish = detected_bearish_gap()

    assert bullish.lower_bound == Decimal("105")
    assert bullish.upper_bound == Decimal("106")
    assert bullish.size == Decimal("1")
    assert bullish.midpoint == Decimal("105.5")

    assert bearish.lower_bound == Decimal("104")
    assert bearish.upper_bound == Decimal("105")
    assert bearish.size == Decimal("1")
    assert bearish.midpoint == Decimal("104.5")


def test_stable_id_is_deterministic() -> None:
    gap = detected_bullish_gap()

    assert gap.stable_id == ("XAUUSDm:M5:BULLISH:0:2")


def test_contains_price_includes_zone_boundaries() -> None:
    gap = detected_bullish_gap()

    assert gap.contains_price("105") is True
    assert gap.contains_price("105.5") is True
    assert gap.contains_price("106") is True
    assert gap.contains_price("106.01") is False


def test_distance_from_zone_is_deterministic() -> None:
    gap = detected_bullish_gap()

    assert gap.distance_from("104") == Decimal("1")
    assert gap.distance_from("105.5") == Decimal("0")
    assert gap.distance_from("107") == Decimal("1")


def test_multiple_gaps_are_ordered() -> None:
    series = create_series(
        [
            ("100", "105", "99", "102"),
            ("103", "113", "102", "112"),
            ("111", "116", "106", "114"),
            ("115", "125", "114", "124"),
            ("123", "128", "117", "126"),
            ("127", "132", "126", "130"),
        ]
    )
    policy = FairValueGapPolicy(minimum_middle_body_ratio="0")

    result = FairValueGapDetector(policy).detect(series)

    indexes = [gap.confirmation_index for gap in result.gaps]

    assert result.count >= 2
    assert indexes == sorted(indexes)
    assert result.latest is result.gaps[-1]


def test_direction_filters_and_confirmation_lookup() -> None:
    bullish_result = FairValueGapDetector().detect(bullish_series())
    bearish_result = FairValueGapDetector().detect(bearish_series())

    bullish = bullish_result.gaps[0]
    bearish = bearish_result.gaps[0]

    assert bullish_result.by_direction(FairValueGapDirection.BULLISH) == (bullish,)
    assert bullish_result.by_direction(FairValueGapDirection.BEARISH) == ()
    assert bullish_result.confirmed_at_index(2) == (bullish,)
    assert bullish_result.confirmed_at_index(1) == ()
    assert bearish_result.latest_bearish is bearish


def test_no_gap_returns_empty_valid_set() -> None:
    series = create_series(
        [
            ("100", "105", "95", "102"),
            ("102", "106", "96", "104"),
            ("104", "107", "97", "105"),
        ]
    )

    result = FairValueGapDetector().detect(series)

    assert result.count == 0
    assert result.gaps == ()
    assert result.latest is None
    assert result.latest_bullish is None
    assert result.latest_bearish is None


def test_insufficient_history_is_fail_safe() -> None:
    series = create_series(
        [
            ("100", "105", "95", "102"),
            ("102", "106", "96", "104"),
        ]
    )

    with pytest.raises(
        FairValueGapDetectionError,
        match="INSUFFICIENT_HISTORY",
    ) as captured:
        FairValueGapDetector().detect(series)

    assert captured.value.reason == (FairValueGapDetectionErrorReason.INSUFFICIENT_HISTORY)


def test_invalid_series_type_is_fail_safe() -> None:
    with pytest.raises(
        FairValueGapDetectionError,
        match="INVALID_SERIES",
    ) as captured:
        FairValueGapDetector().detect("invalid")

    assert captured.value.reason == (FairValueGapDetectionErrorReason.INVALID_SERIES)


def test_nearest_bullish_gap_below_is_selected() -> None:
    result = FairValueGapDetector().detect(bullish_series())

    nearest = result.nearest_bullish_below("110")

    assert nearest is result.gaps[0]


def test_nearest_bearish_gap_above_is_selected() -> None:
    result = FairValueGapDetector().detect(bearish_series())

    nearest = result.nearest_bearish_above("100")

    assert nearest is result.gaps[0]


def test_nearest_lookup_returns_none_without_candidate() -> None:
    bullish = FairValueGapDetector().detect(bullish_series())
    bearish = FairValueGapDetector().detect(bearish_series())

    assert bullish.nearest_bullish_below("100") is None
    assert bearish.nearest_bearish_above("110") is None


def test_manual_gap_rejects_symbol_mismatch() -> None:
    source = bullish_series()
    other = bullish_series(broker_symbol="XAUUSD")

    with pytest.raises(
        ValueError,
        match="same broker symbol",
    ):
        FairValueGap(
            first_index=0,
            direction=FairValueGapDirection.BULLISH,
            first_candle=source.candles[0],
            middle_candle=source.candles[1],
            third_candle=other.candles[2],
        )


def test_manual_set_rejects_wrong_source_candles() -> None:
    source = bullish_series()
    other = create_series(
        [
            ("100", "104", "99", "102"),
            ("103", "113", "102", "112"),
            ("111", "116", "106", "114"),
        ]
    )
    gap = FairValueGap(
        first_index=0,
        direction=FairValueGapDirection.BULLISH,
        first_candle=other.candles[0],
        middle_candle=other.candles[1],
        third_candle=other.candles[2],
    )

    with pytest.raises(
        ValueError,
        match="source history",
    ):
        FairValueGapSet(
            source=source,
            policy=FairValueGapPolicy(),
            gaps=(gap,),
        )


def test_manual_set_rejects_duplicate_gap() -> None:
    source = bullish_series()
    gap = detected_bullish_gap()

    with pytest.raises(
        ValueError,
        match="Duplicate",
    ):
        FairValueGapSet(
            source=source,
            policy=FairValueGapPolicy(),
            gaps=(gap, gap),
        )


def test_gap_is_immutable() -> None:
    gap = detected_bullish_gap()

    with pytest.raises(FrozenInstanceError):
        gap.first_index = 1


def test_gap_set_is_immutable() -> None:
    result = FairValueGapDetector().detect(bullish_series())

    with pytest.raises(FrozenInstanceError):
        result.gaps = ()


def test_function_api_delegates() -> None:
    result = detect_fair_value_gaps(bullish_series())

    assert result.count == 1


def test_detector_alias_methods_delegate() -> None:
    detector = FairValueGapDetector()
    series = bullish_series()

    assert detector.evaluate(series) == detector.detect(series)
    assert detector.find(series) == detector.detect(series)


def test_public_aliases_are_preserved() -> None:
    assert FVGDirection is FairValueGapDirection
    assert FVGPolicy is FairValueGapPolicy
    assert FVG is FairValueGap
    assert FVGSet is FairValueGapSet
    assert FVGDetector is FairValueGapDetector


def test_detector_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="FairValueGapPolicy",
    ):
        FairValueGapDetector(policy="invalid")


def test_invalid_direction_is_rejected() -> None:
    source = bullish_series()

    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        FairValueGap(
            first_index=0,
            direction="INVALID",
            first_candle=source.candles[0],
            middle_candle=source.candles[1],
            third_candle=source.candles[2],
        )
