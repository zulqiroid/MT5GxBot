from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase15_extension_architecture_blueprint import (
    PHASE_15_BLUEPRINT_COMPONENTS,
    PHASE_15_BLUEPRINT_NEXT_ALLOWED,
    PHASE_15_BLUEPRINT_REQUIREMENTS,
    Phase15ExtensionArchitecturePlanner,
    build_phase15_extension_architecture,
)
from tests.test_phase15_controlled_roadmap_extension_admission_gate import (
    bullish_phase15_extension_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedAdmission:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase15_architecture_decision():
    return build_phase15_extension_architecture(bullish_phase15_extension_decision())


def test_blueprint_created() -> None:
    decision = bullish_phase15_architecture_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.blueprint_required.blueprint_status == "BLUEPRINT_READY"


def test_lineage_preserved() -> None:
    admission = bullish_phase15_extension_decision()
    blueprint = build_phase15_extension_architecture(admission).blueprint_required
    assert blueprint.admission_decision is admission
    assert blueprint.admission_permit is admission.permit_required
    assert blueprint.phase14_final_handoff is admission.permit_required.source_bundle
    assert (blueprint.source_phase, blueprint.target_phase) == (14, 15)


def test_component_requirement_contract_exact() -> None:
    blueprint = bullish_phase15_architecture_decision().blueprint_required
    assert blueprint.components == PHASE_15_BLUEPRINT_COMPONENTS
    assert blueprint.requirements == PHASE_15_BLUEPRINT_REQUIREMENTS
    assert (blueprint.component_count, blueprint.requirement_count) == (8, 12)


def test_gold_scope_and_risk_exact() -> None:
    blueprint = bullish_phase15_architecture_decision().blueprint_required
    assert blueprint.symbol == "XAUUSD"
    assert blueprint.timeframes == ("H4", "H1", "M15", "M5")
    assert blueprint.closed_candles_only is True
    assert blueprint.max_gold_positions == 1
    assert blueprint.aggregate_risk_budget_bps == 50
    assert blueprint.stage_risk_bps == (25, 25)


def test_safety_and_future_gates_preserved() -> None:
    blueprint = bullish_phase15_architecture_decision().blueprint_required
    assert blueprint.oco_required is True
    assert blueprint.broker_stop_loss_required is True
    assert blueprint.guards_required is True
    assert blueprint.terminal_flat_state_required is True
    assert blueprint.martingale_prohibited is True
    assert blueprint.grid_prohibited is True
    assert blueprint.no_stop_loss_prohibited is True
    assert blueprint.explicit_human_authorization_required is True
    assert blueprint.separate_runtime_execution_gate_required is True
    assert blueprint.separate_real_account_read_gate_required is True
    assert blueprint.separate_production_gate_required is True


def test_planning_only_and_next_step() -> None:
    blueprint = bullish_phase15_architecture_decision().blueprint_required
    assert blueprint.planning_admitted is True
    assert blueprint.execution_admitted is False
    assert blueprint.ready_for_fake_validation is True
    assert blueprint.next_allowed_step == PHASE_15_BLUEPRINT_NEXT_ALLOWED


def test_all_runtime_statuses_blocked() -> None:
    blueprint = bullish_phase15_architecture_decision().blueprint_required
    statuses = (
        blueprint.real_preflight_execution_status,
        blueprint.mt5_import_status,
        blueprint.mt5_initialization_status,
        blueprint.terminal_connection_status,
        blueprint.broker_access_status,
        blueprint.real_account_read_status,
        blueprint.production_activation_status,
        blueprint.live_execution_status,
    )
    assert statuses == ("BLOCKED",) * 8
    assert blueprint.no_real_or_external_effects is True


def test_blockers_and_deterministic_id() -> None:
    first = bullish_phase15_architecture_decision().blueprint_required
    second = bullish_phase15_architecture_decision().blueprint_required
    assert first.blueprint_id == second.blueprint_id

    missing = build_phase15_extension_architecture(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase15_admission_decision_missing",)

    blocked = Phase15ExtensionArchitecturePlanner().build(BlockedAdmission())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase15_admission_decision_blocked",)
    with pytest.raises(RuntimeError, match="blueprint is blocked"):
        _ = blocked.blueprint_required
