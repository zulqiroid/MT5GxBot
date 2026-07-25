from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TypeAlias

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandleSeries
from app.strategy.dealing_ranges import (
    DealingRange,
    DealingRangeDirection,
    DealingRangePriceLocation,
    DealingRangeSet,
)

DecimalLike: TypeAlias = Decimal | int | float | str


class OptimalTradeEntryPriceLocation(str, Enum):
    BELOW_ZONE = "BELOW_ZONE"
    IN_ZONE = "IN_ZONE"
    ABOVE_ZONE = "ABOVE_ZONE"


class OptimalTradeEntryDetectionErrorReason(str, Enum):
    INVALID_DEALING_RANGE_SET = "INVALID_DEALING_RANGE_SET"


class OptimalTradeEntryDetectionError(RuntimeError):
    """Structured OTE-zone detection failure."""

    def __init__(
        self,
        reason: OptimalTradeEntryDetectionErrorReason,
        message: str,
    ) -> None:
        self.reason = OptimalTradeEntryDetectionErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Optimal Trade Entry detection error [{self.reason.value}]: {self.message}"
        )


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


def _decimal_value(
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

    return decimal_value


def _ratio_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    ratio = _decimal_value(
        value,
        field_name,
    )

    if ratio < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    if ratio > Decimal("1"):
        raise ValueError(f"{field_name} cannot exceed one.")

    return ratio


def _positive_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    decimal_value = _decimal_value(
        value,
        field_name,
    )

    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return decimal_value


def _validate_retracement_band(
    shallow_retracement: object,
    deep_retracement: object,
) -> tuple[Decimal, Decimal]:
    shallow = _ratio_decimal(
        shallow_retracement,
        "shallow_retracement",
    )
    deep = _ratio_decimal(
        deep_retracement,
        "deep_retracement",
    )

    if shallow < Decimal("0.50"):
        raise ValueError("shallow_retracement must be at least 50 percent.")

    if deep <= shallow:
        raise ValueError("deep_retracement must be strictly greater than shallow_retracement.")

    return shallow, deep


def _retracement_price(
    dealing_range: DealingRange,
    retracement: Decimal,
) -> Decimal:
    retracement_distance = dealing_range.size * retracement

    if dealing_range.direction == DealingRangeDirection.BULLISH:
        return dealing_range.terminal_price - retracement_distance

    return dealing_range.terminal_price + retracement_distance


@dataclass(frozen=True, slots=True)
class OptimalTradeEntryPolicy:
    """Deterministic confirmed-range OTE policy."""

    shallow_retracement: Decimal = Decimal("0.62")
    deep_retracement: Decimal = Decimal("0.79")

    def __post_init__(self) -> None:
        shallow_retracement, deep_retracement = _validate_retracement_band(
            self.shallow_retracement,
            self.deep_retracement,
        )

        object.__setattr__(
            self,
            "shallow_retracement",
            shallow_retracement,
        )
        object.__setattr__(
            self,
            "deep_retracement",
            deep_retracement,
        )

    @property
    def retracement_span(self) -> Decimal:
        return self.deep_retracement - self.shallow_retracement


@dataclass(frozen=True, slots=True)
class OptimalTradeEntryZone:
    """One confirmed OTE zone derived from a dealing range."""

    dealing_range: DealingRange
    shallow_retracement: Decimal
    deep_retracement: Decimal

    def __post_init__(self) -> None:
        if not isinstance(
            self.dealing_range,
            DealingRange,
        ):
            raise ValueError("dealing_range must be a DealingRange.")

        shallow_retracement, deep_retracement = _validate_retracement_band(
            self.shallow_retracement,
            self.deep_retracement,
        )

        object.__setattr__(
            self,
            "shallow_retracement",
            shallow_retracement,
        )
        object.__setattr__(
            self,
            "deep_retracement",
            deep_retracement,
        )

    @property
    def direction(self) -> DealingRangeDirection:
        return self.dealing_range.direction

    @property
    def broker_symbol(self) -> str:
        return self.dealing_range.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.dealing_range.timeframe

    @property
    def confirmation_index(self) -> int:
        return self.dealing_range.confirmation_index

    @property
    def confirmed_at(self) -> datetime:
        return self.dealing_range.confirmed_at

    @property
    def shallow_price(self) -> Decimal:
        return _retracement_price(
            self.dealing_range,
            self.shallow_retracement,
        )

    @property
    def deep_price(self) -> Decimal:
        return _retracement_price(
            self.dealing_range,
            self.deep_retracement,
        )

    @property
    def lower_bound(self) -> Decimal:
        return min(
            self.shallow_price,
            self.deep_price,
        )

    @property
    def upper_bound(self) -> Decimal:
        return max(
            self.shallow_price,
            self.deep_price,
        )

    @property
    def size(self) -> Decimal:
        return self.upper_bound - self.lower_bound

    @property
    def midpoint(self) -> Decimal:
        return (self.lower_bound + self.upper_bound) / Decimal("2")

    @property
    def entry_price(self) -> Decimal:
        return self.midpoint

    @property
    def midpoint_retracement(self) -> Decimal:
        return (self.shallow_retracement + self.deep_retracement) / Decimal("2")

    @property
    def dealing_range_location(
        self,
    ) -> DealingRangePriceLocation:
        return self.dealing_range.classify_price(self.midpoint)

    @property
    def is_bullish(self) -> bool:
        return self.direction == DealingRangeDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == DealingRangeDirection.BEARISH

    @property
    def stable_id(self) -> str:
        return (
            f"{self.dealing_range.stable_id}:OTE:{self.shallow_retracement}:{self.deep_retracement}"
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
    ) -> OptimalTradeEntryPriceLocation:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        if selected_price < self.lower_bound:
            return OptimalTradeEntryPriceLocation.BELOW_ZONE

        if selected_price > self.upper_bound:
            return OptimalTradeEntryPriceLocation.ABOVE_ZONE

        return OptimalTradeEntryPriceLocation.IN_ZONE

    def retracement_for_price(
        self,
        price: DecimalLike,
    ) -> Decimal:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        if self.is_bullish:
            return (self.dealing_range.terminal_price - selected_price) / self.dealing_range.size

        return (selected_price - self.dealing_range.terminal_price) / self.dealing_range.size

    def normalized_zone_position(
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
class OptimalTradeEntryZoneSet:
    """Ordered OTE zones for one dealing-range collection."""

    dealing_ranges: DealingRangeSet
    policy: OptimalTradeEntryPolicy
    zones: tuple[OptimalTradeEntryZone, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.dealing_ranges,
            DealingRangeSet,
        ):
            raise ValueError("dealing_ranges must be a DealingRangeSet.")

        if not isinstance(
            self.policy,
            OptimalTradeEntryPolicy,
        ):
            raise ValueError("policy must be an OptimalTradeEntryPolicy.")

        zones = tuple(self.zones)

        for zone in zones:
            if not isinstance(
                zone,
                OptimalTradeEntryZone,
            ):
                raise ValueError("zones must contain OptimalTradeEntryZone instances.")

        direction_order = {
            DealingRangeDirection.BULLISH: 0,
            DealingRangeDirection.BEARISH: 1,
        }

        expected_order = tuple(
            sorted(
                zones,
                key=lambda zone: (
                    zone.confirmation_index,
                    zone.dealing_range.first_index,
                    direction_order[zone.direction],
                ),
            )
        )

        if zones != expected_order:
            raise ValueError("Optimal Trade Entry zones must be ordered by confirmation index.")

        stable_ids: set[str] = set()
        covered_range_ids: set[str] = set()

        for zone in zones:
            if zone.dealing_range not in self.dealing_ranges.ranges:
                raise ValueError(
                    "OTE zone dealing range does not belong to the source dealing-range set."
                )

            if (
                zone.shallow_retracement != self.policy.shallow_retracement
                or zone.deep_retracement != self.policy.deep_retracement
            ):
                raise ValueError("OTE zone retracements do not match the configured policy.")

            if zone.size <= 0:
                raise ValueError("OTE zone must have positive size.")

            if zone.is_bullish and (
                zone.dealing_range_location != DealingRangePriceLocation.DISCOUNT
            ):
                raise ValueError("Bullish OTE zone must remain in dealing-range discount.")

            if zone.is_bearish and (
                zone.dealing_range_location != DealingRangePriceLocation.PREMIUM
            ):
                raise ValueError("Bearish OTE zone must remain in dealing-range premium.")

            if zone.stable_id in stable_ids:
                raise ValueError("Duplicate Optimal Trade Entry zones are not allowed.")

            stable_ids.add(zone.stable_id)
            covered_range_ids.add(zone.dealing_range.stable_id)

        expected_range_ids = {
            dealing_range.stable_id for dealing_range in self.dealing_ranges.ranges
        }

        if covered_range_ids != expected_range_ids:
            raise ValueError("Every confirmed dealing range must have exactly one OTE zone.")

        object.__setattr__(
            self,
            "zones",
            zones,
        )

    @property
    def source(self) -> ClosedCandleSeries:
        return self.dealing_ranges.source

    @property
    def broker_symbol(self) -> str:
        return self.dealing_ranges.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.dealing_ranges.timeframe

    @property
    def count(self) -> int:
        return len(self.zones)

    @property
    def bullish(
        self,
    ) -> tuple[OptimalTradeEntryZone, ...]:
        return tuple(zone for zone in self.zones if zone.direction == DealingRangeDirection.BULLISH)

    @property
    def bearish(
        self,
    ) -> tuple[OptimalTradeEntryZone, ...]:
        return tuple(zone for zone in self.zones if zone.direction == DealingRangeDirection.BEARISH)

    @property
    def latest(
        self,
    ) -> OptimalTradeEntryZone | None:
        if not self.zones:
            return None

        return self.zones[-1]

    @property
    def latest_bullish(
        self,
    ) -> OptimalTradeEntryZone | None:
        if not self.bullish:
            return None

        return self.bullish[-1]

    @property
    def latest_bearish(
        self,
    ) -> OptimalTradeEntryZone | None:
        if not self.bearish:
            return None

        return self.bearish[-1]

    def by_direction(
        self,
        direction: DealingRangeDirection,
    ) -> tuple[OptimalTradeEntryZone, ...]:
        try:
            selected_direction = DealingRangeDirection(direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported OTE direction: {direction}.") from error

        if selected_direction == DealingRangeDirection.BULLISH:
            return self.bullish

        return self.bearish

    def confirmed_at_index(
        self,
        index: int,
    ) -> tuple[OptimalTradeEntryZone, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(zone for zone in self.zones if zone.confirmation_index == selected_index)

    def available_at(
        self,
        index: int,
    ) -> tuple[OptimalTradeEntryZone, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(zone for zone in self.zones if zone.confirmation_index <= selected_index)

    def containing(
        self,
        price: DecimalLike,
    ) -> tuple[OptimalTradeEntryZone, ...]:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        return tuple(zone for zone in self.zones if zone.contains_price(selected_price))

    def latest_containing(
        self,
        price: DecimalLike,
    ) -> OptimalTradeEntryZone | None:
        containing_zones = self.containing(price)

        if not containing_zones:
            return None

        return containing_zones[-1]

    def for_dealing_range(
        self,
        dealing_range: DealingRange,
    ) -> OptimalTradeEntryZone | None:
        if not isinstance(
            dealing_range,
            DealingRange,
        ):
            raise ValueError("dealing_range must be a DealingRange.")

        for zone in self.zones:
            if zone.dealing_range == dealing_range:
                return zone

        return None

    def nearest_bullish_below(
        self,
        price: DecimalLike,
    ) -> OptimalTradeEntryZone | None:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        candidates = tuple(zone for zone in self.bullish if zone.upper_bound <= selected_price)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda zone: (
                selected_price - zone.upper_bound,
                -zone.confirmation_index,
            ),
        )

    def nearest_bearish_above(
        self,
        price: DecimalLike,
    ) -> OptimalTradeEntryZone | None:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        candidates = tuple(zone for zone in self.bearish if zone.lower_bound >= selected_price)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda zone: (
                zone.lower_bound - selected_price,
                -zone.confirmation_index,
            ),
        )


class OptimalTradeEntryDetector:
    """
    Pure confirmed dealing-range OTE detector.

    Retracement is measured from the terminal anchor back
    toward the origin anchor.
    """

    def __init__(
        self,
        policy: OptimalTradeEntryPolicy | None = None,
    ) -> None:
        selected_policy = policy or OptimalTradeEntryPolicy()

        if not isinstance(
            selected_policy,
            OptimalTradeEntryPolicy,
        ):
            raise ValueError("policy must be an OptimalTradeEntryPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> OptimalTradeEntryPolicy:
        return self._policy

    def detect(
        self,
        dealing_ranges: DealingRangeSet,
    ) -> OptimalTradeEntryZoneSet:
        if not isinstance(
            dealing_ranges,
            DealingRangeSet,
        ):
            raise OptimalTradeEntryDetectionError(
                OptimalTradeEntryDetectionErrorReason.INVALID_DEALING_RANGE_SET,
                "dealing_ranges must be a DealingRangeSet.",
            )

        zones = tuple(
            OptimalTradeEntryZone(
                dealing_range=dealing_range,
                shallow_retracement=(self._policy.shallow_retracement),
                deep_retracement=(self._policy.deep_retracement),
            )
            for dealing_range in dealing_ranges.ranges
        )

        return OptimalTradeEntryZoneSet(
            dealing_ranges=dealing_ranges,
            policy=self._policy,
            zones=zones,
        )

    def evaluate(
        self,
        dealing_ranges: DealingRangeSet,
    ) -> OptimalTradeEntryZoneSet:
        """Compatibility alias for detect()."""

        return self.detect(dealing_ranges)

    def find(
        self,
        dealing_ranges: DealingRangeSet,
    ) -> OptimalTradeEntryZoneSet:
        """Compatibility alias for detect()."""

        return self.detect(dealing_ranges)


def detect_optimal_trade_entry_zones(
    dealing_ranges: DealingRangeSet,
    policy: OptimalTradeEntryPolicy | None = None,
) -> OptimalTradeEntryZoneSet:
    return OptimalTradeEntryDetector(policy=policy).detect(dealing_ranges)


OTE = OptimalTradeEntryZone
OTECollection = OptimalTradeEntryZoneSet
OTEDetector = OptimalTradeEntryDetector
OTEDirection = DealingRangeDirection
OTELocation = OptimalTradeEntryPriceLocation
OTEPolicy = OptimalTradeEntryPolicy
OTESet = OptimalTradeEntryZoneSet
OTEZone = OptimalTradeEntryZone
OptimalTradeEntryCollection = OptimalTradeEntryZoneSet
