from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase11_deterministic_read_only_preflight import (
    PHASE_11_LIVE_EXECUTION_STATUS,
    PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS,
    PHASE_11_PREFLIGHT_EVENT_TYPES,
    PHASE_11_PREFLIGHT_MODE,
    PHASE_11_PREFLIGHT_OUTCOME,
    PHASE_11_PREFLIGHT_SCHEMA_VERSION,
    PHASE_11_PREFLIGHT_SOURCE,
    PHASE_11_PREFLIGHT_STATUS,
    PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS,
    PHASE_11_PRODUCTION_ACTIVATION_STATUS,
    PHASE_11_REAL_PREFLIGHT_EXECUTION_STATUS,
    StrategyPhase11DeterministicReadOnlyPreflightRunner,
    run_phase11_deterministic_read_only_preflight,
)
from tests.test_phase11_terminal_broker_account_capability_contract import (
    bullish_phase11_capability_contract_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedCapabilityDecision:
    is_allowed: bool = False


def bullish_phase11_read_only_preflight_decision():
    return run_phase11_deterministic_read_only_preflight(
        bullish_phase11_capability_contract_decision()
    )


def test_static_preflight_contract_is_stable() -> None:
    assert PHASE_11_PREFLIGHT_SCHEMA_VERSION == "1.0"
    assert PHASE_11_PREFLIGHT_MODE == "DETERMINISTIC_FAKE_READ_ONLY"
    assert PHASE_11_PREFLIGHT_STATUS == "COMPLETED"
    assert PHASE_11_PREFLIGHT_OUTCOME == "READY_FOR_READINESS_AUDIT"
    assert PHASE_11_PREFLIGHT_SOURCE == "DETERMINISTIC_FAKE_ONLY"
    assert PHASE_11_REAL_PREFLIGHT_EXECUTION_STATUS == "BLOCKED"
    assert PHASE_11_PRODUCTION_ACTIVATION_STATUS == "BLOCKED"
    assert PHASE_11_LIVE_EXECUTION_STATUS == "BLOCKED"


def test_deterministic_read_only_preflight_is_created() -> None:
    decision = bullish_phase11_read_only_preflight_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.preflight is not None


def test_preflight_preserves_full_lineage() -> None:
    capability_decision = bullish_phase11_capability_contract_decision()
    contract = capability_decision.contract_required
    admission_decision = contract.admission_decision
    admission_permit = contract.admission_permit
    phase10_bundle = admission_permit.phase10_handoff_bundle

    preflight = run_phase11_deterministic_read_only_preflight(
        capability_decision
    ).preflight_required

    assert preflight.capability_decision is capability_decision
    assert preflight.capability_contract is contract
    assert preflight.admission_decision is admission_decision
    assert preflight.admission_permit is admission_permit
    assert preflight.phase10_handoff_bundle is phase10_bundle


def test_preflight_status_and_source_are_exact() -> None:
    preflight = bullish_phase11_read_only_preflight_decision().preflight_required

    assert preflight.mode == "DETERMINISTIC_FAKE_READ_ONLY"
    assert preflight.status == "COMPLETED"
    assert preflight.outcome == "READY_FOR_READINESS_AUDIT"
    assert preflight.source == "DETERMINISTIC_FAKE_ONLY"


def test_fake_terminal_lifecycle_is_exact() -> None:
    preflight = bullish_phase11_read_only_preflight_decision().preflight_required
    snapshot = preflight.terminal_snapshot

    assert snapshot.terminal_name == "GoldXBot-Fake-MT5"
    assert snapshot.build_number == 5000
    assert snapshot.lifecycle_state == "FAKE_SHUTDOWN_COMPLETE"
    assert snapshot.fake_initialized is True
    assert snapshot.fake_shutdown_completed is True
    assert snapshot.real_terminal_connected is False
    assert preflight.fake_terminal_lifecycle_exercised is True


def test_fake_account_snapshot_is_flat_and_read_only() -> None:
    preflight = bullish_phase11_read_only_preflight_decision().preflight_required
    snapshot = preflight.account_snapshot

    assert snapshot.account_id == "FAKE-ACCOUNT-11001"
    assert snapshot.trade_mode == "FAKE_DEMO_READ_ONLY"
    assert snapshot.trade_allowed is False
    assert snapshot.open_gold_position_count == 0
    assert snapshot.pending_gold_order_count == 0
    assert snapshot.reserved_risk_bps == 0
    assert snapshot.is_real_account is False
    assert preflight.terminal_flat_state_valid is True
    assert preflight.exposure_state_valid is True
    assert preflight.margin_state_valid is True


def test_fake_symbol_and_tick_snapshot_is_exact() -> None:
    preflight = bullish_phase11_read_only_preflight_decision().preflight_required
    snapshot = preflight.symbol_snapshot

    assert snapshot.requested_symbol == "XAUUSD"
    assert snapshot.resolved_symbol == "XAUUSD"
    assert snapshot.visible is True
    assert snapshot.digits == 2
    assert snapshot.point_scale == 100
    assert snapshot.bid_price_points == 241000
    assert snapshot.ask_price_points == 241020
    assert snapshot.spread_points == 20
    assert snapshot.real_broker_data_used is False
    assert preflight.symbol_resolution_valid is True
    assert preflight.tick_snapshot_valid is True


def test_verified_and_blocked_capabilities_are_exact() -> None:
    preflight = bullish_phase11_read_only_preflight_decision().preflight_required

    assert preflight.verified_capability_ids == PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS
    assert preflight.blocked_capability_ids == PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS
    assert preflight.verified_capability_count == 14
    assert preflight.blocked_capability_count == 3
    assert preflight.capability_inventory_valid is True


def test_gold_risk_and_timeframe_scope_is_preserved() -> None:
    preflight = bullish_phase11_read_only_preflight_decision().preflight_required

    assert preflight.allowed_symbol == "XAUUSD"
    assert preflight.allowed_timeframes == ("H4", "H1", "M15", "M5")
    assert preflight.closed_candles_only is True
    assert preflight.max_gold_positions == 1
    assert preflight.aggregate_risk_budget_bps == 50
    assert preflight.stage_risk_bps == (25, 25)


def test_preflight_event_trace_is_exact_and_contiguous() -> None:
    preflight = bullish_phase11_read_only_preflight_decision().preflight_required

    assert len(preflight.events) == 14
    assert tuple(event.sequence_index for event in preflight.events) == tuple(range(14))
    assert tuple(event.event_type for event in preflight.events) == (PHASE_11_PREFLIGHT_EVENT_TYPES)
    assert all(event.status == "PASSED" for event in preflight.events)
    assert preflight.event_trace_contiguous is True
    assert preflight.event_trace_order_valid is True


def test_real_preflight_and_all_external_effects_are_blocked() -> None:
    preflight = bullish_phase11_read_only_preflight_decision().preflight_required

    assert preflight.real_mt5_imported is False
    assert preflight.real_mt5_initialized is False
    assert preflight.real_terminal_connected is False
    assert preflight.real_broker_request_sent is False
    assert preflight.real_account_read_performed is False
    assert preflight.order_check_invoked is False
    assert preflight.order_send_invoked is False
    assert preflight.external_state_written is False
    assert preflight.production_activated is False
    assert preflight.live_order_submitted is False
    assert preflight.real_preflight_execution_status == "BLOCKED"
    assert preflight.production_activation_status == "BLOCKED"
    assert preflight.live_execution_status == "BLOCKED"
    assert preflight.no_real_or_external_effects is True


def test_preflight_is_ready_for_readiness_audit() -> None:
    preflight = bullish_phase11_read_only_preflight_decision().preflight_required

    assert preflight.ready_for_readiness_audit is True


def test_preflight_id_is_deterministic() -> None:
    first = bullish_phase11_read_only_preflight_decision().preflight_required
    second = bullish_phase11_read_only_preflight_decision().preflight_required

    assert first.preflight_digest == second.preflight_digest
    assert first.preflight_id == second.preflight_id


def test_missing_capability_contract_blocks_preflight() -> None:
    decision = run_phase11_deterministic_read_only_preflight(None)

    assert decision.is_allowed is False
    assert decision.preflight is None
    assert decision.blockers == ("capability_contract_decision_missing",)


def test_blocked_capability_contract_blocks_preflight() -> None:
    decision = run_phase11_deterministic_read_only_preflight(FakeBlockedCapabilityDecision())

    assert decision.is_allowed is False
    assert decision.preflight is None
    assert decision.blockers == ("capability_contract_decision_blocked",)

    with pytest.raises(RuntimeError, match="preflight is blocked"):
        _ = decision.preflight_required


def test_factory_and_function_api_match() -> None:
    capability_decision = bullish_phase11_capability_contract_decision()

    factory_decision = StrategyPhase11DeterministicReadOnlyPreflightRunner().run(
        capability_decision
    )
    function_decision = run_phase11_deterministic_read_only_preflight(capability_decision)

    assert (
        factory_decision.preflight_required.preflight_id
        == function_decision.preflight_required.preflight_id
    )
