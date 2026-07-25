from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.broker.mt5_client import (
    MT5Client,
    MT5ConnectionError,
    MT5ConnectionState,
)
from app.config.settings import Settings


class FakeMT5Adapter:
    def __init__(self) -> None:
        self.initialize_result = True
        self.initialize_exception: Exception | None = None
        self.shutdown_exception: Exception | None = None
        self.error: Any = (0, "No error")

        self.initialize_calls = 0
        self.shutdown_calls = 0
        self.initialize_paths: list[str | None] = []

        self.terminal = SimpleNamespace(connected=True)
        self.account = SimpleNamespace(login=12345678)
        self.symbol = SimpleNamespace(name="XAUUSD")
        self.tick = SimpleNamespace(bid=2400.0, ask=2400.2)
        self.symbols = (SimpleNamespace(name="XAUUSD"),)
        self.rates = [
            {
                "time": 1,
                "open": 2400.0,
                "high": 2401.0,
                "low": 2399.0,
                "close": 2400.5,
            }
        ]

        self.selected_symbols: list[tuple[str, bool]] = []
        self.rate_requests: list[tuple[str, int, int, int]] = []

    def initialize(
        self,
        *,
        path: str | None = None,
    ) -> bool:
        self.initialize_calls += 1
        self.initialize_paths.append(path)

        if self.initialize_exception is not None:
            raise self.initialize_exception

        return self.initialize_result

    def shutdown(self) -> None:
        self.shutdown_calls += 1

        if self.shutdown_exception is not None:
            raise self.shutdown_exception

    def last_error(self) -> Any:
        return self.error

    def terminal_info(self) -> Any:
        return self.terminal

    def account_info(self) -> Any:
        return self.account

    def symbol_info(self, symbol: str) -> Any:
        assert symbol
        return self.symbol

    def symbol_info_tick(self, symbol: str) -> Any:
        assert symbol
        return self.tick

    def symbols_get(self) -> Any:
        return self.symbols

    def symbol_select(
        self,
        symbol: str,
        enable: bool = True,
    ) -> bool:
        self.selected_symbols.append((symbol, enable))
        return True

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        self.rate_requests.append(
            (
                symbol,
                timeframe,
                start_pos,
                count,
            )
        )
        return self.rates


def create_settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        **overrides,
    )


def create_client(
    adapter: FakeMT5Adapter | None = None,
    **settings_overrides: object,
) -> tuple[MT5Client, FakeMT5Adapter]:
    selected_adapter = adapter or FakeMT5Adapter()

    client = MT5Client(
        settings=create_settings(**settings_overrides),
        adapter=selected_adapter,
    )

    return client, selected_adapter


def test_client_starts_disconnected() -> None:
    client, _ = create_client()

    assert client.state == MT5ConnectionState.DISCONNECTED
    assert client.initialized is False
    assert client.last_error() == (0, "No error")


def test_successful_initialization_changes_state() -> None:
    client, adapter = create_client()

    assert client.initialize() is True
    assert client.state == MT5ConnectionState.CONNECTED
    assert client.initialized is True
    assert adapter.initialize_calls == 1
    assert adapter.initialize_paths == [None]


def test_initialization_is_idempotent() -> None:
    client, adapter = create_client()

    assert client.initialize() is True
    assert client.initialize() is True

    assert adapter.initialize_calls == 1


def test_failed_initialization_is_recorded() -> None:
    adapter = FakeMT5Adapter()
    adapter.initialize_result = False
    adapter.error = (10004, "Terminal unavailable")

    client, _ = create_client(adapter)

    assert client.initialize() is False
    assert client.state == MT5ConnectionState.FAILED
    assert client.initialized is False
    assert client.last_error() == (
        10004,
        "Terminal unavailable",
    )


def test_initialization_exception_is_contained() -> None:
    adapter = FakeMT5Adapter()
    adapter.initialize_exception = RuntimeError("adapter failure")

    client, _ = create_client(adapter)

    assert client.initialize() is False
    assert client.state == MT5ConnectionState.FAILED
    assert "RuntimeError" in client.last_error()[1]


def test_failed_connection_can_be_retried() -> None:
    adapter = FakeMT5Adapter()
    adapter.initialize_result = False
    adapter.error = (1, "First attempt failed")

    client, _ = create_client(adapter)

    assert client.initialize() is False

    adapter.initialize_result = True

    assert client.initialize() is True
    assert client.state == MT5ConnectionState.CONNECTED
    assert adapter.initialize_calls == 2


def test_missing_configured_terminal_is_blocked(
    tmp_path: Path,
) -> None:
    missing_terminal = (tmp_path / "missing-terminal64.exe").resolve()

    client, adapter = create_client(mt5_terminal_path=str(missing_terminal))

    assert client.initialize() is False
    assert client.state == MT5ConnectionState.FAILED
    assert adapter.initialize_calls == 0
    assert "does not exist" in client.last_error()[1]


def test_existing_terminal_path_is_forwarded(
    tmp_path: Path,
) -> None:
    terminal = (tmp_path / "terminal64.exe").resolve()
    terminal.touch()

    client, adapter = create_client(mt5_terminal_path=str(terminal))

    assert client.initialize() is True
    assert adapter.initialize_paths == [str(terminal)]


def test_connect_or_raise_uses_structured_error() -> None:
    adapter = FakeMT5Adapter()
    adapter.initialize_result = False
    adapter.error = (500, "Connection rejected")

    client, _ = create_client(adapter)

    with pytest.raises(
        MT5ConnectionError,
        match="Connection rejected",
    ) as captured:
        client.connect_or_raise()

    assert captured.value.code == 500
    assert captured.value.message == "Connection rejected"


def test_context_manager_initializes_and_shuts_down() -> None:
    client, adapter = create_client()

    with client as connected_client:
        assert connected_client is client
        assert client.initialized is True

    assert adapter.initialize_calls == 1
    assert adapter.shutdown_calls == 1
    assert client.state == MT5ConnectionState.DISCONNECTED


def test_shutdown_is_idempotent() -> None:
    client, adapter = create_client()

    client.initialize()
    client.shutdown()
    client.shutdown()

    assert adapter.shutdown_calls == 1
    assert client.state == MT5ConnectionState.DISCONNECTED


def test_shutdown_exception_is_contained() -> None:
    adapter = FakeMT5Adapter()
    adapter.shutdown_exception = RuntimeError("shutdown failure")

    client, _ = create_client(adapter)
    client.initialize()
    client.shutdown()

    assert client.state == MT5ConnectionState.FAILED
    assert "shutdown failure" in client.last_error()[1]


@pytest.mark.parametrize(
    "operation",
    [
        lambda client: client.terminal_info(),
        lambda client: client.account_info(),
        lambda client: client.symbol_info("XAUUSD"),
        lambda client: client.symbol_info_tick("XAUUSD"),
        lambda client: client.symbols_get(),
        lambda client: client.symbol_select("XAUUSD"),
        lambda client: client.copy_rates_from_pos(
            "XAUUSD",
            15,
            0,
            100,
        ),
    ],
)
def test_read_operations_require_initialization(
    operation: Any,
) -> None:
    client, _ = create_client()

    with pytest.raises(
        MT5ConnectionError,
        match="before initialization",
    ):
        operation(client)


def test_read_operations_delegate_to_adapter() -> None:
    client, adapter = create_client()
    client.connect_or_raise()

    assert client.terminal_info() is adapter.terminal
    assert client.account_info() is adapter.account
    assert client.symbol_info("XAUUSD") is adapter.symbol
    assert client.symbol_info_tick("XAUUSD") is adapter.tick
    assert client.symbols_get() is adapter.symbols
    assert client.symbol_select("XAUUSD", True) is True
    assert (
        client.copy_rates_from_pos(
            "XAUUSD",
            15,
            0,
            100,
        )
        is adapter.rates
    )

    assert adapter.selected_symbols == [("XAUUSD", True)]
    assert adapter.rate_requests == [("XAUUSD", 15, 0, 100)]


def test_disconnected_snapshot_does_not_read_adapter() -> None:
    client, _ = create_client()

    snapshot = client.connection_snapshot()

    assert snapshot.state == MT5ConnectionState.DISCONNECTED
    assert snapshot.initialized is False
    assert snapshot.terminal_available is False
    assert snapshot.account_available is False
    assert snapshot.account_login is None


def test_connected_snapshot_contains_diagnostics() -> None:
    client, _ = create_client()
    client.connect_or_raise()

    snapshot = client.connection_snapshot()

    assert snapshot.state == MT5ConnectionState.CONNECTED
    assert snapshot.initialized is True
    assert snapshot.terminal_available is True
    assert snapshot.account_available is True
    assert snapshot.terminal_connected is True
    assert snapshot.account_login == 12345678


def test_none_read_result_captures_adapter_error() -> None:
    adapter = FakeMT5Adapter()
    adapter.terminal = None
    adapter.error = (404, "Terminal info unavailable")

    client, _ = create_client(adapter)
    client.connect_or_raise()

    assert client.terminal_info() is None
    assert client.last_error() == (
        404,
        "Terminal info unavailable",
    )


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        "   ",
        "\n",
    ],
)
def test_invalid_symbol_is_rejected(symbol: str) -> None:
    client, _ = create_client()
    client.connect_or_raise()

    with pytest.raises(ValueError):
        client.symbol_info(symbol)


@pytest.mark.parametrize(
    ("start_pos", "count"),
    [
        (-1, 100),
        (0, 0),
        (0, -1),
    ],
)
def test_invalid_rate_request_is_rejected(
    start_pos: int,
    count: int,
) -> None:
    client, _ = create_client()
    client.connect_or_raise()

    with pytest.raises(ValueError):
        client.copy_rates_from_pos(
            "XAUUSD",
            15,
            start_pos,
            count,
        )


def test_required_constructor_types_are_enforced() -> None:
    with pytest.raises(ValueError, match="Settings"):
        MT5Client(
            settings="invalid",
            adapter=FakeMT5Adapter(),
        )

    with pytest.raises(ValueError, match="MT5Adapter"):
        MT5Client(
            settings=create_settings(),
            adapter=object(),
        )
