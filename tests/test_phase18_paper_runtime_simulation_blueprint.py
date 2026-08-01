from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase18_deterministic_paper_runtime_simulation_admission import (
    admit_phase18_deterministic_paper_runtime_simulation,
)
from app.strategy.phase18_paper_runtime_simulation_blueprint import (
    PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES,
    PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_NEXT_ALLOWED,
    PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_STATUS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS,
    Phase18PaperRuntimeSimulationBlueprintPlanner,
    build_phase18_paper_runtime_simulation_blueprint,
)


def _blueprint():
    return build_phase18_paper_runtime_simulation_blueprint().blueprint_required


def test_critical_blueprint_is_ready() -> None:
    decision = build_phase18_paper_runtime_simulation_blueprint()

    assert decision.ready is True
    assert decision.reason == "PHASE_18_BLUEPRINT_READY_FOR_VALIDATION"
    assert decision.blueprint_required.status == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_STATUS
    )


def test_critical_blueprint_preserves_admission_lineage() -> None:
    permit = (
        admit_phase18_deterministic_paper_runtime_simulation().permit_required
    )
    blueprint = _blueprint()

    assert blueprint.admission_id == permit.admission_id
    assert blueprint.admission_digest == permit.admission_digest


def test_critical_component_contract_is_exact() -> None:
    blueprint = _blueprint()

    assert tuple(item.name for item in blueprint.components) == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS
    )
    assert blueprint.component_count == 8


def test_critical_requirement_contract_is_exact() -> None:
    blueprint = _blueprint()

    assert tuple(item.name for item in blueprint.requirements) == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS
    )
    assert blueprint.requirement_count == 12


def test_critical_risk_and_market_scope_are_exact() -> None:
    blueprint = _blueprint()

    assert blueprint.mode == "PAPER"
    assert blueprint.symbol == "XAUUSD"
    assert blueprint.timeframes == ("H4", "H1", "M15", "M5")
    assert blueprint.closed_candles_only is True
    assert blueprint.maximum_open_gold_positions == 1
    assert blueprint.aggregate_risk_budget_bps == 50
    assert blueprint.stage_risk_bps == (25, 25)


def test_critical_runtime_effects_remain_blocked() -> None:
    blueprint = _blueprint()

    assert blueprint.blocked_runtime_statuses == (
        PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES
    )
    assert blueprint.simulation_execution_permitted is False
    assert blueprint.phase19_admitted is False


def test_next_allowed_step_is_validation() -> None:
    assert _blueprint().next_allowed_step == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_NEXT_ALLOWED
    )


def test_component_and_requirement_ordinals_are_sequential() -> None:
    blueprint = _blueprint()

    assert tuple(item.ordinal for item in blueprint.components) == tuple(
        range(1, 9)
    )
    assert tuple(item.ordinal for item in blueprint.requirements) == tuple(
        range(1, 13)
    )


def test_blueprint_digest_and_id_are_deterministic() -> None:
    first = _blueprint()
    second = _blueprint()

    assert first.blueprint_digest == second.blueprint_digest
    assert first.blueprint_id == second.blueprint_id
    assert len(first.blueprint_digest) == 64
    assert first.blueprint_id.endswith(f"SHA256[{first.blueprint_digest}]")


def test_invalid_execution_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot permit simulation execution",
    ):
        replace(
            _blueprint(),
            simulation_execution_permitted=True,
        )


def test_planner_type_is_available() -> None:
    assert Phase18PaperRuntimeSimulationBlueprintPlanner is not None
