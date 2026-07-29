"""Immutable Phase 12 final audit and handoff bundle.

This module consumes the successful Step 12.4 preflight readiness safety
audit and creates one immutable Phase 12 completion handoff. It preserves
the complete Phase 11 handoff, Phase 12 planning admission, runtime contract,
deterministic fake validation, and readiness-audit lineage.

Phase 12 remains fail-closed. Real preflight execution, MetaTrader 5 import
or initialization, terminal connection, broker requests, real account reads,
order_check, order_send, external writes, production activation, and live
order submission remain blocked. Explicit human authorization and separate
future runtime and production gates remain mandatory.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_12_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_12_FINAL_HANDOFF_PHASE_STATUS = "PHASE_12_COMPLETE"
PHASE_12_FINAL_HANDOFF_STATUS = "READY_FOR_PHASE_13"
PHASE_12_FINAL_HANDOFF_MODE = "REAL_PREFLIGHT_CONTRACT_ONLY"
PHASE_12_FINAL_HANDOFF_EVIDENCE_SOURCE = "DETERMINISTIC_FAKE_EVIDENCE_ONLY"
PHASE_12_FINAL_HANDOFF_REAL_PREFLIGHT_STATUS = "BLOCKED"
PHASE_12_FINAL_HANDOFF_MT5_STATUS = "BLOCKED"
PHASE_12_FINAL_HANDOFF_TERMINAL_STATUS = "BLOCKED"
PHASE_12_FINAL_HANDOFF_BROKER_STATUS = "BLOCKED"
PHASE_12_FINAL_HANDOFF_PRODUCTION_STATUS = "BLOCKED"
PHASE_12_FINAL_HANDOFF_LIVE_STATUS = "BLOCKED"


def _required(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase12FinalAuditHandoffBundle:
    """Immutable proof that Phase 12 is complete and fail-closed."""

    readiness_audit_decision: object
    readiness_audit_report: object
    validation_decision: object
    validation_report: object
    runtime_contract_decision: object
    runtime_contract: object
    admission_decision: object
    admission_permit: object
    phase11_handoff_bundle: object

    schema_version: str
    phase_number: int
    source_phase_number: int
    target_phase_number: int

    phase_status: str
    handoff_status: str
    contract_mode: str
    evidence_source: str

    readiness_audit_status: str
    readiness_audit_handoff_status: str
    validation_status: str
    validation_outcome: str

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    oco_required: bool
    broker_stop_loss_required: bool
    guards_required: bool
    terminal_flat_state_required: bool

    verified_capability_count: int
    blocked_capability_count: int
    snapshot_schema_count: int
    total_snapshot_field_count: int
    validation_event_count: int
    readiness_finding_count: int

    terminal_snapshot_valid: bool
    account_snapshot_valid: bool
    symbol_tick_snapshot_valid: bool
    exposure_snapshot_valid: bool
    order_position_snapshot_valid: bool
    capability_contract_valid: bool
    snapshot_schema_coverage_valid: bool
    risk_contract_valid: bool
    oco_broker_sl_guard_contract_valid: bool
    terminal_flat_state_valid: bool
    validation_event_trace_contiguous: bool
    validation_event_trace_order_valid: bool

    phase11_lineage_preserved: bool
    admission_lineage_preserved: bool
    runtime_contract_lineage_preserved: bool
    validation_lineage_preserved: bool
    readiness_audit_lineage_preserved: bool

    explicit_human_authorization_required: bool
    separate_runtime_gate_required: bool
    separate_production_gate_required: bool

    real_mt5_imported: bool
    real_mt5_initialized: bool
    real_terminal_connected: bool
    real_broker_request_sent: bool
    real_account_read_performed: bool
    order_check_invoked: bool
    order_send_invoked: bool
    external_state_written: bool
    production_activated: bool
    live_order_submitted: bool

    real_preflight_execution_status: str
    mt5_initialization_status: str
    terminal_connection_status: str
    broker_access_status: str
    production_activation_status: str
    live_execution_status: str
    no_real_or_external_effects: bool

    readiness_audit_passed: bool
    phase_complete: bool
    ready_for_phase_13: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_12_FINAL_HANDOFF_SCHEMA_VERSION:
            raise ValueError("final handoff schema version is inconsistent.")

        if (self.phase_number, self.source_phase_number, self.target_phase_number) != (
            12,
            11,
            13,
        ):
            raise ValueError("phase transition must be 11 -> 12 -> 13.")

        if self.phase_status != PHASE_12_FINAL_HANDOFF_PHASE_STATUS:
            raise ValueError("phase status must be PHASE_12_COMPLETE.")

        if self.handoff_status != PHASE_12_FINAL_HANDOFF_STATUS:
            raise ValueError("handoff status must be READY_FOR_PHASE_13.")

        if self.contract_mode != PHASE_12_FINAL_HANDOFF_MODE:
            raise ValueError("contract mode is inconsistent.")

        if self.evidence_source != PHASE_12_FINAL_HANDOFF_EVIDENCE_SOURCE:
            raise ValueError("evidence source is inconsistent.")

        if self.readiness_audit_status != "PASSED":
            raise ValueError("readiness audit status must be PASSED.")

        if self.readiness_audit_handoff_status != "READY_FOR_FINAL_HANDOFF":
            raise ValueError("readiness audit handoff must be READY_FOR_FINAL_HANDOFF.")

        if self.validation_status != "PASSED":
            raise ValueError("validation status must be PASSED.")

        if self.validation_outcome != "READY_FOR_READINESS_AUDIT":
            raise ValueError("validation outcome is inconsistent.")

        if self.symbol != "XAUUSD":
            raise ValueError("Phase 12 handoff is XAUUSD only.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 12 timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("Phase 12 requires closed candles only.")

        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("staged risk must be 25+25 bps.")

        if (
            self.verified_capability_count,
            self.blocked_capability_count,
        ) != (14, 3):
            raise ValueError("capability counts are inconsistent.")

        if (
            self.snapshot_schema_count,
            self.total_snapshot_field_count,
        ) != (5, 32):
            raise ValueError("snapshot counts are inconsistent.")

        if (
            self.validation_event_count,
            self.readiness_finding_count,
        ) != (14, 14):
            raise ValueError("event/finding counts are inconsistent.")

        required_truths = (
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.terminal_snapshot_valid,
            self.account_snapshot_valid,
            self.symbol_tick_snapshot_valid,
            self.exposure_snapshot_valid,
            self.order_position_snapshot_valid,
            self.capability_contract_valid,
            self.snapshot_schema_coverage_valid,
            self.risk_contract_valid,
            self.oco_broker_sl_guard_contract_valid,
            self.terminal_flat_state_valid,
            self.validation_event_trace_contiguous,
            self.validation_event_trace_order_valid,
            self.phase11_lineage_preserved,
            self.admission_lineage_preserved,
            self.runtime_contract_lineage_preserved,
            self.validation_lineage_preserved,
            self.readiness_audit_lineage_preserved,
            self.explicit_human_authorization_required,
            self.separate_runtime_gate_required,
            self.separate_production_gate_required,
            self.no_real_or_external_effects,
            self.readiness_audit_passed,
            self.phase_complete,
            self.ready_for_phase_13,
        )
        if not all(required_truths):
            raise ValueError("final handoff contains a failed invariant.")

        forbidden_effects = (
            self.real_mt5_imported,
            self.real_mt5_initialized,
            self.real_terminal_connected,
            self.real_broker_request_sent,
            self.real_account_read_performed,
            self.order_check_invoked,
            self.order_send_invoked,
            self.external_state_written,
            self.production_activated,
            self.live_order_submitted,
        )
        if any(forbidden_effects):
            raise ValueError("final handoff detected a real effect.")

        statuses = (
            self.real_preflight_execution_status,
            self.mt5_initialization_status,
            self.terminal_connection_status,
            self.broker_access_status,
            self.production_activation_status,
            self.live_execution_status,
        )
        if any(status != "BLOCKED" for status in statuses):
            raise ValueError("all real runtime statuses must remain BLOCKED.")

    @property
    def handoff_digest(self) -> str:
        audit_id = str(getattr(self.readiness_audit_report, "audit_id", ""))
        validation_id = str(getattr(self.validation_report, "validation_id", ""))
        contract_id = str(getattr(self.runtime_contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase11_handoff_id = str(getattr(self.phase11_handoff_bundle, "handoff_id", ""))

        material = "|".join(
            (
                self.schema_version,
                audit_id,
                validation_id,
                contract_id,
                permit_id,
                phase11_handoff_id,
                str(self.phase_number),
                str(self.source_phase_number),
                str(self.target_phase_number),
                self.phase_status,
                self.handoff_status,
                self.contract_mode,
                self.evidence_source,
                self.readiness_audit_status,
                self.readiness_audit_handoff_status,
                self.validation_status,
                self.validation_outcome,
                self.symbol,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                str(self.max_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.verified_capability_count),
                str(self.blocked_capability_count),
                str(self.snapshot_schema_count),
                str(self.total_snapshot_field_count),
                str(self.validation_event_count),
                str(self.readiness_finding_count),
                str(self.readiness_audit_passed),
                str(self.phase_complete),
                str(self.ready_for_phase_13),
                self.real_preflight_execution_status,
                self.mt5_initialization_status,
                self.terminal_connection_status,
                self.broker_access_status,
                self.production_activation_status,
                self.live_execution_status,
                str(self.no_real_or_external_effects),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return f"GOLDXBOT_PHASE_12_FINAL_AUDIT_HANDOFF:SHA256[{self.handoff_digest}]"


@dataclass(frozen=True, slots=True)
class Phase12FinalAuditHandoffDecision:
    """Allowed or blocked Phase 12 final-handoff decision."""

    is_allowed: bool
    bundle: Phase12FinalAuditHandoffBundle | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.bundle is None or self.blockers:
                raise ValueError("allowed handoff decision is inconsistent.")
        elif self.bundle is not None or not self.blockers:
            raise ValueError("blocked handoff decision is inconsistent.")

    @property
    def bundle_required(self) -> Phase12FinalAuditHandoffBundle:
        if self.bundle is None:
            raise RuntimeError("Phase 12 final audit handoff is blocked.")
        return self.bundle


class StrategyPhase12FinalAuditHandoffFactory:
    """Creates the immutable Phase 12 completion handoff."""

    def create(
        self,
        readiness_audit_decision: object,
    ) -> Phase12FinalAuditHandoffDecision:
        if readiness_audit_decision is None:
            return Phase12FinalAuditHandoffDecision(
                False,
                None,
                ("readiness_audit_decision_missing",),
            )

        if getattr(readiness_audit_decision, "is_allowed", True) is not True:
            return Phase12FinalAuditHandoffDecision(
                False,
                None,
                ("readiness_audit_decision_blocked",),
            )

        try:
            audit = _required(
                readiness_audit_decision,
                "report_required",
            )
            validation_decision = _required(
                audit,
                "validation_decision",
            )
            validation = _required(audit, "validation_report")
            runtime_contract_decision = _required(
                audit,
                "runtime_contract_decision",
            )
            runtime_contract = _required(
                audit,
                "runtime_contract",
            )
            admission_decision = _required(
                audit,
                "admission_decision",
            )
            admission_permit = _required(
                audit,
                "admission_permit",
            )
            phase11_handoff_bundle = _required(
                audit,
                "phase11_handoff_bundle",
            )

            source_valid = (
                _required(audit, "audit_status") == "PASSED"
                and _required(audit, "handoff_status") == "READY_FOR_FINAL_HANDOFF"
                and _required(audit, "audit_source") == "DETERMINISTIC_FAKE_EVIDENCE_ONLY"
                and _required(audit, "readiness_audit_passed") is True
                and _required(audit, "ready_for_final_handoff") is True
                and _required(audit, "verified_capability_count") == 14
                and _required(audit, "blocked_capability_count") == 3
                and _required(audit, "snapshot_schema_count") == 5
                and _required(audit, "total_snapshot_field_count") == 32
                and _required(audit, "validation_event_count") == 14
                and len(_required(audit, "findings")) == 14
                and _required(audit, "no_real_or_external_effects") is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase12FinalAuditHandoffDecision(
                False,
                None,
                (f"phase12_final_handoff_source_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase12FinalAuditHandoffDecision(
                False,
                None,
                ("phase12_final_handoff_source_invariants_failed",),
            )

        complete_lineage_valid = (
            readiness_audit_decision.report_required is audit
            and audit.validation_decision is validation_decision
            and validation_decision.report_required is validation
            and validation.contract_decision is runtime_contract_decision
            and runtime_contract_decision.contract_required is runtime_contract
            and runtime_contract.admission_decision is admission_decision
            and runtime_contract.admission_permit is admission_permit
            and admission_permit.phase11_handoff_bundle is phase11_handoff_bundle
        )

        bundle = Phase12FinalAuditHandoffBundle(
            readiness_audit_decision=readiness_audit_decision,
            readiness_audit_report=audit,
            validation_decision=validation_decision,
            validation_report=validation,
            runtime_contract_decision=runtime_contract_decision,
            runtime_contract=runtime_contract,
            admission_decision=admission_decision,
            admission_permit=admission_permit,
            phase11_handoff_bundle=phase11_handoff_bundle,
            schema_version=PHASE_12_FINAL_HANDOFF_SCHEMA_VERSION,
            phase_number=12,
            source_phase_number=11,
            target_phase_number=13,
            phase_status=PHASE_12_FINAL_HANDOFF_PHASE_STATUS,
            handoff_status=PHASE_12_FINAL_HANDOFF_STATUS,
            contract_mode=PHASE_12_FINAL_HANDOFF_MODE,
            evidence_source=PHASE_12_FINAL_HANDOFF_EVIDENCE_SOURCE,
            readiness_audit_status=audit.audit_status,
            readiness_audit_handoff_status=audit.handoff_status,
            validation_status=audit.validation_status,
            validation_outcome=audit.validation_outcome,
            symbol=audit.symbol,
            timeframes=audit.timeframes,
            closed_candles_only=audit.closed_candles_only,
            max_gold_positions=audit.max_gold_positions,
            aggregate_risk_budget_bps=audit.aggregate_risk_budget_bps,
            stage_risk_bps=audit.stage_risk_bps,
            oco_required=audit.oco_required,
            broker_stop_loss_required=audit.broker_stop_loss_required,
            guards_required=audit.guards_required,
            terminal_flat_state_required=audit.terminal_flat_state_required,
            verified_capability_count=audit.verified_capability_count,
            blocked_capability_count=audit.blocked_capability_count,
            snapshot_schema_count=audit.snapshot_schema_count,
            total_snapshot_field_count=audit.total_snapshot_field_count,
            validation_event_count=audit.validation_event_count,
            readiness_finding_count=len(audit.findings),
            terminal_snapshot_valid=audit.terminal_snapshot_valid,
            account_snapshot_valid=audit.account_snapshot_valid,
            symbol_tick_snapshot_valid=audit.symbol_tick_snapshot_valid,
            exposure_snapshot_valid=audit.exposure_snapshot_valid,
            order_position_snapshot_valid=audit.order_position_snapshot_valid,
            capability_contract_valid=audit.capability_contract_valid,
            snapshot_schema_coverage_valid=(audit.snapshot_schema_coverage_valid),
            risk_contract_valid=audit.risk_contract_valid,
            oco_broker_sl_guard_contract_valid=(audit.oco_broker_sl_guard_contract_valid),
            terminal_flat_state_valid=audit.terminal_flat_state_valid,
            validation_event_trace_contiguous=(audit.validation_event_trace_contiguous),
            validation_event_trace_order_valid=(audit.validation_event_trace_order_valid),
            phase11_lineage_preserved=(
                audit.phase11_lineage_preserved is True
                and phase11_handoff_bundle.phase_number == 11
                and phase11_handoff_bundle.phase_status == "PHASE_11_COMPLETE"
            ),
            admission_lineage_preserved=(audit.admission_lineage_preserved is True),
            runtime_contract_lineage_preserved=(audit.runtime_contract_lineage_preserved is True),
            validation_lineage_preserved=(audit.validation_lineage_preserved is True),
            readiness_audit_lineage_preserved=complete_lineage_valid,
            explicit_human_authorization_required=(audit.explicit_human_authorization_required),
            separate_runtime_gate_required=(audit.separate_runtime_gate_required),
            separate_production_gate_required=(audit.separate_production_gate_required),
            real_mt5_imported=audit.real_mt5_imported,
            real_mt5_initialized=audit.real_mt5_initialized,
            real_terminal_connected=audit.real_terminal_connected,
            real_broker_request_sent=audit.real_broker_request_sent,
            real_account_read_performed=audit.real_account_read_performed,
            order_check_invoked=audit.order_check_invoked,
            order_send_invoked=audit.order_send_invoked,
            external_state_written=audit.external_state_written,
            production_activated=audit.production_activated,
            live_order_submitted=audit.live_order_submitted,
            real_preflight_execution_status=(audit.real_preflight_execution_status),
            mt5_initialization_status=audit.mt5_initialization_status,
            terminal_connection_status=audit.terminal_connection_status,
            broker_access_status=audit.broker_access_status,
            production_activation_status=(audit.production_activation_status),
            live_execution_status=audit.live_execution_status,
            no_real_or_external_effects=(audit.no_real_or_external_effects),
            readiness_audit_passed=audit.readiness_audit_passed,
            phase_complete=True,
            ready_for_phase_13=True,
        )

        return Phase12FinalAuditHandoffDecision(
            True,
            bundle,
            (),
        )


def create_phase12_final_audit_handoff(
    readiness_audit_decision: object,
) -> Phase12FinalAuditHandoffDecision:
    """Create the immutable Phase 12 final audit handoff."""

    return StrategyPhase12FinalAuditHandoffFactory().create(readiness_audit_decision)


__all__ = (
    "PHASE_12_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_12_FINAL_HANDOFF_PHASE_STATUS",
    "PHASE_12_FINAL_HANDOFF_STATUS",
    "PHASE_12_FINAL_HANDOFF_MODE",
    "PHASE_12_FINAL_HANDOFF_EVIDENCE_SOURCE",
    "PHASE_12_FINAL_HANDOFF_REAL_PREFLIGHT_STATUS",
    "PHASE_12_FINAL_HANDOFF_MT5_STATUS",
    "PHASE_12_FINAL_HANDOFF_TERMINAL_STATUS",
    "PHASE_12_FINAL_HANDOFF_BROKER_STATUS",
    "PHASE_12_FINAL_HANDOFF_PRODUCTION_STATUS",
    "PHASE_12_FINAL_HANDOFF_LIVE_STATUS",
    "Phase12FinalAuditHandoffBundle",
    "Phase12FinalAuditHandoffDecision",
    "StrategyPhase12FinalAuditHandoffFactory",
    "create_phase12_final_audit_handoff",
)
