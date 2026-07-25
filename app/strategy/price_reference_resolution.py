from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.price_reference_availability import (
    PriceReferenceAvailabilityDecision,
)
from app.strategy.price_reference_plan import (
    DirectionalPriceReferencePlan,
    PriceReferenceRequirement,
    PriceReferenceRole,
)


class PriceReferenceResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    BLOCKED = "BLOCKED"


class PriceReferenceResolutionReason(str, Enum):
    RESOLVED = "RESOLVED"
    AVAILABILITY_BLOCKED = "AVAILABILITY_BLOCKED"
    ENTRY_VALUE_MISSING = "ENTRY_VALUE_MISSING"
    STOP_VALUE_MISSING = "STOP_VALUE_MISSING"
    TARGET_VALUE_MISSING = "TARGET_VALUE_MISSING"
    MULTIPLE_VALUES_MISSING = "MULTIPLE_VALUES_MISSING"
    DIRECTIONAL_ORDER_INVALID = "DIRECTIONAL_ORDER_INVALID"


class PriceReferenceResolutionBlocker(str, Enum):
    AVAILABILITY_BLOCKED = "AVAILABILITY_BLOCKED"
    ENTRY_VALUE_MISSING = "ENTRY_VALUE_MISSING"
    STOP_VALUE_MISSING = "STOP_VALUE_MISSING"
    TARGET_VALUE_MISSING = "TARGET_VALUE_MISSING"
    DIRECTIONAL_ORDER_INVALID = "DIRECTIONAL_ORDER_INVALID"


class PriceReferenceResolutionErrorReason(str, Enum):
    INVALID_AVAILABILITY_DECISION = "INVALID_AVAILABILITY_DECISION"
    INVALID_OBSERVATIONS = "INVALID_OBSERVATIONS"


class PriceReferenceResolutionError(RuntimeError):
    """Structured price-reference resolution failure."""

    def __init__(
        self,
        reason: PriceReferenceResolutionErrorReason,
        message: str,
    ) -> None:
        self.reason = PriceReferenceResolutionErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Price-reference resolution error [{self.reason.value}]: {self.message}")


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _positive_finite_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError(f"{field_name} must be a Decimal.")

    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if value <= Decimal("0"):
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


@dataclass(frozen=True, slots=True)
class PriceReferenceResolutionPolicy:
    """
    Validation policy for observed reference values.

    Resolution remains analytical. It does not create a
    broker order, risk allocation, or executable trade.
    """

    validate_directional_order: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "validate_directional_order",
            _strict_boolean(
                self.validate_directional_order,
                "validate_directional_order",
            ),
        )


@dataclass(frozen=True, slots=True)
class PriceReferenceValueObservation:
    """One observed value for one planned requirement."""

    requirement: PriceReferenceRequirement
    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(
            self.requirement,
            PriceReferenceRequirement,
        ):
            raise ValueError("requirement must be a PriceReferenceRequirement.")

        object.__setattr__(
            self,
            "value",
            _positive_finite_decimal(
                self.value,
                "value",
            ),
        )

    @property
    def role(self) -> PriceReferenceRole:
        return self.requirement.role

    @property
    def stable_id(self) -> str:
        return f"{self.requirement.stable_id}:VALUE[{self.value}]"


@dataclass(frozen=True, slots=True)
class PriceReferenceValueSnapshot:
    """
    Immutable observations associated with one plan.

    Observations may include selected and non-selected plan
    requirements, but duplicates and foreign requirements
    are rejected.
    """

    plan: DirectionalPriceReferencePlan
    observations: tuple[
        PriceReferenceValueObservation,
        ...,
    ]

    def __post_init__(self) -> None:
        if not isinstance(
            self.plan,
            DirectionalPriceReferencePlan,
        ):
            raise ValueError("plan must be a DirectionalPriceReferencePlan.")

        if not isinstance(self.observations, tuple):
            raise ValueError("observations must be a tuple.")

        requirements: list[PriceReferenceRequirement] = []

        for observation in self.observations:
            if not isinstance(
                observation,
                PriceReferenceValueObservation,
            ):
                raise ValueError(
                    "observations must contain PriceReferenceValueObservation objects."
                )

            if observation.requirement not in self.plan.requirements:
                raise ValueError("Observation requirement does not belong to the supplied plan.")

            requirements.append(observation.requirement)

        if len(set(requirements)) != len(requirements):
            raise ValueError("Reference value observations cannot contain duplicate requirements.")

    def observation_for(
        self,
        requirement: PriceReferenceRequirement,
    ) -> PriceReferenceValueObservation | None:
        if not isinstance(
            requirement,
            PriceReferenceRequirement,
        ):
            raise ValueError("requirement must be a PriceReferenceRequirement.")

        for observation in self.observations:
            if observation.requirement == requirement:
                return observation

        return None

    def value_for(
        self,
        requirement: PriceReferenceRequirement,
    ) -> Decimal | None:
        observation = self.observation_for(requirement)

        if observation is None:
            return None

        return observation.value

    @property
    def stable_id(self) -> str:
        observation_fragment = (
            "NONE"
            if not self.observations
            else "|".join(observation.stable_id for observation in self.observations)
        )

        return f"{self.plan.stable_id}:REFERENCE_VALUES:{observation_fragment}"


@dataclass(frozen=True, slots=True)
class _PriceReferenceResolutionEvaluation:
    status: PriceReferenceResolutionStatus
    reason: PriceReferenceResolutionReason
    blockers: tuple[
        PriceReferenceResolutionBlocker,
        ...,
    ]
    observations: PriceReferenceValueSnapshot | None
    entry_value: Decimal | None
    stop_value: Decimal | None
    target_value: Decimal | None


_MISSING_REASON_MAP = {
    PriceReferenceResolutionBlocker.ENTRY_VALUE_MISSING: (
        PriceReferenceResolutionReason.ENTRY_VALUE_MISSING
    ),
    PriceReferenceResolutionBlocker.STOP_VALUE_MISSING: (
        PriceReferenceResolutionReason.STOP_VALUE_MISSING
    ),
    PriceReferenceResolutionBlocker.TARGET_VALUE_MISSING: (
        PriceReferenceResolutionReason.TARGET_VALUE_MISSING
    ),
}


def _missing_reason(
    blockers: tuple[
        PriceReferenceResolutionBlocker,
        ...,
    ],
) -> PriceReferenceResolutionReason:
    if len(blockers) == 1:
        return _MISSING_REASON_MAP[blockers[0]]

    return PriceReferenceResolutionReason.MULTIPLE_VALUES_MISSING


def _directional_order_is_valid(
    *,
    direction: DirectionalPermissionDirection,
    entry_value: Decimal | None,
    stop_value: Decimal | None,
    target_value: Decimal | None,
) -> bool:
    if direction == DirectionalPermissionDirection.BULLISH:
        if entry_value is not None and stop_value is not None and not stop_value < entry_value:
            return False

        if entry_value is not None and target_value is not None and not entry_value < target_value:
            return False

        return True

    if direction == DirectionalPermissionDirection.BEARISH:
        if entry_value is not None and stop_value is not None and not entry_value < stop_value:
            return False

        if entry_value is not None and target_value is not None and not target_value < entry_value:
            return False

        return True

    return False


def _derive_resolution(
    availability_decision: (PriceReferenceAvailabilityDecision),
    observations: PriceReferenceValueSnapshot | None,
    policy: PriceReferenceResolutionPolicy,
) -> _PriceReferenceResolutionEvaluation:
    if availability_decision.is_blocked:
        return _PriceReferenceResolutionEvaluation(
            status=PriceReferenceResolutionStatus.BLOCKED,
            reason=(PriceReferenceResolutionReason.AVAILABILITY_BLOCKED),
            blockers=(PriceReferenceResolutionBlocker.AVAILABILITY_BLOCKED,),
            observations=None,
            entry_value=None,
            stop_value=None,
            target_value=None,
        )

    if observations is None:
        raise PriceReferenceResolutionError(
            PriceReferenceResolutionErrorReason.INVALID_OBSERVATIONS,
            "observations are required for a ready availability decision.",
        )

    plan = availability_decision.plan

    if plan is None:
        raise PriceReferenceResolutionError(
            PriceReferenceResolutionErrorReason.INVALID_OBSERVATIONS,
            "Ready availability decision has no directional plan.",
        )

    if observations.plan != plan:
        raise PriceReferenceResolutionError(
            PriceReferenceResolutionErrorReason.INVALID_OBSERVATIONS,
            "Value snapshot does not reference the supplied directional plan.",
        )

    selected_entry = availability_decision.selected_entry
    selected_stop = availability_decision.selected_stop
    selected_target = availability_decision.selected_target

    entry_value = observations.value_for(selected_entry) if selected_entry is not None else None
    stop_value = observations.value_for(selected_stop) if selected_stop is not None else None
    target_value = observations.value_for(selected_target) if selected_target is not None else None

    blockers: list[PriceReferenceResolutionBlocker] = []

    if selected_entry is not None and entry_value is None:
        blockers.append(PriceReferenceResolutionBlocker.ENTRY_VALUE_MISSING)

    if selected_stop is not None and stop_value is None:
        blockers.append(PriceReferenceResolutionBlocker.STOP_VALUE_MISSING)

    if selected_target is not None and target_value is None:
        blockers.append(PriceReferenceResolutionBlocker.TARGET_VALUE_MISSING)

    if blockers:
        blocker_tuple = tuple(blockers)

        return _PriceReferenceResolutionEvaluation(
            status=PriceReferenceResolutionStatus.BLOCKED,
            reason=_missing_reason(blocker_tuple),
            blockers=blocker_tuple,
            observations=observations,
            entry_value=entry_value,
            stop_value=stop_value,
            target_value=target_value,
        )

    if policy.validate_directional_order and not _directional_order_is_valid(
        direction=availability_decision.direction,
        entry_value=entry_value,
        stop_value=stop_value,
        target_value=target_value,
    ):
        return _PriceReferenceResolutionEvaluation(
            status=PriceReferenceResolutionStatus.BLOCKED,
            reason=(PriceReferenceResolutionReason.DIRECTIONAL_ORDER_INVALID),
            blockers=(PriceReferenceResolutionBlocker.DIRECTIONAL_ORDER_INVALID,),
            observations=observations,
            entry_value=entry_value,
            stop_value=stop_value,
            target_value=target_value,
        )

    return _PriceReferenceResolutionEvaluation(
        status=PriceReferenceResolutionStatus.RESOLVED,
        reason=PriceReferenceResolutionReason.RESOLVED,
        blockers=(),
        observations=observations,
        entry_value=entry_value,
        stop_value=stop_value,
        target_value=target_value,
    )


@dataclass(frozen=True, slots=True)
class PriceReferenceResolutionDecision:
    """Validated selected-reference value resolution."""

    availability_decision: PriceReferenceAvailabilityDecision
    policy: PriceReferenceResolutionPolicy
    status: PriceReferenceResolutionStatus
    reason: PriceReferenceResolutionReason
    blockers: tuple[
        PriceReferenceResolutionBlocker,
        ...,
    ]
    observations: PriceReferenceValueSnapshot | None
    entry_value: Decimal | None
    stop_value: Decimal | None
    target_value: Decimal | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.availability_decision,
            PriceReferenceAvailabilityDecision,
        ):
            raise ValueError("availability_decision must be a PriceReferenceAvailabilityDecision.")

        if not isinstance(
            self.policy,
            PriceReferenceResolutionPolicy,
        ):
            raise ValueError("policy must be a PriceReferenceResolutionPolicy.")

        try:
            status = PriceReferenceResolutionStatus(self.status)
            reason = PriceReferenceResolutionReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported resolution status or reason.") from error

        blockers = tuple(PriceReferenceResolutionBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Resolution blockers cannot contain duplicates.")

        if self.observations is not None and not isinstance(
            self.observations,
            PriceReferenceValueSnapshot,
        ):
            raise ValueError("observations must be a PriceReferenceValueSnapshot or None.")

        for field_name in (
            "entry_value",
            "stop_value",
            "target_value",
        ):
            value = getattr(self, field_name)

            if value is not None:
                _positive_finite_decimal(
                    value,
                    field_name,
                )

        expected = _derive_resolution(
            self.availability_decision,
            self.observations,
            self.policy,
        )
        supplied = _PriceReferenceResolutionEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            observations=self.observations,
            entry_value=self.entry_value,
            stop_value=self.stop_value,
            target_value=self.target_value,
        )

        if supplied != expected:
            raise ValueError(
                "Resolution decision does not match its availability, observations, and policy."
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
    def plan(self) -> DirectionalPriceReferencePlan | None:
        return self.availability_decision.plan

    @property
    def broker_symbol(self) -> str:
        return self.availability_decision.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.availability_decision.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.availability_decision.direction

    @property
    def is_resolved(self) -> bool:
        return self.status == PriceReferenceResolutionStatus.RESOLVED

    @property
    def is_blocked(self) -> bool:
        return not self.is_resolved

    @property
    def has_entry_value(self) -> bool:
        return self.entry_value is not None

    @property
    def has_stop_value(self) -> bool:
        return self.stop_value is not None

    @property
    def has_target_value(self) -> bool:
        return self.target_value is not None

    @property
    def can_continue_to_reward_risk_analysis(self) -> bool:
        return self.is_resolved

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
        value_fragment = ":".join(
            (
                (str(self.entry_value) if self.entry_value is not None else "NO_ENTRY"),
                (str(self.stop_value) if self.stop_value is not None else "NO_STOP"),
                (str(self.target_value) if self.target_value is not None else "NO_TARGET"),
            )
        )

        return (
            f"{self.availability_decision.stable_id}:"
            f"REFERENCE_RESOLUTION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}:"
            f"{value_fragment}"
        )


class StrategyPriceReferenceResolutionGate:
    """
    Pure gate for resolving selected reference values.

    RESOLVED means reward/risk analysis may continue. It does
    not create a position size, order request, or permission
    to trade.
    """

    def __init__(
        self,
        policy: (PriceReferenceResolutionPolicy | None) = None,
    ) -> None:
        selected_policy = policy or PriceReferenceResolutionPolicy()

        if not isinstance(
            selected_policy,
            PriceReferenceResolutionPolicy,
        ):
            raise ValueError("policy must be a PriceReferenceResolutionPolicy.")

        self._policy = selected_policy

    @property
    def policy(
        self,
    ) -> PriceReferenceResolutionPolicy:
        return self._policy

    def evaluate(
        self,
        availability_decision: (PriceReferenceAvailabilityDecision),
        observations: (PriceReferenceValueSnapshot | None) = None,
    ) -> PriceReferenceResolutionDecision:
        if not isinstance(
            availability_decision,
            PriceReferenceAvailabilityDecision,
        ):
            raise PriceReferenceResolutionError(
                PriceReferenceResolutionErrorReason.INVALID_AVAILABILITY_DECISION,
                "availability_decision must be a PriceReferenceAvailabilityDecision.",
            )

        if observations is not None and not isinstance(
            observations,
            PriceReferenceValueSnapshot,
        ):
            raise PriceReferenceResolutionError(
                PriceReferenceResolutionErrorReason.INVALID_OBSERVATIONS,
                "observations must be a PriceReferenceValueSnapshot or None.",
            )

        evaluation = _derive_resolution(
            availability_decision,
            observations,
            self._policy,
        )

        return PriceReferenceResolutionDecision(
            availability_decision=availability_decision,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            observations=evaluation.observations,
            entry_value=evaluation.entry_value,
            stop_value=evaluation.stop_value,
            target_value=evaluation.target_value,
        )

    def resolve(
        self,
        availability_decision: (PriceReferenceAvailabilityDecision),
        observations: (PriceReferenceValueSnapshot | None) = None,
    ) -> PriceReferenceResolutionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            availability_decision,
            observations,
        )

    def check(
        self,
        availability_decision: (PriceReferenceAvailabilityDecision),
        observations: (PriceReferenceValueSnapshot | None) = None,
    ) -> PriceReferenceResolutionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            availability_decision,
            observations,
        )


def evaluate_price_reference_resolution(
    availability_decision: (PriceReferenceAvailabilityDecision),
    observations: PriceReferenceValueSnapshot | None = None,
    policy: PriceReferenceResolutionPolicy | None = None,
) -> PriceReferenceResolutionDecision:
    return StrategyPriceReferenceResolutionGate(policy=policy).evaluate(
        availability_decision,
        observations,
    )


ReferenceResolutionBlocker = PriceReferenceResolutionBlocker
ReferenceResolutionDecision = PriceReferenceResolutionDecision
ReferenceResolutionGate = StrategyPriceReferenceResolutionGate
ReferenceResolutionPolicy = PriceReferenceResolutionPolicy
ReferenceResolutionReason = PriceReferenceResolutionReason
ReferenceResolutionStatus = PriceReferenceResolutionStatus
ReferenceValueObservation = PriceReferenceValueObservation
ReferenceValueSnapshot = PriceReferenceValueSnapshot
