from __future__ import annotations

from dataclasses import dataclass

import MetaTrader5 as mt5
from loguru import logger

from app.broker.account_service import AccountService
from app.broker.mt5_client import MT5Client
from app.config.constants import BotMode
from app.config.settings import Settings


@dataclass(frozen=True)
class TradingPermissionReport:
    terminal_connected: bool
    terminal_trade_allowed: bool
    account_trade_allowed: bool
    account_expert_allowed: bool
    symbol_trade_mode: int | None
    symbol_trade_mode_name: str
    spread_ok: bool
    live_mode_blocked: bool
    safe_for_future_order: bool
    reasons: tuple[str, ...]


class TradingPermissionGuard:
    """
    Central safety gate for future trade execution.

    Important:
    - This class does NOT place trades.
    - Execution engine will later call this before every order.
    - If safe_for_future_order=False, order placement must be blocked.
    """

    def __init__(
        self,
        mt5_client: MT5Client,
        account_service: AccountService,
        settings: Settings,
    ) -> None:
        self._mt5 = mt5_client
        self._account_service = account_service
        self._settings = settings

    def run_diagnostics(self, symbol: str) -> TradingPermissionReport:
        reasons: list[str] = []

        terminal_info = self._account_service.get_terminal_info()
        account_info = self._account_service.get_account_info()
        symbol_info = self._mt5.symbol_info(symbol)

        terminal_connected = bool(getattr(terminal_info, "connected", False))
        terminal_trade_allowed = bool(getattr(terminal_info, "trade_allowed", False))
        account_trade_allowed = bool(getattr(account_info, "trade_allowed", False))
        account_expert_allowed = bool(getattr(account_info, "trade_expert", False))

        symbol_trade_mode = None
        symbol_trade_mode_name = "UNKNOWN"
        spread_ok = False

        if not terminal_connected:
            reasons.append("MT5 terminal is not connected.")

        if not terminal_trade_allowed:
            reasons.append(
                "MT5 terminal trading is disabled. Enable Algo Trading / automated trading in MT5 when execution phase starts."
            )

        if not account_trade_allowed:
            reasons.append("Account trading is not allowed by terminal/broker/account permissions.")

        if not account_expert_allowed:
            reasons.append("Expert/algorithmic trading is not allowed for this account/session.")

        if symbol_info is None:
            reasons.append(f"Symbol info missing for {symbol}.")
        else:
            symbol_trade_mode = int(symbol_info.trade_mode)
            symbol_trade_mode_name = self._get_symbol_trade_mode_name(symbol_trade_mode)

            if symbol_trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
                reasons.append(
                    f"Symbol trading is not FULL mode. Current mode: {symbol_trade_mode_name}."
                )

            spread_ok = symbol_info.spread <= self._settings.max_spread_points

            if not spread_ok:
                reasons.append(
                    f"Spread too high. Current: {symbol_info.spread}, Max Allowed: {self._settings.max_spread_points}."
                )

        live_mode_blocked = (
            self._settings.bot_mode == BotMode.LIVE and not self._settings.enable_live_trading
        )

        if live_mode_blocked:
            reasons.append("LIVE mode is blocked because ENABLE_LIVE_TRADING=false.")

        safe_for_future_order = (
            terminal_connected
            and terminal_trade_allowed
            and account_trade_allowed
            and account_expert_allowed
            and symbol_trade_mode == mt5.SYMBOL_TRADE_MODE_FULL
            and spread_ok
            and not live_mode_blocked
        )

        report = TradingPermissionReport(
            terminal_connected=terminal_connected,
            terminal_trade_allowed=terminal_trade_allowed,
            account_trade_allowed=account_trade_allowed,
            account_expert_allowed=account_expert_allowed,
            symbol_trade_mode=symbol_trade_mode,
            symbol_trade_mode_name=symbol_trade_mode_name,
            spread_ok=spread_ok,
            live_mode_blocked=live_mode_blocked,
            safe_for_future_order=safe_for_future_order,
            reasons=tuple(reasons),
        )

        self.log_report(report)

        return report

    def log_report(self, report: TradingPermissionReport) -> None:
        logger.info("========== TRADING PERMISSION DIAGNOSTICS ==========")
        logger.info("Terminal Connected: {}", report.terminal_connected)
        logger.info("Terminal Trade Allowed: {}", report.terminal_trade_allowed)
        logger.info("Account Trade Allowed: {}", report.account_trade_allowed)
        logger.info("Account Expert Allowed: {}", report.account_expert_allowed)
        logger.info(
            "Symbol Trade Mode: {} ({})",
            report.symbol_trade_mode,
            report.symbol_trade_mode_name,
        )
        logger.info("Spread OK: {}", report.spread_ok)
        logger.info("Live Mode Blocked: {}", report.live_mode_blocked)
        logger.info("Safe For Future Order: {}", report.safe_for_future_order)

        if report.reasons:
            logger.warning("Safety reasons:")
            for reason in report.reasons:
                logger.warning("- {}", reason)
        else:
            logger.success("All trading permission diagnostics passed.")

    @staticmethod
    def _get_symbol_trade_mode_name(trade_mode: int) -> str:
        mapping = {
            mt5.SYMBOL_TRADE_MODE_DISABLED: "DISABLED",
            mt5.SYMBOL_TRADE_MODE_LONGONLY: "LONG_ONLY",
            mt5.SYMBOL_TRADE_MODE_SHORTONLY: "SHORT_ONLY",
            mt5.SYMBOL_TRADE_MODE_CLOSEONLY: "CLOSE_ONLY",
            mt5.SYMBOL_TRADE_MODE_FULL: "FULL",
        }

        return mapping.get(trade_mode, "UNKNOWN")
