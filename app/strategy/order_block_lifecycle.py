from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandle
from app.strategy.order_blocks import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockSet,
)


class OrderBlockLifecycleState(str, Enum):
    UNTOUCHED = "UNTOUCHED"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
    FULLY_MITIGATED = "FULLY_MITIGATED"
    INVALIDATED = "INVALIDATED"
    BREAKER_CONFIRMED = "BREAKER_CONFIRMED"


class OrderBlockLifecycleEventKind(str, Enum):
    MITIGATION = "MITIGATION"
    INVALIDATION = "INVALIDATION"
    BREAKER = "BREAKER"


class OrderBlockLifecycleErrorReason(str, Enum):
    INVALID_ORDER_BLOCK_SET = "INVALID_ORDER_BLOCK_SET"


class OrderBlockLifecycleError(RuntimeError):
    """Structured Order Block lifecycle tracking failure."""

    def __init__(
        self,
        reason: OrderBlockLifecycleErrorReason,
        message: str,
    ) -> None:
        self.reason = OrderBlockLifecycleErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Order Block lifecycle error [{self.reason.value}]: {self.message}")


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


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _opposite_direction(
    direction: OrderBlockDirection,
) -> OrderBlockDirection:
    if direction == OrderBlockDirection.BULLISH:
        return OrderBlockDirection.BEARISH

    return OrderBlockDirection.BULLISH


def _is_invalidated(
    block: OrderBlock,
    candle: ClosedCandle,
) -> bool:
    if block.direction == OrderBlockDirection.BULLISH:
        return candle.close < block.lower_bound

    return candle.close > block.upper_bound


def _invalidation_distance(
    block: OrderBlock,
    candle: ClosedCandle,
) -> Decimal:
    if block.direction == OrderBlockDirection.BULLISH:
        return max(
            block.lower_bound - candle.close,
            Decimal("0"),
        )

    return max(
        candle.close - block.upper_bound,
        Decimal("0"),
    )


def _raw_mitigation_penetration(
    block: OrderBlock,
    candle: ClosedCandle,
) -> Decimal:
    if block.direction == OrderBlockDirection.BULLISH:
        penetration = block.upper_bound - candle.low
    else:
        penetration = candle.high - block.lower_bound

    return max(
        penetration,
        Decimal("0"),
    )


def _zone_mitigation_penetration(
    block: OrderBlock,
    candle: ClosedCandle,
) -> Decimal:
    return min(
        _raw_mitigation_penetration(
            block,
            candle,
        ),
        block.size,
    )


def _mitigation_state_reached(
    block: OrderBlock,
    candle: ClosedCandle,
) -> OrderBlockLifecycleState:
    if block.direction == OrderBlockDirection.BULLISH:
        if candle.low >= block.upper_bound:
            return OrderBlockLifecycleState.UNTOUCHED

        if candle.low <= block.lower_bound:
            return OrderBlockLifecycleState.FULLY_MITIGATED

        return OrderBlockLifecycleState.PARTIALLY_MITIGATED

    if candle.high <= block.lower_bound:
        return OrderBlockLifecycleState.UNTOUCHED

    if candle.high >= block.upper_bound:
        return OrderBlockLifecycleState.FULLY_MITIGATED

    return OrderBlockLifecycleState.PARTIALLY_MITIGATED


def _raw_breaker_penetration(
    block: OrderBlock,
    candle: ClosedCandle,
) -> Decimal:
    if block.direction == OrderBlockDirection.BULLISH:
        penetration = candle.high - block.lower_bound
    else:
        penetration = block.upper_bound - candle.low

    return max(
        penetration,
        Decimal("0"),
    )


def _breaker_close_rejected(
    block: OrderBlock,
    candle: ClosedCandle,
) -> bool:
    if block.direction == OrderBlockDirection.BULLISH:
        return candle.close <= block.lower_bound

    return candle.close >= block.upper_bound


@dataclass(frozen=True, slots=True)
class OrderBlockLifecyclePolicy:
    """Strict closed-candle OB lifecycle policy."""

    minimum_mitigation_penetration: Decimal = Decimal("0")
    minimum_breaker_penetration: Decimal = Decimal("0")
    require_breaker_close_rejection: bool = True

    def __post_init__(self) -> None:
        minimum_mitigation_penetration = _non_negative_decimal(
            self.minimum_mitigation_penetration,
            "minimum_mitigation_penetration",
        )
        minimum_breaker_penetration = _non_negative_decimal(
            self.minimum_breaker_penetration,
            "minimum_breaker_penetration",
        )
        require_breaker_close_rejection = _strict_boolean(
            self.require_breaker_close_rejection,
            "require_breaker_close_rejection",
        )

        object.__setattr__(
            self,
            "minimum_mitigation_penetration",
            minimum_mitigation_penetration,
        )
        object.__setattr__(
            self,
            "minimum_breaker_penetration",
            minimum_breaker_penetration,
        )
        object.__setattr__(
            self,
            "require_breaker_close_rejection",
            require_breaker_close_rejection,
        )


@dataclass(frozen=True, slots=True)
class OrderBlockLifecycleEvent:
    """One closed-candle OB lifecycle transition."""

    index: int
    kind: OrderBlockLifecycleEventKind
    block: OrderBlock
    candle: ClosedCandle
    previous_state: OrderBlockLifecycleState
    new_state: OrderBlockLifecycleState

    def __post_init__(self) -> None:
        index = _non_negative_integer(
            self.index,
            "index",
        )

        try:
            kind = OrderBlockLifecycleEventKind(self.kind)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Unsupported Order Block lifecycle event kind: {self.kind}."
            ) from error

        try:
            previous_state = OrderBlockLifecycleState(self.previous_state)
            new_state = OrderBlockLifecycleState(self.new_state)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported Order Block lifecycle state.") from error

        if not isinstance(self.block, OrderBlock):
            raise ValueError("block must be an OrderBlock.")

        if not isinstance(self.candle, ClosedCandle):
            raise ValueError("candle must be a ClosedCandle.")

        if index <= self.block.confirmation_index:
            raise ValueError(
                "Order Block lifecycle events can occur only after the confirmation candle."
            )

        if self.candle.broker_symbol != self.block.broker_symbol:
            raise ValueError("Lifecycle candle and Order Block symbol must match.")

        if self.candle.timeframe != self.block.timeframe:
            raise ValueError("Lifecycle candle and Order Block timeframe must match.")

        if kind == OrderBlockLifecycleEventKind.MITIGATION:
            if previous_state not in {
                OrderBlockLifecycleState.UNTOUCHED,
                OrderBlockLifecycleState.PARTIALLY_MITIGATED,
            }:
                raise ValueError("Mitigation cannot follow the supplied previous lifecycle state.")

            if _is_invalidated(self.block, self.candle):
                raise ValueError("An invalidating candle cannot be recorded as mitigation.")

            reached_state = _mitigation_state_reached(
                self.block,
                self.candle,
            )

            if reached_state not in {
                OrderBlockLifecycleState.PARTIALLY_MITIGATED,
                OrderBlockLifecycleState.FULLY_MITIGATED,
            }:
                raise ValueError("Mitigation candle must penetrate the Order Block.")

            if new_state != reached_state:
                raise ValueError("new_state must match the deepest mitigation state reached.")

        elif kind == OrderBlockLifecycleEventKind.INVALIDATION:
            if previous_state in {
                OrderBlockLifecycleState.INVALIDATED,
                OrderBlockLifecycleState.BREAKER_CONFIRMED,
            }:
                raise ValueError(
                    "Invalidation cannot follow the supplied previous lifecycle state."
                )

            if new_state != OrderBlockLifecycleState.INVALIDATED:
                raise ValueError("Invalidation must transition to INVALIDATED.")

            if not _is_invalidated(
                self.block,
                self.candle,
            ):
                raise ValueError(
                    "Invalidation candle must close beyond the distal Order Block boundary."
                )

        else:
            if previous_state != OrderBlockLifecycleState.INVALIDATED:
                raise ValueError("Breaker confirmation requires an invalidated Order Block.")

            if new_state != OrderBlockLifecycleState.BREAKER_CONFIRMED:
                raise ValueError("Breaker event must transition to BREAKER_CONFIRMED.")

            if (
                _raw_breaker_penetration(
                    self.block,
                    self.candle,
                )
                <= 0
            ):
                raise ValueError(
                    "Breaker candle must penetrate the invalidated Order Block boundary."
                )

        object.__setattr__(self, "index", index)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "previous_state",
            previous_state,
        )
        object.__setattr__(
            self,
            "new_state",
            new_state,
        )

    @property
    def broker_symbol(self) -> str:
        return self.candle.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.candle.timeframe

    @property
    def confirmed_at(self) -> datetime:
        return self.candle.close_time

    @property
    def raw_mitigation_penetration(self) -> Decimal:
        return _raw_mitigation_penetration(
            self.block,
            self.candle,
        )

    @property
    def zone_mitigation_penetration(
        self,
    ) -> Decimal:
        return _zone_mitigation_penetration(
            self.block,
            self.candle,
        )

    @property
    def mitigation_fraction(self) -> Decimal:
        return self.zone_mitigation_penetration / self.block.size

    @property
    def mitigation_percentage(self) -> Decimal:
        return self.mitigation_fraction * Decimal("100")

    @property
    def invalidation_distance(self) -> Decimal:
        return _invalidation_distance(
            self.block,
            self.candle,
        )

    @property
    def breaker_penetration(self) -> Decimal:
        return _raw_breaker_penetration(
            self.block,
            self.candle,
        )

    @property
    def breaker_close_rejected(self) -> bool:
        return _breaker_close_rejected(
            self.block,
            self.candle,
        )

    @property
    def breaker_direction(
        self,
    ) -> OrderBlockDirection | None:
        if self.kind != OrderBlockLifecycleEventKind.BREAKER:
            return None

        return _opposite_direction(self.block.direction)

    @property
    def is_mitigation(self) -> bool:
        return self.kind == OrderBlockLifecycleEventKind.MITIGATION

    @property
    def is_invalidation(self) -> bool:
        return self.kind == OrderBlockLifecycleEventKind.INVALIDATION

    @property
    def is_breaker(self) -> bool:
        return self.kind == OrderBlockLifecycleEventKind.BREAKER

    @property
    def is_progress_only(self) -> bool:
        return self.previous_state == self.new_state

    @property
    def stable_id(self) -> str:
        return f"{self.block.stable_id}:{self.kind.value}:{self.index}:{self.new_state.value}"


@dataclass(frozen=True, slots=True)
class OrderBlockLifecycleSnapshot:
    """Ordered lifecycle history for one Order Block set."""

    order_blocks: OrderBlockSet
    policy: OrderBlockLifecyclePolicy
    events: tuple[OrderBlockLifecycleEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.order_blocks,
            OrderBlockSet,
        ):
            raise ValueError("order_blocks must be an OrderBlockSet.")

        if not isinstance(
            self.policy,
            OrderBlockLifecyclePolicy,
        ):
            raise ValueError("policy must be an OrderBlockLifecyclePolicy.")

        events = tuple(self.events)

        for event in events:
            if not isinstance(
                event,
                OrderBlockLifecycleEvent,
            ):
                raise ValueError("events must contain OrderBlockLifecycleEvent instances.")

        expected_order = tuple(
            sorted(
                events,
                key=lambda event: (
                    event.index,
                    event.block.confirmation_index,
                    event.block.stable_id,
                    event.kind.value,
                ),
            )
        )

        if events != expected_order:
            raise ValueError("Order Block lifecycle events must be ordered deterministically.")

        states = {
            block.stable_id: (OrderBlockLifecycleState.UNTOUCHED)
            for block in self.order_blocks.blocks
        }
        deepest_penetrations = {block.stable_id: Decimal("0") for block in self.order_blocks.blocks}
        event_keys: set[tuple[str, int]] = set()

        for event in events:
            if event.block not in self.order_blocks.blocks:
                raise ValueError("Lifecycle Order Block does not belong to the source set.")

            if event.index >= self.order_blocks.source.count:
                raise ValueError("Lifecycle event index exceeds source history.")

            if event.candle != self.order_blocks.source.candles[event.index]:
                raise ValueError("Lifecycle candle does not match source history.")

            event_key = (
                event.block.stable_id,
                event.index,
            )

            if event_key in event_keys:
                raise ValueError("An Order Block cannot produce multiple events on one candle.")

            block_id = event.block.stable_id
            current_state = states[block_id]

            if event.previous_state != current_state:
                raise ValueError("Order Block lifecycle state chain is invalid.")

            if current_state == OrderBlockLifecycleState.BREAKER_CONFIRMED:
                raise ValueError("A confirmed breaker cannot produce additional lifecycle events.")

            if event.is_mitigation:
                penetration = event.raw_mitigation_penetration

                if penetration <= self.policy.minimum_mitigation_penetration:
                    raise ValueError(
                        "Mitigation does not exceed the minimum penetration threshold."
                    )

                zone_penetration = event.zone_mitigation_penetration

                if zone_penetration <= deepest_penetrations[block_id]:
                    raise ValueError("Mitigation must establish a new deepest zone penetration.")

                deepest_penetrations[block_id] = zone_penetration

            elif event.is_invalidation:
                if event.invalidation_distance <= 0:
                    raise ValueError("Invalidation must close beyond the distal boundary.")

            else:
                penetration = event.breaker_penetration

                if penetration <= self.policy.minimum_breaker_penetration:
                    raise ValueError(
                        "Breaker retest does not exceed the minimum penetration threshold."
                    )

                if self.policy.require_breaker_close_rejection and not event.breaker_close_rejected:
                    raise ValueError(
                        "Breaker retest did not close back beyond the invalidation boundary."
                    )

            states[block_id] = event.new_state
            event_keys.add(event_key)

        object.__setattr__(
            self,
            "events",
            events,
        )

    @property
    def broker_symbol(self) -> str:
        return self.order_blocks.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.order_blocks.timeframe

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def latest(
        self,
    ) -> OrderBlockLifecycleEvent | None:
        if not self.events:
            return None

        return self.events[-1]

    def _require_block(
        self,
        block: OrderBlock,
    ) -> None:
        if not isinstance(block, OrderBlock):
            raise ValueError("block must be an OrderBlock.")

        if block not in self.order_blocks.blocks:
            raise ValueError("block does not belong to this lifecycle snapshot.")

    def events_for_block(
        self,
        block: OrderBlock,
    ) -> tuple[OrderBlockLifecycleEvent, ...]:
        self._require_block(block)

        return tuple(event for event in self.events if event.block == block)

    def events_at(
        self,
        index: int,
    ) -> tuple[OrderBlockLifecycleEvent, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(event for event in self.events if event.index == selected_index)

    def latest_event_for(
        self,
        block: OrderBlock,
    ) -> OrderBlockLifecycleEvent | None:
        block_events = self.events_for_block(block)

        if not block_events:
            return None

        return block_events[-1]

    def first_mitigation_event(
        self,
        block: OrderBlock,
    ) -> OrderBlockLifecycleEvent | None:
        for event in self.events_for_block(block):
            if event.is_mitigation:
                return event

        return None

    def invalidation_event(
        self,
        block: OrderBlock,
    ) -> OrderBlockLifecycleEvent | None:
        for event in self.events_for_block(block):
            if event.is_invalidation:
                return event

        return None

    def breaker_event(
        self,
        block: OrderBlock,
    ) -> OrderBlockLifecycleEvent | None:
        for event in self.events_for_block(block):
            if event.is_breaker:
                return event

        return None

    def state_for(
        self,
        block: OrderBlock,
    ) -> OrderBlockLifecycleState:
        latest_event = self.latest_event_for(block)

        if latest_event is None:
            return OrderBlockLifecycleState.UNTOUCHED

        return latest_event.new_state

    def mitigation_fraction_for(
        self,
        block: OrderBlock,
    ) -> Decimal:
        mitigation_events = tuple(
            event for event in self.events_for_block(block) if event.is_mitigation
        )

        if not mitigation_events:
            return Decimal("0")

        return mitigation_events[-1].mitigation_fraction

    def was_mitigated(
        self,
        block: OrderBlock,
    ) -> bool:
        return self.first_mitigation_event(block) is not None

    def is_invalidated(
        self,
        block: OrderBlock,
    ) -> bool:
        return self.state_for(block) == OrderBlockLifecycleState.INVALIDATED

    def is_breaker(
        self,
        block: OrderBlock,
    ) -> bool:
        return self.state_for(block) == OrderBlockLifecycleState.BREAKER_CONFIRMED

    @property
    def untouched_blocks(
        self,
    ) -> tuple[OrderBlock, ...]:
        return tuple(
            block
            for block in self.order_blocks.blocks
            if (self.state_for(block) == OrderBlockLifecycleState.UNTOUCHED)
        )

    @property
    def mitigated_blocks(
        self,
    ) -> tuple[OrderBlock, ...]:
        return tuple(block for block in self.order_blocks.blocks if self.was_mitigated(block))

    @property
    def partially_mitigated_blocks(
        self,
    ) -> tuple[OrderBlock, ...]:
        return tuple(
            block
            for block in self.order_blocks.blocks
            if (self.state_for(block) == OrderBlockLifecycleState.PARTIALLY_MITIGATED)
        )

    @property
    def fully_mitigated_blocks(
        self,
    ) -> tuple[OrderBlock, ...]:
        return tuple(
            block
            for block in self.order_blocks.blocks
            if any(
                event.new_state == OrderBlockLifecycleState.FULLY_MITIGATED
                for event in self.events_for_block(block)
            )
        )

    @property
    def invalidated_blocks(
        self,
    ) -> tuple[OrderBlock, ...]:
        return tuple(block for block in self.order_blocks.blocks if self.is_invalidated(block))

    @property
    def breaker_blocks(
        self,
    ) -> tuple[OrderBlock, ...]:
        return tuple(block for block in self.order_blocks.blocks if self.is_breaker(block))

    @property
    def active_blocks(
        self,
    ) -> tuple[OrderBlock, ...]:
        return tuple(
            block
            for block in self.order_blocks.blocks
            if self.state_for(block)
            in {
                OrderBlockLifecycleState.UNTOUCHED,
                OrderBlockLifecycleState.PARTIALLY_MITIGATED,
                OrderBlockLifecycleState.FULLY_MITIGATED,
            }
        )


class OrderBlockLifecycleTracker:
    """
    Pure closed-candle OB lifecycle tracker.

    Invalidation is close-based. Breakers require a later
    retest after invalidation.
    """

    def __init__(
        self,
        policy: OrderBlockLifecyclePolicy | None = None,
    ) -> None:
        selected_policy = policy or OrderBlockLifecyclePolicy()

        if not isinstance(
            selected_policy,
            OrderBlockLifecyclePolicy,
        ):
            raise ValueError("policy must be an OrderBlockLifecyclePolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> OrderBlockLifecyclePolicy:
        return self._policy

    def track(
        self,
        order_blocks: OrderBlockSet,
    ) -> OrderBlockLifecycleSnapshot:
        if not isinstance(
            order_blocks,
            OrderBlockSet,
        ):
            raise OrderBlockLifecycleError(
                OrderBlockLifecycleErrorReason.INVALID_ORDER_BLOCK_SET,
                "order_blocks must be an OrderBlockSet.",
            )

        events: list[OrderBlockLifecycleEvent] = []

        for block in order_blocks.blocks:
            current_state = OrderBlockLifecycleState.UNTOUCHED
            deepest_penetration = Decimal("0")

            for index in range(
                block.confirmation_index + 1,
                order_blocks.source.count,
            ):
                candle = order_blocks.source.candles[index]

                if current_state == OrderBlockLifecycleState.BREAKER_CONFIRMED:
                    break

                if current_state == OrderBlockLifecycleState.INVALIDATED:
                    breaker_penetration = _raw_breaker_penetration(
                        block,
                        candle,
                    )

                    if breaker_penetration <= self._policy.minimum_breaker_penetration:
                        continue

                    if self._policy.require_breaker_close_rejection and not _breaker_close_rejected(
                        block,
                        candle,
                    ):
                        continue

                    event = OrderBlockLifecycleEvent(
                        index=index,
                        kind=(OrderBlockLifecycleEventKind.BREAKER),
                        block=block,
                        candle=candle,
                        previous_state=current_state,
                        new_state=(OrderBlockLifecycleState.BREAKER_CONFIRMED),
                    )
                    events.append(event)
                    current_state = event.new_state
                    break

                if _is_invalidated(block, candle):
                    event = OrderBlockLifecycleEvent(
                        index=index,
                        kind=(OrderBlockLifecycleEventKind.INVALIDATION),
                        block=block,
                        candle=candle,
                        previous_state=current_state,
                        new_state=(OrderBlockLifecycleState.INVALIDATED),
                    )
                    events.append(event)
                    current_state = event.new_state
                    continue

                reached_state = _mitigation_state_reached(
                    block,
                    candle,
                )

                if reached_state == OrderBlockLifecycleState.UNTOUCHED:
                    continue

                raw_penetration = _raw_mitigation_penetration(
                    block,
                    candle,
                )

                if raw_penetration <= self._policy.minimum_mitigation_penetration:
                    continue

                zone_penetration = _zone_mitigation_penetration(
                    block,
                    candle,
                )

                if zone_penetration <= deepest_penetration:
                    continue

                event = OrderBlockLifecycleEvent(
                    index=index,
                    kind=(OrderBlockLifecycleEventKind.MITIGATION),
                    block=block,
                    candle=candle,
                    previous_state=current_state,
                    new_state=reached_state,
                )
                events.append(event)

                current_state = reached_state
                deepest_penetration = zone_penetration

        ordered_events = tuple(
            sorted(
                events,
                key=lambda event: (
                    event.index,
                    event.block.confirmation_index,
                    event.block.stable_id,
                    event.kind.value,
                ),
            )
        )

        return OrderBlockLifecycleSnapshot(
            order_blocks=order_blocks,
            policy=self._policy,
            events=ordered_events,
        )

    def evaluate(
        self,
        order_blocks: OrderBlockSet,
    ) -> OrderBlockLifecycleSnapshot:
        """Compatibility alias for track()."""

        return self.track(order_blocks)

    def detect(
        self,
        order_blocks: OrderBlockSet,
    ) -> OrderBlockLifecycleSnapshot:
        """Compatibility alias for track()."""

        return self.track(order_blocks)


def track_order_block_lifecycle(
    order_blocks: OrderBlockSet,
    policy: OrderBlockLifecyclePolicy | None = None,
) -> OrderBlockLifecycleSnapshot:
    return OrderBlockLifecycleTracker(policy=policy).track(order_blocks)


OBLifecycleState = OrderBlockLifecycleState
OBLifecycleEventKind = OrderBlockLifecycleEventKind
OBLifecyclePolicy = OrderBlockLifecyclePolicy
OBLifecycleEvent = OrderBlockLifecycleEvent
OBLifecycleSnapshot = OrderBlockLifecycleSnapshot
OBLifecycleTracker = OrderBlockLifecycleTracker
