from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.order_intent_blueprint import (
    OrderIntentBlueprintDecision,
    OrderIntentExecutionState,
    OrderIntentProtectionMode,
    StrategyOrderIntentBlueprint,
    StrategyOrderSide,
)


class ExecutionBoundaryLockStatus(str, Enum):
    LOCKED = "LOCKED"
    BLOCKED = "BLOCKED"


class ExecutionBoundaryLockReason(str, Enum):
    LOCKED_ANALYTICAL_ONLY = "LOCKED_ANALYTICAL_ONLY"
    ORDER_INTENT_BLOCKED = "ORDER_INTENT_BLOCKED"


class ExecutionBoundaryBarrier(str, Enum):
    ORDER_INTENT_BLOCKED = "ORDER_INTENT_BLOCKED"
    ANALYTICAL_ONLY = "ANALYTICAL_ONLY"
    BROKER_REQUEST_ABSENT = "BROKER_REQUEST_ABSENT"
    EXECUTION_AUTHORIZATION_ABSENT = "EXECUTION_AUTHORIZATION_ABSENT"
    BROKER_STOP_REQUIRED = "BROKER_STOP_REQUIRED"


class ExecutionBoundaryLockErrorReason(str, Enum):
    INVALID_ORDER_INTENT_DECISION = "INVALID_ORDER_INTENT_DECISION"


class ExecutionBoundaryLockError(RuntimeError):
    """Structured execution-boundary lock failure."""

    def __init__(
        self,
        reason: ExecutionBoundaryLockErrorReason,
        message: str,
    ) -> None:
        self.reason = ExecutionBoundaryLockErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Execution-boundary lock error [{self.reason.value}]: {self.message}")


_REQUIRED_BARRIERS = (
    ExecutionBoundaryBarrier.ANALYTICAL_ONLY,
    ExecutionBoundaryBarrier.BROKER_REQUEST_ABSENT,
    ExecutionBoundaryBarrier.EXECUTION_AUTHORIZATION_ABSENT,
    ExecutionBoundaryBarrier.BROKER_STOP_REQUIRED,
)


@dataclass(frozen=True, slots=True)
class StrategyExecutionBoundaryLock:
    """
    Immutable safety lock around analytical order intent.

    This object cannot authorize, construct, submit, or
    represent a broker order.
    """

    order_intent: OrderIntentBlueprintDecision
    blueprint: StrategyOrderIntentBlueprint
    barriers: tuple[ExecutionBoundaryBarrier, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.order_intent,
            OrderIntentBlueprintDecision,
        ):
            raise ValueError("order_intent must be an OrderIntentBlueprintDecision.")

        if not self.order_intent.is_created:
            raise ValueError("An execution lock requires a created order-intent blueprint.")

        if not isinstance(
            self.blueprint,
            StrategyOrderIntentBlueprint,
        ):
            raise ValueError("blueprint must be a StrategyOrderIntentBlueprint.")

        if self.blueprint != self.order_intent.blueprint_required:
            raise ValueError("Execution-lock blueprint must match the order-intent decision.")

        if not isinstance(self.barriers, tuple):
            raise ValueError("barriers must be a tuple.")

        if not all(
            isinstance(
                barrier,
                ExecutionBoundaryBarrier,
            )
            for barrier in self.barriers
        ):
            raise ValueError("barriers must contain ExecutionBoundaryBarrier members.")

        if self.barriers != _REQUIRED_BARRIERS:
            raise ValueError(
                "Execution lock must preserve all safety barriers in deterministic order."
            )

        if self.blueprint.execution_state != OrderIntentExecutionState.ANALYTICAL_ONLY:
            raise ValueError("Execution lock requires an analytical-only order intent.")

        if self.blueprint.protection_mode != OrderIntentProtectionMode.BROKER_STOP_REQUIRED:
            raise ValueError("Execution lock requires a broker-side protective stop.")

        if not self.blueprint.requires_broker_stop:
            raise ValueError("Order intent must require a broker stop.")

        if not self.blueprint.has_protective_stop:
            raise ValueError("Order intent must contain a protective stop value.")

        if self.blueprint.has_broker_request:
            raise ValueError("Execution lock cannot contain a broker request.")

        if self.blueprint.can_submit_order:
            raise ValueError("Execution lock cannot permit order submission.")

        if self.blueprint.is_executable:
            raise ValueError("Execution lock cannot wrap an executable order intent.")

    @property
    def broker_symbol(self) -> str:
        return self.blueprint.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.blueprint.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.blueprint.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.blueprint.side

    @property
    def barrier_count(self) -> int:
        return len(self.barriers)

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
    def lock_id(self) -> str:
        barrier_fragment = ",".join(barrier.value for barrier in self.barriers)

        return f"{self.broker_symbol}:{self.side.value}:EXECUTION_LOCK:{barrier_fragment}"

    @property
    def stable_id(self) -> str:
        return f"{self.order_intent.stable_id}:EXECUTION_BOUNDARY_LOCK:{self.lock_id}"


@dataclass(frozen=True, slots=True)
class _ExecutionBoundaryEvaluation:
    status: ExecutionBoundaryLockStatus
    reason: ExecutionBoundaryLockReason
    barriers: tuple[ExecutionBoundaryBarrier, ...]
    lock: StrategyExecutionBoundaryLock | None


def _derive_lock(
    order_intent: OrderIntentBlueprintDecision,
) -> _ExecutionBoundaryEvaluation:
    if order_intent.is_blocked:
        return _ExecutionBoundaryEvaluation(
            status=ExecutionBoundaryLockStatus.BLOCKED,
            reason=(ExecutionBoundaryLockReason.ORDER_INTENT_BLOCKED),
            barriers=(ExecutionBoundaryBarrier.ORDER_INTENT_BLOCKED,),
            lock=None,
        )

    blueprint = order_intent.blueprint_required
    lock = StrategyExecutionBoundaryLock(
        order_intent=order_intent,
        blueprint=blueprint,
        barriers=_REQUIRED_BARRIERS,
    )

    return _ExecutionBoundaryEvaluation(
        status=ExecutionBoundaryLockStatus.LOCKED,
        reason=(ExecutionBoundaryLockReason.LOCKED_ANALYTICAL_ONLY),
        barriers=_REQUIRED_BARRIERS,
        lock=lock,
    )


@dataclass(frozen=True, slots=True)
class ExecutionBoundaryLockDecision:
    """Validated immutable execution-boundary result."""

    order_intent: OrderIntentBlueprintDecision
    status: ExecutionBoundaryLockStatus
    reason: ExecutionBoundaryLockReason
    barriers: tuple[ExecutionBoundaryBarrier, ...]
    lock: StrategyExecutionBoundaryLock | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.order_intent,
            OrderIntentBlueprintDecision,
        ):
            raise ValueError("order_intent must be an OrderIntentBlueprintDecision.")

        if not isinstance(
            self.status,
            ExecutionBoundaryLockStatus,
        ):
            raise ValueError("status must be an ExecutionBoundaryLockStatus member.")

        if not isinstance(
            self.reason,
            ExecutionBoundaryLockReason,
        ):
            raise ValueError("reason must be an ExecutionBoundaryLockReason member.")

        if not isinstance(self.barriers, tuple):
            raise ValueError("barriers must be a tuple.")

        if not all(
            isinstance(
                barrier,
                ExecutionBoundaryBarrier,
            )
            for barrier in self.barriers
        ):
            raise ValueError("barriers must contain ExecutionBoundaryBarrier members.")

        if len(set(self.barriers)) != len(self.barriers):
            raise ValueError("Execution barriers cannot contain duplicates.")

        if self.lock is not None and not isinstance(
            self.lock,
            StrategyExecutionBoundaryLock,
        ):
            raise ValueError("lock must be a StrategyExecutionBoundaryLock or None.")

        expected = _derive_lock(self.order_intent)
        supplied = _ExecutionBoundaryEvaluation(
            status=self.status,
            reason=self.reason,
            barriers=self.barriers,
            lock=self.lock,
        )

        if supplied != expected:
            raise ValueError("Execution-boundary result does not match its order-intent decision.")

    @property
    def broker_symbol(self) -> str:
        return self.order_intent.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.order_intent.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.order_intent.direction

    @property
    def is_locked(self) -> bool:
        return self.status == ExecutionBoundaryLockStatus.LOCKED

    @property
    def is_blocked(self) -> bool:
        return self.status == ExecutionBoundaryLockStatus.BLOCKED

    @property
    def has_lock(self) -> bool:
        return self.lock is not None

    @property
    def barrier_count(self) -> int:
        return len(self.barriers)

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
    def lock_required(
        self,
    ) -> StrategyExecutionBoundaryLock:
        if self.lock is None:
            raise ValueError("No execution-boundary lock was created.")

        return self.lock

    @property
    def stable_id(self) -> str:
        barrier_fragment = ",".join(barrier.value for barrier in self.barriers)

        return (
            f"{self.order_intent.stable_id}:"
            f"EXECUTION_BOUNDARY_LOCK_DECISION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{barrier_fragment}"
        )


class StrategyExecutionBoundaryLockFactory:
    """
    Pure factory that seals analytical order intent.

    The generated lock does not expose an unlock, authorize,
    request-building, submission, or broker-write operation.
    """

    def generate(
        self,
        order_intent: OrderIntentBlueprintDecision,
    ) -> ExecutionBoundaryLockDecision:
        if not isinstance(
            order_intent,
            OrderIntentBlueprintDecision,
        ):
            raise ExecutionBoundaryLockError(
                ExecutionBoundaryLockErrorReason.INVALID_ORDER_INTENT_DECISION,
                "order_intent must be an OrderIntentBlueprintDecision.",
            )

        evaluation = _derive_lock(order_intent)

        return ExecutionBoundaryLockDecision(
            order_intent=order_intent,
            status=evaluation.status,
            reason=evaluation.reason,
            barriers=evaluation.barriers,
            lock=evaluation.lock,
        )

    def build(
        self,
        order_intent: OrderIntentBlueprintDecision,
    ) -> ExecutionBoundaryLockDecision:
        """Compatibility alias for generate()."""

        return self.generate(order_intent)

    def evaluate(
        self,
        order_intent: OrderIntentBlueprintDecision,
    ) -> ExecutionBoundaryLockDecision:
        """Compatibility alias for generate()."""

        return self.generate(order_intent)


def generate_execution_boundary_lock(
    order_intent: OrderIntentBlueprintDecision,
) -> ExecutionBoundaryLockDecision:
    return StrategyExecutionBoundaryLockFactory().generate(order_intent)


AnalyticalExecutionLock = StrategyExecutionBoundaryLock
ExecutionBoundaryBarrierType = ExecutionBoundaryBarrier
ExecutionBoundaryDecision = ExecutionBoundaryLockDecision
ExecutionBoundaryFactory = StrategyExecutionBoundaryLockFactory
ExecutionBoundaryLock = StrategyExecutionBoundaryLock
ExecutionLockBarrier = ExecutionBoundaryBarrier
ExecutionLockDecision = ExecutionBoundaryLockDecision
ExecutionLockFactory = StrategyExecutionBoundaryLockFactory
ExecutionLockReason = ExecutionBoundaryLockReason
ExecutionLockStatus = ExecutionBoundaryLockStatus
