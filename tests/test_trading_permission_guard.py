from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.broker.account_service import (
    AccountServiceError,
    AccountServiceErrorReason,
    BrokerAccountSnapshot,
)
from app.broker.exposure_service import (
    BrokerExposureErrorReason,
    BrokerExposureSafetyIssue,
    BrokerExposureServiceError,
    BrokerGoldExposureSnapshot,
    BrokerPositionSnapshot,
)
from app.broker.mt5_client import (
    MT5ConnectionSnapshot,
    MT5ConnectionState,
)
from app.broker.symbol_service import (
    BrokerGoldSymbolSnapshot,
    SymbolServiceError,
    SymbolServiceErrorReason,
)
from app.config.constants import (
    LIVE_TRADING_CONFIRMATION_PHRASE,
    AppEnvironment,
    BotMode,
)
from app.config.settings import Settings
from app.domain.exposure import AccountSnapshot
from app.domain.sizing import GoldSymbolSpecification
from app.domain.trading import TradeSide
from app.safety.trading_permission_guard import (
    TradingPermissionGuard,
    TradingPermissionIssue,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def create_settings(
    mode: BotMode = BotMode.DEMO,
    **overrides: object,
) -> Settings:
    values: dict[str, object] = {
        "bot_mode": mode,
        "max_spread_points": 50,
    }

    if mode == BotMode.LIVE:
        values.update(
            {
                "app_env": AppEnvironment.PRODUCTION,
                "enable_live_trading": True,
                "live_trading_confirmation": (LIVE_TRADING_CONFIRMATION_PHRASE),
            }
        )

    values.update(overrides)

    return Settings(
        _env_file=None,
        **values,
    )


def create_connection(
    **overrides: object,
) -> MT5ConnectionSnapshot:
    values: dict[str, object] = {
        "state": MT5ConnectionState.CONNECTED,
        "initialized": True,
        "terminal_available": True,
        "account_available": True,
        "terminal_connected": True,
        "account_login": 12345678,
        "last_error_code": 0,
        "last_error_message": "No error",
    }
    values.update(overrides)

    return MT5ConnectionSnapshot(**values)


def create_account(
    **overrides: object,
) -> BrokerAccountSnapshot:
    account = AccountSnapshot(
        login=12345678,
        server="Broker-Demo",
        currency="USD",
        balance="10000.00",
        equity="10000.00",
        margin="0",
        free_margin="10000.00",
        observed_at=NOW,
    )

    values: dict[str, object] = {
        "account": account,
        "leverage": 500,
        "trade_allowed": True,
        "expert_trading_allowed": True,
        "account_name": "Demo Account",
        "company": "Example Broker",
    }
    values.update(overrides)

    return BrokerAccountSnapshot(**values)


def create_symbol(
    *,
    bid: str = "2400.00",
    ask: str = "2400.20",
) -> BrokerGoldSymbolSnapshot:
    specification = GoldSymbolSpecification(
        symbol="XAUUSD",
        account_currency="USD",
        tick_size="0.01",
        tick_value_per_lot="1.00",
        volume_min="0.01",
        volume_max="100.00",
        volume_step="0.01",
    )

    return BrokerGoldSymbolSnapshot(
        broker_symbol="XAUUSDm",
        specification=specification,
        bid=bid,
        ask=ask,
        point="0.01",
        digits=2,
        visible=True,
        observed_at=NOW,
    )


def create_exposure(
    *,
    positions: tuple[BrokerPositionSnapshot, ...] = (),
) -> BrokerGoldExposureSnapshot:
    return BrokerGoldExposureSnapshot(
        broker_symbol="XAUUSDm",
        positions=positions,
        pending_orders=(),
        observed_at=NOW,
    )


def create_position(
    *,
    stop_loss: str | None = "2390.00",
    take_profit: str | None = "2420.00",
) -> BrokerPositionSnapshot:
    return BrokerPositionSnapshot(
        ticket=1001,
        broker_symbol="XAUUSDm",
        side=TradeSide.BUY,
        volume=Decimal("0.10"),
        entry_price=Decimal("2400.00"),
        current_price=Decimal("2405.00"),
        stop_loss=stop_loss,
        take_profit=take_profit,
        unrealized_pnl=Decimal("50.00"),
        magic_number=26062801,
        opened_at=NOW,
        observed_at=NOW,
    )


class FakeConnectionReader:
    def __init__(
        self,
        snapshot: Any | None = None,
    ) -> None:
        self.snapshot = snapshot or create_connection()
        self.exception: Exception | None = None
        self.calls = 0

    def connection_snapshot(self) -> Any:
        self.calls += 1

        if self.exception is not None:
            raise self.exception

        return self.snapshot


class FakeAccountReader:
    def __init__(
        self,
        snapshot: Any | None = None,
    ) -> None:
        self.snapshot = snapshot or create_account()
        self.exception: Exception | None = None
        self.calls = 0

    def read_snapshot(self) -> Any:
        self.calls += 1

        if self.exception is not None:
            raise self.exception

        return self.snapshot


class FakeSymbolReader:
    def __init__(
        self,
        snapshot: Any | None = None,
    ) -> None:
        self.snapshot = snapshot or create_symbol()
        self.exception: Exception | None = None
        self.calls = 0
        self.currencies: list[str] = []

    def read_snapshot(
        self,
        *,
        account_currency: str,
    ) -> Any:
        self.calls += 1
        self.currencies.append(account_currency)

        if self.exception is not None:
            raise self.exception

        return self.snapshot


class FakeExposureReader:
    def __init__(
        self,
        snapshot: Any | None = None,
    ) -> None:
        self.snapshot = snapshot or create_exposure()
        self.exception: Exception | None = None
        self.calls = 0
        self.symbols: list[str] = []

    def read_snapshot(
        self,
        *,
        broker_symbol: str,
    ) -> Any:
        self.calls += 1
        self.symbols.append(broker_symbol)

        if self.exception is not None:
            raise self.exception

        return self.snapshot


def create_guard(
    *,
    settings: Settings | None = None,
    connection: FakeConnectionReader | None = None,
    account: FakeAccountReader | None = None,
    symbol: FakeSymbolReader | None = None,
    exposure: FakeExposureReader | None = None,
) -> tuple[
    TradingPermissionGuard,
    FakeConnectionReader,
    FakeAccountReader,
    FakeSymbolReader,
    FakeExposureReader,
]:
    connection_reader = connection or FakeConnectionReader()
    account_reader = account or FakeAccountReader()
    symbol_reader = symbol or FakeSymbolReader()
    exposure_reader = exposure or FakeExposureReader()

    guard = TradingPermissionGuard(
        settings=settings or create_settings(),
        connection_reader=connection_reader,
        account_reader=account_reader,
        symbol_reader=symbol_reader,
        exposure_reader=exposure_reader,
        clock=lambda: NOW,
    )

    return (
        guard,
        connection_reader,
        account_reader,
        symbol_reader,
        exposure_reader,
    )


def test_healthy_demo_environment_is_allowed() -> None:
    guard, _, _, symbol, exposure = create_guard()

    result = guard.evaluate()

    assert result.allowed is True
    assert result.new_entry_allowed is True
    assert result.infrastructure_ready is True
    assert result.issues == ()
    assert result.connection is not None
    assert result.account is not None
    assert result.symbol is not None
    assert result.exposure is not None
    assert symbol.currencies == ["USD"]
    assert exposure.symbols == ["XAUUSDm"]


def test_fully_armed_live_environment_is_allowed() -> None:
    guard, *_ = create_guard(settings=create_settings(BotMode.LIVE))

    result = guard.evaluate()

    assert result.allowed is True
    assert result.bot_mode == BotMode.LIVE


@pytest.mark.parametrize(
    "mode",
    [
        BotMode.PAPER,
        BotMode.BACKTEST,
    ],
)
def test_read_only_modes_block_broker_entry(
    mode: BotMode,
) -> None:
    guard, *_ = create_guard(settings=create_settings(mode))

    result = guard.evaluate()

    assert result.allowed is False
    assert result.is_read_only_mode is True
    assert result.infrastructure_ready is True
    assert TradingPermissionIssue.READ_ONLY_MODE in result.issues


def test_disconnected_mt5_stops_downstream_reads() -> None:
    connection = FakeConnectionReader(
        create_connection(
            state=MT5ConnectionState.DISCONNECTED,
            initialized=False,
            terminal_available=False,
            account_available=False,
            terminal_connected=False,
            account_login=None,
            last_error_code=10004,
            last_error_message="Terminal unavailable",
        )
    )

    guard, _, account, symbol, exposure = create_guard(connection=connection)

    result = guard.evaluate()

    assert result.allowed is False
    assert result.infrastructure_ready is False
    assert TradingPermissionIssue.MT5_NOT_INITIALIZED in result.issues
    assert TradingPermissionIssue.TERMINAL_UNAVAILABLE in result.issues
    assert account.calls == 0
    assert symbol.calls == 0
    assert exposure.calls == 0


@pytest.mark.parametrize(
    ("field_name", "issue"),
    [
        (
            "terminal_available",
            TradingPermissionIssue.TERMINAL_UNAVAILABLE,
        ),
        (
            "terminal_connected",
            TradingPermissionIssue.TERMINAL_DISCONNECTED,
        ),
        (
            "account_available",
            TradingPermissionIssue.ACCOUNT_UNAVAILABLE,
        ),
    ],
)
def test_connection_health_blocks_are_enforced(
    field_name: str,
    issue: TradingPermissionIssue,
) -> None:
    connection = FakeConnectionReader(create_connection(**{field_name: False}))

    guard, *_ = create_guard(connection=connection)

    result = guard.evaluate()

    assert issue in result.issues
    assert result.infrastructure_ready is False


def test_account_trading_disabled_is_blocked() -> None:
    account = FakeAccountReader(create_account(trade_allowed=False))

    guard, *_ = create_guard(account=account)

    result = guard.evaluate()

    assert TradingPermissionIssue.ACCOUNT_TRADING_DISABLED in result.issues


def test_expert_trading_disabled_is_blocked() -> None:
    account = FakeAccountReader(create_account(expert_trading_allowed=False))

    guard, *_ = create_guard(account=account)

    result = guard.evaluate()

    assert TradingPermissionIssue.EXPERT_TRADING_DISABLED in result.issues


def test_spread_above_limit_is_blocked() -> None:
    symbol = FakeSymbolReader(
        create_symbol(
            bid="2400.00",
            ask="2400.51",
        )
    )

    guard, *_ = create_guard(symbol=symbol)

    result = guard.evaluate()

    assert TradingPermissionIssue.SPREAD_LIMIT_EXCEEDED in result.issues
    assert result.symbol is not None
    assert result.symbol.spread_points == Decimal("51")


def test_spread_at_exact_limit_is_allowed() -> None:
    symbol = FakeSymbolReader(
        create_symbol(
            bid="2400.00",
            ask="2400.50",
        )
    )

    guard, *_ = create_guard(symbol=symbol)

    result = guard.evaluate()

    assert TradingPermissionIssue.SPREAD_LIMIT_EXCEEDED not in result.issues


def test_existing_gold_exposure_blocks_new_entry() -> None:
    exposure = FakeExposureReader(create_exposure(positions=(create_position(),)))

    guard, *_ = create_guard(exposure=exposure)

    result = guard.evaluate()

    assert TradingPermissionIssue.BROKER_EXPOSURE_ACTIVE in result.issues


def test_unsafe_exposure_is_reported() -> None:
    exposure = FakeExposureReader(
        create_exposure(
            positions=(
                create_position(
                    stop_loss=None,
                    take_profit=None,
                ),
            )
        )
    )

    guard, *_ = create_guard(exposure=exposure)

    result = guard.evaluate()

    assert TradingPermissionIssue.BROKER_EXPOSURE_UNSAFE in result.issues

    diagnostic_codes = {diagnostic.code for diagnostic in result.diagnostics}

    assert BrokerExposureSafetyIssue.POSITION_WITHOUT_STOP_LOSS.value in diagnostic_codes
    assert BrokerExposureSafetyIssue.POSITION_WITHOUT_TAKE_PROFIT.value in diagnostic_codes


def test_connection_exception_is_fail_safe() -> None:
    connection = FakeConnectionReader()
    connection.exception = RuntimeError("connection snapshot failure")

    guard, _, account, symbol, exposure = create_guard(connection=connection)

    result = guard.evaluate()

    assert TradingPermissionIssue.CONNECTION_SNAPSHOT_FAILED in result.issues
    assert result.infrastructure_ready is False
    assert account.calls == 0
    assert symbol.calls == 0
    assert exposure.calls == 0


def test_invalid_connection_snapshot_is_fail_safe() -> None:
    connection = FakeConnectionReader(snapshot="invalid")

    guard, *_ = create_guard(connection=connection)

    result = guard.evaluate()

    assert TradingPermissionIssue.CONNECTION_SNAPSHOT_INVALID in result.issues


def test_account_service_error_is_captured() -> None:
    account = FakeAccountReader()
    account.exception = AccountServiceError(
        AccountServiceErrorReason.ACCOUNT_INFO_UNAVAILABLE,
        "Account unavailable",
    )

    guard, *_ = create_guard(account=account)

    result = guard.evaluate()

    assert TradingPermissionIssue.ACCOUNT_SERVICE_FAILED in result.issues
    assert result.account is None
    assert result.diagnostics[-1].code == (AccountServiceErrorReason.ACCOUNT_INFO_UNAVAILABLE.value)


def test_symbol_service_error_is_captured() -> None:
    symbol = FakeSymbolReader()
    symbol.exception = SymbolServiceError(
        SymbolServiceErrorReason.NO_GOLD_SYMBOL_FOUND,
        "Gold symbol unavailable",
    )

    guard, *_ = create_guard(symbol=symbol)

    result = guard.evaluate()

    assert TradingPermissionIssue.SYMBOL_SERVICE_FAILED in result.issues
    assert result.symbol is None


def test_exposure_service_error_is_captured() -> None:
    exposure = FakeExposureReader()
    exposure.exception = BrokerExposureServiceError(
        BrokerExposureErrorReason.POSITIONS_UNAVAILABLE,
        "Positions unavailable",
    )

    guard, *_ = create_guard(exposure=exposure)

    result = guard.evaluate()

    assert TradingPermissionIssue.EXPOSURE_SERVICE_FAILED in result.issues
    assert result.exposure is None


def test_require_allowed_returns_allowed_snapshot() -> None:
    guard, *_ = create_guard()

    result = guard.evaluate()

    assert result.require_allowed() is result


def test_require_allowed_raises_with_reasons() -> None:
    guard, *_ = create_guard(settings=create_settings(BotMode.PAPER))

    result = guard.evaluate()

    with pytest.raises(
        PermissionError,
        match="READ_ONLY_MODE",
    ):
        result.require_allowed()


def test_permission_snapshot_is_immutable() -> None:
    guard, *_ = create_guard()

    result = guard.evaluate()

    with pytest.raises(FrozenInstanceError):
        result.issues = (TradingPermissionIssue.READ_ONLY_MODE,)


def test_compatibility_methods_delegate() -> None:
    guard, *_ = create_guard()

    assert guard.check().allowed is True
    assert guard.can_trade() is True
    assert guard.assert_can_trade().allowed is True


def test_naive_clock_is_rejected() -> None:
    guard, connection, account, symbol, exposure = create_guard()

    invalid_guard = TradingPermissionGuard(
        settings=create_settings(),
        connection_reader=connection,
        account_reader=account,
        symbol_reader=symbol,
        exposure_reader=exposure,
        clock=lambda: datetime(2026, 7, 25, 12, 0),
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        invalid_guard.evaluate()


@pytest.mark.parametrize(
    ("argument_name", "replacement", "message"),
    [
        (
            "settings",
            "invalid",
            "Settings",
        ),
        (
            "connection_reader",
            object(),
            "ConnectionSnapshotReader",
        ),
        (
            "account_reader",
            object(),
            "AccountSnapshotReader",
        ),
        (
            "symbol_reader",
            object(),
            "SymbolSnapshotReader",
        ),
        (
            "exposure_reader",
            object(),
            "ExposureSnapshotReader",
        ),
    ],
)
def test_constructor_protocols_are_enforced(
    argument_name: str,
    replacement: object,
    message: str,
) -> None:
    arguments: dict[str, object] = {
        "settings": create_settings(),
        "connection_reader": FakeConnectionReader(),
        "account_reader": FakeAccountReader(),
        "symbol_reader": FakeSymbolReader(),
        "exposure_reader": FakeExposureReader(),
        "clock": lambda: NOW,
    }
    arguments[argument_name] = replacement

    with pytest.raises(ValueError, match=message):
        TradingPermissionGuard(**arguments)


def test_constructor_requires_callable_clock() -> None:
    with pytest.raises(ValueError, match="clock"):
        TradingPermissionGuard(
            settings=create_settings(),
            connection_reader=FakeConnectionReader(),
            account_reader=FakeAccountReader(),
            symbol_reader=FakeSymbolReader(),
            exposure_reader=FakeExposureReader(),
            clock="invalid",
        )
