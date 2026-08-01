"""Phase 17 paper-mode operational-readiness blueprint.

Consumes the successful Step 17.1 planning-only admission permit and defines
an immutable deterministic blueprint for paper-mode operational readiness.

No real .env access, MT5 import or initialization, terminal connection,
broker/account access, order operations, external writes, production
activation, or live execution is admitted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_17_BLUEPRINT_SCHEMA_VERSION = "1.0"
PHASE_17_BLUEPRINT_STATUS = "BLUEPRINT_READY"
PHASE_17_BLUEPRINT_MODE = "DETERMINISTIC_PAPER_MODE_PLANNING_ONLY"
PHASE_17_BLUEPRINT_SOURCE = "PHASE_17_ADMISSION_PERMIT_ONLY"
PHASE_17_BLUEPRINT_NEXT_ALLOWED_STEP = "DETERMINISTIC_PAPER_MODE_OPERATIONAL_VALIDATION"

PHASE_17_BLUEPRINT_COMPONENT_NAMES = (
    "PaperModeStartupPlan",
    "PaperModeShutdownPlan",
    "OperatorControlPlan",
    "OfflineObservabilityPlan",
    "FailClosedIncidentDrillPlan",
    "EvidenceCapturePlan",
    "RollbackAndRecoveryPlan",
    "OperationalHandoffPlan",
)

PHASE_17_BLUEPRINT_REQUIREMENTS = (
    "P17-REQ-01: planning-only execution boundary",
    "P17-REQ-02: deterministic paper-mode only",
    "P17-REQ-03: real .env access prohibited",
    "P17-REQ-04: XAUUSD-only scope",
    "P17-REQ-05: closed H4/H1/M15/M5 candles only",
    "P17-REQ-06: one aggregate Gold position maximum",
    "P17-REQ-07: aggregate risk remains 50 bps",
    "P17-REQ-08: staged risk remains 25 plus 25 bps",
    "P17-REQ-09: OCO, broker SL, guards, and flat state required",
    "P17-REQ-10: martingale, grid, and no-SL prohibited",
    "P17-REQ-11: all real runtime and live effects blocked",
    "P17-REQ-12: deterministic validation and safety audit required",
)


@dataclass(frozen=True, slots=True)
class Phase17OperationalComponent:
    ordinal: int
    name: str
    responsibility: str
    real_effect_allowed: bool = False

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise ValueError("component ordinal must be positive")
        if self.name not in PHASE_17_BLUEPRINT_COMPONENT_NAMES:
            raise ValueError("unknown Phase 17 component")
        if not self.responsibility.strip():
            raise ValueError("component responsibility is required")
        if self.real_effect_allowed:
            raise ValueError("Phase 17 components must remain effect-free")


@dataclass(frozen=True, slots=True)
class Phase17OperationalRequirement:
    ordinal: int
    statement: str
    mandatory: bool = True

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise ValueError("requirement ordinal must be positive")
        if self.statement not in PHASE_17_BLUEPRINT_REQUIREMENTS:
            raise ValueError("unknown Phase 17 requirement")
        if self.mandatory is not True:
            raise ValueError("all Phase 17 requirements are mandatory")


PHASE_17_BLUEPRINT_COMPONENTS = tuple(
    Phase17OperationalComponent(
        ordinal=index,
        name=name,
        responsibility=responsibility,
    )
    for index, (name, responsibility) in enumerate(
        (
            (
                "PaperModeStartupPlan",
                "Define deterministic paper-mode startup checks.",
            ),
            (
                "PaperModeShutdownPlan",
                "Define fail-closed shutdown and flat-state checks.",
            ),
            (
                "OperatorControlPlan",
                "Define explicit operator controls and stop conditions.",
            ),
            (
                "OfflineObservabilityPlan",
                "Define local fake-only logs and evidence fields.",
            ),
            (
                "FailClosedIncidentDrillPlan",
                "Define deterministic incident drill outcomes.",
            ),
            (
                "EvidenceCapturePlan",
                "Define immutable paper-mode readiness evidence.",
            ),
            (
                "RollbackAndRecoveryPlan",
                "Define checkpoint rollback and recovery procedures.",
            ),
            (
                "OperationalHandoffPlan",
                "Define audited handoff prerequisites.",
            ),
        ),
        start=1,
    )
)

PHASE_17_BLUEPRINT_REQUIREMENT_OBJECTS = tuple(
    Phase17OperationalRequirement(index, statement)
    for index, statement in enumerate(
        PHASE_17_BLUEPRINT_REQUIREMENTS,
        start=1,
    )
)


@dataclass(frozen=True, slots=True)
class Phase17PaperModeOperationalReadinessBlueprint:
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase16_final_handoff: object = field(repr=False)

    schema_version: str
    blueprint_status: str
    blueprint_mode: str
    blueprint_source: str
    next_allowed_step: str

    components: tuple[Phase17OperationalComponent, ...]
    requirements: tuple[Phase17OperationalRequirement, ...]
    component_count: int
    requirement_count: int
    operational_track_count: int

    phase16_evidence_counts: tuple[int, ...]
    source_validation_audit_counts: tuple[int, ...]
    source_evidence_counts: tuple[int, ...]

    release_baseline_commit: str
    release_baseline_tag: str

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    planning_admitted: bool
    execution_admitted: bool
    real_env_access_allowed: bool
    deterministic_fakes_only: bool
    paper_mode_only: bool
    fail_closed_required: bool
    evidence_handoff_required: bool

    runtime_statuses: tuple[str, ...]
    no_real_or_external_effects: bool
    ready_for_deterministic_validation: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_17_BLUEPRINT_SCHEMA_VERSION:
            raise ValueError("blueprint schema changed")
        if self.blueprint_status != PHASE_17_BLUEPRINT_STATUS:
            raise ValueError("blueprint status changed")
        if self.blueprint_mode != PHASE_17_BLUEPRINT_MODE:
            raise ValueError("blueprint mode changed")
        if self.blueprint_source != PHASE_17_BLUEPRINT_SOURCE:
            raise ValueError("blueprint source changed")
        if self.next_allowed_step != PHASE_17_BLUEPRINT_NEXT_ALLOWED_STEP:
            raise ValueError("next allowed step changed")

        if self.components != PHASE_17_BLUEPRINT_COMPONENTS:
            raise ValueError("blueprint components changed")
        if self.requirements != PHASE_17_BLUEPRINT_REQUIREMENT_OBJECTS:
            raise ValueError("blueprint requirements changed")
        if (
            self.component_count,
            self.requirement_count,
            self.operational_track_count,
        ) != (8, 12, 5):
            raise ValueError("blueprint counts changed")

        if self.phase16_evidence_counts != (8, 12, 5, 25, 16):
            raise ValueError("Phase 16 evidence changed")
        if self.source_validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("source validation/audit evidence changed")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence changed")
        if (
            self.release_baseline_commit != "6ba3a00"
            or self.release_baseline_tag != "goldxbot-phase-15-complete"
        ):
            raise ValueError("release baseline changed")

        if (
            self.symbol != "XAUUSD"
            or self.timeframes != ("H4", "H1", "M15", "M5")
            or not self.closed_candles_only
            or self.max_gold_positions != 1
            or self.aggregate_risk_budget_bps != 50
            or self.stage_risk_bps != (25, 25)
        ):
            raise ValueError("Gold scope or risk invariants changed")

        if not self.planning_admitted or self.execution_admitted:
            raise ValueError("Phase 17 must remain planning-only")
        required = (
            self.deterministic_fakes_only,
            self.paper_mode_only,
            self.fail_closed_required,
            self.evidence_handoff_required,
            self.no_real_or_external_effects,
            self.ready_for_deterministic_validation,
        )
        if not all(required):
            raise ValueError("blueprint lost a required invariant")
        if self.real_env_access_allowed:
            raise ValueError("real .env access must remain prohibited")
        if self.runtime_statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def blueprint_id(self) -> str:
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        material = "|".join(
            (
                permit_id,
                self.schema_version,
                self.blueprint_status,
                self.blueprint_mode,
                self.next_allowed_step,
                ",".join(item.name for item in self.components),
                ",".join(item.statement for item in self.requirements),
                ",".join(map(str, self.phase16_evidence_counts)),
                ",".join(self.runtime_statuses),
            )
        )
        digest = hashlib.sha256(material.encode()).hexdigest()
        return f"GOLDXBOT_PHASE_17_BLUEPRINT:SHA256[{digest}]"


@dataclass(frozen=True, slots=True)
class Phase17PaperModeOperationalReadinessBlueprintDecision:
    is_allowed: bool
    blueprint: Phase17PaperModeOperationalReadinessBlueprint | None
    blockers: tuple[str, ...]

    @property
    def blueprint_required(
        self,
    ) -> Phase17PaperModeOperationalReadinessBlueprint:
        if self.blueprint is None:
            raise RuntimeError("Phase 17 operational blueprint is blocked.")
        return self.blueprint


class Phase17PaperModeOperationalReadinessPlanner:
    def build(
        self,
        admission_decision: object,
    ) -> Phase17PaperModeOperationalReadinessBlueprintDecision:
        if admission_decision is None:
            return Phase17PaperModeOperationalReadinessBlueprintDecision(
                False,
                None,
                ("phase17_admission_missing",),
            )
        if getattr(admission_decision, "is_allowed", True) is not True:
            return Phase17PaperModeOperationalReadinessBlueprintDecision(
                False,
                None,
                ("phase17_admission_blocked",),
            )

        try:
            permit = admission_decision.permit_required
            source = permit.source_bundle
            valid = (
                permit.admission_status
                == "ADMITTED_FOR_PAPER_MODE_OPERATIONAL_READINESS_PLANNING_ONLY"
                and permit.next_allowed_step == "PAPER_MODE_OPERATIONAL_BLUEPRINT"
                and permit.planning_admitted is True
                and permit.execution_admitted is False
                and len(permit.operational_tracks) == 5
                and permit.phase16_evidence_counts == (8, 12, 5, 25, 16)
                and permit.real_env_access_allowed is False
                and permit.runtime_statuses == ("BLOCKED",) * 8
                and permit.no_real_or_external_effects is True
                and permit.foundation_ready is True
                and source.phase_status == "PHASE_16_COMPLETE"
                and source.handoff_status == "PHASE_16_OFFLINE_RELEASE_READINESS_COMPLETE"
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase17PaperModeOperationalReadinessBlueprintDecision(
                False,
                None,
                (f"phase17_admission_invalid:{type(error).__name__}",),
            )

        if not valid:
            return Phase17PaperModeOperationalReadinessBlueprintDecision(
                False,
                None,
                ("phase17_admission_contract_invalid",),
            )

        blueprint = Phase17PaperModeOperationalReadinessBlueprint(
            admission_decision=admission_decision,
            admission_permit=permit,
            phase16_final_handoff=source,
            schema_version=PHASE_17_BLUEPRINT_SCHEMA_VERSION,
            blueprint_status=PHASE_17_BLUEPRINT_STATUS,
            blueprint_mode=PHASE_17_BLUEPRINT_MODE,
            blueprint_source=PHASE_17_BLUEPRINT_SOURCE,
            next_allowed_step=PHASE_17_BLUEPRINT_NEXT_ALLOWED_STEP,
            components=PHASE_17_BLUEPRINT_COMPONENTS,
            requirements=PHASE_17_BLUEPRINT_REQUIREMENT_OBJECTS,
            component_count=8,
            requirement_count=12,
            operational_track_count=5,
            phase16_evidence_counts=permit.phase16_evidence_counts,
            source_validation_audit_counts=(permit.source_validation_audit_counts),
            source_evidence_counts=permit.source_evidence_counts,
            release_baseline_commit=permit.release_baseline_commit,
            release_baseline_tag=permit.release_baseline_tag,
            symbol=permit.symbol,
            timeframes=permit.timeframes,
            closed_candles_only=permit.closed_candles_only,
            max_gold_positions=permit.max_gold_positions,
            aggregate_risk_budget_bps=permit.aggregate_risk_budget_bps,
            stage_risk_bps=permit.stage_risk_bps,
            planning_admitted=True,
            execution_admitted=False,
            real_env_access_allowed=False,
            deterministic_fakes_only=True,
            paper_mode_only=True,
            fail_closed_required=True,
            evidence_handoff_required=True,
            runtime_statuses=permit.runtime_statuses,
            no_real_or_external_effects=True,
            ready_for_deterministic_validation=True,
        )
        return Phase17PaperModeOperationalReadinessBlueprintDecision(
            True,
            blueprint,
            (),
        )


def build_phase17_paper_mode_operational_readiness_blueprint(
    admission_decision: object,
) -> Phase17PaperModeOperationalReadinessBlueprintDecision:
    return Phase17PaperModeOperationalReadinessPlanner().build(admission_decision)


__all__ = (
    "PHASE_17_BLUEPRINT_SCHEMA_VERSION",
    "PHASE_17_BLUEPRINT_STATUS",
    "PHASE_17_BLUEPRINT_MODE",
    "PHASE_17_BLUEPRINT_SOURCE",
    "PHASE_17_BLUEPRINT_NEXT_ALLOWED_STEP",
    "PHASE_17_BLUEPRINT_COMPONENT_NAMES",
    "PHASE_17_BLUEPRINT_REQUIREMENTS",
    "PHASE_17_BLUEPRINT_COMPONENTS",
    "PHASE_17_BLUEPRINT_REQUIREMENT_OBJECTS",
    "Phase17OperationalComponent",
    "Phase17OperationalRequirement",
    "Phase17PaperModeOperationalReadinessBlueprint",
    "Phase17PaperModeOperationalReadinessBlueprintDecision",
    "Phase17PaperModeOperationalReadinessPlanner",
    "build_phase17_paper_mode_operational_readiness_blueprint",
)
