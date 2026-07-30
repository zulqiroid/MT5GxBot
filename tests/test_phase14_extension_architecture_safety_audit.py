from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase14_extension_architecture_safety_audit import (
    AUDIT_SOURCE,
    AUDIT_STATUS,
    FINDINGS,
    HANDOFF_STATUS,
    SCHEMA_VERSION,
    Phase14ArchitectureSafetyAuditor,
    audit_phase14_architecture_safety,
)
from tests.test_phase14_deterministic_extension_architecture_validation import (
    bullish_phase14_architecture_validation_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedValidation:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase14_safety_audit_decision():
    return audit_phase14_architecture_safety(bullish_phase14_architecture_validation_decision())


def test_static_contract() -> None:
    assert SCHEMA_VERSION == "1.0"
    assert AUDIT_STATUS == "PASSED"
    assert HANDOFF_STATUS == "READY_FOR_PHASE_14_FINAL_HANDOFF"
    assert AUDIT_SOURCE == "DETERMINISTIC_ARCHITECTURE_VALIDATION_EVIDENCE_ONLY"


def test_audit_created() -> None:
    decision = bullish_phase14_safety_audit_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None


def test_lineage_preserved() -> None:
    validation = bullish_phase14_architecture_validation_decision()
    report = audit_phase14_architecture_safety(validation).report_required
    assert report.validation_decision is validation
    assert report.validation_report is validation.report_required
    assert report.lineage_preserved is True


def test_status_and_handoff_exact() -> None:
    report = bullish_phase14_safety_audit_decision().report_required
    assert report.audit_status == "PASSED"
    assert report.handoff_status == "READY_FOR_PHASE_14_FINAL_HANDOFF"
    assert report.safety_audit_passed is True
    assert report.ready_for_final_handoff is True


def test_validation_counts_exact() -> None:
    report = bullish_phase14_safety_audit_decision().report_required
    assert (report.component_results, report.requirement_results, report.total_results) == (
        8,
        12,
        20,
    )


def test_source_evidence_exact() -> None:
    report = bullish_phase14_safety_audit_decision().report_required
    assert (
        report.runtime_operations,
        report.blocked_writes,
        report.error_mappings,
        report.snapshot_mappings,
        report.snapshot_fields,
        report.prior_events,
        report.prior_findings,
    ) == (10, 3, 10, 5, 32, 15, 16)


def test_findings_complete() -> None:
    report = bullish_phase14_safety_audit_decision().report_required
    assert report.finding_count == 16
    assert tuple(item.name for item in report.findings) == FINDINGS
    assert all(item.passed for item in report.findings)


def test_validation_flags_true() -> None:
    report = bullish_phase14_safety_audit_decision().report_required
    assert report.result_order_valid is True
    assert report.fake_only is True


def test_gold_scope_exact() -> None:
    report = bullish_phase14_safety_audit_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_bps == 50
    assert report.stage_risk_bps == (25, 25)


def test_safety_and_gates_true() -> None:
    report = bullish_phase14_safety_audit_decision().report_required
    assert report.safety_invariants_valid is True
    assert report.future_gates_required is True
    assert report.flat_state_required is True


def test_all_runtime_statuses_blocked() -> None:
    report = bullish_phase14_safety_audit_decision().report_required
    statuses = (
        report.real_preflight_status,
        report.mt5_import_status,
        report.mt5_initialization_status,
        report.terminal_status,
        report.broker_status,
        report.account_read_status,
        report.production_status,
        report.live_status,
    )
    assert statuses == ("BLOCKED",) * 8
    assert report.no_real_effects is True


def test_audit_id_deterministic() -> None:
    first = bullish_phase14_safety_audit_decision().report_required
    second = bullish_phase14_safety_audit_decision().report_required
    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id


def test_missing_validation_blocks() -> None:
    decision = audit_phase14_architecture_safety(None)
    assert decision.is_allowed is False
    assert decision.blockers == ("phase14_validation_decision_missing",)


def test_blocked_validation_blocks() -> None:
    decision = audit_phase14_architecture_safety(BlockedValidation())
    assert decision.is_allowed is False
    assert decision.blockers == ("phase14_validation_decision_blocked",)
    with pytest.raises(RuntimeError, match="safety audit is blocked"):
        _ = decision.report_required


def test_factory_and_function_match() -> None:
    validation = bullish_phase14_architecture_validation_decision()
    first = Phase14ArchitectureSafetyAuditor().audit(validation).report_required
    second = audit_phase14_architecture_safety(validation).report_required
    assert first.audit_id == second.audit_id
