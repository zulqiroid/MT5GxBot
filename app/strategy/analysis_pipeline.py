from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TypeVar

from app.config.constants import TimeframeName
from app.market.closed_candle import ClosedCandleSeries
from app.strategy.context_freshness import (
    ContextFreshnessDecision,
)
from app.strategy.directional_permission import (
    DirectionalPermissionDecision,
    DirectionalPermissionDirection,
)
from app.strategy.multi_timeframe_context import (
    MultiTimeframeContextBuilder,
    MultiTimeframeContextBuildError,
    MultiTimeframeContextCounts,
    MultiTimeframeContextPolicy,
    MultiTimeframeContextSnapshot,
)
from app.strategy.strategy_readiness import (
    CompositeStrategyReadinessGate,
    StrategyReadinessBlocker,
    StrategyReadinessDecision,
    StrategyReadinessError,
    StrategyReadinessPolicy,
    StrategyReadinessReason,
    StrategyReadinessStatus,
)

ResultT = TypeVar("ResultT")


class AnalysisPipelineStage(str, Enum):
    CONTEXT = "CONTEXT"
    READINESS = "READINESS"


class AnalysisPipelineErrorReason(str, Enum):
    INVALID_CONTEXT = "INVALID_CONTEXT"
    CONTEXT_BUILD_FAILED = "CONTEXT_BUILD_FAILED"
    READINESS_EVALUATION_FAILED = "READINESS_EVALUATION_FAILED"


class AnalysisPipelineBuildError(RuntimeError):
    """Structured end-to-end analysis pipeline failure."""

    def __init__(
        self,
        reason: AnalysisPipelineErrorReason,
        message: str,
        *,
        stage: AnalysisPipelineStage,
        context_error: (MultiTimeframeContextBuildError | None) = None,
        readiness_error: StrategyReadinessError | None = None,
    ) -> None:
        self.reason = AnalysisPipelineErrorReason(reason)
        self.message = str(message)
        self.stage = AnalysisPipelineStage(stage)
        self.context_error = context_error
        self.readiness_error = readiness_error

        super().__init__(
            "Analysis pipeline error "
            f"[{self.reason.value}] "
            f"[stage={self.stage.value}]: "
            f"{self.message}"
        )


@dataclass(frozen=True, slots=True)
class AnalysisPipelinePolicy:
    """Policies for context building and readiness."""

    context_policy: MultiTimeframeContextPolicy = field(default_factory=MultiTimeframeContextPolicy)
    readiness_policy: StrategyReadinessPolicy = field(default_factory=StrategyReadinessPolicy)

    def __post_init__(self) -> None:
        if not isinstance(
            self.context_policy,
            MultiTimeframeContextPolicy,
        ):
            raise ValueError("context_policy must be a MultiTimeframeContextPolicy.")

        if not isinstance(
            self.readiness_policy,
            StrategyReadinessPolicy,
        ):
            raise ValueError("readiness_policy must be a StrategyReadinessPolicy.")


@dataclass(frozen=True, slots=True)
class AnalysisPipelineSnapshot:
    """
    Complete immutable multi-timeframe analysis result.

    READY means strategy analysis may continue. It does not
    authorize broker-side order submission.
    """

    policy: AnalysisPipelinePolicy
    context: MultiTimeframeContextSnapshot
    readiness: StrategyReadinessDecision

    def __post_init__(self) -> None:
        if not isinstance(
            self.policy,
            AnalysisPipelinePolicy,
        ):
            raise ValueError("policy must be an AnalysisPipelinePolicy.")

        if not isinstance(
            self.context,
            MultiTimeframeContextSnapshot,
        ):
            raise ValueError("context must be a MultiTimeframeContextSnapshot.")

        if not isinstance(
            self.readiness,
            StrategyReadinessDecision,
        ):
            raise ValueError("readiness must be a StrategyReadinessDecision.")

        if self.context.policy != self.policy.context_policy:
            raise ValueError("Context policy does not match the analysis pipeline policy.")

        if self.readiness.policy != self.policy.readiness_policy:
            raise ValueError("Readiness policy does not match the analysis pipeline policy.")

        if self.readiness.context != self.context:
            raise ValueError("Readiness decision does not reference the analysis context.")

    @property
    def broker_symbol(self) -> str:
        return self.context.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.context.observed_at

    @property
    def timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return self.context.timeframes

    @property
    def counts(self) -> MultiTimeframeContextCounts:
        return self.context.counts

    @property
    def freshness(
        self,
    ) -> ContextFreshnessDecision:
        return self.readiness.freshness

    @property
    def directional(
        self,
    ) -> DirectionalPermissionDecision:
        return self.readiness.directional

    @property
    def status(self) -> StrategyReadinessStatus:
        return self.readiness.status

    @property
    def reason(self) -> StrategyReadinessReason:
        return self.readiness.reason

    @property
    def blockers(
        self,
    ) -> tuple[StrategyReadinessBlocker, ...]:
        return self.readiness.blockers

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.readiness.direction

    @property
    def is_ready(self) -> bool:
        return self.readiness.is_ready

    @property
    def is_blocked(self) -> bool:
        return self.readiness.is_blocked

    @property
    def can_analyze_setup(self) -> bool:
        return self.readiness.can_analyze_setup

    @property
    def is_bullish(self) -> bool:
        return self.readiness.is_bullish

    @property
    def is_bearish(self) -> bool:
        return self.readiness.is_bearish

    @property
    def is_fresh(self) -> bool:
        return self.readiness.is_fresh

    @property
    def alignment_score(self) -> Decimal:
        return self.readiness.alignment_score

    @property
    def stale_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return self.readiness.stale_timeframes

    @property
    def stable_id(self) -> str:
        return f"{self.context.stable_id}:ANALYSIS_PIPELINE:{self.status.value}:{self.reason.value}"


class MultiTimeframeAnalysisPipeline:
    """
    Pure end-to-end H4/H1/M15/M5 analysis pipeline.

    This class performs no MT5 initialization and exposes no
    order-submission methods.
    """

    def __init__(
        self,
        policy: AnalysisPipelinePolicy | None = None,
    ) -> None:
        selected_policy = policy or AnalysisPipelinePolicy()

        if not isinstance(
            selected_policy,
            AnalysisPipelinePolicy,
        ):
            raise ValueError("policy must be an AnalysisPipelinePolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> AnalysisPipelinePolicy:
        return self._policy

    def _run_context_stage(
        self,
        operation: Callable[
            [],
            MultiTimeframeContextSnapshot,
        ],
    ) -> MultiTimeframeContextSnapshot:
        try:
            return operation()
        except MultiTimeframeContextBuildError as error:
            raise AnalysisPipelineBuildError(
                AnalysisPipelineErrorReason.CONTEXT_BUILD_FAILED,
                str(error),
                stage=AnalysisPipelineStage.CONTEXT,
                context_error=error,
            ) from error
        except AnalysisPipelineBuildError:
            raise
        except Exception as error:
            raise AnalysisPipelineBuildError(
                AnalysisPipelineErrorReason.CONTEXT_BUILD_FAILED,
                str(error),
                stage=AnalysisPipelineStage.CONTEXT,
            ) from error

    def _run_readiness_stage(
        self,
        operation: Callable[
            [],
            StrategyReadinessDecision,
        ],
    ) -> StrategyReadinessDecision:
        try:
            return operation()
        except StrategyReadinessError as error:
            raise AnalysisPipelineBuildError(
                AnalysisPipelineErrorReason.READINESS_EVALUATION_FAILED,
                str(error),
                stage=AnalysisPipelineStage.READINESS,
                readiness_error=error,
            ) from error
        except AnalysisPipelineBuildError:
            raise
        except Exception as error:
            raise AnalysisPipelineBuildError(
                AnalysisPipelineErrorReason.READINESS_EVALUATION_FAILED,
                str(error),
                stage=AnalysisPipelineStage.READINESS,
            ) from error

    def evaluate_context(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> AnalysisPipelineSnapshot:
        if not isinstance(
            context,
            MultiTimeframeContextSnapshot,
        ):
            raise AnalysisPipelineBuildError(
                AnalysisPipelineErrorReason.INVALID_CONTEXT,
                "context must be a MultiTimeframeContextSnapshot.",
                stage=AnalysisPipelineStage.READINESS,
            )

        if context.policy != self._policy.context_policy:
            raise AnalysisPipelineBuildError(
                AnalysisPipelineErrorReason.INVALID_CONTEXT,
                "Context policy does not match the analysis pipeline policy.",
                stage=AnalysisPipelineStage.READINESS,
            )

        readiness = self._run_readiness_stage(
            lambda: CompositeStrategyReadinessGate(self._policy.readiness_policy).evaluate(context)
        )

        return AnalysisPipelineSnapshot(
            policy=self._policy,
            context=context,
            readiness=readiness,
        )

    def build(
        self,
        series_by_timeframe: Mapping[
            TimeframeName,
            ClosedCandleSeries,
        ],
    ) -> AnalysisPipelineSnapshot:
        context = self._run_context_stage(
            lambda: MultiTimeframeContextBuilder(self._policy.context_policy).build(
                series_by_timeframe
            )
        )

        return self.evaluate_context(context)

    def build_as_of(
        self,
        series_by_timeframe: Mapping[
            TimeframeName,
            ClosedCandleSeries,
        ],
        observed_at: datetime,
    ) -> AnalysisPipelineSnapshot:
        context = self._run_context_stage(
            lambda: MultiTimeframeContextBuilder(self._policy.context_policy).build_as_of(
                series_by_timeframe,
                observed_at,
            )
        )

        return self.evaluate_context(context)

    def build_latest(
        self,
        series_by_timeframe: Mapping[
            TimeframeName,
            ClosedCandleSeries,
        ],
    ) -> AnalysisPipelineSnapshot:
        """Compatibility alias for build()."""

        return self.build(series_by_timeframe)

    def evaluate(
        self,
        series_by_timeframe: Mapping[
            TimeframeName,
            ClosedCandleSeries,
        ],
    ) -> AnalysisPipelineSnapshot:
        """Compatibility alias for build()."""

        return self.build(series_by_timeframe)


def build_analysis_pipeline(
    series_by_timeframe: Mapping[
        TimeframeName,
        ClosedCandleSeries,
    ],
    policy: AnalysisPipelinePolicy | None = None,
) -> AnalysisPipelineSnapshot:
    return MultiTimeframeAnalysisPipeline(policy=policy).build(series_by_timeframe)


AnalysisPipeline = MultiTimeframeAnalysisPipeline
AnalysisPolicy = AnalysisPipelinePolicy
AnalysisSnapshot = AnalysisPipelineSnapshot
GoldAnalysisPipeline = MultiTimeframeAnalysisPipeline
MultiTimeframeAnalysisSnapshot = AnalysisPipelineSnapshot
StrategyAnalysisPipeline = MultiTimeframeAnalysisPipeline
