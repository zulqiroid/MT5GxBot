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
from app.strategy.planning_package import (
    StrategyPlanningPackage,
    StrategyPlanningPackageDecision,
)

PLANNING_AUDIT_SCHEMA_VERSION = "1.0"


class PlanningAuditComponent(str, Enum):
    RISK_ADMISSION = "RISK_ADMISSION"
    SIZING_HANDOFF = "SIZING_HANDOFF"
    SIZING_SPECIFICATION = "SIZING_SPECIFICATION"
    POSITION_SIZE = "POSITION_SIZE"
    SIZED_TRADE_PLAN = "SIZED_TRADE_PLAN"
    ORDER_INTENT = "ORDER_INTENT"
    EXECUTION_LOCK = "EXECUTION_LOCK"


class PlanningAuditManifestStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditManifestReason(str, Enum):
    CREATED = "CREATED"
    PLANNING_PACKAGE_BLOCKED = "PLANNING_PACKAGE_BLOCKED"


class PlanningAuditManifestBlocker(str, Enum):
    PLANNING_PACKAGE_BLOCKED = "PLANNING_PACKAGE_BLOCKED"


class PlanningAuditManifestErrorReason(str, Enum):
    INVALID_PLANNING_PACKAGE_DECISION = "INVALID_PLANNING_PACKAGE_DECISION"


class PlanningAuditManifestError(RuntimeError):
    """Structured planning-audit manifest failure."""

    def __init__(
        self,
        reason: PlanningAuditManifestErrorReason,
        message: str,
    ) -> None:
        self.reason = PlanningAuditManifestErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Planning-audit manifest error [{self.reason.value}]: {self.message}")


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


def _digest_for_payload(payload: str) -> str:
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PlanningAuditLineageEntry:
    """One deterministic component in the audit lineage."""

    component: PlanningAuditComponent
    stable_id: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.component,
            PlanningAuditComponent,
        ):
            raise ValueError("component must be a PlanningAuditComponent member.")

        object.__setattr__(
            self,
            "stable_id",
            _non_empty_string(
                self.stable_id,
                "stable_id",
            ),
        )

    @property
    def canonical_line(self) -> str:
        return f"{self.component.value}={self.stable_id}"


def _lineage_for(
    package: StrategyPlanningPackage,
) -> tuple[PlanningAuditLineageEntry, ...]:
    return (
        PlanningAuditLineageEntry(
            component=(PlanningAuditComponent.RISK_ADMISSION),
            stable_id=package.risk_admission.stable_id,
        ),
        PlanningAuditLineageEntry(
            component=(PlanningAuditComponent.SIZING_HANDOFF),
            stable_id=package.sizing_handoff.stable_id,
        ),
        PlanningAuditLineageEntry(
            component=(PlanningAuditComponent.SIZING_SPECIFICATION),
            stable_id=(package.sizing_specification.stable_id),
        ),
        PlanningAuditLineageEntry(
            component=PlanningAuditComponent.POSITION_SIZE,
            stable_id=package.position_size.stable_id,
        ),
        PlanningAuditLineageEntry(
            component=(PlanningAuditComponent.SIZED_TRADE_PLAN),
            stable_id=package.sized_plan.stable_id,
        ),
        PlanningAuditLineageEntry(
            component=PlanningAuditComponent.ORDER_INTENT,
            stable_id=package.order_intent.stable_id,
        ),
        PlanningAuditLineageEntry(
            component=PlanningAuditComponent.EXECUTION_LOCK,
            stable_id=package.execution_lock.stable_id,
        ),
    )


def _canonical_payload_for(
    package: StrategyPlanningPackage,
    schema_version: str,
    lineage: tuple[
        PlanningAuditLineageEntry,
        ...,
    ],
) -> str:
    header = (
        f"SCHEMA_VERSION={schema_version}",
        f"BROKER_SYMBOL={package.broker_symbol}",
        f"OBSERVED_AT={package.observed_at.isoformat()}",
        f"DIRECTION={package.direction.value}",
        f"SIDE={package.side.value}",
        f"PACKAGE_ID={package.package_id}",
        f"PACKAGE_STABLE_ID={package.stable_id}",
    )
    lineage_lines = tuple(entry.canonical_line for entry in lineage)

    return "\n".join(header + lineage_lines)


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditManifest:
    """
    Immutable SHA-256 manifest for analytical lineage.

    The manifest is audit-ready but performs no file,
    database, network, broker, or execution write.
    """

    planning_package: StrategyPlanningPackageDecision
    schema_version: str
    lineage: tuple[
        PlanningAuditLineageEntry,
        ...,
    ]
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.planning_package,
            StrategyPlanningPackageDecision,
        ):
            raise ValueError("planning_package must be a StrategyPlanningPackageDecision.")

        if not self.planning_package.is_created:
            raise ValueError("An audit manifest requires a created strategy-planning package.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PLANNING_AUDIT_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current planning-audit schema.")

        if not isinstance(self.lineage, tuple):
            raise ValueError("lineage must be a tuple.")

        if not all(
            isinstance(
                entry,
                PlanningAuditLineageEntry,
            )
            for entry in self.lineage
        ):
            raise ValueError("lineage must contain PlanningAuditLineageEntry objects.")

        components = tuple(entry.component for entry in self.lineage)

        if len(set(components)) != len(components):
            raise ValueError("Planning-audit lineage cannot contain duplicate components.")

        package = self.planning_package.package_required
        expected_lineage = _lineage_for(package)

        if self.lineage != expected_lineage:
            raise ValueError(
                "Planning-audit lineage must exactly match "
                "the package components in deterministic "
                "order."
            )

        digest = _non_empty_string(
            self.digest,
            "digest",
        )

        if not _is_lowercase_sha256(digest):
            raise ValueError("digest must be a lowercase SHA-256 hexadecimal value.")

        expected_payload = _canonical_payload_for(
            package,
            schema_version,
            self.lineage,
        )
        expected_digest = _digest_for_payload(expected_payload)

        if digest != expected_digest:
            raise ValueError("digest does not match the canonical planning-audit payload.")

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "digest",
            digest,
        )

    @property
    def package(self) -> StrategyPlanningPackage:
        return self.planning_package.package_required

    @property
    def broker_symbol(self) -> str:
        return self.package.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.package.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.package.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.package.side

    @property
    def component_count(self) -> int:
        return len(self.lineage)

    @property
    def canonical_payload(self) -> str:
        return _canonical_payload_for(
            self.package,
            self.schema_version,
            self.lineage,
        )

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def is_tamper_evident(self) -> bool:
        return True

    @property
    def is_persisted(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
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
    def manifest_id(self) -> str:
        return f"{self.broker_symbol}:{self.side.value}:PLANNING_AUDIT:SHA256[{self.digest}]"

    @property
    def stable_id(self) -> str:
        return f"{self.planning_package.stable_id}:PLANNING_AUDIT_MANIFEST:{self.manifest_id}"


@dataclass(frozen=True, slots=True)
class _PlanningAuditManifestEvaluation:
    status: PlanningAuditManifestStatus
    reason: PlanningAuditManifestReason
    blockers: tuple[
        PlanningAuditManifestBlocker,
        ...,
    ]
    manifest: StrategyPlanningAuditManifest | None


def _derive_manifest(
    planning_package: StrategyPlanningPackageDecision,
) -> _PlanningAuditManifestEvaluation:
    if planning_package.is_blocked:
        return _PlanningAuditManifestEvaluation(
            status=PlanningAuditManifestStatus.BLOCKED,
            reason=(PlanningAuditManifestReason.PLANNING_PACKAGE_BLOCKED),
            blockers=(PlanningAuditManifestBlocker.PLANNING_PACKAGE_BLOCKED,),
            manifest=None,
        )

    package = planning_package.package_required
    lineage = _lineage_for(package)
    payload = _canonical_payload_for(
        package,
        PLANNING_AUDIT_SCHEMA_VERSION,
        lineage,
    )
    manifest = StrategyPlanningAuditManifest(
        planning_package=planning_package,
        schema_version=(PLANNING_AUDIT_SCHEMA_VERSION),
        lineage=lineage,
        digest=_digest_for_payload(payload),
    )

    return _PlanningAuditManifestEvaluation(
        status=PlanningAuditManifestStatus.CREATED,
        reason=PlanningAuditManifestReason.CREATED,
        blockers=(),
        manifest=manifest,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditManifestDecision:
    """Validated planning-audit manifest result."""

    planning_package: StrategyPlanningPackageDecision
    status: PlanningAuditManifestStatus
    reason: PlanningAuditManifestReason
    blockers: tuple[
        PlanningAuditManifestBlocker,
        ...,
    ]
    manifest: StrategyPlanningAuditManifest | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.planning_package,
            StrategyPlanningPackageDecision,
        ):
            raise ValueError("planning_package must be a StrategyPlanningPackageDecision.")

        try:
            status = PlanningAuditManifestStatus(self.status)
            reason = PlanningAuditManifestReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported planning-audit manifest status or reason.") from error

        blockers = tuple(PlanningAuditManifestBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Planning-audit blockers cannot contain duplicates.")

        if self.manifest is not None and not isinstance(
            self.manifest,
            StrategyPlanningAuditManifest,
        ):
            raise ValueError("manifest must be a StrategyPlanningAuditManifest or None.")

        expected = _derive_manifest(self.planning_package)
        supplied = _PlanningAuditManifestEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            manifest=self.manifest,
        )

        if supplied != expected:
            raise ValueError("Planning-audit result does not match its strategy-planning package.")

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
        return self.planning_package.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.planning_package.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.planning_package.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditManifestStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_manifest(self) -> bool:
        return self.manifest is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def manifest_required(
        self,
    ) -> StrategyPlanningAuditManifest:
        if self.manifest is None:
            raise ValueError("No planning-audit manifest was created.")

        return self.manifest

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
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
            f"{self.planning_package.stable_id}:"
            f"PLANNING_AUDIT_MANIFEST_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditManifestFactory:
    """
    Pure factory for deterministic analytical audit data.

    CREATED produces an in-memory manifest only. No file,
    database, network, or broker write is performed.
    """

    def generate(
        self,
        planning_package: StrategyPlanningPackageDecision,
    ) -> PlanningAuditManifestDecision:
        if not isinstance(
            planning_package,
            StrategyPlanningPackageDecision,
        ):
            raise PlanningAuditManifestError(
                PlanningAuditManifestErrorReason.INVALID_PLANNING_PACKAGE_DECISION,
                "planning_package must be a StrategyPlanningPackageDecision.",
            )

        evaluation = _derive_manifest(planning_package)

        return PlanningAuditManifestDecision(
            planning_package=planning_package,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            manifest=evaluation.manifest,
        )

    def build(
        self,
        planning_package: StrategyPlanningPackageDecision,
    ) -> PlanningAuditManifestDecision:
        """Compatibility alias for generate()."""

        return self.generate(planning_package)

    def evaluate(
        self,
        planning_package: StrategyPlanningPackageDecision,
    ) -> PlanningAuditManifestDecision:
        """Compatibility alias for generate()."""

        return self.generate(planning_package)


def generate_planning_audit_manifest(
    planning_package: StrategyPlanningPackageDecision,
) -> PlanningAuditManifestDecision:
    return StrategyPlanningAuditManifestFactory().generate(planning_package)


AuditLineageComponent = PlanningAuditComponent
AuditLineageEntry = PlanningAuditLineageEntry
PlanningAuditManifest = StrategyPlanningAuditManifest
PlanningAuditManifestFactory = StrategyPlanningAuditManifestFactory
StrategyAuditManifest = StrategyPlanningAuditManifest
StrategyAuditManifestDecision = PlanningAuditManifestDecision
StrategyAuditManifestFactory = StrategyPlanningAuditManifestFactory
