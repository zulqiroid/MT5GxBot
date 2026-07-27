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
    StrategyPlanningAuditPersistenceOutcomeContract,
)
from app.strategy.planning_audit_persistence_outcome_evidence import (
    PlanningAuditPersistenceOutcomeEvidenceDecision,
    PlanningAuditPersistenceOutcomeEvidenceSnapshot,
    PlanningAuditPersistenceOutcomeEvidenceSourceMode,
)
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageTarget,
)

PLANNING_AUDIT_PERSISTENCE_OUTCOME_RECEIPT_SCHEMA_VERSION = "1.0"


class PlanningAuditPersistenceOutcomeReceiptCheck(
    str,
    Enum,
):
    EVIDENCE_ACCEPTED = "EVIDENCE_ACCEPTED"
    EVIDENCE_DIGEST_MATCH = "EVIDENCE_DIGEST_MATCH"
    OUTCOME_KIND_ALLOWED = "OUTCOME_KIND_ALLOWED"
    TARGET_MATCH = "TARGET_MATCH"
    REQUEST_LINEAGE_MATCH = "REQUEST_LINEAGE_MATCH"
    PAYLOAD_LINEAGE_MATCH = "PAYLOAD_LINEAGE_MATCH"
    BINDING_LINEAGE_MATCH = "BINDING_LINEAGE_MATCH"
    NO_WRITE_BOUNDARY = "NO_WRITE_BOUNDARY"


_REQUIRED_CHECKS = (
    PlanningAuditPersistenceOutcomeReceiptCheck.EVIDENCE_ACCEPTED,
    PlanningAuditPersistenceOutcomeReceiptCheck.EVIDENCE_DIGEST_MATCH,
    PlanningAuditPersistenceOutcomeReceiptCheck.OUTCOME_KIND_ALLOWED,
    PlanningAuditPersistenceOutcomeReceiptCheck.TARGET_MATCH,
    PlanningAuditPersistenceOutcomeReceiptCheck.REQUEST_LINEAGE_MATCH,
    PlanningAuditPersistenceOutcomeReceiptCheck.PAYLOAD_LINEAGE_MATCH,
    PlanningAuditPersistenceOutcomeReceiptCheck.BINDING_LINEAGE_MATCH,
    PlanningAuditPersistenceOutcomeReceiptCheck.NO_WRITE_BOUNDARY,
)


class PlanningAuditPersistenceOutcomeReceiptStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditPersistenceOutcomeReceiptReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    OUTCOME_EVIDENCE_BLOCKED = "OUTCOME_EVIDENCE_BLOCKED"


class PlanningAuditPersistenceOutcomeReceiptBlocker(
    str,
    Enum,
):
    OUTCOME_EVIDENCE_BLOCKED = "OUTCOME_EVIDENCE_BLOCKED"


class PlanningAuditPersistenceOutcomeReceiptErrorReason(
    str,
    Enum,
):
    INVALID_OUTCOME_EVIDENCE_DECISION = "INVALID_OUTCOME_EVIDENCE_DECISION"


class PlanningAuditPersistenceOutcomeReceiptError(RuntimeError):
    """Structured analytical outcome-receipt failure."""

    def __init__(
        self,
        reason: (PlanningAuditPersistenceOutcomeReceiptErrorReason),
        message: str,
    ) -> None:
        self.reason = PlanningAuditPersistenceOutcomeReceiptErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Planning-audit persistence outcome-receipt "
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


def _canonical_receipt_payload(
    *,
    schema_version: str,
    checks: tuple[
        PlanningAuditPersistenceOutcomeReceiptCheck,
        ...,
    ],
    evidence_stable_id: str,
    source_name: str,
    source_mode: (PlanningAuditPersistenceOutcomeEvidenceSourceMode),
    target: PlanningAuditStorageTarget,
    outcome_kind: PlanningAuditPersistenceOutcomeKind,
    storage_record_reference: str,
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
            f"EVIDENCE_STABLE_ID={evidence_stable_id}",
            f"SOURCE_NAME={source_name}",
            f"SOURCE_MODE={source_mode.value}",
            f"TARGET={target.value}",
            f"OUTCOME_KIND={outcome_kind.value}",
            (f"STORAGE_RECORD_REFERENCE={storage_record_reference}"),
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
class StrategyPlanningAuditPersistenceOutcomeReceipt:
    """
    Immutable receipt for an accepted external outcome.

    It independently verifies evidence and contract lineage.
    It does not fabricate an outcome, invoke an adapter,
    submit a request, write storage, or perform trading
    execution.
    """

    outcome_evidence: PlanningAuditPersistenceOutcomeEvidenceDecision
    schema_version: str
    checks: tuple[
        PlanningAuditPersistenceOutcomeReceiptCheck,
        ...,
    ]
    source_name: str
    source_mode: PlanningAuditPersistenceOutcomeEvidenceSourceMode
    target: PlanningAuditStorageTarget
    outcome_kind: PlanningAuditPersistenceOutcomeKind
    storage_record_reference: str
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
    receipt_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.outcome_evidence,
            PlanningAuditPersistenceOutcomeEvidenceDecision,
        ):
            raise ValueError(
                "outcome_evidence must be a PlanningAuditPersistenceOutcomeEvidenceDecision."
            )

        if not self.outcome_evidence.is_accepted:
            raise ValueError("An outcome receipt requires accepted persistence outcome evidence.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PLANNING_AUDIT_PERSISTENCE_OUTCOME_RECEIPT_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current persistence outcome-receipt schema."
            )

        if not isinstance(self.checks, tuple):
            raise ValueError("checks must be a tuple.")

        if not all(
            isinstance(
                check,
                PlanningAuditPersistenceOutcomeReceiptCheck,
            )
            for check in self.checks
        ):
            raise ValueError("checks must contain persistence outcome receipt check members.")

        if len(set(self.checks)) != len(self.checks):
            raise ValueError("Outcome-receipt checks cannot contain duplicates.")

        if self.checks != _REQUIRED_CHECKS:
            raise ValueError(
                "Outcome-receipt checks must contain every required check in deterministic order."
            )

        source_name = _non_empty_string(
            self.source_name,
            "source_name",
        )

        if not isinstance(
            self.source_mode,
            PlanningAuditPersistenceOutcomeEvidenceSourceMode,
        ):
            raise ValueError(
                "source_mode must be a PlanningAuditPersistenceOutcomeEvidenceSourceMode member."
            )

        if self.source_mode != PlanningAuditPersistenceOutcomeEvidenceSourceMode.EXTERNAL_READ_ONLY:
            raise ValueError("Outcome receipt source mode must remain EXTERNAL_READ_ONLY.")

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

        storage_record_reference = _non_empty_string(
            self.storage_record_reference,
            "storage_record_reference",
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
        receipt_digest = _non_empty_string(
            self.receipt_digest,
            "receipt_digest",
        )

        for field_name, digest in (
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
            ("receipt_digest", receipt_digest),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        evidence = self.outcome_evidence.evidence_required
        contract = self.outcome_evidence.outcome_contract.contract_required

        if source_name != evidence.source_name:
            raise ValueError("source_name must match the accepted outcome evidence.")

        if self.source_mode != evidence.source_mode:
            raise ValueError("source_mode must match the accepted outcome evidence.")

        if self.target != evidence.target:
            raise ValueError("target must match the accepted outcome evidence.")

        if self.target != contract.target:
            raise ValueError("target must match the persistence outcome contract.")

        if self.outcome_kind != evidence.outcome_kind:
            raise ValueError("outcome_kind must match the accepted outcome evidence.")

        if self.outcome_kind not in contract.allowed_outcomes:
            raise ValueError("outcome_kind must be allowed by the persistence outcome contract.")

        if storage_record_reference != evidence.storage_record_reference:
            raise ValueError("storage_record_reference must match the accepted outcome evidence.")

        expected_evidence_digest = _sha256_digest(evidence.canonical_payload)

        if evidence_digest != evidence.evidence_digest:
            raise ValueError("evidence_digest must match the accepted outcome evidence.")

        if evidence_digest != expected_evidence_digest:
            raise ValueError("evidence_digest must match the canonical outcome-evidence payload.")

        expected_contract_digest = _sha256_digest(contract.canonical_payload)

        if outcome_contract_digest != contract.outcome_contract_digest:
            raise ValueError("outcome_contract_digest must match the persistence outcome contract.")

        if outcome_contract_digest != expected_contract_digest:
            raise ValueError(
                "outcome_contract_digest must match the canonical outcome-contract payload."
            )

        comparisons = (
            (
                "request_id",
                request_id,
                evidence.request_id,
                contract.expected_request_id,
            ),
            (
                "request_digest",
                request_digest,
                evidence.request_digest,
                contract.expected_request_digest,
            ),
            (
                "content_length_bytes",
                content_length,
                evidence.content_length_bytes,
                contract.expected_content_length_bytes,
            ),
            (
                "content_digest",
                content_digest,
                evidence.content_digest,
                contract.expected_content_digest,
            ),
            (
                "manifest_digest",
                manifest_digest,
                evidence.manifest_digest,
                contract.expected_manifest_digest,
            ),
            (
                "idempotency_key",
                idempotency_key,
                evidence.idempotency_key,
                contract.expected_idempotency_key,
            ),
            (
                "binding_receipt_digest",
                binding_receipt_digest,
                evidence.binding_receipt_digest,
                contract.expected_binding_receipt_digest,
            ),
            (
                "binding_id",
                binding_id,
                evidence.binding_id,
                contract.expected_binding_id,
            ),
            (
                "snapshot_id",
                snapshot_id,
                evidence.snapshot_id,
                contract.expected_snapshot_id,
            ),
            (
                "contract_id",
                contract_id,
                evidence.contract_id,
                contract.expected_contract_id,
            ),
        )

        for field_name, supplied, evidence_value, expected in comparisons:
            if supplied != evidence_value:
                raise ValueError(f"{field_name} must match the accepted outcome evidence.")

            if supplied != expected:
                raise ValueError(f"{field_name} must match the persistence outcome contract.")

        if not evidence.is_read_only_evidence:
            raise ValueError("Outcome receipt requires read-only external evidence.")

        if evidence.has_adapter_instance:
            raise ValueError("Outcome receipt cannot contain an adapter instance.")

        if evidence.can_submit_request:
            raise ValueError("Outcome receipt evidence cannot submit a request.")

        if evidence.can_invoke_adapter:
            raise ValueError("Outcome receipt evidence cannot invoke an adapter.")

        if evidence.can_write_storage:
            raise ValueError("Outcome receipt evidence cannot write storage.")

        if evidence.can_write_network:
            raise ValueError("Outcome receipt evidence cannot write to the network.")

        if not (self.outcome_evidence.has_accepted_external_outcome):
            raise ValueError("Outcome receipt requires an accepted external outcome.")

        if not (self.outcome_evidence.can_continue_to_outcome_receipt_design):
            raise ValueError("Outcome evidence does not permit receipt design.")

        if self.outcome_evidence.has_adapter_instance:
            raise ValueError("Outcome evidence decision cannot contain an adapter instance.")

        if self.outcome_evidence.request_submission_authorized:
            raise ValueError("Outcome receipt cannot inherit request submission authorization.")

        if self.outcome_evidence.adapter_invocation_authorized:
            raise ValueError("Outcome receipt cannot inherit adapter invocation authorization.")

        if self.outcome_evidence.storage_write_authorized:
            raise ValueError("Outcome receipt cannot inherit storage write authorization.")

        if self.outcome_evidence.is_persisted:
            raise ValueError("Outcome receipt cannot claim persistence from analytical evidence.")

        if self.outcome_evidence.can_write_storage:
            raise ValueError("Outcome receipt cannot write storage.")

        if self.outcome_evidence.can_write_network:
            raise ValueError("Outcome receipt cannot write to the network.")

        if self.outcome_evidence.execution_authorized:
            raise ValueError("Outcome receipt cannot contain trading execution authorization.")

        if self.outcome_evidence.has_broker_request:
            raise ValueError("Outcome receipt cannot contain a broker request.")

        if self.outcome_evidence.can_submit_order:
            raise ValueError("Outcome receipt cannot submit an order.")

        if self.outcome_evidence.is_executable:
            raise ValueError("Outcome receipt cannot be executable.")

        canonical_payload = _canonical_receipt_payload(
            schema_version=schema_version,
            checks=self.checks,
            evidence_stable_id=evidence.stable_id,
            source_name=source_name,
            source_mode=self.source_mode,
            target=self.target,
            outcome_kind=self.outcome_kind,
            storage_record_reference=(storage_record_reference),
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
        expected_receipt_digest = _sha256_digest(canonical_payload)

        if receipt_digest != expected_receipt_digest:
            raise ValueError("receipt_digest does not match the canonical outcome-receipt payload.")

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
            "receipt_digest",
            receipt_digest,
        )

    @property
    def evidence(
        self,
    ) -> PlanningAuditPersistenceOutcomeEvidenceSnapshot:
        return self.outcome_evidence.evidence_required

    @property
    def contract(
        self,
    ) -> StrategyPlanningAuditPersistenceOutcomeContract:
        return self.outcome_evidence.outcome_contract.contract_required

    @property
    def broker_symbol(self) -> str:
        return self.contract.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.evidence.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.contract.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.contract.side

    @property
    def verification_count(self) -> int:
        return len(self.checks)

    @property
    def canonical_payload(self) -> str:
        return _canonical_receipt_payload(
            schema_version=self.schema_version,
            checks=self.checks,
            evidence_stable_id=self.evidence.stable_id,
            source_name=self.source_name,
            source_mode=self.source_mode,
            target=self.target,
            outcome_kind=self.outcome_kind,
            storage_record_reference=(self.storage_record_reference),
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
    def is_verified(self) -> bool:
        return True

    @property
    def is_tamper_evident(self) -> bool:
        return True

    @property
    def records_external_outcome(self) -> bool:
        return True

    @property
    def indicates_created(self) -> bool:
        return self.outcome_kind == PlanningAuditPersistenceOutcomeKind.CREATED

    @property
    def indicates_existing(self) -> bool:
        return self.outcome_kind == PlanningAuditPersistenceOutcomeKind.EXISTING

    @property
    def can_continue_to_audit_completion_design(
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
    def receipt_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"AUDIT_PERSISTENCE_OUTCOME_RECEIPT:"
            f"{self.outcome_kind.value}:"
            f"RECORD[{self.storage_record_reference}]:"
            f"RECEIPT_SHA256[{self.receipt_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.outcome_evidence.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_OUTCOME_RECEIPT:"
            f"{self.receipt_id}"
        )


@dataclass(frozen=True, slots=True)
class _PersistenceOutcomeReceiptEvaluation:
    status: PlanningAuditPersistenceOutcomeReceiptStatus
    reason: PlanningAuditPersistenceOutcomeReceiptReason
    blockers: tuple[
        PlanningAuditPersistenceOutcomeReceiptBlocker,
        ...,
    ]
    receipt: StrategyPlanningAuditPersistenceOutcomeReceipt | None


def _derive_receipt(
    outcome_evidence: (PlanningAuditPersistenceOutcomeEvidenceDecision),
) -> _PersistenceOutcomeReceiptEvaluation:
    if outcome_evidence.is_blocked:
        return _PersistenceOutcomeReceiptEvaluation(
            status=(PlanningAuditPersistenceOutcomeReceiptStatus.BLOCKED),
            reason=(PlanningAuditPersistenceOutcomeReceiptReason.OUTCOME_EVIDENCE_BLOCKED),
            blockers=(PlanningAuditPersistenceOutcomeReceiptBlocker.OUTCOME_EVIDENCE_BLOCKED,),
            receipt=None,
        )

    evidence = outcome_evidence.evidence_required
    contract = outcome_evidence.outcome_contract.contract_required

    canonical_payload = _canonical_receipt_payload(
        schema_version=(PLANNING_AUDIT_PERSISTENCE_OUTCOME_RECEIPT_SCHEMA_VERSION),
        checks=_REQUIRED_CHECKS,
        evidence_stable_id=evidence.stable_id,
        source_name=evidence.source_name,
        source_mode=evidence.source_mode,
        target=evidence.target,
        outcome_kind=evidence.outcome_kind,
        storage_record_reference=(evidence.storage_record_reference),
        evidence_digest=evidence.evidence_digest,
        outcome_contract_digest=(contract.outcome_contract_digest),
        request_id=evidence.request_id,
        request_digest=evidence.request_digest,
        content_length_bytes=(evidence.content_length_bytes),
        content_digest=evidence.content_digest,
        manifest_digest=evidence.manifest_digest,
        idempotency_key=evidence.idempotency_key,
        binding_receipt_digest=(evidence.binding_receipt_digest),
        binding_id=evidence.binding_id,
        snapshot_id=evidence.snapshot_id,
        contract_id=evidence.contract_id,
    )

    receipt = StrategyPlanningAuditPersistenceOutcomeReceipt(
        outcome_evidence=outcome_evidence,
        schema_version=(PLANNING_AUDIT_PERSISTENCE_OUTCOME_RECEIPT_SCHEMA_VERSION),
        checks=_REQUIRED_CHECKS,
        source_name=evidence.source_name,
        source_mode=evidence.source_mode,
        target=evidence.target,
        outcome_kind=evidence.outcome_kind,
        storage_record_reference=(evidence.storage_record_reference),
        evidence_digest=evidence.evidence_digest,
        outcome_contract_digest=(contract.outcome_contract_digest),
        request_id=evidence.request_id,
        request_digest=evidence.request_digest,
        content_length_bytes=(evidence.content_length_bytes),
        content_digest=evidence.content_digest,
        manifest_digest=evidence.manifest_digest,
        idempotency_key=evidence.idempotency_key,
        binding_receipt_digest=(evidence.binding_receipt_digest),
        binding_id=evidence.binding_id,
        snapshot_id=evidence.snapshot_id,
        contract_id=evidence.contract_id,
        receipt_digest=_sha256_digest(canonical_payload),
    )

    return _PersistenceOutcomeReceiptEvaluation(
        status=(PlanningAuditPersistenceOutcomeReceiptStatus.CREATED),
        reason=(PlanningAuditPersistenceOutcomeReceiptReason.CREATED),
        blockers=(),
        receipt=receipt,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditPersistenceOutcomeReceiptDecision:
    """Validated analytical persistence-outcome receipt."""

    outcome_evidence: PlanningAuditPersistenceOutcomeEvidenceDecision
    status: PlanningAuditPersistenceOutcomeReceiptStatus
    reason: PlanningAuditPersistenceOutcomeReceiptReason
    blockers: tuple[
        PlanningAuditPersistenceOutcomeReceiptBlocker,
        ...,
    ]
    receipt: StrategyPlanningAuditPersistenceOutcomeReceipt | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.outcome_evidence,
            PlanningAuditPersistenceOutcomeEvidenceDecision,
        ):
            raise ValueError(
                "outcome_evidence must be a PlanningAuditPersistenceOutcomeEvidenceDecision."
            )

        try:
            status = PlanningAuditPersistenceOutcomeReceiptStatus(self.status)
            reason = PlanningAuditPersistenceOutcomeReceiptReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported persistence outcome-receipt status or reason.") from error

        blockers = tuple(
            PlanningAuditPersistenceOutcomeReceiptBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Outcome-receipt blockers cannot contain duplicates.")

        if self.receipt is not None and not isinstance(
            self.receipt,
            StrategyPlanningAuditPersistenceOutcomeReceipt,
        ):
            raise ValueError(
                "receipt must be a StrategyPlanningAuditPersistenceOutcomeReceipt or None."
            )

        expected = _derive_receipt(self.outcome_evidence)
        supplied = _PersistenceOutcomeReceiptEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            receipt=self.receipt,
        )

        if supplied != expected:
            raise ValueError(
                "Persistence outcome-receipt result does not match its outcome-evidence decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.outcome_evidence.broker_symbol

    @property
    def observed_at(self) -> datetime:
        if self.receipt is not None:
            return self.receipt.observed_at

        return self.outcome_evidence.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.outcome_evidence.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditPersistenceOutcomeReceiptStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_receipt(self) -> bool:
        return self.receipt is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def receipt_required(
        self,
    ) -> StrategyPlanningAuditPersistenceOutcomeReceipt:
        if self.receipt is None:
            raise ValueError("No planning-audit persistence outcome receipt was created.")

        return self.receipt

    @property
    def can_continue_to_audit_completion_design(
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
            f"{self.outcome_evidence.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_OUTCOME_"
            f"RECEIPT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditPersistenceOutcomeReceiptFactory:
    """
    Pure factory for deterministic outcome receipts.

    CREATED permits later audit-completion design only.
    No evidence is fabricated and no adapter invocation,
    request submission, persistence, network, broker, MT5,
    or trading execution operation is performed.
    """

    def generate(
        self,
        outcome_evidence: (PlanningAuditPersistenceOutcomeEvidenceDecision),
    ) -> PlanningAuditPersistenceOutcomeReceiptDecision:
        if not isinstance(
            outcome_evidence,
            PlanningAuditPersistenceOutcomeEvidenceDecision,
        ):
            raise PlanningAuditPersistenceOutcomeReceiptError(
                PlanningAuditPersistenceOutcomeReceiptErrorReason.INVALID_OUTCOME_EVIDENCE_DECISION,
                "outcome_evidence must be a PlanningAuditPersistenceOutcomeEvidenceDecision.",
            )

        evaluation = _derive_receipt(outcome_evidence)

        return PlanningAuditPersistenceOutcomeReceiptDecision(
            outcome_evidence=outcome_evidence,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            receipt=evaluation.receipt,
        )

    def build(
        self,
        outcome_evidence: (PlanningAuditPersistenceOutcomeEvidenceDecision),
    ) -> PlanningAuditPersistenceOutcomeReceiptDecision:
        """Compatibility alias for generate()."""

        return self.generate(outcome_evidence)

    def evaluate(
        self,
        outcome_evidence: (PlanningAuditPersistenceOutcomeEvidenceDecision),
    ) -> PlanningAuditPersistenceOutcomeReceiptDecision:
        """Compatibility alias for generate()."""

        return self.generate(outcome_evidence)


def generate_planning_audit_persistence_outcome_receipt(
    outcome_evidence: (PlanningAuditPersistenceOutcomeEvidenceDecision),
) -> PlanningAuditPersistenceOutcomeReceiptDecision:
    return StrategyPlanningAuditPersistenceOutcomeReceiptFactory().generate(outcome_evidence)


AuditPersistenceOutcomeReceipt = StrategyPlanningAuditPersistenceOutcomeReceipt
AuditPersistenceOutcomeReceiptBlocker = PlanningAuditPersistenceOutcomeReceiptBlocker
AuditPersistenceOutcomeReceiptCheck = PlanningAuditPersistenceOutcomeReceiptCheck
AuditPersistenceOutcomeReceiptDecision = PlanningAuditPersistenceOutcomeReceiptDecision
AuditPersistenceOutcomeReceiptFactory = StrategyPlanningAuditPersistenceOutcomeReceiptFactory
AuditPersistenceOutcomeReceiptReason = PlanningAuditPersistenceOutcomeReceiptReason
AuditPersistenceOutcomeReceiptStatus = PlanningAuditPersistenceOutcomeReceiptStatus
PlanningAuditPersistenceOutcomeReceipt = StrategyPlanningAuditPersistenceOutcomeReceipt
PlanningAuditPersistenceOutcomeReceiptFactory = (
    StrategyPlanningAuditPersistenceOutcomeReceiptFactory
)
StrategyAuditPersistenceOutcomeReceipt = StrategyPlanningAuditPersistenceOutcomeReceipt
StrategyAuditPersistenceOutcomeReceiptFactory = (
    StrategyPlanningAuditPersistenceOutcomeReceiptFactory
)
