from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.constants import (
    DEFAULT_GOLD_SYMBOL_CANDIDATES,
    AppEnvironment,
    BotMode,
    TimeframeName,
)


class Settings(BaseSettings):
    """
    Central enterprise configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="GoldX Enterprise Bot", alias="APP_NAME")
    app_env: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        alias="APP_ENV",
    )
    bot_mode: BotMode = Field(default=BotMode.DEMO, alias="BOT_MODE")

    enable_live_trading: bool = Field(default=False, alias="ENABLE_LIVE_TRADING")

    mt5_terminal_path: str | None = Field(default=None, alias="MT5_TERMINAL_PATH")

    gold_symbol_candidates: list[str] = Field(
        default_factory=lambda: DEFAULT_GOLD_SYMBOL_CANDIDATES.copy(),
        alias="GOLD_SYMBOL_CANDIDATES",
    )

    timeframe: TimeframeName = Field(default=TimeframeName.M15, alias="TIMEFRAME")
    candles_count: int = Field(default=300, alias="CANDLES_COUNT")

    risk_per_trade_percent: float = Field(
        default=0.5,
        alias="RISK_PER_TRADE_PERCENT",
    )
    max_risk_per_trade_percent: float = Field(
        default=1.0,
        alias="MAX_RISK_PER_TRADE_PERCENT",
    )
    max_daily_loss_percent: float = Field(
        default=2.0,
        alias="MAX_DAILY_LOSS_PERCENT",
    )
    max_trades_per_day: int = Field(default=3, alias="MAX_TRADES_PER_DAY")
    max_open_trades: int = Field(default=1, alias="MAX_OPEN_TRADES")

    magic_number: int = Field(default=26062801, alias="MAGIC_NUMBER")
    order_comment: str = Field(default="goldx_enterprise_bot", alias="ORDER_COMMENT")

    max_spread_points: int = Field(default=50, alias="MAX_SPREAD_POINTS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: Path = Field(default=Path("data/logs"), alias="LOG_DIR")

    @field_validator("gold_symbol_candidates", mode="before")
    @classmethod
    def parse_symbol_candidates(cls, value: object) -> list[str]:
        if value is None:
            return DEFAULT_GOLD_SYMBOL_CANDIDATES.copy()

        if isinstance(value, str):
            symbols = [item.strip() for item in value.split(",") if item.strip()]
            return symbols or DEFAULT_GOLD_SYMBOL_CANDIDATES.copy()

        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]

        raise ValueError("GOLD_SYMBOL_CANDIDATES must be comma-separated text or list.")

    @field_validator("candles_count")
    @classmethod
    def validate_candles_count(cls, value: int) -> int:
        if value < 50:
            raise ValueError("CANDLES_COUNT must be at least 50.")
        return value

    @field_validator("risk_per_trade_percent")
    @classmethod
    def validate_risk_per_trade(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("RISK_PER_TRADE_PERCENT must be greater than 0.")
        return value

    @field_validator("max_daily_loss_percent")
    @classmethod
    def validate_daily_loss(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("MAX_DAILY_LOSS_PERCENT must be greater than 0.")
        return value

    @field_validator("max_trades_per_day")
    @classmethod
    def validate_max_trades(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_TRADES_PER_DAY must be greater than 0.")
        return value

    @field_validator("max_open_trades")
    @classmethod
    def validate_max_open_trades(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_OPEN_TRADES must be greater than 0.")
        return value

    @model_validator(mode="after")
    def validate_safety_rules(self) -> "Settings":
        if self.risk_per_trade_percent > self.max_risk_per_trade_percent:
            raise ValueError(
                "RISK_PER_TRADE_PERCENT cannot be greater than MAX_RISK_PER_TRADE_PERCENT."
            )

        if self.bot_mode == BotMode.LIVE and not self.enable_live_trading:
            raise ValueError(
                "LIVE mode is blocked. Set ENABLE_LIVE_TRADING=true only after "
                "backtest, demo forward test, and risk review."
            )

        return self

    @property
    def is_live_mode(self) -> bool:
        return self.bot_mode == BotMode.LIVE

    @property
    def is_demo_mode(self) -> bool:
        return self.bot_mode == BotMode.DEMO

    @property
    def is_backtest_mode(self) -> bool:
        return self.bot_mode == BotMode.BACKTEST

    @property
    def normalized_log_level(self) -> str:
        return self.log_level.upper().strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings
