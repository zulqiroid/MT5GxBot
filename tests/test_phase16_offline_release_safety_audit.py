from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase16_offline_release_safety_audit import (
    PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_HANDOFF_STATUS,
    PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SOURCE,
    PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_STATUS,
    PHASE_16_OFFLINE_RELEASE_SAFETY_FINDINGS,
    Phase16OfflineReleaseSafetyAuditor,
    audit_phase16_offline_release_readiness_safety,
)
from tests.test_phase16_deterministic_offline_release_validation import (
    bullish_phase16_offline_validation_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedValidation:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase16_offline_safety_audit_decision():
    return audit_phase16_offline_release_readiness_safety(
        bullish_phase16_offline_validation_decision()
    )


def test_critical_audit_created() -> None:
    decision = bullish_phase16_offline_safety_audit_decision()
    report = decision.report_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert report.audit_status == PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_STATUS
    assert report.handoff_status == PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_HANDOFF_STATUS
    assert report.audit_source == PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SOURCE


def test_critical_complete_lineage_preserved() -> None:
    validation = bullish_phase16_offline_validation_decision()
    report = audit_phase16_offline_release_readiness_safety(validation).report_required
    assert report.validation_decision is validation
    assert report.validation_report is validation.report_required
    assert report.blueprint_decision is validation.report_required.blueprint_decision
    assert report.blueprint is validation.report_required.blueprint
    assert report.lineage_preserved is True


def test_critical_validation_counts_exact() -> None:
    report = bullish_phase16_offline_safety_audit_decision().report_required
    assert (
        report.component_results,
        report.requirement_results,
        report.track_results,
        report.total_results,
    ) == (8, 12, 5, 25)


def test_critical_release_baseline_and_source_counts_preserved() -> None:
    report = bullish_phase16_offline_safety_audit_decision().report_required
    assert report.release_baseline_commit == "6ba3a00"
    assert report.release_baseline_tag == "goldxbot-phase-15-complete"
    assert report.source_validation_audit_counts == (8, 12, 20, 16)
    assert report.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_critical_real_env_and_release_controls_protected() -> None:
    report = bullish_phase16_offline_safety_audit_decision().report_required
    assert report.real_env_protected is True
    assert report.release_controls_valid is True
    assert report.safety_invariants_valid is True


def test_critical_all_real_runtime_statuses_blocked() -> None:
    report = bullish_phase16_offline_safety_audit_decision().report_required
    assert report.runtime_statuses == ("BLOCKED",) * 8
    assert report.no_real_effects is True
    assert report.ready_for_final_handoff is True


def test_safety_findings_exact() -> None:
    report = bullish_phase16_offline_safety_audit_decision().report_required
    assert report.finding_count == 16
    assert tuple(item.name for item in report.findings) == (
        PHASE_16_OFFLINE_RELEASE_SAFETY_FINDINGS
    )
    assert all(item.status == "PASSED" for item in report.findings)


def test_gold_scope_and_risk_exact() -> None:
    report = bullish_phase16_offline_safety_audit_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)


def test_audit_status_and_handoff_exact() -> None:
    report = bullish_phase16_offline_safety_audit_decision().report_required
    assert report.audit_status == "PASSED"
    assert report.handoff_status == "READY_FOR_PHASE_16_FINAL_HANDOFF"
    assert report.safety_audit_passed is True
    assert report.ready_for_final_handoff is True


def test_audit_id_is_deterministic() -> None:
    first = bullish_phase16_offline_safety_audit_decision().report_required
    second = bullish_phase16_offline_safety_audit_decision().report_required
    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id


def test_missing_and_blocked_validation_are_rejected() -> None:
    missing = audit_phase16_offline_release_readiness_safety(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase16_validation_decision_missing",)

    blocked = audit_phase16_offline_release_readiness_safety(BlockedValidation())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase16_validation_decision_blocked",)
    with pytest.raises(RuntimeError, match="safety audit is blocked"):
        _ = blocked.report_required


def test_factory_and_function_match() -> None:
    validation = bullish_phase16_offline_validation_decision()
    first = Phase16OfflineReleaseSafetyAuditor().audit(validation).report_required
    second = audit_phase16_offline_release_readiness_safety(validation).report_required
    assert first.audit_id == second.audit_id
