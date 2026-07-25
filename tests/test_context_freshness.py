from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.timeframes import get_timeframe_spec
from app.strategy.context_freshness import (
    ContextFreshnessDecision,
    ContextFreshnessError,
    ContextFreshnessErrorReason,
    ContextFreshnessPolicy,
    ContextFreshnessReason,
    ContextFreshnessStatus,
    FreshnessDecision,
    FreshnessDetail,
    FreshnessGate,
    FreshnessPolicy,
    FreshnessReason,
    FreshnessStatus,
    MultiTimeframeContextFreshnessGate,
    MultiTimeframeFreshnessGate,
    TimeframeFreshness,
    evaluate_context_freshness,
)
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiTimeframeContextBuilder,
    MultiTimeframeContextSnapshot,
)

OBSERVED_AT = datetime(
    2026,
    7,
    25,
    20,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    timeframe: TimeframeName,
    *,
    end_at: datetime = OBSERVED_AT,
    count: int = 8,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    candles: list[ClosedCandle] = []
    first_open = end_at - duration * count

    for index in range(count):
        open_time = first_open + duration * index

        if index % 2 == 0:
            open_price = Decimal("100")
            close_price = Decimal("101")
        else:
            open_price = Decimal("101")
            close_price = Decimal("100")

        candles.append(
            ClosedCandle(
                broker_symbol=broker_symbol,
                timeframe=timeframe,
                open_time=open_time,
                observed_at=open_time + duration,
                open=open_price,
                high=Decimal("102"),
                low=Decimal("98"),
                close=close_price,
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


def snapshot_with_offsets(
    offsets: dict[
        TimeframeName,
        timedelta,
    ]
    | None = None,
) -> MultiTimeframeContextSnapshot:
    selected_offsets = offsets or {}

    for timeframe, offset in selected_offsets.items():
        if not isinstance(timeframe, TimeframeName):
            raise ValueError("Offset keys must be TimeframeName members.")

        if not isinstance(offset, timedelta):
            raise ValueError("Freshness offsets must be timedeltas.")

        if offset < timedelta(0):
            raise ValueError("Freshness offsets cannot be negative.")

    residuals = tuple(
        (offset % get_timeframe_spec(timeframe).duration)
        for timeframe, offset in selected_offsets.items()
    )
    shared_residual = max(
        residuals,
        default=timedelta(0),
    )

    mapping: dict[
        TimeframeName,
        ClosedCandleSeries,
    ] = {}

    for timeframe in GOLD_TIMEFRAME_HIERARCHY:
        duration = get_timeframe_spec(timeframe).duration
        requested_offset = selected_offsets.get(
            timeframe,
            timedelta(0),
        )
        whole_candle_lag = requested_offset // duration
        aligned_end_at = OBSERVED_AT - duration * whole_candle_lag

        mapping[timeframe] = create_series(
            timeframe,
            end_at=aligned_end_at,
        )

    snapshot = MultiTimeframeContextBuilder().build(mapping)

    if shared_residual == timedelta(0):
        return snapshot

    return replace(
        snapshot,
        observed_at=(snapshot.observed_at + shared_residual),
    )


def fresh_snapshot() -> MultiTimeframeContextSnapshot:
    return snapshot_with_offsets()


def test_default_policy_allows_one_candle_lag() -> None:
    policy = ContextFreshnessPolicy()

    assert policy.maximum_lag_candles == (
        (TimeframeName.H4, 1),
        (TimeframeName.H1, 1),
        (TimeframeName.M15, 1),
        (TimeframeName.M5, 1),
    )

    for timeframe in GOLD_TIMEFRAME_HIERARCHY:
        assert policy.maximum_for(timeframe) == 1


@pytest.mark.parametrize(
    "maximum_lag_candles",
    [
        (
            (TimeframeName.H1, 1),
            (TimeframeName.H4, 1),
            (TimeframeName.M15, 1),
            (TimeframeName.M5, 1),
        ),
        (
            (TimeframeName.H4, 1),
            (TimeframeName.H1, 1),
            (TimeframeName.M15, 1),
        ),
        (
            (TimeframeName.H4, 1),
            (TimeframeName.H1, 1),
            (TimeframeName.M15, 1),
            (TimeframeName.H4, 1),
        ),
        (
            ("H4", 1),
            ("H1", 1),
            ("M15", 1),
            ("M5", 1),
        ),
        (
            (TimeframeName.H4, -1),
            (TimeframeName.H1, 1),
            (TimeframeName.M15, 1),
            (TimeframeName.M5, 1),
        ),
        (
            (TimeframeName.H4, True),
            (TimeframeName.H1, 1),
            (TimeframeName.M15, 1),
            (TimeframeName.M5, 1),
        ),
    ],
)
def test_invalid_policy_is_rejected(
    maximum_lag_candles: tuple[object, ...],
) -> None:
    with pytest.raises(ValueError):
        ContextFreshnessPolicy(maximum_lag_candles=maximum_lag_candles)


def test_policy_lookup_rejects_unknown_timeframe() -> None:
    with pytest.raises(ValueError):
        ContextFreshnessPolicy().maximum_for("M1")


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="ContextFreshnessPolicy",
    ):
        MultiTimeframeFreshnessGate(policy="invalid")


def test_invalid_context_is_fail_safe() -> None:
    with pytest.raises(
        ContextFreshnessError,
        match="INVALID_CONTEXT",
    ) as captured:
        MultiTimeframeFreshnessGate().evaluate("invalid")

    assert captured.value.reason == (ContextFreshnessErrorReason.INVALID_CONTEXT)


def test_synchronized_context_is_ready() -> None:
    decision = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot())

    assert decision.status == (ContextFreshnessStatus.READY)
    assert decision.reason == (ContextFreshnessReason.ALL_TIMEFRAMES_FRESH)
    assert decision.is_ready is True
    assert decision.is_blocked is False


def test_synchronized_context_has_zero_lag() -> None:
    decision = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot())

    assert all(detail.lag == timedelta(0) for detail in decision.details)
    assert all(detail.lag_candle_fraction == Decimal("0") for detail in decision.details)


@pytest.mark.parametrize(
    "timeframe",
    GOLD_TIMEFRAME_HIERARCHY,
)
def test_exact_one_candle_lag_is_fresh(
    timeframe: TimeframeName,
) -> None:
    duration = get_timeframe_spec(timeframe).duration
    snapshot = snapshot_with_offsets({timeframe: duration})

    decision = MultiTimeframeFreshnessGate().evaluate(snapshot)
    detail = decision.detail_for(timeframe)

    assert detail.lag == duration
    assert detail.maximum_lag == duration
    assert detail.lag_candle_fraction == Decimal("1")
    assert detail.is_fresh is True
    assert timeframe not in decision.stale_timeframes


@pytest.mark.parametrize(
    "timeframe",
    GOLD_TIMEFRAME_HIERARCHY,
)
def test_lag_above_one_candle_is_stale(
    timeframe: TimeframeName,
) -> None:
    duration = get_timeframe_spec(timeframe).duration
    snapshot = snapshot_with_offsets({timeframe: (duration + timedelta(seconds=1))})

    decision = MultiTimeframeFreshnessGate().evaluate(snapshot)
    detail = decision.detail_for(timeframe)

    assert decision.is_blocked is True
    assert decision.reason == (ContextFreshnessReason.STALE_TIMEFRAME)
    assert detail.is_stale is True
    assert timeframe in decision.stale_timeframes
    assert detail.excess_lag == timedelta(seconds=1)


def test_multiple_stale_timeframes_preserve_order() -> None:
    snapshot = snapshot_with_offsets(
        {
            TimeframeName.H4: timedelta(hours=8),
            TimeframeName.M15: timedelta(minutes=31),
        }
    )

    decision = MultiTimeframeFreshnessGate().evaluate(snapshot)

    assert decision.stale_timeframes == (
        TimeframeName.H4,
        TimeframeName.M15,
    )
    assert decision.fresh_timeframes == (
        TimeframeName.H1,
        TimeframeName.M5,
    )
    assert decision.stale_count == 2
    assert decision.fresh_count == 2


def test_zero_lag_policy_requires_exact_synchronization() -> None:
    policy = ContextFreshnessPolicy(
        maximum_lag_candles=(
            (TimeframeName.H4, 1),
            (TimeframeName.H1, 1),
            (TimeframeName.M15, 1),
            (TimeframeName.M5, 0),
        )
    )
    snapshot = snapshot_with_offsets({TimeframeName.M5: timedelta(seconds=1)})

    decision = MultiTimeframeFreshnessGate(policy).evaluate(snapshot)

    assert decision.stale_timeframes == (TimeframeName.M5,)


def test_custom_timeframe_threshold_is_respected() -> None:
    policy = ContextFreshnessPolicy(
        maximum_lag_candles=(
            (TimeframeName.H4, 2),
            (TimeframeName.H1, 1),
            (TimeframeName.M15, 1),
            (TimeframeName.M5, 1),
        )
    )
    snapshot = snapshot_with_offsets({TimeframeName.H4: timedelta(hours=8)})

    decision = MultiTimeframeFreshnessGate(policy).evaluate(snapshot)

    assert decision.is_ready is True
    assert decision.detail_for(TimeframeName.H4).lag_candle_fraction == Decimal("2")


def test_custom_threshold_still_blocks_excess() -> None:
    policy = ContextFreshnessPolicy(
        maximum_lag_candles=(
            (TimeframeName.H4, 2),
            (TimeframeName.H1, 1),
            (TimeframeName.M15, 1),
            (TimeframeName.M5, 1),
        )
    )
    snapshot = snapshot_with_offsets(
        {TimeframeName.H4: (timedelta(hours=8) + timedelta(seconds=1))}
    )

    decision = MultiTimeframeFreshnessGate(policy).evaluate(snapshot)

    assert decision.is_blocked is True
    assert decision.stale_timeframes == (TimeframeName.H4,)


def test_detail_metrics_are_exact() -> None:
    snapshot = snapshot_with_offsets({TimeframeName.M15: timedelta(minutes=30)})

    detail = MultiTimeframeFreshnessGate().evaluate(snapshot).detail_for(TimeframeName.M15)

    assert detail.timeframe == TimeframeName.M15
    assert detail.lag == timedelta(minutes=30)
    assert detail.maximum_lag == timedelta(minutes=15)
    assert detail.lag_candle_fraction == Decimal("2")
    assert detail.excess_lag == timedelta(minutes=15)
    assert detail.stable_id.startswith("M15:")


def test_worst_timeframe_uses_lag_fraction() -> None:
    snapshot = snapshot_with_offsets(
        {
            TimeframeName.H4: timedelta(hours=4),
            TimeframeName.M5: timedelta(minutes=10),
        }
    )

    decision = MultiTimeframeFreshnessGate().evaluate(snapshot)

    assert decision.worst_timeframe == (TimeframeName.M5)
    assert decision.maximum_lag_candle_fraction == Decimal("2")


def test_equal_worst_fraction_prefers_hierarchy_order() -> None:
    snapshot = snapshot_with_offsets(
        {
            TimeframeName.H4: timedelta(hours=8),
            TimeframeName.H1: timedelta(hours=2),
        }
    )

    decision = MultiTimeframeFreshnessGate().evaluate(snapshot)

    assert decision.worst_timeframe == (TimeframeName.H4)


def test_detail_lookup_is_available() -> None:
    decision = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot())

    assert decision.detail_for(TimeframeName.H1) is decision.details[1]


def test_invalid_detail_lookup_is_rejected() -> None:
    decision = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot())

    with pytest.raises(ValueError):
        decision.detail_for("M1")


def test_decision_preserves_context_metadata() -> None:
    decision = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot())

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.stable_id == (f"{decision.context.stable_id}:FRESHNESS:READY:NONE")


def test_stale_stable_id_lists_timeframes() -> None:
    snapshot = snapshot_with_offsets(
        {
            TimeframeName.H4: timedelta(hours=8),
            TimeframeName.M5: timedelta(minutes=10),
        }
    )

    decision = MultiTimeframeFreshnessGate().evaluate(snapshot)

    assert decision.stable_id.endswith("FRESHNESS:BLOCKED:H4,M5")


def test_manual_detail_rejects_future_close() -> None:
    with pytest.raises(
        ValueError,
        match="after observed_at",
    ):
        TimeframeFreshness(
            timeframe=TimeframeName.M5,
            latest_close=(OBSERVED_AT + timedelta(minutes=5)),
            observed_at=OBSERVED_AT,
            candle_duration=timedelta(minutes=5),
            maximum_lag_candles=1,
        )


def test_manual_detail_rejects_wrong_duration() -> None:
    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        TimeframeFreshness(
            timeframe=TimeframeName.H1,
            latest_close=OBSERVED_AT,
            observed_at=OBSERVED_AT,
            candle_duration=timedelta(minutes=5),
            maximum_lag_candles=1,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot())

    with pytest.raises(
        ValueError,
        match="status",
    ):
        replace(
            decision,
            status=ContextFreshnessStatus.BLOCKED,
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot())

    with pytest.raises(
        ValueError,
        match="reason",
    ):
        replace(
            decision,
            reason=(ContextFreshnessReason.STALE_TIMEFRAME),
        )


def test_manual_decision_rejects_modified_details() -> None:
    decision = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot())
    modified = replace(
        decision.details[0],
        maximum_lag_candles=2,
    )

    with pytest.raises(
        ValueError,
        match="do not match",
    ):
        replace(
            decision,
            details=(
                modified,
                *decision.details[1:],
            ),
        )


def test_detail_is_immutable() -> None:
    detail = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot()).details[0]

    with pytest.raises(FrozenInstanceError):
        detail.maximum_lag_candles = 2


def test_decision_is_immutable() -> None:
    decision = MultiTimeframeFreshnessGate().evaluate(fresh_snapshot())

    with pytest.raises(FrozenInstanceError):
        decision.status = ContextFreshnessStatus.BLOCKED


def test_policy_is_immutable() -> None:
    policy = ContextFreshnessPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.maximum_lag_candles = ()


def test_evaluation_is_deterministic() -> None:
    gate = MultiTimeframeFreshnessGate()
    snapshot = fresh_snapshot()

    assert gate.evaluate(snapshot) == gate.evaluate(snapshot)


def test_function_api_delegates() -> None:
    decision = evaluate_context_freshness(fresh_snapshot())

    assert decision.is_ready is True


def test_gate_alias_methods_delegate() -> None:
    gate = MultiTimeframeFreshnessGate()
    snapshot = fresh_snapshot()

    assert gate.check(snapshot) == gate.evaluate(snapshot)
    assert gate.decide(snapshot) == gate.evaluate(snapshot)


def test_public_aliases_are_preserved() -> None:
    assert FreshnessDecision is ContextFreshnessDecision
    assert FreshnessDetail is TimeframeFreshness
    assert FreshnessGate is MultiTimeframeFreshnessGate
    assert FreshnessPolicy is ContextFreshnessPolicy
    assert FreshnessReason is ContextFreshnessReason
    assert FreshnessStatus is ContextFreshnessStatus
    assert MultiTimeframeContextFreshnessGate is MultiTimeframeFreshnessGate
