"""Immutable Phase 13 controlled read-only runtime safety audit.

This module consumes the successful Step 13.3 deterministic fake runtime
boundary validation and creates a fail-closed safety audit for runtime
operations, blocked writes, error mappings, snapshot mappings, XAUUSD risk,
terminal flat state, and all future authorization gates.

The audit is evidence-only. It never imports or initializes real MetaTrader 5,
connects to a terminal, contacts a broker, reads a real account, runs
order_check, sends an order, writes external state, activates production, or
submits a live order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_13_RUNTIME_SAFETY_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_13_RUNTIME_SAFETY_AUDIT_STATUS = "PASSED"
PHASE_13_RUNTIME_SAFETY_AUDIT_HANDOFF_STATUS = "READY_FOR_FINAL_HANDOFF"
PHASE_13_RUNTIME_SAFETY_AUDIT_SOURCE = "DETERMINISTIC_FAKE_BOUNDARY_EVIDENCE_ONLY"

PHASE_13_RUNTIME_SAFETY_FINDING_NAMES = (
    "phase12_lineage",
    "phase13_admission_lineage",
    "runtime_boundary_lineage",
    "fake_validation_lineage",
    "runtime_operations",
    "blocked_write_operations",
    "fail_closed_error_mappings",
    "terminal_snapshot_mapping",
    "account_snapshot_mapping",
    "symbol_tick_snapshot_mapping",
    "exposure_snapshot_mapping",
    "order_position_snapshot_mapping",
    "risk_and_position_limits",
    "oco_broker_sl_guards_and_flat_state",
    "future_authorization_gates",
    "no_real_or_external_effects",
)


def _required(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


def _snapshot_map(report: object) -> dict[str, dict[str, object]]:
    payloads = _required(report, "snapshot_payloads")
    mapped: dict[str, dict[str, object]] = {}

    for snapshot_name, field_names, values in payloads:
        mapped[str(snapshot_name)] = dict(zip(field_names, values, strict=True))

    return mapped


@dataclass(frozen=True, slots=True)
class Phase13RuntimeSafetyAuditFinding:
    """Immutable result for one Phase 13 runtime safety invariant."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in PHASE_13_RUNTIME_SAFETY_FINDING_NAMES:
            raise ValueError("unsupported Phase 13 runtime safety finding.")

        if self.passed is not True:
            raise ValueError("successful runtime safety findings must pass.")

        if not self.evidence:
            raise ValueError("runtime safety finding evidence is required.")

    @property
    def finding_digest(self) -> str:
        material = "|".join((self.name, str(self.passed), self.evidence))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase13ControlledReadOnlyRuntimeSafetyAuditReport:
    """Immutable evidence that Phase 13 remains fail-closed."""

    validation_decision: object
    validation_report: object
    boundary_decision: object
    runtime_boundary_contract: object
    admission_decision: object
    admission_permit: object
    phase12_handoff_bundle: object

    schema_version: str
    audit_status: str
    handoff_status: str
    audit_source: str

    validation_status: str
    validation_outcome: str
    validation_source: str

    runtime_operation_count: int
    blocked_write_operation_count: int
    error_mapping_count: int
    snapshot_mapping_count: int
    total_snapshot_field_count: int
    validation_event_count: int

    runtime_operation_order_valid: bool
    all_runtime_operations_fake_only: bool
    no_real_runtime_operation_invoked: bool
    blocked_write_contract_valid: bool
    error_mapping_contract_valid: bool
    snapshot_mapping_coverage_valid: bool
    snapshot_mappings_read_only: bool
    snapshot_mappings_deterministic: bool
    no_real_snapshot_data_used: bool

    terminal_snapshot_valid: bool
    account_snapshot_valid: bool
    symbol_tick_snapshot_valid: bool
    exposure_snapshot_valid: bool
    order_position_snapshot_valid: bool

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]
    risk_contract_valid: bool

    oco_required: bool
    broker_stop_loss_required: bool
    guards_required: bool
    terminal_flat_state_required: bool
    oco_broker_sl_guard_contract_valid: bool
    terminal_flat_state_valid: bool

    event_trace_contiguous: bool
    event_trace_order_valid: bool

    phase12_lineage_preserved: bool
    admission_lineage_preserved: bool
    boundary_lineage_preserved: bool
    validation_lineage_preserved: bool

    explicit_human_authorization_required: bool
    separate_runtime_execution_gate_required: bool
    separate_real_account_read_gate_required: bool
    separate_production_gate_required: bool

    real_preflight_executed: bool
    real_mt5_imported: bool
    real_mt5_initialized: bool
    real_terminal_connected: bool
    real_broker_access_performed: bool
    real_account_read_performed: bool
    order_check_invoked: bool
    order_send_invoked: bool
    external_state_written: bool
    production_activated: bool
    live_order_submitted: bool

    real_preflight_execution_status: str
    mt5_import_status: str
    mt5_initialization_status: str
    terminal_connection_status: str
    broker_access_status: str
    real_account_read_status: str
    production_activation_status: str
    live_execution_status: str
    no_real_or_external_effects: bool

    findings: tuple[Phase13RuntimeSafetyAuditFinding, ...]
    finding_count: int
    runtime_safety_audit_passed: bool
    ready_for_final_handoff: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_13_RUNTIME_SAFETY_AUDIT_SCHEMA_VERSION:
            raise ValueError("runtime safety audit schema is inconsistent.")

        if self.audit_status != PHASE_13_RUNTIME_SAFETY_AUDIT_STATUS:
            raise ValueError("runtime safety audit status must be PASSED.")

        if self.handoff_status != PHASE_13_RUNTIME_SAFETY_AUDIT_HANDOFF_STATUS:
            raise ValueError("runtime safety audit handoff is inconsistent.")

        if self.audit_source != PHASE_13_RUNTIME_SAFETY_AUDIT_SOURCE:
            raise ValueError("runtime safety audit source is inconsistent.")

        if self.validation_status != "PASSED":
            raise ValueError("source validation must pass.")

        if self.validation_outcome != "READY_FOR_RUNTIME_SAFETY_AUDIT":
            raise ValueError("source validation outcome is inconsistent.")

        if self.validation_source != "DETERMINISTIC_IN_MEMORY_FAKE_ONLY":
            raise ValueError("source validation must be fake-only.")

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
            raise ValueError("snapshot mapping counts are inconsistent.")

        if self.validation_event_count != 15:
            raise ValueError("fifteen validation events are required.")

        if self.finding_count != 16:
            raise ValueError("sixteen runtime safety findings are required.")

        if tuple(finding.name for finding in self.findings) != (
            PHASE_13_RUNTIME_SAFETY_FINDING_NAMES
        ):
            raise ValueError("runtime safety finding order is inconsistent.")

        if self.symbol != "XAUUSD":
            raise ValueError("runtime safety audit is XAUUSD only.")

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
            self.runtime_operation_order_valid,
            self.all_runtime_operations_fake_only,
            self.no_real_runtime_operation_invoked,
            self.blocked_write_contract_valid,
            self.error_mapping_contract_valid,
            self.snapshot_mapping_coverage_valid,
            self.snapshot_mappings_read_only,
            self.snapshot_mappings_deterministic,
            self.no_real_snapshot_data_used,
            self.terminal_snapshot_valid,
            self.account_snapshot_valid,
            self.symbol_tick_snapshot_valid,
            self.exposure_snapshot_valid,
            self.order_position_snapshot_valid,
            self.risk_contract_valid,
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.oco_broker_sl_guard_contract_valid,
            self.terminal_flat_state_valid,
            self.event_trace_contiguous,
            self.event_trace_order_valid,
            self.phase12_lineage_preserved,
            self.admission_lineage_preserved,
            self.boundary_lineage_preserved,
            self.validation_lineage_preserved,
            self.explicit_human_authorization_required,
            self.separate_runtime_execution_gate_required,
            self.separate_real_account_read_gate_required,
            self.separate_production_gate_required,
            self.no_real_or_external_effects,
            self.runtime_safety_audit_passed,
            self.ready_for_final_handoff,
        )
        if not all(required):
            raise ValueError("runtime safety audit lost a required invariant.")

        forbidden = (
            self.real_preflight_executed,
            self.real_mt5_imported,
            self.real_mt5_initialized,
            self.real_terminal_connected,
            self.real_broker_access_performed,
            self.real_account_read_performed,
            self.order_check_invoked,
            self.order_send_invoked,
            self.external_state_written,
            self.production_activated,
            self.live_order_submitted,
        )
        if any(forbidden):
            raise ValueError("runtime safety audit detected a real effect.")

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

    @property
    def audit_digest(self) -> str:
        validation_id = str(getattr(self.validation_report, "validation_id", ""))
        contract_id = str(getattr(self.runtime_boundary_contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase12_handoff_id = str(getattr(self.phase12_handoff_bundle, "handoff_id", ""))
        finding_material = ",".join(finding.finding_digest for finding in self.findings)
        material = "|".join(
            (
                self.schema_version,
                validation_id,
                contract_id,
                permit_id,
                phase12_handoff_id,
                self.audit_status,
                self.handoff_status,
                self.audit_source,
                self.validation_status,
                self.validation_outcome,
                self.validation_source,
                str(self.runtime_operation_count),
                str(self.blocked_write_operation_count),
                str(self.error_mapping_count),
                str(self.snapshot_mapping_count),
                str(self.total_snapshot_field_count),
                str(self.validation_event_count),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                finding_material,
                str(self.no_real_or_external_effects),
                str(self.ready_for_final_handoff),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_13_CONTROLLED_READ_ONLY_RUNTIME_SAFETY_AUDIT:"
            f"SHA256[{self.audit_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase13ControlledReadOnlyRuntimeSafetyAuditDecision:
    """Allowed or blocked Phase 13 runtime safety audit decision."""

    is_allowed: bool
    report: Phase13ControlledReadOnlyRuntimeSafetyAuditReport | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.report is None or self.blockers:
                raise ValueError("allowed audit decision is inconsistent.")
        elif self.report is not None or not self.blockers:
            raise ValueError("blocked audit decision is inconsistent.")

    @property
    def report_required(
        self,
    ) -> Phase13ControlledReadOnlyRuntimeSafetyAuditReport:
        if self.report is None:
            raise RuntimeError("Phase 13 controlled read-only runtime safety audit is blocked.")
        return self.report


class StrategyPhase13ControlledReadOnlyRuntimeSafetyAuditor:
    """Audits Step 13.3 deterministic fake evidence only."""

    def audit(
        self,
        validation_decision: object,
    ) -> Phase13ControlledReadOnlyRuntimeSafetyAuditDecision:
        if validation_decision is None:
            return Phase13ControlledReadOnlyRuntimeSafetyAuditDecision(
                False,
                None,
                ("fake_boundary_validation_decision_missing",),
            )

        if getattr(validation_decision, "is_allowed", True) is not True:
            return Phase13ControlledReadOnlyRuntimeSafetyAuditDecision(
                False,
                None,
                ("fake_boundary_validation_decision_blocked",),
            )

        try:
            validation = _required(
                validation_decision,
                "report_required",
            )
            boundary_decision = _required(
                validation,
                "boundary_decision",
            )
            boundary = _required(
                validation,
                "runtime_boundary_contract",
            )
            admission_decision = _required(
                validation,
                "admission_decision",
            )
            admission_permit = _required(
                validation,
                "admission_permit",
            )
            phase12_handoff_bundle = _required(
                validation,
                "phase12_handoff_bundle",
            )

            source_valid = (
                _required(validation, "validation_status") == "PASSED"
                and _required(validation, "validation_outcome") == "READY_FOR_RUNTIME_SAFETY_AUDIT"
                and _required(validation, "validation_source")
                == "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"
                and _required(validation, "runtime_operation_count") == 10
                and _required(validation, "blocked_write_operation_count") == 3
                and _required(validation, "error_mapping_count") == 10
                and _required(validation, "snapshot_mapping_count") == 5
                and _required(validation, "total_snapshot_field_count") == 32
                and _required(validation, "event_count") == 15
                and _required(validation, "no_real_or_external_effects") is True
                and _required(validation, "ready_for_runtime_safety_audit") is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase13ControlledReadOnlyRuntimeSafetyAuditDecision(
                False,
                None,
                (f"fake_boundary_validation_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase13ControlledReadOnlyRuntimeSafetyAuditDecision(
                False,
                None,
                ("fake_boundary_validation_invariants_failed",),
            )

        snapshots = _snapshot_map(validation)
        terminal = snapshots["TERMINAL_SNAPSHOT"]
        account = snapshots["ACCOUNT_SNAPSHOT"]
        symbol_tick = snapshots["SYMBOL_TICK_SNAPSHOT"]
        exposure = snapshots["EXPOSURE_SNAPSHOT"]
        order_position = snapshots["ORDER_POSITION_SNAPSHOT"]

        terminal_snapshot_valid = (
            terminal["terminal_name"] == "GoldXBot-Phase13-Fake"
            and terminal["build_number"] == 5100
            and terminal["connected"] is False
            and terminal["trade_allowed"] is False
            and terminal["dlls_allowed"] is False
            and terminal["lifecycle_state"] == "FAKE_BOUNDARY_VALIDATED"
        )
        account_snapshot_valid = (
            account["account_id"] == "PHASE13-FAKE-ACCOUNT"
            and account["trade_mode"] == "FAKE_READ_ONLY"
            and account["trade_allowed"] is False
            and account["currency"] == "USD"
            and account["balance_minor_units"] == 10_000_000
            and account["equity_minor_units"] == 10_000_000
            and account["margin_used_minor_units"] == 0
            and account["margin_free_minor_units"] == 10_000_000
        )
        symbol_tick_snapshot_valid = (
            symbol_tick["requested_symbol"] == "XAUUSD"
            and symbol_tick["resolved_symbol"] == "XAUUSD"
            and symbol_tick["visible"] is True
            and symbol_tick["digits"] == 2
            and symbol_tick["point_scale"] == 100
            and symbol_tick["bid_price_points"] == 241_000
            and symbol_tick["ask_price_points"] == 241_020
            and symbol_tick["spread_points"] == 20
        )
        exposure_snapshot_valid = (
            exposure["open_gold_position_count"] == 0
            and exposure["pending_gold_order_count"] == 0
            and exposure["reserved_risk_bps"] == 0
            and exposure["aggregate_risk_budget_bps"] == 50
            and exposure["stage_risk_bps"] == (25, 25)
        )
        order_position_snapshot_valid = (
            order_position["position_ids"] == ()
            and order_position["order_ids"] == ()
            and order_position["oco_group_ids"] == ()
            and order_position["broker_stop_loss_attached"] is True
            and order_position["terminal_flat_state"] is True
        )

        phase12_lineage_preserved = (
            admission_permit.phase12_handoff_bundle is phase12_handoff_bundle
            and phase12_handoff_bundle.phase_number == 12
            and phase12_handoff_bundle.phase_status == "PHASE_12_COMPLETE"
            and phase12_handoff_bundle.handoff_status == "READY_FOR_PHASE_13"
        )
        admission_lineage_preserved = (
            boundary.admission_decision is admission_decision
            and boundary.admission_permit is admission_permit
        )
        boundary_lineage_preserved = boundary_decision.contract_required is boundary
        validation_lineage_preserved = (
            validation_decision.report_required is validation
            and validation.boundary_decision is boundary_decision
            and validation.runtime_boundary_contract is boundary
        )

        risk_contract_valid = (
            validation.symbol == "XAUUSD"
            and validation.timeframes == ("H4", "H1", "M15", "M5")
            and validation.closed_candles_only is True
            and validation.max_gold_positions == 1
            and validation.aggregate_risk_budget_bps == 50
            and validation.stage_risk_bps == (25, 25)
            and sum(validation.stage_risk_bps) == validation.aggregate_risk_budget_bps
            and validation.risk_contract_valid is True
        )
        oco_broker_sl_guard_contract_valid = (
            validation.oco_required is True
            and validation.broker_stop_loss_required is True
            and validation.guards_required is True
            and validation.terminal_flat_state_required is True
            and validation.oco_broker_sl_guard_contract_valid is True
        )
        terminal_flat_state_valid = (
            exposure_snapshot_valid
            and order_position_snapshot_valid
            and validation.terminal_flat_state_valid is True
        )

        no_real_or_external_effects = (
            validation.real_preflight_executed is False
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
            and validation.no_real_or_external_effects is True
        )

        findings = (
            Phase13RuntimeSafetyAuditFinding(
                "phase12_lineage",
                phase12_lineage_preserved,
                "Phase 12 completion and Phase 13 handoff lineage is exact.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "phase13_admission_lineage",
                admission_lineage_preserved,
                "Phase 13 admission decision and permit lineage is exact.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "runtime_boundary_lineage",
                boundary_lineage_preserved,
                "Step 13.2 runtime-boundary lineage is exact.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "fake_validation_lineage",
                validation_lineage_preserved,
                "Step 13.3 fake validation lineage is exact.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "runtime_operations",
                (
                    validation.runtime_operation_order_valid is True
                    and validation.operations_fake_only is True
                    and validation.no_real_runtime_operation_invoked is True
                ),
                "Ten runtime operations validated through fake-only results.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "blocked_write_operations",
                validation.blocked_write_contract_valid is True,
                "ORDER_CHECK, ORDER_SEND, and OCO writes remain blocked.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "fail_closed_error_mappings",
                validation.error_mapping_contract_valid is True,
                "Ten errors block without retry, side effects, or bypass.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "terminal_snapshot_mapping",
                terminal_snapshot_valid,
                "Fake terminal is disconnected and trading-disabled.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "account_snapshot_mapping",
                account_snapshot_valid,
                "Fake account is read-only with zero used margin.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "symbol_tick_snapshot_mapping",
                symbol_tick_snapshot_valid,
                "Deterministic XAUUSD symbol and tick mapping is valid.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "exposure_snapshot_mapping",
                exposure_snapshot_valid,
                "Gold positions, orders, and reserved risk remain zero.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "order_position_snapshot_mapping",
                order_position_snapshot_valid,
                "Order-position evidence is empty, flat, and protected.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "risk_and_position_limits",
                risk_contract_valid,
                "25+25 bps equals 50 bps with one Gold position max.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "oco_broker_sl_guards_and_flat_state",
                (oco_broker_sl_guard_contract_valid and terminal_flat_state_valid),
                "OCO, broker SL, guards, and terminal flat state are valid.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "future_authorization_gates",
                (
                    validation.explicit_human_authorization_required is True
                    and validation.separate_runtime_execution_gate_required is True
                    and validation.separate_real_account_read_gate_required is True
                    and validation.separate_production_gate_required is True
                ),
                "Human, runtime, account-read, and production gates stand.",
            ),
            Phase13RuntimeSafetyAuditFinding(
                "no_real_or_external_effects",
                no_real_or_external_effects,
                "No real MT5, terminal, broker, account, write, or order effect.",
            ),
        )

        audit_passed = all(finding.passed for finding in findings)

        report = Phase13ControlledReadOnlyRuntimeSafetyAuditReport(
            validation_decision=validation_decision,
            validation_report=validation,
            boundary_decision=boundary_decision,
            runtime_boundary_contract=boundary,
            admission_decision=admission_decision,
            admission_permit=admission_permit,
            phase12_handoff_bundle=phase12_handoff_bundle,
            schema_version=PHASE_13_RUNTIME_SAFETY_AUDIT_SCHEMA_VERSION,
            audit_status=PHASE_13_RUNTIME_SAFETY_AUDIT_STATUS,
            handoff_status=PHASE_13_RUNTIME_SAFETY_AUDIT_HANDOFF_STATUS,
            audit_source=PHASE_13_RUNTIME_SAFETY_AUDIT_SOURCE,
            validation_status=validation.validation_status,
            validation_outcome=validation.validation_outcome,
            validation_source=validation.validation_source,
            runtime_operation_count=validation.runtime_operation_count,
            blocked_write_operation_count=(validation.blocked_write_operation_count),
            error_mapping_count=validation.error_mapping_count,
            snapshot_mapping_count=validation.snapshot_mapping_count,
            total_snapshot_field_count=(validation.total_snapshot_field_count),
            validation_event_count=validation.event_count,
            runtime_operation_order_valid=(validation.runtime_operation_order_valid),
            all_runtime_operations_fake_only=(validation.operations_fake_only),
            no_real_runtime_operation_invoked=(validation.no_real_runtime_operation_invoked),
            blocked_write_contract_valid=(validation.blocked_write_contract_valid),
            error_mapping_contract_valid=(validation.error_mapping_contract_valid),
            snapshot_mapping_coverage_valid=(validation.snapshot_mapping_coverage_valid),
            snapshot_mappings_read_only=(validation.snapshot_mappings_read_only),
            snapshot_mappings_deterministic=(validation.snapshot_mappings_deterministic),
            no_real_snapshot_data_used=(validation.no_real_snapshot_data_used),
            terminal_snapshot_valid=terminal_snapshot_valid,
            account_snapshot_valid=account_snapshot_valid,
            symbol_tick_snapshot_valid=symbol_tick_snapshot_valid,
            exposure_snapshot_valid=exposure_snapshot_valid,
            order_position_snapshot_valid=order_position_snapshot_valid,
            symbol=validation.symbol,
            timeframes=validation.timeframes,
            closed_candles_only=validation.closed_candles_only,
            max_gold_positions=validation.max_gold_positions,
            aggregate_risk_budget_bps=(validation.aggregate_risk_budget_bps),
            stage_risk_bps=validation.stage_risk_bps,
            risk_contract_valid=risk_contract_valid,
            oco_required=validation.oco_required,
            broker_stop_loss_required=validation.broker_stop_loss_required,
            guards_required=validation.guards_required,
            terminal_flat_state_required=(validation.terminal_flat_state_required),
            oco_broker_sl_guard_contract_valid=(oco_broker_sl_guard_contract_valid),
            terminal_flat_state_valid=terminal_flat_state_valid,
            event_trace_contiguous=validation.event_trace_contiguous,
            event_trace_order_valid=validation.event_trace_order_valid,
            phase12_lineage_preserved=phase12_lineage_preserved,
            admission_lineage_preserved=admission_lineage_preserved,
            boundary_lineage_preserved=boundary_lineage_preserved,
            validation_lineage_preserved=validation_lineage_preserved,
            explicit_human_authorization_required=(
                validation.explicit_human_authorization_required
            ),
            separate_runtime_execution_gate_required=(
                validation.separate_runtime_execution_gate_required
            ),
            separate_real_account_read_gate_required=(
                validation.separate_real_account_read_gate_required
            ),
            separate_production_gate_required=(validation.separate_production_gate_required),
            real_preflight_executed=False,
            real_mt5_imported=False,
            real_mt5_initialized=False,
            real_terminal_connected=False,
            real_broker_access_performed=False,
            real_account_read_performed=False,
            order_check_invoked=False,
            order_send_invoked=False,
            external_state_written=False,
            production_activated=False,
            live_order_submitted=False,
            real_preflight_execution_status=(validation.real_preflight_execution_status),
            mt5_import_status=validation.mt5_import_status,
            mt5_initialization_status=validation.mt5_initialization_status,
            terminal_connection_status=(validation.terminal_connection_status),
            broker_access_status=validation.broker_access_status,
            real_account_read_status=validation.real_account_read_status,
            production_activation_status=(validation.production_activation_status),
            live_execution_status=validation.live_execution_status,
            no_real_or_external_effects=no_real_or_external_effects,
            findings=findings,
            finding_count=len(findings),
            runtime_safety_audit_passed=audit_passed,
            ready_for_final_handoff=audit_passed,
        )
        return Phase13ControlledReadOnlyRuntimeSafetyAuditDecision(
            True,
            report,
            (),
        )


def audit_phase13_controlled_read_only_runtime_safety(
    validation_decision: object,
) -> Phase13ControlledReadOnlyRuntimeSafetyAuditDecision:
    """Audit Step 13.3 deterministic fake runtime-boundary evidence."""

    return StrategyPhase13ControlledReadOnlyRuntimeSafetyAuditor().audit(validation_decision)


__all__ = (
    "PHASE_13_RUNTIME_SAFETY_AUDIT_SCHEMA_VERSION",
    "PHASE_13_RUNTIME_SAFETY_AUDIT_STATUS",
    "PHASE_13_RUNTIME_SAFETY_AUDIT_HANDOFF_STATUS",
    "PHASE_13_RUNTIME_SAFETY_AUDIT_SOURCE",
    "PHASE_13_RUNTIME_SAFETY_FINDING_NAMES",
    "Phase13RuntimeSafetyAuditFinding",
    "Phase13ControlledReadOnlyRuntimeSafetyAuditReport",
    "Phase13ControlledReadOnlyRuntimeSafetyAuditDecision",
    "StrategyPhase13ControlledReadOnlyRuntimeSafetyAuditor",
    "audit_phase13_controlled_read_only_runtime_safety",
)
