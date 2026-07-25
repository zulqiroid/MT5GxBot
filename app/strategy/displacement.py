from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)


class DisplacementDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class DisplacementDetectionErrorReason(str, Enum):
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INVALID_SERIES = "INVALID_SERIES"


class DisplacementDetectionError(RuntimeError):
    """Structured closed-candle displacement failure."""

    def __init__(
        self,
        reason: DisplacementDetectionErrorReason,
        message: str,
    ) -> None:
        self.reason = DisplacementDetectionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Displacement detection error [{self.reason.value}]: {self.message}")


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


def _non_negative_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    decimal_value = _decimal_value(
        value,
        field_name,
    )

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


def _at_least_one_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    decimal_value = _decimal_value(
        value,
        field_name,
    )

    if decimal_value < Decimal("1"):
        raise ValueError(f"{field_name} must be at least one.")

    return decimal_value


def _candle_range(
    candle: ClosedCandle,
) -> Decimal:
    return candle.high - candle.low


def _body_size(
    candle: ClosedCandle,
) -> Decimal:
    return abs(candle.close - candle.open)


def _direction_for(
    candle: ClosedCandle,
) -> DisplacementDirection | None:
    if candle.close > candle.open:
        return DisplacementDirection.BULLISH

    if candle.close < candle.open:
        return DisplacementDirection.BEARISH

    return None


def _close_retracement(
    candle: ClosedCandle,
    direction: DisplacementDirection,
) -> Decimal:
    if direction == DisplacementDirection.BULLISH:
        return candle.high - candle.close

    return candle.close - candle.low


@dataclass(frozen=True, slots=True)
class DisplacementPolicy:
    """Conservative closed-candle displacement policy."""

    lookback_candles: int = 3
    minimum_body_ratio: Decimal = Decimal("0.60")
    minimum_range_expansion_ratio: Decimal = Decimal("1.50")
    maximum_close_retracement_ratio: Decimal = Decimal("0.25")
    minimum_absolute_range: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        lookback_candles = _positive_integer(
            self.lookback_candles,
            "lookback_candles",
            100,
        )
        minimum_body_ratio = _ratio_decimal(
            self.minimum_body_ratio,
            "minimum_body_ratio",
        )
        minimum_range_expansion_ratio = _at_least_one_decimal(
            self.minimum_range_expansion_ratio,
            "minimum_range_expansion_ratio",
        )
        maximum_close_retracement_ratio = _ratio_decimal(
            self.maximum_close_retracement_ratio,
            "maximum_close_retracement_ratio",
        )
        minimum_absolute_range = _non_negative_decimal(
            self.minimum_absolute_range,
            "minimum_absolute_range",
        )

        object.__setattr__(
            self,
            "lookback_candles",
            lookback_candles,
        )
        object.__setattr__(
            self,
            "minimum_body_ratio",
            minimum_body_ratio,
        )
        object.__setattr__(
            self,
            "minimum_range_expansion_ratio",
            minimum_range_expansion_ratio,
        )
        object.__setattr__(
            self,
            "maximum_close_retracement_ratio",
            maximum_close_retracement_ratio,
        )
        object.__setattr__(
            self,
            "minimum_absolute_range",
            minimum_absolute_range,
        )

    @property
    def minimum_history(self) -> int:
        return self.lookback_candles + 1


@dataclass(frozen=True, slots=True)
class DisplacementImpulse:
    """One close-confirmed displacement candle."""

    index: int
    direction: DisplacementDirection
    candle: ClosedCandle
    baseline_average_range: Decimal

    def __post_init__(self) -> None:
        index = _non_negative_integer(
            self.index,
            "index",
        )

        try:
            direction = DisplacementDirection(self.direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported displacement direction: {self.direction}.") from error

        if not isinstance(self.candle, ClosedCandle):
            raise ValueError("candle must be a ClosedCandle.")

        baseline_average_range = _positive_decimal(
            self.baseline_average_range,
            "baseline_average_range",
        )

        candle_direction = _direction_for(self.candle)

        if candle_direction is None:
            raise ValueError("A displacement candle cannot be a doji.")

        if candle_direction != direction:
            raise ValueError("Displacement direction must match the candle body direction.")

        if self.candle_range <= 0:
            raise ValueError("A displacement candle requires positive range.")

        object.__setattr__(self, "index", index)
        object.__setattr__(
            self,
            "direction",
            direction,
        )
        object.__setattr__(
            self,
            "baseline_average_range",
            baseline_average_range,
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
    def candle_range(self) -> Decimal:
        return _candle_range(self.candle)

    @property
    def body_size(self) -> Decimal:
        return _body_size(self.candle)

    @property
    def body_ratio(self) -> Decimal:
        return self.body_size / self.candle_range

    @property
    def range_expansion_ratio(self) -> Decimal:
        return self.candle_range / self.baseline_average_range

    @property
    def close_retracement(self) -> Decimal:
        return _close_retracement(
            self.candle,
            self.direction,
        )

    @property
    def close_retracement_ratio(self) -> Decimal:
        return self.close_retracement / self.candle_range

    @property
    def is_bullish(self) -> bool:
        return self.direction == DisplacementDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == DisplacementDirection.BEARISH

    @property
    def stable_id(self) -> str:
        return f"{self.broker_symbol}:{self.timeframe.value}:{self.direction.value}:{self.index}"


@dataclass(frozen=True, slots=True)
class DisplacementSet:
    """Ordered displacement impulses from one candle series."""

    source: ClosedCandleSeries
    policy: DisplacementPolicy
    impulses: tuple[DisplacementImpulse, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.source,
            ClosedCandleSeries,
        ):
            raise ValueError("source must be a ClosedCandleSeries.")

        if not isinstance(
            self.policy,
            DisplacementPolicy,
        ):
            raise ValueError("policy must be a DisplacementPolicy.")

        impulses = tuple(self.impulses)

        for impulse in impulses:
            if not isinstance(
                impulse,
                DisplacementImpulse,
            ):
                raise ValueError("impulses must contain DisplacementImpulse instances.")

        expected_order = tuple(
            sorted(
                impulses,
                key=lambda impulse: impulse.index,
            )
        )

        if impulses != expected_order:
            raise ValueError("Displacement impulses must be ordered by candle index.")

        indexes: set[int] = set()

        for impulse in impulses:
            if impulse.index in indexes:
                raise ValueError("Duplicate displacement indexes are not allowed.")

            if impulse.index >= self.source.count:
                raise ValueError("Displacement index exceeds source history.")

            if impulse.index < self.policy.lookback_candles:
                raise ValueError("Displacement index does not have enough prior lookback candles.")

            if impulse.candle != self.source.candles[impulse.index]:
                raise ValueError(
                    "Displacement candle does not match the source candle at its index."
                )

            prior_start = impulse.index - self.policy.lookback_candles
            prior_candles = self.source.candles[prior_start : impulse.index]
            expected_baseline = sum(
                (_candle_range(candle) for candle in prior_candles),
                start=Decimal("0"),
            ) / Decimal(self.policy.lookback_candles)

            if impulse.baseline_average_range != expected_baseline:
                raise ValueError(
                    "Displacement baseline does not match the configured prior-candle average."
                )

            if impulse.candle_range <= self.policy.minimum_absolute_range:
                raise ValueError("Displacement range does not exceed the minimum absolute range.")

            if impulse.body_ratio < self.policy.minimum_body_ratio:
                raise ValueError("Displacement body ratio is below the configured minimum.")

            if impulse.range_expansion_ratio <= self.policy.minimum_range_expansion_ratio:
                raise ValueError(
                    "Displacement range does not strictly exceed the expansion threshold."
                )

            if impulse.close_retracement_ratio > self.policy.maximum_close_retracement_ratio:
                raise ValueError("Displacement close retracement exceeds the configured maximum.")

            indexes.add(impulse.index)

        object.__setattr__(
            self,
            "impulses",
            impulses,
        )

    @property
    def broker_symbol(self) -> str:
        return self.source.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.source.timeframe

    @property
    def count(self) -> int:
        return len(self.impulses)

    @property
    def bullish(
        self,
    ) -> tuple[DisplacementImpulse, ...]:
        return tuple(
            impulse
            for impulse in self.impulses
            if impulse.direction == DisplacementDirection.BULLISH
        )

    @property
    def bearish(
        self,
    ) -> tuple[DisplacementImpulse, ...]:
        return tuple(
            impulse
            for impulse in self.impulses
            if impulse.direction == DisplacementDirection.BEARISH
        )

    @property
    def latest(
        self,
    ) -> DisplacementImpulse | None:
        if not self.impulses:
            return None

        return self.impulses[-1]

    @property
    def latest_bullish(
        self,
    ) -> DisplacementImpulse | None:
        if not self.bullish:
            return None

        return self.bullish[-1]

    @property
    def latest_bearish(
        self,
    ) -> DisplacementImpulse | None:
        if not self.bearish:
            return None

        return self.bearish[-1]

    @property
    def strongest(
        self,
    ) -> DisplacementImpulse | None:
        if not self.impulses:
            return None

        return max(
            self.impulses,
            key=lambda impulse: (
                impulse.range_expansion_ratio,
                impulse.body_ratio,
                -impulse.index,
            ),
        )

    def by_direction(
        self,
        direction: DisplacementDirection,
    ) -> tuple[DisplacementImpulse, ...]:
        try:
            selected_direction = DisplacementDirection(direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported displacement direction: {direction}.") from error

        if selected_direction == DisplacementDirection.BULLISH:
            return self.bullish

        return self.bearish

    def at_index(
        self,
        index: int,
    ) -> DisplacementImpulse | None:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        for impulse in self.impulses:
            if impulse.index == selected_index:
                return impulse

        return None

    def confirmed_at_index(
        self,
        index: int,
    ) -> tuple[DisplacementImpulse, ...]:
        impulse = self.at_index(index)

        if impulse is None:
            return ()

        return (impulse,)


class DisplacementDetector:
    """
    Pure deterministic closed-candle displacement detector.

    The current candle is compared only with fully closed
    candles immediately preceding it.
    """

    def __init__(
        self,
        policy: DisplacementPolicy | None = None,
    ) -> None:
        selected_policy = policy or DisplacementPolicy()

        if not isinstance(
            selected_policy,
            DisplacementPolicy,
        ):
            raise ValueError("policy must be a DisplacementPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> DisplacementPolicy:
        return self._policy

    def detect(
        self,
        series: ClosedCandleSeries,
    ) -> DisplacementSet:
        if not isinstance(
            series,
            ClosedCandleSeries,
        ):
            raise DisplacementDetectionError(
                DisplacementDetectionErrorReason.INVALID_SERIES,
                "series must be a ClosedCandleSeries.",
            )

        if series.count < self._policy.minimum_history:
            raise DisplacementDetectionError(
                DisplacementDetectionErrorReason.INSUFFICIENT_HISTORY,
                "At least "
                f"{self._policy.minimum_history} closed "
                "candles are required; received "
                f"{series.count}.",
            )

        impulses: list[DisplacementImpulse] = []

        for index in range(
            self._policy.lookback_candles,
            series.count,
        ):
            candle = series.candles[index]
            direction = _direction_for(candle)

            if direction is None:
                continue

            candle_range = _candle_range(candle)

            if candle_range <= self._policy.minimum_absolute_range:
                continue

            if candle_range <= 0:
                continue

            prior_start = index - self._policy.lookback_candles
            prior_candles = series.candles[prior_start:index]
            baseline_average_range = sum(
                (_candle_range(prior) for prior in prior_candles),
                start=Decimal("0"),
            ) / Decimal(self._policy.lookback_candles)

            if baseline_average_range <= 0:
                continue

            body_ratio = _body_size(candle) / candle_range

            if body_ratio < self._policy.minimum_body_ratio:
                continue

            range_expansion_ratio = candle_range / baseline_average_range

            if range_expansion_ratio <= self._policy.minimum_range_expansion_ratio:
                continue

            close_retracement_ratio = (
                _close_retracement(
                    candle,
                    direction,
                )
                / candle_range
            )

            if close_retracement_ratio > self._policy.maximum_close_retracement_ratio:
                continue

            impulses.append(
                DisplacementImpulse(
                    index=index,
                    direction=direction,
                    candle=candle,
                    baseline_average_range=(baseline_average_range),
                )
            )

        return DisplacementSet(
            source=series,
            policy=self._policy,
            impulses=tuple(impulses),
        )

    def evaluate(
        self,
        series: ClosedCandleSeries,
    ) -> DisplacementSet:
        """Compatibility alias for detect()."""

        return self.detect(series)

    def find(
        self,
        series: ClosedCandleSeries,
    ) -> DisplacementSet:
        """Compatibility alias for detect()."""

        return self.detect(series)


def detect_displacement_impulses(
    series: ClosedCandleSeries,
    policy: DisplacementPolicy | None = None,
) -> DisplacementSet:
    return DisplacementDetector(policy=policy).detect(series)


Displacement = DisplacementImpulse
DisplacementCollection = DisplacementSet
ImpulseDirection = DisplacementDirection
ImpulseDetector = DisplacementDetector
ImpulsePolicy = DisplacementPolicy
