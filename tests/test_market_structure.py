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
from app.strategy.market_structure import (
    BreakDirection,
    BreakKind,
    MarketStructureAnalysisError,
    MarketStructureAnalyzer,
    MarketStructureBias,
    MarketStructureErrorReason,
    MarketStructurePolicy,
    MarketStructureSnapshot,
    StructureAnalyzer,
    StructureBias,
    StructureBreakDirection,
    StructureBreakEvent,
    StructureBreakKind,
    StructureEvent,
    StructureSnapshot,
    analyze_market_structure,
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
    ordering = {
        SwingKind.HIGH: 0,
        SwingKind.LOW: 1,
    }

    ordered = sorted(
        specifications,
        key=lambda value: (
            value[0],
            ordering[value[1]],
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


def bullish_break_series(
    break_close: str = "111",
) -> ConfirmedSwingSet:
    break_price = Decimal(break_close)
    break_high = max(
        Decimal("112"),
        break_price,
    )

    series = create_series(
        [
            ("100", "105", "95"),
            ("105", "110", "100"),
            ("104", "108", "99"),
            (
                break_close,
                str(break_high),
                "103",
            ),
        ]
    )

    return create_swing_set(
        series,
        [(1, SwingKind.HIGH)],
    )


def bearish_break_series(
    break_close: str = "89",
) -> ConfirmedSwingSet:
    series = create_series(
        [
            ("100", "105", "95"),
            ("95", "100", "90"),
            ("96", "101", "92"),
            (break_close, "94", "88"),
        ]
    )

    return create_swing_set(
        series,
        [(1, SwingKind.LOW)],
    )


def test_default_policy_is_neutral_and_close_confirmed() -> None:
    policy = MarketStructurePolicy()

    assert policy.initial_bias == (MarketStructureBias.NEUTRAL)
    assert policy.minimum_break_distance == Decimal("0")


@pytest.mark.parametrize(
    "value",
    [
        "-0.01",
        "NaN",
        "Infinity",
        object(),
    ],
)
def test_invalid_break_distance_is_rejected(
    value: object,
) -> None:
    with pytest.raises(ValueError):
        MarketStructurePolicy(minimum_break_distance=value)


def test_invalid_initial_bias_is_rejected() -> None:
    with pytest.raises(ValueError):
        MarketStructurePolicy(initial_bias="INVALID")


def test_neutral_bullish_break_establishes_bos() -> None:
    result = MarketStructureAnalyzer().analyze(bullish_break_series())

    assert result.count == 1
    assert result.current_bias == (MarketStructureBias.BULLISH)

    event = result.events[0]

    assert event.kind == StructureBreakKind.BOS
    assert event.direction == (StructureBreakDirection.BULLISH)
    assert event.previous_bias == (MarketStructureBias.NEUTRAL)
    assert event.new_bias == (MarketStructureBias.BULLISH)


def test_neutral_bearish_break_establishes_bos() -> None:
    result = MarketStructureAnalyzer().analyze(bearish_break_series())

    event = result.events[0]

    assert event.kind == StructureBreakKind.BOS
    assert event.direction == (StructureBreakDirection.BEARISH)
    assert result.current_bias == (MarketStructureBias.BEARISH)


def test_bullish_break_against_bearish_bias_is_choch() -> None:
    policy = MarketStructurePolicy(initial_bias=MarketStructureBias.BEARISH)

    result = MarketStructureAnalyzer(policy).analyze(bullish_break_series())

    event = result.events[0]

    assert event.kind == StructureBreakKind.CHOCH
    assert event.previous_bias == (MarketStructureBias.BEARISH)
    assert event.new_bias == (MarketStructureBias.BULLISH)


def test_bearish_break_against_bullish_bias_is_choch() -> None:
    policy = MarketStructurePolicy(initial_bias=MarketStructureBias.BULLISH)

    result = MarketStructureAnalyzer(policy).analyze(bearish_break_series())

    event = result.events[0]

    assert event.kind == StructureBreakKind.CHOCH
    assert event.previous_bias == (MarketStructureBias.BULLISH)
    assert event.new_bias == (MarketStructureBias.BEARISH)


def test_same_direction_break_is_bos() -> None:
    policy = MarketStructurePolicy(initial_bias=MarketStructureBias.BULLISH)

    result = MarketStructureAnalyzer(policy).analyze(bullish_break_series())

    assert result.events[0].kind == (StructureBreakKind.BOS)


def test_exact_swing_level_touch_is_not_a_break() -> None:
    result = MarketStructureAnalyzer().analyze(bullish_break_series("110"))

    assert result.events == ()
    assert result.current_bias == (MarketStructureBias.NEUTRAL)


def test_minimum_break_distance_is_strict() -> None:
    policy = MarketStructurePolicy(minimum_break_distance="2")

    exact_threshold = MarketStructureAnalyzer(policy).analyze(bullish_break_series("112"))

    above_threshold = MarketStructureAnalyzer(policy).analyze(bullish_break_series("112.01"))

    assert exact_threshold.events == ()
    assert above_threshold.count == 1


def test_swing_is_not_breakable_on_confirmation_candle() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("105", "110", "100"),
            ("111", "112", "99"),
            ("109", "110", "103"),
        ]
    )
    swings = create_swing_set(
        series,
        [(1, SwingKind.HIGH)],
    )

    result = MarketStructureAnalyzer().analyze(swings)

    assert result.events == ()


def test_broken_level_does_not_repeat_events() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("105", "110", "100"),
            ("104", "108", "99"),
            ("111", "112", "103"),
            ("113", "114", "105"),
        ]
    )
    swings = create_swing_set(
        series,
        [(1, SwingKind.HIGH)],
    )

    result = MarketStructureAnalyzer().analyze(swings)

    assert result.count == 1
    assert result.events[0].index == 3


def test_new_confirmed_high_can_create_new_bos() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("105", "110", "100"),
            ("104", "108", "99"),
            ("111", "112", "103"),
            ("115", "120", "110"),
            ("116", "118", "112"),
            ("121", "122", "115"),
        ]
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (4, SwingKind.HIGH),
        ],
    )

    result = MarketStructureAnalyzer().analyze(swings)

    assert result.count == 2
    assert [event.index for event in result.events] == [3, 6]
    assert all(event.kind == StructureBreakKind.BOS for event in result.events)


def test_latest_high_supersedes_older_unbroken_high() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("105", "110", "100"),
            ("104", "108", "99"),
            ("109", "120", "103"),
            ("110", "115", "104"),
            ("115", "118", "108"),
        ]
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.HIGH),
            (3, SwingKind.HIGH),
        ],
    )

    result = MarketStructureAnalyzer().analyze(swings)

    assert result.events == ()


def test_choch_then_same_direction_bos_updates_bias_chain() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("95", "100", "90"),
            ("96", "101", "92"),
            ("89", "94", "88"),
            ("88", "92", "85"),
            ("89", "93", "87"),
            ("84", "90", "83"),
        ]
    )
    swings = create_swing_set(
        series,
        [
            (1, SwingKind.LOW),
            (4, SwingKind.LOW),
        ],
    )
    policy = MarketStructurePolicy(initial_bias=MarketStructureBias.BULLISH)

    result = MarketStructureAnalyzer(policy).analyze(swings)

    assert [event.kind for event in result.events] == [
        StructureBreakKind.CHOCH,
        StructureBreakKind.BOS,
    ]
    assert result.current_bias == (MarketStructureBias.BEARISH)


def test_no_swings_returns_empty_structure() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("101", "106", "96"),
            ("102", "107", "97"),
        ]
    )
    swings = create_swing_set(series, [])

    result = MarketStructureAnalyzer().analyze(swings)

    assert result.count == 0
    assert result.latest_event is None
    assert result.current_bias == (MarketStructureBias.NEUTRAL)


def test_initial_bias_is_preserved_without_events() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("101", "106", "96"),
            ("102", "107", "97"),
        ]
    )
    swings = create_swing_set(series, [])
    policy = MarketStructurePolicy(initial_bias=MarketStructureBias.BEARISH)

    result = MarketStructureAnalyzer(policy).analyze(swings)

    assert result.current_bias == (MarketStructureBias.BEARISH)


def test_event_exposes_break_context() -> None:
    result = MarketStructureAnalyzer().analyze(bullish_break_series())
    event = result.events[0]

    assert event.index == 3
    assert event.break_price == Decimal("111")
    assert event.level_price == Decimal("110")
    assert event.break_distance == Decimal("1")
    assert event.confirmed_at == event.candle.close_time
    assert event.broker_symbol == "XAUUSDm"
    assert event.timeframe == TimeframeName.M5
    assert event.is_bos is True
    assert event.is_choch is False
    assert event.is_bullish is True
    assert event.is_bearish is False


def test_result_filters_events() -> None:
    result = MarketStructureAnalyzer().analyze(bullish_break_series())

    assert result.bos_events == result.events
    assert result.choch_events == ()
    assert result.bullish_breaks == result.events
    assert result.bearish_breaks == ()
    assert result.events_at(3) == result.events
    assert result.events_at(2) == ()


def test_bias_after_uses_event_history() -> None:
    result = MarketStructureAnalyzer().analyze(bullish_break_series())

    assert result.bias_after(2) == (MarketStructureBias.NEUTRAL)
    assert result.bias_after(3) == (MarketStructureBias.BULLISH)


def test_result_preserves_symbol_and_timeframe() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("105", "110", "100"),
            ("104", "108", "99"),
            ("111", "112", "103"),
        ],
        timeframe=TimeframeName.H1,
        broker_symbol="XAUUSD.pro",
    )
    swings = create_swing_set(
        series,
        [(1, SwingKind.HIGH)],
    )

    result = MarketStructureAnalyzer().analyze(swings)

    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1


def test_invalid_swing_set_type_is_fail_safe() -> None:
    with pytest.raises(
        MarketStructureAnalysisError,
        match="INVALID_SWING_SET",
    ) as captured:
        MarketStructureAnalyzer().analyze("invalid")

    assert captured.value.reason == (MarketStructureErrorReason.INVALID_SWING_SET)


def test_analyzer_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="MarketStructurePolicy",
    ):
        MarketStructureAnalyzer(policy="invalid")


def test_event_rejects_break_on_confirmation_candle() -> None:
    swings = bullish_break_series()
    swing = swings.points[0]

    with pytest.raises(
        ValueError,
        match="after its confirmation",
    ):
        StructureBreakEvent(
            index=swing.confirmed_by_index,
            kind=StructureBreakKind.BOS,
            direction=StructureBreakDirection.BULLISH,
            previous_bias=MarketStructureBias.NEUTRAL,
            new_bias=MarketStructureBias.BULLISH,
            broken_swing=swing,
            candle=swings.source.candles[swing.confirmed_by_index],
        )


def test_event_rejects_wrong_break_kind() -> None:
    swings = bullish_break_series()
    swing = swings.points[0]
    candle = swings.source.candles[3]

    with pytest.raises(
        ValueError,
        match="Break kind",
    ):
        StructureBreakEvent(
            index=3,
            kind=StructureBreakKind.CHOCH,
            direction=StructureBreakDirection.BULLISH,
            previous_bias=MarketStructureBias.NEUTRAL,
            new_bias=MarketStructureBias.BULLISH,
            broken_swing=swing,
            candle=candle,
        )


def test_snapshot_rejects_duplicate_level_breaks() -> None:
    series = create_series(
        [
            ("100", "105", "95"),
            ("105", "110", "100"),
            ("104", "108", "99"),
            ("111", "112", "103"),
            ("112", "113", "104"),
        ]
    )
    swings = create_swing_set(
        series,
        [(1, SwingKind.HIGH)],
    )
    swing = swings.points[0]

    first = StructureBreakEvent(
        index=3,
        kind=StructureBreakKind.BOS,
        direction=StructureBreakDirection.BULLISH,
        previous_bias=MarketStructureBias.NEUTRAL,
        new_bias=MarketStructureBias.BULLISH,
        broken_swing=swing,
        candle=series.candles[3],
    )
    second = StructureBreakEvent(
        index=4,
        kind=StructureBreakKind.BOS,
        direction=StructureBreakDirection.BULLISH,
        previous_bias=MarketStructureBias.BULLISH,
        new_bias=MarketStructureBias.BULLISH,
        broken_swing=swing,
        candle=series.candles[4],
    )

    with pytest.raises(
        ValueError,
        match="more than once",
    ):
        MarketStructureSnapshot(
            swings=swings,
            policy=MarketStructurePolicy(),
            events=(first, second),
        )


def test_snapshot_rejects_invalid_bias_chain() -> None:
    swings = bullish_break_series()
    swing = swings.points[0]

    event = StructureBreakEvent(
        index=3,
        kind=StructureBreakKind.BOS,
        direction=StructureBreakDirection.BULLISH,
        previous_bias=MarketStructureBias.BULLISH,
        new_bias=MarketStructureBias.BULLISH,
        broken_swing=swing,
        candle=swings.source.candles[3],
    )

    with pytest.raises(
        ValueError,
        match="bias chain",
    ):
        MarketStructureSnapshot(
            swings=swings,
            policy=MarketStructurePolicy(),
            events=(event,),
        )


def test_snapshot_is_immutable() -> None:
    result = MarketStructureAnalyzer().analyze(bullish_break_series())

    with pytest.raises(FrozenInstanceError):
        result.events = ()


def test_event_is_immutable() -> None:
    event = MarketStructureAnalyzer().analyze(bullish_break_series()).events[0]

    with pytest.raises(FrozenInstanceError):
        event.index = 4


def test_function_api_delegates() -> None:
    result = analyze_market_structure(bullish_break_series())

    assert result.count == 1


def test_analyzer_alias_methods_delegate() -> None:
    analyzer = MarketStructureAnalyzer()
    swings = bullish_break_series()

    assert analyzer.evaluate(swings) == analyzer.analyze(swings)
    assert analyzer.detect(swings) == analyzer.analyze(swings)


def test_public_aliases_are_preserved() -> None:
    assert StructureBias is MarketStructureBias
    assert BreakKind is StructureBreakKind
    assert BreakDirection is StructureBreakDirection
    assert StructureEvent is StructureBreakEvent
    assert StructureSnapshot is MarketStructureSnapshot
    assert StructureAnalyzer is MarketStructureAnalyzer
