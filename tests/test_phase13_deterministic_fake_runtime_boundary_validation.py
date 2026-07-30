from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase13_deterministic_fake_runtime_boundary_validation import (
    EVENT_TYPES,
    SCHEMA_VERSION,
    VALIDATION_OUTCOME,
    VALIDATION_SOURCE,
    VALIDATION_STATUS,
    StrategyPhase13DeterministicFakeRuntimeBoundaryValidator,
    validate_phase13_runtime_boundary_with_fakes,
)
from tests.test_phase13_controlled_read_only_runtime_boundary import (
    bullish_phase13_runtime_boundary_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedBoundaryDecision:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase13_fake_boundary_validation_decision():
    return validate_phase13_runtime_boundary_with_fakes(bullish_phase13_runtime_boundary_decision())


def test_static_contract_is_stable() -> None:
    assert SCHEMA_VERSION == "1.0"
    assert VALIDATION_STATUS == "PASSED"
    assert VALIDATION_OUTCOME == "READY_FOR_RUNTIME_SAFETY_AUDIT"
    assert VALIDATION_SOURCE == "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"


def test_fake_boundary_validation_report_is_created() -> None:
    decision = bullish_phase13_fake_boundary_validation_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None


def test_complete_lineage_is_preserved() -> None:
    source = bullish_phase13_runtime_boundary_decision()
    contract = source.contract_required
    report = validate_phase13_runtime_boundary_with_fakes(source).report_required
    assert report.boundary_decision is source
    assert report.runtime_boundary_contract is contract
    assert report.admission_decision is contract.admission_decision
    assert report.admission_permit is contract.admission_permit
    assert report.phase12_handoff_bundle is contract.phase12_handoff_bundle


def test_status_outcome_and_source_are_exact() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.validation_status == "PASSED"
    assert report.validation_outcome == "READY_FOR_RUNTIME_SAFETY_AUDIT"
    assert report.validation_source == "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"
    assert report.ready_for_runtime_safety_audit is True


def test_runtime_operation_validation_is_exact() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.runtime_operation_count == 10
    assert report.runtime_operation_order_valid is True
    assert report.operations_fake_only is True
    assert report.no_real_runtime_operation_invoked is True


def test_blocked_writes_and_error_mappings_are_exact() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.blocked_write_operation_count == 3
    assert report.blocked_write_operation_names == (
        "ORDER_CHECK",
        "ORDER_SEND",
        "APPLICATION_OCO_CONTROL",
    )
    assert report.blocked_write_contract_valid is True
    assert report.error_mapping_count == 10
    assert report.error_mapping_contract_valid is True


def test_snapshot_mapping_validation_is_exact() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.snapshot_mapping_count == 5
    assert report.total_snapshot_field_count == 32
    assert report.snapshot_mapping_coverage_valid is True
    assert report.snapshot_mappings_read_only is True
    assert report.snapshot_mappings_deterministic is True
    assert report.no_real_snapshot_data_used is True


def test_gold_risk_scope_is_exact() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)
    assert report.risk_contract_valid is True


def test_oco_broker_sl_guards_and_flat_state_are_exact() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.oco_required is True
    assert report.broker_stop_loss_required is True
    assert report.guards_required is True
    assert report.terminal_flat_state_required is True
    assert report.oco_broker_sl_guard_contract_valid is True
    assert report.terminal_flat_state_valid is True


def test_event_trace_is_exact() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.events == EVENT_TYPES
    assert report.event_count == 15
    assert report.event_trace_contiguous is True
    assert report.event_trace_order_valid is True


def test_all_lineage_flags_are_true() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.phase12_lineage_preserved is True
    assert report.admission_lineage_preserved is True
    assert report.boundary_lineage_preserved is True


def test_future_gates_remain_mandatory() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.explicit_human_authorization_required is True
    assert report.separate_runtime_execution_gate_required is True
    assert report.separate_real_account_read_gate_required is True
    assert report.separate_production_gate_required is True


def test_all_real_and_external_effects_are_blocked() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.real_preflight_executed is False
    assert report.real_mt5_imported is False
    assert report.real_mt5_initialized is False
    assert report.real_terminal_connected is False
    assert report.real_broker_access_performed is False
    assert report.real_account_read_performed is False
    assert report.order_check_invoked is False
    assert report.order_send_invoked is False
    assert report.external_state_written is False
    assert report.production_activated is False
    assert report.live_order_submitted is False
    assert report.no_real_or_external_effects is True


def test_all_runtime_statuses_remain_blocked() -> None:
    report = bullish_phase13_fake_boundary_validation_decision().report_required
    assert report.real_preflight_execution_status == "BLOCKED"
    assert report.mt5_import_status == "BLOCKED"
    assert report.mt5_initialization_status == "BLOCKED"
    assert report.terminal_connection_status == "BLOCKED"
    assert report.broker_access_status == "BLOCKED"
    assert report.real_account_read_status == "BLOCKED"
    assert report.production_activation_status == "BLOCKED"
    assert report.live_execution_status == "BLOCKED"


def test_validation_id_is_deterministic() -> None:
    first = bullish_phase13_fake_boundary_validation_decision().report_required
    second = bullish_phase13_fake_boundary_validation_decision().report_required
    assert first.validation_digest == second.validation_digest
    assert first.validation_id == second.validation_id


def test_missing_boundary_blocks_validation() -> None:
    decision = validate_phase13_runtime_boundary_with_fakes(None)
    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("runtime_boundary_decision_missing",)


def test_blocked_boundary_blocks_validation() -> None:
    decision = validate_phase13_runtime_boundary_with_fakes(FakeBlockedBoundaryDecision())
    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("runtime_boundary_decision_blocked",)
    with pytest.raises(RuntimeError, match="validation is blocked"):
        _ = decision.report_required


def test_factory_and_function_api_match() -> None:
    source = bullish_phase13_runtime_boundary_decision()
    factory = (
        StrategyPhase13DeterministicFakeRuntimeBoundaryValidator().validate(source).report_required
    )
    function = validate_phase13_runtime_boundary_with_fakes(source).report_required
    assert factory.validation_id == function.validation_id
