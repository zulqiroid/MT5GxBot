from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.order_intent_blueprint import (
    StrategyOrderSide,
)
from app.strategy.planning_audit_storage_adapter_binding import (
    PlanningAuditStorageAdapterBindingMode,
    PlanningAuditStorageAdapterInvocationMode,
    StrategyPlanningAuditStorageAdapterBinding,
)
from app.strategy.planning_audit_storage_adapter_binding_verification import (
    PlanningAuditStorageAdapterBindingVerificationDecision,
    StrategyPlanningAuditStorageAdapterBindingVerificationReceipt,
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

PLANNING_AUDIT_PERSISTENCE_REQUEST_SCHEMA_VERSION = "1.0"


class PlanningAuditPersistenceRequestMode(str, Enum):
    PREPARE_ONLY = "PREPARE_ONLY"


class PlanningAuditPersistenceInvocationMode(str, Enum):
    DISABLED = "DISABLED"


class PlanningAuditPersistenceRequestStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditPersistenceRequestReason(str, Enum):
    CREATED = "CREATED"
    BINDING_VERIFICATION_BLOCKED = "BINDING_VERIFICATION_BLOCKED"


class PlanningAuditPersistenceRequestBlocker(str, Enum):
    BINDING_VERIFICATION_BLOCKED = "BINDING_VERIFICATION_BLOCKED"


class PlanningAuditPersistenceRequestErrorReason(
    str,
    Enum,
):
    INVALID_BINDING_VERIFICATION_DECISION = "INVALID_BINDING_VERIFICATION_DECISION"


class PlanningAuditPersistenceRequestError(RuntimeError):
    """Structured analytical persistence-request failure."""

    def __init__(
        self,
        reason: PlanningAuditPersistenceRequestErrorReason,
        message: str,
    ) -> None:
        self.reason = PlanningAuditPersistenceRequestErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Planning-audit persistence-request error [{self.reason.value}]: {self.message}"
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


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


def _is_lowercase_sha256(value: str) -> bool:
    hexadecimal = set("0123456789abcdef")

    return (
        len(value) == 64
        and value == value.lower()
        and all(character in hexadecimal for character in value)
    )


def _sha256_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _canonical_request_payload(
    *,
    schema_version: str,
    request_mode: PlanningAuditPersistenceRequestMode,
    invocation_mode: PlanningAuditPersistenceInvocationMode,
    adapter_name: str,
    target: PlanningAuditStorageTarget,
    operation: PlanningAuditStorageAdapterOperation,
    duplicate_policy: PlanningAuditStorageDuplicatePolicy,
    integrity_policy: PlanningAuditStorageIntegrityPolicy,
    result_expectation: PlanningAuditStorageResultExpectation,
    content_length_bytes: int,
    content_digest: str,
    manifest_digest: str,
    idempotency_key: str,
    retention_days: int,
    binding_verification_receipt_digest: str,
    binding_id: str,
    snapshot_id: str,
    contract_id: str,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"REQUEST_MODE={request_mode.value}",
            f"INVOCATION_MODE={invocation_mode.value}",
            f"ADAPTER_NAME={adapter_name}",
            f"TARGET={target.value}",
            f"OPERATION={operation.value}",
            f"DUPLICATE_POLICY={duplicate_policy.value}",
            f"INTEGRITY_POLICY={integrity_policy.value}",
            f"RESULT_EXPECTATION={result_expectation.value}",
            (f"CONTENT_LENGTH_BYTES={content_length_bytes}"),
            f"CONTENT_DIGEST={content_digest}",
            f"MANIFEST_DIGEST={manifest_digest}",
            f"IDEMPOTENCY_KEY={idempotency_key}",
            f"RETENTION_DAYS={retention_days}",
            (f"BINDING_VERIFICATION_RECEIPT_DIGEST={binding_verification_receipt_digest}"),
            f"BINDING_ID={binding_id}",
            f"SNAPSHOT_ID={snapshot_id}",
            f"CONTRACT_ID={contract_id}",
        )
    )


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditPersistenceRequestBlueprint:
    """
    Immutable prepare-only persistence request blueprint.

    It preserves verified payload and adapter-contract
    lineage but contains no adapter instance, callable,
    path, connection, transaction, invocation,
    authorization, or storage-write operation.
    """

    binding_verification: PlanningAuditStorageAdapterBindingVerificationDecision
    schema_version: str
    request_mode: PlanningAuditPersistenceRequestMode
    invocation_mode: PlanningAuditPersistenceInvocationMode
    adapter_name: str
    target: PlanningAuditStorageTarget
    operation: PlanningAuditStorageAdapterOperation
    duplicate_policy: PlanningAuditStorageDuplicatePolicy
    integrity_policy: PlanningAuditStorageIntegrityPolicy
    result_expectation: PlanningAuditStorageResultExpectation
    content: str
    content_length_bytes: int
    content_digest: str
    manifest_digest: str
    idempotency_key: str
    retention_days: int
    binding_verification_receipt_digest: str
    binding_id: str
    snapshot_id: str
    contract_id: str
    request_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.binding_verification,
            PlanningAuditStorageAdapterBindingVerificationDecision,
        ):
            raise ValueError(
                "binding_verification must be a "
                "PlanningAuditStorageAdapterBindingVerificationDecision."
            )

        if not self.binding_verification.is_verified:
            raise ValueError(
                "A persistence request blueprint requires a verified adapter-binding decision."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PLANNING_AUDIT_PERSISTENCE_REQUEST_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current persistence-request schema.")

        if not isinstance(
            self.request_mode,
            PlanningAuditPersistenceRequestMode,
        ):
            raise ValueError("request_mode must be a PlanningAuditPersistenceRequestMode member.")

        if self.request_mode != PlanningAuditPersistenceRequestMode.PREPARE_ONLY:
            raise ValueError("Persistence request mode must remain PREPARE_ONLY.")

        if not isinstance(
            self.invocation_mode,
            PlanningAuditPersistenceInvocationMode,
        ):
            raise ValueError(
                "invocation_mode must be a PlanningAuditPersistenceInvocationMode member."
            )

        if self.invocation_mode != PlanningAuditPersistenceInvocationMode.DISABLED:
            raise ValueError("Persistence invocation mode must remain DISABLED.")

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
            self.operation,
            PlanningAuditStorageAdapterOperation,
        ):
            raise ValueError("operation must be a PlanningAuditStorageAdapterOperation member.")

        if self.operation != PlanningAuditStorageAdapterOperation.APPEND_IF_ABSENT:
            raise ValueError("Persistence operation must remain APPEND_IF_ABSENT.")

        if not isinstance(
            self.duplicate_policy,
            PlanningAuditStorageDuplicatePolicy,
        ):
            raise ValueError(
                "duplicate_policy must be a PlanningAuditStorageDuplicatePolicy member."
            )

        if self.duplicate_policy != PlanningAuditStorageDuplicatePolicy.RETURN_EXISTING:
            raise ValueError("Duplicate policy must remain RETURN_EXISTING.")

        if not isinstance(
            self.integrity_policy,
            PlanningAuditStorageIntegrityPolicy,
        ):
            raise ValueError(
                "integrity_policy must be a PlanningAuditStorageIntegrityPolicy member."
            )

        if self.integrity_policy != PlanningAuditStorageIntegrityPolicy.VERIFY_BEFORE_ACCEPT:
            raise ValueError("Integrity policy must remain VERIFY_BEFORE_ACCEPT.")

        if not isinstance(
            self.result_expectation,
            PlanningAuditStorageResultExpectation,
        ):
            raise ValueError(
                "result_expectation must be a PlanningAuditStorageResultExpectation member."
            )

        if self.result_expectation != PlanningAuditStorageResultExpectation.CREATED_OR_EXISTING:
            raise ValueError("Result expectation must remain CREATED_OR_EXISTING.")

        content = _non_empty_string(
            self.content,
            "content",
        )
        content_length = _positive_integer(
            self.content_length_bytes,
            "content_length_bytes",
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
        retention_days = _positive_integer(
            self.retention_days,
            "retention_days",
        )
        receipt_digest = _non_empty_string(
            self.binding_verification_receipt_digest,
            "binding_verification_receipt_digest",
        )
        binding_id = _non_empty_string(
            self.binding_id,
            "binding_id",
        )
        snapshot_id = _non_empty_string(
            self.snapshot_id,
            "snapshot_id",
        )
        contract_id = _non_empty_string(
            self.contract_id,
            "contract_id",
        )
        request_digest = _non_empty_string(
            self.request_digest,
            "request_digest",
        )

        for field_name, value in (
            ("content_digest", content_digest),
            ("manifest_digest", manifest_digest),
            ("idempotency_key", idempotency_key),
            (
                "binding_verification_receipt_digest",
                receipt_digest,
            ),
            ("request_digest", request_digest),
        ):
            if not _is_lowercase_sha256(value):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        receipt = self.binding_verification.receipt_required
        binding = receipt.binding
        snapshot = receipt.snapshot
        contract = receipt.contract

        if binding.binding_mode != PlanningAuditStorageAdapterBindingMode.REFERENCE_ONLY:
            raise ValueError("Persistence request requires a REFERENCE_ONLY adapter binding.")

        if binding.invocation_mode != PlanningAuditStorageAdapterInvocationMode.DISABLED:
            raise ValueError("Persistence request requires disabled adapter invocation.")

        if adapter_name != snapshot.adapter_name:
            raise ValueError("adapter_name must match the verified capability snapshot.")

        if self.target != snapshot.target:
            raise ValueError("target must match the verified capability snapshot.")

        if self.target != contract.target:
            raise ValueError("target must match the verified adapter contract.")

        if self.operation != contract.operation:
            raise ValueError("operation must match the verified adapter contract.")

        if self.duplicate_policy != contract.duplicate_policy:
            raise ValueError("duplicate_policy must match the verified adapter contract.")

        if self.integrity_policy != contract.integrity_policy:
            raise ValueError("integrity_policy must match the verified adapter contract.")

        if self.result_expectation != contract.result_expectation:
            raise ValueError("result_expectation must match the verified adapter contract.")

        if content != contract.content:
            raise ValueError("content must exactly match the verified adapter contract.")

        if content_length != contract.content_length_bytes:
            raise ValueError("content_length_bytes must match the verified adapter contract.")

        if len(content.encode("utf-8")) != content_length:
            raise ValueError("content_length_bytes must match the UTF-8 payload size.")

        if content_digest != contract.content_digest:
            raise ValueError("content_digest must match the verified adapter contract.")

        if content_digest != receipt.verified_content_digest:
            raise ValueError("content_digest must match the binding verification receipt.")

        if manifest_digest != contract.manifest_digest:
            raise ValueError("manifest_digest must match the verified adapter contract.")

        if manifest_digest != receipt.verified_manifest_digest:
            raise ValueError("manifest_digest must match the binding verification receipt.")

        if idempotency_key != contract.idempotency_key:
            raise ValueError("idempotency_key must match the verified adapter contract.")

        if idempotency_key != receipt.verified_idempotency_key:
            raise ValueError("idempotency_key must match the binding verification receipt.")

        if retention_days != contract.retention_days:
            raise ValueError("retention_days must match the verified adapter contract.")

        if receipt_digest != receipt.receipt_digest:
            raise ValueError(
                "binding_verification_receipt_digest must match the binding verification receipt."
            )

        if binding_id != receipt.verified_binding_id:
            raise ValueError("binding_id must match the binding verification receipt.")

        if binding_id != binding.binding_id:
            raise ValueError("binding_id must match the verified adapter binding.")

        if snapshot_id != receipt.verified_snapshot_id:
            raise ValueError("snapshot_id must match the binding verification receipt.")

        if snapshot_id != snapshot.stable_id:
            raise ValueError("snapshot_id must match the verified capability snapshot.")

        if contract_id != receipt.verified_contract_id:
            raise ValueError("contract_id must match the binding verification receipt.")

        if contract_id != contract.contract_id:
            raise ValueError("contract_id must match the verified adapter contract.")

        if not receipt.is_verified:
            raise ValueError("Persistence request requires a verified binding receipt.")

        if not (receipt.can_continue_to_persistence_request_design):
            raise ValueError("Binding verification does not permit persistence-request design.")

        if receipt.has_adapter_instance:
            raise ValueError("Persistence request cannot contain an adapter instance.")

        if receipt.adapter_invocation_authorized:
            raise ValueError("Persistence request cannot inherit adapter invocation authorization.")

        if receipt.storage_write_authorized:
            raise ValueError("Persistence request cannot inherit storage-write authorization.")

        if receipt.is_persisted:
            raise ValueError("Persistence request cannot assume prior persistence.")

        if receipt.can_write_storage:
            raise ValueError("Persistence request cannot write storage.")

        if receipt.can_write_network:
            raise ValueError("Persistence request cannot write to the network.")

        if receipt.execution_authorized:
            raise ValueError("Persistence request cannot contain trading execution authorization.")

        if receipt.has_broker_request:
            raise ValueError("Persistence request cannot contain a broker request.")

        if receipt.can_submit_order:
            raise ValueError("Persistence request cannot submit an order.")

        if receipt.is_executable:
            raise ValueError("Persistence request cannot be executable.")

        canonical_payload = _canonical_request_payload(
            schema_version=schema_version,
            request_mode=self.request_mode,
            invocation_mode=self.invocation_mode,
            adapter_name=adapter_name,
            target=self.target,
            operation=self.operation,
            duplicate_policy=self.duplicate_policy,
            integrity_policy=self.integrity_policy,
            result_expectation=self.result_expectation,
            content_length_bytes=content_length,
            content_digest=content_digest,
            manifest_digest=manifest_digest,
            idempotency_key=idempotency_key,
            retention_days=retention_days,
            binding_verification_receipt_digest=(receipt_digest),
            binding_id=binding_id,
            snapshot_id=snapshot_id,
            contract_id=contract_id,
        )
        expected_request_digest = _sha256_digest(canonical_payload)

        if request_digest != expected_request_digest:
            raise ValueError(
                "request_digest does not match the canonical persistence-request payload."
            )

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
            "content",
            content,
        )
        object.__setattr__(
            self,
            "content_length_bytes",
            content_length,
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
        object.__setattr__(
            self,
            "retention_days",
            retention_days,
        )
        object.__setattr__(
            self,
            "binding_verification_receipt_digest",
            receipt_digest,
        )
        object.__setattr__(
            self,
            "binding_id",
            binding_id,
        )
        object.__setattr__(
            self,
            "snapshot_id",
            snapshot_id,
        )
        object.__setattr__(
            self,
            "contract_id",
            contract_id,
        )
        object.__setattr__(
            self,
            "request_digest",
            request_digest,
        )

    @property
    def receipt(
        self,
    ) -> StrategyPlanningAuditStorageAdapterBindingVerificationReceipt:
        return self.binding_verification.receipt_required

    @property
    def binding(
        self,
    ) -> StrategyPlanningAuditStorageAdapterBinding:
        return self.receipt.binding

    @property
    def contract(
        self,
    ) -> StrategyPlanningAuditStorageAdapterContract:
        return self.receipt.contract

    @property
    def snapshot(self):
        return self.receipt.snapshot

    @property
    def broker_symbol(self) -> str:
        return self.binding.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.binding.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.binding.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.binding.side

    @property
    def content_bytes(self) -> bytes:
        return self.content.encode("utf-8")

    @property
    def canonical_payload(self) -> str:
        return _canonical_request_payload(
            schema_version=self.schema_version,
            request_mode=self.request_mode,
            invocation_mode=self.invocation_mode,
            adapter_name=self.adapter_name,
            target=self.target,
            operation=self.operation,
            duplicate_policy=self.duplicate_policy,
            integrity_policy=self.integrity_policy,
            result_expectation=self.result_expectation,
            content_length_bytes=self.content_length_bytes,
            content_digest=self.content_digest,
            manifest_digest=self.manifest_digest,
            idempotency_key=self.idempotency_key,
            retention_days=self.retention_days,
            binding_verification_receipt_digest=(self.binding_verification_receipt_digest),
            binding_id=self.binding_id,
            snapshot_id=self.snapshot_id,
            contract_id=self.contract_id,
        )

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def is_prepare_only(self) -> bool:
        return True

    @property
    def is_request_blueprint_ready(self) -> bool:
        return True

    @property
    def can_continue_to_request_verification_design(
        self,
    ) -> bool:
        return True

    @property
    def has_adapter_instance(self) -> bool:
        return False

    @property
    def request_submission_authorized(self) -> bool:
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
    def request_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"AUDIT_PERSISTENCE_REQUEST:"
            f"{self.adapter_name}:"
            f"{self.target.value}:"
            f"{self.request_mode.value}:"
            f"{self.invocation_mode.value}:"
            f"{self.operation.value}:"
            f"IDEMPOTENCY_SHA256["
            f"{self.idempotency_key}]:"
            f"REQUEST_SHA256[{self.request_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.binding_verification.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_REQUEST:"
            f"{self.request_id}"
        )


@dataclass(frozen=True, slots=True)
class _PersistenceRequestEvaluation:
    status: PlanningAuditPersistenceRequestStatus
    reason: PlanningAuditPersistenceRequestReason
    blockers: tuple[
        PlanningAuditPersistenceRequestBlocker,
        ...,
    ]
    request: StrategyPlanningAuditPersistenceRequestBlueprint | None


def _derive_request(
    binding_verification: (PlanningAuditStorageAdapterBindingVerificationDecision),
) -> _PersistenceRequestEvaluation:
    if binding_verification.is_blocked:
        return _PersistenceRequestEvaluation(
            status=PlanningAuditPersistenceRequestStatus.BLOCKED,
            reason=(PlanningAuditPersistenceRequestReason.BINDING_VERIFICATION_BLOCKED),
            blockers=(PlanningAuditPersistenceRequestBlocker.BINDING_VERIFICATION_BLOCKED,),
            request=None,
        )

    receipt = binding_verification.receipt_required
    binding = receipt.binding
    snapshot = receipt.snapshot
    contract = receipt.contract

    canonical_payload = _canonical_request_payload(
        schema_version=(PLANNING_AUDIT_PERSISTENCE_REQUEST_SCHEMA_VERSION),
        request_mode=(PlanningAuditPersistenceRequestMode.PREPARE_ONLY),
        invocation_mode=(PlanningAuditPersistenceInvocationMode.DISABLED),
        adapter_name=snapshot.adapter_name,
        target=contract.target,
        operation=contract.operation,
        duplicate_policy=contract.duplicate_policy,
        integrity_policy=contract.integrity_policy,
        result_expectation=contract.result_expectation,
        content_length_bytes=contract.content_length_bytes,
        content_digest=contract.content_digest,
        manifest_digest=contract.manifest_digest,
        idempotency_key=contract.idempotency_key,
        retention_days=contract.retention_days,
        binding_verification_receipt_digest=(receipt.receipt_digest),
        binding_id=binding.binding_id,
        snapshot_id=snapshot.stable_id,
        contract_id=contract.contract_id,
    )

    request = StrategyPlanningAuditPersistenceRequestBlueprint(
        binding_verification=binding_verification,
        schema_version=(PLANNING_AUDIT_PERSISTENCE_REQUEST_SCHEMA_VERSION),
        request_mode=(PlanningAuditPersistenceRequestMode.PREPARE_ONLY),
        invocation_mode=(PlanningAuditPersistenceInvocationMode.DISABLED),
        adapter_name=snapshot.adapter_name,
        target=contract.target,
        operation=contract.operation,
        duplicate_policy=contract.duplicate_policy,
        integrity_policy=contract.integrity_policy,
        result_expectation=contract.result_expectation,
        content=contract.content,
        content_length_bytes=contract.content_length_bytes,
        content_digest=contract.content_digest,
        manifest_digest=contract.manifest_digest,
        idempotency_key=contract.idempotency_key,
        retention_days=contract.retention_days,
        binding_verification_receipt_digest=(receipt.receipt_digest),
        binding_id=binding.binding_id,
        snapshot_id=snapshot.stable_id,
        contract_id=contract.contract_id,
        request_digest=_sha256_digest(canonical_payload),
    )

    return _PersistenceRequestEvaluation(
        status=PlanningAuditPersistenceRequestStatus.CREATED,
        reason=PlanningAuditPersistenceRequestReason.CREATED,
        blockers=(),
        request=request,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditPersistenceRequestDecision:
    """Validated analytical persistence-request result."""

    binding_verification: PlanningAuditStorageAdapterBindingVerificationDecision
    status: PlanningAuditPersistenceRequestStatus
    reason: PlanningAuditPersistenceRequestReason
    blockers: tuple[
        PlanningAuditPersistenceRequestBlocker,
        ...,
    ]
    request: StrategyPlanningAuditPersistenceRequestBlueprint | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.binding_verification,
            PlanningAuditStorageAdapterBindingVerificationDecision,
        ):
            raise ValueError(
                "binding_verification must be a "
                "PlanningAuditStorageAdapterBindingVerificationDecision."
            )

        try:
            status = PlanningAuditPersistenceRequestStatus(self.status)
            reason = PlanningAuditPersistenceRequestReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported persistence-request status or reason.") from error

        blockers = tuple(
            PlanningAuditPersistenceRequestBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Persistence-request blockers cannot contain duplicates.")

        if self.request is not None and not isinstance(
            self.request,
            StrategyPlanningAuditPersistenceRequestBlueprint,
        ):
            raise ValueError(
                "request must be a StrategyPlanningAuditPersistenceRequestBlueprint or None."
            )

        expected = _derive_request(self.binding_verification)
        supplied = _PersistenceRequestEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            request=self.request,
        )

        if supplied != expected:
            raise ValueError(
                "Persistence-request result does not match its binding-verification decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.binding_verification.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.binding_verification.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.binding_verification.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditPersistenceRequestStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_request(self) -> bool:
        return self.request is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def request_required(
        self,
    ) -> StrategyPlanningAuditPersistenceRequestBlueprint:
        if self.request is None:
            raise ValueError("No planning-audit persistence request was created.")

        return self.request

    @property
    def can_continue_to_request_verification_design(
        self,
    ) -> bool:
        return self.is_created

    @property
    def has_adapter_instance(self) -> bool:
        return False

    @property
    def request_submission_authorized(self) -> bool:
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
            f"{self.binding_verification.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_REQUEST_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditPersistenceRequestFactory:
    """
    Pure factory for prepare-only persistence requests.

    CREATED permits later request-verification design only.
    It performs and authorizes no adapter instance,
    invocation, persistence, network, broker, MT5, or
    trading execution operation.
    """

    def generate(
        self,
        binding_verification: (PlanningAuditStorageAdapterBindingVerificationDecision),
    ) -> PlanningAuditPersistenceRequestDecision:
        if not isinstance(
            binding_verification,
            PlanningAuditStorageAdapterBindingVerificationDecision,
        ):
            raise PlanningAuditPersistenceRequestError(
                PlanningAuditPersistenceRequestErrorReason.INVALID_BINDING_VERIFICATION_DECISION,
                "binding_verification must be a "
                "PlanningAuditStorageAdapterBindingVerificationDecision.",
            )

        evaluation = _derive_request(binding_verification)

        return PlanningAuditPersistenceRequestDecision(
            binding_verification=binding_verification,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            request=evaluation.request,
        )

    def build(
        self,
        binding_verification: (PlanningAuditStorageAdapterBindingVerificationDecision),
    ) -> PlanningAuditPersistenceRequestDecision:
        """Compatibility alias for generate()."""

        return self.generate(binding_verification)

    def evaluate(
        self,
        binding_verification: (PlanningAuditStorageAdapterBindingVerificationDecision),
    ) -> PlanningAuditPersistenceRequestDecision:
        """Compatibility alias for generate()."""

        return self.generate(binding_verification)


def generate_planning_audit_persistence_request(
    binding_verification: (PlanningAuditStorageAdapterBindingVerificationDecision),
) -> PlanningAuditPersistenceRequestDecision:
    return StrategyPlanningAuditPersistenceRequestFactory().generate(binding_verification)


AuditPersistenceRequest = StrategyPlanningAuditPersistenceRequestBlueprint
AuditPersistenceRequestDecision = PlanningAuditPersistenceRequestDecision
AuditPersistenceRequestFactory = StrategyPlanningAuditPersistenceRequestFactory
AuditPersistenceRequestMode = PlanningAuditPersistenceRequestMode
AuditPersistenceInvocationMode = PlanningAuditPersistenceInvocationMode
PlanningAuditPersistenceRequest = StrategyPlanningAuditPersistenceRequestBlueprint
PlanningAuditPersistenceRequestFactory = StrategyPlanningAuditPersistenceRequestFactory
StrategyAuditPersistenceRequest = StrategyPlanningAuditPersistenceRequestBlueprint
StrategyAuditPersistenceRequestFactory = StrategyPlanningAuditPersistenceRequestFactory
