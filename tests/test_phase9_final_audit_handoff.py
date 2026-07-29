from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase9_final_audit_handoff import (
    PHASE_9_FINAL_HANDOFF_LIVE_EXECUTION_STATUS,
    PHASE_9_FINAL_HANDOFF_PHASE_STATUS,
    PHASE_9_FINAL_HANDOFF_SCHEMA_VERSION,
    PHASE_9_FINAL_HANDOFF_SIMULATION_MODE,
    PHASE_9_FINAL_HANDOFF_STATUS,
    StrategyPhase9FinalAuditHandoffFactory,
    create_phase9_final_audit_handoff,
)
from tests.test_phase9_simulation_safety_audit import (
    bullish_phase9_simulation_safety_audit_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedSafetyAuditDecision:
    is_allowed: bool = False


def bullish_phase9_final_audit_handoff_decision():
    return create_phase9_final_audit_handoff(bullish_phase9_simulation_safety_audit_decision())


def test_static_final_handoff_contract_is_stable() -> None:
    assert PHASE_9_FINAL_HANDOFF_SCHEMA_VERSION == "1.0"
    assert PHASE_9_FINAL_HANDOFF_PHASE_STATUS == "PHASE_9_COMPLETE"
    assert PHASE_9_FINAL_HANDOFF_STATUS == "READY_FOR_PHASE_10"
    assert PHASE_9_FINAL_HANDOFF_SIMULATION_MODE == "IN_MEMORY_ONLY"
    assert PHASE_9_FINAL_HANDOFF_LIVE_EXECUTION_STATUS == "BLOCKED"


def test_phase9_final_handoff_is_created() -> None:
    decision = bullish_phase9_final_audit_handoff_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.bundle is not None


def test_full_lineage_is_preserved() -> None:
    safety_decision = bullish_phase9_simulation_safety_audit_decision()
    report = safety_decision.report_required
    simulation_run = report.simulation_run
    scenario_contract = simulation_run.scenario_contract
    admission_permit = scenario_contract.admission_permit
    phase8_handoff_bundle = admission_permit.phase8_handoff_bundle

    bundle = create_phase9_final_audit_handoff(safety_decision).bundle_required

    assert bundle.safety_audit_decision is safety_decision
    assert bundle.safety_audit_report is report
    assert bundle.simulation_run is simulation_run
    assert bundle.scenario_contract is scenario_contract
    assert bundle.admission_permit is admission_permit
    assert bundle.phase8_handoff_bundle is phase8_handoff_bundle


def test_phase_transition_and_status_contract_is_exact() -> None:
    bundle = bullish_phase9_final_audit_handoff_decision().bundle_required

    assert bundle.phase_number == 9
    assert bundle.source_phase_number == 8
    assert bundle.target_phase_number == 10
    assert bundle.phase_status == "PHASE_9_COMPLETE"
    assert bundle.handoff_status == "READY_FOR_PHASE_10"
    assert bundle.phase_complete is True
    assert bundle.ready_for_phase_10 is True


def test_simulation_and_safety_status_contract_is_exact() -> None:
    bundle = bullish_phase9_final_audit_handoff_decision().bundle_required

    assert bundle.simulation_mode == "IN_MEMORY_ONLY"
    assert bundle.live_execution_status == "BLOCKED"
    assert bundle.simulation_status == "COMPLETED"
    assert bundle.simulation_outcome == "TAKE_PROFIT"
    assert bundle.safety_audit_status == "PASSED"
    assert bundle.safety_handoff_status == "READY_FOR_FINAL_HANDOFF"


def test_market_scope_contract_is_exact() -> None:
    bundle = bullish_phase9_final_audit_handoff_decision().bundle_required

    assert bundle.symbol == "XAUUSD"
    assert bundle.side == "LONG"
    assert bundle.timeframes == ("H4", "H1", "M15", "M5")
    assert bundle.closed_candles_only is True


def test_risk_and_position_contract_is_exact() -> None:
    bundle = bullish_phase9_final_audit_handoff_decision().bundle_required

    assert bundle.aggregate_risk_budget_bps == 50
    assert bundle.stage_risk_bps == (25, 25)
    assert bundle.maximum_reserved_risk_bps == 50
    assert bundle.maximum_gold_position_count == 1
    assert bundle.terminal_gold_position_count == 0
    assert bundle.terminal_active_oco_order_count == 0
    assert bundle.risk_contract_valid is True
    assert bundle.position_contract_valid is True
    assert bundle.terminal_state_valid is True


def test_oco_and_kill_switch_contract_is_exact() -> None:
    bundle = bullish_phase9_final_audit_handoff_decision().bundle_required

    assert bundle.oco_group_id == "SIM-XAUUSD-OCO-001"
    assert bundle.broker_stop_loss_attached is True
    assert bundle.take_profit_filled is True
    assert bundle.stop_loss_filled is False
    assert bundle.stop_loss_canceled_by_oco is True
    assert bundle.oco_contract_valid is True
    assert bundle.kill_switch_count == 4
    assert bundle.all_kill_switches_passed is True
    assert bundle.kill_switch_contract_valid is True


def test_trace_and_lineage_audits_are_exact() -> None:
    bundle = bullish_phase9_final_audit_handoff_decision().bundle_required

    assert bundle.trace_event_count == 8
    assert bundle.trace_contiguous is True
    assert bundle.trace_order_valid is True
    assert bundle.admission_lineage_preserved is True
    assert bundle.scenario_lineage_preserved is True
    assert bundle.simulation_lineage_preserved is True
    assert bundle.safety_audit_lineage_preserved is True


def test_final_handoff_has_no_live_or_external_effects() -> None:
    bundle = bullish_phase9_final_audit_handoff_decision().bundle_required

    assert bundle.executes_in_memory_simulation is True
    assert bundle.evaluates_strategy is False
    assert bundle.initializes_mt5 is False
    assert bundle.sends_broker_request is False
    assert bundle.writes_external_state is False
    assert bundle.submits_live_order is False
    assert bundle.no_live_or_external_effects is True


def test_final_handoff_id_is_deterministic() -> None:
    first = bullish_phase9_final_audit_handoff_decision().bundle_required
    second = bullish_phase9_final_audit_handoff_decision().bundle_required

    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id


def test_missing_safety_audit_blocks_handoff() -> None:
    decision = create_phase9_final_audit_handoff(None)

    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("safety_audit_decision_missing",)


def test_blocked_safety_audit_blocks_handoff() -> None:
    decision = create_phase9_final_audit_handoff(FakeBlockedSafetyAuditDecision())

    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("safety_audit_decision_blocked",)

    with pytest.raises(RuntimeError, match="handoff is blocked"):
        _ = decision.bundle_required


def test_factory_and_function_api_match() -> None:
    safety_decision = bullish_phase9_simulation_safety_audit_decision()

    factory_decision = StrategyPhase9FinalAuditHandoffFactory().create(safety_decision)
    function_decision = create_phase9_final_audit_handoff(safety_decision)

    assert (
        factory_decision.bundle_required.handoff_id == function_decision.bundle_required.handoff_id
    )


def test_final_handoff_does_not_mutate_safety_audit() -> None:
    safety_decision = bullish_phase9_simulation_safety_audit_decision()
    report = safety_decision.report_required

    before = (
        report.audit_status,
        report.final_handoff_status,
        report.run_status,
        report.run_outcome,
        report.maximum_reserved_risk_bps,
        report.maximum_gold_position_count,
        report.terminal_gold_position_count,
    )

    _ = create_phase9_final_audit_handoff(safety_decision).bundle_required

    after = (
        report.audit_status,
        report.final_handoff_status,
        report.run_status,
        report.run_outcome,
        report.maximum_reserved_risk_bps,
        report.maximum_gold_position_count,
        report.terminal_gold_position_count,
    )

    assert after == before
