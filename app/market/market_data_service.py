from __future__ import annotations

from datetime import datetime

import pandas as pd
from loguru import logger

from app.broker.mt5_client import MT5Client
from app.config.settings import Settings
from app.market.candle_model import Candle, CandleBatch
from app.market.market_data_validator import MarketDataValidator
from app.market.timeframes import get_mt5_timeframe


class MarketDataService:
    """
    Fetches, validates, and prepares market candle data from MT5.
    """

    def __init__(
        self,
        mt5_client: MT5Client,
        settings: Settings,
        validator: MarketDataValidator | None = None,
    ) -> None:
        self._mt5 = mt5_client
        self._settings = settings
        self._validator = validator or MarketDataValidator()

    def fetch_candles_dataframe(
        self,
        symbol: str,
        count: int | None = None,
        minimum_candles: int = 50,
    ) -> pd.DataFrame:
        candle_count = count or self._settings.candles_count
        timeframe_name = self._settings.timeframe.value
        timeframe = get_mt5_timeframe(timeframe_name)

        rates = self._mt5.copy_rates_from_pos(
            symbol=symbol,
            timeframe=timeframe,
            start_pos=0,
            count=candle_count,
        )

        if rates is None:
            raise RuntimeError(f"Could not fetch candles for symbol: {symbol}")

        df = pd.DataFrame(rates)

        if df.empty:
            raise RuntimeError(f"MT5 returned empty candles for symbol: {symbol}")

        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = self._normalize_columns(df)
        df = df.sort_values("time").reset_index(drop=True)

        report = self._validator.validate_dataframe(
            df=df,
            minimum_candles=minimum_candles,
        )
        self._validator.log_report(report)

        if not report.is_valid:
            raise RuntimeError("Market data validation failed: " + " | ".join(report.reasons))

        return df

    def fetch_candle_batch(
        self,
        symbol: str,
        count: int | None = None,
        minimum_candles: int = 50,
    ) -> CandleBatch:
        df = self.fetch_candles_dataframe(
            symbol=symbol,
            count=count,
            minimum_candles=minimum_candles,
        )

        candles = tuple(self._build_candles_from_dataframe(df))

        return CandleBatch(
            symbol=symbol,
            timeframe=self._settings.timeframe.value,
            candles=candles,
            dataframe=df.copy(),
        )

    def log_latest_candles(self, symbol: str, count: int = 10) -> None:
        minimum_candles = min(5, count)

        candle_batch = self.fetch_candle_batch(
            symbol=symbol,
            count=count,
            minimum_candles=minimum_candles,
        )

        latest = candle_batch.latest

        logger.info(
            "========== LATEST {} CANDLES ==========",
            self._settings.timeframe.value,
        )
        logger.info(
            "\n{}",
            candle_batch.dataframe[["time", "open", "high", "low", "close", "tick_volume"]].tail(
                count
            ),
        )

        logger.info("========== LATEST VALIDATED CANDLE ==========")
        logger.info("Time: {}", latest.time)
        logger.info("Open: {}", latest.open)
        logger.info("High: {}", latest.high)
        logger.info("Low: {}", latest.low)
        logger.info("Close: {}", latest.close)
        logger.info("Bullish: {}", latest.is_bullish)
        logger.info("Bearish: {}", latest.is_bearish)
        logger.info("Body Size: {}", latest.body_size)
        logger.info("Full Range: {}", latest.full_range)

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        expected_columns = [
            "time",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "spread",
            "real_volume",
        ]

        for column in expected_columns:
            if column not in df.columns:
                df[column] = 0

        return df[expected_columns].copy()

    @staticmethod
    def _build_candles_from_dataframe(df: pd.DataFrame) -> list[Candle]:
        candles: list[Candle] = []

        for _, row in df.iterrows():
            time_value = row["time"]

            if hasattr(time_value, "to_pydatetime"):
                candle_time: datetime = time_value.to_pydatetime()
            else:
                candle_time = time_value

            candles.append(
                Candle(
                    time=candle_time,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    tick_volume=int(row["tick_volume"]),
                    spread=int(row["spread"]),
                    real_volume=int(row["real_volume"]),
                )
            )

        return candles
