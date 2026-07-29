from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase12_real_preflight_planning_admission_gate import (
    PHASE_12_AGGREGATE_RISK_BUDGET_BPS,
    PHASE_12_ALLOWED_SYMBOL,
    PHASE_12_ALLOWED_TIMEFRAMES,
    PHASE_12_REAL_PREFLIGHT_ADMISSION_MODE,
    PHASE_12_REAL_PREFLIGHT_ADMISSION_STATUS,
    PHASE_12_REAL_PREFLIGHT_SCHEMA_VERSION,
    PHASE_12_STAGE_RISK_BPS,
    StrategyPhase12RealPreflightPlanningAdmissionGate,
    evaluate_phase12_real_preflight_planning_admission,
)
from tests.test_phase11_final_audit_handoff import (
    bullish_phase11_final_audit_handoff_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedPhase11HandoffDecision:
    is_allowed: bool = False


def bullish_phase12_real_preflight_planning_admission_decision():
    return evaluate_phase12_real_preflight_planning_admission(
        bullish_phase11_final_audit_handoff_decision()
    )


def test_static_contract_is_stable() -> None:
    assert PHASE_12_REAL_PREFLIGHT_SCHEMA_VERSION == "1.0"
    assert PHASE_12_REAL_PREFLIGHT_ADMISSION_MODE == "REAL_PREFLIGHT_PLANNING_ONLY"
    assert PHASE_12_REAL_PREFLIGHT_ADMISSION_STATUS == "ADMITTED"
    assert PHASE_12_ALLOWED_SYMBOL == "XAUUSD"
    assert PHASE_12_ALLOWED_TIMEFRAMES == ("H4", "H1", "M15", "M5")
    assert PHASE_12_AGGREGATE_RISK_BUDGET_BPS == 50
    assert PHASE_12_STAGE_RISK_BPS == (25, 25)


def test_phase12_admission_is_created() -> None:
    decision = bullish_phase12_real_preflight_planning_admission_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.permit is not None


def test_phase11_lineage_is_preserved() -> None:
    source = bullish_phase11_final_audit_handoff_decision()
    permit = evaluate_phase12_real_preflight_planning_admission(source).permit_required
    assert permit.phase11_handoff_decision is source
    assert permit.phase11_handoff_bundle is source.bundle_required


def test_phase_transition_is_exact() -> None:
    permit = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    assert permit.source_phase_number == 11
    assert permit.target_phase_number == 12
    assert permit.source_phase_status == "PHASE_11_COMPLETE"
    assert permit.source_handoff_status == "READY_FOR_PHASE_12"
    assert permit.phase12_foundation_ready is True


def test_admission_is_planning_only() -> None:
    permit = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    assert permit.admission_mode == "REAL_PREFLIGHT_PLANNING_ONLY"
    assert permit.admission_status == "ADMITTED"
    assert permit.permits_contract_planning is True
    assert permit.permits_adapter_planning is True
    assert permit.permits_snapshot_schema_planning is True


def test_gold_risk_scope_is_exact() -> None:
    permit = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    assert permit.allowed_symbol == "XAUUSD"
    assert permit.allowed_timeframes == ("H4", "H1", "M15", "M5")
    assert permit.closed_candles_only is True
    assert permit.max_gold_positions == 1
    assert permit.aggregate_risk_budget_bps == 50
    assert permit.stage_risk_bps == (25, 25)


def test_oco_guards_and_prohibitions_are_preserved() -> None:
    permit = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    assert permit.oco_required is True
    assert permit.broker_stop_loss_required is True
    assert permit.guards_required is True
    assert permit.terminal_flat_state_required is True
    assert permit.martingale_prohibited is True
    assert permit.grid_prohibited is True
    assert permit.no_stop_loss_prohibited is True


def test_phase11_evidence_is_preserved() -> None:
    permit = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    assert permit.verified_capability_count == 14
    assert permit.blocked_capability_count == 3
    assert permit.verified_event_count == 14


def test_runtime_statuses_are_blocked() -> None:
    permit = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    assert permit.real_preflight_execution_status == "BLOCKED"
    assert permit.mt5_initialization_status == "BLOCKED"
    assert permit.terminal_connection_status == "BLOCKED"
    assert permit.broker_access_status == "BLOCKED"
    assert permit.production_activation_status == "BLOCKED"
    assert permit.live_execution_status == "BLOCKED"


def test_all_runtime_effects_are_prohibited() -> None:
    permit = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    assert permit.permits_real_mt5_import is False
    assert permit.permits_mt5_initialization is False
    assert permit.permits_terminal_connection is False
    assert permit.permits_broker_requests is False
    assert permit.permits_real_account_reads is False
    assert permit.permits_order_check is False
    assert permit.permits_order_send is False
    assert permit.permits_external_writes is False
    assert permit.permits_production_activation is False
    assert permit.permits_live_order_submission is False


def test_future_gates_are_mandatory() -> None:
    permit = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    assert permit.requires_explicit_human_authorization is True
    assert permit.requires_separate_real_preflight_runtime_gate is True
    assert permit.requires_separate_production_gate is True


def test_permit_id_is_deterministic() -> None:
    first = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    second = bullish_phase12_real_preflight_planning_admission_decision().permit_required
    assert first.permit_digest == second.permit_digest
    assert first.permit_id == second.permit_id


def test_missing_source_blocks_admission() -> None:
    decision = evaluate_phase12_real_preflight_planning_admission(None)
    assert decision.is_allowed is False
    assert decision.permit is None
    assert decision.blockers == ("phase11_handoff_decision_missing",)


def test_blocked_source_blocks_admission() -> None:
    decision = evaluate_phase12_real_preflight_planning_admission(
        FakeBlockedPhase11HandoffDecision()
    )
    assert decision.is_allowed is False
    assert decision.permit is None
    assert decision.blockers == ("phase11_handoff_decision_blocked",)
    with pytest.raises(RuntimeError, match="admission is blocked"):
        _ = decision.permit_required


def test_factory_and_function_match() -> None:
    source = bullish_phase11_final_audit_handoff_decision()
    factory = StrategyPhase12RealPreflightPlanningAdmissionGate().evaluate(source).permit_required
    function = evaluate_phase12_real_preflight_planning_admission(source).permit_required
    assert factory.permit_id == function.permit_id
