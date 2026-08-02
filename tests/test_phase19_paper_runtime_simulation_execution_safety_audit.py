from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase19_paper_runtime_simulation_execution_blueprint_validation import (
    validate_phase19_paper_runtime_simulation_execution_blueprint,
)
from app.strategy.phase19_paper_runtime_simulation_execution_safety_audit import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_NEXT_ALLOWED,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_STATUS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_FINDINGS,
    Phase19PaperRuntimeSimulationExecutionSafetyAudit,
    audit_phase19_paper_runtime_simulation_execution_safety,
)


def _audit() -> Phase19PaperRuntimeSimulationExecutionSafetyAudit:
    return (
        audit_phase19_paper_runtime_simulation_execution_safety()
        .audit_required
    )


def test_critical_execution_safety_audit_passes() -> None:
    decision = audit_phase19_paper_runtime_simulation_execution_safety()

    assert decision.passed is True
    assert decision.reason == "PHASE_19_EXECUTION_SAFETY_AUDIT_PASSED"
    assert decision.audit_required.status == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_STATUS
    )


def test_critical_validation_lineage_is_preserved() -> None:
    report = (
        validate_phase19_paper_runtime_simulation_execution_blueprint()
        .report_required
    )
    audit = _audit()

    assert audit.validation_id == report.validation_id
    assert audit.validation_digest == report.validation_digest


def test_critical_all_safety_findings_pass() -> None:
    audit = _audit()

    assert tuple(item.name for item in audit.findings) == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_FINDINGS
    )
    assert audit.finding_count == 10
    assert audit.passed_count == 10
    assert all(item.passed for item in audit.findings)


def test_critical_market_position_and_risk_guards_are_exact() -> None:
    evidence = {item.name: item.evidence for item in _audit().findings}

    assert evidence["MARKET_SCOPE_RESTRICTED"] == (
        "symbol=XAUUSD;timeframes=H4,H1,M15,M5"
    )
    assert evidence["POSITION_LIMIT_CONFIRMED"] == (
        "maximum_open_gold_positions=1"
    )
    assert evidence["RISK_LIMITS_CONFIRMED"] == (
        "maximum_open_gold_positions=1;"
        "aggregate_bps=50;"
        "stage_bps=(25, 25)"
    )


def test_critical_protection_and_unsafe_pattern_guards_pass() -> None:
    evidence = {item.name: item.evidence for item in _audit().findings}

    assert evidence["PROTECTION_AND_FLATNESS_CONFIRMED"] == (
        "oco_required=True;"
        "stop_loss_required=True;"
        "terminal_flat_required=True"
    )
    assert evidence["UNSAFE_POSITIONING_PATTERNS_FORBIDDEN"] == (
        "martingale=False;grid=False;no_sl=False"
    )


def test_critical_execution_external_effects_and_phase20_are_blocked() -> None:
    audit = _audit()
    evidence = {item.name: item.evidence for item in audit.findings}

    assert evidence["REAL_AND_EXTERNAL_EFFECTS_BLOCKED"] == (
        "simulation_execution_permitted=False;"
        "real_runtime_access_permitted=False;"
        "external_effects_permitted=False"
    )
    assert evidence["PHASE_20_NOT_ADMITTED"] == "phase20_admitted=False"
    assert audit.simulation_execution_permitted is False
    assert audit.real_runtime_access_permitted is False
    assert audit.external_effects_permitted is False
    assert audit.phase20_admitted is False


def test_next_allowed_step_is_final_execution_handoff() -> None:
    assert _audit().next_allowed_step == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_NEXT_ALLOWED
    )


def test_safety_audit_digest_and_id_are_deterministic() -> None:
    first = _audit()
    second = _audit()

    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id
    assert len(first.audit_digest) == 64
    assert first.audit_id.endswith(f"SHA256[{first.audit_digest}]")


def test_invalid_simulation_execution_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot permit simulation execution",
    ):
        replace(
            _audit(),
            simulation_execution_permitted=True,
        )


def test_invalid_phase20_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 20 cannot be admitted",
    ):
        replace(
            _audit(),
            phase20_admitted=True,
        )
