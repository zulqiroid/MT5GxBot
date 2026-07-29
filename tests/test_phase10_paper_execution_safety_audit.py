from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase10_paper_execution_safety_audit import (
    PHASE_10_PAPER_SAFETY_AUDIT_SCHEMA_VERSION,
    PHASE_10_PAPER_SAFETY_AUDIT_STATUS,
    PHASE_10_PAPER_SAFETY_HANDOFF_STATUS,
    PHASE_10_PAPER_SAFETY_LIVE_EXECUTION_STATUS,
    PHASE_10_PAPER_SAFETY_REQUIRED_GUARDS,
    StrategyPhase10PaperExecutionSafetyAuditor,
    audit_phase10_paper_execution_safety,
)
from tests.test_phase10_deterministic_paper_execution_engine import (
    bullish_phase10_deterministic_paper_execution_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedExecutionDecision:
    is_allowed: bool = False


def bullish_phase10_paper_execution_safety_audit_decision():
    return audit_phase10_paper_execution_safety(
        bullish_phase10_deterministic_paper_execution_decision()
    )


def test_static_paper_safety_contract_is_stable() -> None:
    assert PHASE_10_PAPER_SAFETY_AUDIT_SCHEMA_VERSION == "1.0"
    assert PHASE_10_PAPER_SAFETY_AUDIT_STATUS == "PASSED"
    assert PHASE_10_PAPER_SAFETY_HANDOFF_STATUS == "READY_FOR_FINAL_HANDOFF"
    assert PHASE_10_PAPER_SAFETY_LIVE_EXECUTION_STATUS == "BLOCKED"
    assert PHASE_10_PAPER_SAFETY_REQUIRED_GUARDS == (
        "daily_loss_limit",
        "spread_guard",
        "stale_data_guard",
        "duplicate_position_guard",
    )


def test_paper_safety_audit_is_created() -> None:
    decision = bullish_phase10_paper_execution_safety_audit_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None


def test_audit_preserves_execution_contract_and_admission_lineage() -> None:
    execution_decision = bullish_phase10_deterministic_paper_execution_decision()
    execution = execution_decision.execution_required
    contract = execution.contract
    admission_permit = contract.admission_permit

    report = audit_phase10_paper_execution_safety(execution_decision).report_required

    assert report.execution_decision is execution_decision
    assert report.execution is execution
    assert report.contract is contract
    assert report.admission_permit is admission_permit


def test_audit_and_handoff_statuses_are_exact() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.audit_status == "PASSED"
    assert report.final_handoff_status == "READY_FOR_FINAL_HANDOFF"
    assert report.live_execution_status == "BLOCKED"
    assert report.safety_audit_passed is True
    assert report.ready_for_final_handoff is True


def test_execution_summary_is_exact() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.execution_mode == "IN_MEMORY_PAPER"
    assert report.execution_status == "COMPLETED"
    assert report.execution_outcome == "TAKE_PROFIT"
    assert report.symbol == "XAUUSD"
    assert report.side == "LONG"


def test_risk_audit_is_exact() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.stage_risk_bps == (25, 25)
    assert report.aggregate_risk_budget_bps == 50
    assert report.maximum_reserved_risk_bps == 50
    assert report.aggregate_risk_never_exceeded is True
    assert report.stage_risk_sum_valid is True


def test_position_and_terminal_state_audit_is_exact() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.maximum_gold_position_count == 1
    assert report.terminal_gold_position_count == 0
    assert report.terminal_active_oco_order_count == 0
    assert report.terminal_reserved_risk_bps == 0
    assert report.one_gold_position_limit_preserved is True
    assert report.terminal_flat_state_valid is True


def test_oco_and_broker_stop_loss_audit_is_exact() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.position_group_id == "PAPER-XAUUSD-POSITION-001"
    assert report.oco_group_id == "PAPER-XAUUSD-OCO-001"
    assert report.broker_stop_loss_attached is True
    assert report.take_profit_filled is True
    assert report.stop_loss_filled is False
    assert report.stop_loss_canceled_by_oco is True
    assert report.oco_contract_valid is True


def test_all_required_paper_guards_pass() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.guard_names == PHASE_10_PAPER_SAFETY_REQUIRED_GUARDS
    assert report.guard_count == 4
    assert report.all_guards_passed is True


def test_paper_ledger_audit_is_exact() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.ledger_entry_count == 6
    assert report.ledger_sequence_indices == tuple(range(6))
    assert report.ledger_contiguous is True
    assert report.ledger_order_valid is True


def test_paper_event_trace_audit_is_exact() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.event_count == 11
    assert report.event_sequence_indices == tuple(range(11))
    assert report.event_trace_contiguous is True
    assert report.event_trace_order_valid is True


def test_paper_profit_metrics_are_exact() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.realized_profit_points == 2000
    assert report.reward_risk_milli == 2000
    assert report.profit_metrics_valid is True


def test_findings_are_complete_and_passed() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert len(report.findings) == 10
    assert tuple(finding.name for finding in report.findings) == (
        "aggregate_risk",
        "one_gold_position",
        "terminal_flat_state",
        "oco_and_broker_stop_loss",
        "kill_switches",
        "paper_ledger_integrity",
        "execution_trace_integrity",
        "paper_profit_metrics",
        "closed_candle_scope",
        "no_live_effects",
    )
    assert all(finding.passed is True for finding in report.findings)


def test_audit_confirms_no_live_or_external_effects() -> None:
    report = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert report.uses_closed_candles_only is True
    assert report.executes_paper_orders_in_memory is True
    assert report.evaluates_strategy is False
    assert report.initializes_mt5 is False
    assert report.sends_broker_request is False
    assert report.writes_external_state is False
    assert report.submits_live_order is False
    assert report.no_live_or_external_effects is True


def test_audit_id_is_deterministic() -> None:
    first = bullish_phase10_paper_execution_safety_audit_decision().report_required
    second = bullish_phase10_paper_execution_safety_audit_decision().report_required

    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id


def test_missing_execution_blocks_audit() -> None:
    decision = audit_phase10_paper_execution_safety(None)

    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("paper_execution_decision_missing",)


def test_blocked_execution_blocks_audit() -> None:
    decision = audit_phase10_paper_execution_safety(FakeBlockedExecutionDecision())

    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("paper_execution_decision_blocked",)

    with pytest.raises(RuntimeError, match="safety audit is blocked"):
        _ = decision.report_required


def test_factory_and_function_api_match() -> None:
    execution_decision = bullish_phase10_deterministic_paper_execution_decision()

    factory_decision = StrategyPhase10PaperExecutionSafetyAuditor().audit(execution_decision)
    function_decision = audit_phase10_paper_execution_safety(execution_decision)

    assert factory_decision.report_required.audit_id == function_decision.report_required.audit_id
