from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.config.constants import TimeframeName
from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.setup_qualification import (
    SetupEvidenceCounts,
    SetupQualificationDecision,
)


class SetupCandidateGenerationStatus(str, Enum):
    GENERATED = "GENERATED"
    BLOCKED = "BLOCKED"


class SetupCandidateGenerationReason(str, Enum):
    GENERATED = "GENERATED"
    QUALIFICATION_BLOCKED = "QUALIFICATION_BLOCKED"
    INSUFFICIENT_TOTAL_EVIDENCE = "INSUFFICIENT_TOTAL_EVIDENCE"


class SetupCandidateGenerationBlocker(str, Enum):
    QUALIFICATION_BLOCKED = "QUALIFICATION_BLOCKED"
    INSUFFICIENT_TOTAL_EVIDENCE = "INSUFFICIENT_TOTAL_EVIDENCE"


class SetupCandidateErrorReason(str, Enum):
    INVALID_QUALIFICATION = "INVALID_QUALIFICATION"


class SetupCandidateError(RuntimeError):
    """Structured setup-candidate generation failure."""

    def __init__(
        self,
        reason: SetupCandidateErrorReason,
        message: str,
    ) -> None:
        self.reason = SetupCandidateErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Setup candidate error [{self.reason.value}]: {self.message}")


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
class SetupCandidatePolicy:
    """
    Admission requirements for a qualified setup candidate.

    Candidate admission remains analysis-only and does not
    represent permission to submit an order.
    """

    minimum_total_evidence: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_total_evidence",
            _non_negative_integer(
                self.minimum_total_evidence,
                "minimum_total_evidence",
            ),
        )


@dataclass(frozen=True, slots=True)
class StrategySetupCandidate:
    """
    Immutable non-executable setup candidate.

    The candidate intentionally contains no entry price,
    stop-loss, take-profit, volume, order type, or broker
    ticket.
    """

    qualification: SetupQualificationDecision

    def __post_init__(self) -> None:
        if not isinstance(
            self.qualification,
            SetupQualificationDecision,
        ):
            raise ValueError("qualification must be a SetupQualificationDecision.")

        if not self.qualification.is_qualified:
            raise ValueError("A setup candidate requires a qualified setup decision.")

        if self.qualification.direction == DirectionalPermissionDirection.NONE:
            raise ValueError("A setup candidate requires a resolved bullish or bearish direction.")

    @property
    def broker_symbol(self) -> str:
        return self.qualification.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.qualification.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.qualification.direction

    @property
    def setup_timeframe(self) -> TimeframeName:
        return self.qualification.setup_timeframe

    @property
    def execution_timeframe(self) -> TimeframeName:
        return self.qualification.execution_timeframe

    @property
    def setup_evidence(self) -> SetupEvidenceCounts:
        return self.qualification.setup_evidence

    @property
    def execution_evidence(
        self,
    ) -> SetupEvidenceCounts:
        return self.qualification.execution_evidence

    @property
    def setup_evidence_total(self) -> int:
        return self.setup_evidence.total

    @property
    def execution_evidence_total(self) -> int:
        return self.execution_evidence.total

    @property
    def total_evidence(self) -> int:
        return self.setup_evidence_total + self.execution_evidence_total

    @property
    def is_bullish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BEARISH

    @property
    def is_executable(self) -> bool:
        """
        Candidates are deliberately non-executable.

        Broker permission, exposure checks, risk sizing, and
        order construction belong to later independent gates.
        """

        return False

    @property
    def candidate_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.observed_at.isoformat()}:"
            f"{self.direction.value}:"
            f"{self.setup_timeframe.value}:"
            f"{self.execution_timeframe.value}"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.qualification.stable_id}:SETUP_CANDIDATE:{self.candidate_id}"


@dataclass(frozen=True, slots=True)
class _SetupCandidateEvaluation:
    status: SetupCandidateGenerationStatus
    reason: SetupCandidateGenerationReason
    blockers: tuple[
        SetupCandidateGenerationBlocker,
        ...,
    ]
    candidate: StrategySetupCandidate | None


def _derive_candidate_generation(
    qualification: SetupQualificationDecision,
    policy: SetupCandidatePolicy,
) -> _SetupCandidateEvaluation:
    if qualification.is_blocked:
        return _SetupCandidateEvaluation(
            status=SetupCandidateGenerationStatus.BLOCKED,
            reason=(SetupCandidateGenerationReason.QUALIFICATION_BLOCKED),
            blockers=(SetupCandidateGenerationBlocker.QUALIFICATION_BLOCKED,),
            candidate=None,
        )

    candidate = StrategySetupCandidate(qualification=qualification)

    if candidate.total_evidence < policy.minimum_total_evidence:
        return _SetupCandidateEvaluation(
            status=SetupCandidateGenerationStatus.BLOCKED,
            reason=(SetupCandidateGenerationReason.INSUFFICIENT_TOTAL_EVIDENCE),
            blockers=(SetupCandidateGenerationBlocker.INSUFFICIENT_TOTAL_EVIDENCE,),
            candidate=None,
        )

    return _SetupCandidateEvaluation(
        status=SetupCandidateGenerationStatus.GENERATED,
        reason=SetupCandidateGenerationReason.GENERATED,
        blockers=(),
        candidate=candidate,
    )


@dataclass(frozen=True, slots=True)
class SetupCandidateGenerationDecision:
    """Validated setup-candidate generation result."""

    qualification: SetupQualificationDecision
    policy: SetupCandidatePolicy
    status: SetupCandidateGenerationStatus
    reason: SetupCandidateGenerationReason
    blockers: tuple[
        SetupCandidateGenerationBlocker,
        ...,
    ]
    candidate: StrategySetupCandidate | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.qualification,
            SetupQualificationDecision,
        ):
            raise ValueError("qualification must be a SetupQualificationDecision.")

        if not isinstance(
            self.policy,
            SetupCandidatePolicy,
        ):
            raise ValueError("policy must be a SetupCandidatePolicy.")

        try:
            status = SetupCandidateGenerationStatus(self.status)
            reason = SetupCandidateGenerationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported candidate generation status or reason.") from error

        blockers = tuple(SetupCandidateGenerationBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Candidate generation blockers cannot contain duplicates.")

        if self.candidate is not None and not isinstance(
            self.candidate,
            StrategySetupCandidate,
        ):
            raise ValueError("candidate must be a StrategySetupCandidate or None.")

        expected = _derive_candidate_generation(
            self.qualification,
            self.policy,
        )
        supplied = _SetupCandidateEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            candidate=self.candidate,
        )

        if supplied != expected:
            raise ValueError(
                "Candidate generation result does not match its qualification and policy."
            )

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

    @property
    def broker_symbol(self) -> str:
        return self.qualification.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.qualification.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.qualification.direction

    @property
    def is_generated(self) -> bool:
        return self.status == SetupCandidateGenerationStatus.GENERATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_generated

    @property
    def has_candidate(self) -> bool:
        return self.candidate is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def candidate_required(
        self,
    ) -> StrategySetupCandidate:
        if self.candidate is None:
            raise ValueError("No setup candidate was generated.")

        return self.candidate

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.qualification.stable_id}:"
            f"CANDIDATE_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategySetupCandidateFactory:
    """
    Pure factory for non-executable setup candidates.

    GENERATED does not grant broker-side trading permission.
    """

    def __init__(
        self,
        policy: SetupCandidatePolicy | None = None,
    ) -> None:
        selected_policy = policy or SetupCandidatePolicy()

        if not isinstance(
            selected_policy,
            SetupCandidatePolicy,
        ):
            raise ValueError("policy must be a SetupCandidatePolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> SetupCandidatePolicy:
        return self._policy

    def generate(
        self,
        qualification: SetupQualificationDecision,
    ) -> SetupCandidateGenerationDecision:
        if not isinstance(
            qualification,
            SetupQualificationDecision,
        ):
            raise SetupCandidateError(
                SetupCandidateErrorReason.INVALID_QUALIFICATION,
                "qualification must be a SetupQualificationDecision.",
            )

        evaluation = _derive_candidate_generation(
            qualification,
            self._policy,
        )

        return SetupCandidateGenerationDecision(
            qualification=qualification,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            candidate=evaluation.candidate,
        )

    def build(
        self,
        qualification: SetupQualificationDecision,
    ) -> SetupCandidateGenerationDecision:
        """Compatibility alias for generate()."""

        return self.generate(qualification)

    def evaluate(
        self,
        qualification: SetupQualificationDecision,
    ) -> SetupCandidateGenerationDecision:
        """Compatibility alias for generate()."""

        return self.generate(qualification)


def generate_setup_candidate(
    qualification: SetupQualificationDecision,
    policy: SetupCandidatePolicy | None = None,
) -> SetupCandidateGenerationDecision:
    return StrategySetupCandidateFactory(policy=policy).generate(qualification)


CandidateDecision = SetupCandidateGenerationDecision
CandidateFactory = StrategySetupCandidateFactory
CandidateGenerationBlocker = SetupCandidateGenerationBlocker
CandidateGenerationReason = SetupCandidateGenerationReason
CandidateGenerationStatus = SetupCandidateGenerationStatus
CandidatePolicy = SetupCandidatePolicy
SetupCandidate = StrategySetupCandidate
SetupCandidateFactory = StrategySetupCandidateFactory
