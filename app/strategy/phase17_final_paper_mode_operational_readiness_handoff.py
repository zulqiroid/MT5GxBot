"""Phase 17 final paper-mode operational-readiness handoff.

Consumes the successful Step 17.4 paper-mode operational safety-audit
decision and closes the Phase 17 planning-only roadmap with an immutable
final handoff.

This handoff is not authorization for real MT5 import or initialization,
terminal connection, broker/account access, order operations, external
writes, production activation, or live execution. All such effects remain
blocked.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_17_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_17_FINAL_STATUS = "PHASE_17_COMPLETE"
PHASE_17_FINAL_HANDOFF_STATUS = "PHASE_17_PAPER_MODE_OPERATIONAL_READINESS_COMPLETE"
PHASE_17_FINAL_HANDOFF_SOURCE = "PHASE_17_PAPER_MODE_OPERATIONAL_SAFETY_AUDIT_ONLY"
PHASE_17_FINAL_DECISION = "PAPER_MODE_OPERATIONAL_READINESS_ESTABLISHED"
PHASE_17_FINAL_NEXT_PHASE_STATUS = "NOT_DEFINED"
PHASE_17_FINAL_BLOCKED_STATUS = "BLOCKED"


@dataclass(frozen=True, slots=True)
class Phase17FinalPaperModeOperationalReadinessHandoff:
    safety_audit_decision: object = field(repr=False)
    safety_audit_report: object = field(repr=False)
    validation_decision: object = field(repr=False)
    validation_report: object = field(repr=False)
    blueprint_decision: object = field(repr=False)
    blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase16_final_handoff: object = field(repr=False)

    schema_version: str
    phase_status: str
    handoff_status: str
    handoff_source: str
    readiness_decision: str

    component_results: int
    requirement_results: int
    track_results: int
    total_results: int
    safety_finding_count: int

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
    planning_boundary_preserved: bool
    operational_controls_preserved: bool
    safety_invariants_preserved: bool
    lineage_preserved: bool
    real_env_protected: bool
    future_gates_preserved: bool

    phase17_roadmap_complete: bool
    next_phase_status: str
    phase18_admitted: bool

    runtime_statuses: tuple[str, ...]
    no_real_or_external_effects: bool
    final_handoff_ready: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_17_FINAL_HANDOFF_SCHEMA_VERSION:
            raise ValueError("final handoff schema changed")
        if self.phase_status != PHASE_17_FINAL_STATUS:
            raise ValueError("Phase 17 status changed")
        if self.handoff_status != PHASE_17_FINAL_HANDOFF_STATUS:
            raise ValueError("final handoff status changed")
        if self.handoff_source != PHASE_17_FINAL_HANDOFF_SOURCE:
            raise ValueError("final handoff source changed")
        if self.readiness_decision != PHASE_17_FINAL_DECISION:
            raise ValueError("readiness decision changed")

        if (
            self.component_results,
            self.requirement_results,
            self.track_results,
            self.total_results,
            self.safety_finding_count,
        ) != (8, 12, 5, 25, 16):
            raise ValueError("Phase 17 evidence counts changed")
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
            self.planning_boundary_preserved,
            self.operational_controls_preserved,
            self.safety_invariants_preserved,
            self.lineage_preserved,
            self.real_env_protected,
            self.future_gates_preserved,
            self.phase17_roadmap_complete,
            self.no_real_or_external_effects,
            self.final_handoff_ready,
        )
        if not all(required):
            raise ValueError("final handoff lost a required invariant")
        if self.next_phase_status != PHASE_17_FINAL_NEXT_PHASE_STATUS:
            raise ValueError("next phase must remain undefined")
        if self.phase18_admitted:
            raise ValueError("Phase 18 must not be admitted")
        if self.runtime_statuses != (PHASE_17_FINAL_BLOCKED_STATUS,) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def handoff_id(self) -> str:
        audit_id = str(getattr(self.safety_audit_report, "audit_id", ""))
        material = "|".join(
            (
                audit_id,
                self.schema_version,
                self.phase_status,
                self.handoff_status,
                self.handoff_source,
                self.readiness_decision,
                str(self.component_results),
                str(self.requirement_results),
                str(self.track_results),
                str(self.total_results),
                str(self.safety_finding_count),
                ",".join(map(str, self.phase16_evidence_counts)),
                ",".join(map(str, self.source_validation_audit_counts)),
                ",".join(map(str, self.source_evidence_counts)),
                self.release_baseline_commit,
                self.release_baseline_tag,
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                self.next_phase_status,
                str(self.phase18_admitted),
                ",".join(self.runtime_statuses),
                str(self.no_real_or_external_effects),
            )
        )
        digest = hashlib.sha256(material.encode()).hexdigest()
        return f"GOLDXBOT_PHASE_17_FINAL_HANDOFF:SHA256[{digest}]"


@dataclass(frozen=True, slots=True)
class Phase17FinalPaperModeOperationalReadinessDecision:
    is_allowed: bool
    handoff: Phase17FinalPaperModeOperationalReadinessHandoff | None
    blockers: tuple[str, ...]

    @property
    def handoff_required(
        self,
    ) -> Phase17FinalPaperModeOperationalReadinessHandoff:
        if self.handoff is None:
            raise RuntimeError("Phase 17 final paper-mode operational handoff is blocked.")
        return self.handoff


class Phase17FinalPaperModeOperationalReadinessGate:
    def finalize(
        self,
        safety_audit_decision: object,
    ) -> Phase17FinalPaperModeOperationalReadinessDecision:
        if safety_audit_decision is None:
            return Phase17FinalPaperModeOperationalReadinessDecision(
                False,
                None,
                ("phase17_safety_audit_missing",),
            )
        if getattr(safety_audit_decision, "is_allowed", True) is not True:
            return Phase17FinalPaperModeOperationalReadinessDecision(
                False,
                None,
                ("phase17_safety_audit_blocked",),
            )

        try:
            audit = safety_audit_decision.report_required
            validation_decision = audit.validation_decision
            validation = audit.validation_report
            blueprint_decision = audit.blueprint_decision
            blueprint = audit.blueprint
            admission_decision = audit.admission_decision
            permit = audit.admission_permit
            source = audit.phase16_final_handoff

            audit_valid = (
                audit.audit_status == "PASSED"
                and audit.handoff_status == "READY_FOR_PHASE_17_FINAL_HANDOFF"
                and audit.audit_source == "DETERMINISTIC_PAPER_MODE_OPERATIONAL_VALIDATION_ONLY"
                and audit.finding_count == 16
                and len(audit.findings) == 16
                and all(isinstance(finding, str) and bool(finding) for finding in audit.findings)
                and (
                    audit.component_results,
                    audit.requirement_results,
                    audit.track_results,
                    audit.total_results,
                )
                == (8, 12, 5, 25)
                and audit.planning_boundary_valid is True
                and audit.operational_controls_valid is True
                and audit.safety_invariants_valid is True
                and audit.real_env_protected is True
                and audit.future_gates_preserved is True
                and audit.no_real_or_external_effects is True
                and audit.safety_audit_passed is True
                and audit.ready_for_final_handoff is True
            )

            lineage_preserved = (
                safety_audit_decision.report_required is audit
                and validation_decision.report_required is validation
                and blueprint_decision.blueprint_required is blueprint
                and blueprint.admission_decision is admission_decision
                and blueprint.admission_permit is permit
                and blueprint.phase16_final_handoff is source
                and admission_decision.permit_required is permit
                and permit.source_bundle is source
                and audit.lineage_preserved is True
                and validation.lineage_preserved is True
                and source.phase_status == "PHASE_16_COMPLETE"
                and source.handoff_status == "PHASE_16_OFFLINE_RELEASE_READINESS_COMPLETE"
            )

            evidence_preserved = (
                audit.phase16_evidence_counts == (8, 12, 5, 25, 16)
                and audit.source_validation_audit_counts == (8, 12, 20, 16)
                and audit.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)
                and validation.validation_status == "PASSED"
                and validation.total_results == 25
                and blueprint.blueprint_status == "BLUEPRINT_READY"
                and blueprint.component_count == 8
                and blueprint.requirement_count == 12
                and blueprint.operational_track_count == 5
                and permit.planning_admitted is True
                and permit.execution_admitted is False
            )

            forbidden_effects = (
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
            runtime_statuses = audit.runtime_statuses
            no_real_effects = (
                not any(forbidden_effects)
                and runtime_statuses == ("BLOCKED",) * 8
                and validation.no_real_or_external_effects is True
                and audit.no_real_or_external_effects is True
                and blueprint.no_real_or_external_effects is True
                and permit.no_real_or_external_effects is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase17FinalPaperModeOperationalReadinessDecision(
                False,
                None,
                (f"phase17_safety_audit_invalid:{type(error).__name__}",),
            )

        if not all(
            (
                audit_valid,
                lineage_preserved,
                evidence_preserved,
                no_real_effects,
            )
        ):
            return Phase17FinalPaperModeOperationalReadinessDecision(
                False,
                None,
                ("phase17_final_handoff_contract_invalid",),
            )

        handoff = Phase17FinalPaperModeOperationalReadinessHandoff(
            safety_audit_decision=safety_audit_decision,
            safety_audit_report=audit,
            validation_decision=validation_decision,
            validation_report=validation,
            blueprint_decision=blueprint_decision,
            blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=permit,
            phase16_final_handoff=source,
            schema_version=PHASE_17_FINAL_HANDOFF_SCHEMA_VERSION,
            phase_status=PHASE_17_FINAL_STATUS,
            handoff_status=PHASE_17_FINAL_HANDOFF_STATUS,
            handoff_source=PHASE_17_FINAL_HANDOFF_SOURCE,
            readiness_decision=PHASE_17_FINAL_DECISION,
            component_results=audit.component_results,
            requirement_results=audit.requirement_results,
            track_results=audit.track_results,
            total_results=audit.total_results,
            safety_finding_count=audit.finding_count,
            phase16_evidence_counts=audit.phase16_evidence_counts,
            source_validation_audit_counts=(audit.source_validation_audit_counts),
            source_evidence_counts=audit.source_evidence_counts,
            release_baseline_commit=audit.release_baseline_commit,
            release_baseline_tag=audit.release_baseline_tag,
            symbol=audit.symbol,
            timeframes=audit.timeframes,
            closed_candles_only=audit.closed_candles_only,
            max_gold_positions=audit.max_gold_positions,
            aggregate_risk_budget_bps=audit.aggregate_risk_budget_bps,
            stage_risk_bps=audit.stage_risk_bps,
            planning_admitted=True,
            execution_admitted=False,
            planning_boundary_preserved=audit.planning_boundary_valid,
            operational_controls_preserved=(audit.operational_controls_valid),
            safety_invariants_preserved=audit.safety_invariants_valid,
            lineage_preserved=lineage_preserved,
            real_env_protected=audit.real_env_protected,
            future_gates_preserved=audit.future_gates_preserved,
            phase17_roadmap_complete=True,
            next_phase_status=PHASE_17_FINAL_NEXT_PHASE_STATUS,
            phase18_admitted=False,
            runtime_statuses=runtime_statuses,
            no_real_or_external_effects=no_real_effects,
            final_handoff_ready=True,
        )
        return Phase17FinalPaperModeOperationalReadinessDecision(
            True,
            handoff,
            (),
        )


def finalize_phase17_paper_mode_operational_readiness(
    safety_audit_decision: object,
) -> Phase17FinalPaperModeOperationalReadinessDecision:
    return Phase17FinalPaperModeOperationalReadinessGate().finalize(safety_audit_decision)


__all__ = (
    "PHASE_17_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_17_FINAL_STATUS",
    "PHASE_17_FINAL_HANDOFF_STATUS",
    "PHASE_17_FINAL_HANDOFF_SOURCE",
    "PHASE_17_FINAL_DECISION",
    "PHASE_17_FINAL_NEXT_PHASE_STATUS",
    "PHASE_17_FINAL_BLOCKED_STATUS",
    "Phase17FinalPaperModeOperationalReadinessHandoff",
    "Phase17FinalPaperModeOperationalReadinessDecision",
    "Phase17FinalPaperModeOperationalReadinessGate",
    "finalize_phase17_paper_mode_operational_readiness",
)
