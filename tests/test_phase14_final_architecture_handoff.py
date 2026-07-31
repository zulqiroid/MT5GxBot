from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase14_final_architecture_handoff import (
    PHASE_14_FINAL_HANDOFF_EVIDENCE_SOURCE,
    PHASE_14_FINAL_HANDOFF_MODE,
    PHASE_14_FINAL_HANDOFF_PHASE_STATUS,
    PHASE_14_FINAL_HANDOFF_SCHEMA_VERSION,
    PHASE_14_FINAL_HANDOFF_STATUS,
    Phase14FinalArchitectureHandoffFactory,
    create_phase14_final_architecture_handoff,
)
from tests.test_phase14_extension_architecture_safety_audit import (
    bullish_phase14_safety_audit_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedAudit:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase14_final_handoff_decision():
    return create_phase14_final_architecture_handoff(bullish_phase14_safety_audit_decision())


def test_static_final_handoff_contract() -> None:
    assert PHASE_14_FINAL_HANDOFF_SCHEMA_VERSION == "1.0"
    assert PHASE_14_FINAL_HANDOFF_PHASE_STATUS == "PHASE_14_COMPLETE"
    assert PHASE_14_FINAL_HANDOFF_STATUS == "PHASE_14_EXTENSION_COMPLETE"
    assert (
        PHASE_14_FINAL_HANDOFF_MODE
        == "HUMAN_AUTHORIZED_READ_ONLY_PREFLIGHT_OBSERVABILITY_PLANNING_ONLY"
    )
    assert (
        PHASE_14_FINAL_HANDOFF_EVIDENCE_SOURCE
        == "DETERMINISTIC_ARCHITECTURE_VALIDATION_AND_SAFETY_AUDIT_ONLY"
    )


def test_final_handoff_created() -> None:
    decision = bullish_phase14_final_handoff_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.bundle is not None


def test_complete_lineage_preserved() -> None:
    audit = bullish_phase14_safety_audit_decision()
    bundle = create_phase14_final_architecture_handoff(audit).bundle_required
    assert bundle.audit_decision is audit
    assert bundle.audit_report is audit.report_required
    assert bundle.validation_report is audit.report_required.validation_report
    assert bundle.architecture_blueprint is audit.report_required.blueprint
    assert bundle.admission_permit is audit.report_required.admission_permit
    assert bundle.phase13_handoff_bundle is audit.report_required.phase13_handoff
    assert bundle.lineage_preserved is True


def test_phase_completion_exact() -> None:
    bundle = bullish_phase14_final_handoff_decision().bundle_required
    assert bundle.phase_number == 14
    assert bundle.source_phase_number == 13
    assert bundle.next_phase_number is None
    assert bundle.phase_status == "PHASE_14_COMPLETE"
    assert bundle.handoff_status == "PHASE_14_EXTENSION_COMPLETE"
    assert bundle.phase_complete is True
    assert bundle.extension_roadmap_complete is True
    assert bundle.phase15_admitted is False


def test_validation_and_audit_counts_exact() -> None:
    bundle = bullish_phase14_final_handoff_decision().bundle_required
    assert bundle.component_result_count == 8
    assert bundle.requirement_result_count == 12
    assert bundle.total_validation_result_count == 20
    assert bundle.architecture_safety_finding_count == 16


def test_source_evidence_counts_exact() -> None:
    bundle = bullish_phase14_final_handoff_decision().bundle_required
    assert (
        bundle.runtime_operation_count,
        bundle.blocked_write_operation_count,
        bundle.error_mapping_count,
        bundle.snapshot_mapping_count,
        bundle.total_snapshot_field_count,
        bundle.prior_validation_event_count,
        bundle.prior_runtime_safety_finding_count,
    ) == (10, 3, 10, 5, 32, 15, 16)


def test_gold_scope_exact() -> None:
    bundle = bullish_phase14_final_handoff_decision().bundle_required
    assert bundle.symbol == "XAUUSD"
    assert bundle.timeframes == ("H4", "H1", "M15", "M5")
    assert bundle.closed_candles_only is True
    assert bundle.max_gold_positions == 1
    assert bundle.aggregate_risk_budget_bps == 50
    assert bundle.stage_risk_bps == (25, 25)


def test_architecture_validation_and_audit_invariants() -> None:
    bundle = bullish_phase14_final_handoff_decision().bundle_required
    assert bundle.architecture_blueprint_valid is True
    assert bundle.deterministic_validation_passed is True
    assert bundle.architecture_safety_audit_passed is True


def test_risk_and_execution_safety_invariants() -> None:
    bundle = bullish_phase14_final_handoff_decision().bundle_required
    assert bundle.risk_contract_valid is True
    assert bundle.oco_broker_sl_guards_valid is True
    assert bundle.terminal_flat_state_valid is True
    assert bundle.future_gates_required is True


def test_all_real_runtime_statuses_blocked() -> None:
    bundle = bullish_phase14_final_handoff_decision().bundle_required
    statuses = (
        bundle.real_preflight_execution_status,
        bundle.mt5_import_status,
        bundle.mt5_initialization_status,
        bundle.terminal_connection_status,
        bundle.broker_access_status,
        bundle.real_account_read_status,
        bundle.production_activation_status,
        bundle.live_execution_status,
    )
    assert statuses == ("BLOCKED",) * 8


def test_no_real_effects_and_no_phase15() -> None:
    bundle = bullish_phase14_final_handoff_decision().bundle_required
    assert bundle.no_real_or_external_effects is True
    assert bundle.phase15_admitted is False
    assert bundle.next_phase_number is None


def test_handoff_id_is_deterministic() -> None:
    first = bullish_phase14_final_handoff_decision().bundle_required
    second = bullish_phase14_final_handoff_decision().bundle_required
    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id


def test_source_audit_is_not_mutated() -> None:
    source = bullish_phase14_safety_audit_decision()
    audit = source.report_required
    before = (
        audit.audit_status,
        audit.handoff_status,
        audit.ready_for_final_handoff,
        audit.no_real_effects,
    )
    _ = create_phase14_final_architecture_handoff(source).bundle_required
    after = (
        audit.audit_status,
        audit.handoff_status,
        audit.ready_for_final_handoff,
        audit.no_real_effects,
    )
    assert after == before


def test_missing_or_blocked_audit_blocks() -> None:
    missing = create_phase14_final_architecture_handoff(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase14_safety_audit_decision_missing",)

    blocked = create_phase14_final_architecture_handoff(BlockedAudit())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase14_safety_audit_decision_blocked",)
    with pytest.raises(RuntimeError, match="handoff is blocked"):
        _ = blocked.bundle_required


def test_factory_and_function_match() -> None:
    audit = bullish_phase14_safety_audit_decision()
    first = Phase14FinalArchitectureHandoffFactory().create(audit).bundle_required
    second = create_phase14_final_architecture_handoff(audit).bundle_required
    assert first.handoff_id == second.handoff_id
