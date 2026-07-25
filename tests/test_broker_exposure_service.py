from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.broker.exposure_service import (
    BrokerExposureErrorReason,
    BrokerExposureSafetyIssue,
    BrokerExposureService,
    BrokerExposureServiceError,
)
from app.broker.mt5_client import MT5ConnectionError
from app.domain.trading import EntryType, TradeSide

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
OPENED_EPOCH = int(
    datetime(
        2026,
        7,
        25,
        11,
        0,
        tzinfo=timezone.utc,
    ).timestamp()
)


class FakeExposureClient:
    def __init__(self) -> None:
        self.initialized = True
        self.positions_calls: list[str | None] = []
        self.orders_calls: list[str | None] = []
        self.positions_exception: Exception | None = None
        self.orders_exception: Exception | None = None
        self.positions: Any = ()
        self.orders: Any = ()

    def positions_get(
        self,
        symbol: str | None = None,
    ) -> Any:
        self.positions_calls.append(symbol)

        if self.positions_exception is not None:
            raise self.positions_exception

        return self.positions

    def orders_get(
        self,
        symbol: str | None = None,
    ) -> Any:
        self.orders_calls.append(symbol)

        if self.orders_exception is not None:
            raise self.orders_exception

        return self.orders


def create_position(**overrides: object) -> Any:
    values: dict[str, object] = {
        "ticket": 1001,
        "symbol": "XAUUSDm",
        "type": 0,
        "volume": "0.10",
        "price_open": "2400.00",
        "price_current": "2405.00",
        "sl": "2390.00",
        "tp": "2420.00",
        "profit": "50.00",
        "magic": 26062801,
        "time": OPENED_EPOCH,
        "comment": "goldx",
    }
    values.update(overrides)

    return SimpleNamespace(**values)


def create_order(**overrides: object) -> Any:
    values: dict[str, object] = {
        "ticket": 2001,
        "symbol": "XAUUSDm",
        "type": 4,
        "volume_current": "0.10",
        "volume_initial": "0.10",
        "price_open": "2410.00",
        "sl": "2400.00",
        "tp": "2430.00",
        "magic": 26062801,
        "time_setup": OPENED_EPOCH,
        "comment": "goldx",
    }
    values.update(overrides)

    return SimpleNamespace(**values)


def create_service(
    client: FakeExposureClient | None = None,
    clock=lambda: NOW,
) -> tuple[BrokerExposureService, FakeExposureClient]:
    selected_client = client or FakeExposureClient()

    return (
        BrokerExposureService(
            mt5_client=selected_client,
            clock=clock,
        ),
        selected_client,
    )


def test_empty_exposure_is_safe_for_new_entry() -> None:
    service, client = create_service()

    snapshot = service.read_snapshot(broker_symbol="XAUUSDm")

    assert snapshot.positions == ()
    assert snapshot.pending_orders == ()
    assert snapshot.has_active_exposure is False
    assert snapshot.safe_for_new_entry is True
    assert snapshot.reconciliation_required is False
    assert client.positions_calls == ["XAUUSDm"]
    assert client.orders_calls == ["XAUUSDm"]


def test_buy_position_is_mapped() -> None:
    client = FakeExposureClient()
    client.positions = (create_position(),)

    service, _ = create_service(client)

    snapshot = service.read_snapshot(broker_symbol="XAUUSDm")
    position = snapshot.positions[0]

    assert position.ticket == 1001
    assert position.side == TradeSide.BUY
    assert position.volume == Decimal("0.10")
    assert position.entry_price == Decimal("2400.00")
    assert position.current_price == Decimal("2405.00")
    assert position.stop_loss == Decimal("2390.00")
    assert position.take_profit == Decimal("2420.00")
    assert position.unrealized_pnl == Decimal("50.00")
    assert position.price_move == Decimal("5.00")
    assert position.has_stop_loss is True
    assert position.has_take_profit is True


def test_sell_position_price_move_is_directional() -> None:
    client = FakeExposureClient()
    client.positions = (
        create_position(
            type=1,
            price_open="2400.00",
            price_current="2395.00",
            sl="2410.00",
            tp="2380.00",
        ),
    )

    service, _ = create_service(client)

    position = service.read_snapshot(broker_symbol="XAUUSDm").positions[0]

    assert position.side == TradeSide.SELL
    assert position.price_move == Decimal("5.00")


@pytest.mark.parametrize(
    ("order_type", "side", "entry_type"),
    [
        (2, TradeSide.BUY, EntryType.LIMIT),
        (3, TradeSide.SELL, EntryType.LIMIT),
        (4, TradeSide.BUY, EntryType.STOP),
        (5, TradeSide.SELL, EntryType.STOP),
    ],
)
def test_supported_pending_orders_are_mapped(
    order_type: int,
    side: TradeSide,
    entry_type: EntryType,
) -> None:
    client = FakeExposureClient()
    client.orders = (create_order(type=order_type),)

    service, _ = create_service(client)

    order = service.read_snapshot(broker_symbol="XAUUSDm").pending_orders[0]

    assert order.side == side
    assert order.entry_type == entry_type
    assert order.volume == Decimal("0.10")
    assert order.has_stop_loss is True
    assert order.has_take_profit is True


def test_volume_initial_is_used_when_current_missing() -> None:
    client = FakeExposureClient()
    raw_order = vars(create_order()).copy()
    raw_order.pop("volume_current")
    client.orders = (SimpleNamespace(**raw_order),)

    service, _ = create_service(client)

    order = service.read_snapshot(broker_symbol="XAUUSDm").pending_orders[0]

    assert order.volume == Decimal("0.10")


def test_zero_stop_and_target_become_missing() -> None:
    client = FakeExposureClient()
    client.positions = (create_position(sl=0, tp=0),)

    service, _ = create_service(client)

    position = service.read_snapshot(broker_symbol="XAUUSDm").positions[0]

    assert position.stop_loss is None
    assert position.take_profit is None


def test_missing_position_protection_is_detected() -> None:
    client = FakeExposureClient()
    client.positions = (create_position(sl=0, tp=0),)

    service, _ = create_service(client)

    snapshot = service.read_snapshot(broker_symbol="XAUUSDm")

    assert BrokerExposureSafetyIssue.POSITION_WITHOUT_STOP_LOSS in snapshot.safety_issues
    assert BrokerExposureSafetyIssue.POSITION_WITHOUT_TAKE_PROFIT in snapshot.safety_issues
    assert snapshot.reconciliation_required is True
    assert snapshot.safe_for_new_entry is False


def test_missing_pending_protection_is_detected() -> None:
    client = FakeExposureClient()
    client.orders = (create_order(sl=0, tp=0),)

    service, _ = create_service(client)

    snapshot = service.read_snapshot(broker_symbol="XAUUSDm")

    assert BrokerExposureSafetyIssue.PENDING_ORDER_WITHOUT_STOP_LOSS in snapshot.safety_issues
    assert BrokerExposureSafetyIssue.PENDING_ORDER_WITHOUT_TAKE_PROFIT in snapshot.safety_issues


def test_multiple_positions_are_detected() -> None:
    client = FakeExposureClient()
    client.positions = (
        create_position(ticket=1001),
        create_position(ticket=1002),
    )

    service, _ = create_service(client)

    snapshot = service.read_snapshot(broker_symbol="XAUUSDm")

    assert BrokerExposureSafetyIssue.MULTIPLE_OPEN_POSITIONS in snapshot.safety_issues


def test_mixed_position_and_orders_are_detected() -> None:
    client = FakeExposureClient()
    client.positions = (create_position(),)
    client.orders = (create_order(),)

    service, _ = create_service(client)

    snapshot = service.read_snapshot(broker_symbol="XAUUSDm")

    assert BrokerExposureSafetyIssue.POSITION_AND_PENDING_ORDERS in snapshot.safety_issues


def test_duplicate_ticket_is_blocked() -> None:
    client = FakeExposureClient()
    client.positions = (create_position(ticket=1001),)
    client.orders = (create_order(ticket=1001),)

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="DUPLICATE_TICKET",
    ) as captured:
        service.read_snapshot(broker_symbol="XAUUSDm")

    assert captured.value.reason == BrokerExposureErrorReason.DUPLICATE_TICKET


def test_disconnected_client_is_blocked() -> None:
    client = FakeExposureClient()
    client.initialized = False

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="CONNECTION_REQUIRED",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")

    assert client.positions_calls == []
    assert client.orders_calls == []


def test_none_positions_result_is_blocked() -> None:
    client = FakeExposureClient()
    client.positions = None

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="POSITIONS_UNAVAILABLE",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


def test_none_orders_result_is_blocked() -> None:
    client = FakeExposureClient()
    client.orders = None

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="ORDERS_UNAVAILABLE",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


def test_position_read_exception_is_wrapped() -> None:
    client = FakeExposureClient()
    client.positions_exception = RuntimeError("position failure")

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="POSITIONS_READ_FAILED",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


def test_order_read_exception_is_wrapped() -> None:
    client = FakeExposureClient()
    client.orders_exception = RuntimeError("order failure")

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="ORDERS_READ_FAILED",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


def test_mt5_connection_error_is_wrapped() -> None:
    client = FakeExposureClient()
    client.positions_exception = MT5ConnectionError(
        500,
        "connection lost",
    )

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="connection lost",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


@pytest.mark.parametrize("position_type", [2, 5, 99])
def test_unsupported_position_type_is_blocked(
    position_type: int,
) -> None:
    client = FakeExposureClient()
    client.positions = (create_position(type=position_type),)

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="UNSUPPORTED_POSITION_TYPE",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


@pytest.mark.parametrize("order_type", [0, 1, 6, 7, 99])
def test_unsupported_order_type_is_blocked(
    order_type: int,
) -> None:
    client = FakeExposureClient()
    client.orders = (create_order(type=order_type),)

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="UNSUPPORTED_ORDER_TYPE",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("ticket", 0),
        ("volume", 0),
        ("price_open", "NaN"),
        ("price_current", 0),
        ("sl", -1),
        ("magic", -1),
        ("time", 0),
    ],
)
def test_invalid_position_data_is_blocked(
    field_name: str,
    value: object,
) -> None:
    client = FakeExposureClient()
    client.positions = (create_position(**{field_name: value}),)

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="INVALID_POSITION_DATA",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("ticket", 0),
        ("volume_current", 0),
        ("price_open", "NaN"),
        ("sl", -1),
        ("magic", -1),
        ("time_setup", 0),
    ],
)
def test_invalid_order_data_is_blocked(
    field_name: str,
    value: object,
) -> None:
    client = FakeExposureClient()
    client.orders = (create_order(**{field_name: value}),)

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="INVALID_ORDER_DATA",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


def test_position_symbol_mismatch_is_blocked() -> None:
    client = FakeExposureClient()
    client.positions = (create_position(symbol="XAUUSD"),)

    service, _ = create_service(client)

    with pytest.raises(
        BrokerExposureServiceError,
        match="does not match",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


def test_mapping_data_is_supported() -> None:
    client = FakeExposureClient()
    client.positions = (vars(create_position()).copy(),)
    client.orders = (vars(create_order()).copy(),)

    service, _ = create_service(client)

    snapshot = service.read_snapshot(broker_symbol="XAUUSDm")

    assert snapshot.positions[0].ticket == 1001
    assert snapshot.pending_orders[0].ticket == 2001


def test_naive_clock_is_blocked() -> None:
    service, _ = create_service(clock=lambda: datetime(2026, 7, 25, 12, 0))

    with pytest.raises(
        BrokerExposureServiceError,
        match="INVALID_CLOCK",
    ):
        service.read_snapshot(broker_symbol="XAUUSDm")


def test_constructor_requires_protocol() -> None:
    with pytest.raises(
        ValueError,
        match="BrokerExposureClient",
    ):
        BrokerExposureService(
            mt5_client=object(),
        )


def test_constructor_requires_callable_clock() -> None:
    client = FakeExposureClient()

    with pytest.raises(ValueError, match="clock"):
        BrokerExposureService(
            mt5_client=client,
            clock="invalid",
        )
