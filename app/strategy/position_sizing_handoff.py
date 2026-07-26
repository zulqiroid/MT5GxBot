from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.risk_budget_admission import (
    RiskBudgetAdmissionDecision,
)

_ZERO = Decimal("0")


class PositionSizingHandoffStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PositionSizingHandoffReason(str, Enum):
    CREATED = "CREATED"
    RISK_BUDGET_BLOCKED = "RISK_BUDGET_BLOCKED"


class PositionSizingHandoffBlocker(str, Enum):
    RISK_BUDGET_BLOCKED = "RISK_BUDGET_BLOCKED"


class PositionSizingHandoffErrorReason(str, Enum):
    INVALID_RISK_ADMISSION = "INVALID_RISK_ADMISSION"


class PositionSizingHandoffError(RuntimeError):
    """Structured position-sizing handoff failure."""

    def __init__(
        self,
        reason: PositionSizingHandoffErrorReason,
        message: str,
    ) -> None:
        self.reason = PositionSizingHandoffErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Position-sizing handoff error [{self.reason.value}]: {self.message}")


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


def _canonical_decimal(value: Decimal) -> str:
    if value == _ZERO:
        return "0"

    return format(value.normalize(), "f")


@dataclass(frozen=True, slots=True)
class StrategyPositionSizingHandoff:
    """
    Immutable input contract for later position sizing.

    The handoff deliberately contains no calculated volume,
    normalized lot size, broker request, or order ticket.
    """

    risk_admission: RiskBudgetAdmissionDecision
    direction: DirectionalPermissionDirection
    approved_risk_amount: Decimal
    entry_value: Decimal
    stop_value: Decimal
    target_value: Decimal
    risk_distance: Decimal
    reward_distance: Decimal
    reward_risk_ratio: Decimal

    def __post_init__(self) -> None:
        if not isinstance(
            self.risk_admission,
            RiskBudgetAdmissionDecision,
        ):
            raise ValueError("risk_admission must be a RiskBudgetAdmissionDecision.")

        if not self.risk_admission.is_admitted:
            raise ValueError("A position-sizing handoff requires an admitted risk-budget decision.")

        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if self.direction == DirectionalPermissionDirection.NONE:
            raise ValueError("Position sizing requires a resolved bullish or bearish direction.")

        if self.direction != self.risk_admission.direction:
            raise ValueError("Handoff direction must match the risk-budget admission.")

        for field_name in (
            "approved_risk_amount",
            "entry_value",
            "stop_value",
            "target_value",
            "risk_distance",
            "reward_distance",
            "reward_risk_ratio",
        ):
            object.__setattr__(
                self,
                field_name,
                _positive_finite_decimal(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        expected_risk_amount = self.risk_admission.approved_risk_amount

        if expected_risk_amount is None:
            raise ValueError("Admitted risk-budget decision has no approved risk amount.")

        reward_risk = self.risk_admission.reward_risk
        metrics = reward_risk.metrics

        if metrics is None:
            raise ValueError("Admitted risk-budget decision has no reward-to-risk metrics.")

        expected_values = {
            "approved_risk_amount": expected_risk_amount,
            "entry_value": metrics.entry_value,
            "stop_value": metrics.stop_value,
            "target_value": metrics.target_value,
            "risk_distance": metrics.risk_distance,
            "reward_distance": metrics.reward_distance,
            "reward_risk_ratio": (metrics.reward_risk_ratio),
        }

        for field_name, expected_value in expected_values.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(f"{field_name} must match the admitted strategy analysis.")

        if self.direction == DirectionalPermissionDirection.BULLISH:
            if not (self.stop_value < self.entry_value < self.target_value):
                raise ValueError("Bullish handoff requires stop < entry < target.")
        else:
            if not (self.target_value < self.entry_value < self.stop_value):
                raise ValueError("Bearish handoff requires target < entry < stop.")

    @property
    def broker_symbol(self) -> str:
        return self.risk_admission.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.risk_admission.observed_at

    @property
    def account_equity(self) -> Decimal:
        snapshot = self.risk_admission.snapshot

        if snapshot is None:
            raise ValueError("Admitted risk decision has no account snapshot.")

        return snapshot.account_equity

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
    def handoff_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.direction.value}:"
            f"RISK_AMOUNT["
            f"{_canonical_decimal(self.approved_risk_amount)}]:"
            f"ENTRY["
            f"{_canonical_decimal(self.entry_value)}]:"
            f"STOP["
            f"{_canonical_decimal(self.stop_value)}]:"
            f"TARGET["
            f"{_canonical_decimal(self.target_value)}]:"
            f"RISK_DISTANCE["
            f"{_canonical_decimal(self.risk_distance)}]:"
            f"REWARD_DISTANCE["
            f"{_canonical_decimal(self.reward_distance)}]:"
            f"RR["
            f"{_canonical_decimal(self.reward_risk_ratio)}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.risk_admission.stable_id}:POSITION_SIZING_HANDOFF:{self.handoff_id}"


@dataclass(frozen=True, slots=True)
class _PositionSizingHandoffEvaluation:
    status: PositionSizingHandoffStatus
    reason: PositionSizingHandoffReason
    blockers: tuple[
        PositionSizingHandoffBlocker,
        ...,
    ]
    handoff: StrategyPositionSizingHandoff | None


def _derive_handoff(
    risk_admission: RiskBudgetAdmissionDecision,
) -> _PositionSizingHandoffEvaluation:
    if risk_admission.is_blocked:
        return _PositionSizingHandoffEvaluation(
            status=PositionSizingHandoffStatus.BLOCKED,
            reason=(PositionSizingHandoffReason.RISK_BUDGET_BLOCKED),
            blockers=(PositionSizingHandoffBlocker.RISK_BUDGET_BLOCKED,),
            handoff=None,
        )

    approved_risk_amount = risk_admission.approved_risk_amount
    reward_risk = risk_admission.reward_risk
    metrics = reward_risk.metrics

    if approved_risk_amount is None:
        raise ValueError("Admitted risk-budget decision has no approved risk amount.")

    if metrics is None:
        raise ValueError("Admitted risk-budget decision has no reward-to-risk metrics.")

    handoff = StrategyPositionSizingHandoff(
        risk_admission=risk_admission,
        direction=risk_admission.direction,
        approved_risk_amount=approved_risk_amount,
        entry_value=metrics.entry_value,
        stop_value=metrics.stop_value,
        target_value=metrics.target_value,
        risk_distance=metrics.risk_distance,
        reward_distance=metrics.reward_distance,
        reward_risk_ratio=metrics.reward_risk_ratio,
    )

    return _PositionSizingHandoffEvaluation(
        status=PositionSizingHandoffStatus.CREATED,
        reason=PositionSizingHandoffReason.CREATED,
        blockers=(),
        handoff=handoff,
    )


@dataclass(frozen=True, slots=True)
class PositionSizingHandoffDecision:
    """Validated position-sizing handoff result."""

    risk_admission: RiskBudgetAdmissionDecision
    status: PositionSizingHandoffStatus
    reason: PositionSizingHandoffReason
    blockers: tuple[
        PositionSizingHandoffBlocker,
        ...,
    ]
    handoff: StrategyPositionSizingHandoff | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.risk_admission,
            RiskBudgetAdmissionDecision,
        ):
            raise ValueError("risk_admission must be a RiskBudgetAdmissionDecision.")

        try:
            status = PositionSizingHandoffStatus(self.status)
            reason = PositionSizingHandoffReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported position-sizing handoff status or reason.") from error

        blockers = tuple(PositionSizingHandoffBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Position-sizing handoff blockers cannot contain duplicates.")

        if self.handoff is not None and not isinstance(
            self.handoff,
            StrategyPositionSizingHandoff,
        ):
            raise ValueError("handoff must be a StrategyPositionSizingHandoff or None.")

        expected = _derive_handoff(self.risk_admission)
        supplied = _PositionSizingHandoffEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            handoff=self.handoff,
        )

        if supplied != expected:
            raise ValueError(
                "Position-sizing handoff result does not match its risk-budget admission."
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
    def broker_symbol(self) -> str:
        return self.risk_admission.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.risk_admission.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.risk_admission.direction

    @property
    def is_created(self) -> bool:
        return self.status == PositionSizingHandoffStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_handoff(self) -> bool:
        return self.handoff is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def handoff_required(
        self,
    ) -> StrategyPositionSizingHandoff:
        if self.handoff is None:
            raise ValueError("No position-sizing handoff was created.")

        return self.handoff

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.risk_admission.stable_id}:"
            f"POSITION_SIZING_HANDOFF_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPositionSizingHandoffFactory:
    """
    Pure factory for position-sizing input handoffs.

    CREATED permits later sizing analysis only. No volume,
    order request, or broker operation is produced.
    """

    def generate(
        self,
        risk_admission: RiskBudgetAdmissionDecision,
    ) -> PositionSizingHandoffDecision:
        if not isinstance(
            risk_admission,
            RiskBudgetAdmissionDecision,
        ):
            raise PositionSizingHandoffError(
                PositionSizingHandoffErrorReason.INVALID_RISK_ADMISSION,
                "risk_admission must be a RiskBudgetAdmissionDecision.",
            )

        evaluation = _derive_handoff(risk_admission)

        return PositionSizingHandoffDecision(
            risk_admission=risk_admission,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            handoff=evaluation.handoff,
        )

    def build(
        self,
        risk_admission: RiskBudgetAdmissionDecision,
    ) -> PositionSizingHandoffDecision:
        """Compatibility alias for generate()."""

        return self.generate(risk_admission)

    def evaluate(
        self,
        risk_admission: RiskBudgetAdmissionDecision,
    ) -> PositionSizingHandoffDecision:
        """Compatibility alias for generate()."""

        return self.generate(risk_admission)


def generate_position_sizing_handoff(
    risk_admission: RiskBudgetAdmissionDecision,
) -> PositionSizingHandoffDecision:
    return StrategyPositionSizingHandoffFactory().generate(risk_admission)


PositionSizingHandoff = StrategyPositionSizingHandoff
PositionSizingHandoffFactory = StrategyPositionSizingHandoffFactory
SizingHandoff = StrategyPositionSizingHandoff
SizingHandoffBlocker = PositionSizingHandoffBlocker
SizingHandoffDecision = PositionSizingHandoffDecision
SizingHandoffFactory = StrategyPositionSizingHandoffFactory
SizingHandoffReason = PositionSizingHandoffReason
SizingHandoffStatus = PositionSizingHandoffStatus
