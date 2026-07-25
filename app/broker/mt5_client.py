from __future__ import annotations

from types import TracebackType

import MetaTrader5 as mt5
from loguru import logger

from app.config.settings import Settings


class MT5Client:
    """
    Enterprise wrapper around MetaTrader5 Python package.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._initialized = False

    def initialize(self) -> bool:
        if self._initialized:
            logger.debug("MT5 is already initialized.")
            return True

        if self._settings.mt5_terminal_path:
            initialized = mt5.initialize(path=self._settings.mt5_terminal_path)
        else:
            initialized = mt5.initialize()

        if not initialized:
            logger.error("MT5 initialize failed. Error: {}", mt5.last_error())
            return False

        self._initialized = True
        logger.success("MT5 initialized successfully.")
        return True

    def shutdown(self) -> None:
        if self._initialized:
            mt5.shutdown()
            self._initialized = False
            logger.info("MT5 connection closed safely.")

    def __enter__(self) -> "MT5Client":
        if not self.initialize():
            raise RuntimeError(f"MT5 initialize failed. Error: {mt5.last_error()}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.shutdown()

    @staticmethod
    def last_error() -> tuple[int, str]:
        return mt5.last_error()

    @staticmethod
    def terminal_info():
        info = mt5.terminal_info()
        if info is None:
            logger.error("Could not read terminal info. Error: {}", mt5.last_error())
        return info

    @staticmethod
    def account_info():
        info = mt5.account_info()
        if info is None:
            logger.error("Could not read account info. Error: {}", mt5.last_error())
        return info

    @staticmethod
    def symbol_info(symbol: str):
        return mt5.symbol_info(symbol)

    @staticmethod
    def symbol_info_tick(symbol: str):
        return mt5.symbol_info_tick(symbol)

    @staticmethod
    def symbols_get():
        symbols = mt5.symbols_get()
        if symbols is None:
            logger.error("Could not fetch broker symbols. Error: {}", mt5.last_error())
        return symbols

    @staticmethod
    def symbol_select(symbol: str, enable: bool = True) -> bool:
        selected = mt5.symbol_select(symbol, enable)
        if not selected:
            logger.error(
                "Could not change symbol visibility. Symbol: {}, Error: {}",
                symbol,
                mt5.last_error(),
            )
        return selected

    @staticmethod
    def copy_rates_from_pos(symbol: str, timeframe: int, start_pos: int, count: int):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
        if rates is None:
            logger.error(
                "Could not fetch candles. Symbol: {}, Error: {}",
                symbol,
                mt5.last_error(),
            )
        return rates
