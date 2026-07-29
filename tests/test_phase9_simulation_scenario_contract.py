from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase9_simulation_scenario_contract import (
    PHASE_9_SIMULATION_AGGREGATE_RISK_BPS,
    PHASE_9_SIMULATION_KILL_SWITCHES,
    PHASE_9_SIMULATION_OCO_GROUP_ID,
    PHASE_9_SIMULATION_SCENARIO_ID,
    PHASE_9_SIMULATION_SCENARIO_SCHEMA_VERSION,
    PHASE_9_SIMULATION_SCENARIO_STATUS,
    PHASE_9_SIMULATION_SCENARIO_SYMBOL,
    PHASE_9_SIMULATION_SCENARIO_TIMEFRAMES,
    PHASE_9_SIMULATION_STAGE_RISK_BPS,
    StrategyPhase9SimulationScenarioFactory,
    create_phase9_simulation_scenario,
)
from tests.test_phase9_simulation_admission_gate import (
    bullish_phase9_simulation_admission_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedAdmissionDecision:
    is_allowed: bool = False


def bullish_phase9_simulation_scenario_decision():
    return create_phase9_simulation_scenario(bullish_phase9_simulation_admission_decision())


def test_static_scenario_contract_is_stable() -> None:
    assert PHASE_9_SIMULATION_SCENARIO_SCHEMA_VERSION == "1.0"
    assert PHASE_9_SIMULATION_SCENARIO_STATUS == "CONTRACT_READY"
    assert PHASE_9_SIMULATION_SCENARIO_ID == "XAUUSD_CLOSED_CANDLE_SCENARIO_001"
    assert PHASE_9_SIMULATION_SCENARIO_SYMBOL == "XAUUSD"
    assert PHASE_9_SIMULATION_SCENARIO_TIMEFRAMES == (
        "H4",
        "H1",
        "M15",
        "M5",
    )


def test_simulation_scenario_is_created() -> None:
    decision = bullish_phase9_simulation_scenario_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.contract is not None


def test_scenario_preserves_admission_lineage() -> None:
    admission_decision = bullish_phase9_simulation_admission_decision()
    admission_permit = admission_decision.permit_required

    contract = create_phase9_simulation_scenario(admission_decision).contract_required

    assert contract.admission_decision is admission_decision
    assert contract.admission_permit is admission_permit


def test_closed_candle_set_is_exact() -> None:
    contract = bullish_phase9_simulation_scenario_decision().contract_required

    assert contract.symbol == "XAUUSD"
    assert contract.timeframes == ("H4", "H1", "M15", "M5")
    assert len(contract.closed_candles) == 4
    assert tuple(candle.timeframe for candle in contract.closed_candles) == contract.timeframes
    assert all(
        candle.close_time_utc == "2026-01-05T12:00:00Z" for candle in contract.closed_candles
    )
    assert all(candle.is_closed is True for candle in contract.closed_candles)


def test_price_scenario_is_exact() -> None:
    contract = bullish_phase9_simulation_scenario_decision().contract_required

    assert contract.side == "LONG"
    assert contract.entry_price_points == 240900
    assert contract.stop_loss_price_points == 239900
    assert contract.take_profit_price_points == 242900
    assert contract.price_scale == 100
    assert (
        contract.stop_loss_price_points
        < contract.entry_price_points
        < contract.take_profit_price_points
    )


def test_risk_stage_allocation_is_exact() -> None:
    contract = bullish_phase9_simulation_scenario_decision().contract_required

    assert contract.aggregate_risk_budget_bps == PHASE_9_SIMULATION_AGGREGATE_RISK_BPS == 50
    assert contract.stage_risk_bps == PHASE_9_SIMULATION_STAGE_RISK_BPS == (25, 25)
    assert sum(contract.stage_risk_bps) == contract.aggregate_risk_budget_bps
    assert contract.max_gold_positions == 1


def test_oco_stop_loss_and_kill_switch_contract_is_exact() -> None:
    contract = bullish_phase9_simulation_scenario_decision().contract_required

    assert contract.oco_group_id == PHASE_9_SIMULATION_OCO_GROUP_ID
    assert contract.broker_stop_loss_required is True
    assert contract.kill_switches == PHASE_9_SIMULATION_KILL_SWITCHES
    assert contract.oco_required is True
    assert contract.kill_switches_required is True


def test_prohibited_execution_patterns_are_preserved() -> None:
    contract = bullish_phase9_simulation_scenario_decision().contract_required

    assert contract.martingale_prohibited is True
    assert contract.grid_prohibited is True
    assert contract.no_stop_loss_prohibited is True
    assert contract.one_gold_position_max is True
    assert contract.staged_aggregate_risk_required is True


def test_contract_performs_no_execution_or_external_effects() -> None:
    contract = bullish_phase9_simulation_scenario_decision().contract_required

    assert contract.permits_simulation_planning is True
    assert contract.permits_simulation_execution is False
    assert contract.permits_strategy_evaluation is False
    assert contract.permits_mt5_initialization is False
    assert contract.permits_broker_requests is False
    assert contract.permits_external_writes is False
    assert contract.permits_order_submission is False


def test_scenario_id_is_deterministic() -> None:
    first = bullish_phase9_simulation_scenario_decision().contract_required
    second = bullish_phase9_simulation_scenario_decision().contract_required

    assert first.scenario_digest == second.scenario_digest
    assert first.contract_id == second.contract_id


def test_missing_admission_blocks_scenario() -> None:
    decision = create_phase9_simulation_scenario(None)

    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("simulation_admission_decision_missing",)


def test_blocked_admission_blocks_scenario() -> None:
    decision = create_phase9_simulation_scenario(FakeBlockedAdmissionDecision())

    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("simulation_admission_decision_blocked",)

    with pytest.raises(RuntimeError, match="scenario is blocked"):
        _ = decision.contract_required


def test_factory_and_function_api_match() -> None:
    admission_decision = bullish_phase9_simulation_admission_decision()

    factory_decision = StrategyPhase9SimulationScenarioFactory().create(admission_decision)
    function_decision = create_phase9_simulation_scenario(admission_decision)

    assert (
        factory_decision.contract_required.contract_id
        == function_decision.contract_required.contract_id
    )


def test_scenario_creation_does_not_mutate_admission_permit() -> None:
    admission_decision = bullish_phase9_simulation_admission_decision()
    permit = admission_decision.permit_required

    before = (
        permit.source_phase_number,
        permit.target_phase_number,
        permit.admission_mode,
        permit.admission_status,
        permit.live_execution_status,
        permit.allowed_symbol,
        permit.allowed_timeframes,
    )

    _ = create_phase9_simulation_scenario(admission_decision).contract_required

    after = (
        permit.source_phase_number,
        permit.target_phase_number,
        permit.admission_mode,
        permit.admission_status,
        permit.live_execution_status,
        permit.allowed_symbol,
        permit.allowed_timeframes,
    )

    assert after == before
