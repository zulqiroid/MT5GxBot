from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.position_sizing_handoff import (
    PositionSizingHandoffDecision,
    StrategyPositionSizingHandoff,
)

_ZERO = Decimal("0")


class PositionSizingSpecificationStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class PositionSizingSpecificationReason(str, Enum):
    READY = "READY"
    HANDOFF_BLOCKED = "HANDOFF_BLOCKED"


class PositionSizingSpecificationBlocker(str, Enum):
    HANDOFF_BLOCKED = "HANDOFF_BLOCKED"


class PositionSizingSpecificationErrorReason(str, Enum):
    INVALID_HANDOFF_DECISION = "INVALID_HANDOFF_DECISION"
    INVALID_SPECIFICATION = "INVALID_SPECIFICATION"


class PositionSizingSpecificationError(RuntimeError):
    """Structured broker sizing-specification failure."""

    def __init__(
        self,
        reason: PositionSizingSpecificationErrorReason,
        message: str,
    ) -> None:
        self.reason = PositionSizingSpecificationErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Position-sizing specification error [{self.reason.value}]: {self.message}"
        )


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _aware_datetime(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value


def _non_empty_string(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")

    return normalized


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

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
class PositionSizingSpecificationPolicy:
    """
    Matching requirements for broker sizing economics.

    READY means volume calculation may begin. The policy
    does not authorize trading or broker-side operations.
    """

    require_symbol_match: bool = True
    require_non_stale_snapshot: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "require_symbol_match",
            _strict_boolean(
                self.require_symbol_match,
                "require_symbol_match",
            ),
        )
        object.__setattr__(
            self,
            "require_non_stale_snapshot",
            _strict_boolean(
                self.require_non_stale_snapshot,
                "require_non_stale_snapshot",
            ),
        )


@dataclass(frozen=True, slots=True)
class PositionSizingSpecification:
    """
    Immutable broker economics required for position sizing.

    No volume, lot size, order request, or execution output
    is produced by this specification.
    """

    observed_at: datetime
    broker_symbol: str
    digits: int
    point_size: Decimal
    tick_size: Decimal
    tick_value: Decimal
    contract_size: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observed_at",
            _aware_datetime(
                self.observed_at,
                "observed_at",
            ),
        )
        object.__setattr__(
            self,
            "broker_symbol",
            _non_empty_string(
                self.broker_symbol,
                "broker_symbol",
            ),
        )
        object.__setattr__(
            self,
            "digits",
            _non_negative_integer(
                self.digits,
                "digits",
            ),
        )

        for field_name in (
            "point_size",
            "tick_size",
            "tick_value",
            "contract_size",
            "volume_min",
            "volume_max",
            "volume_step",
        ):
            object.__setattr__(
                self,
                field_name,
                _positive_finite_decimal(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        if self.volume_min > self.volume_max:
            raise ValueError("volume_min cannot exceed volume_max.")

        if self.volume_step > self.volume_max:
            raise ValueError("volume_step cannot exceed volume_max.")

        if not _is_step_aligned(
            self.volume_min,
            self.volume_step,
        ):
            raise ValueError("volume_min must align with volume_step.")

        if not _is_step_aligned(
            self.volume_max,
            self.volume_step,
        ):
            raise ValueError("volume_max must align with volume_step.")

        if not _is_step_aligned(
            self.tick_size,
            self.point_size,
        ):
            raise ValueError("tick_size must align with point_size.")

    @property
    def value_per_price_unit(self) -> Decimal:
        return self.tick_value / self.tick_size

    @property
    def points_per_tick(self) -> Decimal:
        return self.tick_size / self.point_size

    @property
    def volume_slot_count(self) -> int:
        slot_distance = self.volume_max - self.volume_min

        return int(slot_distance / self.volume_step) + 1

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def stable_id(self) -> str:
        return (
            f"{self.observed_at.isoformat()}:"
            f"{self.broker_symbol}:"
            f"DIGITS[{self.digits}]:"
            f"POINT[{_canonical_decimal(self.point_size)}]:"
            f"TICK_SIZE["
            f"{_canonical_decimal(self.tick_size)}]:"
            f"TICK_VALUE["
            f"{_canonical_decimal(self.tick_value)}]:"
            f"CONTRACT["
            f"{_canonical_decimal(self.contract_size)}]:"
            f"VOLUME_MIN["
            f"{_canonical_decimal(self.volume_min)}]:"
            f"VOLUME_MAX["
            f"{_canonical_decimal(self.volume_max)}]:"
            f"VOLUME_STEP["
            f"{_canonical_decimal(self.volume_step)}]"
        )


@dataclass(frozen=True, slots=True)
class _PositionSizingSpecificationEvaluation:
    status: PositionSizingSpecificationStatus
    reason: PositionSizingSpecificationReason
    blockers: tuple[
        PositionSizingSpecificationBlocker,
        ...,
    ]
    specification: PositionSizingSpecification | None


def _derive_specification(
    handoff_decision: PositionSizingHandoffDecision,
    specification: PositionSizingSpecification | None,
    policy: PositionSizingSpecificationPolicy,
) -> _PositionSizingSpecificationEvaluation:
    if handoff_decision.is_blocked:
        return _PositionSizingSpecificationEvaluation(
            status=PositionSizingSpecificationStatus.BLOCKED,
            reason=(PositionSizingSpecificationReason.HANDOFF_BLOCKED),
            blockers=(PositionSizingSpecificationBlocker.HANDOFF_BLOCKED,),
            specification=None,
        )

    if specification is None:
        raise PositionSizingSpecificationError(
            PositionSizingSpecificationErrorReason.INVALID_SPECIFICATION,
            "A created position-sizing handoff requires a PositionSizingSpecification.",
        )

    handoff = handoff_decision.handoff_required

    if policy.require_symbol_match and specification.broker_symbol != handoff.broker_symbol:
        raise PositionSizingSpecificationError(
            PositionSizingSpecificationErrorReason.INVALID_SPECIFICATION,
            "Sizing specification broker symbol does not match the strategy handoff.",
        )

    if policy.require_non_stale_snapshot and specification.observed_at < handoff.observed_at:
        raise PositionSizingSpecificationError(
            PositionSizingSpecificationErrorReason.INVALID_SPECIFICATION,
            "Sizing specification cannot predate the strategy handoff.",
        )

    return _PositionSizingSpecificationEvaluation(
        status=PositionSizingSpecificationStatus.READY,
        reason=PositionSizingSpecificationReason.READY,
        blockers=(),
        specification=specification,
    )


@dataclass(frozen=True, slots=True)
class PositionSizingSpecificationDecision:
    """Validated broker sizing-specification result."""

    handoff_decision: PositionSizingHandoffDecision
    policy: PositionSizingSpecificationPolicy
    status: PositionSizingSpecificationStatus
    reason: PositionSizingSpecificationReason
    blockers: tuple[
        PositionSizingSpecificationBlocker,
        ...,
    ]
    specification: PositionSizingSpecification | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.handoff_decision,
            PositionSizingHandoffDecision,
        ):
            raise ValueError("handoff_decision must be a PositionSizingHandoffDecision.")

        if not isinstance(
            self.policy,
            PositionSizingSpecificationPolicy,
        ):
            raise ValueError("policy must be a PositionSizingSpecificationPolicy.")

        try:
            status = PositionSizingSpecificationStatus(self.status)
            reason = PositionSizingSpecificationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported sizing-specification status or reason.") from error

        blockers = tuple(PositionSizingSpecificationBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Sizing-specification blockers cannot contain duplicates.")

        if self.specification is not None and not isinstance(
            self.specification,
            PositionSizingSpecification,
        ):
            raise ValueError("specification must be a PositionSizingSpecification or None.")

        expected = _derive_specification(
            self.handoff_decision,
            self.specification,
            self.policy,
        )
        supplied = _PositionSizingSpecificationEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            specification=self.specification,
        )

        if supplied != expected:
            raise ValueError(
                "Sizing-specification result does not match its handoff, specification, and policy."
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
        return self.handoff_decision.handoff

    @property
    def broker_symbol(self) -> str:
        return self.handoff_decision.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.handoff_decision.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.handoff_decision.direction

    @property
    def is_ready(self) -> bool:
        return self.status == PositionSizingSpecificationStatus.READY

    @property
    def is_blocked(self) -> bool:
        return not self.is_ready

    @property
    def can_calculate_volume(self) -> bool:
        return self.is_ready

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def is_executable(self) -> bool:
        return False

    @property
    def specification_required(
        self,
    ) -> PositionSizingSpecification:
        if self.specification is None:
            raise ValueError("No position-sizing specification is available.")

        return self.specification

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )
        specification_fragment = (
            self.specification.stable_id if self.specification is not None else "NO_SPECIFICATION"
        )

        return (
            f"{self.handoff_decision.stable_id}:"
            f"POSITION_SIZING_SPECIFICATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}:"
            f"{specification_fragment}"
        )


class StrategyPositionSizingSpecificationGate:
    """
    Pure gate for broker position-sizing economics.

    READY permits volume calculation only. No broker request,
    order submission, or execution permission is produced.
    """

    def __init__(
        self,
        policy: (PositionSizingSpecificationPolicy | None) = None,
    ) -> None:
        selected_policy = policy or PositionSizingSpecificationPolicy()

        if not isinstance(
            selected_policy,
            PositionSizingSpecificationPolicy,
        ):
            raise ValueError("policy must be a PositionSizingSpecificationPolicy.")

        self._policy = selected_policy

    @property
    def policy(
        self,
    ) -> PositionSizingSpecificationPolicy:
        return self._policy

    def evaluate(
        self,
        handoff_decision: PositionSizingHandoffDecision,
        specification: (PositionSizingSpecification | None) = None,
    ) -> PositionSizingSpecificationDecision:
        if not isinstance(
            handoff_decision,
            PositionSizingHandoffDecision,
        ):
            raise PositionSizingSpecificationError(
                PositionSizingSpecificationErrorReason.INVALID_HANDOFF_DECISION,
                "handoff_decision must be a PositionSizingHandoffDecision.",
            )

        if specification is not None and not isinstance(
            specification,
            PositionSizingSpecification,
        ):
            raise PositionSizingSpecificationError(
                PositionSizingSpecificationErrorReason.INVALID_SPECIFICATION,
                "specification must be a PositionSizingSpecification or None.",
            )

        evaluation = _derive_specification(
            handoff_decision,
            specification,
            self._policy,
        )

        return PositionSizingSpecificationDecision(
            handoff_decision=handoff_decision,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            specification=evaluation.specification,
        )

    def assess(
        self,
        handoff_decision: PositionSizingHandoffDecision,
        specification: (PositionSizingSpecification | None) = None,
    ) -> PositionSizingSpecificationDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            handoff_decision,
            specification,
        )

    def check(
        self,
        handoff_decision: PositionSizingHandoffDecision,
        specification: (PositionSizingSpecification | None) = None,
    ) -> PositionSizingSpecificationDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            handoff_decision,
            specification,
        )


def evaluate_position_sizing_specification(
    handoff_decision: PositionSizingHandoffDecision,
    specification: PositionSizingSpecification | None = None,
    policy: PositionSizingSpecificationPolicy | None = None,
) -> PositionSizingSpecificationDecision:
    return StrategyPositionSizingSpecificationGate(policy=policy).evaluate(
        handoff_decision,
        specification,
    )


BrokerSizingSpecification = PositionSizingSpecification
SizingSpecification = PositionSizingSpecification
SizingSpecificationBlocker = PositionSizingSpecificationBlocker
SizingSpecificationDecision = PositionSizingSpecificationDecision
SizingSpecificationGate = StrategyPositionSizingSpecificationGate
SizingSpecificationPolicy = PositionSizingSpecificationPolicy
SizingSpecificationReason = PositionSizingSpecificationReason
SizingSpecificationStatus = PositionSizingSpecificationStatus
