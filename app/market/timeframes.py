from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType
from typing import Final, Mapping

import MetaTrader5 as mt5

from app.config.constants import TimeframeName


@dataclass(frozen=True, slots=True)
class TimeframeSpec:
    """Immutable MT5 and duration mapping for one timeframe."""

    name: TimeframeName
    mt5_value: int
    seconds: int

    def __post_init__(self) -> None:
        try:
            name = TimeframeName(self.name)
        except ValueError as error:
            raise ValueError(f"Unsupported timeframe: {self.name}.") from error

        if (
            isinstance(self.mt5_value, bool)
            or not isinstance(self.mt5_value, int)
            or self.mt5_value <= 0
        ):
            raise ValueError("mt5_value must be a positive integer.")

        if isinstance(self.seconds, bool) or not isinstance(self.seconds, int) or self.seconds <= 0:
            raise ValueError("seconds must be a positive integer.")

        object.__setattr__(self, "name", name)

    @property
    def duration(self) -> timedelta:
        return timedelta(seconds=self.seconds)

    @property
    def label(self) -> str:
        return self.name.value


_TIMEFRAME_SPECS_SOURCE: Final[dict[TimeframeName, TimeframeSpec]] = {
    TimeframeName.M1: TimeframeSpec(
        name=TimeframeName.M1,
        mt5_value=mt5.TIMEFRAME_M1,
        seconds=60,
    ),
    TimeframeName.M5: TimeframeSpec(
        name=TimeframeName.M5,
        mt5_value=mt5.TIMEFRAME_M5,
        seconds=300,
    ),
    TimeframeName.M15: TimeframeSpec(
        name=TimeframeName.M15,
        mt5_value=mt5.TIMEFRAME_M15,
        seconds=900,
    ),
    TimeframeName.M30: TimeframeSpec(
        name=TimeframeName.M30,
        mt5_value=mt5.TIMEFRAME_M30,
        seconds=1800,
    ),
    TimeframeName.H1: TimeframeSpec(
        name=TimeframeName.H1,
        mt5_value=mt5.TIMEFRAME_H1,
        seconds=3600,
    ),
    TimeframeName.H4: TimeframeSpec(
        name=TimeframeName.H4,
        mt5_value=mt5.TIMEFRAME_H4,
        seconds=14400,
    ),
    TimeframeName.D1: TimeframeSpec(
        name=TimeframeName.D1,
        mt5_value=mt5.TIMEFRAME_D1,
        seconds=86400,
    ),
}

TIMEFRAME_SPECS: Final[Mapping[TimeframeName, TimeframeSpec]] = MappingProxyType(
    _TIMEFRAME_SPECS_SOURCE
)

SUPPORTED_STRATEGY_TIMEFRAMES: Final[tuple[TimeframeName, ...]] = (
    TimeframeName.H4,
    TimeframeName.H1,
    TimeframeName.M15,
    TimeframeName.M5,
)

SUPPORTED_TIMEFRAMES: Final[tuple[str, ...]] = tuple(
    timeframe.value for timeframe in TIMEFRAME_SPECS
)

# Backward compatibility with the existing market-data service.
MT5_TIMEFRAMES: Final[dict[str, int]] = {
    timeframe.value: specification.mt5_value for timeframe, specification in TIMEFRAME_SPECS.items()
}

MT5_TIMEFRAME_MAP = MT5_TIMEFRAMES
TIMEFRAME_MAP = MT5_TIMEFRAMES
Timeframe = TimeframeName


def parse_timeframe(
    timeframe: TimeframeName | str,
) -> TimeframeName:
    if isinstance(timeframe, TimeframeName):
        return timeframe

    normalized = str(timeframe).strip().upper()

    try:
        return TimeframeName(normalized)
    except ValueError as error:
        supported = ", ".join(SUPPORTED_TIMEFRAMES)

        raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {supported}") from error


def get_timeframe_spec(
    timeframe: TimeframeName | str,
) -> TimeframeSpec:
    parsed = parse_timeframe(timeframe)

    try:
        return TIMEFRAME_SPECS[parsed]
    except KeyError as error:
        raise ValueError(f"No specification exists for {parsed.value}.") from error


def get_mt5_timeframe(
    timeframe_name: TimeframeName | str,
) -> int:
    """Backward-compatible MT5 timeframe resolver."""

    return get_timeframe_spec(timeframe_name).mt5_value


def timeframe_seconds(
    timeframe: TimeframeName | str,
) -> int:
    return get_timeframe_spec(timeframe).seconds


def timeframe_duration(
    timeframe: TimeframeName | str,
) -> timedelta:
    return get_timeframe_spec(timeframe).duration


def is_strategy_timeframe(
    timeframe: TimeframeName | str,
) -> bool:
    return parse_timeframe(timeframe) in SUPPORTED_STRATEGY_TIMEFRAMES
