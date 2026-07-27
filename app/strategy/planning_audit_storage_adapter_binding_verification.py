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
from app.strategy.planning_audit_storage_adapter_assessment import (
    PlanningAuditStorageAdapterCapabilitySnapshot,
)
from app.strategy.planning_audit_storage_adapter_binding import (
    PlanningAuditStorageAdapterBindingDecision,
    PlanningAuditStorageAdapterBindingMode,
    PlanningAuditStorageAdapterBindingVerificationMode,
    PlanningAuditStorageAdapterInvocationMode,
    StrategyPlanningAuditStorageAdapterBinding,
)
from app.strategy.planning_audit_storage_adapter_contract import (
    StrategyPlanningAuditStorageAdapterContract,
)

PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_VERIFICATION_SCHEMA_VERSION = "1.0"


class PlanningAuditStorageAdapterBindingVerificationCheck(
    str,
    Enum,
):
    REFERENCE_ONLY_MODE = "REFERENCE_ONLY_MODE"
    INVOCATION_DISABLED = "INVOCATION_DISABLED"
    SNAPSHOT_ID_MATCH = "SNAPSHOT_ID_MATCH"
    CONTRACT_ID_MATCH = "CONTRACT_ID_MATCH"
    CONTRACT_SEMANTICS_MATCH = "CONTRACT_SEMANTICS_MATCH"
    DIGEST_LINEAGE_MATCH = "DIGEST_LINEAGE_MATCH"
    IDEMPOTENCY_KEY_MATCH = "IDEMPOTENCY_KEY_MATCH"
    NO_IMPLEMENTATION_SURFACE = "NO_IMPLEMENTATION_SURFACE"


_REQUIRED_CHECKS = (
    PlanningAuditStorageAdapterBindingVerificationCheck.REFERENCE_ONLY_MODE,
    PlanningAuditStorageAdapterBindingVerificationCheck.INVOCATION_DISABLED,
    PlanningAuditStorageAdapterBindingVerificationCheck.SNAPSHOT_ID_MATCH,
    PlanningAuditStorageAdapterBindingVerificationCheck.CONTRACT_ID_MATCH,
    PlanningAuditStorageAdapterBindingVerificationCheck.CONTRACT_SEMANTICS_MATCH,
    PlanningAuditStorageAdapterBindingVerificationCheck.DIGEST_LINEAGE_MATCH,
    PlanningAuditStorageAdapterBindingVerificationCheck.IDEMPOTENCY_KEY_MATCH,
    PlanningAuditStorageAdapterBindingVerificationCheck.NO_IMPLEMENTATION_SURFACE,
)


class PlanningAuditStorageAdapterBindingVerificationStatus(
    str,
    Enum,
):
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"


class PlanningAuditStorageAdapterBindingVerificationReason(
    str,
    Enum,
):
    VERIFIED = "VERIFIED"
    ADAPTER_BINDING_BLOCKED = "ADAPTER_BINDING_BLOCKED"


class PlanningAuditStorageAdapterBindingVerificationBlocker(
    str,
    Enum,
):
    ADAPTER_BINDING_BLOCKED = "ADAPTER_BINDING_BLOCKED"


class PlanningAuditStorageAdapterBindingVerificationErrorReason(
    str,
    Enum,
):
    INVALID_ADAPTER_BINDING_DECISION = "INVALID_ADAPTER_BINDING_DECISION"


class PlanningAuditStorageAdapterBindingVerificationError(RuntimeError):
    """Structured adapter-binding verification failure."""

    def __init__(
        self,
        reason: (PlanningAuditStorageAdapterBindingVerificationErrorReason),
        message: str,
    ) -> None:
        self.reason = PlanningAuditStorageAdapterBindingVerificationErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Planning-audit adapter-binding verification "
            f"error [{self.reason.value}]: {self.message}"
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


def _sha256_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _canonical_receipt_payload(
    *,
    schema_version: str,
    checks: tuple[
        PlanningAuditStorageAdapterBindingVerificationCheck,
        ...,
    ],
    binding_stable_id: str,
    verified_binding_id: str,
    verified_snapshot_id: str,
    verified_contract_id: str,
    verified_content_digest: str,
    verified_manifest_digest: str,
    verified_idempotency_key: str,
) -> str:
    check_fragment = ",".join(check.value for check in checks)

    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"CHECKS={check_fragment}",
            f"BINDING_STABLE_ID={binding_stable_id}",
            f"BINDING_ID={verified_binding_id}",
            f"SNAPSHOT_ID={verified_snapshot_id}",
            f"CONTRACT_ID={verified_contract_id}",
            (f"CONTENT_DIGEST={verified_content_digest}"),
            (f"MANIFEST_DIGEST={verified_manifest_digest}"),
            (f"IDEMPOTENCY_KEY={verified_idempotency_key}"),
        )
    )


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditStorageAdapterBindingVerificationReceipt:
    """
    Immutable independent verification of an adapter binding.

    The receipt validates binding, snapshot, contract, digest,
    idempotency, and no-invocation lineage. It performs no
    adapter import, instance creation, invocation, storage,
    network, broker, MT5, or execution operation.
    """

    adapter_binding: PlanningAuditStorageAdapterBindingDecision
    schema_version: str
    checks: tuple[
        PlanningAuditStorageAdapterBindingVerificationCheck,
        ...,
    ]
    verified_binding_id: str
    verified_snapshot_id: str
    verified_contract_id: str
    verified_content_digest: str
    verified_manifest_digest: str
    verified_idempotency_key: str
    receipt_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.adapter_binding,
            PlanningAuditStorageAdapterBindingDecision,
        ):
            raise ValueError(
                "adapter_binding must be a PlanningAuditStorageAdapterBindingDecision."
            )

        if not self.adapter_binding.is_created:
            raise ValueError(
                "A binding verification receipt requires a created audit storage adapter binding."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_VERIFICATION_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current adapter-binding verification schema."
            )

        if not isinstance(self.checks, tuple):
            raise ValueError("checks must be a tuple.")

        if not all(
            isinstance(
                check,
                PlanningAuditStorageAdapterBindingVerificationCheck,
            )
            for check in self.checks
        ):
            raise ValueError("checks must contain adapter-binding verification check members.")

        if len(set(self.checks)) != len(self.checks):
            raise ValueError("Binding-verification checks cannot contain duplicates.")

        if self.checks != _REQUIRED_CHECKS:
            raise ValueError(
                "Binding-verification checks must contain "
                "every required check in deterministic "
                "order."
            )

        verified_binding_id = _non_empty_string(
            self.verified_binding_id,
            "verified_binding_id",
        )
        verified_snapshot_id = _non_empty_string(
            self.verified_snapshot_id,
            "verified_snapshot_id",
        )
        verified_contract_id = _non_empty_string(
            self.verified_contract_id,
            "verified_contract_id",
        )
        verified_content_digest = _non_empty_string(
            self.verified_content_digest,
            "verified_content_digest",
        )
        verified_manifest_digest = _non_empty_string(
            self.verified_manifest_digest,
            "verified_manifest_digest",
        )
        verified_idempotency_key = _non_empty_string(
            self.verified_idempotency_key,
            "verified_idempotency_key",
        )
        receipt_digest = _non_empty_string(
            self.receipt_digest,
            "receipt_digest",
        )

        for field_name, value in (
            (
                "verified_content_digest",
                verified_content_digest,
            ),
            (
                "verified_manifest_digest",
                verified_manifest_digest,
            ),
            (
                "verified_idempotency_key",
                verified_idempotency_key,
            ),
            (
                "receipt_digest",
                receipt_digest,
            ),
        ):
            if not _is_lowercase_sha256(value):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        binding = self.adapter_binding.binding_required
        snapshot = binding.snapshot
        contract = binding.contract

        if binding.binding_mode != PlanningAuditStorageAdapterBindingMode.REFERENCE_ONLY:
            raise ValueError("Verified binding must remain REFERENCE_ONLY.")

        if not binding.is_reference_only:
            raise ValueError("Verified binding must expose the reference-only invariant.")

        if binding.invocation_mode != PlanningAuditStorageAdapterInvocationMode.DISABLED:
            raise ValueError("Verified binding invocation mode must remain DISABLED.")

        if (
            binding.verification_mode
            != PlanningAuditStorageAdapterBindingVerificationMode.SNAPSHOT_AND_CONTRACT_LOCKED
        ):
            raise ValueError("Verified binding must lock its snapshot and adapter contract.")

        if verified_binding_id != binding.binding_id:
            raise ValueError("verified_binding_id must match the adapter binding.")

        if verified_snapshot_id != binding.capability_snapshot_id:
            raise ValueError("verified_snapshot_id must match the binding snapshot identity.")

        if verified_snapshot_id != snapshot.stable_id:
            raise ValueError("verified_snapshot_id must match the capability snapshot.")

        if verified_contract_id != binding.contract_id:
            raise ValueError("verified_contract_id must match the binding contract identity.")

        if verified_contract_id != contract.contract_id:
            raise ValueError("verified_contract_id must match the adapter contract.")

        if binding.operation != contract.operation:
            raise ValueError("Binding operation does not match the adapter contract.")

        if binding.duplicate_policy != contract.duplicate_policy:
            raise ValueError("Binding duplicate policy does not match the adapter contract.")

        if binding.integrity_policy != contract.integrity_policy:
            raise ValueError("Binding integrity policy does not match the adapter contract.")

        if binding.result_expectation != contract.result_expectation:
            raise ValueError("Binding result expectation does not match the adapter contract.")

        if verified_content_digest != binding.content_digest:
            raise ValueError("verified_content_digest must match the adapter binding.")

        if verified_content_digest != contract.content_digest:
            raise ValueError("verified_content_digest must match the adapter contract.")

        if verified_manifest_digest != binding.manifest_digest:
            raise ValueError("verified_manifest_digest must match the adapter binding.")

        if verified_manifest_digest != contract.manifest_digest:
            raise ValueError("verified_manifest_digest must match the adapter contract.")

        if verified_idempotency_key != binding.idempotency_key:
            raise ValueError("verified_idempotency_key must match the adapter binding.")

        if verified_idempotency_key != contract.idempotency_key:
            raise ValueError("verified_idempotency_key must match the adapter contract.")

        if not snapshot.active:
            raise ValueError("Binding verification requires an active capability snapshot.")

        if snapshot.invocation_enabled:
            raise ValueError("Binding verification requires adapter invocation to remain disabled.")

        if not snapshot.is_read_only_snapshot:
            raise ValueError("Binding verification requires a read-only capability snapshot.")

        if snapshot.can_invoke_adapter:
            raise ValueError("Capability snapshot cannot invoke the adapter.")

        if snapshot.can_write_storage:
            raise ValueError("Capability snapshot cannot write storage.")

        if binding.has_adapter_instance:
            raise ValueError("Verified binding cannot contain an adapter instance.")

        if binding.adapter_binding_authorized:
            raise ValueError("Verified binding cannot authorize adapter binding.")

        if binding.adapter_invocation_authorized:
            raise ValueError("Verified binding cannot authorize adapter invocation.")

        if binding.storage_write_authorized:
            raise ValueError("Verified binding cannot authorize storage writes.")

        if binding.is_persisted:
            raise ValueError("Verified binding cannot assume prior persistence.")

        if binding.can_write_storage:
            raise ValueError("Verified binding cannot write storage.")

        if binding.can_write_network:
            raise ValueError("Verified binding cannot write to the network.")

        if binding.execution_authorized:
            raise ValueError("Verified binding cannot contain trading execution authorization.")

        if binding.has_broker_request:
            raise ValueError("Verified binding cannot contain a broker request.")

        if binding.can_submit_order:
            raise ValueError("Verified binding cannot submit an order.")

        if binding.is_executable:
            raise ValueError("Verified binding cannot be executable.")

        canonical_payload = _canonical_receipt_payload(
            schema_version=schema_version,
            checks=self.checks,
            binding_stable_id=binding.stable_id,
            verified_binding_id=verified_binding_id,
            verified_snapshot_id=verified_snapshot_id,
            verified_contract_id=verified_contract_id,
            verified_content_digest=(verified_content_digest),
            verified_manifest_digest=(verified_manifest_digest),
            verified_idempotency_key=(verified_idempotency_key),
        )
        expected_receipt_digest = _sha256_digest(canonical_payload)

        if receipt_digest != expected_receipt_digest:
            raise ValueError(
                "receipt_digest does not match the canonical binding-verification payload."
            )

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "verified_binding_id",
            verified_binding_id,
        )
        object.__setattr__(
            self,
            "verified_snapshot_id",
            verified_snapshot_id,
        )
        object.__setattr__(
            self,
            "verified_contract_id",
            verified_contract_id,
        )
        object.__setattr__(
            self,
            "verified_content_digest",
            verified_content_digest,
        )
        object.__setattr__(
            self,
            "verified_manifest_digest",
            verified_manifest_digest,
        )
        object.__setattr__(
            self,
            "verified_idempotency_key",
            verified_idempotency_key,
        )
        object.__setattr__(
            self,
            "receipt_digest",
            receipt_digest,
        )

    @property
    def binding(
        self,
    ) -> StrategyPlanningAuditStorageAdapterBinding:
        return self.adapter_binding.binding_required

    @property
    def snapshot(
        self,
    ) -> PlanningAuditStorageAdapterCapabilitySnapshot:
        return self.binding.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPlanningAuditStorageAdapterContract:
        return self.binding.contract

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
    def verification_count(self) -> int:
        return len(self.checks)

    @property
    def canonical_payload(self) -> str:
        return _canonical_receipt_payload(
            schema_version=self.schema_version,
            checks=self.checks,
            binding_stable_id=self.binding.stable_id,
            verified_binding_id=self.verified_binding_id,
            verified_snapshot_id=self.verified_snapshot_id,
            verified_contract_id=self.verified_contract_id,
            verified_content_digest=(self.verified_content_digest),
            verified_manifest_digest=(self.verified_manifest_digest),
            verified_idempotency_key=(self.verified_idempotency_key),
        )

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def is_verified(self) -> bool:
        return True

    @property
    def is_tamper_evident(self) -> bool:
        return True

    @property
    def can_continue_to_persistence_request_design(
        self,
    ) -> bool:
        return True

    @property
    def has_adapter_instance(self) -> bool:
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
    def receipt_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"AUDIT_ADAPTER_BINDING_VERIFIED:"
            f"BINDING[{self.verified_binding_id}]:"
            f"RECEIPT_SHA256[{self.receipt_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.adapter_binding.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_"
            f"VERIFICATION_RECEIPT:"
            f"{self.receipt_id}"
        )


@dataclass(frozen=True, slots=True)
class _AdapterBindingVerificationEvaluation:
    status: PlanningAuditStorageAdapterBindingVerificationStatus
    reason: PlanningAuditStorageAdapterBindingVerificationReason
    blockers: tuple[
        PlanningAuditStorageAdapterBindingVerificationBlocker,
        ...,
    ]
    receipt: StrategyPlanningAuditStorageAdapterBindingVerificationReceipt | None


def _derive_verification(
    adapter_binding: (PlanningAuditStorageAdapterBindingDecision),
) -> _AdapterBindingVerificationEvaluation:
    if adapter_binding.is_blocked:
        return _AdapterBindingVerificationEvaluation(
            status=(PlanningAuditStorageAdapterBindingVerificationStatus.BLOCKED),
            reason=(PlanningAuditStorageAdapterBindingVerificationReason.ADAPTER_BINDING_BLOCKED),
            blockers=(
                PlanningAuditStorageAdapterBindingVerificationBlocker.ADAPTER_BINDING_BLOCKED,
            ),
            receipt=None,
        )

    binding = adapter_binding.binding_required
    canonical_payload = _canonical_receipt_payload(
        schema_version=(PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_VERIFICATION_SCHEMA_VERSION),
        checks=_REQUIRED_CHECKS,
        binding_stable_id=binding.stable_id,
        verified_binding_id=binding.binding_id,
        verified_snapshot_id=(binding.capability_snapshot_id),
        verified_contract_id=binding.contract_id,
        verified_content_digest=binding.content_digest,
        verified_manifest_digest=binding.manifest_digest,
        verified_idempotency_key=binding.idempotency_key,
    )

    receipt = StrategyPlanningAuditStorageAdapterBindingVerificationReceipt(
        adapter_binding=adapter_binding,
        schema_version=(PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_VERIFICATION_SCHEMA_VERSION),
        checks=_REQUIRED_CHECKS,
        verified_binding_id=binding.binding_id,
        verified_snapshot_id=(binding.capability_snapshot_id),
        verified_contract_id=binding.contract_id,
        verified_content_digest=binding.content_digest,
        verified_manifest_digest=(binding.manifest_digest),
        verified_idempotency_key=(binding.idempotency_key),
        receipt_digest=_sha256_digest(canonical_payload),
    )

    return _AdapterBindingVerificationEvaluation(
        status=(PlanningAuditStorageAdapterBindingVerificationStatus.VERIFIED),
        reason=(PlanningAuditStorageAdapterBindingVerificationReason.VERIFIED),
        blockers=(),
        receipt=receipt,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditStorageAdapterBindingVerificationDecision:
    """Validated adapter-binding verification result."""

    adapter_binding: PlanningAuditStorageAdapterBindingDecision
    status: PlanningAuditStorageAdapterBindingVerificationStatus
    reason: PlanningAuditStorageAdapterBindingVerificationReason
    blockers: tuple[
        PlanningAuditStorageAdapterBindingVerificationBlocker,
        ...,
    ]
    receipt: StrategyPlanningAuditStorageAdapterBindingVerificationReceipt | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.adapter_binding,
            PlanningAuditStorageAdapterBindingDecision,
        ):
            raise ValueError(
                "adapter_binding must be a PlanningAuditStorageAdapterBindingDecision."
            )

        try:
            status = PlanningAuditStorageAdapterBindingVerificationStatus(self.status)
            reason = PlanningAuditStorageAdapterBindingVerificationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Unsupported adapter-binding verification status or reason."
            ) from error

        blockers = tuple(
            PlanningAuditStorageAdapterBindingVerificationBlocker(blocker)
            for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Binding-verification blockers cannot contain duplicates.")

        if self.receipt is not None and not isinstance(
            self.receipt,
            StrategyPlanningAuditStorageAdapterBindingVerificationReceipt,
        ):
            raise ValueError("receipt must be a binding-verification receipt or None.")

        expected = _derive_verification(self.adapter_binding)
        supplied = _AdapterBindingVerificationEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            receipt=self.receipt,
        )

        if supplied != expected:
            raise ValueError(
                "Adapter-binding verification result does not match its binding decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.adapter_binding.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.adapter_binding.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.adapter_binding.direction

    @property
    def is_verified(self) -> bool:
        return self.status == PlanningAuditStorageAdapterBindingVerificationStatus.VERIFIED

    @property
    def is_blocked(self) -> bool:
        return not self.is_verified

    @property
    def has_receipt(self) -> bool:
        return self.receipt is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def receipt_required(
        self,
    ) -> StrategyPlanningAuditStorageAdapterBindingVerificationReceipt:
        if self.receipt is None:
            raise ValueError("No adapter-binding verification receipt was created.")

        return self.receipt

    @property
    def can_continue_to_persistence_request_design(
        self,
    ) -> bool:
        return self.is_verified

    @property
    def has_adapter_instance(self) -> bool:
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
            f"{self.adapter_binding.stable_id}:"
            f"PLANNING_AUDIT_STORAGE_ADAPTER_BINDING_"
            f"VERIFICATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditStorageAdapterBindingVerificationFactory:
    """
    Pure factory for adapter-binding verification.

    VERIFIED permits later persistence-request design only.
    It performs and authorizes no adapter import, instance,
    invocation, persistence, network, broker, MT5, or
    trading execution operation.
    """

    def verify(
        self,
        adapter_binding: (PlanningAuditStorageAdapterBindingDecision),
    ) -> PlanningAuditStorageAdapterBindingVerificationDecision:
        if not isinstance(
            adapter_binding,
            PlanningAuditStorageAdapterBindingDecision,
        ):
            raise (
                PlanningAuditStorageAdapterBindingVerificationError(
                    PlanningAuditStorageAdapterBindingVerificationErrorReason.INVALID_ADAPTER_BINDING_DECISION,
                    "adapter_binding must be a PlanningAuditStorageAdapterBindingDecision.",
                )
            )

        evaluation = _derive_verification(adapter_binding)

        return PlanningAuditStorageAdapterBindingVerificationDecision(
            adapter_binding=adapter_binding,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            receipt=evaluation.receipt,
        )

    def generate(
        self,
        adapter_binding: (PlanningAuditStorageAdapterBindingDecision),
    ) -> PlanningAuditStorageAdapterBindingVerificationDecision:
        """Compatibility alias for verify()."""

        return self.verify(adapter_binding)

    def evaluate(
        self,
        adapter_binding: (PlanningAuditStorageAdapterBindingDecision),
    ) -> PlanningAuditStorageAdapterBindingVerificationDecision:
        """Compatibility alias for verify()."""

        return self.verify(adapter_binding)


def verify_planning_audit_storage_adapter_binding(
    adapter_binding: (PlanningAuditStorageAdapterBindingDecision),
) -> PlanningAuditStorageAdapterBindingVerificationDecision:
    return StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(adapter_binding)


AuditStorageAdapterBindingVerificationBlocker = (
    PlanningAuditStorageAdapterBindingVerificationBlocker
)
AuditStorageAdapterBindingVerificationCheck = PlanningAuditStorageAdapterBindingVerificationCheck
AuditStorageAdapterBindingVerificationDecision = (
    PlanningAuditStorageAdapterBindingVerificationDecision
)
AuditStorageAdapterBindingVerificationFactory = (
    StrategyPlanningAuditStorageAdapterBindingVerificationFactory
)
AuditStorageAdapterBindingVerificationReason = PlanningAuditStorageAdapterBindingVerificationReason
AuditStorageAdapterBindingVerificationReceipt = (
    StrategyPlanningAuditStorageAdapterBindingVerificationReceipt
)
AuditStorageAdapterBindingVerificationStatus = PlanningAuditStorageAdapterBindingVerificationStatus
PlanningAuditStorageAdapterBindingVerificationFactory = (
    StrategyPlanningAuditStorageAdapterBindingVerificationFactory
)
PlanningAuditStorageAdapterBindingVerificationReceipt = (
    StrategyPlanningAuditStorageAdapterBindingVerificationReceipt
)
StrategyAuditStorageAdapterBindingVerificationFactory = (
    StrategyPlanningAuditStorageAdapterBindingVerificationFactory
)
StrategyAuditStorageAdapterBindingVerificationReceipt = (
    StrategyPlanningAuditStorageAdapterBindingVerificationReceipt
)
