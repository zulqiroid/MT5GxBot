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
from app.strategy.planning_audit_storage_adapter_contract import (
    PlanningAuditStorageAdapterContractDecision,
    StrategyPlanningAuditStorageAdapterContract,
)
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageTarget,
)


class PlanningAuditStorageAdapterCapability(str, Enum):
    APPEND_IF_ABSENT = "APPEND_IF_ABSENT"
    RETURN_EXISTING_ON_DUPLICATE = "RETURN_EXISTING_ON_DUPLICATE"
    VERIFY_BEFORE_ACCEPT = "VERIFY_BEFORE_ACCEPT"
    ENCRYPTION_AT_REST = "ENCRYPTION_AT_REST"
    IDEMPOTENCY_KEY_LOOKUP = "IDEMPOTENCY_KEY_LOOKUP"
    RETENTION_POLICY_ENFORCEMENT = "RETENTION_POLICY_ENFORCEMENT"
    DRY_RUN_ONLY = "DRY_RUN_ONLY"


_CAPABILITY_ORDER = (
    PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
    PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
    PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
    PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
    PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
    PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
    PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
)


class PlanningAuditStorageAdapterAssessmentStatus(
    str,
    Enum,
):
    COMPATIBLE = "COMPATIBLE"
    BLOCKED = "BLOCKED"


class PlanningAuditStorageAdapterAssessmentReason(
    str,
    Enum,
):
    COMPATIBLE = "COMPATIBLE"
    ADAPTER_CONTRACT_BLOCKED = "ADAPTER_CONTRACT_BLOCKED"
    SNAPSHOT_STALE = "SNAPSHOT_STALE"
    ADAPTER_INACTIVE = "ADAPTER_INACTIVE"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    INVOCATION_ENABLED = "INVOCATION_ENABLED"
    APPEND_IF_ABSENT_UNSUPPORTED = "APPEND_IF_ABSENT_UNSUPPORTED"
    DUPLICATE_POLICY_UNSUPPORTED = "DUPLICATE_POLICY_UNSUPPORTED"
    INTEGRITY_VERIFICATION_UNSUPPORTED = "INTEGRITY_VERIFICATION_UNSUPPORTED"
    ENCRYPTION_UNSUPPORTED = "ENCRYPTION_UNSUPPORTED"
    IDEMPOTENCY_UNSUPPORTED = "IDEMPOTENCY_UNSUPPORTED"
    RETENTION_ENFORCEMENT_UNSUPPORTED = "RETENTION_ENFORCEMENT_UNSUPPORTED"
    DRY_RUN_CAPABILITY_REQUIRED = "DRY_RUN_CAPABILITY_REQUIRED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RETENTION_TOO_SHORT = "RETENTION_TOO_SHORT"
    MULTIPLE_ADAPTER_BLOCKERS = "MULTIPLE_ADAPTER_BLOCKERS"


class PlanningAuditStorageAdapterAssessmentBlocker(
    str,
    Enum,
):
    ADAPTER_CONTRACT_BLOCKED = "ADAPTER_CONTRACT_BLOCKED"
    SNAPSHOT_STALE = "SNAPSHOT_STALE"
    ADAPTER_INACTIVE = "ADAPTER_INACTIVE"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    INVOCATION_ENABLED = "INVOCATION_ENABLED"
    APPEND_IF_ABSENT_UNSUPPORTED = "APPEND_IF_ABSENT_UNSUPPORTED"
    DUPLICATE_POLICY_UNSUPPORTED = "DUPLICATE_POLICY_UNSUPPORTED"
    INTEGRITY_VERIFICATION_UNSUPPORTED = "INTEGRITY_VERIFICATION_UNSUPPORTED"
    ENCRYPTION_UNSUPPORTED = "ENCRYPTION_UNSUPPORTED"
    IDEMPOTENCY_UNSUPPORTED = "IDEMPOTENCY_UNSUPPORTED"
    RETENTION_ENFORCEMENT_UNSUPPORTED = "RETENTION_ENFORCEMENT_UNSUPPORTED"
    DRY_RUN_CAPABILITY_REQUIRED = "DRY_RUN_CAPABILITY_REQUIRED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RETENTION_TOO_SHORT = "RETENTION_TOO_SHORT"


class PlanningAuditStorageAdapterAssessmentErrorReason(
    str,
    Enum,
):
    INVALID_ADAPTER_CONTRACT_DECISION = "INVALID_ADAPTER_CONTRACT_DECISION"
    INVALID_CAPABILITY_SNAPSHOT = "INVALID_CAPABILITY_SNAPSHOT"


class PlanningAuditStorageAdapterAssessmentError(RuntimeError):
    """Structured read-only adapter assessment failure."""

    def __init__(
        self,
        reason: (PlanningAuditStorageAdapterAssessmentErrorReason),
        message: str,
    ) -> None:
        self.reason = PlanningAuditStorageAdapterAssessmentErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Planning-audit storage adapter-assessment error [{self.reason.value}]: {self.message}"
        )


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

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


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageAdapterAssessmentPolicy:
    """Strict requirements for read-only compatibility."""

    require_non_stale_snapshot: bool = True
    require_active_adapter: bool = True
    require_invocation_disabled: bool = True
    require_append_if_absent: bool = True
    require_duplicate_return_existing: bool = True
    require_integrity_verification: bool = True
    require_encryption_at_rest: bool = True
    require_idempotency_lookup: bool = True
    require_retention_enforcement: bool = True
    require_dry_run_only: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "require_non_stale_snapshot",
            "require_active_adapter",
            "require_invocation_disabled",
            "require_append_if_absent",
            "require_duplicate_return_existing",
            "require_integrity_verification",
            "require_encryption_at_rest",
            "require_idempotency_lookup",
            "require_retention_enforcement",
            "require_dry_run_only",
        ):
            object.__setattr__(
                self,
                field_name,
                _strict_boolean(
                    getattr(self, field_name),
                    field_name,
                ),
            )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageAdapterCapabilitySnapshot:
    """
    Externally supplied read-only adapter capabilities.

    No adapter object, connection, credential, path,
    transaction, command, or invocation is included.
    """

    observed_at: datetime
    adapter_name: str
    target: PlanningAuditStorageTarget
    active: bool
    invocation_enabled: bool
    capabilities: tuple[
        PlanningAuditStorageAdapterCapability,
        ...,
    ]
    maximum_payload_bytes: int
    maximum_retention_days: int

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
            "adapter_name",
            _non_empty_string(
                self.adapter_name,
                "adapter_name",
            ),
        )

        if not isinstance(
            self.target,
            PlanningAuditStorageTarget,
        ):
            raise ValueError("target must be a PlanningAuditStorageTarget member.")

        object.__setattr__(
            self,
            "active",
            _strict_boolean(
                self.active,
                "active",
            ),
        )
        object.__setattr__(
            self,
            "invocation_enabled",
            _strict_boolean(
                self.invocation_enabled,
                "invocation_enabled",
            ),
        )

        if not isinstance(self.capabilities, tuple):
            raise ValueError("capabilities must be a tuple.")

        if not all(
            isinstance(
                capability,
                PlanningAuditStorageAdapterCapability,
            )
            for capability in self.capabilities
        ):
            raise ValueError(
                "capabilities must contain PlanningAuditStorageAdapterCapability members."
            )

        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("Adapter capabilities cannot contain duplicates.")

        expected_order = tuple(
            capability for capability in _CAPABILITY_ORDER if capability in self.capabilities
        )

        if self.capabilities != expected_order:
            raise ValueError("Adapter capabilities must use deterministic order.")

        object.__setattr__(
            self,
            "maximum_payload_bytes",
            _positive_integer(
                self.maximum_payload_bytes,
                "maximum_payload_bytes",
            ),
        )
        object.__setattr__(
            self,
            "maximum_retention_days",
            _positive_integer(
                self.maximum_retention_days,
                "maximum_retention_days",
            ),
        )

    def supports(
        self,
        capability: PlanningAuditStorageAdapterCapability,
    ) -> bool:
        if not isinstance(
            capability,
            PlanningAuditStorageAdapterCapability,
        ):
            raise ValueError("capability must be a PlanningAuditStorageAdapterCapability.")

        return capability in self.capabilities

    @property
    def capability_count(self) -> int:
        return len(self.capabilities)

    @property
    def is_read_only_snapshot(self) -> bool:
        return True

    @property
    def can_invoke_adapter(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def stable_id(self) -> str:
        capability_fragment = ",".join(capability.value for capability in self.capabilities)

        return (
            f"{self.observed_at.isoformat()}:"
            f"{self.adapter_name}:"
            f"{self.target.value}:"
            f"ACTIVE[{self.active}]:"
            f"INVOCATION_ENABLED["
            f"{self.invocation_enabled}]:"
            f"CAPABILITIES[{capability_fragment}]:"
            f"MAX_PAYLOAD_BYTES["
            f"{self.maximum_payload_bytes}]:"
            f"MAX_RETENTION_DAYS["
            f"{self.maximum_retention_days}]"
        )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageAdapterAssessmentMetrics:
    """Deterministic payload and retention measurements."""

    required_payload_bytes: int
    maximum_payload_bytes: int
    payload_surplus_bytes: int
    payload_deficit_bytes: int
    required_retention_days: int
    maximum_retention_days: int
    retention_surplus_days: int
    retention_deficit_days: int

    def __post_init__(self) -> None:
        for field_name in (
            "required_payload_bytes",
            "maximum_payload_bytes",
            "required_retention_days",
            "maximum_retention_days",
        ):
            object.__setattr__(
                self,
                field_name,
                _positive_integer(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        for field_name in (
            "payload_surplus_bytes",
            "payload_deficit_bytes",
            "retention_surplus_days",
            "retention_deficit_days",
        ):
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")

        expected_payload_surplus = max(
            0,
            self.maximum_payload_bytes - self.required_payload_bytes,
        )
        expected_payload_deficit = max(
            0,
            self.required_payload_bytes - self.maximum_payload_bytes,
        )
        expected_retention_surplus = max(
            0,
            self.maximum_retention_days - self.required_retention_days,
        )
        expected_retention_deficit = max(
            0,
            self.required_retention_days - self.maximum_retention_days,
        )

        if self.payload_surplus_bytes != expected_payload_surplus:
            raise ValueError("payload_surplus_bytes is inconsistent.")

        if self.payload_deficit_bytes != expected_payload_deficit:
            raise ValueError("payload_deficit_bytes is inconsistent.")

        if self.retention_surplus_days != expected_retention_surplus:
            raise ValueError("retention_surplus_days is inconsistent.")

        if self.retention_deficit_days != expected_retention_deficit:
            raise ValueError("retention_deficit_days is inconsistent.")

    @property
    def supports_payload(self) -> bool:
        return self.payload_deficit_bytes == 0

    @property
    def supports_retention(self) -> bool:
        return self.retention_deficit_days == 0

    @property
    def stable_id(self) -> str:
        return (
            f"REQUIRED_PAYLOAD["
            f"{self.required_payload_bytes}]:"
            f"MAXIMUM_PAYLOAD["
            f"{self.maximum_payload_bytes}]:"
            f"PAYLOAD_SURPLUS["
            f"{self.payload_surplus_bytes}]:"
            f"PAYLOAD_DEFICIT["
            f"{self.payload_deficit_bytes}]:"
            f"REQUIRED_RETENTION["
            f"{self.required_retention_days}]:"
            f"MAXIMUM_RETENTION["
            f"{self.maximum_retention_days}]:"
            f"RETENTION_SURPLUS["
            f"{self.retention_surplus_days}]:"
            f"RETENTION_DEFICIT["
            f"{self.retention_deficit_days}]"
        )


def _build_metrics(
    contract: StrategyPlanningAuditStorageAdapterContract,
    snapshot: (PlanningAuditStorageAdapterCapabilitySnapshot),
) -> PlanningAuditStorageAdapterAssessmentMetrics:
    return PlanningAuditStorageAdapterAssessmentMetrics(
        required_payload_bytes=(contract.content_length_bytes),
        maximum_payload_bytes=(snapshot.maximum_payload_bytes),
        payload_surplus_bytes=max(
            0,
            snapshot.maximum_payload_bytes - contract.content_length_bytes,
        ),
        payload_deficit_bytes=max(
            0,
            contract.content_length_bytes - snapshot.maximum_payload_bytes,
        ),
        required_retention_days=contract.retention_days,
        maximum_retention_days=(snapshot.maximum_retention_days),
        retention_surplus_days=max(
            0,
            snapshot.maximum_retention_days - contract.retention_days,
        ),
        retention_deficit_days=max(
            0,
            contract.retention_days - snapshot.maximum_retention_days,
        ),
    )


def _reason_for_blockers(
    blockers: tuple[
        PlanningAuditStorageAdapterAssessmentBlocker,
        ...,
    ],
) -> PlanningAuditStorageAdapterAssessmentReason:
    if not blockers:
        return PlanningAuditStorageAdapterAssessmentReason.COMPATIBLE

    if len(blockers) > 1:
        return PlanningAuditStorageAdapterAssessmentReason.MULTIPLE_ADAPTER_BLOCKERS

    return PlanningAuditStorageAdapterAssessmentReason(blockers[0].value)


@dataclass(frozen=True, slots=True)
class _AdapterAssessmentEvaluation:
    status: PlanningAuditStorageAdapterAssessmentStatus
    reason: PlanningAuditStorageAdapterAssessmentReason
    blockers: tuple[
        PlanningAuditStorageAdapterAssessmentBlocker,
        ...,
    ]
    snapshot: PlanningAuditStorageAdapterCapabilitySnapshot | None
    metrics: PlanningAuditStorageAdapterAssessmentMetrics | None


def _derive_assessment(
    adapter_contract: (PlanningAuditStorageAdapterContractDecision),
    snapshot: (PlanningAuditStorageAdapterCapabilitySnapshot | None),
    policy: PlanningAuditStorageAdapterAssessmentPolicy,
) -> _AdapterAssessmentEvaluation:
    if adapter_contract.is_blocked:
        return _AdapterAssessmentEvaluation(
            status=(PlanningAuditStorageAdapterAssessmentStatus.BLOCKED),
            reason=(PlanningAuditStorageAdapterAssessmentReason.ADAPTER_CONTRACT_BLOCKED),
            blockers=(PlanningAuditStorageAdapterAssessmentBlocker.ADAPTER_CONTRACT_BLOCKED,),
            snapshot=None,
            metrics=None,
        )

    if snapshot is None:
        raise PlanningAuditStorageAdapterAssessmentError(
            PlanningAuditStorageAdapterAssessmentErrorReason.INVALID_CAPABILITY_SNAPSHOT,
            "A created adapter contract requires a capability snapshot.",
        )

    contract = adapter_contract.contract_required
    metrics = _build_metrics(
        contract,
        snapshot,
    )
    blockers: list[PlanningAuditStorageAdapterAssessmentBlocker] = []

    if policy.require_non_stale_snapshot and snapshot.observed_at < contract.observed_at:
        blockers.append(PlanningAuditStorageAdapterAssessmentBlocker.SNAPSHOT_STALE)

    if policy.require_active_adapter and not snapshot.active:
        blockers.append(PlanningAuditStorageAdapterAssessmentBlocker.ADAPTER_INACTIVE)

    if snapshot.target != contract.target:
        blockers.append(PlanningAuditStorageAdapterAssessmentBlocker.TARGET_MISMATCH)

    if policy.require_invocation_disabled and snapshot.invocation_enabled:
        blockers.append(PlanningAuditStorageAdapterAssessmentBlocker.INVOCATION_ENABLED)

    required_capabilities = (
        (
            policy.require_append_if_absent,
            PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
            PlanningAuditStorageAdapterAssessmentBlocker.APPEND_IF_ABSENT_UNSUPPORTED,
        ),
        (
            policy.require_duplicate_return_existing,
            PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
            PlanningAuditStorageAdapterAssessmentBlocker.DUPLICATE_POLICY_UNSUPPORTED,
        ),
        (
            policy.require_integrity_verification,
            PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
            PlanningAuditStorageAdapterAssessmentBlocker.INTEGRITY_VERIFICATION_UNSUPPORTED,
        ),
        (
            policy.require_encryption_at_rest,
            PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
            PlanningAuditStorageAdapterAssessmentBlocker.ENCRYPTION_UNSUPPORTED,
        ),
        (
            policy.require_idempotency_lookup,
            PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
            PlanningAuditStorageAdapterAssessmentBlocker.IDEMPOTENCY_UNSUPPORTED,
        ),
        (
            policy.require_retention_enforcement,
            PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
            PlanningAuditStorageAdapterAssessmentBlocker.RETENTION_ENFORCEMENT_UNSUPPORTED,
        ),
        (
            policy.require_dry_run_only,
            PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
            PlanningAuditStorageAdapterAssessmentBlocker.DRY_RUN_CAPABILITY_REQUIRED,
        ),
    )

    for required, capability, blocker in required_capabilities:
        if required and not snapshot.supports(capability):
            blockers.append(blocker)

    if not metrics.supports_payload:
        blockers.append(PlanningAuditStorageAdapterAssessmentBlocker.PAYLOAD_TOO_LARGE)

    if not metrics.supports_retention:
        blockers.append(PlanningAuditStorageAdapterAssessmentBlocker.RETENTION_TOO_SHORT)

    blocker_tuple = tuple(blockers)

    return _AdapterAssessmentEvaluation(
        status=(
            PlanningAuditStorageAdapterAssessmentStatus.BLOCKED
            if blocker_tuple
            else PlanningAuditStorageAdapterAssessmentStatus.COMPATIBLE
        ),
        reason=_reason_for_blockers(blocker_tuple),
        blockers=blocker_tuple,
        snapshot=snapshot,
        metrics=metrics,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageAdapterAssessmentDecision:
    """Validated read-only adapter compatibility result."""

    adapter_contract: PlanningAuditStorageAdapterContractDecision
    policy: PlanningAuditStorageAdapterAssessmentPolicy
    status: PlanningAuditStorageAdapterAssessmentStatus
    reason: PlanningAuditStorageAdapterAssessmentReason
    blockers: tuple[
        PlanningAuditStorageAdapterAssessmentBlocker,
        ...,
    ]
    snapshot: PlanningAuditStorageAdapterCapabilitySnapshot | None
    metrics: PlanningAuditStorageAdapterAssessmentMetrics | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.adapter_contract,
            PlanningAuditStorageAdapterContractDecision,
        ):
            raise ValueError(
                "adapter_contract must be a PlanningAuditStorageAdapterContractDecision."
            )

        if not isinstance(
            self.policy,
            PlanningAuditStorageAdapterAssessmentPolicy,
        ):
            raise ValueError("policy must be a PlanningAuditStorageAdapterAssessmentPolicy.")

        try:
            status = PlanningAuditStorageAdapterAssessmentStatus(self.status)
            reason = PlanningAuditStorageAdapterAssessmentReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported adapter-assessment status or reason.") from error

        blockers = tuple(
            PlanningAuditStorageAdapterAssessmentBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Adapter-assessment blockers cannot contain duplicates.")

        if self.snapshot is not None and not isinstance(
            self.snapshot,
            PlanningAuditStorageAdapterCapabilitySnapshot,
        ):
            raise ValueError("snapshot must be a capability snapshot or None.")

        if self.metrics is not None and not isinstance(
            self.metrics,
            PlanningAuditStorageAdapterAssessmentMetrics,
        ):
            raise ValueError("metrics must be adapter-assessment metrics or None.")

        expected = _derive_assessment(
            self.adapter_contract,
            self.snapshot,
            self.policy,
        )
        supplied = _AdapterAssessmentEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            snapshot=self.snapshot,
            metrics=self.metrics,
        )

        if supplied != expected:
            raise ValueError(
                "Adapter-assessment result does not match its contract, snapshot, and policy."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def contract(
        self,
    ) -> StrategyPlanningAuditStorageAdapterContract | None:
        return self.adapter_contract.contract

    @property
    def broker_symbol(self) -> str:
        return self.adapter_contract.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.adapter_contract.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.adapter_contract.direction

    @property
    def side(self) -> StrategyOrderSide | None:
        if self.contract is None:
            return None

        return self.contract.side

    @property
    def is_compatible(self) -> bool:
        return self.status == PlanningAuditStorageAdapterAssessmentStatus.COMPATIBLE

    @property
    def is_blocked(self) -> bool:
        return not self.is_compatible

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
    def snapshot_required(
        self,
    ) -> PlanningAuditStorageAdapterCapabilitySnapshot:
        if self.snapshot is None:
            raise ValueError("No adapter capability snapshot is available.")

        return self.snapshot

    @property
    def metrics_required(
        self,
    ) -> PlanningAuditStorageAdapterAssessmentMetrics:
        if self.metrics is None:
            raise ValueError("No adapter-assessment metrics are available.")

        return self.metrics

    @property
    def can_continue_to_adapter_binding_design(self) -> bool:
        return self.is_compatible

    @property
    def adapter_binding_authorized(self) -> bool:
        return False

    @property
    def adapter_invocation_authorized(self) -> bool:
        return False

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
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )
        snapshot_fragment = (
            self.snapshot.stable_id if self.snapshot is not None else "NO_CAPABILITY_SNAPSHOT"
        )
        metrics_fragment = (
            self.metrics.stable_id if self.metrics is not None else "NO_ASSESSMENT_METRICS"
        )

        return (
            f"{self.adapter_contract.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_ADAPTER_ASSESSMENT:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}:"
            f"{snapshot_fragment}:"
            f"{metrics_fragment}"
        )


class StrategyPlanningAuditStorageAdapterAssessmentGate:
    """
    Pure read-only adapter compatibility gate.

    COMPATIBLE allows later binding-design analysis only.
    No adapter discovery, import, initialization, invocation,
    storage write, network call, broker action, or MT5
    operation is performed or authorized.
    """

    def __init__(
        self,
        policy: (PlanningAuditStorageAdapterAssessmentPolicy | None) = None,
    ) -> None:
        selected_policy = policy or PlanningAuditStorageAdapterAssessmentPolicy()

        if not isinstance(
            selected_policy,
            PlanningAuditStorageAdapterAssessmentPolicy,
        ):
            raise ValueError("policy must be a PlanningAuditStorageAdapterAssessmentPolicy.")

        self._policy = selected_policy

    @property
    def policy(
        self,
    ) -> PlanningAuditStorageAdapterAssessmentPolicy:
        return self._policy

    def assess(
        self,
        adapter_contract: (PlanningAuditStorageAdapterContractDecision),
        snapshot: (PlanningAuditStorageAdapterCapabilitySnapshot | None) = None,
    ) -> PlanningAuditStorageAdapterAssessmentDecision:
        if not isinstance(
            adapter_contract,
            PlanningAuditStorageAdapterContractDecision,
        ):
            raise PlanningAuditStorageAdapterAssessmentError(
                PlanningAuditStorageAdapterAssessmentErrorReason.INVALID_ADAPTER_CONTRACT_DECISION,
                "adapter_contract must be a PlanningAuditStorageAdapterContractDecision.",
            )

        if snapshot is not None and not isinstance(
            snapshot,
            PlanningAuditStorageAdapterCapabilitySnapshot,
        ):
            raise PlanningAuditStorageAdapterAssessmentError(
                PlanningAuditStorageAdapterAssessmentErrorReason.INVALID_CAPABILITY_SNAPSHOT,
                "snapshot must be an adapter capability snapshot or None.",
            )

        evaluation = _derive_assessment(
            adapter_contract,
            snapshot,
            self._policy,
        )

        return PlanningAuditStorageAdapterAssessmentDecision(
            adapter_contract=adapter_contract,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            snapshot=evaluation.snapshot,
            metrics=evaluation.metrics,
        )

    def evaluate(
        self,
        adapter_contract: (PlanningAuditStorageAdapterContractDecision),
        snapshot: (PlanningAuditStorageAdapterCapabilitySnapshot | None) = None,
    ) -> PlanningAuditStorageAdapterAssessmentDecision:
        """Compatibility alias for assess()."""

        return self.assess(
            adapter_contract,
            snapshot,
        )

    def check(
        self,
        adapter_contract: (PlanningAuditStorageAdapterContractDecision),
        snapshot: (PlanningAuditStorageAdapterCapabilitySnapshot | None) = None,
    ) -> PlanningAuditStorageAdapterAssessmentDecision:
        """Compatibility alias for assess()."""

        return self.assess(
            adapter_contract,
            snapshot,
        )


def assess_planning_audit_storage_adapter(
    adapter_contract: (PlanningAuditStorageAdapterContractDecision),
    snapshot: (PlanningAuditStorageAdapterCapabilitySnapshot | None) = None,
    policy: (PlanningAuditStorageAdapterAssessmentPolicy | None) = None,
) -> PlanningAuditStorageAdapterAssessmentDecision:
    return StrategyPlanningAuditStorageAdapterAssessmentGate(policy=policy).assess(
        adapter_contract,
        snapshot,
    )


AuditStorageAdapterAssessmentBlocker = PlanningAuditStorageAdapterAssessmentBlocker
AuditStorageAdapterAssessmentDecision = PlanningAuditStorageAdapterAssessmentDecision
AuditStorageAdapterAssessmentGate = StrategyPlanningAuditStorageAdapterAssessmentGate
AuditStorageAdapterAssessmentMetrics = PlanningAuditStorageAdapterAssessmentMetrics
AuditStorageAdapterAssessmentPolicy = PlanningAuditStorageAdapterAssessmentPolicy
AuditStorageAdapterAssessmentReason = PlanningAuditStorageAdapterAssessmentReason
AuditStorageAdapterAssessmentStatus = PlanningAuditStorageAdapterAssessmentStatus
AuditStorageAdapterCapability = PlanningAuditStorageAdapterCapability
AuditStorageAdapterCapabilitySnapshot = PlanningAuditStorageAdapterCapabilitySnapshot
StrategyAuditStorageAdapterAssessmentGate = StrategyPlanningAuditStorageAdapterAssessmentGate
