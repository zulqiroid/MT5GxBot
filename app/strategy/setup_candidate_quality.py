from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.setup_candidate import (
    StrategySetupCandidate,
)

_ZERO = Decimal("0")
_HALF = Decimal("0.5")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


class SetupCandidateQualityStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    BLOCKED = "BLOCKED"


class SetupCandidateQualityTier(str, Enum):
    PREMIUM = "PREMIUM"
    STRONG = "STRONG"
    ACCEPTABLE = "ACCEPTABLE"
    WEAK = "WEAK"


class SetupCandidateQualityReason(str, Enum):
    ACCEPTED = "ACCEPTED"
    BELOW_MINIMUM_SCORE = "BELOW_MINIMUM_SCORE"


class SetupCandidateQualityBlocker(str, Enum):
    BELOW_MINIMUM_SCORE = "BELOW_MINIMUM_SCORE"


class SetupCandidateQualityErrorReason(str, Enum):
    INVALID_CANDIDATE = "INVALID_CANDIDATE"


class SetupCandidateQualityError(RuntimeError):
    """Structured candidate-quality evaluation failure."""

    def __init__(
        self,
        reason: SetupCandidateQualityErrorReason,
        message: str,
    ) -> None:
        self.reason = SetupCandidateQualityErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Setup candidate quality error [{self.reason.value}]: {self.message}")


def _decimal_between_zero_and_hundred(
    value: object,
    field_name: str,
) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError(f"{field_name} must be a Decimal.")

    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if value < _ZERO or value > _HUNDRED:
        raise ValueError(f"{field_name} must be between 0 and 100.")

    return value


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


def _ratio(
    actual: int,
    target: int,
) -> Decimal:
    selected_actual = Decimal(actual)
    selected_target = Decimal(target)

    return min(
        selected_actual / selected_target,
        _ONE,
    )


def _tier_for_score(
    score: Decimal,
) -> SetupCandidateQualityTier:
    if score >= Decimal("80"):
        return SetupCandidateQualityTier.PREMIUM

    if score >= Decimal("60"):
        return SetupCandidateQualityTier.STRONG

    if score >= Decimal("40"):
        return SetupCandidateQualityTier.ACCEPTABLE

    return SetupCandidateQualityTier.WEAK


@dataclass(frozen=True, slots=True)
class SetupCandidateQualityPolicy:
    """
    Exact quality-scoring weights and admission threshold.

    Weights must total exactly 100. Quality acceptance remains
    analysis-only and does not authorize trading.
    """

    alignment_weight: Decimal = Decimal("50")
    setup_evidence_weight: Decimal = Decimal("25")
    execution_evidence_weight: Decimal = Decimal("15")
    execution_bias_weight: Decimal = Decimal("10")
    setup_evidence_target: int = 1
    execution_evidence_target: int = 1
    minimum_score: Decimal = Decimal("40")

    def __post_init__(self) -> None:
        alignment_weight = _decimal_between_zero_and_hundred(
            self.alignment_weight,
            "alignment_weight",
        )
        setup_evidence_weight = _decimal_between_zero_and_hundred(
            self.setup_evidence_weight,
            "setup_evidence_weight",
        )
        execution_evidence_weight = _decimal_between_zero_and_hundred(
            self.execution_evidence_weight,
            "execution_evidence_weight",
        )
        execution_bias_weight = _decimal_between_zero_and_hundred(
            self.execution_bias_weight,
            "execution_bias_weight",
        )
        minimum_score = _decimal_between_zero_and_hundred(
            self.minimum_score,
            "minimum_score",
        )
        setup_evidence_target = _positive_integer(
            self.setup_evidence_target,
            "setup_evidence_target",
        )
        execution_evidence_target = _positive_integer(
            self.execution_evidence_target,
            "execution_evidence_target",
        )

        total_weight = (
            alignment_weight
            + setup_evidence_weight
            + execution_evidence_weight
            + execution_bias_weight
        )

        if total_weight != _HUNDRED:
            raise ValueError("Candidate quality weights must total exactly 100.")

        object.__setattr__(
            self,
            "alignment_weight",
            alignment_weight,
        )
        object.__setattr__(
            self,
            "setup_evidence_weight",
            setup_evidence_weight,
        )
        object.__setattr__(
            self,
            "execution_evidence_weight",
            execution_evidence_weight,
        )
        object.__setattr__(
            self,
            "execution_bias_weight",
            execution_bias_weight,
        )
        object.__setattr__(
            self,
            "setup_evidence_target",
            setup_evidence_target,
        )
        object.__setattr__(
            self,
            "execution_evidence_target",
            execution_evidence_target,
        )
        object.__setattr__(
            self,
            "minimum_score",
            minimum_score,
        )


@dataclass(frozen=True, slots=True)
class SetupCandidateQualityComponents:
    """Exact score contribution from every quality dimension."""

    alignment: Decimal
    setup_evidence: Decimal
    execution_evidence: Decimal
    execution_bias: Decimal

    def __post_init__(self) -> None:
        for field_name in (
            "alignment",
            "setup_evidence",
            "execution_evidence",
            "execution_bias",
        ):
            object.__setattr__(
                self,
                field_name,
                _decimal_between_zero_and_hundred(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        if self.total > _HUNDRED:
            raise ValueError("Quality component total cannot exceed 100.")

    @property
    def total(self) -> Decimal:
        return self.alignment + self.setup_evidence + self.execution_evidence + self.execution_bias


def _execution_bias_ratio(
    candidate: StrategySetupCandidate,
) -> Decimal:
    direction = candidate.direction
    execution_bias = candidate.qualification.execution_bias

    if direction == DirectionalPermissionDirection.BULLISH:
        expected = MarketStructureBias.BULLISH
        opposite = MarketStructureBias.BEARISH
    elif direction == DirectionalPermissionDirection.BEARISH:
        expected = MarketStructureBias.BEARISH
        opposite = MarketStructureBias.BULLISH
    else:
        return _ZERO

    if execution_bias == expected:
        return _ONE

    if execution_bias == MarketStructureBias.NEUTRAL:
        return _HALF

    if execution_bias == opposite:
        return _ZERO

    return _ZERO


def _derive_components(
    candidate: StrategySetupCandidate,
    policy: SetupCandidateQualityPolicy,
) -> SetupCandidateQualityComponents:
    alignment_ratio = candidate.qualification.analysis.alignment_score
    setup_ratio = _ratio(
        candidate.setup_evidence_total,
        policy.setup_evidence_target,
    )
    execution_ratio = _ratio(
        candidate.execution_evidence_total,
        policy.execution_evidence_target,
    )
    execution_bias_ratio = _execution_bias_ratio(candidate)

    return SetupCandidateQualityComponents(
        alignment=(alignment_ratio * policy.alignment_weight),
        setup_evidence=(setup_ratio * policy.setup_evidence_weight),
        execution_evidence=(execution_ratio * policy.execution_evidence_weight),
        execution_bias=(execution_bias_ratio * policy.execution_bias_weight),
    )


@dataclass(frozen=True, slots=True)
class _SetupCandidateQualityEvaluation:
    status: SetupCandidateQualityStatus
    reason: SetupCandidateQualityReason
    tier: SetupCandidateQualityTier
    blockers: tuple[
        SetupCandidateQualityBlocker,
        ...,
    ]
    components: SetupCandidateQualityComponents


def _derive_quality(
    candidate: StrategySetupCandidate,
    policy: SetupCandidateQualityPolicy,
) -> _SetupCandidateQualityEvaluation:
    components = _derive_components(
        candidate,
        policy,
    )
    tier = _tier_for_score(components.total)

    if components.total < policy.minimum_score:
        return _SetupCandidateQualityEvaluation(
            status=SetupCandidateQualityStatus.BLOCKED,
            reason=(SetupCandidateQualityReason.BELOW_MINIMUM_SCORE),
            tier=tier,
            blockers=(SetupCandidateQualityBlocker.BELOW_MINIMUM_SCORE,),
            components=components,
        )

    return _SetupCandidateQualityEvaluation(
        status=SetupCandidateQualityStatus.ACCEPTED,
        reason=SetupCandidateQualityReason.ACCEPTED,
        tier=tier,
        blockers=(),
        components=components,
    )


@dataclass(frozen=True, slots=True)
class SetupCandidateQualityDecision:
    """Validated candidate-quality assessment."""

    candidate: StrategySetupCandidate
    policy: SetupCandidateQualityPolicy
    status: SetupCandidateQualityStatus
    reason: SetupCandidateQualityReason
    tier: SetupCandidateQualityTier
    blockers: tuple[
        SetupCandidateQualityBlocker,
        ...,
    ]
    components: SetupCandidateQualityComponents

    def __post_init__(self) -> None:
        if not isinstance(
            self.candidate,
            StrategySetupCandidate,
        ):
            raise ValueError("candidate must be a StrategySetupCandidate.")

        if not isinstance(
            self.policy,
            SetupCandidateQualityPolicy,
        ):
            raise ValueError("policy must be a SetupCandidateQualityPolicy.")

        if not isinstance(
            self.components,
            SetupCandidateQualityComponents,
        ):
            raise ValueError("components must be SetupCandidateQualityComponents.")

        try:
            status = SetupCandidateQualityStatus(self.status)
            reason = SetupCandidateQualityReason(self.reason)
            tier = SetupCandidateQualityTier(self.tier)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported quality status, reason, or tier.") from error

        blockers = tuple(SetupCandidateQualityBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Candidate quality blockers cannot contain duplicates.")

        expected = _derive_quality(
            self.candidate,
            self.policy,
        )
        supplied = _SetupCandidateQualityEvaluation(
            status=status,
            reason=reason,
            tier=tier,
            blockers=blockers,
            components=self.components,
        )

        if supplied != expected:
            raise ValueError("Candidate quality result does not match its candidate and policy.")

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
            "tier",
            tier,
        )
        object.__setattr__(
            self,
            "blockers",
            blockers,
        )

    @property
    def broker_symbol(self) -> str:
        return self.candidate.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.candidate.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.candidate.direction

    @property
    def score(self) -> Decimal:
        return self.components.total

    @property
    def is_accepted(self) -> bool:
        return self.status == SetupCandidateQualityStatus.ACCEPTED

    @property
    def is_blocked(self) -> bool:
        return not self.is_accepted

    @property
    def can_continue_to_price_planning(self) -> bool:
        return self.is_accepted

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.candidate.stable_id}:"
            f"CANDIDATE_QUALITY:"
            f"{self.status.value}:"
            f"{self.tier.value}:"
            f"{self.score}:"
            f"{blocker_fragment}"
        )


class StrategySetupCandidateQualityGate:
    """
    Pure quality-scoring gate for setup candidates.

    ACCEPTED means the candidate may continue through later
    analysis stages. It does not grant trading permission.
    """

    def __init__(
        self,
        policy: SetupCandidateQualityPolicy | None = None,
    ) -> None:
        selected_policy = policy or SetupCandidateQualityPolicy()

        if not isinstance(
            selected_policy,
            SetupCandidateQualityPolicy,
        ):
            raise ValueError("policy must be a SetupCandidateQualityPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> SetupCandidateQualityPolicy:
        return self._policy

    def evaluate(
        self,
        candidate: StrategySetupCandidate,
    ) -> SetupCandidateQualityDecision:
        if not isinstance(
            candidate,
            StrategySetupCandidate,
        ):
            raise SetupCandidateQualityError(
                SetupCandidateQualityErrorReason.INVALID_CANDIDATE,
                "candidate must be a StrategySetupCandidate.",
            )

        evaluation = _derive_quality(
            candidate,
            self._policy,
        )

        return SetupCandidateQualityDecision(
            candidate=candidate,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            tier=evaluation.tier,
            blockers=evaluation.blockers,
            components=evaluation.components,
        )

    def score(
        self,
        candidate: StrategySetupCandidate,
    ) -> SetupCandidateQualityDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(candidate)

    def assess(
        self,
        candidate: StrategySetupCandidate,
    ) -> SetupCandidateQualityDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(candidate)


def evaluate_setup_candidate_quality(
    candidate: StrategySetupCandidate,
    policy: SetupCandidateQualityPolicy | None = None,
) -> SetupCandidateQualityDecision:
    return StrategySetupCandidateQualityGate(policy=policy).evaluate(candidate)


CandidateQualityBlocker = SetupCandidateQualityBlocker
CandidateQualityComponents = SetupCandidateQualityComponents
CandidateQualityDecision = SetupCandidateQualityDecision
CandidateQualityGate = StrategySetupCandidateQualityGate
CandidateQualityPolicy = SetupCandidateQualityPolicy
CandidateQualityReason = SetupCandidateQualityReason
CandidateQualityStatus = SetupCandidateQualityStatus
CandidateQualityTier = SetupCandidateQualityTier
SetupQualityGate = StrategySetupCandidateQualityGate
