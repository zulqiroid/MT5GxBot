from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandleSeries
from app.market.closed_candle_service import (
    CandleDataServiceError,
    CandleDataSnapshot,
    CandleLoadRequest,
)
from app.market.timeframes import (
    SUPPORTED_STRATEGY_TIMEFRAMES,
    get_timeframe_spec,
    parse_timeframe,
)


class MultiTimeframeDataErrorReason(str, Enum):
    TIMEFRAME_LOAD_FAILED = "TIMEFRAME_LOAD_FAILED"
    INVALID_TIMEFRAME_SNAPSHOT = "INVALID_TIMEFRAME_SNAPSHOT"
    MISSING_TIMEFRAME = "MISSING_TIMEFRAME"
    DUPLICATE_TIMEFRAME = "DUPLICATE_TIMEFRAME"
    SYMBOL_MISMATCH = "SYMBOL_MISMATCH"
    SNAPSHOT_FROM_FUTURE = "SNAPSHOT_FROM_FUTURE"
    STALE_MARKET_DATA = "STALE_MARKET_DATA"
    HISTORY_GAP = "HISTORY_GAP"
    INVALID_CLOCK = "INVALID_CLOCK"


class MultiTimeframeDataServiceError(RuntimeError):
    """Structured multi-timeframe market-data failure."""

    def __init__(
        self,
        reason: MultiTimeframeDataErrorReason,
        message: str,
        *,
        timeframe: TimeframeName | None = None,
    ) -> None:
        self.reason = MultiTimeframeDataErrorReason(reason)
        self.message = str(message)
        self.timeframe = None if timeframe is None else parse_timeframe(timeframe)

        suffix = "" if self.timeframe is None else f" [{self.timeframe.value}]"

        super().__init__(
            f"Multi-timeframe data error [{self.reason.value}]{suffix}: {self.message}"
        )


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
class MultiTimeframeLoadRequest:
    """Fixed H4/H1/M15/M5 closed-candle load request."""

    broker_symbol: str
    h4_count: int
    h1_count: int
    m15_count: int
    m5_count: int
    require_contiguous: bool = True
    max_staleness_bars: int = 1
    reject_stale: bool = True

    def __post_init__(self) -> None:
        broker_symbol = _required_text(
            self.broker_symbol,
            "broker_symbol",
        )
        h4_count = _bounded_positive_integer(
            self.h4_count,
            "h4_count",
            10_000,
        )
        h1_count = _bounded_positive_integer(
            self.h1_count,
            "h1_count",
            10_000,
        )
        m15_count = _bounded_positive_integer(
            self.m15_count,
            "m15_count",
            10_000,
        )
        m5_count = _bounded_positive_integer(
            self.m5_count,
            "m5_count",
            10_000,
        )
        require_contiguous = _strict_boolean(
            self.require_contiguous,
            "require_contiguous",
        )
        max_staleness_bars = _bounded_positive_integer(
            self.max_staleness_bars,
            "max_staleness_bars",
            100,
        )
        reject_stale = _strict_boolean(
            self.reject_stale,
            "reject_stale",
        )

        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(
            self,
            "h4_count",
            h4_count,
        )
        object.__setattr__(
            self,
            "h1_count",
            h1_count,
        )
        object.__setattr__(
            self,
            "m15_count",
            m15_count,
        )
        object.__setattr__(
            self,
            "m5_count",
            m5_count,
        )
        object.__setattr__(
            self,
            "require_contiguous",
            require_contiguous,
        )
        object.__setattr__(
            self,
            "max_staleness_bars",
            max_staleness_bars,
        )
        object.__setattr__(
            self,
            "reject_stale",
            reject_stale,
        )

    @property
    def timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return SUPPORTED_STRATEGY_TIMEFRAMES

    def count_for(
        self,
        timeframe: TimeframeName | str,
    ) -> int:
        parsed = parse_timeframe(timeframe)

        counts = {
            TimeframeName.H4: self.h4_count,
            TimeframeName.H1: self.h1_count,
            TimeframeName.M15: self.m15_count,
            TimeframeName.M5: self.m5_count,
        }

        try:
            return counts[parsed]
        except KeyError as error:
            raise ValueError(f"{parsed.value} is not a primary strategy timeframe.") from error


@dataclass(frozen=True, slots=True)
class TimeframeMarketSlice:
    """One validated closed-candle timeframe snapshot."""

    timeframe: TimeframeName
    data: CandleDataSnapshot

    def __post_init__(self) -> None:
        timeframe = parse_timeframe(self.timeframe)

        if timeframe not in SUPPORTED_STRATEGY_TIMEFRAMES:
            raise ValueError(f"{timeframe.value} is not a primary strategy timeframe.")

        if not isinstance(
            self.data,
            CandleDataSnapshot,
        ):
            raise ValueError("data must be a CandleDataSnapshot.")

        if self.data.request.timeframe != timeframe:
            raise ValueError("Candle snapshot timeframe does not match the slice timeframe.")

        if self.data.forming is not None:
            raise ValueError("Strategy timeframe slices cannot contain forming candles.")

        object.__setattr__(
            self,
            "timeframe",
            timeframe,
        )

    @property
    def closed(self) -> ClosedCandleSeries:
        return self.data.closed

    @property
    def broker_symbol(self) -> str:
        return self.closed.broker_symbol

    @property
    def latest_close_time(self) -> datetime:
        return self.closed.latest.close_time

    @property
    def loaded_at(self) -> datetime:
        return self.data.loaded_at

    @property
    def has_gaps(self) -> bool:
        return self.closed.has_gaps

    def age_at(
        self,
        evaluated_at: datetime,
    ) -> timedelta:
        normalized = _utc_datetime(
            evaluated_at,
            "evaluated_at",
        )

        return normalized - self.latest_close_time

    def maximum_age(
        self,
        staleness_bars: int,
    ) -> timedelta:
        bars = _bounded_positive_integer(
            staleness_bars,
            "staleness_bars",
            100,
        )

        return get_timeframe_spec(self.timeframe).duration * bars

    def is_stale_at(
        self,
        evaluated_at: datetime,
        staleness_bars: int,
    ) -> bool:
        return self.age_at(evaluated_at) > self.maximum_age(staleness_bars)


@dataclass(frozen=True, slots=True)
class MultiTimeframeMarketSnapshot:
    """Synchronized H4/H1/M15/M5 strategy market state."""

    request: MultiTimeframeLoadRequest
    evaluated_at: datetime
    slices: tuple[TimeframeMarketSlice, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.request,
            MultiTimeframeLoadRequest,
        ):
            raise ValueError("request must be a MultiTimeframeLoadRequest.")

        evaluated_at = _utc_datetime(
            self.evaluated_at,
            "evaluated_at",
        )
        slices = tuple(self.slices)

        if len(slices) != len(SUPPORTED_STRATEGY_TIMEFRAMES):
            raise ValueError("Exactly four primary timeframe slices are required.")

        for market_slice in slices:
            if not isinstance(
                market_slice,
                TimeframeMarketSlice,
            ):
                raise ValueError("slices must contain TimeframeMarketSlice instances.")

        timeframes = tuple(market_slice.timeframe for market_slice in slices)

        if len(timeframes) != len(set(timeframes)):
            raise ValueError("Duplicate timeframe slices are not allowed.")

        missing = tuple(
            timeframe for timeframe in SUPPORTED_STRATEGY_TIMEFRAMES if timeframe not in timeframes
        )

        if missing:
            missing_text = ", ".join(timeframe.value for timeframe in missing)
            raise ValueError(f"Primary timeframe slices are missing: {missing_text}.")

        ordered_slices = tuple(
            next(market_slice for market_slice in slices if market_slice.timeframe == timeframe)
            for timeframe in SUPPORTED_STRATEGY_TIMEFRAMES
        )

        for market_slice in ordered_slices:
            if market_slice.broker_symbol != self.request.broker_symbol:
                raise ValueError("All timeframe slices must use the requested broker symbol.")

            expected_count = self.request.count_for(market_slice.timeframe)

            if market_slice.closed.count != expected_count:
                raise ValueError(
                    f"{market_slice.timeframe.value} candle count does not match the request."
                )

            if market_slice.loaded_at > evaluated_at:
                raise ValueError(
                    f"{market_slice.timeframe.value} snapshot was loaded in the future."
                )

            if market_slice.latest_close_time > evaluated_at:
                raise ValueError(
                    f"{market_slice.timeframe.value} latest closed candle is in the future."
                )

        object.__setattr__(
            self,
            "evaluated_at",
            evaluated_at,
        )
        object.__setattr__(
            self,
            "slices",
            ordered_slices,
        )

    @property
    def by_timeframe(
        self,
    ) -> Mapping[
        TimeframeName,
        TimeframeMarketSlice,
    ]:
        return MappingProxyType(
            {market_slice.timeframe: market_slice for market_slice in self.slices}
        )

    def get(
        self,
        timeframe: TimeframeName | str,
    ) -> TimeframeMarketSlice:
        parsed = parse_timeframe(timeframe)

        try:
            return self.by_timeframe[parsed]
        except KeyError as error:
            raise ValueError(
                f"{parsed.value} is not available in this strategy snapshot."
            ) from error

    @property
    def h4(self) -> TimeframeMarketSlice:
        return self.get(TimeframeName.H4)

    @property
    def h1(self) -> TimeframeMarketSlice:
        return self.get(TimeframeName.H1)

    @property
    def m15(self) -> TimeframeMarketSlice:
        return self.get(TimeframeName.M15)

    @property
    def m5(self) -> TimeframeMarketSlice:
        return self.get(TimeframeName.M5)

    @property
    def stale_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return tuple(
            market_slice.timeframe
            for market_slice in self.slices
            if market_slice.is_stale_at(
                self.evaluated_at,
                self.request.max_staleness_bars,
            )
        )

    @property
    def gap_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return tuple(
            market_slice.timeframe for market_slice in self.slices if market_slice.has_gaps
        )

    @property
    def all_fresh(self) -> bool:
        return not self.stale_timeframes

    @property
    def has_gaps(self) -> bool:
        return bool(self.gap_timeframes)

    @property
    def latest_close_times(
        self,
    ) -> Mapping[TimeframeName, datetime]:
        return MappingProxyType(
            {
                market_slice.timeframe: (market_slice.latest_close_time)
                for market_slice in self.slices
            }
        )

    @property
    def strategy_series(
        self,
    ) -> Mapping[
        TimeframeName,
        ClosedCandleSeries,
    ]:
        return MappingProxyType(
            {market_slice.timeframe: (market_slice.closed) for market_slice in self.slices}
        )


@runtime_checkable
class ClosedCandleSnapshotReader(Protocol):
    """Closed-candle loader contract used by the orchestrator."""

    def read_snapshot(
        self,
        request: CandleLoadRequest,
    ) -> CandleDataSnapshot: ...


class MultiTimeframeMarketDataService:
    """
    Read-only H4/H1/M15/M5 candle orchestrator.

    Every underlying request is closed-only. Forming candles
    never enter the strategy snapshot.
    """

    def __init__(
        self,
        candle_reader: ClosedCandleSnapshotReader,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(
            candle_reader,
            ClosedCandleSnapshotReader,
        ):
            raise ValueError("candle_reader must implement ClosedCandleSnapshotReader.")

        if not callable(clock):
            raise ValueError("clock must be callable.")

        self._candle_reader = candle_reader
        self._clock = clock

    def read_snapshot(
        self,
        request: MultiTimeframeLoadRequest,
    ) -> MultiTimeframeMarketSnapshot:
        if not isinstance(
            request,
            MultiTimeframeLoadRequest,
        ):
            raise ValueError("request must be a MultiTimeframeLoadRequest.")

        try:
            evaluated_at = _utc_datetime(
                self._clock(),
                "clock result",
            )
        except Exception as error:
            raise MultiTimeframeDataServiceError(
                MultiTimeframeDataErrorReason.INVALID_CLOCK,
                str(error),
            ) from error

        slices: list[TimeframeMarketSlice] = []

        for timeframe in SUPPORTED_STRATEGY_TIMEFRAMES:
            load_request = CandleLoadRequest(
                broker_symbol=request.broker_symbol,
                timeframe=timeframe,
                closed_count=request.count_for(timeframe),
                include_forming=False,
                require_contiguous=(request.require_contiguous),
            )

            try:
                data = self._candle_reader.read_snapshot(load_request)
            except CandleDataServiceError as error:
                raise MultiTimeframeDataServiceError(
                    MultiTimeframeDataErrorReason.TIMEFRAME_LOAD_FAILED,
                    str(error),
                    timeframe=timeframe,
                ) from error
            except Exception as error:
                raise MultiTimeframeDataServiceError(
                    MultiTimeframeDataErrorReason.TIMEFRAME_LOAD_FAILED,
                    f"Loading closed candles raised {type(error).__name__}: {error}",
                    timeframe=timeframe,
                ) from error

            if not isinstance(
                data,
                CandleDataSnapshot,
            ):
                raise MultiTimeframeDataServiceError(
                    MultiTimeframeDataErrorReason.INVALID_TIMEFRAME_SNAPSHOT,
                    "Candle reader returned an unsupported snapshot type.",
                    timeframe=timeframe,
                )

            try:
                slices.append(
                    TimeframeMarketSlice(
                        timeframe=timeframe,
                        data=data,
                    )
                )
            except ValueError as error:
                raise MultiTimeframeDataServiceError(
                    MultiTimeframeDataErrorReason.INVALID_TIMEFRAME_SNAPSHOT,
                    str(error),
                    timeframe=timeframe,
                ) from error

        try:
            snapshot = MultiTimeframeMarketSnapshot(
                request=request,
                evaluated_at=evaluated_at,
                slices=tuple(slices),
            )
        except ValueError as error:
            message = str(error)

            if "future" in message:
                reason = MultiTimeframeDataErrorReason.SNAPSHOT_FROM_FUTURE
            elif "symbol" in message:
                reason = MultiTimeframeDataErrorReason.SYMBOL_MISMATCH
            elif "Duplicate" in message:
                reason = MultiTimeframeDataErrorReason.DUPLICATE_TIMEFRAME
            elif "missing" in message:
                reason = MultiTimeframeDataErrorReason.MISSING_TIMEFRAME
            else:
                reason = MultiTimeframeDataErrorReason.INVALID_TIMEFRAME_SNAPSHOT

            raise MultiTimeframeDataServiceError(
                reason,
                message,
            ) from error

        if request.require_contiguous and snapshot.has_gaps:
            gap_text = ", ".join(timeframe.value for timeframe in snapshot.gap_timeframes)

            raise MultiTimeframeDataServiceError(
                MultiTimeframeDataErrorReason.HISTORY_GAP,
                f"Closed candle history contains gaps in: {gap_text}.",
            )

        if request.reject_stale and not snapshot.all_fresh:
            stale_text = ", ".join(timeframe.value for timeframe in snapshot.stale_timeframes)

            raise MultiTimeframeDataServiceError(
                MultiTimeframeDataErrorReason.STALE_MARKET_DATA,
                f"Latest closed candle is stale in: {stale_text}.",
            )

        return snapshot

    def read_strategy_snapshot(
        self,
        *,
        broker_symbol: str,
        h4_count: int,
        h1_count: int,
        m15_count: int,
        m5_count: int,
        require_contiguous: bool = True,
        max_staleness_bars: int = 1,
        reject_stale: bool = True,
    ) -> MultiTimeframeMarketSnapshot:
        request = MultiTimeframeLoadRequest(
            broker_symbol=broker_symbol,
            h4_count=h4_count,
            h1_count=h1_count,
            m15_count=m15_count,
            m5_count=m5_count,
            require_contiguous=require_contiguous,
            max_staleness_bars=max_staleness_bars,
            reject_stale=reject_stale,
        )

        return self.read_snapshot(request)

    def get_strategy_snapshot(
        self,
        *,
        broker_symbol: str,
        h4_count: int,
        h1_count: int,
        m15_count: int,
        m5_count: int,
        require_contiguous: bool = True,
        max_staleness_bars: int = 1,
        reject_stale: bool = True,
    ) -> MultiTimeframeMarketSnapshot:
        """Compatibility alias for read_strategy_snapshot()."""

        return self.read_strategy_snapshot(
            broker_symbol=broker_symbol,
            h4_count=h4_count,
            h1_count=h1_count,
            m15_count=m15_count,
            m5_count=m5_count,
            require_contiguous=require_contiguous,
            max_staleness_bars=max_staleness_bars,
            reject_stale=reject_stale,
        )


StrategyTimeframeService = MultiTimeframeMarketDataService
