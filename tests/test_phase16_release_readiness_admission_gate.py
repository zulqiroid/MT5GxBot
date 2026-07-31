from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase16_release_readiness_admission_gate import (
    PHASE_16_ADMISSION_MODE,
    PHASE_16_ADMISSION_SOURCE,
    PHASE_16_ADMISSION_STATUS,
    PHASE_16_FUTURE_GATE_REQUIREMENTS,
    PHASE_16_NEXT_ALLOWED_STEP,
    PHASE_16_RELEASE_READINESS_TRACKS,
    PHASE_16_SAFETY_REQUIREMENTS,
    Phase16OfflineReleaseReadinessAdmissionGate,
    evaluate_phase16_offline_release_readiness_admission,
)
from tests.test_phase15_final_architecture_handoff import (
    bullish_phase15_final_handoff_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedHandoff:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase16_admission_decision():
    return evaluate_phase16_offline_release_readiness_admission(
        bullish_phase15_final_handoff_decision()
    )


def test_critical_admission_created() -> None:
    decision = bullish_phase16_admission_decision()
    permit = decision.permit_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert permit.admission_status == PHASE_16_ADMISSION_STATUS
    assert permit.admission_mode == PHASE_16_ADMISSION_MODE
    assert permit.admission_source == PHASE_16_ADMISSION_SOURCE


def test_critical_phase15_lineage_preserved() -> None:
    source = bullish_phase15_final_handoff_decision()
    permit = evaluate_phase16_offline_release_readiness_admission(source).permit_required
    assert permit.source_bundle is source.handoff_required
    assert (permit.source_phase, permit.target_phase) == (15, 16)


def test_critical_phase16_planning_only() -> None:
    permit = bullish_phase16_admission_decision().permit_required
    assert permit.phase16_planning_admitted is True
    assert permit.phase16_execution_admitted is False
    assert permit.phase16_foundation_ready is True
    assert permit.next_allowed_step == PHASE_16_NEXT_ALLOWED_STEP


def test_critical_release_readiness_tracks_exact() -> None:
    permit = bullish_phase16_admission_decision().permit_required
    assert permit.release_readiness_tracks == PHASE_16_RELEASE_READINESS_TRACKS
    assert len(permit.release_readiness_tracks) == 5


def test_critical_gold_scope_and_risk_preserved() -> None:
    permit = bullish_phase16_admission_decision().permit_required
    assert permit.symbol == "XAUUSD"
    assert permit.timeframes == ("H4", "H1", "M15", "M5")
    assert permit.closed_candles_only is True
    assert permit.max_gold_positions == 1
    assert permit.aggregate_risk_budget_bps == 50
    assert permit.stage_risk_bps == (25, 25)


def test_critical_all_real_runtime_statuses_blocked() -> None:
    permit = bullish_phase16_admission_decision().permit_required
    assert permit.runtime_statuses == ("BLOCKED",) * 8
    assert permit.no_real_or_external_effects is True


def test_source_counts_preserved() -> None:
    permit = bullish_phase16_admission_decision().permit_required
    assert permit.validation_audit_counts == (8, 12, 20, 16)
    assert permit.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_safety_and_future_gates_exact() -> None:
    permit = bullish_phase16_admission_decision().permit_required
    assert permit.safety_requirements == PHASE_16_SAFETY_REQUIREMENTS
    assert permit.future_gate_requirements == PHASE_16_FUTURE_GATE_REQUIREMENTS


def test_permit_id_is_deterministic() -> None:
    first = bullish_phase16_admission_decision().permit_required
    second = bullish_phase16_admission_decision().permit_required
    assert first.permit_id == second.permit_id


def test_missing_and_blocked_sources_are_rejected() -> None:
    missing = evaluate_phase16_offline_release_readiness_admission(None)
    assert missing.blockers == ("phase15_final_handoff_decision_missing",)

    blocked = evaluate_phase16_offline_release_readiness_admission(BlockedHandoff())
    assert blocked.blockers == ("phase15_final_handoff_decision_blocked",)
    with pytest.raises(RuntimeError, match="release admission is blocked"):
        _ = blocked.permit_required


def test_factory_and_function_match() -> None:
    source = bullish_phase15_final_handoff_decision()
    first = Phase16OfflineReleaseReadinessAdmissionGate().evaluate(source).permit_required
    second = evaluate_phase16_offline_release_readiness_admission(source).permit_required
    assert first.permit_id == second.permit_id
