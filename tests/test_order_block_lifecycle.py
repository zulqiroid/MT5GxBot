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
    DisplacementDirection,
    DisplacementImpulse,
    DisplacementPolicy,
    DisplacementSet,
)
from app.strategy.order_block_lifecycle import (
    OBLifecycleEvent,
    OBLifecycleEventKind,
    OBLifecyclePolicy,
    OBLifecycleSnapshot,
    OBLifecycleState,
    OBLifecycleTracker,
    OrderBlockLifecycleError,
    OrderBlockLifecycleErrorReason,
    OrderBlockLifecycleEvent,
    OrderBlockLifecycleEventKind,
    OrderBlockLifecyclePolicy,
    OrderBlockLifecycleSnapshot,
    OrderBlockLifecycleState,
    OrderBlockLifecycleTracker,
    track_order_block_lifecycle,
)
from app.strategy.order_blocks import (
    OrderBlockDetector,
    OrderBlockDirection,
    OrderBlockPolicy,
    OrderBlockSet,
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


def create_order_block_set(
    rows: list[tuple[str, str, str, str]],
    *,
    direction: DisplacementDirection,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> OrderBlockSet:
    displacement_policy = DisplacementPolicy(lookback_candles=2)
    series = create_series(
        rows,
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )
    prior = series.candles[:2]
    baseline = sum(
        (candle.high - candle.low for candle in prior),
        start=Decimal("0"),
    ) / Decimal("2")
    impulse = DisplacementImpulse(
        index=2,
        direction=direction,
        candle=series.candles[2],
        baseline_average_range=baseline,
    )
    displacement_set = DisplacementSet(
        source=series,
        policy=displacement_policy,
        impulses=(impulse,),
    )

    return OrderBlockDetector(OrderBlockPolicy()).detect(displacement_set)


def bullish_block_set(
    post_rows: list[tuple[str, str, str, str]] | None = None,
    *,
    timeframe: TimeframeName = TimeframeName.M5,
    broker_symbol: str = "XAUUSDm",
) -> OrderBlockSet:
    rows = [
        ("100", "102", "98", "101"),
        ("101", "103", "99", "100"),
        ("100", "110", "99", "109"),
    ]

    if post_rows is not None:
        rows.extend(post_rows)

    return create_order_block_set(
        rows,
        direction=DisplacementDirection.BULLISH,
        timeframe=timeframe,
        broker_symbol=broker_symbol,
    )


def bearish_block_set(
    post_rows: list[tuple[str, str, str, str]] | None = None,
) -> OrderBlockSet:
    rows = [
        ("100", "102", "98", "99"),
        ("99", "103", "98", "102"),
        ("102", "103", "91", "92"),
    ]

    if post_rows is not None:
        rows.extend(post_rows)

    return create_order_block_set(
        rows,
        direction=DisplacementDirection.BEARISH,
    )


def test_default_policy_is_conservative() -> None:
    policy = OrderBlockLifecyclePolicy()

    assert policy.minimum_mitigation_penetration == Decimal("0")
    assert policy.minimum_breaker_penetration == Decimal("0")
    assert policy.require_breaker_close_rejection is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"minimum_mitigation_penetration": "-0.01"},
        {"minimum_mitigation_penetration": "NaN"},
        {"minimum_mitigation_penetration": True},
        {"minimum_breaker_penetration": "-0.01"},
        {"minimum_breaker_penetration": "Infinity"},
        {"minimum_breaker_penetration": True},
        {"require_breaker_close_rejection": 1},
    ],
)
def test_invalid_policy_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        OrderBlockLifecyclePolicy(**overrides)


def test_bullish_partial_mitigation_is_detected() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.count == 1
    assert result.state_for(block) == (OrderBlockLifecycleState.PARTIALLY_MITIGATED)


def test_bearish_partial_mitigation_is_detected() -> None:
    blocks = bearish_block_set(
        [
            ("97", "99", "96", "97.5"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.state_for(block) == (OrderBlockLifecycleState.PARTIALLY_MITIGATED)


def test_exact_proximal_touch_is_not_mitigation() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "103", "104"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.events == ()


def test_exact_mitigation_threshold_is_rejected() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )
    policy = OrderBlockLifecyclePolicy(minimum_mitigation_penetration="0.5")

    result = OrderBlockLifecycleTracker(policy).track(blocks)

    assert result.events == ()


def test_mitigation_above_threshold_is_detected() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )
    policy = OrderBlockLifecyclePolicy(minimum_mitigation_penetration="0.49")

    result = OrderBlockLifecycleTracker(policy).track(blocks)

    assert result.count == 1


def test_exact_distal_wick_is_full_mitigation() -> None:
    blocks = bullish_block_set(
        [
            ("102", "104", "99", "100"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.state_for(block) == (OrderBlockLifecycleState.FULLY_MITIGATED)
    assert result.mitigation_fraction_for(block) == Decimal("1")


def test_bearish_exact_distal_wick_is_full_mitigation() -> None:
    blocks = bearish_block_set(
        [
            ("100", "103", "97", "102"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.state_for(block) == (OrderBlockLifecycleState.FULLY_MITIGATED)


def test_bullish_close_below_distal_invalidates() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.state_for(block) == (OrderBlockLifecycleState.INVALIDATED)
    assert result.events[0].is_invalidation is True


def test_bearish_close_above_distal_invalidates() -> None:
    blocks = bearish_block_set(
        [
            ("100", "105", "99", "104"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.is_invalidated(block) is True


def test_exact_distal_close_does_not_invalidate() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "99", "99"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.state_for(block) == (OrderBlockLifecycleState.FULLY_MITIGATED)
    assert result.invalidation_event(block) is None


def test_invalidation_supersedes_same_candle_mitigation() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.count == 1
    assert result.events[0].kind == (OrderBlockLifecycleEventKind.INVALIDATION)


def test_bullish_ob_becomes_bearish_breaker() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
            ("98", "100", "97", "98.5"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)
    breaker = result.breaker_event(block)

    assert breaker is not None
    assert result.is_breaker(block) is True
    assert breaker.breaker_direction == (OrderBlockDirection.BEARISH)


def test_bearish_ob_becomes_bullish_breaker() -> None:
    blocks = bearish_block_set(
        [
            ("100", "105", "99", "104"),
            ("104", "105", "101", "104"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)
    breaker = result.breaker_event(block)

    assert breaker is not None
    assert breaker.breaker_direction == (OrderBlockDirection.BULLISH)


def test_breaker_requires_later_candle() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.count == 1
    assert result.breaker_blocks == ()


def test_exact_breaker_boundary_touch_is_rejected() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
            ("98", "99", "97", "98.5"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.breaker_blocks == ()


def test_exact_breaker_threshold_is_rejected() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
            ("98", "100", "97", "98.5"),
        ]
    )
    policy = OrderBlockLifecyclePolicy(minimum_breaker_penetration="1")

    result = OrderBlockLifecycleTracker(policy).track(blocks)

    assert result.breaker_blocks == ()


def test_breaker_above_threshold_is_detected() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
            ("98", "100.01", "97", "98.5"),
        ]
    )
    policy = OrderBlockLifecyclePolicy(minimum_breaker_penetration="1")

    result = OrderBlockLifecycleTracker(policy).track(blocks)

    assert len(result.breaker_blocks) == 1


def test_breaker_requires_close_rejection_by_default() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
            ("98", "100", "97", "99.5"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.breaker_blocks == ()


def test_wick_only_breaker_mode_is_available() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
            ("98", "100", "97", "99.5"),
        ]
    )
    policy = OrderBlockLifecyclePolicy(require_breaker_close_rejection=False)

    result = OrderBlockLifecycleTracker(policy).track(blocks)

    assert len(result.breaker_blocks) == 1
    assert result.breaker_event(blocks.blocks[0]).breaker_close_rejected is False


def test_complete_lifecycle_is_ordered() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
            ("102", "104", "99", "100"),
            ("101", "102", "97", "98"),
            ("98", "100", "97", "98.5"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert [event.index for event in result.events] == [3, 4, 5, 6]
    assert [event.new_state for event in result.events] == [
        OrderBlockLifecycleState.PARTIALLY_MITIGATED,
        OrderBlockLifecycleState.FULLY_MITIGATED,
        OrderBlockLifecycleState.INVALIDATED,
        OrderBlockLifecycleState.BREAKER_CONFIRMED,
    ]


def test_full_mitigation_can_later_invalidate() -> None:
    blocks = bullish_block_set(
        [
            ("102", "104", "99", "100"),
            ("101", "102", "97", "98"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.was_mitigated(block) is True
    assert result.is_invalidated(block) is True
    assert result.fully_mitigated_blocks == (block,)


def test_same_state_deeper_progress_is_recorded() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.8", "104"),
            ("104", "105", "102.5", "104"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.count == 2
    assert result.events[1].is_progress_only is True
    assert result.mitigation_fraction_for(blocks.blocks[0]) == Decimal("0.125")


def test_shallower_revisit_does_not_add_event() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
            ("104", "105", "102.8", "104"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.count == 1


def test_breaker_confirmation_blocks_repeat_events() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
            ("98", "100", "97", "98.5"),
            ("98", "102", "96", "98"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.count == 2
    assert result.events[-1].is_breaker is True


def test_mitigation_event_exposes_exact_metrics() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )

    event = OrderBlockLifecycleTracker().track(blocks).events[0]

    assert event.raw_mitigation_penetration == Decimal("0.5")
    assert event.zone_mitigation_penetration == Decimal("0.5")
    assert event.mitigation_fraction == Decimal("0.125")
    assert event.mitigation_percentage == Decimal("12.500")
    assert event.confirmed_at == event.candle.close_time
    assert event.is_mitigation is True


def test_invalidation_event_exposes_distance() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
        ]
    )

    event = OrderBlockLifecycleTracker().track(blocks).events[0]

    assert event.invalidation_distance == Decimal("1")
    assert event.is_invalidation is True


def test_breaker_event_exposes_context() -> None:
    blocks = bullish_block_set(
        [
            ("101", "102", "97", "98"),
            ("98", "100", "97", "98.5"),
        ]
    )

    event = OrderBlockLifecycleTracker().track(blocks).events[-1]

    assert event.breaker_penetration == Decimal("1")
    assert event.breaker_close_rejected is True
    assert event.is_breaker is True
    assert ":BREAKER:4:" in event.stable_id


def test_snapshot_filters_states() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.untouched_blocks == ()
    assert result.mitigated_blocks == (block,)
    assert result.partially_mitigated_blocks == (block,)
    assert result.fully_mitigated_blocks == ()
    assert result.invalidated_blocks == ()
    assert result.breaker_blocks == ()
    assert result.active_blocks == (block,)
    assert result.events_at(3) == result.events
    assert result.events_at(2) == ()


def test_unvisited_block_remains_active() -> None:
    blocks = bullish_block_set(
        [
            ("105", "106", "103", "105"),
        ]
    )
    block = blocks.blocks[0]

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.untouched_blocks == (block,)
    assert result.mitigated_blocks == ()
    assert result.active_blocks == (block,)
    assert result.latest is None
    assert result.mitigation_fraction_for(block) == Decimal("0")


def test_result_preserves_market_context() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ],
        timeframe=TimeframeName.H1,
        broker_symbol="XAUUSD.pro",
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    assert result.broker_symbol == "XAUUSD.pro"
    assert result.timeframe == TimeframeName.H1


def test_invalid_order_block_set_type_is_fail_safe() -> None:
    with pytest.raises(
        OrderBlockLifecycleError,
        match="INVALID_ORDER_BLOCK_SET",
    ) as captured:
        OrderBlockLifecycleTracker().track("invalid")

    assert captured.value.reason == (OrderBlockLifecycleErrorReason.INVALID_ORDER_BLOCK_SET)


def test_tracker_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="OrderBlockLifecyclePolicy",
    ):
        OrderBlockLifecycleTracker(policy="invalid")


def test_event_rejects_confirmation_candle() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )
    block = blocks.blocks[0]

    with pytest.raises(
        ValueError,
        match="after",
    ):
        OrderBlockLifecycleEvent(
            index=block.confirmation_index,
            kind=(OrderBlockLifecycleEventKind.MITIGATION),
            block=block,
            candle=block.displacement.candle,
            previous_state=(OrderBlockLifecycleState.UNTOUCHED),
            new_state=(OrderBlockLifecycleState.PARTIALLY_MITIGATED),
        )


def test_event_rejects_wrong_mitigation_state() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )
    block = blocks.blocks[0]

    with pytest.raises(
        ValueError,
        match="deepest mitigation state",
    ):
        OrderBlockLifecycleEvent(
            index=3,
            kind=(OrderBlockLifecycleEventKind.MITIGATION),
            block=block,
            candle=blocks.source.candles[3],
            previous_state=(OrderBlockLifecycleState.UNTOUCHED),
            new_state=(OrderBlockLifecycleState.FULLY_MITIGATED),
        )


def test_snapshot_rejects_invalid_state_chain() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
            ("98", "100", "97", "98.5"),
        ]
    )
    block = blocks.blocks[0]

    first = OrderBlockLifecycleEvent(
        index=3,
        kind=OrderBlockLifecycleEventKind.MITIGATION,
        block=block,
        candle=blocks.source.candles[3],
        previous_state=(OrderBlockLifecycleState.UNTOUCHED),
        new_state=(OrderBlockLifecycleState.PARTIALLY_MITIGATED),
    )
    invalid_breaker = OrderBlockLifecycleEvent(
        index=4,
        kind=OrderBlockLifecycleEventKind.BREAKER,
        block=block,
        candle=blocks.source.candles[4],
        previous_state=(OrderBlockLifecycleState.INVALIDATED),
        new_state=(OrderBlockLifecycleState.BREAKER_CONFIRMED),
    )

    with pytest.raises(
        ValueError,
        match="state chain",
    ):
        OrderBlockLifecycleSnapshot(
            order_blocks=blocks,
            policy=OrderBlockLifecyclePolicy(),
            events=(first, invalid_breaker),
        )


def test_snapshot_rejects_out_of_order_events() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
            ("101", "102", "97", "98"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    with pytest.raises(
        ValueError,
        match="ordered",
    ):
        OrderBlockLifecycleSnapshot(
            order_blocks=blocks,
            policy=result.policy,
            events=tuple(reversed(result.events)),
        )


def test_block_lookup_requires_membership() -> None:
    first = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )
    second = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ],
        broker_symbol="XAUUSD",
    )

    result = OrderBlockLifecycleTracker().track(first)

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        result.state_for(second.blocks[0])


def test_event_is_immutable() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )

    event = OrderBlockLifecycleTracker().track(blocks).events[0]

    with pytest.raises(FrozenInstanceError):
        event.index = 4


def test_snapshot_is_immutable() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )

    result = OrderBlockLifecycleTracker().track(blocks)

    with pytest.raises(FrozenInstanceError):
        result.events = ()


def test_function_api_delegates() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )

    result = track_order_block_lifecycle(blocks)

    assert result.count == 1


def test_tracker_alias_methods_delegate() -> None:
    blocks = bullish_block_set(
        [
            ("104", "105", "102.5", "104"),
        ]
    )
    tracker = OrderBlockLifecycleTracker()

    assert tracker.evaluate(blocks) == tracker.track(blocks)
    assert tracker.detect(blocks) == tracker.track(blocks)


def test_public_aliases_are_preserved() -> None:
    assert OBLifecycleState is OrderBlockLifecycleState
    assert OBLifecycleEventKind is OrderBlockLifecycleEventKind
    assert OBLifecyclePolicy is OrderBlockLifecyclePolicy
    assert OBLifecycleEvent is OrderBlockLifecycleEvent
    assert OBLifecycleSnapshot is OrderBlockLifecycleSnapshot
    assert OBLifecycleTracker is OrderBlockLifecycleTracker
