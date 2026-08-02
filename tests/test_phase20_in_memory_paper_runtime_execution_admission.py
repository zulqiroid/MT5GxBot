from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase19_paper_runtime_simulation_execution_final_handoff import (
    generate_phase19_paper_runtime_simulation_execution_final_handoff,
)
from app.strategy.phase20_in_memory_paper_runtime_execution_admission import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_NEXT_ALLOWED,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_REQUIREMENTS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_STATUS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_BLOCKED_CAPABILITIES,
    Phase20InMemoryPaperRuntimeExecutionAdmission,
    admit_phase20_in_memory_paper_runtime_simulation_execution,
)


def _admission() -> Phase20InMemoryPaperRuntimeExecutionAdmission:
    return (
        admit_phase20_in_memory_paper_runtime_simulation_execution()
        .admission_required
    )


def test_critical_in_memory_execution_is_admitted() -> None:
    decision = admit_phase20_in_memory_paper_runtime_simulation_execution()

    assert decision.admitted is True
    assert decision.reason == "PHASE_20_IN_MEMORY_EXECUTION_ADMITTED"
    assert decision.admission_required.status == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_STATUS
    )


def test_critical_phase19_handoff_lineage_is_preserved() -> None:
    handoff = (
        generate_phase19_paper_runtime_simulation_execution_final_handoff()
        .handoff_required
    )
    admission = _admission()

    assert admission.phase19_handoff_id == handoff.handoff_id
    assert admission.phase19_handoff_digest == handoff.handoff_digest


def test_critical_requirements_are_complete() -> None:
    admission = _admission()

    assert tuple(item.name for item in admission.requirements) == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_REQUIREMENTS
    )
    assert admission.requirement_count == 12


def test_critical_market_position_and_risk_scope_is_exact() -> None:
    admission = _admission()

    assert admission.symbol == "XAUUSD"
    assert admission.timeframes == ("H4", "H1", "M15", "M5")
    assert admission.closed_candles_only is True
    assert admission.maximum_open_gold_positions == 1
    assert admission.aggregate_risk_budget_bps == 50
    assert admission.stage_risk_bps == (25, 25)


def test_critical_only_in_memory_simulation_execution_is_permitted() -> None:
    admission = _admission()

    assert admission.in_memory_only is True
    assert admission.simulation_execution_permitted is True
    assert admission.real_runtime_access_permitted is False
    assert admission.external_effects_permitted is False


def test_critical_real_capabilities_and_phase21_remain_blocked() -> None:
    admission = _admission()

    assert admission.blocked_capabilities == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_BLOCKED_CAPABILITIES
    )
    assert admission.remote_push_permitted is False
    assert admission.phase21_admitted is False


def test_next_allowed_step_is_execution_engine_blueprint() -> None:
    assert _admission().next_allowed_step == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_NEXT_ALLOWED
    )


def test_admission_digest_and_id_are_deterministic() -> None:
    first = _admission()
    second = _admission()

    assert first.admission_digest == second.admission_digest
    assert first.admission_id == second.admission_id
    assert len(first.admission_digest) == 64
    assert first.admission_id.endswith(f"SHA256[{first.admission_digest}]")


def test_external_effect_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot permit external effects",
    ):
        replace(
            _admission(),
            external_effects_permitted=True,
        )


def test_phase21_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 21 cannot be admitted",
    ):
        replace(
            _admission(),
            phase21_admitted=True,
        )
