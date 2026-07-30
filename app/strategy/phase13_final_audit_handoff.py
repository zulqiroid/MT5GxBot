"""Phase 13 final audit handoff and defined-roadmap completion.

This module consumes the successful Step 13.4 runtime-safety audit and
creates one immutable completion bundle. The currently defined roadmap ends
at Phase 13; this handoff does not admit Phase 14.

All real MT5, terminal, broker, account-read, order, external-write,
production, and live-execution effects remain blocked.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_13_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_13_FINAL_HANDOFF_PHASE_STATUS = "PHASE_13_COMPLETE"
PHASE_13_FINAL_HANDOFF_STATUS = "DEFINED_ROADMAP_COMPLETE"
PHASE_13_FINAL_HANDOFF_MODE = "CONTROLLED_READ_ONLY_RUNTIME_BOUNDARY_CONTRACT_ONLY"
PHASE_13_FINAL_HANDOFF_EVIDENCE_SOURCE = "DETERMINISTIC_FAKE_BOUNDARY_EVIDENCE_ONLY"


@dataclass(frozen=True, slots=True)
class Phase13FinalAuditHandoffBundle:
    """Immutable Phase 13 completion and safety handoff."""

    audit_decision: object = field(repr=False)
    audit_report: object = field(repr=False)
    validation_report: object = field(repr=False)
    runtime_boundary_contract: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase12_handoff_bundle: object = field(repr=False)

    schema_version: str
    phase_number: int
    source_phase_number: int
    next_phase_number: int | None
    phase_status: str
    handoff_status: str
    contract_mode: str
    evidence_source: str

    runtime_operation_count: int
    blocked_write_operation_count: int
    error_mapping_count: int
    snapshot_mapping_count: int
    total_snapshot_field_count: int
    validation_event_count: int
    runtime_safety_finding_count: int

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    lineage_preserved: bool
    boundary_contract_valid: bool
    snapshot_contract_valid: bool
    risk_contract_valid: bool
    oco_broker_sl_guards_valid: bool
    terminal_flat_state_valid: bool
    future_gates_required: bool
    runtime_safety_audit_passed: bool

    real_preflight_execution_status: str
    mt5_import_status: str
    mt5_initialization_status: str
    terminal_connection_status: str
    broker_access_status: str
    real_account_read_status: str
    production_activation_status: str
    live_execution_status: str

    no_real_or_external_effects: bool
    phase_complete: bool
    defined_roadmap_complete: bool
    phase14_admitted: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_13_FINAL_HANDOFF_SCHEMA_VERSION:
            raise ValueError("final handoff schema is inconsistent.")

        if (self.phase_number, self.source_phase_number) != (13, 12):
            raise ValueError("phase transition must be 12 to 13.")

        if self.next_phase_number is not None:
            raise ValueError("no next phase is defined.")

        if self.phase_status != PHASE_13_FINAL_HANDOFF_PHASE_STATUS:
            raise ValueError("phase status must be PHASE_13_COMPLETE.")

        if self.handoff_status != PHASE_13_FINAL_HANDOFF_STATUS:
            raise ValueError("handoff must complete the defined roadmap.")

        if self.contract_mode != PHASE_13_FINAL_HANDOFF_MODE:
            raise ValueError("contract mode is inconsistent.")

        if self.evidence_source != PHASE_13_FINAL_HANDOFF_EVIDENCE_SOURCE:
            raise ValueError("evidence source is inconsistent.")

        if (
            self.runtime_operation_count,
            self.blocked_write_operation_count,
            self.error_mapping_count,
        ) != (10, 3, 10):
            raise ValueError("operation/error counts are inconsistent.")

        if (
            self.snapshot_mapping_count,
            self.total_snapshot_field_count,
        ) != (5, 32):
            raise ValueError("snapshot counts are inconsistent.")

        if (
            self.validation_event_count,
            self.runtime_safety_finding_count,
        ) != (15, 16):
            raise ValueError("validation evidence counts are inconsistent.")

        if self.symbol != "XAUUSD":
            raise ValueError("final handoff is XAUUSD only.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("closed candles are required.")

        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("staged risk must be 25+25 bps.")

        required = (
            self.lineage_preserved,
            self.boundary_contract_valid,
            self.snapshot_contract_valid,
            self.risk_contract_valid,
            self.oco_broker_sl_guards_valid,
            self.terminal_flat_state_valid,
            self.future_gates_required,
            self.runtime_safety_audit_passed,
            self.no_real_or_external_effects,
            self.phase_complete,
            self.defined_roadmap_complete,
        )
        if not all(required):
            raise ValueError("final handoff lost a required invariant.")

        statuses = (
            self.real_preflight_execution_status,
            self.mt5_import_status,
            self.mt5_initialization_status,
            self.terminal_connection_status,
            self.broker_access_status,
            self.real_account_read_status,
            self.production_activation_status,
            self.live_execution_status,
        )
        if any(status != "BLOCKED" for status in statuses):
            raise ValueError("all runtime statuses must remain BLOCKED.")

        if self.phase14_admitted:
            raise ValueError("Phase 14 is not admitted.")

    @property
    def handoff_digest(self) -> str:
        audit_id = str(getattr(self.audit_report, "audit_id", ""))
        validation_id = str(getattr(self.validation_report, "validation_id", ""))
        contract_id = str(getattr(self.runtime_boundary_contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase12_handoff_id = str(getattr(self.phase12_handoff_bundle, "handoff_id", ""))
        material = "|".join(
            (
                self.schema_version,
                audit_id,
                validation_id,
                contract_id,
                permit_id,
                phase12_handoff_id,
                self.phase_status,
                self.handoff_status,
                self.contract_mode,
                self.evidence_source,
                str(self.runtime_operation_count),
                str(self.blocked_write_operation_count),
                str(self.error_mapping_count),
                str(self.snapshot_mapping_count),
                str(self.total_snapshot_field_count),
                str(self.validation_event_count),
                str(self.runtime_safety_finding_count),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.no_real_or_external_effects),
                str(self.defined_roadmap_complete),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return f"GOLDXBOT_PHASE_13_FINAL_AUDIT_HANDOFF:SHA256[{self.handoff_digest}]"


@dataclass(frozen=True, slots=True)
class Phase13FinalAuditHandoffDecision:
    """Allowed or blocked final-handoff decision."""

    is_allowed: bool
    bundle: Phase13FinalAuditHandoffBundle | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.bundle is None or self.blockers:
                raise ValueError("allowed handoff decision is inconsistent.")
        elif self.bundle is not None or not self.blockers:
            raise ValueError("blocked handoff decision is inconsistent.")

    @property
    def bundle_required(self) -> Phase13FinalAuditHandoffBundle:
        if self.bundle is None:
            raise RuntimeError("Phase 13 final audit handoff is blocked.")
        return self.bundle


class StrategyPhase13FinalAuditHandoffFactory:
    """Creates the immutable Phase 13 completion handoff."""

    def create(
        self,
        audit_decision: object,
    ) -> Phase13FinalAuditHandoffDecision:
        if audit_decision is None:
            return Phase13FinalAuditHandoffDecision(
                False,
                None,
                ("runtime_safety_audit_decision_missing",),
            )

        if getattr(audit_decision, "is_allowed", True) is not True:
            return Phase13FinalAuditHandoffDecision(
                False,
                None,
                ("runtime_safety_audit_decision_blocked",),
            )

        try:
            audit = audit_decision.report_required
            validation = audit.validation_report
            boundary = audit.runtime_boundary_contract
            admission = audit.admission_permit
            phase12 = audit.phase12_handoff_bundle

            source_valid = (
                audit.audit_status == "PASSED"
                and audit.handoff_status == "READY_FOR_FINAL_HANDOFF"
                and audit.audit_source == "DETERMINISTIC_FAKE_BOUNDARY_EVIDENCE_ONLY"
                and audit.runtime_safety_audit_passed is True
                and audit.ready_for_final_handoff is True
                and audit.no_real_or_external_effects is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase13FinalAuditHandoffDecision(
                False,
                None,
                (f"phase13_final_handoff_source_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase13FinalAuditHandoffDecision(
                False,
                None,
                ("phase13_final_handoff_source_invariants_failed",),
            )

        lineage_preserved = (
            audit_decision.report_required is audit
            and audit.validation_decision.report_required is validation
            and validation.boundary_decision.contract_required is boundary
            and boundary.admission_permit is admission
            and admission.phase12_handoff_bundle is phase12
            and phase12.phase_status == "PHASE_12_COMPLETE"
        )

        boundary_contract_valid = (
            audit.runtime_operation_order_valid is True
            and audit.all_runtime_operations_fake_only is True
            and audit.no_real_runtime_operation_invoked is True
            and audit.blocked_write_contract_valid is True
            and audit.error_mapping_contract_valid is True
        )

        snapshot_contract_valid = (
            audit.snapshot_mapping_coverage_valid is True
            and audit.snapshot_mappings_read_only is True
            and audit.snapshot_mappings_deterministic is True
            and audit.no_real_snapshot_data_used is True
            and audit.terminal_snapshot_valid is True
            and audit.account_snapshot_valid is True
            and audit.symbol_tick_snapshot_valid is True
            and audit.exposure_snapshot_valid is True
            and audit.order_position_snapshot_valid is True
        )

        risk_contract_valid = (
            audit.symbol == "XAUUSD"
            and audit.timeframes == ("H4", "H1", "M15", "M5")
            and audit.closed_candles_only is True
            and audit.max_gold_positions == 1
            and audit.aggregate_risk_budget_bps == 50
            and audit.stage_risk_bps == (25, 25)
            and audit.risk_contract_valid is True
        )

        oco_broker_sl_guards_valid = (
            audit.oco_required is True
            and audit.broker_stop_loss_required is True
            and audit.guards_required is True
            and audit.terminal_flat_state_required is True
            and audit.oco_broker_sl_guard_contract_valid is True
        )

        future_gates_required = (
            audit.explicit_human_authorization_required is True
            and audit.separate_runtime_execution_gate_required is True
            and audit.separate_real_account_read_gate_required is True
            and audit.separate_production_gate_required is True
        )

        bundle = Phase13FinalAuditHandoffBundle(
            audit_decision=audit_decision,
            audit_report=audit,
            validation_report=validation,
            runtime_boundary_contract=boundary,
            admission_permit=admission,
            phase12_handoff_bundle=phase12,
            schema_version=PHASE_13_FINAL_HANDOFF_SCHEMA_VERSION,
            phase_number=13,
            source_phase_number=12,
            next_phase_number=None,
            phase_status=PHASE_13_FINAL_HANDOFF_PHASE_STATUS,
            handoff_status=PHASE_13_FINAL_HANDOFF_STATUS,
            contract_mode=PHASE_13_FINAL_HANDOFF_MODE,
            evidence_source=PHASE_13_FINAL_HANDOFF_EVIDENCE_SOURCE,
            runtime_operation_count=audit.runtime_operation_count,
            blocked_write_operation_count=(audit.blocked_write_operation_count),
            error_mapping_count=audit.error_mapping_count,
            snapshot_mapping_count=audit.snapshot_mapping_count,
            total_snapshot_field_count=audit.total_snapshot_field_count,
            validation_event_count=audit.validation_event_count,
            runtime_safety_finding_count=audit.finding_count,
            symbol=audit.symbol,
            timeframes=audit.timeframes,
            closed_candles_only=audit.closed_candles_only,
            max_gold_positions=audit.max_gold_positions,
            aggregate_risk_budget_bps=audit.aggregate_risk_budget_bps,
            stage_risk_bps=audit.stage_risk_bps,
            lineage_preserved=lineage_preserved,
            boundary_contract_valid=boundary_contract_valid,
            snapshot_contract_valid=snapshot_contract_valid,
            risk_contract_valid=risk_contract_valid,
            oco_broker_sl_guards_valid=oco_broker_sl_guards_valid,
            terminal_flat_state_valid=audit.terminal_flat_state_valid,
            future_gates_required=future_gates_required,
            runtime_safety_audit_passed=audit.runtime_safety_audit_passed,
            real_preflight_execution_status=(audit.real_preflight_execution_status),
            mt5_import_status=audit.mt5_import_status,
            mt5_initialization_status=audit.mt5_initialization_status,
            terminal_connection_status=audit.terminal_connection_status,
            broker_access_status=audit.broker_access_status,
            real_account_read_status=audit.real_account_read_status,
            production_activation_status=(audit.production_activation_status),
            live_execution_status=audit.live_execution_status,
            no_real_or_external_effects=audit.no_real_or_external_effects,
            phase_complete=True,
            defined_roadmap_complete=True,
            phase14_admitted=False,
        )
        return Phase13FinalAuditHandoffDecision(True, bundle, ())


def create_phase13_final_audit_handoff(
    audit_decision: object,
) -> Phase13FinalAuditHandoffDecision:
    """Create the Phase 13 final audit handoff."""

    return StrategyPhase13FinalAuditHandoffFactory().create(audit_decision)


__all__ = (
    "PHASE_13_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_13_FINAL_HANDOFF_PHASE_STATUS",
    "PHASE_13_FINAL_HANDOFF_STATUS",
    "PHASE_13_FINAL_HANDOFF_MODE",
    "PHASE_13_FINAL_HANDOFF_EVIDENCE_SOURCE",
    "Phase13FinalAuditHandoffBundle",
    "Phase13FinalAuditHandoffDecision",
    "StrategyPhase13FinalAuditHandoffFactory",
    "create_phase13_final_audit_handoff",
)
