from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase12_final_audit_handoff import (
    PHASE_12_FINAL_HANDOFF_EVIDENCE_SOURCE,
    PHASE_12_FINAL_HANDOFF_MODE,
    PHASE_12_FINAL_HANDOFF_PHASE_STATUS,
    PHASE_12_FINAL_HANDOFF_SCHEMA_VERSION,
    PHASE_12_FINAL_HANDOFF_STATUS,
    StrategyPhase12FinalAuditHandoffFactory,
    create_phase12_final_audit_handoff,
)
from tests.test_phase12_preflight_readiness_safety_audit import (
    bullish_phase12_readiness_audit_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedReadinessAuditDecision:
    is_allowed: bool = False


def bullish_phase12_final_audit_handoff_decision():
    return create_phase12_final_audit_handoff(bullish_phase12_readiness_audit_decision())


def test_static_final_handoff_contract_is_stable() -> None:
    assert PHASE_12_FINAL_HANDOFF_SCHEMA_VERSION == "1.0"
    assert PHASE_12_FINAL_HANDOFF_PHASE_STATUS == "PHASE_12_COMPLETE"
    assert PHASE_12_FINAL_HANDOFF_STATUS == "READY_FOR_PHASE_13"
    assert PHASE_12_FINAL_HANDOFF_MODE == "REAL_PREFLIGHT_CONTRACT_ONLY"
    assert PHASE_12_FINAL_HANDOFF_EVIDENCE_SOURCE == "DETERMINISTIC_FAKE_EVIDENCE_ONLY"


def test_phase12_final_handoff_is_created() -> None:
    decision = bullish_phase12_final_audit_handoff_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.bundle is not None


def test_complete_lineage_is_preserved() -> None:
    audit_decision = bullish_phase12_readiness_audit_decision()
    audit = audit_decision.report_required
    bundle = create_phase12_final_audit_handoff(audit_decision).bundle_required

    assert bundle.readiness_audit_decision is audit_decision
    assert bundle.readiness_audit_report is audit
    assert bundle.validation_decision is audit.validation_decision
    assert bundle.validation_report is audit.validation_report
    assert bundle.runtime_contract_decision is audit.runtime_contract_decision
    assert bundle.runtime_contract is audit.runtime_contract
    assert bundle.admission_decision is audit.admission_decision
    assert bundle.admission_permit is audit.admission_permit
    assert bundle.phase11_handoff_bundle is audit.phase11_handoff_bundle


def test_phase_transition_and_completion_are_exact() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.phase_number == 12
    assert bundle.source_phase_number == 11
    assert bundle.target_phase_number == 13
    assert bundle.phase_status == "PHASE_12_COMPLETE"
    assert bundle.handoff_status == "READY_FOR_PHASE_13"
    assert bundle.phase_complete is True
    assert bundle.ready_for_phase_13 is True


def test_audit_validation_and_contract_statuses_are_exact() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.contract_mode == "REAL_PREFLIGHT_CONTRACT_ONLY"
    assert bundle.evidence_source == "DETERMINISTIC_FAKE_EVIDENCE_ONLY"
    assert bundle.readiness_audit_status == "PASSED"
    assert bundle.readiness_audit_handoff_status == "READY_FOR_FINAL_HANDOFF"
    assert bundle.validation_status == "PASSED"
    assert bundle.validation_outcome == "READY_FOR_READINESS_AUDIT"


def test_market_and_risk_scope_is_exact() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.symbol == "XAUUSD"
    assert bundle.timeframes == ("H4", "H1", "M15", "M5")
    assert bundle.closed_candles_only is True
    assert bundle.max_gold_positions == 1
    assert bundle.aggregate_risk_budget_bps == 50
    assert bundle.stage_risk_bps == (25, 25)
    assert bundle.risk_contract_valid is True


def test_oco_stop_loss_guards_and_flat_state_are_exact() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.oco_required is True
    assert bundle.broker_stop_loss_required is True
    assert bundle.guards_required is True
    assert bundle.terminal_flat_state_required is True
    assert bundle.oco_broker_sl_guard_contract_valid is True
    assert bundle.terminal_flat_state_valid is True


def test_capability_snapshot_event_and_finding_counts_are_exact() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.verified_capability_count == 14
    assert bundle.blocked_capability_count == 3
    assert bundle.snapshot_schema_count == 5
    assert bundle.total_snapshot_field_count == 32
    assert bundle.validation_event_count == 14
    assert bundle.readiness_finding_count == 14


def test_all_snapshot_and_contract_flags_are_true() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.terminal_snapshot_valid is True
    assert bundle.account_snapshot_valid is True
    assert bundle.symbol_tick_snapshot_valid is True
    assert bundle.exposure_snapshot_valid is True
    assert bundle.order_position_snapshot_valid is True
    assert bundle.capability_contract_valid is True
    assert bundle.snapshot_schema_coverage_valid is True
    assert bundle.validation_event_trace_contiguous is True
    assert bundle.validation_event_trace_order_valid is True


def test_all_lineage_flags_are_true() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.phase11_lineage_preserved is True
    assert bundle.admission_lineage_preserved is True
    assert bundle.runtime_contract_lineage_preserved is True
    assert bundle.validation_lineage_preserved is True
    assert bundle.readiness_audit_lineage_preserved is True


def test_future_authorization_gates_remain_mandatory() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.explicit_human_authorization_required is True
    assert bundle.separate_runtime_gate_required is True
    assert bundle.separate_production_gate_required is True


def test_all_real_and_external_effects_are_blocked() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.real_mt5_imported is False
    assert bundle.real_mt5_initialized is False
    assert bundle.real_terminal_connected is False
    assert bundle.real_broker_request_sent is False
    assert bundle.real_account_read_performed is False
    assert bundle.order_check_invoked is False
    assert bundle.order_send_invoked is False
    assert bundle.external_state_written is False
    assert bundle.production_activated is False
    assert bundle.live_order_submitted is False
    assert bundle.no_real_or_external_effects is True


def test_all_runtime_statuses_remain_blocked() -> None:
    bundle = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert bundle.real_preflight_execution_status == "BLOCKED"
    assert bundle.mt5_initialization_status == "BLOCKED"
    assert bundle.terminal_connection_status == "BLOCKED"
    assert bundle.broker_access_status == "BLOCKED"
    assert bundle.production_activation_status == "BLOCKED"
    assert bundle.live_execution_status == "BLOCKED"


def test_final_handoff_id_is_deterministic() -> None:
    first = bullish_phase12_final_audit_handoff_decision().bundle_required
    second = bullish_phase12_final_audit_handoff_decision().bundle_required
    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id


def test_missing_readiness_audit_blocks_handoff() -> None:
    decision = create_phase12_final_audit_handoff(None)
    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("readiness_audit_decision_missing",)


def test_blocked_readiness_audit_blocks_handoff() -> None:
    decision = create_phase12_final_audit_handoff(FakeBlockedReadinessAuditDecision())
    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("readiness_audit_decision_blocked",)
    with pytest.raises(RuntimeError, match="handoff is blocked"):
        _ = decision.bundle_required


def test_factory_and_function_api_match() -> None:
    audit_decision = bullish_phase12_readiness_audit_decision()
    factory = StrategyPhase12FinalAuditHandoffFactory().create(audit_decision).bundle_required
    function = create_phase12_final_audit_handoff(audit_decision).bundle_required
    assert factory.handoff_id == function.handoff_id


def test_final_handoff_does_not_mutate_readiness_audit() -> None:
    audit_decision = bullish_phase12_readiness_audit_decision()
    audit = audit_decision.report_required
    before = (
        audit.audit_status,
        audit.handoff_status,
        audit.validation_status,
        audit.validation_outcome,
        audit.verified_capability_count,
        audit.blocked_capability_count,
        audit.snapshot_schema_count,
        audit.total_snapshot_field_count,
        audit.validation_event_count,
        len(audit.findings),
    )

    _ = create_phase12_final_audit_handoff(audit_decision).bundle_required

    after = (
        audit.audit_status,
        audit.handoff_status,
        audit.validation_status,
        audit.validation_outcome,
        audit.verified_capability_count,
        audit.blocked_capability_count,
        audit.snapshot_schema_count,
        audit.total_snapshot_field_count,
        audit.validation_event_count,
        len(audit.findings),
    )

    assert after == before
