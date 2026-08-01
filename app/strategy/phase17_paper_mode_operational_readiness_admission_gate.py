"""Phase 17 controlled paper-mode operational-readiness admission.

Planning-only and deterministic. Real .env access, MT5 import/initialization,
terminal connection, broker/account access, order operations, external writes,
production activation, and live execution remain blocked.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_17_ADMISSION_STATUS = "ADMITTED_FOR_PAPER_MODE_OPERATIONAL_READINESS_PLANNING_ONLY"
PHASE_17_ADMISSION_MODE = "DETERMINISTIC_PAPER_MODE_PLANNING_ONLY"
PHASE_17_ADMISSION_SOURCE = "PHASE_16_FINAL_HANDOFF_ONLY"
PHASE_17_NEXT_ALLOWED_STEP = "PAPER_MODE_OPERATIONAL_BLUEPRINT"

PHASE_17_OPERATIONAL_TRACKS = (
    "PAPER_MODE_STARTUP_SHUTDOWN_PLANNING",
    "DETERMINISTIC_OPERATOR_CONTROL_PLANNING",
    "OFFLINE_OBSERVABILITY_PLANNING",
    "FAIL_CLOSED_INCIDENT_DRILL_PLANNING",
    "PAPER_MODE_EVIDENCE_HANDOFF_PLANNING",
)

PHASE_17_SAFETY_REQUIREMENTS = (
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

PHASE_17_FUTURE_GATES = (
    "REAL_MT5_IMPORT_GATE_REQUIRED",
    "MT5_INITIALIZATION_GATE_REQUIRED",
    "TERMINAL_CONNECTION_GATE_REQUIRED",
    "BROKER_ACCESS_GATE_REQUIRED",
    "REAL_ACCOUNT_READ_GATE_REQUIRED",
    "ORDER_CHECK_GATE_REQUIRED",
    "ORDER_SEND_GATE_REQUIRED",
    "PRODUCTION_ACTIVATION_GATE_REQUIRED",
    "LIVE_EXECUTION_GATE_REQUIRED",
)


@dataclass(frozen=True, slots=True)
class Phase17PaperModeOperationalReadinessPermit:
    source_bundle: object = field(repr=False)
    admission_status: str
    admission_mode: str
    admission_source: str
    next_allowed_step: str
    planning_admitted: bool
    execution_admitted: bool
    operational_tracks: tuple[str, ...]
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
    safety_requirements: tuple[str, ...]
    future_gates: tuple[str, ...]
    runtime_statuses: tuple[str, ...]
    real_env_access_allowed: bool
    no_real_or_external_effects: bool
    foundation_ready: bool

    def __post_init__(self) -> None:
        if (
            self.admission_status != PHASE_17_ADMISSION_STATUS
            or self.admission_mode != PHASE_17_ADMISSION_MODE
            or self.admission_source != PHASE_17_ADMISSION_SOURCE
            or self.next_allowed_step != PHASE_17_NEXT_ALLOWED_STEP
        ):
            raise ValueError("Phase 17 admission metadata changed")
        if not self.planning_admitted or self.execution_admitted:
            raise ValueError("Phase 17 must remain planning-only")
        if self.operational_tracks != PHASE_17_OPERATIONAL_TRACKS:
            raise ValueError("Phase 17 tracks changed")
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
        if self.safety_requirements != PHASE_17_SAFETY_REQUIREMENTS:
            raise ValueError("safety requirements changed")
        if self.future_gates != PHASE_17_FUTURE_GATES:
            raise ValueError("future gates changed")
        if self.runtime_statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must remain blocked")
        if (
            self.real_env_access_allowed
            or not self.no_real_or_external_effects
            or not self.foundation_ready
        ):
            raise ValueError("Phase 17 safety foundation changed")

    @property
    def permit_id(self) -> str:
        source_id = str(getattr(self.source_bundle, "handoff_id", ""))
        material = "|".join(
            (
                source_id,
                self.admission_status,
                self.admission_mode,
                self.next_allowed_step,
                ",".join(self.operational_tracks),
                ",".join(map(str, self.phase16_evidence_counts)),
                ",".join(self.runtime_statuses),
            )
        )
        digest = hashlib.sha256(material.encode()).hexdigest()
        return f"GOLDXBOT_PHASE_17_PERMIT:SHA256[{digest}]"


@dataclass(frozen=True, slots=True)
class Phase17PaperModeOperationalReadinessAdmissionDecision:
    is_allowed: bool
    permit: Phase17PaperModeOperationalReadinessPermit | None
    blockers: tuple[str, ...]

    @property
    def permit_required(self) -> Phase17PaperModeOperationalReadinessPermit:
        if self.permit is None:
            raise RuntimeError("Phase 17 operational admission is blocked.")
        return self.permit


class Phase17PaperModeOperationalReadinessAdmissionGate:
    def evaluate(
        self,
        phase16_decision: object,
    ) -> Phase17PaperModeOperationalReadinessAdmissionDecision:
        if phase16_decision is None:
            return Phase17PaperModeOperationalReadinessAdmissionDecision(
                False, None, ("phase16_final_handoff_missing",)
            )
        if getattr(phase16_decision, "is_allowed", True) is not True:
            return Phase17PaperModeOperationalReadinessAdmissionDecision(
                False, None, ("phase16_final_handoff_blocked",)
            )
        try:
            source = phase16_decision.handoff_required
            valid = (
                source.phase_status == "PHASE_16_COMPLETE"
                and source.handoff_status == "PHASE_16_OFFLINE_RELEASE_READINESS_COMPLETE"
                and source.release_decision == "OFFLINE_RELEASE_READINESS_ESTABLISHED"
                and (
                    source.component_results,
                    source.requirement_results,
                    source.track_results,
                    source.total_results,
                    source.safety_finding_count,
                )
                == (8, 12, 5, 25, 16)
                and source.phase16_roadmap_complete is True
                and source.next_phase_status == "NOT_DEFINED"
                and source.phase17_admitted is False
                and source.execution_admitted is False
                and source.real_env_protected is True
                and source.runtime_statuses == ("BLOCKED",) * 8
                and source.no_real_or_external_effects is True
                and source.final_handoff_ready is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase17PaperModeOperationalReadinessAdmissionDecision(
                False,
                None,
                (f"phase16_final_handoff_invalid:{type(error).__name__}",),
            )
        if not valid:
            return Phase17PaperModeOperationalReadinessAdmissionDecision(
                False, None, ("phase16_final_handoff_contract_invalid",)
            )

        permit = Phase17PaperModeOperationalReadinessPermit(
            source_bundle=source,
            admission_status=PHASE_17_ADMISSION_STATUS,
            admission_mode=PHASE_17_ADMISSION_MODE,
            admission_source=PHASE_17_ADMISSION_SOURCE,
            next_allowed_step=PHASE_17_NEXT_ALLOWED_STEP,
            planning_admitted=True,
            execution_admitted=False,
            operational_tracks=PHASE_17_OPERATIONAL_TRACKS,
            phase16_evidence_counts=(8, 12, 5, 25, 16),
            source_validation_audit_counts=source.source_validation_audit_counts,
            source_evidence_counts=source.source_evidence_counts,
            release_baseline_commit=source.release_baseline_commit,
            release_baseline_tag=source.release_baseline_tag,
            symbol=source.symbol,
            timeframes=source.timeframes,
            closed_candles_only=source.closed_candles_only,
            max_gold_positions=source.max_gold_positions,
            aggregate_risk_budget_bps=source.aggregate_risk_budget_bps,
            stage_risk_bps=source.stage_risk_bps,
            safety_requirements=PHASE_17_SAFETY_REQUIREMENTS,
            future_gates=PHASE_17_FUTURE_GATES,
            runtime_statuses=source.runtime_statuses,
            real_env_access_allowed=False,
            no_real_or_external_effects=True,
            foundation_ready=True,
        )
        return Phase17PaperModeOperationalReadinessAdmissionDecision(True, permit, ())


def evaluate_phase17_paper_mode_operational_readiness_admission(
    phase16_decision: object,
) -> Phase17PaperModeOperationalReadinessAdmissionDecision:
    return Phase17PaperModeOperationalReadinessAdmissionGate().evaluate(phase16_decision)


__all__ = (
    "PHASE_17_ADMISSION_STATUS",
    "PHASE_17_ADMISSION_MODE",
    "PHASE_17_ADMISSION_SOURCE",
    "PHASE_17_NEXT_ALLOWED_STEP",
    "PHASE_17_OPERATIONAL_TRACKS",
    "PHASE_17_SAFETY_REQUIREMENTS",
    "PHASE_17_FUTURE_GATES",
    "Phase17PaperModeOperationalReadinessPermit",
    "Phase17PaperModeOperationalReadinessAdmissionDecision",
    "Phase17PaperModeOperationalReadinessAdmissionGate",
    "evaluate_phase17_paper_mode_operational_readiness_admission",
)
