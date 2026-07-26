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
from app.strategy.planning_audit_record import (
    PlanningAuditRecordDecision,
    StrategyPlanningAuditRecord,
)

PLANNING_AUDIT_EXPORT_SCHEMA_VERSION = "1.0"


class PlanningAuditExportMediaType(str, Enum):
    JSON = "application/json"


class PlanningAuditExportEncoding(str, Enum):
    UTF_8 = "utf-8"


class PlanningAuditExportStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditExportReason(str, Enum):
    CREATED = "CREATED"
    AUDIT_RECORD_BLOCKED = "AUDIT_RECORD_BLOCKED"


class PlanningAuditExportBlocker(str, Enum):
    AUDIT_RECORD_BLOCKED = "AUDIT_RECORD_BLOCKED"


class PlanningAuditExportErrorReason(str, Enum):
    INVALID_AUDIT_RECORD_DECISION = "INVALID_AUDIT_RECORD_DECISION"


class PlanningAuditExportError(RuntimeError):
    """Structured planning-audit export failure."""

    def __init__(
        self,
        reason: PlanningAuditExportErrorReason,
        message: str,
    ) -> None:
        self.reason = PlanningAuditExportErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Planning-audit export error [{self.reason.value}]: {self.message}")


def _non_empty_string(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    if not value:
        raise ValueError(f"{field_name} cannot be empty.")

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


def _sha256_digest(value: bytes) -> str:
    return sha256(value).hexdigest()


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditExportEnvelope:
    """
    Immutable export-ready wrapper around an audit record.

    The envelope provides canonical bytes and metadata but
    performs no filesystem, database, network, or broker
    write.
    """

    audit_record: PlanningAuditRecordDecision
    schema_version: str
    media_type: PlanningAuditExportMediaType
    encoding: PlanningAuditExportEncoding
    content: str
    content_length_bytes: int
    content_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.audit_record,
            PlanningAuditRecordDecision,
        ):
            raise ValueError("audit_record must be a PlanningAuditRecordDecision.")

        if not self.audit_record.is_created:
            raise ValueError("An export envelope requires a created planning-audit record.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PLANNING_AUDIT_EXPORT_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current planning-audit export schema.")

        if not isinstance(
            self.media_type,
            PlanningAuditExportMediaType,
        ):
            raise ValueError("media_type must be a PlanningAuditExportMediaType member.")

        if self.media_type != PlanningAuditExportMediaType.JSON:
            raise ValueError("Planning-audit export media type must be application/json.")

        if not isinstance(
            self.encoding,
            PlanningAuditExportEncoding,
        ):
            raise ValueError("encoding must be a PlanningAuditExportEncoding member.")

        if self.encoding != PlanningAuditExportEncoding.UTF_8:
            raise ValueError("Planning-audit export encoding must be utf-8.")

        content = _non_empty_string(
            self.content,
            "content",
        )
        content_length_bytes = _positive_integer(
            self.content_length_bytes,
            "content_length_bytes",
        )
        content_digest = _non_empty_string(
            self.content_digest,
            "content_digest",
        )

        if not _is_lowercase_sha256(content_digest):
            raise ValueError("content_digest must be a lowercase SHA-256 hexadecimal value.")

        record = self.audit_record.record_required
        expected_content = record.canonical_json

        if content != expected_content:
            raise ValueError(
                "Export content must exactly match the canonical planning-audit record JSON."
            )

        encoded_content = content.encode(self.encoding.value)
        expected_length = len(encoded_content)

        if content_length_bytes != expected_length:
            raise ValueError("content_length_bytes does not match the UTF-8 payload size.")

        expected_digest = _sha256_digest(encoded_content)

        if content_digest != expected_digest:
            raise ValueError("content_digest does not match the canonical export payload.")

        if content_digest != record.record_digest:
            raise ValueError("Export digest must match the planning-audit record digest.")

        if not record.is_serialization_ready:
            raise ValueError("Export envelope requires a serialization-ready record.")

        if record.is_persisted:
            raise ValueError("Export envelope cannot assume record persistence.")

        if record.can_write_storage:
            raise ValueError("Export envelope cannot expose storage writes.")

        if record.can_write_network:
            raise ValueError("Export envelope cannot expose network writes.")

        if record.execution_authorized:
            raise ValueError("Export envelope cannot contain execution authorization.")

        if record.has_broker_request:
            raise ValueError("Export envelope cannot contain a broker request.")

        if record.can_submit_order:
            raise ValueError("Export envelope cannot permit order submission.")

        if record.is_executable:
            raise ValueError("Export envelope cannot contain an executable record.")

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
            content_length_bytes,
        )
        object.__setattr__(
            self,
            "content_digest",
            content_digest,
        )

    @property
    def record(self) -> StrategyPlanningAuditRecord:
        return self.audit_record.record_required

    @property
    def manifest(self):
        return self.record.manifest

    @property
    def broker_symbol(self) -> str:
        return self.record.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.record.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.record.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.record.side

    @property
    def manifest_digest(self) -> str:
        return self.record.manifest_digest

    @property
    def record_digest(self) -> str:
        return self.record.record_digest

    @property
    def content_bytes(self) -> bytes:
        return self.content.encode(self.encoding.value)

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def is_export_ready(self) -> bool:
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
    def envelope_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"PLANNING_AUDIT_EXPORT:"
            f"JSON:"
            f"UTF8:"
            f"BYTES[{self.content_length_bytes}]:"
            f"SHA256[{self.content_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.audit_record.stable_id}:PLANNING_AUDIT_EXPORT_ENVELOPE:{self.envelope_id}"


@dataclass(frozen=True, slots=True)
class _PlanningAuditExportEvaluation:
    status: PlanningAuditExportStatus
    reason: PlanningAuditExportReason
    blockers: tuple[
        PlanningAuditExportBlocker,
        ...,
    ]
    envelope: StrategyPlanningAuditExportEnvelope | None


def _derive_envelope(
    audit_record: PlanningAuditRecordDecision,
) -> _PlanningAuditExportEvaluation:
    if audit_record.is_blocked:
        return _PlanningAuditExportEvaluation(
            status=PlanningAuditExportStatus.BLOCKED,
            reason=(PlanningAuditExportReason.AUDIT_RECORD_BLOCKED),
            blockers=(PlanningAuditExportBlocker.AUDIT_RECORD_BLOCKED,),
            envelope=None,
        )

    record = audit_record.record_required
    content = record.canonical_json
    content_bytes = content.encode(PlanningAuditExportEncoding.UTF_8.value)
    envelope = StrategyPlanningAuditExportEnvelope(
        audit_record=audit_record,
        schema_version=(PLANNING_AUDIT_EXPORT_SCHEMA_VERSION),
        media_type=PlanningAuditExportMediaType.JSON,
        encoding=PlanningAuditExportEncoding.UTF_8,
        content=content,
        content_length_bytes=len(content_bytes),
        content_digest=_sha256_digest(content_bytes),
    )

    return _PlanningAuditExportEvaluation(
        status=PlanningAuditExportStatus.CREATED,
        reason=PlanningAuditExportReason.CREATED,
        blockers=(),
        envelope=envelope,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditExportDecision:
    """Validated planning-audit export-envelope result."""

    audit_record: PlanningAuditRecordDecision
    status: PlanningAuditExportStatus
    reason: PlanningAuditExportReason
    blockers: tuple[
        PlanningAuditExportBlocker,
        ...,
    ]
    envelope: StrategyPlanningAuditExportEnvelope | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.audit_record,
            PlanningAuditRecordDecision,
        ):
            raise ValueError("audit_record must be a PlanningAuditRecordDecision.")

        try:
            status = PlanningAuditExportStatus(self.status)
            reason = PlanningAuditExportReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported planning-audit export status or reason.") from error

        blockers = tuple(PlanningAuditExportBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Planning-audit export blockers cannot contain duplicates.")

        if self.envelope is not None and not isinstance(
            self.envelope,
            StrategyPlanningAuditExportEnvelope,
        ):
            raise ValueError("envelope must be a StrategyPlanningAuditExportEnvelope or None.")

        expected = _derive_envelope(self.audit_record)
        supplied = _PlanningAuditExportEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            envelope=self.envelope,
        )

        if supplied != expected:
            raise ValueError(
                "Planning-audit export result does not match its audit-record decision."
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
        return self.audit_record.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.audit_record.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.audit_record.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditExportStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_envelope(self) -> bool:
        return self.envelope is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def envelope_required(
        self,
    ) -> StrategyPlanningAuditExportEnvelope:
        if self.envelope is None:
            raise ValueError("No planning-audit export envelope was created.")

        return self.envelope

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
            f"{self.audit_record.stable_id}:"
            f"PLANNING_AUDIT_EXPORT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditExportFactory:
    """
    Pure factory for immutable audit export envelopes.

    CREATED provides verified bytes and metadata only. It
    performs no filesystem, database, network, or broker
    operation.
    """

    def generate(
        self,
        audit_record: PlanningAuditRecordDecision,
    ) -> PlanningAuditExportDecision:
        if not isinstance(
            audit_record,
            PlanningAuditRecordDecision,
        ):
            raise PlanningAuditExportError(
                PlanningAuditExportErrorReason.INVALID_AUDIT_RECORD_DECISION,
                "audit_record must be a PlanningAuditRecordDecision.",
            )

        evaluation = _derive_envelope(audit_record)

        return PlanningAuditExportDecision(
            audit_record=audit_record,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            envelope=evaluation.envelope,
        )

    def build(
        self,
        audit_record: PlanningAuditRecordDecision,
    ) -> PlanningAuditExportDecision:
        """Compatibility alias for generate()."""

        return self.generate(audit_record)

    def evaluate(
        self,
        audit_record: PlanningAuditRecordDecision,
    ) -> PlanningAuditExportDecision:
        """Compatibility alias for generate()."""

        return self.generate(audit_record)


def generate_planning_audit_export(
    audit_record: PlanningAuditRecordDecision,
) -> PlanningAuditExportDecision:
    return StrategyPlanningAuditExportFactory().generate(audit_record)


AuditExportEnvelope = StrategyPlanningAuditExportEnvelope
AuditExportFactory = StrategyPlanningAuditExportFactory
PlanningAuditExportEnvelope = StrategyPlanningAuditExportEnvelope
PlanningAuditExportFactory = StrategyPlanningAuditExportFactory
StrategyAuditExportEnvelope = StrategyPlanningAuditExportEnvelope
StrategyAuditExportFactory = StrategyPlanningAuditExportFactory
