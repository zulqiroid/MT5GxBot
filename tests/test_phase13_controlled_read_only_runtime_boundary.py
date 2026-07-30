from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase13_controlled_read_only_runtime_boundary import (
    PHASE_13_BLOCKED_WRITE_OPERATION_NAMES,
    PHASE_13_ERROR_MAPPING_CODES,
    PHASE_13_RUNTIME_BOUNDARY_MODE,
    PHASE_13_RUNTIME_BOUNDARY_SCHEMA_VERSION,
    PHASE_13_RUNTIME_BOUNDARY_SOURCE,
    PHASE_13_RUNTIME_BOUNDARY_STATUS,
    PHASE_13_RUNTIME_OPERATION_NAMES,
    PHASE_13_SNAPSHOT_MAPPING_NAMES,
    StrategyPhase13ControlledReadOnlyRuntimeBoundaryFactory,
    create_phase13_controlled_read_only_runtime_boundary,
)
from tests.test_phase13_controlled_read_only_runtime_admission_gate import (
    bullish_phase13_runtime_admission_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedAdmissionDecision:
    is_allowed: bool = False


def bullish_phase13_runtime_boundary_decision():
    return create_phase13_controlled_read_only_runtime_boundary(
        bullish_phase13_runtime_admission_decision()
    )


def test_static_runtime_boundary_contract_is_stable() -> None:
    assert PHASE_13_RUNTIME_BOUNDARY_SCHEMA_VERSION == "1.0"
    assert PHASE_13_RUNTIME_BOUNDARY_STATUS == "CONTRACT_READY"
    assert PHASE_13_RUNTIME_BOUNDARY_MODE == "CONTROLLED_READ_ONLY_RUNTIME_BOUNDARY_CONTRACT_ONLY"
    assert PHASE_13_RUNTIME_BOUNDARY_SOURCE == "IMMUTABLE_PLANNING_ONLY"


def test_runtime_boundary_contract_is_created() -> None:
    decision = bullish_phase13_runtime_boundary_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.contract is not None


def test_admission_and_phase12_lineage_are_preserved() -> None:
    admission = bullish_phase13_runtime_admission_decision()
    contract = create_phase13_controlled_read_only_runtime_boundary(admission).contract_required
    assert contract.admission_decision is admission
    assert contract.admission_permit is admission.permit_required
    assert contract.phase12_handoff_bundle is admission.permit_required.phase12_handoff_bundle


def test_contract_status_mode_and_source_are_exact() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert contract.contract_status == "CONTRACT_READY"
    assert contract.contract_mode == "CONTROLLED_READ_ONLY_RUNTIME_BOUNDARY_CONTRACT_ONLY"
    assert contract.contract_source == "IMMUTABLE_PLANNING_ONLY"
    assert contract.contract_ready_for_fake_validation is True


def test_runtime_operations_are_exact_and_blocked() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert (
        tuple(operation.operation_name for operation in contract.runtime_operations)
        == PHASE_13_RUNTIME_OPERATION_NAMES
    )
    assert contract.runtime_operation_count == 10
    assert all(
        operation.runtime_invocation_allowed is False for operation in contract.runtime_operations
    )
    assert all(
        operation.separate_runtime_gate_required is True
        for operation in contract.runtime_operations
    )


def test_blocked_write_operations_are_exact() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert (
        tuple(operation.operation_name for operation in contract.blocked_write_operations)
        == PHASE_13_BLOCKED_WRITE_OPERATION_NAMES
    )
    assert contract.blocked_write_operation_count == 3
    assert all(operation.fail_closed is True for operation in contract.blocked_write_operations)
    assert all(
        operation.invocation_allowed is False for operation in contract.blocked_write_operations
    )


def test_fail_closed_error_mappings_are_exact() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert (
        tuple(mapping.error_code for mapping in contract.error_mappings)
        == PHASE_13_ERROR_MAPPING_CODES
    )
    assert contract.error_mapping_count == 10
    assert all(mapping.outcome == "BLOCKED" for mapping in contract.error_mappings)
    assert all(mapping.retry_allowed is False for mapping in contract.error_mappings)
    assert all(mapping.side_effects_allowed is False for mapping in contract.error_mappings)
    assert all(mapping.human_review_required is True for mapping in contract.error_mappings)


def test_snapshot_mappings_are_exact() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert (
        tuple(mapping.snapshot_name for mapping in contract.snapshot_mappings)
        == PHASE_13_SNAPSHOT_MAPPING_NAMES
    )
    assert contract.snapshot_mapping_count == 5
    assert contract.total_snapshot_field_count == 32
    assert all(mapping.read_only is True for mapping in contract.snapshot_mappings)
    assert all(mapping.real_data_access_allowed is False for mapping in contract.snapshot_mappings)


def test_gold_risk_scope_is_exact() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert contract.symbol == "XAUUSD"
    assert contract.timeframes == ("H4", "H1", "M15", "M5")
    assert contract.closed_candles_only is True
    assert contract.max_gold_positions == 1
    assert contract.aggregate_risk_budget_bps == 50
    assert contract.stage_risk_bps == (25, 25)


def test_safety_invariants_are_preserved() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert contract.oco_required is True
    assert contract.broker_stop_loss_required is True
    assert contract.guards_required is True
    assert contract.terminal_flat_state_required is True


def test_fake_validation_is_the_only_allowed_next_action() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert contract.permits_fake_boundary_validation is True
    assert contract.permits_fake_error_mapping_validation is True
    assert contract.permits_fake_snapshot_mapping_validation is True


def test_all_real_and_external_effects_are_blocked() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert contract.permits_real_preflight_execution is False
    assert contract.permits_real_mt5_import is False
    assert contract.permits_mt5_initialization is False
    assert contract.permits_terminal_connection is False
    assert contract.permits_broker_access is False
    assert contract.permits_real_account_reads is False
    assert contract.permits_order_check is False
    assert contract.permits_order_send is False
    assert contract.permits_external_writes is False
    assert contract.permits_production_activation is False
    assert contract.permits_live_order_submission is False


def test_all_runtime_statuses_remain_blocked() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert contract.real_preflight_execution_status == "BLOCKED"
    assert contract.mt5_import_status == "BLOCKED"
    assert contract.mt5_initialization_status == "BLOCKED"
    assert contract.terminal_connection_status == "BLOCKED"
    assert contract.broker_access_status == "BLOCKED"
    assert contract.real_account_read_status == "BLOCKED"
    assert contract.production_activation_status == "BLOCKED"
    assert contract.live_execution_status == "BLOCKED"


def test_future_gates_remain_mandatory() -> None:
    contract = bullish_phase13_runtime_boundary_decision().contract_required
    assert contract.explicit_human_authorization_required is True
    assert contract.separate_runtime_execution_gate_required is True
    assert contract.separate_real_account_read_gate_required is True
    assert contract.separate_production_gate_required is True


def test_contract_id_is_deterministic() -> None:
    first = bullish_phase13_runtime_boundary_decision().contract_required
    second = bullish_phase13_runtime_boundary_decision().contract_required
    assert first.contract_digest == second.contract_digest
    assert first.contract_id == second.contract_id


def test_missing_admission_blocks_contract() -> None:
    decision = create_phase13_controlled_read_only_runtime_boundary(None)
    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("phase13_admission_decision_missing",)


def test_blocked_admission_blocks_contract() -> None:
    decision = create_phase13_controlled_read_only_runtime_boundary(FakeBlockedAdmissionDecision())
    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("phase13_admission_decision_blocked",)
    with pytest.raises(RuntimeError, match="runtime boundary is blocked"):
        _ = decision.contract_required


def test_factory_and_function_api_match() -> None:
    admission = bullish_phase13_runtime_admission_decision()
    factory = (
        StrategyPhase13ControlledReadOnlyRuntimeBoundaryFactory()
        .create(admission)
        .contract_required
    )
    function = create_phase13_controlled_read_only_runtime_boundary(admission).contract_required
    assert factory.contract_id == function.contract_id
