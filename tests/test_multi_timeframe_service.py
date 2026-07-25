from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.closed_candle_service import (
    CandleDataErrorReason,
    CandleDataServiceError,
    CandleDataSnapshot,
    CandleLoadRequest,
)
from app.market.multi_timeframe_service import (
    MultiTimeframeDataErrorReason,
    MultiTimeframeDataServiceError,
    MultiTimeframeLoadRequest,
    MultiTimeframeMarketDataService,
    MultiTimeframeMarketSnapshot,
    StrategyTimeframeService,
    TimeframeMarketSlice,
)
from app.market.timeframes import (
    SUPPORTED_STRATEGY_TIMEFRAMES,
    get_timeframe_spec,
)

NOW = datetime(
    2026,
    7,
    25,
    12,
    37,
    tzinfo=timezone.utc,
)


LATEST_OPEN_TIMES = {
    TimeframeName.H4: datetime(
        2026,
        7,
        25,
        8,
        0,
        tzinfo=timezone.utc,
    ),
    TimeframeName.H1: datetime(
        2026,
        7,
        25,
        11,
        0,
        tzinfo=timezone.utc,
    ),
    TimeframeName.M15: datetime(
        2026,
        7,
        25,
        12,
        15,
        tzinfo=timezone.utc,
    ),
    TimeframeName.M5: datetime(
        2026,
        7,
        25,
        12,
        30,
        tzinfo=timezone.utc,
    ),
}


def create_closed_candle(
    *,
    timeframe: TimeframeName,
    open_time: datetime,
    broker_symbol: str = "XAUUSDm",
) -> ClosedCandle:
    return ClosedCandle(
        broker_symbol=broker_symbol,
        timeframe=timeframe,
        open_time=open_time,
        observed_at=NOW,
        open="2400.00",
        high="2405.00",
        low="2398.00",
        close="2403.00",
        tick_volume=1000,
        spread=20,
        real_volume=0,
    )


def create_data_snapshot(
    timeframe: TimeframeName,
    *,
    count: int = 2,
    broker_symbol: str = "XAUUSDm",
    latest_open_time: datetime | None = None,
    loaded_at: datetime = NOW,
    create_gap: bool = False,
) -> CandleDataSnapshot:
    latest_open = latest_open_time or LATEST_OPEN_TIMES[timeframe]
    duration = get_timeframe_spec(timeframe).duration

    previous_open = latest_open - duration

    if create_gap:
        previous_open = latest_open - (duration * 2)

    candles = (
        create_closed_candle(
            timeframe=timeframe,
            open_time=previous_open,
            broker_symbol=broker_symbol,
        ),
        create_closed_candle(
            timeframe=timeframe,
            open_time=latest_open,
            broker_symbol=broker_symbol,
        ),
    )

    if count == 1:
        candles = (candles[-1],)

    request = CandleLoadRequest(
        broker_symbol=broker_symbol,
        timeframe=timeframe,
        closed_count=count,
        include_forming=False,
        require_contiguous=False,
    )

    series = ClosedCandleSeries(
        broker_symbol=broker_symbol,
        timeframe=timeframe,
        candles=candles,
    )

    from app.market.closed_candle import CandleWindow

    return CandleDataSnapshot(
        request=request,
        window=CandleWindow(closed=series),
        loaded_at=loaded_at,
    )


def create_request(
    **overrides: object,
) -> MultiTimeframeLoadRequest:
    values: dict[str, object] = {
        "broker_symbol": "XAUUSDm",
        "h4_count": 2,
        "h1_count": 2,
        "m15_count": 2,
        "m5_count": 2,
        "require_contiguous": True,
        "max_staleness_bars": 1,
        "reject_stale": True,
    }
    values.update(overrides)

    return MultiTimeframeLoadRequest(**values)


class FakeClosedCandleReader:
    def __init__(self) -> None:
        self.requests: list[CandleLoadRequest] = []
        self.exception: Exception | None = None
        self.invalid_result: Any | None = None

        self.snapshots: dict[
            TimeframeName,
            CandleDataSnapshot,
        ] = {
            timeframe: create_data_snapshot(timeframe)
            for timeframe in SUPPORTED_STRATEGY_TIMEFRAMES
        }

    def read_snapshot(
        self,
        request: CandleLoadRequest,
    ) -> Any:
        self.requests.append(request)

        if self.exception is not None:
            raise self.exception

        if self.invalid_result is not None:
            return self.invalid_result

        return self.snapshots[request.timeframe]


def create_service(
    reader: FakeClosedCandleReader | None = None,
    clock=lambda: NOW,
) -> tuple[
    MultiTimeframeMarketDataService,
    FakeClosedCandleReader,
]:
    selected_reader = reader or FakeClosedCandleReader()

    return (
        MultiTimeframeMarketDataService(
            candle_reader=selected_reader,
            clock=clock,
        ),
        selected_reader,
    )


def test_request_uses_fixed_timeframe_order() -> None:
    request = create_request()

    assert request.timeframes == (
        TimeframeName.H4,
        TimeframeName.H1,
        TimeframeName.M15,
        TimeframeName.M5,
    )


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [
        (TimeframeName.H4, 2),
        (TimeframeName.H1, 3),
        (TimeframeName.M15, 4),
        (TimeframeName.M5, 5),
    ],
)
def test_request_returns_count_per_timeframe(
    timeframe: TimeframeName,
    expected: int,
) -> None:
    request = create_request(
        h4_count=2,
        h1_count=3,
        m15_count=4,
        m5_count=5,
    )

    assert request.count_for(timeframe) == expected


def test_non_strategy_count_request_is_blocked() -> None:
    request = create_request()

    with pytest.raises(
        ValueError,
        match="not a primary",
    ):
        request.count_for(TimeframeName.M1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"broker_symbol": ""},
        {"h4_count": 0},
        {"h1_count": True},
        {"m15_count": 10_001},
        {"m5_count": -1},
        {"require_contiguous": 1},
        {"max_staleness_bars": 0},
        {"max_staleness_bars": 101},
        {"reject_stale": 0},
    ],
)
def test_invalid_requests_are_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        create_request(**overrides)


def test_service_loads_all_timeframes_in_fixed_order() -> None:
    service, reader = create_service()

    snapshot = service.read_snapshot(create_request())

    assert snapshot.slices[0].timeframe == TimeframeName.H4
    assert snapshot.slices[1].timeframe == TimeframeName.H1
    assert snapshot.slices[2].timeframe == TimeframeName.M15
    assert snapshot.slices[3].timeframe == TimeframeName.M5

    assert [request.timeframe for request in reader.requests] == [
        TimeframeName.H4,
        TimeframeName.H1,
        TimeframeName.M15,
        TimeframeName.M5,
    ]


def test_underlying_requests_are_closed_only() -> None:
    service, reader = create_service()

    service.read_snapshot(create_request())

    assert all(request.include_forming is False for request in reader.requests)


def test_counts_are_forwarded_to_each_timeframe() -> None:
    service, reader = create_service()

    service.read_snapshot(
        create_request(
            h4_count=2,
            h1_count=2,
            m15_count=2,
            m5_count=2,
        )
    )

    assert [request.closed_count for request in reader.requests] == [2, 2, 2, 2]


def test_healthy_snapshot_is_fresh() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(create_request())

    assert snapshot.all_fresh is True
    assert snapshot.stale_timeframes == ()
    assert snapshot.has_gaps is False
    assert snapshot.gap_timeframes == ()


def test_timeframe_properties_are_available() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(create_request())

    assert snapshot.h4.timeframe == TimeframeName.H4
    assert snapshot.h1.timeframe == TimeframeName.H1
    assert snapshot.m15.timeframe == TimeframeName.M15
    assert snapshot.m5.timeframe == TimeframeName.M5


def test_strategy_series_mapping_is_read_only() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(create_request())

    assert snapshot.strategy_series[TimeframeName.M15].count == 2

    with pytest.raises(TypeError):
        snapshot.strategy_series[TimeframeName.M15] = snapshot.m15.closed


def test_latest_close_times_are_exposed() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(create_request())

    assert snapshot.latest_close_times[TimeframeName.M5] == datetime(
        2026,
        7,
        25,
        12,
        35,
        tzinfo=timezone.utc,
    )


def test_stale_timeframe_is_blocked() -> None:
    reader = FakeClosedCandleReader()
    reader.snapshots[TimeframeName.M5] = create_data_snapshot(
        TimeframeName.M5,
        latest_open_time=datetime(
            2026,
            7,
            25,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    service, _ = create_service(reader)

    with pytest.raises(
        MultiTimeframeDataServiceError,
        match="STALE_MARKET_DATA",
    ) as captured:
        service.read_snapshot(create_request())

    assert captured.value.reason == MultiTimeframeDataErrorReason.STALE_MARKET_DATA


def test_stale_timeframe_can_be_observed_without_rejection() -> None:
    reader = FakeClosedCandleReader()
    reader.snapshots[TimeframeName.M5] = create_data_snapshot(
        TimeframeName.M5,
        latest_open_time=datetime(
            2026,
            7,
            25,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    service, _ = create_service(reader)

    snapshot = service.read_snapshot(create_request(reject_stale=False))

    assert snapshot.all_fresh is False
    assert snapshot.stale_timeframes == (TimeframeName.M5,)


def test_larger_staleness_window_can_allow_data() -> None:
    reader = FakeClosedCandleReader()
    reader.snapshots[TimeframeName.M5] = create_data_snapshot(
        TimeframeName.M5,
        latest_open_time=datetime(
            2026,
            7,
            25,
            12,
            25,
            tzinfo=timezone.utc,
        ),
    )

    service, _ = create_service(reader)

    snapshot = service.read_snapshot(create_request(max_staleness_bars=2))

    assert snapshot.all_fresh is True


def test_gap_is_blocked_when_contiguous_required() -> None:
    reader = FakeClosedCandleReader()
    reader.snapshots[TimeframeName.M15] = create_data_snapshot(
        TimeframeName.M15,
        create_gap=True,
    )

    service, _ = create_service(reader)

    with pytest.raises(
        MultiTimeframeDataServiceError,
        match="HISTORY_GAP",
    ) as captured:
        service.read_snapshot(create_request())

    assert captured.value.reason == MultiTimeframeDataErrorReason.HISTORY_GAP


def test_gap_can_be_observed_when_not_required() -> None:
    reader = FakeClosedCandleReader()
    reader.snapshots[TimeframeName.M15] = create_data_snapshot(
        TimeframeName.M15,
        create_gap=True,
    )

    service, _ = create_service(reader)

    snapshot = service.read_snapshot(create_request(require_contiguous=False))

    assert snapshot.has_gaps is True
    assert snapshot.gap_timeframes == (TimeframeName.M15,)


def test_candle_service_error_is_wrapped() -> None:
    reader = FakeClosedCandleReader()
    reader.exception = CandleDataServiceError(
        CandleDataErrorReason.RATES_UNAVAILABLE,
        "Rates unavailable",
    )

    service, _ = create_service(reader)

    with pytest.raises(
        MultiTimeframeDataServiceError,
        match="TIMEFRAME_LOAD_FAILED",
    ) as captured:
        service.read_snapshot(create_request())

    assert captured.value.timeframe == TimeframeName.H4


def test_generic_reader_error_is_wrapped() -> None:
    reader = FakeClosedCandleReader()
    reader.exception = RuntimeError("reader failure")

    service, _ = create_service(reader)

    with pytest.raises(
        MultiTimeframeDataServiceError,
        match="RuntimeError",
    ):
        service.read_snapshot(create_request())


def test_invalid_reader_result_is_blocked() -> None:
    reader = FakeClosedCandleReader()
    reader.invalid_result = "invalid"

    service, _ = create_service(reader)

    with pytest.raises(
        MultiTimeframeDataServiceError,
        match="INVALID_TIMEFRAME_SNAPSHOT",
    ):
        service.read_snapshot(create_request())


def test_symbol_mismatch_is_blocked() -> None:
    reader = FakeClosedCandleReader()
    reader.snapshots[TimeframeName.H1] = create_data_snapshot(
        TimeframeName.H1,
        broker_symbol="XAUUSD",
    )

    service, _ = create_service(reader)

    with pytest.raises(
        MultiTimeframeDataServiceError,
        match="SYMBOL_MISMATCH",
    ):
        service.read_snapshot(create_request())


def test_future_loaded_snapshot_is_blocked() -> None:
    reader = FakeClosedCandleReader()
    reader.snapshots[TimeframeName.M5] = create_data_snapshot(
        TimeframeName.M5,
        loaded_at=NOW + timedelta(seconds=1),
    )

    service, _ = create_service(reader)

    with pytest.raises(
        MultiTimeframeDataServiceError,
        match="SNAPSHOT_FROM_FUTURE",
    ):
        service.read_snapshot(create_request())


def test_slice_rejects_forming_data() -> None:
    data = create_data_snapshot(TimeframeName.M15)

    from app.market.closed_candle import (
        CandleWindow,
        FormingCandle,
    )

    forming_open = data.closed.latest.close_time
    forming = FormingCandle(
        broker_symbol="XAUUSDm",
        timeframe=TimeframeName.M15,
        open_time=forming_open,
        observed_at=forming_open + timedelta(minutes=5),
        open="2400",
        high="2402",
        low="2399",
        close="2401",
        tick_volume=100,
        spread=20,
        real_volume=0,
    )

    data_with_forming = CandleDataSnapshot(
        request=CandleLoadRequest(
            broker_symbol="XAUUSDm",
            timeframe=TimeframeName.M15,
            closed_count=2,
            include_forming=True,
        ),
        window=CandleWindow(
            closed=data.closed,
            forming=forming,
        ),
        loaded_at=NOW,
    )

    with pytest.raises(
        ValueError,
        match="forming candles",
    ):
        TimeframeMarketSlice(
            timeframe=TimeframeName.M15,
            data=data_with_forming,
        )


def test_snapshot_reorders_valid_slices() -> None:
    request = create_request()

    slices = tuple(
        TimeframeMarketSlice(
            timeframe=timeframe,
            data=create_data_snapshot(timeframe),
        )
        for timeframe in reversed(SUPPORTED_STRATEGY_TIMEFRAMES)
    )

    snapshot = MultiTimeframeMarketSnapshot(
        request=request,
        evaluated_at=NOW,
        slices=slices,
    )

    assert [market_slice.timeframe for market_slice in snapshot.slices] == list(
        SUPPORTED_STRATEGY_TIMEFRAMES
    )


def test_duplicate_timeframe_is_rejected() -> None:
    request = create_request()

    h4_slice = TimeframeMarketSlice(
        timeframe=TimeframeName.H4,
        data=create_data_snapshot(TimeframeName.H4),
    )

    with pytest.raises(
        ValueError,
        match="Duplicate timeframe",
    ):
        MultiTimeframeMarketSnapshot(
            request=request,
            evaluated_at=NOW,
            slices=(
                h4_slice,
                h4_slice,
                TimeframeMarketSlice(
                    timeframe=TimeframeName.M15,
                    data=create_data_snapshot(TimeframeName.M15),
                ),
                TimeframeMarketSlice(
                    timeframe=TimeframeName.M5,
                    data=create_data_snapshot(TimeframeName.M5),
                ),
            ),
        )


def test_snapshot_is_immutable() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(create_request())

    with pytest.raises(FrozenInstanceError):
        snapshot.evaluated_at = NOW + timedelta(minutes=1)


def test_naive_clock_is_blocked() -> None:
    service, _ = create_service(
        clock=lambda: datetime(
            2026,
            7,
            25,
            12,
            37,
        )
    )

    with pytest.raises(
        MultiTimeframeDataServiceError,
        match="INVALID_CLOCK",
    ):
        service.read_snapshot(create_request())


def test_clock_is_normalized_to_utc() -> None:
    local_timezone = timezone(timedelta(hours=5))

    service, _ = create_service(
        clock=lambda: datetime(
            2026,
            7,
            25,
            17,
            37,
            tzinfo=local_timezone,
        )
    )

    snapshot = service.read_snapshot(create_request())

    assert snapshot.evaluated_at == NOW
    assert snapshot.evaluated_at.tzinfo == timezone.utc


def test_strategy_service_alias_is_preserved() -> None:
    assert StrategyTimeframeService is MultiTimeframeMarketDataService


def test_compatibility_method_delegates() -> None:
    service, _ = create_service()

    snapshot = service.get_strategy_snapshot(
        broker_symbol="XAUUSDm",
        h4_count=2,
        h1_count=2,
        m15_count=2,
        m5_count=2,
    )

    assert snapshot.all_fresh is True


def test_service_requires_request_type() -> None:
    service, _ = create_service()

    with pytest.raises(
        ValueError,
        match="MultiTimeframeLoadRequest",
    ):
        service.read_snapshot("invalid")


def test_constructor_requires_reader_protocol() -> None:
    with pytest.raises(
        ValueError,
        match="ClosedCandleSnapshotReader",
    ):
        MultiTimeframeMarketDataService(
            candle_reader=object(),
        )


def test_constructor_requires_callable_clock() -> None:
    reader = FakeClosedCandleReader()

    with pytest.raises(ValueError, match="clock"):
        MultiTimeframeMarketDataService(
            candle_reader=reader,
            clock="invalid",
        )
