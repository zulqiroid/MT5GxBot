from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase17_paper_mode_operational_readiness_blueprint import (
    PHASE_17_BLUEPRINT_COMPONENTS,
    PHASE_17_BLUEPRINT_NEXT_ALLOWED_STEP,
    PHASE_17_BLUEPRINT_REQUIREMENT_OBJECTS,
    PHASE_17_BLUEPRINT_STATUS,
    Phase17PaperModeOperationalReadinessPlanner,
    build_phase17_paper_mode_operational_readiness_blueprint,
)
from tests.test_phase17_paper_mode_operational_readiness_admission_gate import (
    bullish_phase17_admission_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedAdmission:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase17_blueprint_decision():
    return build_phase17_paper_mode_operational_readiness_blueprint(
        bullish_phase17_admission_decision()
    )


def test_critical_blueprint_created() -> None:
    decision = bullish_phase17_blueprint_decision()
    blueprint = decision.blueprint_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert blueprint.blueprint_status == PHASE_17_BLUEPRINT_STATUS
    assert blueprint.next_allowed_step == PHASE_17_BLUEPRINT_NEXT_ALLOWED_STEP


def test_critical_admission_lineage_preserved() -> None:
    admission = bullish_phase17_admission_decision()
    blueprint = build_phase17_paper_mode_operational_readiness_blueprint(
        admission
    ).blueprint_required
    assert blueprint.admission_decision is admission
    assert blueprint.admission_permit is admission.permit_required
    assert blueprint.phase16_final_handoff is admission.permit_required.source_bundle


def test_critical_counts_exact() -> None:
    blueprint = bullish_phase17_blueprint_decision().blueprint_required
    assert blueprint.components == PHASE_17_BLUEPRINT_COMPONENTS
    assert blueprint.requirements == PHASE_17_BLUEPRINT_REQUIREMENT_OBJECTS
    assert (
        blueprint.component_count,
        blueprint.requirement_count,
        blueprint.operational_track_count,
    ) == (8, 12, 5)


def test_critical_planning_only_and_env_blocked() -> None:
    blueprint = bullish_phase17_blueprint_decision().blueprint_required
    assert blueprint.planning_admitted is True
    assert blueprint.execution_admitted is False
    assert blueprint.real_env_access_allowed is False
    assert blueprint.deterministic_fakes_only is True
    assert blueprint.paper_mode_only is True


def test_critical_gold_scope_and_risk_exact() -> None:
    blueprint = bullish_phase17_blueprint_decision().blueprint_required
    assert blueprint.symbol == "XAUUSD"
    assert blueprint.timeframes == ("H4", "H1", "M15", "M5")
    assert blueprint.closed_candles_only is True
    assert blueprint.max_gold_positions == 1
    assert blueprint.aggregate_risk_budget_bps == 50
    assert blueprint.stage_risk_bps == (25, 25)


def test_critical_real_runtime_effects_blocked() -> None:
    blueprint = bullish_phase17_blueprint_decision().blueprint_required
    assert blueprint.runtime_statuses == ("BLOCKED",) * 8
    assert blueprint.no_real_or_external_effects is True
    assert blueprint.ready_for_deterministic_validation is True


def test_phase16_and_source_evidence_preserved() -> None:
    blueprint = bullish_phase17_blueprint_decision().blueprint_required
    assert blueprint.phase16_evidence_counts == (8, 12, 5, 25, 16)
    assert blueprint.source_validation_audit_counts == (8, 12, 20, 16)
    assert blueprint.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_release_baseline_preserved() -> None:
    blueprint = bullish_phase17_blueprint_decision().blueprint_required
    assert blueprint.release_baseline_commit == "6ba3a00"
    assert blueprint.release_baseline_tag == "goldxbot-phase-15-complete"


def test_operational_controls_required() -> None:
    blueprint = bullish_phase17_blueprint_decision().blueprint_required
    assert blueprint.fail_closed_required is True
    assert blueprint.evidence_handoff_required is True
    assert all(not item.real_effect_allowed for item in blueprint.components)
    assert all(item.mandatory for item in blueprint.requirements)


def test_blueprint_id_is_deterministic() -> None:
    first = bullish_phase17_blueprint_decision().blueprint_required
    second = bullish_phase17_blueprint_decision().blueprint_required
    assert first.blueprint_id == second.blueprint_id


def test_missing_blocked_and_factory_contract() -> None:
    missing = build_phase17_paper_mode_operational_readiness_blueprint(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase17_admission_missing",)

    blocked = build_phase17_paper_mode_operational_readiness_blueprint(BlockedAdmission())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase17_admission_blocked",)
    with pytest.raises(RuntimeError, match="blueprint is blocked"):
        _ = blocked.blueprint_required

    admission = bullish_phase17_admission_decision()
    first = Phase17PaperModeOperationalReadinessPlanner().build(admission).blueprint_required
    second = build_phase17_paper_mode_operational_readiness_blueprint(admission).blueprint_required
    assert first.blueprint_id == second.blueprint_id
