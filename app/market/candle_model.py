from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Candle(BaseModel):
    """
    Validated OHLCV candle model.

    Every candle used by indicators/strategy must pass this model first.
    """

    model_config = ConfigDict(frozen=True)

    time: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    tick_volume: int = Field(ge=0)
    spread: int = Field(ge=0)
    real_volume: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_ohlc_structure(self) -> "Candle":
        if self.high < self.low:
            raise ValueError("Candle high cannot be lower than low.")

        if self.open > self.high or self.open < self.low:
            raise ValueError("Candle open must be between high and low.")

        if self.close > self.high or self.close < self.low:
            raise ValueError("Candle close must be between high and low.")

        return self

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def full_range(self) -> float:
        return self.high - self.low


@dataclass(frozen=True)
class CandleBatch:
    """
    Clean validated candle batch for one symbol/timeframe.
    """

    symbol: str
    timeframe: str
    candles: tuple[Candle, ...]
    dataframe: pd.DataFrame

    @property
    def count(self) -> int:
        return len(self.candles)

    @property
    def latest(self) -> Candle:
        if not self.candles:
            raise ValueError("CandleBatch is empty.")
        return self.candles[-1]

    @property
    def previous(self) -> Candle:
        if len(self.candles) < 2:
            raise ValueError("CandleBatch needs at least 2 candles.")
        return self.candles[-2]
