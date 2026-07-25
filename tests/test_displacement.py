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
from app.strategy.displacement import (
    Displacement,
    DisplacementCollection,
    DisplacementDetectionError,
    DisplacementDetectionErrorReason,
    DisplacementDetector,
    DisplacementDirection,
    DisplacementImpulse,
    DisplacementPolicy,
    DisplacementSet,
    ImpulseDetector,
    ImpulseDirection,
    ImpulsePolicy,
    detect_displacement_impulses,
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
    candidate: tuple[str, str, str, str] = (
        "100",
        "108",
        "99",
        "107",
    ),
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    return create_series(
        [
            ("100", "102", "98", "101"),
            ("101", "103", "99", "100"),
            ("100", "102", "98", "101"),
            candidate,
        ],
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )


def bearish_series() -> ClosedCandleSeries:
    return create_series(
        [
            ("100", "102", "98", "101"),
            ("101", "103", "99", "100"),
            ("100", "102", "98", "101"),
            ("107", "108", "99", "100"),
        ]
    )


def detected_bullish() -> DisplacementImpulse:
    return DisplacementDetector().detect(bullish_series()).impulses[0]


def test_default_policy_is_conservative() -> None:
    policy = DisplacementPolicy()

    assert policy.lookback_candles == 3
    assert policy.minimum_history == 4
    assert policy.minimum_body_ratio == Decimal("0.60")
    assert policy.minimum_range_expansion_ratio == Decimal("1.50")
    assert policy.maximum_close_retracement_ratio == Decimal("0.25")
    assert policy.minimum_absolute_range == Decimal("0")


@pytest.mark.parametrize(
    "overrides",
    [
        {"lookback_candles": 0},
        {"lookback_candles": True},
        {"lookback_candles": 101},
        {"minimum_body_ratio": "-0.01"},
        {"minimum_body_ratio": "1.01"},
        {"minimum_body_ratio": True},
        {"minimum_range_expansion_ratio": "0.99"},
        {"minimum_range_expansion_ratio": "NaN"},
        {"maximum_close_retracement_ratio": "-0.01"},
        {"maximum_close_retracement_ratio": "1.01"},
        {"minimum_absolute_range": "-0.01"},
        {"minimum_absolute_range": "Infinity"},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        DisplacementPolicy(**overrides)


def test_bullish_displacement_is_detected() -> None:
    result = DisplacementDetector().detect(bullish_series())

    assert result.count == 1
    assert len(result.bullish) == 1
    assert result.bearish == ()

    impulse = result.impulses[0]

    assert impulse.direction == (DisplacementDirection.BULLISH)
    assert impulse.is_bullish is True
    assert impulse.is_bearish is False


def test_bearish_displacement_is_detected() -> None:
    result = DisplacementDetector().detect(bearish_series())

    assert result.count == 1
    assert result.bullish == ()
    assert len(result.bearish) == 1
    assert result.impulses[0].direction == (DisplacementDirection.BEARISH)


def test_doji_is_not_displacement() -> None:
    result = DisplacementDetector().detect(bullish_series(candidate=("104", "109", "99", "104")))

    assert result.impulses == ()


def test_small_body_is_rejected() -> None:
    result = DisplacementDetector().detect(bullish_series(candidate=("103", "109", "99", "105")))

    assert result.impulses == ()


def test_exact_body_ratio_is_allowed() -> None:
    policy = DisplacementPolicy(
        minimum_body_ratio="0.60",
        maximum_close_retracement_ratio="0.30",
    )
    series = bullish_series(candidate=("101", "110", "100", "107"))

    result = DisplacementDetector(policy).detect(series)

    assert result.count == 1
    assert result.impulses[0].body_ratio == Decimal("0.6")


def test_body_ratio_below_threshold_is_rejected() -> None:
    policy = DisplacementPolicy(maximum_close_retracement_ratio="0.50")
    series = bullish_series(
        candidate=(
            "101",
            "110",
            "100",
            "106.99",
        )
    )

    result = DisplacementDetector(policy).detect(series)

    assert result.impulses == ()


def test_exact_range_expansion_threshold_is_rejected() -> None:
    series = bullish_series(candidate=("100", "106", "100", "105"))

    result = DisplacementDetector().detect(series)

    assert result.impulses == ()


def test_range_above_expansion_threshold_is_detected() -> None:
    series = bullish_series(
        candidate=(
            "100",
            "106.01",
            "100",
            "105.01",
        )
    )

    result = DisplacementDetector().detect(series)

    assert result.count == 1


def test_exact_close_retracement_threshold_is_allowed() -> None:
    series = bullish_series(
        candidate=(
            "101",
            "110",
            "100",
            "107.5",
        )
    )

    result = DisplacementDetector().detect(series)

    assert result.count == 1
    assert result.impulses[0].close_retracement_ratio == Decimal("0.25")


def test_close_retracement_above_threshold_is_rejected() -> None:
    series = bullish_series(
        candidate=(
            "101",
            "110",
            "100",
            "107.49",
        )
    )

    result = DisplacementDetector().detect(series)

    assert result.impulses == ()


def test_exact_minimum_absolute_range_is_rejected() -> None:
    policy = DisplacementPolicy(minimum_absolute_range="9")

    result = DisplacementDetector(policy).detect(bullish_series())

    assert result.impulses == ()


def test_range_above_minimum_absolute_range_is_detected() -> None:
    policy = DisplacementPolicy(minimum_absolute_range="8.99")

    result = DisplacementDetector(policy).detect(bullish_series())

    assert result.count == 1


def test_custom_lookback_is_respected() -> None:
    policy = DisplacementPolicy(lookback_candles=2)
    series = create_series(
        [
            ("100", "102", "98", "101"),
            ("101", "103", "99", "100"),
            ("100", "108", "99", "107"),
        ]
    )

    result = DisplacementDetector(policy).detect(series)

    assert result.count == 1
    assert result.impulses[0].baseline_average_range == Decimal("4")


def test_insufficient_history_is_fail_safe() -> None:
    series = create_series(
        [
            ("100", "102", "98", "101"),
            ("101", "103", "99", "100"),
            ("100", "102", "98", "101"),
        ]
    )

    with pytest.raises(
        DisplacementDetectionError,
        match="INSUFFICIENT_HISTORY",
    ) as captured:
        DisplacementDetector().detect(series)

    assert captured.value.reason == (DisplacementDetectionErrorReason.INSUFFICIENT_HISTORY)


def test_invalid_series_type_is_fail_safe() -> None:
    with pytest.raises(
        DisplacementDetectionError,
        match="INVALID_SERIES",
    ) as captured:
        DisplacementDetector().detect("invalid")

    assert captured.value.reason == (DisplacementDetectionErrorReason.INVALID_SERIES)


def test_no_displacement_returns_empty_valid_set() -> None:
    series = create_series(
        [
            ("100", "102", "98", "101"),
            ("101", "103", "99", "100"),
            ("100", "102", "98", "101"),
            ("101", "103", "99", "102"),
        ]
    )

    result = DisplacementDetector().detect(series)

    assert result.count == 0
    assert result.impulses == ()
    assert result.latest is None
    assert result.latest_bullish is None
    assert result.latest_bearish is None
    assert result.strongest is None


def test_impulse_metrics_are_exact() -> None:
    impulse = detected_bullish()

    assert impulse.index == 3
    assert impulse.candle_range == Decimal("9")
    assert impulse.body_size == Decimal("7")
    assert impulse.body_ratio == (Decimal("7") / Decimal("9"))
    assert impulse.baseline_average_range == Decimal("4")
    assert impulse.range_expansion_ratio == Decimal("2.25")
    assert impulse.close_retracement == Decimal("1")
    assert impulse.close_retracement_ratio == (Decimal("1") / Decimal("9"))


def test_impulse_preserves_market_context() -> None:
    result = DisplacementDetector().detect(
        bullish_series(
            timeframe=TimeframeName.H1,
            broker_symbol="XAUUSD.pro",
        )
    )
    impulse = result.impulses[0]

    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1
    assert impulse.broker_symbol == "XAUUSD.pro"
    assert impulse.timeframe == TimeframeName.H1
    assert impulse.confirmed_at == (impulse.candle.close_time)
    assert impulse.stable_id == ("XAUUSD.pro:H1:BULLISH:3")


def test_multiple_impulses_are_ordered() -> None:
    policy = DisplacementPolicy(lookback_candles=1)
    series = create_series(
        [
            ("100", "102", "98", "101"),
            ("100", "108", "100", "107"),
            ("106", "108", "104", "105"),
            ("107", "108", "100", "101"),
        ]
    )

    result = DisplacementDetector(policy).detect(series)

    assert [impulse.index for impulse in result.impulses] == [1, 3]
    assert result.latest is result.impulses[-1]
    assert result.latest_bullish is result.bullish[-1]
    assert result.latest_bearish is result.bearish[-1]


def test_direction_and_index_filters_are_available() -> None:
    result = DisplacementDetector().detect(bullish_series())
    impulse = result.impulses[0]

    assert result.by_direction(DisplacementDirection.BULLISH) == (impulse,)
    assert result.by_direction(DisplacementDirection.BEARISH) == ()
    assert result.at_index(3) is impulse
    assert result.at_index(2) is None
    assert result.confirmed_at_index(3) == (impulse,)
    assert result.confirmed_at_index(2) == ()


def test_invalid_direction_filter_is_rejected() -> None:
    result = DisplacementDetector().detect(bullish_series())

    with pytest.raises(ValueError):
        result.by_direction("INVALID")


def test_strongest_uses_expansion_ratio() -> None:
    policy = DisplacementPolicy(lookback_candles=1)
    series = create_series(
        [
            ("100", "102", "98", "101"),
            ("100", "108", "100", "107"),
            ("106", "108", "104", "105"),
            ("107", "110", "99", "100"),
        ]
    )

    result = DisplacementDetector(policy).detect(series)

    assert result.count == 2
    assert result.strongest is result.impulses[1]


def test_manual_impulse_rejects_wrong_direction() -> None:
    series = bullish_series()

    with pytest.raises(
        ValueError,
        match="body direction",
    ):
        DisplacementImpulse(
            index=3,
            direction=DisplacementDirection.BEARISH,
            candle=series.candles[3],
            baseline_average_range=Decimal("4"),
        )


def test_manual_set_rejects_wrong_baseline() -> None:
    series = bullish_series()
    impulse = DisplacementImpulse(
        index=3,
        direction=DisplacementDirection.BULLISH,
        candle=series.candles[3],
        baseline_average_range=Decimal("5"),
    )

    with pytest.raises(
        ValueError,
        match="baseline",
    ):
        DisplacementSet(
            source=series,
            policy=DisplacementPolicy(),
            impulses=(impulse,),
        )


def test_manual_set_rejects_wrong_source_candle() -> None:
    source = bullish_series()
    other = bullish_series(broker_symbol="XAUUSD")
    impulse = DisplacementImpulse(
        index=3,
        direction=DisplacementDirection.BULLISH,
        candle=other.candles[3],
        baseline_average_range=Decimal("4"),
    )

    with pytest.raises(
        ValueError,
        match="source candle",
    ):
        DisplacementSet(
            source=source,
            policy=DisplacementPolicy(),
            impulses=(impulse,),
        )


def test_manual_set_rejects_duplicate_indexes() -> None:
    series = bullish_series()
    impulse = detected_bullish()

    with pytest.raises(
        ValueError,
        match="Duplicate",
    ):
        DisplacementSet(
            source=series,
            policy=DisplacementPolicy(),
            impulses=(impulse, impulse),
        )


def test_impulse_is_immutable() -> None:
    impulse = detected_bullish()

    with pytest.raises(FrozenInstanceError):
        impulse.index = 4


def test_set_is_immutable() -> None:
    result = DisplacementDetector().detect(bullish_series())

    with pytest.raises(FrozenInstanceError):
        result.impulses = ()


def test_function_api_delegates() -> None:
    result = detect_displacement_impulses(bullish_series())

    assert result.count == 1


def test_detector_alias_methods_delegate() -> None:
    detector = DisplacementDetector()
    series = bullish_series()

    assert detector.evaluate(series) == detector.detect(series)
    assert detector.find(series) == detector.detect(series)


def test_public_aliases_are_preserved() -> None:
    assert Displacement is DisplacementImpulse
    assert DisplacementCollection is DisplacementSet
    assert ImpulseDirection is DisplacementDirection
    assert ImpulseDetector is DisplacementDetector
    assert ImpulsePolicy is DisplacementPolicy


def test_detector_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="DisplacementPolicy",
    ):
        DisplacementDetector(policy="invalid")
