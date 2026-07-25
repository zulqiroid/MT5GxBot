from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.config.constants import TimeframeName
from app.strategy.analysis_pipeline import (
    AnalysisPipelineSnapshot,
)
from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.strategy_context import (
    StrategyContextCounts,
)


class SetupQualificationStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    BLOCKED = "BLOCKED"


class SetupQualificationBlocker(str, Enum):
    STALE_CONTEXT = "STALE_CONTEXT"
    DIRECTION_UNRESOLVED = "DIRECTION_UNRESOLVED"
    ANALYSIS_NOT_READY = "ANALYSIS_NOT_READY"
    SETUP_TIMEFRAME_NEUTRAL = "SETUP_TIMEFRAME_NEUTRAL"
    SETUP_TIMEFRAME_CONFLICT = "SETUP_TIMEFRAME_CONFLICT"
    EXECUTION_TIMEFRAME_NEUTRAL = "EXECUTION_TIMEFRAME_NEUTRAL"
    EXECUTION_TIMEFRAME_CONFLICT = "EXECUTION_TIMEFRAME_CONFLICT"
    INSUFFICIENT_SETUP_EVIDENCE = "INSUFFICIENT_SETUP_EVIDENCE"
    INSUFFICIENT_EXECUTION_EVIDENCE = "INSUFFICIENT_EXECUTION_EVIDENCE"


class SetupQualificationReason(str, Enum):
    QUALIFIED = "QUALIFIED"
    STALE_CONTEXT = "STALE_CONTEXT"
    DIRECTION_UNRESOLVED = "DIRECTION_UNRESOLVED"
    ANALYSIS_NOT_READY = "ANALYSIS_NOT_READY"
    SETUP_TIMEFRAME_NEUTRAL = "SETUP_TIMEFRAME_NEUTRAL"
    SETUP_TIMEFRAME_CONFLICT = "SETUP_TIMEFRAME_CONFLICT"
    EXECUTION_TIMEFRAME_NEUTRAL = "EXECUTION_TIMEFRAME_NEUTRAL"
    EXECUTION_TIMEFRAME_CONFLICT = "EXECUTION_TIMEFRAME_CONFLICT"
    INSUFFICIENT_SETUP_EVIDENCE = "INSUFFICIENT_SETUP_EVIDENCE"
    INSUFFICIENT_EXECUTION_EVIDENCE = "INSUFFICIENT_EXECUTION_EVIDENCE"
    MULTIPLE_BLOCKERS = "MULTIPLE_BLOCKERS"


class SetupQualificationErrorReason(str, Enum):
    INVALID_ANALYSIS = "INVALID_ANALYSIS"


class SetupQualificationError(RuntimeError):
    """Structured setup-qualification failure."""

    def __init__(
        self,
        reason: SetupQualificationErrorReason,
        message: str,
    ) -> None:
        self.reason = SetupQualificationErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Setup qualification error [{self.reason.value}]: {self.message}")


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

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


def _bias_for_direction(
    direction: DirectionalPermissionDirection,
) -> MarketStructureBias:
    selected_direction = DirectionalPermissionDirection(direction)

    if selected_direction == DirectionalPermissionDirection.BULLISH:
        return MarketStructureBias.BULLISH

    if selected_direction == DirectionalPermissionDirection.BEARISH:
        return MarketStructureBias.BEARISH

    return MarketStructureBias.NEUTRAL


def _opposite_bias(
    bias: MarketStructureBias,
) -> MarketStructureBias:
    selected_bias = MarketStructureBias(bias)

    if selected_bias == MarketStructureBias.BULLISH:
        return MarketStructureBias.BEARISH

    if selected_bias == MarketStructureBias.BEARISH:
        return MarketStructureBias.BULLISH

    return MarketStructureBias.NEUTRAL


@dataclass(frozen=True, slots=True)
class SetupQualificationPolicy:
    """
    Conservative strategy setup-qualification policy.

    A qualified result remains analysis-only and does not
    authorize broker-side trading.
    """

    allow_neutral_setup_timeframe: bool = False
    allow_opposing_setup_timeframe: bool = False
    allow_neutral_execution_timeframe: bool = True
    allow_opposing_execution_timeframe: bool = False
    minimum_setup_evidence: int = 0
    minimum_execution_evidence: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allow_neutral_setup_timeframe",
            _strict_boolean(
                self.allow_neutral_setup_timeframe,
                "allow_neutral_setup_timeframe",
            ),
        )
        object.__setattr__(
            self,
            "allow_opposing_setup_timeframe",
            _strict_boolean(
                self.allow_opposing_setup_timeframe,
                "allow_opposing_setup_timeframe",
            ),
        )
        object.__setattr__(
            self,
            "allow_neutral_execution_timeframe",
            _strict_boolean(
                self.allow_neutral_execution_timeframe,
                "allow_neutral_execution_timeframe",
            ),
        )
        object.__setattr__(
            self,
            "allow_opposing_execution_timeframe",
            _strict_boolean(
                self.allow_opposing_execution_timeframe,
                "allow_opposing_execution_timeframe",
            ),
        )
        object.__setattr__(
            self,
            "minimum_setup_evidence",
            _non_negative_integer(
                self.minimum_setup_evidence,
                "minimum_setup_evidence",
            ),
        )
        object.__setattr__(
            self,
            "minimum_execution_evidence",
            _non_negative_integer(
                self.minimum_execution_evidence,
                "minimum_execution_evidence",
            ),
        )


@dataclass(frozen=True, slots=True)
class SetupEvidenceCounts:
    """Directional structural evidence on one timeframe."""

    liquidity_sweeps: int
    fair_value_gaps: int
    displacement_impulses: int
    order_blocks: int
    dealing_ranges: int
    optimal_trade_entry_zones: int

    def __post_init__(self) -> None:
        for field_name in (
            "liquidity_sweeps",
            "fair_value_gaps",
            "displacement_impulses",
            "order_blocks",
            "dealing_ranges",
            "optimal_trade_entry_zones",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_negative_integer(
                    getattr(self, field_name),
                    field_name,
                ),
            )

    @property
    def total(self) -> int:
        return (
            self.liquidity_sweeps
            + self.fair_value_gaps
            + self.displacement_impulses
            + self.order_blocks
            + self.dealing_ranges
            + self.optimal_trade_entry_zones
        )

    @classmethod
    def from_context_counts(
        cls,
        counts: StrategyContextCounts,
    ) -> SetupEvidenceCounts:
        if not isinstance(
            counts,
            StrategyContextCounts,
        ):
            raise ValueError("counts must be StrategyContextCounts.")

        return cls(
            liquidity_sweeps=counts.liquidity_sweeps,
            fair_value_gaps=counts.fair_value_gaps,
            displacement_impulses=(counts.displacement_impulses),
            order_blocks=counts.order_blocks,
            dealing_ranges=counts.dealing_ranges,
            optimal_trade_entry_zones=(counts.optimal_trade_entry_zones),
        )


@dataclass(frozen=True, slots=True)
class _SetupQualificationEvaluation:
    status: SetupQualificationStatus
    reason: SetupQualificationReason
    blockers: tuple[SetupQualificationBlocker, ...]
    direction: DirectionalPermissionDirection
    setup_evidence: SetupEvidenceCounts
    execution_evidence: SetupEvidenceCounts


_BLOCKER_REASON_MAP = {
    SetupQualificationBlocker.STALE_CONTEXT: (SetupQualificationReason.STALE_CONTEXT),
    SetupQualificationBlocker.DIRECTION_UNRESOLVED: (SetupQualificationReason.DIRECTION_UNRESOLVED),
    SetupQualificationBlocker.ANALYSIS_NOT_READY: (SetupQualificationReason.ANALYSIS_NOT_READY),
    SetupQualificationBlocker.SETUP_TIMEFRAME_NEUTRAL: (
        SetupQualificationReason.SETUP_TIMEFRAME_NEUTRAL
    ),
    SetupQualificationBlocker.SETUP_TIMEFRAME_CONFLICT: (
        SetupQualificationReason.SETUP_TIMEFRAME_CONFLICT
    ),
    SetupQualificationBlocker.EXECUTION_TIMEFRAME_NEUTRAL: (
        SetupQualificationReason.EXECUTION_TIMEFRAME_NEUTRAL
    ),
    SetupQualificationBlocker.EXECUTION_TIMEFRAME_CONFLICT: (
        SetupQualificationReason.EXECUTION_TIMEFRAME_CONFLICT
    ),
    SetupQualificationBlocker.INSUFFICIENT_SETUP_EVIDENCE: (
        SetupQualificationReason.INSUFFICIENT_SETUP_EVIDENCE
    ),
    SetupQualificationBlocker.INSUFFICIENT_EXECUTION_EVIDENCE: (
        SetupQualificationReason.INSUFFICIENT_EXECUTION_EVIDENCE
    ),
}


def _reason_for_blockers(
    blockers: tuple[SetupQualificationBlocker, ...],
) -> SetupQualificationReason:
    if not blockers:
        return SetupQualificationReason.QUALIFIED

    if len(blockers) == 1:
        return _BLOCKER_REASON_MAP[blockers[0]]

    return SetupQualificationReason.MULTIPLE_BLOCKERS


def _derive_setup_qualification(
    analysis: AnalysisPipelineSnapshot,
    policy: SetupQualificationPolicy,
) -> _SetupQualificationEvaluation:
    direction = DirectionalPermissionDirection(analysis.direction)
    setup_evidence = SetupEvidenceCounts.from_context_counts(analysis.context.setup_context.counts)
    execution_evidence = SetupEvidenceCounts.from_context_counts(
        analysis.context.execution_context.counts
    )
    blockers: list[SetupQualificationBlocker] = []

    if analysis.is_blocked:
        if not analysis.is_fresh:
            blockers.append(SetupQualificationBlocker.STALE_CONTEXT)

        if direction == DirectionalPermissionDirection.NONE:
            blockers.append(SetupQualificationBlocker.DIRECTION_UNRESOLVED)

        if not blockers:
            blockers.append(SetupQualificationBlocker.ANALYSIS_NOT_READY)

        blocker_tuple = tuple(blockers)

        return _SetupQualificationEvaluation(
            status=SetupQualificationStatus.BLOCKED,
            reason=_reason_for_blockers(blocker_tuple),
            blockers=blocker_tuple,
            direction=direction,
            setup_evidence=setup_evidence,
            execution_evidence=execution_evidence,
        )

    expected_bias = _bias_for_direction(direction)
    opposite_bias = _opposite_bias(expected_bias)
    setup_bias = analysis.directional.bias_for(TimeframeName.M15)
    execution_bias = analysis.directional.bias_for(TimeframeName.M5)

    if setup_bias == MarketStructureBias.NEUTRAL and not policy.allow_neutral_setup_timeframe:
        blockers.append(SetupQualificationBlocker.SETUP_TIMEFRAME_NEUTRAL)

    if setup_bias == opposite_bias and not policy.allow_opposing_setup_timeframe:
        blockers.append(SetupQualificationBlocker.SETUP_TIMEFRAME_CONFLICT)

    if (
        execution_bias == MarketStructureBias.NEUTRAL
        and not policy.allow_neutral_execution_timeframe
    ):
        blockers.append(SetupQualificationBlocker.EXECUTION_TIMEFRAME_NEUTRAL)

    if execution_bias == opposite_bias and not policy.allow_opposing_execution_timeframe:
        blockers.append(SetupQualificationBlocker.EXECUTION_TIMEFRAME_CONFLICT)

    if setup_evidence.total < policy.minimum_setup_evidence:
        blockers.append(SetupQualificationBlocker.INSUFFICIENT_SETUP_EVIDENCE)

    if execution_evidence.total < policy.minimum_execution_evidence:
        blockers.append(SetupQualificationBlocker.INSUFFICIENT_EXECUTION_EVIDENCE)

    blocker_tuple = tuple(blockers)

    return _SetupQualificationEvaluation(
        status=(
            SetupQualificationStatus.BLOCKED
            if blocker_tuple
            else SetupQualificationStatus.QUALIFIED
        ),
        reason=_reason_for_blockers(blocker_tuple),
        blockers=blocker_tuple,
        direction=direction,
        setup_evidence=setup_evidence,
        execution_evidence=execution_evidence,
    )


@dataclass(frozen=True, slots=True)
class SetupQualificationDecision:
    """Validated strategy setup-qualification decision."""

    analysis: AnalysisPipelineSnapshot
    policy: SetupQualificationPolicy
    status: SetupQualificationStatus
    reason: SetupQualificationReason
    blockers: tuple[SetupQualificationBlocker, ...]
    direction: DirectionalPermissionDirection
    setup_evidence: SetupEvidenceCounts
    execution_evidence: SetupEvidenceCounts

    def __post_init__(self) -> None:
        if not isinstance(
            self.analysis,
            AnalysisPipelineSnapshot,
        ):
            raise ValueError("analysis must be an AnalysisPipelineSnapshot.")

        if not isinstance(
            self.policy,
            SetupQualificationPolicy,
        ):
            raise ValueError("policy must be a SetupQualificationPolicy.")

        try:
            status = SetupQualificationStatus(self.status)
            reason = SetupQualificationReason(self.reason)
            direction = DirectionalPermissionDirection(self.direction)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Unsupported setup qualification status, reason, or direction."
            ) from error

        blockers = tuple(SetupQualificationBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Setup qualification blockers cannot contain duplicates.")

        if not isinstance(
            self.setup_evidence,
            SetupEvidenceCounts,
        ):
            raise ValueError("setup_evidence must be SetupEvidenceCounts.")

        if not isinstance(
            self.execution_evidence,
            SetupEvidenceCounts,
        ):
            raise ValueError("execution_evidence must be SetupEvidenceCounts.")

        expected = _derive_setup_qualification(
            self.analysis,
            self.policy,
        )
        supplied = _SetupQualificationEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            direction=direction,
            setup_evidence=self.setup_evidence,
            execution_evidence=(self.execution_evidence),
        )

        if supplied != expected:
            raise ValueError("Setup qualification result does not match its analysis and policy.")

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
            blockers,
        )
        object.__setattr__(
            self,
            "direction",
            direction,
        )

    @property
    def broker_symbol(self) -> str:
        return self.analysis.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.analysis.observed_at

    @property
    def setup_timeframe(self) -> TimeframeName:
        return TimeframeName.M15

    @property
    def execution_timeframe(self) -> TimeframeName:
        return TimeframeName.M5

    @property
    def is_qualified(self) -> bool:
        return self.status == SetupQualificationStatus.QUALIFIED

    @property
    def is_blocked(self) -> bool:
        return not self.is_qualified

    @property
    def can_generate_setup_candidate(self) -> bool:
        return self.is_qualified

    @property
    def is_bullish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BEARISH

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def total_evidence(self) -> int:
        return self.setup_evidence.total + self.execution_evidence.total

    @property
    def setup_bias(self) -> MarketStructureBias:
        return self.analysis.directional.bias_for(self.setup_timeframe)

    @property
    def execution_bias(self) -> MarketStructureBias:
        return self.analysis.directional.bias_for(self.execution_timeframe)

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.analysis.stable_id}:"
            f"SETUP_QUALIFICATION:"
            f"{self.status.value}:"
            f"{self.direction.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategySetupQualificationGate:
    """
    Pure strategy setup-qualification gate.

    QUALIFIED does not grant trading permission and does not
    create an executable order.
    """

    def __init__(
        self,
        policy: SetupQualificationPolicy | None = None,
    ) -> None:
        selected_policy = policy or SetupQualificationPolicy()

        if not isinstance(
            selected_policy,
            SetupQualificationPolicy,
        ):
            raise ValueError("policy must be a SetupQualificationPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> SetupQualificationPolicy:
        return self._policy

    def evaluate(
        self,
        analysis: AnalysisPipelineSnapshot,
    ) -> SetupQualificationDecision:
        if not isinstance(
            analysis,
            AnalysisPipelineSnapshot,
        ):
            raise SetupQualificationError(
                SetupQualificationErrorReason.INVALID_ANALYSIS,
                "analysis must be an AnalysisPipelineSnapshot.",
            )

        evaluation = _derive_setup_qualification(
            analysis,
            self._policy,
        )

        return SetupQualificationDecision(
            analysis=analysis,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            direction=evaluation.direction,
            setup_evidence=evaluation.setup_evidence,
            execution_evidence=(evaluation.execution_evidence),
        )

    def check(
        self,
        analysis: AnalysisPipelineSnapshot,
    ) -> SetupQualificationDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(analysis)

    def qualify(
        self,
        analysis: AnalysisPipelineSnapshot,
    ) -> SetupQualificationDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(analysis)


def evaluate_setup_qualification(
    analysis: AnalysisPipelineSnapshot,
    policy: SetupQualificationPolicy | None = None,
) -> SetupQualificationDecision:
    return StrategySetupQualificationGate(policy=policy).evaluate(analysis)


QualificationBlocker = SetupQualificationBlocker
QualificationDecision = SetupQualificationDecision
QualificationGate = StrategySetupQualificationGate
QualificationPolicy = SetupQualificationPolicy
QualificationReason = SetupQualificationReason
QualificationStatus = SetupQualificationStatus
SetupEligibilityGate = StrategySetupQualificationGate
SetupEvidence = SetupEvidenceCounts
