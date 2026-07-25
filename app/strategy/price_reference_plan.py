from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.config.constants import TimeframeName
from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.price_planning_blueprint import (
    PricePlanningBlueprint,
    PricePlanningBlueprintDecision,
    PricePlanningReferenceSource,
)
from app.strategy.setup_candidate import (
    StrategySetupCandidate,
)
from app.strategy.setup_candidate_quality import (
    SetupCandidateQualityTier,
)


class PriceReferenceRole(str, Enum):
    ENTRY = "ENTRY"
    STOP = "STOP"
    TARGET = "TARGET"


class PriceReferenceRelation(str, Enum):
    ENTRY_DISCOUNT = "ENTRY_DISCOUNT"
    ENTRY_PREMIUM = "ENTRY_PREMIUM"
    STOP_BELOW_ENTRY = "STOP_BELOW_ENTRY"
    STOP_ABOVE_ENTRY = "STOP_ABOVE_ENTRY"
    TARGET_ABOVE_ENTRY = "TARGET_ABOVE_ENTRY"
    TARGET_BELOW_ENTRY = "TARGET_BELOW_ENTRY"


class PriceReferenceSelectionMode(str, Enum):
    FIRST_AVAILABLE = "FIRST_AVAILABLE"


class PriceReferencePlanStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PriceReferencePlanReason(str, Enum):
    CREATED = "CREATED"
    BLUEPRINT_BLOCKED = "BLUEPRINT_BLOCKED"


class PriceReferencePlanBlocker(str, Enum):
    BLUEPRINT_BLOCKED = "BLUEPRINT_BLOCKED"


class PriceReferencePlanErrorReason(str, Enum):
    INVALID_BLUEPRINT_DECISION = "INVALID_BLUEPRINT_DECISION"


class PriceReferencePlanError(RuntimeError):
    """Structured price-reference planning failure."""

    def __init__(
        self,
        reason: PriceReferencePlanErrorReason,
        message: str,
    ) -> None:
        self.reason = PriceReferencePlanErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Price-reference plan error [{self.reason.value}]: {self.message}")


_ENTRY_SOURCES = frozenset(
    {
        PricePlanningReferenceSource.OPTIMAL_TRADE_ENTRY_ZONE,
        PricePlanningReferenceSource.FAIR_VALUE_GAP,
        PricePlanningReferenceSource.ORDER_BLOCK,
    }
)
_STOP_SOURCES = frozenset(
    {
        PricePlanningReferenceSource.PROTECTED_SWING,
    }
)
_TARGET_SOURCES = frozenset(
    {
        PricePlanningReferenceSource.LIQUIDITY_POOL,
        PricePlanningReferenceSource.DEALING_RANGE_EXTREME,
    }
)

_ENTRY_RELATIONS = frozenset(
    {
        PriceReferenceRelation.ENTRY_DISCOUNT,
        PriceReferenceRelation.ENTRY_PREMIUM,
    }
)
_STOP_RELATIONS = frozenset(
    {
        PriceReferenceRelation.STOP_BELOW_ENTRY,
        PriceReferenceRelation.STOP_ABOVE_ENTRY,
    }
)
_TARGET_RELATIONS = frozenset(
    {
        PriceReferenceRelation.TARGET_ABOVE_ENTRY,
        PriceReferenceRelation.TARGET_BELOW_ENTRY,
    }
)


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

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


def _allowed_sources_for_role(
    role: PriceReferenceRole,
) -> frozenset[PricePlanningReferenceSource]:
    if role == PriceReferenceRole.ENTRY:
        return _ENTRY_SOURCES

    if role == PriceReferenceRole.STOP:
        return _STOP_SOURCES

    return _TARGET_SOURCES


def _allowed_relations_for_role(
    role: PriceReferenceRole,
) -> frozenset[PriceReferenceRelation]:
    if role == PriceReferenceRole.ENTRY:
        return _ENTRY_RELATIONS

    if role == PriceReferenceRole.STOP:
        return _STOP_RELATIONS

    return _TARGET_RELATIONS


@dataclass(frozen=True, slots=True)
class PriceReferencePlanPolicy:
    """
    Timeframe-role policy for directional price references.

    This policy creates analytical requirements only and
    does not produce executable prices.
    """

    stop_on_execution_timeframe: bool = True
    targets_on_setup_timeframe: bool = True
    selection_mode: PriceReferenceSelectionMode = PriceReferenceSelectionMode.FIRST_AVAILABLE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "stop_on_execution_timeframe",
            _strict_boolean(
                self.stop_on_execution_timeframe,
                "stop_on_execution_timeframe",
            ),
        )
        object.__setattr__(
            self,
            "targets_on_setup_timeframe",
            _strict_boolean(
                self.targets_on_setup_timeframe,
                "targets_on_setup_timeframe",
            ),
        )

        if not isinstance(
            self.selection_mode,
            PriceReferenceSelectionMode,
        ):
            raise ValueError("selection_mode must be a PriceReferenceSelectionMode member.")


@dataclass(frozen=True, slots=True)
class PriceReferenceRequirement:
    """One immutable directional reference requirement."""

    role: PriceReferenceRole
    source: PricePlanningReferenceSource
    priority: int
    relation: PriceReferenceRelation
    timeframe: TimeframeName

    def __post_init__(self) -> None:
        if not isinstance(
            self.role,
            PriceReferenceRole,
        ):
            raise ValueError("role must be a PriceReferenceRole member.")

        if not isinstance(
            self.source,
            PricePlanningReferenceSource,
        ):
            raise ValueError("source must be a PricePlanningReferenceSource member.")

        if self.source not in _allowed_sources_for_role(self.role):
            raise ValueError(f"{self.source.value} is not valid for the {self.role.value} role.")

        object.__setattr__(
            self,
            "priority",
            _positive_integer(
                self.priority,
                "priority",
            ),
        )

        if not isinstance(
            self.relation,
            PriceReferenceRelation,
        ):
            raise ValueError("relation must be a PriceReferenceRelation member.")

        if self.relation not in _allowed_relations_for_role(self.role):
            raise ValueError(f"{self.relation.value} is not valid for the {self.role.value} role.")

        if not isinstance(
            self.timeframe,
            TimeframeName,
        ):
            raise ValueError("timeframe must be a TimeframeName member.")

    @property
    def stable_id(self) -> str:
        return (
            f"{self.role.value}:"
            f"{self.priority}:"
            f"{self.source.value}:"
            f"{self.relation.value}:"
            f"{self.timeframe.value}"
        )


def _relations_for_direction(
    direction: DirectionalPermissionDirection,
) -> tuple[
    PriceReferenceRelation,
    PriceReferenceRelation,
    PriceReferenceRelation,
]:
    if direction == DirectionalPermissionDirection.BULLISH:
        return (
            PriceReferenceRelation.ENTRY_DISCOUNT,
            PriceReferenceRelation.STOP_BELOW_ENTRY,
            PriceReferenceRelation.TARGET_ABOVE_ENTRY,
        )

    if direction == DirectionalPermissionDirection.BEARISH:
        return (
            PriceReferenceRelation.ENTRY_PREMIUM,
            PriceReferenceRelation.STOP_ABOVE_ENTRY,
            PriceReferenceRelation.TARGET_BELOW_ENTRY,
        )

    raise ValueError("Price-reference planning requires a resolved bullish or bearish direction.")


def _build_requirements(
    blueprint: PricePlanningBlueprint,
    policy: PriceReferencePlanPolicy,
) -> tuple[PriceReferenceRequirement, ...]:
    (
        entry_relation,
        stop_relation,
        target_relation,
    ) = _relations_for_direction(blueprint.direction)

    stop_timeframe = (
        blueprint.execution_timeframe
        if policy.stop_on_execution_timeframe
        else blueprint.setup_timeframe
    )
    target_timeframe = (
        blueprint.setup_timeframe
        if policy.targets_on_setup_timeframe
        else blueprint.execution_timeframe
    )

    requirements: list[PriceReferenceRequirement] = []

    for priority, source in enumerate(
        blueprint.entry_sources,
        start=1,
    ):
        requirements.append(
            PriceReferenceRequirement(
                role=PriceReferenceRole.ENTRY,
                source=source,
                priority=priority,
                relation=entry_relation,
                timeframe=blueprint.setup_timeframe,
            )
        )

    requirements.append(
        PriceReferenceRequirement(
            role=PriceReferenceRole.STOP,
            source=blueprint.stop_source,
            priority=1,
            relation=stop_relation,
            timeframe=stop_timeframe,
        )
    )

    for priority, source in enumerate(
        blueprint.target_sources,
        start=1,
    ):
        requirements.append(
            PriceReferenceRequirement(
                role=PriceReferenceRole.TARGET,
                source=source,
                priority=priority,
                relation=target_relation,
                timeframe=target_timeframe,
            )
        )

    return tuple(requirements)


@dataclass(frozen=True, slots=True)
class DirectionalPriceReferencePlan:
    """
    Immutable non-executable directional reference plan.

    The plan identifies sources, relations, priorities, and
    timeframes. It deliberately contains no price levels.
    """

    blueprint: PricePlanningBlueprint
    policy: PriceReferencePlanPolicy
    direction: DirectionalPermissionDirection
    requirements: tuple[
        PriceReferenceRequirement,
        ...,
    ]

    def __post_init__(self) -> None:
        if not isinstance(
            self.blueprint,
            PricePlanningBlueprint,
        ):
            raise ValueError("blueprint must be a PricePlanningBlueprint.")

        if not isinstance(
            self.policy,
            PriceReferencePlanPolicy,
        ):
            raise ValueError("policy must be a PriceReferencePlanPolicy.")

        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if self.direction == DirectionalPermissionDirection.NONE:
            raise ValueError("A reference plan requires a resolved bullish or bearish direction.")

        if self.direction != self.blueprint.direction:
            raise ValueError("Reference-plan direction must match the blueprint.")

        if not isinstance(self.requirements, tuple):
            raise ValueError("requirements must be a tuple.")

        if not self.requirements:
            raise ValueError("requirements cannot be empty.")

        for requirement in self.requirements:
            if not isinstance(
                requirement,
                PriceReferenceRequirement,
            ):
                raise ValueError("requirements must contain PriceReferenceRequirement objects.")

        expected = _build_requirements(
            self.blueprint,
            self.policy,
        )

        if self.requirements != expected:
            raise ValueError("Reference-plan requirements do not match the blueprint and policy.")

    @property
    def candidate(self) -> StrategySetupCandidate:
        return self.blueprint.candidate

    @property
    def broker_symbol(self) -> str:
        return self.blueprint.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.blueprint.observed_at

    @property
    def quality_score(self) -> Decimal:
        return self.blueprint.quality_score

    @property
    def quality_tier(self) -> SetupCandidateQualityTier:
        return self.blueprint.quality_tier

    @property
    def selection_mode(
        self,
    ) -> PriceReferenceSelectionMode:
        return self.policy.selection_mode

    @property
    def entry_requirements(
        self,
    ) -> tuple[PriceReferenceRequirement, ...]:
        return tuple(
            requirement
            for requirement in self.requirements
            if requirement.role == PriceReferenceRole.ENTRY
        )

    @property
    def stop_requirement(
        self,
    ) -> PriceReferenceRequirement:
        matches = tuple(
            requirement
            for requirement in self.requirements
            if requirement.role == PriceReferenceRole.STOP
        )

        if len(matches) != 1:
            raise ValueError("A reference plan must contain exactly one stop requirement.")

        return matches[0]

    @property
    def target_requirements(
        self,
    ) -> tuple[PriceReferenceRequirement, ...]:
        return tuple(
            requirement
            for requirement in self.requirements
            if requirement.role == PriceReferenceRole.TARGET
        )

    @property
    def is_bullish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BEARISH

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def plan_id(self) -> str:
        requirement_fragment = "|".join(requirement.stable_id for requirement in self.requirements)

        return (
            f"{self.blueprint.blueprint_id}:"
            f"MODE[{self.selection_mode.value}]:"
            f"REFERENCES[{requirement_fragment}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.blueprint.stable_id}:PRICE_REFERENCE_PLAN:{self.plan_id}"


@dataclass(frozen=True, slots=True)
class _PriceReferencePlanEvaluation:
    status: PriceReferencePlanStatus
    reason: PriceReferencePlanReason
    blockers: tuple[
        PriceReferencePlanBlocker,
        ...,
    ]
    plan: DirectionalPriceReferencePlan | None


def _derive_plan(
    blueprint_decision: PricePlanningBlueprintDecision,
    policy: PriceReferencePlanPolicy,
) -> _PriceReferencePlanEvaluation:
    if blueprint_decision.is_blocked:
        return _PriceReferencePlanEvaluation(
            status=PriceReferencePlanStatus.BLOCKED,
            reason=(PriceReferencePlanReason.BLUEPRINT_BLOCKED),
            blockers=(PriceReferencePlanBlocker.BLUEPRINT_BLOCKED,),
            plan=None,
        )

    blueprint = blueprint_decision.blueprint_required
    plan = DirectionalPriceReferencePlan(
        blueprint=blueprint,
        policy=policy,
        direction=blueprint.direction,
        requirements=_build_requirements(
            blueprint,
            policy,
        ),
    )

    return _PriceReferencePlanEvaluation(
        status=PriceReferencePlanStatus.CREATED,
        reason=PriceReferencePlanReason.CREATED,
        blockers=(),
        plan=plan,
    )


@dataclass(frozen=True, slots=True)
class PriceReferencePlanDecision:
    """Validated directional reference-plan result."""

    blueprint_decision: PricePlanningBlueprintDecision
    policy: PriceReferencePlanPolicy
    status: PriceReferencePlanStatus
    reason: PriceReferencePlanReason
    blockers: tuple[
        PriceReferencePlanBlocker,
        ...,
    ]
    plan: DirectionalPriceReferencePlan | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.blueprint_decision,
            PricePlanningBlueprintDecision,
        ):
            raise ValueError("blueprint_decision must be a PricePlanningBlueprintDecision.")

        if not isinstance(
            self.policy,
            PriceReferencePlanPolicy,
        ):
            raise ValueError("policy must be a PriceReferencePlanPolicy.")

        try:
            status = PriceReferencePlanStatus(self.status)
            reason = PriceReferencePlanReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported reference-plan status or reason.") from error

        blockers = tuple(PriceReferencePlanBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Reference-plan blockers cannot contain duplicates.")

        if self.plan is not None and not isinstance(
            self.plan,
            DirectionalPriceReferencePlan,
        ):
            raise ValueError("plan must be a DirectionalPriceReferencePlan or None.")

        expected = _derive_plan(
            self.blueprint_decision,
            self.policy,
        )
        supplied = _PriceReferencePlanEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            plan=self.plan,
        )

        if supplied != expected:
            raise ValueError(
                "Reference-plan result does not match its blueprint decision and policy."
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
    def blueprint(self) -> PricePlanningBlueprint | None:
        return self.blueprint_decision.blueprint

    @property
    def broker_symbol(self) -> str:
        return self.blueprint_decision.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.blueprint_decision.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.blueprint_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == PriceReferencePlanStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_plan(self) -> bool:
        return self.plan is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def plan_required(
        self,
    ) -> DirectionalPriceReferencePlan:
        if self.plan is None:
            raise ValueError("No directional price-reference plan was created.")

        return self.plan

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.blueprint_decision.stable_id}:"
            f"REFERENCE_PLAN_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPriceReferencePlanFactory:
    """
    Pure directional price-reference plan factory.

    CREATED means reference lookup may continue. It does not
    create executable price levels or trading permission.
    """

    def __init__(
        self,
        policy: PriceReferencePlanPolicy | None = None,
    ) -> None:
        selected_policy = policy or PriceReferencePlanPolicy()

        if not isinstance(
            selected_policy,
            PriceReferencePlanPolicy,
        ):
            raise ValueError("policy must be a PriceReferencePlanPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> PriceReferencePlanPolicy:
        return self._policy

    def generate(
        self,
        blueprint_decision: PricePlanningBlueprintDecision,
    ) -> PriceReferencePlanDecision:
        if not isinstance(
            blueprint_decision,
            PricePlanningBlueprintDecision,
        ):
            raise PriceReferencePlanError(
                PriceReferencePlanErrorReason.INVALID_BLUEPRINT_DECISION,
                "blueprint_decision must be a PricePlanningBlueprintDecision.",
            )

        evaluation = _derive_plan(
            blueprint_decision,
            self._policy,
        )

        return PriceReferencePlanDecision(
            blueprint_decision=blueprint_decision,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            plan=evaluation.plan,
        )

    def build(
        self,
        blueprint_decision: PricePlanningBlueprintDecision,
    ) -> PriceReferencePlanDecision:
        """Compatibility alias for generate()."""

        return self.generate(blueprint_decision)

    def evaluate(
        self,
        blueprint_decision: PricePlanningBlueprintDecision,
    ) -> PriceReferencePlanDecision:
        """Compatibility alias for generate()."""

        return self.generate(blueprint_decision)


def generate_price_reference_plan(
    blueprint_decision: PricePlanningBlueprintDecision,
    policy: PriceReferencePlanPolicy | None = None,
) -> PriceReferencePlanDecision:
    return StrategyPriceReferencePlanFactory(policy=policy).generate(blueprint_decision)


DirectionalReferencePlan = DirectionalPriceReferencePlan
PlanningReferencePlanDecision = PriceReferencePlanDecision
PlanningReferencePlanFactory = StrategyPriceReferencePlanFactory
PlanningReferencePlanPolicy = PriceReferencePlanPolicy
PriceReferencePlanFactory = StrategyPriceReferencePlanFactory
ReferencePlanBlocker = PriceReferencePlanBlocker
ReferencePlanReason = PriceReferencePlanReason
ReferencePlanStatus = PriceReferencePlanStatus
ReferenceRequirement = PriceReferenceRequirement
