from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase20_in_memory_paper_runtime_execution_engine_blueprint import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES,
    build_phase20_in_memory_paper_runtime_execution_engine_blueprint,
)
from app.strategy.phase20_in_memory_paper_runtime_execution_engine_validation import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_CHECKS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_NEXT_ALLOWED,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_STATUS,
    Phase20InMemoryPaperRuntimeEngineValidationReport,
    validate_phase20_in_memory_paper_runtime_execution_engine_blueprint,
)


def _report() -> Phase20InMemoryPaperRuntimeEngineValidationReport:
    return (
        validate_phase20_in_memory_paper_runtime_execution_engine_blueprint()
        .report_required
    )


def test_critical_engine_blueprint_validation_passes() -> None:
    decision = (
        validate_phase20_in_memory_paper_runtime_execution_engine_blueprint()
    )

    assert decision.valid is True
    assert decision.reason == "PHASE_20_ENGINE_BLUEPRINT_VALIDATED"
    assert decision.report_required.status == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_STATUS
    )


def test_critical_blueprint_lineage_is_preserved() -> None:
    blueprint = (
        build_phase20_in_memory_paper_runtime_execution_engine_blueprint()
        .blueprint_required
    )
    report = _report()

    assert report.blueprint_id == blueprint.blueprint_id
    assert report.blueprint_digest == blueprint.blueprint_digest


def test_critical_all_validation_checks_pass() -> None:
    report = _report()

    assert tuple(item.name for item in report.checks) == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_CHECKS
    )
    assert report.check_count == 12
    assert report.passed_count == 12
    assert all(item.passed for item in report.checks)


def test_critical_component_invariant_and_state_contracts_are_exact() -> None:
    evidence = {item.name: item.evidence for item in _report().checks}

    assert evidence["COMPONENT_CHAIN_COMPLETE"] == "components=12"
    assert evidence["INVARIANT_CONTRACT_COMPLETE"] == "invariants=14"
    assert evidence["STATE_MACHINE_CONTRACT_EXACT"] == (
        f"states={','.join(PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES)}"
    )


def test_critical_market_fill_and_risk_contracts_are_exact() -> None:
    evidence = {item.name: item.evidence for item in _report().checks}

    assert evidence["MARKET_SCOPE_EXACT"] == (
        "symbol=XAUUSD;timeframes=H4,H1,M15,M5"
    )
    assert evidence["FILL_POLICIES_CONSERVATIVE"] == (
        "entry_fill_policy=NEXT_EVENT_OPEN_AFTER_SIGNAL_CLOSE;"
        "same_bar_conflict_policy=STOP_FIRST"
    )
    assert evidence["POSITION_AND_RISK_LIMITS_EXACT"] == (
        "maximum_open_gold_positions=1;"
        "aggregate_bps=50;"
        "stage_bps=(25, 25)"
    )


def test_critical_execution_boundary_and_phase21_remain_blocked() -> None:
    report = _report()
    evidence = {item.name: item.evidence for item in report.checks}

    assert evidence["IN_MEMORY_AND_REAL_EFFECT_BOUNDARIES_PRESERVED"] == (
        "in_memory_only=True;"
        "simulation_execution_permitted=True;"
        "engine_invocation_permitted=False;"
        "real_runtime_access_permitted=False;"
        "external_effects_permitted=False"
    )
    assert evidence["PHASE_21_NOT_ADMITTED"] == "phase21_admitted=False"
    assert report.in_memory_simulation_execution_admitted is True
    assert report.engine_invocation_permitted is False
    assert report.real_runtime_access_permitted is False
    assert report.external_effects_permitted is False
    assert report.phase21_admitted is False


def test_next_allowed_step_is_engine_safety_audit() -> None:
    assert _report().next_allowed_step == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_NEXT_ALLOWED
    )


def test_validation_digest_and_id_are_deterministic() -> None:
    first = _report()
    second = _report()

    assert first.validation_digest == second.validation_digest
    assert first.validation_id == second.validation_id
    assert len(first.validation_digest) == 64
    assert first.validation_id.endswith(f"SHA256[{first.validation_digest}]")


def test_invalid_engine_invocation_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot invoke the engine",
    ):
        replace(
            _report(),
            engine_invocation_permitted=True,
        )


def test_invalid_phase21_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 21 cannot be admitted",
    ):
        replace(
            _report(),
            phase21_admitted=True,
        )
