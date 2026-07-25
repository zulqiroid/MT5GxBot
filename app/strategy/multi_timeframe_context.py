from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandleSeries
from app.strategy.market_structure import (
    MarketStructureBias,
    MarketStructureSnapshot,
)
from app.strategy.strategy_context import (
    StrategyContextBuilder,
    StrategyContextBuildError,
    StrategyContextPolicy,
    StrategyContextSnapshot,
)

GOLD_TIMEFRAME_HIERARCHY = (
    TimeframeName.H4,
    TimeframeName.H1,
    TimeframeName.M15,
    TimeframeName.M5,
)


class MultiTimeframeAlignment(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    MIXED = "MIXED"
    NEUTRAL = "NEUTRAL"


class MultiTimeframeContextErrorReason(str, Enum):
    INVALID_SERIES_MAP = "INVALID_SERIES_MAP"
    MISSING_TIMEFRAME = "MISSING_TIMEFRAME"
    UNEXPECTED_TIMEFRAME = "UNEXPECTED_TIMEFRAME"
    TIMEFRAME_MISMATCH = "TIMEFRAME_MISMATCH"
    SYMBOL_MISMATCH = "SYMBOL_MISMATCH"
    UNSUPPORTED_SYMBOL = "UNSUPPORTED_SYMBOL"
    INVALID_AS_OF_TIME = "INVALID_AS_OF_TIME"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    CONTEXT_BUILD_FAILED = "CONTEXT_BUILD_FAILED"


class MultiTimeframeContextBuildError(RuntimeError):
    """Structured multi-timeframe context build failure."""

    def __init__(
        self,
        reason: MultiTimeframeContextErrorReason,
        message: str,
        *,
        timeframe: TimeframeName | None = None,
        context_error: StrategyContextBuildError | None = None,
    ) -> None:
        self.reason = MultiTimeframeContextErrorReason(reason)
        self.message = str(message)
        self.timeframe = None if timeframe is None else TimeframeName(timeframe)
        self.context_error = context_error

        timeframe_suffix = "" if self.timeframe is None else f" [timeframe={self.timeframe.value}]"

        super().__init__(
            f"Multi-timeframe context error [{self.reason.value}]{timeframe_suffix}: {self.message}"
        )


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


def _require_aware_datetime(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value


def _is_supported_gold_symbol(
    broker_symbol: str,
) -> bool:
    return broker_symbol.strip().upper().startswith("XAUUSD")


def _market_structure_bias(
    snapshot: MarketStructureSnapshot,
) -> MarketStructureBias:
    """
    Resolve the latest bias without requiring a stored
    ``bias`` dataclass field.

    Existing market-structure snapshots derive their state
    from policy plus confirmed events. The compatibility
    checks below support the established public aliases and
    keep this layer independent of one property name.
    """

    if not isinstance(
        snapshot,
        MarketStructureSnapshot,
    ):
        raise ValueError("snapshot must be a MarketStructureSnapshot.")

    for attribute_name in (
        "current_bias",
        "final_bias",
        "latest_bias",
        "bias",
    ):
        value = getattr(
            snapshot,
            attribute_name,
            None,
        )

        if value is not None:
            return MarketStructureBias(value)

    if snapshot.events:
        latest_event = snapshot.events[-1]

        for attribute_name in (
            "bias_after",
            "resulting_bias",
            "new_bias",
            "current_bias",
            "bias",
        ):
            value = getattr(
                latest_event,
                attribute_name,
                None,
            )

            if value is not None:
                return MarketStructureBias(value)

        direction = getattr(
            latest_event,
            "direction",
            None,
        )

        if direction is not None:
            direction_value = str(
                getattr(
                    direction,
                    "value",
                    direction,
                )
            ).upper()

            if direction_value == "BULLISH":
                return MarketStructureBias.BULLISH

            if direction_value == "BEARISH":
                return MarketStructureBias.BEARISH

    return MarketStructureBias(snapshot.policy.initial_bias)


@dataclass(frozen=True, slots=True)
class MultiTimeframeContextPolicy:
    """Policies for the fixed Gold timeframe hierarchy."""

    context_policy: StrategyContextPolicy = field(default_factory=StrategyContextPolicy)
    required_timeframes: tuple[TimeframeName, ...] = GOLD_TIMEFRAME_HIERARCHY
    minimum_aligned_timeframes: int = 3

    def __post_init__(self) -> None:
        if not isinstance(
            self.context_policy,
            StrategyContextPolicy,
        ):
            raise ValueError("context_policy must be a StrategyContextPolicy.")

        required_timeframes = tuple(self.required_timeframes)

        for timeframe in required_timeframes:
            if not isinstance(timeframe, TimeframeName):
                raise ValueError("required_timeframes must contain TimeframeName values.")

        if required_timeframes != (GOLD_TIMEFRAME_HIERARCHY):
            raise ValueError(
                "required_timeframes must preserve the Gold hierarchy H4, H1, M15, M5."
            )

        minimum_aligned_timeframes = _positive_integer(
            self.minimum_aligned_timeframes,
            "minimum_aligned_timeframes",
            len(required_timeframes),
        )

        object.__setattr__(
            self,
            "required_timeframes",
            required_timeframes,
        )
        object.__setattr__(
            self,
            "minimum_aligned_timeframes",
            minimum_aligned_timeframes,
        )


@dataclass(frozen=True, slots=True)
class MultiTimeframeContextCounts:
    """Aggregate counts across all timeframe contexts."""

    context_count: int
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
    total_patterns: int
    total_lifecycle_events: int

    def __post_init__(self) -> None:
        for field_name in (
            "context_count",
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
            "total_patterns",
            "total_lifecycle_events",
        ):
            _non_negative_integer(
                getattr(self, field_name),
                field_name,
            )


@dataclass(frozen=True, slots=True)
class MultiTimeframeContextSnapshot:
    """Immutable H4/H1/M15/M5 strategy context."""

    policy: MultiTimeframeContextPolicy
    observed_at: datetime
    contexts: tuple[StrategyContextSnapshot, ...]
    structure_biases: tuple[
        tuple[TimeframeName, MarketStructureBias],
        ...,
    ] = ()

    def __post_init__(self) -> None:
        if not isinstance(
            self.policy,
            MultiTimeframeContextPolicy,
        ):
            raise ValueError("policy must be a MultiTimeframeContextPolicy.")

        observed_at = _require_aware_datetime(
            self.observed_at,
            "observed_at",
        )
        contexts = tuple(self.contexts)

        for context in contexts:
            if not isinstance(
                context,
                StrategyContextSnapshot,
            ):
                raise ValueError("contexts must contain StrategyContextSnapshot instances.")

        expected_timeframes = self.policy.required_timeframes
        actual_timeframes = tuple(context.timeframe for context in contexts)

        if actual_timeframes != expected_timeframes:
            raise ValueError("Contexts must follow the ordered H4, H1, M15, M5 hierarchy.")

        structure_biases = tuple(self.structure_biases)

        if not structure_biases:
            structure_biases = tuple(
                (
                    context.timeframe,
                    _market_structure_bias(context.market_structure),
                )
                for context in contexts
            )

        normalized_biases: list[
            tuple[
                TimeframeName,
                MarketStructureBias,
            ]
        ] = []

        for item in structure_biases:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("structure_biases must contain (timeframe, bias) pairs.")

            timeframe, bias = item

            try:
                selected_timeframe = TimeframeName(timeframe)
                selected_bias = MarketStructureBias(bias)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "structure_biases contains an unsupported timeframe or bias."
                ) from error

            normalized_biases.append(
                (
                    selected_timeframe,
                    selected_bias,
                )
            )

        bias_timeframes = tuple(timeframe for timeframe, _ in normalized_biases)

        if bias_timeframes != expected_timeframes:
            raise ValueError("Structure biases must follow the ordered H4, H1, M15, M5 hierarchy.")

        broker_symbols = {context.broker_symbol for context in contexts}

        if len(broker_symbols) != 1:
            raise ValueError("All timeframe contexts must use the same broker symbol.")

        for context in contexts:
            if context.policy != self.policy.context_policy:
                raise ValueError(
                    "A timeframe context policy does not match the multi-timeframe policy."
                )

            if context.as_of_time > observed_at:
                raise ValueError("A timeframe context contains a candle after observed_at.")

        object.__setattr__(
            self,
            "observed_at",
            observed_at,
        )
        object.__setattr__(
            self,
            "contexts",
            contexts,
        )
        object.__setattr__(
            self,
            "structure_biases",
            tuple(normalized_biases),
        )

    @property
    def broker_symbol(self) -> str:
        return self.contexts[0].broker_symbol

    @property
    def timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return tuple(context.timeframe for context in self.contexts)

    @property
    def stable_id(self) -> str:
        return f"{self.broker_symbol}:MULTI_TIMEFRAME:{self.observed_at.isoformat()}"

    def context_for(
        self,
        timeframe: TimeframeName,
    ) -> StrategyContextSnapshot:
        try:
            selected_timeframe = TimeframeName(timeframe)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported strategy timeframe: {timeframe}.") from error

        for context in self.contexts:
            if context.timeframe == selected_timeframe:
                return context

        raise ValueError("Timeframe is not part of this multi-timeframe context.")

    @property
    def h4(
        self,
    ) -> StrategyContextSnapshot:
        return self.context_for(TimeframeName.H4)

    @property
    def h1(
        self,
    ) -> StrategyContextSnapshot:
        return self.context_for(TimeframeName.H1)

    @property
    def m15(
        self,
    ) -> StrategyContextSnapshot:
        return self.context_for(TimeframeName.M15)

    @property
    def m5(
        self,
    ) -> StrategyContextSnapshot:
        return self.context_for(TimeframeName.M5)

    @property
    def higher_timeframe_contexts(
        self,
    ) -> tuple[StrategyContextSnapshot, ...]:
        return (self.h4, self.h1)

    @property
    def setup_context(
        self,
    ) -> StrategyContextSnapshot:
        return self.m15

    @property
    def execution_context(
        self,
    ) -> StrategyContextSnapshot:
        return self.m5

    @property
    def bullish_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return tuple(
            timeframe
            for timeframe, bias in self.structure_biases
            if bias == MarketStructureBias.BULLISH
        )

    @property
    def bearish_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return tuple(
            timeframe
            for timeframe, bias in self.structure_biases
            if bias == MarketStructureBias.BEARISH
        )

    @property
    def neutral_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return tuple(
            timeframe
            for timeframe, bias in self.structure_biases
            if bias == MarketStructureBias.NEUTRAL
        )

    @property
    def has_directional_conflict(self) -> bool:
        return bool(self.bullish_timeframes and self.bearish_timeframes)

    @property
    def alignment(
        self,
    ) -> MultiTimeframeAlignment:
        bullish_count = len(self.bullish_timeframes)
        bearish_count = len(self.bearish_timeframes)

        if bullish_count and bearish_count:
            return MultiTimeframeAlignment.MIXED

        if bullish_count >= self.policy.minimum_aligned_timeframes:
            return MultiTimeframeAlignment.BULLISH

        if bearish_count >= self.policy.minimum_aligned_timeframes:
            return MultiTimeframeAlignment.BEARISH

        return MultiTimeframeAlignment.NEUTRAL

    @property
    def aligned_direction(
        self,
    ) -> MultiTimeframeAlignment:
        return self.alignment

    @property
    def alignment_score(self) -> Decimal:
        directional_count = max(
            len(self.bullish_timeframes),
            len(self.bearish_timeframes),
        )

        return Decimal(directional_count) / Decimal(len(self.contexts))

    @property
    def is_fully_aligned(self) -> bool:
        return self.alignment in {
            MultiTimeframeAlignment.BULLISH,
            MultiTimeframeAlignment.BEARISH,
        } and self.alignment_score == Decimal("1")

    @property
    def higher_timeframe_alignment(
        self,
    ) -> MultiTimeframeAlignment:
        biases = dict(self.structure_biases)
        h4_bias = biases[TimeframeName.H4]
        h1_bias = biases[TimeframeName.H1]

        if h4_bias == MarketStructureBias.BULLISH and h1_bias == MarketStructureBias.BULLISH:
            return MultiTimeframeAlignment.BULLISH

        if h4_bias == MarketStructureBias.BEARISH and h1_bias == MarketStructureBias.BEARISH:
            return MultiTimeframeAlignment.BEARISH

        if (
            h4_bias != MarketStructureBias.NEUTRAL
            and h1_bias != MarketStructureBias.NEUTRAL
            and h4_bias != h1_bias
        ):
            return MultiTimeframeAlignment.MIXED

        return MultiTimeframeAlignment.NEUTRAL

    @property
    def higher_timeframes_aligned(self) -> bool:
        return self.higher_timeframe_alignment in {
            MultiTimeframeAlignment.BULLISH,
            MultiTimeframeAlignment.BEARISH,
        }

    def latest_close_for(
        self,
        timeframe: TimeframeName,
    ) -> datetime:
        return self.context_for(timeframe).as_of_time

    def lag_for(
        self,
        timeframe: TimeframeName,
    ) -> timedelta:
        return self.observed_at - self.latest_close_for(timeframe)

    @property
    def counts(self) -> MultiTimeframeContextCounts:
        context_counts = tuple(context.counts for context in self.contexts)

        return MultiTimeframeContextCounts(
            context_count=len(self.contexts),
            swing_points=sum(count.swing_points for count in context_counts),
            structure_breaks=sum(count.structure_breaks for count in context_counts),
            liquidity_pools=sum(count.liquidity_pools for count in context_counts),
            liquidity_sweeps=sum(count.liquidity_sweeps for count in context_counts),
            fair_value_gaps=sum(count.fair_value_gaps for count in context_counts),
            fvg_mitigation_events=sum(count.fvg_mitigation_events for count in context_counts),
            displacement_impulses=sum(count.displacement_impulses for count in context_counts),
            order_blocks=sum(count.order_blocks for count in context_counts),
            order_block_lifecycle_events=sum(
                count.order_block_lifecycle_events for count in context_counts
            ),
            dealing_ranges=sum(count.dealing_ranges for count in context_counts),
            optimal_trade_entry_zones=sum(
                count.optimal_trade_entry_zones for count in context_counts
            ),
            total_patterns=sum(count.total_patterns for count in context_counts),
            total_lifecycle_events=sum(count.total_lifecycle_events for count in context_counts),
        )


class MultiTimeframeContextBuilder:
    """
    Pure H4/H1/M15/M5 strategy-context builder.

    build_as_of() truncates every timeframe independently to
    candles closed on or before one shared observation time.
    """

    def __init__(
        self,
        policy: MultiTimeframeContextPolicy | None = None,
    ) -> None:
        selected_policy = policy or MultiTimeframeContextPolicy()

        if not isinstance(
            selected_policy,
            MultiTimeframeContextPolicy,
        ):
            raise ValueError("policy must be a MultiTimeframeContextPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> MultiTimeframeContextPolicy:
        return self._policy

    def _validate_series_map(
        self,
        series_by_timeframe: Mapping[
            TimeframeName,
            ClosedCandleSeries,
        ],
    ) -> None:
        if not isinstance(series_by_timeframe, Mapping):
            raise MultiTimeframeContextBuildError(
                MultiTimeframeContextErrorReason.INVALID_SERIES_MAP,
                "series_by_timeframe must be a mapping.",
            )

        expected = set(self._policy.required_timeframes)
        actual = set(series_by_timeframe.keys())

        missing = expected - actual

        if missing:
            timeframe = next(item for item in self._policy.required_timeframes if item in missing)
            raise MultiTimeframeContextBuildError(
                MultiTimeframeContextErrorReason.MISSING_TIMEFRAME,
                "Required timeframe series is missing.",
                timeframe=timeframe,
            )

        unexpected = actual - expected

        if unexpected:
            value = next(iter(unexpected))
            raise MultiTimeframeContextBuildError(
                MultiTimeframeContextErrorReason.UNEXPECTED_TIMEFRAME,
                f"Unexpected timeframe key: {value}.",
            )

        broker_symbols: set[str] = set()

        for timeframe in self._policy.required_timeframes:
            series = series_by_timeframe[timeframe]

            if not isinstance(
                series,
                ClosedCandleSeries,
            ):
                raise MultiTimeframeContextBuildError(
                    MultiTimeframeContextErrorReason.INVALID_SERIES_MAP,
                    "Each mapping value must be a ClosedCandleSeries.",
                    timeframe=timeframe,
                )

            if series.timeframe != timeframe:
                raise MultiTimeframeContextBuildError(
                    MultiTimeframeContextErrorReason.TIMEFRAME_MISMATCH,
                    "Series timeframe does not match its mapping key.",
                    timeframe=timeframe,
                )

            if not _is_supported_gold_symbol(series.broker_symbol):
                raise MultiTimeframeContextBuildError(
                    MultiTimeframeContextErrorReason.UNSUPPORTED_SYMBOL,
                    "Only XAUUSD broker symbols are supported.",
                    timeframe=timeframe,
                )

            broker_symbols.add(series.broker_symbol)

        if len(broker_symbols) != 1:
            raise MultiTimeframeContextBuildError(
                MultiTimeframeContextErrorReason.SYMBOL_MISMATCH,
                "All timeframe series must use the same broker symbol.",
            )

    def build(
        self,
        series_by_timeframe: Mapping[
            TimeframeName,
            ClosedCandleSeries,
        ],
    ) -> MultiTimeframeContextSnapshot:
        self._validate_series_map(series_by_timeframe)

        observed_at = max(
            series_by_timeframe[timeframe].candles[-1].close_time
            for timeframe in self._policy.required_timeframes
        )

        return self.build_as_of(
            series_by_timeframe,
            observed_at,
        )

    def build_as_of(
        self,
        series_by_timeframe: Mapping[
            TimeframeName,
            ClosedCandleSeries,
        ],
        observed_at: datetime,
    ) -> MultiTimeframeContextSnapshot:
        self._validate_series_map(series_by_timeframe)

        try:
            selected_observed_at = _require_aware_datetime(
                observed_at,
                "observed_at",
            )
        except ValueError as error:
            raise MultiTimeframeContextBuildError(
                MultiTimeframeContextErrorReason.INVALID_AS_OF_TIME,
                str(error),
            ) from error

        contexts: list[StrategyContextSnapshot] = []
        context_builder = StrategyContextBuilder(self._policy.context_policy)

        for timeframe in self._policy.required_timeframes:
            source = series_by_timeframe[timeframe]
            closed_candles = tuple(
                candle for candle in source.candles if candle.close_time <= selected_observed_at
            )

            if len(closed_candles) < self._policy.context_policy.minimum_history:
                raise MultiTimeframeContextBuildError(
                    MultiTimeframeContextErrorReason.INSUFFICIENT_HISTORY,
                    "Synchronized history contains "
                    f"{len(closed_candles)} candles; "
                    "at least "
                    f"{self._policy.context_policy.minimum_history} "
                    "are required.",
                    timeframe=timeframe,
                )

            synchronized_series = ClosedCandleSeries(
                broker_symbol=source.broker_symbol,
                timeframe=timeframe,
                candles=closed_candles,
            )

            try:
                context = context_builder.build(synchronized_series)
            except StrategyContextBuildError as error:
                raise MultiTimeframeContextBuildError(
                    MultiTimeframeContextErrorReason.CONTEXT_BUILD_FAILED,
                    str(error),
                    timeframe=timeframe,
                    context_error=error,
                ) from error

            contexts.append(context)

        return MultiTimeframeContextSnapshot(
            policy=self._policy,
            observed_at=selected_observed_at,
            contexts=tuple(contexts),
            structure_biases=tuple(
                (
                    context.timeframe,
                    _market_structure_bias(context.market_structure),
                )
                for context in contexts
            ),
        )

    def build_latest(
        self,
        series_by_timeframe: Mapping[
            TimeframeName,
            ClosedCandleSeries,
        ],
    ) -> MultiTimeframeContextSnapshot:
        """Compatibility alias for build()."""

        return self.build(series_by_timeframe)

    def evaluate(
        self,
        series_by_timeframe: Mapping[
            TimeframeName,
            ClosedCandleSeries,
        ],
    ) -> MultiTimeframeContextSnapshot:
        """Compatibility alias for build()."""

        return self.build(series_by_timeframe)


def build_multi_timeframe_context(
    series_by_timeframe: Mapping[
        TimeframeName,
        ClosedCandleSeries,
    ],
    policy: MultiTimeframeContextPolicy | None = None,
) -> MultiTimeframeContextSnapshot:
    return MultiTimeframeContextBuilder(policy=policy).build(series_by_timeframe)


MultiContext = MultiTimeframeContextSnapshot
MultiContextBuilder = MultiTimeframeContextBuilder
MultiContextCounts = MultiTimeframeContextCounts
MultiContextPolicy = MultiTimeframeContextPolicy
MultiTimeframeContext = MultiTimeframeContextSnapshot
TimeframeAlignment = MultiTimeframeAlignment
