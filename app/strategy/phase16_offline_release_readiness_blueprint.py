"""Phase 16 offline release-readiness blueprint.

Consumes the successful Phase 16 planning-only admission permit and defines a
deterministic, immutable blueprint for offline release preparation.

No real MT5 import, terminal connection, broker access, real account read,
order check, order send, external write, production activation, or live
execution is admitted by this module.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_16_RELEASE_BLUEPRINT_SCHEMA_VERSION = "1.0"
PHASE_16_RELEASE_BLUEPRINT_STATUS = "BLUEPRINT_READY"
PHASE_16_RELEASE_BLUEPRINT_MODE = "OFFLINE_PLANNING_ONLY"
PHASE_16_RELEASE_BLUEPRINT_SOURCE = "PHASE_16_OFFLINE_RELEASE_READINESS_ADMISSION_ONLY"
PHASE_16_RELEASE_BLUEPRINT_NEXT_ALLOWED = "DETERMINISTIC_OFFLINE_RELEASE_VALIDATION"
PHASE_16_RELEASE_BASELINE_COMMIT = "6ba3a00"
PHASE_16_RELEASE_BASELINE_TAG = "goldxbot-phase-15-complete"
PHASE_16_RELEASE_BLUEPRINT_BLOCKED_STATUS = "BLOCKED"


@dataclass(frozen=True, slots=True)
class Phase16ReleaseReadinessComponent:
    """One immutable offline release-readiness component."""

    ordinal: int
    name: str
    responsibility: str
    input_contract: str
    output_contract: str
    real_effect_allowed: bool = False

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise ValueError("component ordinal must be positive")
        if not all(
            (
                self.name.strip(),
                self.responsibility.strip(),
                self.input_contract.strip(),
                self.output_contract.strip(),
            )
        ):
            raise ValueError("component fields must be non-empty")
        if self.real_effect_allowed:
            raise ValueError("Phase 16 components must remain effect-free")


@dataclass(frozen=True, slots=True)
class Phase16ReleaseReadinessRequirement:
    """One mandatory offline release-readiness requirement."""

    ordinal: int
    code: str
    statement: str
    mandatory: bool = True

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise ValueError("requirement ordinal must be positive")
        if not self.code.strip() or not self.statement.strip():
            raise ValueError("requirement fields must be non-empty")
        if self.mandatory is not True:
            raise ValueError("all Phase 16 requirements are mandatory")


PHASE_16_RELEASE_READINESS_COMPONENTS = (
    Phase16ReleaseReadinessComponent(
        1,
        "FrozenReleaseBaseline",
        "Anchor offline release planning to the verified Phase 15 checkpoint.",
        "Phase16OfflineReleaseReadinessPermit",
        "FrozenReleaseBaselinePlan",
    ),
    Phase16ReleaseReadinessComponent(
        2,
        "VersionAndTagManifest",
        "Define immutable release version and tag evidence.",
        "FrozenReleaseBaselinePlan",
        "VersionTagManifest",
    ),
    Phase16ReleaseReadinessComponent(
        3,
        "ReproducibleEnvironmentChecklist",
        "Define offline environment and dependency verification steps.",
        "VersionTagManifest",
        "EnvironmentChecklist",
    ),
    Phase16ReleaseReadinessComponent(
        4,
        "PaperModeOperatorRunbook",
        "Define paper-mode startup, shutdown, and observation procedures.",
        "EnvironmentChecklist",
        "PaperModeRunbook",
    ),
    Phase16ReleaseReadinessComponent(
        5,
        "OfflineConfigurationValidator",
        "Validate configuration shape without reading or changing real .env.",
        "PaperModeRunbook",
        "OfflineConfigurationPlan",
    ),
    Phase16ReleaseReadinessComponent(
        6,
        "BackupAndRollbackPlan",
        "Define backup, restore, and checkpoint rollback procedures.",
        "OfflineConfigurationPlan",
        "BackupRollbackPlan",
    ),
    Phase16ReleaseReadinessComponent(
        7,
        "OfflineSmokeCommandPlan",
        "Define deterministic fake-only release smoke commands.",
        "BackupRollbackPlan",
        "OfflineSmokePlan",
    ),
    Phase16ReleaseReadinessComponent(
        8,
        "IncidentRecoveryChecklist",
        "Define safe stop, evidence capture, and recovery procedures.",
        "OfflineSmokePlan",
        "IncidentRecoveryChecklist",
    ),
)


PHASE_16_RELEASE_READINESS_REQUIREMENTS = (
    Phase16ReleaseReadinessRequirement(
        1,
        "P16-REQ-01",
        "All work remains offline and planning-only.",
    ),
    Phase16ReleaseReadinessRequirement(
        2,
        "P16-REQ-02",
        "The Phase 15 verified commit and annotated tag remain the baseline.",
    ),
    Phase16ReleaseReadinessRequirement(
        3,
        "P16-REQ-03",
        "The real .env file is never read, changed, copied, or committed.",
    ),
    Phase16ReleaseReadinessRequirement(
        4,
        "P16-REQ-04",
        "Only deterministic fakes and paper-mode procedures are admitted.",
    ),
    Phase16ReleaseReadinessRequirement(
        5,
        "P16-REQ-05",
        "The release scope remains XAUUSD-only.",
    ),
    Phase16ReleaseReadinessRequirement(
        6,
        "P16-REQ-06",
        "Only closed H4, H1, M15, and M5 candles are modeled.",
    ),
    Phase16ReleaseReadinessRequirement(
        7,
        "P16-REQ-07",
        "At most one aggregate Gold position is permitted.",
    ),
    Phase16ReleaseReadinessRequirement(
        8,
        "P16-REQ-08",
        "Aggregate staged risk remains 50 bps as 25 plus 25 bps.",
    ),
    Phase16ReleaseReadinessRequirement(
        9,
        "P16-REQ-09",
        "OCO, broker stop-loss, guards, and terminal-flat state are required.",
    ),
    Phase16ReleaseReadinessRequirement(
        10,
        "P16-REQ-10",
        "Martingale, grid, and no-stop-loss behavior remain prohibited.",
    ),
    Phase16ReleaseReadinessRequirement(
        11,
        "P16-REQ-11",
        "All real MT5, terminal, broker, account, production, and live effects remain blocked.",
    ),
    Phase16ReleaseReadinessRequirement(
        12,
        "P16-REQ-12",
        "Deterministic validation and a separate safety audit are required before final handoff.",
    ),
)


@dataclass(frozen=True, slots=True)
class Phase16OfflineReleaseReadinessBlueprint:
    """Immutable Phase 16 offline release-readiness blueprint."""

    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase15_final_handoff: object = field(repr=False)

    schema_version: str
    blueprint_status: str
    blueprint_mode: str
    blueprint_source: str
    next_allowed_step: str

    release_baseline_commit: str
    release_baseline_tag: str

    components: tuple[Phase16ReleaseReadinessComponent, ...]
    requirements: tuple[Phase16ReleaseReadinessRequirement, ...]
    component_count: int
    requirement_count: int
    release_readiness_track_count: int

    source_phase: int
    target_phase: int
    planning_admitted: bool
    execution_admitted: bool

    source_validation_audit_counts: tuple[int, ...]
    source_evidence_counts: tuple[int, ...]

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    real_env_access_allowed: bool
    deterministic_fakes_only: bool
    paper_mode_only: bool
    backup_and_rollback_required: bool
    incident_recovery_required: bool

    runtime_statuses: tuple[str, ...]
    no_real_or_external_effects: bool
    ready_for_deterministic_offline_validation: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_16_RELEASE_BLUEPRINT_SCHEMA_VERSION:
            raise ValueError("blueprint schema is inconsistent")
        if self.blueprint_status != PHASE_16_RELEASE_BLUEPRINT_STATUS:
            raise ValueError("blueprint status is inconsistent")
        if self.blueprint_mode != PHASE_16_RELEASE_BLUEPRINT_MODE:
            raise ValueError("blueprint mode is inconsistent")
        if self.blueprint_source != PHASE_16_RELEASE_BLUEPRINT_SOURCE:
            raise ValueError("blueprint source is inconsistent")
        if self.next_allowed_step != PHASE_16_RELEASE_BLUEPRINT_NEXT_ALLOWED:
            raise ValueError("next allowed step is inconsistent")

        if self.release_baseline_commit != PHASE_16_RELEASE_BASELINE_COMMIT:
            raise ValueError("release baseline commit changed")
        if self.release_baseline_tag != PHASE_16_RELEASE_BASELINE_TAG:
            raise ValueError("release baseline tag changed")

        if self.components != PHASE_16_RELEASE_READINESS_COMPONENTS:
            raise ValueError("release components are inconsistent")
        if self.requirements != PHASE_16_RELEASE_READINESS_REQUIREMENTS:
            raise ValueError("release requirements are inconsistent")
        if (
            self.component_count,
            self.requirement_count,
            self.release_readiness_track_count,
        ) != (8, 12, 5):
            raise ValueError("release blueprint counts are inconsistent")

        if (self.source_phase, self.target_phase) != (15, 16):
            raise ValueError("phase lineage is inconsistent")
        if self.planning_admitted is not True or self.execution_admitted:
            raise ValueError("Phase 16 must remain planning-only")

        if self.source_validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("source validation/audit counts changed")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence counts changed")

        if self.symbol != "XAUUSD":
            raise ValueError("blueprint is XAUUSD-only")
        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("timeframes are inconsistent")
        if self.closed_candles_only is not True:
            raise ValueError("closed candles are required")
        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required")
        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps")
        if self.stage_risk_bps != (25, 25):
            raise ValueError("staged risk must be 25+25 bps")

        if self.real_env_access_allowed:
            raise ValueError("real .env access must remain prohibited")
        required = (
            self.deterministic_fakes_only,
            self.paper_mode_only,
            self.backup_and_rollback_required,
            self.incident_recovery_required,
            self.no_real_or_external_effects,
            self.ready_for_deterministic_offline_validation,
        )
        if not all(required):
            raise ValueError("release blueprint lost a required invariant")
        if self.runtime_statuses != (PHASE_16_RELEASE_BLUEPRINT_BLOCKED_STATUS,) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def blueprint_digest(self) -> str:
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        component_material = "|".join(
            f"{item.ordinal}:{item.name}:{item.input_contract}:{item.output_contract}"
            for item in self.components
        )
        requirement_material = "|".join(
            f"{item.ordinal}:{item.code}:{item.statement}" for item in self.requirements
        )
        material = "|".join(
            (
                self.schema_version,
                permit_id,
                self.blueprint_status,
                self.blueprint_mode,
                self.blueprint_source,
                self.next_allowed_step,
                self.release_baseline_commit,
                self.release_baseline_tag,
                component_material,
                requirement_material,
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.no_real_or_external_effects),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def blueprint_id(self) -> str:
        return (
            f"GOLDXBOT_PHASE_16_OFFLINE_RELEASE_READINESS_BLUEPRINT:SHA256[{self.blueprint_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase16OfflineReleaseReadinessBlueprintDecision:
    """Allowed or blocked Phase 16 blueprint decision."""

    is_allowed: bool
    blueprint: Phase16OfflineReleaseReadinessBlueprint | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.blueprint is None or self.blockers:
                raise ValueError("allowed blueprint decision is inconsistent")
        elif self.blueprint is not None or not self.blockers:
            raise ValueError("blocked blueprint decision is inconsistent")

    @property
    def blueprint_required(self) -> Phase16OfflineReleaseReadinessBlueprint:
        if self.blueprint is None:
            raise RuntimeError("Phase 16 release-readiness blueprint is blocked.")
        return self.blueprint


class Phase16OfflineReleaseReadinessPlanner:
    """Builds the Phase 16 offline release-readiness blueprint."""

    def build(
        self,
        admission_decision: object,
    ) -> Phase16OfflineReleaseReadinessBlueprintDecision:
        if admission_decision is None:
            return Phase16OfflineReleaseReadinessBlueprintDecision(
                False,
                None,
                ("phase16_admission_decision_missing",),
            )
        if getattr(admission_decision, "is_allowed", True) is not True:
            return Phase16OfflineReleaseReadinessBlueprintDecision(
                False,
                None,
                ("phase16_admission_decision_blocked",),
            )

        try:
            permit = admission_decision.permit_required
            source = permit.source_bundle
            source_valid = (
                permit.admission_status == "ADMITTED_FOR_OFFLINE_RELEASE_READINESS_PLANNING_ONLY"
                and permit.admission_mode == "OFFLINE_RELEASE_READINESS_PLANNING_ONLY"
                and permit.admission_source == "PHASE_15_FINAL_ARCHITECTURE_HANDOFF_ONLY"
                and permit.next_allowed_step == "OFFLINE_RELEASE_READINESS_BLUEPRINT"
                and permit.phase16_planning_admitted is True
                and permit.phase16_execution_admitted is False
                and permit.phase16_foundation_ready is True
                and len(permit.release_readiness_tracks) == 5
                and permit.validation_audit_counts == (8, 12, 20, 16)
                and permit.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)
                and permit.runtime_statuses == ("BLOCKED",) * 8
                and permit.no_real_or_external_effects is True
                and source.phase_status == "PHASE_15_COMPLETE"
                and source.handoff_status == "PHASE_15_EXTENSION_COMPLETE"
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase16OfflineReleaseReadinessBlueprintDecision(
                False,
                None,
                (f"phase16_admission_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase16OfflineReleaseReadinessBlueprintDecision(
                False,
                None,
                ("phase16_admission_contract_invalid",),
            )

        blueprint = Phase16OfflineReleaseReadinessBlueprint(
            admission_decision=admission_decision,
            admission_permit=permit,
            phase15_final_handoff=source,
            schema_version=PHASE_16_RELEASE_BLUEPRINT_SCHEMA_VERSION,
            blueprint_status=PHASE_16_RELEASE_BLUEPRINT_STATUS,
            blueprint_mode=PHASE_16_RELEASE_BLUEPRINT_MODE,
            blueprint_source=PHASE_16_RELEASE_BLUEPRINT_SOURCE,
            next_allowed_step=PHASE_16_RELEASE_BLUEPRINT_NEXT_ALLOWED,
            release_baseline_commit=PHASE_16_RELEASE_BASELINE_COMMIT,
            release_baseline_tag=PHASE_16_RELEASE_BASELINE_TAG,
            components=PHASE_16_RELEASE_READINESS_COMPONENTS,
            requirements=PHASE_16_RELEASE_READINESS_REQUIREMENTS,
            component_count=len(PHASE_16_RELEASE_READINESS_COMPONENTS),
            requirement_count=len(PHASE_16_RELEASE_READINESS_REQUIREMENTS),
            release_readiness_track_count=len(permit.release_readiness_tracks),
            source_phase=permit.source_phase,
            target_phase=permit.target_phase,
            planning_admitted=permit.phase16_planning_admitted,
            execution_admitted=permit.phase16_execution_admitted,
            source_validation_audit_counts=permit.validation_audit_counts,
            source_evidence_counts=permit.source_evidence_counts,
            symbol=permit.symbol,
            timeframes=permit.timeframes,
            closed_candles_only=permit.closed_candles_only,
            max_gold_positions=permit.max_gold_positions,
            aggregate_risk_budget_bps=permit.aggregate_risk_budget_bps,
            stage_risk_bps=permit.stage_risk_bps,
            real_env_access_allowed=False,
            deterministic_fakes_only=True,
            paper_mode_only=True,
            backup_and_rollback_required=True,
            incident_recovery_required=True,
            runtime_statuses=permit.runtime_statuses,
            no_real_or_external_effects=True,
            ready_for_deterministic_offline_validation=True,
        )
        return Phase16OfflineReleaseReadinessBlueprintDecision(
            True,
            blueprint,
            (),
        )


def build_phase16_offline_release_readiness_blueprint(
    admission_decision: object,
) -> Phase16OfflineReleaseReadinessBlueprintDecision:
    """Build the Phase 16 offline release-readiness blueprint."""

    return Phase16OfflineReleaseReadinessPlanner().build(admission_decision)


__all__ = (
    "PHASE_16_RELEASE_BLUEPRINT_SCHEMA_VERSION",
    "PHASE_16_RELEASE_BLUEPRINT_STATUS",
    "PHASE_16_RELEASE_BLUEPRINT_MODE",
    "PHASE_16_RELEASE_BLUEPRINT_SOURCE",
    "PHASE_16_RELEASE_BLUEPRINT_NEXT_ALLOWED",
    "PHASE_16_RELEASE_BASELINE_COMMIT",
    "PHASE_16_RELEASE_BASELINE_TAG",
    "PHASE_16_RELEASE_BLUEPRINT_BLOCKED_STATUS",
    "PHASE_16_RELEASE_READINESS_COMPONENTS",
    "PHASE_16_RELEASE_READINESS_REQUIREMENTS",
    "Phase16ReleaseReadinessComponent",
    "Phase16ReleaseReadinessRequirement",
    "Phase16OfflineReleaseReadinessBlueprint",
    "Phase16OfflineReleaseReadinessBlueprintDecision",
    "Phase16OfflineReleaseReadinessPlanner",
    "build_phase16_offline_release_readiness_blueprint",
)
