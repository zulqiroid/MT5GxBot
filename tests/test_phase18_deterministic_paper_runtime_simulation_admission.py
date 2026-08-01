from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase18_deterministic_paper_runtime_simulation_admission import (
    PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMISSION_SCHEMA_VERSION,
    PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED,
    PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_BLUEPRINT,
    Phase18DeterministicPaperRuntimeSimulationAdmissionPermit,
    admit_phase18_deterministic_paper_runtime_simulation,
)


def _permit() -> Phase18DeterministicPaperRuntimeSimulationAdmissionPermit:
    return admit_phase18_deterministic_paper_runtime_simulation().permit_required


def test_critical_phase18_admission_is_created() -> None:
    decision = admit_phase18_deterministic_paper_runtime_simulation()

    assert decision.admitted is True
    assert decision.reason == "PHASE_18_ADMISSION_READY_FOR_BLUEPRINT"
    assert decision.permit_required.phase_status == (
        PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED
    )


def test_critical_phase18_is_planning_only() -> None:
    permit = _permit()

    assert permit.planning_permitted is True
    assert permit.simulation_execution_permitted is False
    assert permit.next_allowed_step == (
        PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_BLUEPRINT
    )


def test_critical_gold_scope_and_closed_candles_are_exact() -> None:
    permit = _permit()

    assert permit.symbol == "XAUUSD"
    assert permit.timeframes == ("H4", "H1", "M15", "M5")
    assert permit.closed_candles_only is True


def test_critical_risk_invariants_are_exact() -> None:
    permit = _permit()

    assert permit.maximum_open_gold_positions == 1
    assert permit.aggregate_risk_budget_bps == 50
    assert permit.stage_risk_bps == (25, 25)


def test_critical_execution_safety_is_fail_closed() -> None:
    permit = _permit()

    assert permit.oco_required is True
    assert permit.broker_stop_loss_required is True
    assert permit.terminal_flat_required is True
    assert permit.martingale_forbidden is True
    assert permit.grid_forbidden is True
    assert permit.no_stop_loss_forbidden is True


def test_critical_all_real_runtime_statuses_are_blocked() -> None:
    permit = _permit()

    assert permit.blocked_runtime_statuses == (
        "REAL_ENV_BLOCKED",
        "MT5_INITIALIZATION_BLOCKED",
        "TERMINAL_CONNECTION_BLOCKED",
        "BROKER_READ_BLOCKED",
        "BROKER_WRITE_BLOCKED",
        "ACCOUNT_ACCESS_BLOCKED",
        "PRODUCTION_BLOCKED",
        "LIVE_TRADING_BLOCKED",
    )
    assert permit.no_real_or_external_effects is True


def test_phase19_is_not_admitted() -> None:
    assert _permit().phase19_admitted is False


def test_admission_digest_and_id_are_deterministic() -> None:
    first = _permit()
    second = _permit()

    assert first.admission_digest == second.admission_digest
    assert first.admission_id == second.admission_id
    assert len(first.admission_digest) == 64
    assert first.admission_id.endswith(f"SHA256[{first.admission_digest}]")


def test_schema_version_is_exact() -> None:
    assert _permit().schema_version == (
        PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMISSION_SCHEMA_VERSION
    )


def test_invalid_execution_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot permit simulation execution",
    ):
        replace(
            _permit(),
            simulation_execution_permitted=True,
        )
