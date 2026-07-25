from __future__ import annotations

import MetaTrader5 as mt5


MT5_TIMEFRAMES: dict[str, int] = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def get_mt5_timeframe(timeframe_name: str) -> int:
    timeframe = MT5_TIMEFRAMES.get(timeframe_name.upper().strip())

    if timeframe is None:
        supported = ", ".join(MT5_TIMEFRAMES.keys())
        raise ValueError(
            f"Unsupported timeframe: {timeframe_name}. Supported: {supported}"
        )

    return timeframe
