from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from app.config.constants import TimeframeName
from app.market.timeframes import get_timeframe_spec
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiTimeframeContextSnapshot,
)


class ContextFreshnessStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class ContextFreshnessReason(str, Enum):
    ALL_TIMEFRAMES_FRESH = "ALL_TIMEFRAMES_FRESH"
    STALE_TIMEFRAME = "STALE_TIMEFRAME"


class ContextFreshnessErrorReason(str, Enum):
    INVALID_CONTEXT = "INVALID_CONTEXT"


class ContextFreshnessError(RuntimeError):
    """Structured context-freshness evaluation failure."""

    def __init__(
        self,
        reason: ContextFreshnessErrorReason,
        message: str,
    ) -> None:
        self.reason = ContextFreshnessErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Context freshness error [{self.reason.value}]: {self.message}")


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


def _require_aware_datetime(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value


def _require_positive_duration(
    value: object,
    field_name: str,
) -> timedelta:
    if not isinstance(value, timedelta):
        raise ValueError(f"{field_name} must be a timedelta.")

    if value <= timedelta(0):
        raise ValueError(f"{field_name} must be positive.")

    return value


def _duration_decimal_seconds(
    value: timedelta,
) -> Decimal:
    return Decimal(str(value.total_seconds()))


@dataclass(frozen=True, slots=True)
class ContextFreshnessPolicy:
    """Allowed lag in candle units for H4/H1/M15/M5."""

    maximum_lag_candles: tuple[
        tuple[TimeframeName, int],
        ...,
    ] = (
        (TimeframeName.H4, 1),
        (TimeframeName.H1, 1),
        (TimeframeName.M15, 1),
        (TimeframeName.M5, 1),
    )

    def __post_init__(self) -> None:
        maximum_lag_candles = tuple(self.maximum_lag_candles)

        normalized: list[tuple[TimeframeName, int]] = []

        for item in maximum_lag_candles:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError(
                    "maximum_lag_candles must contain (timeframe, candle_count) pairs."
                )

            timeframe, candle_count = item

            if not isinstance(
                timeframe,
                TimeframeName,
            ):
                raise ValueError("maximum_lag_candles must use TimeframeName members.")

            selected_timeframe = timeframe

            selected_count = _non_negative_integer(
                candle_count,
                "maximum_lag_candle_count",
            )

            normalized.append(
                (
                    selected_timeframe,
                    selected_count,
                )
            )

        actual_timeframes = tuple(timeframe for timeframe, _ in normalized)

        if actual_timeframes != GOLD_TIMEFRAME_HIERARCHY:
            raise ValueError("maximum_lag_candles must preserve the H4, H1, M15, M5 hierarchy.")

        if len(set(actual_timeframes)) != len(actual_timeframes):
            raise ValueError("maximum_lag_candles cannot contain duplicate timeframes.")

        object.__setattr__(
            self,
            "maximum_lag_candles",
            tuple(normalized),
        )

    def maximum_for(
        self,
        timeframe: TimeframeName,
    ) -> int:
        try:
            selected_timeframe = TimeframeName(timeframe)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported freshness timeframe: {timeframe}.") from error

        limits = dict(self.maximum_lag_candles)

        if selected_timeframe not in limits:
            raise ValueError("Timeframe is not configured in the freshness policy.")

        return limits[selected_timeframe]


@dataclass(frozen=True, slots=True)
class TimeframeFreshness:
    """Freshness metrics for one timeframe context."""

    timeframe: TimeframeName
    latest_close: datetime
    observed_at: datetime
    candle_duration: timedelta
    maximum_lag_candles: int

    def __post_init__(self) -> None:
        try:
            timeframe = TimeframeName(self.timeframe)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported freshness timeframe: {self.timeframe}.") from error

        latest_close = _require_aware_datetime(
            self.latest_close,
            "latest_close",
        )
        observed_at = _require_aware_datetime(
            self.observed_at,
            "observed_at",
        )
        candle_duration = _require_positive_duration(
            self.candle_duration,
            "candle_duration",
        )
        maximum_lag_candles = _non_negative_integer(
            self.maximum_lag_candles,
            "maximum_lag_candles",
        )

        if latest_close > observed_at:
            raise ValueError("latest_close cannot be after observed_at.")

        expected_duration = get_timeframe_spec(timeframe).duration

        if candle_duration != expected_duration:
            raise ValueError("candle_duration does not match the selected timeframe.")

        object.__setattr__(
            self,
            "timeframe",
            timeframe,
        )
        object.__setattr__(
            self,
            "latest_close",
            latest_close,
        )
        object.__setattr__(
            self,
            "observed_at",
            observed_at,
        )
        object.__setattr__(
            self,
            "candle_duration",
            candle_duration,
        )
        object.__setattr__(
            self,
            "maximum_lag_candles",
            maximum_lag_candles,
        )

    @property
    def lag(self) -> timedelta:
        return self.observed_at - self.latest_close

    @property
    def maximum_lag(self) -> timedelta:
        return self.candle_duration * self.maximum_lag_candles

    @property
    def lag_candle_fraction(self) -> Decimal:
        return _duration_decimal_seconds(self.lag) / _duration_decimal_seconds(self.candle_duration)

    @property
    def is_fresh(self) -> bool:
        return self.lag <= self.maximum_lag

    @property
    def is_stale(self) -> bool:
        return not self.is_fresh

    @property
    def excess_lag(self) -> timedelta:
        if self.is_fresh:
            return timedelta(0)

        return self.lag - self.maximum_lag

    @property
    def stable_id(self) -> str:
        return (
            f"{self.timeframe.value}:"
            f"{self.latest_close.isoformat()}:"
            f"{self.observed_at.isoformat()}:"
            f"{self.maximum_lag_candles}"
        )


def _derive_details(
    context: MultiTimeframeContextSnapshot,
    policy: ContextFreshnessPolicy,
) -> tuple[TimeframeFreshness, ...]:
    return tuple(
        TimeframeFreshness(
            timeframe=timeframe,
            latest_close=context.latest_close_for(timeframe),
            observed_at=context.observed_at,
            candle_duration=get_timeframe_spec(timeframe).duration,
            maximum_lag_candles=policy.maximum_for(timeframe),
        )
        for timeframe in GOLD_TIMEFRAME_HIERARCHY
    )


@dataclass(frozen=True, slots=True)
class ContextFreshnessDecision:
    """Validated readiness decision for one MTF context."""

    context: MultiTimeframeContextSnapshot
    policy: ContextFreshnessPolicy
    status: ContextFreshnessStatus
    reason: ContextFreshnessReason
    details: tuple[TimeframeFreshness, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.context,
            MultiTimeframeContextSnapshot,
        ):
            raise ValueError("context must be a MultiTimeframeContextSnapshot.")

        if not isinstance(
            self.policy,
            ContextFreshnessPolicy,
        ):
            raise ValueError("policy must be a ContextFreshnessPolicy.")

        try:
            status = ContextFreshnessStatus(self.status)
            reason = ContextFreshnessReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported freshness status or reason.") from error

        details = tuple(self.details)

        for detail in details:
            if not isinstance(
                detail,
                TimeframeFreshness,
            ):
                raise ValueError("details must contain TimeframeFreshness instances.")

        actual_timeframes = tuple(detail.timeframe for detail in details)

        if actual_timeframes != GOLD_TIMEFRAME_HIERARCHY:
            raise ValueError("Freshness details must follow the H4, H1, M15, M5 hierarchy.")

        expected_details = _derive_details(
            self.context,
            self.policy,
        )

        if details != expected_details:
            raise ValueError("Freshness details do not match their context and policy.")

        stale_exists = any(detail.is_stale for detail in details)
        expected_status = (
            ContextFreshnessStatus.BLOCKED if stale_exists else ContextFreshnessStatus.READY
        )
        expected_reason = (
            ContextFreshnessReason.STALE_TIMEFRAME
            if stale_exists
            else (ContextFreshnessReason.ALL_TIMEFRAMES_FRESH)
        )

        if status != expected_status:
            raise ValueError("Freshness status does not match the derived timeframe details.")

        if reason != expected_reason:
            raise ValueError("Freshness reason does not match the derived timeframe details.")

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self,
            "details",
            details,
        )

    @property
    def broker_symbol(self) -> str:
        return self.context.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.context.observed_at

    @property
    def is_ready(self) -> bool:
        return self.status == ContextFreshnessStatus.READY

    @property
    def is_blocked(self) -> bool:
        return not self.is_ready

    @property
    def fresh_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return tuple(detail.timeframe for detail in self.details if detail.is_fresh)

    @property
    def stale_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return tuple(detail.timeframe for detail in self.details if detail.is_stale)

    @property
    def fresh_count(self) -> int:
        return len(self.fresh_timeframes)

    @property
    def stale_count(self) -> int:
        return len(self.stale_timeframes)

    @property
    def worst_detail(self) -> TimeframeFreshness:
        return max(
            self.details,
            key=lambda detail: (
                detail.lag_candle_fraction,
                -GOLD_TIMEFRAME_HIERARCHY.index(detail.timeframe),
            ),
        )

    @property
    def worst_timeframe(self) -> TimeframeName:
        return self.worst_detail.timeframe

    @property
    def maximum_lag_candle_fraction(
        self,
    ) -> Decimal:
        return self.worst_detail.lag_candle_fraction

    def detail_for(
        self,
        timeframe: TimeframeName,
    ) -> TimeframeFreshness:
        try:
            selected_timeframe = TimeframeName(timeframe)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported freshness timeframe: {timeframe}.") from error

        for detail in self.details:
            if detail.timeframe == selected_timeframe:
                return detail

        raise ValueError("Timeframe is not part of this freshness decision.")

    @property
    def stable_id(self) -> str:
        stale_fragment = (
            "NONE"
            if not self.stale_timeframes
            else ",".join(timeframe.value for timeframe in self.stale_timeframes)
        )

        return f"{self.context.stable_id}:FRESHNESS:{self.status.value}:{stale_fragment}"


class MultiTimeframeFreshnessGate:
    """
    Pure market-context freshness gate.

    READY means synchronized context data is sufficiently
    recent. It does not authorize trading.
    """

    def __init__(
        self,
        policy: ContextFreshnessPolicy | None = None,
    ) -> None:
        selected_policy = policy or ContextFreshnessPolicy()

        if not isinstance(
            selected_policy,
            ContextFreshnessPolicy,
        ):
            raise ValueError("policy must be a ContextFreshnessPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> ContextFreshnessPolicy:
        return self._policy

    def evaluate(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> ContextFreshnessDecision:
        if not isinstance(
            context,
            MultiTimeframeContextSnapshot,
        ):
            raise ContextFreshnessError(
                ContextFreshnessErrorReason.INVALID_CONTEXT,
                "context must be a MultiTimeframeContextSnapshot.",
            )

        details = _derive_details(
            context,
            self._policy,
        )
        stale_exists = any(detail.is_stale for detail in details)

        return ContextFreshnessDecision(
            context=context,
            policy=self._policy,
            status=(
                ContextFreshnessStatus.BLOCKED if stale_exists else ContextFreshnessStatus.READY
            ),
            reason=(
                ContextFreshnessReason.STALE_TIMEFRAME
                if stale_exists
                else (ContextFreshnessReason.ALL_TIMEFRAMES_FRESH)
            ),
            details=details,
        )

    def check(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> ContextFreshnessDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(context)

    def decide(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> ContextFreshnessDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(context)


def evaluate_context_freshness(
    context: MultiTimeframeContextSnapshot,
    policy: ContextFreshnessPolicy | None = None,
) -> ContextFreshnessDecision:
    return MultiTimeframeFreshnessGate(policy=policy).evaluate(context)


FreshnessDecision = ContextFreshnessDecision
FreshnessDetail = TimeframeFreshness
FreshnessGate = MultiTimeframeFreshnessGate
FreshnessPolicy = ContextFreshnessPolicy
FreshnessReason = ContextFreshnessReason
FreshnessStatus = ContextFreshnessStatus
MultiTimeframeContextFreshnessGate = MultiTimeframeFreshnessGate
