from __future__ import annotations

from enum import Enum


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class BotMode(str, Enum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    DEMO = "DEMO"
    LIVE = "LIVE"


class TimeframeName(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"


DEFAULT_GOLD_SYMBOL_CANDIDATES: list[str] = [
    "XAUUSD",
    "XAUUSDm",
    "XAUUSD.",
    "GOLD",
    "Gold",
]
