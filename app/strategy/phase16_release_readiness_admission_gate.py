"""Phase 16 offline release-readiness admission gate.

Planning-only. No real MT5, terminal, broker, account, production, live
execution, order operations, or external writes are admitted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_16_ADMISSION_SCHEMA_VERSION = "1.0"
PHASE_16_ADMISSION_STATUS = "ADMITTED_FOR_OFFLINE_RELEASE_READINESS_PLANNING_ONLY"
PHASE_16_ADMISSION_MODE = "OFFLINE_RELEASE_READINESS_PLANNING_ONLY"
PHASE_16_ADMISSION_SOURCE = "PHASE_15_FINAL_ARCHITECTURE_HANDOFF_ONLY"
PHASE_16_NEXT_ALLOWED_STEP = "OFFLINE_RELEASE_READINESS_BLUEPRINT"
PHASE_16_BLOCKED_STATUS = "BLOCKED"

PHASE_16_RELEASE_READINESS_TRACKS = (
    "FROZEN_RELEASE_BASELINE_PLANNING",
    "PAPER_MODE_OPERATOR_RUNBOOK_PLANNING",
    "CONFIGURATION_VALIDATION_PLANNING",
    "BACKUP_AND_ROLLBACK_PLANNING",
    "OFFLINE_SMOKE_VALIDATION_PLANNING",
)

PHASE_16_SAFETY_REQUIREMENTS = (
    "XAUUSD_ONLY",
    "CLOSED_H4_H1_M15_M5_ONLY",
    "ONE_GOLD_POSITION_MAXIMUM",
    "AGGREGATE_RISK_50_BPS",
    "STAGED_RISK_25_PLUS_25_BPS",
    "OCO_REQUIRED",
    "BROKER_STOP_LOSS_REQUIRED",
    "GUARDS_REQUIRED",
    "TERMINAL_FLAT_STATE_REQUIRED",
    "MARTINGALE_PROHIBITED",
    "GRID_PROHIBITED",
    "NO_STOP_LOSS_PROHIBITED",
)

PHASE_16_FUTURE_GATE_REQUIREMENTS = (
    "EXPLICIT_HUMAN_AUTHORIZATION_REQUIRED",
    "SEPARATE_REAL_MT5_IMPORT_GATE_REQUIRED",
    "SEPARATE_TERMINAL_CONNECTION_GATE_REQUIRED",
    "SEPARATE_REAL_ACCOUNT_READ_GATE_REQUIRED",
    "SEPARATE_PRODUCTION_GATE_REQUIRED",
    "SEPARATE_LIVE_EXECUTION_GATE_REQUIRED",
)


@dataclass(frozen=True, slots=True)
class Phase16OfflineReleaseReadinessPermit:
    source_bundle: object = field(repr=False)
    schema_version: str
    admission_status: str
    admission_mode: str
    admission_source: str
    next_allowed_step: str
    source_phase: int
    target_phase: int
    phase16_planning_admitted: bool
    phase16_execution_admitted: bool
    release_readiness_tracks: tuple[str, ...]
    validation_audit_counts: tuple[int, ...]
    source_evidence_counts: tuple[int, ...]
    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]
    safety_requirements: tuple[str, ...]
    future_gate_requirements: tuple[str, ...]
    runtime_statuses: tuple[str, ...]
    no_real_or_external_effects: bool
    phase16_foundation_ready: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_16_ADMISSION_SCHEMA_VERSION:
            raise ValueError("schema mismatch")
        if self.admission_status != PHASE_16_ADMISSION_STATUS:
            raise ValueError("status mismatch")
        if self.admission_mode != PHASE_16_ADMISSION_MODE:
            raise ValueError("mode mismatch")
        if self.admission_source != PHASE_16_ADMISSION_SOURCE:
            raise ValueError("source mismatch")
        if self.next_allowed_step != PHASE_16_NEXT_ALLOWED_STEP:
            raise ValueError("next step mismatch")
        if (self.source_phase, self.target_phase) != (15, 16):
            raise ValueError("phase lineage mismatch")
        if not self.phase16_planning_admitted or self.phase16_execution_admitted:
            raise ValueError("Phase 16 must remain planning-only")
        if self.release_readiness_tracks != PHASE_16_RELEASE_READINESS_TRACKS:
            raise ValueError("readiness tracks changed")
        if self.validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("validation/audit counts changed")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence changed")
        if self.symbol != "XAUUSD":
            raise ValueError("XAUUSD-only")
        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("timeframes changed")
        if not self.closed_candles_only:
            raise ValueError("closed candles required")
        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum required")
        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must remain 50 bps")
        if self.stage_risk_bps != (25, 25):
            raise ValueError("staged risk must remain 25+25 bps")
        if self.safety_requirements != PHASE_16_SAFETY_REQUIREMENTS:
            raise ValueError("safety requirements changed")
        if self.future_gate_requirements != PHASE_16_FUTURE_GATE_REQUIREMENTS:
            raise ValueError("future gate requirements changed")
        if self.runtime_statuses != (PHASE_16_BLOCKED_STATUS,) * 8:
            raise ValueError("real runtime statuses must remain blocked")
        if not self.no_real_or_external_effects:
            raise ValueError("real/external effects are forbidden")
        if not self.phase16_foundation_ready:
            raise ValueError("Phase 16 foundation is not ready")

    @property
    def permit_digest(self) -> str:
        source_id = str(getattr(self.source_bundle, "handoff_id", ""))
        material = "|".join(
            (
                self.schema_version,
                source_id,
                self.admission_status,
                self.admission_mode,
                self.next_allowed_step,
                ",".join(self.release_readiness_tracks),
                ",".join(map(str, self.validation_audit_counts)),
                ",".join(map(str, self.source_evidence_counts)),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                ",".join(self.safety_requirements),
                ",".join(self.future_gate_requirements),
                ",".join(self.runtime_statuses),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def permit_id(self) -> str:
        return f"GOLDXBOT_PHASE_16_OFFLINE_RELEASE_READINESS_PERMIT:SHA256[{self.permit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase16OfflineReleaseReadinessAdmissionDecision:
    is_allowed: bool
    permit: Phase16OfflineReleaseReadinessPermit | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.permit is None or self.blockers:
                raise ValueError("allowed decision mismatch")
        elif self.permit is not None or not self.blockers:
            raise ValueError("blocked decision mismatch")

    @property
    def permit_required(self) -> Phase16OfflineReleaseReadinessPermit:
        if self.permit is None:
            raise RuntimeError("Phase 16 offline release admission is blocked.")
        return self.permit


class Phase16OfflineReleaseReadinessAdmissionGate:
    def evaluate(
        self,
        phase15_handoff_decision: object,
    ) -> Phase16OfflineReleaseReadinessAdmissionDecision:
        if phase15_handoff_decision is None:
            return Phase16OfflineReleaseReadinessAdmissionDecision(
                False,
                None,
                ("phase15_final_handoff_decision_missing",),
            )
        if getattr(phase15_handoff_decision, "is_allowed", True) is not True:
            return Phase16OfflineReleaseReadinessAdmissionDecision(
                False,
                None,
                ("phase15_final_handoff_decision_blocked",),
            )

        try:
            handoff = phase15_handoff_decision.handoff_required
            source_valid = (
                handoff.phase_status == "PHASE_15_COMPLETE"
                and handoff.handoff_status == "PHASE_15_EXTENSION_COMPLETE"
                and (
                    handoff.component_results,
                    handoff.requirement_results,
                    handoff.total_results,
                    handoff.architecture_safety_findings,
                )
                == (8, 12, 20, 16)
                and handoff.source_validation_audit_counts == (8, 12, 20, 16)
                and handoff.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)
                and handoff.extension_roadmap_complete is True
                and handoff.next_phase_status == "NOT_DEFINED"
                and handoff.phase16_admitted is False
                and handoff.lineage_preserved is True
                and handoff.safety_invariants_preserved is True
                and handoff.future_gates_preserved is True
                and handoff.runtime_statuses == ("BLOCKED",) * 8
                and handoff.no_real_or_external_effects is True
                and handoff.final_handoff_ready is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase16OfflineReleaseReadinessAdmissionDecision(
                False,
                None,
                (f"phase15_final_handoff_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase16OfflineReleaseReadinessAdmissionDecision(
                False,
                None,
                ("phase15_final_handoff_contract_invalid",),
            )

        permit = Phase16OfflineReleaseReadinessPermit(
            source_bundle=handoff,
            schema_version=PHASE_16_ADMISSION_SCHEMA_VERSION,
            admission_status=PHASE_16_ADMISSION_STATUS,
            admission_mode=PHASE_16_ADMISSION_MODE,
            admission_source=PHASE_16_ADMISSION_SOURCE,
            next_allowed_step=PHASE_16_NEXT_ALLOWED_STEP,
            source_phase=15,
            target_phase=16,
            phase16_planning_admitted=True,
            phase16_execution_admitted=False,
            release_readiness_tracks=PHASE_16_RELEASE_READINESS_TRACKS,
            validation_audit_counts=handoff.source_validation_audit_counts,
            source_evidence_counts=handoff.source_evidence_counts,
            symbol=handoff.symbol,
            timeframes=handoff.timeframes,
            closed_candles_only=handoff.closed_candles_only,
            max_gold_positions=handoff.max_gold_positions,
            aggregate_risk_budget_bps=handoff.aggregate_risk_budget_bps,
            stage_risk_bps=handoff.stage_risk_bps,
            safety_requirements=PHASE_16_SAFETY_REQUIREMENTS,
            future_gate_requirements=PHASE_16_FUTURE_GATE_REQUIREMENTS,
            runtime_statuses=handoff.runtime_statuses,
            no_real_or_external_effects=True,
            phase16_foundation_ready=True,
        )
        return Phase16OfflineReleaseReadinessAdmissionDecision(True, permit, ())


def evaluate_phase16_offline_release_readiness_admission(
    phase15_handoff_decision: object,
) -> Phase16OfflineReleaseReadinessAdmissionDecision:
    return Phase16OfflineReleaseReadinessAdmissionGate().evaluate(phase15_handoff_decision)


__all__ = (
    "PHASE_16_ADMISSION_SCHEMA_VERSION",
    "PHASE_16_ADMISSION_STATUS",
    "PHASE_16_ADMISSION_MODE",
    "PHASE_16_ADMISSION_SOURCE",
    "PHASE_16_NEXT_ALLOWED_STEP",
    "PHASE_16_BLOCKED_STATUS",
    "PHASE_16_RELEASE_READINESS_TRACKS",
    "PHASE_16_SAFETY_REQUIREMENTS",
    "PHASE_16_FUTURE_GATE_REQUIREMENTS",
    "Phase16OfflineReleaseReadinessPermit",
    "Phase16OfflineReleaseReadinessAdmissionDecision",
    "Phase16OfflineReleaseReadinessAdmissionGate",
    "evaluate_phase16_offline_release_readiness_admission",
)
