"""Final Phase 15 architecture handoff.

Consumes the successful Step 15.4 architecture safety-audit decision and
produces an immutable final handoff that closes the optional Phase 15
controlled roadmap extension.

This module admits no Phase 16 work and performs no real MT5 import,
initialization, terminal connection, broker access, account read, order
operation, external write, production activation, or live execution.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_15_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_15_FINAL_STATUS = "PHASE_15_COMPLETE"
PHASE_15_FINAL_HANDOFF_STATUS = "PHASE_15_EXTENSION_COMPLETE"
PHASE_15_FINAL_HANDOFF_SOURCE = "PHASE_15_ARCHITECTURE_SAFETY_AUDIT_ONLY"
PHASE_15_NEXT_PHASE_STATUS = "NOT_DEFINED"


@dataclass(frozen=True, slots=True)
class Phase15FinalArchitectureHandoff:
    """Immutable final handoff for the Phase 15 optional extension."""

    audit_decision: object = field(repr=False)
    audit_report: object = field(repr=False)
    validation_decision: object = field(repr=False)
    validation_report: object = field(repr=False)
    architecture_decision: object = field(repr=False)
    architecture_blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase14_final_handoff: object = field(repr=False)

    schema_version: str
    phase_status: str
    handoff_status: str
    handoff_source: str

    component_results: int
    requirement_results: int
    total_results: int
    architecture_safety_findings: int
    source_validation_audit_counts: tuple[int, ...]
    source_evidence_counts: tuple[int, ...]

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    phase15_planning_admitted: bool
    phase15_execution_admitted: bool
    extension_roadmap_complete: bool
    next_phase_status: str
    phase16_admitted: bool

    lineage_preserved: bool
    safety_invariants_preserved: bool
    future_gates_preserved: bool
    runtime_statuses: tuple[str, ...]
    no_real_or_external_effects: bool
    final_handoff_ready: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_15_FINAL_HANDOFF_SCHEMA_VERSION:
            raise ValueError("final handoff schema is inconsistent")
        if self.phase_status != PHASE_15_FINAL_STATUS:
            raise ValueError("Phase 15 status is inconsistent")
        if self.handoff_status != PHASE_15_FINAL_HANDOFF_STATUS:
            raise ValueError("Phase 15 handoff status is inconsistent")
        if self.handoff_source != PHASE_15_FINAL_HANDOFF_SOURCE:
            raise ValueError("Phase 15 handoff source is inconsistent")

        if (
            self.component_results,
            self.requirement_results,
            self.total_results,
            self.architecture_safety_findings,
        ) != (8, 12, 20, 16):
            raise ValueError("Phase 15 result counts are inconsistent")
        if self.source_validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("source validation/audit counts changed")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence counts changed")

        if self.symbol != "XAUUSD":
            raise ValueError("final handoff is XAUUSD-only")
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

        if self.phase15_planning_admitted is not True:
            raise ValueError("Phase 15 planning admission was lost")
        if self.phase15_execution_admitted:
            raise ValueError("Phase 15 execution must remain unadmitted")
        if self.extension_roadmap_complete is not True:
            raise ValueError("Phase 15 extension roadmap must be complete")
        if self.next_phase_status != PHASE_15_NEXT_PHASE_STATUS:
            raise ValueError("next phase must remain undefined")
        if self.phase16_admitted:
            raise ValueError("Phase 16 must remain unadmitted")

        required = (
            self.lineage_preserved,
            self.safety_invariants_preserved,
            self.future_gates_preserved,
            self.no_real_or_external_effects,
            self.final_handoff_ready,
        )
        if not all(required):
            raise ValueError("final handoff lost a required invariant")
        if self.runtime_statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def handoff_digest(self) -> str:
        audit_id = str(getattr(self.audit_report, "audit_id", ""))
        material = "|".join(
            (
                self.schema_version,
                audit_id,
                self.phase_status,
                self.handoff_status,
                self.handoff_source,
                str(self.component_results),
                str(self.requirement_results),
                str(self.total_results),
                str(self.architecture_safety_findings),
                ",".join(map(str, self.source_validation_audit_counts)),
                ",".join(map(str, self.source_evidence_counts)),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.extension_roadmap_complete),
                self.next_phase_status,
                str(self.phase16_admitted),
                str(self.no_real_or_external_effects),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return f"GOLDXBOT_PHASE_15_FINAL_ARCHITECTURE_HANDOFF:SHA256[{self.handoff_digest}]"


@dataclass(frozen=True, slots=True)
class Phase15FinalArchitectureHandoffDecision:
    """Allowed or blocked final Phase 15 handoff decision."""

    is_allowed: bool
    handoff: Phase15FinalArchitectureHandoff | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.handoff is None or self.blockers:
                raise ValueError("allowed final handoff is inconsistent")
        elif self.handoff is not None or not self.blockers:
            raise ValueError("blocked final handoff is inconsistent")

    @property
    def handoff_required(self) -> Phase15FinalArchitectureHandoff:
        if self.handoff is None:
            raise RuntimeError("Phase 15 final architecture handoff is blocked.")
        return self.handoff


class Phase15FinalArchitectureHandoffBuilder:
    """Builds the final handoff from Step 15.4 audit evidence."""

    def build(
        self,
        audit_decision: object,
    ) -> Phase15FinalArchitectureHandoffDecision:
        if audit_decision is None:
            return Phase15FinalArchitectureHandoffDecision(
                False,
                None,
                ("phase15_audit_decision_missing",),
            )
        if getattr(audit_decision, "is_allowed", True) is not True:
            return Phase15FinalArchitectureHandoffDecision(
                False,
                None,
                ("phase15_audit_decision_blocked",),
            )

        try:
            audit = audit_decision.report_required
            validation_decision = audit.validation_decision
            validation = audit.validation_report
            architecture_decision = audit.architecture_decision
            blueprint = audit.architecture_blueprint
            admission_decision = audit.admission_decision
            permit = audit.admission_permit
            phase14 = audit.phase14_final_handoff

            audit_valid = (
                audit.audit_status == "PASSED"
                and audit.handoff_status == "READY_FOR_PHASE_15_FINAL_HANDOFF"
                and audit.safety_audit_passed is True
                and audit.ready_for_final_handoff is True
                and audit.finding_count == 16
                and all(finding.status == "PASSED" for finding in audit.findings)
                and audit.no_real_effects is True
            )

            lineage_preserved = (
                audit_decision.report_required is audit
                and validation_decision.report_required is validation
                and architecture_decision.blueprint_required is blueprint
                and blueprint.admission_decision is admission_decision
                and blueprint.admission_permit is permit
                and blueprint.phase14_final_handoff is phase14
                and admission_decision.permit_required is permit
                and permit.source_bundle is phase14
                and phase14.phase_status == "PHASE_14_COMPLETE"
                and phase14.handoff_status == "PHASE_14_EXTENSION_COMPLETE"
                and audit.lineage_preserved is True
            )

            safety_preserved = (
                audit.safety_invariants_valid is True
                and audit.flat_state_required is True
                and blueprint.oco_required is True
                and blueprint.broker_stop_loss_required is True
                and blueprint.guards_required is True
                and blueprint.terminal_flat_state_required is True
                and blueprint.martingale_prohibited is True
                and blueprint.grid_prohibited is True
                and blueprint.no_stop_loss_prohibited is True
            )

            future_gates_preserved = (
                audit.future_gates_required is True
                and blueprint.explicit_human_authorization_required is True
                and blueprint.separate_runtime_execution_gate_required is True
                and blueprint.separate_real_account_read_gate_required is True
                and blueprint.separate_production_gate_required is True
            )

            runtime_statuses = audit.runtime_statuses
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase15FinalArchitectureHandoffDecision(
                False,
                None,
                (f"phase15_audit_invalid:{type(error).__name__}",),
            )

        if not all(
            (
                audit_valid,
                lineage_preserved,
                safety_preserved,
                future_gates_preserved,
                runtime_statuses == ("BLOCKED",) * 8,
            )
        ):
            return Phase15FinalArchitectureHandoffDecision(
                False,
                None,
                ("phase15_final_handoff_contract_invalid",),
            )

        handoff = Phase15FinalArchitectureHandoff(
            audit_decision=audit_decision,
            audit_report=audit,
            validation_decision=validation_decision,
            validation_report=validation,
            architecture_decision=architecture_decision,
            architecture_blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=permit,
            phase14_final_handoff=phase14,
            schema_version=PHASE_15_FINAL_HANDOFF_SCHEMA_VERSION,
            phase_status=PHASE_15_FINAL_STATUS,
            handoff_status=PHASE_15_FINAL_HANDOFF_STATUS,
            handoff_source=PHASE_15_FINAL_HANDOFF_SOURCE,
            component_results=audit.component_results,
            requirement_results=audit.requirement_results,
            total_results=audit.total_results,
            architecture_safety_findings=audit.finding_count,
            source_validation_audit_counts=(audit.source_validation_audit_counts),
            source_evidence_counts=audit.source_evidence_counts,
            symbol=audit.symbol,
            timeframes=audit.timeframes,
            closed_candles_only=audit.closed_candles_only,
            max_gold_positions=audit.max_gold_positions,
            aggregate_risk_budget_bps=audit.aggregate_risk_budget_bps,
            stage_risk_bps=audit.stage_risk_bps,
            phase15_planning_admitted=True,
            phase15_execution_admitted=False,
            extension_roadmap_complete=True,
            next_phase_status=PHASE_15_NEXT_PHASE_STATUS,
            phase16_admitted=False,
            lineage_preserved=lineage_preserved,
            safety_invariants_preserved=safety_preserved,
            future_gates_preserved=future_gates_preserved,
            runtime_statuses=runtime_statuses,
            no_real_or_external_effects=True,
            final_handoff_ready=True,
        )
        return Phase15FinalArchitectureHandoffDecision(True, handoff, ())


def build_phase15_final_architecture_handoff(
    audit_decision: object,
) -> Phase15FinalArchitectureHandoffDecision:
    """Build the final Phase 15 architecture handoff."""

    return Phase15FinalArchitectureHandoffBuilder().build(audit_decision)


__all__ = (
    "PHASE_15_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_15_FINAL_STATUS",
    "PHASE_15_FINAL_HANDOFF_STATUS",
    "PHASE_15_FINAL_HANDOFF_SOURCE",
    "PHASE_15_NEXT_PHASE_STATUS",
    "Phase15FinalArchitectureHandoff",
    "Phase15FinalArchitectureHandoffDecision",
    "Phase15FinalArchitectureHandoffBuilder",
    "build_phase15_final_architecture_handoff",
)
