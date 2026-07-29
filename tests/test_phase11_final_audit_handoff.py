from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase11_final_audit_handoff import (
    PHASE_11_FINAL_HANDOFF_LIVE_STATUS,
    PHASE_11_FINAL_HANDOFF_MODE,
    PHASE_11_FINAL_HANDOFF_PHASE_STATUS,
    PHASE_11_FINAL_HANDOFF_PRODUCTION_STATUS,
    PHASE_11_FINAL_HANDOFF_REAL_PREFLIGHT_STATUS,
    PHASE_11_FINAL_HANDOFF_SCHEMA_VERSION,
    PHASE_11_FINAL_HANDOFF_STATUS,
    StrategyPhase11FinalAuditHandoffFactory,
    create_phase11_final_audit_handoff,
)
from tests.test_phase11_readiness_safety_audit import (
    bullish_phase11_readiness_safety_audit_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedReadinessAuditDecision:
    is_allowed: bool = False


def bullish_phase11_final_audit_handoff_decision():
    return create_phase11_final_audit_handoff(bullish_phase11_readiness_safety_audit_decision())


def test_static_final_handoff_contract_is_stable() -> None:
    assert PHASE_11_FINAL_HANDOFF_SCHEMA_VERSION == "1.0"
    assert PHASE_11_FINAL_HANDOFF_PHASE_STATUS == "PHASE_11_COMPLETE"
    assert PHASE_11_FINAL_HANDOFF_STATUS == "READY_FOR_PHASE_12"
    assert PHASE_11_FINAL_HANDOFF_MODE == "DETERMINISTIC_FAKE_READ_ONLY"
    assert PHASE_11_FINAL_HANDOFF_REAL_PREFLIGHT_STATUS == "BLOCKED"
    assert PHASE_11_FINAL_HANDOFF_PRODUCTION_STATUS == "BLOCKED"
    assert PHASE_11_FINAL_HANDOFF_LIVE_STATUS == "BLOCKED"


def test_phase11_final_handoff_is_created() -> None:
    decision = bullish_phase11_final_audit_handoff_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.bundle is not None


def test_complete_lineage_is_preserved() -> None:
    audit_decision = bullish_phase11_readiness_safety_audit_decision()
    report = audit_decision.report_required
    preflight_decision = report.preflight_decision
    preflight = report.preflight
    capability_decision = report.capability_decision
    capability_contract = report.capability_contract
    admission_decision = report.admission_decision
    admission_permit = report.admission_permit
    phase10_bundle = report.phase10_handoff_bundle

    bundle = create_phase11_final_audit_handoff(audit_decision).bundle_required

    assert bundle.readiness_audit_decision is audit_decision
    assert bundle.readiness_audit_report is report
    assert bundle.preflight_decision is preflight_decision
    assert bundle.preflight is preflight
    assert bundle.capability_decision is capability_decision
    assert bundle.capability_contract is capability_contract
    assert bundle.admission_decision is admission_decision
    assert bundle.admission_permit is admission_permit
    assert bundle.phase10_handoff_bundle is phase10_bundle


def test_phase_transition_and_completion_are_exact() -> None:
    bundle = bullish_phase11_final_audit_handoff_decision().bundle_required

    assert bundle.phase_number == 11
    assert bundle.source_phase_number == 10
    assert bundle.target_phase_number == 12
    assert bundle.phase_status == "PHASE_11_COMPLETE"
    assert bundle.handoff_status == "READY_FOR_PHASE_12"
    assert bundle.phase_complete is True
    assert bundle.ready_for_phase_12 is True


def test_readiness_and_execution_statuses_are_exact() -> None:
    bundle = bullish_phase11_final_audit_handoff_decision().bundle_required

    assert bundle.readiness_mode == "DETERMINISTIC_FAKE_READ_ONLY"
    assert bundle.readiness_audit_status == "PASSED"
    assert bundle.readiness_audit_handoff_status == "READY_FOR_FINAL_HANDOFF"
    assert bundle.real_preflight_execution_status == "BLOCKED"
    assert bundle.production_activation_status == "BLOCKED"
    assert bundle.live_execution_status == "BLOCKED"


def test_market_and_risk_scope_is_exact() -> None:
    bundle = bullish_phase11_final_audit_handoff_decision().bundle_required

    assert bundle.symbol == "XAUUSD"
    assert bundle.timeframes == ("H4", "H1", "M15", "M5")
    assert bundle.closed_candles_only is True
    assert bundle.stage_risk_bps == (25, 25)
    assert bundle.aggregate_risk_budget_bps == 50
    assert bundle.max_gold_positions == 1
    assert bundle.risk_contract_valid is True


def test_oco_stop_loss_guards_and_flat_state_are_exact() -> None:
    bundle = bullish_phase11_final_audit_handoff_decision().bundle_required

    assert bundle.oco_required is True
    assert bundle.broker_stop_loss_required is True
    assert bundle.guards_required is True
    assert bundle.terminal_flat_state_required is True
    assert bundle.oco_and_stop_loss_contract_valid is True
    assert bundle.terminal_flat_state_valid is True


def test_capability_and_event_contract_is_exact() -> None:
    bundle = bullish_phase11_final_audit_handoff_decision().bundle_required

    assert bundle.verified_capability_count == 14
    assert bundle.blocked_capability_count == 3
    assert bundle.capability_inventory_valid is True
    assert bundle.event_count == 14
    assert bundle.event_trace_contiguous is True
    assert bundle.event_trace_order_valid is True


def test_snapshot_and_lifecycle_contract_is_exact() -> None:
    bundle = bullish_phase11_final_audit_handoff_decision().bundle_required

    assert bundle.terminal_snapshot_valid is True
    assert bundle.account_snapshot_valid is True
    assert bundle.symbol_snapshot_valid is True
    assert bundle.terminal_lifecycle_valid is True
    assert bundle.margin_state_valid is True
    assert bundle.exposure_state_valid is True


def test_all_lineage_flags_are_true() -> None:
    bundle = bullish_phase11_final_audit_handoff_decision().bundle_required

    assert bundle.phase10_lineage_preserved is True
    assert bundle.admission_lineage_preserved is True
    assert bundle.capability_lineage_preserved is True
    assert bundle.preflight_lineage_preserved is True
    assert bundle.readiness_audit_lineage_preserved is True


def test_future_authorization_gates_remain_mandatory() -> None:
    bundle = bullish_phase11_final_audit_handoff_decision().bundle_required

    assert bundle.explicit_human_authorization_required is True
    assert bundle.separate_real_preflight_gate_required is True
    assert bundle.separate_production_gate_required is True


def test_final_handoff_has_no_real_or_external_effects() -> None:
    bundle = bullish_phase11_final_audit_handoff_decision().bundle_required

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
    assert bundle.readiness_audit_passed is True


def test_final_handoff_id_is_deterministic() -> None:
    first = bullish_phase11_final_audit_handoff_decision().bundle_required
    second = bullish_phase11_final_audit_handoff_decision().bundle_required

    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id


def test_missing_readiness_audit_blocks_handoff() -> None:
    decision = create_phase11_final_audit_handoff(None)

    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("readiness_audit_decision_missing",)


def test_blocked_readiness_audit_blocks_handoff() -> None:
    decision = create_phase11_final_audit_handoff(FakeBlockedReadinessAuditDecision())

    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("readiness_audit_decision_blocked",)

    with pytest.raises(RuntimeError, match="handoff is blocked"):
        _ = decision.bundle_required


def test_factory_and_function_api_match() -> None:
    audit_decision = bullish_phase11_readiness_safety_audit_decision()

    factory_decision = StrategyPhase11FinalAuditHandoffFactory().create(audit_decision)
    function_decision = create_phase11_final_audit_handoff(audit_decision)

    assert (
        factory_decision.bundle_required.handoff_id == function_decision.bundle_required.handoff_id
    )


def test_final_handoff_does_not_mutate_readiness_audit() -> None:
    audit_decision = bullish_phase11_readiness_safety_audit_decision()
    report = audit_decision.report_required

    before = (
        report.audit_status,
        report.final_handoff_status,
        report.preflight_status,
        report.preflight_outcome,
        report.verified_capability_count,
        report.blocked_capability_count,
        report.event_count,
    )

    _ = create_phase11_final_audit_handoff(audit_decision).bundle_required

    after = (
        report.audit_status,
        report.final_handoff_status,
        report.preflight_status,
        report.preflight_outcome,
        report.verified_capability_count,
        report.blocked_capability_count,
        report.event_count,
    )

    assert after == before
