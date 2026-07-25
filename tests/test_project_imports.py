import importlib

import pytest

PROJECT_MODULES = [
    "app.config.constants",
    "app.config.settings",
    "app.domain",
    "app.domain.exposure",
    "app.domain.risk",
    "app.domain.trading",
    "app.logs.logger",
    "app.broker.account_service",
    "app.broker.mt5_client",
    "app.broker.symbol_service",
    "app.market.candle_model",
    "app.market.market_data_service",
    "app.market.market_data_validator",
    "app.market.timeframes",
    "app.safety.trading_permission_guard",
]


@pytest.mark.parametrize("module_name", PROJECT_MODULES)
def test_project_module_imports_without_starting_bot(
    module_name: str,
) -> None:
    imported_module = importlib.import_module(module_name)

    assert imported_module is not None
