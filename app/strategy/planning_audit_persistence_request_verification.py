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
from app.strategy.planning_audit_persistence_request import (
    PlanningAuditPersistenceInvocationMode,
    PlanningAuditPersistenceRequestDecision,
    PlanningAuditPersistenceRequestMode,
    StrategyPlanningAuditPersistenceRequestBlueprint,
)

PLANNING_AUDIT_PERSISTENCE_REQUEST_VERIFICATION_SCHEMA_VERSION = "1.0"


class PlanningAuditPersistenceRequestVerificationCheck(
    str,
    Enum,
):
    PREPARE_ONLY_MODE = "PREPARE_ONLY_MODE"
    INVOCATION_DISABLED = "INVOCATION_DISABLED"
    REQUEST_DIGEST_MATCH = "REQUEST_DIGEST_MATCH"
    UTF8_LENGTH_MATCH = "UTF8_LENGTH_MATCH"
    CONTENT_DIGEST_MATCH = "CONTENT_DIGEST_MATCH"
    MANIFEST_DIGEST_MATCH = "MANIFEST_DIGEST_MATCH"
    IDEMPOTENCY_KEY_MATCH = "IDEMPOTENCY_KEY_MATCH"
    BINDING_RECEIPT_MATCH = "BINDING_RECEIPT_MATCH"
    IDENTITY_LINEAGE_MATCH = "IDENTITY_LINEAGE_MATCH"
    NO_SUBMISSION_SURFACE = "NO_SUBMISSION_SURFACE"


_REQUIRED_CHECKS = (
    PlanningAuditPersistenceRequestVerificationCheck.PREPARE_ONLY_MODE,
    PlanningAuditPersistenceRequestVerificationCheck.INVOCATION_DISABLED,
    PlanningAuditPersistenceRequestVerificationCheck.REQUEST_DIGEST_MATCH,
    PlanningAuditPersistenceRequestVerificationCheck.UTF8_LENGTH_MATCH,
    PlanningAuditPersistenceRequestVerificationCheck.CONTENT_DIGEST_MATCH,
    PlanningAuditPersistenceRequestVerificationCheck.MANIFEST_DIGEST_MATCH,
    PlanningAuditPersistenceRequestVerificationCheck.IDEMPOTENCY_KEY_MATCH,
    PlanningAuditPersistenceRequestVerificationCheck.BINDING_RECEIPT_MATCH,
    PlanningAuditPersistenceRequestVerificationCheck.IDENTITY_LINEAGE_MATCH,
    PlanningAuditPersistenceRequestVerificationCheck.NO_SUBMISSION_SURFACE,
)


class PlanningAuditPersistenceRequestVerificationStatus(
    str,
    Enum,
):
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"


class PlanningAuditPersistenceRequestVerificationReason(
    str,
    Enum,
):
    VERIFIED = "VERIFIED"
    PERSISTENCE_REQUEST_BLOCKED = "PERSISTENCE_REQUEST_BLOCKED"


class PlanningAuditPersistenceRequestVerificationBlocker(
    str,
    Enum,
):
    PERSISTENCE_REQUEST_BLOCKED = "PERSISTENCE_REQUEST_BLOCKED"


class PlanningAuditPersistenceRequestVerificationErrorReason(
    str,
    Enum,
):
    INVALID_PERSISTENCE_REQUEST_DECISION = "INVALID_PERSISTENCE_REQUEST_DECISION"


class PlanningAuditPersistenceRequestVerificationError(RuntimeError):
    """Structured persistence-request verification failure."""

    def __init__(
        self,
        reason: (PlanningAuditPersistenceRequestVerificationErrorReason),
        message: str,
    ) -> None:
        self.reason = PlanningAuditPersistenceRequestVerificationErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Planning-audit persistence-request "
            f"verification error [{self.reason.value}]: "
            f"{self.message}"
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


def _canonical_verification_payload(
    *,
    schema_version: str,
    checks: tuple[
        PlanningAuditPersistenceRequestVerificationCheck,
        ...,
    ],
    request_stable_id: str,
    verified_request_id: str,
    verified_request_digest: str,
    verified_content_length_bytes: int,
    verified_content_digest: str,
    verified_manifest_digest: str,
    verified_idempotency_key: str,
    verified_binding_receipt_digest: str,
    verified_binding_id: str,
    verified_snapshot_id: str,
    verified_contract_id: str,
) -> str:
    checks_fragment = ",".join(check.value for check in checks)

    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"CHECKS={checks_fragment}",
            f"REQUEST_STABLE_ID={request_stable_id}",
            f"REQUEST_ID={verified_request_id}",
            f"REQUEST_DIGEST={verified_request_digest}",
            (f"CONTENT_LENGTH_BYTES={verified_content_length_bytes}"),
            f"CONTENT_DIGEST={verified_content_digest}",
            f"MANIFEST_DIGEST={verified_manifest_digest}",
            f"IDEMPOTENCY_KEY={verified_idempotency_key}",
            (f"BINDING_RECEIPT_DIGEST={verified_binding_receipt_digest}"),
            f"BINDING_ID={verified_binding_id}",
            f"SNAPSHOT_ID={verified_snapshot_id}",
            f"CONTRACT_ID={verified_contract_id}",
        )
    )


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditPersistenceRequestVerificationReceipt:
    """
    Immutable independent verification of a persistence
    request blueprint.

    The receipt validates request digest, payload length,
    audit lineage, prepare-only mode, and the no-submission
    boundary. It performs no request submission, adapter
    invocation, persistence, network, broker, MT5, or
    trading execution operation.
    """

    persistence_request: PlanningAuditPersistenceRequestDecision
    schema_version: str
    checks: tuple[
        PlanningAuditPersistenceRequestVerificationCheck,
        ...,
    ]
    verified_request_id: str
    verified_request_digest: str
    verified_content_length_bytes: int
    verified_content_digest: str
    verified_manifest_digest: str
    verified_idempotency_key: str
    verified_binding_receipt_digest: str
    verified_binding_id: str
    verified_snapshot_id: str
    verified_contract_id: str
    verification_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.persistence_request,
            PlanningAuditPersistenceRequestDecision,
        ):
            raise ValueError(
                "persistence_request must be a PlanningAuditPersistenceRequestDecision."
            )

        if not self.persistence_request.is_created:
            raise ValueError(
                "A request verification receipt requires a created persistence request."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PLANNING_AUDIT_PERSISTENCE_REQUEST_VERIFICATION_SCHEMA_VERSION):
            raise ValueError("schema_version must match the current request-verification schema.")

        if not isinstance(self.checks, tuple):
            raise ValueError("checks must be a tuple.")

        if not all(
            isinstance(
                check,
                PlanningAuditPersistenceRequestVerificationCheck,
            )
            for check in self.checks
        ):
            raise ValueError("checks must contain persistence-request verification check members.")

        if len(set(self.checks)) != len(self.checks):
            raise ValueError("Request-verification checks cannot contain duplicates.")

        if self.checks != _REQUIRED_CHECKS:
            raise ValueError(
                "Request-verification checks must contain "
                "every required check in deterministic "
                "order."
            )

        verified_request_id = _non_empty_string(
            self.verified_request_id,
            "verified_request_id",
        )
        verified_request_digest = _non_empty_string(
            self.verified_request_digest,
            "verified_request_digest",
        )
        verified_content_length = _positive_integer(
            self.verified_content_length_bytes,
            "verified_content_length_bytes",
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
        verified_binding_receipt_digest = _non_empty_string(
            self.verified_binding_receipt_digest,
            "verified_binding_receipt_digest",
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
        verification_digest = _non_empty_string(
            self.verification_digest,
            "verification_digest",
        )

        for field_name, digest in (
            (
                "verified_request_digest",
                verified_request_digest,
            ),
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
                "verified_binding_receipt_digest",
                verified_binding_receipt_digest,
            ),
            (
                "verification_digest",
                verification_digest,
            ),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        request = self.persistence_request.request_required
        receipt = request.receipt
        binding = request.binding
        snapshot = request.snapshot
        contract = request.contract

        if request.request_mode != PlanningAuditPersistenceRequestMode.PREPARE_ONLY:
            raise ValueError("Verified persistence request must remain PREPARE_ONLY.")

        if not request.is_prepare_only:
            raise ValueError("Verified persistence request must expose the prepare-only invariant.")

        if request.invocation_mode != PlanningAuditPersistenceInvocationMode.DISABLED:
            raise ValueError("Verified persistence request invocation must remain DISABLED.")

        if verified_request_id != request.request_id:
            raise ValueError("verified_request_id must match the persistence request.")

        if verified_request_digest != request.request_digest:
            raise ValueError("verified_request_digest must match the persistence request.")

        expected_request_digest = _sha256_digest(request.canonical_payload)

        if verified_request_digest != expected_request_digest:
            raise ValueError("verified_request_digest must match the canonical request payload.")

        if verified_content_length != request.content_length_bytes:
            raise ValueError("verified_content_length_bytes must match the persistence request.")

        if verified_content_length != len(request.content.encode("utf-8")):
            raise ValueError("verified_content_length_bytes must match the UTF-8 request payload.")

        if verified_content_digest != request.content_digest:
            raise ValueError("verified_content_digest must match the persistence request.")

        if verified_content_digest != contract.content_digest:
            raise ValueError("verified_content_digest must match the adapter contract.")

        if verified_content_digest != receipt.verified_content_digest:
            raise ValueError("verified_content_digest must match the binding-verification receipt.")

        if verified_manifest_digest != request.manifest_digest:
            raise ValueError("verified_manifest_digest must match the persistence request.")

        if verified_manifest_digest != contract.manifest_digest:
            raise ValueError("verified_manifest_digest must match the adapter contract.")

        if verified_manifest_digest != receipt.verified_manifest_digest:
            raise ValueError(
                "verified_manifest_digest must match the binding-verification receipt."
            )

        if verified_idempotency_key != request.idempotency_key:
            raise ValueError("verified_idempotency_key must match the persistence request.")

        if verified_idempotency_key != contract.idempotency_key:
            raise ValueError("verified_idempotency_key must match the adapter contract.")

        if verified_idempotency_key != receipt.verified_idempotency_key:
            raise ValueError(
                "verified_idempotency_key must match the binding-verification receipt."
            )

        if verified_binding_receipt_digest != request.binding_verification_receipt_digest:
            raise ValueError("verified_binding_receipt_digest must match the persistence request.")

        if verified_binding_receipt_digest != receipt.receipt_digest:
            raise ValueError(
                "verified_binding_receipt_digest must match the binding-verification receipt."
            )

        if verified_binding_id != request.binding_id:
            raise ValueError("verified_binding_id must match the persistence request.")

        if verified_binding_id != binding.binding_id:
            raise ValueError("verified_binding_id must match the adapter binding.")

        if verified_snapshot_id != request.snapshot_id:
            raise ValueError("verified_snapshot_id must match the persistence request.")

        if verified_snapshot_id != snapshot.stable_id:
            raise ValueError("verified_snapshot_id must match the capability snapshot.")

        if verified_contract_id != request.contract_id:
            raise ValueError("verified_contract_id must match the persistence request.")

        if verified_contract_id != contract.contract_id:
            raise ValueError("verified_contract_id must match the adapter contract.")

        if request.has_adapter_instance:
            raise ValueError("Verified request cannot contain an adapter instance.")

        if request.request_submission_authorized:
            raise ValueError("Verified request cannot authorize request submission.")

        if request.adapter_invocation_authorized:
            raise ValueError("Verified request cannot authorize adapter invocation.")

        if request.storage_write_authorized:
            raise ValueError("Verified request cannot authorize storage writes.")

        if request.is_persisted:
            raise ValueError("Verified request cannot assume prior persistence.")

        if request.can_write_storage:
            raise ValueError("Verified request cannot write storage.")

        if request.can_write_network:
            raise ValueError("Verified request cannot write to the network.")

        if request.execution_authorized:
            raise ValueError("Verified request cannot contain trading execution authorization.")

        if request.has_broker_request:
            raise ValueError("Verified request cannot contain a broker request.")

        if request.can_submit_order:
            raise ValueError("Verified request cannot submit an order.")

        if request.is_executable:
            raise ValueError("Verified request cannot be executable.")

        canonical_payload = _canonical_verification_payload(
            schema_version=schema_version,
            checks=self.checks,
            request_stable_id=request.stable_id,
            verified_request_id=verified_request_id,
            verified_request_digest=(verified_request_digest),
            verified_content_length_bytes=(verified_content_length),
            verified_content_digest=(verified_content_digest),
            verified_manifest_digest=(verified_manifest_digest),
            verified_idempotency_key=(verified_idempotency_key),
            verified_binding_receipt_digest=(verified_binding_receipt_digest),
            verified_binding_id=verified_binding_id,
            verified_snapshot_id=verified_snapshot_id,
            verified_contract_id=verified_contract_id,
        )
        expected_verification_digest = _sha256_digest(canonical_payload)

        if verification_digest != expected_verification_digest:
            raise ValueError(
                "verification_digest does not match the canonical request-verification payload."
            )

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "verified_request_id",
            verified_request_id,
        )
        object.__setattr__(
            self,
            "verified_request_digest",
            verified_request_digest,
        )
        object.__setattr__(
            self,
            "verified_content_length_bytes",
            verified_content_length,
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
            "verified_binding_receipt_digest",
            verified_binding_receipt_digest,
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
            "verification_digest",
            verification_digest,
        )

    @property
    def request(
        self,
    ) -> StrategyPlanningAuditPersistenceRequestBlueprint:
        return self.persistence_request.request_required

    @property
    def receipt(self):
        return self.request.receipt

    @property
    def binding(self):
        return self.request.binding

    @property
    def snapshot(self):
        return self.request.snapshot

    @property
    def contract(self):
        return self.request.contract

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
    def verification_count(self) -> int:
        return len(self.checks)

    @property
    def canonical_payload(self) -> str:
        return _canonical_verification_payload(
            schema_version=self.schema_version,
            checks=self.checks,
            request_stable_id=self.request.stable_id,
            verified_request_id=self.verified_request_id,
            verified_request_digest=(self.verified_request_digest),
            verified_content_length_bytes=(self.verified_content_length_bytes),
            verified_content_digest=(self.verified_content_digest),
            verified_manifest_digest=(self.verified_manifest_digest),
            verified_idempotency_key=(self.verified_idempotency_key),
            verified_binding_receipt_digest=(self.verified_binding_receipt_digest),
            verified_binding_id=self.verified_binding_id,
            verified_snapshot_id=self.verified_snapshot_id,
            verified_contract_id=self.verified_contract_id,
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
    def can_continue_to_storage_outcome_design(
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
            f"AUDIT_PERSISTENCE_REQUEST_VERIFIED:"
            f"REQUEST[{self.verified_request_id}]:"
            f"VERIFICATION_SHA256["
            f"{self.verification_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.persistence_request.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_REQUEST_"
            f"VERIFICATION_RECEIPT:"
            f"{self.receipt_id}"
        )


@dataclass(frozen=True, slots=True)
class _PersistenceRequestVerificationEvaluation:
    status: PlanningAuditPersistenceRequestVerificationStatus
    reason: PlanningAuditPersistenceRequestVerificationReason
    blockers: tuple[
        PlanningAuditPersistenceRequestVerificationBlocker,
        ...,
    ]
    receipt: StrategyPlanningAuditPersistenceRequestVerificationReceipt | None


def _derive_verification(
    persistence_request: (PlanningAuditPersistenceRequestDecision),
) -> _PersistenceRequestVerificationEvaluation:
    if persistence_request.is_blocked:
        return _PersistenceRequestVerificationEvaluation(
            status=(PlanningAuditPersistenceRequestVerificationStatus.BLOCKED),
            reason=(PlanningAuditPersistenceRequestVerificationReason.PERSISTENCE_REQUEST_BLOCKED),
            blockers=(
                PlanningAuditPersistenceRequestVerificationBlocker.PERSISTENCE_REQUEST_BLOCKED,
            ),
            receipt=None,
        )

    request = persistence_request.request_required

    canonical_payload = _canonical_verification_payload(
        schema_version=(PLANNING_AUDIT_PERSISTENCE_REQUEST_VERIFICATION_SCHEMA_VERSION),
        checks=_REQUIRED_CHECKS,
        request_stable_id=request.stable_id,
        verified_request_id=request.request_id,
        verified_request_digest=request.request_digest,
        verified_content_length_bytes=(request.content_length_bytes),
        verified_content_digest=request.content_digest,
        verified_manifest_digest=request.manifest_digest,
        verified_idempotency_key=request.idempotency_key,
        verified_binding_receipt_digest=(request.binding_verification_receipt_digest),
        verified_binding_id=request.binding_id,
        verified_snapshot_id=request.snapshot_id,
        verified_contract_id=request.contract_id,
    )

    receipt = StrategyPlanningAuditPersistenceRequestVerificationReceipt(
        persistence_request=persistence_request,
        schema_version=(PLANNING_AUDIT_PERSISTENCE_REQUEST_VERIFICATION_SCHEMA_VERSION),
        checks=_REQUIRED_CHECKS,
        verified_request_id=request.request_id,
        verified_request_digest=request.request_digest,
        verified_content_length_bytes=(request.content_length_bytes),
        verified_content_digest=request.content_digest,
        verified_manifest_digest=(request.manifest_digest),
        verified_idempotency_key=(request.idempotency_key),
        verified_binding_receipt_digest=(request.binding_verification_receipt_digest),
        verified_binding_id=request.binding_id,
        verified_snapshot_id=request.snapshot_id,
        verified_contract_id=request.contract_id,
        verification_digest=_sha256_digest(canonical_payload),
    )

    return _PersistenceRequestVerificationEvaluation(
        status=(PlanningAuditPersistenceRequestVerificationStatus.VERIFIED),
        reason=(PlanningAuditPersistenceRequestVerificationReason.VERIFIED),
        blockers=(),
        receipt=receipt,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditPersistenceRequestVerificationDecision:
    """Validated persistence-request verification result."""

    persistence_request: PlanningAuditPersistenceRequestDecision
    status: PlanningAuditPersistenceRequestVerificationStatus
    reason: PlanningAuditPersistenceRequestVerificationReason
    blockers: tuple[
        PlanningAuditPersistenceRequestVerificationBlocker,
        ...,
    ]
    receipt: StrategyPlanningAuditPersistenceRequestVerificationReceipt | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.persistence_request,
            PlanningAuditPersistenceRequestDecision,
        ):
            raise ValueError(
                "persistence_request must be a PlanningAuditPersistenceRequestDecision."
            )

        try:
            status = PlanningAuditPersistenceRequestVerificationStatus(self.status)
            reason = PlanningAuditPersistenceRequestVerificationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Unsupported persistence-request verification status or reason."
            ) from error

        blockers = tuple(
            PlanningAuditPersistenceRequestVerificationBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Request-verification blockers cannot contain duplicates.")

        if self.receipt is not None and not isinstance(
            self.receipt,
            StrategyPlanningAuditPersistenceRequestVerificationReceipt,
        ):
            raise ValueError("receipt must be a persistence-request verification receipt or None.")

        expected = _derive_verification(self.persistence_request)
        supplied = _PersistenceRequestVerificationEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            receipt=self.receipt,
        )

        if supplied != expected:
            raise ValueError(
                "Persistence-request verification result does not match its request decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.persistence_request.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.persistence_request.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.persistence_request.direction

    @property
    def is_verified(self) -> bool:
        return self.status == PlanningAuditPersistenceRequestVerificationStatus.VERIFIED

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
    ) -> StrategyPlanningAuditPersistenceRequestVerificationReceipt:
        if self.receipt is None:
            raise ValueError("No persistence-request verification receipt was created.")

        return self.receipt

    @property
    def can_continue_to_storage_outcome_design(
        self,
    ) -> bool:
        return self.is_verified

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
            f"{self.persistence_request.stable_id}:"
            f"PLANNING_AUDIT_PERSISTENCE_REQUEST_"
            f"VERIFICATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditPersistenceRequestVerificationFactory:
    """
    Pure factory for persistence-request verification.

    VERIFIED permits later storage-outcome design only.
    It performs and authorizes no request submission,
    adapter invocation, persistence, network, broker, MT5,
    or trading execution operation.
    """

    def verify(
        self,
        persistence_request: (PlanningAuditPersistenceRequestDecision),
    ) -> PlanningAuditPersistenceRequestVerificationDecision:
        if not isinstance(
            persistence_request,
            PlanningAuditPersistenceRequestDecision,
        ):
            raise (
                PlanningAuditPersistenceRequestVerificationError(
                    PlanningAuditPersistenceRequestVerificationErrorReason.INVALID_PERSISTENCE_REQUEST_DECISION,
                    "persistence_request must be a PlanningAuditPersistenceRequestDecision.",
                )
            )

        evaluation = _derive_verification(persistence_request)

        return PlanningAuditPersistenceRequestVerificationDecision(
            persistence_request=persistence_request,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            receipt=evaluation.receipt,
        )

    def generate(
        self,
        persistence_request: (PlanningAuditPersistenceRequestDecision),
    ) -> PlanningAuditPersistenceRequestVerificationDecision:
        """Compatibility alias for verify()."""

        return self.verify(persistence_request)

    def evaluate(
        self,
        persistence_request: (PlanningAuditPersistenceRequestDecision),
    ) -> PlanningAuditPersistenceRequestVerificationDecision:
        """Compatibility alias for verify()."""

        return self.verify(persistence_request)


def verify_planning_audit_persistence_request(
    persistence_request: (PlanningAuditPersistenceRequestDecision),
) -> PlanningAuditPersistenceRequestVerificationDecision:
    return StrategyPlanningAuditPersistenceRequestVerificationFactory().verify(persistence_request)


AuditPersistenceRequestVerificationBlocker = PlanningAuditPersistenceRequestVerificationBlocker
AuditPersistenceRequestVerificationCheck = PlanningAuditPersistenceRequestVerificationCheck
AuditPersistenceRequestVerificationDecision = PlanningAuditPersistenceRequestVerificationDecision
AuditPersistenceRequestVerificationFactory = (
    StrategyPlanningAuditPersistenceRequestVerificationFactory
)
AuditPersistenceRequestVerificationReason = PlanningAuditPersistenceRequestVerificationReason
AuditPersistenceRequestVerificationReceipt = (
    StrategyPlanningAuditPersistenceRequestVerificationReceipt
)
AuditPersistenceRequestVerificationStatus = PlanningAuditPersistenceRequestVerificationStatus
PlanningAuditPersistenceRequestVerificationFactory = (
    StrategyPlanningAuditPersistenceRequestVerificationFactory
)
PlanningAuditPersistenceRequestVerificationReceipt = (
    StrategyPlanningAuditPersistenceRequestVerificationReceipt
)
StrategyAuditPersistenceRequestVerificationFactory = (
    StrategyPlanningAuditPersistenceRequestVerificationFactory
)
StrategyAuditPersistenceRequestVerificationReceipt = (
    StrategyPlanningAuditPersistenceRequestVerificationReceipt
)
