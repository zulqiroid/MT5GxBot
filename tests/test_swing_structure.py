from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.timeframes import get_timeframe_spec
from app.strategy.swings import (
    ConfirmedSwingDetector,
    ConfirmedSwingPoint,
    ConfirmedSwingSet,
    SwingDetectionError,
    SwingDetectionErrorReason,
    SwingDetectionPolicy,
    SwingDetector,
    SwingKind,
    SwingPoint,
    SwingPointSet,
    detect_confirmed_swings,
)

START = datetime(
    2026,
    7,
    25,
    12,
    0,
    tzinfo=timezone.utc,
)


def create_candle(
    index: int,
    *,
    high: str,
    low: str,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandle:
    duration = get_timeframe_spec(timeframe).duration
    open_time = START + duration * index
    high_price = Decimal(high)
    low_price = Decimal(low)
    midpoint = (high_price + low_price) / Decimal("2")

    return ClosedCandle(
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


def create_series(
    highs: list[str],
    lows: list[str],
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    candles = tuple(
        create_candle(
            index,
            high=high,
            low=low,
            timeframe=timeframe,
            broker_symbol=broker_symbol,
        )
        for index, (high, low) in enumerate(zip(highs, lows, strict=True))
    )

    return ClosedCandleSeries(
        broker_symbol=broker_symbol,
        timeframe=timeframe,
        candles=candles,
    )


def high_series() -> ClosedCandleSeries:
    return create_series(
        highs=["10", "12", "20", "13", "11"],
        lows=["5", "6", "8", "7", "6"],
    )


def low_series() -> ClosedCandleSeries:
    return create_series(
        highs=["15", "14", "13", "14", "15"],
        lows=["10", "8", "2", "7", "9"],
    )


def dual_series() -> ClosedCandleSeries:
    return create_series(
        highs=["10", "12", "20", "13", "11"],
        lows=["5", "4", "1", "3", "6"],
    )


def test_default_policy_uses_two_sided_confirmation() -> None:
    policy = SwingDetectionPolicy()

    assert policy.left_bars == 2
    assert policy.right_bars == 2
    assert policy.allow_dual_swings is False
    assert policy.minimum_candles == 5
    assert policy.window_size == 5


@pytest.mark.parametrize(
    "overrides",
    [
        {"left_bars": 0},
        {"left_bars": True},
        {"right_bars": 0},
        {"right_bars": 1001},
        {"allow_dual_swings": 1},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        SwingDetectionPolicy(**overrides)


def test_confirmed_swing_high_is_detected() -> None:
    result = ConfirmedSwingDetector().detect(high_series())

    assert result.count == 1
    assert len(result.highs) == 1
    assert result.lows == ()

    swing = result.highs[0]

    assert swing.kind == SwingKind.HIGH
    assert swing.index == 2
    assert swing.price == Decimal("20")
    assert swing.confirmed_by_index == 4
    assert swing.confirmed_at == (result.source.candles[4].close_time)


def test_confirmed_swing_low_is_detected() -> None:
    result = ConfirmedSwingDetector().detect(low_series())

    assert result.count == 1
    assert result.highs == ()
    assert len(result.lows) == 1

    swing = result.lows[0]

    assert swing.kind == SwingKind.LOW
    assert swing.index == 2
    assert swing.price == Decimal("2")
    assert swing.is_low is True
    assert swing.is_high is False


def test_swing_properties_preserve_market_context() -> None:
    result = ConfirmedSwingDetector().detect(high_series())
    swing = result.highs[0]

    assert swing.broker_symbol == "XAUUSDm"
    assert swing.timeframe == TimeframeName.M5
    assert swing.open_time == START + timedelta(minutes=10)
    assert swing.close_time == START + timedelta(minutes=15)


def test_edge_candles_cannot_be_swings() -> None:
    series = create_series(
        highs=["30", "12", "15", "13", "25"],
        lows=["1", "6", "7", "5", "2"],
    )

    result = ConfirmedSwingDetector().detect(series)

    assert all(point.index not in {0, 1, 3, 4} for point in result.points)


def test_equal_high_plateau_is_not_a_swing() -> None:
    series = create_series(
        highs=["10", "20", "20", "13", "11"],
        lows=["5", "6", "7", "6", "5"],
    )

    result = ConfirmedSwingDetector().detect(series)

    assert result.highs == ()


def test_equal_low_plateau_is_not_a_swing() -> None:
    series = create_series(
        highs=["15", "14", "13", "14", "15"],
        lows=["10", "2", "2", "7", "9"],
    )

    result = ConfirmedSwingDetector().detect(series)

    assert result.lows == ()


def test_dual_swing_is_rejected_by_default() -> None:
    result = ConfirmedSwingDetector().detect(dual_series())

    assert result.points == ()
    assert result.contains_dual_swing is False


def test_dual_swing_can_be_explicitly_allowed() -> None:
    policy = SwingDetectionPolicy(allow_dual_swings=True)

    result = ConfirmedSwingDetector(policy).detect(dual_series())

    assert result.count == 2
    assert result.points[0].kind == SwingKind.HIGH
    assert result.points[1].kind == SwingKind.LOW
    assert result.points[0].index == 2
    assert result.points[1].index == 2
    assert result.contains_dual_swing is True


def test_custom_left_and_right_confirmation() -> None:
    policy = SwingDetectionPolicy(
        left_bars=1,
        right_bars=1,
    )
    series = create_series(
        highs=["10", "15", "11"],
        lows=["5", "8", "6"],
    )

    result = ConfirmedSwingDetector(policy).detect(series)

    assert result.highs[0].index == 1
    assert result.highs[0].confirmed_by_index == 2


def test_unconfirmed_tail_cannot_be_detected() -> None:
    series = create_series(
        highs=["10", "11", "12", "13", "30"],
        lows=["5", "6", "7", "8", "9"],
    )

    result = ConfirmedSwingDetector().detect(series)

    assert result.points == ()
    assert result.last_eligible_index == 2
    assert result.unconfirmed_tail_count == 2


def test_insufficient_history_is_fail_safe() -> None:
    series = create_series(
        highs=["10", "12", "11", "10"],
        lows=["5", "6", "4", "3"],
    )

    with pytest.raises(
        SwingDetectionError,
        match="INSUFFICIENT_HISTORY",
    ) as captured:
        ConfirmedSwingDetector().detect(series)

    assert captured.value.reason == (SwingDetectionErrorReason.INSUFFICIENT_HISTORY)


def test_invalid_series_type_is_fail_safe() -> None:
    with pytest.raises(
        SwingDetectionError,
        match="INVALID_SERIES",
    ):
        ConfirmedSwingDetector().detect("invalid")


def test_no_swing_returns_empty_valid_set() -> None:
    series = create_series(
        highs=["10", "11", "12", "13", "14"],
        lows=["5", "6", "7", "8", "9"],
    )

    result = ConfirmedSwingDetector().detect(series)

    assert result.count == 0
    assert result.latest is None
    assert result.latest_high is None
    assert result.latest_low is None


def test_multiple_swings_are_ordered() -> None:
    series = create_series(
        highs=[
            "10",
            "12",
            "20",
            "14",
            "13",
            "12",
            "18",
            "13",
            "11",
        ],
        lows=[
            "5",
            "6",
            "8",
            "7",
            "2",
            "6",
            "8",
            "5",
            "4",
        ],
    )

    result = ConfirmedSwingDetector().detect(series)

    assert [point.index for point in result.points] == sorted(
        point.index for point in result.points
    )
    assert result.latest == result.points[-1]


def test_high_and_low_filters_are_stable() -> None:
    policy = SwingDetectionPolicy(allow_dual_swings=True)
    result = ConfirmedSwingDetector(policy).detect(dual_series())

    assert result.by_kind(SwingKind.HIGH) == result.highs
    assert result.by_kind(SwingKind.LOW) == result.lows
    assert result.at_index(2) == result.points
    assert result.at_index(1) == ()


def test_invalid_kind_filter_is_rejected() -> None:
    result = ConfirmedSwingDetector().detect(high_series())

    with pytest.raises(ValueError):
        result.by_kind("INVALID")


def test_negative_index_filter_is_rejected() -> None:
    result = ConfirmedSwingDetector().detect(high_series())

    with pytest.raises(ValueError):
        result.at_index(-1)


def test_result_preserves_symbol_and_timeframe() -> None:
    series = create_series(
        highs=["10", "12", "20", "13", "11"],
        lows=["5", "6", "8", "7", "6"],
        timeframe=TimeframeName.H1,
        broker_symbol="XAUUSD.pro",
    )

    result = ConfirmedSwingDetector().detect(series)

    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1


def test_swing_point_is_immutable() -> None:
    point = ConfirmedSwingDetector().detect(high_series()).highs[0]

    with pytest.raises(FrozenInstanceError):
        point.index = 3


def test_swing_set_is_immutable() -> None:
    result = ConfirmedSwingDetector().detect(high_series())

    with pytest.raises(FrozenInstanceError):
        result.points = ()


def test_manual_point_requires_future_confirmation_index() -> None:
    candle = high_series().candles[2]

    with pytest.raises(
        ValueError,
        match="greater",
    ):
        ConfirmedSwingPoint(
            index=2,
            kind=SwingKind.HIGH,
            candle=candle,
            confirmed_by_index=2,
            confirmed_at=candle.close_time,
        )


def test_manual_set_rejects_wrong_confirmation_index() -> None:
    source = high_series()
    point = ConfirmedSwingPoint(
        index=2,
        kind=SwingKind.HIGH,
        candle=source.candles[2],
        confirmed_by_index=3,
        confirmed_at=source.candles[3].close_time,
    )

    with pytest.raises(
        ValueError,
        match="detection policy",
    ):
        ConfirmedSwingSet(
            source=source,
            policy=SwingDetectionPolicy(),
            points=(point,),
        )


def test_manual_set_rejects_wrong_source_candle() -> None:
    source = high_series()
    other = low_series()

    point = ConfirmedSwingPoint(
        index=2,
        kind=SwingKind.HIGH,
        candle=other.candles[2],
        confirmed_by_index=4,
        confirmed_at=source.candles[4].close_time,
    )

    with pytest.raises(
        ValueError,
        match="source candle",
    ):
        ConfirmedSwingSet(
            source=source,
            policy=SwingDetectionPolicy(),
            points=(point,),
        )


def test_manual_set_rejects_dual_points_when_disabled() -> None:
    source = dual_series()
    confirmation_time = source.candles[4].close_time

    points = (
        ConfirmedSwingPoint(
            index=2,
            kind=SwingKind.HIGH,
            candle=source.candles[2],
            confirmed_by_index=4,
            confirmed_at=confirmation_time,
        ),
        ConfirmedSwingPoint(
            index=2,
            kind=SwingKind.LOW,
            candle=source.candles[2],
            confirmed_by_index=4,
            confirmed_at=confirmation_time,
        ),
    )

    with pytest.raises(
        ValueError,
        match="Dual swings",
    ):
        ConfirmedSwingSet(
            source=source,
            policy=SwingDetectionPolicy(),
            points=points,
        )


def test_function_api_delegates_to_detector() -> None:
    result = detect_confirmed_swings(high_series())

    assert result.highs[0].index == 2


def test_evaluate_alias_delegates() -> None:
    detector = ConfirmedSwingDetector()

    assert detector.evaluate(high_series()) == detector.detect(high_series())


def test_public_aliases_are_preserved() -> None:
    assert SwingPoint is ConfirmedSwingPoint
    assert SwingPointSet is ConfirmedSwingSet
    assert SwingDetector is ConfirmedSwingDetector


def test_detector_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="SwingDetectionPolicy",
    ):
        ConfirmedSwingDetector(policy="invalid")
