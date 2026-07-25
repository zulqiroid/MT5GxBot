from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import MetaTrader5 as mt5
import pytest

from app.broker.mt5_client import MT5ConnectionError
from app.config.constants import TimeframeName
from app.market.closed_candle_service import (
    CandleDataErrorReason,
    CandleDataServiceError,
    CandleLoadRequest,
    ClosedCandleMarketDataService,
    StrategyMarketDataService,
)

NOW = datetime(
    2026,
    7,
    25,
    12,
    37,
    tzinfo=timezone.utc,
)


def create_rate(
    open_time: datetime,
    **overrides: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "time": int(open_time.timestamp()),
        "open": "2400.00",
        "high": "2405.00",
        "low": "2398.00",
        "close": "2403.00",
        "tick_volume": 1000,
        "spread": 20,
        "real_volume": 0,
    }
    values.update(overrides)

    return values


CLOSED_RATES = (
    create_rate(
        datetime(
            2026,
            7,
            25,
            11,
            45,
            tzinfo=timezone.utc,
        ),
        close="2401.00",
    ),
    create_rate(
        datetime(
            2026,
            7,
            25,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        open="2401.00",
        close="2402.00",
    ),
    create_rate(
        datetime(
            2026,
            7,
            25,
            12,
            15,
            tzinfo=timezone.utc,
        ),
        open="2402.00",
        close="2403.00",
    ),
)

FORMING_RATE = create_rate(
    datetime(
        2026,
        7,
        25,
        12,
        30,
        tzinfo=timezone.utc,
    ),
    open="2403.00",
    high="2404.00",
    low="2401.00",
    close="2402.50",
    tick_volume=300,
)


class FakeRatesClient:
    def __init__(self) -> None:
        self.initialized = True
        self.requests: list[tuple[str, int, int, int]] = []
        self.exception: Exception | None = None
        self.closed_rates: Any = CLOSED_RATES
        self.forming_rates: Any = (FORMING_RATE,)

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        self.requests.append(
            (
                symbol,
                timeframe,
                start_pos,
                count,
            )
        )

        if self.exception is not None:
            raise self.exception

        if start_pos == 0:
            return self.forming_rates

        return self.closed_rates


def create_service(
    client: FakeRatesClient | None = None,
    clock=lambda: NOW,
) -> tuple[
    ClosedCandleMarketDataService,
    FakeRatesClient,
]:
    selected_client = client or FakeRatesClient()

    return (
        ClosedCandleMarketDataService(
            mt5_client=selected_client,
            clock=clock,
        ),
        selected_client,
    )


def create_request(
    **overrides: object,
) -> CandleLoadRequest:
    values: dict[str, object] = {
        "broker_symbol": "XAUUSDm",
        "timeframe": TimeframeName.M15,
        "closed_count": 3,
        "include_forming": False,
        "require_contiguous": False,
    }
    values.update(overrides)

    return CandleLoadRequest(**values)


def test_request_normalizes_symbol_and_timeframe() -> None:
    request = CandleLoadRequest(
        broker_symbol=" XAUUSDm ",
        timeframe="m15",
        closed_count=3,
    )

    assert request.broker_symbol == "XAUUSDm"
    assert request.timeframe == TimeframeName.M15


@pytest.mark.parametrize(
    "overrides",
    [
        {"broker_symbol": ""},
        {"timeframe": "M7"},
        {"closed_count": 0},
        {"closed_count": 10_001},
        {"closed_count": True},
        {"include_forming": 1},
        {"require_contiguous": 0},
    ],
)
def test_invalid_requests_are_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        create_request(**overrides)


def test_closed_history_uses_mt5_position_one() -> None:
    service, client = create_service()

    series = service.read_closed_series(
        broker_symbol="XAUUSDm",
        timeframe="M15",
        count=3,
    )

    assert series.count == 3
    assert client.requests == [
        (
            "XAUUSDm",
            mt5.TIMEFRAME_M15,
            1,
            3,
        )
    ]


def test_closed_rates_are_sorted_chronologically() -> None:
    client = FakeRatesClient()
    client.closed_rates = tuple(reversed(CLOSED_RATES))

    service, _ = create_service(client)

    series = service.read_closed_series(
        broker_symbol="XAUUSDm",
        timeframe="M15",
        count=3,
    )

    assert series.first.open_time.hour == 11
    assert series.first.open_time.minute == 45
    assert series.latest.open_time.hour == 12
    assert series.latest.open_time.minute == 15


def test_closed_data_uses_exact_decimals() -> None:
    service, _ = create_service()

    series = service.read_closed_series(
        broker_symbol="XAUUSDm",
        timeframe="M15",
        count=3,
    )

    assert series.latest.open == Decimal("2402.00")
    assert series.latest.close == Decimal("2403.00")


def test_snapshot_exposes_age_and_gap_state() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(create_request())

    assert snapshot.closed.count == 3
    assert snapshot.forming is None
    assert snapshot.latest_closed.close_time == datetime(
        2026,
        7,
        25,
        12,
        30,
        tzinfo=timezone.utc,
    )
    assert snapshot.latest_closed_age == timedelta(minutes=7)
    assert snapshot.has_gaps is False


def test_window_loads_forming_candle_separately() -> None:
    service, client = create_service()

    window = service.read_candle_window(
        broker_symbol="XAUUSDm",
        timeframe="M15",
        closed_count=3,
    )

    assert window.closed.count == 3
    assert window.forming is not None
    assert window.forming.open_time == datetime(
        2026,
        7,
        25,
        12,
        30,
        tzinfo=timezone.utc,
    )
    assert client.requests == [
        (
            "XAUUSDm",
            mt5.TIMEFRAME_M15,
            1,
            3,
        ),
        (
            "XAUUSDm",
            mt5.TIMEFRAME_M15,
            0,
            1,
        ),
    ]


def test_disconnected_client_is_blocked() -> None:
    client = FakeRatesClient()
    client.initialized = False

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="CONNECTION_REQUIRED",
    ) as captured:
        service.read_snapshot(create_request())

    assert captured.value.reason == CandleDataErrorReason.CONNECTION_REQUIRED
    assert client.requests == []


def test_none_rates_are_blocked() -> None:
    client = FakeRatesClient()
    client.closed_rates = None

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="RATES_UNAVAILABLE",
    ):
        service.read_snapshot(create_request())


def test_non_iterable_rates_are_blocked() -> None:
    client = FakeRatesClient()
    client.closed_rates = 123

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="INVALID_RATE_DATA",
    ):
        service.read_snapshot(create_request())


def test_insufficient_closed_rates_are_blocked() -> None:
    client = FakeRatesClient()
    client.closed_rates = CLOSED_RATES[:2]

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="INSUFFICIENT_RATES",
    ) as captured:
        service.read_snapshot(create_request())

    assert captured.value.reason == CandleDataErrorReason.INSUFFICIENT_RATES


def test_generic_read_exception_is_wrapped() -> None:
    client = FakeRatesClient()
    client.exception = RuntimeError("rates adapter failure")

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="RATES_READ_FAILED",
    ):
        service.read_snapshot(create_request())


def test_mt5_connection_error_is_wrapped() -> None:
    client = FakeRatesClient()
    client.exception = MT5ConnectionError(
        500,
        "connection lost",
    )

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="connection lost",
    ):
        service.read_snapshot(create_request())


def test_invalid_closed_rate_is_blocked() -> None:
    client = FakeRatesClient()
    invalid_rate = CLOSED_RATES[0].copy()
    invalid_rate.pop("high")
    client.closed_rates = (
        invalid_rate,
        *CLOSED_RATES[1:],
    )

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="INVALID_RATE_DATA",
    ):
        service.read_snapshot(create_request())


def test_unfinished_rate_cannot_enter_closed_history() -> None:
    client = FakeRatesClient()
    client.closed_rates = (
        *CLOSED_RATES[:2],
        FORMING_RATE,
    )

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="INVALID_RATE_DATA",
    ):
        service.read_snapshot(create_request())


def test_gaps_are_reported_but_allowed_by_default() -> None:
    client = FakeRatesClient()
    client.closed_rates = (
        CLOSED_RATES[0],
        CLOSED_RATES[2],
    )

    service, _ = create_service(client)

    snapshot = service.read_snapshot(create_request(closed_count=2))

    assert snapshot.has_gaps is True
    assert snapshot.closed.missing_candle_count == 1


def test_contiguous_request_blocks_gaps() -> None:
    client = FakeRatesClient()
    client.closed_rates = (
        CLOSED_RATES[0],
        CLOSED_RATES[2],
    )

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="CLOSED_SERIES_GAP",
    ) as captured:
        service.read_snapshot(
            create_request(
                closed_count=2,
                require_contiguous=True,
            )
        )

    assert captured.value.reason == CandleDataErrorReason.CLOSED_SERIES_GAP


def test_duplicate_closed_times_are_blocked() -> None:
    client = FakeRatesClient()
    client.closed_rates = (
        CLOSED_RATES[0],
        CLOSED_RATES[0],
        CLOSED_RATES[2],
    )

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="INVALID_RATE_DATA",
    ):
        service.read_snapshot(create_request())


def test_missing_forming_candle_is_blocked() -> None:
    client = FakeRatesClient()
    client.forming_rates = ()

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="FORMING_CANDLE_UNAVAILABLE",
    ):
        service.read_snapshot(create_request(include_forming=True))


def test_closed_rate_cannot_be_used_as_forming() -> None:
    client = FakeRatesClient()
    client.forming_rates = (CLOSED_RATES[-1],)

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="FORMING_CANDLE_UNAVAILABLE",
    ):
        service.read_snapshot(create_request(include_forming=True))


def test_forming_candle_must_follow_latest_closed() -> None:
    client = FakeRatesClient()
    client.closed_rates = (CLOSED_RATES[1],)
    client.forming_rates = (FORMING_RATE,)

    service, _ = create_service(client)

    with pytest.raises(
        CandleDataServiceError,
        match="FORMING_CANDLE_UNAVAILABLE",
    ):
        service.read_snapshot(
            create_request(
                closed_count=1,
                include_forming=True,
            )
        )


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

    assert snapshot.loaded_at == NOW
    assert snapshot.loaded_at.tzinfo == timezone.utc


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
        CandleDataServiceError,
        match="INVALID_CLOCK",
    ):
        service.read_snapshot(create_request())


def test_snapshot_is_immutable() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(create_request())

    with pytest.raises(FrozenInstanceError):
        snapshot.loaded_at = NOW + timedelta(minutes=1)


def test_strategy_service_alias_is_preserved() -> None:
    assert StrategyMarketDataService is ClosedCandleMarketDataService


def test_compatibility_methods_delegate() -> None:
    service, _ = create_service()

    series = service.get_closed_candles(
        broker_symbol="XAUUSDm",
        timeframe="M15",
        count=3,
    )
    window = service.get_candle_window(
        broker_symbol="XAUUSDm",
        timeframe="M15",
        closed_count=3,
    )

    assert series.count == 3
    assert window.forming is not None


def test_read_snapshot_requires_request_type() -> None:
    service, _ = create_service()

    with pytest.raises(
        ValueError,
        match="CandleLoadRequest",
    ):
        service.read_snapshot("invalid")


def test_constructor_requires_rates_client() -> None:
    with pytest.raises(
        ValueError,
        match="CandleRatesClient",
    ):
        ClosedCandleMarketDataService(
            mt5_client=object(),
        )


def test_constructor_requires_callable_clock() -> None:
    client = FakeRatesClient()

    with pytest.raises(ValueError, match="clock"):
        ClosedCandleMarketDataService(
            mt5_client=client,
            clock="invalid",
        )
