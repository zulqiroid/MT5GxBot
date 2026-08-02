from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase19_paper_runtime_simulation_execution_admission import (
    admit_phase19_paper_runtime_simulation_execution_planning,
)
from app.strategy.phase19_paper_runtime_simulation_execution_blueprint import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_NEXT_ALLOWED,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_STATUS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_REQUIREMENTS,
    Phase19PaperRuntimeSimulationExecutionBlueprint,
    build_phase19_paper_runtime_simulation_execution_blueprint,
)


def _blueprint() -> Phase19PaperRuntimeSimulationExecutionBlueprint:
    return build_phase19_paper_runtime_simulation_execution_blueprint().blueprint_required


def test_critical_execution_blueprint_is_ready() -> None:
    decision = build_phase19_paper_runtime_simulation_execution_blueprint()
    assert decision.ready is True
    assert decision.reason == "PHASE_19_EXECUTION_BLUEPRINT_READY"
    assert decision.blueprint_required.status == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_STATUS


def test_critical_admission_lineage_is_preserved() -> None:
    admission = admit_phase19_paper_runtime_simulation_execution_planning().admission_required
    blueprint = _blueprint()
    assert blueprint.admission_id == admission.admission_id
    assert blueprint.admission_digest == admission.admission_digest


def test_critical_all_components_are_ordered_and_complete() -> None:
    blueprint = _blueprint()
    assert tuple(item.name for item in blueprint.components) == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS
    assert tuple(item.order for item in blueprint.components) == tuple(range(1, 11))
    assert blueprint.component_count == 10


def test_critical_all_requirements_are_complete() -> None:
    blueprint = _blueprint()
    assert tuple(item.name for item in blueprint.requirements) == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_REQUIREMENTS
    assert blueprint.requirement_count == 12


def test_critical_market_and_risk_scope_is_exact() -> None:
    blueprint = _blueprint()
    assert blueprint.symbol == "XAUUSD"
    assert blueprint.timeframes == ("H4", "H1", "M15", "M5")
    assert blueprint.closed_candles_only is True
    assert blueprint.maximum_open_gold_positions == 1
    assert blueprint.aggregate_risk_budget_bps == 50
    assert blueprint.stage_risk_bps == (25, 25)


def test_critical_execution_and_real_access_remain_blocked() -> None:
    blueprint = _blueprint()
    assert blueprint.simulation_execution_permitted is False
    assert blueprint.real_runtime_access_permitted is False
    assert blueprint.phase20_admitted is False


def test_next_allowed_step_is_blueprint_validation() -> None:
    assert _blueprint().next_allowed_step == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_NEXT_ALLOWED


def test_blueprint_digest_and_id_are_deterministic() -> None:
    first = _blueprint()
    second = _blueprint()
    assert first.blueprint_digest == second.blueprint_digest
    assert first.blueprint_id == second.blueprint_id
    assert len(first.blueprint_digest) == 64
    assert first.blueprint_id.endswith(f"SHA256[{first.blueprint_digest}]")


def test_invalid_simulation_execution_permission_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot permit simulation execution"):
        replace(_blueprint(), simulation_execution_permitted=True)


def test_invalid_phase20_admission_is_rejected() -> None:
    with pytest.raises(ValueError, match="Phase 20 cannot be admitted"):
        replace(_blueprint(), phase20_admitted=True)
