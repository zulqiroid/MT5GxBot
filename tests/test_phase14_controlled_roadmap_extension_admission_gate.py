from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase14_controlled_roadmap_extension_admission_gate import (
    ADMISSION_MODE,
    ADMISSION_SOURCE,
    ADMISSION_STATUS,
    SCHEMA_VERSION,
    Phase14RoadmapExtensionAdmissionGate,
    evaluate_phase14_roadmap_extension,
)
from tests.test_phase13_final_audit_handoff import (
    bullish_phase13_final_handoff_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedSource:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase14_extension_decision():
    return evaluate_phase14_roadmap_extension(bullish_phase13_final_handoff_decision())


def test_static_contract() -> None:
    assert SCHEMA_VERSION == "1.0"
    assert ADMISSION_MODE == "CONTROLLED_ROADMAP_EXTENSION_PLANNING_ONLY"
    assert ADMISSION_STATUS == "ADMITTED"
    assert ADMISSION_SOURCE == "PHASE_13_DEFINED_ROADMAP_COMPLETION"


def test_admission_created() -> None:
    decision = bullish_phase14_extension_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.permit is not None


def test_lineage_preserved() -> None:
    source = bullish_phase13_final_handoff_decision()
    permit = evaluate_phase14_roadmap_extension(source).permit_required
    assert permit.source_decision is source
    assert permit.source_bundle is source.bundle_required


def test_transition_exact() -> None:
    permit = bullish_phase14_extension_decision().permit_required
    assert permit.source_phase == 13
    assert permit.target_phase == 14


def test_planning_only() -> None:
    permit = bullish_phase14_extension_decision().permit_required
    assert permit.requirements_planning_allowed is True
    assert permit.architecture_planning_allowed is True
    assert permit.test_blueprint_planning_allowed is True
    assert permit.safety_gate_planning_allowed is True
    assert permit.phase14_planning_admitted is True
    assert permit.phase14_execution_admitted is False


def test_source_counts_preserved() -> None:
    permit = bullish_phase14_extension_decision().permit_required
    assert (
        permit.runtime_operations,
        permit.blocked_write_operations,
        permit.error_mappings,
        permit.snapshot_mappings,
        permit.snapshot_fields,
        permit.validation_events,
        permit.safety_findings,
    ) == (10, 3, 10, 5, 32, 15, 16)


def test_gold_scope_exact() -> None:
    permit = bullish_phase14_extension_decision().permit_required
    assert permit.symbol == "XAUUSD"
    assert permit.timeframes == ("H4", "H1", "M15", "M5")
    assert permit.closed_candles_only is True
    assert permit.max_gold_positions == 1
    assert permit.aggregate_risk_budget_bps == 50
    assert permit.stage_risk_bps == (25, 25)


def test_safety_invariants_preserved() -> None:
    permit = bullish_phase14_extension_decision().permit_required
    assert permit.oco_required is True
    assert permit.broker_sl_required is True
    assert permit.guards_required is True
    assert permit.flat_state_required is True
    assert permit.martingale_prohibited is True
    assert permit.grid_prohibited is True
    assert permit.no_sl_prohibited is True


def test_future_gates_required() -> None:
    permit = bullish_phase14_extension_decision().permit_required
    assert permit.human_authorization_required is True
    assert permit.runtime_gate_required is True
    assert permit.account_read_gate_required is True
    assert permit.production_gate_required is True


def test_all_runtime_statuses_blocked() -> None:
    permit = bullish_phase14_extension_decision().permit_required
    statuses = (
        permit.real_preflight_status,
        permit.mt5_import_status,
        permit.mt5_initialization_status,
        permit.terminal_status,
        permit.broker_status,
        permit.account_read_status,
        permit.production_status,
        permit.live_status,
    )
    assert statuses == ("BLOCKED",) * 8


def test_permit_id_deterministic() -> None:
    first = bullish_phase14_extension_decision().permit_required
    second = bullish_phase14_extension_decision().permit_required
    assert first.permit_digest == second.permit_digest
    assert first.permit_id == second.permit_id


def test_source_not_mutated() -> None:
    source = bullish_phase13_final_handoff_decision()
    bundle = source.bundle_required
    before = (
        bundle.next_phase_number,
        bundle.phase14_admitted,
        bundle.defined_roadmap_complete,
    )
    _ = evaluate_phase14_roadmap_extension(source).permit_required
    after = (
        bundle.next_phase_number,
        bundle.phase14_admitted,
        bundle.defined_roadmap_complete,
    )
    assert after == before


def test_missing_source_blocks() -> None:
    decision = evaluate_phase14_roadmap_extension(None)
    assert decision.is_allowed is False
    assert decision.blockers == ("phase13_handoff_decision_missing",)


def test_blocked_source_blocks() -> None:
    decision = evaluate_phase14_roadmap_extension(BlockedSource())
    assert decision.is_allowed is False
    assert decision.blockers == ("phase13_handoff_decision_blocked",)
    with pytest.raises(RuntimeError, match="admission is blocked"):
        _ = decision.permit_required


def test_factory_and_function_match() -> None:
    source = bullish_phase13_final_handoff_decision()
    first = Phase14RoadmapExtensionAdmissionGate().evaluate(source).permit_required
    second = evaluate_phase14_roadmap_extension(source).permit_required
    assert first.permit_id == second.permit_id
