from __future__ import annotations

import sys
from datetime import datetime

from loguru import logger

from app.broker.account_service import AccountService
from app.broker.mt5_client import MT5Client
from app.broker.symbol_service import SymbolService
from app.config.settings import Settings, get_settings
from app.logs.logger import configure_logger
from app.market.market_data_service import MarketDataService
from app.safety.trading_permission_guard import TradingPermissionGuard


def log_startup_banner(settings: Settings) -> None:
    logger.info("==========================================")
    logger.info("🚀 {} starting", settings.app_name)
    logger.info("Started at: {}", datetime.now())
    logger.info("Environment: {}", settings.app_env.value)
    logger.info("Bot Mode: {}", settings.bot_mode.value)
    logger.info("Live Trading Enabled: {}", settings.enable_live_trading)
    logger.info("Timeframe: {}", settings.timeframe.value)
    logger.info("Candles Count: {}", settings.candles_count)
    logger.info("Risk Per Trade: {}%", settings.risk_per_trade_percent)
    logger.info("Max Daily Loss: {}%", settings.max_daily_loss_percent)
    logger.info("Max Spread Points: {}", settings.max_spread_points)
    logger.info("==========================================")


def run_health_check(settings: Settings) -> int:
    log_startup_banner(settings)

    mt5_client = MT5Client(settings=settings)

    with mt5_client:
        account_service = AccountService(mt5_client=mt5_client)
        account_service.log_terminal_info()
        account_service.log_account_info()

        symbol_service = SymbolService(
            mt5_client=mt5_client,
            settings=settings,
        )

        gold_symbol = symbol_service.find_gold_symbol()

        if gold_symbol is None:
            return 1

        symbol_service.log_symbol_info(gold_symbol)

        permission_guard = TradingPermissionGuard(
            mt5_client=mt5_client,
            account_service=account_service,
            settings=settings,
        )

        permission_report = permission_guard.run_diagnostics(gold_symbol)

        if not permission_report.safe_for_future_order:
            logger.warning("Future order execution is currently blocked by safety diagnostics.")
            logger.warning("This is OK in Phase 1 because we are not placing trades yet.")

        market_data_service = MarketDataService(
            mt5_client=mt5_client,
            settings=settings,
        )

        market_data_service.log_latest_candles(
            symbol=gold_symbol,
            count=10,
        )

        logger.success("Phase 1 Step 1.4 completed successfully.")
        logger.info("No trade was placed. This was only a safety diagnostic test.")

    return 0


def main() -> int:
    settings = get_settings()
    configure_logger(settings)
    return run_health_check(settings)


if __name__ == "__main__":
    sys.exit(main())
