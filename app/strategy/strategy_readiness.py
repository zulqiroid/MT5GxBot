from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.config.constants import TimeframeName
from app.strategy.context_freshness import (
    ContextFreshnessDecision,
    ContextFreshnessPolicy,
    MultiTimeframeFreshnessGate,
)
from app.strategy.directional_permission import (
    DirectionalPermissionDecision,
    DirectionalPermissionDirection,
    DirectionalPermissionPolicy,
    MultiTimeframeDirectionalGate,
)
from app.strategy.multi_timeframe_context import (
    MultiTimeframeContextSnapshot,
)


class StrategyReadinessStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class StrategyReadinessBlocker(str, Enum):
    STALE_CONTEXT = "STALE_CONTEXT"
    DIRECTION_BLOCKED = "DIRECTION_BLOCKED"


class StrategyReadinessReason(str, Enum):
    READY = "READY"
    STALE_CONTEXT = "STALE_CONTEXT"
    DIRECTION_BLOCKED = "DIRECTION_BLOCKED"
    STALE_AND_DIRECTION_BLOCKED = "STALE_AND_DIRECTION_BLOCKED"


class StrategyReadinessErrorReason(str, Enum):
    INVALID_CONTEXT = "INVALID_CONTEXT"


class StrategyReadinessError(RuntimeError):
    """Structured composite-readiness evaluation failure."""

    def __init__(
        self,
        reason: StrategyReadinessErrorReason,
        message: str,
    ) -> None:
        self.reason = StrategyReadinessErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Strategy readiness error [{self.reason.value}]: {self.message}")


@dataclass(frozen=True, slots=True)
class StrategyReadinessPolicy:
    """
    Composite strategy-analysis readiness policy.

    This policy does not represent broker authorization,
    risk approval, or permission to submit orders.
    """

    freshness_policy: ContextFreshnessPolicy = field(default_factory=ContextFreshnessPolicy)
    directional_policy: DirectionalPermissionPolicy = field(
        default_factory=DirectionalPermissionPolicy
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.freshness_policy,
            ContextFreshnessPolicy,
        ):
            raise ValueError("freshness_policy must be a ContextFreshnessPolicy.")

        if not isinstance(
            self.directional_policy,
            DirectionalPermissionPolicy,
        ):
            raise ValueError("directional_policy must be a DirectionalPermissionPolicy.")


@dataclass(frozen=True, slots=True)
class _StrategyReadinessEvaluation:
    status: StrategyReadinessStatus
    reason: StrategyReadinessReason
    blockers: tuple[StrategyReadinessBlocker, ...]


def _derive_readiness(
    freshness: ContextFreshnessDecision,
    directional: DirectionalPermissionDecision,
) -> _StrategyReadinessEvaluation:
    blockers: list[StrategyReadinessBlocker] = []

    if freshness.is_blocked:
        blockers.append(StrategyReadinessBlocker.STALE_CONTEXT)

    if directional.is_blocked:
        blockers.append(StrategyReadinessBlocker.DIRECTION_BLOCKED)

    blocker_tuple = tuple(blockers)

    if not blocker_tuple:
        return _StrategyReadinessEvaluation(
            status=StrategyReadinessStatus.READY,
            reason=StrategyReadinessReason.READY,
            blockers=(),
        )

    if blocker_tuple == (StrategyReadinessBlocker.STALE_CONTEXT,):
        reason = StrategyReadinessReason.STALE_CONTEXT
    elif blocker_tuple == (StrategyReadinessBlocker.DIRECTION_BLOCKED,):
        reason = StrategyReadinessReason.DIRECTION_BLOCKED
    else:
        reason = StrategyReadinessReason.STALE_AND_DIRECTION_BLOCKED

    return _StrategyReadinessEvaluation(
        status=StrategyReadinessStatus.BLOCKED,
        reason=reason,
        blockers=blocker_tuple,
    )


@dataclass(frozen=True, slots=True)
class StrategyReadinessDecision:
    """One validated composite strategy-readiness result."""

    context: MultiTimeframeContextSnapshot
    policy: StrategyReadinessPolicy
    freshness: ContextFreshnessDecision
    directional: DirectionalPermissionDecision
    status: StrategyReadinessStatus
    reason: StrategyReadinessReason
    blockers: tuple[StrategyReadinessBlocker, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.context,
            MultiTimeframeContextSnapshot,
        ):
            raise ValueError("context must be a MultiTimeframeContextSnapshot.")

        if not isinstance(
            self.policy,
            StrategyReadinessPolicy,
        ):
            raise ValueError("policy must be a StrategyReadinessPolicy.")

        if not isinstance(
            self.freshness,
            ContextFreshnessDecision,
        ):
            raise ValueError("freshness must be a ContextFreshnessDecision.")

        if not isinstance(
            self.directional,
            DirectionalPermissionDecision,
        ):
            raise ValueError("directional must be a DirectionalPermissionDecision.")

        try:
            status = StrategyReadinessStatus(self.status)
            reason = StrategyReadinessReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported strategy readiness status or reason.") from error

        blockers = tuple(self.blockers)

        normalized_blockers: list[StrategyReadinessBlocker] = []

        for blocker in blockers:
            try:
                normalized_blockers.append(StrategyReadinessBlocker(blocker))
            except (TypeError, ValueError) as error:
                raise ValueError(f"Unsupported strategy readiness blocker: {blocker}.") from error

        blocker_tuple = tuple(normalized_blockers)

        if len(set(blocker_tuple)) != len(blocker_tuple):
            raise ValueError("Strategy readiness blockers cannot contain duplicates.")

        if self.freshness.context != self.context:
            raise ValueError("Freshness decision does not reference the readiness context.")

        if self.directional.context != self.context:
            raise ValueError("Directional decision does not reference the readiness context.")

        if self.freshness.policy != self.policy.freshness_policy:
            raise ValueError("Freshness decision policy does not match the readiness policy.")

        if self.directional.policy != self.policy.directional_policy:
            raise ValueError("Directional decision policy does not match the readiness policy.")

        expected = _derive_readiness(
            self.freshness,
            self.directional,
        )

        supplied = _StrategyReadinessEvaluation(
            status=status,
            reason=reason,
            blockers=blocker_tuple,
        )

        if supplied != expected:
            raise ValueError("Strategy readiness result does not match its component decisions.")

        object.__setattr__(
            self,
            "status",
            status,
        )
        object.__setattr__(
            self,
            "reason",
            reason,
        )
        object.__setattr__(
            self,
            "blockers",
            blocker_tuple,
        )

    @property
    def broker_symbol(self) -> str:
        return self.context.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.context.observed_at

    @property
    def is_ready(self) -> bool:
        return self.status == StrategyReadinessStatus.READY

    @property
    def is_blocked(self) -> bool:
        return not self.is_ready

    @property
    def can_analyze_setup(self) -> bool:
        return self.is_ready

    @property
    def has_stale_context(self) -> bool:
        return StrategyReadinessBlocker.STALE_CONTEXT in self.blockers

    @property
    def has_directional_blocker(self) -> bool:
        return StrategyReadinessBlocker.DIRECTION_BLOCKED in self.blockers

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def is_fresh(self) -> bool:
        return self.freshness.is_ready

    @property
    def is_directionally_allowed(self) -> bool:
        return self.directional.is_allowed

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.directional.direction

    @property
    def has_direction(self) -> bool:
        return self.directional.has_direction

    @property
    def is_bullish(self) -> bool:
        return self.directional.is_bullish

    @property
    def is_bearish(self) -> bool:
        return self.directional.is_bearish

    @property
    def alignment_score(self) -> Decimal:
        return self.directional.alignment_score

    @property
    def stale_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return self.freshness.stale_timeframes

    @property
    def fresh_timeframes(
        self,
    ) -> tuple[TimeframeName, ...]:
        return self.freshness.fresh_timeframes

    @property
    def directional_reason(self):
        return self.directional.reason

    @property
    def freshness_reason(self):
        return self.freshness.reason

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.context.stable_id}:"
            f"STRATEGY_READINESS:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class CompositeStrategyReadinessGate:
    """
    Pure composite strategy-analysis readiness gate.

    READY does not grant broker-side trading permission.
    """

    def __init__(
        self,
        policy: StrategyReadinessPolicy | None = None,
    ) -> None:
        selected_policy = policy or StrategyReadinessPolicy()

        if not isinstance(
            selected_policy,
            StrategyReadinessPolicy,
        ):
            raise ValueError("policy must be a StrategyReadinessPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> StrategyReadinessPolicy:
        return self._policy

    def evaluate(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> StrategyReadinessDecision:
        if not isinstance(
            context,
            MultiTimeframeContextSnapshot,
        ):
            raise StrategyReadinessError(
                StrategyReadinessErrorReason.INVALID_CONTEXT,
                "context must be a MultiTimeframeContextSnapshot.",
            )

        freshness = MultiTimeframeFreshnessGate(self._policy.freshness_policy).evaluate(context)
        directional = MultiTimeframeDirectionalGate(self._policy.directional_policy).evaluate(
            context
        )
        evaluation = _derive_readiness(
            freshness,
            directional,
        )

        return StrategyReadinessDecision(
            context=context,
            policy=self._policy,
            freshness=freshness,
            directional=directional,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
        )

    def check(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> StrategyReadinessDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(context)

    def decide(
        self,
        context: MultiTimeframeContextSnapshot,
    ) -> StrategyReadinessDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(context)


def evaluate_strategy_readiness(
    context: MultiTimeframeContextSnapshot,
    policy: StrategyReadinessPolicy | None = None,
) -> StrategyReadinessDecision:
    return CompositeStrategyReadinessGate(policy=policy).evaluate(context)


ReadinessBlocker = StrategyReadinessBlocker
ReadinessDecision = StrategyReadinessDecision
ReadinessGate = CompositeStrategyReadinessGate
ReadinessPolicy = StrategyReadinessPolicy
ReadinessReason = StrategyReadinessReason
ReadinessStatus = StrategyReadinessStatus
StrategyAnalysisReadinessGate = CompositeStrategyReadinessGate
