from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase13_final_audit_handoff import (
    PHASE_13_FINAL_HANDOFF_EVIDENCE_SOURCE,
    PHASE_13_FINAL_HANDOFF_MODE,
    PHASE_13_FINAL_HANDOFF_PHASE_STATUS,
    PHASE_13_FINAL_HANDOFF_SCHEMA_VERSION,
    PHASE_13_FINAL_HANDOFF_STATUS,
    StrategyPhase13FinalAuditHandoffFactory,
    create_phase13_final_audit_handoff,
)
from tests.test_phase13_controlled_read_only_runtime_safety_audit import (
    bullish_phase13_runtime_safety_audit_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedAuditDecision:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase13_final_handoff_decision():
    return create_phase13_final_audit_handoff(bullish_phase13_runtime_safety_audit_decision())


def test_static_final_handoff_contract_is_stable() -> None:
    assert PHASE_13_FINAL_HANDOFF_SCHEMA_VERSION == "1.0"
    assert PHASE_13_FINAL_HANDOFF_PHASE_STATUS == "PHASE_13_COMPLETE"
    assert PHASE_13_FINAL_HANDOFF_STATUS == "DEFINED_ROADMAP_COMPLETE"
    assert PHASE_13_FINAL_HANDOFF_MODE == "CONTROLLED_READ_ONLY_RUNTIME_BOUNDARY_CONTRACT_ONLY"
    assert PHASE_13_FINAL_HANDOFF_EVIDENCE_SOURCE == "DETERMINISTIC_FAKE_BOUNDARY_EVIDENCE_ONLY"


def test_phase13_final_handoff_is_created() -> None:
    decision = bullish_phase13_final_handoff_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.bundle is not None


def test_complete_lineage_is_preserved() -> None:
    bundle = bullish_phase13_final_handoff_decision().bundle_required
    assert bundle.lineage_preserved is True
    assert bundle.audit_decision.report_required is bundle.audit_report
    assert bundle.audit_report.validation_report is bundle.validation_report
    assert bundle.audit_report.runtime_boundary_contract is bundle.runtime_boundary_contract
    assert bundle.audit_report.admission_permit is bundle.admission_permit
    assert bundle.audit_report.phase12_handoff_bundle is bundle.phase12_handoff_bundle


def test_phase_and_roadmap_completion_are_exact() -> None:
    bundle = bullish_phase13_final_handoff_decision().bundle_required
    assert bundle.phase_number == 13
    assert bundle.source_phase_number == 12
    assert bundle.next_phase_number is None
    assert bundle.phase_status == "PHASE_13_COMPLETE"
    assert bundle.handoff_status == "DEFINED_ROADMAP_COMPLETE"
    assert bundle.phase_complete is True
    assert bundle.defined_roadmap_complete is True
    assert bundle.phase14_admitted is False


def test_operation_error_snapshot_and_evidence_counts_are_exact() -> None:
    bundle = bullish_phase13_final_handoff_decision().bundle_required
    assert bundle.runtime_operation_count == 10
    assert bundle.blocked_write_operation_count == 3
    assert bundle.error_mapping_count == 10
    assert bundle.snapshot_mapping_count == 5
    assert bundle.total_snapshot_field_count == 32
    assert bundle.validation_event_count == 15
    assert bundle.runtime_safety_finding_count == 16


def test_boundary_and_snapshot_contracts_are_valid() -> None:
    bundle = bullish_phase13_final_handoff_decision().bundle_required
    assert bundle.boundary_contract_valid is True
    assert bundle.snapshot_contract_valid is True


def test_gold_risk_scope_is_exact() -> None:
    bundle = bullish_phase13_final_handoff_decision().bundle_required
    assert bundle.symbol == "XAUUSD"
    assert bundle.timeframes == ("H4", "H1", "M15", "M5")
    assert bundle.closed_candles_only is True
    assert bundle.max_gold_positions == 1
    assert bundle.aggregate_risk_budget_bps == 50
    assert bundle.stage_risk_bps == (25, 25)
    assert bundle.risk_contract_valid is True


def test_oco_guards_flat_state_and_future_gates_are_valid() -> None:
    bundle = bullish_phase13_final_handoff_decision().bundle_required
    assert bundle.oco_broker_sl_guards_valid is True
    assert bundle.terminal_flat_state_valid is True
    assert bundle.future_gates_required is True
    assert bundle.runtime_safety_audit_passed is True


def test_all_runtime_statuses_remain_blocked() -> None:
    bundle = bullish_phase13_final_handoff_decision().bundle_required
    assert bundle.real_preflight_execution_status == "BLOCKED"
    assert bundle.mt5_import_status == "BLOCKED"
    assert bundle.mt5_initialization_status == "BLOCKED"
    assert bundle.terminal_connection_status == "BLOCKED"
    assert bundle.broker_access_status == "BLOCKED"
    assert bundle.real_account_read_status == "BLOCKED"
    assert bundle.production_activation_status == "BLOCKED"
    assert bundle.live_execution_status == "BLOCKED"
    assert bundle.no_real_or_external_effects is True


def test_final_handoff_id_is_deterministic() -> None:
    first = bullish_phase13_final_handoff_decision().bundle_required
    second = bullish_phase13_final_handoff_decision().bundle_required
    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id


def test_missing_audit_blocks_handoff() -> None:
    decision = create_phase13_final_audit_handoff(None)
    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("runtime_safety_audit_decision_missing",)


def test_blocked_audit_blocks_handoff() -> None:
    decision = create_phase13_final_audit_handoff(FakeBlockedAuditDecision())
    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("runtime_safety_audit_decision_blocked",)
    with pytest.raises(RuntimeError, match="handoff is blocked"):
        _ = decision.bundle_required


def test_factory_and_function_api_match() -> None:
    audit = bullish_phase13_runtime_safety_audit_decision()
    factory = StrategyPhase13FinalAuditHandoffFactory().create(audit).bundle_required
    function = create_phase13_final_audit_handoff(audit).bundle_required
    assert factory.handoff_id == function.handoff_id


def test_final_handoff_does_not_mutate_audit() -> None:
    decision = bullish_phase13_runtime_safety_audit_decision()
    audit = decision.report_required
    before = (
        audit.audit_status,
        audit.handoff_status,
        audit.validation_event_count,
        audit.finding_count,
        audit.no_real_or_external_effects,
    )
    _ = create_phase13_final_audit_handoff(decision).bundle_required
    after = (
        audit.audit_status,
        audit.handoff_status,
        audit.validation_event_count,
        audit.finding_count,
        audit.no_real_or_external_effects,
    )
    assert after == before
