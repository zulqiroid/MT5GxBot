"""Phase 15 controlled roadmap-extension admission gate.

Consumes the completed Phase 14 final handoff and admits Phase 15 planning
only. No real MT5, terminal, broker, account, order, external-write,
production, or live execution effect is enabled.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_15_EXTENSION_ADMISSION_SCHEMA_VERSION = "1.0"
PHASE_15_EXTENSION_ADMISSION_STATUS = "ADMITTED_FOR_PLANNING_ONLY"
PHASE_15_EXTENSION_ADMISSION_MODE = "CONTROLLED_ROADMAP_EXTENSION_PLANNING_ONLY"
PHASE_15_EXTENSION_ADMISSION_SOURCE = "PHASE_14_FINAL_ARCHITECTURE_HANDOFF_ONLY"
PHASE_15_EXTENSION_BLOCKED_STATUS = "BLOCKED"

PHASE_15_PLANNING_TRACKS = (
    "REQUIREMENTS_PLANNING",
    "ARCHITECTURE_PLANNING",
    "DETERMINISTIC_VALIDATION_PLANNING",
    "SAFETY_AUDIT_PLANNING",
)

PHASE_15_SAFETY_REQUIREMENTS = (
    "OCO_REQUIRED",
    "BROKER_STOP_LOSS_REQUIRED",
    "GUARDS_REQUIRED",
    "TERMINAL_FLAT_STATE_REQUIRED",
    "MARTINGALE_PROHIBITED",
    "GRID_PROHIBITED",
    "NO_STOP_LOSS_PROHIBITED",
)

PHASE_15_FUTURE_GATE_REQUIREMENTS = (
    "EXPLICIT_HUMAN_AUTHORIZATION_REQUIRED",
    "SEPARATE_RUNTIME_EXECUTION_GATE_REQUIRED",
    "SEPARATE_REAL_ACCOUNT_READ_GATE_REQUIRED",
    "SEPARATE_PRODUCTION_GATE_REQUIRED",
)


@dataclass(frozen=True, slots=True)
class Phase15RoadmapExtensionPermit:
    source_bundle: object = field(repr=False)
    schema_version: str
    admission_status: str
    admission_mode: str
    admission_source: str
    source_phase: int
    target_phase: int
    phase15_planning_admitted: bool
    phase15_execution_admitted: bool
    planning_tracks: tuple[str, ...]
    validation_audit_counts: tuple[int, int, int, int]
    source_evidence_counts: tuple[int, int, int, int, int, int, int]
    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, int]
    safety_requirements: tuple[str, ...]
    future_gate_requirements: tuple[str, ...]
    runtime_statuses: tuple[str, ...]
    no_real_or_external_effects: bool
    phase15_foundation_ready: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_15_EXTENSION_ADMISSION_SCHEMA_VERSION:
            raise ValueError("invalid Phase 15 admission schema")
        if self.admission_status != PHASE_15_EXTENSION_ADMISSION_STATUS:
            raise ValueError("invalid Phase 15 admission status")
        if self.admission_mode != PHASE_15_EXTENSION_ADMISSION_MODE:
            raise ValueError("invalid Phase 15 admission mode")
        if self.admission_source != PHASE_15_EXTENSION_ADMISSION_SOURCE:
            raise ValueError("invalid Phase 15 admission source")
        if (self.source_phase, self.target_phase) != (14, 15):
            raise ValueError("phase transition must be 14 to 15")
        if self.phase15_planning_admitted is not True:
            raise ValueError("Phase 15 planning must be admitted")
        if self.phase15_execution_admitted:
            raise ValueError("Phase 15 execution is not admitted")
        if self.planning_tracks != PHASE_15_PLANNING_TRACKS:
            raise ValueError("Phase 15 planning tracks are inconsistent")
        if self.validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("validation/audit counts are inconsistent")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence counts are inconsistent")
        if self.symbol != "XAUUSD":
            raise ValueError("Phase 15 planning is XAUUSD only")
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
        if self.safety_requirements != PHASE_15_SAFETY_REQUIREMENTS:
            raise ValueError("safety requirements are inconsistent")
        if self.future_gate_requirements != PHASE_15_FUTURE_GATE_REQUIREMENTS:
            raise ValueError("future gate requirements are inconsistent")
        if self.runtime_statuses != (PHASE_15_EXTENSION_BLOCKED_STATUS,) * 8:
            raise ValueError("all real runtime statuses must remain blocked")
        if not self.no_real_or_external_effects:
            raise ValueError("real or external effects are prohibited")
        if not self.phase15_foundation_ready:
            raise ValueError("Phase 15 foundation must be ready")

    @property
    def permit_digest(self) -> str:
        source_handoff_id = str(getattr(self.source_bundle, "handoff_id", ""))
        material = "|".join(
            (
                self.schema_version,
                source_handoff_id,
                self.admission_status,
                self.admission_mode,
                self.admission_source,
                str(self.source_phase),
                str(self.target_phase),
                str(self.phase15_planning_admitted),
                str(self.phase15_execution_admitted),
                ",".join(self.planning_tracks),
                ",".join(map(str, self.validation_audit_counts)),
                ",".join(map(str, self.source_evidence_counts)),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                ",".join(self.safety_requirements),
                ",".join(self.future_gate_requirements),
                ",".join(self.runtime_statuses),
                str(self.no_real_or_external_effects),
                str(self.phase15_foundation_ready),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def permit_id(self) -> str:
        return f"GOLDXBOT_PHASE_15_ROADMAP_EXTENSION_ADMISSION:SHA256[{self.permit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase15RoadmapExtensionAdmissionDecision:
    is_allowed: bool
    permit: Phase15RoadmapExtensionPermit | None
    blockers: tuple[str, ...]

    @property
    def permit_required(self) -> Phase15RoadmapExtensionPermit:
        if self.permit is None:
            raise RuntimeError("Phase 15 roadmap extension admission is blocked.")
        return self.permit


class Phase15RoadmapExtensionAdmissionGate:
    def evaluate(
        self,
        phase14_final_decision: object,
    ) -> Phase15RoadmapExtensionAdmissionDecision:
        if phase14_final_decision is None:
            return Phase15RoadmapExtensionAdmissionDecision(
                False, None, ("phase14_final_handoff_decision_missing",)
            )
        if getattr(phase14_final_decision, "is_allowed", True) is not True:
            return Phase15RoadmapExtensionAdmissionDecision(
                False, None, ("phase14_final_handoff_decision_blocked",)
            )

        try:
            source = phase14_final_decision.bundle_required
            source_valid = (
                source.phase_number == 14
                and source.source_phase_number == 13
                and source.next_phase_number is None
                and source.phase_status == "PHASE_14_COMPLETE"
                and source.handoff_status == "PHASE_14_EXTENSION_COMPLETE"
                and source.phase_complete is True
                and source.extension_roadmap_complete is True
                and source.phase15_admitted is False
                and source.no_real_or_external_effects is True
                and source.lineage_preserved is True
                and source.architecture_blueprint_valid is True
                and source.deterministic_validation_passed is True
                and source.architecture_safety_audit_passed is True
                and source.risk_contract_valid is True
                and source.oco_broker_sl_guards_valid is True
                and source.terminal_flat_state_valid is True
                and source.future_gates_required is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase15RoadmapExtensionAdmissionDecision(
                False,
                None,
                (f"phase14_final_handoff_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase15RoadmapExtensionAdmissionDecision(
                False, None, ("phase14_final_handoff_contract_invalid",)
            )

        permit = Phase15RoadmapExtensionPermit(
            source_bundle=source,
            schema_version=PHASE_15_EXTENSION_ADMISSION_SCHEMA_VERSION,
            admission_status=PHASE_15_EXTENSION_ADMISSION_STATUS,
            admission_mode=PHASE_15_EXTENSION_ADMISSION_MODE,
            admission_source=PHASE_15_EXTENSION_ADMISSION_SOURCE,
            source_phase=14,
            target_phase=15,
            phase15_planning_admitted=True,
            phase15_execution_admitted=False,
            planning_tracks=PHASE_15_PLANNING_TRACKS,
            validation_audit_counts=(
                source.component_result_count,
                source.requirement_result_count,
                source.total_validation_result_count,
                source.architecture_safety_finding_count,
            ),
            source_evidence_counts=(
                source.runtime_operation_count,
                source.blocked_write_operation_count,
                source.error_mapping_count,
                source.snapshot_mapping_count,
                source.total_snapshot_field_count,
                source.prior_validation_event_count,
                source.prior_runtime_safety_finding_count,
            ),
            symbol=source.symbol,
            timeframes=source.timeframes,
            closed_candles_only=source.closed_candles_only,
            max_gold_positions=source.max_gold_positions,
            aggregate_risk_budget_bps=source.aggregate_risk_budget_bps,
            stage_risk_bps=source.stage_risk_bps,
            safety_requirements=PHASE_15_SAFETY_REQUIREMENTS,
            future_gate_requirements=PHASE_15_FUTURE_GATE_REQUIREMENTS,
            runtime_statuses=(
                source.real_preflight_execution_status,
                source.mt5_import_status,
                source.mt5_initialization_status,
                source.terminal_connection_status,
                source.broker_access_status,
                source.real_account_read_status,
                source.production_activation_status,
                source.live_execution_status,
            ),
            no_real_or_external_effects=True,
            phase15_foundation_ready=True,
        )
        return Phase15RoadmapExtensionAdmissionDecision(True, permit, ())


def evaluate_phase15_roadmap_extension(
    phase14_final_decision: object,
) -> Phase15RoadmapExtensionAdmissionDecision:
    return Phase15RoadmapExtensionAdmissionGate().evaluate(phase14_final_decision)


__all__ = (
    "PHASE_15_EXTENSION_ADMISSION_SCHEMA_VERSION",
    "PHASE_15_EXTENSION_ADMISSION_STATUS",
    "PHASE_15_EXTENSION_ADMISSION_MODE",
    "PHASE_15_EXTENSION_ADMISSION_SOURCE",
    "PHASE_15_EXTENSION_BLOCKED_STATUS",
    "PHASE_15_PLANNING_TRACKS",
    "PHASE_15_SAFETY_REQUIREMENTS",
    "PHASE_15_FUTURE_GATE_REQUIREMENTS",
    "Phase15RoadmapExtensionPermit",
    "Phase15RoadmapExtensionAdmissionDecision",
    "Phase15RoadmapExtensionAdmissionGate",
    "evaluate_phase15_roadmap_extension",
)
