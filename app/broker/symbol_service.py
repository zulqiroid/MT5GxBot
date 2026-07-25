from __future__ import annotations

from loguru import logger

from app.broker.mt5_client import MT5Client
from app.config.settings import Settings


class SymbolService:
    """
    Handles broker symbol discovery and symbol-level checks.
    """

    def __init__(self, mt5_client: MT5Client, settings: Settings) -> None:
        self._mt5 = mt5_client
        self._settings = settings

    def find_gold_symbol(self) -> str | None:
        """
        Tries configured gold symbols first.
        If not found, searches all broker symbols containing XAU or GOLD.
        """

        for symbol in self._settings.gold_symbol_candidates:
            info = self._mt5.symbol_info(symbol)

            if info is not None:
                if not info.visible:
                    self._mt5.symbol_select(symbol, True)

                logger.success("Gold symbol detected from config: {}", symbol)
                return symbol

        all_symbols = self._mt5.symbols_get()

        if all_symbols is None:
            return None

        for item in all_symbols:
            symbol_name = item.name
            upper_name = symbol_name.upper()

            if "XAU" in upper_name or "GOLD" in upper_name:
                if not item.visible:
                    self._mt5.symbol_select(symbol_name, True)

                logger.success("Gold symbol detected from broker list: {}", symbol_name)
                return symbol_name

        logger.error(
            "No gold symbol found. Check MT5 Market Watch and GOLD_SYMBOL_CANDIDATES."
        )
        return None

    def log_symbol_info(self, symbol: str) -> None:
        info = self._mt5.symbol_info(symbol)
        tick = self._mt5.symbol_info_tick(symbol)

        if info is None:
            logger.error("Symbol info not found for {}", symbol)
            return

        if tick is None:
            logger.error("Tick info not found for {}", symbol)
            return

        logger.info("========== GOLD SYMBOL INFO ==========")
        logger.info("Symbol: {}", symbol)
        logger.info("Description: {}", info.description)
        logger.info("Visible: {}", info.visible)
        logger.info("Bid: {}", tick.bid)
        logger.info("Ask: {}", tick.ask)
        logger.info("Spread Points: {}", info.spread)
        logger.info("Max Allowed Spread Points: {}", self._settings.max_spread_points)
        logger.info("Point: {}", info.point)
        logger.info("Digits: {}", info.digits)
        logger.info("Min Lot: {}", info.volume_min)
        logger.info("Max Lot: {}", info.volume_max)
        logger.info("Lot Step: {}", info.volume_step)
        logger.info("Trade Mode: {}", info.trade_mode)

    def is_spread_acceptable(self, symbol: str) -> bool:
        info = self._mt5.symbol_info(symbol)

        if info is None:
            logger.error("Cannot validate spread. Symbol info missing: {}", symbol)
            return False

        if info.spread > self._settings.max_spread_points:
            logger.warning(
                "Spread too high. Symbol: {}, Current: {}, Max Allowed: {}",
                symbol,
                info.spread,
                self._settings.max_spread_points,
            )
            return False

        logger.info(
            "Spread accepted. Symbol: {}, Current: {}, Max Allowed: {}",
            symbol,
            info.spread,
            self._settings.max_spread_points,
        )
        return True
