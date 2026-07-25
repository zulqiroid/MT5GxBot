from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.config.constants import (
    DEFAULT_GOLD_SYMBOL_CANDIDATES,
    LIVE_TRADING_CONFIRMATION_PHRASE,
    VALID_LOG_LEVELS,
    AppEnvironment,
    BotMode,
    TimeframeName,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central typed configuration with fail-safe trading defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
        validate_default=True,
        frozen=True,
    )

    app_name: str = Field(
        default="GoldX Enterprise Bot",
        min_length=1,
        max_length=80,
        alias="APP_NAME",
    )
    app_env: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        alias="APP_ENV",
    )
    bot_mode: BotMode = Field(
        default=BotMode.PAPER,
        alias="BOT_MODE",
    )

    enable_live_trading: bool = Field(
        default=False,
        alias="ENABLE_LIVE_TRADING",
    )
    live_trading_confirmation: str = Field(
        default="",
        alias="LIVE_TRADING_CONFIRMATION",
        repr=False,
    )

    mt5_terminal_path: str | None = Field(
        default=None,
        alias="MT5_TERMINAL_PATH",
    )

    gold_symbol_candidates: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: DEFAULT_GOLD_SYMBOL_CANDIDATES.copy(),
        alias="GOLD_SYMBOL_CANDIDATES",
    )

    timeframe: TimeframeName = Field(
        default=TimeframeName.M15,
        alias="TIMEFRAME",
    )
    candles_count: int = Field(
        default=500,
        ge=100,
        le=5000,
        alias="CANDLES_COUNT",
    )

    risk_per_trade_percent: float = Field(
        default=0.25,
        gt=0,
        le=1.0,
        alias="RISK_PER_TRADE_PERCENT",
    )
    max_risk_per_trade_percent: float = Field(
        default=1.0,
        gt=0,
        le=1.0,
        alias="MAX_RISK_PER_TRADE_PERCENT",
    )
    max_daily_loss_percent: float = Field(
        default=2.0,
        gt=0,
        le=10.0,
        alias="MAX_DAILY_LOSS_PERCENT",
    )
    max_trades_per_day: int = Field(
        default=3,
        ge=1,
        le=20,
        alias="MAX_TRADES_PER_DAY",
    )
    max_open_trades: int = Field(
        default=1,
        ge=1,
        le=1,
        alias="MAX_OPEN_TRADES",
    )

    magic_number: int = Field(
        default=26062801,
        ge=1,
        alias="MAGIC_NUMBER",
    )
    order_comment: str = Field(
        default="goldx_enterprise_bot",
        min_length=1,
        max_length=31,
        alias="ORDER_COMMENT",
    )

    max_spread_points: int = Field(
        default=50,
        ge=1,
        le=1000,
        alias="MAX_SPREAD_POINTS",
    )

    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
    )
    log_dir: Path = Field(
        default=Path("data/logs"),
        alias="LOG_DIR",
    )

    @field_validator("app_name", "order_comment")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Value cannot be blank.")

        if "\n" in normalized or "\r" in normalized:
            raise ValueError("Value cannot contain line breaks.")

        return normalized

    @field_validator("mt5_terminal_path", mode="before")
    @classmethod
    def normalize_mt5_terminal_path(cls, value: object) -> str | None:
        if value is None:
            return None

        normalized = str(value).strip().strip('"')

        if not normalized:
            return None

        path = Path(normalized).expanduser()

        if not path.is_absolute():
            raise ValueError("MT5_TERMINAL_PATH must be an absolute path.")

        if path.suffix.lower() != ".exe":
            raise ValueError("MT5_TERMINAL_PATH must point to an .exe file.")

        return str(path)

    @field_validator("gold_symbol_candidates", mode="before")
    @classmethod
    def parse_symbol_candidates(cls, value: object) -> list[str]:
        if value is None:
            return DEFAULT_GOLD_SYMBOL_CANDIDATES.copy()

        if isinstance(value, str):
            raw_symbols = value.split(",")
        elif isinstance(value, (list, tuple, set)):
            raw_symbols = [str(item) for item in value]
        else:
            raise ValueError("GOLD_SYMBOL_CANDIDATES must be comma-separated text or a list.")

        symbols: list[str] = []
        seen: set[str] = set()

        for raw_symbol in raw_symbols:
            symbol = str(raw_symbol).strip()

            if symbol and symbol not in seen:
                symbols.append(symbol)
                seen.add(symbol)

        if not symbols:
            raise ValueError("GOLD_SYMBOL_CANDIDATES must contain at least one symbol.")

        return symbols

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper().strip()

        if normalized not in VALID_LOG_LEVELS:
            allowed = ", ".join(sorted(VALID_LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}.")

        return normalized

    @field_validator("log_dir", mode="before")
    @classmethod
    def resolve_log_dir(cls, value: object) -> Path:
        if value is None or not str(value).strip():
            path = Path("data/logs")
        else:
            path = Path(str(value).strip()).expanduser()

        if not path.is_absolute():
            path = PROJECT_ROOT / path

        return path.resolve()

    @model_validator(mode="after")
    def validate_safety_rules(self) -> "Settings":
        if self.risk_per_trade_percent > self.max_risk_per_trade_percent:
            raise ValueError("RISK_PER_TRADE_PERCENT cannot exceed MAX_RISK_PER_TRADE_PERCENT.")

        if self.bot_mode == BotMode.LIVE:
            if self.app_env != AppEnvironment.PRODUCTION:
                raise ValueError("LIVE mode requires APP_ENV=production.")

            if not self.enable_live_trading:
                raise ValueError("LIVE mode requires ENABLE_LIVE_TRADING=true.")

            if self.live_trading_confirmation != LIVE_TRADING_CONFIRMATION_PHRASE:
                raise ValueError("LIVE mode requires the exact confirmation phrase.")

        elif self.enable_live_trading:
            raise ValueError("ENABLE_LIVE_TRADING=true is valid only when BOT_MODE=LIVE.")

        return self

    @property
    def is_live_mode(self) -> bool:
        return self.bot_mode == BotMode.LIVE

    @property
    def is_demo_mode(self) -> bool:
        return self.bot_mode == BotMode.DEMO

    @property
    def is_paper_mode(self) -> bool:
        return self.bot_mode == BotMode.PAPER

    @property
    def is_backtest_mode(self) -> bool:
        return self.bot_mode == BotMode.BACKTEST

    @property
    def live_trading_armed(self) -> bool:
        return (
            self.bot_mode == BotMode.LIVE
            and self.app_env == AppEnvironment.PRODUCTION
            and self.enable_live_trading
            and self.live_trading_confirmation == LIVE_TRADING_CONFIRMATION_PHRASE
        )

    @property
    def normalized_log_level(self) -> str:
        return self.log_level


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings


def clear_settings_cache() -> None:
    get_settings.cache_clear()
