from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from app.broker.mt5_client import MT5ConnectionError
from app.config.constants import TimeframeName
from app.market.closed_candle import (
    CandleWindow,
    ClosedCandle,
    ClosedCandleSeries,
    FormingCandle,
)
from app.market.timeframes import (
    get_timeframe_spec,
    parse_timeframe,
)


class CandleDataErrorReason(str, Enum):
    CONNECTION_REQUIRED = "CONNECTION_REQUIRED"
    RATES_READ_FAILED = "RATES_READ_FAILED"
    RATES_UNAVAILABLE = "RATES_UNAVAILABLE"
    INSUFFICIENT_RATES = "INSUFFICIENT_RATES"
    INVALID_RATE_DATA = "INVALID_RATE_DATA"
    CLOSED_SERIES_GAP = "CLOSED_SERIES_GAP"
    FORMING_CANDLE_UNAVAILABLE = "FORMING_CANDLE_UNAVAILABLE"
    INVALID_CLOCK = "INVALID_CLOCK"


class CandleDataServiceError(RuntimeError):
    """Structured failure while loading strategy candle data."""

    def __init__(
        self,
        reason: CandleDataErrorReason,
        message: str,
    ) -> None:
        self.reason = CandleDataErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Candle data error [{self.reason.value}]: {self.message}")


@runtime_checkable
class CandleRatesClient(Protocol):
    """Read-only MT5 rates contract used by the loader."""

    @property
    def initialized(self) -> bool: ...

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _bounded_positive_integer(
    value: object,
    field_name: str,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    if value > maximum:
        raise ValueError(f"{field_name} cannot exceed {maximum}.")

    return value


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _utc_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CandleLoadRequest:
    """Request for closed and optional forming candles."""

    broker_symbol: str
    timeframe: TimeframeName
    closed_count: int
    include_forming: bool = False
    require_contiguous: bool = False

    def __post_init__(self) -> None:
        broker_symbol = _required_text(
            self.broker_symbol,
            "broker_symbol",
        )
        timeframe = parse_timeframe(self.timeframe)
        closed_count = _bounded_positive_integer(
            self.closed_count,
            "closed_count",
            10_000,
        )
        include_forming = _strict_boolean(
            self.include_forming,
            "include_forming",
        )
        require_contiguous = _strict_boolean(
            self.require_contiguous,
            "require_contiguous",
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
            "closed_count",
            closed_count,
        )
        object.__setattr__(
            self,
            "include_forming",
            include_forming,
        )
        object.__setattr__(
            self,
            "require_contiguous",
            require_contiguous,
        )


@dataclass(frozen=True, slots=True)
class CandleDataSnapshot:
    """One deterministic candle-data observation."""

    request: CandleLoadRequest
    window: CandleWindow
    loaded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(
            self.request,
            CandleLoadRequest,
        ):
            raise ValueError("request must be a CandleLoadRequest.")

        if not isinstance(self.window, CandleWindow):
            raise ValueError("window must be a CandleWindow.")

        loaded_at = _utc_datetime(
            self.loaded_at,
            "loaded_at",
        )

        if self.window.closed.broker_symbol != self.request.broker_symbol:
            raise ValueError("Window symbol must match the request.")

        if self.window.closed.timeframe != self.request.timeframe:
            raise ValueError("Window timeframe must match the request.")

        if self.window.closed.count != self.request.closed_count:
            raise ValueError("Closed candle count must match the request.")

        if self.request.include_forming and self.window.forming is None:
            raise ValueError("A forming candle was requested but not loaded.")

        if not self.request.include_forming and self.window.forming is not None:
            raise ValueError("Unexpected forming candle in closed-only snapshot.")

        if loaded_at < self.window.closed.latest.close_time:
            raise ValueError("loaded_at cannot precede the latest closed candle.")

        object.__setattr__(
            self,
            "loaded_at",
            loaded_at,
        )

    @property
    def closed(self) -> ClosedCandleSeries:
        return self.window.closed

    @property
    def forming(self) -> FormingCandle | None:
        return self.window.forming

    @property
    def latest_closed(self) -> ClosedCandle:
        return self.window.latest_closed

    @property
    def latest_closed_age(self) -> timedelta:
        return self.loaded_at - self.latest_closed.close_time

    @property
    def has_gaps(self) -> bool:
        return self.closed.has_gaps


class ClosedCandleMarketDataService:
    """
    Read-only deterministic MT5 candle loader.

    Closed history starts from MT5 position 1. Position 0 is
    read separately only when a forming candle is requested.
    """

    def __init__(
        self,
        mt5_client: CandleRatesClient,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(
            mt5_client,
            CandleRatesClient,
        ):
            raise ValueError("mt5_client must implement the CandleRatesClient protocol.")

        if not callable(clock):
            raise ValueError("clock must be callable.")

        self._mt5 = mt5_client
        self._clock = clock

    def read_snapshot(
        self,
        request: CandleLoadRequest,
    ) -> CandleDataSnapshot:
        if not isinstance(request, CandleLoadRequest):
            raise ValueError("request must be a CandleLoadRequest.")

        self._require_connection()

        try:
            loaded_at = _utc_datetime(
                self._clock(),
                "clock result",
            )
        except Exception as error:
            raise CandleDataServiceError(
                CandleDataErrorReason.INVALID_CLOCK,
                str(error),
            ) from error

        specification = get_timeframe_spec(request.timeframe)

        closed_rates = self._read_rates(
            symbol=request.broker_symbol,
            timeframe=specification.mt5_value,
            start_pos=1,
            count=request.closed_count,
            purpose="closed candles",
        )

        if len(closed_rates) != request.closed_count:
            raise CandleDataServiceError(
                CandleDataErrorReason.INSUFFICIENT_RATES,
                "Requested "
                f"{request.closed_count} closed candles but "
                f"MT5 returned {len(closed_rates)}.",
            )

        closed_series = self._map_closed_series(
            rates=closed_rates,
            request=request,
            loaded_at=loaded_at,
        )

        if request.require_contiguous and closed_series.has_gaps:
            raise CandleDataServiceError(
                CandleDataErrorReason.CLOSED_SERIES_GAP,
                "Closed candle history contains "
                f"{closed_series.missing_candle_count} "
                "missing timeframe intervals.",
            )

        forming: FormingCandle | None = None

        if request.include_forming:
            forming_rates = self._read_rates(
                symbol=request.broker_symbol,
                timeframe=specification.mt5_value,
                start_pos=0,
                count=1,
                purpose="forming candle",
            )

            if len(forming_rates) != 1:
                raise CandleDataServiceError(
                    CandleDataErrorReason.FORMING_CANDLE_UNAVAILABLE,
                    "MT5 did not return exactly one forming candle.",
                )

            forming = self._map_forming_candle(
                rate=forming_rates[0],
                request=request,
                loaded_at=loaded_at,
            )

        try:
            window = CandleWindow(
                closed=closed_series,
                forming=forming,
            )
        except ValueError as error:
            reason = (
                CandleDataErrorReason.FORMING_CANDLE_UNAVAILABLE
                if request.include_forming
                else CandleDataErrorReason.INVALID_RATE_DATA
            )

            raise CandleDataServiceError(
                reason,
                str(error),
            ) from error

        return CandleDataSnapshot(
            request=request,
            window=window,
            loaded_at=loaded_at,
        )

    def read_closed_series(
        self,
        *,
        broker_symbol: str,
        timeframe: TimeframeName | str,
        count: int,
        require_contiguous: bool = False,
    ) -> ClosedCandleSeries:
        request = CandleLoadRequest(
            broker_symbol=broker_symbol,
            timeframe=parse_timeframe(timeframe),
            closed_count=count,
            include_forming=False,
            require_contiguous=require_contiguous,
        )

        return self.read_snapshot(request).closed

    def read_candle_window(
        self,
        *,
        broker_symbol: str,
        timeframe: TimeframeName | str,
        closed_count: int,
        require_contiguous: bool = False,
    ) -> CandleWindow:
        request = CandleLoadRequest(
            broker_symbol=broker_symbol,
            timeframe=parse_timeframe(timeframe),
            closed_count=closed_count,
            include_forming=True,
            require_contiguous=require_contiguous,
        )

        return self.read_snapshot(request).window

    def get_closed_candles(
        self,
        *,
        broker_symbol: str,
        timeframe: TimeframeName | str,
        count: int,
        require_contiguous: bool = False,
    ) -> ClosedCandleSeries:
        """Compatibility alias for read_closed_series()."""

        return self.read_closed_series(
            broker_symbol=broker_symbol,
            timeframe=timeframe,
            count=count,
            require_contiguous=require_contiguous,
        )

    def get_candle_window(
        self,
        *,
        broker_symbol: str,
        timeframe: TimeframeName | str,
        closed_count: int,
        require_contiguous: bool = False,
    ) -> CandleWindow:
        """Compatibility alias for read_candle_window()."""

        return self.read_candle_window(
            broker_symbol=broker_symbol,
            timeframe=timeframe,
            closed_count=closed_count,
            require_contiguous=require_contiguous,
        )

    def _require_connection(self) -> None:
        if self._mt5.initialized:
            return

        raise CandleDataServiceError(
            CandleDataErrorReason.CONNECTION_REQUIRED,
            "MT5 must be initialized before reading candles.",
        )

    def _read_rates(
        self,
        *,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
        purpose: str,
    ) -> tuple[object, ...]:
        try:
            raw_rates = self._mt5.copy_rates_from_pos(
                symbol,
                timeframe,
                start_pos,
                count,
            )
        except MT5ConnectionError as error:
            raise CandleDataServiceError(
                CandleDataErrorReason.RATES_READ_FAILED,
                str(error),
            ) from error
        except Exception as error:
            raise CandleDataServiceError(
                CandleDataErrorReason.RATES_READ_FAILED,
                f"Reading {purpose} raised {type(error).__name__}: {error}",
            ) from error

        if raw_rates is None:
            raise CandleDataServiceError(
                CandleDataErrorReason.RATES_UNAVAILABLE,
                f"MT5 returned no data for {purpose}.",
            )

        try:
            return tuple(raw_rates)
        except TypeError as error:
            raise CandleDataServiceError(
                CandleDataErrorReason.INVALID_RATE_DATA,
                f"MT5 {purpose} result is not iterable.",
            ) from error

    @staticmethod
    def _map_closed_series(
        *,
        rates: tuple[object, ...],
        request: CandleLoadRequest,
        loaded_at: datetime,
    ) -> ClosedCandleSeries:
        try:
            candles = tuple(
                sorted(
                    (
                        ClosedCandle.from_mt5_rate(
                            rate,
                            broker_symbol=(request.broker_symbol),
                            timeframe=request.timeframe,
                            observed_at=loaded_at,
                        )
                        for rate in rates
                    ),
                    key=lambda candle: candle.open_time,
                )
            )

            return ClosedCandleSeries(
                broker_symbol=request.broker_symbol,
                timeframe=request.timeframe,
                candles=candles,
            )
        except (TypeError, ValueError) as error:
            raise CandleDataServiceError(
                CandleDataErrorReason.INVALID_RATE_DATA,
                str(error),
            ) from error

    @staticmethod
    def _map_forming_candle(
        *,
        rate: object,
        request: CandleLoadRequest,
        loaded_at: datetime,
    ) -> FormingCandle:
        try:
            return FormingCandle.from_mt5_rate(
                rate,
                broker_symbol=request.broker_symbol,
                timeframe=request.timeframe,
                observed_at=loaded_at,
            )
        except (TypeError, ValueError) as error:
            raise CandleDataServiceError(
                CandleDataErrorReason.FORMING_CANDLE_UNAVAILABLE,
                str(error),
            ) from error


StrategyMarketDataService = ClosedCandleMarketDataService
