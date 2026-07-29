from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase9_simulation_admission_gate import (
    PHASE_9_ALLOWED_SYMBOL,
    PHASE_9_ALLOWED_TIMEFRAMES,
    PHASE_9_LIVE_EXECUTION_BLOCKED,
    PHASE_9_SIMULATION_ADMISSION_GRANTED,
    PHASE_9_SIMULATION_ADMISSION_MODE,
    PHASE_9_SIMULATION_ADMISSION_SCHEMA_VERSION,
    StrategyPhase9SimulationAdmissionGate,
    evaluate_phase9_simulation_admission,
)
from tests.test_phase8_final_audit_handoff import (
    bullish_phase8_final_handoff_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedPhase8HandoffDecision:
    is_allowed: bool = False


def bullish_phase9_simulation_admission_decision():
    return evaluate_phase9_simulation_admission(bullish_phase8_final_handoff_decision())


def test_schema_and_static_contract_are_stable() -> None:
    assert PHASE_9_SIMULATION_ADMISSION_SCHEMA_VERSION == "1.0"
    assert PHASE_9_SIMULATION_ADMISSION_MODE == "SIMULATION_ONLY"
    assert PHASE_9_SIMULATION_ADMISSION_GRANTED == "ADMITTED"
    assert PHASE_9_LIVE_EXECUTION_BLOCKED == "BLOCKED"
    assert PHASE_9_ALLOWED_SYMBOL == "XAUUSD"
    assert PHASE_9_ALLOWED_TIMEFRAMES == ("H4", "H1", "M15", "M5")


def test_phase9_simulation_admission_is_created() -> None:
    decision = bullish_phase9_simulation_admission_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.permit is not None


def test_admission_preserves_phase8_lineage() -> None:
    handoff_decision = bullish_phase8_final_handoff_decision()
    handoff_bundle = handoff_decision.bundle_required

    permit = evaluate_phase9_simulation_admission(handoff_decision).permit_required

    assert permit.phase8_handoff_decision is handoff_decision
    assert permit.phase8_handoff_bundle is handoff_bundle


def test_phase_transition_contract_is_exact() -> None:
    permit = bullish_phase9_simulation_admission_decision().permit_required

    assert permit.source_phase_number == 8
    assert permit.target_phase_number == 9
    assert permit.source_phase_status == "PHASE_8_COMPLETE"
    assert permit.source_handoff_status == "READY_FOR_PHASE_9"
    assert permit.phase9_foundation_ready is True


def test_phase8_terminal_source_contract_is_exact() -> None:
    permit = bullish_phase9_simulation_admission_decision().permit_required

    assert permit.source_terminal_audit_status == "PASSED"
    assert permit.source_terminal_reentry_status == "BLOCKED"
    assert permit.source_total_event_count == 800
    assert permit.source_final_consumed_count == 800
    assert permit.source_final_remaining_count == 0
    assert permit.source_final_last_sequence_index == 799
    assert permit.source_next_event_sequence_index is None


def test_simulation_only_admission_contract_is_exact() -> None:
    permit = bullish_phase9_simulation_admission_decision().permit_required

    assert permit.admission_mode == "SIMULATION_ONLY"
    assert permit.admission_status == "ADMITTED"
    assert permit.live_execution_status == "BLOCKED"
    assert permit.permits_simulation_planning is True
    assert permit.permits_simulation_execution is False
    assert permit.permits_strategy_evaluation is False


def test_gold_closed_candle_scope_is_exact() -> None:
    permit = bullish_phase9_simulation_admission_decision().permit_required

    assert permit.allowed_symbol == "XAUUSD"
    assert permit.allowed_timeframes == ("H4", "H1", "M15", "M5")
    assert permit.closed_candles_only is True


def test_risk_and_execution_invariants_are_preserved() -> None:
    permit = bullish_phase9_simulation_admission_decision().permit_required

    assert permit.one_gold_position_max is True
    assert permit.staged_aggregate_risk_required is True
    assert permit.oco_required is True
    assert permit.broker_stop_loss_required is True
    assert permit.martingale_prohibited is True
    assert permit.grid_prohibited is True
    assert permit.no_stop_loss_prohibited is True
    assert permit.kill_switches_required is True


def test_admission_performs_no_execution_or_external_effects() -> None:
    permit = bullish_phase9_simulation_admission_decision().permit_required

    assert permit.permits_simulation_execution is False
    assert permit.permits_strategy_evaluation is False
    assert permit.permits_mt5_initialization is False
    assert permit.permits_broker_requests is False
    assert permit.permits_external_writes is False
    assert permit.permits_order_submission is False


def test_admission_id_is_deterministic() -> None:
    first = bullish_phase9_simulation_admission_decision().permit_required
    second = bullish_phase9_simulation_admission_decision().permit_required

    assert first.permit_digest == second.permit_digest
    assert first.permit_id == second.permit_id


def test_missing_phase8_handoff_blocks_admission() -> None:
    decision = evaluate_phase9_simulation_admission(None)

    assert decision.is_allowed is False
    assert decision.permit is None
    assert decision.blockers == ("phase8_handoff_decision_missing",)


def test_blocked_phase8_handoff_blocks_admission() -> None:
    decision = evaluate_phase9_simulation_admission(FakeBlockedPhase8HandoffDecision())

    assert decision.is_allowed is False
    assert decision.permit is None
    assert decision.blockers == ("phase8_handoff_decision_blocked",)

    with pytest.raises(RuntimeError, match="admission is blocked"):
        _ = decision.permit_required


def test_factory_and_function_api_match() -> None:
    handoff_decision = bullish_phase8_final_handoff_decision()

    factory_decision = StrategyPhase9SimulationAdmissionGate().evaluate(handoff_decision)
    function_decision = evaluate_phase9_simulation_admission(handoff_decision)

    assert factory_decision.permit_required.permit_id == function_decision.permit_required.permit_id


def test_admission_does_not_mutate_phase8_handoff() -> None:
    handoff_decision = bullish_phase8_final_handoff_decision()
    bundle = handoff_decision.bundle_required

    before = (
        bundle.phase_number,
        bundle.total_event_count,
        bundle.final_consumed_count,
        bundle.final_remaining_count,
        bundle.phase_status,
        bundle.handoff_status,
    )

    _ = evaluate_phase9_simulation_admission(handoff_decision).permit_required

    after = (
        bundle.phase_number,
        bundle.total_event_count,
        bundle.final_consumed_count,
        bundle.final_remaining_count,
        bundle.phase_status,
        bundle.handoff_status,
    )

    assert after == before
