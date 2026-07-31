from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase15_final_architecture_handoff import (
    PHASE_15_FINAL_HANDOFF_SOURCE,
    PHASE_15_FINAL_HANDOFF_STATUS,
    PHASE_15_FINAL_STATUS,
    PHASE_15_NEXT_PHASE_STATUS,
    Phase15FinalArchitectureHandoffBuilder,
    build_phase15_final_architecture_handoff,
)
from tests.test_phase15_architecture_safety_audit import (
    bullish_phase15_safety_audit_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedAudit:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase15_final_handoff_decision():
    return build_phase15_final_architecture_handoff(bullish_phase15_safety_audit_decision())


def test_critical_final_handoff_created() -> None:
    decision = bullish_phase15_final_handoff_decision()
    handoff = decision.handoff_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert handoff.phase_status == PHASE_15_FINAL_STATUS
    assert handoff.handoff_status == PHASE_15_FINAL_HANDOFF_STATUS
    assert handoff.handoff_source == PHASE_15_FINAL_HANDOFF_SOURCE


def test_critical_complete_lineage_preserved() -> None:
    audit = bullish_phase15_safety_audit_decision()
    handoff = build_phase15_final_architecture_handoff(audit).handoff_required
    assert handoff.audit_decision is audit
    assert handoff.audit_report is audit.report_required
    assert handoff.validation_decision is audit.report_required.validation_decision
    assert handoff.architecture_blueprint is audit.report_required.architecture_blueprint
    assert handoff.phase14_final_handoff is audit.report_required.phase14_final_handoff
    assert handoff.lineage_preserved is True


def test_critical_result_counts_preserved() -> None:
    handoff = bullish_phase15_final_handoff_decision().handoff_required
    assert (
        handoff.component_results,
        handoff.requirement_results,
        handoff.total_results,
        handoff.architecture_safety_findings,
    ) == (8, 12, 20, 16)
    assert handoff.source_validation_audit_counts == (8, 12, 20, 16)
    assert handoff.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_critical_gold_scope_and_risk_preserved() -> None:
    handoff = bullish_phase15_final_handoff_decision().handoff_required
    assert handoff.symbol == "XAUUSD"
    assert handoff.timeframes == ("H4", "H1", "M15", "M5")
    assert handoff.closed_candles_only is True
    assert handoff.max_gold_positions == 1
    assert handoff.aggregate_risk_budget_bps == 50
    assert handoff.stage_risk_bps == (25, 25)


def test_critical_phase15_complete_and_no_phase16_admission() -> None:
    handoff = bullish_phase15_final_handoff_decision().handoff_required
    assert handoff.phase_status == "PHASE_15_COMPLETE"
    assert handoff.handoff_status == "PHASE_15_EXTENSION_COMPLETE"
    assert handoff.extension_roadmap_complete is True
    assert handoff.next_phase_status == PHASE_15_NEXT_PHASE_STATUS
    assert handoff.next_phase_status == "NOT_DEFINED"
    assert handoff.phase16_admitted is False


def test_critical_all_real_runtime_statuses_blocked() -> None:
    handoff = bullish_phase15_final_handoff_decision().handoff_required
    assert handoff.runtime_statuses == ("BLOCKED",) * 8
    assert handoff.no_real_or_external_effects is True
    assert handoff.phase15_execution_admitted is False


def test_safety_and_future_gates_preserved() -> None:
    handoff = bullish_phase15_final_handoff_decision().handoff_required
    assert handoff.safety_invariants_preserved is True
    assert handoff.future_gates_preserved is True
    assert handoff.phase15_planning_admitted is True
    assert handoff.final_handoff_ready is True


def test_handoff_id_is_deterministic() -> None:
    first = bullish_phase15_final_handoff_decision().handoff_required
    second = bullish_phase15_final_handoff_decision().handoff_required
    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id


def test_missing_and_blocked_audit_are_rejected() -> None:
    missing = build_phase15_final_architecture_handoff(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase15_audit_decision_missing",)

    blocked = build_phase15_final_architecture_handoff(BlockedAudit())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase15_audit_decision_blocked",)
    with pytest.raises(RuntimeError, match="final architecture handoff is blocked"):
        _ = blocked.handoff_required


def test_factory_and_function_match() -> None:
    audit = bullish_phase15_safety_audit_decision()
    first = Phase15FinalArchitectureHandoffBuilder().build(audit).handoff_required
    second = build_phase15_final_architecture_handoff(audit).handoff_required
    assert first.handoff_id == second.handoff_id
