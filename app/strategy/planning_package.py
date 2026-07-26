from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.order_intent_blueprint import (
    OrderIntentBlueprintDecision,
    StrategyOrderIntentBlueprint,
    StrategyOrderSide,
)
from app.strategy.order_intent_execution_lock import (
    ExecutionBoundaryLockDecision,
    StrategyExecutionBoundaryLock,
)
from app.strategy.position_size_calculation import (
    PositionSizeCalculationDecision,
    PositionSizeMetrics,
)
from app.strategy.position_sizing_handoff import (
    PositionSizingHandoffDecision,
    StrategyPositionSizingHandoff,
)
from app.strategy.position_sizing_specification import (
    PositionSizingSpecification,
    PositionSizingSpecificationDecision,
)
from app.strategy.risk_budget_admission import (
    RiskBudgetAdmissionDecision,
)
from app.strategy.sized_trade_plan import (
    SizedTradePlanDecision,
    StrategySizedTradePlan,
)

_ZERO = Decimal("0")


class StrategyPlanningPackageStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class StrategyPlanningPackageReason(str, Enum):
    CREATED = "CREATED"
    EXECUTION_LOCK_BLOCKED = "EXECUTION_LOCK_BLOCKED"


class StrategyPlanningPackageBlocker(str, Enum):
    EXECUTION_LOCK_BLOCKED = "EXECUTION_LOCK_BLOCKED"


class StrategyPlanningPackageErrorReason(str, Enum):
    INVALID_EXECUTION_LOCK_DECISION = "INVALID_EXECUTION_LOCK_DECISION"


class StrategyPlanningPackageError(RuntimeError):
    """Structured strategy-planning package failure."""

    def __init__(
        self,
        reason: StrategyPlanningPackageErrorReason,
        message: str,
    ) -> None:
        self.reason = StrategyPlanningPackageErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Strategy-planning package error [{self.reason.value}]: {self.message}")


def _canonical_decimal(value: Decimal) -> str:
    if value == _ZERO:
        return "0"

    return format(value.normalize(), "f")


@dataclass(frozen=True, slots=True)
class StrategyPlanningPackage:
    """
    Immutable, audit-ready analytical strategy package.

    The package preserves the complete validated planning
    lineage without adding broker-request construction,
    execution authorization, or order submission.
    """

    execution_lock: ExecutionBoundaryLockDecision
    order_intent: OrderIntentBlueprintDecision
    sized_plan: SizedTradePlanDecision
    position_size: PositionSizeCalculationDecision
    sizing_specification: PositionSizingSpecificationDecision
    sizing_handoff: PositionSizingHandoffDecision
    risk_admission: RiskBudgetAdmissionDecision

    def __post_init__(self) -> None:
        expected_types = (
            (
                "execution_lock",
                self.execution_lock,
                ExecutionBoundaryLockDecision,
            ),
            (
                "order_intent",
                self.order_intent,
                OrderIntentBlueprintDecision,
            ),
            (
                "sized_plan",
                self.sized_plan,
                SizedTradePlanDecision,
            ),
            (
                "position_size",
                self.position_size,
                PositionSizeCalculationDecision,
            ),
            (
                "sizing_specification",
                self.sizing_specification,
                PositionSizingSpecificationDecision,
            ),
            (
                "sizing_handoff",
                self.sizing_handoff,
                PositionSizingHandoffDecision,
            ),
            (
                "risk_admission",
                self.risk_admission,
                RiskBudgetAdmissionDecision,
            ),
        )

        for field_name, value, expected_type in expected_types:
            if not isinstance(value, expected_type):
                raise ValueError(f"{field_name} must be a {expected_type.__name__}.")

        if not self.execution_lock.is_locked:
            raise ValueError("A planning package requires a locked execution-boundary decision.")

        if not self.order_intent.is_created:
            raise ValueError("Planning package requires a created order-intent blueprint.")

        if not self.sized_plan.is_created:
            raise ValueError("Planning package requires a created sized trade plan.")

        if not self.position_size.is_calculated:
            raise ValueError("Planning package requires a calculated position-size decision.")

        if not self.sizing_specification.is_ready:
            raise ValueError("Planning package requires a ready sizing specification.")

        if not self.sizing_handoff.is_created:
            raise ValueError("Planning package requires a created sizing handoff.")

        if not self.risk_admission.is_admitted:
            raise ValueError("Planning package requires an admitted risk-budget decision.")

        lineage = (
            (
                self.order_intent,
                self.execution_lock.order_intent,
                "order_intent",
            ),
            (
                self.sized_plan,
                self.order_intent.sized_plan,
                "sized_plan",
            ),
            (
                self.position_size,
                self.sized_plan.position_size,
                "position_size",
            ),
            (
                self.sizing_specification,
                self.position_size.specification_decision,
                "sizing_specification",
            ),
            (
                self.sizing_handoff,
                self.sizing_specification.handoff_decision,
                "sizing_handoff",
            ),
            (
                self.risk_admission,
                self.sizing_handoff.risk_admission,
                "risk_admission",
            ),
        )

        for supplied, expected, field_name in lineage:
            if supplied is not expected:
                raise ValueError(f"{field_name} must preserve exact strategy lineage.")

        symbol = self.execution_lock.broker_symbol
        observed_at = self.execution_lock.observed_at
        direction = self.execution_lock.direction

        for component_name, component in (
            ("order_intent", self.order_intent),
            ("sized_plan", self.sized_plan),
            ("position_size", self.position_size),
            (
                "sizing_specification",
                self.sizing_specification,
            ),
            ("sizing_handoff", self.sizing_handoff),
            ("risk_admission", self.risk_admission),
        ):
            if component.broker_symbol != symbol:
                raise ValueError(
                    f"{component_name} broker symbol does not match the execution lock."
                )

            if component.observed_at != observed_at:
                raise ValueError(
                    f"{component_name} observation time does not match the execution lock."
                )

            if component.direction != direction:
                raise ValueError(f"{component_name} direction does not match the execution lock.")

        if self.execution_lock.execution_authorized:
            raise ValueError("Planning package cannot contain execution authorization.")

        if self.execution_lock.has_broker_request:
            raise ValueError("Planning package cannot contain a broker request.")

        if self.execution_lock.can_build_broker_request:
            raise ValueError("Planning package cannot build a broker request.")

        if self.execution_lock.can_submit_order:
            raise ValueError("Planning package cannot submit an order.")

        if self.execution_lock.is_executable:
            raise ValueError("Planning package cannot contain an executable boundary decision.")

    @property
    def lock(self) -> StrategyExecutionBoundaryLock:
        return self.execution_lock.lock_required

    @property
    def blueprint(
        self,
    ) -> StrategyOrderIntentBlueprint:
        return self.order_intent.blueprint_required

    @property
    def plan(self) -> StrategySizedTradePlan:
        return self.sized_plan.plan_required

    @property
    def metrics(self) -> PositionSizeMetrics:
        metrics = self.position_size.metrics

        if metrics is None:
            raise ValueError("Planning package has no position-size metrics.")

        return metrics

    @property
    def specification(
        self,
    ) -> PositionSizingSpecification:
        return self.sizing_specification.specification_required

    @property
    def handoff(
        self,
    ) -> StrategyPositionSizingHandoff:
        return self.sizing_handoff.handoff_required

    @property
    def broker_symbol(self) -> str:
        return self.execution_lock.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.execution_lock.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.execution_lock.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.blueprint.side

    @property
    def entry_price(self) -> Decimal:
        return self.plan.entry_price

    @property
    def stop_loss(self) -> Decimal:
        return self.plan.stop_loss

    @property
    def take_profit(self) -> Decimal:
        return self.plan.take_profit

    @property
    def volume(self) -> Decimal:
        return self.plan.volume

    @property
    def approved_risk_amount(self) -> Decimal:
        return self.plan.approved_risk_amount

    @property
    def actual_risk_amount(self) -> Decimal:
        return self.plan.actual_risk_amount

    @property
    def unused_risk_amount(self) -> Decimal:
        return self.plan.unused_risk_amount

    @property
    def reward_risk_ratio(self) -> Decimal:
        return self.plan.reward_risk_ratio

    @property
    def risk_utilization_percent(self) -> Decimal:
        return self.plan.risk_utilization_percent

    @property
    def component_count(self) -> int:
        return 7

    @property
    def is_complete(self) -> bool:
        return True

    @property
    def is_locked(self) -> bool:
        return True

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def can_build_broker_request(self) -> bool:
        return False

    @property
    def can_submit_order(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def package_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"ENTRY["
            f"{_canonical_decimal(self.entry_price)}]:"
            f"STOP["
            f"{_canonical_decimal(self.stop_loss)}]:"
            f"TARGET["
            f"{_canonical_decimal(self.take_profit)}]:"
            f"VOLUME["
            f"{_canonical_decimal(self.volume)}]:"
            f"APPROVED_RISK["
            f"{_canonical_decimal(self.approved_risk_amount)}]:"
            f"ACTUAL_RISK["
            f"{_canonical_decimal(self.actual_risk_amount)}]:"
            f"RR["
            f"{_canonical_decimal(self.reward_risk_ratio)}]:"
            f"EXECUTION_LOCKED"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.execution_lock.stable_id}:STRATEGY_PLANNING_PACKAGE:{self.package_id}"


@dataclass(frozen=True, slots=True)
class _PlanningPackageEvaluation:
    status: StrategyPlanningPackageStatus
    reason: StrategyPlanningPackageReason
    blockers: tuple[
        StrategyPlanningPackageBlocker,
        ...,
    ]
    package: StrategyPlanningPackage | None


def _derive_package(
    execution_lock: ExecutionBoundaryLockDecision,
) -> _PlanningPackageEvaluation:
    if execution_lock.is_blocked:
        return _PlanningPackageEvaluation(
            status=StrategyPlanningPackageStatus.BLOCKED,
            reason=(StrategyPlanningPackageReason.EXECUTION_LOCK_BLOCKED),
            blockers=(StrategyPlanningPackageBlocker.EXECUTION_LOCK_BLOCKED,),
            package=None,
        )

    order_intent = execution_lock.order_intent
    sized_plan = order_intent.sized_plan
    position_size = sized_plan.position_size
    sizing_specification = position_size.specification_decision
    sizing_handoff = sizing_specification.handoff_decision
    risk_admission = sizing_handoff.risk_admission

    package = StrategyPlanningPackage(
        execution_lock=execution_lock,
        order_intent=order_intent,
        sized_plan=sized_plan,
        position_size=position_size,
        sizing_specification=sizing_specification,
        sizing_handoff=sizing_handoff,
        risk_admission=risk_admission,
    )

    return _PlanningPackageEvaluation(
        status=StrategyPlanningPackageStatus.CREATED,
        reason=StrategyPlanningPackageReason.CREATED,
        blockers=(),
        package=package,
    )


@dataclass(frozen=True, slots=True)
class StrategyPlanningPackageDecision:
    """Validated strategy-planning package result."""

    execution_lock: ExecutionBoundaryLockDecision
    status: StrategyPlanningPackageStatus
    reason: StrategyPlanningPackageReason
    blockers: tuple[
        StrategyPlanningPackageBlocker,
        ...,
    ]
    package: StrategyPlanningPackage | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.execution_lock,
            ExecutionBoundaryLockDecision,
        ):
            raise ValueError("execution_lock must be an ExecutionBoundaryLockDecision.")

        try:
            status = StrategyPlanningPackageStatus(self.status)
            reason = StrategyPlanningPackageReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported planning-package status or reason.") from error

        blockers = tuple(StrategyPlanningPackageBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Planning-package blockers cannot contain duplicates.")

        if self.package is not None and not isinstance(
            self.package,
            StrategyPlanningPackage,
        ):
            raise ValueError("package must be a StrategyPlanningPackage or None.")

        expected = _derive_package(self.execution_lock)
        supplied = _PlanningPackageEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            package=self.package,
        )

        if supplied != expected:
            raise ValueError(
                "Planning-package result does not match its execution-boundary decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.execution_lock.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.execution_lock.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.execution_lock.direction

    @property
    def is_created(self) -> bool:
        return self.status == StrategyPlanningPackageStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_package(self) -> bool:
        return self.package is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def package_required(
        self,
    ) -> StrategyPlanningPackage:
        if self.package is None:
            raise ValueError("No strategy-planning package was created.")

        return self.package

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def can_submit_order(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.execution_lock.stable_id}:"
            f"STRATEGY_PLANNING_PACKAGE_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningPackageFactory:
    """
    Pure factory for the complete analytical planning chain.

    CREATED means the package is ready for audit, logging,
    persistence design, or orchestration analysis only.
    """

    def generate(
        self,
        execution_lock: ExecutionBoundaryLockDecision,
    ) -> StrategyPlanningPackageDecision:
        if not isinstance(
            execution_lock,
            ExecutionBoundaryLockDecision,
        ):
            raise StrategyPlanningPackageError(
                StrategyPlanningPackageErrorReason.INVALID_EXECUTION_LOCK_DECISION,
                "execution_lock must be an ExecutionBoundaryLockDecision.",
            )

        evaluation = _derive_package(execution_lock)

        return StrategyPlanningPackageDecision(
            execution_lock=execution_lock,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            package=evaluation.package,
        )

    def build(
        self,
        execution_lock: ExecutionBoundaryLockDecision,
    ) -> StrategyPlanningPackageDecision:
        """Compatibility alias for generate()."""

        return self.generate(execution_lock)

    def evaluate(
        self,
        execution_lock: ExecutionBoundaryLockDecision,
    ) -> StrategyPlanningPackageDecision:
        """Compatibility alias for generate()."""

        return self.generate(execution_lock)


def generate_strategy_planning_package(
    execution_lock: ExecutionBoundaryLockDecision,
) -> StrategyPlanningPackageDecision:
    return StrategyPlanningPackageFactory().generate(execution_lock)


AnalyticalPlanningPackage = StrategyPlanningPackage
PlanningPackage = StrategyPlanningPackage
PlanningPackageBlocker = StrategyPlanningPackageBlocker
PlanningPackageDecision = StrategyPlanningPackageDecision
PlanningPackageFactory = StrategyPlanningPackageFactory
PlanningPackageReason = StrategyPlanningPackageReason
PlanningPackageStatus = StrategyPlanningPackageStatus
