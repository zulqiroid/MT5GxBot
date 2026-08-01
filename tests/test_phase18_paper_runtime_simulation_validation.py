from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase18_paper_runtime_simulation_blueprint import (
    PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES,
    build_phase18_paper_runtime_simulation_blueprint,
)
from app.strategy.phase18_paper_runtime_simulation_validation import (
    PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_CHECKS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_NEXT_ALLOWED,
    PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_OUTCOME,
    PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_STATUS,
    Phase18PaperRuntimeSimulationValidationReport,
    validate_phase18_paper_runtime_simulation_blueprint,
)


def _report() -> Phase18PaperRuntimeSimulationValidationReport:
    return validate_phase18_paper_runtime_simulation_blueprint().report_required


def test_critical_validation_passes() -> None:
    decision = validate_phase18_paper_runtime_simulation_blueprint()

    assert decision.valid is True
    assert decision.reason == "PHASE_18_BLUEPRINT_VALIDATION_PASSED"
    assert decision.report_required.status == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_STATUS
    )
    assert decision.report_required.outcome == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_OUTCOME
    )


def test_critical_validation_preserves_blueprint_lineage() -> None:
    blueprint = (
        build_phase18_paper_runtime_simulation_blueprint().blueprint_required
    )
    report = _report()

    assert report.blueprint_id == blueprint.blueprint_id
    assert report.blueprint_digest == blueprint.blueprint_digest


def test_critical_all_validation_checks_pass() -> None:
    report = _report()

    assert tuple(item.name for item in report.results) == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_CHECKS
    )
    assert report.result_count == 10
    assert report.passed_count == 10
    assert all(item.passed for item in report.results)


def test_critical_component_and_requirement_evidence_is_exact() -> None:
    report = _report()
    evidence = {item.name: item.evidence for item in report.results}

    assert evidence["COMPONENT_CONTRACT_COMPLETE"] == "components=8"
    assert evidence["REQUIREMENT_CONTRACT_COMPLETE"] == "requirements=12"


def test_critical_market_and_risk_evidence_is_exact() -> None:
    report = _report()
    evidence = {item.name: item.evidence for item in report.results}

    assert evidence["MARKET_SCOPE_EXACT"] == (
        "mode=PAPER;symbol=XAUUSD;timeframes=H4,H1,M15,M5"
    )
    assert evidence["RISK_BUDGET_EXACT"] == (
        "aggregate_bps=50;stage_bps=(25, 25)"
    )
    assert evidence["POSITION_LIMIT_EXACT"] == (
        "maximum_open_gold_positions=1"
    )


def test_critical_real_runtime_and_execution_remain_blocked() -> None:
    report = _report()
    evidence = {item.name: item.evidence for item in report.results}

    assert evidence["REAL_RUNTIME_STATUSES_BLOCKED"] == ",".join(
        PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES
    )
    assert evidence["SIMULATION_EXECUTION_BLOCKED"] == (
        "simulation_execution_permitted=False"
    )
    assert evidence["PHASE_19_BLOCKED"] == "phase19_admitted=False"


def test_next_allowed_step_is_safety_audit() -> None:
    assert _report().next_allowed_step == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_NEXT_ALLOWED
    )


def test_validation_digest_and_id_are_deterministic() -> None:
    first = _report()
    second = _report()

    assert first.validation_digest == second.validation_digest
    assert first.validation_id == second.validation_id
    assert len(first.validation_digest) == 64
    assert first.validation_id.endswith(f"SHA256[{first.validation_digest}]")


def test_phase19_is_not_admitted() -> None:
    report = _report()

    assert report.no_real_or_external_effects is True
    assert report.phase19_admitted is False


def test_invalid_phase19_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 19 cannot be admitted",
    ):
        replace(
            _report(),
            phase19_admitted=True,
        )
