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
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageTarget,
)
from app.strategy.planning_audit_storage_blueprint import (
    PlanningAuditStorageBlueprintDecision,
    PlanningAuditStorageEncryptionMode,
    PlanningAuditStorageIdempotencyMode,
    PlanningAuditStorageWriteMode,
    StrategyPlanningAuditStorageBlueprint,
)

PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT_SCHEMA_VERSION = "1.0"


class PlanningAuditStorageAdapterOperation(str, Enum):
    APPEND_IF_ABSENT = "APPEND_IF_ABSENT"


class PlanningAuditStorageDuplicatePolicy(str, Enum):
    RETURN_EXISTING = "RETURN_EXISTING"


class PlanningAuditStorageIntegrityPolicy(str, Enum):
    VERIFY_BEFORE_ACCEPT = "VERIFY_BEFORE_ACCEPT"


class PlanningAuditStorageResultExpectation(str, Enum):
    CREATED_OR_EXISTING = "CREATED_OR_EXISTING"


class PlanningAuditStorageAdapterContractStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditStorageAdapterContractReason(str, Enum):
    CREATED = "CREATED"
    STORAGE_BLUEPRINT_BLOCKED = "STORAGE_BLUEPRINT_BLOCKED"


class PlanningAuditStorageAdapterContractBlocker(str, Enum):
    STORAGE_BLUEPRINT_BLOCKED = "STORAGE_BLUEPRINT_BLOCKED"


class PlanningAuditStorageAdapterContractErrorReason(
    str,
    Enum,
):
    INVALID_STORAGE_BLUEPRINT_DECISION = "INVALID_STORAGE_BLUEPRINT_DECISION"


class PlanningAuditStorageAdapterContractError(RuntimeError):
    """Structured analytical adapter-contract failure."""

    def __init__(
        self,
        reason: (PlanningAuditStorageAdapterContractErrorReason),
        message: str,
    ) -> None:
        self.reason = PlanningAuditStorageAdapterContractErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Planning-audit storage adapter-contract error [{self.reason.value}]: {self.message}"
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


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditStorageAdapterContract:
    """
    Immutable implementation-neutral persistence contract.

    It defines what a future adapter must preserve but does
    not provide an adapter, path, connection, transaction,
    command, invocation, authorization, or write operation.
    """

    storage_blueprint: PlanningAuditStorageBlueprintDecision
    schema_version: str
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

    def __post_init__(self) -> None:
        if not isinstance(
            self.storage_blueprint,
            PlanningAuditStorageBlueprintDecision,
        ):
            raise ValueError("storage_blueprint must be a PlanningAuditStorageBlueprintDecision.")

        if not self.storage_blueprint.is_created:
            raise ValueError("An adapter contract requires a created audit storage blueprint.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current storage adapter-contract schema."
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
            raise ValueError("Storage adapter operation must be APPEND_IF_ABSENT.")

        if not isinstance(
            self.duplicate_policy,
            PlanningAuditStorageDuplicatePolicy,
        ):
            raise ValueError(
                "duplicate_policy must be a PlanningAuditStorageDuplicatePolicy member."
            )

        if self.duplicate_policy != PlanningAuditStorageDuplicatePolicy.RETURN_EXISTING:
            raise ValueError("Duplicate policy must return the existing idempotent record.")

        if not isinstance(
            self.integrity_policy,
            PlanningAuditStorageIntegrityPolicy,
        ):
            raise ValueError(
                "integrity_policy must be a PlanningAuditStorageIntegrityPolicy member."
            )

        if self.integrity_policy != PlanningAuditStorageIntegrityPolicy.VERIFY_BEFORE_ACCEPT:
            raise ValueError("Integrity policy must verify content before acceptance.")

        if not isinstance(
            self.result_expectation,
            PlanningAuditStorageResultExpectation,
        ):
            raise ValueError(
                "result_expectation must be a PlanningAuditStorageResultExpectation member."
            )

        if self.result_expectation != PlanningAuditStorageResultExpectation.CREATED_OR_EXISTING:
            raise ValueError("Result expectation must be CREATED_OR_EXISTING.")

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

        for field_name, value in (
            ("content_digest", content_digest),
            ("manifest_digest", manifest_digest),
            ("idempotency_key", idempotency_key),
        ):
            if not _is_lowercase_sha256(value):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        blueprint = self.storage_blueprint.blueprint_required

        if self.target != blueprint.target:
            raise ValueError("target must match the storage blueprint.")

        if blueprint.write_mode != PlanningAuditStorageWriteMode.APPEND_ONLY:
            raise ValueError("Adapter contract requires an append-only storage blueprint.")

        if (
            blueprint.encryption_mode
            != PlanningAuditStorageEncryptionMode.ENCRYPTION_AT_REST_REQUIRED
        ):
            raise ValueError("Adapter contract requires encryption at rest.")

        if blueprint.idempotency_mode != PlanningAuditStorageIdempotencyMode.IDEMPOTENCY_REQUIRED:
            raise ValueError("Adapter contract requires idempotency.")

        if content != blueprint.content:
            raise ValueError("content must exactly match the storage blueprint.")

        if content_length != blueprint.content_length_bytes:
            raise ValueError("content_length_bytes must match the storage blueprint.")

        if len(content.encode("utf-8")) != content_length:
            raise ValueError("content_length_bytes must match the UTF-8 payload size.")

        if content_digest != blueprint.content_digest:
            raise ValueError("content_digest must match the storage blueprint.")

        if manifest_digest != blueprint.manifest_digest:
            raise ValueError("manifest_digest must match the storage blueprint.")

        if idempotency_key != blueprint.idempotency_key:
            raise ValueError("idempotency_key must match the storage blueprint.")

        if retention_days != blueprint.retention_days:
            raise ValueError("retention_days must match the storage blueprint.")

        if not blueprint.is_write_blueprint_ready:
            raise ValueError("Adapter contract requires a ready storage blueprint.")

        if not blueprint.is_append_only:
            raise ValueError("Adapter contract requires append-only storage.")

        if not blueprint.requires_encryption_at_rest:
            raise ValueError("Adapter contract requires encryption at rest.")

        if not blueprint.requires_idempotency:
            raise ValueError("Adapter contract requires idempotency.")

        if blueprint.storage_write_authorized:
            raise ValueError("Adapter contract cannot inherit storage write authorization.")

        if blueprint.is_persisted:
            raise ValueError("Adapter contract cannot assume prior persistence.")

        if blueprint.can_write_storage:
            raise ValueError("Adapter contract cannot inherit storage write capability.")

        if blueprint.can_write_network:
            raise ValueError("Adapter contract cannot inherit network write capability.")

        if blueprint.execution_authorized:
            raise ValueError("Adapter contract cannot contain execution authorization.")

        if blueprint.has_broker_request:
            raise ValueError("Adapter contract cannot contain a broker request.")

        if blueprint.can_submit_order:
            raise ValueError("Adapter contract cannot permit order submission.")

        if blueprint.is_executable:
            raise ValueError("Adapter contract cannot contain an executable blueprint.")

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

    @property
    def blueprint(
        self,
    ) -> StrategyPlanningAuditStorageBlueprint:
        return self.storage_blueprint.blueprint_required

    @property
    def broker_symbol(self) -> str:
        return self.blueprint.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.blueprint.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.blueprint.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.blueprint.side

    @property
    def content_bytes(self) -> bytes:
        return self.content.encode("utf-8")

    @property
    def requires_append_only(self) -> bool:
        return True

    @property
    def requires_encryption_at_rest(self) -> bool:
        return True

    @property
    def requires_idempotency(self) -> bool:
        return True

    @property
    def requires_integrity_verification(self) -> bool:
        return True

    @property
    def is_adapter_contract_ready(self) -> bool:
        return True

    @property
    def can_continue_to_adapter_implementation(self) -> bool:
        return True

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
    def contract_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"AUDIT_STORAGE_ADAPTER_CONTRACT:"
            f"{self.target.value}:"
            f"{self.operation.value}:"
            f"{self.duplicate_policy.value}:"
            f"{self.integrity_policy.value}:"
            f"IDEMPOTENCY_SHA256["
            f"{self.idempotency_key}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.storage_blueprint.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT:"
            f"{self.contract_id}"
        )


@dataclass(frozen=True, slots=True)
class _StorageAdapterContractEvaluation:
    status: PlanningAuditStorageAdapterContractStatus
    reason: PlanningAuditStorageAdapterContractReason
    blockers: tuple[
        PlanningAuditStorageAdapterContractBlocker,
        ...,
    ]
    contract: StrategyPlanningAuditStorageAdapterContract | None


def _derive_contract(
    storage_blueprint: (PlanningAuditStorageBlueprintDecision),
) -> _StorageAdapterContractEvaluation:
    if storage_blueprint.is_blocked:
        return _StorageAdapterContractEvaluation(
            status=(PlanningAuditStorageAdapterContractStatus.BLOCKED),
            reason=(PlanningAuditStorageAdapterContractReason.STORAGE_BLUEPRINT_BLOCKED),
            blockers=(PlanningAuditStorageAdapterContractBlocker.STORAGE_BLUEPRINT_BLOCKED,),
            contract=None,
        )

    blueprint = storage_blueprint.blueprint_required

    contract = StrategyPlanningAuditStorageAdapterContract(
        storage_blueprint=storage_blueprint,
        schema_version=(PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT_SCHEMA_VERSION),
        target=blueprint.target,
        operation=(PlanningAuditStorageAdapterOperation.APPEND_IF_ABSENT),
        duplicate_policy=(PlanningAuditStorageDuplicatePolicy.RETURN_EXISTING),
        integrity_policy=(PlanningAuditStorageIntegrityPolicy.VERIFY_BEFORE_ACCEPT),
        result_expectation=(PlanningAuditStorageResultExpectation.CREATED_OR_EXISTING),
        content=blueprint.content,
        content_length_bytes=(blueprint.content_length_bytes),
        content_digest=blueprint.content_digest,
        manifest_digest=blueprint.manifest_digest,
        idempotency_key=blueprint.idempotency_key,
        retention_days=blueprint.retention_days,
    )

    return _StorageAdapterContractEvaluation(
        status=(PlanningAuditStorageAdapterContractStatus.CREATED),
        reason=(PlanningAuditStorageAdapterContractReason.CREATED),
        blockers=(),
        contract=contract,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageAdapterContractDecision:
    """Validated analytical adapter-contract result."""

    storage_blueprint: PlanningAuditStorageBlueprintDecision
    status: PlanningAuditStorageAdapterContractStatus
    reason: PlanningAuditStorageAdapterContractReason
    blockers: tuple[
        PlanningAuditStorageAdapterContractBlocker,
        ...,
    ]
    contract: StrategyPlanningAuditStorageAdapterContract | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.storage_blueprint,
            PlanningAuditStorageBlueprintDecision,
        ):
            raise ValueError("storage_blueprint must be a PlanningAuditStorageBlueprintDecision.")

        try:
            status = PlanningAuditStorageAdapterContractStatus(self.status)
            reason = PlanningAuditStorageAdapterContractReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported storage adapter-contract status or reason.") from error

        blockers = tuple(
            PlanningAuditStorageAdapterContractBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Adapter-contract blockers cannot contain duplicates.")

        if self.contract is not None and not isinstance(
            self.contract,
            StrategyPlanningAuditStorageAdapterContract,
        ):
            raise ValueError(
                "contract must be a StrategyPlanningAuditStorageAdapterContract or None."
            )

        expected = _derive_contract(self.storage_blueprint)
        supplied = _StorageAdapterContractEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            contract=self.contract,
        )

        if supplied != expected:
            raise ValueError(
                "Storage adapter-contract result does not match its storage-blueprint decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.storage_blueprint.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.storage_blueprint.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.storage_blueprint.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditStorageAdapterContractStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_contract(self) -> bool:
        return self.contract is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def contract_required(
        self,
    ) -> StrategyPlanningAuditStorageAdapterContract:
        if self.contract is None:
            raise ValueError("No planning-audit storage adapter contract was created.")

        return self.contract

    @property
    def can_continue_to_adapter_implementation(self) -> bool:
        return self.is_created

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
            f"{self.storage_blueprint.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_ADAPTER_CONTRACT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditStorageAdapterContractFactory:
    """
    Pure factory for implementation-neutral adapter contracts.

    CREATED permits later adapter implementation design only.
    It performs and authorizes no persistence, network,
    broker, MT5, or execution operation.
    """

    def generate(
        self,
        storage_blueprint: (PlanningAuditStorageBlueprintDecision),
    ) -> PlanningAuditStorageAdapterContractDecision:
        if not isinstance(
            storage_blueprint,
            PlanningAuditStorageBlueprintDecision,
        ):
            raise PlanningAuditStorageAdapterContractError(
                PlanningAuditStorageAdapterContractErrorReason.INVALID_STORAGE_BLUEPRINT_DECISION,
                "storage_blueprint must be a PlanningAuditStorageBlueprintDecision.",
            )

        evaluation = _derive_contract(storage_blueprint)

        return PlanningAuditStorageAdapterContractDecision(
            storage_blueprint=storage_blueprint,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            contract=evaluation.contract,
        )

    def build(
        self,
        storage_blueprint: (PlanningAuditStorageBlueprintDecision),
    ) -> PlanningAuditStorageAdapterContractDecision:
        """Compatibility alias for generate()."""

        return self.generate(storage_blueprint)

    def evaluate(
        self,
        storage_blueprint: (PlanningAuditStorageBlueprintDecision),
    ) -> PlanningAuditStorageAdapterContractDecision:
        """Compatibility alias for generate()."""

        return self.generate(storage_blueprint)


def generate_planning_audit_storage_adapter_contract(
    storage_blueprint: PlanningAuditStorageBlueprintDecision,
) -> PlanningAuditStorageAdapterContractDecision:
    return StrategyPlanningAuditStorageAdapterContractFactory().generate(storage_blueprint)


AuditStorageAdapterContract = StrategyPlanningAuditStorageAdapterContract
AuditStorageAdapterContractDecision = PlanningAuditStorageAdapterContractDecision
AuditStorageAdapterContractFactory = StrategyPlanningAuditStorageAdapterContractFactory
AuditStorageAdapterOperation = PlanningAuditStorageAdapterOperation
AuditStorageDuplicatePolicy = PlanningAuditStorageDuplicatePolicy
AuditStorageIntegrityPolicy = PlanningAuditStorageIntegrityPolicy
AuditStorageResultExpectation = PlanningAuditStorageResultExpectation
PlanningAuditStorageAdapterContract = StrategyPlanningAuditStorageAdapterContract
PlanningAuditStorageAdapterContractFactory = StrategyPlanningAuditStorageAdapterContractFactory
StrategyAuditStorageAdapterContract = StrategyPlanningAuditStorageAdapterContract
StrategyAuditStorageAdapterContractFactory = StrategyPlanningAuditStorageAdapterContractFactory
