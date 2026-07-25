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
    FairValueGap,
    FairValueGapDirection,
    FairValueGapPolicy,
    FairValueGapSet,
)
from app.strategy.fvg_mitigation import (
    FairValueGapMitigationError,
    FairValueGapMitigationErrorReason,
    FairValueGapMitigationEvent,
    FairValueGapMitigationPolicy,
    FairValueGapMitigationSnapshot,
    FairValueGapMitigationState,
    FairValueGapMitigationTracker,
    FVGMitigationEvent,
    FVGMitigationPolicy,
    FVGMitigationSnapshot,
    FVGMitigationState,
    FVGMitigationTracker,
    track_fair_value_gap_mitigation,
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


def bullish_gap_set(
    post_rows: list[tuple[str, str, str, str]] | None = None,
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> FairValueGapSet:
    rows = [
        ("100", "105", "99", "102"),
        ("103", "113", "102", "112"),
        ("111", "116", "106", "114"),
    ]

    if post_rows is not None:
        rows.extend(post_rows)

    series = create_series(
        rows,
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )
    gap = FairValueGap(
        first_index=0,
        direction=FairValueGapDirection.BULLISH,
        first_candle=series.candles[0],
        middle_candle=series.candles[1],
        third_candle=series.candles[2],
    )

    return FairValueGapSet(
        source=series,
        policy=FairValueGapPolicy(),
        gaps=(gap,),
    )


def bearish_gap_set(
    post_rows: list[tuple[str, str, str, str]] | None = None,
) -> FairValueGapSet:
    rows = [
        ("110", "111", "105", "108"),
        ("107", "108", "97", "98"),
        ("99", "104", "95", "96"),
    ]

    if post_rows is not None:
        rows.extend(post_rows)

    series = create_series(rows)
    gap = FairValueGap(
        first_index=0,
        direction=FairValueGapDirection.BEARISH,
        first_candle=series.candles[0],
        middle_candle=series.candles[1],
        third_candle=series.candles[2],
    )

    return FairValueGapSet(
        source=series,
        policy=FairValueGapPolicy(),
        gaps=(gap,),
    )


def test_default_policy_uses_strict_penetration() -> None:
    policy = FairValueGapMitigationPolicy()

    assert policy.minimum_penetration == Decimal("0")


@pytest.mark.parametrize(
    "value",
    [
        "-0.01",
        "NaN",
        "Infinity",
        object(),
    ],
)
def test_invalid_policy_is_rejected(
    value: object,
) -> None:
    with pytest.raises(ValueError):
        FairValueGapMitigationPolicy(minimum_penetration=value)


def test_bullish_partial_mitigation_is_detected() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107.5"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)
    gap = gap_set.gaps[0]

    assert result.count == 1
    assert result.state_for(gap) == (FairValueGapMitigationState.PARTIALLY_MITIGATED)


def test_bearish_partial_mitigation_is_detected() -> None:
    gap_set = bearish_gap_set(
        [
            ("103", "104.25", "102", "103.5"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.state_for(gap_set.gaps[0]) == (FairValueGapMitigationState.PARTIALLY_MITIGATED)


def test_bullish_consequent_encroachment_is_detected() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.5", "107"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.state_for(gap_set.gaps[0]) == (
        FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT
    )


def test_bearish_consequent_encroachment_is_detected() -> None:
    gap_set = bearish_gap_set(
        [
            ("103", "104.5", "102", "103"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.state_for(gap_set.gaps[0]) == (
        FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT
    )


def test_bullish_exact_opposite_boundary_is_full_fill() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105", "107"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.is_fully_filled(gap_set.gaps[0]) is True


def test_bearish_exact_opposite_boundary_is_full_fill() -> None:
    gap_set = bearish_gap_set(
        [
            ("103", "105", "102", "103"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.is_fully_filled(gap_set.gaps[0]) is True


def test_bullish_exact_near_boundary_touch_is_not_mitigation() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "106", "107"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.events == ()
    assert result.state_for(gap_set.gaps[0]) == FairValueGapMitigationState.UNTOUCHED


def test_bearish_exact_near_boundary_touch_is_not_mitigation() -> None:
    gap_set = bearish_gap_set(
        [
            ("103", "104", "102", "103"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.events == ()


def test_exact_minimum_penetration_is_rejected() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )
    policy = FairValueGapMitigationPolicy(minimum_penetration="0.25")

    result = FairValueGapMitigationTracker(policy).track(gap_set)

    assert result.events == ()


def test_penetration_above_minimum_is_detected() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )
    policy = FairValueGapMitigationPolicy(minimum_penetration="0.24")

    result = FairValueGapMitigationTracker(policy).track(gap_set)

    assert result.count == 1


def test_bullish_multistage_lifecycle_is_ordered() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
            ("106", "108", "105.5", "107"),
            ("106", "108", "105", "107"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert [event.index for event in result.events] == [3, 4, 5]
    assert [event.new_state for event in result.events] == [
        FairValueGapMitigationState.PARTIALLY_MITIGATED,
        FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT,
        FairValueGapMitigationState.FULLY_FILLED,
    ]


def test_bearish_multistage_lifecycle_is_ordered() -> None:
    gap_set = bearish_gap_set(
        [
            ("103", "104.25", "102", "103"),
            ("103", "104.5", "102", "103"),
            ("103", "105", "102", "103"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert [event.new_state for event in result.events] == [
        FairValueGapMitigationState.PARTIALLY_MITIGATED,
        FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT,
        FairValueGapMitigationState.FULLY_FILLED,
    ]


def test_direct_full_fill_uses_one_event() -> None:
    gap_set = bullish_gap_set(
        [
            ("106", "108", "104.5", "107"),
        ]
    )
    gap = gap_set.gaps[0]

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.count == 1
    assert result.first_touch_event(gap) == (result.full_fill_event(gap))
    assert result.consequent_encroachment_event(gap) == result.full_fill_event(gap)


def test_full_fill_blocks_repeat_events() -> None:
    gap_set = bullish_gap_set(
        [
            ("106", "108", "105", "107"),
            ("106", "109", "104", "108"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.count == 1
    assert result.events[0].index == 3


def test_same_state_deeper_progress_is_recorded() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.90", "107"),
            ("107", "108", "105.70", "107"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.count == 2
    assert result.events[1].is_progress_only is True
    assert result.fill_fraction_for(gap_set.gaps[0]) == Decimal("0.30")


def test_event_exposes_exact_mitigation_context() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )

    event = FairValueGapMitigationTracker().track(gap_set).events[0]

    assert event.index == 3
    assert event.extreme_price == Decimal("105.75")
    assert event.raw_penetration == Decimal("0.25")
    assert event.zone_penetration == Decimal("0.25")
    assert event.fill_fraction == Decimal("0.25")
    assert event.fill_percentage == Decimal("25.00")
    assert event.confirmed_at == event.candle.close_time
    assert event.stable_id.endswith(":MITIGATION:3:PARTIALLY_MITIGATED")


def test_consequent_encroachment_fill_fraction_is_half() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.5", "107"),
            ("106", "108", "105", "107"),
        ]
    )
    gap = gap_set.gaps[0]

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.events[0].fill_fraction == Decimal("0.5")
    assert result.fill_fraction_for(gap) == Decimal("1")


def test_snapshot_filters_gap_states() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.5", "107"),
        ]
    )
    gap = gap_set.gaps[0]

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.untouched_gaps == ()
    assert result.mitigated_gaps == (gap,)
    assert result.partially_mitigated_gaps == ()
    assert result.consequent_encroachment_gaps == (gap,)
    assert result.fully_filled_gaps == ()
    assert result.active_gaps == (gap,)
    assert result.events_at(3) == result.events
    assert result.events_at(2) == ()


def test_unvisited_gap_remains_active_and_untouched() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "106", "107"),
        ]
    )
    gap = gap_set.gaps[0]

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.untouched_gaps == (gap,)
    assert result.mitigated_gaps == ()
    assert result.active_gaps == (gap,)
    assert result.latest is None
    assert result.fill_fraction_for(gap) == Decimal("0")


def test_result_preserves_market_context() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ],
        timeframe=TimeframeName.H1,
        broker_symbol="XAUUSD.pro",
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1


def test_invalid_gap_set_type_is_fail_safe() -> None:
    with pytest.raises(
        FairValueGapMitigationError,
        match="INVALID_GAP_SET",
    ) as captured:
        FairValueGapMitigationTracker().track("invalid")

    assert captured.value.reason == (FairValueGapMitigationErrorReason.INVALID_GAP_SET)


def test_tracker_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="FairValueGapMitigationPolicy",
    ):
        FairValueGapMitigationTracker(policy="invalid")


def test_event_rejects_confirmation_candle() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )
    gap = gap_set.gaps[0]

    with pytest.raises(
        ValueError,
        match="after",
    ):
        FairValueGapMitigationEvent(
            index=gap.confirmation_index,
            gap=gap,
            candle=gap.third_candle,
            previous_state=(FairValueGapMitigationState.UNTOUCHED),
            new_state=(FairValueGapMitigationState.PARTIALLY_MITIGATED),
        )


def test_event_rejects_wrong_reached_state() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )
    gap = gap_set.gaps[0]

    with pytest.raises(
        ValueError,
        match="deepest state",
    ):
        FairValueGapMitigationEvent(
            index=3,
            gap=gap,
            candle=gap_set.source.candles[3],
            previous_state=(FairValueGapMitigationState.UNTOUCHED),
            new_state=(FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT),
        )


def test_snapshot_rejects_invalid_state_chain() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
            ("106", "108", "105.5", "107"),
        ]
    )
    gap = gap_set.gaps[0]

    first = FairValueGapMitigationEvent(
        index=3,
        gap=gap,
        candle=gap_set.source.candles[3],
        previous_state=(FairValueGapMitigationState.UNTOUCHED),
        new_state=(FairValueGapMitigationState.PARTIALLY_MITIGATED),
    )
    invalid_second = FairValueGapMitigationEvent(
        index=4,
        gap=gap,
        candle=gap_set.source.candles[4],
        previous_state=(FairValueGapMitigationState.UNTOUCHED),
        new_state=(FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT),
    )

    with pytest.raises(
        ValueError,
        match="state chain",
    ):
        FairValueGapMitigationSnapshot(
            gap_set=gap_set,
            policy=FairValueGapMitigationPolicy(),
            events=(first, invalid_second),
        )


def test_snapshot_rejects_out_of_order_events() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
            ("106", "108", "105.5", "107"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    with pytest.raises(
        ValueError,
        match="ordered",
    ):
        FairValueGapMitigationSnapshot(
            gap_set=gap_set,
            policy=result.policy,
            events=tuple(reversed(result.events)),
        )


def test_gap_lookup_requires_snapshot_membership() -> None:
    first = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )
    second = bullish_gap_set(
        [
            ("107", "108", "105.5", "107"),
        ],
        broker_symbol="XAUUSD",
    )

    result = FairValueGapMitigationTracker().track(first)

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        result.state_for(second.gaps[0])


def test_event_is_immutable() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )

    event = FairValueGapMitigationTracker().track(gap_set).events[0]

    with pytest.raises(FrozenInstanceError):
        event.index = 4


def test_snapshot_is_immutable() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )

    result = FairValueGapMitigationTracker().track(gap_set)

    with pytest.raises(FrozenInstanceError):
        result.events = ()


def test_function_api_delegates() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )

    result = track_fair_value_gap_mitigation(gap_set)

    assert result.count == 1


def test_tracker_alias_methods_delegate() -> None:
    gap_set = bullish_gap_set(
        [
            ("107", "108", "105.75", "107"),
        ]
    )
    tracker = FairValueGapMitigationTracker()

    assert tracker.evaluate(gap_set) == tracker.track(gap_set)
    assert tracker.detect(gap_set) == tracker.track(gap_set)


def test_public_aliases_are_preserved() -> None:
    assert FVGMitigationState is FairValueGapMitigationState
    assert FVGMitigationPolicy is FairValueGapMitigationPolicy
    assert FVGMitigationEvent is FairValueGapMitigationEvent
    assert FVGMitigationSnapshot is FairValueGapMitigationSnapshot
    assert FVGMitigationTracker is FairValueGapMitigationTracker
