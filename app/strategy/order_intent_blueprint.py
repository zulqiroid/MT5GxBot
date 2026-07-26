from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.sized_trade_plan import (
    SizedTradePlanDecision,
    StrategySizedTradePlan,
)

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


class StrategyOrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderIntentProtectionMode(str, Enum):
    BROKER_STOP_REQUIRED = "BROKER_STOP_REQUIRED"


class OrderIntentExecutionState(str, Enum):
    ANALYTICAL_ONLY = "ANALYTICAL_ONLY"


class OrderIntentBlueprintStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class OrderIntentBlueprintReason(str, Enum):
    CREATED = "CREATED"
    SIZED_PLAN_BLOCKED = "SIZED_PLAN_BLOCKED"


class OrderIntentBlueprintBlocker(str, Enum):
    SIZED_PLAN_BLOCKED = "SIZED_PLAN_BLOCKED"


class OrderIntentBlueprintErrorReason(str, Enum):
    INVALID_SIZED_PLAN_DECISION = "INVALID_SIZED_PLAN_DECISION"


class OrderIntentBlueprintError(RuntimeError):
    """Structured analytical order-intent failure."""

    def __init__(
        self,
        reason: OrderIntentBlueprintErrorReason,
        message: str,
    ) -> None:
        self.reason = OrderIntentBlueprintErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Order-intent blueprint error [{self.reason.value}]: {self.message}")


def _positive_finite_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError(f"{field_name} must be a Decimal.")

    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if value <= _ZERO:
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


def _non_negative_finite_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError(f"{field_name} must be a Decimal.")

    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if value < _ZERO:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


def _canonical_decimal(value: Decimal) -> str:
    if value == _ZERO:
        return "0"

    return format(value.normalize(), "f")


def _side_for_direction(
    direction: DirectionalPermissionDirection,
) -> StrategyOrderSide:
    if direction == DirectionalPermissionDirection.BULLISH:
        return StrategyOrderSide.BUY

    if direction == DirectionalPermissionDirection.BEARISH:
        return StrategyOrderSide.SELL

    raise ValueError("Order intent requires a resolved bullish or bearish direction.")


@dataclass(frozen=True, slots=True)
class StrategyOrderIntentBlueprint:
    """
    Immutable analytical boundary before execution design.

    The blueprint contains strategy intent but deliberately
    contains no broker request or authority to submit one.
    """

    sized_plan: SizedTradePlanDecision
    side: StrategyOrderSide
    protection_mode: OrderIntentProtectionMode
    execution_state: OrderIntentExecutionState
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    volume: Decimal
    approved_risk_amount: Decimal
    actual_risk_amount: Decimal
    unused_risk_amount: Decimal
    reward_risk_ratio: Decimal
    risk_utilization_percent: Decimal

    def __post_init__(self) -> None:
        if not isinstance(
            self.sized_plan,
            SizedTradePlanDecision,
        ):
            raise ValueError("sized_plan must be a SizedTradePlanDecision.")

        if not self.sized_plan.is_created:
            raise ValueError("An order-intent blueprint requires a created sized trade plan.")

        if not isinstance(self.side, StrategyOrderSide):
            raise ValueError("side must be a StrategyOrderSide member.")

        if not isinstance(
            self.protection_mode,
            OrderIntentProtectionMode,
        ):
            raise ValueError("protection_mode must be an OrderIntentProtectionMode member.")

        if self.protection_mode != OrderIntentProtectionMode.BROKER_STOP_REQUIRED:
            raise ValueError("Order intent requires a broker-side protective stop.")

        if not isinstance(
            self.execution_state,
            OrderIntentExecutionState,
        ):
            raise ValueError("execution_state must be an OrderIntentExecutionState member.")

        if self.execution_state != OrderIntentExecutionState.ANALYTICAL_ONLY:
            raise ValueError("Order-intent blueprint must remain analytical only.")

        for field_name in (
            "entry_price",
            "stop_loss",
            "take_profit",
            "volume",
            "approved_risk_amount",
            "actual_risk_amount",
            "reward_risk_ratio",
            "risk_utilization_percent",
        ):
            object.__setattr__(
                self,
                field_name,
                _positive_finite_decimal(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        object.__setattr__(
            self,
            "unused_risk_amount",
            _non_negative_finite_decimal(
                self.unused_risk_amount,
                "unused_risk_amount",
            ),
        )

        if self.risk_utilization_percent > _HUNDRED:
            raise ValueError("risk_utilization_percent cannot exceed 100.")

        plan = self.sized_plan.plan_required
        expected_side = _side_for_direction(plan.direction)

        if self.side != expected_side:
            raise ValueError("Order side must match the sized plan direction.")

        expected_values = {
            "entry_price": plan.entry_price,
            "stop_loss": plan.stop_loss,
            "take_profit": plan.take_profit,
            "volume": plan.volume,
            "approved_risk_amount": (plan.approved_risk_amount),
            "actual_risk_amount": (plan.actual_risk_amount),
            "unused_risk_amount": (plan.unused_risk_amount),
            "reward_risk_ratio": (plan.reward_risk_ratio),
            "risk_utilization_percent": (plan.risk_utilization_percent),
        }

        for field_name, expected_value in expected_values.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(f"{field_name} must match the sized trade plan.")

        if self.side == StrategyOrderSide.BUY:
            if not (self.stop_loss < self.entry_price < self.take_profit):
                raise ValueError("BUY intent requires stop_loss < entry_price < take_profit.")
        else:
            if not (self.take_profit < self.entry_price < self.stop_loss):
                raise ValueError("SELL intent requires take_profit < entry_price < stop_loss.")

        if self.actual_risk_amount > self.approved_risk_amount:
            raise ValueError("actual_risk_amount cannot exceed the approved risk amount.")

        expected_unused = self.approved_risk_amount - self.actual_risk_amount

        if self.unused_risk_amount != expected_unused:
            raise ValueError("unused_risk_amount is inconsistent.")

        expected_utilization = self.actual_risk_amount / self.approved_risk_amount * _HUNDRED

        if self.risk_utilization_percent != expected_utilization:
            raise ValueError("risk_utilization_percent is inconsistent.")

    @property
    def plan(self) -> StrategySizedTradePlan:
        return self.sized_plan.plan_required

    @property
    def broker_symbol(self) -> str:
        return self.plan.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.plan.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.plan.direction

    @property
    def requires_broker_stop(self) -> bool:
        return True

    @property
    def has_protective_stop(self) -> bool:
        return self.stop_loss > _ZERO

    @property
    def can_submit_order(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def intent_id(self) -> str:
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
            f"UNUSED_RISK["
            f"{_canonical_decimal(self.unused_risk_amount)}]:"
            f"RR["
            f"{_canonical_decimal(self.reward_risk_ratio)}]:"
            f"UTILIZATION_PCT["
            f"{_canonical_decimal(self.risk_utilization_percent)}]:"
            f"PROTECTION[{self.protection_mode.value}]:"
            f"EXECUTION[{self.execution_state.value}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.sized_plan.stable_id}:ORDER_INTENT_BLUEPRINT:{self.intent_id}"


@dataclass(frozen=True, slots=True)
class _OrderIntentBlueprintEvaluation:
    status: OrderIntentBlueprintStatus
    reason: OrderIntentBlueprintReason
    blockers: tuple[
        OrderIntentBlueprintBlocker,
        ...,
    ]
    blueprint: StrategyOrderIntentBlueprint | None


def _derive_blueprint(
    sized_plan: SizedTradePlanDecision,
) -> _OrderIntentBlueprintEvaluation:
    if sized_plan.is_blocked:
        return _OrderIntentBlueprintEvaluation(
            status=OrderIntentBlueprintStatus.BLOCKED,
            reason=(OrderIntentBlueprintReason.SIZED_PLAN_BLOCKED),
            blockers=(OrderIntentBlueprintBlocker.SIZED_PLAN_BLOCKED,),
            blueprint=None,
        )

    plan = sized_plan.plan_required

    blueprint = StrategyOrderIntentBlueprint(
        sized_plan=sized_plan,
        side=_side_for_direction(plan.direction),
        protection_mode=(OrderIntentProtectionMode.BROKER_STOP_REQUIRED),
        execution_state=(OrderIntentExecutionState.ANALYTICAL_ONLY),
        entry_price=plan.entry_price,
        stop_loss=plan.stop_loss,
        take_profit=plan.take_profit,
        volume=plan.volume,
        approved_risk_amount=(plan.approved_risk_amount),
        actual_risk_amount=plan.actual_risk_amount,
        unused_risk_amount=plan.unused_risk_amount,
        reward_risk_ratio=plan.reward_risk_ratio,
        risk_utilization_percent=(plan.risk_utilization_percent),
    )

    return _OrderIntentBlueprintEvaluation(
        status=OrderIntentBlueprintStatus.CREATED,
        reason=OrderIntentBlueprintReason.CREATED,
        blockers=(),
        blueprint=blueprint,
    )


@dataclass(frozen=True, slots=True)
class OrderIntentBlueprintDecision:
    """Validated analytical order-intent result."""

    sized_plan: SizedTradePlanDecision
    status: OrderIntentBlueprintStatus
    reason: OrderIntentBlueprintReason
    blockers: tuple[
        OrderIntentBlueprintBlocker,
        ...,
    ]
    blueprint: StrategyOrderIntentBlueprint | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.sized_plan,
            SizedTradePlanDecision,
        ):
            raise ValueError("sized_plan must be a SizedTradePlanDecision.")

        try:
            status = OrderIntentBlueprintStatus(self.status)
            reason = OrderIntentBlueprintReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported order-intent status or reason.") from error

        blockers = tuple(OrderIntentBlueprintBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Order-intent blockers cannot contain duplicates.")

        if self.blueprint is not None and not isinstance(
            self.blueprint,
            StrategyOrderIntentBlueprint,
        ):
            raise ValueError("blueprint must be a StrategyOrderIntentBlueprint or None.")

        expected = _derive_blueprint(self.sized_plan)
        supplied = _OrderIntentBlueprintEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            blueprint=self.blueprint,
        )

        if supplied != expected:
            raise ValueError("Order-intent result does not match its sized trade plan.")

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
        return self.sized_plan.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.sized_plan.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.sized_plan.direction

    @property
    def is_created(self) -> bool:
        return self.status == OrderIntentBlueprintStatus.CREATED

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
    ) -> StrategyOrderIntentBlueprint:
        if self.blueprint is None:
            raise ValueError("No order-intent blueprint was created.")

        return self.blueprint

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.sized_plan.stable_id}:"
            f"ORDER_INTENT_BLUEPRINT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyOrderIntentBlueprintFactory:
    """
    Pure factory for analytical order intent.

    CREATED does not grant trading permission and does not
    produce a broker request.
    """

    def generate(
        self,
        sized_plan: SizedTradePlanDecision,
    ) -> OrderIntentBlueprintDecision:
        if not isinstance(
            sized_plan,
            SizedTradePlanDecision,
        ):
            raise OrderIntentBlueprintError(
                OrderIntentBlueprintErrorReason.INVALID_SIZED_PLAN_DECISION,
                "sized_plan must be a SizedTradePlanDecision.",
            )

        evaluation = _derive_blueprint(sized_plan)

        return OrderIntentBlueprintDecision(
            sized_plan=sized_plan,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            blueprint=evaluation.blueprint,
        )

    def build(
        self,
        sized_plan: SizedTradePlanDecision,
    ) -> OrderIntentBlueprintDecision:
        """Compatibility alias for generate()."""

        return self.generate(sized_plan)

    def evaluate(
        self,
        sized_plan: SizedTradePlanDecision,
    ) -> OrderIntentBlueprintDecision:
        """Compatibility alias for generate()."""

        return self.generate(sized_plan)


def generate_order_intent_blueprint(
    sized_plan: SizedTradePlanDecision,
) -> OrderIntentBlueprintDecision:
    return StrategyOrderIntentBlueprintFactory().generate(sized_plan)


AnalyticalOrderIntent = StrategyOrderIntentBlueprint
OrderIntentBlueprint = StrategyOrderIntentBlueprint
OrderIntentBlueprintFactory = StrategyOrderIntentBlueprintFactory
OrderIntentBlocker = OrderIntentBlueprintBlocker
OrderIntentDecision = OrderIntentBlueprintDecision
OrderIntentExecutionMode = OrderIntentExecutionState
OrderIntentFactory = StrategyOrderIntentBlueprintFactory
OrderIntentReason = OrderIntentBlueprintReason
OrderIntentSide = StrategyOrderSide
OrderIntentStatus = OrderIntentBlueprintStatus
