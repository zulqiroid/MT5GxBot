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
from app.strategy.planning_audit_persistence_request_verification import (
    PlanningAuditPersistenceRequestVerificationDecision,
    StrategyPlanningAuditPersistenceRequestVerificationReceipt,
)
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageTarget,
)

PLANNING_AUDIT_PERSISTENCE_OUTCOME_CONTRACT_SCHEMA_VERSION = "1.0"


class PlanningAuditPersistenceOutcomeKind(str, Enum):
    CREATED = "CREATED"
    EXISTING = "EXISTING"


_ALLOWED_OUTCOMES = (
    PlanningAuditPersistenceOutcomeKind.CREATED,
    PlanningAuditPersistenceOutcomeKind.EXISTING,
)


class PlanningAuditPersistenceConflictPolicy(str, Enum):
    REJECT_DIGEST_MISMATCH = "REJECT_DIGEST_MISMATCH"


class PlanningAuditPersistenceOutcomeEvidenceMode(str, Enum):
    REQUIRE_VERIFIED_RESULT = "REQUIRE_VERIFIED_RESULT"


class PlanningAuditPersistenceOutcomeContractStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditPersistenceOutcomeContractReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    REQUEST_VERIFICATION_BLOCKED = "REQUEST_VERIFICATION_BLOCKED"


class PlanningAuditPersistenceOutcomeContractBlocker(
    str,
    Enum,
):
    REQUEST_VERIFICATION_BLOCKED = "REQUEST_VERIFICATION_BLOCKED"


class PlanningAuditPersistenceOutcomeContractErrorReason(
    str,
    Enum,
):
    INVALID_REQUEST_VERIFICATION_DECISION = "INVALID_REQUEST_VERIFICATION_DECISION"


class PlanningAuditPersistenceOutcomeContractError(RuntimeError):
    """Structured analytical outcome-contract failure."""

    def __init__(
        self,
        reason: (PlanningAuditPersistenceOutcomeContractErrorReason),
        message: str,
    ) -> None:
        self.reason = PlanningAuditPersistenceOutcomeContractErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Planning-audit persistence outcome-contract "
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


def _canonical_contract_payload(
    *,
    schema_version: str,
    target: PlanningAuditStorageTarget,
    allowed_outcomes: tuple[
        PlanningAuditPersistenceOutcomeKind,
        ...,
    ],
    conflict_policy: PlanningAuditPersistenceConflictPolicy,
    evidence_mode: PlanningAuditPersistenceOutcomeEvidenceMode,
    expected_request_id: str,
    expected_request_digest: str,
    expected_content_length_bytes: int,
    expected_content_digest: str,
    expected_manifest_digest: str,
    expected_idempotency_key: str,
    expected_binding_receipt_digest: str,
    expected_binding_id: str,
    expected_snapshot_id: str,
    expected_contract_id: str,
) -> str:
    outcome_fragment = ",".join(outcome.value for outcome in allowed_outcomes)

    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"TARGET={target.value}",
            f"ALLOWED_OUTCOMES={outcome_fragment}",
            f"CONFLICT_POLICY={conflict_policy.value}",
            f"EVIDENCE_MODE={evidence_mode.value}",
            f"EXPECTED_REQUEST_ID={expected_request_id}",
            (f"EXPECTED_REQUEST_DIGEST={expected_request_digest}"),
            (f"EXPECTED_CONTENT_LENGTH_BYTES={expected_content_length_bytes}"),
            (f"EXPECTED_CONTENT_DIGEST={expected_content_digest}"),
            (f"EXPECTED_MANIFEST_DIGEST={expected_manifest_digest}"),
            (f"EXPECTED_IDEMPOTENCY_KEY={expected_idempotency_key}"),
            (f"EXPECTED_BINDING_RECEIPT_DIGEST={expected_binding_receipt_digest}"),
            f"EXPECTED_BINDING_ID={expected_binding_id}",
            f"EXPECTED_SNAPSHOT_ID={expected_snapshot_id}",
            f"EXPECTED_CONTRACT_ID={expected_contract_id}",
        )
    )


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditPersistenceOutcomeContract:
    """
    Immutable contract for evaluating future persistence
    outcome evidence.

    It specifies valid CREATED or EXISTING outcomes and
    requires exact digest and identity matching. It does
    not create an outcome, invoke an adapter, submit a
    request, or write to storage.
    """

    request_verification: PlanningAuditPersistenceRequestVerificationDecision
    schema_version: str
    target: PlanningAuditStorageTarget
    allowed_outcomes: tuple[
        PlanningAuditPersistenceOutcomeKind,
        ...,
    ]
    conflict_policy: PlanningAuditPersistenceConflictPolicy
    evidence_mode: PlanningAuditPersistenceOutcomeEvidenceMode
    expected_request_id: str
    expected_request_digest: str
    expected_content_length_bytes: int
    expected_content_digest: str
    expected_manifest_digest: str
    expected_idempotency_key: str
    expected_binding_receipt_digest: str
    expected_binding_id: str
    expected_snapshot_id: str
    expected_contract_id: str
    outcome_contract_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.request_verification,
            PlanningAuditPersistenceRequestVerificationDecision,
        ):
            raise ValueError(
                "request_verification must be a "
                "PlanningAuditPersistenceRequestVerificationDecision."
            )

        if not self.request_verification.is_verified:
            raise ValueError(
                "An outcome contract requires a verified persistence-request decision."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PLANNING_AUDIT_PERSISTENCE_OUTCOME_CONTRACT_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current persistence outcome-contract schema."
            )

        if not isinstance(
            self.target,
            PlanningAuditStorageTarget,
        ):
            raise ValueError("target must be a PlanningAuditStorageTarget member.")

        if not isinstance(self.allowed_outcomes, tuple):
            raise ValueError("allowed_outcomes must be a tuple.")

        if not all(
            isinstance(
                outcome,
                PlanningAuditPersistenceOutcomeKind,
            )
            for outcome in self.allowed_outcomes
        ):
            raise ValueError(
                "allowed_outcomes must contain PlanningAuditPersistenceOutcomeKind members."
            )

        if len(set(self.allowed_outcomes)) != len(self.allowed_outcomes):
            raise ValueError("allowed_outcomes cannot contain duplicates.")

        if self.allowed_outcomes != _ALLOWED_OUTCOMES:
            raise ValueError(
                "allowed_outcomes must contain CREATED and EXISTING in deterministic order."
            )

        if not isinstance(
            self.conflict_policy,
            PlanningAuditPersistenceConflictPolicy,
        ):
            raise ValueError(
                "conflict_policy must be a PlanningAuditPersistenceConflictPolicy member."
            )

        if self.conflict_policy != PlanningAuditPersistenceConflictPolicy.REJECT_DIGEST_MISMATCH:
            raise ValueError("Outcome contract must reject digest mismatches.")

        if not isinstance(
            self.evidence_mode,
            PlanningAuditPersistenceOutcomeEvidenceMode,
        ):
            raise ValueError(
                "evidence_mode must be a PlanningAuditPersistenceOutcomeEvidenceMode member."
            )

        if (
            self.evidence_mode
            != PlanningAuditPersistenceOutcomeEvidenceMode.REQUIRE_VERIFIED_RESULT
        ):
            raise ValueError("Outcome contract must require verified result evidence.")

        expected_request_id = _non_empty_string(
            self.expected_request_id,
            "expected_request_id",
        )
        expected_request_digest = _non_empty_string(
            self.expected_request_digest,
            "expected_request_digest",
        )
        expected_content_length = _positive_integer(
            self.expected_content_length_bytes,
            "expected_content_length_bytes",
        )
        expected_content_digest = _non_empty_string(
            self.expected_content_digest,
            "expected_content_digest",
        )
        expected_manifest_digest = _non_empty_string(
            self.expected_manifest_digest,
            "expected_manifest_digest",
        )
        expected_idempotency_key = _non_empty_string(
            self.expected_idempotency_key,
            "expected_idempotency_key",
        )
        expected_binding_receipt_digest = _non_empty_string(
            self.expected_binding_receipt_digest,
            "expected_binding_receipt_digest",
        )
        expected_binding_id = _non_empty_string(
            self.expected_binding_id,
            "expected_binding_id",
        )
        expected_snapshot_id = _non_empty_string(
            self.expected_snapshot_id,
            "expected_snapshot_id",
        )
        expected_contract_id = _non_empty_string(
            self.expected_contract_id,
            "expected_contract_id",
        )
        outcome_contract_digest = _non_empty_string(
            self.outcome_contract_digest,
            "outcome_contract_digest",
        )

        for field_name, digest in (
            (
                "expected_request_digest",
                expected_request_digest,
            ),
            (
                "expected_content_digest",
                expected_content_digest,
            ),
            (
                "expected_manifest_digest",
                expected_manifest_digest,
            ),
            (
                "expected_idempotency_key",
                expected_idempotency_key,
            ),
            (
                "expected_binding_receipt_digest",
                expected_binding_receipt_digest,
            ),
            (
                "outcome_contract_digest",
                outcome_contract_digest,
            ),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        verification_receipt = self.request_verification.receipt_required
        request = verification_receipt.request

        if self.target != request.target:
            raise ValueError("target must match the verified persistence request.")

        if expected_request_id != request.request_id:
            raise ValueError("expected_request_id must match the persistence request.")

        if expected_request_id != verification_receipt.verified_request_id:
            raise ValueError("expected_request_id must match the request-verification receipt.")

        if expected_request_digest != request.request_digest:
            raise ValueError("expected_request_digest must match the persistence request.")

        if expected_request_digest != verification_receipt.verified_request_digest:
            raise ValueError("expected_request_digest must match the request-verification receipt.")

        if expected_content_length != request.content_length_bytes:
            raise ValueError("expected_content_length_bytes must match the persistence request.")

        if expected_content_length != verification_receipt.verified_content_length_bytes:
            raise ValueError(
                "expected_content_length_bytes must match the request-verification receipt."
            )

        if expected_content_digest != request.content_digest:
            raise ValueError("expected_content_digest must match the persistence request.")

        if expected_content_digest != verification_receipt.verified_content_digest:
            raise ValueError("expected_content_digest must match the request-verification receipt.")

        if expected_manifest_digest != request.manifest_digest:
            raise ValueError("expected_manifest_digest must match the persistence request.")

        if expected_manifest_digest != verification_receipt.verified_manifest_digest:
            raise ValueError(
                "expected_manifest_digest must match the request-verification receipt."
            )

        if expected_idempotency_key != request.idempotency_key:
            raise ValueError("expected_idempotency_key must match the persistence request.")

        if expected_idempotency_key != verification_receipt.verified_idempotency_key:
            raise ValueError(
                "expected_idempotency_key must match the request-verification receipt."
            )

        if expected_binding_receipt_digest != request.binding_verification_receipt_digest:
            raise ValueError("expected_binding_receipt_digest must match the persistence request.")

        if expected_binding_receipt_digest != verification_receipt.verified_binding_receipt_digest:
            raise ValueError(
                "expected_binding_receipt_digest must match the request-verification receipt."
            )

        if expected_binding_id != request.binding_id:
            raise ValueError("expected_binding_id must match the persistence request.")

        if expected_binding_id != verification_receipt.verified_binding_id:
            raise ValueError("expected_binding_id must match the request-verification receipt.")

        if expected_snapshot_id != request.snapshot_id:
            raise ValueError("expected_snapshot_id must match the persistence request.")

        if expected_snapshot_id != verification_receipt.verified_snapshot_id:
            raise ValueError("expected_snapshot_id must match the request-verification receipt.")

        if expected_contract_id != request.contract_id:
            raise ValueError("expected_contract_id must match the persistence request.")

        if expected_contract_id != verification_receipt.verified_contract_id:
            raise ValueError("expected_contract_id must match the request-verification receipt.")

        if not verification_receipt.is_verified:
            raise ValueError("Outcome contract requires a verified request-verification receipt.")

        if not verification_receipt.is_tamper_evident:
            raise ValueError("Outcome contract requires tamper-evident request verification.")

        if not (verification_receipt.can_continue_to_storage_outcome_design):
            raise ValueError("Request verification does not permit storage-outcome design.")

        if verification_receipt.has_adapter_instance:
            raise ValueError("Outcome contract cannot contain an adapter instance.")

        if verification_receipt.request_submission_authorized:
            raise ValueError("Outcome contract cannot inherit request submission authorization.")

        if verification_receipt.adapter_invocation_authorized:
            raise ValueError("Outcome contract cannot inherit adapter invocation authorization.")

        if verification_receipt.storage_write_authorized:
            raise ValueError("Outcome contract cannot inherit storage write authorization.")

        if verification_receipt.is_persisted:
            raise ValueError("Outcome contract cannot assume prior persistence.")

        if verification_receipt.can_write_storage:
            raise ValueError("Outcome contract cannot write storage.")

        if verification_receipt.can_write_network:
            raise ValueError("Outcome contract cannot write to the network.")

        if verification_receipt.execution_authorized:
            raise ValueError("Outcome contract cannot contain trading execution authorization.")

        if verification_receipt.has_broker_request:
            raise ValueError("Outcome contract cannot contain a broker request.")

        if verification_receipt.can_submit_order:
            raise ValueError("Outcome contract cannot submit an order.")

        if verification_receipt.is_executable:
            raise ValueError("Outcome contract cannot be executable.")

        canonical_payload = _canonical_contract_payload(
            schema_version=schema_version,
            target=self.target,
            allowed_outcomes=self.allowed_outcomes,
            conflict_policy=self.conflict_policy,
            evidence_mode=self.evidence_mode,
            expected_request_id=expected_request_id,
            expected_request_digest=(expected_request_digest),
            expected_content_length_bytes=(expected_content_length),
            expected_content_digest=(expected_content_digest),
            expected_manifest_digest=(expected_manifest_digest),
            expected_idempotency_key=(expected_idempotency_key),
            expected_binding_receipt_digest=(expected_binding_receipt_digest),
            expected_binding_id=expected_binding_id,
            expected_snapshot_id=expected_snapshot_id,
            expected_contract_id=expected_contract_id,
        )
        calculated_contract_digest = _sha256_digest(canonical_payload)

        if outcome_contract_digest != calculated_contract_digest:
            raise ValueError(
                "outcome_contract_digest does not match the canonical outcome-contract payload."
            )

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "expected_request_id",
            expected_request_id,
        )
        object.__setattr__(
            self,
            "expected_request_digest",
            expected_request_digest,
        )
        object.__setattr__(
            self,
            "expected_content_length_bytes",
            expected_content_length,
        )
        object.__setattr__(
            self,
            "expected_content_digest",
            expected_content_digest,
        )
        object.__setattr__(
            self,
            "expected_manifest_digest",
            expected_manifest_digest,
        )
        object.__setattr__(
            self,
            "expected_idempotency_key",
            expected_idempotency_key,
        )
        object.__setattr__(
            self,
            "expected_binding_receipt_digest",
            expected_binding_receipt_digest,
        )
        object.__setattr__(
            self,
            "expected_binding_id",
            expected_binding_id,
        )
        object.__setattr__(
            self,
            "expected_snapshot_id",
            expected_snapshot_id,
        )
        object.__setattr__(
            self,
            "expected_contract_id",
            expected_contract_id,
        )
        object.__setattr__(
            self,
            "outcome_contract_digest",
            outcome_contract_digest,
        )

    @property
    def verification_receipt(
        self,
    ) -> StrategyPlanningAuditPersistenceRequestVerificationReceipt:
        return self.request_verification.receipt_required

    @property
    def request(self):
        return self.verification_receipt.request

    @property
    def broker_symbol(self) -> str:
        return self.request.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.request.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.request.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.request.side

    @property
    def canonical_payload(self) -> str:
        return _canonical_contract_payload(
            schema_version=self.schema_version,
            target=self.target,
            allowed_outcomes=self.allowed_outcomes,
            conflict_policy=self.conflict_policy,
            evidence_mode=self.evidence_mode,
            expected_request_id=self.expected_request_id,
            expected_request_digest=(self.expected_request_digest),
            expected_content_length_bytes=(self.expected_content_length_bytes),
            expected_content_digest=(self.expected_content_digest),
            expected_manifest_digest=(self.expected_manifest_digest),
            expected_idempotency_key=(self.expected_idempotency_key),
            expected_binding_receipt_digest=(self.expected_binding_receipt_digest),
            expected_binding_id=self.expected_binding_id,
            expected_snapshot_id=self.expected_snapshot_id,
            expected_contract_id=self.expected_contract_id,
        )

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def allowed_outcome_count(self) -> int:
        return len(self.allowed_outcomes)

    @property
    def allows_created(self) -> bool:
        return PlanningAuditPersistenceOutcomeKind.CREATED in self.allowed_outcomes

    @property
    def allows_existing(self) -> bool:
        return PlanningAuditPersistenceOutcomeKind.EXISTING in self.allowed_outcomes

    @property
    def requires_digest_match(self) -> bool:
        return True

    @property
    def requires_verified_result(self) -> bool:
        return True

    @property
    def is_specification_only(self) -> bool:
        return True

    @property
    def is_outcome_contract_ready(self) -> bool:
        return True

    @property
    def can_continue_to_outcome_evidence_design(
        self,
    ) -> bool:
        return True

    @property
    def has_outcome_evidence(self) -> bool:
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
            f"AUDIT_PERSISTENCE_OUTCOME_CONTRACT:"
            f"{self.target.value}:"
            f"{self.conflict_policy.value}:"
            f"{self.evidence_mode.value}:"
            f"REQUEST[{self.expected_request_id}]:"
            f"CONTRACT_SHA256["
            f"{self.outcome_contract_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.request_verification.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_OUTCOME_CONTRACT:"
            f"{self.contract_id}"
        )


@dataclass(frozen=True, slots=True)
class _PersistenceOutcomeContractEvaluation:
    status: PlanningAuditPersistenceOutcomeContractStatus
    reason: PlanningAuditPersistenceOutcomeContractReason
    blockers: tuple[
        PlanningAuditPersistenceOutcomeContractBlocker,
        ...,
    ]
    contract: StrategyPlanningAuditPersistenceOutcomeContract | None


def _derive_contract(
    request_verification: (PlanningAuditPersistenceRequestVerificationDecision),
) -> _PersistenceOutcomeContractEvaluation:
    if request_verification.is_blocked:
        return _PersistenceOutcomeContractEvaluation(
            status=(PlanningAuditPersistenceOutcomeContractStatus.BLOCKED),
            reason=(PlanningAuditPersistenceOutcomeContractReason.REQUEST_VERIFICATION_BLOCKED),
            blockers=(PlanningAuditPersistenceOutcomeContractBlocker.REQUEST_VERIFICATION_BLOCKED,),
            contract=None,
        )

    verification_receipt = request_verification.receipt_required
    request = verification_receipt.request

    canonical_payload = _canonical_contract_payload(
        schema_version=(PLANNING_AUDIT_PERSISTENCE_OUTCOME_CONTRACT_SCHEMA_VERSION),
        target=request.target,
        allowed_outcomes=_ALLOWED_OUTCOMES,
        conflict_policy=(PlanningAuditPersistenceConflictPolicy.REJECT_DIGEST_MISMATCH),
        evidence_mode=(PlanningAuditPersistenceOutcomeEvidenceMode.REQUIRE_VERIFIED_RESULT),
        expected_request_id=request.request_id,
        expected_request_digest=request.request_digest,
        expected_content_length_bytes=(request.content_length_bytes),
        expected_content_digest=request.content_digest,
        expected_manifest_digest=request.manifest_digest,
        expected_idempotency_key=request.idempotency_key,
        expected_binding_receipt_digest=(request.binding_verification_receipt_digest),
        expected_binding_id=request.binding_id,
        expected_snapshot_id=request.snapshot_id,
        expected_contract_id=request.contract_id,
    )

    contract = StrategyPlanningAuditPersistenceOutcomeContract(
        request_verification=request_verification,
        schema_version=(PLANNING_AUDIT_PERSISTENCE_OUTCOME_CONTRACT_SCHEMA_VERSION),
        target=request.target,
        allowed_outcomes=_ALLOWED_OUTCOMES,
        conflict_policy=(PlanningAuditPersistenceConflictPolicy.REJECT_DIGEST_MISMATCH),
        evidence_mode=(PlanningAuditPersistenceOutcomeEvidenceMode.REQUIRE_VERIFIED_RESULT),
        expected_request_id=request.request_id,
        expected_request_digest=request.request_digest,
        expected_content_length_bytes=(request.content_length_bytes),
        expected_content_digest=request.content_digest,
        expected_manifest_digest=request.manifest_digest,
        expected_idempotency_key=request.idempotency_key,
        expected_binding_receipt_digest=(request.binding_verification_receipt_digest),
        expected_binding_id=request.binding_id,
        expected_snapshot_id=request.snapshot_id,
        expected_contract_id=request.contract_id,
        outcome_contract_digest=_sha256_digest(canonical_payload),
    )

    return _PersistenceOutcomeContractEvaluation(
        status=(PlanningAuditPersistenceOutcomeContractStatus.CREATED),
        reason=(PlanningAuditPersistenceOutcomeContractReason.CREATED),
        blockers=(),
        contract=contract,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditPersistenceOutcomeContractDecision:
    """Validated analytical outcome-contract result."""

    request_verification: PlanningAuditPersistenceRequestVerificationDecision
    status: PlanningAuditPersistenceOutcomeContractStatus
    reason: PlanningAuditPersistenceOutcomeContractReason
    blockers: tuple[
        PlanningAuditPersistenceOutcomeContractBlocker,
        ...,
    ]
    contract: StrategyPlanningAuditPersistenceOutcomeContract | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.request_verification,
            PlanningAuditPersistenceRequestVerificationDecision,
        ):
            raise ValueError(
                "request_verification must be a "
                "PlanningAuditPersistenceRequestVerificationDecision."
            )

        try:
            status = PlanningAuditPersistenceOutcomeContractStatus(self.status)
            reason = PlanningAuditPersistenceOutcomeContractReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Unsupported persistence outcome-contract status or reason."
            ) from error

        blockers = tuple(
            PlanningAuditPersistenceOutcomeContractBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Outcome-contract blockers cannot contain duplicates.")

        if self.contract is not None and not isinstance(
            self.contract,
            StrategyPlanningAuditPersistenceOutcomeContract,
        ):
            raise ValueError(
                "contract must be a StrategyPlanningAuditPersistenceOutcomeContract or None."
            )

        expected = _derive_contract(self.request_verification)
        supplied = _PersistenceOutcomeContractEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            contract=self.contract,
        )

        if supplied != expected:
            raise ValueError(
                "Persistence outcome-contract result does "
                "not match its request-verification "
                "decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.request_verification.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.request_verification.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.request_verification.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditPersistenceOutcomeContractStatus.CREATED

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
    ) -> StrategyPlanningAuditPersistenceOutcomeContract:
        if self.contract is None:
            raise ValueError("No planning-audit persistence outcome contract was created.")

        return self.contract

    @property
    def can_continue_to_outcome_evidence_design(
        self,
    ) -> bool:
        return self.is_created

    @property
    def has_outcome_evidence(self) -> bool:
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
            f"{self.request_verification.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_OUTCOME_"
            f"CONTRACT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditPersistenceOutcomeContractFactory:
    """
    Pure factory for persistence outcome contracts.

    CREATED permits later outcome-evidence design only.
    It creates no outcome and performs or authorizes no
    adapter invocation, request submission, persistence,
    network, broker, MT5, or trading execution operation.
    """

    def generate(
        self,
        request_verification: (PlanningAuditPersistenceRequestVerificationDecision),
    ) -> PlanningAuditPersistenceOutcomeContractDecision:
        if not isinstance(
            request_verification,
            PlanningAuditPersistenceRequestVerificationDecision,
        ):
            raise PlanningAuditPersistenceOutcomeContractError(
                PlanningAuditPersistenceOutcomeContractErrorReason.INVALID_REQUEST_VERIFICATION_DECISION,
                "request_verification must be a "
                "PlanningAuditPersistenceRequestVerificationDecision.",
            )

        evaluation = _derive_contract(request_verification)

        return PlanningAuditPersistenceOutcomeContractDecision(
            request_verification=request_verification,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            contract=evaluation.contract,
        )

    def build(
        self,
        request_verification: (PlanningAuditPersistenceRequestVerificationDecision),
    ) -> PlanningAuditPersistenceOutcomeContractDecision:
        """Compatibility alias for generate()."""

        return self.generate(request_verification)

    def evaluate(
        self,
        request_verification: (PlanningAuditPersistenceRequestVerificationDecision),
    ) -> PlanningAuditPersistenceOutcomeContractDecision:
        """Compatibility alias for generate()."""

        return self.generate(request_verification)


def generate_planning_audit_persistence_outcome_contract(
    request_verification: (PlanningAuditPersistenceRequestVerificationDecision),
) -> PlanningAuditPersistenceOutcomeContractDecision:
    return StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(request_verification)


AuditPersistenceConflictPolicy = PlanningAuditPersistenceConflictPolicy
AuditPersistenceOutcomeContract = StrategyPlanningAuditPersistenceOutcomeContract
AuditPersistenceOutcomeContractDecision = PlanningAuditPersistenceOutcomeContractDecision
AuditPersistenceOutcomeContractFactory = StrategyPlanningAuditPersistenceOutcomeContractFactory
AuditPersistenceOutcomeEvidenceMode = PlanningAuditPersistenceOutcomeEvidenceMode
AuditPersistenceOutcomeKind = PlanningAuditPersistenceOutcomeKind
PlanningAuditPersistenceOutcomeContract = StrategyPlanningAuditPersistenceOutcomeContract
PlanningAuditPersistenceOutcomeContractFactory = (
    StrategyPlanningAuditPersistenceOutcomeContractFactory
)
StrategyAuditPersistenceOutcomeContract = StrategyPlanningAuditPersistenceOutcomeContract
StrategyAuditPersistenceOutcomeContractFactory = (
    StrategyPlanningAuditPersistenceOutcomeContractFactory
)
