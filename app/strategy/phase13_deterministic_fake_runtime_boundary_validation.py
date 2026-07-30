"""Deterministic fake validation for the Phase 13 runtime boundary."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

SCHEMA_VERSION = "1.0"
VALIDATION_STATUS = "PASSED"
VALIDATION_OUTCOME = "READY_FOR_RUNTIME_SAFETY_AUDIT"
VALIDATION_SOURCE = "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"

EVENT_TYPES = (
    "RUNTIME_BOUNDARY_CONTRACT_ACCEPTED",
    "RUNTIME_OPERATIONS_VALIDATED",
    "BLOCKED_WRITE_OPERATIONS_VALIDATED",
    "FAIL_CLOSED_ERROR_MAPPINGS_VALIDATED",
    "TERMINAL_SNAPSHOT_MAPPED",
    "ACCOUNT_SNAPSHOT_MAPPED",
    "SYMBOL_TICK_SNAPSHOT_MAPPED",
    "EXPOSURE_SNAPSHOT_MAPPED",
    "ORDER_POSITION_SNAPSHOT_MAPPED",
    "XAUUSD_SCOPE_VALIDATED",
    "RISK_CONTRACT_VALIDATED",
    "OCO_BROKER_SL_GUARDS_VALIDATED",
    "TERMINAL_FLAT_STATE_VALIDATED",
    "FUTURE_GATES_VALIDATED",
    "REAL_EFFECTS_CONFIRMED_BLOCKED",
)


def _required(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


def _snapshot_payloads() -> tuple[tuple[str, tuple[str, ...], tuple[object, ...]], ...]:
    return (
        (
            "TERMINAL_SNAPSHOT",
            (
                "terminal_name",
                "build_number",
                "connected",
                "trade_allowed",
                "dlls_allowed",
                "lifecycle_state",
            ),
            (
                "GoldXBot-Phase13-Fake",
                5100,
                False,
                False,
                False,
                "FAKE_BOUNDARY_VALIDATED",
            ),
        ),
        (
            "ACCOUNT_SNAPSHOT",
            (
                "account_id",
                "trade_mode",
                "trade_allowed",
                "currency",
                "balance_minor_units",
                "equity_minor_units",
                "margin_used_minor_units",
                "margin_free_minor_units",
            ),
            (
                "PHASE13-FAKE-ACCOUNT",
                "FAKE_READ_ONLY",
                False,
                "USD",
                10_000_000,
                10_000_000,
                0,
                10_000_000,
            ),
        ),
        (
            "SYMBOL_TICK_SNAPSHOT",
            (
                "requested_symbol",
                "resolved_symbol",
                "visible",
                "digits",
                "point_scale",
                "bid_price_points",
                "ask_price_points",
                "spread_points",
            ),
            (
                "XAUUSD",
                "XAUUSD",
                True,
                2,
                100,
                241_000,
                241_020,
                20,
            ),
        ),
        (
            "EXPOSURE_SNAPSHOT",
            (
                "open_gold_position_count",
                "pending_gold_order_count",
                "reserved_risk_bps",
                "aggregate_risk_budget_bps",
                "stage_risk_bps",
            ),
            (0, 0, 0, 50, (25, 25)),
        ),
        (
            "ORDER_POSITION_SNAPSHOT",
            (
                "position_ids",
                "order_ids",
                "oco_group_ids",
                "broker_stop_loss_attached",
                "terminal_flat_state",
            ),
            ((), (), (), True, True),
        ),
    )


@dataclass(frozen=True, slots=True)
class Phase13DeterministicFakeRuntimeBoundaryValidationReport:
    boundary_decision: object
    runtime_boundary_contract: object
    admission_decision: object
    admission_permit: object
    phase12_handoff_bundle: object

    schema_version: str
    validation_status: str
    validation_outcome: str
    validation_source: str

    runtime_operation_names: tuple[str, ...]
    runtime_operation_count: int
    runtime_operation_order_valid: bool
    operations_fake_only: bool
    no_real_runtime_operation_invoked: bool

    blocked_write_operation_names: tuple[str, ...]
    blocked_write_operation_count: int
    blocked_write_contract_valid: bool

    fail_closed_error_codes: tuple[str, ...]
    error_mapping_count: int
    error_mapping_contract_valid: bool

    snapshot_payloads: tuple[tuple[str, tuple[str, ...], tuple[object, ...]], ...]
    snapshot_mapping_count: int
    total_snapshot_field_count: int
    snapshot_mapping_coverage_valid: bool
    snapshot_mappings_read_only: bool
    snapshot_mappings_deterministic: bool
    no_real_snapshot_data_used: bool

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

    events: tuple[str, ...]
    event_count: int
    event_trace_contiguous: bool
    event_trace_order_valid: bool

    phase12_lineage_preserved: bool
    admission_lineage_preserved: bool
    boundary_lineage_preserved: bool

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
    ready_for_runtime_safety_audit: bool

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("validation schema is inconsistent.")
        if self.validation_status != VALIDATION_STATUS:
            raise ValueError("validation status must be PASSED.")
        if self.validation_outcome != VALIDATION_OUTCOME:
            raise ValueError("validation outcome is inconsistent.")
        if self.validation_source != VALIDATION_SOURCE:
            raise ValueError("validation source is inconsistent.")
        if self.runtime_operation_count != 10:
            raise ValueError("ten runtime operations must validate.")
        if self.blocked_write_operation_count != 3:
            raise ValueError("three writes must remain blocked.")
        if self.error_mapping_count != 10:
            raise ValueError("ten error mappings must validate.")
        if self.snapshot_mapping_count != 5:
            raise ValueError("five snapshots must validate.")
        if self.total_snapshot_field_count != 32:
            raise ValueError("snapshot field count is inconsistent.")
        if self.symbol != "XAUUSD":
            raise ValueError("validation is XAUUSD only.")
        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("timeframes are inconsistent.")
        if not self.closed_candles_only:
            raise ValueError("closed candles are required.")
        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required.")
        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps.")
        if self.stage_risk_bps != (25, 25):
            raise ValueError("staged risk must be 25+25 bps.")
        if self.events != EVENT_TYPES or self.event_count != 15:
            raise ValueError("validation event trace is inconsistent.")

        required = (
            self.runtime_operation_order_valid,
            self.operations_fake_only,
            self.no_real_runtime_operation_invoked,
            self.blocked_write_contract_valid,
            self.error_mapping_contract_valid,
            self.snapshot_mapping_coverage_valid,
            self.snapshot_mappings_read_only,
            self.snapshot_mappings_deterministic,
            self.no_real_snapshot_data_used,
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
            self.explicit_human_authorization_required,
            self.separate_runtime_execution_gate_required,
            self.separate_real_account_read_gate_required,
            self.separate_production_gate_required,
            self.no_real_or_external_effects,
            self.ready_for_runtime_safety_audit,
        )
        if not all(required):
            raise ValueError("fake validation lost a safety invariant.")

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
            raise ValueError("fake validation detected a real effect.")

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
    def validation_digest(self) -> str:
        contract_id = str(getattr(self.runtime_boundary_contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        handoff_id = str(getattr(self.phase12_handoff_bundle, "handoff_id", ""))
        snapshot_material = ",".join(
            f"{name}:{','.join(fields)}:{repr(values)}"
            for name, fields, values in self.snapshot_payloads
        )
        material = "|".join(
            (
                self.schema_version,
                contract_id,
                permit_id,
                handoff_id,
                self.validation_status,
                self.validation_outcome,
                self.validation_source,
                ",".join(self.runtime_operation_names),
                ",".join(self.blocked_write_operation_names),
                ",".join(self.fail_closed_error_codes),
                snapshot_material,
                ",".join(self.events),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.no_real_or_external_effects),
                str(self.ready_for_runtime_safety_audit),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def validation_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_13_DETERMINISTIC_FAKE_BOUNDARY_VALIDATION:"
            f"SHA256[{self.validation_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase13DeterministicFakeRuntimeBoundaryValidationDecision:
    is_allowed: bool
    report: Phase13DeterministicFakeRuntimeBoundaryValidationReport | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.report is None or self.blockers:
                raise ValueError("allowed validation decision is inconsistent.")
        elif self.report is not None or not self.blockers:
            raise ValueError("blocked validation decision is inconsistent.")

    @property
    def report_required(
        self,
    ) -> Phase13DeterministicFakeRuntimeBoundaryValidationReport:
        if self.report is None:
            raise RuntimeError("Phase 13 deterministic fake boundary validation is blocked.")
        return self.report


class StrategyPhase13DeterministicFakeRuntimeBoundaryValidator:
    def validate(
        self,
        boundary_decision: object,
    ) -> Phase13DeterministicFakeRuntimeBoundaryValidationDecision:
        if boundary_decision is None:
            return Phase13DeterministicFakeRuntimeBoundaryValidationDecision(
                False,
                None,
                ("runtime_boundary_decision_missing",),
            )
        if getattr(boundary_decision, "is_allowed", True) is not True:
            return Phase13DeterministicFakeRuntimeBoundaryValidationDecision(
                False,
                None,
                ("runtime_boundary_decision_blocked",),
            )

        try:
            contract = _required(boundary_decision, "contract_required")
            admission_decision = _required(contract, "admission_decision")
            admission_permit = _required(contract, "admission_permit")
            phase12_handoff_bundle = _required(
                contract,
                "phase12_handoff_bundle",
            )
            source_valid = (
                _required(contract, "contract_status") == "CONTRACT_READY"
                and _required(contract, "contract_mode")
                == "CONTROLLED_READ_ONLY_RUNTIME_BOUNDARY_CONTRACT_ONLY"
                and _required(contract, "runtime_operation_count") == 10
                and _required(contract, "blocked_write_operation_count") == 3
                and _required(contract, "error_mapping_count") == 10
                and _required(contract, "snapshot_mapping_count") == 5
                and _required(contract, "total_snapshot_field_count") == 32
                and _required(contract, "contract_ready_for_fake_validation") is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase13DeterministicFakeRuntimeBoundaryValidationDecision(
                False,
                None,
                (f"runtime_boundary_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase13DeterministicFakeRuntimeBoundaryValidationDecision(
                False,
                None,
                ("runtime_boundary_invariants_failed",),
            )

        operation_names = tuple(
            operation.operation_name for operation in contract.runtime_operations
        )
        blocked_names = tuple(
            operation.operation_name for operation in contract.blocked_write_operations
        )
        error_codes = tuple(mapping.error_code for mapping in contract.error_mappings)
        payloads = _snapshot_payloads()
        snapshot_names = tuple(payload[0] for payload in payloads)
        expected_snapshot_names = tuple(
            mapping.snapshot_name for mapping in contract.snapshot_mappings
        )
        mapping_coverage = snapshot_names == expected_snapshot_names and all(
            fields == mapping.field_names
            for (_, fields, _), mapping in zip(
                payloads,
                contract.snapshot_mappings,
                strict=True,
            )
        )

        exposure = dict(zip(payloads[3][1], payloads[3][2], strict=True))
        flat_state = (
            exposure["open_gold_position_count"] == 0
            and exposure["pending_gold_order_count"] == 0
            and exposure["reserved_risk_bps"] == 0
        )
        risk_valid = (
            contract.symbol == "XAUUSD"
            and contract.timeframes == ("H4", "H1", "M15", "M5")
            and contract.closed_candles_only is True
            and contract.max_gold_positions == 1
            and contract.aggregate_risk_budget_bps == 50
            and contract.stage_risk_bps == (25, 25)
            and sum(contract.stage_risk_bps) == contract.aggregate_risk_budget_bps
        )
        blocked_valid = blocked_names == (
            "ORDER_CHECK",
            "ORDER_SEND",
            "APPLICATION_OCO_CONTROL",
        ) and all(
            not operation.invocation_allowed and operation.fail_closed
            for operation in contract.blocked_write_operations
        )
        errors_valid = all(
            mapping.outcome == "BLOCKED"
            and not mapping.retry_allowed
            and not mapping.side_effects_allowed
            and mapping.human_review_required
            for mapping in contract.error_mappings
        )
        no_effects = (
            not contract.permits_real_preflight_execution
            and not contract.permits_real_mt5_import
            and not contract.permits_mt5_initialization
            and not contract.permits_terminal_connection
            and not contract.permits_broker_access
            and not contract.permits_real_account_reads
            and not contract.permits_order_check
            and not contract.permits_order_send
            and not contract.permits_external_writes
            and not contract.permits_production_activation
            and not contract.permits_live_order_submission
        )

        report = Phase13DeterministicFakeRuntimeBoundaryValidationReport(
            boundary_decision=boundary_decision,
            runtime_boundary_contract=contract,
            admission_decision=admission_decision,
            admission_permit=admission_permit,
            phase12_handoff_bundle=phase12_handoff_bundle,
            schema_version=SCHEMA_VERSION,
            validation_status=VALIDATION_STATUS,
            validation_outcome=VALIDATION_OUTCOME,
            validation_source=VALIDATION_SOURCE,
            runtime_operation_names=operation_names,
            runtime_operation_count=len(operation_names),
            runtime_operation_order_valid=operation_names
            == tuple(operation.operation_name for operation in contract.runtime_operations),
            operations_fake_only=True,
            no_real_runtime_operation_invoked=True,
            blocked_write_operation_names=blocked_names,
            blocked_write_operation_count=len(blocked_names),
            blocked_write_contract_valid=blocked_valid,
            fail_closed_error_codes=error_codes,
            error_mapping_count=len(error_codes),
            error_mapping_contract_valid=errors_valid,
            snapshot_payloads=payloads,
            snapshot_mapping_count=len(payloads),
            total_snapshot_field_count=sum(len(fields) for _, fields, _ in payloads),
            snapshot_mapping_coverage_valid=mapping_coverage,
            snapshot_mappings_read_only=True,
            snapshot_mappings_deterministic=True,
            no_real_snapshot_data_used=True,
            symbol=contract.symbol,
            timeframes=contract.timeframes,
            closed_candles_only=contract.closed_candles_only,
            max_gold_positions=contract.max_gold_positions,
            aggregate_risk_budget_bps=contract.aggregate_risk_budget_bps,
            stage_risk_bps=contract.stage_risk_bps,
            risk_contract_valid=risk_valid,
            oco_required=contract.oco_required,
            broker_stop_loss_required=contract.broker_stop_loss_required,
            guards_required=contract.guards_required,
            terminal_flat_state_required=contract.terminal_flat_state_required,
            oco_broker_sl_guard_contract_valid=(
                contract.oco_required
                and contract.broker_stop_loss_required
                and contract.guards_required
                and contract.terminal_flat_state_required
            ),
            terminal_flat_state_valid=flat_state,
            events=EVENT_TYPES,
            event_count=len(EVENT_TYPES),
            event_trace_contiguous=True,
            event_trace_order_valid=True,
            phase12_lineage_preserved=(
                admission_permit.phase12_handoff_bundle is phase12_handoff_bundle
                and phase12_handoff_bundle.phase_status == "PHASE_12_COMPLETE"
            ),
            admission_lineage_preserved=(
                contract.admission_decision is admission_decision
                and contract.admission_permit is admission_permit
            ),
            boundary_lineage_preserved=(boundary_decision.contract_required is contract),
            explicit_human_authorization_required=(contract.explicit_human_authorization_required),
            separate_runtime_execution_gate_required=(
                contract.separate_runtime_execution_gate_required
            ),
            separate_real_account_read_gate_required=(
                contract.separate_real_account_read_gate_required
            ),
            separate_production_gate_required=(contract.separate_production_gate_required),
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
            real_preflight_execution_status="BLOCKED",
            mt5_import_status="BLOCKED",
            mt5_initialization_status="BLOCKED",
            terminal_connection_status="BLOCKED",
            broker_access_status="BLOCKED",
            real_account_read_status="BLOCKED",
            production_activation_status="BLOCKED",
            live_execution_status="BLOCKED",
            no_real_or_external_effects=no_effects,
            ready_for_runtime_safety_audit=True,
        )
        return Phase13DeterministicFakeRuntimeBoundaryValidationDecision(
            True,
            report,
            (),
        )


def validate_phase13_runtime_boundary_with_fakes(
    boundary_decision: object,
) -> Phase13DeterministicFakeRuntimeBoundaryValidationDecision:
    return StrategyPhase13DeterministicFakeRuntimeBoundaryValidator().validate(boundary_decision)


__all__ = (
    "SCHEMA_VERSION",
    "VALIDATION_STATUS",
    "VALIDATION_OUTCOME",
    "VALIDATION_SOURCE",
    "EVENT_TYPES",
    "Phase13DeterministicFakeRuntimeBoundaryValidationReport",
    "Phase13DeterministicFakeRuntimeBoundaryValidationDecision",
    "StrategyPhase13DeterministicFakeRuntimeBoundaryValidator",
    "validate_phase13_runtime_boundary_with_fakes",
)
