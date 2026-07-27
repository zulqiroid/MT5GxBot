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
    PlanningAuditPersistenceOutcomeContractDecision,
    PlanningAuditPersistenceOutcomeKind,
    StrategyPlanningAuditPersistenceOutcomeContract,
)
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageTarget,
)

PLANNING_AUDIT_PERSISTENCE_OUTCOME_EVIDENCE_SCHEMA_VERSION = "1.0"


class PlanningAuditPersistenceOutcomeEvidenceSourceMode(
    str,
    Enum,
):
    EXTERNAL_READ_ONLY = "EXTERNAL_READ_ONLY"


class PlanningAuditPersistenceOutcomeEvidenceStatus(
    str,
    Enum,
):
    ACCEPTED = "ACCEPTED"
    BLOCKED = "BLOCKED"


class PlanningAuditPersistenceOutcomeEvidenceReason(
    str,
    Enum,
):
    ACCEPTED = "ACCEPTED"
    OUTCOME_CONTRACT_BLOCKED = "OUTCOME_CONTRACT_BLOCKED"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    OUTCOME_NOT_ALLOWED = "OUTCOME_NOT_ALLOWED"
    REQUEST_ID_MISMATCH = "REQUEST_ID_MISMATCH"
    REQUEST_DIGEST_MISMATCH = "REQUEST_DIGEST_MISMATCH"
    CONTENT_LENGTH_MISMATCH = "CONTENT_LENGTH_MISMATCH"
    CONTENT_DIGEST_MISMATCH = "CONTENT_DIGEST_MISMATCH"
    MANIFEST_DIGEST_MISMATCH = "MANIFEST_DIGEST_MISMATCH"
    IDEMPOTENCY_KEY_MISMATCH = "IDEMPOTENCY_KEY_MISMATCH"
    BINDING_RECEIPT_MISMATCH = "BINDING_RECEIPT_MISMATCH"
    BINDING_ID_MISMATCH = "BINDING_ID_MISMATCH"
    SNAPSHOT_ID_MISMATCH = "SNAPSHOT_ID_MISMATCH"
    CONTRACT_ID_MISMATCH = "CONTRACT_ID_MISMATCH"
    MULTIPLE_EVIDENCE_BLOCKERS = "MULTIPLE_EVIDENCE_BLOCKERS"


class PlanningAuditPersistenceOutcomeEvidenceBlocker(
    str,
    Enum,
):
    OUTCOME_CONTRACT_BLOCKED = "OUTCOME_CONTRACT_BLOCKED"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    OUTCOME_NOT_ALLOWED = "OUTCOME_NOT_ALLOWED"
    REQUEST_ID_MISMATCH = "REQUEST_ID_MISMATCH"
    REQUEST_DIGEST_MISMATCH = "REQUEST_DIGEST_MISMATCH"
    CONTENT_LENGTH_MISMATCH = "CONTENT_LENGTH_MISMATCH"
    CONTENT_DIGEST_MISMATCH = "CONTENT_DIGEST_MISMATCH"
    MANIFEST_DIGEST_MISMATCH = "MANIFEST_DIGEST_MISMATCH"
    IDEMPOTENCY_KEY_MISMATCH = "IDEMPOTENCY_KEY_MISMATCH"
    BINDING_RECEIPT_MISMATCH = "BINDING_RECEIPT_MISMATCH"
    BINDING_ID_MISMATCH = "BINDING_ID_MISMATCH"
    SNAPSHOT_ID_MISMATCH = "SNAPSHOT_ID_MISMATCH"
    CONTRACT_ID_MISMATCH = "CONTRACT_ID_MISMATCH"


class PlanningAuditPersistenceOutcomeEvidenceErrorReason(
    str,
    Enum,
):
    INVALID_OUTCOME_CONTRACT_DECISION = "INVALID_OUTCOME_CONTRACT_DECISION"
    INVALID_EVIDENCE_SNAPSHOT = "INVALID_EVIDENCE_SNAPSHOT"


class PlanningAuditPersistenceOutcomeEvidenceError(RuntimeError):
    """Structured read-only outcome-evidence failure."""

    def __init__(
        self,
        reason: (PlanningAuditPersistenceOutcomeEvidenceErrorReason),
        message: str,
    ) -> None:
        self.reason = PlanningAuditPersistenceOutcomeEvidenceErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Planning-audit persistence outcome-evidence "
            f"error [{self.reason.value}]: {self.message}"
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

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    return normalized


def _opaque_reference(
    value: object,
    field_name: str,
) -> str:
    normalized = _non_empty_string(
        value,
        field_name,
    )

    if "/" in normalized or "\\" in normalized:
        raise ValueError(f"{field_name} must be an opaque reference, not a filesystem path.")

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


def _is_lowercase_sha256(value: str) -> bool:
    hexadecimal = set("0123456789abcdef")

    return (
        len(value) == 64
        and value == value.lower()
        and all(character in hexadecimal for character in value)
    )


def _sha256_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _canonical_evidence_payload(
    *,
    schema_version: str,
    observed_at: datetime,
    source_name: str,
    source_mode: (PlanningAuditPersistenceOutcomeEvidenceSourceMode),
    target: PlanningAuditStorageTarget,
    outcome_kind: PlanningAuditPersistenceOutcomeKind,
    storage_record_reference: str,
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
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"OBSERVED_AT={observed_at.isoformat()}",
            f"SOURCE_NAME={source_name}",
            f"SOURCE_MODE={source_mode.value}",
            f"TARGET={target.value}",
            f"OUTCOME_KIND={outcome_kind.value}",
            (f"STORAGE_RECORD_REFERENCE={storage_record_reference}"),
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
class PlanningAuditPersistenceOutcomeEvidencePolicy:
    """Strict policy for external read-only evidence."""

    require_non_stale_evidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "require_non_stale_evidence",
            _strict_boolean(
                self.require_non_stale_evidence,
                "require_non_stale_evidence",
            ),
        )


@dataclass(frozen=True, slots=True)
class PlanningAuditPersistenceOutcomeEvidenceSnapshot:
    """
    Externally supplied read-only persistence-result evidence.

    The snapshot contains no adapter object, credential,
    path, connection, transaction, callable, request
    handle, or write operation.
    """

    schema_version: str
    observed_at: datetime
    source_name: str
    source_mode: PlanningAuditPersistenceOutcomeEvidenceSourceMode
    target: PlanningAuditStorageTarget
    outcome_kind: PlanningAuditPersistenceOutcomeKind
    storage_record_reference: str
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
    evidence_digest: str

    def __post_init__(self) -> None:
        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PLANNING_AUDIT_PERSISTENCE_OUTCOME_EVIDENCE_SCHEMA_VERSION):
            raise ValueError("schema_version must match the current outcome-evidence schema.")

        observed_at = _aware_datetime(
            self.observed_at,
            "observed_at",
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
            raise ValueError("Outcome evidence source mode must remain EXTERNAL_READ_ONLY.")

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

        storage_record_reference = _opaque_reference(
            self.storage_record_reference,
            "storage_record_reference",
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
        evidence_digest = _non_empty_string(
            self.evidence_digest,
            "evidence_digest",
        )

        for field_name, digest in (
            ("request_digest", request_digest),
            ("content_digest", content_digest),
            ("manifest_digest", manifest_digest),
            ("idempotency_key", idempotency_key),
            (
                "binding_receipt_digest",
                binding_receipt_digest,
            ),
            ("evidence_digest", evidence_digest),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        canonical_payload = _canonical_evidence_payload(
            schema_version=schema_version,
            observed_at=observed_at,
            source_name=source_name,
            source_mode=self.source_mode,
            target=self.target,
            outcome_kind=self.outcome_kind,
            storage_record_reference=(storage_record_reference),
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
        expected_evidence_digest = _sha256_digest(canonical_payload)

        if evidence_digest != expected_evidence_digest:
            raise ValueError(
                "evidence_digest does not match the canonical outcome-evidence payload."
            )

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "observed_at",
            observed_at,
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
            "evidence_digest",
            evidence_digest,
        )

    @classmethod
    def create(
        cls,
        *,
        observed_at: datetime,
        source_name: str,
        target: PlanningAuditStorageTarget,
        outcome_kind: PlanningAuditPersistenceOutcomeKind,
        storage_record_reference: str,
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
    ) -> PlanningAuditPersistenceOutcomeEvidenceSnapshot:
        normalized_observed_at = _aware_datetime(
            observed_at,
            "observed_at",
        )
        normalized_source_name = _non_empty_string(
            source_name,
            "source_name",
        )
        normalized_reference = _opaque_reference(
            storage_record_reference,
            "storage_record_reference",
        )

        if not isinstance(
            target,
            PlanningAuditStorageTarget,
        ):
            raise ValueError("target must be a PlanningAuditStorageTarget member.")

        if not isinstance(
            outcome_kind,
            PlanningAuditPersistenceOutcomeKind,
        ):
            raise ValueError("outcome_kind must be a PlanningAuditPersistenceOutcomeKind member.")

        source_mode = PlanningAuditPersistenceOutcomeEvidenceSourceMode.EXTERNAL_READ_ONLY
        canonical_payload = _canonical_evidence_payload(
            schema_version=(PLANNING_AUDIT_PERSISTENCE_OUTCOME_EVIDENCE_SCHEMA_VERSION),
            observed_at=normalized_observed_at,
            source_name=normalized_source_name,
            source_mode=source_mode,
            target=target,
            outcome_kind=outcome_kind,
            storage_record_reference=normalized_reference,
            request_id=request_id,
            request_digest=request_digest,
            content_length_bytes=content_length_bytes,
            content_digest=content_digest,
            manifest_digest=manifest_digest,
            idempotency_key=idempotency_key,
            binding_receipt_digest=(binding_receipt_digest),
            binding_id=binding_id,
            snapshot_id=snapshot_id,
            contract_id=contract_id,
        )

        return cls(
            schema_version=(PLANNING_AUDIT_PERSISTENCE_OUTCOME_EVIDENCE_SCHEMA_VERSION),
            observed_at=normalized_observed_at,
            source_name=normalized_source_name,
            source_mode=source_mode,
            target=target,
            outcome_kind=outcome_kind,
            storage_record_reference=normalized_reference,
            request_id=request_id,
            request_digest=request_digest,
            content_length_bytes=content_length_bytes,
            content_digest=content_digest,
            manifest_digest=manifest_digest,
            idempotency_key=idempotency_key,
            binding_receipt_digest=(binding_receipt_digest),
            binding_id=binding_id,
            snapshot_id=snapshot_id,
            contract_id=contract_id,
            evidence_digest=_sha256_digest(canonical_payload),
        )

    @property
    def canonical_payload(self) -> str:
        return _canonical_evidence_payload(
            schema_version=self.schema_version,
            observed_at=self.observed_at,
            source_name=self.source_name,
            source_mode=self.source_mode,
            target=self.target,
            outcome_kind=self.outcome_kind,
            storage_record_reference=(self.storage_record_reference),
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
    def is_read_only_evidence(self) -> bool:
        return True

    @property
    def indicates_created(self) -> bool:
        return self.outcome_kind == PlanningAuditPersistenceOutcomeKind.CREATED

    @property
    def indicates_existing(self) -> bool:
        return self.outcome_kind == PlanningAuditPersistenceOutcomeKind.EXISTING

    @property
    def has_adapter_instance(self) -> bool:
        return False

    @property
    def can_submit_request(self) -> bool:
        return False

    @property
    def can_invoke_adapter(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def can_write_network(self) -> bool:
        return False

    @property
    def stable_id(self) -> str:
        return (
            f"{self.observed_at.isoformat()}:"
            f"{self.source_name}:"
            f"{self.target.value}:"
            f"{self.outcome_kind.value}:"
            f"RECORD[{self.storage_record_reference}]:"
            f"EVIDENCE_SHA256[{self.evidence_digest}]"
        )


def _reason_for_blockers(
    blockers: tuple[
        PlanningAuditPersistenceOutcomeEvidenceBlocker,
        ...,
    ],
) -> PlanningAuditPersistenceOutcomeEvidenceReason:
    if not blockers:
        return PlanningAuditPersistenceOutcomeEvidenceReason.ACCEPTED

    if len(blockers) > 1:
        return PlanningAuditPersistenceOutcomeEvidenceReason.MULTIPLE_EVIDENCE_BLOCKERS

    return PlanningAuditPersistenceOutcomeEvidenceReason(blockers[0].value)


@dataclass(frozen=True, slots=True)
class _OutcomeEvidenceEvaluation:
    status: PlanningAuditPersistenceOutcomeEvidenceStatus
    reason: PlanningAuditPersistenceOutcomeEvidenceReason
    blockers: tuple[
        PlanningAuditPersistenceOutcomeEvidenceBlocker,
        ...,
    ]
    evidence: PlanningAuditPersistenceOutcomeEvidenceSnapshot | None


def _derive_assessment(
    outcome_contract: (PlanningAuditPersistenceOutcomeContractDecision),
    evidence: (PlanningAuditPersistenceOutcomeEvidenceSnapshot | None),
    policy: PlanningAuditPersistenceOutcomeEvidencePolicy,
) -> _OutcomeEvidenceEvaluation:
    if outcome_contract.is_blocked:
        return _OutcomeEvidenceEvaluation(
            status=(PlanningAuditPersistenceOutcomeEvidenceStatus.BLOCKED),
            reason=(PlanningAuditPersistenceOutcomeEvidenceReason.OUTCOME_CONTRACT_BLOCKED),
            blockers=(PlanningAuditPersistenceOutcomeEvidenceBlocker.OUTCOME_CONTRACT_BLOCKED,),
            evidence=None,
        )

    if evidence is None:
        raise PlanningAuditPersistenceOutcomeEvidenceError(
            PlanningAuditPersistenceOutcomeEvidenceErrorReason.INVALID_EVIDENCE_SNAPSHOT,
            "A created outcome contract requires an external evidence snapshot.",
        )

    contract = outcome_contract.contract_required
    blockers: list[PlanningAuditPersistenceOutcomeEvidenceBlocker] = []

    if policy.require_non_stale_evidence and evidence.observed_at < contract.observed_at:
        blockers.append(PlanningAuditPersistenceOutcomeEvidenceBlocker.EVIDENCE_STALE)

    if evidence.target != contract.target:
        blockers.append(PlanningAuditPersistenceOutcomeEvidenceBlocker.TARGET_MISMATCH)

    if evidence.outcome_kind not in contract.allowed_outcomes:
        blockers.append(PlanningAuditPersistenceOutcomeEvidenceBlocker.OUTCOME_NOT_ALLOWED)

    comparisons = (
        (
            evidence.request_id,
            contract.expected_request_id,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.REQUEST_ID_MISMATCH,
        ),
        (
            evidence.request_digest,
            contract.expected_request_digest,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.REQUEST_DIGEST_MISMATCH,
        ),
        (
            evidence.content_length_bytes,
            contract.expected_content_length_bytes,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.CONTENT_LENGTH_MISMATCH,
        ),
        (
            evidence.content_digest,
            contract.expected_content_digest,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.CONTENT_DIGEST_MISMATCH,
        ),
        (
            evidence.manifest_digest,
            contract.expected_manifest_digest,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.MANIFEST_DIGEST_MISMATCH,
        ),
        (
            evidence.idempotency_key,
            contract.expected_idempotency_key,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.IDEMPOTENCY_KEY_MISMATCH,
        ),
        (
            evidence.binding_receipt_digest,
            contract.expected_binding_receipt_digest,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.BINDING_RECEIPT_MISMATCH,
        ),
        (
            evidence.binding_id,
            contract.expected_binding_id,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.BINDING_ID_MISMATCH,
        ),
        (
            evidence.snapshot_id,
            contract.expected_snapshot_id,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.SNAPSHOT_ID_MISMATCH,
        ),
        (
            evidence.contract_id,
            contract.expected_contract_id,
            PlanningAuditPersistenceOutcomeEvidenceBlocker.CONTRACT_ID_MISMATCH,
        ),
    )

    for supplied, expected, blocker in comparisons:
        if supplied != expected:
            blockers.append(blocker)

    blocker_tuple = tuple(blockers)

    return _OutcomeEvidenceEvaluation(
        status=(
            PlanningAuditPersistenceOutcomeEvidenceStatus.BLOCKED
            if blocker_tuple
            else PlanningAuditPersistenceOutcomeEvidenceStatus.ACCEPTED
        ),
        reason=_reason_for_blockers(blocker_tuple),
        blockers=blocker_tuple,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditPersistenceOutcomeEvidenceDecision:
    """Validated read-only outcome-evidence assessment."""

    outcome_contract: PlanningAuditPersistenceOutcomeContractDecision
    policy: PlanningAuditPersistenceOutcomeEvidencePolicy
    status: PlanningAuditPersistenceOutcomeEvidenceStatus
    reason: PlanningAuditPersistenceOutcomeEvidenceReason
    blockers: tuple[
        PlanningAuditPersistenceOutcomeEvidenceBlocker,
        ...,
    ]
    evidence: PlanningAuditPersistenceOutcomeEvidenceSnapshot | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.outcome_contract,
            PlanningAuditPersistenceOutcomeContractDecision,
        ):
            raise ValueError(
                "outcome_contract must be a PlanningAuditPersistenceOutcomeContractDecision."
            )

        if not isinstance(
            self.policy,
            PlanningAuditPersistenceOutcomeEvidencePolicy,
        ):
            raise ValueError("policy must be a PlanningAuditPersistenceOutcomeEvidencePolicy.")

        try:
            status = PlanningAuditPersistenceOutcomeEvidenceStatus(self.status)
            reason = PlanningAuditPersistenceOutcomeEvidenceReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported outcome-evidence status or reason.") from error

        blockers = tuple(
            PlanningAuditPersistenceOutcomeEvidenceBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Outcome-evidence blockers cannot contain duplicates.")

        if self.evidence is not None and not isinstance(
            self.evidence,
            PlanningAuditPersistenceOutcomeEvidenceSnapshot,
        ):
            raise ValueError("evidence must be an outcome-evidence snapshot or None.")

        expected = _derive_assessment(
            self.outcome_contract,
            self.evidence,
            self.policy,
        )
        supplied = _OutcomeEvidenceEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            evidence=self.evidence,
        )

        if supplied != expected:
            raise ValueError(
                "Outcome-evidence assessment does not match its contract, evidence, and policy."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def contract(
        self,
    ) -> StrategyPlanningAuditPersistenceOutcomeContract | None:
        return self.outcome_contract.contract

    @property
    def broker_symbol(self) -> str:
        return self.outcome_contract.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.outcome_contract.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.outcome_contract.direction

    @property
    def side(self) -> StrategyOrderSide | None:
        if self.contract is None:
            return None

        return self.contract.side

    @property
    def is_accepted(self) -> bool:
        return self.status == PlanningAuditPersistenceOutcomeEvidenceStatus.ACCEPTED

    @property
    def is_blocked(self) -> bool:
        return not self.is_accepted

    @property
    def has_evidence(self) -> bool:
        return self.evidence is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def evidence_required(
        self,
    ) -> PlanningAuditPersistenceOutcomeEvidenceSnapshot:
        if self.evidence is None:
            raise ValueError("No persistence outcome-evidence snapshot is available.")

        return self.evidence

    @property
    def has_accepted_external_outcome(self) -> bool:
        return self.is_accepted

    @property
    def can_continue_to_outcome_receipt_design(
        self,
    ) -> bool:
        return self.is_accepted

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
        evidence_fragment = (
            self.evidence.stable_id if self.evidence is not None else "NO_OUTCOME_EVIDENCE"
        )

        return (
            f"{self.outcome_contract.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_OUTCOME_EVIDENCE:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}:"
            f"{evidence_fragment}"
        )


class StrategyPlanningAuditPersistenceOutcomeEvidenceGate:
    """
    Pure read-only outcome-evidence assessment gate.

    ACCEPTED permits later outcome-receipt design only.
    No evidence is fabricated and no adapter invocation,
    request submission, persistence, network, broker, MT5,
    or trading execution operation is performed.
    """

    def __init__(
        self,
        policy: (PlanningAuditPersistenceOutcomeEvidencePolicy | None) = None,
    ) -> None:
        selected_policy = policy or PlanningAuditPersistenceOutcomeEvidencePolicy()

        if not isinstance(
            selected_policy,
            PlanningAuditPersistenceOutcomeEvidencePolicy,
        ):
            raise ValueError("policy must be a PlanningAuditPersistenceOutcomeEvidencePolicy.")

        self._policy = selected_policy

    @property
    def policy(
        self,
    ) -> PlanningAuditPersistenceOutcomeEvidencePolicy:
        return self._policy

    def assess(
        self,
        outcome_contract: (PlanningAuditPersistenceOutcomeContractDecision),
        evidence: (PlanningAuditPersistenceOutcomeEvidenceSnapshot | None) = None,
    ) -> PlanningAuditPersistenceOutcomeEvidenceDecision:
        if not isinstance(
            outcome_contract,
            PlanningAuditPersistenceOutcomeContractDecision,
        ):
            raise PlanningAuditPersistenceOutcomeEvidenceError(
                PlanningAuditPersistenceOutcomeEvidenceErrorReason.INVALID_OUTCOME_CONTRACT_DECISION,
                "outcome_contract must be a PlanningAuditPersistenceOutcomeContractDecision.",
            )

        if evidence is not None and not isinstance(
            evidence,
            PlanningAuditPersistenceOutcomeEvidenceSnapshot,
        ):
            raise PlanningAuditPersistenceOutcomeEvidenceError(
                PlanningAuditPersistenceOutcomeEvidenceErrorReason.INVALID_EVIDENCE_SNAPSHOT,
                "evidence must be an outcome-evidence snapshot or None.",
            )

        evaluation = _derive_assessment(
            outcome_contract,
            evidence,
            self._policy,
        )

        return PlanningAuditPersistenceOutcomeEvidenceDecision(
            outcome_contract=outcome_contract,
            policy=self._policy,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            evidence=evaluation.evidence,
        )

    def evaluate(
        self,
        outcome_contract: (PlanningAuditPersistenceOutcomeContractDecision),
        evidence: (PlanningAuditPersistenceOutcomeEvidenceSnapshot | None) = None,
    ) -> PlanningAuditPersistenceOutcomeEvidenceDecision:
        """Compatibility alias for assess()."""

        return self.assess(
            outcome_contract,
            evidence,
        )

    def check(
        self,
        outcome_contract: (PlanningAuditPersistenceOutcomeContractDecision),
        evidence: (PlanningAuditPersistenceOutcomeEvidenceSnapshot | None) = None,
    ) -> PlanningAuditPersistenceOutcomeEvidenceDecision:
        """Compatibility alias for assess()."""

        return self.assess(
            outcome_contract,
            evidence,
        )


def assess_planning_audit_persistence_outcome_evidence(
    outcome_contract: (PlanningAuditPersistenceOutcomeContractDecision),
    evidence: (PlanningAuditPersistenceOutcomeEvidenceSnapshot | None) = None,
    policy: (PlanningAuditPersistenceOutcomeEvidencePolicy | None) = None,
) -> PlanningAuditPersistenceOutcomeEvidenceDecision:
    return StrategyPlanningAuditPersistenceOutcomeEvidenceGate(policy=policy).assess(
        outcome_contract,
        evidence,
    )


def create_planning_audit_persistence_outcome_evidence(
    **kwargs: object,
) -> PlanningAuditPersistenceOutcomeEvidenceSnapshot:
    return PlanningAuditPersistenceOutcomeEvidenceSnapshot.create(**kwargs)


AuditPersistenceOutcomeEvidenceBlocker = PlanningAuditPersistenceOutcomeEvidenceBlocker
AuditPersistenceOutcomeEvidenceDecision = PlanningAuditPersistenceOutcomeEvidenceDecision
AuditPersistenceOutcomeEvidenceGate = StrategyPlanningAuditPersistenceOutcomeEvidenceGate
AuditPersistenceOutcomeEvidencePolicy = PlanningAuditPersistenceOutcomeEvidencePolicy
AuditPersistenceOutcomeEvidenceReason = PlanningAuditPersistenceOutcomeEvidenceReason
AuditPersistenceOutcomeEvidenceSnapshot = PlanningAuditPersistenceOutcomeEvidenceSnapshot
AuditPersistenceOutcomeEvidenceSourceMode = PlanningAuditPersistenceOutcomeEvidenceSourceMode
AuditPersistenceOutcomeEvidenceStatus = PlanningAuditPersistenceOutcomeEvidenceStatus
StrategyAuditPersistenceOutcomeEvidenceGate = StrategyPlanningAuditPersistenceOutcomeEvidenceGate
