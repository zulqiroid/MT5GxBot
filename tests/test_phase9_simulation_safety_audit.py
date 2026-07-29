from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase9_simulation_safety_audit import (
    PHASE_9_SIMULATION_SAFETY_AUDIT_LIVE_EXECUTION_BLOCKED,
    PHASE_9_SIMULATION_SAFETY_AUDIT_READY_FOR_FINAL_HANDOFF,
    PHASE_9_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION,
    PHASE_9_SIMULATION_SAFETY_AUDIT_STATUS_PASSED,
    PHASE_9_SIMULATION_SAFETY_REQUIRED_KILL_SWITCHES,
    StrategyPhase9SimulationSafetyAuditor,
    audit_phase9_deterministic_simulation_safety,
)
from tests.test_phase9_deterministic_in_memory_simulation_runner import (
    bullish_phase9_deterministic_simulation_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedSimulationDecision:
    is_allowed: bool = False


def bullish_phase9_simulation_safety_audit_decision():
    return audit_phase9_deterministic_simulation_safety(
        bullish_phase9_deterministic_simulation_decision()
    )


def test_static_safety_audit_contract_is_stable() -> None:
    assert PHASE_9_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION == "1.0"
    assert PHASE_9_SIMULATION_SAFETY_AUDIT_STATUS_PASSED == "PASSED"
    assert PHASE_9_SIMULATION_SAFETY_AUDIT_LIVE_EXECUTION_BLOCKED == "BLOCKED"
    assert PHASE_9_SIMULATION_SAFETY_AUDIT_READY_FOR_FINAL_HANDOFF == "READY_FOR_FINAL_HANDOFF"
    assert PHASE_9_SIMULATION_SAFETY_REQUIRED_KILL_SWITCHES == (
        "daily_loss_limit",
        "spread_guard",
        "stale_data_guard",
        "duplicate_position_guard",
    )


def test_simulation_safety_audit_is_created() -> None:
    decision = bullish_phase9_simulation_safety_audit_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None


def test_audit_preserves_simulation_lineage() -> None:
    simulation_decision = bullish_phase9_deterministic_simulation_decision()
    simulation_run = simulation_decision.run_required

    report = audit_phase9_deterministic_simulation_safety(simulation_decision).report_required

    assert report.simulation_decision is simulation_decision
    assert report.simulation_run is simulation_run


def test_run_summary_and_handoff_status_are_exact() -> None:
    report = bullish_phase9_simulation_safety_audit_decision().report_required

    assert report.run_status == "COMPLETED"
    assert report.run_outcome == "TAKE_PROFIT"
    assert report.symbol == "XAUUSD"
    assert report.side == "LONG"
    assert report.audit_status == "PASSED"
    assert report.final_handoff_status == "READY_FOR_FINAL_HANDOFF"
    assert report.live_execution_status == "BLOCKED"
    assert report.ready_for_final_handoff is True


def test_aggregate_and_staged_risk_audit_is_exact() -> None:
    report = bullish_phase9_simulation_safety_audit_decision().report_required

    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)
    assert report.maximum_reserved_risk_bps == 50
    assert report.aggregate_risk_never_exceeded is True
    assert report.stage_risk_sum_valid is True


def test_one_position_and_terminal_flat_state_audit_is_exact() -> None:
    report = bullish_phase9_simulation_safety_audit_decision().report_required

    assert report.maximum_gold_position_count == 1
    assert report.terminal_gold_position_count == 0
    assert report.one_gold_position_limit_preserved is True
    assert report.terminal_flat_state_valid is True


def test_oco_and_broker_stop_loss_audit_is_exact() -> None:
    report = bullish_phase9_simulation_safety_audit_decision().report_required

    assert report.oco_group_id == "SIM-XAUUSD-OCO-001"
    assert report.broker_stop_loss_attached is True
    assert report.take_profit_filled is True
    assert report.stop_loss_filled is False
    assert report.stop_loss_canceled_by_oco is True
    assert report.terminal_active_oco_order_count == 0
    assert report.oco_contract_valid is True


def test_all_required_kill_switches_are_audited() -> None:
    report = bullish_phase9_simulation_safety_audit_decision().report_required

    assert report.kill_switch_names == PHASE_9_SIMULATION_SAFETY_REQUIRED_KILL_SWITCHES
    assert report.kill_switch_count == 4
    assert report.all_kill_switches_passed is True


def test_trace_integrity_audit_is_exact() -> None:
    report = bullish_phase9_simulation_safety_audit_decision().report_required

    assert report.trace_sequence_indices == tuple(range(8))
    assert len(report.trace_event_types) == 8
    assert report.trace_contiguous is True
    assert report.trace_order_valid is True


def test_safety_findings_are_complete_and_passed() -> None:
    report = bullish_phase9_simulation_safety_audit_decision().report_required

    assert len(report.findings) == 8
    assert tuple(finding.name for finding in report.findings) == (
        "aggregate_risk",
        "one_gold_position",
        "terminal_flat_state",
        "oco_and_broker_stop_loss",
        "kill_switches",
        "trace_integrity",
        "closed_candle_scope",
        "no_live_effects",
    )
    assert all(finding.passed is True for finding in report.findings)
    assert report.safety_audit_passed is True


def test_audit_confirms_no_live_or_external_effects() -> None:
    report = bullish_phase9_simulation_safety_audit_decision().report_required

    assert report.uses_closed_candles_only is True
    assert report.executes_in_memory_simulation is True
    assert report.evaluates_strategy is False
    assert report.initializes_mt5 is False
    assert report.sends_broker_request is False
    assert report.writes_external_state is False
    assert report.submits_live_order is False
    assert report.no_live_or_external_effects is True


def test_audit_id_is_deterministic() -> None:
    first = bullish_phase9_simulation_safety_audit_decision().report_required
    second = bullish_phase9_simulation_safety_audit_decision().report_required

    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id


def test_missing_simulation_blocks_audit() -> None:
    decision = audit_phase9_deterministic_simulation_safety(None)

    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("simulation_decision_missing",)


def test_blocked_simulation_blocks_audit() -> None:
    decision = audit_phase9_deterministic_simulation_safety(FakeBlockedSimulationDecision())

    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("simulation_decision_blocked",)

    with pytest.raises(RuntimeError, match="audit is blocked"):
        _ = decision.report_required


def test_factory_and_function_api_match() -> None:
    simulation_decision = bullish_phase9_deterministic_simulation_decision()

    factory_decision = StrategyPhase9SimulationSafetyAuditor().audit(simulation_decision)
    function_decision = audit_phase9_deterministic_simulation_safety(simulation_decision)

    assert factory_decision.report_required.audit_id == function_decision.report_required.audit_id


def test_audit_does_not_mutate_simulation_run() -> None:
    simulation_decision = bullish_phase9_deterministic_simulation_decision()
    simulation_run = simulation_decision.run_required

    before = (
        simulation_run.status,
        simulation_run.outcome,
        simulation_run.aggregate_risk_budget_bps,
        simulation_run.max_gold_position_count_observed,
        simulation_run.terminal_gold_position_count,
        simulation_run.terminal_active_oco_order_count,
    )

    _ = audit_phase9_deterministic_simulation_safety(simulation_decision).report_required

    after = (
        simulation_run.status,
        simulation_run.outcome,
        simulation_run.aggregate_risk_budget_bps,
        simulation_run.max_gold_position_count_observed,
        simulation_run.terminal_gold_position_count,
        simulation_run.terminal_active_oco_order_count,
    )

    assert after == before
