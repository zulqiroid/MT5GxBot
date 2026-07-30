"""Phase 14 fail-closed architecture safety audit."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

SCHEMA_VERSION = "1.0"
AUDIT_STATUS = "PASSED"
HANDOFF_STATUS = "READY_FOR_PHASE_14_FINAL_HANDOFF"
AUDIT_SOURCE = "DETERMINISTIC_ARCHITECTURE_VALIDATION_EVIDENCE_ONLY"
FINDINGS = (
    "PHASE_13_LINEAGE",
    "PHASE_14_ADMISSION_LINEAGE",
    "ARCHITECTURE_LINEAGE",
    "VALIDATION_LINEAGE",
    "COMPONENT_RESULTS",
    "REQUIREMENT_RESULTS",
    "SOURCE_EVIDENCE",
    "XAUUSD_SCOPE",
    "CLOSED_CANDLES",
    "RISK_LIMITS",
    "OCO_BROKER_SL_GUARDS",
    "TERMINAL_FLAT_STATE",
    "FUTURE_GATES",
    "FAKE_ONLY_EVIDENCE",
    "BLOCKED_STATUSES",
    "NO_REAL_EFFECTS",
)


@dataclass(frozen=True, slots=True)
class Phase14SafetyFinding:
    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in FINDINGS:
            raise ValueError("unsupported finding")
        if not self.passed or not self.evidence:
            raise ValueError("finding must pass with evidence")


@dataclass(frozen=True, slots=True)
class Phase14ArchitectureSafetyAuditReport:
    validation_decision: object = field(repr=False)
    validation_report: object = field(repr=False)
    blueprint: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase13_handoff: object = field(repr=False)

    schema_version: str
    audit_status: str
    handoff_status: str
    audit_source: str
    component_results: int
    requirement_results: int
    total_results: int
    runtime_operations: int
    blocked_writes: int
    error_mappings: int
    snapshot_mappings: int
    snapshot_fields: int
    prior_events: int
    prior_findings: int
    findings: tuple[Phase14SafetyFinding, ...]
    finding_count: int

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_bps: int
    stage_risk_bps: tuple[int, ...]

    lineage_preserved: bool
    result_order_valid: bool
    fake_only: bool
    safety_invariants_valid: bool
    future_gates_required: bool
    flat_state_required: bool
    no_real_effects: bool

    real_preflight_status: str
    mt5_import_status: str
    mt5_initialization_status: str
    terminal_status: str
    broker_status: str
    account_read_status: str
    production_status: str
    live_status: str

    safety_audit_passed: bool
    ready_for_final_handoff: bool

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid schema")
        if self.audit_status != AUDIT_STATUS:
            raise ValueError("invalid audit status")
        if self.handoff_status != HANDOFF_STATUS:
            raise ValueError("invalid handoff status")
        if self.audit_source != AUDIT_SOURCE:
            raise ValueError("invalid audit source")
        if (
            self.component_results,
            self.requirement_results,
            self.total_results,
        ) != (8, 12, 20):
            raise ValueError("invalid validation counts")
        if (
            self.runtime_operations,
            self.blocked_writes,
            self.error_mappings,
            self.snapshot_mappings,
            self.snapshot_fields,
            self.prior_events,
            self.prior_findings,
        ) != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("invalid source evidence")
        if self.finding_count != 16:
            raise ValueError("invalid finding count")
        if tuple(item.name for item in self.findings) != FINDINGS:
            raise ValueError("invalid finding order")
        if self.symbol != "XAUUSD":
            raise ValueError("XAUUSD only")
        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("invalid timeframes")
        if not self.closed_candles_only:
            raise ValueError("closed candles required")
        if self.max_gold_positions != 1:
            raise ValueError("one position maximum")
        if self.aggregate_risk_bps != 50 or self.stage_risk_bps != (25, 25):
            raise ValueError("invalid risk limits")
        required = (
            self.lineage_preserved,
            self.result_order_valid,
            self.fake_only,
            self.safety_invariants_valid,
            self.future_gates_required,
            self.flat_state_required,
            self.no_real_effects,
            self.safety_audit_passed,
            self.ready_for_final_handoff,
        )
        if not all(required):
            raise ValueError("audit invariant lost")
        statuses = (
            self.real_preflight_status,
            self.mt5_import_status,
            self.mt5_initialization_status,
            self.terminal_status,
            self.broker_status,
            self.account_read_status,
            self.production_status,
            self.live_status,
        )
        if statuses != ("BLOCKED",) * 8:
            raise ValueError("runtime statuses must remain blocked")

    @property
    def audit_digest(self) -> str:
        validation_id = str(getattr(self.validation_report, "validation_id", ""))
        material = "|".join(
            (
                self.schema_version,
                validation_id,
                self.audit_status,
                self.handoff_status,
                str(self.total_results),
                str(self.finding_count),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.no_real_effects),
            )
        )
        return hashlib.sha256(material.encode()).hexdigest()

    @property
    def audit_id(self) -> str:
        return f"GOLDXBOT_PHASE_14_SAFETY_AUDIT:SHA256[{self.audit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase14ArchitectureSafetyAuditDecision:
    is_allowed: bool
    report: Phase14ArchitectureSafetyAuditReport | None
    blockers: tuple[str, ...]

    @property
    def report_required(self) -> Phase14ArchitectureSafetyAuditReport:
        if self.report is None:
            raise RuntimeError("Phase 14 architecture safety audit is blocked.")
        return self.report


class Phase14ArchitectureSafetyAuditor:
    def audit(self, decision: object) -> Phase14ArchitectureSafetyAuditDecision:
        if decision is None:
            return Phase14ArchitectureSafetyAuditDecision(
                False, None, ("phase14_validation_decision_missing",)
            )
        if getattr(decision, "is_allowed", True) is not True:
            return Phase14ArchitectureSafetyAuditDecision(
                False, None, ("phase14_validation_decision_blocked",)
            )
        try:
            validation = decision.report_required
            blueprint = validation.architecture_blueprint
            permit = validation.admission_permit
            handoff = validation.phase13_handoff_bundle
            valid = (
                validation.validation_status == "PASSED"
                and validation.validation_outcome == "READY_FOR_ARCHITECTURE_SAFETY_AUDIT"
                and validation.validation_source == "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"
                and validation.total_results == 20
                and validation.all_results_fake_only is True
                and all(item.real_effect_performed is False for item in validation.results)
                and validation.no_real_or_external_effects is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase14ArchitectureSafetyAuditDecision(
                False,
                None,
                (f"phase14_validation_invalid:{type(error).__name__}",),
            )
        if not valid:
            return Phase14ArchitectureSafetyAuditDecision(
                False, None, ("phase14_validation_contract_invalid",)
            )

        evidence = tuple(
            Phase14SafetyFinding(name, True, f"{name} verified fail-closed.") for name in FINDINGS
        )
        lineage = (
            validation.lineage_preserved
            and decision.report_required is validation
            and validation.architecture_blueprint is blueprint
            and validation.admission_permit is permit
            and permit.source_bundle is handoff
        )
        safety = (
            validation.safety_invariants_preserved
            and blueprint.oco_required
            and blueprint.broker_sl_required
            and blueprint.guards_required
            and blueprint.martingale_prohibited
            and blueprint.grid_prohibited
            and blueprint.no_sl_prohibited
        )
        gates = (
            validation.future_gates_required
            and blueprint.human_authorization_required
            and blueprint.runtime_gate_required
            and blueprint.account_read_gate_required
            and blueprint.production_gate_required
        )
        report = Phase14ArchitectureSafetyAuditReport(
            validation_decision=decision,
            validation_report=validation,
            blueprint=blueprint,
            admission_permit=permit,
            phase13_handoff=handoff,
            schema_version=SCHEMA_VERSION,
            audit_status=AUDIT_STATUS,
            handoff_status=HANDOFF_STATUS,
            audit_source=AUDIT_SOURCE,
            component_results=validation.component_results,
            requirement_results=validation.requirement_results,
            total_results=validation.total_results,
            runtime_operations=validation.runtime_operations,
            blocked_writes=validation.blocked_write_operations,
            error_mappings=validation.error_mappings,
            snapshot_mappings=validation.snapshot_mappings,
            snapshot_fields=validation.snapshot_fields,
            prior_events=validation.prior_validation_events,
            prior_findings=validation.prior_safety_findings,
            findings=evidence,
            finding_count=len(evidence),
            symbol=validation.symbol,
            timeframes=validation.timeframes,
            closed_candles_only=validation.closed_candles_only,
            max_gold_positions=validation.max_gold_positions,
            aggregate_risk_bps=validation.aggregate_risk_budget_bps,
            stage_risk_bps=validation.stage_risk_bps,
            lineage_preserved=lineage,
            result_order_valid=(
                validation.result_sequence_valid
                and validation.component_order_valid
                and validation.requirement_order_valid
            ),
            fake_only=(
                validation.all_results_fake_only
                and all(item.real_effect_performed is False for item in validation.results)
            ),
            safety_invariants_valid=safety,
            future_gates_required=gates,
            flat_state_required=blueprint.flat_state_required,
            no_real_effects=validation.no_real_or_external_effects,
            real_preflight_status=validation.real_preflight_status,
            mt5_import_status=validation.mt5_import_status,
            mt5_initialization_status=validation.mt5_initialization_status,
            terminal_status=validation.terminal_status,
            broker_status=validation.broker_status,
            account_read_status=validation.account_read_status,
            production_status=validation.production_status,
            live_status=validation.live_status,
            safety_audit_passed=True,
            ready_for_final_handoff=True,
        )
        return Phase14ArchitectureSafetyAuditDecision(True, report, ())


def audit_phase14_architecture_safety(
    decision: object,
) -> Phase14ArchitectureSafetyAuditDecision:
    return Phase14ArchitectureSafetyAuditor().audit(decision)


__all__ = (
    "SCHEMA_VERSION",
    "AUDIT_STATUS",
    "HANDOFF_STATUS",
    "AUDIT_SOURCE",
    "FINDINGS",
    "Phase14SafetyFinding",
    "Phase14ArchitectureSafetyAuditReport",
    "Phase14ArchitectureSafetyAuditDecision",
    "Phase14ArchitectureSafetyAuditor",
    "audit_phase14_architecture_safety",
)
