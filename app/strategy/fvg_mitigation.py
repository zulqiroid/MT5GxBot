from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandle
from app.strategy.fair_value_gaps import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapSet,
)


class FairValueGapMitigationState(str, Enum):
    UNTOUCHED = "UNTOUCHED"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
    CONSEQUENT_ENCROACHMENT = "CONSEQUENT_ENCROACHMENT"
    FULLY_FILLED = "FULLY_FILLED"


class FairValueGapMitigationErrorReason(str, Enum):
    INVALID_GAP_SET = "INVALID_GAP_SET"


class FairValueGapMitigationError(RuntimeError):
    """Structured FVG mitigation tracking failure."""

    def __init__(
        self,
        reason: FairValueGapMitigationErrorReason,
        message: str,
    ) -> None:
        self.reason = FairValueGapMitigationErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Fair value gap mitigation error [{self.reason.value}]: {self.message}")


_STATE_RANK = {
    FairValueGapMitigationState.UNTOUCHED: 0,
    FairValueGapMitigationState.PARTIALLY_MITIGATED: 1,
    FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT: 2,
    FairValueGapMitigationState.FULLY_FILLED: 3,
}


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


def _state_rank(
    state: FairValueGapMitigationState,
) -> int:
    return _STATE_RANK[FairValueGapMitigationState(state)]


def _raw_penetration(
    gap: FairValueGap,
    candle: ClosedCandle,
) -> Decimal:
    if gap.direction == FairValueGapDirection.BULLISH:
        penetration = gap.upper_bound - candle.low
    else:
        penetration = candle.high - gap.lower_bound

    return max(
        penetration,
        Decimal("0"),
    )


def _zone_penetration(
    gap: FairValueGap,
    candle: ClosedCandle,
) -> Decimal:
    return min(
        _raw_penetration(gap, candle),
        gap.size,
    )


def _state_reached(
    gap: FairValueGap,
    candle: ClosedCandle,
) -> FairValueGapMitigationState:
    if gap.direction == FairValueGapDirection.BULLISH:
        if candle.low >= gap.upper_bound:
            return FairValueGapMitigationState.UNTOUCHED

        if candle.low <= gap.lower_bound:
            return FairValueGapMitigationState.FULLY_FILLED

        if candle.low <= gap.midpoint:
            return FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT

        return FairValueGapMitigationState.PARTIALLY_MITIGATED

    if candle.high <= gap.lower_bound:
        return FairValueGapMitigationState.UNTOUCHED

    if candle.high >= gap.upper_bound:
        return FairValueGapMitigationState.FULLY_FILLED

    if candle.high >= gap.midpoint:
        return FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT

    return FairValueGapMitigationState.PARTIALLY_MITIGATED


@dataclass(frozen=True, slots=True)
class FairValueGapMitigationPolicy:
    """Strict closed-candle FVG mitigation policy."""

    minimum_penetration: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        minimum_penetration = _non_negative_decimal(
            self.minimum_penetration,
            "minimum_penetration",
        )

        object.__setattr__(
            self,
            "minimum_penetration",
            minimum_penetration,
        )


@dataclass(frozen=True, slots=True)
class FairValueGapMitigationEvent:
    """One new deepest mitigation observation."""

    index: int
    gap: FairValueGap
    candle: ClosedCandle
    previous_state: FairValueGapMitigationState
    new_state: FairValueGapMitigationState

    def __post_init__(self) -> None:
        index = _non_negative_integer(
            self.index,
            "index",
        )

        if not isinstance(self.gap, FairValueGap):
            raise ValueError("gap must be a FairValueGap.")

        if not isinstance(self.candle, ClosedCandle):
            raise ValueError("candle must be a ClosedCandle.")

        try:
            previous_state = FairValueGapMitigationState(self.previous_state)
            new_state = FairValueGapMitigationState(self.new_state)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported FVG mitigation state.") from error

        if index <= self.gap.confirmation_index:
            raise ValueError("An FVG can be mitigated only after its confirmation candle.")

        if self.candle.broker_symbol != self.gap.broker_symbol:
            raise ValueError("Mitigation candle and FVG symbol must match.")

        if self.candle.timeframe != self.gap.timeframe:
            raise ValueError("Mitigation candle and FVG timeframe must match.")

        reached_state = _state_reached(
            self.gap,
            self.candle,
        )

        if reached_state == FairValueGapMitigationState.UNTOUCHED:
            raise ValueError("Mitigation candle must penetrate the FVG zone.")

        if new_state != reached_state:
            raise ValueError("new_state must match the deepest state reached by the candle.")

        if _state_rank(new_state) < _state_rank(previous_state):
            raise ValueError("FVG mitigation state cannot regress.")

        object.__setattr__(self, "index", index)
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
    def extreme_price(self) -> Decimal:
        if self.gap.direction == FairValueGapDirection.BULLISH:
            return self.candle.low

        return self.candle.high

    @property
    def raw_penetration(self) -> Decimal:
        return _raw_penetration(
            self.gap,
            self.candle,
        )

    @property
    def zone_penetration(self) -> Decimal:
        return _zone_penetration(
            self.gap,
            self.candle,
        )

    @property
    def fill_fraction(self) -> Decimal:
        return self.zone_penetration / self.gap.size

    @property
    def fill_percentage(self) -> Decimal:
        return self.fill_fraction * Decimal("100")

    @property
    def is_progress_only(self) -> bool:
        return self.previous_state == self.new_state

    @property
    def reached_consequent_encroachment(
        self,
    ) -> bool:
        return _state_rank(self.new_state) >= _state_rank(
            FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT
        )

    @property
    def fully_filled(self) -> bool:
        return self.new_state == FairValueGapMitigationState.FULLY_FILLED

    @property
    def stable_id(self) -> str:
        return f"{self.gap.stable_id}:MITIGATION:{self.index}:{self.new_state.value}"


@dataclass(frozen=True, slots=True)
class FairValueGapMitigationSnapshot:
    """Ordered lifecycle history for one FVG collection."""

    gap_set: FairValueGapSet
    policy: FairValueGapMitigationPolicy
    events: tuple[FairValueGapMitigationEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.gap_set,
            FairValueGapSet,
        ):
            raise ValueError("gap_set must be a FairValueGapSet.")

        if not isinstance(
            self.policy,
            FairValueGapMitigationPolicy,
        ):
            raise ValueError("policy must be a FairValueGapMitigationPolicy.")

        events = tuple(self.events)

        for event in events:
            if not isinstance(
                event,
                FairValueGapMitigationEvent,
            ):
                raise ValueError("events must contain FairValueGapMitigationEvent instances.")

        expected_order = tuple(
            sorted(
                events,
                key=lambda event: (
                    event.index,
                    event.gap.confirmation_index,
                    event.gap.stable_id,
                ),
            )
        )

        if events != expected_order:
            raise ValueError("FVG mitigation events must be ordered deterministically.")

        states = {
            gap.stable_id: (FairValueGapMitigationState.UNTOUCHED) for gap in self.gap_set.gaps
        }
        deepest_penetrations = {gap.stable_id: Decimal("0") for gap in self.gap_set.gaps}

        for event in events:
            if event.gap not in self.gap_set.gaps:
                raise ValueError("Mitigated FVG does not belong to the source gap set.")

            if event.index >= self.gap_set.source.count:
                raise ValueError("Mitigation event index exceeds source history.")

            if event.candle != self.gap_set.source.candles[event.index]:
                raise ValueError("Mitigation event candle does not match source history.")

            gap_id = event.gap.stable_id
            current_state = states[gap_id]
            deepest_penetration = deepest_penetrations[gap_id]

            if current_state == FairValueGapMitigationState.FULLY_FILLED:
                raise ValueError("A fully filled FVG cannot produce additional events.")

            if event.previous_state != current_state:
                raise ValueError("FVG mitigation state chain is invalid.")

            if event.raw_penetration <= self.policy.minimum_penetration:
                raise ValueError(
                    "Mitigation event does not exceed the minimum penetration distance."
                )

            if event.zone_penetration <= deepest_penetration:
                raise ValueError("Mitigation event must establish a new deepest zone penetration.")

            states[gap_id] = event.new_state
            deepest_penetrations[gap_id] = event.zone_penetration

        object.__setattr__(
            self,
            "events",
            events,
        )

    @property
    def broker_symbol(self) -> str:
        return self.gap_set.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.gap_set.timeframe

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def latest(
        self,
    ) -> FairValueGapMitigationEvent | None:
        if not self.events:
            return None

        return self.events[-1]

    def _require_gap(
        self,
        gap: FairValueGap,
    ) -> None:
        if not isinstance(gap, FairValueGap):
            raise ValueError("gap must be a FairValueGap.")

        if gap not in self.gap_set.gaps:
            raise ValueError("gap does not belong to this mitigation snapshot.")

    def events_for_gap(
        self,
        gap: FairValueGap,
    ) -> tuple[FairValueGapMitigationEvent, ...]:
        self._require_gap(gap)

        return tuple(event for event in self.events if event.gap == gap)

    def events_at(
        self,
        index: int,
    ) -> tuple[FairValueGapMitigationEvent, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(event for event in self.events if event.index == selected_index)

    def latest_event_for(
        self,
        gap: FairValueGap,
    ) -> FairValueGapMitigationEvent | None:
        gap_events = self.events_for_gap(gap)

        if not gap_events:
            return None

        return gap_events[-1]

    def first_touch_event(
        self,
        gap: FairValueGap,
    ) -> FairValueGapMitigationEvent | None:
        gap_events = self.events_for_gap(gap)

        if not gap_events:
            return None

        return gap_events[0]

    def consequent_encroachment_event(
        self,
        gap: FairValueGap,
    ) -> FairValueGapMitigationEvent | None:
        self._require_gap(gap)

        for event in self.events_for_gap(gap):
            if event.reached_consequent_encroachment:
                return event

        return None

    def full_fill_event(
        self,
        gap: FairValueGap,
    ) -> FairValueGapMitigationEvent | None:
        self._require_gap(gap)

        for event in self.events_for_gap(gap):
            if event.fully_filled:
                return event

        return None

    def state_for(
        self,
        gap: FairValueGap,
    ) -> FairValueGapMitigationState:
        latest_event = self.latest_event_for(gap)

        if latest_event is None:
            return FairValueGapMitigationState.UNTOUCHED

        return latest_event.new_state

    def fill_fraction_for(
        self,
        gap: FairValueGap,
    ) -> Decimal:
        latest_event = self.latest_event_for(gap)

        if latest_event is None:
            return Decimal("0")

        return latest_event.fill_fraction

    def is_fully_filled(
        self,
        gap: FairValueGap,
    ) -> bool:
        return self.state_for(gap) == FairValueGapMitigationState.FULLY_FILLED

    @property
    def untouched_gaps(
        self,
    ) -> tuple[FairValueGap, ...]:
        return tuple(
            gap
            for gap in self.gap_set.gaps
            if (self.state_for(gap) == FairValueGapMitigationState.UNTOUCHED)
        )

    @property
    def mitigated_gaps(
        self,
    ) -> tuple[FairValueGap, ...]:
        return tuple(
            gap
            for gap in self.gap_set.gaps
            if (self.state_for(gap) != FairValueGapMitigationState.UNTOUCHED)
        )

    @property
    def partially_mitigated_gaps(
        self,
    ) -> tuple[FairValueGap, ...]:
        return tuple(
            gap
            for gap in self.gap_set.gaps
            if (self.state_for(gap) == FairValueGapMitigationState.PARTIALLY_MITIGATED)
        )

    @property
    def consequent_encroachment_gaps(
        self,
    ) -> tuple[FairValueGap, ...]:
        return tuple(
            gap
            for gap in self.gap_set.gaps
            if (
                _state_rank(self.state_for(gap))
                >= _state_rank(FairValueGapMitigationState.CONSEQUENT_ENCROACHMENT)
            )
        )

    @property
    def fully_filled_gaps(
        self,
    ) -> tuple[FairValueGap, ...]:
        return tuple(gap for gap in self.gap_set.gaps if self.is_fully_filled(gap))

    @property
    def active_gaps(
        self,
    ) -> tuple[FairValueGap, ...]:
        return tuple(gap for gap in self.gap_set.gaps if not self.is_fully_filled(gap))


class FairValueGapMitigationTracker:
    """
    Pure closed-candle FVG lifecycle tracker.

    Events are emitted only when a candle establishes a new
    deepest penetration into the FVG.
    """

    def __init__(
        self,
        policy: FairValueGapMitigationPolicy | None = None,
    ) -> None:
        selected_policy = policy or FairValueGapMitigationPolicy()

        if not isinstance(
            selected_policy,
            FairValueGapMitigationPolicy,
        ):
            raise ValueError("policy must be a FairValueGapMitigationPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> FairValueGapMitigationPolicy:
        return self._policy

    def track(
        self,
        gap_set: FairValueGapSet,
    ) -> FairValueGapMitigationSnapshot:
        if not isinstance(
            gap_set,
            FairValueGapSet,
        ):
            raise FairValueGapMitigationError(
                FairValueGapMitigationErrorReason.INVALID_GAP_SET,
                "gap_set must be a FairValueGapSet.",
            )

        events: list[FairValueGapMitigationEvent] = []

        for gap in gap_set.gaps:
            current_state = FairValueGapMitigationState.UNTOUCHED
            deepest_penetration = Decimal("0")

            for index in range(
                gap.confirmation_index + 1,
                gap_set.source.count,
            ):
                candle = gap_set.source.candles[index]
                reached_state = _state_reached(
                    gap,
                    candle,
                )

                if reached_state == FairValueGapMitigationState.UNTOUCHED:
                    continue

                raw_penetration = _raw_penetration(
                    gap,
                    candle,
                )

                if raw_penetration <= self._policy.minimum_penetration:
                    continue

                zone_penetration = _zone_penetration(
                    gap,
                    candle,
                )

                if zone_penetration <= deepest_penetration:
                    continue

                if _state_rank(reached_state) < _state_rank(current_state):
                    continue

                event = FairValueGapMitigationEvent(
                    index=index,
                    gap=gap,
                    candle=candle,
                    previous_state=current_state,
                    new_state=reached_state,
                )
                events.append(event)

                current_state = reached_state
                deepest_penetration = zone_penetration

                if current_state == FairValueGapMitigationState.FULLY_FILLED:
                    break

        ordered_events = tuple(
            sorted(
                events,
                key=lambda event: (
                    event.index,
                    event.gap.confirmation_index,
                    event.gap.stable_id,
                ),
            )
        )

        return FairValueGapMitigationSnapshot(
            gap_set=gap_set,
            policy=self._policy,
            events=ordered_events,
        )

    def evaluate(
        self,
        gap_set: FairValueGapSet,
    ) -> FairValueGapMitigationSnapshot:
        """Compatibility alias for track()."""

        return self.track(gap_set)

    def detect(
        self,
        gap_set: FairValueGapSet,
    ) -> FairValueGapMitigationSnapshot:
        """Compatibility alias for track()."""

        return self.track(gap_set)


def track_fair_value_gap_mitigation(
    gap_set: FairValueGapSet,
    policy: FairValueGapMitigationPolicy | None = None,
) -> FairValueGapMitigationSnapshot:
    return FairValueGapMitigationTracker(policy=policy).track(gap_set)


FVGMitigationState = FairValueGapMitigationState
FVGMitigationPolicy = FairValueGapMitigationPolicy
FVGMitigationEvent = FairValueGapMitigationEvent
FVGMitigationSnapshot = FairValueGapMitigationSnapshot
FVGMitigationTracker = FairValueGapMitigationTracker
