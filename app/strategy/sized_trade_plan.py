from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.position_size_calculation import (
    PositionSizeCalculationDecision,
)
from app.strategy.position_sizing_handoff import (
    StrategyPositionSizingHandoff,
)
from app.strategy.position_sizing_specification import (
    PositionSizingSpecification,
)

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


class SizedTradePlanStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class SizedTradePlanReason(str, Enum):
    CREATED = "CREATED"
    POSITION_SIZE_BLOCKED = "POSITION_SIZE_BLOCKED"


class SizedTradePlanBlocker(str, Enum):
    POSITION_SIZE_BLOCKED = "POSITION_SIZE_BLOCKED"


class SizedTradePlanErrorReason(str, Enum):
    INVALID_POSITION_SIZE_DECISION = "INVALID_POSITION_SIZE_DECISION"


class SizedTradePlanError(RuntimeError):
    """Structured sized-trade-plan generation failure."""

    def __init__(
        self,
        reason: SizedTradePlanErrorReason,
        message: str,
    ) -> None:
        self.reason = SizedTradePlanErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Sized trade plan error [{self.reason.value}]: {self.message}")


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


def _is_step_aligned(
    value: Decimal,
    step: Decimal,
) -> bool:
    quotient = value / step

    return quotient == quotient.to_integral_value()


@dataclass(frozen=True, slots=True)
class StrategySizedTradePlan:
    """
    Immutable analytical trade plan with calculated volume.

    This object is deliberately non-executable. It contains
    no broker request, order type, time-in-force, deviation,
    magic number, or order ticket.
    """

    position_size: PositionSizeCalculationDecision
    direction: DirectionalPermissionDirection
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
            self.position_size,
            PositionSizeCalculationDecision,
        ):
            raise ValueError("position_size must be a PositionSizeCalculationDecision.")

        if not self.position_size.is_calculated:
            raise ValueError("A sized trade plan requires a calculated position-size decision.")

        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if self.direction == DirectionalPermissionDirection.NONE:
            raise ValueError("A sized trade plan requires a resolved bullish or bearish direction.")

        if self.direction != self.position_size.direction:
            raise ValueError("Plan direction must match the position-size decision.")

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

        handoff = self.position_size.handoff
        specification = self.position_size.specification
        metrics = self.position_size.metrics

        if handoff is None:
            raise ValueError("Calculated position-size decision has no position-sizing handoff.")

        if specification is None:
            raise ValueError(
                "Calculated position-size decision has no broker sizing specification."
            )

        if metrics is None:
            raise ValueError("Calculated position-size decision has no position-size metrics.")

        expected_values = {
            "entry_price": handoff.entry_value,
            "stop_loss": handoff.stop_value,
            "take_profit": handoff.target_value,
            "volume": metrics.normalized_volume,
            "approved_risk_amount": (handoff.approved_risk_amount),
            "actual_risk_amount": (metrics.actual_risk_amount),
            "unused_risk_amount": (metrics.unused_risk_amount),
            "reward_risk_ratio": (handoff.reward_risk_ratio),
            "risk_utilization_percent": (metrics.risk_utilization_percent),
        }

        for field_name, expected_value in expected_values.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(f"{field_name} must match the calculated strategy analysis.")

        if self.direction == DirectionalPermissionDirection.BULLISH:
            if not (self.stop_loss < self.entry_price < self.take_profit):
                raise ValueError("Bullish plan requires stop_loss < entry_price < take_profit.")
        else:
            if not (self.take_profit < self.entry_price < self.stop_loss):
                raise ValueError("Bearish plan requires take_profit < entry_price < stop_loss.")

        if self.volume < specification.volume_min:
            raise ValueError("Plan volume cannot be below volume_min.")

        if self.volume > specification.volume_max:
            raise ValueError("Plan volume cannot exceed volume_max.")

        if not _is_step_aligned(
            self.volume,
            specification.volume_step,
        ):
            raise ValueError("Plan volume must align with volume_step.")

        expected_actual_risk = self.volume * metrics.risk_per_volume_unit

        if self.actual_risk_amount != expected_actual_risk:
            raise ValueError("actual_risk_amount does not match the calculated volume.")

        if self.actual_risk_amount > self.approved_risk_amount:
            raise ValueError("actual_risk_amount cannot exceed the approved risk amount.")

        expected_unused_risk = self.approved_risk_amount - self.actual_risk_amount

        if self.unused_risk_amount != expected_unused_risk:
            raise ValueError("unused_risk_amount is inconsistent.")

        expected_utilization = self.actual_risk_amount / self.approved_risk_amount * _HUNDRED

        if self.risk_utilization_percent != expected_utilization:
            raise ValueError("risk_utilization_percent is inconsistent.")

    @property
    def handoff(self) -> StrategyPositionSizingHandoff:
        handoff = self.position_size.handoff

        if handoff is None:
            raise ValueError("Sized plan has no position-sizing handoff.")

        return handoff

    @property
    def specification(
        self,
    ) -> PositionSizingSpecification:
        specification = self.position_size.specification

        if specification is None:
            raise ValueError("Sized plan has no broker specification.")

        return specification

    @property
    def broker_symbol(self) -> str:
        return self.position_size.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.position_size.observed_at

    @property
    def risk_distance(self) -> Decimal:
        return self.handoff.risk_distance

    @property
    def reward_distance(self) -> Decimal:
        return self.handoff.reward_distance

    @property
    def is_bullish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == DirectionalPermissionDirection.BEARISH

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def plan_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.direction.value}:"
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
            f"{_canonical_decimal(self.risk_utilization_percent)}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.position_size.stable_id}:SIZED_TRADE_PLAN:{self.plan_id}"


@dataclass(frozen=True, slots=True)
class _SizedTradePlanEvaluation:
    status: SizedTradePlanStatus
    reason: SizedTradePlanReason
    blockers: tuple[
        SizedTradePlanBlocker,
        ...,
    ]
    plan: StrategySizedTradePlan | None


def _derive_plan(
    position_size: PositionSizeCalculationDecision,
) -> _SizedTradePlanEvaluation:
    if position_size.is_blocked:
        return _SizedTradePlanEvaluation(
            status=SizedTradePlanStatus.BLOCKED,
            reason=(SizedTradePlanReason.POSITION_SIZE_BLOCKED),
            blockers=(SizedTradePlanBlocker.POSITION_SIZE_BLOCKED,),
            plan=None,
        )

    handoff = position_size.handoff
    metrics = position_size.metrics

    if handoff is None:
        raise ValueError("Calculated position size has no handoff.")

    if metrics is None:
        raise ValueError("Calculated position size has no metrics.")

    plan = StrategySizedTradePlan(
        position_size=position_size,
        direction=position_size.direction,
        entry_price=handoff.entry_value,
        stop_loss=handoff.stop_value,
        take_profit=handoff.target_value,
        volume=metrics.normalized_volume,
        approved_risk_amount=(handoff.approved_risk_amount),
        actual_risk_amount=metrics.actual_risk_amount,
        unused_risk_amount=metrics.unused_risk_amount,
        reward_risk_ratio=handoff.reward_risk_ratio,
        risk_utilization_percent=(metrics.risk_utilization_percent),
    )

    return _SizedTradePlanEvaluation(
        status=SizedTradePlanStatus.CREATED,
        reason=SizedTradePlanReason.CREATED,
        blockers=(),
        plan=plan,
    )


@dataclass(frozen=True, slots=True)
class SizedTradePlanDecision:
    """Validated immutable sized-trade-plan result."""

    position_size: PositionSizeCalculationDecision
    status: SizedTradePlanStatus
    reason: SizedTradePlanReason
    blockers: tuple[
        SizedTradePlanBlocker,
        ...,
    ]
    plan: StrategySizedTradePlan | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.position_size,
            PositionSizeCalculationDecision,
        ):
            raise ValueError("position_size must be a PositionSizeCalculationDecision.")

        try:
            status = SizedTradePlanStatus(self.status)
            reason = SizedTradePlanReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported sized-trade-plan status or reason.") from error

        blockers = tuple(SizedTradePlanBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Sized-trade-plan blockers cannot contain duplicates.")

        if self.plan is not None and not isinstance(
            self.plan,
            StrategySizedTradePlan,
        ):
            raise ValueError("plan must be a StrategySizedTradePlan or None.")

        expected = _derive_plan(self.position_size)
        supplied = _SizedTradePlanEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            plan=self.plan,
        )

        if supplied != expected:
            raise ValueError("Sized-trade-plan result does not match its position-size decision.")

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
        return self.position_size.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.position_size.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.position_size.direction

    @property
    def is_created(self) -> bool:
        return self.status == SizedTradePlanStatus.CREATED

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
    def plan_required(self) -> StrategySizedTradePlan:
        if self.plan is None:
            raise ValueError("No sized trade plan was created.")

        return self.plan

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.position_size.stable_id}:"
            f"SIZED_TRADE_PLAN_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategySizedTradePlanFactory:
    """
    Pure sized-trade-plan factory.

    CREATED means later order-intent analysis may continue.
    No broker order or trading permission is produced.
    """

    def generate(
        self,
        position_size: PositionSizeCalculationDecision,
    ) -> SizedTradePlanDecision:
        if not isinstance(
            position_size,
            PositionSizeCalculationDecision,
        ):
            raise SizedTradePlanError(
                SizedTradePlanErrorReason.INVALID_POSITION_SIZE_DECISION,
                "position_size must be a PositionSizeCalculationDecision.",
            )

        evaluation = _derive_plan(position_size)

        return SizedTradePlanDecision(
            position_size=position_size,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            plan=evaluation.plan,
        )

    def build(
        self,
        position_size: PositionSizeCalculationDecision,
    ) -> SizedTradePlanDecision:
        """Compatibility alias for generate()."""

        return self.generate(position_size)

    def evaluate(
        self,
        position_size: PositionSizeCalculationDecision,
    ) -> SizedTradePlanDecision:
        """Compatibility alias for generate()."""

        return self.generate(position_size)


def generate_sized_trade_plan(
    position_size: PositionSizeCalculationDecision,
) -> SizedTradePlanDecision:
    return StrategySizedTradePlanFactory().generate(position_size)


SizedPositionPlan = StrategySizedTradePlan
SizedPositionPlanDecision = SizedTradePlanDecision
SizedTradePlan = StrategySizedTradePlan
SizedTradePlanFactory = StrategySizedTradePlanFactory
TradePlanBlocker = SizedTradePlanBlocker
TradePlanDecision = SizedTradePlanDecision
TradePlanFactory = StrategySizedTradePlanFactory
TradePlanReason = SizedTradePlanReason
TradePlanStatus = SizedTradePlanStatus
