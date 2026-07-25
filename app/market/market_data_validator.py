from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from loguru import logger

REQUIRED_CANDLE_COLUMNS: tuple[str, ...] = (
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)


@dataclass(frozen=True)
class MarketDataValidationReport:
    is_valid: bool
    candle_count: int
    reasons: tuple[str, ...]


class MarketDataValidator:
    """
    Validates raw candle dataframe before it reaches indicators/strategy.
    """

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        minimum_candles: int = 50,
    ) -> MarketDataValidationReport:
        reasons: list[str] = []

        if df is None:
            return MarketDataValidationReport(
                is_valid=False,
                candle_count=0,
                reasons=("DataFrame is None.",),
            )

        if df.empty:
            return MarketDataValidationReport(
                is_valid=False,
                candle_count=0,
                reasons=("DataFrame is empty.",),
            )

        missing_columns = [column for column in REQUIRED_CANDLE_COLUMNS if column not in df.columns]

        if missing_columns:
            reasons.append(f"Missing columns: {missing_columns}")

        if len(df) < minimum_candles:
            reasons.append(f"Not enough candles. Current: {len(df)}, Minimum: {minimum_candles}")

        if "time" in df.columns:
            if df["time"].isna().any():
                reasons.append("Time column contains empty values.")

            if df["time"].duplicated().any():
                reasons.append("Duplicate candle timestamps detected.")

            if not df["time"].is_monotonic_increasing:
                reasons.append("Candle time is not sorted ascending.")

        numeric_columns = ["open", "high", "low", "close", "tick_volume", "spread"]

        for column in numeric_columns:
            if column in df.columns and df[column].isna().any():
                reasons.append(f"{column} column contains empty values.")

        for column in ["open", "high", "low", "close"]:
            if column in df.columns and (df[column] <= 0).any():
                reasons.append(f"{column} column contains non-positive values.")

        if {"open", "high", "low", "close"}.issubset(df.columns):
            invalid_high_low = df["high"] < df["low"]
            invalid_open = (df["open"] > df["high"]) | (df["open"] < df["low"])
            invalid_close = (df["close"] > df["high"]) | (df["close"] < df["low"])

            if invalid_high_low.any():
                reasons.append("Some candles have high lower than low.")

            if invalid_open.any():
                reasons.append("Some candles have open outside high/low range.")

            if invalid_close.any():
                reasons.append("Some candles have close outside high/low range.")

        is_valid = len(reasons) == 0

        return MarketDataValidationReport(
            is_valid=is_valid,
            candle_count=len(df),
            reasons=tuple(reasons),
        )

    def log_report(self, report: MarketDataValidationReport) -> None:
        logger.info("========== MARKET DATA VALIDATION ==========")
        logger.info("Candles Count: {}", report.candle_count)
        logger.info("Is Valid: {}", report.is_valid)

        if report.reasons:
            logger.warning("Market data validation issues:")
            for reason in report.reasons:
                logger.warning("- {}", reason)
        else:
            logger.success("Market data validation passed.")
