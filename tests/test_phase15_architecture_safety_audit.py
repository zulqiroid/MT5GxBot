from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase15_architecture_safety_audit import (
    PHASE_15_ARCHITECTURE_SAFETY_AUDIT_HANDOFF_STATUS,
    PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SOURCE,
    PHASE_15_ARCHITECTURE_SAFETY_AUDIT_STATUS,
    PHASE_15_ARCHITECTURE_SAFETY_FINDINGS,
    Phase15ArchitectureSafetyAuditor,
    audit_phase15_extension_architecture_safety,
)
from tests.test_phase15_deterministic_architecture_validation import (
    bullish_phase15_architecture_validation_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedValidation:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase15_safety_audit_decision():
    return audit_phase15_extension_architecture_safety(
        bullish_phase15_architecture_validation_decision()
    )


def test_audit_created_and_static_contract() -> None:
    decision = bullish_phase15_safety_audit_decision()
    report = decision.report_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert PHASE_15_ARCHITECTURE_SAFETY_AUDIT_STATUS == "PASSED"
    assert PHASE_15_ARCHITECTURE_SAFETY_AUDIT_HANDOFF_STATUS == "READY_FOR_PHASE_15_FINAL_HANDOFF"
    assert (
        PHASE_15_ARCHITECTURE_SAFETY_AUDIT_SOURCE
        == "DETERMINISTIC_ARCHITECTURE_VALIDATION_EVIDENCE_ONLY"
    )
    assert report.audit_status == "PASSED"


def test_complete_lineage_preserved() -> None:
    validation = bullish_phase15_architecture_validation_decision()
    report = audit_phase15_extension_architecture_safety(validation).report_required
    assert report.validation_decision is validation
    assert report.validation_report is validation.report_required
    assert report.architecture_decision is validation.report_required.architecture_decision
    assert report.architecture_blueprint is validation.report_required.architecture_blueprint
    assert report.lineage_preserved is True


def test_validation_counts_exact() -> None:
    report = bullish_phase15_safety_audit_decision().report_required
    assert (
        report.component_results,
        report.requirement_results,
        report.total_results,
    ) == (8, 12, 20)


def test_safety_findings_exact() -> None:
    report = bullish_phase15_safety_audit_decision().report_required
    assert report.finding_count == 16
    assert tuple(item.name for item in report.findings) == (PHASE_15_ARCHITECTURE_SAFETY_FINDINGS)
    assert all(item.status == "PASSED" for item in report.findings)


def test_source_counts_preserved() -> None:
    report = bullish_phase15_safety_audit_decision().report_required
    assert report.source_validation_audit_counts == (8, 12, 20, 16)
    assert report.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_gold_scope_and_risk_exact() -> None:
    report = bullish_phase15_safety_audit_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)


def test_safety_gates_and_handoff_exact() -> None:
    report = bullish_phase15_safety_audit_decision().report_required
    assert report.safety_invariants_valid is True
    assert report.future_gates_required is True
    assert report.flat_state_required is True
    assert report.safety_audit_passed is True
    assert report.ready_for_final_handoff is True
    assert report.handoff_status == "READY_FOR_PHASE_15_FINAL_HANDOFF"


def test_all_runtime_statuses_blocked_and_no_effects() -> None:
    report = bullish_phase15_safety_audit_decision().report_required
    assert report.runtime_statuses == ("BLOCKED",) * 8
    assert report.no_real_effects is True


def test_audit_id_is_deterministic() -> None:
    first = bullish_phase15_safety_audit_decision().report_required
    second = bullish_phase15_safety_audit_decision().report_required
    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id


def test_missing_blocked_and_factory_contract() -> None:
    missing = audit_phase15_extension_architecture_safety(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase15_validation_decision_missing",)

    blocked = audit_phase15_extension_architecture_safety(BlockedValidation())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase15_validation_decision_blocked",)
    with pytest.raises(RuntimeError, match="safety audit is blocked"):
        _ = blocked.report_required

    validation = bullish_phase15_architecture_validation_decision()
    first = Phase15ArchitectureSafetyAuditor().audit(validation).report_required
    second = audit_phase15_extension_architecture_safety(validation).report_required
    assert first.audit_id == second.audit_id
