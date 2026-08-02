from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase19_paper_runtime_simulation_execution_blueprint import (
    build_phase19_paper_runtime_simulation_execution_blueprint,
)
from app.strategy.phase19_paper_runtime_simulation_execution_blueprint_validation import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_CHECKS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_NEXT_ALLOWED,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_STATUS,
    Phase19PaperRuntimeSimulationExecutionValidationReport,
    validate_phase19_paper_runtime_simulation_execution_blueprint,
)


def _report() -> Phase19PaperRuntimeSimulationExecutionValidationReport:
    return (
        validate_phase19_paper_runtime_simulation_execution_blueprint()
        .report_required
    )


def test_critical_execution_blueprint_validation_passes() -> None:
    decision = validate_phase19_paper_runtime_simulation_execution_blueprint()

    assert decision.valid is True
    assert decision.reason == "PHASE_19_EXECUTION_BLUEPRINT_VALIDATED"
    assert decision.report_required.status == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_STATUS
    )


def test_critical_blueprint_lineage_is_preserved() -> None:
    blueprint = (
        build_phase19_paper_runtime_simulation_execution_blueprint()
        .blueprint_required
    )
    report = _report()

    assert report.blueprint_id == blueprint.blueprint_id
    assert report.blueprint_digest == blueprint.blueprint_digest


def test_critical_all_validation_checks_pass() -> None:
    report = _report()

    assert tuple(item.name for item in report.checks) == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_CHECKS
    )
    assert report.check_count == 10
    assert report.passed_count == 10
    assert all(item.passed for item in report.checks)


def test_critical_component_and_requirement_counts_are_exact() -> None:
    evidence = {item.name: item.evidence for item in _report().checks}

    assert evidence["COMPONENT_CONTRACT_COMPLETE"] == "components=10"
    assert evidence["REQUIREMENT_CONTRACT_COMPLETE"] == "requirements=12"


def test_critical_market_and_risk_scope_is_exact() -> None:
    evidence = {item.name: item.evidence for item in _report().checks}

    assert evidence["MARKET_SCOPE_EXACT"] == (
        "symbol=XAUUSD;timeframes=H4,H1,M15,M5"
    )
    assert evidence["POSITION_AND_RISK_LIMITS_EXACT"] == (
        "maximum_open_gold_positions=1;"
        "aggregate_bps=50;"
        "stage_bps=(25, 25)"
    )


def test_critical_execution_and_phase20_remain_blocked() -> None:
    report = _report()
    evidence = {item.name: item.evidence for item in report.checks}

    assert evidence["REAL_AND_SIMULATION_EXECUTION_BLOCKED"] == (
        "simulation_execution_permitted=False;"
        "real_runtime_access_permitted=False"
    )
    assert evidence["PHASE_20_NOT_ADMITTED"] == "phase20_admitted=False"
    assert report.simulation_execution_permitted is False
    assert report.real_runtime_access_permitted is False
    assert report.phase20_admitted is False


def test_next_allowed_step_is_execution_safety_audit() -> None:
    assert _report().next_allowed_step == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_NEXT_ALLOWED
    )


def test_validation_digest_and_id_are_deterministic() -> None:
    first = _report()
    second = _report()

    assert first.validation_digest == second.validation_digest
    assert first.validation_id == second.validation_id
    assert len(first.validation_digest) == 64
    assert first.validation_id.endswith(f"SHA256[{first.validation_digest}]")


def test_invalid_real_runtime_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot permit real runtime access",
    ):
        replace(
            _report(),
            real_runtime_access_permitted=True,
        )


def test_invalid_phase20_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 20 cannot be admitted",
    ):
        replace(
            _report(),
            phase20_admitted=True,
        )
