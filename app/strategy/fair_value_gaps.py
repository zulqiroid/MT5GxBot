from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TypeAlias

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)

DecimalLike: TypeAlias = Decimal | int | float | str


class FairValueGapDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class FairValueGapDetectionErrorReason(str, Enum):
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INVALID_SERIES = "INVALID_SERIES"


class FairValueGapDetectionError(RuntimeError):
    """Structured three-candle FVG detection failure."""

    def __init__(
        self,
        reason: FairValueGapDetectionErrorReason,
        message: str,
    ) -> None:
        self.reason = FairValueGapDetectionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Fair value gap detection error [{self.reason.value}]: {self.message}")


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


def _non_negative_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid decimal number.") from error

    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if decimal_value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return decimal_value


def _ratio_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    ratio = _non_negative_decimal(
        value,
        field_name,
    )

    if ratio > Decimal("1"):
        raise ValueError(f"{field_name} cannot exceed one.")

    return ratio


def _positive_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    decimal_value = _non_negative_decimal(
        value,
        field_name,
    )

    if decimal_value == 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return decimal_value


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _middle_body_ratio(
    candle: ClosedCandle,
) -> Decimal:
    candle_range = candle.high - candle.low

    if candle_range == 0:
        return Decimal("0")

    return abs(candle.close - candle.open) / candle_range


def _middle_direction_matches(
    candle: ClosedCandle,
    direction: FairValueGapDirection,
) -> bool:
    if direction == FairValueGapDirection.BULLISH:
        return candle.close > candle.open

    return candle.close < candle.open


@dataclass(frozen=True, slots=True)
class FairValueGapPolicy:
    """Deterministic ICT three-candle FVG policy."""

    minimum_gap_size: Decimal = Decimal("0")
    require_middle_direction: bool = True
    minimum_middle_body_ratio: Decimal = Decimal("0.50")

    def __post_init__(self) -> None:
        minimum_gap_size = _non_negative_decimal(
            self.minimum_gap_size,
            "minimum_gap_size",
        )
        require_middle_direction = _strict_boolean(
            self.require_middle_direction,
            "require_middle_direction",
        )
        minimum_middle_body_ratio = _ratio_decimal(
            self.minimum_middle_body_ratio,
            "minimum_middle_body_ratio",
        )

        object.__setattr__(
            self,
            "minimum_gap_size",
            minimum_gap_size,
        )
        object.__setattr__(
            self,
            "require_middle_direction",
            require_middle_direction,
        )
        object.__setattr__(
            self,
            "minimum_middle_body_ratio",
            minimum_middle_body_ratio,
        )


@dataclass(frozen=True, slots=True)
class FairValueGap:
    """One confirmed bullish or bearish three-candle FVG."""

    first_index: int
    direction: FairValueGapDirection
    first_candle: ClosedCandle
    middle_candle: ClosedCandle
    third_candle: ClosedCandle

    def __post_init__(self) -> None:
        first_index = _non_negative_integer(
            self.first_index,
            "first_index",
        )

        try:
            direction = FairValueGapDirection(self.direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported fair value gap direction: {self.direction}.") from error

        candles = (
            self.first_candle,
            self.middle_candle,
            self.third_candle,
        )

        for candle in candles:
            if not isinstance(candle, ClosedCandle):
                raise ValueError("FVG candles must be ClosedCandle instances.")

        broker_symbols = {candle.broker_symbol for candle in candles}
        timeframes = {candle.timeframe for candle in candles}

        if len(broker_symbols) != 1:
            raise ValueError("All FVG candles must use the same broker symbol.")

        if len(timeframes) != 1:
            raise ValueError("All FVG candles must use the same timeframe.")

        duration = self.first_candle.close_time - self.first_candle.open_time

        if self.middle_candle.open_time != self.first_candle.open_time + duration:
            raise ValueError("Middle candle must immediately follow the first candle.")

        if self.third_candle.open_time != self.middle_candle.open_time + duration:
            raise ValueError("Third candle must immediately follow the middle candle.")

        if direction == FairValueGapDirection.BULLISH:
            if self.third_candle.low <= self.first_candle.high:
                raise ValueError(
                    "Bullish FVG requires the third-candle low above the first-candle high."
                )
        elif self.third_candle.high >= self.first_candle.low:
            raise ValueError(
                "Bearish FVG requires the third-candle high below the first-candle low."
            )

        object.__setattr__(
            self,
            "first_index",
            first_index,
        )
        object.__setattr__(
            self,
            "direction",
            direction,
        )

    @property
    def middle_index(self) -> int:
        return self.first_index + 1

    @property
    def confirmation_index(self) -> int:
        return self.first_index + 2

    @property
    def confirmed_at(self) -> datetime:
        return self.third_candle.close_time

    @property
    def broker_symbol(self) -> str:
        return self.first_candle.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.first_candle.timeframe

    @property
    def lower_bound(self) -> Decimal:
        if self.direction == FairValueGapDirection.BULLISH:
            return self.first_candle.high

        return self.third_candle.high

    @property
    def upper_bound(self) -> Decimal:
        if self.direction == FairValueGapDirection.BULLISH:
            return self.third_candle.low

        return self.first_candle.low

    @property
    def size(self) -> Decimal:
        return self.upper_bound - self.lower_bound

    @property
    def midpoint(self) -> Decimal:
        return (self.lower_bound + self.upper_bound) / Decimal("2")

    @property
    def middle_body_ratio(self) -> Decimal:
        return _middle_body_ratio(self.middle_candle)

    @property
    def middle_direction_matches(self) -> bool:
        return _middle_direction_matches(
            self.middle_candle,
            self.direction,
        )

    @property
    def is_bullish(self) -> bool:
        return self.direction == FairValueGapDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == FairValueGapDirection.BEARISH

    @property
    def stable_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.timeframe.value}:"
            f"{self.direction.value}:"
            f"{self.first_index}:"
            f"{self.confirmation_index}"
        )

    def contains_price(
        self,
        price: DecimalLike,
    ) -> bool:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        return self.lower_bound <= selected_price <= self.upper_bound

    def distance_from(
        self,
        price: DecimalLike,
    ) -> Decimal:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        if self.contains_price(selected_price):
            return Decimal("0")

        if selected_price < self.lower_bound:
            return self.lower_bound - selected_price

        return selected_price - self.upper_bound


@dataclass(frozen=True, slots=True)
class FairValueGapSet:
    """Ordered FVGs detected from one closed-candle series."""

    source: ClosedCandleSeries
    policy: FairValueGapPolicy
    gaps: tuple[FairValueGap, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.source,
            ClosedCandleSeries,
        ):
            raise ValueError("source must be a ClosedCandleSeries.")

        if not isinstance(
            self.policy,
            FairValueGapPolicy,
        ):
            raise ValueError("policy must be a FairValueGapPolicy.")

        gaps = tuple(self.gaps)
        direction_order = {
            FairValueGapDirection.BULLISH: 0,
            FairValueGapDirection.BEARISH: 1,
        }

        expected_order = tuple(
            sorted(
                gaps,
                key=lambda gap: (
                    gap.confirmation_index,
                    direction_order[gap.direction],
                ),
            )
        )

        if gaps != expected_order:
            raise ValueError("Fair value gaps must be ordered by confirmation index.")

        stable_ids: set[str] = set()

        for gap in gaps:
            if not isinstance(gap, FairValueGap):
                raise ValueError("gaps must contain FairValueGap instances.")

            if gap.confirmation_index >= self.source.count:
                raise ValueError("FVG confirmation index exceeds source history.")

            expected_candles = (
                self.source.candles[gap.first_index],
                self.source.candles[gap.middle_index],
                self.source.candles[gap.confirmation_index],
            )

            if expected_candles != (
                gap.first_candle,
                gap.middle_candle,
                gap.third_candle,
            ):
                raise ValueError("FVG candles do not match the source history at their indexes.")

            if gap.size <= self.policy.minimum_gap_size:
                raise ValueError("FVG does not exceed the configured minimum gap size.")

            if self.policy.require_middle_direction and not gap.middle_direction_matches:
                raise ValueError("FVG middle-candle direction does not match the gap direction.")

            if gap.middle_body_ratio < self.policy.minimum_middle_body_ratio:
                raise ValueError("FVG middle-candle body ratio is below the configured minimum.")

            if gap.stable_id in stable_ids:
                raise ValueError("Duplicate fair value gaps are not allowed.")

            stable_ids.add(gap.stable_id)

        object.__setattr__(
            self,
            "gaps",
            gaps,
        )

    @property
    def broker_symbol(self) -> str:
        return self.source.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.source.timeframe

    @property
    def count(self) -> int:
        return len(self.gaps)

    @property
    def bullish(
        self,
    ) -> tuple[FairValueGap, ...]:
        return tuple(gap for gap in self.gaps if gap.direction == FairValueGapDirection.BULLISH)

    @property
    def bearish(
        self,
    ) -> tuple[FairValueGap, ...]:
        return tuple(gap for gap in self.gaps if gap.direction == FairValueGapDirection.BEARISH)

    @property
    def latest(
        self,
    ) -> FairValueGap | None:
        if not self.gaps:
            return None

        return self.gaps[-1]

    @property
    def latest_bullish(
        self,
    ) -> FairValueGap | None:
        if not self.bullish:
            return None

        return self.bullish[-1]

    @property
    def latest_bearish(
        self,
    ) -> FairValueGap | None:
        if not self.bearish:
            return None

        return self.bearish[-1]

    def by_direction(
        self,
        direction: FairValueGapDirection,
    ) -> tuple[FairValueGap, ...]:
        try:
            selected_direction = FairValueGapDirection(direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported fair value gap direction: {direction}.") from error

        if selected_direction == FairValueGapDirection.BULLISH:
            return self.bullish

        return self.bearish

    def confirmed_at_index(
        self,
        index: int,
    ) -> tuple[FairValueGap, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(gap for gap in self.gaps if gap.confirmation_index == selected_index)

    def nearest_bullish_below(
        self,
        price: DecimalLike,
    ) -> FairValueGap | None:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        candidates = tuple(gap for gap in self.bullish if gap.midpoint <= selected_price)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda gap: (
                selected_price - gap.midpoint,
                -gap.confirmation_index,
            ),
        )

    def nearest_bearish_above(
        self,
        price: DecimalLike,
    ) -> FairValueGap | None:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        candidates = tuple(gap for gap in self.bearish if gap.midpoint >= selected_price)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda gap: (
                gap.midpoint - selected_price,
                -gap.confirmation_index,
            ),
        )


class FairValueGapDetector:
    """
    Pure three-candle ICT FVG detector.

    Every FVG is confirmed only when the third candle has
    fully closed.
    """

    def __init__(
        self,
        policy: FairValueGapPolicy | None = None,
    ) -> None:
        selected_policy = policy or FairValueGapPolicy()

        if not isinstance(
            selected_policy,
            FairValueGapPolicy,
        ):
            raise ValueError("policy must be a FairValueGapPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> FairValueGapPolicy:
        return self._policy

    def detect(
        self,
        series: ClosedCandleSeries,
    ) -> FairValueGapSet:
        if not isinstance(
            series,
            ClosedCandleSeries,
        ):
            raise FairValueGapDetectionError(
                FairValueGapDetectionErrorReason.INVALID_SERIES,
                "series must be a ClosedCandleSeries.",
            )

        if series.count < 3:
            raise FairValueGapDetectionError(
                FairValueGapDetectionErrorReason.INSUFFICIENT_HISTORY,
                f"At least three closed candles are required; received {series.count}.",
            )

        gaps: list[FairValueGap] = []

        for first_index in range(series.count - 2):
            first_candle = series.candles[first_index]
            middle_candle = series.candles[first_index + 1]
            third_candle = series.candles[first_index + 2]

            direction: FairValueGapDirection | None = None

            if third_candle.low > first_candle.high:
                direction = FairValueGapDirection.BULLISH
            elif third_candle.high < first_candle.low:
                direction = FairValueGapDirection.BEARISH

            if direction is None:
                continue

            gap = FairValueGap(
                first_index=first_index,
                direction=direction,
                first_candle=first_candle,
                middle_candle=middle_candle,
                third_candle=third_candle,
            )

            if gap.size <= self._policy.minimum_gap_size:
                continue

            if self._policy.require_middle_direction and not gap.middle_direction_matches:
                continue

            if gap.middle_body_ratio < self._policy.minimum_middle_body_ratio:
                continue

            gaps.append(gap)

        return FairValueGapSet(
            source=series,
            policy=self._policy,
            gaps=tuple(gaps),
        )

    def evaluate(
        self,
        series: ClosedCandleSeries,
    ) -> FairValueGapSet:
        """Compatibility alias for detect()."""

        return self.detect(series)

    def find(
        self,
        series: ClosedCandleSeries,
    ) -> FairValueGapSet:
        """Compatibility alias for detect()."""

        return self.detect(series)


def detect_fair_value_gaps(
    series: ClosedCandleSeries,
    policy: FairValueGapPolicy | None = None,
) -> FairValueGapSet:
    return FairValueGapDetector(policy=policy).detect(series)


FVGDirection = FairValueGapDirection
FVGPolicy = FairValueGapPolicy
FVG = FairValueGap
FVGSet = FairValueGapSet
FVGDetector = FairValueGapDetector
