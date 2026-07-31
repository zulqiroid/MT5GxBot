"""Phase 15 deterministic architecture safety audit.

Consumes the successful Step 15.3 deterministic fake-validation decision and
produces an immutable safety-audit report for the Phase 15 planning-only
architecture.

No real MT5 import, initialization, terminal connection, broker access,
account read, order check, order send, external write, production activation,
or live execution is performed or admitted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_15_ARCHITECTURE_SAFETY_AUDIT_STATUS = "PASSED"
PHASE_15_ARCHITECTURE_SAFETY_AUDIT_HANDOFF_STATUS = "READY_FOR_PHASE_15_FINAL_HANDOFF"
PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SOURCE = "DETERMINISTIC_ARCHITECTURE_VALIDATION_EVIDENCE_ONLY"

PHASE_15_ARCHITECTURE_SAFETY_FINDINGS = (
    "PHASE_14_FINAL_HANDOFF_LINEAGE_PRESERVED",
    "PHASE_15_ADMISSION_LINEAGE_PRESERVED",
    "ARCHITECTURE_BLUEPRINT_LINEAGE_PRESERVED",
    "DETERMINISTIC_VALIDATION_PASSED",
    "ALL_VALIDATION_RESULTS_FAKE_ONLY",
    "XAUUSD_ONLY_SCOPE_PRESERVED",
    "CLOSED_CANDLE_TIMEFRAMES_PRESERVED",
    "ONE_GOLD_POSITION_MAXIMUM_PRESERVED",
    "AGGREGATE_RISK_50_BPS_PRESERVED",
    "STAGED_RISK_25_PLUS_25_BPS_PRESERVED",
    "OCO_BROKER_STOP_LOSS_AND_GUARDS_REQUIRED",
    "TERMINAL_FLAT_STATE_REQUIRED",
    "MARTINGALE_GRID_AND_NO_STOP_LOSS_PROHIBITED",
    "FUTURE_AUTHORIZATION_AND_RUNTIME_GATES_REQUIRED",
    "ALL_REAL_RUNTIME_STATUSES_BLOCKED",
    "NO_REAL_OR_EXTERNAL_EFFECTS_DETECTED",
)


@dataclass(frozen=True, slots=True)
class Phase15ArchitectureSafetyFinding:
    """One immutable Phase 15 safety finding."""

    ordinal: int
    name: str
    status: str
    evidence: str

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise ValueError("finding ordinal must be positive")
        if self.name not in PHASE_15_ARCHITECTURE_SAFETY_FINDINGS:
            raise ValueError("unknown Phase 15 safety finding")
        if self.status != "PASSED":
            raise ValueError("safety finding must pass")
        if not self.evidence.strip():
            raise ValueError("safety finding evidence is required")

    @property
    def digest(self) -> str:
        material = "|".join(
            (
                str(self.ordinal),
                self.name,
                self.status,
                self.evidence,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase15ArchitectureSafetyAuditReport:
    """Immutable Phase 15 architecture safety-audit report."""

    validation_decision: object = field(repr=False)
    validation_report: object = field(repr=False)
    architecture_decision: object = field(repr=False)
    architecture_blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase14_final_handoff: object = field(repr=False)

    schema_version: str
    audit_status: str
    handoff_status: str
    audit_source: str

    findings: tuple[Phase15ArchitectureSafetyFinding, ...]
    finding_count: int

    component_results: int
    requirement_results: int
    total_results: int
    source_validation_audit_counts: tuple[int, ...]
    source_evidence_counts: tuple[int, ...]

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    safety_invariants_valid: bool
    future_gates_required: bool
    lineage_preserved: bool
    flat_state_required: bool

    runtime_statuses: tuple[str, ...]
    no_real_effects: bool
    safety_audit_passed: bool
    ready_for_final_handoff: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SCHEMA_VERSION:
            raise ValueError("audit schema is inconsistent")
        if self.audit_status != PHASE_15_ARCHITECTURE_SAFETY_AUDIT_STATUS:
            raise ValueError("audit status is inconsistent")
        if self.handoff_status != PHASE_15_ARCHITECTURE_SAFETY_AUDIT_HANDOFF_STATUS:
            raise ValueError("audit handoff status is inconsistent")
        if self.audit_source != PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SOURCE:
            raise ValueError("audit source is inconsistent")

        if self.finding_count != 16 or len(self.findings) != 16:
            raise ValueError("exactly sixteen findings are required")
        if tuple(item.ordinal for item in self.findings) != tuple(range(1, 17)):
            raise ValueError("finding order is inconsistent")
        if tuple(item.name for item in self.findings) != (PHASE_15_ARCHITECTURE_SAFETY_FINDINGS):
            raise ValueError("finding names are inconsistent")
        if not all(item.status == "PASSED" for item in self.findings):
            raise ValueError("all findings must pass")

        if (
            self.component_results,
            self.requirement_results,
            self.total_results,
        ) != (8, 12, 20):
            raise ValueError("validation counts are inconsistent")
        if self.source_validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("source validation/audit counts changed")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence counts changed")

        if self.symbol != "XAUUSD":
            raise ValueError("audit is XAUUSD-only")
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

        required = (
            self.safety_invariants_valid,
            self.future_gates_required,
            self.lineage_preserved,
            self.flat_state_required,
            self.no_real_effects,
            self.safety_audit_passed,
            self.ready_for_final_handoff,
        )
        if not all(required):
            raise ValueError("audit lost a required invariant")
        if self.runtime_statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def audit_digest(self) -> str:
        validation_id = str(getattr(self.validation_report, "validation_id", ""))
        material = "|".join(
            (
                self.schema_version,
                validation_id,
                self.audit_status,
                self.handoff_status,
                self.audit_source,
                ",".join(item.digest for item in self.findings),
                str(self.component_results),
                str(self.requirement_results),
                str(self.total_results),
                ",".join(map(str, self.source_validation_audit_counts)),
                ",".join(map(str, self.source_evidence_counts)),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.no_real_effects),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return f"GOLDXBOT_PHASE_15_ARCHITECTURE_SAFETY_AUDIT:SHA256[{self.audit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase15ArchitectureSafetyAuditDecision:
    """Allowed or blocked Phase 15 safety-audit decision."""

    is_allowed: bool
    report: Phase15ArchitectureSafetyAuditReport | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.report is None or self.blockers:
                raise ValueError("allowed safety-audit decision is inconsistent")
        elif self.report is not None or not self.blockers:
            raise ValueError("blocked safety-audit decision is inconsistent")

    @property
    def report_required(self) -> Phase15ArchitectureSafetyAuditReport:
        if self.report is None:
            raise RuntimeError("Phase 15 architecture safety audit is blocked.")
        return self.report


def _build_findings() -> tuple[Phase15ArchitectureSafetyFinding, ...]:
    evidence = (
        "Phase 14 final handoff object is preserved by identity.",
        "Phase 15 admission decision and permit are preserved by identity.",
        "Architecture decision and blueprint are preserved by identity.",
        "Step 15.3 validation status and outcome passed.",
        "Twenty ordered validation results are fake-only with no effects.",
        "Symbol contract remains XAUUSD-only.",
        "Only closed H4/H1/M15/M5 candles are modeled.",
        "Aggregate Gold position maximum remains one.",
        "Aggregate staged risk remains exactly 50 basis points.",
        "Stage risk remains exactly 25 plus 25 basis points.",
        "OCO, broker stop-loss, and execution guards remain mandatory.",
        "Terminal-flat state remains mandatory.",
        "Martingale, grid, and no-stop-loss behavior remain prohibited.",
        "Human authorization and separate future gates remain mandatory.",
        "All eight real runtime statuses remain BLOCKED.",
        "No real, external, production, or live effect was detected.",
    )
    return tuple(
        Phase15ArchitectureSafetyFinding(
            ordinal=index,
            name=name,
            status="PASSED",
            evidence=evidence[index - 1],
        )
        for index, name in enumerate(
            PHASE_15_ARCHITECTURE_SAFETY_FINDINGS,
            start=1,
        )
    )


class Phase15ArchitectureSafetyAuditor:
    """Audits the Step 15.3 deterministic validation evidence."""

    def audit(
        self,
        validation_decision: object,
    ) -> Phase15ArchitectureSafetyAuditDecision:
        if validation_decision is None:
            return Phase15ArchitectureSafetyAuditDecision(
                False,
                None,
                ("phase15_validation_decision_missing",),
            )
        if getattr(validation_decision, "is_allowed", True) is not True:
            return Phase15ArchitectureSafetyAuditDecision(
                False,
                None,
                ("phase15_validation_decision_blocked",),
            )

        try:
            validation = validation_decision.report_required
            architecture_decision = validation.architecture_decision
            blueprint = validation.architecture_blueprint
            admission_decision = validation.admission_decision
            permit = validation.admission_permit
            phase14 = validation.phase14_final_handoff

            validation_valid = (
                validation.validation_status == "PASSED"
                and validation.validation_outcome == "READY_FOR_ARCHITECTURE_SAFETY_AUDIT"
                and validation.validation_source == "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"
                and validation.component_results == 8
                and validation.requirement_results == 12
                and validation.total_results == 20
                and validation.result_sequence_valid is True
                and validation.component_order_valid is True
                and validation.requirement_order_valid is True
                and validation.all_results_fake_only is True
                and validation.ready_for_architecture_safety_audit is True
                and validation.no_real_or_external_effects is True
            )

            lineage_preserved = (
                validation_decision.report_required is validation
                and architecture_decision.blueprint_required is blueprint
                and blueprint.admission_decision is admission_decision
                and blueprint.admission_permit is permit
                and blueprint.phase14_final_handoff is phase14
                and admission_decision.permit_required is permit
                and permit.source_bundle is phase14
                and validation.lineage_preserved is True
            )

            blueprint_valid = (
                blueprint.blueprint_status == "BLUEPRINT_READY"
                and blueprint.blueprint_mode == "PLANNING_ONLY"
                and blueprint.next_allowed_step == "DETERMINISTIC_FAKE_VALIDATION"
                and blueprint.component_count == 8
                and blueprint.requirement_count == 12
                and blueprint.execution_admitted is False
                and blueprint.no_real_or_external_effects is True
            )

            safety_valid = (
                validation.safety_invariants_preserved is True
                and blueprint.oco_required is True
                and blueprint.broker_stop_loss_required is True
                and blueprint.guards_required is True
                and blueprint.terminal_flat_state_required is True
                and blueprint.martingale_prohibited is True
                and blueprint.grid_prohibited is True
                and blueprint.no_stop_loss_prohibited is True
            )

            future_gates_required = (
                validation.future_gates_required is True
                and blueprint.explicit_human_authorization_required is True
                and blueprint.separate_runtime_execution_gate_required is True
                and blueprint.separate_real_account_read_gate_required is True
                and blueprint.separate_production_gate_required is True
            )

            runtime_statuses = validation.runtime_statuses
            no_real_effects = (
                validation.no_real_or_external_effects is True
                and all(item.real_effect_performed is False for item in validation.results)
                and runtime_statuses == ("BLOCKED",) * 8
                and validation.real_preflight_executed is False
                and validation.real_mt5_imported is False
                and validation.real_mt5_initialized is False
                and validation.real_terminal_connected is False
                and validation.real_broker_access_performed is False
                and validation.real_account_read_performed is False
                and validation.order_check_invoked is False
                and validation.order_send_invoked is False
                and validation.external_state_written is False
                and validation.production_activated is False
                and validation.live_order_submitted is False
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase15ArchitectureSafetyAuditDecision(
                False,
                None,
                (f"phase15_validation_invalid:{type(error).__name__}",),
            )

        if not all(
            (
                validation_valid,
                lineage_preserved,
                blueprint_valid,
                safety_valid,
                future_gates_required,
                no_real_effects,
            )
        ):
            return Phase15ArchitectureSafetyAuditDecision(
                False,
                None,
                ("phase15_architecture_safety_contract_invalid",),
            )

        findings = _build_findings()
        report = Phase15ArchitectureSafetyAuditReport(
            validation_decision=validation_decision,
            validation_report=validation,
            architecture_decision=architecture_decision,
            architecture_blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=permit,
            phase14_final_handoff=phase14,
            schema_version=(PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SCHEMA_VERSION),
            audit_status=PHASE_15_ARCHITECTURE_SAFETY_AUDIT_STATUS,
            handoff_status=(PHASE_15_ARCHITECTURE_SAFETY_AUDIT_HANDOFF_STATUS),
            audit_source=PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SOURCE,
            findings=findings,
            finding_count=len(findings),
            component_results=validation.component_results,
            requirement_results=validation.requirement_results,
            total_results=validation.total_results,
            source_validation_audit_counts=(validation.source_validation_audit_counts),
            source_evidence_counts=validation.source_evidence_counts,
            symbol=validation.symbol,
            timeframes=validation.timeframes,
            closed_candles_only=validation.closed_candles_only,
            max_gold_positions=validation.max_gold_positions,
            aggregate_risk_budget_bps=(validation.aggregate_risk_budget_bps),
            stage_risk_bps=validation.stage_risk_bps,
            safety_invariants_valid=safety_valid,
            future_gates_required=future_gates_required,
            lineage_preserved=lineage_preserved,
            flat_state_required=blueprint.terminal_flat_state_required,
            runtime_statuses=runtime_statuses,
            no_real_effects=no_real_effects,
            safety_audit_passed=True,
            ready_for_final_handoff=True,
        )
        return Phase15ArchitectureSafetyAuditDecision(True, report, ())


def audit_phase15_extension_architecture_safety(
    validation_decision: object,
) -> Phase15ArchitectureSafetyAuditDecision:
    """Audit Step 15.3 deterministic architecture-validation evidence."""

    return Phase15ArchitectureSafetyAuditor().audit(validation_decision)


__all__ = (
    "PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SCHEMA_VERSION",
    "PHASE_15_ARCHITECTURE_SAFETY_AUDIT_STATUS",
    "PHASE_15_ARCHITECTURE_SAFETY_AUDIT_HANDOFF_STATUS",
    "PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SOURCE",
    "PHASE_15_ARCHITECTURE_SAFETY_FINDINGS",
    "Phase15ArchitectureSafetyFinding",
    "Phase15ArchitectureSafetyAuditReport",
    "Phase15ArchitectureSafetyAuditDecision",
    "Phase15ArchitectureSafetyAuditor",
    "audit_phase15_extension_architecture_safety",
)
