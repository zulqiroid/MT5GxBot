from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase11_live_readiness_admission_gate import (
    PHASE_11_AGGREGATE_RISK_BUDGET_BPS,
    PHASE_11_ALLOWED_SYMBOL,
    PHASE_11_ALLOWED_TIMEFRAMES,
    PHASE_11_LIVE_EXECUTION_STATUS,
    PHASE_11_LIVE_READINESS_ADMISSION_MODE,
    PHASE_11_LIVE_READINESS_ADMISSION_STATUS,
    PHASE_11_LIVE_READINESS_SCHEMA_VERSION,
    PHASE_11_MAX_GOLD_POSITIONS,
    PHASE_11_PRODUCTION_ACTIVATION_STATUS,
    PHASE_11_STAGE_RISK_BPS,
    StrategyPhase11LiveReadinessAdmissionGate,
    evaluate_phase11_live_readiness_admission,
)
from tests.test_phase10_final_audit_handoff import (
    bullish_phase10_final_audit_handoff_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedPhase10HandoffDecision:
    is_allowed: bool = False


def bullish_phase11_live_readiness_admission_decision():
    return evaluate_phase11_live_readiness_admission(bullish_phase10_final_audit_handoff_decision())


def test_static_admission_contract_is_stable() -> None:
    assert PHASE_11_LIVE_READINESS_SCHEMA_VERSION == "1.0"
    assert PHASE_11_LIVE_READINESS_ADMISSION_MODE == "LIVE_READINESS_ONLY"
    assert PHASE_11_LIVE_READINESS_ADMISSION_STATUS == "ADMITTED"
    assert PHASE_11_LIVE_EXECUTION_STATUS == "BLOCKED"
    assert PHASE_11_PRODUCTION_ACTIVATION_STATUS == "BLOCKED"
    assert PHASE_11_ALLOWED_SYMBOL == "XAUUSD"
    assert PHASE_11_ALLOWED_TIMEFRAMES == ("H4", "H1", "M15", "M5")
    assert PHASE_11_MAX_GOLD_POSITIONS == 1
    assert PHASE_11_AGGREGATE_RISK_BUDGET_BPS == 50
    assert PHASE_11_STAGE_RISK_BPS == (25, 25)


def test_phase11_live_readiness_admission_is_created() -> None:
    decision = bullish_phase11_live_readiness_admission_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.permit is not None


def test_admission_preserves_phase10_lineage() -> None:
    handoff_decision = bullish_phase10_final_audit_handoff_decision()
    handoff_bundle = handoff_decision.bundle_required

    permit = evaluate_phase11_live_readiness_admission(handoff_decision).permit_required

    assert permit.phase10_handoff_decision is handoff_decision
    assert permit.phase10_handoff_bundle is handoff_bundle


def test_phase_transition_contract_is_exact() -> None:
    permit = bullish_phase11_live_readiness_admission_decision().permit_required

    assert permit.source_phase_number == 10
    assert permit.target_phase_number == 11
    assert permit.source_phase_status == "PHASE_10_COMPLETE"
    assert permit.source_handoff_status == "READY_FOR_PHASE_11"
    assert permit.phase11_foundation_ready is True


def test_source_safety_contract_is_exact() -> None:
    permit = bullish_phase11_live_readiness_admission_decision().permit_required

    assert permit.source_execution_mode == "IN_MEMORY_PAPER"
    assert permit.source_live_execution_status == "BLOCKED"
    assert permit.source_safety_audit_status == "PASSED"


def test_fail_closed_admission_contract_is_exact() -> None:
    permit = bullish_phase11_live_readiness_admission_decision().permit_required

    assert permit.admission_mode == "LIVE_READINESS_ONLY"
    assert permit.admission_status == "ADMITTED"
    assert permit.live_execution_status == "BLOCKED"
    assert permit.production_activation_status == "BLOCKED"
    assert permit.permits_readiness_planning is True
    assert permit.permits_capability_inventory_planning is True


def test_gold_closed_candle_scope_is_exact() -> None:
    permit = bullish_phase11_live_readiness_admission_decision().permit_required

    assert permit.allowed_symbol == "XAUUSD"
    assert permit.allowed_timeframes == ("H4", "H1", "M15", "M5")
    assert permit.closed_candles_only is True


def test_risk_position_oco_and_guard_contract_is_exact() -> None:
    permit = bullish_phase11_live_readiness_admission_decision().permit_required

    assert permit.max_gold_positions == 1
    assert permit.aggregate_risk_budget_bps == 50
    assert permit.stage_risk_bps == (25, 25)
    assert permit.one_gold_position_max is True
    assert permit.staged_aggregate_risk_required is True
    assert permit.oco_required is True
    assert permit.broker_stop_loss_required is True
    assert permit.guards_required is True
    assert permit.terminal_flat_state_required is True


def test_prohibited_patterns_are_preserved() -> None:
    permit = bullish_phase11_live_readiness_admission_decision().permit_required

    assert permit.martingale_prohibited is True
    assert permit.grid_prohibited is True
    assert permit.no_stop_loss_prohibited is True


def test_admission_has_no_execution_or_external_effects() -> None:
    permit = bullish_phase11_live_readiness_admission_decision().permit_required

    assert permit.permits_preflight_execution is False
    assert permit.permits_paper_execution is False
    assert permit.permits_mt5_initialization is False
    assert permit.permits_broker_requests is False
    assert permit.permits_external_writes is False
    assert permit.permits_live_order_submission is False


def test_human_authorization_and_future_gate_are_mandatory() -> None:
    permit = bullish_phase11_live_readiness_admission_decision().permit_required

    assert permit.requires_explicit_human_authorization is True
    assert permit.requires_separate_production_gate is True


def test_admission_id_is_deterministic() -> None:
    first = bullish_phase11_live_readiness_admission_decision().permit_required
    second = bullish_phase11_live_readiness_admission_decision().permit_required

    assert first.permit_digest == second.permit_digest
    assert first.permit_id == second.permit_id


def test_missing_phase10_handoff_blocks_admission() -> None:
    decision = evaluate_phase11_live_readiness_admission(None)

    assert decision.is_allowed is False
    assert decision.permit is None
    assert decision.blockers == ("phase10_handoff_decision_missing",)


def test_blocked_phase10_handoff_blocks_admission() -> None:
    decision = evaluate_phase11_live_readiness_admission(FakeBlockedPhase10HandoffDecision())

    assert decision.is_allowed is False
    assert decision.permit is None
    assert decision.blockers == ("phase10_handoff_decision_blocked",)

    with pytest.raises(RuntimeError, match="admission is blocked"):
        _ = decision.permit_required


def test_factory_and_function_api_match() -> None:
    handoff_decision = bullish_phase10_final_audit_handoff_decision()

    factory_decision = StrategyPhase11LiveReadinessAdmissionGate().evaluate(handoff_decision)
    function_decision = evaluate_phase11_live_readiness_admission(handoff_decision)

    assert factory_decision.permit_required.permit_id == function_decision.permit_required.permit_id


def test_admission_does_not_mutate_phase10_handoff() -> None:
    handoff_decision = bullish_phase10_final_audit_handoff_decision()
    bundle = handoff_decision.bundle_required

    before = (
        bundle.phase_number,
        bundle.phase_status,
        bundle.handoff_status,
        bundle.execution_mode,
        bundle.live_execution_status,
        bundle.safety_audit_status,
    )

    _ = evaluate_phase11_live_readiness_admission(handoff_decision).permit_required

    after = (
        bundle.phase_number,
        bundle.phase_status,
        bundle.handoff_status,
        bundle.execution_mode,
        bundle.live_execution_status,
        bundle.safety_audit_status,
    )

    assert after == before
