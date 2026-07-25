from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.broker.account_service import (
    AccountReadinessReason,
    AccountService,
    AccountServiceError,
    AccountServiceErrorReason,
)
from app.broker.mt5_client import MT5ConnectionError

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


class FakeAccountClient:
    def __init__(self) -> None:
        self.initialized = True
        self.account_calls = 0
        self.terminal_calls = 0
        self.account_exception: Exception | None = None

        self.account: Any = SimpleNamespace(
            login=12345678,
            server="Broker-Demo",
            currency="usd",
            balance=10000.00,
            equity=9800.00,
            margin=1000.00,
            margin_free=8800.00,
            leverage=500,
            trade_allowed=True,
            trade_expert=True,
            name="Demo Account",
            company="Example Broker",
        )

        self.terminal: Any = SimpleNamespace(
            connected=True,
            trade_allowed=True,
            company="Example Broker",
            name="MetaTrader 5",
            path="C:/MT5/terminal64.exe",
        )

    def account_info(self) -> Any:
        self.account_calls += 1

        if self.account_exception is not None:
            raise self.account_exception

        return self.account

    def terminal_info(self) -> Any:
        self.terminal_calls += 1
        return self.terminal


def create_service(
    client: FakeAccountClient | None = None,
    clock=lambda: NOW,
) -> tuple[AccountService, FakeAccountClient]:
    selected_client = client or FakeAccountClient()

    return (
        AccountService(
            mt5_client=selected_client,
            clock=clock,
        ),
        selected_client,
    )


def test_account_snapshot_maps_core_fields() -> None:
    service, client = create_service()

    snapshot = service.read_snapshot()

    assert client.account_calls == 1
    assert snapshot.account.login == 12345678
    assert snapshot.account.server == "Broker-Demo"
    assert snapshot.account.currency == "USD"
    assert snapshot.account.balance == Decimal("10000.0")
    assert snapshot.account.equity == Decimal("9800.0")
    assert snapshot.account.margin == Decimal("1000.0")
    assert snapshot.account.free_margin == Decimal("8800.0")
    assert snapshot.account.observed_at == NOW
    assert snapshot.leverage == 500
    assert snapshot.trade_allowed is True
    assert snapshot.expert_trading_allowed is True


def test_account_snapshot_uses_decimal_strings_exactly() -> None:
    client = FakeAccountClient()
    client.account.balance = "10000.25"
    client.account.equity = "9999.75"
    client.account.margin = "100.50"
    client.account.margin_free = "9899.25"

    service, _ = create_service(client)

    snapshot = service.read_snapshot()

    assert snapshot.account.balance == Decimal("10000.25")
    assert snapshot.account.equity == Decimal("9999.75")
    assert snapshot.account.margin == Decimal("100.50")
    assert snapshot.account.free_margin == Decimal("9899.25")


def test_clock_timestamp_is_normalized_to_utc() -> None:
    local_timezone = timezone(timedelta(hours=5))

    service, _ = create_service(
        clock=lambda: datetime(
            2026,
            7,
            25,
            17,
            0,
            tzinfo=local_timezone,
        )
    )

    snapshot = service.read_snapshot()

    assert snapshot.account.observed_at == NOW
    assert snapshot.account.observed_at.tzinfo == timezone.utc


def test_account_is_ready_when_permissions_are_enabled() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot()

    assert snapshot.readiness_reasons == ()
    assert snapshot.automated_trading_ready is True


def test_disabled_account_trading_is_reported() -> None:
    client = FakeAccountClient()
    client.account.trade_allowed = False

    service, _ = create_service(client)

    snapshot = service.read_snapshot()

    assert snapshot.automated_trading_ready is False
    assert snapshot.readiness_reasons == (AccountReadinessReason.ACCOUNT_TRADING_DISABLED,)


def test_disabled_expert_trading_is_reported() -> None:
    client = FakeAccountClient()
    client.account.trade_expert = False

    service, _ = create_service(client)

    snapshot = service.read_snapshot()

    assert snapshot.automated_trading_ready is False
    assert snapshot.readiness_reasons == (AccountReadinessReason.EXPERT_TRADING_DISABLED,)


def test_both_permission_blocks_are_preserved() -> None:
    client = FakeAccountClient()
    client.account.trade_allowed = False
    client.account.trade_expert = False

    service, _ = create_service(client)

    snapshot = service.read_snapshot()

    assert snapshot.readiness_reasons == (
        AccountReadinessReason.ACCOUNT_TRADING_DISABLED,
        AccountReadinessReason.EXPERT_TRADING_DISABLED,
    )


def test_integer_permission_flags_are_supported() -> None:
    client = FakeAccountClient()
    client.account.trade_allowed = 1
    client.account.trade_expert = 0

    service, _ = create_service(client)

    snapshot = service.read_snapshot()

    assert snapshot.trade_allowed is True
    assert snapshot.expert_trading_allowed is False


def test_account_snapshot_is_immutable() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.leverage = 100


def test_disconnected_client_is_blocked() -> None:
    client = FakeAccountClient()
    client.initialized = False

    service, _ = create_service(client)

    with pytest.raises(
        AccountServiceError,
        match="CONNECTION_REQUIRED",
    ) as captured:
        service.read_snapshot()

    assert captured.value.reason == AccountServiceErrorReason.CONNECTION_REQUIRED
    assert client.account_calls == 0


def test_none_account_info_is_blocked() -> None:
    client = FakeAccountClient()
    client.account = None

    service, _ = create_service(client)

    with pytest.raises(
        AccountServiceError,
        match="ACCOUNT_INFO_UNAVAILABLE",
    ) as captured:
        service.read_snapshot()

    assert captured.value.reason == AccountServiceErrorReason.ACCOUNT_INFO_UNAVAILABLE


def test_mt5_connection_error_is_wrapped() -> None:
    client = FakeAccountClient()
    client.account_exception = MT5ConnectionError(
        500,
        "Account read failed",
    )

    service, _ = create_service(client)

    with pytest.raises(
        AccountServiceError,
        match="ACCOUNT_INFO_READ_FAILED",
    ) as captured:
        service.read_snapshot()

    assert captured.value.reason == AccountServiceErrorReason.ACCOUNT_INFO_READ_FAILED


def test_generic_read_exception_is_wrapped() -> None:
    client = FakeAccountClient()
    client.account_exception = RuntimeError("unexpected adapter failure")

    service, _ = create_service(client)

    with pytest.raises(
        AccountServiceError,
        match="RuntimeError",
    ):
        service.read_snapshot()


@pytest.mark.parametrize(
    "missing_field",
    [
        "login",
        "server",
        "currency",
        "balance",
        "equity",
        "margin",
        "margin_free",
        "leverage",
        "trade_allowed",
        "trade_expert",
    ],
)
def test_missing_required_broker_field_is_blocked(
    missing_field: str,
) -> None:
    client = FakeAccountClient()
    values = vars(client.account).copy()
    values.pop(missing_field)
    client.account = SimpleNamespace(**values)

    service, _ = create_service(client)

    with pytest.raises(
        AccountServiceError,
        match="INVALID_ACCOUNT_DATA",
    ):
        service.read_snapshot()


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("login", 0),
        ("server", ""),
        ("currency", ""),
        ("balance", "NaN"),
        ("equity", "Infinity"),
        ("margin", "-1"),
        ("leverage", 0),
        ("trade_allowed", "yes"),
        ("trade_expert", 2),
    ],
)
def test_invalid_broker_field_is_blocked(
    field_name: str,
    value: object,
) -> None:
    client = FakeAccountClient()
    setattr(client.account, field_name, value)

    service, _ = create_service(client)

    with pytest.raises(
        AccountServiceError,
        match="INVALID_ACCOUNT_DATA",
    ):
        service.read_snapshot()


def test_naive_clock_is_blocked() -> None:
    service, _ = create_service(clock=lambda: datetime(2026, 7, 25, 12, 0))

    with pytest.raises(
        AccountServiceError,
        match="INVALID_CLOCK",
    ) as captured:
        service.read_snapshot()

    assert captured.value.reason == AccountServiceErrorReason.INVALID_CLOCK


def test_non_datetime_clock_result_is_blocked() -> None:
    service, _ = create_service(clock=lambda: "2026-07-25")

    with pytest.raises(
        AccountServiceError,
        match="INVALID_CLOCK",
    ):
        service.read_snapshot()


def test_mapping_account_data_is_supported() -> None:
    client = FakeAccountClient()
    client.account = {
        "login": 12345678,
        "server": "Broker-Demo",
        "currency": "USD",
        "balance": "10000.00",
        "equity": "10000.00",
        "margin": "0",
        "margin_free": "10000.00",
        "leverage": 500,
        "trade_allowed": True,
        "trade_expert": True,
        "name": "Mapping Account",
        "company": "Example Broker",
    }

    service, _ = create_service(client)

    snapshot = service.read_snapshot()

    assert snapshot.account.login == 12345678
    assert snapshot.account_name == "Mapping Account"


def test_optional_blank_text_becomes_none() -> None:
    client = FakeAccountClient()
    client.account.name = "   "
    client.account.company = None

    service, _ = create_service(client)

    snapshot = service.read_snapshot()

    assert snapshot.account_name is None
    assert snapshot.company is None


def test_get_account_snapshot_returns_domain_snapshot() -> None:
    service, _ = create_service()

    account = service.get_account_snapshot()

    assert account.login == 12345678
    assert account.currency == "USD"


def test_compatibility_raw_account_method_delegates() -> None:
    service, client = create_service()

    result = service.get_account_info()

    assert result is client.account
    assert client.account_calls == 1


def test_compatibility_terminal_method_delegates() -> None:
    service, client = create_service()

    result = service.get_terminal_info()

    assert result is client.terminal
    assert client.terminal_calls == 1


def test_log_diagnostics_read_without_mutating_data() -> None:
    service, client = create_service()

    service.log_terminal_info()
    service.log_account_info()

    assert client.terminal_calls == 1
    assert client.account_calls == 1


def test_constructor_requires_account_client_protocol() -> None:
    with pytest.raises(
        ValueError,
        match="AccountInfoClient",
    ):
        AccountService(
            mt5_client=object(),
        )


def test_constructor_requires_callable_clock() -> None:
    client = FakeAccountClient()

    with pytest.raises(ValueError, match="clock"):
        AccountService(
            mt5_client=client,
            clock="invalid",
        )
