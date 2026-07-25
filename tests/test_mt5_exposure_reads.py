from typing import Any

import pytest

from app.broker.mt5_client import (
    MT5Client,
    MT5ConnectionError,
)
from app.config.settings import Settings


class FakeExposureAdapter:
    def __init__(self) -> None:
        self.error: Any = (0, "No error")
        self.positions: Any = ()
        self.orders: Any = ()
        self.position_symbols: list[str | None] = []
        self.order_symbols: list[str | None] = []

    def initialize(
        self,
        *,
        path: str | None = None,
    ) -> bool:
        return True

    def shutdown(self) -> None:
        return None

    def last_error(self) -> Any:
        return self.error

    def terminal_info(self) -> Any:
        return object()

    def account_info(self) -> Any:
        return object()

    def symbol_info(self, symbol: str) -> Any:
        return object()

    def symbol_info_tick(self, symbol: str) -> Any:
        return object()

    def symbols_get(self) -> Any:
        return ()

    def symbol_select(
        self,
        symbol: str,
        enable: bool = True,
    ) -> bool:
        return True

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        return ()

    def positions_get(
        self,
        *,
        symbol: str | None = None,
    ) -> Any:
        self.position_symbols.append(symbol)
        return self.positions

    def orders_get(
        self,
        *,
        symbol: str | None = None,
    ) -> Any:
        self.order_symbols.append(symbol)
        return self.orders


class FakeAdapterWithoutExposureMethods:
    def initialize(
        self,
        *,
        path: str | None = None,
    ) -> bool:
        return True

    def shutdown(self) -> None:
        return None

    def last_error(self) -> Any:
        return (0, "No error")

    def terminal_info(self) -> Any:
        return object()

    def account_info(self) -> Any:
        return object()

    def symbol_info(self, symbol: str) -> Any:
        return object()

    def symbol_info_tick(self, symbol: str) -> Any:
        return object()

    def symbols_get(self) -> Any:
        return ()

    def symbol_select(
        self,
        symbol: str,
        enable: bool = True,
    ) -> bool:
        return True

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        return ()


def create_client(adapter: Any) -> MT5Client:
    return MT5Client(
        settings=Settings(_env_file=None),
        adapter=adapter,
    )


def test_exposure_reads_require_connection() -> None:
    client = create_client(FakeExposureAdapter())

    with pytest.raises(MT5ConnectionError):
        client.positions_get("XAUUSDm")

    with pytest.raises(MT5ConnectionError):
        client.orders_get("XAUUSDm")


def test_position_read_delegates_symbol_filter() -> None:
    adapter = FakeExposureAdapter()
    adapter.positions = ("position",)

    client = create_client(adapter)
    client.connect_or_raise()

    assert client.positions_get("XAUUSDm") == ("position",)
    assert adapter.position_symbols == ["XAUUSDm"]


def test_order_read_delegates_symbol_filter() -> None:
    adapter = FakeExposureAdapter()
    adapter.orders = ("order",)

    client = create_client(adapter)
    client.connect_or_raise()

    assert client.orders_get("XAUUSDm") == ("order",)
    assert adapter.order_symbols == ["XAUUSDm"]


def test_all_symbol_reads_delegate_none() -> None:
    adapter = FakeExposureAdapter()
    client = create_client(adapter)
    client.connect_or_raise()

    client.positions_get()
    client.orders_get()

    assert adapter.position_symbols == [None]
    assert adapter.order_symbols == [None]


def test_blank_symbol_is_rejected() -> None:
    client = create_client(FakeExposureAdapter())
    client.connect_or_raise()

    with pytest.raises(ValueError):
        client.positions_get(" ")

    with pytest.raises(ValueError):
        client.orders_get("\n")


def test_none_position_result_captures_error() -> None:
    adapter = FakeExposureAdapter()
    adapter.positions = None
    adapter.error = (404, "Positions unavailable")

    client = create_client(adapter)
    client.connect_or_raise()

    assert client.positions_get("XAUUSDm") is None
    assert client.last_error() == (
        404,
        "Positions unavailable",
    )


def test_adapter_without_position_method_is_blocked() -> None:
    client = create_client(FakeAdapterWithoutExposureMethods())
    client.connect_or_raise()

    with pytest.raises(
        MT5ConnectionError,
        match="positions_get",
    ):
        client.positions_get("XAUUSDm")


def test_adapter_without_order_method_is_blocked() -> None:
    client = create_client(FakeAdapterWithoutExposureMethods())
    client.connect_or_raise()

    with pytest.raises(
        MT5ConnectionError,
        match="orders_get",
    ):
        client.orders_get("XAUUSDm")
