from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.config.constants import TimeframeName
from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.price_planning_admission import (
    PricePlanningAdmissionDecision,
)
from app.strategy.setup_candidate import (
    StrategySetupCandidate,
)
from app.strategy.setup_candidate_quality import (
    SetupCandidateQualityTier,
)


class PricePlanningReferenceSource(str, Enum):
    OPTIMAL_TRADE_ENTRY_ZONE = "OPTIMAL_TRADE_ENTRY_ZONE"
    FAIR_VALUE_GAP = "FAIR_VALUE_GAP"
    ORDER_BLOCK = "ORDER_BLOCK"
    PROTECTED_SWING = "PROTECTED_SWING"
    LIQUIDITY_POOL = "LIQUIDITY_POOL"
    DEALING_RANGE_EXTREME = "DEALING_RANGE_EXTREME"


class PricePlanningBlueprintStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PricePlanningBlueprintReason(str, Enum):
    CREATED = "CREATED"
    ADMISSION_BLOCKED = "ADMISSION_BLOCKED"


class PricePlanningBlueprintBlocker(str, Enum):
    ADMISSION_BLOCKED = "ADMISSION_BLOCKED"


class PricePlanningBlueprintErrorReason(str, Enum):
    INVALID_ADMISSION = "INVALID_ADMISSION"


class PricePlanningBlueprintError(RuntimeError):
    """Structured price-planning blueprint failure."""

    def __init__(
        self,
        reason: PricePlanningBlueprintErrorReason,
        message: str,
    ) -> None:
        self.reason = PricePlanningBlueprintErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Price-planning blueprint error [{self.reason.value}]: {self.message}")


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


def _strict_source_priority(
    value: object,
    *,
    field_name: str,
    allowed: frozenset[PricePlanningReferenceSource],
) -> tuple[PricePlanningReferenceSource, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{field_name} must be a tuple.")

    if not value:
        raise ValueError(f"{field_name} cannot be empty.")

    normalized: list[PricePlanningReferenceSource] = []

    for source in value:
        if not isinstance(
            source,
            PricePlanningReferenceSource,
        ):
            raise ValueError(f"{field_name} must contain PricePlanningReferenceSource members.")

        if source not in allowed:
            raise ValueError(f"{source.value} is not permitted in {field_name}.")

        normalized.append(source)

    normalized_tuple = tuple(normalized)

    if len(set(normalized_tuple)) != len(normalized_tuple):
        raise ValueError(f"{field_name} cannot contain duplicates.")

    return normalized_tuple


@dataclass(frozen=True, slots=True)
class PricePlanningBlueprintPolicy:
    """
    Reference-source priorities for later price planning.

    The policy defines analytical source preferences only.
    It does not create prices or authorize trading.
    """

    entry_source_priority: tuple[
        PricePlanningReferenceSource,
        ...,
    ] = (
        PricePlanningReferenceSource.OPTIMAL_TRADE_ENTRY_ZONE,
        PricePlanningReferenceSource.FAIR_VALUE_GAP,
        PricePlanningReferenceSource.ORDER_BLOCK,
    )
    stop_reference_source: PricePlanningReferenceSource = (
        PricePlanningReferenceSource.PROTECTED_SWING
    )
    target_source_priority: tuple[
        PricePlanningReferenceSource,
        ...,
    ] = (
        PricePlanningReferenceSource.LIQUIDITY_POOL,
        PricePlanningReferenceSource.DEALING_RANGE_EXTREME,
    )

    def __post_init__(self) -> None:
        entry_sources = _strict_source_priority(
            self.entry_source_priority,
            field_name="entry_source_priority",
            allowed=_ENTRY_SOURCES,
        )
        target_sources = _strict_source_priority(
            self.target_source_priority,
            field_name="target_source_priority",
            allowed=_TARGET_SOURCES,
        )

        if not isinstance(
            self.stop_reference_source,
            PricePlanningReferenceSource,
        ):
            raise ValueError("stop_reference_source must be a PricePlanningReferenceSource member.")

        if self.stop_reference_source not in _STOP_SOURCES:
            raise ValueError("stop_reference_source must be PROTECTED_SWING.")

        object.__setattr__(
            self,
            "entry_source_priority",
            entry_sources,
        )
        object.__setattr__(
            self,
            "target_source_priority",
            target_sources,
        )


@dataclass(frozen=True, slots=True)
class PricePlanningBlueprint:
    """
    Immutable non-executable price-planning blueprint.

    No entry price, stop-loss price, take-profit price,
    volume, or broker order is produced at this stage.
    """

    admission: PricePlanningAdmissionDecision
    policy: PricePlanningBlueprintPolicy
    direction: DirectionalPermissionDirection
    setup_timeframe: TimeframeName
    execution_timeframe: TimeframeName
    entry_sources: tuple[
        PricePlanningReferenceSource,
        ...,
    ]
    stop_source: PricePlanningReferenceSource
    target_sources: tuple[
        PricePlanningReferenceSource,
        ...,
    ]

    def __post_init__(self) -> None:
        if not isinstance(
            self.admission,
            PricePlanningAdmissionDecision,
        ):
            raise ValueError("admission must be a PricePlanningAdmissionDecision.")

        if not self.admission.is_admitted:
            raise ValueError(
                "A price-planning blueprint requires an admitted price-planning decision."
            )

        if not isinstance(
            self.policy,
            PricePlanningBlueprintPolicy,
        ):
            raise ValueError("policy must be a PricePlanningBlueprintPolicy.")

        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if self.direction == DirectionalPermissionDirection.NONE:
            raise ValueError("A blueprint requires a resolved bullish or bearish direction.")

        if self.direction != self.admission.direction:
            raise ValueError("Blueprint direction must match admission.")

        if not isinstance(
            self.setup_timeframe,
            TimeframeName,
        ):
            raise ValueError("setup_timeframe must be a TimeframeName member.")

        if not isinstance(
            self.execution_timeframe,
            TimeframeName,
        ):
            raise ValueError("execution_timeframe must be a TimeframeName member.")

        if self.setup_timeframe != self.admission.candidate.setup_timeframe:
            raise ValueError("Blueprint setup timeframe must match the admitted candidate.")

        if self.execution_timeframe != self.admission.candidate.execution_timeframe:
            raise ValueError("Blueprint execution timeframe must match the admitted candidate.")

        entry_sources = _strict_source_priority(
            self.entry_sources,
            field_name="entry_sources",
            allowed=_ENTRY_SOURCES,
        )
        target_sources = _strict_source_priority(
            self.target_sources,
            field_name="target_sources",
            allowed=_TARGET_SOURCES,
        )

        if not isinstance(
            self.stop_source,
            PricePlanningReferenceSource,
        ):
            raise ValueError("stop_source must be a PricePlanningReferenceSource member.")

        if self.stop_source not in _STOP_SOURCES:
            raise ValueError("stop_source must be PROTECTED_SWING.")

        if entry_sources != self.policy.entry_source_priority:
            raise ValueError("Blueprint entry sources must match the blueprint policy.")

        if self.stop_source != self.policy.stop_reference_source:
            raise ValueError("Blueprint stop source must match the blueprint policy.")

        if target_sources != self.policy.target_source_priority:
            raise ValueError("Blueprint target sources must match the blueprint policy.")

        object.__setattr__(
            self,
            "entry_sources",
            entry_sources,
        )
        object.__setattr__(
            self,
            "target_sources",
            target_sources,
        )

    @property
    def candidate(self) -> StrategySetupCandidate:
        return self.admission.candidate

    @property
    def broker_symbol(self) -> str:
        return self.admission.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.admission.observed_at

    @property
    def quality_score(self) -> Decimal:
        return self.admission.score

    @property
    def quality_tier(self) -> SetupCandidateQualityTier:
        return self.admission.tier

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
    def blueprint_id(self) -> str:
        entry_fragment = ",".join(source.value for source in self.entry_sources)
        target_fragment = ",".join(source.value for source in self.target_sources)

        return (
            f"{self.candidate.candidate_id}:"
            f"ENTRY[{entry_fragment}]:"
            f"STOP[{self.stop_source.value}]:"
            f"TARGET[{target_fragment}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.admission.stable_id}:PRICE_PLANNING_BLUEPRINT:{self.blueprint_id}"


@dataclass(frozen=True, slots=True)
class _PricePlanningBlueprintEvaluation:
    status: PricePlanningBlueprintStatus
    reason: PricePlanningBlueprintReason
    blockers: tuple[
        PricePlanningBlueprintBlocker,
        ...,
    ]
    blueprint: PricePlanningBlueprint | None


def _derive_blueprint(
    admission: PricePlanningAdmissionDecision,
    policy: PricePlanningBlueprintPolicy,
) -> _PricePlanningBlueprintEvaluation:
    if admission.is_blocked:
        return _PricePlanningBlueprintEvaluation(
            status=PricePlanningBlueprintStatus.BLOCKED,
            reason=(PricePlanningBlueprintReason.ADMISSION_BLOCKED),
            blockers=(PricePlanningBlueprintBlocker.ADMISSION_BLOCKED,),
            blueprint=None,
        )

    blueprint = PricePlanningBlueprint(
        admission=admission,
        policy=policy,
        direction=admission.direction,
        setup_timeframe=(admission.candidate.setup_timeframe),
        execution_timeframe=(admission.candidate.execution_timeframe),
        entry_sources=policy.entry_source_priority,
        stop_source=policy.stop_reference_source,
        target_sources=policy.target_source_priority,
    )

    return _PricePlanningBlueprintEvaluation(
        status=PricePlanningBlueprintStatus.CREATED,
        reason=PricePlanningBlueprintReason.CREATED,
        blockers=(),
        blueprint=blueprint,
    )


@dataclass(frozen=True, slots=True)
class PricePlanningBlueprintDecision:
    """Validated price-planning blueprint result."""

    admission: PricePlanningAdmissionDecision
    policy: PricePlanningBlueprintPolicy
    status: PricePlanningBlueprintStatus
    reason: PricePlanningBlueprintReason
    blockers: tuple[
        PricePlanningBlueprintBlocker,
        ...,
    ]
    blueprint: PricePlanningBlueprint | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.admission,
            PricePlanningAdmissionDecision,
        ):
            raise ValueError("admission must be a PricePlanningAdmissionDecision.")

        if not isinstance(
            self.policy,
            PricePlanningBlueprintPolicy,
        ):
            raise ValueError("policy must be a PricePlanningBlueprintPolicy.")

        try:
            status = PricePlanningBlueprintStatus(self.status)
            reason = PricePlanningBlueprintReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported blueprint status or reason.") from error

        blockers = tuple(PricePlanningBlueprintBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Blueprint blockers cannot contain duplicates.")

        if self.blueprint is not None and not isinstance(
            self.blueprint,
            PricePlanningBlueprint,
        ):
            raise ValueError("blueprint must be a PricePlanningBlueprint or None.")

        expected = _derive_blueprint(
            self.admission,
            self.policy,
        )
        supplied = _PricePlanningBlueprintEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            blueprint=self.blueprint,
        )

        if supplied != expected:
            raise ValueError("Blueprint result does not match its admission and policy.")

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
        return self.admission.candidate

    @property
    def broker_symbol(self) -> str:
        return self.admission.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.admission.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.admission.direction

    @property
    def quality_score(self) -> Decimal:
        return self.admission.score

    @property
    def quality_tier(self) -> SetupCandidateQualityTier:
        return self.admission.tier

    @property
    def is_created(self) -> bool:
        return self.status == PricePlanningBlueprintStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_blueprint(self) -> bool:
        return self.blueprint is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def blueprint_required(
        self,
    ) -> PricePlanningBlueprint:
        if self.blueprint is None:
            raise ValueError("No price-planning blueprint was created.")

        return self.blueprint

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.admission.stable_id}:"
            f"BLUEPRINT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPricePlanningBlueprintFactory:
    """
    Pure factory for non-executable planning blueprints.

    CREATED means reference-source planning may continue.
    It does not grant permission to trade.
    """

    def __init__(
        self,
        policy: PricePlanningBlueprintPolicy | None = None,
    ) -> None:
        selected_policy = policy or PricePlanningBlueprintPolicy()

        if not isinstance(
            selected_policy,
            PricePlanningBlueprintPolicy,
        ):
            raise ValueError("policy must be a PricePlanningBlueprintPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> PricePlanningBlueprintPolicy:
        return self._policy

    def generate(
        self,
        admission: PricePlanningAdmissionDecision,
    ) -> PricePlanningBlueprintDecision:
        if not isinstance(
            admission,
            PricePlanningAdmissionDecision,
        ):
            raise PricePlanningBlueprintError(
                PricePlanningBlueprintErrorReason.INVALID_ADMISSION,
                "admission must be a PricePlanningAdmissionDecision.",
            )

        evaluation = _derive_blueprint(
            admission,
            self._policy,
        )

        return PricePlanningBlueprintDecision(
            admission=admission,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            blueprint=evaluation.blueprint,
        )

    def build(
        self,
        admission: PricePlanningAdmissionDecision,
    ) -> PricePlanningBlueprintDecision:
        """Compatibility alias for generate()."""

        return self.generate(admission)

    def evaluate(
        self,
        admission: PricePlanningAdmissionDecision,
    ) -> PricePlanningBlueprintDecision:
        """Compatibility alias for generate()."""

        return self.generate(admission)


def generate_price_planning_blueprint(
    admission: PricePlanningAdmissionDecision,
    policy: PricePlanningBlueprintPolicy | None = None,
) -> PricePlanningBlueprintDecision:
    return StrategyPricePlanningBlueprintFactory(policy=policy).generate(admission)


PlanningBlueprint = PricePlanningBlueprint
PlanningBlueprintBlocker = PricePlanningBlueprintBlocker
PlanningBlueprintDecision = PricePlanningBlueprintDecision
PlanningBlueprintFactory = StrategyPricePlanningBlueprintFactory
PlanningBlueprintPolicy = PricePlanningBlueprintPolicy
PlanningBlueprintReason = PricePlanningBlueprintReason
PlanningBlueprintStatus = PricePlanningBlueprintStatus
PlanningReferenceSource = PricePlanningReferenceSource
PriceBlueprintFactory = StrategyPricePlanningBlueprintFactory
