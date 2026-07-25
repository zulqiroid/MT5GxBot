from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandle
from app.strategy.swings import (
    ConfirmedSwingPoint,
    ConfirmedSwingSet,
    SwingKind,
)


class MarketStructureBias(str, Enum):
    NEUTRAL = "NEUTRAL"
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class StructureBreakKind(str, Enum):
    BOS = "BOS"
    CHOCH = "CHOCH"


class StructureBreakDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class MarketStructureErrorReason(str, Enum):
    INVALID_SWING_SET = "INVALID_SWING_SET"
    AMBIGUOUS_BREAK = "AMBIGUOUS_BREAK"


class MarketStructureAnalysisError(RuntimeError):
    """Structured failure during BOS/CHOCH analysis."""

    def __init__(
        self,
        reason: MarketStructureErrorReason,
        message: str,
    ) -> None:
        self.reason = MarketStructureErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Market structure error [{self.reason.value}]: {self.message}")


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


def _bias_for_direction(
    direction: StructureBreakDirection,
) -> MarketStructureBias:
    if direction == StructureBreakDirection.BULLISH:
        return MarketStructureBias.BULLISH

    return MarketStructureBias.BEARISH


def _expected_break_kind(
    previous_bias: MarketStructureBias,
    direction: StructureBreakDirection,
) -> StructureBreakKind:
    directional_bias = _bias_for_direction(direction)

    if previous_bias in {
        MarketStructureBias.NEUTRAL,
        directional_bias,
    }:
        return StructureBreakKind.BOS

    return StructureBreakKind.CHOCH


@dataclass(frozen=True, slots=True)
class MarketStructurePolicy:
    """Conservative close-confirmed structure policy."""

    initial_bias: MarketStructureBias = MarketStructureBias.NEUTRAL
    minimum_break_distance: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        try:
            initial_bias = MarketStructureBias(self.initial_bias)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported initial bias: {self.initial_bias}.") from error

        minimum_break_distance = _non_negative_decimal(
            self.minimum_break_distance,
            "minimum_break_distance",
        )

        object.__setattr__(
            self,
            "initial_bias",
            initial_bias,
        )
        object.__setattr__(
            self,
            "minimum_break_distance",
            minimum_break_distance,
        )


@dataclass(frozen=True, slots=True)
class StructureBreakEvent:
    """One close-confirmed BOS or CHOCH event."""

    index: int
    kind: StructureBreakKind
    direction: StructureBreakDirection
    previous_bias: MarketStructureBias
    new_bias: MarketStructureBias
    broken_swing: ConfirmedSwingPoint
    candle: ClosedCandle

    def __post_init__(self) -> None:
        index = _non_negative_integer(
            self.index,
            "index",
        )

        try:
            kind = StructureBreakKind(self.kind)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported break kind: {self.kind}.") from error

        try:
            direction = StructureBreakDirection(self.direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported break direction: {self.direction}.") from error

        try:
            previous_bias = MarketStructureBias(self.previous_bias)
            new_bias = MarketStructureBias(self.new_bias)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported structure bias.") from error

        if not isinstance(
            self.broken_swing,
            ConfirmedSwingPoint,
        ):
            raise ValueError("broken_swing must be a ConfirmedSwingPoint.")

        if not isinstance(self.candle, ClosedCandle):
            raise ValueError("candle must be a ClosedCandle.")

        if index <= self.broken_swing.confirmed_by_index:
            raise ValueError("A swing can be broken only after its confirmation candle has closed.")

        if self.candle.broker_symbol != self.broken_swing.broker_symbol:
            raise ValueError("Break candle and swing symbol must match.")

        if self.candle.timeframe != self.broken_swing.timeframe:
            raise ValueError("Break candle and swing timeframe must match.")

        expected_bias = _bias_for_direction(direction)

        if new_bias != expected_bias:
            raise ValueError("new_bias must match break direction.")

        expected_kind = _expected_break_kind(
            previous_bias,
            direction,
        )

        if kind != expected_kind:
            raise ValueError("Break kind does not match the previous bias and break direction.")

        if direction == StructureBreakDirection.BULLISH:
            if self.broken_swing.kind != SwingKind.HIGH:
                raise ValueError("Bullish breaks must break a swing high.")

            if self.candle.close <= self.broken_swing.price:
                raise ValueError("Bullish break candle must close above the swing-high price.")
        else:
            if self.broken_swing.kind != SwingKind.LOW:
                raise ValueError("Bearish breaks must break a swing low.")

            if self.candle.close >= self.broken_swing.price:
                raise ValueError("Bearish break candle must close below the swing-low price.")

        object.__setattr__(self, "index", index)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "direction",
            direction,
        )
        object.__setattr__(
            self,
            "previous_bias",
            previous_bias,
        )
        object.__setattr__(
            self,
            "new_bias",
            new_bias,
        )

    @property
    def break_price(self) -> Decimal:
        return self.candle.close

    @property
    def level_price(self) -> Decimal:
        return self.broken_swing.price

    @property
    def break_distance(self) -> Decimal:
        return abs(self.break_price - self.level_price)

    @property
    def confirmed_at(self) -> datetime:
        return self.candle.close_time

    @property
    def broker_symbol(self) -> str:
        return self.candle.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.candle.timeframe

    @property
    def is_bos(self) -> bool:
        return self.kind == StructureBreakKind.BOS

    @property
    def is_choch(self) -> bool:
        return self.kind == StructureBreakKind.CHOCH

    @property
    def is_bullish(self) -> bool:
        return self.direction == StructureBreakDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == StructureBreakDirection.BEARISH


@dataclass(frozen=True, slots=True)
class MarketStructureSnapshot:
    """Ordered close-confirmed market-structure history."""

    swings: ConfirmedSwingSet
    policy: MarketStructurePolicy
    events: tuple[StructureBreakEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.swings,
            ConfirmedSwingSet,
        ):
            raise ValueError("swings must be a ConfirmedSwingSet.")

        if not isinstance(
            self.policy,
            MarketStructurePolicy,
        ):
            raise ValueError("policy must be a MarketStructurePolicy.")

        events = tuple(self.events)
        previous_index = -1
        running_bias = self.policy.initial_bias
        broken_keys: set[tuple[int, SwingKind]] = set()

        for event in events:
            if not isinstance(
                event,
                StructureBreakEvent,
            ):
                raise ValueError("events must contain StructureBreakEvent instances.")

            if event.index <= previous_index:
                raise ValueError(
                    "Structure events must be ordered by strictly increasing candle index."
                )

            if event.index >= self.swings.source.count:
                raise ValueError("Structure event index exceeds source history.")

            if event.candle != self.swings.source.candles[event.index]:
                raise ValueError(
                    "Structure event candle does not match the source candle at its index."
                )

            if event.broken_swing not in self.swings.points:
                raise ValueError("Broken swing does not belong to the source swing set.")

            key = (
                event.broken_swing.index,
                event.broken_swing.kind,
            )

            if key in broken_keys:
                raise ValueError("A confirmed swing level cannot be broken more than once.")

            if event.previous_bias != running_bias:
                raise ValueError("Structure event bias chain is invalid.")

            if (
                event.break_distance <= self.policy.minimum_break_distance
                and self.policy.minimum_break_distance > 0
            ):
                raise ValueError("Structure event does not exceed the minimum break distance.")

            broken_keys.add(key)
            running_bias = event.new_bias
            previous_index = event.index

        object.__setattr__(
            self,
            "events",
            events,
        )

    @property
    def broker_symbol(self) -> str:
        return self.swings.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.swings.timeframe

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def current_bias(self) -> MarketStructureBias:
        if not self.events:
            return self.policy.initial_bias

        return self.events[-1].new_bias

    @property
    def latest_event(
        self,
    ) -> StructureBreakEvent | None:
        if not self.events:
            return None

        return self.events[-1]

    @property
    def bos_events(
        self,
    ) -> tuple[StructureBreakEvent, ...]:
        return tuple(event for event in self.events if event.kind == StructureBreakKind.BOS)

    @property
    def choch_events(
        self,
    ) -> tuple[StructureBreakEvent, ...]:
        return tuple(event for event in self.events if event.kind == StructureBreakKind.CHOCH)

    @property
    def bullish_breaks(
        self,
    ) -> tuple[StructureBreakEvent, ...]:
        return tuple(
            event for event in self.events if event.direction == StructureBreakDirection.BULLISH
        )

    @property
    def bearish_breaks(
        self,
    ) -> tuple[StructureBreakEvent, ...]:
        return tuple(
            event for event in self.events if event.direction == StructureBreakDirection.BEARISH
        )

    def events_at(
        self,
        index: int,
    ) -> tuple[StructureBreakEvent, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(event for event in self.events if event.index == selected_index)

    def bias_after(
        self,
        index: int,
    ) -> MarketStructureBias:
        selected_index = _non_negative_integer(
            index,
            "index",
        )
        bias = self.policy.initial_bias

        for event in self.events:
            if event.index > selected_index:
                break

            bias = event.new_bias

        return bias


class MarketStructureAnalyzer:
    """
    Pure close-confirmed BOS/CHOCH analyzer.

    Swing levels become available only after their confirming
    candle has closed. Each swing level can produce one event.
    """

    def __init__(
        self,
        policy: MarketStructurePolicy | None = None,
    ) -> None:
        selected_policy = policy or MarketStructurePolicy()

        if not isinstance(
            selected_policy,
            MarketStructurePolicy,
        ):
            raise ValueError("policy must be a MarketStructurePolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> MarketStructurePolicy:
        return self._policy

    def analyze(
        self,
        swings: ConfirmedSwingSet,
    ) -> MarketStructureSnapshot:
        if not isinstance(
            swings,
            ConfirmedSwingSet,
        ):
            raise MarketStructureAnalysisError(
                MarketStructureErrorReason.INVALID_SWING_SET,
                "swings must be a ConfirmedSwingSet.",
            )

        confirmation_map: dict[
            int,
            list[ConfirmedSwingPoint],
        ] = {}

        for point in swings.points:
            confirmation_map.setdefault(
                point.confirmed_by_index,
                [],
            ).append(point)

        latest_high: ConfirmedSwingPoint | None = None
        latest_low: ConfirmedSwingPoint | None = None
        broken_levels: set[tuple[int, SwingKind]] = set()
        events: list[StructureBreakEvent] = []
        current_bias = self._policy.initial_bias

        for index, candle in enumerate(swings.source.candles):
            bullish_swing = self._eligible_swing(
                latest_high,
                broken_levels,
            )
            bearish_swing = self._eligible_swing(
                latest_low,
                broken_levels,
            )

            bullish_break = (
                bullish_swing is not None
                and candle.close > bullish_swing.price + self._policy.minimum_break_distance
            )
            bearish_break = (
                bearish_swing is not None
                and candle.close < bearish_swing.price - self._policy.minimum_break_distance
            )

            if bullish_break and bearish_break:
                raise MarketStructureAnalysisError(
                    MarketStructureErrorReason.AMBIGUOUS_BREAK,
                    f"Candle index {index} simultaneously breaks the active swing high and low.",
                )

            if bullish_break:
                assert bullish_swing is not None

                event = self._create_event(
                    index=index,
                    candle=candle,
                    swing=bullish_swing,
                    direction=(StructureBreakDirection.BULLISH),
                    previous_bias=current_bias,
                )
                events.append(event)
                broken_levels.add(
                    (
                        bullish_swing.index,
                        bullish_swing.kind,
                    )
                )
                current_bias = event.new_bias

            elif bearish_break:
                assert bearish_swing is not None

                event = self._create_event(
                    index=index,
                    candle=candle,
                    swing=bearish_swing,
                    direction=(StructureBreakDirection.BEARISH),
                    previous_bias=current_bias,
                )
                events.append(event)
                broken_levels.add(
                    (
                        bearish_swing.index,
                        bearish_swing.kind,
                    )
                )
                current_bias = event.new_bias

            # A swing confirmed by this candle becomes usable
            # only from the following candle onward.
            for point in confirmation_map.get(index, ()):
                if point.kind == SwingKind.HIGH:
                    latest_high = point
                else:
                    latest_low = point

        return MarketStructureSnapshot(
            swings=swings,
            policy=self._policy,
            events=tuple(events),
        )

    def evaluate(
        self,
        swings: ConfirmedSwingSet,
    ) -> MarketStructureSnapshot:
        """Compatibility alias for analyze()."""

        return self.analyze(swings)

    def detect(
        self,
        swings: ConfirmedSwingSet,
    ) -> MarketStructureSnapshot:
        """Compatibility alias for analyze()."""

        return self.analyze(swings)

    @staticmethod
    def _eligible_swing(
        swing: ConfirmedSwingPoint | None,
        broken_levels: set[tuple[int, SwingKind]],
    ) -> ConfirmedSwingPoint | None:
        if swing is None:
            return None

        key = (swing.index, swing.kind)

        if key in broken_levels:
            return None

        return swing

    @staticmethod
    def _create_event(
        *,
        index: int,
        candle: ClosedCandle,
        swing: ConfirmedSwingPoint,
        direction: StructureBreakDirection,
        previous_bias: MarketStructureBias,
    ) -> StructureBreakEvent:
        new_bias = _bias_for_direction(direction)
        kind = _expected_break_kind(
            previous_bias,
            direction,
        )

        return StructureBreakEvent(
            index=index,
            kind=kind,
            direction=direction,
            previous_bias=previous_bias,
            new_bias=new_bias,
            broken_swing=swing,
            candle=candle,
        )


def analyze_market_structure(
    swings: ConfirmedSwingSet,
    policy: MarketStructurePolicy | None = None,
) -> MarketStructureSnapshot:
    return MarketStructureAnalyzer(policy=policy).analyze(swings)


StructureBias = MarketStructureBias
BreakKind = StructureBreakKind
BreakDirection = StructureBreakDirection
StructureEvent = StructureBreakEvent
StructureSnapshot = MarketStructureSnapshot
StructureAnalyzer = MarketStructureAnalyzer
