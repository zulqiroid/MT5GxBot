from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase17_final_paper_mode_operational_readiness_handoff import (
    PHASE_17_FINAL_DECISION,
    PHASE_17_FINAL_HANDOFF_STATUS,
    PHASE_17_FINAL_NEXT_PHASE_STATUS,
    PHASE_17_FINAL_STATUS,
    Phase17FinalPaperModeOperationalReadinessGate,
    finalize_phase17_paper_mode_operational_readiness,
)
from tests.test_phase17_paper_mode_operational_safety_audit import (
    bullish_phase17_safety_audit_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedAudit:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase17_final_handoff_decision():
    return finalize_phase17_paper_mode_operational_readiness(
        bullish_phase17_safety_audit_decision()
    )


def test_critical_final_handoff_created() -> None:
    decision = bullish_phase17_final_handoff_decision()
    handoff = decision.handoff_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert handoff.phase_status == PHASE_17_FINAL_STATUS
    assert handoff.handoff_status == PHASE_17_FINAL_HANDOFF_STATUS
    assert handoff.readiness_decision == PHASE_17_FINAL_DECISION


def test_critical_complete_lineage_preserved() -> None:
    audit = bullish_phase17_safety_audit_decision()
    handoff = finalize_phase17_paper_mode_operational_readiness(audit).handoff_required
    assert handoff.safety_audit_decision is audit
    assert handoff.safety_audit_report is audit.report_required
    assert handoff.validation_decision is audit.report_required.validation_decision
    assert handoff.validation_report is audit.report_required.validation_report
    assert handoff.blueprint_decision is audit.report_required.blueprint_decision
    assert handoff.blueprint is audit.report_required.blueprint
    assert handoff.lineage_preserved is True


def test_critical_phase17_completion_exact() -> None:
    handoff = bullish_phase17_final_handoff_decision().handoff_required
    assert handoff.phase_status == "PHASE_17_COMPLETE"
    assert handoff.handoff_status == "PHASE_17_PAPER_MODE_OPERATIONAL_READINESS_COMPLETE"
    assert handoff.readiness_decision == "PAPER_MODE_OPERATIONAL_READINESS_ESTABLISHED"
    assert handoff.final_handoff_ready is True


def test_critical_evidence_counts_exact() -> None:
    handoff = bullish_phase17_final_handoff_decision().handoff_required
    assert (
        handoff.component_results,
        handoff.requirement_results,
        handoff.track_results,
        handoff.total_results,
        handoff.safety_finding_count,
    ) == (8, 12, 5, 25, 16)


def test_critical_source_evidence_preserved() -> None:
    handoff = bullish_phase17_final_handoff_decision().handoff_required
    assert handoff.phase16_evidence_counts == (8, 12, 5, 25, 16)
    assert handoff.source_validation_audit_counts == (8, 12, 20, 16)
    assert handoff.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_critical_all_real_effects_blocked() -> None:
    handoff = bullish_phase17_final_handoff_decision().handoff_required
    assert handoff.runtime_statuses == ("BLOCKED",) * 8
    assert handoff.execution_admitted is False
    assert handoff.no_real_or_external_effects is True
    assert handoff.real_env_protected is True


def test_gold_scope_and_operational_controls_preserved() -> None:
    handoff = bullish_phase17_final_handoff_decision().handoff_required
    assert handoff.symbol == "XAUUSD"
    assert handoff.timeframes == ("H4", "H1", "M15", "M5")
    assert handoff.aggregate_risk_budget_bps == 50
    assert handoff.stage_risk_bps == (25, 25)
    assert handoff.planning_boundary_preserved is True
    assert handoff.operational_controls_preserved is True
    assert handoff.future_gates_preserved is True


def test_roadmap_closed_and_phase18_not_admitted() -> None:
    handoff = bullish_phase17_final_handoff_decision().handoff_required
    assert handoff.phase17_roadmap_complete is True
    assert handoff.next_phase_status == PHASE_17_FINAL_NEXT_PHASE_STATUS
    assert handoff.next_phase_status == "NOT_DEFINED"
    assert handoff.phase18_admitted is False


def test_handoff_id_is_deterministic() -> None:
    first = bullish_phase17_final_handoff_decision().handoff_required
    second = bullish_phase17_final_handoff_decision().handoff_required
    assert first.handoff_id == second.handoff_id


def test_missing_blocked_and_factory_contract() -> None:
    missing = finalize_phase17_paper_mode_operational_readiness(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase17_safety_audit_missing",)

    blocked = finalize_phase17_paper_mode_operational_readiness(BlockedAudit())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase17_safety_audit_blocked",)
    with pytest.raises(RuntimeError, match="handoff is blocked"):
        _ = blocked.handoff_required

    audit = bullish_phase17_safety_audit_decision()
    first = Phase17FinalPaperModeOperationalReadinessGate().finalize(audit).handoff_required
    second = finalize_phase17_paper_mode_operational_readiness(audit).handoff_required
    assert first.handoff_id == second.handoff_id
