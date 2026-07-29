from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase10_paper_scenario_order_intent_contract import (
    PHASE_10_PAPER_AGGREGATE_RISK_BPS,
    PHASE_10_PAPER_ENTRY_PRICE_POINTS,
    PHASE_10_PAPER_INTENT_MODE,
    PHASE_10_PAPER_KILL_SWITCHES,
    PHASE_10_PAPER_OCO_GROUP_ID,
    PHASE_10_PAPER_POSITION_GROUP_ID,
    PHASE_10_PAPER_SCENARIO_ID,
    PHASE_10_PAPER_SCENARIO_SCHEMA_VERSION,
    PHASE_10_PAPER_SCENARIO_STATUS,
    PHASE_10_PAPER_STAGE_RISK_BPS,
    PHASE_10_PAPER_STOP_LOSS_PRICE_POINTS,
    PHASE_10_PAPER_TAKE_PROFIT_PRICE_POINTS,
    StrategyPhase10PaperScenarioOrderIntentFactory,
    create_phase10_paper_scenario_order_intent,
)
from tests.test_phase10_paper_admission_gate import (
    bullish_phase10_paper_admission_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedAdmissionDecision:
    is_allowed: bool = False


def bullish_phase10_paper_scenario_order_intent_decision():
    return create_phase10_paper_scenario_order_intent(bullish_phase10_paper_admission_decision())


def test_static_paper_scenario_contract_is_stable() -> None:
    assert PHASE_10_PAPER_SCENARIO_SCHEMA_VERSION == "1.0"
    assert PHASE_10_PAPER_SCENARIO_STATUS == "CONTRACT_READY"
    assert PHASE_10_PAPER_SCENARIO_ID == "XAUUSD_PAPER_SCENARIO_001"
    assert PHASE_10_PAPER_INTENT_MODE == "PAPER_INTENT_ONLY"
    assert PHASE_10_PAPER_ENTRY_PRICE_POINTS == 241000
    assert PHASE_10_PAPER_STOP_LOSS_PRICE_POINTS == 240000
    assert PHASE_10_PAPER_TAKE_PROFIT_PRICE_POINTS == 243000


def test_paper_scenario_and_intents_are_created() -> None:
    decision = bullish_phase10_paper_scenario_order_intent_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.contract is not None


def test_contract_preserves_admission_lineage() -> None:
    admission_decision = bullish_phase10_paper_admission_decision()
    admission_permit = admission_decision.permit_required

    contract = create_phase10_paper_scenario_order_intent(admission_decision).contract_required

    assert contract.admission_decision is admission_decision
    assert contract.admission_permit is admission_permit


def test_closed_candle_scope_is_exact() -> None:
    contract = bullish_phase10_paper_scenario_order_intent_decision().contract_required

    assert contract.symbol == "XAUUSD"
    assert contract.timeframes == ("H4", "H1", "M15", "M5")
    assert len(contract.candles) == 4
    assert tuple(candle.timeframe for candle in contract.candles) == (
        "H4",
        "H1",
        "M15",
        "M5",
    )
    assert all(candle.is_closed is True for candle in contract.candles)
    assert contract.closed_candles_only is True


def test_price_and_position_contract_is_exact() -> None:
    contract = bullish_phase10_paper_scenario_order_intent_decision().contract_required

    assert contract.side == "LONG"
    assert contract.entry_price_points == 241000
    assert contract.stop_loss_price_points == 240000
    assert contract.take_profit_price_points == 243000
    assert contract.price_scale == 100
    assert contract.position_group_id == PHASE_10_PAPER_POSITION_GROUP_ID
    assert contract.max_gold_positions == 1


def test_order_intent_roles_types_and_prices_are_exact() -> None:
    contract = bullish_phase10_paper_scenario_order_intent_decision().contract_required

    assert tuple(intent.role for intent in contract.order_intents) == (
        "ENTRY",
        "STOP_LOSS",
        "TAKE_PROFIT",
    )
    assert tuple(intent.order_type for intent in contract.order_intents) == (
        "PAPER_MARKET",
        "PAPER_STOP",
        "PAPER_LIMIT",
    )
    assert tuple(intent.price_points for intent in contract.order_intents) == (
        241000,
        240000,
        243000,
    )


def test_entry_intent_contract_is_exact() -> None:
    entry = bullish_phase10_paper_scenario_order_intent_decision().contract_required.order_intents[
        0
    ]

    assert entry.intent_id == "PAPER-ENTRY-001"
    assert entry.role == "ENTRY"
    assert entry.side == "BUY"
    assert entry.risk_bps == 50
    assert entry.oco_group_id is None
    assert entry.reduce_only is False
    assert entry.broker_stop_loss_required is True


def test_exit_oco_intents_are_exact() -> None:
    contract = bullish_phase10_paper_scenario_order_intent_decision().contract_required
    stop_loss, take_profit = contract.order_intents[1:]

    assert stop_loss.side == "SELL"
    assert take_profit.side == "SELL"
    assert stop_loss.oco_group_id == PHASE_10_PAPER_OCO_GROUP_ID
    assert take_profit.oco_group_id == PHASE_10_PAPER_OCO_GROUP_ID
    assert stop_loss.reduce_only is True
    assert take_profit.reduce_only is True
    assert stop_loss.broker_stop_loss_required is True
    assert take_profit.broker_stop_loss_required is False


def test_staged_and_aggregate_risk_contract_is_exact() -> None:
    contract = bullish_phase10_paper_scenario_order_intent_decision().contract_required

    assert contract.stage_risk_bps == PHASE_10_PAPER_STAGE_RISK_BPS == (25, 25)
    assert contract.aggregate_risk_budget_bps == PHASE_10_PAPER_AGGREGATE_RISK_BPS == 50
    assert sum(contract.stage_risk_bps) == 50


def test_kill_switch_and_prohibited_patterns_are_preserved() -> None:
    contract = bullish_phase10_paper_scenario_order_intent_decision().contract_required

    assert contract.kill_switches == PHASE_10_PAPER_KILL_SWITCHES
    assert contract.oco_required is True
    assert contract.broker_stop_loss_required is True
    assert contract.martingale_prohibited is True
    assert contract.grid_prohibited is True
    assert contract.no_stop_loss_prohibited is True


def test_contract_and_intents_are_non_executable() -> None:
    contract = bullish_phase10_paper_scenario_order_intent_decision().contract_required

    assert all(intent.paper_submission_allowed is False for intent in contract.order_intents)
    assert all(intent.live_submission_allowed is False for intent in contract.order_intents)
    assert contract.permits_paper_planning is True
    assert contract.permits_paper_execution is False
    assert contract.permits_strategy_evaluation is False
    assert contract.permits_mt5_initialization is False
    assert contract.permits_broker_requests is False
    assert contract.permits_external_writes is False
    assert contract.permits_live_order_submission is False


def test_contract_id_is_deterministic() -> None:
    first = bullish_phase10_paper_scenario_order_intent_decision().contract_required
    second = bullish_phase10_paper_scenario_order_intent_decision().contract_required

    assert first.contract_digest == second.contract_digest
    assert first.contract_id == second.contract_id


def test_missing_admission_blocks_contract() -> None:
    decision = create_phase10_paper_scenario_order_intent(None)

    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("paper_admission_decision_missing",)


def test_blocked_admission_blocks_contract() -> None:
    decision = create_phase10_paper_scenario_order_intent(FakeBlockedAdmissionDecision())

    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("paper_admission_decision_blocked",)

    with pytest.raises(RuntimeError, match="order intent is blocked"):
        _ = decision.contract_required


def test_factory_and_function_api_match() -> None:
    admission_decision = bullish_phase10_paper_admission_decision()

    factory_decision = StrategyPhase10PaperScenarioOrderIntentFactory().create(admission_decision)
    function_decision = create_phase10_paper_scenario_order_intent(admission_decision)

    assert (
        factory_decision.contract_required.contract_id
        == function_decision.contract_required.contract_id
    )


def test_contract_creation_does_not_mutate_admission() -> None:
    admission_decision = bullish_phase10_paper_admission_decision()
    permit = admission_decision.permit_required

    before = (
        permit.admission_mode,
        permit.admission_status,
        permit.live_execution_status,
        permit.aggregate_risk_budget_bps,
        permit.stage_risk_bps,
    )

    _ = create_phase10_paper_scenario_order_intent(admission_decision).contract_required

    after = (
        permit.admission_mode,
        permit.admission_status,
        permit.live_execution_status,
        permit.aggregate_risk_budget_bps,
        permit.stage_risk_bps,
    )

    assert after == before
