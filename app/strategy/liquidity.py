from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TypeAlias

from app.config.constants import TimeframeName
from app.strategy.swings import (
    ConfirmedSwingPoint,
    ConfirmedSwingSet,
    SwingKind,
)

DecimalLike: TypeAlias = Decimal | int | float | str


class LiquiditySide(str, Enum):
    BUY_SIDE = "BUY_SIDE"
    SELL_SIDE = "SELL_SIDE"


class LiquidityDetectionErrorReason(str, Enum):
    INVALID_SWING_SET = "INVALID_SWING_SET"


class LiquidityDetectionError(RuntimeError):
    """Structured liquidity-pool detection failure."""

    def __init__(
        self,
        reason: LiquidityDetectionErrorReason,
        message: str,
    ) -> None:
        self.reason = LiquidityDetectionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Liquidity detection error [{self.reason.value}]: {self.message}")


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


def _side_for_kind(
    kind: SwingKind,
) -> LiquiditySide:
    if kind == SwingKind.HIGH:
        return LiquiditySide.BUY_SIDE

    return LiquiditySide.SELL_SIDE


def _kind_for_side(
    side: LiquiditySide,
) -> SwingKind:
    if side == LiquiditySide.BUY_SIDE:
        return SwingKind.HIGH

    return SwingKind.LOW


def _mean_price(
    points: tuple[ConfirmedSwingPoint, ...] | list[ConfirmedSwingPoint],
) -> Decimal:
    total = sum(
        (point.price for point in points),
        start=Decimal("0"),
    )

    return total / Decimal(len(points))


@dataclass(frozen=True, slots=True)
class LiquidityPoolPolicy:
    """Deterministic equal-high/equal-low clustering policy."""

    price_tolerance: Decimal = Decimal("0.50")
    minimum_touches: int = 2
    maximum_touch_gap: int = 100

    def __post_init__(self) -> None:
        price_tolerance = _non_negative_decimal(
            self.price_tolerance,
            "price_tolerance",
        )
        minimum_touches = _positive_integer(
            self.minimum_touches,
            "minimum_touches",
            100,
        )
        maximum_touch_gap = _positive_integer(
            self.maximum_touch_gap,
            "maximum_touch_gap",
            100_000,
        )

        if minimum_touches < 2:
            raise ValueError("minimum_touches must be at least two.")

        object.__setattr__(
            self,
            "price_tolerance",
            price_tolerance,
        )
        object.__setattr__(
            self,
            "minimum_touches",
            minimum_touches,
        )
        object.__setattr__(
            self,
            "maximum_touch_gap",
            maximum_touch_gap,
        )


@dataclass(frozen=True, slots=True)
class LiquidityPool:
    """One confirmed equal-high or equal-low liquidity pool."""

    side: LiquiditySide
    touches: tuple[ConfirmedSwingPoint, ...]

    def __post_init__(self) -> None:
        try:
            side = LiquiditySide(self.side)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported liquidity side: {self.side}.") from error

        touches = tuple(self.touches)

        if len(touches) < 2:
            raise ValueError("A liquidity pool requires at least two confirmed swing touches.")

        for touch in touches:
            if not isinstance(
                touch,
                ConfirmedSwingPoint,
            ):
                raise ValueError("touches must contain ConfirmedSwingPoint instances.")

        expected_kind = _kind_for_side(side)

        if any(touch.kind != expected_kind for touch in touches):
            raise ValueError(
                f"{side.value} liquidity requires only {expected_kind.value} swing points."
            )

        broker_symbols = {touch.broker_symbol for touch in touches}
        timeframes = {touch.timeframe for touch in touches}

        if len(broker_symbols) != 1:
            raise ValueError("All liquidity-pool touches must use the same broker symbol.")

        if len(timeframes) != 1:
            raise ValueError("All liquidity-pool touches must use the same timeframe.")

        indexes = tuple(touch.index for touch in touches)

        if indexes != tuple(sorted(indexes)):
            raise ValueError("Liquidity-pool touches must be ordered by swing index.")

        if len(indexes) != len(set(indexes)):
            raise ValueError("Duplicate liquidity-pool touches are not allowed.")

        object.__setattr__(self, "side", side)
        object.__setattr__(
            self,
            "touches",
            touches,
        )

    @property
    def source_kind(self) -> SwingKind:
        return _kind_for_side(self.side)

    @property
    def broker_symbol(self) -> str:
        return self.touches[0].broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.touches[0].timeframe

    @property
    def touch_count(self) -> int:
        return len(self.touches)

    @property
    def first_touch(self) -> ConfirmedSwingPoint:
        return self.touches[0]

    @property
    def latest_touch(self) -> ConfirmedSwingPoint:
        return self.touches[-1]

    @property
    def first_index(self) -> int:
        return self.first_touch.index

    @property
    def last_index(self) -> int:
        return self.latest_touch.index

    @property
    def confirmation_index(self) -> int:
        return self.latest_touch.confirmed_by_index

    @property
    def confirmed_at(self) -> datetime:
        return self.latest_touch.confirmed_at

    @property
    def touch_prices(self) -> tuple[Decimal, ...]:
        return tuple(touch.price for touch in self.touches)

    @property
    def level(self) -> Decimal:
        return _mean_price(self.touches)

    @property
    def lower_bound(self) -> Decimal:
        return min(self.touch_prices)

    @property
    def upper_bound(self) -> Decimal:
        return max(self.touch_prices)

    @property
    def price_span(self) -> Decimal:
        return self.upper_bound - self.lower_bound

    @property
    def is_buy_side(self) -> bool:
        return self.side == LiquiditySide.BUY_SIDE

    @property
    def is_sell_side(self) -> bool:
        return self.side == LiquiditySide.SELL_SIDE

    @property
    def stable_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.timeframe.value}:"
            f"{self.side.value}:"
            f"{self.first_index}:"
            f"{self.last_index}"
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

        return abs(self.level - selected_price)


@dataclass(frozen=True, slots=True)
class LiquidityPoolSet:
    """Ordered liquidity pools derived from one swing set."""

    swings: ConfirmedSwingSet
    policy: LiquidityPoolPolicy
    pools: tuple[LiquidityPool, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.swings,
            ConfirmedSwingSet,
        ):
            raise ValueError("swings must be a ConfirmedSwingSet.")

        if not isinstance(
            self.policy,
            LiquidityPoolPolicy,
        ):
            raise ValueError("policy must be a LiquidityPoolPolicy.")

        pools = tuple(self.pools)
        side_order = {
            LiquiditySide.BUY_SIDE: 0,
            LiquiditySide.SELL_SIDE: 1,
        }

        expected_order = tuple(
            sorted(
                pools,
                key=lambda pool: (
                    pool.confirmation_index,
                    pool.first_index,
                    side_order[pool.side],
                ),
            )
        )

        if pools != expected_order:
            raise ValueError("Liquidity pools must be ordered by confirmation index.")

        used_touch_keys: set[tuple[int, SwingKind]] = set()

        for pool in pools:
            if not isinstance(pool, LiquidityPool):
                raise ValueError("pools must contain LiquidityPool instances.")

            if pool.touch_count < self.policy.minimum_touches:
                raise ValueError("Liquidity pool does not meet the minimum-touch requirement.")

            if pool.price_span > self.policy.price_tolerance:
                raise ValueError("Liquidity pool exceeds the configured price tolerance.")

            for previous, current in zip(
                pool.touches,
                pool.touches[1:],
                strict=False,
            ):
                if current.index - previous.index > self.policy.maximum_touch_gap:
                    raise ValueError("Liquidity-pool touch gap exceeds the configured maximum.")

            for touch in pool.touches:
                if touch not in self.swings.points:
                    raise ValueError(
                        "Liquidity-pool touch does not belong to the source swing set."
                    )

                key = (touch.index, touch.kind)

                if key in used_touch_keys:
                    raise ValueError("A confirmed swing cannot belong to multiple liquidity pools.")

                used_touch_keys.add(key)

        object.__setattr__(
            self,
            "pools",
            pools,
        )

    @property
    def broker_symbol(self) -> str:
        return self.swings.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.swings.timeframe

    @property
    def count(self) -> int:
        return len(self.pools)

    @property
    def buy_side(
        self,
    ) -> tuple[LiquidityPool, ...]:
        return tuple(pool for pool in self.pools if pool.side == LiquiditySide.BUY_SIDE)

    @property
    def sell_side(
        self,
    ) -> tuple[LiquidityPool, ...]:
        return tuple(pool for pool in self.pools if pool.side == LiquiditySide.SELL_SIDE)

    @property
    def latest(
        self,
    ) -> LiquidityPool | None:
        if not self.pools:
            return None

        return self.pools[-1]

    @property
    def latest_buy_side(
        self,
    ) -> LiquidityPool | None:
        if not self.buy_side:
            return None

        return self.buy_side[-1]

    @property
    def latest_sell_side(
        self,
    ) -> LiquidityPool | None:
        if not self.sell_side:
            return None

        return self.sell_side[-1]

    def by_side(
        self,
        side: LiquiditySide,
    ) -> tuple[LiquidityPool, ...]:
        try:
            selected_side = LiquiditySide(side)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported liquidity side: {side}.") from error

        if selected_side == LiquiditySide.BUY_SIDE:
            return self.buy_side

        return self.sell_side

    def confirmed_by(
        self,
        index: int,
    ) -> tuple[LiquidityPool, ...]:
        selected_index = _non_negative_integer(
            index,
            "index",
        )

        return tuple(pool for pool in self.pools if pool.confirmation_index == selected_index)

    def nearest_buy_side_above(
        self,
        price: DecimalLike,
    ) -> LiquidityPool | None:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        candidates = tuple(pool for pool in self.buy_side if pool.level >= selected_price)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda pool: (
                pool.level - selected_price,
                pool.confirmation_index,
            ),
        )

    def nearest_sell_side_below(
        self,
        price: DecimalLike,
    ) -> LiquidityPool | None:
        selected_price = _positive_decimal(
            price,
            "price",
        )

        candidates = tuple(pool for pool in self.sell_side if pool.level <= selected_price)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda pool: (
                selected_price - pool.level,
                pool.confirmation_index,
            ),
        )


class LiquidityPoolDetector:
    """
    Pure confirmed-swing liquidity-pool detector.

    One swing point can join only one cluster. When several
    clusters are eligible, the nearest existing price cluster
    is selected deterministically.
    """

    def __init__(
        self,
        policy: LiquidityPoolPolicy | None = None,
    ) -> None:
        selected_policy = policy or LiquidityPoolPolicy()

        if not isinstance(
            selected_policy,
            LiquidityPoolPolicy,
        ):
            raise ValueError("policy must be a LiquidityPoolPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> LiquidityPoolPolicy:
        return self._policy

    def detect(
        self,
        swings: ConfirmedSwingSet,
    ) -> LiquidityPoolSet:
        if not isinstance(
            swings,
            ConfirmedSwingSet,
        ):
            raise LiquidityDetectionError(
                LiquidityDetectionErrorReason.INVALID_SWING_SET,
                "swings must be a ConfirmedSwingSet.",
            )

        pools = [
            *self._cluster_points(
                swings.highs,
                LiquiditySide.BUY_SIDE,
            ),
            *self._cluster_points(
                swings.lows,
                LiquiditySide.SELL_SIDE,
            ),
        ]

        side_order = {
            LiquiditySide.BUY_SIDE: 0,
            LiquiditySide.SELL_SIDE: 1,
        }

        ordered_pools = tuple(
            sorted(
                pools,
                key=lambda pool: (
                    pool.confirmation_index,
                    pool.first_index,
                    side_order[pool.side],
                ),
            )
        )

        return LiquidityPoolSet(
            swings=swings,
            policy=self._policy,
            pools=ordered_pools,
        )

    def evaluate(
        self,
        swings: ConfirmedSwingSet,
    ) -> LiquidityPoolSet:
        """Compatibility alias for detect()."""

        return self.detect(swings)

    def find(
        self,
        swings: ConfirmedSwingSet,
    ) -> LiquidityPoolSet:
        """Compatibility alias for detect()."""

        return self.detect(swings)

    def _cluster_points(
        self,
        points: tuple[ConfirmedSwingPoint, ...],
        side: LiquiditySide,
    ) -> tuple[LiquidityPool, ...]:
        clusters: list[list[ConfirmedSwingPoint]] = []

        for point in points:
            candidates: list[tuple[Decimal, int, int]] = []

            for cluster_index, cluster in enumerate(clusters):
                last_touch = cluster[-1]

                if point.index - last_touch.index > self._policy.maximum_touch_gap:
                    continue

                candidate_prices = [touch.price for touch in cluster]
                candidate_prices.append(point.price)

                price_span = max(candidate_prices) - min(candidate_prices)

                if price_span > self._policy.price_tolerance:
                    continue

                distance = abs(point.price - _mean_price(cluster))

                candidates.append(
                    (
                        distance,
                        cluster[0].index,
                        cluster_index,
                    )
                )

            if candidates:
                selected_cluster_index = min(candidates)[2]
                clusters[selected_cluster_index].append(point)
            else:
                clusters.append([point])

        return tuple(
            LiquidityPool(
                side=side,
                touches=tuple(cluster),
            )
            for cluster in clusters
            if len(cluster) >= self._policy.minimum_touches
        )


def detect_liquidity_pools(
    swings: ConfirmedSwingSet,
    policy: LiquidityPoolPolicy | None = None,
) -> LiquidityPoolSet:
    return LiquidityPoolDetector(policy=policy).detect(swings)


LiquidityPoolCollection = LiquidityPoolSet
LiquidityDetector = LiquidityPoolDetector
LiquidityPolicy = LiquidityPoolPolicy
