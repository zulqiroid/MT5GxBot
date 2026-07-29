from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase12_real_preflight_runtime_contract import (
    PHASE_12_BLOCKED_ADAPTER_CAPABILITY_IDS,
    PHASE_12_RUNTIME_CONTRACT_MODE,
    PHASE_12_RUNTIME_CONTRACT_SCHEMA_VERSION,
    PHASE_12_RUNTIME_CONTRACT_SOURCE,
    PHASE_12_RUNTIME_CONTRACT_STATUS,
    PHASE_12_SNAPSHOT_SCHEMA_NAMES,
    PHASE_12_VERIFIED_ADAPTER_CAPABILITY_IDS,
    StrategyPhase12RealPreflightRuntimeContractFactory,
    create_phase12_real_preflight_runtime_contract,
)
from tests.test_phase12_real_preflight_planning_admission_gate import (
    bullish_phase12_real_preflight_planning_admission_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedAdmissionDecision:
    is_allowed: bool = False


def bullish_phase12_runtime_contract_decision():
    return create_phase12_real_preflight_runtime_contract(
        bullish_phase12_real_preflight_planning_admission_decision()
    )


def test_static_runtime_contract_is_stable() -> None:
    assert PHASE_12_RUNTIME_CONTRACT_SCHEMA_VERSION == "1.0"
    assert PHASE_12_RUNTIME_CONTRACT_STATUS == "CONTRACT_READY"
    assert PHASE_12_RUNTIME_CONTRACT_MODE == "REAL_PREFLIGHT_CONTRACT_ONLY"
    assert PHASE_12_RUNTIME_CONTRACT_SOURCE == "IMMUTABLE_PLANNING_ONLY"


def test_runtime_contract_is_created() -> None:
    decision = bullish_phase12_runtime_contract_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.contract is not None


def test_admission_lineage_is_preserved() -> None:
    admission = bullish_phase12_real_preflight_planning_admission_decision()
    contract = create_phase12_real_preflight_runtime_contract(admission).contract_required
    assert contract.admission_decision is admission
    assert contract.admission_permit is admission.permit_required
    assert contract.phase11_handoff_bundle is admission.permit_required.phase11_handoff_bundle


def test_contract_status_mode_and_source_are_exact() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    assert contract.contract_status == "CONTRACT_READY"
    assert contract.contract_mode == "REAL_PREFLIGHT_CONTRACT_ONLY"
    assert contract.contract_source == "IMMUTABLE_PLANNING_ONLY"
    assert contract.contract_ready_for_fake_validation is True


def test_verified_adapter_capabilities_are_exact() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    assert (
        tuple(capability.capability_id for capability in contract.verified_adapter_capabilities)
        == PHASE_12_VERIFIED_ADAPTER_CAPABILITY_IDS
    )
    assert contract.verified_capability_count == 14


def test_blocked_adapter_capabilities_are_exact() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    assert (
        tuple(capability.capability_id for capability in contract.blocked_adapter_capabilities)
        == PHASE_12_BLOCKED_ADAPTER_CAPABILITY_IDS
    )
    assert contract.blocked_capability_count == 3
    assert all(
        capability.access_class == "CONTROLLED_WRITE"
        for capability in contract.blocked_adapter_capabilities
    )


def test_snapshot_schemas_are_exact() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    assert (
        tuple(schema.schema_name for schema in contract.snapshot_schemas)
        == PHASE_12_SNAPSHOT_SCHEMA_NAMES
    )
    assert contract.snapshot_schema_count == 5
    assert contract.total_snapshot_field_count == 32
    assert all(schema.read_only is True for schema in contract.snapshot_schemas)
    assert all(schema.real_data_access_allowed is False for schema in contract.snapshot_schemas)


def test_gold_risk_and_timeframe_scope_is_exact() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    assert contract.symbol == "XAUUSD"
    assert contract.timeframes == ("H4", "H1", "M15", "M5")
    assert contract.closed_candles_only is True
    assert contract.max_gold_positions == 1
    assert contract.aggregate_risk_budget_bps == 50
    assert contract.stage_risk_bps == (25, 25)


def test_oco_guard_and_prohibited_patterns_are_preserved() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    assert contract.oco_required is True
    assert contract.broker_stop_loss_required is True
    assert contract.guards_required is True
    assert contract.terminal_flat_state_required is True
    assert contract.martingale_prohibited is True
    assert contract.grid_prohibited is True
    assert contract.no_stop_loss_prohibited is True


def test_contract_allows_fake_validation_only() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    assert contract.permits_contract_validation is True
    assert contract.permits_fake_adapter_validation is True
    assert contract.permits_fake_snapshot_validation is True


def test_runtime_invocation_is_blocked_for_all_capabilities() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    all_capabilities = (
        contract.verified_adapter_capabilities + contract.blocked_adapter_capabilities
    )
    assert all(capability.runtime_invocation_allowed is False for capability in all_capabilities)
    assert all(capability.separate_runtime_gate_required is True for capability in all_capabilities)


def test_all_real_and_external_effects_are_blocked() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    assert contract.permits_real_mt5_import is False
    assert contract.permits_mt5_initialization is False
    assert contract.permits_terminal_connection is False
    assert contract.permits_broker_requests is False
    assert contract.permits_real_account_reads is False
    assert contract.permits_order_check is False
    assert contract.permits_order_send is False
    assert contract.permits_external_writes is False
    assert contract.permits_production_activation is False
    assert contract.permits_live_order_submission is False
    assert contract.real_preflight_execution_status == "BLOCKED"
    assert contract.mt5_initialization_status == "BLOCKED"
    assert contract.terminal_connection_status == "BLOCKED"
    assert contract.broker_access_status == "BLOCKED"
    assert contract.production_activation_status == "BLOCKED"
    assert contract.live_execution_status == "BLOCKED"


def test_future_gates_remain_mandatory() -> None:
    contract = bullish_phase12_runtime_contract_decision().contract_required
    assert contract.explicit_human_authorization_required is True
    assert contract.separate_runtime_gate_required is True
    assert contract.separate_production_gate_required is True


def test_contract_id_is_deterministic() -> None:
    first = bullish_phase12_runtime_contract_decision().contract_required
    second = bullish_phase12_runtime_contract_decision().contract_required
    assert first.contract_digest == second.contract_digest
    assert first.contract_id == second.contract_id


def test_missing_admission_blocks_contract() -> None:
    decision = create_phase12_real_preflight_runtime_contract(None)
    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("phase12_admission_decision_missing",)


def test_blocked_admission_blocks_contract() -> None:
    decision = create_phase12_real_preflight_runtime_contract(FakeBlockedAdmissionDecision())
    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("phase12_admission_decision_blocked",)
    with pytest.raises(RuntimeError, match="runtime contract is blocked"):
        _ = decision.contract_required


def test_factory_and_function_api_match() -> None:
    admission = bullish_phase12_real_preflight_planning_admission_decision()
    factory = (
        StrategyPhase12RealPreflightRuntimeContractFactory().create(admission).contract_required
    )
    function = create_phase12_real_preflight_runtime_contract(admission).contract_required
    assert factory.contract_id == function.contract_id
