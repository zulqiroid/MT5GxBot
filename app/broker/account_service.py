from __future__ import annotations

from loguru import logger

from app.broker.mt5_client import MT5Client


class AccountService:
    """
    Reads and logs MT5 terminal/account information.

    Purpose:
    - Keep account diagnostics separate from main.py.
    - Provide clean account/terminal status for safety guards.
    """

    def __init__(self, mt5_client: MT5Client) -> None:
        self._mt5 = mt5_client

    def get_terminal_info(self):
        return self._mt5.terminal_info()

    def get_account_info(self):
        return self._mt5.account_info()

    def log_terminal_info(self) -> None:
        terminal_info = self.get_terminal_info()

        if terminal_info is None:
            return

        logger.info("========== TERMINAL INFO ==========")
        logger.info("Connected: {}", terminal_info.connected)
        logger.info("Trade Allowed: {}", terminal_info.trade_allowed)
        logger.info("Company: {}", terminal_info.company)
        logger.info("Name: {}", terminal_info.name)
        logger.info("Path: {}", terminal_info.path)

    def log_account_info(self) -> None:
        account_info = self.get_account_info()

        if account_info is None:
            return

        logger.info("========== ACCOUNT INFO ==========")
        logger.info("Login: {}", account_info.login)
        logger.info("Server: {}", account_info.server)
        logger.info("Currency: {}", account_info.currency)
        logger.info("Balance: {}", account_info.balance)
        logger.info("Equity: {}", account_info.equity)
        logger.info("Margin Free: {}", account_info.margin_free)
        logger.info("Leverage: 1:{}", account_info.leverage)
        logger.info("Account Trade Allowed: {}", getattr(account_info, "trade_allowed", None))
        logger.info("Expert Trading Allowed: {}", getattr(account_info, "trade_expert", None))
        logger.info("Trade Mode: {}", getattr(account_info, "trade_mode", None))
