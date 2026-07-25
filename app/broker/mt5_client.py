from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import RLock
from types import TracebackType
from typing import Any, Protocol, runtime_checkable

import MetaTrader5 as mt5
from loguru import logger

from app.config.settings import Settings

MT5Error = tuple[int, str]


class MT5ConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    FAILED = "FAILED"


class MT5ConnectionError(RuntimeError):
    """Raised when an MT5 operation requires a valid connection."""

    def __init__(self, code: int, message: str) -> None:
        self.code = int(code)
        self.message = str(message)

        super().__init__(f"MT5 connection error [{self.code}]: {self.message}")


@dataclass(frozen=True, slots=True)
class MT5ConnectionSnapshot:
    """Immutable diagnostic view of the current MT5 connection."""

    state: MT5ConnectionState
    initialized: bool
    terminal_available: bool
    account_available: bool
    terminal_connected: bool
    account_login: int | None
    last_error_code: int
    last_error_message: str


@runtime_checkable
class MT5Adapter(Protocol):
    """Minimum read-only MT5 interface required by GoldXBot."""

    def initialize(
        self,
        *,
        path: str | None = None,
    ) -> bool: ...

    def shutdown(self) -> None: ...

    def last_error(self) -> Any: ...

    def terminal_info(self) -> Any: ...

    def account_info(self) -> Any: ...

    def symbol_info(self, symbol: str) -> Any: ...

    def symbol_info_tick(self, symbol: str) -> Any: ...

    def symbols_get(self) -> Any: ...

    def symbol_select(
        self,
        symbol: str,
        enable: bool = True,
    ) -> bool: ...

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any: ...


class MetaTrader5Adapter:
    """Thin adapter around the installed MetaTrader5 package."""

    def initialize(
        self,
        *,
        path: str | None = None,
    ) -> bool:
        if path is None:
            return bool(mt5.initialize())

        return bool(mt5.initialize(path=path))

    def shutdown(self) -> None:
        mt5.shutdown()

    def last_error(self) -> Any:
        return mt5.last_error()

    def terminal_info(self) -> Any:
        return mt5.terminal_info()

    def account_info(self) -> Any:
        return mt5.account_info()

    def symbol_info(self, symbol: str) -> Any:
        return mt5.symbol_info(symbol)

    def symbol_info_tick(self, symbol: str) -> Any:
        return mt5.symbol_info_tick(symbol)

    def symbols_get(self) -> Any:
        return mt5.symbols_get()

    def symbol_select(
        self,
        symbol: str,
        enable: bool = True,
    ) -> bool:
        return bool(mt5.symbol_select(symbol, enable))

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        return mt5.copy_rates_from_pos(
            symbol,
            timeframe,
            start_pos,
            count,
        )


class MT5Client:
    """
    Thread-safe and testable MetaTrader5 connection gateway.

    Important:
    - This client contains no order placement methods.
    - Unit tests can inject a fake MT5Adapter.
    - Read operations require successful initialization.
    """

    def __init__(
        self,
        settings: Settings,
        adapter: MT5Adapter | None = None,
    ) -> None:
        if not isinstance(settings, Settings):
            raise ValueError("settings must be a Settings instance.")

        selected_adapter = adapter or MetaTrader5Adapter()

        if not isinstance(selected_adapter, MT5Adapter):
            raise ValueError("adapter must implement the MT5Adapter protocol.")

        self._settings = settings
        self._adapter = selected_adapter
        self._state = MT5ConnectionState.DISCONNECTED
        self._last_error: MT5Error = (0, "No error")
        self._lock = RLock()

    @property
    def state(self) -> MT5ConnectionState:
        with self._lock:
            return self._state

    @property
    def initialized(self) -> bool:
        with self._lock:
            return self._state == MT5ConnectionState.CONNECTED

    @property
    def settings(self) -> Settings:
        return self._settings

    def initialize(self) -> bool:
        """Initialize MT5 once and retain deterministic state."""

        with self._lock:
            if self._state == MT5ConnectionState.CONNECTED:
                logger.debug("MT5 is already initialized.")
                return True

            if self._state == MT5ConnectionState.CONNECTING:
                self._last_error = (
                    -1,
                    "MT5 initialization is already in progress.",
                )
                return False

            terminal_path = self._settings.mt5_terminal_path

            if terminal_path is not None:
                executable = Path(terminal_path)

                if not executable.is_file():
                    self._state = MT5ConnectionState.FAILED
                    self._last_error = (
                        -1,
                        f"Configured MT5 terminal executable does not exist: {executable}",
                    )

                    logger.error(self._last_error[1])
                    return False

            self._state = MT5ConnectionState.CONNECTING

            try:
                initialized = self._adapter.initialize(
                    path=terminal_path,
                )
            except Exception as error:
                self._state = MT5ConnectionState.FAILED
                self._last_error = (
                    -1,
                    f"MT5 initialization raised {type(error).__name__}: {error}",
                )

                logger.exception(self._last_error[1])
                return False

            if not initialized:
                self._state = MT5ConnectionState.FAILED
                self._capture_adapter_error()

                logger.error(
                    "MT5 initialization failed. Code: {}, Error: {}",
                    self._last_error[0],
                    self._last_error[1],
                )
                return False

            self._state = MT5ConnectionState.CONNECTED
            self._last_error = (0, "No error")

            logger.success("MT5 initialized successfully.")
            return True

    def connect_or_raise(self) -> None:
        """Initialize MT5 or raise a structured connection error."""

        if self.initialize():
            return

        code, message = self.last_error()
        raise MT5ConnectionError(code, message)

    def shutdown(self) -> None:
        """Safely close an initialized connection."""

        with self._lock:
            if self._state != MT5ConnectionState.CONNECTED:
                if self._state == MT5ConnectionState.CONNECTING:
                    self._last_error = (
                        -1,
                        "Cannot shut down while MT5 is connecting.",
                    )
                    self._state = MT5ConnectionState.FAILED
                    return

                self._state = MT5ConnectionState.DISCONNECTED
                return

            try:
                self._adapter.shutdown()
            except Exception as error:
                self._state = MT5ConnectionState.FAILED
                self._last_error = (
                    -1,
                    f"MT5 shutdown raised {type(error).__name__}: {error}",
                )

                logger.exception(self._last_error[1])
                return

            self._state = MT5ConnectionState.DISCONNECTED
            self._last_error = (0, "No error")

            logger.info("MT5 connection closed safely.")

    def last_error(self) -> MT5Error:
        with self._lock:
            return self._last_error

    def connection_snapshot(self) -> MT5ConnectionSnapshot:
        """Read terminal/account diagnostics without changing state."""

        with self._lock:
            if self._state != MT5ConnectionState.CONNECTED:
                return MT5ConnectionSnapshot(
                    state=self._state,
                    initialized=False,
                    terminal_available=False,
                    account_available=False,
                    terminal_connected=False,
                    account_login=None,
                    last_error_code=self._last_error[0],
                    last_error_message=self._last_error[1],
                )

            terminal = self._safe_adapter_read(
                "terminal_info",
                self._adapter.terminal_info,
            )
            account = self._safe_adapter_read(
                "account_info",
                self._adapter.account_info,
            )

            raw_login = getattr(account, "login", None)
            account_login: int | None = None

            if raw_login is not None:
                try:
                    account_login = int(raw_login)
                except (TypeError, ValueError):
                    account_login = None

            return MT5ConnectionSnapshot(
                state=self._state,
                initialized=True,
                terminal_available=terminal is not None,
                account_available=account is not None,
                terminal_connected=bool(getattr(terminal, "connected", False)),
                account_login=account_login,
                last_error_code=self._last_error[0],
                last_error_message=self._last_error[1],
            )

    def terminal_info(self) -> Any:
        with self._lock:
            self._require_initialized()

            return self._safe_adapter_read(
                "terminal_info",
                self._adapter.terminal_info,
            )

    def account_info(self) -> Any:
        with self._lock:
            self._require_initialized()

            return self._safe_adapter_read(
                "account_info",
                self._adapter.account_info,
            )

    def symbol_info(self, symbol: str) -> Any:
        normalized_symbol = self._required_symbol(symbol)

        with self._lock:
            self._require_initialized()

            return self._safe_adapter_read(
                "symbol_info",
                lambda: self._adapter.symbol_info(normalized_symbol),
            )

    def symbol_info_tick(self, symbol: str) -> Any:
        normalized_symbol = self._required_symbol(symbol)

        with self._lock:
            self._require_initialized()

            return self._safe_adapter_read(
                "symbol_info_tick",
                lambda: self._adapter.symbol_info_tick(normalized_symbol),
            )

    def symbols_get(self) -> Any:
        with self._lock:
            self._require_initialized()

            return self._safe_adapter_read(
                "symbols_get",
                self._adapter.symbols_get,
            )

    def symbol_select(
        self,
        symbol: str,
        enable: bool = True,
    ) -> bool:
        normalized_symbol = self._required_symbol(symbol)

        if not isinstance(enable, bool):
            raise ValueError("enable must be a boolean.")

        with self._lock:
            self._require_initialized()

            try:
                selected = self._adapter.symbol_select(
                    normalized_symbol,
                    enable,
                )
            except Exception as error:
                self._record_operation_exception(
                    "symbol_select",
                    error,
                )
                raise MT5ConnectionError(*self._last_error) from error

            if not selected:
                self._capture_adapter_error()

                logger.error(
                    "Could not change symbol visibility. Symbol: {}, Code: {}, Error: {}",
                    normalized_symbol,
                    self._last_error[0],
                    self._last_error[1],
                )
                return False

            self._last_error = (0, "No error")
            return True

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        normalized_symbol = self._required_symbol(symbol)

        if isinstance(timeframe, bool) or not isinstance(
            timeframe,
            int,
        ):
            raise ValueError("timeframe must be an integer.")

        if isinstance(start_pos, bool) or not isinstance(
            start_pos,
            int,
        ):
            raise ValueError("start_pos must be an integer.")

        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError("count must be an integer.")

        if start_pos < 0:
            raise ValueError("start_pos cannot be negative.")

        if count <= 0:
            raise ValueError("count must be greater than zero.")

        with self._lock:
            self._require_initialized()

            return self._safe_adapter_read(
                "copy_rates_from_pos",
                lambda: self._adapter.copy_rates_from_pos(
                    normalized_symbol,
                    timeframe,
                    start_pos,
                    count,
                ),
            )

    def __enter__(self) -> MT5Client:
        self.connect_or_raise()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.shutdown()

    def _require_initialized(self) -> None:
        if self._state == MT5ConnectionState.CONNECTED:
            return

        code, message = self._last_error

        if code == 0:
            code = -1
            message = "MT5 operation attempted before initialization."

        raise MT5ConnectionError(code, message)

    def _safe_adapter_read(
        self,
        operation_name: str,
        operation: Any,
    ) -> Any:
        try:
            result = operation()
        except Exception as error:
            self._record_operation_exception(
                operation_name,
                error,
            )
            raise MT5ConnectionError(*self._last_error) from error

        if result is None:
            self._capture_adapter_error()

            logger.error(
                "MT5 operation {} returned no data. Code: {}, Error: {}",
                operation_name,
                self._last_error[0],
                self._last_error[1],
            )
        else:
            self._last_error = (0, "No error")

        return result

    def _record_operation_exception(
        self,
        operation_name: str,
        error: Exception,
    ) -> None:
        self._last_error = (
            -1,
            f"MT5 operation {operation_name} raised {type(error).__name__}: {error}",
        )

        logger.exception(self._last_error[1])

    def _capture_adapter_error(self) -> None:
        try:
            raw_error = self._adapter.last_error()
        except Exception as error:
            self._last_error = (
                -1,
                f"Unable to read MT5 last_error: {type(error).__name__}: {error}",
            )
            return

        self._last_error = self._normalize_error(raw_error)

    @staticmethod
    def _normalize_error(raw_error: Any) -> MT5Error:
        if isinstance(raw_error, tuple) and len(raw_error) >= 2:
            try:
                code = int(raw_error[0])
            except (TypeError, ValueError):
                code = -1

            return code, str(raw_error[1])

        return -1, str(raw_error)

    @staticmethod
    def _required_symbol(symbol: str) -> str:
        normalized = str(symbol).strip()

        if not normalized:
            raise ValueError("symbol cannot be blank.")

        if "\n" in normalized or "\r" in normalized:
            raise ValueError("symbol cannot contain line breaks.")

        if len(normalized) > 64:
            raise ValueError("symbol cannot exceed 64 characters.")

        return normalized
