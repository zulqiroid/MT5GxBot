from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase11_terminal_broker_account_capability_contract import (
    PHASE_11_ACCOUNT_CAPABILITY_IDS,
    PHASE_11_BROKER_CAPABILITY_IDS,
    PHASE_11_CAPABILITY_LIVE_EXECUTION_STATUS,
    PHASE_11_CAPABILITY_MODE,
    PHASE_11_CAPABILITY_PREFLIGHT_EXECUTION_STATUS,
    PHASE_11_CAPABILITY_PRODUCTION_ACTIVATION_STATUS,
    PHASE_11_CAPABILITY_SCHEMA_VERSION,
    PHASE_11_CAPABILITY_SOURCE,
    PHASE_11_CAPABILITY_STATUS,
    PHASE_11_TERMINAL_CAPABILITY_IDS,
    StrategyPhase11TerminalBrokerAccountCapabilityFactory,
    create_phase11_terminal_broker_account_capability_contract,
)
from tests.test_phase11_live_readiness_admission_gate import (
    bullish_phase11_live_readiness_admission_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedAdmissionDecision:
    is_allowed: bool = False


def bullish_phase11_capability_contract_decision():
    return create_phase11_terminal_broker_account_capability_contract(
        bullish_phase11_live_readiness_admission_decision()
    )


def test_static_capability_contract_is_stable() -> None:
    assert PHASE_11_CAPABILITY_SCHEMA_VERSION == "1.0"
    assert PHASE_11_CAPABILITY_STATUS == "CONTRACT_READY"
    assert PHASE_11_CAPABILITY_MODE == "READINESS_CAPABILITY_INVENTORY"
    assert PHASE_11_CAPABILITY_SOURCE == "DETERMINISTIC_FAKE_ONLY"
    assert PHASE_11_CAPABILITY_PREFLIGHT_EXECUTION_STATUS == "BLOCKED"
    assert PHASE_11_CAPABILITY_PRODUCTION_ACTIVATION_STATUS == "BLOCKED"
    assert PHASE_11_CAPABILITY_LIVE_EXECUTION_STATUS == "BLOCKED"


def test_capability_contract_is_created() -> None:
    decision = bullish_phase11_capability_contract_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.contract is not None


def test_contract_preserves_admission_lineage() -> None:
    admission_decision = bullish_phase11_live_readiness_admission_decision()
    admission_permit = admission_decision.permit_required

    contract = create_phase11_terminal_broker_account_capability_contract(
        admission_decision
    ).contract_required

    assert contract.admission_decision is admission_decision
    assert contract.admission_permit is admission_permit


def test_contract_status_and_source_are_exact() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert contract.status == "CONTRACT_READY"
    assert contract.capability_mode == "READINESS_CAPABILITY_INVENTORY"
    assert contract.capability_source == "DETERMINISTIC_FAKE_ONLY"
    assert contract.fake_inventory_only is True
    assert contract.readiness_planning_only is True


def test_capability_counts_and_access_classes_are_exact() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert contract.total_capability_count == 17
    assert len(contract.all_capabilities) == 17
    assert contract.read_only_capability_count == 13
    assert contract.controlled_lifecycle_capability_count == 2
    assert contract.controlled_write_capability_count == 2


def test_terminal_capability_inventory_is_exact() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert (
        tuple(capability.capability_id for capability in contract.terminal_capabilities)
        == PHASE_11_TERMINAL_CAPABILITY_IDS
    )
    assert tuple(capability.access_class for capability in contract.terminal_capabilities) == (
        "READ_ONLY",
        "CONTROLLED_LIFECYCLE",
        "READ_ONLY",
        "CONTROLLED_LIFECYCLE",
    )


def test_broker_capability_inventory_is_exact() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert (
        tuple(capability.capability_id for capability in contract.broker_capabilities)
        == PHASE_11_BROKER_CAPABILITY_IDS
    )
    assert tuple(capability.access_class for capability in contract.broker_capabilities[-2:]) == (
        "CONTROLLED_WRITE",
        "CONTROLLED_WRITE",
    )


def test_account_capability_inventory_is_exact() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert (
        tuple(capability.capability_id for capability in contract.account_capabilities)
        == PHASE_11_ACCOUNT_CAPABILITY_IDS
    )
    assert all(
        capability.access_class == "READ_ONLY" for capability in contract.account_capabilities
    )


def test_gold_closed_candle_scope_is_preserved() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert contract.allowed_symbol == "XAUUSD"
    assert contract.allowed_timeframes == ("H4", "H1", "M15", "M5")
    assert contract.closed_candles_only is True


def test_risk_oco_guard_and_terminal_contract_is_preserved() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert contract.max_gold_positions == 1
    assert contract.aggregate_risk_budget_bps == 50
    assert contract.stage_risk_bps == (25, 25)
    assert contract.oco_required is True
    assert contract.broker_stop_loss_required is True
    assert contract.guards_required is True
    assert contract.terminal_flat_state_required is True


def test_fake_capabilities_are_non_executable() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert all(
        capability.verified_with_fake_contract is True for capability in contract.all_capabilities
    )
    assert all(
        capability.runtime_invocation_allowed is False for capability in contract.all_capabilities
    )
    assert all(capability.future_gate_required is True for capability in contract.all_capabilities)


def test_real_terminal_broker_and_account_effects_are_blocked() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert contract.permits_real_mt5_import is False
    assert contract.permits_mt5_initialization is False
    assert contract.permits_terminal_connection is False
    assert contract.permits_broker_requests is False
    assert contract.permits_real_account_reads is False
    assert contract.permits_external_writes is False
    assert contract.permits_live_order_submission is False
    assert contract.preflight_execution_status == "BLOCKED"
    assert contract.production_activation_status == "BLOCKED"
    assert contract.live_execution_status == "BLOCKED"


def test_future_human_and_gate_requirements_are_mandatory() -> None:
    contract = bullish_phase11_capability_contract_decision().contract_required

    assert contract.explicit_human_authorization_required is True
    assert contract.separate_preflight_gate_required is True
    assert contract.separate_production_gate_required is True
    assert contract.martingale_prohibited is True
    assert contract.grid_prohibited is True
    assert contract.no_stop_loss_prohibited is True


def test_contract_id_is_deterministic() -> None:
    first = bullish_phase11_capability_contract_decision().contract_required
    second = bullish_phase11_capability_contract_decision().contract_required

    assert first.contract_digest == second.contract_digest
    assert first.contract_id == second.contract_id


def test_missing_admission_blocks_contract() -> None:
    decision = create_phase11_terminal_broker_account_capability_contract(None)

    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("live_readiness_admission_missing",)


def test_blocked_admission_blocks_contract() -> None:
    decision = create_phase11_terminal_broker_account_capability_contract(
        FakeBlockedAdmissionDecision()
    )

    assert decision.is_allowed is False
    assert decision.contract is None
    assert decision.blockers == ("live_readiness_admission_blocked",)

    with pytest.raises(RuntimeError, match="contract is blocked"):
        _ = decision.contract_required


def test_factory_and_function_api_match() -> None:
    admission_decision = bullish_phase11_live_readiness_admission_decision()

    factory_decision = StrategyPhase11TerminalBrokerAccountCapabilityFactory().create(
        admission_decision
    )
    function_decision = create_phase11_terminal_broker_account_capability_contract(
        admission_decision
    )

    assert (
        factory_decision.contract_required.contract_id
        == function_decision.contract_required.contract_id
    )
