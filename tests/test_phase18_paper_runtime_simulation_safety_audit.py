from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase18_paper_runtime_simulation_safety_audit import (
    PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_HANDOFF_STATUS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_STATUS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_FINDINGS,
    Phase18PaperRuntimeSimulationSafetyAuditReport,
    audit_phase18_paper_runtime_simulation_safety,
)
from app.strategy.phase18_paper_runtime_simulation_validation import (
    validate_phase18_paper_runtime_simulation_blueprint,
)


def _report() -> Phase18PaperRuntimeSimulationSafetyAuditReport:
    return audit_phase18_paper_runtime_simulation_safety().report_required


def test_critical_safety_audit_passes() -> None:
    decision = audit_phase18_paper_runtime_simulation_safety()

    assert decision.passed is True
    assert decision.reason == "PHASE_18_SIMULATION_SAFETY_AUDIT_PASSED"
    assert decision.report_required.status == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_STATUS
    )


def test_critical_validation_lineage_is_preserved() -> None:
    validation = (
        validate_phase18_paper_runtime_simulation_blueprint().report_required
    )
    report = _report()

    assert report.validation_id == validation.validation_id
    assert report.validation_digest == validation.validation_digest


def test_critical_all_safety_findings_pass() -> None:
    report = _report()

    assert tuple(item.name for item in report.findings) == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_FINDINGS
    )
    assert report.finding_count == 10
    assert report.passed_count == 10
    assert all(item.passed for item in report.findings)


def test_critical_market_and_risk_safety_is_enforced() -> None:
    evidence = {item.name: item.evidence for item in _report().findings}

    assert "mode=PAPER" in evidence["PAPER_MODE_ENFORCED"]
    assert "symbol=XAUUSD" in evidence["XAUUSD_SCOPE_ENFORCED"]
    assert evidence["CLOSED_CANDLES_ENFORCED"] == (
        "closed_candles_only=True"
    )
    assert evidence["ONE_POSITION_LIMIT_ENFORCED"] == (
        "maximum_open_gold_positions=1"
    )
    assert evidence["FIFTY_BPS_RISK_LIMIT_ENFORCED"] == (
        "aggregate_bps=50;stage_bps=(25, 25)"
    )


def test_critical_real_runtime_access_remains_blocked() -> None:
    report = _report()
    evidence = {item.name: item.evidence for item in report.findings}

    assert "MT5_INITIALIZATION_BLOCKED" in (
        evidence["REAL_RUNTIME_ACCESS_BLOCKED"]
    )
    assert "BROKER_WRITE_BLOCKED" in (
        evidence["REAL_RUNTIME_ACCESS_BLOCKED"]
    )
    assert "LIVE_TRADING_BLOCKED" in (
        evidence["REAL_RUNTIME_ACCESS_BLOCKED"]
    )
    assert report.real_runtime_access_permitted is False


def test_critical_execution_and_phase19_remain_blocked() -> None:
    report = _report()
    evidence = {item.name: item.evidence for item in report.findings}

    assert evidence["SIMULATION_EXECUTION_STILL_BLOCKED"] == (
        "simulation_execution_permitted=False"
    )
    assert evidence["PHASE_19_NOT_ADMITTED"] == "phase19_admitted=False"
    assert report.simulation_execution_permitted is False
    assert report.phase19_admitted is False


def test_handoff_status_is_ready_for_final_handoff() -> None:
    assert _report().handoff_status == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_HANDOFF_STATUS
    )


def test_audit_digest_and_id_are_deterministic() -> None:
    first = _report()
    second = _report()

    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id
    assert len(first.audit_digest) == 64
    assert first.audit_id.endswith(f"SHA256[{first.audit_digest}]")


def test_invalid_real_runtime_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot permit real runtime access",
    ):
        replace(
            _report(),
            real_runtime_access_permitted=True,
        )


def test_invalid_phase19_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 19 cannot be admitted",
    ):
        replace(
            _report(),
            phase19_admitted=True,
        )
