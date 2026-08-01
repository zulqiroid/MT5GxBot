from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase17_paper_mode_operational_safety_audit import (
    PHASE_17_SAFETY_AUDIT_HANDOFF_STATUS,
    PHASE_17_SAFETY_AUDIT_STATUS,
    PHASE_17_SAFETY_FINDINGS,
    Phase17PaperModeOperationalSafetyAuditor,
    audit_phase17_paper_mode_operational_safety,
)
from tests.test_phase17_deterministic_paper_mode_operational_validation import (
    bullish_phase17_validation_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedValidation:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase17_safety_audit_decision():
    return audit_phase17_paper_mode_operational_safety(bullish_phase17_validation_decision())


def test_critical_audit_created() -> None:
    decision = bullish_phase17_safety_audit_decision()
    report = decision.report_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert report.audit_status == PHASE_17_SAFETY_AUDIT_STATUS
    assert report.handoff_status == PHASE_17_SAFETY_AUDIT_HANDOFF_STATUS


def test_critical_lineage_preserved() -> None:
    validation = bullish_phase17_validation_decision()
    report = audit_phase17_paper_mode_operational_safety(validation).report_required
    assert report.validation_decision is validation
    assert report.validation_report is validation.report_required
    assert report.lineage_preserved is True


def test_critical_validation_counts_exact() -> None:
    report = bullish_phase17_safety_audit_decision().report_required
    assert (
        report.component_results,
        report.requirement_results,
        report.track_results,
        report.total_results,
    ) == (8, 12, 5, 25)


def test_critical_findings_exact() -> None:
    report = bullish_phase17_safety_audit_decision().report_required
    assert report.finding_count == 16
    assert report.findings == PHASE_17_SAFETY_FINDINGS


def test_critical_evidence_preserved() -> None:
    report = bullish_phase17_safety_audit_decision().report_required
    assert report.phase16_evidence_counts == (8, 12, 5, 25, 16)
    assert report.source_validation_audit_counts == (8, 12, 20, 16)
    assert report.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_critical_real_effects_blocked() -> None:
    report = bullish_phase17_safety_audit_decision().report_required
    assert report.real_env_protected is True
    assert report.runtime_statuses == ("BLOCKED",) * 8
    assert report.no_real_or_external_effects is True
    assert report.ready_for_final_handoff is True


def test_controls_future_gates_and_safety_preserved() -> None:
    report = bullish_phase17_safety_audit_decision().report_required
    assert report.planning_boundary_valid is True
    assert report.operational_controls_valid is True
    assert report.safety_invariants_valid is True
    assert report.future_gates_preserved is True


def test_gold_scope_risk_and_baseline_exact() -> None:
    report = bullish_phase17_safety_audit_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)
    assert report.release_baseline_commit == "6ba3a00"
    assert report.release_baseline_tag == "goldxbot-phase-15-complete"


def test_audit_id_is_deterministic() -> None:
    first = bullish_phase17_safety_audit_decision().report_required
    second = bullish_phase17_safety_audit_decision().report_required
    assert first.audit_id == second.audit_id


def test_missing_blocked_and_factory_contract() -> None:
    missing = audit_phase17_paper_mode_operational_safety(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase17_validation_missing",)

    blocked = audit_phase17_paper_mode_operational_safety(BlockedValidation())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase17_validation_blocked",)
    with pytest.raises(RuntimeError, match="safety audit is blocked"):
        _ = blocked.report_required

    validation = bullish_phase17_validation_decision()
    first = Phase17PaperModeOperationalSafetyAuditor().audit(validation).report_required
    second = audit_phase17_paper_mode_operational_safety(validation).report_required
    assert first.audit_id == second.audit_id
