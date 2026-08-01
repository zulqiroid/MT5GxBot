"""Phase 17 paper-mode operational safety audit.

Consumes Step 17.3 deterministic validation evidence and produces a
planning-only immutable audit. All real MT5, broker, account, terminal,
production, live, external-write, and real .env effects remain blocked.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_17_SAFETY_AUDIT_STATUS = "PASSED"
PHASE_17_SAFETY_AUDIT_HANDOFF_STATUS = "READY_FOR_PHASE_17_FINAL_HANDOFF"
PHASE_17_SAFETY_AUDIT_SOURCE = "DETERMINISTIC_PAPER_MODE_OPERATIONAL_VALIDATION_ONLY"

PHASE_17_SAFETY_FINDINGS = (
    "PHASE_16_FINAL_HANDOFF_LINEAGE_PRESERVED",
    "PHASE_17_ADMISSION_LINEAGE_PRESERVED",
    "PHASE_17_BLUEPRINT_LINEAGE_PRESERVED",
    "DETERMINISTIC_OPERATIONAL_VALIDATION_PASSED",
    "ALL_TWENTY_FIVE_RESULTS_FAKE_ONLY",
    "PLANNING_ONLY_BOUNDARY_PRESERVED",
    "REAL_ENV_ACCESS_PROHIBITED",
    "PAPER_MODE_ONLY_PRESERVED",
    "FAIL_CLOSED_CONTROL_PRESERVED",
    "EVIDENCE_HANDOFF_PRESERVED",
    "XAUUSD_CLOSED_CANDLE_SCOPE_PRESERVED",
    "ONE_POSITION_AND_50_BPS_RISK_PRESERVED",
    "OCO_STOP_LOSS_GUARDS_AND_FLAT_STATE_REQUIRED",
    "MARTINGALE_GRID_AND_NO_STOP_LOSS_PROHIBITED",
    "FUTURE_REAL_OPERATION_GATES_PRESERVED",
    "ALL_REAL_RUNTIME_AND_LIVE_EFFECTS_BLOCKED",
)


@dataclass(frozen=True, slots=True)
class Phase17PaperModeOperationalSafetyAuditReport:
    validation_decision: object = field(repr=False)
    validation_report: object = field(repr=False)
    blueprint_decision: object = field(repr=False)
    blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase16_final_handoff: object = field(repr=False)

    audit_status: str
    handoff_status: str
    audit_source: str
    findings: tuple[str, ...]
    finding_count: int

    component_results: int
    requirement_results: int
    track_results: int
    total_results: int

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

    planning_boundary_valid: bool
    operational_controls_valid: bool
    safety_invariants_valid: bool
    lineage_preserved: bool
    real_env_protected: bool
    future_gates_preserved: bool

    runtime_statuses: tuple[str, ...]
    no_real_or_external_effects: bool
    safety_audit_passed: bool
    ready_for_final_handoff: bool

    def __post_init__(self) -> None:
        if (
            self.audit_status != PHASE_17_SAFETY_AUDIT_STATUS
            or self.handoff_status != PHASE_17_SAFETY_AUDIT_HANDOFF_STATUS
            or self.audit_source != PHASE_17_SAFETY_AUDIT_SOURCE
        ):
            raise ValueError("Phase 17 audit metadata changed")
        if self.findings != PHASE_17_SAFETY_FINDINGS:
            raise ValueError("Phase 17 safety findings changed")
        if self.finding_count != 16:
            raise ValueError("exactly sixteen findings are required")
        if (
            self.component_results,
            self.requirement_results,
            self.track_results,
            self.total_results,
        ) != (8, 12, 5, 25):
            raise ValueError("validation evidence counts changed")
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
        required = (
            self.planning_boundary_valid,
            self.operational_controls_valid,
            self.safety_invariants_valid,
            self.lineage_preserved,
            self.real_env_protected,
            self.future_gates_preserved,
            self.no_real_or_external_effects,
            self.safety_audit_passed,
            self.ready_for_final_handoff,
        )
        if not all(required):
            raise ValueError("audit lost a required invariant")
        if self.runtime_statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def audit_id(self) -> str:
        validation_id = str(getattr(self.validation_report, "validation_id", ""))
        material = "|".join(
            (
                validation_id,
                self.audit_status,
                self.handoff_status,
                ",".join(self.findings),
                ",".join(map(str, self.phase16_evidence_counts)),
                ",".join(self.runtime_statuses),
            )
        )
        digest = hashlib.sha256(material.encode()).hexdigest()
        return f"GOLDXBOT_PHASE_17_SAFETY_AUDIT:SHA256[{digest}]"


@dataclass(frozen=True, slots=True)
class Phase17PaperModeOperationalSafetyAuditDecision:
    is_allowed: bool
    report: Phase17PaperModeOperationalSafetyAuditReport | None
    blockers: tuple[str, ...]

    @property
    def report_required(
        self,
    ) -> Phase17PaperModeOperationalSafetyAuditReport:
        if self.report is None:
            raise RuntimeError("Phase 17 paper-mode operational safety audit is blocked.")
        return self.report


class Phase17PaperModeOperationalSafetyAuditor:
    def audit(
        self,
        validation_decision: object,
    ) -> Phase17PaperModeOperationalSafetyAuditDecision:
        if validation_decision is None:
            return Phase17PaperModeOperationalSafetyAuditDecision(
                False,
                None,
                ("phase17_validation_missing",),
            )
        if getattr(validation_decision, "is_allowed", True) is not True:
            return Phase17PaperModeOperationalSafetyAuditDecision(
                False,
                None,
                ("phase17_validation_blocked",),
            )

        try:
            validation = validation_decision.report_required
            blueprint_decision = validation.blueprint_decision
            blueprint = validation.blueprint
            admission_decision = validation.admission_decision
            permit = validation.admission_permit
            source = validation.phase16_final_handoff

            valid = (
                validation.validation_status == "PASSED"
                and validation.validation_outcome == "READY_FOR_PAPER_MODE_OPERATIONAL_SAFETY_AUDIT"
                and (
                    validation.component_results,
                    validation.requirement_results,
                    validation.track_results,
                    validation.total_results,
                )
                == (8, 12, 5, 25)
                and validation.all_results_fake_only is True
                and validation.planning_only_preserved is True
                and validation.fail_closed_preserved is True
                and validation.evidence_handoff_preserved is True
                and validation.real_env_access_performed is False
                and validation.no_real_or_external_effects is True
                and validation.ready_for_operational_safety_audit is True
            )
            lineage = (
                validation_decision.report_required is validation
                and blueprint_decision.blueprint_required is blueprint
                and blueprint.admission_decision is admission_decision
                and blueprint.admission_permit is permit
                and blueprint.phase16_final_handoff is source
                and admission_decision.permit_required is permit
                and permit.source_bundle is source
                and validation.lineage_preserved is True
                and source.phase_status == "PHASE_16_COMPLETE"
            )
            future_gates = len(permit.future_gates) == 9 and all(
                gate.endswith("_GATE_REQUIRED") for gate in permit.future_gates
            )
            controls = (
                blueprint.deterministic_fakes_only is True
                and blueprint.paper_mode_only is True
                and blueprint.fail_closed_required is True
                and blueprint.evidence_handoff_required is True
                and validation.planning_only_preserved is True
            )
            safety = (
                validation.symbol == "XAUUSD"
                and validation.timeframes == ("H4", "H1", "M15", "M5")
                and validation.closed_candles_only is True
                and validation.max_gold_positions == 1
                and validation.aggregate_risk_budget_bps == 50
                and validation.stage_risk_bps == (25, 25)
                and len(permit.safety_requirements) == 12
            )
            forbidden = (
                validation.real_env_access_performed,
                validation.real_preflight_executed,
                validation.real_mt5_imported,
                validation.real_mt5_initialized,
                validation.real_terminal_connected,
                validation.real_broker_access_performed,
                validation.real_account_read_performed,
                validation.order_check_invoked,
                validation.order_send_invoked,
                validation.external_state_written,
                validation.production_activated,
                validation.live_order_submitted,
            )
            no_effects = (
                not any(forbidden)
                and validation.runtime_statuses == ("BLOCKED",) * 8
                and all(
                    result.fake_only and not result.real_effect_performed
                    for result in validation.results
                )
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase17PaperModeOperationalSafetyAuditDecision(
                False,
                None,
                (f"phase17_validation_invalid:{type(error).__name__}",),
            )

        if not all((valid, lineage, future_gates, controls, safety, no_effects)):
            return Phase17PaperModeOperationalSafetyAuditDecision(
                False,
                None,
                ("phase17_operational_safety_contract_invalid",),
            )

        report = Phase17PaperModeOperationalSafetyAuditReport(
            validation_decision=validation_decision,
            validation_report=validation,
            blueprint_decision=blueprint_decision,
            blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=permit,
            phase16_final_handoff=source,
            audit_status=PHASE_17_SAFETY_AUDIT_STATUS,
            handoff_status=PHASE_17_SAFETY_AUDIT_HANDOFF_STATUS,
            audit_source=PHASE_17_SAFETY_AUDIT_SOURCE,
            findings=PHASE_17_SAFETY_FINDINGS,
            finding_count=16,
            component_results=validation.component_results,
            requirement_results=validation.requirement_results,
            track_results=validation.track_results,
            total_results=validation.total_results,
            phase16_evidence_counts=validation.phase16_evidence_counts,
            source_validation_audit_counts=(validation.source_validation_audit_counts),
            source_evidence_counts=validation.source_evidence_counts,
            release_baseline_commit=validation.release_baseline_commit,
            release_baseline_tag=validation.release_baseline_tag,
            symbol=validation.symbol,
            timeframes=validation.timeframes,
            closed_candles_only=validation.closed_candles_only,
            max_gold_positions=validation.max_gold_positions,
            aggregate_risk_budget_bps=(validation.aggregate_risk_budget_bps),
            stage_risk_bps=validation.stage_risk_bps,
            planning_boundary_valid=True,
            operational_controls_valid=controls,
            safety_invariants_valid=safety,
            lineage_preserved=lineage,
            real_env_protected=True,
            future_gates_preserved=future_gates,
            runtime_statuses=validation.runtime_statuses,
            no_real_or_external_effects=no_effects,
            safety_audit_passed=True,
            ready_for_final_handoff=True,
        )
        return Phase17PaperModeOperationalSafetyAuditDecision(
            True,
            report,
            (),
        )


def audit_phase17_paper_mode_operational_safety(
    validation_decision: object,
) -> Phase17PaperModeOperationalSafetyAuditDecision:
    return Phase17PaperModeOperationalSafetyAuditor().audit(validation_decision)


__all__ = (
    "PHASE_17_SAFETY_AUDIT_STATUS",
    "PHASE_17_SAFETY_AUDIT_HANDOFF_STATUS",
    "PHASE_17_SAFETY_AUDIT_SOURCE",
    "PHASE_17_SAFETY_FINDINGS",
    "Phase17PaperModeOperationalSafetyAuditReport",
    "Phase17PaperModeOperationalSafetyAuditDecision",
    "Phase17PaperModeOperationalSafetyAuditor",
    "audit_phase17_paper_mode_operational_safety",
)
