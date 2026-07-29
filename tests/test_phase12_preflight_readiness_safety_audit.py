from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase12_preflight_readiness_safety_audit import (
    PHASE_12_READINESS_AUDIT_HANDOFF_STATUS,
    PHASE_12_READINESS_AUDIT_SCHEMA_VERSION,
    PHASE_12_READINESS_AUDIT_SOURCE,
    PHASE_12_READINESS_AUDIT_STATUS,
    PHASE_12_READINESS_FINDING_NAMES,
    StrategyPhase12PreflightReadinessSafetyAuditor,
    audit_phase12_preflight_readiness_safety,
)
from tests.test_phase12_deterministic_fake_runtime_validation import (
    bullish_phase12_fake_validation_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedValidationDecision:
    is_allowed: bool = False


def bullish_phase12_readiness_audit_decision():
    return audit_phase12_preflight_readiness_safety(bullish_phase12_fake_validation_decision())


def test_static_readiness_audit_contract_is_stable() -> None:
    assert PHASE_12_READINESS_AUDIT_SCHEMA_VERSION == "1.0"
    assert PHASE_12_READINESS_AUDIT_STATUS == "PASSED"
    assert PHASE_12_READINESS_AUDIT_HANDOFF_STATUS == "READY_FOR_FINAL_HANDOFF"
    assert PHASE_12_READINESS_AUDIT_SOURCE == "DETERMINISTIC_FAKE_EVIDENCE_ONLY"


def test_readiness_audit_report_is_created() -> None:
    decision = bullish_phase12_readiness_audit_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None


def test_complete_lineage_is_preserved() -> None:
    validation_decision = bullish_phase12_fake_validation_decision()
    validation = validation_decision.report_required
    report = audit_phase12_preflight_readiness_safety(validation_decision).report_required

    assert report.validation_decision is validation_decision
    assert report.validation_report is validation
    assert report.runtime_contract_decision is validation.contract_decision
    assert report.runtime_contract is validation.runtime_contract
    assert report.admission_decision is validation.admission_decision
    assert report.admission_permit is validation.admission_permit
    assert report.phase11_handoff_bundle is validation.phase11_handoff_bundle


def test_audit_and_handoff_statuses_are_exact() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.audit_status == "PASSED"
    assert report.handoff_status == "READY_FOR_FINAL_HANDOFF"
    assert report.audit_source == "DETERMINISTIC_FAKE_EVIDENCE_ONLY"
    assert report.readiness_audit_passed is True
    assert report.ready_for_final_handoff is True


def test_terminal_account_broker_snapshots_are_valid() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.terminal_snapshot_valid is True
    assert report.account_snapshot_valid is True
    assert report.symbol_tick_snapshot_valid is True


def test_exposure_and_order_position_snapshots_are_valid() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.exposure_snapshot_valid is True
    assert report.order_position_snapshot_valid is True
    assert report.terminal_flat_state_valid is True


def test_capability_contract_audit_is_exact() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.verified_capability_count == 14
    assert report.blocked_capability_count == 3
    assert report.capability_contract_valid is True


def test_snapshot_schema_audit_is_exact() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.snapshot_schema_count == 5
    assert report.total_snapshot_field_count == 32
    assert report.snapshot_schema_coverage_valid is True
    assert report.snapshot_payloads_deterministic is True
    assert report.snapshot_payloads_read_only is True
    assert report.no_real_snapshot_data_used is True


def test_gold_risk_scope_is_exact() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)
    assert report.risk_contract_valid is True


def test_oco_broker_sl_guards_and_flat_state_are_exact() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.oco_required is True
    assert report.broker_stop_loss_required is True
    assert report.guards_required is True
    assert report.terminal_flat_state_required is True
    assert report.oco_broker_sl_guard_contract_valid is True
    assert report.terminal_flat_state_valid is True


def test_validation_event_evidence_is_exact() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.validation_event_count == 14
    assert report.validation_event_trace_contiguous is True
    assert report.validation_event_trace_order_valid is True


def test_all_lineage_flags_are_true() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.phase11_lineage_preserved is True
    assert report.admission_lineage_preserved is True
    assert report.runtime_contract_lineage_preserved is True
    assert report.validation_lineage_preserved is True


def test_future_gates_remain_mandatory() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.explicit_human_authorization_required is True
    assert report.separate_runtime_gate_required is True
    assert report.separate_production_gate_required is True


def test_readiness_findings_are_complete_and_passed() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert len(report.findings) == 14
    assert tuple(finding.name for finding in report.findings) == (PHASE_12_READINESS_FINDING_NAMES)
    assert all(finding.passed is True for finding in report.findings)


def test_all_real_and_external_effects_are_blocked() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
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


def test_all_runtime_statuses_remain_blocked() -> None:
    report = bullish_phase12_readiness_audit_decision().report_required
    assert report.real_preflight_execution_status == "BLOCKED"
    assert report.mt5_initialization_status == "BLOCKED"
    assert report.terminal_connection_status == "BLOCKED"
    assert report.broker_access_status == "BLOCKED"
    assert report.production_activation_status == "BLOCKED"
    assert report.live_execution_status == "BLOCKED"


def test_audit_id_is_deterministic() -> None:
    first = bullish_phase12_readiness_audit_decision().report_required
    second = bullish_phase12_readiness_audit_decision().report_required
    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id


def test_missing_validation_blocks_audit() -> None:
    decision = audit_phase12_preflight_readiness_safety(None)
    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("fake_validation_decision_missing",)


def test_blocked_validation_blocks_audit() -> None:
    decision = audit_phase12_preflight_readiness_safety(FakeBlockedValidationDecision())
    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("fake_validation_decision_blocked",)
    with pytest.raises(RuntimeError, match="audit is blocked"):
        _ = decision.report_required


def test_factory_and_function_api_match() -> None:
    validation_decision = bullish_phase12_fake_validation_decision()
    factory = (
        StrategyPhase12PreflightReadinessSafetyAuditor().audit(validation_decision).report_required
    )
    function = audit_phase12_preflight_readiness_safety(validation_decision).report_required
    assert factory.audit_id == function.audit_id
