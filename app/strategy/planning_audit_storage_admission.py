from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.order_intent_blueprint import (
    StrategyOrderSide,
)
from app.strategy.planning_audit_verification import (
    PlanningAuditVerificationDecision,
    StrategyPlanningAuditVerificationReceipt,
)


class PlanningAuditStorageTarget(str, Enum):
    AUDIT_ARCHIVE = "AUDIT_ARCHIVE"


class PlanningAuditStorageAdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"
    BLOCKED = "BLOCKED"


class PlanningAuditStorageAdmissionReason(str, Enum):
    ADMITTED = "ADMITTED"
    VERIFICATION_BLOCKED = "VERIFICATION_BLOCKED"
    SNAPSHOT_STALE = "SNAPSHOT_STALE"
    STORAGE_DISABLED = "STORAGE_DISABLED"
    ENCRYPTION_REQUIRED = "ENCRYPTION_REQUIRED"
    APPEND_ONLY_REQUIRED = "APPEND_ONLY_REQUIRED"
    IDEMPOTENCY_REQUIRED = "IDEMPOTENCY_REQUIRED"
    RETENTION_TOO_SHORT = "RETENTION_TOO_SHORT"
    INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"
    MULTIPLE_STORAGE_BLOCKERS = "MULTIPLE_STORAGE_BLOCKERS"


class PlanningAuditStorageAdmissionBlocker(str, Enum):
    VERIFICATION_BLOCKED = "VERIFICATION_BLOCKED"
    SNAPSHOT_STALE = "SNAPSHOT_STALE"
    STORAGE_DISABLED = "STORAGE_DISABLED"
    ENCRYPTION_REQUIRED = "ENCRYPTION_REQUIRED"
    APPEND_ONLY_REQUIRED = "APPEND_ONLY_REQUIRED"
    IDEMPOTENCY_REQUIRED = "IDEMPOTENCY_REQUIRED"
    RETENTION_TOO_SHORT = "RETENTION_TOO_SHORT"
    INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"


class PlanningAuditStorageAdmissionErrorReason(str, Enum):
    INVALID_VERIFICATION_DECISION = "INVALID_VERIFICATION_DECISION"
    INVALID_STORAGE_SNAPSHOT = "INVALID_STORAGE_SNAPSHOT"


class PlanningAuditStorageAdmissionError(RuntimeError):
    """Structured read-only storage-admission failure."""

    def __init__(
        self,
        reason: PlanningAuditStorageAdmissionErrorReason,
        message: str,
    ) -> None:
        self.reason = PlanningAuditStorageAdmissionErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Planning-audit storage-admission error [{self.reason.value}]: {self.message}"
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


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageAdmissionPolicy:
    """
    Safety requirements for later audit persistence design.

    Admission does not perform or authorize a storage write.
    """

    require_non_stale_snapshot: bool = True
    require_storage_enabled: bool = True
    require_encryption_at_rest: bool = True
    require_append_only: bool = True
    require_idempotency: bool = True
    minimum_retention_days: int = 90

    def __post_init__(self) -> None:
        for field_name in (
            "require_non_stale_snapshot",
            "require_storage_enabled",
            "require_encryption_at_rest",
            "require_append_only",
            "require_idempotency",
        ):
            object.__setattr__(
                self,
                field_name,
                _strict_boolean(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        object.__setattr__(
            self,
            "minimum_retention_days",
            _positive_integer(
                self.minimum_retention_days,
                "minimum_retention_days",
            ),
        )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageSnapshot:
    """
    Immutable externally supplied storage-readiness facts.

    It contains no path, credential, connection, transaction,
    command, or write operation.
    """

    observed_at: datetime
    target: PlanningAuditStorageTarget
    storage_enabled: bool
    encryption_at_rest: bool
    append_only: bool
    idempotency_supported: bool
    retention_days: int
    available_capacity_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observed_at",
            _aware_datetime(
                self.observed_at,
                "observed_at",
            ),
        )

        if not isinstance(
            self.target,
            PlanningAuditStorageTarget,
        ):
            raise ValueError("target must be a PlanningAuditStorageTarget member.")

        for field_name in (
            "storage_enabled",
            "encryption_at_rest",
            "append_only",
            "idempotency_supported",
        ):
            object.__setattr__(
                self,
                field_name,
                _strict_boolean(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        object.__setattr__(
            self,
            "retention_days",
            _positive_integer(
                self.retention_days,
                "retention_days",
            ),
        )
        object.__setattr__(
            self,
            "available_capacity_bytes",
            _non_negative_integer(
                self.available_capacity_bytes,
                "available_capacity_bytes",
            ),
        )

    @property
    def is_read_only_snapshot(self) -> bool:
        return True

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def stable_id(self) -> str:
        return (
            f"{self.observed_at.isoformat()}:"
            f"{self.target.value}:"
            f"ENABLED[{self.storage_enabled}]:"
            f"ENCRYPTED[{self.encryption_at_rest}]:"
            f"APPEND_ONLY[{self.append_only}]:"
            f"IDEMPOTENT[{self.idempotency_supported}]:"
            f"RETENTION_DAYS[{self.retention_days}]:"
            f"CAPACITY_BYTES["
            f"{self.available_capacity_bytes}]"
        )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageMetrics:
    """Deterministic capacity and retention measurements."""

    required_capacity_bytes: int
    available_capacity_bytes: int
    capacity_surplus_bytes: int
    capacity_deficit_bytes: int
    retention_days: int
    minimum_retention_days: int
    retention_surplus_days: int
    retention_deficit_days: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_capacity_bytes",
            _positive_integer(
                self.required_capacity_bytes,
                "required_capacity_bytes",
            ),
        )
        object.__setattr__(
            self,
            "available_capacity_bytes",
            _non_negative_integer(
                self.available_capacity_bytes,
                "available_capacity_bytes",
            ),
        )

        for field_name in (
            "capacity_surplus_bytes",
            "capacity_deficit_bytes",
            "retention_surplus_days",
            "retention_deficit_days",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_negative_integer(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        object.__setattr__(
            self,
            "retention_days",
            _positive_integer(
                self.retention_days,
                "retention_days",
            ),
        )
        object.__setattr__(
            self,
            "minimum_retention_days",
            _positive_integer(
                self.minimum_retention_days,
                "minimum_retention_days",
            ),
        )

        expected_capacity_surplus = max(
            0,
            self.available_capacity_bytes - self.required_capacity_bytes,
        )
        expected_capacity_deficit = max(
            0,
            self.required_capacity_bytes - self.available_capacity_bytes,
        )
        expected_retention_surplus = max(
            0,
            self.retention_days - self.minimum_retention_days,
        )
        expected_retention_deficit = max(
            0,
            self.minimum_retention_days - self.retention_days,
        )

        if self.capacity_surplus_bytes != expected_capacity_surplus:
            raise ValueError("capacity_surplus_bytes is inconsistent.")

        if self.capacity_deficit_bytes != expected_capacity_deficit:
            raise ValueError("capacity_deficit_bytes is inconsistent.")

        if self.retention_surplus_days != expected_retention_surplus:
            raise ValueError("retention_surplus_days is inconsistent.")

        if self.retention_deficit_days != expected_retention_deficit:
            raise ValueError("retention_deficit_days is inconsistent.")

    @property
    def has_sufficient_capacity(self) -> bool:
        return self.capacity_deficit_bytes == 0

    @property
    def has_sufficient_retention(self) -> bool:
        return self.retention_deficit_days == 0

    @property
    def stable_id(self) -> str:
        return (
            f"REQUIRED_CAPACITY["
            f"{self.required_capacity_bytes}]:"
            f"AVAILABLE_CAPACITY["
            f"{self.available_capacity_bytes}]:"
            f"CAPACITY_SURPLUS["
            f"{self.capacity_surplus_bytes}]:"
            f"CAPACITY_DEFICIT["
            f"{self.capacity_deficit_bytes}]:"
            f"RETENTION_DAYS[{self.retention_days}]:"
            f"MINIMUM_RETENTION_DAYS["
            f"{self.minimum_retention_days}]:"
            f"RETENTION_SURPLUS["
            f"{self.retention_surplus_days}]:"
            f"RETENTION_DEFICIT["
            f"{self.retention_deficit_days}]"
        )


def _build_metrics(
    receipt: StrategyPlanningAuditVerificationReceipt,
    snapshot: PlanningAuditStorageSnapshot,
    policy: PlanningAuditStorageAdmissionPolicy,
) -> PlanningAuditStorageMetrics:
    required_capacity = receipt.verified_content_length_bytes

    return PlanningAuditStorageMetrics(
        required_capacity_bytes=required_capacity,
        available_capacity_bytes=(snapshot.available_capacity_bytes),
        capacity_surplus_bytes=max(
            0,
            snapshot.available_capacity_bytes - required_capacity,
        ),
        capacity_deficit_bytes=max(
            0,
            required_capacity - snapshot.available_capacity_bytes,
        ),
        retention_days=snapshot.retention_days,
        minimum_retention_days=(policy.minimum_retention_days),
        retention_surplus_days=max(
            0,
            snapshot.retention_days - policy.minimum_retention_days,
        ),
        retention_deficit_days=max(
            0,
            policy.minimum_retention_days - snapshot.retention_days,
        ),
    )


def _reason_for_blockers(
    blockers: tuple[
        PlanningAuditStorageAdmissionBlocker,
        ...,
    ],
) -> PlanningAuditStorageAdmissionReason:
    if not blockers:
        return PlanningAuditStorageAdmissionReason.ADMITTED

    if len(blockers) > 1:
        return PlanningAuditStorageAdmissionReason.MULTIPLE_STORAGE_BLOCKERS

    mapping = {
        (PlanningAuditStorageAdmissionBlocker.VERIFICATION_BLOCKED): (
            PlanningAuditStorageAdmissionReason.VERIFICATION_BLOCKED
        ),
        (PlanningAuditStorageAdmissionBlocker.SNAPSHOT_STALE): (
            PlanningAuditStorageAdmissionReason.SNAPSHOT_STALE
        ),
        (PlanningAuditStorageAdmissionBlocker.STORAGE_DISABLED): (
            PlanningAuditStorageAdmissionReason.STORAGE_DISABLED
        ),
        (PlanningAuditStorageAdmissionBlocker.ENCRYPTION_REQUIRED): (
            PlanningAuditStorageAdmissionReason.ENCRYPTION_REQUIRED
        ),
        (PlanningAuditStorageAdmissionBlocker.APPEND_ONLY_REQUIRED): (
            PlanningAuditStorageAdmissionReason.APPEND_ONLY_REQUIRED
        ),
        (PlanningAuditStorageAdmissionBlocker.IDEMPOTENCY_REQUIRED): (
            PlanningAuditStorageAdmissionReason.IDEMPOTENCY_REQUIRED
        ),
        (PlanningAuditStorageAdmissionBlocker.RETENTION_TOO_SHORT): (
            PlanningAuditStorageAdmissionReason.RETENTION_TOO_SHORT
        ),
        (PlanningAuditStorageAdmissionBlocker.INSUFFICIENT_CAPACITY): (
            PlanningAuditStorageAdmissionReason.INSUFFICIENT_CAPACITY
        ),
    }

    return mapping[blockers[0]]


@dataclass(frozen=True, slots=True)
class _PlanningAuditStorageAdmissionEvaluation:
    status: PlanningAuditStorageAdmissionStatus
    reason: PlanningAuditStorageAdmissionReason
    blockers: tuple[
        PlanningAuditStorageAdmissionBlocker,
        ...,
    ]
    snapshot: PlanningAuditStorageSnapshot | None
    metrics: PlanningAuditStorageMetrics | None


def _derive_admission(
    verification: PlanningAuditVerificationDecision,
    snapshot: PlanningAuditStorageSnapshot | None,
    policy: PlanningAuditStorageAdmissionPolicy,
) -> _PlanningAuditStorageAdmissionEvaluation:
    if verification.is_blocked:
        return _PlanningAuditStorageAdmissionEvaluation(
            status=PlanningAuditStorageAdmissionStatus.BLOCKED,
            reason=(PlanningAuditStorageAdmissionReason.VERIFICATION_BLOCKED),
            blockers=(PlanningAuditStorageAdmissionBlocker.VERIFICATION_BLOCKED,),
            snapshot=None,
            metrics=None,
        )

    if snapshot is None:
        raise PlanningAuditStorageAdmissionError(
            PlanningAuditStorageAdmissionErrorReason.INVALID_STORAGE_SNAPSHOT,
            "A verified audit receipt requires a PlanningAuditStorageSnapshot.",
        )

    receipt = verification.receipt_required
    metrics = _build_metrics(
        receipt,
        snapshot,
        policy,
    )
    blockers: list[PlanningAuditStorageAdmissionBlocker] = []

    if policy.require_non_stale_snapshot and snapshot.observed_at < receipt.observed_at:
        blockers.append(PlanningAuditStorageAdmissionBlocker.SNAPSHOT_STALE)

    if policy.require_storage_enabled and not snapshot.storage_enabled:
        blockers.append(PlanningAuditStorageAdmissionBlocker.STORAGE_DISABLED)

    if policy.require_encryption_at_rest and not snapshot.encryption_at_rest:
        blockers.append(PlanningAuditStorageAdmissionBlocker.ENCRYPTION_REQUIRED)

    if policy.require_append_only and not snapshot.append_only:
        blockers.append(PlanningAuditStorageAdmissionBlocker.APPEND_ONLY_REQUIRED)

    if policy.require_idempotency and not snapshot.idempotency_supported:
        blockers.append(PlanningAuditStorageAdmissionBlocker.IDEMPOTENCY_REQUIRED)

    if not metrics.has_sufficient_retention:
        blockers.append(PlanningAuditStorageAdmissionBlocker.RETENTION_TOO_SHORT)

    if not metrics.has_sufficient_capacity:
        blockers.append(PlanningAuditStorageAdmissionBlocker.INSUFFICIENT_CAPACITY)

    blocker_tuple = tuple(blockers)

    return _PlanningAuditStorageAdmissionEvaluation(
        status=(
            PlanningAuditStorageAdmissionStatus.BLOCKED
            if blocker_tuple
            else PlanningAuditStorageAdmissionStatus.ADMITTED
        ),
        reason=_reason_for_blockers(blocker_tuple),
        blockers=blocker_tuple,
        snapshot=snapshot,
        metrics=metrics,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageAdmissionDecision:
    """Validated read-only audit storage-admission result."""

    verification: PlanningAuditVerificationDecision
    policy: PlanningAuditStorageAdmissionPolicy
    status: PlanningAuditStorageAdmissionStatus
    reason: PlanningAuditStorageAdmissionReason
    blockers: tuple[
        PlanningAuditStorageAdmissionBlocker,
        ...,
    ]
    snapshot: PlanningAuditStorageSnapshot | None
    metrics: PlanningAuditStorageMetrics | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.verification,
            PlanningAuditVerificationDecision,
        ):
            raise ValueError("verification must be a PlanningAuditVerificationDecision.")

        if not isinstance(
            self.policy,
            PlanningAuditStorageAdmissionPolicy,
        ):
            raise ValueError("policy must be a PlanningAuditStorageAdmissionPolicy.")

        try:
            status = PlanningAuditStorageAdmissionStatus(self.status)
            reason = PlanningAuditStorageAdmissionReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported audit storage-admission status or reason.") from error

        blockers = tuple(PlanningAuditStorageAdmissionBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Storage-admission blockers cannot contain duplicates.")

        if self.snapshot is not None and not isinstance(
            self.snapshot,
            PlanningAuditStorageSnapshot,
        ):
            raise ValueError("snapshot must be a PlanningAuditStorageSnapshot or None.")

        if self.metrics is not None and not isinstance(
            self.metrics,
            PlanningAuditStorageMetrics,
        ):
            raise ValueError("metrics must be PlanningAuditStorageMetrics or None.")

        expected = _derive_admission(
            self.verification,
            self.snapshot,
            self.policy,
        )
        supplied = _PlanningAuditStorageAdmissionEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            snapshot=self.snapshot,
            metrics=self.metrics,
        )

        if supplied != expected:
            raise ValueError(
                "Audit storage-admission result does not "
                "match its verification, snapshot, and "
                "policy."
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
    def receipt(
        self,
    ) -> StrategyPlanningAuditVerificationReceipt | None:
        return self.verification.receipt

    @property
    def broker_symbol(self) -> str:
        return self.verification.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.verification.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.verification.direction

    @property
    def side(self) -> StrategyOrderSide | None:
        if self.receipt is None:
            return None

        return self.receipt.side

    @property
    def is_admitted(self) -> bool:
        return self.status == PlanningAuditStorageAdmissionStatus.ADMITTED

    @property
    def is_blocked(self) -> bool:
        return not self.is_admitted

    @property
    def has_snapshot(self) -> bool:
        return self.snapshot is not None

    @property
    def has_metrics(self) -> bool:
        return self.metrics is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def can_continue_to_storage_write_design(self) -> bool:
        return self.is_admitted

    @property
    def storage_write_authorized(self) -> bool:
        return False

    @property
    def is_persisted(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def can_write_network(self) -> bool:
        return False

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
    def snapshot_required(
        self,
    ) -> PlanningAuditStorageSnapshot:
        if self.snapshot is None:
            raise ValueError("No audit storage snapshot is available.")

        return self.snapshot

    @property
    def metrics_required(
        self,
    ) -> PlanningAuditStorageMetrics:
        if self.metrics is None:
            raise ValueError("No audit storage metrics are available.")

        return self.metrics

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )
        snapshot_fragment = (
            self.snapshot.stable_id if self.snapshot is not None else "NO_STORAGE_SNAPSHOT"
        )
        metrics_fragment = (
            self.metrics.stable_id if self.metrics is not None else "NO_STORAGE_METRICS"
        )

        return (
            f"{self.verification.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_ADMISSION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}:"
            f"{snapshot_fragment}:"
            f"{metrics_fragment}"
        )


class StrategyPlanningAuditStorageAdmissionGate:
    """
    Pure read-only storage-admission gate.

    ADMITTED allows later storage-write design analysis only.
    It does not create a path, connection, transaction, file,
    database write, network request, or broker operation.
    """

    def __init__(
        self,
        policy: (PlanningAuditStorageAdmissionPolicy | None) = None,
    ) -> None:
        selected_policy = policy or PlanningAuditStorageAdmissionPolicy()

        if not isinstance(
            selected_policy,
            PlanningAuditStorageAdmissionPolicy,
        ):
            raise ValueError("policy must be a PlanningAuditStorageAdmissionPolicy.")

        self._policy = selected_policy

    @property
    def policy(
        self,
    ) -> PlanningAuditStorageAdmissionPolicy:
        return self._policy

    def evaluate(
        self,
        verification: PlanningAuditVerificationDecision,
        snapshot: PlanningAuditStorageSnapshot | None = None,
    ) -> PlanningAuditStorageAdmissionDecision:
        if not isinstance(
            verification,
            PlanningAuditVerificationDecision,
        ):
            raise PlanningAuditStorageAdmissionError(
                PlanningAuditStorageAdmissionErrorReason.INVALID_VERIFICATION_DECISION,
                "verification must be a PlanningAuditVerificationDecision.",
            )

        if snapshot is not None and not isinstance(
            snapshot,
            PlanningAuditStorageSnapshot,
        ):
            raise PlanningAuditStorageAdmissionError(
                PlanningAuditStorageAdmissionErrorReason.INVALID_STORAGE_SNAPSHOT,
                "snapshot must be a PlanningAuditStorageSnapshot or None.",
            )

        evaluation = _derive_admission(
            verification,
            snapshot,
            self._policy,
        )

        return PlanningAuditStorageAdmissionDecision(
            verification=verification,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            snapshot=evaluation.snapshot,
            metrics=evaluation.metrics,
        )

    def admit(
        self,
        verification: PlanningAuditVerificationDecision,
        snapshot: PlanningAuditStorageSnapshot | None = None,
    ) -> PlanningAuditStorageAdmissionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            verification,
            snapshot,
        )

    def check(
        self,
        verification: PlanningAuditVerificationDecision,
        snapshot: PlanningAuditStorageSnapshot | None = None,
    ) -> PlanningAuditStorageAdmissionDecision:
        """Compatibility alias for evaluate()."""

        return self.evaluate(
            verification,
            snapshot,
        )


def evaluate_planning_audit_storage_admission(
    verification: PlanningAuditVerificationDecision,
    snapshot: PlanningAuditStorageSnapshot | None = None,
    policy: PlanningAuditStorageAdmissionPolicy | None = None,
) -> PlanningAuditStorageAdmissionDecision:
    return StrategyPlanningAuditStorageAdmissionGate(policy=policy).evaluate(
        verification,
        snapshot,
    )


AuditStorageAdmissionBlocker = PlanningAuditStorageAdmissionBlocker
AuditStorageAdmissionDecision = PlanningAuditStorageAdmissionDecision
AuditStorageAdmissionGate = StrategyPlanningAuditStorageAdmissionGate
AuditStorageAdmissionPolicy = PlanningAuditStorageAdmissionPolicy
AuditStorageAdmissionReason = PlanningAuditStorageAdmissionReason
AuditStorageAdmissionStatus = PlanningAuditStorageAdmissionStatus
AuditStorageMetrics = PlanningAuditStorageMetrics
AuditStorageSnapshot = PlanningAuditStorageSnapshot
AuditStorageTarget = PlanningAuditStorageTarget
StrategyAuditStorageAdmissionGate = StrategyPlanningAuditStorageAdmissionGate
