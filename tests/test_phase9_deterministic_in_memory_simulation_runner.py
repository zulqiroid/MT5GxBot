from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase9_deterministic_in_memory_simulation_runner import (
    PHASE_9_SIMULATION_RUN_EVENT_TYPES,
    PHASE_9_SIMULATION_RUN_OUTCOME_TAKE_PROFIT,
    PHASE_9_SIMULATION_RUN_STATUS_COMPLETED,
    PHASE_9_SIMULATION_RUNNER_SCHEMA_VERSION,
    StrategyPhase9DeterministicInMemorySimulationRunner,
    run_phase9_deterministic_in_memory_simulation,
)
from tests.test_phase9_simulation_scenario_contract import (
    bullish_phase9_simulation_scenario_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedScenarioDecision:
    is_allowed: bool = False


def bullish_phase9_deterministic_simulation_decision():
    return run_phase9_deterministic_in_memory_simulation(
        bullish_phase9_simulation_scenario_decision()
    )


def test_runner_static_contract_is_stable() -> None:
    assert PHASE_9_SIMULATION_RUNNER_SCHEMA_VERSION == "1.0"
    assert PHASE_9_SIMULATION_RUN_STATUS_COMPLETED == "COMPLETED"
    assert PHASE_9_SIMULATION_RUN_OUTCOME_TAKE_PROFIT == "TAKE_PROFIT"
    assert len(PHASE_9_SIMULATION_RUN_EVENT_TYPES) == 8


def test_deterministic_simulation_run_is_created() -> None:
    decision = bullish_phase9_deterministic_simulation_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.run is not None


def test_run_preserves_scenario_lineage() -> None:
    scenario_decision = bullish_phase9_simulation_scenario_decision()
    scenario_contract = scenario_decision.contract_required

    simulation_run = run_phase9_deterministic_in_memory_simulation(scenario_decision).run_required

    assert simulation_run.scenario_decision is scenario_decision
    assert simulation_run.scenario_contract is scenario_contract


def test_terminal_run_contract_is_exact() -> None:
    simulation_run = bullish_phase9_deterministic_simulation_decision().run_required

    assert simulation_run.status == "COMPLETED"
    assert simulation_run.outcome == "TAKE_PROFIT"
    assert simulation_run.symbol == "XAUUSD"
    assert simulation_run.side == "LONG"
    assert simulation_run.entry_price_points == 240900
    assert simulation_run.stop_loss_price_points == 239900
    assert simulation_run.take_profit_price_points == 242900
    assert simulation_run.final_price_points == 242900
    assert simulation_run.price_scale == 100


def test_risk_and_reward_metrics_are_exact() -> None:
    simulation_run = bullish_phase9_deterministic_simulation_decision().run_required

    assert simulation_run.aggregate_risk_budget_bps == 50
    assert simulation_run.stage_risk_bps == (25, 25)
    assert simulation_run.risk_distance_points == 1000
    assert simulation_run.reward_distance_points == 2000
    assert simulation_run.realized_profit_points == 2000
    assert simulation_run.reward_risk_milli == 2000


def test_one_position_maximum_and_terminal_flat_state_are_exact() -> None:
    simulation_run = bullish_phase9_deterministic_simulation_decision().run_required

    assert simulation_run.max_gold_position_count_observed == 1
    assert simulation_run.terminal_gold_position_count == 0
    assert simulation_run.terminal_active_oco_order_count == 0
    assert max(event.open_gold_position_count for event in simulation_run.trace_events) == 1


def test_oco_and_broker_stop_loss_outcome_is_exact() -> None:
    simulation_run = bullish_phase9_deterministic_simulation_decision().run_required

    assert simulation_run.oco_group_id == "SIM-XAUUSD-OCO-001"
    assert simulation_run.broker_stop_loss_attached is True
    assert simulation_run.take_profit_filled is True
    assert simulation_run.stop_loss_filled is False
    assert simulation_run.stop_loss_canceled_by_oco is True


def test_all_kill_switches_pass() -> None:
    simulation_run = bullish_phase9_deterministic_simulation_decision().run_required

    assert simulation_run.kill_switches_passed is True
    assert tuple(result.name for result in simulation_run.kill_switch_results) == (
        "daily_loss_limit",
        "spread_guard",
        "stale_data_guard",
        "duplicate_position_guard",
    )
    assert all(result.passed is True for result in simulation_run.kill_switch_results)


def test_trace_is_exact_contiguous_and_deterministic() -> None:
    simulation_run = bullish_phase9_deterministic_simulation_decision().run_required

    assert tuple(event.sequence_index for event in simulation_run.trace_events) == tuple(range(8))
    assert (
        tuple(event.event_type for event in simulation_run.trace_events)
        == PHASE_9_SIMULATION_RUN_EVENT_TYPES
    )
    assert simulation_run.trace_events[-1].price_points == 242900
    assert simulation_run.trace_events[-1].open_gold_position_count == 0
    assert simulation_run.trace_events[-1].active_oco_order_count == 0


def test_in_memory_run_has_no_live_or_external_effects() -> None:
    simulation_run = bullish_phase9_deterministic_simulation_decision().run_required

    assert simulation_run.uses_closed_candles_only is True
    assert simulation_run.executes_in_memory_simulation is True
    assert simulation_run.evaluates_strategy is False
    assert simulation_run.initializes_mt5 is False
    assert simulation_run.sends_broker_request is False
    assert simulation_run.writes_external_state is False
    assert simulation_run.submits_live_order is False


def test_run_id_is_deterministic() -> None:
    first = bullish_phase9_deterministic_simulation_decision().run_required
    second = bullish_phase9_deterministic_simulation_decision().run_required

    assert first.run_digest == second.run_digest
    assert first.run_id == second.run_id


def test_missing_scenario_blocks_runner() -> None:
    decision = run_phase9_deterministic_in_memory_simulation(None)

    assert decision.is_allowed is False
    assert decision.run is None
    assert decision.blockers == ("simulation_scenario_decision_missing",)


def test_blocked_scenario_blocks_runner() -> None:
    decision = run_phase9_deterministic_in_memory_simulation(FakeBlockedScenarioDecision())

    assert decision.is_allowed is False
    assert decision.run is None
    assert decision.blockers == ("simulation_scenario_decision_blocked",)

    with pytest.raises(RuntimeError, match="simulation is blocked"):
        _ = decision.run_required


def test_factory_and_function_api_match() -> None:
    scenario_decision = bullish_phase9_simulation_scenario_decision()

    factory_decision = StrategyPhase9DeterministicInMemorySimulationRunner().run(scenario_decision)
    function_decision = run_phase9_deterministic_in_memory_simulation(scenario_decision)

    assert factory_decision.run_required.run_id == function_decision.run_required.run_id


def test_runner_does_not_mutate_scenario_contract() -> None:
    scenario_decision = bullish_phase9_simulation_scenario_decision()
    contract = scenario_decision.contract_required

    before = (
        contract.status,
        contract.symbol,
        contract.entry_price_points,
        contract.stop_loss_price_points,
        contract.take_profit_price_points,
        contract.aggregate_risk_budget_bps,
        contract.stage_risk_bps,
    )

    _ = run_phase9_deterministic_in_memory_simulation(scenario_decision).run_required

    after = (
        contract.status,
        contract.symbol,
        contract.entry_price_points,
        contract.stop_loss_price_points,
        contract.take_profit_price_points,
        contract.aggregate_risk_budget_bps,
        contract.stage_risk_bps,
    )

    assert after == before
