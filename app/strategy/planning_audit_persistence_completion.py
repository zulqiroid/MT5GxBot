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
from app.strategy.planning_audit_persistence_outcome_contract import (
    PlanningAuditPersistenceOutcomeKind,
)
from app.strategy.planning_audit_persistence_outcome_receipt import (
    PlanningAuditPersistenceOutcomeReceiptDecision,
    StrategyPlanningAuditPersistenceOutcomeReceipt,
)
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageTarget,
)

PLANNING_AUDIT_PERSISTENCE_COMPLETION_SCHEMA_VERSION = "1.0"


class PlanningAuditPersistenceCompletionCheck(str, Enum):
    OUTCOME_RECEIPT_CREATED = "OUTCOME_RECEIPT_CREATED"
    OUTCOME_RECEIPT_DIGEST_MATCH = "OUTCOME_RECEIPT_DIGEST_MATCH"
    EVIDENCE_DIGEST_MATCH = "EVIDENCE_DIGEST_MATCH"
    OUTCOME_CONTRACT_DIGEST_MATCH = "OUTCOME_CONTRACT_DIGEST_MATCH"
    OUTCOME_KIND_CONFIRMED = "OUTCOME_KIND_CONFIRMED"
    STORAGE_REFERENCE_CONFIRMED = "STORAGE_REFERENCE_CONFIRMED"
    REQUEST_LINEAGE_COMPLETE = "REQUEST_LINEAGE_COMPLETE"
    PAYLOAD_LINEAGE_COMPLETE = "PAYLOAD_LINEAGE_COMPLETE"
    BINDING_LINEAGE_COMPLETE = "BINDING_LINEAGE_COMPLETE"
    NO_WRITE_BOUNDARY = "NO_WRITE_BOUNDARY"


_REQUIRED_CHECKS = (
    PlanningAuditPersistenceCompletionCheck.OUTCOME_RECEIPT_CREATED,
    PlanningAuditPersistenceCompletionCheck.OUTCOME_RECEIPT_DIGEST_MATCH,
    PlanningAuditPersistenceCompletionCheck.EVIDENCE_DIGEST_MATCH,
    PlanningAuditPersistenceCompletionCheck.OUTCOME_CONTRACT_DIGEST_MATCH,
    PlanningAuditPersistenceCompletionCheck.OUTCOME_KIND_CONFIRMED,
    PlanningAuditPersistenceCompletionCheck.STORAGE_REFERENCE_CONFIRMED,
    PlanningAuditPersistenceCompletionCheck.REQUEST_LINEAGE_COMPLETE,
    PlanningAuditPersistenceCompletionCheck.PAYLOAD_LINEAGE_COMPLETE,
    PlanningAuditPersistenceCompletionCheck.BINDING_LINEAGE_COMPLETE,
    PlanningAuditPersistenceCompletionCheck.NO_WRITE_BOUNDARY,
)


class PlanningAuditPersistenceCompletionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class PlanningAuditPersistenceCompletionReason(str, Enum):
    COMPLETED = "COMPLETED"
    OUTCOME_RECEIPT_BLOCKED = "OUTCOME_RECEIPT_BLOCKED"


class PlanningAuditPersistenceCompletionBlocker(str, Enum):
    OUTCOME_RECEIPT_BLOCKED = "OUTCOME_RECEIPT_BLOCKED"


class PlanningAuditPersistenceCompletionErrorReason(
    str,
    Enum,
):
    INVALID_OUTCOME_RECEIPT_DECISION = "INVALID_OUTCOME_RECEIPT_DECISION"


class PlanningAuditPersistenceCompletionError(RuntimeError):
    """Structured analytical completion-certificate failure."""

    def __init__(
        self,
        reason: (PlanningAuditPersistenceCompletionErrorReason),
        message: str,
    ) -> None:
        self.reason = PlanningAuditPersistenceCompletionErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Planning-audit persistence completion error [{self.reason.value}]: {self.message}"
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

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

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


def _canonical_completion_payload(
    *,
    schema_version: str,
    checks: tuple[
        PlanningAuditPersistenceCompletionCheck,
        ...,
    ],
    outcome_receipt_stable_id: str,
    target: PlanningAuditStorageTarget,
    outcome_kind: PlanningAuditPersistenceOutcomeKind,
    source_name: str,
    storage_record_reference: str,
    outcome_receipt_digest: str,
    evidence_digest: str,
    outcome_contract_digest: str,
    request_id: str,
    request_digest: str,
    content_length_bytes: int,
    content_digest: str,
    manifest_digest: str,
    idempotency_key: str,
    binding_receipt_digest: str,
    binding_id: str,
    snapshot_id: str,
    contract_id: str,
) -> str:
    check_fragment = ",".join(check.value for check in checks)

    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"CHECKS={check_fragment}",
            (f"OUTCOME_RECEIPT_STABLE_ID={outcome_receipt_stable_id}"),
            f"TARGET={target.value}",
            f"OUTCOME_KIND={outcome_kind.value}",
            f"SOURCE_NAME={source_name}",
            (f"STORAGE_RECORD_REFERENCE={storage_record_reference}"),
            (f"OUTCOME_RECEIPT_DIGEST={outcome_receipt_digest}"),
            f"EVIDENCE_DIGEST={evidence_digest}",
            (f"OUTCOME_CONTRACT_DIGEST={outcome_contract_digest}"),
            f"REQUEST_ID={request_id}",
            f"REQUEST_DIGEST={request_digest}",
            (f"CONTENT_LENGTH_BYTES={content_length_bytes}"),
            f"CONTENT_DIGEST={content_digest}",
            f"MANIFEST_DIGEST={manifest_digest}",
            f"IDEMPOTENCY_KEY={idempotency_key}",
            (f"BINDING_RECEIPT_DIGEST={binding_receipt_digest}"),
            f"BINDING_ID={binding_id}",
            f"SNAPSHOT_ID={snapshot_id}",
            f"CONTRACT_ID={contract_id}",
        )
    )


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditPersistenceCompletionCertificate:
    """
    Immutable analytical certificate for a verified external
    persistence outcome.

    The certificate seals complete request, payload,
    evidence, outcome-contract, and binding lineage. It
    records external evidence but performs and authorizes no
    persistence, adapter invocation, network, broker, MT5,
    or trading execution operation.
    """

    outcome_receipt: PlanningAuditPersistenceOutcomeReceiptDecision
    schema_version: str
    checks: tuple[
        PlanningAuditPersistenceCompletionCheck,
        ...,
    ]
    target: PlanningAuditStorageTarget
    outcome_kind: PlanningAuditPersistenceOutcomeKind
    source_name: str
    storage_record_reference: str
    outcome_receipt_digest: str
    evidence_digest: str
    outcome_contract_digest: str
    request_id: str
    request_digest: str
    content_length_bytes: int
    content_digest: str
    manifest_digest: str
    idempotency_key: str
    binding_receipt_digest: str
    binding_id: str
    snapshot_id: str
    contract_id: str
    completion_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.outcome_receipt,
            PlanningAuditPersistenceOutcomeReceiptDecision,
        ):
            raise ValueError(
                "outcome_receipt must be a PlanningAuditPersistenceOutcomeReceiptDecision."
            )

        if not self.outcome_receipt.is_created:
            raise ValueError(
                "A persistence completion certificate requires a created outcome receipt."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PLANNING_AUDIT_PERSISTENCE_COMPLETION_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current persistence-completion schema.")

        if not isinstance(self.checks, tuple):
            raise ValueError("checks must be a tuple.")

        if not all(
            isinstance(
                check,
                PlanningAuditPersistenceCompletionCheck,
            )
            for check in self.checks
        ):
            raise ValueError("checks must contain persistence-completion check members.")

        if len(set(self.checks)) != len(self.checks):
            raise ValueError("Persistence-completion checks cannot contain duplicates.")

        if self.checks != _REQUIRED_CHECKS:
            raise ValueError(
                "Persistence-completion checks must contain "
                "every required check in deterministic order."
            )

        if not isinstance(
            self.target,
            PlanningAuditStorageTarget,
        ):
            raise ValueError("target must be a PlanningAuditStorageTarget member.")

        if not isinstance(
            self.outcome_kind,
            PlanningAuditPersistenceOutcomeKind,
        ):
            raise ValueError("outcome_kind must be a PlanningAuditPersistenceOutcomeKind member.")

        source_name = _non_empty_string(
            self.source_name,
            "source_name",
        )
        storage_record_reference = _non_empty_string(
            self.storage_record_reference,
            "storage_record_reference",
        )
        outcome_receipt_digest = _non_empty_string(
            self.outcome_receipt_digest,
            "outcome_receipt_digest",
        )
        evidence_digest = _non_empty_string(
            self.evidence_digest,
            "evidence_digest",
        )
        outcome_contract_digest = _non_empty_string(
            self.outcome_contract_digest,
            "outcome_contract_digest",
        )
        request_id = _non_empty_string(
            self.request_id,
            "request_id",
        )
        request_digest = _non_empty_string(
            self.request_digest,
            "request_digest",
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
        binding_receipt_digest = _non_empty_string(
            self.binding_receipt_digest,
            "binding_receipt_digest",
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
        completion_digest = _non_empty_string(
            self.completion_digest,
            "completion_digest",
        )

        for field_name, digest in (
            (
                "outcome_receipt_digest",
                outcome_receipt_digest,
            ),
            ("evidence_digest", evidence_digest),
            (
                "outcome_contract_digest",
                outcome_contract_digest,
            ),
            ("request_digest", request_digest),
            ("content_digest", content_digest),
            ("manifest_digest", manifest_digest),
            ("idempotency_key", idempotency_key),
            (
                "binding_receipt_digest",
                binding_receipt_digest,
            ),
            ("completion_digest", completion_digest),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        receipt = self.outcome_receipt.receipt_required
        evidence = receipt.evidence
        contract = receipt.contract

        if self.target != receipt.target:
            raise ValueError("target must match the persistence outcome receipt.")

        if self.target != evidence.target:
            raise ValueError("target must match the accepted external evidence.")

        if self.target != contract.target:
            raise ValueError("target must match the persistence outcome contract.")

        if self.outcome_kind != receipt.outcome_kind:
            raise ValueError("outcome_kind must match the persistence outcome receipt.")

        if self.outcome_kind != evidence.outcome_kind:
            raise ValueError("outcome_kind must match the accepted external evidence.")

        if self.outcome_kind not in (
            PlanningAuditPersistenceOutcomeKind.CREATED,
            PlanningAuditPersistenceOutcomeKind.EXISTING,
        ):
            raise ValueError("outcome_kind must be CREATED or EXISTING.")

        if source_name != receipt.source_name:
            raise ValueError("source_name must match the persistence outcome receipt.")

        if source_name != evidence.source_name:
            raise ValueError("source_name must match the accepted external evidence.")

        if storage_record_reference != receipt.storage_record_reference:
            raise ValueError("storage_record_reference must match the persistence outcome receipt.")

        if storage_record_reference != evidence.storage_record_reference:
            raise ValueError("storage_record_reference must match the accepted external evidence.")

        calculated_receipt_digest = _sha256_digest(receipt.canonical_payload)

        if outcome_receipt_digest != receipt.receipt_digest:
            raise ValueError("outcome_receipt_digest must match the persistence outcome receipt.")

        if outcome_receipt_digest != calculated_receipt_digest:
            raise ValueError(
                "outcome_receipt_digest must match the canonical outcome-receipt payload."
            )

        calculated_evidence_digest = _sha256_digest(evidence.canonical_payload)

        if evidence_digest != receipt.evidence_digest:
            raise ValueError("evidence_digest must match the persistence outcome receipt.")

        if evidence_digest != evidence.evidence_digest:
            raise ValueError("evidence_digest must match the accepted external evidence.")

        if evidence_digest != calculated_evidence_digest:
            raise ValueError("evidence_digest must match the canonical outcome-evidence payload.")

        calculated_contract_digest = _sha256_digest(contract.canonical_payload)

        if outcome_contract_digest != receipt.outcome_contract_digest:
            raise ValueError("outcome_contract_digest must match the persistence outcome receipt.")

        if outcome_contract_digest != contract.outcome_contract_digest:
            raise ValueError("outcome_contract_digest must match the persistence outcome contract.")

        if outcome_contract_digest != calculated_contract_digest:
            raise ValueError(
                "outcome_contract_digest must match the canonical outcome-contract payload."
            )

        comparisons = (
            (
                "request_id",
                request_id,
                receipt.request_id,
                evidence.request_id,
                contract.expected_request_id,
            ),
            (
                "request_digest",
                request_digest,
                receipt.request_digest,
                evidence.request_digest,
                contract.expected_request_digest,
            ),
            (
                "content_length_bytes",
                content_length,
                receipt.content_length_bytes,
                evidence.content_length_bytes,
                contract.expected_content_length_bytes,
            ),
            (
                "content_digest",
                content_digest,
                receipt.content_digest,
                evidence.content_digest,
                contract.expected_content_digest,
            ),
            (
                "manifest_digest",
                manifest_digest,
                receipt.manifest_digest,
                evidence.manifest_digest,
                contract.expected_manifest_digest,
            ),
            (
                "idempotency_key",
                idempotency_key,
                receipt.idempotency_key,
                evidence.idempotency_key,
                contract.expected_idempotency_key,
            ),
            (
                "binding_receipt_digest",
                binding_receipt_digest,
                receipt.binding_receipt_digest,
                evidence.binding_receipt_digest,
                contract.expected_binding_receipt_digest,
            ),
            (
                "binding_id",
                binding_id,
                receipt.binding_id,
                evidence.binding_id,
                contract.expected_binding_id,
            ),
            (
                "snapshot_id",
                snapshot_id,
                receipt.snapshot_id,
                evidence.snapshot_id,
                contract.expected_snapshot_id,
            ),
            (
                "contract_id",
                contract_id,
                receipt.contract_id,
                evidence.contract_id,
                contract.expected_contract_id,
            ),
        )

        for (
            field_name,
            supplied,
            receipt_value,
            evidence_value,
            contract_value,
        ) in comparisons:
            if supplied != receipt_value:
                raise ValueError(f"{field_name} must match the persistence outcome receipt.")

            if supplied != evidence_value:
                raise ValueError(f"{field_name} must match the accepted external evidence.")

            if supplied != contract_value:
                raise ValueError(f"{field_name} must match the persistence outcome contract.")

        if not receipt.is_verified:
            raise ValueError(
                "Completion certificate requires a verified persistence outcome receipt."
            )

        if not receipt.is_tamper_evident:
            raise ValueError("Completion certificate requires a tamper-evident outcome receipt.")

        if not receipt.records_external_outcome:
            raise ValueError("Completion certificate requires a recorded external outcome.")

        if not (receipt.can_continue_to_audit_completion_design):
            raise ValueError("Outcome receipt does not permit audit completion design.")

        if receipt.has_adapter_instance:
            raise ValueError("Completion certificate cannot contain an adapter instance.")

        if receipt.request_submission_authorized:
            raise ValueError(
                "Completion certificate cannot inherit request-submission authorization."
            )

        if receipt.adapter_invocation_authorized:
            raise ValueError(
                "Completion certificate cannot inherit adapter-invocation authorization."
            )

        if receipt.storage_write_authorized:
            raise ValueError("Completion certificate cannot inherit storage-write authorization.")

        if receipt.is_persisted:
            raise ValueError(
                "Completion certificate cannot claim that "
                "its analytical layer performed persistence."
            )

        if receipt.can_write_storage:
            raise ValueError("Completion certificate cannot write storage.")

        if receipt.can_write_network:
            raise ValueError("Completion certificate cannot write to the network.")

        if receipt.execution_authorized:
            raise ValueError(
                "Completion certificate cannot contain trading execution authorization."
            )

        if receipt.has_broker_request:
            raise ValueError("Completion certificate cannot contain a broker request.")

        if receipt.can_submit_order:
            raise ValueError("Completion certificate cannot submit an order.")

        if receipt.is_executable:
            raise ValueError("Completion certificate cannot be executable.")

        canonical_payload = _canonical_completion_payload(
            schema_version=schema_version,
            checks=self.checks,
            outcome_receipt_stable_id=receipt.stable_id,
            target=self.target,
            outcome_kind=self.outcome_kind,
            source_name=source_name,
            storage_record_reference=(storage_record_reference),
            outcome_receipt_digest=(outcome_receipt_digest),
            evidence_digest=evidence_digest,
            outcome_contract_digest=(outcome_contract_digest),
            request_id=request_id,
            request_digest=request_digest,
            content_length_bytes=content_length,
            content_digest=content_digest,
            manifest_digest=manifest_digest,
            idempotency_key=idempotency_key,
            binding_receipt_digest=(binding_receipt_digest),
            binding_id=binding_id,
            snapshot_id=snapshot_id,
            contract_id=contract_id,
        )
        expected_completion_digest = _sha256_digest(canonical_payload)

        if completion_digest != expected_completion_digest:
            raise ValueError(
                "completion_digest does not match the canonical persistence-completion payload."
            )

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "source_name",
            source_name,
        )
        object.__setattr__(
            self,
            "storage_record_reference",
            storage_record_reference,
        )
        object.__setattr__(
            self,
            "outcome_receipt_digest",
            outcome_receipt_digest,
        )
        object.__setattr__(
            self,
            "evidence_digest",
            evidence_digest,
        )
        object.__setattr__(
            self,
            "outcome_contract_digest",
            outcome_contract_digest,
        )
        object.__setattr__(
            self,
            "request_id",
            request_id,
        )
        object.__setattr__(
            self,
            "request_digest",
            request_digest,
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
            "binding_receipt_digest",
            binding_receipt_digest,
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
            "completion_digest",
            completion_digest,
        )

    @property
    def receipt(
        self,
    ) -> StrategyPlanningAuditPersistenceOutcomeReceipt:
        return self.outcome_receipt.receipt_required

    @property
    def evidence(self):
        return self.receipt.evidence

    @property
    def contract(self):
        return self.receipt.contract

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
    def verification_count(self) -> int:
        return len(self.checks)

    @property
    def canonical_payload(self) -> str:
        return _canonical_completion_payload(
            schema_version=self.schema_version,
            checks=self.checks,
            outcome_receipt_stable_id=(self.receipt.stable_id),
            target=self.target,
            outcome_kind=self.outcome_kind,
            source_name=self.source_name,
            storage_record_reference=(self.storage_record_reference),
            outcome_receipt_digest=(self.outcome_receipt_digest),
            evidence_digest=self.evidence_digest,
            outcome_contract_digest=(self.outcome_contract_digest),
            request_id=self.request_id,
            request_digest=self.request_digest,
            content_length_bytes=self.content_length_bytes,
            content_digest=self.content_digest,
            manifest_digest=self.manifest_digest,
            idempotency_key=self.idempotency_key,
            binding_receipt_digest=(self.binding_receipt_digest),
            binding_id=self.binding_id,
            snapshot_id=self.snapshot_id,
            contract_id=self.contract_id,
        )

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def is_completed(self) -> bool:
        return True

    @property
    def is_verified(self) -> bool:
        return True

    @property
    def is_tamper_evident(self) -> bool:
        return True

    @property
    def records_external_persistence(self) -> bool:
        return True

    @property
    def performed_persistence(self) -> bool:
        return False

    @property
    def indicates_created(self) -> bool:
        return self.outcome_kind == PlanningAuditPersistenceOutcomeKind.CREATED

    @property
    def indicates_existing(self) -> bool:
        return self.outcome_kind == PlanningAuditPersistenceOutcomeKind.EXISTING

    @property
    def can_continue_to_final_audit_bundle_design(
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
    def certificate_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"AUDIT_PERSISTENCE_COMPLETION:"
            f"{self.outcome_kind.value}:"
            f"RECORD[{self.storage_record_reference}]:"
            f"COMPLETION_SHA256["
            f"{self.completion_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.outcome_receipt.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_COMPLETION:"
            f"{self.certificate_id}"
        )


@dataclass(frozen=True, slots=True)
class _PersistenceCompletionEvaluation:
    status: PlanningAuditPersistenceCompletionStatus
    reason: PlanningAuditPersistenceCompletionReason
    blockers: tuple[
        PlanningAuditPersistenceCompletionBlocker,
        ...,
    ]
    certificate: StrategyPlanningAuditPersistenceCompletionCertificate | None


def _derive_completion(
    outcome_receipt: (PlanningAuditPersistenceOutcomeReceiptDecision),
) -> _PersistenceCompletionEvaluation:
    if outcome_receipt.is_blocked:
        return _PersistenceCompletionEvaluation(
            status=(PlanningAuditPersistenceCompletionStatus.BLOCKED),
            reason=(PlanningAuditPersistenceCompletionReason.OUTCOME_RECEIPT_BLOCKED),
            blockers=(PlanningAuditPersistenceCompletionBlocker.OUTCOME_RECEIPT_BLOCKED,),
            certificate=None,
        )

    receipt = outcome_receipt.receipt_required

    canonical_payload = _canonical_completion_payload(
        schema_version=(PLANNING_AUDIT_PERSISTENCE_COMPLETION_SCHEMA_VERSION),
        checks=_REQUIRED_CHECKS,
        outcome_receipt_stable_id=receipt.stable_id,
        target=receipt.target,
        outcome_kind=receipt.outcome_kind,
        source_name=receipt.source_name,
        storage_record_reference=(receipt.storage_record_reference),
        outcome_receipt_digest=receipt.receipt_digest,
        evidence_digest=receipt.evidence_digest,
        outcome_contract_digest=(receipt.outcome_contract_digest),
        request_id=receipt.request_id,
        request_digest=receipt.request_digest,
        content_length_bytes=receipt.content_length_bytes,
        content_digest=receipt.content_digest,
        manifest_digest=receipt.manifest_digest,
        idempotency_key=receipt.idempotency_key,
        binding_receipt_digest=(receipt.binding_receipt_digest),
        binding_id=receipt.binding_id,
        snapshot_id=receipt.snapshot_id,
        contract_id=receipt.contract_id,
    )

    certificate = StrategyPlanningAuditPersistenceCompletionCertificate(
        outcome_receipt=outcome_receipt,
        schema_version=(PLANNING_AUDIT_PERSISTENCE_COMPLETION_SCHEMA_VERSION),
        checks=_REQUIRED_CHECKS,
        target=receipt.target,
        outcome_kind=receipt.outcome_kind,
        source_name=receipt.source_name,
        storage_record_reference=(receipt.storage_record_reference),
        outcome_receipt_digest=receipt.receipt_digest,
        evidence_digest=receipt.evidence_digest,
        outcome_contract_digest=(receipt.outcome_contract_digest),
        request_id=receipt.request_id,
        request_digest=receipt.request_digest,
        content_length_bytes=(receipt.content_length_bytes),
        content_digest=receipt.content_digest,
        manifest_digest=receipt.manifest_digest,
        idempotency_key=receipt.idempotency_key,
        binding_receipt_digest=(receipt.binding_receipt_digest),
        binding_id=receipt.binding_id,
        snapshot_id=receipt.snapshot_id,
        contract_id=receipt.contract_id,
        completion_digest=_sha256_digest(canonical_payload),
    )

    return _PersistenceCompletionEvaluation(
        status=(PlanningAuditPersistenceCompletionStatus.COMPLETED),
        reason=(PlanningAuditPersistenceCompletionReason.COMPLETED),
        blockers=(),
        certificate=certificate,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditPersistenceCompletionDecision:
    """Validated analytical persistence-completion result."""

    outcome_receipt: PlanningAuditPersistenceOutcomeReceiptDecision
    status: PlanningAuditPersistenceCompletionStatus
    reason: PlanningAuditPersistenceCompletionReason
    blockers: tuple[
        PlanningAuditPersistenceCompletionBlocker,
        ...,
    ]
    certificate: StrategyPlanningAuditPersistenceCompletionCertificate | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.outcome_receipt,
            PlanningAuditPersistenceOutcomeReceiptDecision,
        ):
            raise ValueError(
                "outcome_receipt must be a PlanningAuditPersistenceOutcomeReceiptDecision."
            )

        try:
            status = PlanningAuditPersistenceCompletionStatus(self.status)
            reason = PlanningAuditPersistenceCompletionReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported persistence-completion status or reason.") from error

        blockers = tuple(
            PlanningAuditPersistenceCompletionBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Persistence-completion blockers cannot contain duplicates.")

        if self.certificate is not None and not isinstance(
            self.certificate,
            StrategyPlanningAuditPersistenceCompletionCertificate,
        ):
            raise ValueError(
                "certificate must be a "
                "StrategyPlanningAuditPersistenceCompletionCertificate "
                "or None."
            )

        expected = _derive_completion(self.outcome_receipt)
        supplied = _PersistenceCompletionEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            certificate=self.certificate,
        )

        if supplied != expected:
            raise ValueError(
                "Persistence-completion result does not match its outcome-receipt decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.outcome_receipt.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.outcome_receipt.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.outcome_receipt.direction

    @property
    def is_completed(self) -> bool:
        return self.status == PlanningAuditPersistenceCompletionStatus.COMPLETED

    @property
    def is_blocked(self) -> bool:
        return not self.is_completed

    @property
    def has_certificate(self) -> bool:
        return self.certificate is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def certificate_required(
        self,
    ) -> StrategyPlanningAuditPersistenceCompletionCertificate:
        if self.certificate is None:
            raise ValueError("No planning-audit persistence completion certificate was created.")

        return self.certificate

    @property
    def can_continue_to_final_audit_bundle_design(
        self,
    ) -> bool:
        return self.is_completed

    @property
    def performed_persistence(self) -> bool:
        return False

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
            f"{self.outcome_receipt.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_COMPLETION_"
            f"GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditPersistenceCompletionFactory:
    """
    Pure factory for analytical completion certificates.

    COMPLETED permits later final-audit-bundle design only.
    It performs and authorizes no persistence, adapter
    invocation, request submission, network, broker, MT5,
    or trading execution operation.
    """

    def generate(
        self,
        outcome_receipt: (PlanningAuditPersistenceOutcomeReceiptDecision),
    ) -> PlanningAuditPersistenceCompletionDecision:
        if not isinstance(
            outcome_receipt,
            PlanningAuditPersistenceOutcomeReceiptDecision,
        ):
            raise PlanningAuditPersistenceCompletionError(
                PlanningAuditPersistenceCompletionErrorReason.INVALID_OUTCOME_RECEIPT_DECISION,
                "outcome_receipt must be a PlanningAuditPersistenceOutcomeReceiptDecision.",
            )

        evaluation = _derive_completion(outcome_receipt)

        return PlanningAuditPersistenceCompletionDecision(
            outcome_receipt=outcome_receipt,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            certificate=evaluation.certificate,
        )

    def build(
        self,
        outcome_receipt: (PlanningAuditPersistenceOutcomeReceiptDecision),
    ) -> PlanningAuditPersistenceCompletionDecision:
        """Compatibility alias for generate()."""

        return self.generate(outcome_receipt)

    def evaluate(
        self,
        outcome_receipt: (PlanningAuditPersistenceOutcomeReceiptDecision),
    ) -> PlanningAuditPersistenceCompletionDecision:
        """Compatibility alias for generate()."""

        return self.generate(outcome_receipt)


def generate_planning_audit_persistence_completion(
    outcome_receipt: (PlanningAuditPersistenceOutcomeReceiptDecision),
) -> PlanningAuditPersistenceCompletionDecision:
    return StrategyPlanningAuditPersistenceCompletionFactory().generate(outcome_receipt)


AuditPersistenceCompletionCertificate = StrategyPlanningAuditPersistenceCompletionCertificate
AuditPersistenceCompletionCheck = PlanningAuditPersistenceCompletionCheck
AuditPersistenceCompletionDecision = PlanningAuditPersistenceCompletionDecision
AuditPersistenceCompletionFactory = StrategyPlanningAuditPersistenceCompletionFactory
PlanningAuditPersistenceCompletionCertificate = (
    StrategyPlanningAuditPersistenceCompletionCertificate
)
PlanningAuditPersistenceCompletionFactory = StrategyPlanningAuditPersistenceCompletionFactory
StrategyAuditPersistenceCompletionCertificate = (
    StrategyPlanningAuditPersistenceCompletionCertificate
)
StrategyAuditPersistenceCompletionFactory = StrategyPlanningAuditPersistenceCompletionFactory
