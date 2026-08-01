from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase17_paper_mode_operational_readiness_admission_gate import (
    PHASE_17_ADMISSION_STATUS,
    PHASE_17_FUTURE_GATES,
    PHASE_17_NEXT_ALLOWED_STEP,
    PHASE_17_OPERATIONAL_TRACKS,
    PHASE_17_SAFETY_REQUIREMENTS,
    Phase17PaperModeOperationalReadinessAdmissionGate,
    evaluate_phase17_paper_mode_operational_readiness_admission,
)
from tests.test_phase16_final_release_readiness_handoff import (
    bullish_phase16_final_release_readiness_handoff_decision,
)


@dataclass(frozen=True, slots=True)
class Blocked:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase17_admission_decision():
    return evaluate_phase17_paper_mode_operational_readiness_admission(
        bullish_phase16_final_release_readiness_handoff_decision()
    )


def test_critical_admission_created() -> None:
    decision = bullish_phase17_admission_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.permit_required.admission_status == PHASE_17_ADMISSION_STATUS


def test_critical_phase16_lineage_preserved() -> None:
    source = bullish_phase16_final_release_readiness_handoff_decision()
    permit = evaluate_phase17_paper_mode_operational_readiness_admission(source).permit_required
    assert permit.source_bundle is source.handoff_required


def test_critical_planning_only() -> None:
    permit = bullish_phase17_admission_decision().permit_required
    assert permit.planning_admitted is True
    assert permit.execution_admitted is False
    assert permit.next_allowed_step == PHASE_17_NEXT_ALLOWED_STEP


def test_critical_tracks_exact() -> None:
    permit = bullish_phase17_admission_decision().permit_required
    assert permit.operational_tracks == PHASE_17_OPERATIONAL_TRACKS
    assert len(permit.operational_tracks) == 5


def test_critical_gold_scope_and_risk_preserved() -> None:
    permit = bullish_phase17_admission_decision().permit_required
    assert permit.symbol == "XAUUSD"
    assert permit.timeframes == ("H4", "H1", "M15", "M5")
    assert permit.closed_candles_only is True
    assert permit.max_gold_positions == 1
    assert permit.aggregate_risk_budget_bps == 50
    assert permit.stage_risk_bps == (25, 25)


def test_critical_real_effects_blocked() -> None:
    permit = bullish_phase17_admission_decision().permit_required
    assert permit.real_env_access_allowed is False
    assert permit.runtime_statuses == ("BLOCKED",) * 8
    assert permit.no_real_or_external_effects is True


def test_evidence_and_release_baseline_preserved() -> None:
    permit = bullish_phase17_admission_decision().permit_required
    assert permit.phase16_evidence_counts == (8, 12, 5, 25, 16)
    assert permit.source_validation_audit_counts == (8, 12, 20, 16)
    assert permit.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)
    assert permit.release_baseline_commit == "6ba3a00"
    assert permit.release_baseline_tag == "goldxbot-phase-15-complete"


def test_safety_and_future_gates_exact() -> None:
    permit = bullish_phase17_admission_decision().permit_required
    assert permit.safety_requirements == PHASE_17_SAFETY_REQUIREMENTS
    assert permit.future_gates == PHASE_17_FUTURE_GATES


def test_permit_id_is_deterministic() -> None:
    first = bullish_phase17_admission_decision().permit_required
    second = bullish_phase17_admission_decision().permit_required
    assert first.permit_id == second.permit_id


def test_missing_blocked_and_factory_contract() -> None:
    missing = evaluate_phase17_paper_mode_operational_readiness_admission(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase16_final_handoff_missing",)

    blocked = evaluate_phase17_paper_mode_operational_readiness_admission(Blocked())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase16_final_handoff_blocked",)
    with pytest.raises(RuntimeError, match="admission is blocked"):
        _ = blocked.permit_required

    source = bullish_phase16_final_release_readiness_handoff_decision()
    first = Phase17PaperModeOperationalReadinessAdmissionGate().evaluate(source).permit_required
    second = evaluate_phase17_paper_mode_operational_readiness_admission(source).permit_required
    assert first.permit_id == second.permit_id
