"""Immutable Phase 11 final audit and handoff bundle.

This module consumes the successful Step 11.4 readiness safety audit and
creates one immutable Phase 11 completion handoff. It preserves the full
Phase 10 handoff, Phase 11 admission, capability inventory, deterministic
fake read-only preflight, and readiness-audit lineage.

Phase 11 remains fail-closed. Real preflight execution, MetaTrader 5
initialization, terminal connection, broker requests, real account reads,
external writes, production activation, and live order submission remain
blocked. Explicit human authorization and separate future gates remain
mandatory.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_11_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_11_FINAL_HANDOFF_PHASE_STATUS = "PHASE_11_COMPLETE"
PHASE_11_FINAL_HANDOFF_STATUS = "READY_FOR_PHASE_12"
PHASE_11_FINAL_HANDOFF_MODE = "DETERMINISTIC_FAKE_READ_ONLY"
PHASE_11_FINAL_HANDOFF_REAL_PREFLIGHT_STATUS = "BLOCKED"
PHASE_11_FINAL_HANDOFF_PRODUCTION_STATUS = "BLOCKED"
PHASE_11_FINAL_HANDOFF_LIVE_STATUS = "BLOCKED"


def _required_attribute(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


def _required_int(value: object, name: str) -> int:
    attribute = _required_attribute(value, name)
    if isinstance(attribute, bool) or not isinstance(attribute, int):
        raise ValueError(f"{name} must be an integer.")
    return attribute


@dataclass(frozen=True, slots=True)
class Phase11FinalAuditHandoffBundle:
    """Immutable proof that Phase 11 is complete and fail-closed."""

    readiness_audit_decision: object
    readiness_audit_report: object
    preflight_decision: object
    preflight: object
    capability_decision: object
    capability_contract: object
    admission_decision: object
    admission_permit: object
    phase10_handoff_bundle: object

    schema_version: str
    phase_number: int
    source_phase_number: int
    target_phase_number: int

    phase_status: str
    handoff_status: str
    readiness_mode: str
    readiness_audit_status: str
    readiness_audit_handoff_status: str

    real_preflight_execution_status: str
    production_activation_status: str
    live_execution_status: str

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool

    stage_risk_bps: tuple[int, ...]
    aggregate_risk_budget_bps: int
    max_gold_positions: int

    oco_required: bool
    broker_stop_loss_required: bool
    guards_required: bool
    terminal_flat_state_required: bool

    verified_capability_count: int
    blocked_capability_count: int
    event_count: int

    risk_contract_valid: bool
    oco_and_stop_loss_contract_valid: bool
    capability_inventory_valid: bool
    event_trace_contiguous: bool
    event_trace_order_valid: bool
    terminal_snapshot_valid: bool
    account_snapshot_valid: bool
    symbol_snapshot_valid: bool
    terminal_lifecycle_valid: bool
    margin_state_valid: bool
    exposure_state_valid: bool
    terminal_flat_state_valid: bool

    phase10_lineage_preserved: bool
    admission_lineage_preserved: bool
    capability_lineage_preserved: bool
    preflight_lineage_preserved: bool
    readiness_audit_lineage_preserved: bool

    explicit_human_authorization_required: bool
    separate_real_preflight_gate_required: bool
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
    no_real_or_external_effects: bool

    readiness_audit_passed: bool
    phase_complete: bool
    ready_for_phase_12: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_11_FINAL_HANDOFF_SCHEMA_VERSION:
            raise ValueError("final handoff schema version is inconsistent.")

        if self.phase_number != 11:
            raise ValueError("phase_number must be 11.")

        if self.source_phase_number != 10:
            raise ValueError("source_phase_number must be 10.")

        if self.target_phase_number != 12:
            raise ValueError("target_phase_number must be 12.")

        if self.phase_status != PHASE_11_FINAL_HANDOFF_PHASE_STATUS:
            raise ValueError("phase status must be PHASE_11_COMPLETE.")

        if self.handoff_status != PHASE_11_FINAL_HANDOFF_STATUS:
            raise ValueError("handoff status must be READY_FOR_PHASE_12.")

        if self.readiness_mode != PHASE_11_FINAL_HANDOFF_MODE:
            raise ValueError("readiness mode must be DETERMINISTIC_FAKE_READ_ONLY.")

        if self.readiness_audit_status != "PASSED":
            raise ValueError("readiness audit status must be PASSED.")

        if self.readiness_audit_handoff_status != "READY_FOR_FINAL_HANDOFF":
            raise ValueError("readiness audit handoff must be READY_FOR_FINAL_HANDOFF.")

        if self.real_preflight_execution_status != PHASE_11_FINAL_HANDOFF_REAL_PREFLIGHT_STATUS:
            raise ValueError("real preflight execution must remain BLOCKED.")

        if self.production_activation_status != PHASE_11_FINAL_HANDOFF_PRODUCTION_STATUS:
            raise ValueError("production activation must remain BLOCKED.")

        if self.live_execution_status != PHASE_11_FINAL_HANDOFF_LIVE_STATUS:
            raise ValueError("live execution must remain BLOCKED.")

        if self.symbol != "XAUUSD":
            raise ValueError("Phase 11 handoff is XAUUSD only.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 11 timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("Phase 11 requires closed candles only.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("stage risk allocation is inconsistent.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk budget must be 50 bps.")

        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.verified_capability_count != 14:
            raise ValueError("fourteen fake capabilities must be verified.")

        if self.blocked_capability_count != 3:
            raise ValueError("three write-sensitive capabilities must block.")

        if self.event_count != 14:
            raise ValueError("fourteen preflight events are required.")

        required_truths = (
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.risk_contract_valid,
            self.oco_and_stop_loss_contract_valid,
            self.capability_inventory_valid,
            self.event_trace_contiguous,
            self.event_trace_order_valid,
            self.terminal_snapshot_valid,
            self.account_snapshot_valid,
            self.symbol_snapshot_valid,
            self.terminal_lifecycle_valid,
            self.margin_state_valid,
            self.exposure_state_valid,
            self.terminal_flat_state_valid,
            self.phase10_lineage_preserved,
            self.admission_lineage_preserved,
            self.capability_lineage_preserved,
            self.preflight_lineage_preserved,
            self.readiness_audit_lineage_preserved,
            self.explicit_human_authorization_required,
            self.separate_real_preflight_gate_required,
            self.separate_production_gate_required,
            self.no_real_or_external_effects,
            self.readiness_audit_passed,
            self.phase_complete,
            self.ready_for_phase_12,
        )
        if not all(required_truths):
            raise ValueError("Phase 11 final handoff has a failed invariant.")

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
            raise ValueError("Phase 11 final handoff detected a real effect.")

    @property
    def handoff_digest(self) -> str:
        audit_id = str(getattr(self.readiness_audit_report, "audit_id", ""))
        preflight_id = str(getattr(self.preflight, "preflight_id", ""))
        contract_id = str(getattr(self.capability_contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase10_handoff_id = str(getattr(self.phase10_handoff_bundle, "handoff_id", ""))

        material = "|".join(
            (
                self.schema_version,
                audit_id,
                preflight_id,
                contract_id,
                permit_id,
                phase10_handoff_id,
                str(self.phase_number),
                str(self.source_phase_number),
                str(self.target_phase_number),
                self.phase_status,
                self.handoff_status,
                self.readiness_mode,
                self.readiness_audit_status,
                self.readiness_audit_handoff_status,
                self.real_preflight_execution_status,
                self.production_activation_status,
                self.live_execution_status,
                self.symbol,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.aggregate_risk_budget_bps),
                str(self.max_gold_positions),
                str(self.oco_required),
                str(self.broker_stop_loss_required),
                str(self.guards_required),
                str(self.terminal_flat_state_required),
                str(self.verified_capability_count),
                str(self.blocked_capability_count),
                str(self.event_count),
                str(self.risk_contract_valid),
                str(self.oco_and_stop_loss_contract_valid),
                str(self.capability_inventory_valid),
                str(self.event_trace_contiguous),
                str(self.event_trace_order_valid),
                str(self.terminal_snapshot_valid),
                str(self.account_snapshot_valid),
                str(self.symbol_snapshot_valid),
                str(self.terminal_lifecycle_valid),
                str(self.margin_state_valid),
                str(self.exposure_state_valid),
                str(self.terminal_flat_state_valid),
                str(self.phase10_lineage_preserved),
                str(self.admission_lineage_preserved),
                str(self.capability_lineage_preserved),
                str(self.preflight_lineage_preserved),
                str(self.readiness_audit_lineage_preserved),
                str(self.explicit_human_authorization_required),
                str(self.separate_real_preflight_gate_required),
                str(self.separate_production_gate_required),
                str(self.real_mt5_imported),
                str(self.real_mt5_initialized),
                str(self.real_terminal_connected),
                str(self.real_broker_request_sent),
                str(self.real_account_read_performed),
                str(self.order_check_invoked),
                str(self.order_send_invoked),
                str(self.external_state_written),
                str(self.production_activated),
                str(self.live_order_submitted),
                str(self.no_real_or_external_effects),
                str(self.readiness_audit_passed),
                str(self.phase_complete),
                str(self.ready_for_phase_12),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return f"GOLDXBOT_PHASE_11_FINAL_AUDIT_HANDOFF:SHA256[{self.handoff_digest}]"


@dataclass(frozen=True, slots=True)
class Phase11FinalAuditHandoffDecision:
    """Allowed or blocked Phase 11 final handoff decision."""

    is_allowed: bool
    bundle: Phase11FinalAuditHandoffBundle | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.bundle is None:
                raise ValueError("Allowed decision requires a bundle.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.bundle is not None:
                raise ValueError("Blocked decision cannot have a bundle.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def bundle_required(self) -> Phase11FinalAuditHandoffBundle:
        if self.bundle is None:
            raise RuntimeError("Phase 11 final audit handoff is blocked.")
        return self.bundle


class StrategyPhase11FinalAuditHandoffFactory:
    """Creates the immutable Phase 11 completion handoff."""

    def create(
        self,
        readiness_audit_decision: object,
    ) -> Phase11FinalAuditHandoffDecision:
        if readiness_audit_decision is None:
            return Phase11FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=("readiness_audit_decision_missing",),
            )

        if getattr(readiness_audit_decision, "is_allowed", True) is not True:
            return Phase11FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=("readiness_audit_decision_blocked",),
            )

        try:
            report = _required_attribute(
                readiness_audit_decision,
                "report_required",
            )
            preflight_decision = _required_attribute(
                report,
                "preflight_decision",
            )
            preflight = _required_attribute(report, "preflight")
            capability_decision = _required_attribute(
                report,
                "capability_decision",
            )
            capability_contract = _required_attribute(
                report,
                "capability_contract",
            )
            admission_decision = _required_attribute(
                report,
                "admission_decision",
            )
            admission_permit = _required_attribute(
                report,
                "admission_permit",
            )
            phase10_handoff_bundle = _required_attribute(
                report,
                "phase10_handoff_bundle",
            )

            audit_status = _required_attribute(report, "audit_status")
            audit_handoff_status = _required_attribute(
                report,
                "final_handoff_status",
            )
            readiness_mode = _required_attribute(
                report,
                "preflight_mode",
            )
            real_preflight_status = _required_attribute(
                report,
                "real_preflight_execution_status",
            )
            production_status = _required_attribute(
                report,
                "production_activation_status",
            )
            live_status = _required_attribute(
                report,
                "live_execution_status",
            )

            symbol = _required_attribute(report, "symbol")
            timeframes = _required_attribute(report, "timeframes")
            closed_candles_only = _required_attribute(
                report,
                "closed_candles_only",
            )
            stage_risk_bps = _required_attribute(
                report,
                "stage_risk_bps",
            )
            aggregate_risk_budget_bps = _required_int(
                report,
                "aggregate_risk_budget_bps",
            )
            max_gold_positions = _required_int(
                report,
                "max_gold_positions",
            )
            verified_capability_count = _required_int(
                report,
                "verified_capability_count",
            )
            blocked_capability_count = _required_int(
                report,
                "blocked_capability_count",
            )
            event_count = _required_int(report, "event_count")
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase11FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=(f"phase11_final_handoff_source_invalid:{type(error).__name__}",),
            )

        complete_lineage_valid = (
            report.preflight_decision is preflight_decision
            and preflight_decision.preflight_required is preflight
            and preflight.capability_decision is capability_decision
            and capability_decision.contract_required is capability_contract
            and capability_contract.admission_decision is admission_decision
            and admission_decision.permit_required is admission_permit
            and admission_permit.phase10_handoff_bundle is phase10_handoff_bundle
        )

        try:
            bundle = Phase11FinalAuditHandoffBundle(
                readiness_audit_decision=readiness_audit_decision,
                readiness_audit_report=report,
                preflight_decision=preflight_decision,
                preflight=preflight,
                capability_decision=capability_decision,
                capability_contract=capability_contract,
                admission_decision=admission_decision,
                admission_permit=admission_permit,
                phase10_handoff_bundle=phase10_handoff_bundle,
                schema_version=PHASE_11_FINAL_HANDOFF_SCHEMA_VERSION,
                phase_number=11,
                source_phase_number=10,
                target_phase_number=12,
                phase_status=PHASE_11_FINAL_HANDOFF_PHASE_STATUS,
                handoff_status=PHASE_11_FINAL_HANDOFF_STATUS,
                readiness_mode=str(readiness_mode),
                readiness_audit_status=str(audit_status),
                readiness_audit_handoff_status=str(audit_handoff_status),
                real_preflight_execution_status=str(real_preflight_status),
                production_activation_status=str(production_status),
                live_execution_status=str(live_status),
                symbol=str(symbol),
                timeframes=timeframes,
                closed_candles_only=closed_candles_only is True,
                stage_risk_bps=stage_risk_bps,
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                max_gold_positions=max_gold_positions,
                oco_required=report.oco_required is True,
                broker_stop_loss_required=(report.broker_stop_loss_required is True),
                guards_required=report.guards_required is True,
                terminal_flat_state_required=(report.terminal_flat_state_required is True),
                verified_capability_count=verified_capability_count,
                blocked_capability_count=blocked_capability_count,
                event_count=event_count,
                risk_contract_valid=report.risk_contract_valid is True,
                oco_and_stop_loss_contract_valid=(report.oco_and_stop_loss_contract_valid is True),
                capability_inventory_valid=(report.capability_inventory_valid is True),
                event_trace_contiguous=(report.event_trace_contiguous is True),
                event_trace_order_valid=(report.event_trace_order_valid is True),
                terminal_snapshot_valid=(report.terminal_snapshot_valid is True),
                account_snapshot_valid=(report.account_snapshot_valid is True),
                symbol_snapshot_valid=(report.symbol_snapshot_valid is True),
                terminal_lifecycle_valid=(report.terminal_lifecycle_valid is True),
                margin_state_valid=report.margin_state_valid is True,
                exposure_state_valid=report.exposure_state_valid is True,
                terminal_flat_state_valid=(report.terminal_flat_state_valid is True),
                phase10_lineage_preserved=(
                    report.phase10_lineage_preserved is True
                    and phase10_handoff_bundle.phase_number == 10
                    and phase10_handoff_bundle.phase_status == "PHASE_10_COMPLETE"
                ),
                admission_lineage_preserved=(report.admission_lineage_preserved is True),
                capability_lineage_preserved=(report.capability_lineage_preserved is True),
                preflight_lineage_preserved=(report.preflight_lineage_preserved is True),
                readiness_audit_lineage_preserved=(
                    report is readiness_audit_decision.report_required and complete_lineage_valid
                ),
                explicit_human_authorization_required=(
                    report.explicit_human_authorization_required is True
                ),
                separate_real_preflight_gate_required=(
                    report.separate_preflight_gate_required is True
                ),
                separate_production_gate_required=(
                    report.separate_production_gate_required is True
                ),
                real_mt5_imported=report.real_mt5_imported is True,
                real_mt5_initialized=report.real_mt5_initialized is True,
                real_terminal_connected=(report.real_terminal_connected is True),
                real_broker_request_sent=(report.real_broker_request_sent is True),
                real_account_read_performed=(report.real_account_read_performed is True),
                order_check_invoked=report.order_check_invoked is True,
                order_send_invoked=report.order_send_invoked is True,
                external_state_written=(report.external_state_written is True),
                production_activated=report.production_activated is True,
                live_order_submitted=report.live_order_submitted is True,
                no_real_or_external_effects=(report.no_real_or_external_effects is True),
                readiness_audit_passed=(report.readiness_audit_passed is True),
                phase_complete=True,
                ready_for_phase_12=True,
            )
        except ValueError as error:
            return Phase11FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=(f"phase11_final_handoff_invalid:{type(error).__name__}",),
            )

        return Phase11FinalAuditHandoffDecision(
            is_allowed=True,
            bundle=bundle,
            blockers=(),
        )


def create_phase11_final_audit_handoff(
    readiness_audit_decision: object,
) -> Phase11FinalAuditHandoffDecision:
    """Create the immutable Phase 11 final audit handoff."""

    return StrategyPhase11FinalAuditHandoffFactory().create(readiness_audit_decision)


__all__ = (
    "PHASE_11_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_11_FINAL_HANDOFF_PHASE_STATUS",
    "PHASE_11_FINAL_HANDOFF_STATUS",
    "PHASE_11_FINAL_HANDOFF_MODE",
    "PHASE_11_FINAL_HANDOFF_REAL_PREFLIGHT_STATUS",
    "PHASE_11_FINAL_HANDOFF_PRODUCTION_STATUS",
    "PHASE_11_FINAL_HANDOFF_LIVE_STATUS",
    "Phase11FinalAuditHandoffBundle",
    "Phase11FinalAuditHandoffDecision",
    "StrategyPhase11FinalAuditHandoffFactory",
    "create_phase11_final_audit_handoff",
)
