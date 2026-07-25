from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TypeVar

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.strategy.dealing_ranges import (
    DealingRange,
    DealingRangeDetector,
    DealingRangePolicy,
    DealingRangeSet,
)
from app.strategy.displacement import (
    DisplacementDetector,
    DisplacementImpulse,
    DisplacementPolicy,
    DisplacementSet,
)
from app.strategy.fair_value_gaps import (
    FairValueGap,
    FairValueGapDetector,
    FairValueGapPolicy,
    FairValueGapSet,
)
from app.strategy.fvg_mitigation import (
    FairValueGapMitigationPolicy,
    FairValueGapMitigationSnapshot,
    FairValueGapMitigationTracker,
)
from app.strategy.liquidity import (
    LiquidityPool,
    LiquidityPoolDetector,
    LiquidityPoolPolicy,
    LiquidityPoolSet,
)
from app.strategy.liquidity_sweeps import (
    LiquiditySweepDetector,
    LiquiditySweepEvent,
    LiquiditySweepPolicy,
    LiquiditySweepSnapshot,
)
from app.strategy.market_structure import (
    MarketStructureAnalyzer,
    MarketStructurePolicy,
    MarketStructureSnapshot,
)
from app.strategy.order_block_lifecycle import (
    OrderBlockLifecyclePolicy,
    OrderBlockLifecycleSnapshot,
    OrderBlockLifecycleTracker,
)
from app.strategy.order_blocks import (
    OrderBlock,
    OrderBlockDetector,
    OrderBlockPolicy,
    OrderBlockSet,
)
from app.strategy.ote_zones import (
    OptimalTradeEntryDetector,
    OptimalTradeEntryPolicy,
    OptimalTradeEntryZone,
    OptimalTradeEntryZoneSet,
)
from app.strategy.swings import (
    ConfirmedSwingDetector,
    ConfirmedSwingPoint,
    ConfirmedSwingSet,
    SwingDetectionPolicy,
)

ResultT = TypeVar("ResultT")


class StrategyContextStage(str, Enum):
    SWINGS = "SWINGS"
    MARKET_STRUCTURE = "MARKET_STRUCTURE"
    LIQUIDITY_POOLS = "LIQUIDITY_POOLS"
    LIQUIDITY_SWEEPS = "LIQUIDITY_SWEEPS"
    FAIR_VALUE_GAPS = "FAIR_VALUE_GAPS"
    FVG_MITIGATION = "FVG_MITIGATION"
    DISPLACEMENT = "DISPLACEMENT"
    ORDER_BLOCKS = "ORDER_BLOCKS"
    ORDER_BLOCK_LIFECYCLE = "ORDER_BLOCK_LIFECYCLE"
    DEALING_RANGES = "DEALING_RANGES"
    OPTIMAL_TRADE_ENTRY = "OPTIMAL_TRADE_ENTRY"


class StrategyContextErrorReason(str, Enum):
    INVALID_SERIES = "INVALID_SERIES"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INVALID_AS_OF_INDEX = "INVALID_AS_OF_INDEX"
    PIPELINE_STAGE_FAILED = "PIPELINE_STAGE_FAILED"


class StrategyContextBuildError(RuntimeError):
    """Structured single-timeframe context build failure."""

    def __init__(
        self,
        reason: StrategyContextErrorReason,
        message: str,
        *,
        stage: StrategyContextStage | None = None,
    ) -> None:
        self.reason = StrategyContextErrorReason(reason)
        self.message = str(message)
        self.stage = None if stage is None else StrategyContextStage(stage)

        stage_suffix = "" if self.stage is None else f" [stage={self.stage.value}]"

        super().__init__(
            f"Strategy context error [{self.reason.value}]{stage_suffix}: {self.message}"
        )


def _require_policy_type(
    value: object,
    expected_type: type,
    field_name: str,
) -> None:
    if not isinstance(value, expected_type):
        raise ValueError(f"{field_name} must be a {expected_type.__name__}.")


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


@dataclass(frozen=True, slots=True)
class StrategyContextPolicy:
    """Policies for the complete single-timeframe pipeline."""

    swing_policy: SwingDetectionPolicy = field(default_factory=SwingDetectionPolicy)
    market_structure_policy: MarketStructurePolicy = field(default_factory=MarketStructurePolicy)
    liquidity_pool_policy: LiquidityPoolPolicy = field(default_factory=LiquidityPoolPolicy)
    liquidity_sweep_policy: LiquiditySweepPolicy = field(default_factory=LiquiditySweepPolicy)
    fair_value_gap_policy: FairValueGapPolicy = field(default_factory=FairValueGapPolicy)
    fvg_mitigation_policy: FairValueGapMitigationPolicy = field(
        default_factory=FairValueGapMitigationPolicy
    )
    displacement_policy: DisplacementPolicy = field(default_factory=DisplacementPolicy)
    order_block_policy: OrderBlockPolicy = field(default_factory=OrderBlockPolicy)
    order_block_lifecycle_policy: OrderBlockLifecyclePolicy = field(
        default_factory=OrderBlockLifecyclePolicy
    )
    dealing_range_policy: DealingRangePolicy = field(default_factory=DealingRangePolicy)
    optimal_trade_entry_policy: OptimalTradeEntryPolicy = field(
        default_factory=OptimalTradeEntryPolicy
    )

    def __post_init__(self) -> None:
        requirements = (
            (
                self.swing_policy,
                SwingDetectionPolicy,
                "swing_policy",
            ),
            (
                self.market_structure_policy,
                MarketStructurePolicy,
                "market_structure_policy",
            ),
            (
                self.liquidity_pool_policy,
                LiquidityPoolPolicy,
                "liquidity_pool_policy",
            ),
            (
                self.liquidity_sweep_policy,
                LiquiditySweepPolicy,
                "liquidity_sweep_policy",
            ),
            (
                self.fair_value_gap_policy,
                FairValueGapPolicy,
                "fair_value_gap_policy",
            ),
            (
                self.fvg_mitigation_policy,
                FairValueGapMitigationPolicy,
                "fvg_mitigation_policy",
            ),
            (
                self.displacement_policy,
                DisplacementPolicy,
                "displacement_policy",
            ),
            (
                self.order_block_policy,
                OrderBlockPolicy,
                "order_block_policy",
            ),
            (
                self.order_block_lifecycle_policy,
                OrderBlockLifecyclePolicy,
                "order_block_lifecycle_policy",
            ),
            (
                self.dealing_range_policy,
                DealingRangePolicy,
                "dealing_range_policy",
            ),
            (
                self.optimal_trade_entry_policy,
                OptimalTradeEntryPolicy,
                "optimal_trade_entry_policy",
            ),
        )

        for value, expected_type, field_name in requirements:
            _require_policy_type(
                value,
                expected_type,
                field_name,
            )

    @property
    def minimum_history(self) -> int:
        swing_history = self.swing_policy.left_bars + self.swing_policy.right_bars + 1

        return max(
            3,
            swing_history,
            self.displacement_policy.minimum_history,
        )


@dataclass(frozen=True, slots=True)
class StrategyContextCounts:
    """Stable count summary for one context snapshot."""

    swing_points: int
    structure_breaks: int
    liquidity_pools: int
    liquidity_sweeps: int
    fair_value_gaps: int
    fvg_mitigation_events: int
    displacement_impulses: int
    order_blocks: int
    order_block_lifecycle_events: int
    dealing_ranges: int
    optimal_trade_entry_zones: int

    def __post_init__(self) -> None:
        for field_name in (
            "swing_points",
            "structure_breaks",
            "liquidity_pools",
            "liquidity_sweeps",
            "fair_value_gaps",
            "fvg_mitigation_events",
            "displacement_impulses",
            "order_blocks",
            "order_block_lifecycle_events",
            "dealing_ranges",
            "optimal_trade_entry_zones",
        ):
            value = getattr(self, field_name)
            _non_negative_integer(value, field_name)

    @property
    def total_patterns(self) -> int:
        return (
            self.swing_points
            + self.structure_breaks
            + self.liquidity_pools
            + self.liquidity_sweeps
            + self.fair_value_gaps
            + self.displacement_impulses
            + self.order_blocks
            + self.dealing_ranges
            + self.optimal_trade_entry_zones
        )

    @property
    def total_lifecycle_events(self) -> int:
        return self.fvg_mitigation_events + self.order_block_lifecycle_events


@dataclass(frozen=True, slots=True)
class StrategyContextSnapshot:
    """Complete immutable strategy context for one series."""

    source: ClosedCandleSeries
    policy: StrategyContextPolicy
    swings: ConfirmedSwingSet
    market_structure: MarketStructureSnapshot
    liquidity_pools: LiquidityPoolSet
    liquidity_sweeps: LiquiditySweepSnapshot
    fair_value_gaps: FairValueGapSet
    fvg_mitigation: FairValueGapMitigationSnapshot
    displacements: DisplacementSet
    order_blocks: OrderBlockSet
    order_block_lifecycle: OrderBlockLifecycleSnapshot
    dealing_ranges: DealingRangeSet
    optimal_trade_entry_zones: OptimalTradeEntryZoneSet

    def __post_init__(self) -> None:
        requirements = (
            (
                self.source,
                ClosedCandleSeries,
                "source",
            ),
            (
                self.policy,
                StrategyContextPolicy,
                "policy",
            ),
            (
                self.swings,
                ConfirmedSwingSet,
                "swings",
            ),
            (
                self.market_structure,
                MarketStructureSnapshot,
                "market_structure",
            ),
            (
                self.liquidity_pools,
                LiquidityPoolSet,
                "liquidity_pools",
            ),
            (
                self.liquidity_sweeps,
                LiquiditySweepSnapshot,
                "liquidity_sweeps",
            ),
            (
                self.fair_value_gaps,
                FairValueGapSet,
                "fair_value_gaps",
            ),
            (
                self.fvg_mitigation,
                FairValueGapMitigationSnapshot,
                "fvg_mitigation",
            ),
            (
                self.displacements,
                DisplacementSet,
                "displacements",
            ),
            (
                self.order_blocks,
                OrderBlockSet,
                "order_blocks",
            ),
            (
                self.order_block_lifecycle,
                OrderBlockLifecycleSnapshot,
                "order_block_lifecycle",
            ),
            (
                self.dealing_ranges,
                DealingRangeSet,
                "dealing_ranges",
            ),
            (
                self.optimal_trade_entry_zones,
                OptimalTradeEntryZoneSet,
                "optimal_trade_entry_zones",
            ),
        )

        for value, expected_type, field_name in requirements:
            if not isinstance(value, expected_type):
                raise ValueError(f"{field_name} must be a {expected_type.__name__}.")

        if self.source.count < self.policy.minimum_history:
            raise ValueError(
                "Strategy context source does not satisfy the configured minimum history."
            )

        components = (
            ("swings", self.swings),
            ("market_structure", self.market_structure),
            ("liquidity_pools", self.liquidity_pools),
            ("liquidity_sweeps", self.liquidity_sweeps),
            ("fair_value_gaps", self.fair_value_gaps),
            ("fvg_mitigation", self.fvg_mitigation),
            ("displacements", self.displacements),
            ("order_blocks", self.order_blocks),
            (
                "order_block_lifecycle",
                self.order_block_lifecycle,
            ),
            ("dealing_ranges", self.dealing_ranges),
            (
                "optimal_trade_entry_zones",
                self.optimal_trade_entry_zones,
            ),
        )

        for component_name, component in components:
            if component.broker_symbol != self.source.broker_symbol:
                raise ValueError(
                    f"{component_name} broker symbol does not match the context source."
                )

            if component.timeframe != self.source.timeframe:
                raise ValueError(f"{component_name} timeframe does not match the context source.")

        if self.swings.source != self.source:
            raise ValueError("Swing source does not match the context source.")

        structure_swings = getattr(
            self.market_structure,
            "swings",
            self.swings,
        )

        if structure_swings != self.swings:
            raise ValueError("Market structure does not reference the context swing set.")

        if self.liquidity_pools.swings != self.swings:
            raise ValueError("Liquidity pools do not reference the context swing set.")

        if self.liquidity_sweeps.pool_set != self.liquidity_pools:
            raise ValueError("Liquidity sweeps do not reference the context liquidity pools.")

        if self.fair_value_gaps.source != self.source:
            raise ValueError("Fair value gap source does not match the context source.")

        if self.fvg_mitigation.gap_set != self.fair_value_gaps:
            raise ValueError("FVG mitigation does not reference the context fair value gaps.")

        if self.displacements.source != self.source:
            raise ValueError("Displacement source does not match the context source.")

        if self.order_blocks.displacements != self.displacements:
            raise ValueError("Order Blocks do not reference the context displacement set.")

        if self.order_block_lifecycle.order_blocks != self.order_blocks:
            raise ValueError("Order Block lifecycle does not reference the context Order Blocks.")

        if self.dealing_ranges.swings != self.swings:
            raise ValueError("Dealing ranges do not reference the context swing set.")

        if self.optimal_trade_entry_zones.dealing_ranges != self.dealing_ranges:
            raise ValueError("OTE zones do not reference the context dealing ranges.")

        policy_links = (
            (
                self.swings.policy,
                self.policy.swing_policy,
                "swing",
            ),
            (
                self.market_structure.policy,
                self.policy.market_structure_policy,
                "market structure",
            ),
            (
                self.liquidity_pools.policy,
                self.policy.liquidity_pool_policy,
                "liquidity pool",
            ),
            (
                self.liquidity_sweeps.policy,
                self.policy.liquidity_sweep_policy,
                "liquidity sweep",
            ),
            (
                self.fair_value_gaps.policy,
                self.policy.fair_value_gap_policy,
                "fair value gap",
            ),
            (
                self.fvg_mitigation.policy,
                self.policy.fvg_mitigation_policy,
                "FVG mitigation",
            ),
            (
                self.displacements.policy,
                self.policy.displacement_policy,
                "displacement",
            ),
            (
                self.order_blocks.policy,
                self.policy.order_block_policy,
                "Order Block",
            ),
            (
                self.order_block_lifecycle.policy,
                self.policy.order_block_lifecycle_policy,
                "Order Block lifecycle",
            ),
            (
                self.dealing_ranges.policy,
                self.policy.dealing_range_policy,
                "dealing range",
            ),
            (
                self.optimal_trade_entry_zones.policy,
                self.policy.optimal_trade_entry_policy,
                "OTE",
            ),
        )

        for actual_policy, expected_policy, name in policy_links:
            if actual_policy != expected_policy:
                raise ValueError(f"{name} policy does not match the context policy.")

    @property
    def broker_symbol(self) -> str:
        return self.source.broker_symbol

    @property
    def timeframe(self) -> TimeframeName:
        return self.source.timeframe

    @property
    def as_of_index(self) -> int:
        return self.source.count - 1

    @property
    def as_of_time(self) -> datetime:
        return self.last_closed_candle.close_time

    @property
    def last_closed_candle(self) -> ClosedCandle:
        return self.source.candles[-1]

    @property
    def last_close_price(self) -> Decimal:
        return self.last_closed_candle.close

    @property
    def stable_id(self) -> str:
        return f"{self.broker_symbol}:{self.timeframe.value}:CONTEXT:{self.as_of_index}"

    @property
    def counts(self) -> StrategyContextCounts:
        return StrategyContextCounts(
            swing_points=len(self.swings.points),
            structure_breaks=len(self.market_structure.events),
            liquidity_pools=len(self.liquidity_pools.pools),
            liquidity_sweeps=len(self.liquidity_sweeps.events),
            fair_value_gaps=len(self.fair_value_gaps.gaps),
            fvg_mitigation_events=len(self.fvg_mitigation.events),
            displacement_impulses=len(self.displacements.impulses),
            order_blocks=len(self.order_blocks.blocks),
            order_block_lifecycle_events=len(self.order_block_lifecycle.events),
            dealing_ranges=len(self.dealing_ranges.ranges),
            optimal_trade_entry_zones=len(self.optimal_trade_entry_zones.zones),
        )

    @property
    def active_fair_value_gaps(
        self,
    ) -> tuple[FairValueGap, ...]:
        return self.fvg_mitigation.active_gaps

    @property
    def active_order_blocks(
        self,
    ) -> tuple[OrderBlock, ...]:
        return self.order_block_lifecycle.active_blocks

    @property
    def unswept_liquidity_pools(
        self,
    ) -> tuple[LiquidityPool, ...]:
        return self.liquidity_sweeps.unswept_pools

    @property
    def latest_swing(
        self,
    ) -> ConfirmedSwingPoint | None:
        if not self.swings.points:
            return None

        return self.swings.points[-1]

    @property
    def latest_liquidity_sweep(
        self,
    ) -> LiquiditySweepEvent | None:
        return self.liquidity_sweeps.latest

    @property
    def latest_fair_value_gap(
        self,
    ) -> FairValueGap | None:
        return self.fair_value_gaps.latest

    @property
    def latest_displacement(
        self,
    ) -> DisplacementImpulse | None:
        return self.displacements.latest

    @property
    def latest_order_block(
        self,
    ) -> OrderBlock | None:
        return self.order_blocks.latest

    @property
    def latest_dealing_range(
        self,
    ) -> DealingRange | None:
        return self.dealing_ranges.latest

    @property
    def latest_optimal_trade_entry_zone(
        self,
    ) -> OptimalTradeEntryZone | None:
        return self.optimal_trade_entry_zones.latest


class StrategyContextBuilder:
    """
    Pure single-timeframe strategy-context builder.

    build_as_of() reconstructs the complete pipeline from a
    truncated closed-candle series, preventing lookahead.
    """

    def __init__(
        self,
        policy: StrategyContextPolicy | None = None,
    ) -> None:
        selected_policy = policy or StrategyContextPolicy()

        if not isinstance(
            selected_policy,
            StrategyContextPolicy,
        ):
            raise ValueError("policy must be a StrategyContextPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> StrategyContextPolicy:
        return self._policy

    def _run_stage(
        self,
        stage: StrategyContextStage,
        operation: Callable[[], ResultT],
    ) -> ResultT:
        try:
            return operation()
        except StrategyContextBuildError:
            raise
        except Exception as error:
            raise StrategyContextBuildError(
                StrategyContextErrorReason.PIPELINE_STAGE_FAILED,
                str(error),
                stage=stage,
            ) from error

    def build(
        self,
        series: ClosedCandleSeries,
    ) -> StrategyContextSnapshot:
        if not isinstance(
            series,
            ClosedCandleSeries,
        ):
            raise StrategyContextBuildError(
                StrategyContextErrorReason.INVALID_SERIES,
                "series must be a ClosedCandleSeries.",
            )

        if series.count < self._policy.minimum_history:
            raise StrategyContextBuildError(
                StrategyContextErrorReason.INSUFFICIENT_HISTORY,
                "At least "
                f"{self._policy.minimum_history} closed "
                "candles are required; received "
                f"{series.count}.",
            )

        swings = self._run_stage(
            StrategyContextStage.SWINGS,
            lambda: ConfirmedSwingDetector(self._policy.swing_policy).detect(series),
        )

        market_structure = self._run_stage(
            StrategyContextStage.MARKET_STRUCTURE,
            lambda: MarketStructureAnalyzer(self._policy.market_structure_policy).analyze(swings),
        )

        liquidity_pools = self._run_stage(
            StrategyContextStage.LIQUIDITY_POOLS,
            lambda: LiquidityPoolDetector(self._policy.liquidity_pool_policy).detect(swings),
        )

        liquidity_sweeps = self._run_stage(
            StrategyContextStage.LIQUIDITY_SWEEPS,
            lambda: LiquiditySweepDetector(self._policy.liquidity_sweep_policy).detect(
                liquidity_pools
            ),
        )

        fair_value_gaps = self._run_stage(
            StrategyContextStage.FAIR_VALUE_GAPS,
            lambda: FairValueGapDetector(self._policy.fair_value_gap_policy).detect(series),
        )

        fvg_mitigation = self._run_stage(
            StrategyContextStage.FVG_MITIGATION,
            lambda: FairValueGapMitigationTracker(self._policy.fvg_mitigation_policy).track(
                fair_value_gaps
            ),
        )

        displacements = self._run_stage(
            StrategyContextStage.DISPLACEMENT,
            lambda: DisplacementDetector(self._policy.displacement_policy).detect(series),
        )

        order_blocks = self._run_stage(
            StrategyContextStage.ORDER_BLOCKS,
            lambda: OrderBlockDetector(self._policy.order_block_policy).detect(displacements),
        )

        order_block_lifecycle = self._run_stage(
            StrategyContextStage.ORDER_BLOCK_LIFECYCLE,
            lambda: OrderBlockLifecycleTracker(self._policy.order_block_lifecycle_policy).track(
                order_blocks
            ),
        )

        dealing_ranges = self._run_stage(
            StrategyContextStage.DEALING_RANGES,
            lambda: DealingRangeDetector(self._policy.dealing_range_policy).detect(swings),
        )

        optimal_trade_entry_zones = self._run_stage(
            StrategyContextStage.OPTIMAL_TRADE_ENTRY,
            lambda: OptimalTradeEntryDetector(self._policy.optimal_trade_entry_policy).detect(
                dealing_ranges
            ),
        )

        return StrategyContextSnapshot(
            source=series,
            policy=self._policy,
            swings=swings,
            market_structure=market_structure,
            liquidity_pools=liquidity_pools,
            liquidity_sweeps=liquidity_sweeps,
            fair_value_gaps=fair_value_gaps,
            fvg_mitigation=fvg_mitigation,
            displacements=displacements,
            order_blocks=order_blocks,
            order_block_lifecycle=(order_block_lifecycle),
            dealing_ranges=dealing_ranges,
            optimal_trade_entry_zones=(optimal_trade_entry_zones),
        )

    def build_as_of(
        self,
        series: ClosedCandleSeries,
        index: int,
    ) -> StrategyContextSnapshot:
        if not isinstance(
            series,
            ClosedCandleSeries,
        ):
            raise StrategyContextBuildError(
                StrategyContextErrorReason.INVALID_SERIES,
                "series must be a ClosedCandleSeries.",
            )

        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= series.count
        ):
            raise StrategyContextBuildError(
                StrategyContextErrorReason.INVALID_AS_OF_INDEX,
                f"index must identify an existing closed candle; received {index}.",
            )

        truncated = ClosedCandleSeries(
            broker_symbol=series.broker_symbol,
            timeframe=series.timeframe,
            candles=series.candles[: index + 1],
        )

        return self.build(truncated)

    def build_latest(
        self,
        series: ClosedCandleSeries,
    ) -> StrategyContextSnapshot:
        """Compatibility alias for build()."""

        return self.build(series)

    def evaluate(
        self,
        series: ClosedCandleSeries,
    ) -> StrategyContextSnapshot:
        """Compatibility alias for build()."""

        return self.build(series)


def build_strategy_context(
    series: ClosedCandleSeries,
    policy: StrategyContextPolicy | None = None,
) -> StrategyContextSnapshot:
    return StrategyContextBuilder(policy=policy).build(series)


ContextBuilder = StrategyContextBuilder
ContextCounts = StrategyContextCounts
ContextPolicy = StrategyContextPolicy
MarketContext = StrategyContextSnapshot
StrategyContext = StrategyContextSnapshot
StrategySnapshot = StrategyContextSnapshot
