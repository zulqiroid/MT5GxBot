from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase16_final_release_readiness_handoff import (
    PHASE_16_FINAL_HANDOFF_STATUS,
    PHASE_16_FINAL_NEXT_PHASE_STATUS,
    PHASE_16_FINAL_RELEASE_DECISION,
    PHASE_16_FINAL_STATUS,
    Phase16FinalReleaseReadinessHandoffGate,
    finalize_phase16_offline_release_readiness,
)
from tests.test_phase16_offline_release_safety_audit import (
    bullish_phase16_offline_safety_audit_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedAudit:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase16_final_release_readiness_handoff_decision():
    return finalize_phase16_offline_release_readiness(
        bullish_phase16_offline_safety_audit_decision()
    )


def test_critical_final_handoff_created() -> None:
    decision = bullish_phase16_final_release_readiness_handoff_decision()
    handoff = decision.handoff_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert handoff.phase_status == PHASE_16_FINAL_STATUS
    assert handoff.handoff_status == PHASE_16_FINAL_HANDOFF_STATUS
    assert handoff.release_decision == PHASE_16_FINAL_RELEASE_DECISION


def test_critical_complete_lineage_preserved() -> None:
    audit = bullish_phase16_offline_safety_audit_decision()
    handoff = finalize_phase16_offline_release_readiness(audit).handoff_required
    assert handoff.safety_audit_decision is audit
    assert handoff.safety_audit_report is audit.report_required
    assert handoff.validation_decision is audit.report_required.validation_decision
    assert handoff.validation_report is audit.report_required.validation_report
    assert handoff.blueprint_decision is audit.report_required.blueprint_decision
    assert handoff.blueprint is audit.report_required.blueprint
    assert handoff.lineage_preserved is True


def test_critical_phase16_completion_statuses_exact() -> None:
    handoff = bullish_phase16_final_release_readiness_handoff_decision().handoff_required
    assert handoff.phase_status == "PHASE_16_COMPLETE"
    assert handoff.handoff_status == "PHASE_16_OFFLINE_RELEASE_READINESS_COMPLETE"
    assert handoff.release_decision == "OFFLINE_RELEASE_READINESS_ESTABLISHED"
    assert handoff.final_handoff_ready is True


def test_critical_phase16_evidence_counts_exact() -> None:
    handoff = bullish_phase16_final_release_readiness_handoff_decision().handoff_required
    assert (
        handoff.component_results,
        handoff.requirement_results,
        handoff.track_results,
        handoff.total_results,
        handoff.safety_finding_count,
    ) == (8, 12, 5, 25, 16)


def test_critical_release_baseline_and_source_counts_preserved() -> None:
    handoff = bullish_phase16_final_release_readiness_handoff_decision().handoff_required
    assert handoff.release_baseline_commit == "6ba3a00"
    assert handoff.release_baseline_tag == "goldxbot-phase-15-complete"
    assert handoff.source_validation_audit_counts == (8, 12, 20, 16)
    assert handoff.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_critical_all_real_runtime_and_live_effects_blocked() -> None:
    handoff = bullish_phase16_final_release_readiness_handoff_decision().handoff_required
    assert handoff.runtime_statuses == ("BLOCKED",) * 8
    assert handoff.execution_admitted is False
    assert handoff.no_real_or_external_effects is True
    assert handoff.real_env_protected is True


def test_gold_scope_and_risk_exact() -> None:
    handoff = bullish_phase16_final_release_readiness_handoff_decision().handoff_required
    assert handoff.symbol == "XAUUSD"
    assert handoff.timeframes == ("H4", "H1", "M15", "M5")
    assert handoff.closed_candles_only is True
    assert handoff.max_gold_positions == 1
    assert handoff.aggregate_risk_budget_bps == 50
    assert handoff.stage_risk_bps == (25, 25)


def test_release_controls_and_safety_preserved() -> None:
    handoff = bullish_phase16_final_release_readiness_handoff_decision().handoff_required
    assert handoff.planning_admitted is True
    assert handoff.execution_admitted is False
    assert handoff.release_controls_preserved is True
    assert handoff.safety_invariants_preserved is True
    assert handoff.real_env_protected is True


def test_roadmap_closed_and_phase17_not_admitted() -> None:
    handoff = bullish_phase16_final_release_readiness_handoff_decision().handoff_required
    assert handoff.phase16_roadmap_complete is True
    assert handoff.next_phase_status == PHASE_16_FINAL_NEXT_PHASE_STATUS
    assert handoff.next_phase_status == "NOT_DEFINED"
    assert handoff.phase17_admitted is False


def test_final_handoff_id_is_deterministic() -> None:
    first = bullish_phase16_final_release_readiness_handoff_decision().handoff_required
    second = bullish_phase16_final_release_readiness_handoff_decision().handoff_required
    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id


def test_missing_and_blocked_audit_are_rejected() -> None:
    missing = finalize_phase16_offline_release_readiness(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase16_safety_audit_decision_missing",)

    blocked = finalize_phase16_offline_release_readiness(BlockedAudit())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase16_safety_audit_decision_blocked",)
    with pytest.raises(RuntimeError, match="handoff is blocked"):
        _ = blocked.handoff_required


def test_factory_and_function_match() -> None:
    audit = bullish_phase16_offline_safety_audit_decision()
    first = Phase16FinalReleaseReadinessHandoffGate().finalize(audit).handoff_required
    second = finalize_phase16_offline_release_readiness(audit).handoff_required
    assert first.handoff_id == second.handoff_id
