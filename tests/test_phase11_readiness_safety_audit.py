from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase11_readiness_safety_audit import (
    PHASE_11_READINESS_AUDIT_HANDOFF_STATUS,
    PHASE_11_READINESS_AUDIT_LIVE_STATUS,
    PHASE_11_READINESS_AUDIT_PRODUCTION_STATUS,
    PHASE_11_READINESS_AUDIT_REAL_PREFLIGHT_STATUS,
    PHASE_11_READINESS_AUDIT_SCHEMA_VERSION,
    PHASE_11_READINESS_AUDIT_SOURCE,
    PHASE_11_READINESS_AUDIT_STATUS,
    StrategyPhase11ReadinessSafetyAuditor,
    audit_phase11_readiness_safety,
)
from tests.test_phase11_deterministic_read_only_preflight import (
    bullish_phase11_read_only_preflight_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedPreflightDecision:
    is_allowed: bool = False


def bullish_phase11_readiness_safety_audit_decision():
    return audit_phase11_readiness_safety(bullish_phase11_read_only_preflight_decision())


def test_static_readiness_audit_contract_is_stable() -> None:
    assert PHASE_11_READINESS_AUDIT_SCHEMA_VERSION == "1.0"
    assert PHASE_11_READINESS_AUDIT_STATUS == "PASSED"
    assert PHASE_11_READINESS_AUDIT_HANDOFF_STATUS == "READY_FOR_FINAL_HANDOFF"
    assert PHASE_11_READINESS_AUDIT_SOURCE == "DETERMINISTIC_FAKE_ONLY"
    assert PHASE_11_READINESS_AUDIT_REAL_PREFLIGHT_STATUS == "BLOCKED"
    assert PHASE_11_READINESS_AUDIT_PRODUCTION_STATUS == "BLOCKED"
    assert PHASE_11_READINESS_AUDIT_LIVE_STATUS == "BLOCKED"


def test_readiness_safety_audit_is_created() -> None:
    decision = bullish_phase11_readiness_safety_audit_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None


def test_audit_preserves_complete_lineage() -> None:
    preflight_decision = bullish_phase11_read_only_preflight_decision()
    preflight = preflight_decision.preflight_required
    capability_decision = preflight.capability_decision
    contract = preflight.capability_contract
    admission_decision = preflight.admission_decision
    admission_permit = preflight.admission_permit
    phase10_bundle = preflight.phase10_handoff_bundle

    report = audit_phase11_readiness_safety(preflight_decision).report_required

    assert report.preflight_decision is preflight_decision
    assert report.preflight is preflight
    assert report.capability_decision is capability_decision
    assert report.capability_contract is contract
    assert report.admission_decision is admission_decision
    assert report.admission_permit is admission_permit
    assert report.phase10_handoff_bundle is phase10_bundle


def test_audit_and_handoff_statuses_are_exact() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert report.audit_status == "PASSED"
    assert report.final_handoff_status == "READY_FOR_FINAL_HANDOFF"
    assert report.source == "DETERMINISTIC_FAKE_ONLY"
    assert report.readiness_audit_passed is True
    assert report.ready_for_final_handoff is True


def test_preflight_summary_is_exact() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert report.preflight_mode == "DETERMINISTIC_FAKE_READ_ONLY"
    assert report.preflight_status == "COMPLETED"
    assert report.preflight_outcome == "READY_FOR_READINESS_AUDIT"
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True


def test_risk_position_oco_and_guard_audit_is_exact() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert report.stage_risk_bps == (25, 25)
    assert report.aggregate_risk_budget_bps == 50
    assert report.max_gold_positions == 1
    assert report.risk_contract_valid is True
    assert report.oco_required is True
    assert report.broker_stop_loss_required is True
    assert report.guards_required is True
    assert report.terminal_flat_state_required is True
    assert report.oco_and_stop_loss_contract_valid is True


def test_terminal_account_and_symbol_snapshot_audit_is_exact() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert report.terminal_snapshot_valid is True
    assert report.account_snapshot_valid is True
    assert report.symbol_snapshot_valid is True
    assert report.terminal_lifecycle_valid is True
    assert report.margin_state_valid is True
    assert report.exposure_state_valid is True
    assert report.terminal_flat_state_valid is True


def test_capability_inventory_audit_is_exact() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert report.verified_capability_count == 14
    assert report.blocked_capability_count == 3
    assert report.capability_inventory_valid is True
    assert len(report.verified_capability_ids) == 14
    assert len(report.blocked_capability_ids) == 3


def test_preflight_event_trace_audit_is_exact() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert report.event_count == 14
    assert report.event_sequence_indices == tuple(range(14))
    assert report.event_trace_contiguous is True
    assert report.event_trace_order_valid is True


def test_all_lineage_flags_are_true() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert report.phase10_lineage_preserved is True
    assert report.admission_lineage_preserved is True
    assert report.capability_lineage_preserved is True
    assert report.preflight_lineage_preserved is True


def test_future_authorization_gates_remain_mandatory() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert report.explicit_human_authorization_required is True
    assert report.separate_preflight_gate_required is True
    assert report.separate_production_gate_required is True


def test_findings_are_complete_and_passed() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert len(report.findings) == 12
    assert tuple(finding.name for finding in report.findings) == (
        "phase_lineage",
        "admission_and_capability_lineage",
        "risk_and_position_limits",
        "oco_broker_sl_and_guards",
        "fake_terminal_snapshot",
        "fake_account_snapshot",
        "fake_symbol_tick_snapshot",
        "margin_and_exposure_state",
        "capability_inventory",
        "preflight_event_trace",
        "future_authorization_gates",
        "no_real_or_external_effects",
    )
    assert all(finding.passed is True for finding in report.findings)


def test_audit_confirms_no_real_or_external_effects() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

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


def test_all_execution_statuses_remain_blocked() -> None:
    report = bullish_phase11_readiness_safety_audit_decision().report_required

    assert report.real_preflight_execution_status == "BLOCKED"
    assert report.production_activation_status == "BLOCKED"
    assert report.live_execution_status == "BLOCKED"


def test_audit_id_is_deterministic() -> None:
    first = bullish_phase11_readiness_safety_audit_decision().report_required
    second = bullish_phase11_readiness_safety_audit_decision().report_required

    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id


def test_missing_preflight_blocks_audit() -> None:
    decision = audit_phase11_readiness_safety(None)

    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("read_only_preflight_decision_missing",)


def test_blocked_preflight_blocks_audit() -> None:
    decision = audit_phase11_readiness_safety(FakeBlockedPreflightDecision())

    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("read_only_preflight_decision_blocked",)

    with pytest.raises(RuntimeError, match="audit is blocked"):
        _ = decision.report_required


def test_factory_and_function_api_match() -> None:
    preflight_decision = bullish_phase11_read_only_preflight_decision()

    factory_decision = StrategyPhase11ReadinessSafetyAuditor().audit(preflight_decision)
    function_decision = audit_phase11_readiness_safety(preflight_decision)

    assert factory_decision.report_required.audit_id == function_decision.report_required.audit_id
