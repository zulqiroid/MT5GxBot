from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TypeAlias

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandleSeries
from app.strategy.swings import (
    ConfirmedSwingPoint,
    ConfirmedSwingSet,
    SwingKind,
)

DecimalLike: TypeAlias = Decimal | int | float | str


class DealingRangeDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class DealingRangePriceLocation(str, Enum):
    BELOW_RANGE = "BELOW_RANGE"
    DISCOUNT = "DISCOUNT"
    EQUILIBRIUM = "EQUILIBRIUM"
    PREMIUM = "PREMIUM"
    ABOVE_RANGE = "ABOVE_RANGE"


class DealingRangeDetectionErrorReason(str, Enum):
    INVALID_SWING_SET = "INVALID_SWING_SET"


class DealingRangeDetectionError(RuntimeError):
    """Structured confirmed dealing-range detection failure."""

    def __init__(
        self,
        reason: DealingRangeDetectionErrorReason,
        message: str,
    ) -> None:
        self.reason = DealingRangeDetectionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Dealing range detection error [{self.reason.value}]: {self.message}")


def _positive_integer(
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
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a decimal number.")

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid decimal number.") from error

    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if decimal_value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return decimal_value


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


def _direction_for_anchors(
    first_anchor: ConfirmedSwingPoint,
    second_anchor: ConfirmedSwingPoint,
) -> DealingRangeDirection:
    if first_anchor.kind == SwingKind.LOW and second_anchor.kind == SwingKind.HIGH:
        return DealingRangeDirection.BULLISH

    if first_anchor.kind == SwingKind.HIGH and second_anchor.kind == SwingKind.LOW:
        return DealingRangeDirection.BEARISH

    raise ValueError("Dealing-range anchors must be opposite swing kinds.")


@dataclass(frozen=True, slots=True)
class DealingRangePolicy:
    """Deterministic confirmed-swing dealing-range policy."""

    minimum_range_size: Decimal = Decimal("0")
    maximum_anchor_gap: int = 100

    def __post_init__(self) -> None:
        minimum_range_size = _non_negative_decimal(
            self.minimum_range_size,
            "minimum_range_size",
        )
        maximum_anchor_gap = _positive_integer(
            self.maximum_anchor_gap,
            "maximum_anchor_gap",
            100_000,
        )

        object.__setattr__(
            self,
            "minimum_range_size",
            minimum_range_size,
        )
        object.__setattr__(
            self,
            "maximum_anchor_gap",
            maximum_anchor_gap,
        )


@dataclass(frozen=True, slots=True)
class DealingRange:
    """One confirmed swing-to-swing dealing range."""

    direction: DealingRangeDirection
    first_anchor: ConfirmedSwingPoint
    second_anchor: ConfirmedSwingPoint

    def __post_init__(self) -> None:
        try:
            direction = DealingRangeDirection(self.direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported dealing-range direction: {self.direction}.") from error

        if not isinstance(
            self.first_anchor,
            ConfirmedSwingPoint,
        ):
            raise ValueError("first_anchor must be a ConfirmedSwingPoint.")

        if not isinstance(
            self.second_anchor,
            ConfirmedSwingPoint,
        ):
            raise ValueError("second_anchor must be a ConfirmedSwingPoint.")

        if self.first_anchor.broker_symbol != self.second_anchor.broker_symbol:
            raise ValueError("Dealing-range anchors must use the same broker symbol.")

        if self.first_anchor.timeframe != self.second_anchor.timeframe:
            raise ValueError("Dealing-range anchors must use the same timeframe.")

        if self.first_anchor.index >= self.second_anchor.index:
            raise ValueError("The first dealing-range anchor must precede the second anchor.")

        expected_direction = _direction_for_anchors(
            self.first_anchor,
            self.second_anchor,
        )

        if direction != expected_direction:
            raise ValueError("Dealing-range direction must match the anchor sequence.")

        if (
            direction == DealingRangeDirection.BULLISH
            and self.second_anchor.price <= self.first_anchor.price
        ):
            raise ValueError("Bullish dealing range requires the high anchor above the low anchor.")

        if (
            direction == DealingRangeDirection.BEARISH
            and self.first_anchor.price <= self.second_anchor.price
        ):
            raise ValueError("Bearish dealing range requires the high anchor above the low anchor.")

        object.__setattr__(
            self,
            "direction",
            direction,
        )

    @property
    def broker_symbol(self) -> str:
        return self.first_anchor.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.first_anchor.timeframe

    @property
    def first_index(self) -> int:
        return self.first_anchor.index

    @property
    def second_index(self) -> int:
        return self.second_anchor.index

    @property
    def anchor_gap(self) -> int:
        return self.second_index - self.first_index

    @property
    def confirmation_index(self) -> int:
        return self.second_anchor.confirmed_by_index

    @property
    def confirmed_at(self) -> datetime:
        return self.second_anchor.confirmed_at

    @property
    def origin_price(self) -> Decimal:
        return self.first_anchor.price

    @property
    def terminal_price(self) -> Decimal:
        return self.second_anchor.price

    @property
    def lower_bound(self) -> Decimal:
        return min(
            self.first_anchor.price,
            self.second_anchor.price,
        )

    @property
    def upper_bound(self) -> Decimal:
        return max(
            self.first_anchor.price,
            self.second_anchor.price,
        )

    @property
    def size(self) -> Decimal:
        return self.upper_bound - self.lower_bound

    @property
    def equilibrium(self) -> Decimal:
        return (self.lower_bound + self.upper_bound) / Decimal("2")

    @property
    def discount_lower_bound(self) -> Decimal:
        return self.lower_bound

    @property
    def discount_upper_bound(self) -> Decimal:
        return self.equilibrium

    @property
    def premium_lower_bound(self) -> Decimal:
        return self.equilibrium

    @property
    def premium_upper_bound(self) -> Decimal:
        return self.upper_bound

    @property
    def is_bullish(self) -> bool:
        return self.direction == DealingRangeDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == DealingRangeDirection.BEARISH

    @property
    def stable_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.timeframe.value}:"
            f"{self.direction.value}:"
            f"{self.first_index}:"
            f"{self.second_index}"
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

    def classify_price(
        self,
        price: DecimalLike,
    ) -> DealingRangePriceLocation:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        if selected_price < self.lower_bound:
            return DealingRangePriceLocation.BELOW_RANGE

        if selected_price > self.upper_bound:
            return DealingRangePriceLocation.ABOVE_RANGE

        if selected_price < self.equilibrium:
            return DealingRangePriceLocation.DISCOUNT

        if selected_price > self.equilibrium:
            return DealingRangePriceLocation.PREMIUM

        return DealingRangePriceLocation.EQUILIBRIUM

    def normalized_position(
        self,
        price: DecimalLike,
    ) -> Decimal:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        return (selected_price - self.lower_bound) / self.size

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
class DealingRangeSet:
    """Ordered dealing ranges from one confirmed swing set."""

    swings: ConfirmedSwingSet
    policy: DealingRangePolicy
    ranges: tuple[DealingRange, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.swings,
            ConfirmedSwingSet,
        ):
            raise ValueError("swings must be a ConfirmedSwingSet.")

        if not isinstance(
            self.policy,
            DealingRangePolicy,
        ):
            raise ValueError("policy must be a DealingRangePolicy.")

        ranges = tuple(self.ranges)

        for dealing_range in ranges:
            if not isinstance(
                dealing_range,
                DealingRange,
            ):
                raise ValueError("ranges must contain DealingRange instances.")

        direction_order = {
            DealingRangeDirection.BULLISH: 0,
            DealingRangeDirection.BEARISH: 1,
        }

        expected_order = tuple(
            sorted(
                ranges,
                key=lambda dealing_range: (
                    dealing_range.confirmation_index,
                    dealing_range.first_index,
                    direction_order[dealing_range.direction],
                ),
            )
        )

        if ranges != expected_order:
            raise ValueError("Dealing ranges must be ordered by confirmation index.")

        stable_ids: set[str] = set()

        for dealing_range in ranges:
            if (
                dealing_range.first_anchor not in self.swings.points
                or dealing_range.second_anchor not in self.swings.points
            ):
                raise ValueError("Dealing-range anchors must belong to the source swing set.")

            first_position = self.swings.points.index(dealing_range.first_anchor)
            second_position = self.swings.points.index(dealing_range.second_anchor)

            if second_position != first_position + 1:
                raise ValueError("Dealing-range anchors must be consecutive confirmed swings.")

            if dealing_range.anchor_gap > self.policy.maximum_anchor_gap:
                raise ValueError("Dealing-range anchor gap exceeds the configured maximum.")

            if dealing_range.size <= self.policy.minimum_range_size:
                raise ValueError("Dealing range does not strictly exceed the minimum size.")

            if dealing_range.stable_id in stable_ids:
                raise ValueError("Duplicate dealing ranges are not allowed.")

            stable_ids.add(dealing_range.stable_id)

        object.__setattr__(
            self,
            "ranges",
            ranges,
        )

    @property
    def source(self) -> ClosedCandleSeries:
        return self.swings.source

    @property
    def broker_symbol(self) -> str:
        return self.swings.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.swings.timeframe

    @property
    def count(self) -> int:
        return len(self.ranges)

    @property
    def bullish(
        self,
    ) -> tuple[DealingRange, ...]:
        return tuple(
            dealing_range
            for dealing_range in self.ranges
            if (dealing_range.direction == DealingRangeDirection.BULLISH)
        )

    @property
    def bearish(
        self,
    ) -> tuple[DealingRange, ...]:
        return tuple(
            dealing_range
            for dealing_range in self.ranges
            if (dealing_range.direction == DealingRangeDirection.BEARISH)
        )

    @property
    def latest(
        self,
    ) -> DealingRange | None:
        if not self.ranges:
            return None

        return self.ranges[-1]

    @property
    def latest_bullish(
        self,
    ) -> DealingRange | None:
        if not self.bullish:
            return None

        return self.bullish[-1]

    @property
    def latest_bearish(
        self,
    ) -> DealingRange | None:
        if not self.bearish:
            return None

        return self.bearish[-1]

    def by_direction(
        self,
        direction: DealingRangeDirection,
    ) -> tuple[DealingRange, ...]:
        try:
            selected_direction = DealingRangeDirection(direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported dealing-range direction: {direction}.") from error

        if selected_direction == DealingRangeDirection.BULLISH:
            return self.bullish

        return self.bearish

    def confirmed_at_index(
        self,
        index: int,
    ) -> tuple[DealingRange, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(
            dealing_range
            for dealing_range in self.ranges
            if (dealing_range.confirmation_index == selected_index)
        )

    def available_at(
        self,
        index: int,
    ) -> tuple[DealingRange, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(
            dealing_range
            for dealing_range in self.ranges
            if (dealing_range.confirmation_index <= selected_index)
        )

    def containing(
        self,
        price: DecimalLike,
    ) -> tuple[DealingRange, ...]:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        return tuple(
            dealing_range
            for dealing_range in self.ranges
            if dealing_range.contains_price(selected_price)
        )

    def latest_containing(
        self,
        price: DecimalLike,
    ) -> DealingRange | None:
        containing_ranges = self.containing(price)

        if not containing_ranges:
            return None

        return containing_ranges[-1]

    def for_anchor_pair(
        self,
        first_index: int,
        second_index: int,
    ) -> DealingRange | None:
        selected_first_index = _non_negative_integer(
            first_index,
            "first_index",
        )
        selected_second_index = _non_negative_integer(
            second_index,
            "second_index",
        )

        for dealing_range in self.ranges:
            if (
                dealing_range.first_index == selected_first_index
                and dealing_range.second_index == selected_second_index
            ):
                return dealing_range

        return None


class DealingRangeDetector:
    """
    Pure confirmed-swing dealing-range detector.

    Only consecutive opposite confirmed swings create a
    range. The range becomes available when the second swing
    is confirmed.
    """

    def __init__(
        self,
        policy: DealingRangePolicy | None = None,
    ) -> None:
        selected_policy = policy or DealingRangePolicy()

        if not isinstance(
            selected_policy,
            DealingRangePolicy,
        ):
            raise ValueError("policy must be a DealingRangePolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> DealingRangePolicy:
        return self._policy

    def detect(
        self,
        swings: ConfirmedSwingSet,
    ) -> DealingRangeSet:
        if not isinstance(
            swings,
            ConfirmedSwingSet,
        ):
            raise DealingRangeDetectionError(
                DealingRangeDetectionErrorReason.INVALID_SWING_SET,
                "swings must be a ConfirmedSwingSet.",
            )

        ranges: list[DealingRange] = []

        for first_anchor, second_anchor in zip(
            swings.points,
            swings.points[1:],
            strict=False,
        ):
            if first_anchor.kind == second_anchor.kind:
                continue

            anchor_gap = second_anchor.index - first_anchor.index

            if anchor_gap > self._policy.maximum_anchor_gap:
                continue

            direction = _direction_for_anchors(
                first_anchor,
                second_anchor,
            )

            if direction == DealingRangeDirection.BULLISH:
                size = second_anchor.price - first_anchor.price
            else:
                size = first_anchor.price - second_anchor.price

            if size <= self._policy.minimum_range_size:
                continue

            if size <= 0:
                continue

            ranges.append(
                DealingRange(
                    direction=direction,
                    first_anchor=first_anchor,
                    second_anchor=second_anchor,
                )
            )

        return DealingRangeSet(
            swings=swings,
            policy=self._policy,
            ranges=tuple(ranges),
        )

    def evaluate(
        self,
        swings: ConfirmedSwingSet,
    ) -> DealingRangeSet:
        """Compatibility alias for detect()."""

        return self.detect(swings)

    def find(
        self,
        swings: ConfirmedSwingSet,
    ) -> DealingRangeSet:
        """Compatibility alias for detect()."""

        return self.detect(swings)


def detect_dealing_ranges(
    swings: ConfirmedSwingSet,
    policy: DealingRangePolicy | None = None,
) -> DealingRangeSet:
    return DealingRangeDetector(policy=policy).detect(swings)


DealingRangeCollection = DealingRangeSet
DealingRangeFinder = DealingRangeDetector
RangeDirection = DealingRangeDirection
RangeLocation = DealingRangePriceLocation
RangePolicy = DealingRangePolicy
