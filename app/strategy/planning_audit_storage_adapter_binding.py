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
from app.strategy.planning_audit_storage_adapter_assessment import (
    PlanningAuditStorageAdapterAssessmentDecision,
    PlanningAuditStorageAdapterCapabilitySnapshot,
)
from app.strategy.planning_audit_storage_adapter_contract import (
    PlanningAuditStorageAdapterOperation,
    PlanningAuditStorageDuplicatePolicy,
    PlanningAuditStorageIntegrityPolicy,
    PlanningAuditStorageResultExpectation,
    StrategyPlanningAuditStorageAdapterContract,
)
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageTarget,
)

PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_SCHEMA_VERSION = "1.0"


class PlanningAuditStorageAdapterBindingMode(str, Enum):
    REFERENCE_ONLY = "REFERENCE_ONLY"


class PlanningAuditStorageAdapterInvocationMode(str, Enum):
    DISABLED = "DISABLED"


class PlanningAuditStorageAdapterBindingVerificationMode(
    str,
    Enum,
):
    SNAPSHOT_AND_CONTRACT_LOCKED = "SNAPSHOT_AND_CONTRACT_LOCKED"


class PlanningAuditStorageAdapterBindingStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditStorageAdapterBindingReason(str, Enum):
    CREATED = "CREATED"
    ADAPTER_ASSESSMENT_BLOCKED = "ADAPTER_ASSESSMENT_BLOCKED"


class PlanningAuditStorageAdapterBindingBlocker(str, Enum):
    ADAPTER_ASSESSMENT_BLOCKED = "ADAPTER_ASSESSMENT_BLOCKED"


class PlanningAuditStorageAdapterBindingErrorReason(
    str,
    Enum,
):
    INVALID_ADAPTER_ASSESSMENT_DECISION = "INVALID_ADAPTER_ASSESSMENT_DECISION"


class PlanningAuditStorageAdapterBindingError(RuntimeError):
    """Structured analytical adapter-binding failure."""

    def __init__(
        self,
        reason: (PlanningAuditStorageAdapterBindingErrorReason),
        message: str,
    ) -> None:
        self.reason = PlanningAuditStorageAdapterBindingErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Planning-audit storage adapter-binding error [{self.reason.value}]: {self.message}"
        )


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


def _is_lowercase_sha256(value: str) -> bool:
    hexadecimal = set("0123456789abcdef")

    return (
        len(value) == 64
        and value == value.lower()
        and all(character in hexadecimal for character in value)
    )


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditStorageAdapterBinding:
    """
    Immutable reference-only adapter binding blueprint.

    The binding records compatible adapter metadata and
    locked contract lineage. It contains no adapter object,
    callable, path, connection, transaction, invocation,
    authorization, or persistence operation.
    """

    adapter_assessment: PlanningAuditStorageAdapterAssessmentDecision
    schema_version: str
    adapter_name: str
    target: PlanningAuditStorageTarget
    binding_mode: PlanningAuditStorageAdapterBindingMode
    invocation_mode: PlanningAuditStorageAdapterInvocationMode
    verification_mode: PlanningAuditStorageAdapterBindingVerificationMode
    operation: PlanningAuditStorageAdapterOperation
    duplicate_policy: PlanningAuditStorageDuplicatePolicy
    integrity_policy: PlanningAuditStorageIntegrityPolicy
    result_expectation: PlanningAuditStorageResultExpectation
    capability_snapshot_id: str
    contract_id: str
    content_digest: str
    manifest_digest: str
    idempotency_key: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.adapter_assessment,
            PlanningAuditStorageAdapterAssessmentDecision,
        ):
            raise ValueError(
                "adapter_assessment must be a PlanningAuditStorageAdapterAssessmentDecision."
            )

        if not self.adapter_assessment.is_compatible:
            raise ValueError(
                "An adapter binding requires a compatible audit storage adapter assessment."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_SCHEMA_VERSION):
            raise ValueError("schema_version must match the current adapter-binding schema.")

        adapter_name = _non_empty_string(
            self.adapter_name,
            "adapter_name",
        )

        if not isinstance(
            self.target,
            PlanningAuditStorageTarget,
        ):
            raise ValueError("target must be a PlanningAuditStorageTarget member.")

        if not isinstance(
            self.binding_mode,
            PlanningAuditStorageAdapterBindingMode,
        ):
            raise ValueError(
                "binding_mode must be a PlanningAuditStorageAdapterBindingMode member."
            )

        if self.binding_mode != PlanningAuditStorageAdapterBindingMode.REFERENCE_ONLY:
            raise ValueError("Adapter binding must remain REFERENCE_ONLY.")

        if not isinstance(
            self.invocation_mode,
            PlanningAuditStorageAdapterInvocationMode,
        ):
            raise ValueError(
                "invocation_mode must be a PlanningAuditStorageAdapterInvocationMode member."
            )

        if self.invocation_mode != PlanningAuditStorageAdapterInvocationMode.DISABLED:
            raise ValueError("Adapter invocation mode must remain DISABLED.")

        if not isinstance(
            self.verification_mode,
            PlanningAuditStorageAdapterBindingVerificationMode,
        ):
            raise ValueError(
                "verification_mode must be a "
                "PlanningAuditStorageAdapterBindingVerificationMode "
                "member."
            )

        if (
            self.verification_mode
            != PlanningAuditStorageAdapterBindingVerificationMode.SNAPSHOT_AND_CONTRACT_LOCKED
        ):
            raise ValueError(
                "Binding verification mode must lock the capability snapshot and adapter contract."
            )

        if not isinstance(
            self.operation,
            PlanningAuditStorageAdapterOperation,
        ):
            raise ValueError("operation must be a PlanningAuditStorageAdapterOperation member.")

        if not isinstance(
            self.duplicate_policy,
            PlanningAuditStorageDuplicatePolicy,
        ):
            raise ValueError(
                "duplicate_policy must be a PlanningAuditStorageDuplicatePolicy member."
            )

        if not isinstance(
            self.integrity_policy,
            PlanningAuditStorageIntegrityPolicy,
        ):
            raise ValueError(
                "integrity_policy must be a PlanningAuditStorageIntegrityPolicy member."
            )

        if not isinstance(
            self.result_expectation,
            PlanningAuditStorageResultExpectation,
        ):
            raise ValueError(
                "result_expectation must be a PlanningAuditStorageResultExpectation member."
            )

        capability_snapshot_id = _non_empty_string(
            self.capability_snapshot_id,
            "capability_snapshot_id",
        )
        contract_id = _non_empty_string(
            self.contract_id,
            "contract_id",
        )
        content_digest = _non_empty_string(
            self.content_digest,
            "content_digest",
        )
        manifest_digest = _non_empty_string(
            self.manifest_digest,
            "manifest_digest",
        )
        idempotency_key = _non_empty_string(
            self.idempotency_key,
            "idempotency_key",
        )

        for field_name, digest in (
            ("content_digest", content_digest),
            ("manifest_digest", manifest_digest),
            ("idempotency_key", idempotency_key),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        snapshot = self.adapter_assessment.snapshot_required
        contract = self.adapter_assessment.adapter_contract.contract_required

        if adapter_name != snapshot.adapter_name:
            raise ValueError("adapter_name must match the compatible capability snapshot.")

        if self.target != snapshot.target:
            raise ValueError("target must match the compatible capability snapshot.")

        if self.target != contract.target:
            raise ValueError("target must match the adapter contract.")

        if self.operation != contract.operation:
            raise ValueError("operation must match the adapter contract.")

        if self.duplicate_policy != contract.duplicate_policy:
            raise ValueError("duplicate_policy must match the adapter contract.")

        if self.integrity_policy != contract.integrity_policy:
            raise ValueError("integrity_policy must match the adapter contract.")

        if self.result_expectation != contract.result_expectation:
            raise ValueError("result_expectation must match the adapter contract.")

        if capability_snapshot_id != snapshot.stable_id:
            raise ValueError(
                "capability_snapshot_id must match the compatible capability snapshot."
            )

        if contract_id != contract.contract_id:
            raise ValueError("contract_id must match the adapter contract.")

        if content_digest != contract.content_digest:
            raise ValueError("content_digest must match the adapter contract.")

        if manifest_digest != contract.manifest_digest:
            raise ValueError("manifest_digest must match the adapter contract.")

        if idempotency_key != contract.idempotency_key:
            raise ValueError("idempotency_key must match the adapter contract.")

        if not snapshot.active:
            raise ValueError("Adapter binding requires an active capability snapshot.")

        if snapshot.invocation_enabled:
            raise ValueError("Adapter binding requires invocation to remain disabled.")

        if not snapshot.is_read_only_snapshot:
            raise ValueError("Adapter binding requires a read-only capability snapshot.")

        if snapshot.can_invoke_adapter:
            raise ValueError("Capability snapshot cannot invoke the adapter.")

        if snapshot.can_write_storage:
            raise ValueError("Capability snapshot cannot write storage.")

        if not contract.is_adapter_contract_ready:
            raise ValueError("Adapter binding requires a ready adapter contract.")

        if contract.adapter_invocation_authorized:
            raise ValueError("Adapter binding cannot inherit adapter invocation authorization.")

        if contract.storage_write_authorized:
            raise ValueError("Adapter binding cannot inherit storage write authorization.")

        if contract.can_write_storage:
            raise ValueError("Adapter binding cannot inherit storage write capability.")

        if contract.can_write_network:
            raise ValueError("Adapter binding cannot inherit network write capability.")

        if contract.execution_authorized:
            raise ValueError("Adapter binding cannot contain trading execution authorization.")

        if contract.has_broker_request:
            raise ValueError("Adapter binding cannot contain a broker request.")

        if contract.can_submit_order:
            raise ValueError("Adapter binding cannot permit order submission.")

        if contract.is_executable:
            raise ValueError("Adapter binding cannot contain an executable contract.")

        if not (self.adapter_assessment.can_continue_to_adapter_binding_design):
            raise ValueError("Adapter assessment does not permit binding design.")

        if self.adapter_assessment.adapter_binding_authorized:
            raise ValueError("Adapter assessment cannot authorize binding.")

        if self.adapter_assessment.adapter_invocation_authorized:
            raise ValueError("Adapter assessment cannot authorize invocation.")

        if self.adapter_assessment.storage_write_authorized:
            raise ValueError("Adapter assessment cannot authorize storage writes.")

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "adapter_name",
            adapter_name,
        )
        object.__setattr__(
            self,
            "capability_snapshot_id",
            capability_snapshot_id,
        )
        object.__setattr__(
            self,
            "contract_id",
            contract_id,
        )
        object.__setattr__(
            self,
            "content_digest",
            content_digest,
        )
        object.__setattr__(
            self,
            "manifest_digest",
            manifest_digest,
        )
        object.__setattr__(
            self,
            "idempotency_key",
            idempotency_key,
        )

    @property
    def snapshot(
        self,
    ) -> PlanningAuditStorageAdapterCapabilitySnapshot:
        return self.adapter_assessment.snapshot_required

    @property
    def contract(
        self,
    ) -> StrategyPlanningAuditStorageAdapterContract:
        return self.adapter_assessment.adapter_contract.contract_required

    @property
    def broker_symbol(self) -> str:
        return self.contract.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.contract.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.contract.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.contract.side

    @property
    def is_reference_only(self) -> bool:
        return True

    @property
    def is_binding_ready(self) -> bool:
        return True

    @property
    def can_continue_to_binding_verification_design(
        self,
    ) -> bool:
        return True

    @property
    def has_adapter_instance(self) -> bool:
        return False

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
    def binding_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"AUDIT_STORAGE_ADAPTER_BINDING:"
            f"{self.adapter_name}:"
            f"{self.target.value}:"
            f"{self.binding_mode.value}:"
            f"{self.invocation_mode.value}:"
            f"CONTRACT[{self.contract_id}]:"
            f"IDEMPOTENCY_SHA256["
            f"{self.idempotency_key}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.adapter_assessment.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_ADAPTER_BINDING:"
            f"{self.binding_id}"
        )


@dataclass(frozen=True, slots=True)
class _AdapterBindingEvaluation:
    status: PlanningAuditStorageAdapterBindingStatus
    reason: PlanningAuditStorageAdapterBindingReason
    blockers: tuple[
        PlanningAuditStorageAdapterBindingBlocker,
        ...,
    ]
    binding: StrategyPlanningAuditStorageAdapterBinding | None


def _derive_binding(
    adapter_assessment: (PlanningAuditStorageAdapterAssessmentDecision),
) -> _AdapterBindingEvaluation:
    if adapter_assessment.is_blocked:
        return _AdapterBindingEvaluation(
            status=(PlanningAuditStorageAdapterBindingStatus.BLOCKED),
            reason=(PlanningAuditStorageAdapterBindingReason.ADAPTER_ASSESSMENT_BLOCKED),
            blockers=(PlanningAuditStorageAdapterBindingBlocker.ADAPTER_ASSESSMENT_BLOCKED,),
            binding=None,
        )

    snapshot = adapter_assessment.snapshot_required
    contract = adapter_assessment.adapter_contract.contract_required

    binding = StrategyPlanningAuditStorageAdapterBinding(
        adapter_assessment=adapter_assessment,
        schema_version=(PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_SCHEMA_VERSION),
        adapter_name=snapshot.adapter_name,
        target=contract.target,
        binding_mode=(PlanningAuditStorageAdapterBindingMode.REFERENCE_ONLY),
        invocation_mode=(PlanningAuditStorageAdapterInvocationMode.DISABLED),
        verification_mode=(
            PlanningAuditStorageAdapterBindingVerificationMode.SNAPSHOT_AND_CONTRACT_LOCKED
        ),
        operation=contract.operation,
        duplicate_policy=contract.duplicate_policy,
        integrity_policy=contract.integrity_policy,
        result_expectation=contract.result_expectation,
        capability_snapshot_id=snapshot.stable_id,
        contract_id=contract.contract_id,
        content_digest=contract.content_digest,
        manifest_digest=contract.manifest_digest,
        idempotency_key=contract.idempotency_key,
    )

    return _AdapterBindingEvaluation(
        status=(PlanningAuditStorageAdapterBindingStatus.CREATED),
        reason=(PlanningAuditStorageAdapterBindingReason.CREATED),
        blockers=(),
        binding=binding,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageAdapterBindingDecision:
    """Validated analytical adapter-binding result."""

    adapter_assessment: PlanningAuditStorageAdapterAssessmentDecision
    status: PlanningAuditStorageAdapterBindingStatus
    reason: PlanningAuditStorageAdapterBindingReason
    blockers: tuple[
        PlanningAuditStorageAdapterBindingBlocker,
        ...,
    ]
    binding: StrategyPlanningAuditStorageAdapterBinding | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.adapter_assessment,
            PlanningAuditStorageAdapterAssessmentDecision,
        ):
            raise ValueError(
                "adapter_assessment must be a PlanningAuditStorageAdapterAssessmentDecision."
            )

        try:
            status = PlanningAuditStorageAdapterBindingStatus(self.status)
            reason = PlanningAuditStorageAdapterBindingReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported adapter-binding status or reason.") from error

        blockers = tuple(
            PlanningAuditStorageAdapterBindingBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Adapter-binding blockers cannot contain duplicates.")

        if self.binding is not None and not isinstance(
            self.binding,
            StrategyPlanningAuditStorageAdapterBinding,
        ):
            raise ValueError(
                "binding must be a StrategyPlanningAuditStorageAdapterBinding or None."
            )

        expected = _derive_binding(self.adapter_assessment)
        supplied = _AdapterBindingEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            binding=self.binding,
        )

        if supplied != expected:
            raise ValueError(
                "Adapter-binding result does not match its adapter-assessment decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.adapter_assessment.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.adapter_assessment.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.adapter_assessment.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditStorageAdapterBindingStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_binding(self) -> bool:
        return self.binding is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def binding_required(
        self,
    ) -> StrategyPlanningAuditStorageAdapterBinding:
        if self.binding is None:
            raise ValueError("No planning-audit storage adapter binding was created.")

        return self.binding

    @property
    def can_continue_to_binding_verification_design(
        self,
    ) -> bool:
        return self.is_created

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

        return (
            f"{self.adapter_assessment.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditStorageAdapterBindingFactory:
    """
    Pure factory for reference-only adapter bindings.

    CREATED permits later binding-verification design only.
    It performs and authorizes no adapter import, instance,
    invocation, persistence, network, broker, MT5, or
    execution operation.
    """

    def generate(
        self,
        adapter_assessment: (PlanningAuditStorageAdapterAssessmentDecision),
    ) -> PlanningAuditStorageAdapterBindingDecision:
        if not isinstance(
            adapter_assessment,
            PlanningAuditStorageAdapterAssessmentDecision,
        ):
            raise PlanningAuditStorageAdapterBindingError(
                PlanningAuditStorageAdapterBindingErrorReason.INVALID_ADAPTER_ASSESSMENT_DECISION,
                "adapter_assessment must be a PlanningAuditStorageAdapterAssessmentDecision.",
            )

        evaluation = _derive_binding(adapter_assessment)

        return PlanningAuditStorageAdapterBindingDecision(
            adapter_assessment=adapter_assessment,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            binding=evaluation.binding,
        )

    def build(
        self,
        adapter_assessment: (PlanningAuditStorageAdapterAssessmentDecision),
    ) -> PlanningAuditStorageAdapterBindingDecision:
        """Compatibility alias for generate()."""

        return self.generate(adapter_assessment)

    def evaluate(
        self,
        adapter_assessment: (PlanningAuditStorageAdapterAssessmentDecision),
    ) -> PlanningAuditStorageAdapterBindingDecision:
        """Compatibility alias for generate()."""

        return self.generate(adapter_assessment)


def generate_planning_audit_storage_adapter_binding(
    adapter_assessment: (PlanningAuditStorageAdapterAssessmentDecision),
) -> PlanningAuditStorageAdapterBindingDecision:
    return StrategyPlanningAuditStorageAdapterBindingFactory().generate(adapter_assessment)


AuditStorageAdapterBinding = StrategyPlanningAuditStorageAdapterBinding
AuditStorageAdapterBindingDecision = PlanningAuditStorageAdapterBindingDecision
AuditStorageAdapterBindingFactory = StrategyPlanningAuditStorageAdapterBindingFactory
AuditStorageAdapterBindingMode = PlanningAuditStorageAdapterBindingMode
AuditStorageAdapterBindingVerificationMode = PlanningAuditStorageAdapterBindingVerificationMode
AuditStorageAdapterInvocationMode = PlanningAuditStorageAdapterInvocationMode
PlanningAuditStorageAdapterBinding = StrategyPlanningAuditStorageAdapterBinding
PlanningAuditStorageAdapterBindingFactory = StrategyPlanningAuditStorageAdapterBindingFactory
StrategyAuditStorageAdapterBinding = StrategyPlanningAuditStorageAdapterBinding
StrategyAuditStorageAdapterBindingFactory = StrategyPlanningAuditStorageAdapterBindingFactory
