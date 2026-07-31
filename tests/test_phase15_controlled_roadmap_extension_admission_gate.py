from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase15_controlled_roadmap_extension_admission_gate import (
    PHASE_15_EXTENSION_ADMISSION_MODE,
    PHASE_15_EXTENSION_ADMISSION_SCHEMA_VERSION,
    PHASE_15_EXTENSION_ADMISSION_SOURCE,
    PHASE_15_EXTENSION_ADMISSION_STATUS,
    PHASE_15_EXTENSION_BLOCKED_STATUS,
    PHASE_15_FUTURE_GATE_REQUIREMENTS,
    PHASE_15_PLANNING_TRACKS,
    PHASE_15_SAFETY_REQUIREMENTS,
    Phase15RoadmapExtensionAdmissionGate,
    evaluate_phase15_roadmap_extension,
)
from tests.test_phase14_final_architecture_handoff import (
    bullish_phase14_final_handoff_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedPhase14Handoff:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase15_extension_decision():
    return evaluate_phase15_roadmap_extension(bullish_phase14_final_handoff_decision())


def test_static_contract() -> None:
    assert PHASE_15_EXTENSION_ADMISSION_SCHEMA_VERSION == "1.0"
    assert PHASE_15_EXTENSION_ADMISSION_STATUS == "ADMITTED_FOR_PLANNING_ONLY"
    assert PHASE_15_EXTENSION_ADMISSION_MODE == "CONTROLLED_ROADMAP_EXTENSION_PLANNING_ONLY"
    assert PHASE_15_EXTENSION_ADMISSION_SOURCE == "PHASE_14_FINAL_ARCHITECTURE_HANDOFF_ONLY"
    assert PHASE_15_EXTENSION_BLOCKED_STATUS == "BLOCKED"


def test_admission_created() -> None:
    decision = bullish_phase15_extension_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.permit is not None


def test_phase14_lineage_preserved() -> None:
    source = bullish_phase14_final_handoff_decision()
    permit = evaluate_phase15_roadmap_extension(source).permit_required
    assert permit.source_bundle is source.bundle_required
    assert permit.source_bundle.phase_status == "PHASE_14_COMPLETE"
    assert permit.source_bundle.phase15_admitted is False


def test_transition_exact() -> None:
    permit = bullish_phase15_extension_decision().permit_required
    assert permit.source_phase == 14
    assert permit.target_phase == 15
    assert permit.phase15_foundation_ready is True


def test_planning_only() -> None:
    permit = bullish_phase15_extension_decision().permit_required
    assert permit.phase15_planning_admitted is True
    assert permit.phase15_execution_admitted is False
    assert permit.admission_status == "ADMITTED_FOR_PLANNING_ONLY"


def test_planning_tracks_exact() -> None:
    permit = bullish_phase15_extension_decision().permit_required
    assert permit.planning_tracks == PHASE_15_PLANNING_TRACKS
    assert len(permit.planning_tracks) == 4


def test_validation_audit_counts_preserved() -> None:
    permit = bullish_phase15_extension_decision().permit_required
    assert permit.validation_audit_counts == (8, 12, 20, 16)


def test_source_evidence_counts_preserved() -> None:
    permit = bullish_phase15_extension_decision().permit_required
    assert permit.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_gold_scope_exact() -> None:
    permit = bullish_phase15_extension_decision().permit_required
    assert permit.symbol == "XAUUSD"
    assert permit.timeframes == ("H4", "H1", "M15", "M5")
    assert permit.closed_candles_only is True
    assert permit.max_gold_positions == 1
    assert permit.aggregate_risk_budget_bps == 50
    assert permit.stage_risk_bps == (25, 25)


def test_safety_requirements_exact() -> None:
    permit = bullish_phase15_extension_decision().permit_required
    assert permit.safety_requirements == PHASE_15_SAFETY_REQUIREMENTS
    assert len(permit.safety_requirements) == 7


def test_future_gate_requirements_exact() -> None:
    permit = bullish_phase15_extension_decision().permit_required
    assert permit.future_gate_requirements == PHASE_15_FUTURE_GATE_REQUIREMENTS
    assert len(permit.future_gate_requirements) == 4


def test_all_runtime_statuses_blocked() -> None:
    permit = bullish_phase15_extension_decision().permit_required
    assert permit.runtime_statuses == ("BLOCKED",) * 8
    assert permit.no_real_or_external_effects is True


def test_permit_id_deterministic() -> None:
    first = bullish_phase15_extension_decision().permit_required
    second = bullish_phase15_extension_decision().permit_required
    assert first.permit_digest == second.permit_digest
    assert first.permit_id == second.permit_id


def test_missing_or_blocked_source_blocks() -> None:
    missing = evaluate_phase15_roadmap_extension(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase14_final_handoff_decision_missing",)

    blocked = evaluate_phase15_roadmap_extension(BlockedPhase14Handoff())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase14_final_handoff_decision_blocked",)
    with pytest.raises(RuntimeError, match="admission is blocked"):
        _ = blocked.permit_required


def test_factory_and_function_match() -> None:
    source = bullish_phase14_final_handoff_decision()
    first = Phase15RoadmapExtensionAdmissionGate().evaluate(source).permit_required
    second = evaluate_phase15_roadmap_extension(source).permit_required
    assert first.permit_id == second.permit_id
