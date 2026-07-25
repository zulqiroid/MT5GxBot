from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandle
from app.strategy.liquidity import (
    LiquidityPool,
    LiquidityPoolSet,
    LiquiditySide,
)


class LiquiditySweepErrorReason(str, Enum):
    INVALID_POOL_SET = "INVALID_POOL_SET"
    AMBIGUOUS_SWEEP = "AMBIGUOUS_SWEEP"


class LiquiditySweepDetectionError(RuntimeError):
    """Structured liquidity-sweep detection failure."""

    def __init__(
        self,
        reason: LiquiditySweepErrorReason,
        message: str,
        *,
        candle_index: int | None = None,
    ) -> None:
        self.reason = LiquiditySweepErrorReason(reason)
        self.message = str(message)
        self.candle_index = candle_index

        suffix = "" if candle_index is None else f" [candle_index={candle_index}]"

        super().__init__(f"Liquidity sweep error [{self.reason.value}]{suffix}: {self.message}")


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


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


@dataclass(frozen=True, slots=True)
class LiquiditySweepPolicy:
    """Conservative close-reclaimed liquidity-sweep policy."""

    minimum_penetration: Decimal = Decimal("0")
    require_close_back_inside: bool = True

    def __post_init__(self) -> None:
        minimum_penetration = _non_negative_decimal(
            self.minimum_penetration,
            "minimum_penetration",
        )
        require_close_back_inside = _strict_boolean(
            self.require_close_back_inside,
            "require_close_back_inside",
        )

        object.__setattr__(
            self,
            "minimum_penetration",
            minimum_penetration,
        )
        object.__setattr__(
            self,
            "require_close_back_inside",
            require_close_back_inside,
        )


@dataclass(frozen=True, slots=True)
class LiquiditySweepEvent:
    """One closed-candle sweep of a confirmed liquidity pool."""

    index: int
    pool: LiquidityPool
    candle: ClosedCandle

    def __post_init__(self) -> None:
        index = _non_negative_integer(
            self.index,
            "index",
        )

        if not isinstance(self.pool, LiquidityPool):
            raise ValueError("pool must be a LiquidityPool.")

        if not isinstance(self.candle, ClosedCandle):
            raise ValueError("candle must be a ClosedCandle.")

        if index <= self.pool.confirmation_index:
            raise ValueError(
                "A liquidity pool can be swept only after its final touch has been confirmed."
            )

        if self.candle.broker_symbol != self.pool.broker_symbol:
            raise ValueError("Sweep candle and liquidity-pool symbol must match.")

        if self.candle.timeframe != self.pool.timeframe:
            raise ValueError("Sweep candle and liquidity-pool timeframe must match.")

        if self.pool.side == LiquiditySide.BUY_SIDE:
            if self.candle.high <= self.pool.upper_bound:
                raise ValueError("Buy-side sweep candle must trade above the pool upper boundary.")
        elif self.candle.low >= self.pool.lower_bound:
            raise ValueError("Sell-side sweep candle must trade below the pool lower boundary.")

        object.__setattr__(self, "index", index)

    @property
    def side(self) -> LiquiditySide:
        return self.pool.side

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
    def liquidity_level(self) -> Decimal:
        return self.pool.level

    @property
    def boundary(self) -> Decimal:
        if self.side == LiquiditySide.BUY_SIDE:
            return self.pool.upper_bound

        return self.pool.lower_bound

    @property
    def extreme_price(self) -> Decimal:
        if self.side == LiquiditySide.BUY_SIDE:
            return self.candle.high

        return self.candle.low

    @property
    def penetration(self) -> Decimal:
        return abs(self.extreme_price - self.boundary)

    @property
    def closed_back_inside(self) -> bool:
        if self.side == LiquiditySide.BUY_SIDE:
            return self.candle.close <= self.pool.upper_bound

        return self.candle.close >= self.pool.lower_bound

    @property
    def is_buy_side_sweep(self) -> bool:
        return self.side == LiquiditySide.BUY_SIDE

    @property
    def is_sell_side_sweep(self) -> bool:
        return self.side == LiquiditySide.SELL_SIDE

    @property
    def implied_direction(self) -> str:
        if self.is_buy_side_sweep:
            return "BEARISH"

        return "BULLISH"

    @property
    def stable_id(self) -> str:
        return f"{self.pool.stable_id}:SWEEP:{self.index}"


@dataclass(frozen=True, slots=True)
class LiquiditySweepSnapshot:
    """Ordered sweep history for one liquidity-pool collection."""

    pool_set: LiquidityPoolSet
    policy: LiquiditySweepPolicy
    events: tuple[LiquiditySweepEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.pool_set,
            LiquidityPoolSet,
        ):
            raise ValueError("pool_set must be a LiquidityPoolSet.")

        if not isinstance(
            self.policy,
            LiquiditySweepPolicy,
        ):
            raise ValueError("policy must be a LiquiditySweepPolicy.")

        events = tuple(self.events)
        previous_index = -1
        swept_pool_ids: set[str] = set()

        for event in events:
            if not isinstance(
                event,
                LiquiditySweepEvent,
            ):
                raise ValueError("events must contain LiquiditySweepEvent instances.")

            if event.index <= previous_index:
                raise ValueError(
                    "Sweep events must be ordered by strictly increasing candle index."
                )

            if event.index >= self.pool_set.swings.source.count:
                raise ValueError("Sweep event index exceeds source history.")

            if event.candle != self.pool_set.swings.source.candles[event.index]:
                raise ValueError(
                    "Sweep event candle does not match the source candle at its index."
                )

            if event.pool not in self.pool_set.pools:
                raise ValueError("Swept pool does not belong to the source liquidity-pool set.")

            if event.pool.stable_id in swept_pool_ids:
                raise ValueError("A liquidity pool cannot be swept more than once.")

            if (
                event.penetration <= self.policy.minimum_penetration
                and self.policy.minimum_penetration > 0
            ):
                raise ValueError("Sweep event does not exceed the minimum penetration distance.")

            if self.policy.require_close_back_inside and not event.closed_back_inside:
                raise ValueError("Sweep event did not close back inside the liquidity boundary.")

            swept_pool_ids.add(event.pool.stable_id)
            previous_index = event.index

        object.__setattr__(
            self,
            "events",
            events,
        )

    @property
    def broker_symbol(self) -> str:
        return self.pool_set.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.pool_set.timeframe

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def latest(
        self,
    ) -> LiquiditySweepEvent | None:
        if not self.events:
            return None

        return self.events[-1]

    @property
    def buy_side_sweeps(
        self,
    ) -> tuple[LiquiditySweepEvent, ...]:
        return tuple(event for event in self.events if event.side == LiquiditySide.BUY_SIDE)

    @property
    def sell_side_sweeps(
        self,
    ) -> tuple[LiquiditySweepEvent, ...]:
        return tuple(event for event in self.events if event.side == LiquiditySide.SELL_SIDE)

    @property
    def swept_pools(
        self,
    ) -> tuple[LiquidityPool, ...]:
        return tuple(event.pool for event in self.events)

    @property
    def unswept_pools(
        self,
    ) -> tuple[LiquidityPool, ...]:
        swept_ids = {event.pool.stable_id for event in self.events}

        return tuple(pool for pool in self.pool_set.pools if pool.stable_id not in swept_ids)

    def events_at(
        self,
        index: int,
    ) -> tuple[LiquiditySweepEvent, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(event for event in self.events if event.index == selected_index)

    def events_for_side(
        self,
        side: LiquiditySide,
    ) -> tuple[LiquiditySweepEvent, ...]:
        try:
            selected_side = LiquiditySide(side)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported liquidity side: {side}.") from error

        if selected_side == LiquiditySide.BUY_SIDE:
            return self.buy_side_sweeps

        return self.sell_side_sweeps

    def was_swept(
        self,
        pool: LiquidityPool,
    ) -> bool:
        if not isinstance(pool, LiquidityPool):
            raise ValueError("pool must be a LiquidityPool.")

        return any(event.pool.stable_id == pool.stable_id for event in self.events)


class LiquiditySweepDetector:
    """
    Pure close-confirmed liquidity-sweep detector.

    Each pool becomes eligible only after its confirmation
    candle. Each pool can create at most one sweep event.
    """

    def __init__(
        self,
        policy: LiquiditySweepPolicy | None = None,
    ) -> None:
        selected_policy = policy or LiquiditySweepPolicy()

        if not isinstance(
            selected_policy,
            LiquiditySweepPolicy,
        ):
            raise ValueError("policy must be a LiquiditySweepPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> LiquiditySweepPolicy:
        return self._policy

    def detect(
        self,
        pool_set: LiquidityPoolSet,
    ) -> LiquiditySweepSnapshot:
        if not isinstance(
            pool_set,
            LiquidityPoolSet,
        ):
            raise LiquiditySweepDetectionError(
                LiquiditySweepErrorReason.INVALID_POOL_SET,
                "pool_set must be a LiquidityPoolSet.",
            )

        events: list[LiquiditySweepEvent] = []
        swept_pool_ids: set[str] = set()

        for index, candle in enumerate(pool_set.swings.source.candles):
            eligible_pools = tuple(
                pool
                for pool in pool_set.pools
                if (index > pool.confirmation_index and pool.stable_id not in swept_pool_ids)
            )

            buy_candidates = tuple(
                pool
                for pool in eligible_pools
                if self._is_valid_buy_side_sweep(
                    candle,
                    pool,
                )
            )
            sell_candidates = tuple(
                pool
                for pool in eligible_pools
                if self._is_valid_sell_side_sweep(
                    candle,
                    pool,
                )
            )

            if buy_candidates and sell_candidates:
                raise LiquiditySweepDetectionError(
                    LiquiditySweepErrorReason.AMBIGUOUS_SWEEP,
                    "One closed candle simultaneously sweeps buy-side and sell-side liquidity.",
                    candle_index=index,
                )

            selected_pool: LiquidityPool | None = None

            if buy_candidates:
                selected_pool = max(
                    buy_candidates,
                    key=lambda pool: (
                        pool.upper_bound,
                        pool.confirmation_index,
                    ),
                )
            elif sell_candidates:
                selected_pool = min(
                    sell_candidates,
                    key=lambda pool: (
                        pool.lower_bound,
                        -pool.confirmation_index,
                    ),
                )

            if selected_pool is None:
                continue

            event = LiquiditySweepEvent(
                index=index,
                pool=selected_pool,
                candle=candle,
            )
            events.append(event)
            swept_pool_ids.add(selected_pool.stable_id)

        return LiquiditySweepSnapshot(
            pool_set=pool_set,
            policy=self._policy,
            events=tuple(events),
        )

    def evaluate(
        self,
        pool_set: LiquidityPoolSet,
    ) -> LiquiditySweepSnapshot:
        """Compatibility alias for detect()."""

        return self.detect(pool_set)

    def find(
        self,
        pool_set: LiquidityPoolSet,
    ) -> LiquiditySweepSnapshot:
        """Compatibility alias for detect()."""

        return self.detect(pool_set)

    def _is_valid_buy_side_sweep(
        self,
        candle: ClosedCandle,
        pool: LiquidityPool,
    ) -> bool:
        if pool.side != LiquiditySide.BUY_SIDE:
            return False

        penetrated = candle.high > pool.upper_bound + self._policy.minimum_penetration

        if not penetrated:
            return False

        if not self._policy.require_close_back_inside:
            return True

        return candle.close <= pool.upper_bound

    def _is_valid_sell_side_sweep(
        self,
        candle: ClosedCandle,
        pool: LiquidityPool,
    ) -> bool:
        if pool.side != LiquiditySide.SELL_SIDE:
            return False

        penetrated = candle.low < pool.lower_bound - self._policy.minimum_penetration

        if not penetrated:
            return False

        if not self._policy.require_close_back_inside:
            return True

        return candle.close >= pool.lower_bound


def detect_liquidity_sweeps(
    pool_set: LiquidityPoolSet,
    policy: LiquiditySweepPolicy | None = None,
) -> LiquiditySweepSnapshot:
    return LiquiditySweepDetector(policy=policy).detect(pool_set)


LiquiditySweep = LiquiditySweepEvent
LiquiditySweepSet = LiquiditySweepSnapshot
SweepDetector = LiquiditySweepDetector
SweepPolicy = LiquiditySweepPolicy
