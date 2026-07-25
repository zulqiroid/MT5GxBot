from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.setup_candidate import (
    StrategySetupCandidate,
)
from app.strategy.setup_candidate_quality import (
    SetupCandidateQualityDecision,
    SetupCandidateQualityTier,
)


class PricePlanningAdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"
    BLOCKED = "BLOCKED"


class PricePlanningAdmissionReason(str, Enum):
    ADMITTED = "ADMITTED"
    QUALITY_BLOCKED = "QUALITY_BLOCKED"
    QUALITY_TIER_BELOW_MINIMUM = "QUALITY_TIER_BELOW_MINIMUM"


class PricePlanningAdmissionBlocker(str, Enum):
    QUALITY_BLOCKED = "QUALITY_BLOCKED"
    QUALITY_TIER_BELOW_MINIMUM = "QUALITY_TIER_BELOW_MINIMUM"


class PricePlanningAdmissionErrorReason(str, Enum):
    INVALID_QUALITY_DECISION = "INVALID_QUALITY_DECISION"


class PricePlanningAdmissionError(RuntimeError):
    """Structured price-planning admission failure."""

    def __init__(
        self,
        reason: PricePlanningAdmissionErrorReason,
        message: str,
    ) -> None:
        self.reason = PricePlanningAdmissionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Price-planning admission error [{self.reason.value}]: {self.message}")


_TIER_RANK = {
    SetupCandidateQualityTier.WEAK: 0,
    SetupCandidateQualityTier.ACCEPTABLE: 1,
    SetupCandidateQualityTier.STRONG: 2,
    SetupCandidateQualityTier.PREMIUM: 3,
}


@dataclass(frozen=True, slots=True)
class PricePlanningAdmissionPolicy:
    """
    Candidate-quality requirement for price planning.

    Admission remains analysis-only and does not authorize
    broker-side trading or executable order construction.
    """

    minimum_tier: SetupCandidateQualityTier = SetupCandidateQualityTier.ACCEPTABLE

    def __post_init__(self) -> None:
        if not isinstance(
            self.minimum_tier,
            SetupCandidateQualityTier,
        ):
            raise ValueError("minimum_tier must be a SetupCandidateQualityTier member.")


@dataclass(frozen=True, slots=True)
class _PricePlanningAdmissionEvaluation:
    status: PricePlanningAdmissionStatus
    reason: PricePlanningAdmissionReason
    blockers: tuple[
        PricePlanningAdmissionBlocker,
        ...,
    ]


def _derive_admission(
    quality: SetupCandidateQualityDecision,
    policy: PricePlanningAdmissionPolicy,
) -> _PricePlanningAdmissionEvaluation:
    if quality.is_blocked:
        return _PricePlanningAdmissionEvaluation(
            status=PricePlanningAdmissionStatus.BLOCKED,
            reason=(PricePlanningAdmissionReason.QUALITY_BLOCKED),
            blockers=(PricePlanningAdmissionBlocker.QUALITY_BLOCKED,),
        )

    if _TIER_RANK[quality.tier] < _TIER_RANK[policy.minimum_tier]:
        return _PricePlanningAdmissionEvaluation(
            status=PricePlanningAdmissionStatus.BLOCKED,
            reason=(PricePlanningAdmissionReason.QUALITY_TIER_BELOW_MINIMUM),
            blockers=(PricePlanningAdmissionBlocker.QUALITY_TIER_BELOW_MINIMUM,),
        )

    return _PricePlanningAdmissionEvaluation(
        status=PricePlanningAdmissionStatus.ADMITTED,
        reason=PricePlanningAdmissionReason.ADMITTED,
        blockers=(),
    )


@dataclass(frozen=True, slots=True)
class PricePlanningAdmissionDecision:
    """Validated analytical price-planning admission."""

    quality: SetupCandidateQualityDecision
    policy: PricePlanningAdmissionPolicy
    status: PricePlanningAdmissionStatus
    reason: PricePlanningAdmissionReason
    blockers: tuple[
        PricePlanningAdmissionBlocker,
        ...,
    ]

    def __post_init__(self) -> None:
        if not isinstance(
            self.quality,
            SetupCandidateQualityDecision,
        ):
            raise ValueError("quality must be a SetupCandidateQualityDecision.")

        if not isinstance(
            self.policy,
            PricePlanningAdmissionPolicy,
        ):
            raise ValueError("policy must be a PricePlanningAdmissionPolicy.")

        try:
            status = PricePlanningAdmissionStatus(self.status)
            reason = PricePlanningAdmissionReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported price-planning admission status or reason.") from error

        blockers = tuple(PricePlanningAdmissionBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Price-planning admission blockers cannot contain duplicates.")

        expected = _derive_admission(
            self.quality,
            self.policy,
        )
        supplied = _PricePlanningAdmissionEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
        )

        if supplied != expected:
            raise ValueError(
                "Price-planning admission result does not match its quality decision and policy."
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
    def candidate(self) -> StrategySetupCandidate:
        return self.quality.candidate

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
        return self.quality.score

    @property
    def tier(self) -> SetupCandidateQualityTier:
        return self.quality.tier

    @property
    def minimum_tier(
        self,
    ) -> SetupCandidateQualityTier:
        return self.policy.minimum_tier

    @property
    def is_admitted(self) -> bool:
        return self.status == PricePlanningAdmissionStatus.ADMITTED

    @property
    def is_blocked(self) -> bool:
        return not self.is_admitted

    @property
    def can_plan_prices(self) -> bool:
        return self.is_admitted

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.quality.stable_id}:"
            f"PRICE_PLANNING_ADMISSION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{self.tier.value}:"
            f"{self.minimum_tier.value}:"
            f"{blocker_fragment}"
        )


class StrategyPricePlanningAdmissionGate:
    """
    Pure admission gate for analytical price planning.

    ADMITTED does not grant trading permission and does not
    create executable price or order fields.
    """

    def __init__(
        self,
        policy: PricePlanningAdmissionPolicy | None = None,
    ) -> None:
        selected_policy = policy or PricePlanningAdmissionPolicy()

        if not isinstance(
            selected_policy,
            PricePlanningAdmissionPolicy,
        ):
            raise ValueError("policy must be a PricePlanningAdmissionPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> PricePlanningAdmissionPolicy:
        return self._policy

    def evaluate(
        self,
        quality: SetupCandidateQualityDecision,
    ) -> PricePlanningAdmissionDecision:
        if not isinstance(
            quality,
            SetupCandidateQualityDecision,
        ):
            raise PricePlanningAdmissionError(
                PricePlanningAdmissionErrorReason.INVALID_QUALITY_DECISION,
                "quality must be a SetupCandidateQualityDecision.",
            )

        evaluation = _derive_admission(
            quality,
            self._policy,
        )

        return PricePlanningAdmissionDecision(
            quality=quality,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
        )

    def admit(
        self,
        quality: SetupCandidateQualityDecision,
    ) -> PricePlanningAdmissionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(quality)

    def check(
        self,
        quality: SetupCandidateQualityDecision,
    ) -> PricePlanningAdmissionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(quality)


def evaluate_price_planning_admission(
    quality: SetupCandidateQualityDecision,
    policy: PricePlanningAdmissionPolicy | None = None,
) -> PricePlanningAdmissionDecision:
    return StrategyPricePlanningAdmissionGate(policy=policy).evaluate(quality)


PlanningAdmissionBlocker = PricePlanningAdmissionBlocker
PlanningAdmissionDecision = PricePlanningAdmissionDecision
PlanningAdmissionGate = StrategyPricePlanningAdmissionGate
PlanningAdmissionPolicy = PricePlanningAdmissionPolicy
PlanningAdmissionReason = PricePlanningAdmissionReason
PlanningAdmissionStatus = PricePlanningAdmissionStatus
PricePlanningGate = StrategyPricePlanningAdmissionGate
