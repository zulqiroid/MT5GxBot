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
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageAdmissionDecision,
    PlanningAuditStorageMetrics,
    PlanningAuditStorageSnapshot,
    PlanningAuditStorageTarget,
)
from app.strategy.planning_audit_verification import (
    StrategyPlanningAuditVerificationReceipt,
)

PLANNING_AUDIT_STORAGE_BLUEPRINT_SCHEMA_VERSION = "1.0"


class PlanningAuditStorageWriteMode(str, Enum):
    APPEND_ONLY = "APPEND_ONLY"


class PlanningAuditStorageEncryptionMode(str, Enum):
    ENCRYPTION_AT_REST_REQUIRED = "ENCRYPTION_AT_REST_REQUIRED"


class PlanningAuditStorageIdempotencyMode(str, Enum):
    IDEMPOTENCY_REQUIRED = "IDEMPOTENCY_REQUIRED"


class PlanningAuditStorageBlueprintStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditStorageBlueprintReason(str, Enum):
    CREATED = "CREATED"
    STORAGE_ADMISSION_BLOCKED = "STORAGE_ADMISSION_BLOCKED"


class PlanningAuditStorageBlueprintBlocker(str, Enum):
    STORAGE_ADMISSION_BLOCKED = "STORAGE_ADMISSION_BLOCKED"


class PlanningAuditStorageBlueprintErrorReason(str, Enum):
    INVALID_STORAGE_ADMISSION_DECISION = "INVALID_STORAGE_ADMISSION_DECISION"


class PlanningAuditStorageBlueprintError(RuntimeError):
    """Structured analytical storage-blueprint failure."""

    def __init__(
        self,
        reason: PlanningAuditStorageBlueprintErrorReason,
        message: str,
    ) -> None:
        self.reason = PlanningAuditStorageBlueprintErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Planning-audit storage-blueprint error [{self.reason.value}]: {self.message}"
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


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


def _is_lowercase_sha256(value: str) -> bool:
    hexadecimal = set("0123456789abcdef")

    return (
        len(value) == 64
        and value == value.lower()
        and all(character in hexadecimal for character in value)
    )


def _idempotency_key_for(
    receipt: StrategyPlanningAuditVerificationReceipt,
) -> str:
    source = (
        f"{receipt.broker_symbol}:"
        f"{receipt.side.value}:"
        f"{receipt.verified_manifest_digest}:"
        f"{receipt.verified_content_digest}"
    )

    return sha256(source.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditStorageBlueprint:
    """
    Immutable analytical blueprint for later persistence.

    It specifies verified content and mandatory safeguards,
    but provides no path, connection, transaction, command,
    storage authorization, or write operation.
    """

    storage_admission: PlanningAuditStorageAdmissionDecision
    schema_version: str
    target: PlanningAuditStorageTarget
    write_mode: PlanningAuditStorageWriteMode
    encryption_mode: PlanningAuditStorageEncryptionMode
    idempotency_mode: PlanningAuditStorageIdempotencyMode
    content: str
    content_length_bytes: int
    content_digest: str
    manifest_digest: str
    idempotency_key: str
    retention_days: int
    required_capacity_bytes: int
    available_capacity_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(
            self.storage_admission,
            PlanningAuditStorageAdmissionDecision,
        ):
            raise ValueError("storage_admission must be a PlanningAuditStorageAdmissionDecision.")

        if not self.storage_admission.is_admitted:
            raise ValueError("A storage blueprint requires an admitted audit storage decision.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PLANNING_AUDIT_STORAGE_BLUEPRINT_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current storage-blueprint schema.")

        if not isinstance(
            self.target,
            PlanningAuditStorageTarget,
        ):
            raise ValueError("target must be a PlanningAuditStorageTarget member.")

        if not isinstance(
            self.write_mode,
            PlanningAuditStorageWriteMode,
        ):
            raise ValueError("write_mode must be a PlanningAuditStorageWriteMode member.")

        if self.write_mode != PlanningAuditStorageWriteMode.APPEND_ONLY:
            raise ValueError("Storage blueprint must remain append-only.")

        if not isinstance(
            self.encryption_mode,
            PlanningAuditStorageEncryptionMode,
        ):
            raise ValueError("encryption_mode must be a PlanningAuditStorageEncryptionMode member.")

        if self.encryption_mode != PlanningAuditStorageEncryptionMode.ENCRYPTION_AT_REST_REQUIRED:
            raise ValueError("Storage blueprint must require encryption at rest.")

        if not isinstance(
            self.idempotency_mode,
            PlanningAuditStorageIdempotencyMode,
        ):
            raise ValueError(
                "idempotency_mode must be a PlanningAuditStorageIdempotencyMode member."
            )

        if self.idempotency_mode != PlanningAuditStorageIdempotencyMode.IDEMPOTENCY_REQUIRED:
            raise ValueError("Storage blueprint must require idempotency.")

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
        required_capacity = _positive_integer(
            self.required_capacity_bytes,
            "required_capacity_bytes",
        )
        available_capacity = _non_negative_integer(
            self.available_capacity_bytes,
            "available_capacity_bytes",
        )

        for field_name, digest in (
            ("content_digest", content_digest),
            ("manifest_digest", manifest_digest),
            ("idempotency_key", idempotency_key),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        receipt = self.storage_admission.verification.receipt_required
        envelope = receipt.envelope
        snapshot = self.storage_admission.snapshot_required
        metrics = self.storage_admission.metrics_required
        policy = self.storage_admission.policy

        if self.target != snapshot.target:
            raise ValueError("target must match the admitted storage snapshot.")

        if not snapshot.storage_enabled:
            raise ValueError("Storage blueprint requires enabled storage.")

        if not snapshot.encryption_at_rest:
            raise ValueError("Storage blueprint requires encryption at rest.")

        if not snapshot.append_only:
            raise ValueError("Storage blueprint requires append-only storage.")

        if not snapshot.idempotency_supported:
            raise ValueError("Storage blueprint requires idempotency support.")

        if content != envelope.content:
            raise ValueError("content must exactly match the verified audit-export payload.")

        if content_length != envelope.content_length_bytes:
            raise ValueError("content_length_bytes must match the verified export envelope.")

        if content_length != (receipt.verified_content_length_bytes):
            raise ValueError("content_length_bytes must match the verification receipt.")

        if content_digest != envelope.content_digest:
            raise ValueError("content_digest must match the export envelope.")

        if content_digest != (receipt.verified_content_digest):
            raise ValueError("content_digest must match the verification receipt.")

        if manifest_digest != envelope.manifest_digest:
            raise ValueError("manifest_digest must match the export envelope.")

        if manifest_digest != (receipt.verified_manifest_digest):
            raise ValueError("manifest_digest must match the verification receipt.")

        expected_idempotency_key = _idempotency_key_for(receipt)

        if idempotency_key != expected_idempotency_key:
            raise ValueError("idempotency_key does not match the verified audit lineage.")

        if retention_days != snapshot.retention_days:
            raise ValueError("retention_days must match the admitted storage snapshot.")

        if retention_days < policy.minimum_retention_days:
            raise ValueError("retention_days cannot be below the admitted policy minimum.")

        if required_capacity != (metrics.required_capacity_bytes):
            raise ValueError("required_capacity_bytes must match the storage-admission metrics.")

        if required_capacity != content_length:
            raise ValueError("required_capacity_bytes must equal the verified payload length.")

        if available_capacity != (metrics.available_capacity_bytes):
            raise ValueError("available_capacity_bytes must match the storage-admission metrics.")

        if available_capacity < required_capacity:
            raise ValueError(
                "available_capacity_bytes cannot be below the required payload capacity."
            )

        if not metrics.has_sufficient_capacity:
            raise ValueError("Storage blueprint requires sufficient capacity.")

        if not metrics.has_sufficient_retention:
            raise ValueError("Storage blueprint requires sufficient retention.")

        if not receipt.is_verified:
            raise ValueError("Storage blueprint requires a verified audit receipt.")

        if receipt.is_persisted:
            raise ValueError("Storage blueprint cannot assume prior persistence.")

        if receipt.can_write_storage:
            raise ValueError("Storage blueprint cannot inherit storage write capability.")

        if receipt.can_write_network:
            raise ValueError("Storage blueprint cannot inherit network write capability.")

        if receipt.execution_authorized:
            raise ValueError("Storage blueprint cannot contain execution authorization.")

        if receipt.has_broker_request:
            raise ValueError("Storage blueprint cannot contain a broker request.")

        if receipt.can_submit_order:
            raise ValueError("Storage blueprint cannot permit order submission.")

        if receipt.is_executable:
            raise ValueError("Storage blueprint cannot contain an executable receipt.")

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
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
            "required_capacity_bytes",
            required_capacity,
        )
        object.__setattr__(
            self,
            "available_capacity_bytes",
            available_capacity,
        )

    @property
    def receipt(
        self,
    ) -> StrategyPlanningAuditVerificationReceipt:
        return self.storage_admission.verification.receipt_required

    @property
    def snapshot(
        self,
    ) -> PlanningAuditStorageSnapshot:
        return self.storage_admission.snapshot_required

    @property
    def metrics(self) -> PlanningAuditStorageMetrics:
        return self.storage_admission.metrics_required

    @property
    def envelope(self):
        return self.receipt.envelope

    @property
    def record(self):
        return self.receipt.record

    @property
    def manifest(self):
        return self.receipt.manifest

    @property
    def package(self):
        return self.receipt.package

    @property
    def broker_symbol(self) -> str:
        return self.receipt.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.receipt.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.receipt.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.receipt.side

    @property
    def content_bytes(self) -> bytes:
        return self.content.encode("utf-8")

    @property
    def is_write_blueprint_ready(self) -> bool:
        return True

    @property
    def is_append_only(self) -> bool:
        return True

    @property
    def requires_encryption_at_rest(self) -> bool:
        return True

    @property
    def requires_idempotency(self) -> bool:
        return True

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
    def blueprint_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"AUDIT_STORAGE_BLUEPRINT:"
            f"{self.target.value}:"
            f"{self.write_mode.value}:"
            f"BYTES[{self.content_length_bytes}]:"
            f"CONTENT_SHA256[{self.content_digest}]:"
            f"IDEMPOTENCY_SHA256[{self.idempotency_key}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.storage_admission.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_BLUEPRINT:"
            f"{self.blueprint_id}"
        )


@dataclass(frozen=True, slots=True)
class _PlanningAuditStorageBlueprintEvaluation:
    status: PlanningAuditStorageBlueprintStatus
    reason: PlanningAuditStorageBlueprintReason
    blockers: tuple[
        PlanningAuditStorageBlueprintBlocker,
        ...,
    ]
    blueprint: StrategyPlanningAuditStorageBlueprint | None


def _derive_blueprint(
    storage_admission: PlanningAuditStorageAdmissionDecision,
) -> _PlanningAuditStorageBlueprintEvaluation:
    if storage_admission.is_blocked:
        return _PlanningAuditStorageBlueprintEvaluation(
            status=PlanningAuditStorageBlueprintStatus.BLOCKED,
            reason=(PlanningAuditStorageBlueprintReason.STORAGE_ADMISSION_BLOCKED),
            blockers=(PlanningAuditStorageBlueprintBlocker.STORAGE_ADMISSION_BLOCKED,),
            blueprint=None,
        )

    receipt = storage_admission.verification.receipt_required
    envelope = receipt.envelope
    snapshot = storage_admission.snapshot_required
    metrics = storage_admission.metrics_required

    blueprint = StrategyPlanningAuditStorageBlueprint(
        storage_admission=storage_admission,
        schema_version=(PLANNING_AUDIT_STORAGE_BLUEPRINT_SCHEMA_VERSION),
        target=snapshot.target,
        write_mode=(PlanningAuditStorageWriteMode.APPEND_ONLY),
        encryption_mode=(PlanningAuditStorageEncryptionMode.ENCRYPTION_AT_REST_REQUIRED),
        idempotency_mode=(PlanningAuditStorageIdempotencyMode.IDEMPOTENCY_REQUIRED),
        content=envelope.content,
        content_length_bytes=(envelope.content_length_bytes),
        content_digest=envelope.content_digest,
        manifest_digest=envelope.manifest_digest,
        idempotency_key=_idempotency_key_for(receipt),
        retention_days=snapshot.retention_days,
        required_capacity_bytes=(metrics.required_capacity_bytes),
        available_capacity_bytes=(metrics.available_capacity_bytes),
    )

    return _PlanningAuditStorageBlueprintEvaluation(
        status=PlanningAuditStorageBlueprintStatus.CREATED,
        reason=PlanningAuditStorageBlueprintReason.CREATED,
        blockers=(),
        blueprint=blueprint,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageBlueprintDecision:
    """Validated analytical storage-blueprint result."""

    storage_admission: PlanningAuditStorageAdmissionDecision
    status: PlanningAuditStorageBlueprintStatus
    reason: PlanningAuditStorageBlueprintReason
    blockers: tuple[
        PlanningAuditStorageBlueprintBlocker,
        ...,
    ]
    blueprint: StrategyPlanningAuditStorageBlueprint | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.storage_admission,
            PlanningAuditStorageAdmissionDecision,
        ):
            raise ValueError("storage_admission must be a PlanningAuditStorageAdmissionDecision.")

        try:
            status = PlanningAuditStorageBlueprintStatus(self.status)
            reason = PlanningAuditStorageBlueprintReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported storage-blueprint status or reason.") from error

        blockers = tuple(PlanningAuditStorageBlueprintBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Storage-blueprint blockers cannot contain duplicates.")

        if self.blueprint is not None and not isinstance(
            self.blueprint,
            StrategyPlanningAuditStorageBlueprint,
        ):
            raise ValueError("blueprint must be a StrategyPlanningAuditStorageBlueprint or None.")

        expected = _derive_blueprint(self.storage_admission)
        supplied = _PlanningAuditStorageBlueprintEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            blueprint=self.blueprint,
        )

        if supplied != expected:
            raise ValueError(
                "Storage-blueprint result does not match its storage-admission decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.storage_admission.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.storage_admission.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.storage_admission.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditStorageBlueprintStatus.CREATED

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
    ) -> StrategyPlanningAuditStorageBlueprint:
        if self.blueprint is None:
            raise ValueError("No planning-audit storage blueprint was created.")

        return self.blueprint

    @property
    def can_continue_to_storage_adapter_design(self) -> bool:
        return self.is_created

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
            f"{self.storage_admission.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_BLUEPRINT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditStorageBlueprintFactory:
    """
    Pure factory for analytical storage-write blueprints.

    CREATED permits later adapter-design analysis only.
    It performs and authorizes no storage, network, broker,
    or execution operation.
    """

    def generate(
        self,
        storage_admission: (PlanningAuditStorageAdmissionDecision),
    ) -> PlanningAuditStorageBlueprintDecision:
        if not isinstance(
            storage_admission,
            PlanningAuditStorageAdmissionDecision,
        ):
            raise PlanningAuditStorageBlueprintError(
                PlanningAuditStorageBlueprintErrorReason.INVALID_STORAGE_ADMISSION_DECISION,
                "storage_admission must be a PlanningAuditStorageAdmissionDecision.",
            )

        evaluation = _derive_blueprint(storage_admission)

        return PlanningAuditStorageBlueprintDecision(
            storage_admission=storage_admission,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            blueprint=evaluation.blueprint,
        )

    def build(
        self,
        storage_admission: (PlanningAuditStorageAdmissionDecision),
    ) -> PlanningAuditStorageBlueprintDecision:
        """Compatibility alias for generate()."""

        return self.generate(storage_admission)

    def evaluate(
        self,
        storage_admission: (PlanningAuditStorageAdmissionDecision),
    ) -> PlanningAuditStorageBlueprintDecision:
        """Compatibility alias for generate()."""

        return self.generate(storage_admission)


def generate_planning_audit_storage_blueprint(
    storage_admission: PlanningAuditStorageAdmissionDecision,
) -> PlanningAuditStorageBlueprintDecision:
    return StrategyPlanningAuditStorageBlueprintFactory().generate(storage_admission)


AuditStorageBlueprint = StrategyPlanningAuditStorageBlueprint
AuditStorageBlueprintDecision = PlanningAuditStorageBlueprintDecision
AuditStorageBlueprintFactory = StrategyPlanningAuditStorageBlueprintFactory
AuditStorageEncryptionMode = PlanningAuditStorageEncryptionMode
AuditStorageIdempotencyMode = PlanningAuditStorageIdempotencyMode
AuditStorageWriteMode = PlanningAuditStorageWriteMode
PlanningAuditStorageBlueprint = StrategyPlanningAuditStorageBlueprint
PlanningAuditStorageBlueprintFactory = StrategyPlanningAuditStorageBlueprintFactory
StrategyAuditStorageBlueprint = StrategyPlanningAuditStorageBlueprint
StrategyAuditStorageBlueprintFactory = StrategyPlanningAuditStorageBlueprintFactory
