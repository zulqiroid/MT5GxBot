from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Self, TypeAlias

from app.config.constants import TimeframeName
from app.market.timeframes import (
    get_timeframe_spec,
    parse_timeframe,
)

DecimalLike: TypeAlias = Decimal | int | float | str


class CandleDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    DOJI = "DOJI"


def _required_text(
    value: object,
    field_name: str,
    maximum_length: int = 64,
) -> str:
    normalized = str(value).strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be blank.")

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    if len(normalized) > maximum_length:
        raise ValueError(f"{field_name} cannot exceed {maximum_length} characters.")

    return normalized


def _positive_decimal(
    value: DecimalLike,
    field_name: str,
) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid decimal number.") from error

    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return decimal_value


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer.")

    try:
        integer_value = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a non-negative integer.") from error

    if integer_value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return integer_value


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    integer_value = _non_negative_integer(
        value,
        field_name,
    )

    if integer_value == 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return integer_value


def _utc_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _epoch_to_utc(
    value: object,
    field_name: str,
) -> datetime:
    seconds = _positive_integer(
        value,
        field_name,
    )

    try:
        return datetime.fromtimestamp(
            seconds,
            tz=timezone.utc,
        )
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"{field_name} contains an invalid Unix timestamp.") from error


def _required_field(
    source: object,
    field_name: str,
) -> object:
    if isinstance(source, Mapping):
        if field_name not in source:
            raise ValueError(f"MT5 candle field is missing: {field_name}.")

        return source[field_name]

    if hasattr(source, field_name):
        return getattr(source, field_name)

    try:
        return source[field_name]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"MT5 candle field is missing: {field_name}.") from None


@dataclass(frozen=True, slots=True)
class _CandleBase:
    broker_symbol: str
    timeframe: TimeframeName
    open_time: datetime
    observed_at: datetime
    open: DecimalLike
    high: DecimalLike
    low: DecimalLike
    close: DecimalLike
    tick_volume: int
    spread: int = 0
    real_volume: int = 0

    def __post_init__(self) -> None:
        broker_symbol = _required_text(
            self.broker_symbol,
            "broker_symbol",
        )
        timeframe = parse_timeframe(self.timeframe)
        specification = get_timeframe_spec(timeframe)
        open_time = _utc_datetime(
            self.open_time,
            "open_time",
        )
        observed_at = _utc_datetime(
            self.observed_at,
            "observed_at",
        )

        epoch_seconds = int(open_time.timestamp())

        if epoch_seconds % specification.seconds != 0:
            raise ValueError(f"open_time must align with the {timeframe.value} timeframe boundary.")

        if observed_at < open_time:
            raise ValueError("observed_at cannot be earlier than open_time.")

        open_price = _positive_decimal(
            self.open,
            "open",
        )
        high_price = _positive_decimal(
            self.high,
            "high",
        )
        low_price = _positive_decimal(
            self.low,
            "low",
        )
        close_price = _positive_decimal(
            self.close,
            "close",
        )

        if high_price < low_price:
            raise ValueError("Candle high cannot be below low.")

        if not low_price <= open_price <= high_price:
            raise ValueError("Candle open must be within high and low.")

        if not low_price <= close_price <= high_price:
            raise ValueError("Candle close must be within high and low.")

        tick_volume = _non_negative_integer(
            self.tick_volume,
            "tick_volume",
        )
        spread = _non_negative_integer(
            self.spread,
            "spread",
        )
        real_volume = _non_negative_integer(
            self.real_volume,
            "real_volume",
        )

        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(
            self,
            "timeframe",
            timeframe,
        )
        object.__setattr__(
            self,
            "open_time",
            open_time,
        )
        object.__setattr__(
            self,
            "observed_at",
            observed_at,
        )
        object.__setattr__(self, "open", open_price)
        object.__setattr__(self, "high", high_price)
        object.__setattr__(self, "low", low_price)
        object.__setattr__(self, "close", close_price)
        object.__setattr__(
            self,
            "tick_volume",
            tick_volume,
        )
        object.__setattr__(self, "spread", spread)
        object.__setattr__(
            self,
            "real_volume",
            real_volume,
        )

    @classmethod
    def from_mt5_rate(
        cls,
        rate: object,
        *,
        broker_symbol: str,
        timeframe: TimeframeName | str,
        observed_at: datetime,
    ) -> Self:
        return cls(
            broker_symbol=broker_symbol,
            timeframe=parse_timeframe(timeframe),
            open_time=_epoch_to_utc(
                _required_field(rate, "time"),
                "time",
            ),
            observed_at=observed_at,
            open=_required_field(rate, "open"),
            high=_required_field(rate, "high"),
            low=_required_field(rate, "low"),
            close=_required_field(rate, "close"),
            tick_volume=_required_field(
                rate,
                "tick_volume",
            ),
            spread=_required_field(
                rate,
                "spread",
            ),
            real_volume=_required_field(
                rate,
                "real_volume",
            ),
        )

    @property
    def close_time(self) -> datetime:
        return self.open_time + get_timeframe_spec(self.timeframe).duration

    @property
    def direction(self) -> CandleDirection:
        if self.close > self.open:
            return CandleDirection.BULLISH

        if self.close < self.open:
            return CandleDirection.BEARISH

        return CandleDirection.DOJI

    @property
    def is_bullish(self) -> bool:
        return self.direction == CandleDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == CandleDirection.BEARISH

    @property
    def is_doji(self) -> bool:
        return self.direction == CandleDirection.DOJI

    @property
    def body_size(self) -> Decimal:
        return abs(self.close - self.open)

    @property
    def full_range(self) -> Decimal:
        return self.high - self.low

    @property
    def upper_wick(self) -> Decimal:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> Decimal:
        return min(self.open, self.close) - self.low


@dataclass(frozen=True, slots=True)
class ClosedCandle(_CandleBase):
    """A candle guaranteed to have completed before observation."""

    def __post_init__(self) -> None:
        _CandleBase.__post_init__(self)

        if self.observed_at < self.close_time:
            raise ValueError("Closed candle cannot be observed before its close_time.")

    @property
    def is_closed(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class FormingCandle(_CandleBase):
    """A current candle that has not reached close_time."""

    def __post_init__(self) -> None:
        _CandleBase.__post_init__(self)

        if self.observed_at >= self.close_time:
            raise ValueError("Forming candle must be observed before its close_time.")

    @property
    def is_closed(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ClosedCandleSeries:
    """Chronological, strategy-safe closed candle history."""

    broker_symbol: str
    timeframe: TimeframeName
    candles: tuple[ClosedCandle, ...]

    def __post_init__(self) -> None:
        broker_symbol = _required_text(
            self.broker_symbol,
            "broker_symbol",
        )
        timeframe = parse_timeframe(self.timeframe)
        candles = tuple(self.candles)

        if not candles:
            raise ValueError("ClosedCandleSeries cannot be empty.")

        previous_open_time: datetime | None = None

        for candle in candles:
            if not isinstance(candle, ClosedCandle):
                raise ValueError("ClosedCandleSeries can contain only ClosedCandle instances.")

            if candle.broker_symbol != broker_symbol:
                raise ValueError("All candles must use the series symbol.")

            if candle.timeframe != timeframe:
                raise ValueError("All candles must use the series timeframe.")

            if previous_open_time is not None and candle.open_time <= previous_open_time:
                raise ValueError(
                    "Candle timestamps must be strictly increasing without duplicates."
                )

            previous_open_time = candle.open_time

        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(
            self,
            "timeframe",
            timeframe,
        )
        object.__setattr__(
            self,
            "candles",
            candles,
        )

    @property
    def count(self) -> int:
        return len(self.candles)

    @property
    def first(self) -> ClosedCandle:
        return self.candles[0]

    @property
    def latest(self) -> ClosedCandle:
        return self.candles[-1]

    @property
    def previous(self) -> ClosedCandle:
        if self.count < 2:
            raise ValueError("At least two closed candles are required.")

        return self.candles[-2]

    @property
    def close_prices(self) -> tuple[Decimal, ...]:
        return tuple(candle.close for candle in self.candles)

    @property
    def has_gaps(self) -> bool:
        return self.missing_candle_count > 0

    @property
    def missing_candle_count(self) -> int:
        timeframe_seconds = get_timeframe_spec(self.timeframe).seconds
        missing = 0

        for previous, current in zip(
            self.candles,
            self.candles[1:],
            strict=False,
        ):
            elapsed_seconds = int((current.open_time - previous.open_time).total_seconds())

            missing += max(
                elapsed_seconds // timeframe_seconds - 1,
                0,
            )

        return missing

    def append(
        self,
        candle: ClosedCandle,
    ) -> ClosedCandleSeries:
        return ClosedCandleSeries(
            broker_symbol=self.broker_symbol,
            timeframe=self.timeframe,
            candles=(*self.candles, candle),
        )


@dataclass(frozen=True, slots=True)
class CandleWindow:
    """
    Closed strategy history with an optional separate forming candle.
    """

    closed: ClosedCandleSeries
    forming: FormingCandle | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.closed,
            ClosedCandleSeries,
        ):
            raise ValueError("closed must be a ClosedCandleSeries.")

        if self.forming is None:
            return

        if not isinstance(
            self.forming,
            FormingCandle,
        ):
            raise ValueError("forming must be a FormingCandle.")

        if self.forming.broker_symbol != self.closed.broker_symbol:
            raise ValueError("Forming candle symbol must match the closed series.")

        if self.forming.timeframe != self.closed.timeframe:
            raise ValueError("Forming candle timeframe must match the closed series.")

        if self.forming.open_time != self.closed.latest.close_time:
            raise ValueError("Forming candle must immediately follow the latest closed candle.")

    @property
    def strategy_candles(
        self,
    ) -> tuple[ClosedCandle, ...]:
        return self.closed.candles

    @property
    def latest_closed(self) -> ClosedCandle:
        return self.closed.latest

    @property
    def current_forming(
        self,
    ) -> FormingCandle | None:
        return self.forming
