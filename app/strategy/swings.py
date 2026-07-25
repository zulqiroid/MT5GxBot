from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TypeAlias

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)


class SwingKind(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


class SwingDetectionErrorReason(str, Enum):
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INVALID_SERIES = "INVALID_SERIES"


class SwingDetectionError(RuntimeError):
    """Structured failure while detecting confirmed swings."""

    def __init__(
        self,
        reason: SwingDetectionErrorReason,
        message: str,
    ) -> None:
        self.reason = SwingDetectionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Swing detection error [{self.reason.value}]: {self.message}")


def _positive_integer(
    value: object,
    field_name: str,
    maximum: int = 1_000,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    if value > maximum:
        raise ValueError(f"{field_name} cannot exceed {maximum}.")

    return value


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

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
class SwingDetectionPolicy:
    """Conservative fractal swing-confirmation policy."""

    left_bars: int = 2
    right_bars: int = 2
    allow_dual_swings: bool = False

    def __post_init__(self) -> None:
        left_bars = _positive_integer(
            self.left_bars,
            "left_bars",
        )
        right_bars = _positive_integer(
            self.right_bars,
            "right_bars",
        )
        allow_dual_swings = _strict_boolean(
            self.allow_dual_swings,
            "allow_dual_swings",
        )

        object.__setattr__(
            self,
            "left_bars",
            left_bars,
        )
        object.__setattr__(
            self,
            "right_bars",
            right_bars,
        )
        object.__setattr__(
            self,
            "allow_dual_swings",
            allow_dual_swings,
        )

    @property
    def minimum_candles(self) -> int:
        return self.left_bars + 1 + self.right_bars

    @property
    def window_size(self) -> int:
        return self.minimum_candles


@dataclass(frozen=True, slots=True)
class ConfirmedSwingPoint:
    """One closed-candle swing confirmed by right-side bars."""

    index: int
    kind: SwingKind
    candle: ClosedCandle
    confirmed_by_index: int
    confirmed_at: datetime

    def __post_init__(self) -> None:
        index = _non_negative_integer(
            self.index,
            "index",
        )
        confirmed_by_index = _non_negative_integer(
            self.confirmed_by_index,
            "confirmed_by_index",
        )

        try:
            kind = SwingKind(self.kind)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported swing kind: {self.kind}.") from error

        if not isinstance(self.candle, ClosedCandle):
            raise ValueError("candle must be a ClosedCandle.")

        confirmed_at = _utc_datetime(
            self.confirmed_at,
            "confirmed_at",
        )

        if confirmed_by_index <= index:
            raise ValueError("confirmed_by_index must be greater than the swing index.")

        if confirmed_at < self.candle.close_time:
            raise ValueError("confirmed_at cannot precede the swing candle close.")

        object.__setattr__(self, "index", index)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "confirmed_by_index",
            confirmed_by_index,
        )
        object.__setattr__(
            self,
            "confirmed_at",
            confirmed_at,
        )

    @property
    def price(self) -> Decimal:
        if self.kind == SwingKind.HIGH:
            return self.candle.high

        return self.candle.low

    @property
    def open_time(self) -> datetime:
        return self.candle.open_time

    @property
    def close_time(self) -> datetime:
        return self.candle.close_time

    @property
    def broker_symbol(self) -> str:
        return self.candle.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.candle.timeframe

    @property
    def is_high(self) -> bool:
        return self.kind == SwingKind.HIGH

    @property
    def is_low(self) -> bool:
        return self.kind == SwingKind.LOW


SwingPointKey: TypeAlias = tuple[int, SwingKind]


@dataclass(frozen=True, slots=True)
class ConfirmedSwingSet:
    """Ordered confirmed swings derived from one candle series."""

    source: ClosedCandleSeries
    policy: SwingDetectionPolicy
    points: tuple[ConfirmedSwingPoint, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.source,
            ClosedCandleSeries,
        ):
            raise ValueError("source must be a ClosedCandleSeries.")

        if not isinstance(
            self.policy,
            SwingDetectionPolicy,
        ):
            raise ValueError("policy must be a SwingDetectionPolicy.")

        points = tuple(self.points)

        ordering = {
            SwingKind.HIGH: 0,
            SwingKind.LOW: 1,
        }

        expected_order = tuple(
            sorted(
                points,
                key=lambda point: (
                    point.index,
                    ordering[point.kind],
                ),
            )
        )

        if points != expected_order:
            raise ValueError("Swing points must be ordered by candle index.")

        keys: list[SwingPointKey] = []
        indexes: list[int] = []

        for point in points:
            if not isinstance(
                point,
                ConfirmedSwingPoint,
            ):
                raise ValueError("points must contain ConfirmedSwingPoint instances.")

            if point.index >= self.source.count:
                raise ValueError("Swing index exceeds source history.")

            if point.confirmed_by_index >= self.source.count:
                raise ValueError("Swing confirmation index exceeds source history.")

            if point.confirmed_by_index != point.index + self.policy.right_bars:
                raise ValueError("Swing confirmation index does not match the detection policy.")

            if point.candle != self.source.candles[point.index]:
                raise ValueError("Swing candle does not match the source candle at its index.")

            expected_confirmation_time = self.source.candles[point.confirmed_by_index].close_time

            if point.confirmed_at != expected_confirmation_time:
                raise ValueError("Swing confirmation time does not match its confirming candle.")

            keys.append((point.index, point.kind))
            indexes.append(point.index)

        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate swing point keys are not allowed.")

        if not self.policy.allow_dual_swings and len(indexes) != len(set(indexes)):
            raise ValueError("Dual swings are disabled by the policy.")

        object.__setattr__(
            self,
            "points",
            points,
        )

    @property
    def broker_symbol(self) -> str:
        return self.source.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.source.timeframe

    @property
    def count(self) -> int:
        return len(self.points)

    @property
    def highs(
        self,
    ) -> tuple[ConfirmedSwingPoint, ...]:
        return tuple(point for point in self.points if point.kind == SwingKind.HIGH)

    @property
    def lows(
        self,
    ) -> tuple[ConfirmedSwingPoint, ...]:
        return tuple(point for point in self.points if point.kind == SwingKind.LOW)

    @property
    def latest(
        self,
    ) -> ConfirmedSwingPoint | None:
        if not self.points:
            return None

        return self.points[-1]

    @property
    def latest_high(
        self,
    ) -> ConfirmedSwingPoint | None:
        if not self.highs:
            return None

        return self.highs[-1]

    @property
    def latest_low(
        self,
    ) -> ConfirmedSwingPoint | None:
        if not self.lows:
            return None

        return self.lows[-1]

    @property
    def unconfirmed_tail_count(self) -> int:
        return self.policy.right_bars

    @property
    def last_eligible_index(self) -> int:
        return self.source.count - self.policy.right_bars - 1

    @property
    def contains_dual_swing(self) -> bool:
        indexes = [point.index for point in self.points]

        return len(indexes) != len(set(indexes))

    def at_index(
        self,
        index: int,
    ) -> tuple[ConfirmedSwingPoint, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(point for point in self.points if point.index == selected_index)

    def by_kind(
        self,
        kind: SwingKind,
    ) -> tuple[ConfirmedSwingPoint, ...]:
        try:
            selected_kind = SwingKind(kind)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported swing kind: {kind}.") from error

        return tuple(point for point in self.points if point.kind == selected_kind)


class ConfirmedSwingDetector:
    """
    Pure confirmed fractal swing detector.

    A candle becomes eligible only after all configured
    right-side candles have closed.
    """

    def __init__(
        self,
        policy: SwingDetectionPolicy | None = None,
    ) -> None:
        selected_policy = policy or SwingDetectionPolicy()

        if not isinstance(
            selected_policy,
            SwingDetectionPolicy,
        ):
            raise ValueError("policy must be a SwingDetectionPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> SwingDetectionPolicy:
        return self._policy

    def detect(
        self,
        series: ClosedCandleSeries,
    ) -> ConfirmedSwingSet:
        if not isinstance(
            series,
            ClosedCandleSeries,
        ):
            raise SwingDetectionError(
                SwingDetectionErrorReason.INVALID_SERIES,
                "series must be a ClosedCandleSeries.",
            )

        if series.count < self._policy.minimum_candles:
            raise SwingDetectionError(
                SwingDetectionErrorReason.INSUFFICIENT_HISTORY,
                f"At least "
                f"{self._policy.minimum_candles} closed "
                f"candles are required; received "
                f"{series.count}.",
            )

        points: list[ConfirmedSwingPoint] = []

        first_index = self._policy.left_bars
        final_exclusive = series.count - self._policy.right_bars

        for index in range(
            first_index,
            final_exclusive,
        ):
            candle = series.candles[index]

            left_candles = series.candles[index - self._policy.left_bars : index]
            right_candles = series.candles[index + 1 : index + 1 + self._policy.right_bars]
            neighbors = (
                *left_candles,
                *right_candles,
            )

            is_swing_high = all(candle.high > neighbor.high for neighbor in neighbors)
            is_swing_low = all(candle.low < neighbor.low for neighbor in neighbors)

            if is_swing_high and is_swing_low and not self._policy.allow_dual_swings:
                continue

            confirmation_index = index + self._policy.right_bars
            confirmed_at = series.candles[confirmation_index].close_time

            if is_swing_high:
                points.append(
                    ConfirmedSwingPoint(
                        index=index,
                        kind=SwingKind.HIGH,
                        candle=candle,
                        confirmed_by_index=(confirmation_index),
                        confirmed_at=confirmed_at,
                    )
                )

            if is_swing_low:
                points.append(
                    ConfirmedSwingPoint(
                        index=index,
                        kind=SwingKind.LOW,
                        candle=candle,
                        confirmed_by_index=(confirmation_index),
                        confirmed_at=confirmed_at,
                    )
                )

        return ConfirmedSwingSet(
            source=series,
            policy=self._policy,
            points=tuple(points),
        )

    def evaluate(
        self,
        series: ClosedCandleSeries,
    ) -> ConfirmedSwingSet:
        """Compatibility alias for detect()."""

        return self.detect(series)


def detect_confirmed_swings(
    series: ClosedCandleSeries,
    policy: SwingDetectionPolicy | None = None,
) -> ConfirmedSwingSet:
    return ConfirmedSwingDetector(policy=policy).detect(series)


SwingPoint = ConfirmedSwingPoint
SwingPointSet = ConfirmedSwingSet
SwingDetector = ConfirmedSwingDetector
