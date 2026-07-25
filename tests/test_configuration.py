from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config.constants import (
    LIVE_TRADING_CONFIRMATION_PHRASE,
    AppEnvironment,
    BotMode,
)
from app.config.settings import PROJECT_ROOT, Settings


def test_default_configuration_is_fail_safe() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == AppEnvironment.DEVELOPMENT
    assert settings.bot_mode == BotMode.PAPER
    assert settings.enable_live_trading is False
    assert settings.live_trading_armed is False
    assert settings.max_open_trades == 1
    assert settings.risk_per_trade_percent == 0.25
    assert settings.log_dir == (PROJECT_ROOT / "data/logs").resolve()


def test_environment_template_is_safe_and_parseable() -> None:
    env_example = PROJECT_ROOT / ".env.example"

    assert env_example.is_file()

    settings = Settings(_env_file=env_example)

    assert settings.bot_mode == BotMode.PAPER
    assert settings.enable_live_trading is False
    assert settings.live_trading_armed is False
    assert settings.max_open_trades == 1
    assert settings.gold_symbol_candidates == [
        "XAUUSD",
        "XAUUSDm",
        "XAUUSD.",
        "GOLD",
        "Gold",
    ]


@pytest.mark.parametrize(
    ("values", "expected_message"),
    [
        (
            {
                "risk_per_trade_percent": 0.75,
                "max_risk_per_trade_percent": 0.50,
            },
            "cannot exceed",
        ),
        (
            {
                "max_open_trades": 2,
            },
            "less than or equal to 1",
        ),
        (
            {
                "mt5_terminal_path": "terminal64.exe",
            },
            "absolute path",
        ),
    ],
)
def test_invalid_safety_configuration_is_blocked(
    values: dict[str, object],
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        Settings(_env_file=None, **values)


def test_live_mode_is_blocked_outside_production() -> None:
    with pytest.raises(ValidationError, match="APP_ENV=production"):
        Settings(
            _env_file=None,
            bot_mode=BotMode.LIVE,
            app_env=AppEnvironment.DEVELOPMENT,
            enable_live_trading=True,
            live_trading_confirmation=LIVE_TRADING_CONFIRMATION_PHRASE,
        )


def test_live_mode_is_blocked_without_enable_flag() -> None:
    with pytest.raises(
        ValidationError,
        match="ENABLE_LIVE_TRADING=true",
    ):
        Settings(
            _env_file=None,
            bot_mode=BotMode.LIVE,
            app_env=AppEnvironment.PRODUCTION,
            enable_live_trading=False,
            live_trading_confirmation=LIVE_TRADING_CONFIRMATION_PHRASE,
        )


def test_live_mode_is_blocked_without_confirmation_phrase() -> None:
    with pytest.raises(ValidationError, match="confirmation phrase"):
        Settings(
            _env_file=None,
            bot_mode=BotMode.LIVE,
            app_env=AppEnvironment.PRODUCTION,
            enable_live_trading=True,
            live_trading_confirmation="incorrect",
        )


def test_live_mode_requires_all_explicit_conditions() -> None:
    settings = Settings(
        _env_file=None,
        bot_mode=BotMode.LIVE,
        app_env=AppEnvironment.PRODUCTION,
        enable_live_trading=True,
        live_trading_confirmation=LIVE_TRADING_CONFIRMATION_PHRASE,
    )

    assert settings.live_trading_armed is True
    assert settings.is_live_mode is True


def test_log_directory_cannot_escape_by_default() -> None:
    settings = Settings(_env_file=None)

    expected = Path(PROJECT_ROOT, "data", "logs").resolve()

    assert settings.log_dir == expected
