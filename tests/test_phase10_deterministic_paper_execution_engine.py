from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase10_deterministic_paper_execution_engine import (
    PHASE_10_PAPER_EXECUTION_EVENT_TYPES,
    PHASE_10_PAPER_EXECUTION_MODE,
    PHASE_10_PAPER_EXECUTION_OUTCOME,
    PHASE_10_PAPER_EXECUTION_SCHEMA_VERSION,
    PHASE_10_PAPER_EXECUTION_STATUS,
    PHASE_10_PAPER_LEDGER_ENTRY_TYPES,
    StrategyPhase10DeterministicPaperExecutionEngine,
    execute_phase10_deterministic_paper_contract,
)
from tests.test_phase10_paper_scenario_order_intent_contract import (
    bullish_phase10_paper_scenario_order_intent_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedContractDecision:
    is_allowed: bool = False


def bullish_phase10_deterministic_paper_execution_decision():
    return execute_phase10_deterministic_paper_contract(
        bullish_phase10_paper_scenario_order_intent_decision()
    )


def test_static_paper_execution_contract_is_stable() -> None:
    assert PHASE_10_PAPER_EXECUTION_SCHEMA_VERSION == "1.0"
    assert PHASE_10_PAPER_EXECUTION_MODE == "IN_MEMORY_PAPER"
    assert PHASE_10_PAPER_EXECUTION_STATUS == "COMPLETED"
    assert PHASE_10_PAPER_EXECUTION_OUTCOME == "TAKE_PROFIT"
    assert len(PHASE_10_PAPER_EXECUTION_EVENT_TYPES) == 11
    assert len(PHASE_10_PAPER_LEDGER_ENTRY_TYPES) == 6


def test_deterministic_paper_execution_is_created() -> None:
    decision = bullish_phase10_deterministic_paper_execution_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.execution is not None


def test_execution_preserves_contract_lineage() -> None:
    contract_decision = bullish_phase10_paper_scenario_order_intent_decision()
    contract = contract_decision.contract_required

    execution = execute_phase10_deterministic_paper_contract(contract_decision).execution_required

    assert execution.contract_decision is contract_decision
    assert execution.contract is contract


def test_execution_status_and_market_scope_are_exact() -> None:
    execution = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert execution.execution_mode == "IN_MEMORY_PAPER"
    assert execution.status == "COMPLETED"
    assert execution.outcome == "TAKE_PROFIT"
    assert execution.symbol == "XAUUSD"
    assert execution.side == "LONG"
    assert execution.uses_closed_candles_only is True


def test_price_and_reward_risk_metrics_are_exact() -> None:
    execution = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert execution.entry_price_points == 241000
    assert execution.stop_loss_price_points == 240000
    assert execution.take_profit_price_points == 243000
    assert execution.final_price_points == 243000
    assert execution.risk_distance_points == 1000
    assert execution.reward_distance_points == 2000
    assert execution.realized_profit_points == 2000
    assert execution.reward_risk_milli == 2000


def test_intent_lineage_and_oco_contract_are_exact() -> None:
    execution = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert execution.position_group_id == "PAPER-XAUUSD-POSITION-001"
    assert execution.oco_group_id == "PAPER-XAUUSD-OCO-001"
    assert execution.entry_intent_id == "PAPER-ENTRY-001"
    assert execution.stop_loss_intent_id == "PAPER-SL-001"
    assert execution.take_profit_intent_id == "PAPER-TP-001"
    assert execution.broker_stop_loss_attached is True
    assert execution.take_profit_filled is True
    assert execution.stop_loss_filled is False
    assert execution.stop_loss_canceled_by_oco is True


def test_staged_risk_and_maximum_exposure_are_exact() -> None:
    execution = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert execution.stage_risk_bps == (25, 25)
    assert execution.aggregate_risk_budget_bps == 50
    assert execution.maximum_reserved_risk_bps == 50
    assert execution.maximum_gold_position_count == 1


def test_terminal_state_is_flat_and_clear() -> None:
    execution = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert execution.terminal_gold_position_count == 0
    assert execution.terminal_active_oco_order_count == 0
    assert execution.terminal_reserved_risk_bps == 0


def test_all_paper_guards_pass() -> None:
    execution = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert execution.all_guards_passed is True
    assert tuple(result.name for result in execution.guard_results) == (
        "daily_loss_limit",
        "spread_guard",
        "stale_data_guard",
        "duplicate_position_guard",
    )
    assert all(result.passed is True for result in execution.guard_results)


def test_paper_ledger_is_exact_and_contiguous() -> None:
    execution = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert tuple(entry.sequence_index for entry in execution.ledger_entries) == tuple(range(6))
    assert (
        tuple(entry.entry_type for entry in execution.ledger_entries)
        == PHASE_10_PAPER_LEDGER_ENTRY_TYPES
    )
    assert execution.ledger_entries[-1].realized_profit_points == 2000
    assert execution.ledger_entries[-1].open_gold_position_count == 0


def test_paper_event_trace_is_exact_and_contiguous() -> None:
    execution = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert tuple(event.sequence_index for event in execution.events) == tuple(range(11))
    assert (
        tuple(event.event_type for event in execution.events)
        == PHASE_10_PAPER_EXECUTION_EVENT_TYPES
    )
    assert execution.events[-1].open_gold_position_count == 0
    assert execution.events[-1].active_oco_order_count == 0
    assert execution.events[-1].reserved_risk_bps == 0


def test_paper_execution_has_no_live_or_external_effects() -> None:
    execution = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert execution.executes_paper_orders_in_memory is True
    assert execution.evaluates_strategy is False
    assert execution.initializes_mt5 is False
    assert execution.sends_broker_request is False
    assert execution.writes_external_state is False
    assert execution.submits_live_order is False


def test_execution_id_is_deterministic() -> None:
    first = bullish_phase10_deterministic_paper_execution_decision().execution_required
    second = bullish_phase10_deterministic_paper_execution_decision().execution_required

    assert first.execution_digest == second.execution_digest
    assert first.execution_id == second.execution_id


def test_missing_contract_blocks_execution() -> None:
    decision = execute_phase10_deterministic_paper_contract(None)

    assert decision.is_allowed is False
    assert decision.execution is None
    assert decision.blockers == ("paper_contract_decision_missing",)


def test_blocked_contract_blocks_execution() -> None:
    decision = execute_phase10_deterministic_paper_contract(FakeBlockedContractDecision())

    assert decision.is_allowed is False
    assert decision.execution is None
    assert decision.blockers == ("paper_contract_decision_blocked",)

    with pytest.raises(RuntimeError, match="execution is blocked"):
        _ = decision.execution_required


def test_factory_and_function_api_match() -> None:
    contract_decision = bullish_phase10_paper_scenario_order_intent_decision()

    factory_decision = StrategyPhase10DeterministicPaperExecutionEngine().execute(contract_decision)
    function_decision = execute_phase10_deterministic_paper_contract(contract_decision)

    assert (
        factory_decision.execution_required.execution_id
        == function_decision.execution_required.execution_id
    )
