from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase18_paper_runtime_simulation_final_handoff import (
    generate_phase18_paper_runtime_simulation_final_handoff,
)
from app.strategy.phase19_paper_runtime_simulation_execution_admission import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_NEXT_ALLOWED,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_REQUIREMENTS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_STATUS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLOCKED_CAPABILITIES,
    Phase19PaperRuntimeSimulationExecutionAdmission,
    admit_phase19_paper_runtime_simulation_execution_planning,
)


def _admission() -> Phase19PaperRuntimeSimulationExecutionAdmission:
    return (
        admit_phase19_paper_runtime_simulation_execution_planning()
        .admission_required
    )


def test_critical_phase19_execution_planning_is_admitted() -> None:
    decision = admit_phase19_paper_runtime_simulation_execution_planning()

    assert decision.admitted is True
    assert decision.reason == "PHASE_19_EXECUTION_PLANNING_ADMITTED"
    assert decision.admission_required.status == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_STATUS
    )


def test_critical_phase18_handoff_lineage_is_preserved() -> None:
    handoff = (
        generate_phase18_paper_runtime_simulation_final_handoff()
        .handoff_required
    )
    admission = _admission()

    assert admission.phase18_handoff_id == handoff.handoff_id
    assert admission.phase18_handoff_digest == handoff.handoff_digest


def test_critical_all_admission_requirements_are_present() -> None:
    admission = _admission()

    assert tuple(item.name for item in admission.requirements) == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_REQUIREMENTS
    )
    assert admission.requirement_count == 10


def test_critical_market_scope_is_exact() -> None:
    admission = _admission()

    assert admission.symbol == "XAUUSD"
    assert admission.timeframes == ("H4", "H1", "M15", "M5")
    assert admission.closed_candles_only is True
    assert admission.maximum_open_gold_positions == 1


def test_critical_risk_scope_is_exact() -> None:
    admission = _admission()

    assert admission.aggregate_risk_budget_bps == 50
    assert admission.stage_risk_bps == (25, 25)


def test_critical_all_execution_and_real_access_remain_blocked() -> None:
    admission = _admission()

    assert admission.blocked_capabilities == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLOCKED_CAPABILITIES
    )
    assert admission.planning_permitted is True
    assert admission.simulation_execution_permitted is False
    assert admission.real_runtime_access_permitted is False
    assert admission.phase20_admitted is False


def test_next_allowed_step_is_execution_blueprint() -> None:
    assert _admission().next_allowed_step == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_NEXT_ALLOWED
    )


def test_admission_digest_and_id_are_deterministic() -> None:
    first = _admission()
    second = _admission()

    assert first.admission_digest == second.admission_digest
    assert first.admission_id == second.admission_id
    assert len(first.admission_digest) == 64
    assert first.admission_id.endswith(f"SHA256[{first.admission_digest}]")


def test_simulation_execution_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot permit simulation execution",
    ):
        replace(
            _admission(),
            simulation_execution_permitted=True,
        )


def test_phase20_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 20 cannot be admitted",
    ):
        replace(
            _admission(),
            phase20_admitted=True,
        )
