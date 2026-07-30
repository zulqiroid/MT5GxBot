from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase14_controlled_extension_architecture_blueprint import (
    PHASE_14_BLUEPRINT_COMPONENTS,
    PHASE_14_BLUEPRINT_MODE,
    PHASE_14_BLUEPRINT_REQUIREMENTS,
    PHASE_14_BLUEPRINT_SCHEMA_VERSION,
    PHASE_14_BLUEPRINT_SOURCE,
    PHASE_14_BLUEPRINT_STATUS,
    Phase14ExtensionArchitectureFactory,
    create_phase14_extension_architecture,
)
from tests.test_phase14_controlled_roadmap_extension_admission_gate import (
    bullish_phase14_extension_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedAdmission:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase14_architecture_decision():
    return create_phase14_extension_architecture(bullish_phase14_extension_decision())


def test_static_contract() -> None:
    assert PHASE_14_BLUEPRINT_SCHEMA_VERSION == "1.0"
    assert PHASE_14_BLUEPRINT_STATUS == "BLUEPRINT_READY"
    assert (
        PHASE_14_BLUEPRINT_MODE
        == "HUMAN_AUTHORIZED_READ_ONLY_PREFLIGHT_OBSERVABILITY_PLANNING_ONLY"
    )
    assert PHASE_14_BLUEPRINT_SOURCE == "PHASE_14_EXTENSION_ADMISSION_ONLY"


def test_blueprint_created() -> None:
    decision = bullish_phase14_architecture_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.blueprint is not None


def test_lineage_preserved() -> None:
    admission = bullish_phase14_extension_decision()
    blueprint = create_phase14_extension_architecture(admission).blueprint_required
    assert blueprint.admission_decision is admission
    assert blueprint.admission_permit is admission.permit_required
    assert blueprint.phase13_handoff_bundle is admission.permit_required.source_bundle


def test_status_mode_source_exact() -> None:
    blueprint = bullish_phase14_architecture_decision().blueprint_required
    assert blueprint.blueprint_status == "BLUEPRINT_READY"
    assert blueprint.blueprint_mode == PHASE_14_BLUEPRINT_MODE
    assert blueprint.blueprint_source == PHASE_14_BLUEPRINT_SOURCE
    assert blueprint.ready_for_fake_validation is True


def test_components_exact() -> None:
    blueprint = bullish_phase14_architecture_decision().blueprint_required
    assert len(blueprint.components) == 8
    assert blueprint.components == PHASE_14_BLUEPRINT_COMPONENTS


def test_requirements_exact() -> None:
    blueprint = bullish_phase14_architecture_decision().blueprint_required
    assert len(blueprint.requirements) == 12
    assert blueprint.requirements == PHASE_14_BLUEPRINT_REQUIREMENTS


def test_source_counts_preserved() -> None:
    blueprint = bullish_phase14_architecture_decision().blueprint_required
    assert (
        blueprint.runtime_operations,
        blueprint.blocked_write_operations,
        blueprint.error_mappings,
        blueprint.snapshot_mappings,
        blueprint.snapshot_fields,
        blueprint.validation_events,
        blueprint.safety_findings,
    ) == (10, 3, 10, 5, 32, 15, 16)


def test_gold_scope_exact() -> None:
    blueprint = bullish_phase14_architecture_decision().blueprint_required
    assert blueprint.symbol == "XAUUSD"
    assert blueprint.timeframes == ("H4", "H1", "M15", "M5")
    assert blueprint.closed_candles_only is True
    assert blueprint.max_gold_positions == 1
    assert blueprint.aggregate_risk_budget_bps == 50
    assert blueprint.stage_risk_bps == (25, 25)


def test_safety_invariants_preserved() -> None:
    blueprint = bullish_phase14_architecture_decision().blueprint_required
    assert blueprint.oco_required is True
    assert blueprint.broker_sl_required is True
    assert blueprint.guards_required is True
    assert blueprint.flat_state_required is True
    assert blueprint.martingale_prohibited is True
    assert blueprint.grid_prohibited is True
    assert blueprint.no_sl_prohibited is True


def test_future_gates_required() -> None:
    blueprint = bullish_phase14_architecture_decision().blueprint_required
    assert blueprint.human_authorization_required is True
    assert blueprint.runtime_gate_required is True
    assert blueprint.account_read_gate_required is True
    assert blueprint.production_gate_required is True


def test_only_fake_validation_and_audit_allowed() -> None:
    blueprint = bullish_phase14_architecture_decision().blueprint_required
    assert blueprint.fake_validation_allowed is True
    assert blueprint.safety_audit_allowed is True
    assert blueprint.real_execution_allowed is False
    assert blueprint.real_account_read_allowed is False
    assert blueprint.external_write_allowed is False
    assert blueprint.production_allowed is False
    assert blueprint.live_execution_allowed is False


def test_all_runtime_statuses_blocked() -> None:
    blueprint = bullish_phase14_architecture_decision().blueprint_required
    statuses = (
        blueprint.real_preflight_status,
        blueprint.mt5_import_status,
        blueprint.mt5_initialization_status,
        blueprint.terminal_status,
        blueprint.broker_status,
        blueprint.account_read_status,
        blueprint.production_status,
        blueprint.live_status,
    )
    assert statuses == ("BLOCKED",) * 8


def test_blueprint_id_deterministic() -> None:
    first = bullish_phase14_architecture_decision().blueprint_required
    second = bullish_phase14_architecture_decision().blueprint_required
    assert first.blueprint_digest == second.blueprint_digest
    assert first.blueprint_id == second.blueprint_id


def test_missing_admission_blocks() -> None:
    decision = create_phase14_extension_architecture(None)
    assert decision.is_allowed is False
    assert decision.blockers == ("phase14_admission_decision_missing",)


def test_blocked_admission_blocks() -> None:
    decision = create_phase14_extension_architecture(BlockedAdmission())
    assert decision.is_allowed is False
    assert decision.blockers == ("phase14_admission_decision_blocked",)
    with pytest.raises(RuntimeError, match="blueprint is blocked"):
        _ = decision.blueprint_required


def test_factory_and_function_match() -> None:
    admission = bullish_phase14_extension_decision()
    first = Phase14ExtensionArchitectureFactory().create(admission).blueprint_required
    second = create_phase14_extension_architecture(admission).blueprint_required
    assert first.blueprint_id == second.blueprint_id
