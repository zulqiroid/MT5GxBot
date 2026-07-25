from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.broker.mt5_client import MT5ConnectionError
from app.broker.symbol_service import (
    GoldSymbolService,
    SymbolService,
    SymbolServiceError,
    SymbolServiceErrorReason,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


class FakeSymbolClient:
    def __init__(self) -> None:
        self.initialized = True
        self.symbols_exception: Exception | None = None
        self.info_exception: Exception | None = None
        self.tick_exception: Exception | None = None
        self.select_exception: Exception | None = None
        self.select_result = True

        self.symbols_calls = 0
        self.info_calls: list[str] = []
        self.tick_calls: list[str] = []
        self.select_calls: list[tuple[str, bool]] = []

        self.symbols: Any = (
            SimpleNamespace(name="EURUSD"),
            SimpleNamespace(name="XAUUSDm"),
        )

        self.infos: dict[str, Any] = {
            "XAUUSDm": SimpleNamespace(
                name="XAUUSDm",
                visible=True,
                digits=2,
                point="0.01",
                trade_tick_size="0.01",
                trade_tick_value="1.00",
                trade_tick_value_profit="0.95",
                trade_tick_value_loss="1.05",
                volume_min="0.01",
                volume_max="100.00",
                volume_step="0.01",
                description="Gold vs US Dollar",
                path="Metals/Gold",
            )
        }

        self.ticks: dict[str, Any] = {
            "XAUUSDm": SimpleNamespace(
                bid="2400.10",
                ask="2400.30",
            )
        }

    def symbols_get(self) -> Any:
        self.symbols_calls += 1

        if self.symbols_exception is not None:
            raise self.symbols_exception

        return self.symbols

    def symbol_info(self, symbol: str) -> Any:
        self.info_calls.append(symbol)

        if self.info_exception is not None:
            raise self.info_exception

        return self.infos.get(symbol)

    def symbol_info_tick(self, symbol: str) -> Any:
        self.tick_calls.append(symbol)

        if self.tick_exception is not None:
            raise self.tick_exception

        return self.ticks.get(symbol)

    def symbol_select(
        self,
        symbol: str,
        enable: bool = True,
    ) -> bool:
        self.select_calls.append((symbol, enable))

        if self.select_exception is not None:
            raise self.select_exception

        if self.select_result:
            info = self.infos.get(symbol)

            if info is not None:
                if isinstance(info, dict):
                    info["visible"] = enable
                else:
                    info.visible = enable

        return self.select_result


def create_service(
    client: FakeSymbolClient | None = None,
    candidates: tuple[str, ...] | None = None,
    clock=lambda: NOW,
) -> tuple[SymbolService, FakeSymbolClient]:
    selected_client = client or FakeSymbolClient()

    keyword_arguments: dict[str, object] = {
        "mt5_client": selected_client,
        "clock": clock,
    }

    if candidates is not None:
        keyword_arguments["candidates"] = candidates

    return (
        SymbolService(**keyword_arguments),
        selected_client,
    )


def test_default_candidates_resolve_broker_suffix() -> None:
    service, client = create_service()

    assert service.resolve_symbol() == "XAUUSDm"
    assert client.symbols_calls == 1


def test_exact_candidate_priority_is_preserved() -> None:
    client = FakeSymbolClient()
    client.symbols = (
        SimpleNamespace(name="XAUUSDm"),
        SimpleNamespace(name="XAUUSD"),
    )

    service, _ = create_service(client)

    assert service.resolve_symbol() == "XAUUSD"


def test_case_insensitive_resolution_returns_actual_name() -> None:
    client = FakeSymbolClient()
    client.symbols = (SimpleNamespace(name="xauusdm"),)

    service, _ = create_service(client)

    assert service.resolve_symbol() == "xauusdm"


def test_custom_candidate_order_is_preserved() -> None:
    client = FakeSymbolClient()
    client.symbols = (
        SimpleNamespace(name="GOLD"),
        SimpleNamespace(name="XAUUSDm"),
    )

    service, _ = create_service(
        client,
        candidates=("GOLD", "XAUUSDm"),
    )

    assert service.resolve_symbol() == "GOLD"


def test_candidate_duplicates_are_removed() -> None:
    service, _ = create_service(
        candidates=(
            "XAUUSD",
            "xauusd",
            "XAUUSDm",
        )
    )

    assert service.candidates == (
        "XAUUSD",
        "XAUUSDm",
    )


def test_find_gold_symbol_compatibility_method() -> None:
    service, _ = create_service()

    assert service.find_gold_symbol() == "XAUUSDm"


def test_gold_symbol_service_alias_is_preserved() -> None:
    assert GoldSymbolService is SymbolService


def test_disconnected_client_is_blocked() -> None:
    client = FakeSymbolClient()
    client.initialized = False

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="CONNECTION_REQUIRED",
    ) as captured:
        service.resolve_symbol()

    assert captured.value.reason == SymbolServiceErrorReason.CONNECTION_REQUIRED
    assert client.symbols_calls == 0


def test_none_symbol_list_is_blocked() -> None:
    client = FakeSymbolClient()
    client.symbols = None

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="SYMBOL_LIST_UNAVAILABLE",
    ):
        service.resolve_symbol()


def test_empty_symbol_list_is_blocked() -> None:
    client = FakeSymbolClient()
    client.symbols = ()

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="NO_GOLD_SYMBOL_FOUND",
    ):
        service.resolve_symbol()


def test_missing_gold_symbol_is_blocked() -> None:
    client = FakeSymbolClient()
    client.symbols = (
        SimpleNamespace(name="EURUSD"),
        SimpleNamespace(name="GBPUSD"),
    )

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="NO_GOLD_SYMBOL_FOUND",
    ):
        service.resolve_symbol()


def test_symbol_list_exception_is_wrapped() -> None:
    client = FakeSymbolClient()
    client.symbols_exception = RuntimeError("symbol list failure")

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="RuntimeError",
    ) as captured:
        service.resolve_symbol()

    assert captured.value.reason == SymbolServiceErrorReason.SYMBOL_READ_FAILED


def test_mt5_connection_error_is_wrapped() -> None:
    client = FakeSymbolClient()
    client.symbols_exception = MT5ConnectionError(
        500,
        "connection lost",
    )

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="connection lost",
    ):
        service.resolve_symbol()


def test_symbol_snapshot_maps_broker_data() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(account_currency="usd")

    assert snapshot.canonical_symbol == "XAUUSD"
    assert snapshot.broker_symbol == "XAUUSDm"
    assert snapshot.bid == Decimal("2400.10")
    assert snapshot.ask == Decimal("2400.30")
    assert snapshot.point == Decimal("0.01")
    assert snapshot.digits == 2
    assert snapshot.visible is True
    assert snapshot.observed_at == NOW
    assert snapshot.description == "Gold vs US Dollar"
    assert snapshot.path == "Metals/Gold"


def test_symbol_specification_is_mapped() -> None:
    service, _ = create_service()

    specification = service.read_snapshot(account_currency="USD").specification

    assert specification.symbol == "XAUUSD"
    assert specification.account_currency == "USD"
    assert specification.tick_size == Decimal("0.01")
    assert specification.tick_value_per_lot == Decimal("1.05")
    assert specification.volume_min == Decimal("0.01")
    assert specification.volume_max == Decimal("100.00")
    assert specification.volume_step == Decimal("0.01")


def test_largest_tick_value_is_used_conservatively() -> None:
    client = FakeSymbolClient()
    client.infos["XAUUSDm"].trade_tick_value_profit = "1.25"
    client.infos["XAUUSDm"].trade_tick_value_loss = "1.10"

    service, _ = create_service(client)

    specification = service.read_snapshot(account_currency="USD").specification

    assert specification.tick_value_per_lot == Decimal("1.25")


def test_non_positive_optional_tick_values_are_ignored() -> None:
    client = FakeSymbolClient()
    info = client.infos["XAUUSDm"]

    info.trade_tick_value_loss = "0"
    info.trade_tick_value_profit = "-1"
    info.trade_tick_value = "1.00"

    service, _ = create_service(client)

    specification = service.read_snapshot(account_currency="USD").specification

    assert specification.tick_value_per_lot == Decimal("1.00")


def test_spread_metrics_are_exact() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(account_currency="USD")

    assert snapshot.raw_spread == Decimal("0.20")
    assert snapshot.spread_points == Decimal("20")
    assert snapshot.midpoint == Decimal("2400.20")
    assert snapshot.spread_within("20") is True
    assert snapshot.spread_within("19.99") is False


def test_negative_spread_limit_is_rejected() -> None:
    service, _ = create_service()

    snapshot = service.read_snapshot(account_currency="USD")

    with pytest.raises(ValueError, match="negative"):
        snapshot.spread_within("-1")


def test_invisible_symbol_is_selected() -> None:
    client = FakeSymbolClient()
    client.infos["XAUUSDm"].visible = False

    service, _ = create_service(client)

    snapshot = service.read_snapshot(account_currency="USD")

    assert snapshot.visible is True
    assert client.select_calls == [("XAUUSDm", True)]
    assert client.info_calls == [
        "XAUUSDm",
        "XAUUSDm",
    ]


def test_symbol_selection_failure_is_blocked() -> None:
    client = FakeSymbolClient()
    client.infos["XAUUSDm"].visible = False
    client.select_result = False

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="SYMBOL_SELECTION_FAILED",
    ):
        service.read_snapshot(account_currency="USD")


def test_symbol_remaining_invisible_is_blocked() -> None:
    client = FakeSymbolClient()
    client.infos["XAUUSDm"].visible = False

    def select_without_visibility(
        symbol: str,
        enable: bool = True,
    ) -> bool:
        client.select_calls.append((symbol, enable))
        return True

    client.symbol_select = select_without_visibility

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="remained invisible",
    ):
        service.read_snapshot(account_currency="USD")


def test_missing_symbol_info_is_blocked() -> None:
    client = FakeSymbolClient()
    client.infos = {}

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="SYMBOL_INFO_UNAVAILABLE",
    ):
        service.read_snapshot(account_currency="USD")


def test_missing_tick_is_blocked() -> None:
    client = FakeSymbolClient()
    client.ticks = {}

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="TICK_INFO_UNAVAILABLE",
    ):
        service.read_snapshot(account_currency="USD")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("visible", "yes"),
        ("digits", -1),
        ("point", "0"),
        ("trade_tick_size", "0"),
        ("volume_min", "0"),
        ("volume_max", "0"),
        ("volume_step", "0"),
    ],
)
def test_invalid_symbol_fields_are_blocked(
    field_name: str,
    value: object,
) -> None:
    client = FakeSymbolClient()
    setattr(
        client.infos["XAUUSDm"],
        field_name,
        value,
    )

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="INVALID_SYMBOL_DATA",
    ):
        service.read_snapshot(account_currency="USD")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("bid", "0"),
        ("ask", "NaN"),
    ],
)
def test_invalid_tick_fields_are_blocked(
    field_name: str,
    value: object,
) -> None:
    client = FakeSymbolClient()
    setattr(
        client.ticks["XAUUSDm"],
        field_name,
        value,
    )

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="INVALID_SYMBOL_DATA",
    ):
        service.read_snapshot(account_currency="USD")


def test_ask_below_bid_is_blocked() -> None:
    client = FakeSymbolClient()
    client.ticks["XAUUSDm"].ask = "2399.00"

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="ask cannot be below bid",
    ):
        service.read_snapshot(account_currency="USD")


def test_no_positive_tick_value_is_blocked() -> None:
    client = FakeSymbolClient()
    info = client.infos["XAUUSDm"]

    info.trade_tick_value = "0"
    info.trade_tick_value_profit = "0"
    info.trade_tick_value_loss = "0"

    service, _ = create_service(client)

    with pytest.raises(
        SymbolServiceError,
        match="tick value",
    ):
        service.read_snapshot(account_currency="USD")


def test_mapping_symbol_and_tick_data_are_supported() -> None:
    client = FakeSymbolClient()
    client.symbols = ({"name": "XAUUSDm"},)
    client.infos["XAUUSDm"] = {
        "name": "XAUUSDm",
        "visible": True,
        "digits": 2,
        "point": "0.01",
        "trade_tick_size": "0.01",
        "trade_tick_value": "1.00",
        "trade_tick_value_profit": "1.00",
        "trade_tick_value_loss": "1.05",
        "volume_min": "0.01",
        "volume_max": "100.00",
        "volume_step": "0.01",
        "description": "Mapping Gold",
        "path": "Metals",
    }
    client.ticks["XAUUSDm"] = {
        "bid": "2400.00",
        "ask": "2400.20",
    }

    service, _ = create_service(client)

    snapshot = service.read_snapshot(account_currency="USD")

    assert snapshot.broker_symbol == "XAUUSDm"
    assert snapshot.description == "Mapping Gold"
    assert snapshot.spread_points == Decimal("20")


def test_clock_is_normalized_to_utc() -> None:
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

    snapshot = service.read_snapshot(account_currency="USD")

    assert snapshot.observed_at == NOW
    assert snapshot.observed_at.tzinfo == timezone.utc


def test_naive_clock_is_blocked() -> None:
    service, _ = create_service(
        clock=lambda: datetime(
            2026,
            7,
            25,
            12,
            0,
        )
    )

    with pytest.raises(
        SymbolServiceError,
        match="INVALID_CLOCK",
    ):
        service.read_snapshot(account_currency="USD")


def test_get_symbol_info_compatibility_method() -> None:
    service, client = create_service()

    result = service.get_symbol_info("XAUUSDm")

    assert result is client.infos["XAUUSDm"]


def test_log_symbol_info_reads_snapshot() -> None:
    service, client = create_service()

    service.log_symbol_info(account_currency="USD")

    assert client.symbols_calls == 1
    assert client.info_calls == ["XAUUSDm"]
    assert client.tick_calls == ["XAUUSDm"]


def test_constructor_requires_symbol_client() -> None:
    with pytest.raises(
        ValueError,
        match="SymbolInfoClient",
    ):
        SymbolService(
            mt5_client=object(),
        )


def test_constructor_requires_candidates() -> None:
    client = FakeSymbolClient()

    with pytest.raises(
        ValueError,
        match="At least one",
    ):
        SymbolService(
            mt5_client=client,
            candidates=(),
        )


def test_constructor_rejects_invalid_candidate() -> None:
    client = FakeSymbolClient()

    with pytest.raises(ValueError):
        SymbolService(
            mt5_client=client,
            candidates=("",),
        )


def test_constructor_requires_callable_clock() -> None:
    client = FakeSymbolClient()

    with pytest.raises(ValueError, match="clock"):
        SymbolService(
            mt5_client=client,
            clock="invalid",
        )
