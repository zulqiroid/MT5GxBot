from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.position_sizing_handoff import (
    StrategyPositionSizingHandoff,
)
from app.strategy.position_sizing_specification import (
    PositionSizingSpecification,
    PositionSizingSpecificationDecision,
)

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


class PositionSizeRoundingMode(str, Enum):
    FLOOR = "FLOOR"


class PositionSizeCalculationStatus(str, Enum):
    CALCULATED = "CALCULATED"
    BLOCKED = "BLOCKED"


class PositionSizeCalculationReason(str, Enum):
    CALCULATED = "CALCULATED"
    SPECIFICATION_BLOCKED = "SPECIFICATION_BLOCKED"
    BELOW_MINIMUM_VOLUME = "BELOW_MINIMUM_VOLUME"
    ABOVE_MAXIMUM_VOLUME = "ABOVE_MAXIMUM_VOLUME"


class PositionSizeCalculationBlocker(str, Enum):
    SPECIFICATION_BLOCKED = "SPECIFICATION_BLOCKED"
    BELOW_MINIMUM_VOLUME = "BELOW_MINIMUM_VOLUME"
    ABOVE_MAXIMUM_VOLUME = "ABOVE_MAXIMUM_VOLUME"


class PositionSizeCalculationErrorReason(str, Enum):
    INVALID_SPECIFICATION_DECISION = "INVALID_SPECIFICATION_DECISION"


class PositionSizeCalculationError(RuntimeError):
    """Structured analytical position-size failure."""

    def __init__(
        self,
        reason: PositionSizeCalculationErrorReason,
        message: str,
    ) -> None:
        self.reason = PositionSizeCalculationErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Position-size calculation error [{self.reason.value}]: {self.message}")


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


def _floor_to_step(
    value: Decimal,
    step: Decimal,
) -> Decimal:
    step_count = (value / step).to_integral_value(rounding=ROUND_FLOOR)

    return step_count * step


@dataclass(frozen=True, slots=True)
class PositionSizeCalculationPolicy:
    """
    Safe volume-normalization policy.

    Raw volume is normalized downward so calculated risk
    cannot exceed the approved strategy risk amount.
    """

    rounding_mode: PositionSizeRoundingMode = PositionSizeRoundingMode.FLOOR
    cap_to_maximum_volume: bool = True

    def __post_init__(self) -> None:
        if not isinstance(
            self.rounding_mode,
            PositionSizeRoundingMode,
        ):
            raise ValueError("rounding_mode must be a PositionSizeRoundingMode member.")

        object.__setattr__(
            self,
            "cap_to_maximum_volume",
            _strict_boolean(
                self.cap_to_maximum_volume,
                "cap_to_maximum_volume",
            ),
        )


@dataclass(frozen=True, slots=True)
class PositionSizeMetrics:
    """Exact analytical position-size calculations."""

    risk_per_volume_unit: Decimal
    raw_volume: Decimal
    normalized_volume: Decimal
    actual_risk_amount: Decimal
    unused_risk_amount: Decimal
    risk_utilization_percent: Decimal
    capped_to_maximum: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_per_volume_unit",
            _positive_finite_decimal(
                self.risk_per_volume_unit,
                "risk_per_volume_unit",
            ),
        )
        object.__setattr__(
            self,
            "raw_volume",
            _positive_finite_decimal(
                self.raw_volume,
                "raw_volume",
            ),
        )

        for field_name in (
            "normalized_volume",
            "actual_risk_amount",
            "unused_risk_amount",
            "risk_utilization_percent",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_negative_finite_decimal(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        if self.risk_utilization_percent > _HUNDRED:
            raise ValueError("risk_utilization_percent cannot exceed 100.")

        object.__setattr__(
            self,
            "capped_to_maximum",
            _strict_boolean(
                self.capped_to_maximum,
                "capped_to_maximum",
            ),
        )

    @property
    def stable_id(self) -> str:
        cap_fragment = "CAPPED" if self.capped_to_maximum else "NOT_CAPPED"

        return (
            f"RISK_PER_VOLUME["
            f"{_canonical_decimal(self.risk_per_volume_unit)}]:"
            f"RAW_VOLUME["
            f"{_canonical_decimal(self.raw_volume)}]:"
            f"NORMALIZED_VOLUME["
            f"{_canonical_decimal(self.normalized_volume)}]:"
            f"ACTUAL_RISK["
            f"{_canonical_decimal(self.actual_risk_amount)}]:"
            f"UNUSED_RISK["
            f"{_canonical_decimal(self.unused_risk_amount)}]:"
            f"UTILIZATION_PCT["
            f"{_canonical_decimal(self.risk_utilization_percent)}]:"
            f"{cap_fragment}"
        )


def _calculate_metrics(
    handoff: StrategyPositionSizingHandoff,
    specification: PositionSizingSpecification,
    policy: PositionSizeCalculationPolicy,
) -> PositionSizeMetrics:
    risk_per_volume_unit = (
        handoff.risk_distance / specification.tick_size * specification.tick_value
    )
    raw_volume = handoff.approved_risk_amount / risk_per_volume_unit
    floored_volume = _floor_to_step(
        raw_volume,
        specification.volume_step,
    )
    capped_to_maximum = False

    if raw_volume > specification.volume_max and policy.cap_to_maximum_volume:
        normalized_volume = specification.volume_max
        capped_to_maximum = True
    else:
        normalized_volume = floored_volume

    actual_risk_amount = normalized_volume * risk_per_volume_unit
    unused_risk_amount = handoff.approved_risk_amount - actual_risk_amount

    if unused_risk_amount < _ZERO:
        raise ValueError("Downward-normalized volume cannot exceed the approved risk amount.")

    risk_utilization_percent = actual_risk_amount / handoff.approved_risk_amount * _HUNDRED

    return PositionSizeMetrics(
        risk_per_volume_unit=risk_per_volume_unit,
        raw_volume=raw_volume,
        normalized_volume=normalized_volume,
        actual_risk_amount=actual_risk_amount,
        unused_risk_amount=unused_risk_amount,
        risk_utilization_percent=(risk_utilization_percent),
        capped_to_maximum=capped_to_maximum,
    )


@dataclass(frozen=True, slots=True)
class _PositionSizeCalculationEvaluation:
    status: PositionSizeCalculationStatus
    reason: PositionSizeCalculationReason
    blockers: tuple[
        PositionSizeCalculationBlocker,
        ...,
    ]
    metrics: PositionSizeMetrics | None


def _derive_calculation(
    specification_decision: (PositionSizingSpecificationDecision),
    policy: PositionSizeCalculationPolicy,
) -> _PositionSizeCalculationEvaluation:
    if specification_decision.is_blocked:
        return _PositionSizeCalculationEvaluation(
            status=PositionSizeCalculationStatus.BLOCKED,
            reason=(PositionSizeCalculationReason.SPECIFICATION_BLOCKED),
            blockers=(PositionSizeCalculationBlocker.SPECIFICATION_BLOCKED,),
            metrics=None,
        )

    handoff = specification_decision.handoff_decision.handoff_required
    specification = specification_decision.specification_required
    metrics = _calculate_metrics(
        handoff,
        specification,
        policy,
    )

    if metrics.raw_volume < specification.volume_min:
        return _PositionSizeCalculationEvaluation(
            status=PositionSizeCalculationStatus.BLOCKED,
            reason=(PositionSizeCalculationReason.BELOW_MINIMUM_VOLUME),
            blockers=(PositionSizeCalculationBlocker.BELOW_MINIMUM_VOLUME,),
            metrics=metrics,
        )

    if metrics.raw_volume > specification.volume_max and not policy.cap_to_maximum_volume:
        return _PositionSizeCalculationEvaluation(
            status=PositionSizeCalculationStatus.BLOCKED,
            reason=(PositionSizeCalculationReason.ABOVE_MAXIMUM_VOLUME),
            blockers=(PositionSizeCalculationBlocker.ABOVE_MAXIMUM_VOLUME,),
            metrics=metrics,
        )

    return _PositionSizeCalculationEvaluation(
        status=PositionSizeCalculationStatus.CALCULATED,
        reason=PositionSizeCalculationReason.CALCULATED,
        blockers=(),
        metrics=metrics,
    )


@dataclass(frozen=True, slots=True)
class PositionSizeCalculationDecision:
    """Validated non-executable position-size result."""

    specification_decision: PositionSizingSpecificationDecision
    policy: PositionSizeCalculationPolicy
    status: PositionSizeCalculationStatus
    reason: PositionSizeCalculationReason
    blockers: tuple[
        PositionSizeCalculationBlocker,
        ...,
    ]
    metrics: PositionSizeMetrics | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.specification_decision,
            PositionSizingSpecificationDecision,
        ):
            raise ValueError(
                "specification_decision must be a PositionSizingSpecificationDecision."
            )

        if not isinstance(
            self.policy,
            PositionSizeCalculationPolicy,
        ):
            raise ValueError("policy must be a PositionSizeCalculationPolicy.")

        try:
            status = PositionSizeCalculationStatus(self.status)
            reason = PositionSizeCalculationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported position-size status or reason.") from error

        blockers = tuple(PositionSizeCalculationBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Position-size blockers cannot contain duplicates.")

        if self.metrics is not None and not isinstance(
            self.metrics,
            PositionSizeMetrics,
        ):
            raise ValueError("metrics must be PositionSizeMetrics or None.")

        expected = _derive_calculation(
            self.specification_decision,
            self.policy,
        )
        supplied = _PositionSizeCalculationEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            metrics=self.metrics,
        )

        if supplied != expected:
            raise ValueError(
                "Position-size result does not match its specification decision and policy."
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
    def handoff(
        self,
    ) -> StrategyPositionSizingHandoff | None:
        return self.specification_decision.handoff

    @property
    def specification(
        self,
    ) -> PositionSizingSpecification | None:
        return self.specification_decision.specification

    @property
    def broker_symbol(self) -> str:
        return self.specification_decision.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.specification_decision.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.specification_decision.direction

    @property
    def is_calculated(self) -> bool:
        return self.status == PositionSizeCalculationStatus.CALCULATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_calculated

    @property
    def has_metrics(self) -> bool:
        return self.metrics is not None

    @property
    def raw_volume(self) -> Decimal | None:
        if self.metrics is None:
            return None

        return self.metrics.raw_volume

    @property
    def normalized_volume(self) -> Decimal | None:
        if self.metrics is None:
            return None

        return self.metrics.normalized_volume

    @property
    def actual_risk_amount(self) -> Decimal | None:
        if self.metrics is None:
            return None

        return self.metrics.actual_risk_amount

    @property
    def unused_risk_amount(self) -> Decimal | None:
        if self.metrics is None:
            return None

        return self.metrics.unused_risk_amount

    @property
    def risk_utilization_percent(
        self,
    ) -> Decimal | None:
        if self.metrics is None:
            return None

        return self.metrics.risk_utilization_percent

    @property
    def calculated_volume_required(self) -> Decimal:
        if not self.is_calculated or self.metrics is None:
            raise ValueError("No calculated position volume is available.")

        return self.metrics.normalized_volume

    @property
    def can_continue_to_size_validation(self) -> bool:
        return self.is_calculated

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
        metrics_fragment = self.metrics.stable_id if self.metrics is not None else "NO_SIZE_METRICS"

        return (
            f"{self.specification_decision.stable_id}:"
            f"POSITION_SIZE_CALCULATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}:"
            f"{metrics_fragment}"
        )


class StrategyPositionSizeCalculator:
    """
    Pure deterministic position-size calculator.

    CALCULATED produces an analytical normalized volume only.
    It does not create or submit a broker order.
    """

    def __init__(
        self,
        policy: PositionSizeCalculationPolicy | None = None,
    ) -> None:
        selected_policy = policy or PositionSizeCalculationPolicy()

        if not isinstance(
            selected_policy,
            PositionSizeCalculationPolicy,
        ):
            raise ValueError("policy must be a PositionSizeCalculationPolicy.")

        self._policy = selected_policy

    @property
    def policy(self) -> PositionSizeCalculationPolicy:
        return self._policy

    def calculate(
        self,
        specification_decision: (PositionSizingSpecificationDecision),
    ) -> PositionSizeCalculationDecision:
        if not isinstance(
            specification_decision,
            PositionSizingSpecificationDecision,
        ):
            raise PositionSizeCalculationError(
                PositionSizeCalculationErrorReason.INVALID_SPECIFICATION_DECISION,
                "specification_decision must be a PositionSizingSpecificationDecision.",
            )

        evaluation = _derive_calculation(
            specification_decision,
            self._policy,
        )

        return PositionSizeCalculationDecision(
            specification_decision=(specification_decision),
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            metrics=evaluation.metrics,
        )

    def evaluate(
        self,
        specification_decision: (PositionSizingSpecificationDecision),
    ) -> PositionSizeCalculationDecision:
        """Compatibility alias for calculate()."""

        return self.calculate(specification_decision)

    def size(
        self,
        specification_decision: (PositionSizingSpecificationDecision),
    ) -> PositionSizeCalculationDecision:
        """Compatibility alias for calculate()."""

        return self.calculate(specification_decision)


def calculate_strategy_position_size(
    specification_decision: (PositionSizingSpecificationDecision),
    policy: PositionSizeCalculationPolicy | None = None,
) -> PositionSizeCalculationDecision:
    return StrategyPositionSizeCalculator(policy=policy).calculate(specification_decision)


PositionSizeCalculator = StrategyPositionSizeCalculator
PositionSizeDecision = PositionSizeCalculationDecision
PositionSizePolicy = PositionSizeCalculationPolicy
PositionSizeReason = PositionSizeCalculationReason
PositionSizeStatus = PositionSizeCalculationStatus
SizingCalculationBlocker = PositionSizeCalculationBlocker
SizingCalculationDecision = PositionSizeCalculationDecision
SizingCalculationPolicy = PositionSizeCalculationPolicy
SizingCalculationReason = PositionSizeCalculationReason
SizingCalculationStatus = PositionSizeCalculationStatus
SizingMetrics = PositionSizeMetrics
StrategySizingCalculator = StrategyPositionSizeCalculator
