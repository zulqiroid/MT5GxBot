from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase16_offline_release_readiness_blueprint import (
    PHASE_16_RELEASE_BASELINE_COMMIT,
    PHASE_16_RELEASE_BASELINE_TAG,
    PHASE_16_RELEASE_BLUEPRINT_NEXT_ALLOWED,
    PHASE_16_RELEASE_BLUEPRINT_STATUS,
    PHASE_16_RELEASE_READINESS_COMPONENTS,
    PHASE_16_RELEASE_READINESS_REQUIREMENTS,
    Phase16OfflineReleaseReadinessPlanner,
    build_phase16_offline_release_readiness_blueprint,
)
from tests.test_phase16_release_readiness_admission_gate import (
    bullish_phase16_admission_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedAdmission:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase16_blueprint_decision():
    return build_phase16_offline_release_readiness_blueprint(bullish_phase16_admission_decision())


def test_critical_blueprint_created() -> None:
    decision = bullish_phase16_blueprint_decision()
    blueprint = decision.blueprint_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert blueprint.blueprint_status == PHASE_16_RELEASE_BLUEPRINT_STATUS
    assert blueprint.next_allowed_step == PHASE_16_RELEASE_BLUEPRINT_NEXT_ALLOWED


def test_critical_admission_and_phase15_lineage_preserved() -> None:
    admission = bullish_phase16_admission_decision()
    blueprint = build_phase16_offline_release_readiness_blueprint(admission).blueprint_required
    assert blueprint.admission_decision is admission
    assert blueprint.admission_permit is admission.permit_required
    assert blueprint.phase15_final_handoff is admission.permit_required.source_bundle
    assert blueprint.source_phase == 15
    assert blueprint.target_phase == 16


def test_critical_release_baseline_exact() -> None:
    blueprint = bullish_phase16_blueprint_decision().blueprint_required
    assert blueprint.release_baseline_commit == PHASE_16_RELEASE_BASELINE_COMMIT
    assert blueprint.release_baseline_commit == "6ba3a00"
    assert blueprint.release_baseline_tag == PHASE_16_RELEASE_BASELINE_TAG
    assert blueprint.release_baseline_tag == "goldxbot-phase-15-complete"


def test_critical_component_requirement_and_track_counts() -> None:
    blueprint = bullish_phase16_blueprint_decision().blueprint_required
    assert blueprint.components == PHASE_16_RELEASE_READINESS_COMPONENTS
    assert blueprint.requirements == PHASE_16_RELEASE_READINESS_REQUIREMENTS
    assert (
        blueprint.component_count,
        blueprint.requirement_count,
        blueprint.release_readiness_track_count,
    ) == (8, 12, 5)


def test_critical_planning_only_and_env_blocked() -> None:
    blueprint = bullish_phase16_blueprint_decision().blueprint_required
    assert blueprint.planning_admitted is True
    assert blueprint.execution_admitted is False
    assert blueprint.real_env_access_allowed is False
    assert blueprint.deterministic_fakes_only is True
    assert blueprint.paper_mode_only is True


def test_critical_all_real_runtime_statuses_blocked() -> None:
    blueprint = bullish_phase16_blueprint_decision().blueprint_required
    assert blueprint.runtime_statuses == ("BLOCKED",) * 8
    assert blueprint.no_real_or_external_effects is True
    assert blueprint.ready_for_deterministic_offline_validation is True


def test_source_counts_preserved() -> None:
    blueprint = bullish_phase16_blueprint_decision().blueprint_required
    assert blueprint.source_validation_audit_counts == (8, 12, 20, 16)
    assert blueprint.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_gold_scope_and_risk_exact() -> None:
    blueprint = bullish_phase16_blueprint_decision().blueprint_required
    assert blueprint.symbol == "XAUUSD"
    assert blueprint.timeframes == ("H4", "H1", "M15", "M5")
    assert blueprint.closed_candles_only is True
    assert blueprint.max_gold_positions == 1
    assert blueprint.aggregate_risk_budget_bps == 50
    assert blueprint.stage_risk_bps == (25, 25)


def test_release_controls_required() -> None:
    blueprint = bullish_phase16_blueprint_decision().blueprint_required
    assert blueprint.backup_and_rollback_required is True
    assert blueprint.incident_recovery_required is True
    assert all(component.real_effect_allowed is False for component in blueprint.components)
    assert all(requirement.mandatory for requirement in blueprint.requirements)


def test_blueprint_id_is_deterministic() -> None:
    first = bullish_phase16_blueprint_decision().blueprint_required
    second = bullish_phase16_blueprint_decision().blueprint_required
    assert first.blueprint_digest == second.blueprint_digest
    assert first.blueprint_id == second.blueprint_id


def test_missing_blocked_and_factory_contract() -> None:
    missing = build_phase16_offline_release_readiness_blueprint(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase16_admission_decision_missing",)

    blocked = build_phase16_offline_release_readiness_blueprint(BlockedAdmission())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase16_admission_decision_blocked",)
    with pytest.raises(RuntimeError, match="blueprint is blocked"):
        _ = blocked.blueprint_required

    admission = bullish_phase16_admission_decision()
    first = Phase16OfflineReleaseReadinessPlanner().build(admission).blueprint_required
    second = build_phase16_offline_release_readiness_blueprint(admission).blueprint_required
    assert first.blueprint_id == second.blueprint_id
