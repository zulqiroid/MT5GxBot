from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.price_reference_plan import (
    DirectionalPriceReferencePlan,
    PriceReferencePlanDecision,
    PriceReferenceRequirement,
    PriceReferenceRole,
)


class PriceReferenceAvailabilityStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class PriceReferenceAvailabilityReason(str, Enum):
    READY = "READY"
    PLAN_BLOCKED = "PLAN_BLOCKED"
    ENTRY_REFERENCE_UNAVAILABLE = "ENTRY_REFERENCE_UNAVAILABLE"
    STOP_REFERENCE_UNAVAILABLE = "STOP_REFERENCE_UNAVAILABLE"
    TARGET_REFERENCE_UNAVAILABLE = "TARGET_REFERENCE_UNAVAILABLE"
    MULTIPLE_REFERENCES_UNAVAILABLE = "MULTIPLE_REFERENCES_UNAVAILABLE"


class PriceReferenceAvailabilityBlocker(str, Enum):
    PLAN_BLOCKED = "PLAN_BLOCKED"
    ENTRY_REFERENCE_UNAVAILABLE = "ENTRY_REFERENCE_UNAVAILABLE"
    STOP_REFERENCE_UNAVAILABLE = "STOP_REFERENCE_UNAVAILABLE"
    TARGET_REFERENCE_UNAVAILABLE = "TARGET_REFERENCE_UNAVAILABLE"


class PriceReferenceAvailabilityErrorReason(str, Enum):
    INVALID_PLAN_DECISION = "INVALID_PLAN_DECISION"
    INVALID_AVAILABILITY = "INVALID_AVAILABILITY"


class PriceReferenceAvailabilityError(RuntimeError):
    """Structured reference-availability failure."""

    def __init__(
        self,
        reason: PriceReferenceAvailabilityErrorReason,
        message: str,
    ) -> None:
        self.reason = PriceReferenceAvailabilityErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Price-reference availability error [{self.reason.value}]: {self.message}"
        )


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


@dataclass(frozen=True, slots=True)
class PriceReferenceAvailabilityPolicy:
    """
    Required source roles before price resolution may begin.

    Readiness remains analytical and does not authorize
    executable price or order construction.
    """

    require_entry_reference: bool = True
    require_stop_reference: bool = True
    require_target_reference: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "require_entry_reference",
            _strict_boolean(
                self.require_entry_reference,
                "require_entry_reference",
            ),
        )
        object.__setattr__(
            self,
            "require_stop_reference",
            _strict_boolean(
                self.require_stop_reference,
                "require_stop_reference",
            ),
        )
        object.__setattr__(
            self,
            "require_target_reference",
            _strict_boolean(
                self.require_target_reference,
                "require_target_reference",
            ),
        )


@dataclass(frozen=True, slots=True)
class PriceReferenceAvailabilityItem:
    """Availability of one planned reference requirement."""

    requirement: PriceReferenceRequirement
    available: bool

    def __post_init__(self) -> None:
        if not isinstance(
            self.requirement,
            PriceReferenceRequirement,
        ):
            raise ValueError("requirement must be a PriceReferenceRequirement.")

        object.__setattr__(
            self,
            "available",
            _strict_boolean(
                self.available,
                "available",
            ),
        )

    @property
    def role(self) -> PriceReferenceRole:
        return self.requirement.role

    @property
    def is_available(self) -> bool:
        return self.available

    @property
    def is_unavailable(self) -> bool:
        return not self.available

    @property
    def stable_id(self) -> str:
        state = "AVAILABLE" if self.available else "UNAVAILABLE"

        return f"{self.requirement.stable_id}:{state}"


@dataclass(frozen=True, slots=True)
class PriceReferenceAvailabilitySnapshot:
    """
    Exact availability snapshot for one directional plan.

    Items must correspond one-for-one and in the same order
    as the plan requirements.
    """

    plan: DirectionalPriceReferencePlan
    items: tuple[
        PriceReferenceAvailabilityItem,
        ...,
    ]

    def __post_init__(self) -> None:
        if not isinstance(
            self.plan,
            DirectionalPriceReferencePlan,
        ):
            raise ValueError("plan must be a DirectionalPriceReferencePlan.")

        if not isinstance(self.items, tuple):
            raise ValueError("items must be a tuple.")

        if not self.items:
            raise ValueError("items cannot be empty.")

        for item in self.items:
            if not isinstance(
                item,
                PriceReferenceAvailabilityItem,
            ):
                raise ValueError("items must contain PriceReferenceAvailabilityItem objects.")

        supplied_requirements = tuple(item.requirement for item in self.items)

        if supplied_requirements != self.plan.requirements:
            raise ValueError(
                "Availability items must match all plan requirements in their exact order."
            )

    @property
    def available_items(
        self,
    ) -> tuple[PriceReferenceAvailabilityItem, ...]:
        return tuple(item for item in self.items if item.is_available)

    @property
    def unavailable_items(
        self,
    ) -> tuple[PriceReferenceAvailabilityItem, ...]:
        return tuple(item for item in self.items if item.is_unavailable)

    def first_available(
        self,
        role: PriceReferenceRole,
    ) -> PriceReferenceRequirement | None:
        if not isinstance(role, PriceReferenceRole):
            raise ValueError("role must be a PriceReferenceRole member.")

        for item in self.items:
            if item.role == role and item.is_available:
                return item.requirement

        return None

    @property
    def stable_id(self) -> str:
        item_fragment = "|".join(item.stable_id for item in self.items)

        return f"{self.plan.stable_id}:REFERENCE_AVAILABILITY:{item_fragment}"


@dataclass(frozen=True, slots=True)
class _AvailabilityEvaluation:
    status: PriceReferenceAvailabilityStatus
    reason: PriceReferenceAvailabilityReason
    blockers: tuple[
        PriceReferenceAvailabilityBlocker,
        ...,
    ]
    availability: PriceReferenceAvailabilitySnapshot | None
    selected_entry: PriceReferenceRequirement | None
    selected_stop: PriceReferenceRequirement | None
    selected_target: PriceReferenceRequirement | None


_BLOCKER_REASON_MAP = {
    PriceReferenceAvailabilityBlocker.PLAN_BLOCKED: (PriceReferenceAvailabilityReason.PLAN_BLOCKED),
    PriceReferenceAvailabilityBlocker.ENTRY_REFERENCE_UNAVAILABLE: (
        PriceReferenceAvailabilityReason.ENTRY_REFERENCE_UNAVAILABLE
    ),
    PriceReferenceAvailabilityBlocker.STOP_REFERENCE_UNAVAILABLE: (
        PriceReferenceAvailabilityReason.STOP_REFERENCE_UNAVAILABLE
    ),
    PriceReferenceAvailabilityBlocker.TARGET_REFERENCE_UNAVAILABLE: (
        PriceReferenceAvailabilityReason.TARGET_REFERENCE_UNAVAILABLE
    ),
}


def _reason_for_blockers(
    blockers: tuple[
        PriceReferenceAvailabilityBlocker,
        ...,
    ],
) -> PriceReferenceAvailabilityReason:
    if not blockers:
        return PriceReferenceAvailabilityReason.READY

    if len(blockers) == 1:
        return _BLOCKER_REASON_MAP[blockers[0]]

    return PriceReferenceAvailabilityReason.MULTIPLE_REFERENCES_UNAVAILABLE


def _derive_availability(
    plan_decision: PriceReferencePlanDecision,
    availability: PriceReferenceAvailabilitySnapshot | None,
    policy: PriceReferenceAvailabilityPolicy,
) -> _AvailabilityEvaluation:
    if plan_decision.is_blocked:
        return _AvailabilityEvaluation(
            status=PriceReferenceAvailabilityStatus.BLOCKED,
            reason=(PriceReferenceAvailabilityReason.PLAN_BLOCKED),
            blockers=(PriceReferenceAvailabilityBlocker.PLAN_BLOCKED,),
            availability=None,
            selected_entry=None,
            selected_stop=None,
            selected_target=None,
        )

    if availability is None:
        raise PriceReferenceAvailabilityError(
            PriceReferenceAvailabilityErrorReason.INVALID_AVAILABILITY,
            "availability is required for a created price-reference plan.",
        )

    plan = plan_decision.plan_required

    if availability.plan != plan:
        raise PriceReferenceAvailabilityError(
            PriceReferenceAvailabilityErrorReason.INVALID_AVAILABILITY,
            "Availability snapshot does not reference the supplied directional plan.",
        )

    selected_entry = availability.first_available(PriceReferenceRole.ENTRY)
    selected_stop = availability.first_available(PriceReferenceRole.STOP)
    selected_target = availability.first_available(PriceReferenceRole.TARGET)
    blockers: list[PriceReferenceAvailabilityBlocker] = []

    if policy.require_entry_reference and selected_entry is None:
        blockers.append(PriceReferenceAvailabilityBlocker.ENTRY_REFERENCE_UNAVAILABLE)

    if policy.require_stop_reference and selected_stop is None:
        blockers.append(PriceReferenceAvailabilityBlocker.STOP_REFERENCE_UNAVAILABLE)

    if policy.require_target_reference and selected_target is None:
        blockers.append(PriceReferenceAvailabilityBlocker.TARGET_REFERENCE_UNAVAILABLE)

    blocker_tuple = tuple(blockers)

    return _AvailabilityEvaluation(
        status=(
            PriceReferenceAvailabilityStatus.BLOCKED
            if blocker_tuple
            else PriceReferenceAvailabilityStatus.READY
        ),
        reason=_reason_for_blockers(blocker_tuple),
        blockers=blocker_tuple,
        availability=availability,
        selected_entry=selected_entry,
        selected_stop=selected_stop,
        selected_target=selected_target,
    )


@dataclass(frozen=True, slots=True)
class PriceReferenceAvailabilityDecision:
    """Validated reference-availability assessment."""

    plan_decision: PriceReferencePlanDecision
    policy: PriceReferenceAvailabilityPolicy
    status: PriceReferenceAvailabilityStatus
    reason: PriceReferenceAvailabilityReason
    blockers: tuple[
        PriceReferenceAvailabilityBlocker,
        ...,
    ]
    availability: PriceReferenceAvailabilitySnapshot | None
    selected_entry: PriceReferenceRequirement | None
    selected_stop: PriceReferenceRequirement | None
    selected_target: PriceReferenceRequirement | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.plan_decision,
            PriceReferencePlanDecision,
        ):
            raise ValueError("plan_decision must be a PriceReferencePlanDecision.")

        if not isinstance(
            self.policy,
            PriceReferenceAvailabilityPolicy,
        ):
            raise ValueError("policy must be a PriceReferenceAvailabilityPolicy.")

        try:
            status = PriceReferenceAvailabilityStatus(self.status)
            reason = PriceReferenceAvailabilityReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported availability status or reason.") from error

        blockers = tuple(PriceReferenceAvailabilityBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Availability blockers cannot contain duplicates.")

        if self.availability is not None and not isinstance(
            self.availability,
            PriceReferenceAvailabilitySnapshot,
        ):
            raise ValueError("availability must be a PriceReferenceAvailabilitySnapshot or None.")

        for field_name in (
            "selected_entry",
            "selected_stop",
            "selected_target",
        ):
            value = getattr(self, field_name)

            if value is not None and not isinstance(
                value,
                PriceReferenceRequirement,
            ):
                raise ValueError(f"{field_name} must be a PriceReferenceRequirement or None.")

        expected = _derive_availability(
            self.plan_decision,
            self.availability,
            self.policy,
        )
        supplied = _AvailabilityEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            availability=self.availability,
            selected_entry=self.selected_entry,
            selected_stop=self.selected_stop,
            selected_target=self.selected_target,
        )

        if supplied != expected:
            raise ValueError("Availability decision does not match its plan, snapshot, and policy.")

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
        return self.plan_decision.plan

    @property
    def broker_symbol(self) -> str:
        return self.plan_decision.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.plan_decision.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.plan_decision.direction

    @property
    def is_ready(self) -> bool:
        return self.status == PriceReferenceAvailabilityStatus.READY

    @property
    def is_blocked(self) -> bool:
        return not self.is_ready

    @property
    def can_resolve_prices(self) -> bool:
        return self.is_ready

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
        selection_fragment = ":".join(
            (
                (self.selected_entry.stable_id if self.selected_entry else "NO_ENTRY"),
                (self.selected_stop.stable_id if self.selected_stop else "NO_STOP"),
                (self.selected_target.stable_id if self.selected_target else "NO_TARGET"),
            )
        )

        return (
            f"{self.plan_decision.stable_id}:"
            f"REFERENCE_AVAILABILITY_DECISION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}:"
            f"{selection_fragment}"
        )


class StrategyPriceReferenceAvailabilityGate:
    """
    Pure availability gate for planned price references.

    READY means later reference-value resolution may begin.
    It does not create executable prices or trading permission.
    """

    def __init__(
        self,
        policy: (PriceReferenceAvailabilityPolicy | None) = None,
    ) -> None:
        selected_policy = policy or PriceReferenceAvailabilityPolicy()

        if not isinstance(
            selected_policy,
            PriceReferenceAvailabilityPolicy,
        ):
            raise ValueError("policy must be a PriceReferenceAvailabilityPolicy.")

        self._policy = selected_policy

    @property
    def policy(
        self,
    ) -> PriceReferenceAvailabilityPolicy:
        return self._policy

    def evaluate(
        self,
        plan_decision: PriceReferencePlanDecision,
        availability: (PriceReferenceAvailabilitySnapshot | None) = None,
    ) -> PriceReferenceAvailabilityDecision:
        if not isinstance(
            plan_decision,
            PriceReferencePlanDecision,
        ):
            raise PriceReferenceAvailabilityError(
                PriceReferenceAvailabilityErrorReason.INVALID_PLAN_DECISION,
                "plan_decision must be a PriceReferencePlanDecision.",
            )

        if availability is not None and not isinstance(
            availability,
            PriceReferenceAvailabilitySnapshot,
        ):
            raise PriceReferenceAvailabilityError(
                PriceReferenceAvailabilityErrorReason.INVALID_AVAILABILITY,
                "availability must be a PriceReferenceAvailabilitySnapshot or None.",
            )

        evaluation = _derive_availability(
            plan_decision,
            availability,
            self._policy,
        )

        return PriceReferenceAvailabilityDecision(
            plan_decision=plan_decision,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            availability=evaluation.availability,
            selected_entry=evaluation.selected_entry,
            selected_stop=evaluation.selected_stop,
            selected_target=evaluation.selected_target,
        )

    def assess(
        self,
        plan_decision: PriceReferencePlanDecision,
        availability: (PriceReferenceAvailabilitySnapshot | None) = None,
    ) -> PriceReferenceAvailabilityDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            plan_decision,
            availability,
        )

    def check(
        self,
        plan_decision: PriceReferencePlanDecision,
        availability: (PriceReferenceAvailabilitySnapshot | None) = None,
    ) -> PriceReferenceAvailabilityDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            plan_decision,
            availability,
        )


def evaluate_price_reference_availability(
    plan_decision: PriceReferencePlanDecision,
    availability: (PriceReferenceAvailabilitySnapshot | None) = None,
    policy: (PriceReferenceAvailabilityPolicy | None) = None,
) -> PriceReferenceAvailabilityDecision:
    return StrategyPriceReferenceAvailabilityGate(policy=policy).evaluate(
        plan_decision,
        availability,
    )


ReferenceAvailabilityBlocker = PriceReferenceAvailabilityBlocker
ReferenceAvailabilityDecision = PriceReferenceAvailabilityDecision
ReferenceAvailabilityGate = StrategyPriceReferenceAvailabilityGate
ReferenceAvailabilityItem = PriceReferenceAvailabilityItem
ReferenceAvailabilityPolicy = PriceReferenceAvailabilityPolicy
ReferenceAvailabilityReason = PriceReferenceAvailabilityReason
ReferenceAvailabilitySnapshot = PriceReferenceAvailabilitySnapshot
ReferenceAvailabilityStatus = PriceReferenceAvailabilityStatus
