"""Phase 14 final architecture handoff and extension completion.

This module consumes the successful Step 14.4 architecture safety audit and
creates one immutable Phase 14 completion bundle.

Phase 14 remains planning-only. No Phase 15 is admitted, and all real MT5,
terminal, broker, account-read, order, external-write, production, and live
execution effects remain blocked.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_14_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_14_FINAL_HANDOFF_PHASE_STATUS = "PHASE_14_COMPLETE"
PHASE_14_FINAL_HANDOFF_STATUS = "PHASE_14_EXTENSION_COMPLETE"
PHASE_14_FINAL_HANDOFF_MODE = "HUMAN_AUTHORIZED_READ_ONLY_PREFLIGHT_OBSERVABILITY_PLANNING_ONLY"
PHASE_14_FINAL_HANDOFF_EVIDENCE_SOURCE = (
    "DETERMINISTIC_ARCHITECTURE_VALIDATION_AND_SAFETY_AUDIT_ONLY"
)


@dataclass(frozen=True, slots=True)
class Phase14FinalArchitectureHandoffBundle:
    """Immutable Phase 14 completion and safety handoff."""

    audit_decision: object = field(repr=False)
    audit_report: object = field(repr=False)
    validation_report: object = field(repr=False)
    architecture_blueprint: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase13_handoff_bundle: object = field(repr=False)

    schema_version: str
    phase_number: int
    source_phase_number: int
    next_phase_number: int | None
    phase_status: str
    handoff_status: str
    handoff_mode: str
    evidence_source: str

    component_result_count: int
    requirement_result_count: int
    total_validation_result_count: int
    architecture_safety_finding_count: int

    runtime_operation_count: int
    blocked_write_operation_count: int
    error_mapping_count: int
    snapshot_mapping_count: int
    total_snapshot_field_count: int
    prior_validation_event_count: int
    prior_runtime_safety_finding_count: int

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    lineage_preserved: bool
    architecture_blueprint_valid: bool
    deterministic_validation_passed: bool
    architecture_safety_audit_passed: bool
    risk_contract_valid: bool
    oco_broker_sl_guards_valid: bool
    terminal_flat_state_valid: bool
    future_gates_required: bool

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
    extension_roadmap_complete: bool
    phase15_admitted: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_14_FINAL_HANDOFF_SCHEMA_VERSION:
            raise ValueError("final handoff schema is inconsistent")
        if (self.phase_number, self.source_phase_number) != (14, 13):
            raise ValueError("phase transition must be 13 to 14")
        if self.next_phase_number is not None:
            raise ValueError("no next phase is defined")
        if self.phase_status != PHASE_14_FINAL_HANDOFF_PHASE_STATUS:
            raise ValueError("phase status must be PHASE_14_COMPLETE")
        if self.handoff_status != PHASE_14_FINAL_HANDOFF_STATUS:
            raise ValueError("Phase 14 extension handoff is inconsistent")
        if self.handoff_mode != PHASE_14_FINAL_HANDOFF_MODE:
            raise ValueError("final handoff mode is inconsistent")
        if self.evidence_source != PHASE_14_FINAL_HANDOFF_EVIDENCE_SOURCE:
            raise ValueError("final handoff evidence source is inconsistent")

        if (
            self.component_result_count,
            self.requirement_result_count,
            self.total_validation_result_count,
            self.architecture_safety_finding_count,
        ) != (8, 12, 20, 16):
            raise ValueError("validation and audit counts are inconsistent")

        if (
            self.runtime_operation_count,
            self.blocked_write_operation_count,
            self.error_mapping_count,
            self.snapshot_mapping_count,
            self.total_snapshot_field_count,
            self.prior_validation_event_count,
            self.prior_runtime_safety_finding_count,
        ) != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence counts are inconsistent")

        if self.symbol != "XAUUSD":
            raise ValueError("final handoff is XAUUSD only")
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
            self.lineage_preserved,
            self.architecture_blueprint_valid,
            self.deterministic_validation_passed,
            self.architecture_safety_audit_passed,
            self.risk_contract_valid,
            self.oco_broker_sl_guards_valid,
            self.terminal_flat_state_valid,
            self.future_gates_required,
            self.no_real_or_external_effects,
            self.phase_complete,
            self.extension_roadmap_complete,
        )
        if not all(required):
            raise ValueError("final handoff lost a required invariant")

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
        if statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

        if self.phase15_admitted:
            raise ValueError("Phase 15 is not admitted")

    @property
    def handoff_digest(self) -> str:
        audit_id = str(getattr(self.audit_report, "audit_id", ""))
        validation_id = str(getattr(self.validation_report, "validation_id", ""))
        blueprint_id = str(getattr(self.architecture_blueprint, "blueprint_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase13_handoff_id = str(getattr(self.phase13_handoff_bundle, "handoff_id", ""))
        material = "|".join(
            (
                self.schema_version,
                audit_id,
                validation_id,
                blueprint_id,
                permit_id,
                phase13_handoff_id,
                self.phase_status,
                self.handoff_status,
                self.handoff_mode,
                self.evidence_source,
                str(self.component_result_count),
                str(self.requirement_result_count),
                str(self.total_validation_result_count),
                str(self.architecture_safety_finding_count),
                str(self.runtime_operation_count),
                str(self.blocked_write_operation_count),
                str(self.error_mapping_count),
                str(self.snapshot_mapping_count),
                str(self.total_snapshot_field_count),
                str(self.prior_validation_event_count),
                str(self.prior_runtime_safety_finding_count),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.no_real_or_external_effects),
                str(self.extension_roadmap_complete),
                str(self.phase15_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return f"GOLDXBOT_PHASE_14_FINAL_ARCHITECTURE_HANDOFF:SHA256[{self.handoff_digest}]"


@dataclass(frozen=True, slots=True)
class Phase14FinalArchitectureHandoffDecision:
    """Allowed or blocked Phase 14 final-handoff decision."""

    is_allowed: bool
    bundle: Phase14FinalArchitectureHandoffBundle | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.bundle is None or self.blockers:
                raise ValueError("allowed final-handoff decision is inconsistent")
        elif self.bundle is not None or not self.blockers:
            raise ValueError("blocked final-handoff decision is inconsistent")

    @property
    def bundle_required(self) -> Phase14FinalArchitectureHandoffBundle:
        if self.bundle is None:
            raise RuntimeError("Phase 14 final architecture handoff is blocked.")
        return self.bundle


class Phase14FinalArchitectureHandoffFactory:
    """Creates the immutable Phase 14 completion handoff."""

    def create(
        self,
        audit_decision: object,
    ) -> Phase14FinalArchitectureHandoffDecision:
        if audit_decision is None:
            return Phase14FinalArchitectureHandoffDecision(
                False,
                None,
                ("phase14_safety_audit_decision_missing",),
            )
        if getattr(audit_decision, "is_allowed", True) is not True:
            return Phase14FinalArchitectureHandoffDecision(
                False,
                None,
                ("phase14_safety_audit_decision_blocked",),
            )

        try:
            audit = audit_decision.report_required
            validation = audit.validation_report
            blueprint = audit.blueprint
            permit = audit.admission_permit
            phase13 = audit.phase13_handoff

            source_valid = (
                audit.audit_status == "PASSED"
                and audit.handoff_status == "READY_FOR_PHASE_14_FINAL_HANDOFF"
                and audit.audit_source == "DETERMINISTIC_ARCHITECTURE_VALIDATION_EVIDENCE_ONLY"
                and audit.safety_audit_passed is True
                and audit.ready_for_final_handoff is True
                and audit.no_real_effects is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase14FinalArchitectureHandoffDecision(
                False,
                None,
                (f"phase14_final_handoff_source_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase14FinalArchitectureHandoffDecision(
                False,
                None,
                ("phase14_final_handoff_source_invariants_failed",),
            )

        lineage_preserved = (
            audit_decision.report_required is audit
            and audit.validation_decision.report_required is validation
            and validation.architecture_blueprint is blueprint
            and validation.admission_permit is permit
            and permit.source_bundle is phase13
            and phase13.phase_status == "PHASE_13_COMPLETE"
        )

        architecture_blueprint_valid = (
            blueprint.blueprint_status == "BLUEPRINT_READY"
            and len(blueprint.components) == 8
            and len(blueprint.requirements) == 12
            and blueprint.ready_for_fake_validation is True
            and blueprint.real_execution_allowed is False
            and blueprint.live_execution_allowed is False
        )

        deterministic_validation_passed = (
            validation.validation_status == "PASSED"
            and validation.validation_outcome == "READY_FOR_ARCHITECTURE_SAFETY_AUDIT"
            and validation.validation_source == "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"
            and validation.component_results == 8
            and validation.requirement_results == 12
            and validation.total_results == 20
            and validation.all_results_fake_only is True
            and validation.no_real_or_external_effects is True
        )

        risk_contract_valid = (
            audit.symbol == "XAUUSD"
            and audit.timeframes == ("H4", "H1", "M15", "M5")
            and audit.closed_candles_only is True
            and audit.max_gold_positions == 1
            and audit.aggregate_risk_bps == 50
            and audit.stage_risk_bps == (25, 25)
        )

        oco_broker_sl_guards_valid = (
            audit.safety_invariants_valid is True
            and blueprint.oco_required is True
            and blueprint.broker_sl_required is True
            and blueprint.guards_required is True
            and blueprint.martingale_prohibited is True
            and blueprint.grid_prohibited is True
            and blueprint.no_sl_prohibited is True
        )

        future_gates_required = (
            audit.future_gates_required is True
            and blueprint.human_authorization_required is True
            and blueprint.runtime_gate_required is True
            and blueprint.account_read_gate_required is True
            and blueprint.production_gate_required is True
        )

        bundle = Phase14FinalArchitectureHandoffBundle(
            audit_decision=audit_decision,
            audit_report=audit,
            validation_report=validation,
            architecture_blueprint=blueprint,
            admission_permit=permit,
            phase13_handoff_bundle=phase13,
            schema_version=PHASE_14_FINAL_HANDOFF_SCHEMA_VERSION,
            phase_number=14,
            source_phase_number=13,
            next_phase_number=None,
            phase_status=PHASE_14_FINAL_HANDOFF_PHASE_STATUS,
            handoff_status=PHASE_14_FINAL_HANDOFF_STATUS,
            handoff_mode=PHASE_14_FINAL_HANDOFF_MODE,
            evidence_source=PHASE_14_FINAL_HANDOFF_EVIDENCE_SOURCE,
            component_result_count=audit.component_results,
            requirement_result_count=audit.requirement_results,
            total_validation_result_count=audit.total_results,
            architecture_safety_finding_count=audit.finding_count,
            runtime_operation_count=audit.runtime_operations,
            blocked_write_operation_count=audit.blocked_writes,
            error_mapping_count=audit.error_mappings,
            snapshot_mapping_count=audit.snapshot_mappings,
            total_snapshot_field_count=audit.snapshot_fields,
            prior_validation_event_count=audit.prior_events,
            prior_runtime_safety_finding_count=audit.prior_findings,
            symbol=audit.symbol,
            timeframes=audit.timeframes,
            closed_candles_only=audit.closed_candles_only,
            max_gold_positions=audit.max_gold_positions,
            aggregate_risk_budget_bps=audit.aggregate_risk_bps,
            stage_risk_bps=audit.stage_risk_bps,
            lineage_preserved=lineage_preserved,
            architecture_blueprint_valid=architecture_blueprint_valid,
            deterministic_validation_passed=(deterministic_validation_passed),
            architecture_safety_audit_passed=(audit.safety_audit_passed),
            risk_contract_valid=risk_contract_valid,
            oco_broker_sl_guards_valid=oco_broker_sl_guards_valid,
            terminal_flat_state_valid=audit.flat_state_required,
            future_gates_required=future_gates_required,
            real_preflight_execution_status=audit.real_preflight_status,
            mt5_import_status=audit.mt5_import_status,
            mt5_initialization_status=audit.mt5_initialization_status,
            terminal_connection_status=audit.terminal_status,
            broker_access_status=audit.broker_status,
            real_account_read_status=audit.account_read_status,
            production_activation_status=audit.production_status,
            live_execution_status=audit.live_status,
            no_real_or_external_effects=audit.no_real_effects,
            phase_complete=True,
            extension_roadmap_complete=True,
            phase15_admitted=False,
        )
        return Phase14FinalArchitectureHandoffDecision(True, bundle, ())


def create_phase14_final_architecture_handoff(
    audit_decision: object,
) -> Phase14FinalArchitectureHandoffDecision:
    """Create the Phase 14 final architecture handoff."""

    return Phase14FinalArchitectureHandoffFactory().create(audit_decision)


__all__ = (
    "PHASE_14_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_14_FINAL_HANDOFF_PHASE_STATUS",
    "PHASE_14_FINAL_HANDOFF_STATUS",
    "PHASE_14_FINAL_HANDOFF_MODE",
    "PHASE_14_FINAL_HANDOFF_EVIDENCE_SOURCE",
    "Phase14FinalArchitectureHandoffBundle",
    "Phase14FinalArchitectureHandoffDecision",
    "Phase14FinalArchitectureHandoffFactory",
    "create_phase14_final_architecture_handoff",
)
