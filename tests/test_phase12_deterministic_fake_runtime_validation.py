from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase12_deterministic_fake_runtime_validation import (
    PHASE_12_FAKE_VALIDATION_EVENT_TYPES,
    PHASE_12_FAKE_VALIDATION_OUTCOME,
    PHASE_12_FAKE_VALIDATION_SCHEMA_VERSION,
    PHASE_12_FAKE_VALIDATION_SOURCE,
    PHASE_12_FAKE_VALIDATION_STATUS,
    StrategyPhase12DeterministicFakeRuntimeValidator,
    validate_phase12_runtime_contract_with_fakes,
)
from tests.test_phase12_real_preflight_runtime_contract import (
    bullish_phase12_runtime_contract_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedContractDecision:
    is_allowed: bool = False


def bullish_phase12_fake_validation_decision():
    return validate_phase12_runtime_contract_with_fakes(bullish_phase12_runtime_contract_decision())


def test_static_fake_validation_contract_is_stable() -> None:
    assert PHASE_12_FAKE_VALIDATION_SCHEMA_VERSION == "1.0"
    assert PHASE_12_FAKE_VALIDATION_STATUS == "PASSED"
    assert PHASE_12_FAKE_VALIDATION_OUTCOME == "READY_FOR_READINESS_AUDIT"
    assert PHASE_12_FAKE_VALIDATION_SOURCE == "DETERMINISTIC_IN_MEMORY_FAKE"


def test_fake_validation_report_is_created() -> None:
    decision = bullish_phase12_fake_validation_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None


def test_complete_lineage_is_preserved() -> None:
    contract_decision = bullish_phase12_runtime_contract_decision()
    contract = contract_decision.contract_required
    report = validate_phase12_runtime_contract_with_fakes(contract_decision).report_required

    assert report.contract_decision is contract_decision
    assert report.runtime_contract is contract
    assert report.admission_decision is contract.admission_decision
    assert report.admission_permit is contract.admission_permit
    assert report.phase11_handoff_bundle is contract.phase11_handoff_bundle


def test_validation_status_outcome_and_source_are_exact() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.validation_status == "PASSED"
    assert report.validation_outcome == "READY_FOR_READINESS_AUDIT"
    assert report.validation_source == "DETERMINISTIC_IN_MEMORY_FAKE"
    assert report.ready_for_readiness_audit is True


def test_capability_validation_is_exact() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.verified_capability_count == 14
    assert report.blocked_capability_count == 3
    assert report.verified_capability_contracts_valid is True
    assert report.blocked_capability_contracts_valid is True
    assert report.blocked_capability_ids == (
        "ORDER_CHECK",
        "ORDER_SEND",
        "APPLICATION_OCO_CONTROL",
    )


def test_snapshot_validation_is_exact() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.snapshot_schema_count == 5
    assert report.total_snapshot_field_count == 32
    assert report.snapshot_schema_coverage_valid is True
    assert report.snapshot_payloads_deterministic is True
    assert report.snapshot_payloads_read_only is True
    assert report.no_real_snapshot_data_used is True
    assert tuple(payload.schema_name for payload in report.snapshot_payloads) == (
        "TERMINAL_SNAPSHOT",
        "ACCOUNT_SNAPSHOT",
        "SYMBOL_TICK_SNAPSHOT",
        "EXPOSURE_SNAPSHOT",
        "ORDER_POSITION_SNAPSHOT",
    )


def test_gold_risk_scope_is_exact() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)
    assert report.risk_contract_valid is True


def test_oco_broker_sl_guards_and_flat_state_are_exact() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.oco_required is True
    assert report.broker_stop_loss_required is True
    assert report.guards_required is True
    assert report.terminal_flat_state_required is True
    assert report.oco_broker_sl_guard_contract_valid is True
    assert report.terminal_flat_state_valid is True


def test_validation_event_trace_is_exact() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.event_count == 14
    assert (
        tuple(event.event_type for event in report.events) == PHASE_12_FAKE_VALIDATION_EVENT_TYPES
    )
    assert tuple(event.sequence_index for event in report.events) == tuple(range(14))
    assert report.event_trace_contiguous is True
    assert report.event_trace_order_valid is True
    assert all(event.status == "PASSED" for event in report.events)


def test_all_lineage_flags_are_true() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.admission_lineage_preserved is True
    assert report.contract_lineage_preserved is True
    assert report.phase11_lineage_preserved is True


def test_future_gates_remain_mandatory() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.explicit_human_authorization_required is True
    assert report.separate_runtime_gate_required is True
    assert report.separate_production_gate_required is True


def test_all_real_and_external_effects_are_blocked() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.real_mt5_imported is False
    assert report.real_mt5_initialized is False
    assert report.real_terminal_connected is False
    assert report.real_broker_request_sent is False
    assert report.real_account_read_performed is False
    assert report.order_check_invoked is False
    assert report.order_send_invoked is False
    assert report.external_state_written is False
    assert report.production_activated is False
    assert report.live_order_submitted is False
    assert report.no_real_or_external_effects is True


def test_all_runtime_statuses_are_blocked() -> None:
    report = bullish_phase12_fake_validation_decision().report_required
    assert report.real_preflight_execution_status == "BLOCKED"
    assert report.mt5_initialization_status == "BLOCKED"
    assert report.terminal_connection_status == "BLOCKED"
    assert report.broker_access_status == "BLOCKED"
    assert report.production_activation_status == "BLOCKED"
    assert report.live_execution_status == "BLOCKED"


def test_validation_id_is_deterministic() -> None:
    first = bullish_phase12_fake_validation_decision().report_required
    second = bullish_phase12_fake_validation_decision().report_required
    assert first.validation_digest == second.validation_digest
    assert first.validation_id == second.validation_id


def test_missing_contract_blocks_validation() -> None:
    decision = validate_phase12_runtime_contract_with_fakes(None)
    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("runtime_contract_decision_missing",)


def test_blocked_contract_blocks_validation() -> None:
    decision = validate_phase12_runtime_contract_with_fakes(FakeBlockedContractDecision())
    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("runtime_contract_decision_blocked",)
    with pytest.raises(RuntimeError, match="validation is blocked"):
        _ = decision.report_required


def test_factory_and_function_api_match() -> None:
    contract_decision = bullish_phase12_runtime_contract_decision()
    factory = (
        StrategyPhase12DeterministicFakeRuntimeValidator()
        .validate(contract_decision)
        .report_required
    )
    function = validate_phase12_runtime_contract_with_fakes(contract_decision).report_required
    assert factory.validation_id == function.validation_id
