from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase20_in_memory_paper_runtime_execution_admission import (
    admit_phase20_in_memory_paper_runtime_simulation_execution,
)
from app.strategy.phase20_in_memory_paper_runtime_execution_engine_blueprint import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_NEXT_ALLOWED,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_STATUS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_INVARIANTS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES,
    Phase20InMemoryPaperRuntimeEngineBlueprint,
    build_phase20_in_memory_paper_runtime_execution_engine_blueprint,
)


def _blueprint() -> Phase20InMemoryPaperRuntimeEngineBlueprint:
    return (
        build_phase20_in_memory_paper_runtime_execution_engine_blueprint()
        .blueprint_required
    )


def test_critical_engine_blueprint_is_ready() -> None:
    decision = (
        build_phase20_in_memory_paper_runtime_execution_engine_blueprint()
    )

    assert decision.ready is True
    assert decision.reason == "PHASE_20_ENGINE_BLUEPRINT_READY"
    assert decision.blueprint_required.status == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_STATUS
    )


def test_critical_admission_lineage_is_preserved() -> None:
    admission = (
        admit_phase20_in_memory_paper_runtime_simulation_execution()
        .admission_required
    )
    blueprint = _blueprint()

    assert blueprint.admission_id == admission.admission_id
    assert blueprint.admission_digest == admission.admission_digest


def test_critical_components_are_complete_and_ordered() -> None:
    blueprint = _blueprint()

    assert tuple(item.name for item in blueprint.components) == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS
    )
    assert tuple(item.order for item in blueprint.components) == tuple(
        range(1, 13)
    )
    assert blueprint.component_count == 12


def test_critical_invariants_are_complete() -> None:
    blueprint = _blueprint()

    assert tuple(item.name for item in blueprint.invariants) == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_INVARIANTS
    )
    assert blueprint.invariant_count == 14


def test_critical_state_fill_and_market_contracts_are_exact() -> None:
    blueprint = _blueprint()

    assert blueprint.symbol == "XAUUSD"
    assert blueprint.timeframes == ("H4", "H1", "M15", "M5")
    assert blueprint.states == PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES
    assert blueprint.signal_evaluation_policy == "CANDLE_CLOSE_ONLY"
    assert blueprint.entry_fill_policy == (
        "NEXT_EVENT_OPEN_AFTER_SIGNAL_CLOSE"
    )
    assert blueprint.same_bar_conflict_policy == "STOP_FIRST"


def test_critical_execution_scope_is_in_memory_and_fail_closed() -> None:
    blueprint = _blueprint()

    assert blueprint.in_memory_only is True
    assert blueprint.simulation_execution_permitted is True
    assert blueprint.engine_invocation_permitted is False
    assert blueprint.real_runtime_access_permitted is False
    assert blueprint.external_effects_permitted is False
    assert blueprint.phase21_admitted is False


def test_next_allowed_step_is_engine_validation() -> None:
    assert _blueprint().next_allowed_step == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_NEXT_ALLOWED
    )


def test_blueprint_digest_and_id_are_deterministic() -> None:
    first = _blueprint()
    second = _blueprint()

    assert first.blueprint_digest == second.blueprint_digest
    assert first.blueprint_id == second.blueprint_id
    assert len(first.blueprint_digest) == 64
    assert first.blueprint_id.endswith(f"SHA256[{first.blueprint_digest}]")


def test_engine_invocation_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot invoke the engine",
    ):
        replace(
            _blueprint(),
            engine_invocation_permitted=True,
        )


def test_phase21_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 21 cannot be admitted",
    ):
        replace(
            _blueprint(),
            phase21_admitted=True,
        )
