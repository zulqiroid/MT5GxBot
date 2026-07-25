from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TypeAlias

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandle
from app.strategy.displacement import (
    DisplacementDirection,
    DisplacementImpulse,
    DisplacementSet,
)

DecimalLike: TypeAlias = Decimal | int | float | str


class OrderBlockDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class OrderBlockZoneMode(str, Enum):
    FULL_RANGE = "FULL_RANGE"
    BODY = "BODY"


class OrderBlockDetectionErrorReason(str, Enum):
    INVALID_DISPLACEMENT_SET = "INVALID_DISPLACEMENT_SET"


class OrderBlockDetectionError(RuntimeError):
    """Structured Order Block detection failure."""

    def __init__(
        self,
        reason: OrderBlockDetectionErrorReason,
        message: str,
    ) -> None:
        self.reason = OrderBlockDetectionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Order Block detection error [{self.reason.value}]: {self.message}")


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


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _direction_for_candle(
    candle: ClosedCandle,
) -> OrderBlockDirection | None:
    if candle.close > candle.open:
        return OrderBlockDirection.BULLISH

    if candle.close < candle.open:
        return OrderBlockDirection.BEARISH

    return None


def _direction_for_displacement(
    displacement: DisplacementImpulse,
) -> OrderBlockDirection:
    if displacement.direction == DisplacementDirection.BULLISH:
        return OrderBlockDirection.BULLISH

    return OrderBlockDirection.BEARISH


def _required_source_direction(
    direction: OrderBlockDirection,
) -> OrderBlockDirection:
    if direction == OrderBlockDirection.BULLISH:
        return OrderBlockDirection.BEARISH

    return OrderBlockDirection.BULLISH


def _zone_bounds(
    candle: ClosedCandle,
    mode: OrderBlockZoneMode,
) -> tuple[Decimal, Decimal]:
    if mode == OrderBlockZoneMode.FULL_RANGE:
        return candle.low, candle.high

    return (
        min(candle.open, candle.close),
        max(candle.open, candle.close),
    )


@dataclass(frozen=True, slots=True)
class OrderBlockPolicy:
    """Deterministic displacement-confirmed OB policy."""

    search_back_candles: int = 3
    zone_mode: OrderBlockZoneMode = OrderBlockZoneMode.FULL_RANGE
    minimum_zone_size: Decimal = Decimal("0")
    allow_source_reuse: bool = False

    def __post_init__(self) -> None:
        search_back_candles = _positive_integer(
            self.search_back_candles,
            "search_back_candles",
            100,
        )

        try:
            zone_mode = OrderBlockZoneMode(self.zone_mode)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported Order Block zone mode: {self.zone_mode}.") from error

        minimum_zone_size = _non_negative_decimal(
            self.minimum_zone_size,
            "minimum_zone_size",
        )
        allow_source_reuse = _strict_boolean(
            self.allow_source_reuse,
            "allow_source_reuse",
        )

        object.__setattr__(
            self,
            "search_back_candles",
            search_back_candles,
        )
        object.__setattr__(
            self,
            "zone_mode",
            zone_mode,
        )
        object.__setattr__(
            self,
            "minimum_zone_size",
            minimum_zone_size,
        )
        object.__setattr__(
            self,
            "allow_source_reuse",
            allow_source_reuse,
        )


@dataclass(frozen=True, slots=True)
class OrderBlock:
    """One displacement-confirmed Order Block zone."""

    source_index: int
    direction: OrderBlockDirection
    zone_mode: OrderBlockZoneMode
    source_candle: ClosedCandle
    displacement: DisplacementImpulse

    def __post_init__(self) -> None:
        source_index = _non_negative_integer(
            self.source_index,
            "source_index",
        )

        try:
            direction = OrderBlockDirection(self.direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported Order Block direction: {self.direction}.") from error

        try:
            zone_mode = OrderBlockZoneMode(self.zone_mode)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported Order Block zone mode: {self.zone_mode}.") from error

        if not isinstance(
            self.source_candle,
            ClosedCandle,
        ):
            raise ValueError("source_candle must be a ClosedCandle.")

        if not isinstance(
            self.displacement,
            DisplacementImpulse,
        ):
            raise ValueError("displacement must be a DisplacementImpulse.")

        if self.source_candle.broker_symbol != self.displacement.broker_symbol:
            raise ValueError("Order Block source and displacement must use the same broker symbol.")

        if self.source_candle.timeframe != self.displacement.timeframe:
            raise ValueError("Order Block source and displacement must use the same timeframe.")

        if source_index >= self.displacement.index:
            raise ValueError("Order Block source must precede its displacement candle.")

        expected_direction = _direction_for_displacement(self.displacement)

        if direction != expected_direction:
            raise ValueError("Order Block direction must match the displacement direction.")

        source_direction = _direction_for_candle(self.source_candle)

        if source_direction is None:
            raise ValueError("A doji candle cannot be an Order Block source.")

        if source_direction != _required_source_direction(direction):
            raise ValueError("Order Block source candle must oppose the displacement direction.")

        lower_bound, upper_bound = _zone_bounds(
            self.source_candle,
            zone_mode,
        )

        if upper_bound <= lower_bound:
            raise ValueError("Order Block zone must have positive size.")

        object.__setattr__(
            self,
            "source_index",
            source_index,
        )
        object.__setattr__(
            self,
            "direction",
            direction,
        )
        object.__setattr__(
            self,
            "zone_mode",
            zone_mode,
        )

    @property
    def confirmation_index(self) -> int:
        return self.displacement.index

    @property
    def confirmed_at(self) -> datetime:
        return self.displacement.confirmed_at

    @property
    def broker_symbol(self) -> str:
        return self.source_candle.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.source_candle.timeframe

    @property
    def source_distance(self) -> int:
        return self.confirmation_index - self.source_index

    @property
    def lower_bound(self) -> Decimal:
        return _zone_bounds(
            self.source_candle,
            self.zone_mode,
        )[0]

    @property
    def upper_bound(self) -> Decimal:
        return _zone_bounds(
            self.source_candle,
            self.zone_mode,
        )[1]

    @property
    def size(self) -> Decimal:
        return self.upper_bound - self.lower_bound

    @property
    def midpoint(self) -> Decimal:
        return (self.lower_bound + self.upper_bound) / Decimal("2")

    @property
    def is_bullish(self) -> bool:
        return self.direction == OrderBlockDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == OrderBlockDirection.BEARISH

    @property
    def stable_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.timeframe.value}:"
            f"{self.direction.value}:"
            f"{self.source_index}:"
            f"{self.confirmation_index}:"
            f"{self.zone_mode.value}"
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
class OrderBlockSet:
    """Ordered OB zones from one displacement collection."""

    displacements: DisplacementSet
    policy: OrderBlockPolicy
    blocks: tuple[OrderBlock, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.displacements,
            DisplacementSet,
        ):
            raise ValueError("displacements must be a DisplacementSet.")

        if not isinstance(
            self.policy,
            OrderBlockPolicy,
        ):
            raise ValueError("policy must be an OrderBlockPolicy.")

        blocks = tuple(self.blocks)

        for block in blocks:
            if not isinstance(block, OrderBlock):
                raise ValueError("blocks must contain OrderBlock instances.")

        direction_order = {
            OrderBlockDirection.BULLISH: 0,
            OrderBlockDirection.BEARISH: 1,
        }

        expected_order = tuple(
            sorted(
                blocks,
                key=lambda block: (
                    block.confirmation_index,
                    block.source_index,
                    direction_order[block.direction],
                ),
            )
        )

        if blocks != expected_order:
            raise ValueError("Order Blocks must be ordered by confirmation index.")

        stable_ids: set[str] = set()
        used_source_indexes: set[int] = set()

        for block in blocks:
            if block.displacement not in self.displacements.impulses:
                raise ValueError("Order Block displacement does not belong to the source set.")

            if block.source_index >= self.displacements.source.count:
                raise ValueError("Order Block source index exceeds source history.")

            if block.source_candle != self.displacements.source.candles[block.source_index]:
                raise ValueError("Order Block source candle does not match source history.")

            if block.zone_mode != self.policy.zone_mode:
                raise ValueError("Order Block zone mode does not match the configured policy.")

            if block.source_distance > self.policy.search_back_candles:
                raise ValueError("Order Block source exceeds the configured search window.")

            if block.size <= self.policy.minimum_zone_size:
                raise ValueError("Order Block zone does not strictly exceed the minimum size.")

            nearest_source = self._nearest_opposite_source(block.displacement)

            if nearest_source != block.source_index:
                raise ValueError("Order Block source is not the nearest opposite candle.")

            if block.stable_id in stable_ids:
                raise ValueError("Duplicate Order Blocks are not allowed.")

            if not self.policy.allow_source_reuse and block.source_index in used_source_indexes:
                raise ValueError("Order Block source reuse is disabled.")

            stable_ids.add(block.stable_id)
            used_source_indexes.add(block.source_index)

        object.__setattr__(
            self,
            "blocks",
            blocks,
        )

    def _nearest_opposite_source(
        self,
        displacement: DisplacementImpulse,
    ) -> int | None:
        direction = _direction_for_displacement(displacement)
        required_direction = _required_source_direction(direction)
        first_index = max(
            0,
            displacement.index - self.policy.search_back_candles,
        )

        for index in range(
            displacement.index - 1,
            first_index - 1,
            -1,
        ):
            candle = self.displacements.source.candles[index]

            if _direction_for_candle(candle) == required_direction:
                return index

        return None

    @property
    def source(self):
        return self.displacements.source

    @property
    def broker_symbol(self) -> str:
        return self.displacements.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.displacements.timeframe

    @property
    def count(self) -> int:
        return len(self.blocks)

    @property
    def bullish(
        self,
    ) -> tuple[OrderBlock, ...]:
        return tuple(
            block for block in self.blocks if block.direction == OrderBlockDirection.BULLISH
        )

    @property
    def bearish(
        self,
    ) -> tuple[OrderBlock, ...]:
        return tuple(
            block for block in self.blocks if block.direction == OrderBlockDirection.BEARISH
        )

    @property
    def latest(
        self,
    ) -> OrderBlock | None:
        if not self.blocks:
            return None

        return self.blocks[-1]

    @property
    def latest_bullish(
        self,
    ) -> OrderBlock | None:
        if not self.bullish:
            return None

        return self.bullish[-1]

    @property
    def latest_bearish(
        self,
    ) -> OrderBlock | None:
        if not self.bearish:
            return None

        return self.bearish[-1]

    def by_direction(
        self,
        direction: OrderBlockDirection,
    ) -> tuple[OrderBlock, ...]:
        try:
            selected_direction = OrderBlockDirection(direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported Order Block direction: {direction}.") from error

        if selected_direction == OrderBlockDirection.BULLISH:
            return self.bullish

        return self.bearish

    def confirmed_at_index(
        self,
        index: int,
    ) -> tuple[OrderBlock, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(block for block in self.blocks if block.confirmation_index == selected_index)

    def nearest_bullish_below(
        self,
        price: DecimalLike,
    ) -> OrderBlock | None:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        candidates = tuple(block for block in self.bullish if block.upper_bound <= selected_price)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda block: (
                selected_price - block.upper_bound,
                -block.confirmation_index,
            ),
        )

    def nearest_bearish_above(
        self,
        price: DecimalLike,
    ) -> OrderBlock | None:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        candidates = tuple(block for block in self.bearish if block.lower_bound >= selected_price)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda block: (
                block.lower_bound - selected_price,
                -block.confirmation_index,
            ),
        )


class OrderBlockDetector:
    """
    Pure displacement-confirmed Order Block detector.

    The nearest opposite candle inside the configured search
    window becomes the candidate OB source.
    """

    def __init__(
        self,
        policy: OrderBlockPolicy | None = None,
    ) -> None:
        selected_policy = policy or OrderBlockPolicy()

        if not isinstance(
            selected_policy,
            OrderBlockPolicy,
        ):
            raise ValueError("policy must be an OrderBlockPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> OrderBlockPolicy:
        return self._policy

    def detect(
        self,
        displacements: DisplacementSet,
    ) -> OrderBlockSet:
        if not isinstance(
            displacements,
            DisplacementSet,
        ):
            raise OrderBlockDetectionError(
                OrderBlockDetectionErrorReason.INVALID_DISPLACEMENT_SET,
                "displacements must be a DisplacementSet.",
            )

        blocks: list[OrderBlock] = []
        used_source_indexes: set[int] = set()

        for displacement in displacements.impulses:
            source_index = self._find_source_index(
                displacements,
                displacement,
            )

            if source_index is None:
                continue

            if not self._policy.allow_source_reuse and source_index in used_source_indexes:
                continue

            source_candle = displacements.source.candles[source_index]
            direction = _direction_for_displacement(displacement)
            lower_bound, upper_bound = _zone_bounds(
                source_candle,
                self._policy.zone_mode,
            )

            if upper_bound - lower_bound <= self._policy.minimum_zone_size:
                continue

            block = OrderBlock(
                source_index=source_index,
                direction=direction,
                zone_mode=self._policy.zone_mode,
                source_candle=source_candle,
                displacement=displacement,
            )
            blocks.append(block)
            used_source_indexes.add(source_index)

        return OrderBlockSet(
            displacements=displacements,
            policy=self._policy,
            blocks=tuple(blocks),
        )

    def evaluate(
        self,
        displacements: DisplacementSet,
    ) -> OrderBlockSet:
        """Compatibility alias for detect()."""

        return self.detect(displacements)

    def find(
        self,
        displacements: DisplacementSet,
    ) -> OrderBlockSet:
        """Compatibility alias for detect()."""

        return self.detect(displacements)

    def _find_source_index(
        self,
        displacements: DisplacementSet,
        displacement: DisplacementImpulse,
    ) -> int | None:
        direction = _direction_for_displacement(displacement)
        required_direction = _required_source_direction(direction)
        first_index = max(
            0,
            displacement.index - self._policy.search_back_candles,
        )

        for index in range(
            displacement.index - 1,
            first_index - 1,
            -1,
        ):
            candle = displacements.source.candles[index]

            if _direction_for_candle(candle) == required_direction:
                return index

        return None


def detect_order_blocks(
    displacements: DisplacementSet,
    policy: OrderBlockPolicy | None = None,
) -> OrderBlockSet:
    return OrderBlockDetector(policy=policy).detect(displacements)


OrderBlockCollection = OrderBlockSet
OrderBlockFinder = OrderBlockDetector
OrderBlockMode = OrderBlockZoneMode
OB = OrderBlock
OBDirection = OrderBlockDirection
OBDetector = OrderBlockDetector
OBPolicy = OrderBlockPolicy
OBSet = OrderBlockSet
