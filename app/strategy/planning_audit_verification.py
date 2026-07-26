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
from app.strategy.planning_audit_export import (
    PlanningAuditExportDecision,
    StrategyPlanningAuditExportEnvelope,
)
from app.strategy.planning_audit_manifest import (
    StrategyPlanningAuditManifest,
)
from app.strategy.planning_audit_record import (
    StrategyPlanningAuditRecord,
)
from app.strategy.planning_package import (
    StrategyPlanningPackage,
)

PLANNING_AUDIT_VERIFICATION_SCHEMA_VERSION = "1.0"


class PlanningAuditVerificationCheck(str, Enum):
    CONTENT_MATCHES_RECORD = "CONTENT_MATCHES_RECORD"
    UTF8_LENGTH_MATCHES = "UTF8_LENGTH_MATCHES"
    CONTENT_DIGEST_MATCHES = "CONTENT_DIGEST_MATCHES"
    RECORD_DIGEST_MATCHES = "RECORD_DIGEST_MATCHES"
    MANIFEST_DIGEST_MATCHES = "MANIFEST_DIGEST_MATCHES"
    EXECUTION_BOUNDARY_LOCKED = "EXECUTION_BOUNDARY_LOCKED"


class PlanningAuditVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"


class PlanningAuditVerificationReason(str, Enum):
    VERIFIED = "VERIFIED"
    AUDIT_EXPORT_BLOCKED = "AUDIT_EXPORT_BLOCKED"


class PlanningAuditVerificationBlocker(str, Enum):
    AUDIT_EXPORT_BLOCKED = "AUDIT_EXPORT_BLOCKED"


class PlanningAuditVerificationErrorReason(str, Enum):
    INVALID_AUDIT_EXPORT_DECISION = "INVALID_AUDIT_EXPORT_DECISION"


class PlanningAuditVerificationError(RuntimeError):
    """Structured audit-export verification failure."""

    def __init__(
        self,
        reason: PlanningAuditVerificationErrorReason,
        message: str,
    ) -> None:
        self.reason = PlanningAuditVerificationErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Planning-audit verification error [{self.reason.value}]: {self.message}")


_REQUIRED_CHECKS = (
    PlanningAuditVerificationCheck.CONTENT_MATCHES_RECORD,
    PlanningAuditVerificationCheck.UTF8_LENGTH_MATCHES,
    PlanningAuditVerificationCheck.CONTENT_DIGEST_MATCHES,
    PlanningAuditVerificationCheck.RECORD_DIGEST_MATCHES,
    PlanningAuditVerificationCheck.MANIFEST_DIGEST_MATCHES,
    PlanningAuditVerificationCheck.EXECUTION_BOUNDARY_LOCKED,
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


def _sha256_digest(value: bytes) -> str:
    return sha256(value).hexdigest()


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditVerificationReceipt:
    """
    Immutable independent verification of an export envelope.

    The receipt verifies canonical content, byte length,
    digest lineage, and the locked execution boundary.
    It performs no persistence, network, or broker write.
    """

    audit_export: PlanningAuditExportDecision
    schema_version: str
    checks: tuple[
        PlanningAuditVerificationCheck,
        ...,
    ]
    verified_content_length_bytes: int
    verified_content_digest: str
    verified_manifest_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.audit_export,
            PlanningAuditExportDecision,
        ):
            raise ValueError("audit_export must be a PlanningAuditExportDecision.")

        if not self.audit_export.is_created:
            raise ValueError("A verification receipt requires a created audit-export envelope.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PLANNING_AUDIT_VERIFICATION_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current audit-verification schema.")

        if not isinstance(self.checks, tuple):
            raise ValueError("checks must be a tuple.")

        if not all(
            isinstance(
                check,
                PlanningAuditVerificationCheck,
            )
            for check in self.checks
        ):
            raise ValueError("checks must contain PlanningAuditVerificationCheck members.")

        if len(set(self.checks)) != len(self.checks):
            raise ValueError("Verification checks cannot contain duplicates.")

        if self.checks != _REQUIRED_CHECKS:
            raise ValueError(
                "Verification checks must contain every required check in deterministic order."
            )

        verified_length = _positive_integer(
            self.verified_content_length_bytes,
            "verified_content_length_bytes",
        )
        verified_digest = _non_empty_string(
            self.verified_content_digest,
            "verified_content_digest",
        )
        manifest_digest = _non_empty_string(
            self.verified_manifest_digest,
            "verified_manifest_digest",
        )

        if not _is_lowercase_sha256(verified_digest):
            raise ValueError(
                "verified_content_digest must be a lowercase SHA-256 hexadecimal value."
            )

        if not _is_lowercase_sha256(manifest_digest):
            raise ValueError(
                "verified_manifest_digest must be a lowercase SHA-256 hexadecimal value."
            )

        envelope = self.audit_export.envelope_required
        record = envelope.record
        manifest = envelope.manifest
        package = manifest.package

        if envelope.content != record.canonical_json:
            raise ValueError("Export content does not match the canonical audit record.")

        independently_encoded = envelope.content.encode("utf-8")
        independently_measured_length = len(independently_encoded)

        if verified_length != independently_measured_length:
            raise ValueError(
                "verified_content_length_bytes does not "
                "match the independently measured UTF-8 "
                "payload size."
            )

        if verified_length != envelope.content_length_bytes:
            raise ValueError("Verified content length does not match the export envelope.")

        independently_calculated_digest = _sha256_digest(independently_encoded)

        if verified_digest != independently_calculated_digest:
            raise ValueError(
                "verified_content_digest does not match "
                "the independently calculated payload "
                "digest."
            )

        if verified_digest != envelope.content_digest:
            raise ValueError("Verified content digest does not match the export-envelope digest.")

        if verified_digest != record.record_digest:
            raise ValueError("Verified content digest does not match the audit-record digest.")

        if manifest_digest != envelope.manifest_digest:
            raise ValueError("Verified manifest digest does not match the export envelope.")

        if manifest_digest != manifest.digest:
            raise ValueError("Verified manifest digest does not match the planning-audit manifest.")

        if not package.is_locked:
            raise ValueError("Verification requires a locked strategy planning package.")

        if package.execution_authorized:
            raise ValueError("Verified package cannot contain execution authorization.")

        if package.has_broker_request:
            raise ValueError("Verified package cannot contain a broker request.")

        if package.can_build_broker_request:
            raise ValueError("Verified package cannot build a broker request.")

        if package.can_submit_order:
            raise ValueError("Verified package cannot submit an order.")

        if package.is_executable:
            raise ValueError("Verified package cannot be executable.")

        if envelope.is_persisted:
            raise ValueError("Verification receipt cannot assume export persistence.")

        if envelope.can_write_storage:
            raise ValueError("Verification receipt cannot expose storage writes.")

        if envelope.can_write_network:
            raise ValueError("Verification receipt cannot expose network writes.")

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "verified_content_length_bytes",
            verified_length,
        )
        object.__setattr__(
            self,
            "verified_content_digest",
            verified_digest,
        )
        object.__setattr__(
            self,
            "verified_manifest_digest",
            manifest_digest,
        )

    @property
    def envelope(
        self,
    ) -> StrategyPlanningAuditExportEnvelope:
        return self.audit_export.envelope_required

    @property
    def record(self) -> StrategyPlanningAuditRecord:
        return self.envelope.record

    @property
    def manifest(
        self,
    ) -> StrategyPlanningAuditManifest:
        return self.envelope.manifest

    @property
    def package(self) -> StrategyPlanningPackage:
        return self.manifest.package

    @property
    def broker_symbol(self) -> str:
        return self.envelope.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.envelope.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.envelope.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.envelope.side

    @property
    def verification_count(self) -> int:
        return len(self.checks)

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
    def can_continue_to_storage_admission(self) -> bool:
        return True

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
        check_fragment = ",".join(check.value for check in self.checks)

        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"AUDIT_EXPORT_VERIFIED:"
            f"BYTES[{self.verified_content_length_bytes}]:"
            f"SHA256[{self.verified_content_digest}]:"
            f"CHECKS[{check_fragment}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.audit_export.stable_id}:PLANNING_AUDIT_VERIFICATION_RECEIPT:{self.receipt_id}"
        )


@dataclass(frozen=True, slots=True)
class _PlanningAuditVerificationEvaluation:
    status: PlanningAuditVerificationStatus
    reason: PlanningAuditVerificationReason
    blockers: tuple[
        PlanningAuditVerificationBlocker,
        ...,
    ]
    receipt: StrategyPlanningAuditVerificationReceipt | None


def _derive_verification(
    audit_export: PlanningAuditExportDecision,
) -> _PlanningAuditVerificationEvaluation:
    if audit_export.is_blocked:
        return _PlanningAuditVerificationEvaluation(
            status=PlanningAuditVerificationStatus.BLOCKED,
            reason=(PlanningAuditVerificationReason.AUDIT_EXPORT_BLOCKED),
            blockers=(PlanningAuditVerificationBlocker.AUDIT_EXPORT_BLOCKED,),
            receipt=None,
        )

    envelope = audit_export.envelope_required
    independently_encoded = envelope.content.encode("utf-8")
    receipt = StrategyPlanningAuditVerificationReceipt(
        audit_export=audit_export,
        schema_version=(PLANNING_AUDIT_VERIFICATION_SCHEMA_VERSION),
        checks=_REQUIRED_CHECKS,
        verified_content_length_bytes=len(independently_encoded),
        verified_content_digest=_sha256_digest(independently_encoded),
        verified_manifest_digest=(envelope.manifest_digest),
    )

    return _PlanningAuditVerificationEvaluation(
        status=PlanningAuditVerificationStatus.VERIFIED,
        reason=PlanningAuditVerificationReason.VERIFIED,
        blockers=(),
        receipt=receipt,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditVerificationDecision:
    """Validated audit-export verification result."""

    audit_export: PlanningAuditExportDecision
    status: PlanningAuditVerificationStatus
    reason: PlanningAuditVerificationReason
    blockers: tuple[
        PlanningAuditVerificationBlocker,
        ...,
    ]
    receipt: StrategyPlanningAuditVerificationReceipt | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.audit_export,
            PlanningAuditExportDecision,
        ):
            raise ValueError("audit_export must be a PlanningAuditExportDecision.")

        try:
            status = PlanningAuditVerificationStatus(self.status)
            reason = PlanningAuditVerificationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported planning-audit verification status or reason.") from error

        blockers = tuple(PlanningAuditVerificationBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Audit-verification blockers cannot contain duplicates.")

        if self.receipt is not None and not isinstance(
            self.receipt,
            StrategyPlanningAuditVerificationReceipt,
        ):
            raise ValueError("receipt must be a StrategyPlanningAuditVerificationReceipt or None.")

        expected = _derive_verification(self.audit_export)
        supplied = _PlanningAuditVerificationEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            receipt=self.receipt,
        )

        if supplied != expected:
            raise ValueError(
                "Planning-audit verification result does not match its export-envelope decision."
            )

        object.__setattr__(
            self,
            "status",
            status,
        )
        object.__setattr__(
            self,
            "reason",
            reason,
        )
        object.__setattr__(
            self,
            "blockers",
            blockers,
        )

    @property
    def broker_symbol(self) -> str:
        return self.audit_export.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.audit_export.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.audit_export.direction

    @property
    def is_verified(self) -> bool:
        return self.status == PlanningAuditVerificationStatus.VERIFIED

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
    ) -> StrategyPlanningAuditVerificationReceipt:
        if self.receipt is None:
            raise ValueError("No planning-audit verification receipt was created.")

        return self.receipt

    @property
    def can_continue_to_storage_admission(self) -> bool:
        return self.is_verified

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
            f"{self.audit_export.stable_id}:"
            f"PLANNING_AUDIT_VERIFICATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditVerificationFactory:
    """
    Pure factory for independent export verification.

    VERIFIED permits later storage-admission analysis only.
    It performs no filesystem, database, network, broker,
    or execution operation.
    """

    def verify(
        self,
        audit_export: PlanningAuditExportDecision,
    ) -> PlanningAuditVerificationDecision:
        if not isinstance(
            audit_export,
            PlanningAuditExportDecision,
        ):
            raise PlanningAuditVerificationError(
                PlanningAuditVerificationErrorReason.INVALID_AUDIT_EXPORT_DECISION,
                "audit_export must be a PlanningAuditExportDecision.",
            )

        evaluation = _derive_verification(audit_export)

        return PlanningAuditVerificationDecision(
            audit_export=audit_export,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            receipt=evaluation.receipt,
        )

    def generate(
        self,
        audit_export: PlanningAuditExportDecision,
    ) -> PlanningAuditVerificationDecision:
        """Compatibility alias for verify()."""

        return self.verify(audit_export)

    def evaluate(
        self,
        audit_export: PlanningAuditExportDecision,
    ) -> PlanningAuditVerificationDecision:
        """Compatibility alias for verify()."""

        return self.verify(audit_export)


def verify_planning_audit_export(
    audit_export: PlanningAuditExportDecision,
) -> PlanningAuditVerificationDecision:
    return StrategyPlanningAuditVerificationFactory().verify(audit_export)


AuditExportVerificationCheck = PlanningAuditVerificationCheck
AuditExportVerificationDecision = PlanningAuditVerificationDecision
AuditExportVerificationFactory = StrategyPlanningAuditVerificationFactory
AuditExportVerificationReceipt = StrategyPlanningAuditVerificationReceipt
PlanningAuditVerificationFactory = StrategyPlanningAuditVerificationFactory
PlanningAuditVerificationReceipt = StrategyPlanningAuditVerificationReceipt
StrategyAuditVerificationReceipt = StrategyPlanningAuditVerificationReceipt
