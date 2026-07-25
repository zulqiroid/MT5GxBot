from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import MetaTrader5 as mt5
import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    CandleDirection,
    CandleWindow,
    ClosedCandle,
    ClosedCandleSeries,
    FormingCandle,
)
from app.market.timeframes import (
    MT5_TIMEFRAMES,
    SUPPORTED_STRATEGY_TIMEFRAMES,
    get_mt5_timeframe,
    get_timeframe_spec,
    is_strategy_timeframe,
    parse_timeframe,
    timeframe_duration,
    timeframe_seconds,
)

OPEN_TIME = datetime(
    2026,
    7,
    25,
    12,
    0,
    tzinfo=timezone.utc,
)
M15_CLOSE_TIME = OPEN_TIME + timedelta(minutes=15)


def create_closed(
    *,
    open_time: datetime = OPEN_TIME,
    observed_at: datetime | None = None,
    **overrides: object,
) -> ClosedCandle:
    values: dict[str, object] = {
        "broker_symbol": "XAUUSDm",
        "timeframe": TimeframeName.M15,
        "open_time": open_time,
        "observed_at": (observed_at or open_time + timedelta(minutes=15)),
        "open": "2400.00",
        "high": "2405.00",
        "low": "2398.00",
        "close": "2403.00",
        "tick_volume": 1000,
        "spread": 20,
        "real_volume": 0,
    }
    values.update(overrides)

    return ClosedCandle(**values)


def create_forming(
    *,
    open_time: datetime = OPEN_TIME,
    observed_at: datetime | None = None,
    **overrides: object,
) -> FormingCandle:
    values: dict[str, object] = {
        "broker_symbol": "XAUUSDm",
        "timeframe": TimeframeName.M15,
        "open_time": open_time,
        "observed_at": (observed_at or open_time + timedelta(minutes=5)),
        "open": "2400.00",
        "high": "2402.00",
        "low": "2399.00",
        "close": "2401.00",
        "tick_volume": 250,
        "spread": 20,
        "real_volume": 0,
    }
    values.update(overrides)

    return FormingCandle(**values)


def test_strategy_timeframe_order_is_fixed() -> None:
    assert SUPPORTED_STRATEGY_TIMEFRAMES == (
        TimeframeName.H4,
        TimeframeName.H1,
        TimeframeName.M15,
        TimeframeName.M5,
    )


@pytest.mark.parametrize(
    ("timeframe", "seconds", "mt5_value"),
    [
        (TimeframeName.M1, 60, mt5.TIMEFRAME_M1),
        (TimeframeName.M5, 300, mt5.TIMEFRAME_M5),
        (TimeframeName.M15, 900, mt5.TIMEFRAME_M15),
        (TimeframeName.M30, 1800, mt5.TIMEFRAME_M30),
        (TimeframeName.H1, 3600, mt5.TIMEFRAME_H1),
        (TimeframeName.H4, 14400, mt5.TIMEFRAME_H4),
        (TimeframeName.D1, 86400, mt5.TIMEFRAME_D1),
    ],
)
def test_timeframe_specifications(
    timeframe: TimeframeName,
    seconds: int,
    mt5_value: int,
) -> None:
    specification = get_timeframe_spec(timeframe)

    assert specification.name == timeframe
    assert specification.seconds == seconds
    assert specification.mt5_value == mt5_value
    assert specification.duration == timedelta(seconds=seconds)
    assert get_mt5_timeframe(timeframe) == mt5_value
    assert timeframe_seconds(timeframe) == seconds
    assert timeframe_duration(timeframe) == timedelta(seconds=seconds)


def test_legacy_timeframe_mapping_is_preserved() -> None:
    assert MT5_TIMEFRAMES["M15"] == mt5.TIMEFRAME_M15
    assert get_mt5_timeframe(" m15 ") == mt5.TIMEFRAME_M15


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [
        ("H4", True),
        ("H1", True),
        ("M15", True),
        ("M5", True),
        ("M1", False),
        ("M30", False),
        ("D1", False),
    ],
)
def test_strategy_timeframe_detection(
    timeframe: str,
    expected: bool,
) -> None:
    assert is_strategy_timeframe(timeframe) is expected


def test_invalid_timeframe_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        parse_timeframe("M7")


def test_closed_candle_normalizes_decimal_values() -> None:
    candle = create_closed()

    assert candle.open == Decimal("2400.00")
    assert candle.high == Decimal("2405.00")
    assert candle.low == Decimal("2398.00")
    assert candle.close == Decimal("2403.00")
    assert candle.close_time == M15_CLOSE_TIME
    assert candle.is_closed is True


def test_candle_direction_and_geometry_metrics() -> None:
    candle = create_closed()

    assert candle.direction == CandleDirection.BULLISH
    assert candle.is_bullish is True
    assert candle.is_bearish is False
    assert candle.is_doji is False
    assert candle.body_size == Decimal("3.00")
    assert candle.full_range == Decimal("7.00")
    assert candle.upper_wick == Decimal("2.00")
    assert candle.lower_wick == Decimal("2.00")


def test_bearish_and_doji_directions() -> None:
    bearish = create_closed(
        open="2403",
        close="2400",
    )
    doji = create_closed(
        open="2401",
        close="2401",
    )

    assert bearish.direction == CandleDirection.BEARISH
    assert bearish.is_bearish is True
    assert doji.direction == CandleDirection.DOJI
    assert doji.is_doji is True


def test_closed_candle_requires_completed_interval() -> None:
    with pytest.raises(
        ValueError,
        match="before its close_time",
    ):
        create_closed(observed_at=OPEN_TIME + timedelta(minutes=14))


def test_forming_candle_must_remain_before_close() -> None:
    forming = create_forming()

    assert forming.is_closed is False
    assert forming.close_time == M15_CLOSE_TIME

    with pytest.raises(
        ValueError,
        match="before its close_time",
    ):
        create_forming(observed_at=M15_CLOSE_TIME)


def test_candle_open_time_must_align_to_timeframe() -> None:
    with pytest.raises(
        ValueError,
        match="timeframe boundary",
    ):
        create_closed(
            open_time=OPEN_TIME + timedelta(minutes=1),
            observed_at=M15_CLOSE_TIME + timedelta(minutes=1),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"open": "0"},
        {"high": "NaN"},
        {"low": "-1"},
        {"close": "Infinity"},
        {"high": "2390", "low": "2400"},
        {"open": "2406"},
        {"close": "2390"},
        {"tick_volume": -1},
        {"spread": -1},
        {"real_volume": -1},
    ],
)
def test_invalid_candle_values_are_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        create_closed(**overrides)


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        create_closed(open_time=datetime(2026, 7, 25, 12, 0))

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        create_closed(observed_at=datetime(2026, 7, 25, 12, 15))


def test_closed_candle_is_immutable() -> None:
    candle = create_closed()

    with pytest.raises(FrozenInstanceError):
        candle.close = Decimal("2500")


def test_mt5_mapping_rate_is_supported() -> None:
    epoch = int(OPEN_TIME.timestamp())
    rate = {
        "time": epoch,
        "open": "2400.00",
        "high": "2405.00",
        "low": "2398.00",
        "close": "2403.00",
        "tick_volume": 1000,
        "spread": 20,
        "real_volume": 0,
    }

    candle = ClosedCandle.from_mt5_rate(
        rate,
        broker_symbol="XAUUSDm",
        timeframe="M15",
        observed_at=M15_CLOSE_TIME,
    )

    assert candle.open_time == OPEN_TIME
    assert candle.close == Decimal("2403.00")


def test_mt5_attribute_rate_is_supported() -> None:
    rate = SimpleNamespace(
        time=int(OPEN_TIME.timestamp()),
        open="2400.00",
        high="2405.00",
        low="2398.00",
        close="2403.00",
        tick_volume=1000,
        spread=20,
        real_volume=0,
    )

    candle = FormingCandle.from_mt5_rate(
        rate,
        broker_symbol="XAUUSDm",
        timeframe=TimeframeName.M15,
        observed_at=OPEN_TIME + timedelta(minutes=5),
    )

    assert candle.open_time == OPEN_TIME
    assert candle.is_closed is False


def test_missing_mt5_rate_field_is_rejected() -> None:
    rate = {
        "time": int(OPEN_TIME.timestamp()),
        "open": "2400",
    }

    with pytest.raises(
        ValueError,
        match="field is missing",
    ):
        ClosedCandle.from_mt5_rate(
            rate,
            broker_symbol="XAUUSDm",
            timeframe="M15",
            observed_at=M15_CLOSE_TIME,
        )


def test_closed_series_is_chronological() -> None:
    first = create_closed()
    second_open = M15_CLOSE_TIME
    second = create_closed(
        open_time=second_open,
        observed_at=second_open + timedelta(minutes=15),
        open="2403",
        high="2408",
        low="2401",
        close="2406",
    )

    series = ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=TimeframeName.M15,
        candles=(first, second),
    )

    assert series.count == 2
    assert series.first == first
    assert series.latest == second
    assert series.previous == first
    assert series.close_prices == (
        Decimal("2403.00"),
        Decimal("2406"),
    )
    assert series.has_gaps is False
    assert series.missing_candle_count == 0


def test_closed_series_detects_missing_intervals() -> None:
    first = create_closed()
    third_open = OPEN_TIME + timedelta(minutes=30)
    third = create_closed(
        open_time=third_open,
        observed_at=third_open + timedelta(minutes=15),
    )

    series = ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=TimeframeName.M15,
        candles=(first, third),
    )

    assert series.has_gaps is True
    assert series.missing_candle_count == 1


def test_closed_series_rejects_empty_history() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        ClosedCandleSeries(
            broker_symbol="XAUUSDm",
            timeframe=TimeframeName.M15,
            candles=(),
        )


def test_closed_series_rejects_forming_candle() -> None:
    with pytest.raises(
        ValueError,
        match="only ClosedCandle",
    ):
        ClosedCandleSeries(
            broker_symbol="XAUUSDm",
            timeframe=TimeframeName.M15,
            candles=(create_forming(),),
        )


def test_closed_series_rejects_duplicate_time() -> None:
    first = create_closed()
    duplicate = create_closed()

    with pytest.raises(
        ValueError,
        match="strictly increasing",
    ):
        ClosedCandleSeries(
            broker_symbol="XAUUSDm",
            timeframe=TimeframeName.M15,
            candles=(first, duplicate),
        )


def test_closed_series_rejects_symbol_mismatch() -> None:
    candle = create_closed(broker_symbol="XAUUSD")

    with pytest.raises(
        ValueError,
        match="series symbol",
    ):
        ClosedCandleSeries(
            broker_symbol="XAUUSDm",
            timeframe=TimeframeName.M15,
            candles=(candle,),
        )


def test_closed_series_append_is_immutable() -> None:
    first = create_closed()
    original = ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=TimeframeName.M15,
        candles=(first,),
    )

    second_open = M15_CLOSE_TIME
    second = create_closed(
        open_time=second_open,
        observed_at=second_open + timedelta(minutes=15),
    )

    updated = original.append(second)

    assert original.count == 1
    assert updated.count == 2
    assert updated.latest == second


def test_previous_requires_two_candles() -> None:
    series = ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=TimeframeName.M15,
        candles=(create_closed(),),
    )

    with pytest.raises(
        ValueError,
        match="two closed candles",
    ):
        _ = series.previous


def test_candle_window_separates_forming_candle() -> None:
    closed = create_closed()
    series = ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=TimeframeName.M15,
        candles=(closed,),
    )
    forming = create_forming(
        open_time=M15_CLOSE_TIME,
        observed_at=M15_CLOSE_TIME + timedelta(minutes=5),
    )

    window = CandleWindow(
        closed=series,
        forming=forming,
    )

    assert window.strategy_candles == (closed,)
    assert window.latest_closed == closed
    assert window.current_forming == forming


def test_candle_window_allows_no_forming_candle() -> None:
    series = ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=TimeframeName.M15,
        candles=(create_closed(),),
    )

    window = CandleWindow(closed=series)

    assert window.current_forming is None


def test_forming_candle_must_immediately_follow_history() -> None:
    series = ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=TimeframeName.M15,
        candles=(create_closed(),),
    )
    delayed_open = OPEN_TIME + timedelta(minutes=30)
    forming = create_forming(
        open_time=delayed_open,
        observed_at=delayed_open + timedelta(minutes=5),
    )

    with pytest.raises(
        ValueError,
        match="immediately follow",
    ):
        CandleWindow(
            closed=series,
            forming=forming,
        )
