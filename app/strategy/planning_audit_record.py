from __future__ import annotations

import json
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
from app.strategy.planning_audit_manifest import (
    PlanningAuditManifestDecision,
    StrategyPlanningAuditManifest,
)

PLANNING_AUDIT_RECORD_SCHEMA_VERSION = "1.0"


class PlanningAuditRecordField(str, Enum):
    MANIFEST_SCHEMA_VERSION = "MANIFEST_SCHEMA_VERSION"
    MANIFEST_DIGEST = "MANIFEST_DIGEST"
    BROKER_SYMBOL = "BROKER_SYMBOL"
    OBSERVED_AT = "OBSERVED_AT"
    DIRECTION = "DIRECTION"
    SIDE = "SIDE"
    PACKAGE_ID = "PACKAGE_ID"
    PACKAGE_STABLE_ID = "PACKAGE_STABLE_ID"
    MANIFEST_ID = "MANIFEST_ID"
    MANIFEST_STABLE_ID = "MANIFEST_STABLE_ID"
    MANIFEST_CANONICAL_PAYLOAD = "MANIFEST_CANONICAL_PAYLOAD"


class PlanningAuditRecordStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditRecordReason(str, Enum):
    CREATED = "CREATED"
    AUDIT_MANIFEST_BLOCKED = "AUDIT_MANIFEST_BLOCKED"


class PlanningAuditRecordBlocker(str, Enum):
    AUDIT_MANIFEST_BLOCKED = "AUDIT_MANIFEST_BLOCKED"


class PlanningAuditRecordErrorReason(str, Enum):
    INVALID_AUDIT_MANIFEST_DECISION = "INVALID_AUDIT_MANIFEST_DECISION"


class PlanningAuditRecordError(RuntimeError):
    """Structured planning-audit record failure."""

    def __init__(
        self,
        reason: PlanningAuditRecordErrorReason,
        message: str,
    ) -> None:
        self.reason = PlanningAuditRecordErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Planning-audit record error [{self.reason.value}]: {self.message}")


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


@dataclass(frozen=True, slots=True)
class PlanningAuditRecordEntry:
    """One deterministic field in an audit record."""

    field: PlanningAuditRecordField
    value: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.field,
            PlanningAuditRecordField,
        ):
            raise ValueError("field must be a PlanningAuditRecordField member.")

        object.__setattr__(
            self,
            "value",
            _non_empty_string(
                self.value,
                "value",
            ),
        )

    @property
    def canonical_pair(
        self,
    ) -> tuple[str, str]:
        return self.field.value, self.value


def _entries_for(
    manifest: StrategyPlanningAuditManifest,
) -> tuple[PlanningAuditRecordEntry, ...]:
    package = manifest.package

    return (
        PlanningAuditRecordEntry(
            field=(PlanningAuditRecordField.MANIFEST_SCHEMA_VERSION),
            value=manifest.schema_version,
        ),
        PlanningAuditRecordEntry(
            field=(PlanningAuditRecordField.MANIFEST_DIGEST),
            value=manifest.digest,
        ),
        PlanningAuditRecordEntry(
            field=PlanningAuditRecordField.BROKER_SYMBOL,
            value=manifest.broker_symbol,
        ),
        PlanningAuditRecordEntry(
            field=PlanningAuditRecordField.OBSERVED_AT,
            value=manifest.observed_at.isoformat(),
        ),
        PlanningAuditRecordEntry(
            field=PlanningAuditRecordField.DIRECTION,
            value=manifest.direction.value,
        ),
        PlanningAuditRecordEntry(
            field=PlanningAuditRecordField.SIDE,
            value=manifest.side.value,
        ),
        PlanningAuditRecordEntry(
            field=PlanningAuditRecordField.PACKAGE_ID,
            value=package.package_id,
        ),
        PlanningAuditRecordEntry(
            field=(PlanningAuditRecordField.PACKAGE_STABLE_ID),
            value=package.stable_id,
        ),
        PlanningAuditRecordEntry(
            field=PlanningAuditRecordField.MANIFEST_ID,
            value=manifest.manifest_id,
        ),
        PlanningAuditRecordEntry(
            field=(PlanningAuditRecordField.MANIFEST_STABLE_ID),
            value=manifest.stable_id,
        ),
        PlanningAuditRecordEntry(
            field=(PlanningAuditRecordField.MANIFEST_CANONICAL_PAYLOAD),
            value=manifest.canonical_payload,
        ),
    )


def _canonical_json_for(
    schema_version: str,
    entries: tuple[
        PlanningAuditRecordEntry,
        ...,
    ],
) -> str:
    payload = {
        "schema_version": schema_version,
        "entries": [
            {
                "field": entry.field.value,
                "value": entry.value,
            }
            for entry in entries
        ],
    }

    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditRecord:
    """
    Immutable serialization-ready planning audit record.

    The record remains in memory and provides no persistence,
    network, broker, or execution operation.
    """

    audit_manifest: PlanningAuditManifestDecision
    schema_version: str
    entries: tuple[
        PlanningAuditRecordEntry,
        ...,
    ]
    record_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.audit_manifest,
            PlanningAuditManifestDecision,
        ):
            raise ValueError("audit_manifest must be a PlanningAuditManifestDecision.")

        if not self.audit_manifest.is_created:
            raise ValueError("A planning-audit record requires a created audit manifest.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PLANNING_AUDIT_RECORD_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current planning-audit record schema.")

        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple.")

        if not all(
            isinstance(
                entry,
                PlanningAuditRecordEntry,
            )
            for entry in self.entries
        ):
            raise ValueError("entries must contain PlanningAuditRecordEntry objects.")

        fields = tuple(entry.field for entry in self.entries)

        if len(set(fields)) != len(fields):
            raise ValueError("Planning-audit record cannot contain duplicate fields.")

        manifest = self.audit_manifest.manifest_required
        expected_entries = _entries_for(manifest)

        if self.entries != expected_entries:
            raise ValueError(
                "Planning-audit record entries must "
                "exactly match the manifest in "
                "deterministic order."
            )

        record_digest = _non_empty_string(
            self.record_digest,
            "record_digest",
        )

        if not _is_lowercase_sha256(record_digest):
            raise ValueError("record_digest must be a lowercase SHA-256 hexadecimal value.")

        canonical_json = _canonical_json_for(
            schema_version,
            self.entries,
        )
        expected_digest = _sha256_digest(canonical_json)

        if record_digest != expected_digest:
            raise ValueError("record_digest does not match the canonical audit-record JSON.")

        if not manifest.is_tamper_evident:
            raise ValueError("Planning-audit record requires a tamper-evident manifest.")

        if manifest.is_persisted:
            raise ValueError("Planning-audit record cannot assume manifest persistence.")

        if manifest.can_write_storage:
            raise ValueError("Planning-audit record cannot expose storage writes.")

        if manifest.execution_authorized:
            raise ValueError("Planning-audit record cannot contain execution authorization.")

        if manifest.has_broker_request:
            raise ValueError("Planning-audit record cannot contain a broker request.")

        if manifest.can_submit_order:
            raise ValueError("Planning-audit record cannot permit order submission.")

        if manifest.is_executable:
            raise ValueError("Planning-audit record cannot contain an executable manifest.")

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "record_digest",
            record_digest,
        )

    @property
    def manifest(
        self,
    ) -> StrategyPlanningAuditManifest:
        return self.audit_manifest.manifest_required

    @property
    def broker_symbol(self) -> str:
        return self.manifest.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.manifest.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.manifest.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.manifest.side

    @property
    def manifest_digest(self) -> str:
        return self.manifest.digest

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def canonical_json(self) -> str:
        return _canonical_json_for(
            self.schema_version,
            self.entries,
        )

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def is_serialization_ready(self) -> bool:
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
    def record_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"PLANNING_AUDIT_RECORD:"
            f"SHA256[{self.record_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.audit_manifest.stable_id}:PLANNING_AUDIT_RECORD:{self.record_id}"


@dataclass(frozen=True, slots=True)
class _PlanningAuditRecordEvaluation:
    status: PlanningAuditRecordStatus
    reason: PlanningAuditRecordReason
    blockers: tuple[
        PlanningAuditRecordBlocker,
        ...,
    ]
    record: StrategyPlanningAuditRecord | None


def _derive_record(
    audit_manifest: PlanningAuditManifestDecision,
) -> _PlanningAuditRecordEvaluation:
    if audit_manifest.is_blocked:
        return _PlanningAuditRecordEvaluation(
            status=PlanningAuditRecordStatus.BLOCKED,
            reason=(PlanningAuditRecordReason.AUDIT_MANIFEST_BLOCKED),
            blockers=(PlanningAuditRecordBlocker.AUDIT_MANIFEST_BLOCKED,),
            record=None,
        )

    manifest = audit_manifest.manifest_required
    entries = _entries_for(manifest)
    canonical_json = _canonical_json_for(
        PLANNING_AUDIT_RECORD_SCHEMA_VERSION,
        entries,
    )
    record = StrategyPlanningAuditRecord(
        audit_manifest=audit_manifest,
        schema_version=(PLANNING_AUDIT_RECORD_SCHEMA_VERSION),
        entries=entries,
        record_digest=_sha256_digest(canonical_json),
    )

    return _PlanningAuditRecordEvaluation(
        status=PlanningAuditRecordStatus.CREATED,
        reason=PlanningAuditRecordReason.CREATED,
        blockers=(),
        record=record,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditRecordDecision:
    """Validated planning-audit record result."""

    audit_manifest: PlanningAuditManifestDecision
    status: PlanningAuditRecordStatus
    reason: PlanningAuditRecordReason
    blockers: tuple[
        PlanningAuditRecordBlocker,
        ...,
    ]
    record: StrategyPlanningAuditRecord | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.audit_manifest,
            PlanningAuditManifestDecision,
        ):
            raise ValueError("audit_manifest must be a PlanningAuditManifestDecision.")

        try:
            status = PlanningAuditRecordStatus(self.status)
            reason = PlanningAuditRecordReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported planning-audit record status or reason.") from error

        blockers = tuple(PlanningAuditRecordBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Planning-audit record blockers cannot contain duplicates.")

        if self.record is not None and not isinstance(
            self.record,
            StrategyPlanningAuditRecord,
        ):
            raise ValueError("record must be a StrategyPlanningAuditRecord or None.")

        expected = _derive_record(self.audit_manifest)
        supplied = _PlanningAuditRecordEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            record=self.record,
        )

        if supplied != expected:
            raise ValueError("Planning-audit record result does not match its manifest decision.")

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
        return self.audit_manifest.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.audit_manifest.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.audit_manifest.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditRecordStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_record(self) -> bool:
        return self.record is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def record_required(
        self,
    ) -> StrategyPlanningAuditRecord:
        if self.record is None:
            raise ValueError("No planning-audit record was created.")

        return self.record

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
            f"{self.audit_manifest.stable_id}:"
            f"PLANNING_AUDIT_RECORD_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditRecordFactory:
    """
    Pure factory for canonical in-memory audit records.

    CREATED produces serialization-ready data only. It does
    not write a file, database, network, or broker resource.
    """

    def generate(
        self,
        audit_manifest: PlanningAuditManifestDecision,
    ) -> PlanningAuditRecordDecision:
        if not isinstance(
            audit_manifest,
            PlanningAuditManifestDecision,
        ):
            raise PlanningAuditRecordError(
                PlanningAuditRecordErrorReason.INVALID_AUDIT_MANIFEST_DECISION,
                "audit_manifest must be a PlanningAuditManifestDecision.",
            )

        evaluation = _derive_record(audit_manifest)

        return PlanningAuditRecordDecision(
            audit_manifest=audit_manifest,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            record=evaluation.record,
        )

    def build(
        self,
        audit_manifest: PlanningAuditManifestDecision,
    ) -> PlanningAuditRecordDecision:
        """Compatibility alias for generate()."""

        return self.generate(audit_manifest)

    def evaluate(
        self,
        audit_manifest: PlanningAuditManifestDecision,
    ) -> PlanningAuditRecordDecision:
        """Compatibility alias for generate()."""

        return self.generate(audit_manifest)


def generate_planning_audit_record(
    audit_manifest: PlanningAuditManifestDecision,
) -> PlanningAuditRecordDecision:
    return StrategyPlanningAuditRecordFactory().generate(audit_manifest)


AuditRecord = StrategyPlanningAuditRecord
AuditRecordDecision = PlanningAuditRecordDecision
AuditRecordEntry = PlanningAuditRecordEntry
AuditRecordFactory = StrategyPlanningAuditRecordFactory
AuditRecordField = PlanningAuditRecordField
PlanningAuditRecord = StrategyPlanningAuditRecord
PlanningAuditRecordFactory = StrategyPlanningAuditRecordFactory
StrategyAuditRecord = StrategyPlanningAuditRecord
StrategyAuditRecordDecision = PlanningAuditRecordDecision
StrategyAuditRecordFactory = StrategyPlanningAuditRecordFactory
