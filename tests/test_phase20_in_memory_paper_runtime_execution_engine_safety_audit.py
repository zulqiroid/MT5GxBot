from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase20_in_memory_paper_runtime_execution_engine_safety_audit import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_NEXT_ALLOWED,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_STATUS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_FINDINGS,
    Phase20InMemoryPaperRuntimeEngineSafetyAudit,
    audit_phase20_in_memory_paper_runtime_execution_engine_safety,
)
from app.strategy.phase20_in_memory_paper_runtime_execution_engine_validation import (
    validate_phase20_in_memory_paper_runtime_execution_engine_blueprint,
)


def _audit() -> Phase20InMemoryPaperRuntimeEngineSafetyAudit:
    return (
        audit_phase20_in_memory_paper_runtime_execution_engine_safety()
        .audit_required
    )


def test_critical_engine_safety_audit_passes() -> None:
    decision = audit_phase20_in_memory_paper_runtime_execution_engine_safety()

    assert decision.passed is True
    assert decision.reason == "PHASE_20_ENGINE_SAFETY_AUDIT_PASSED"
    assert decision.audit_required.status == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_STATUS
    )


def test_critical_validation_lineage_is_preserved() -> None:
    report = (
        validate_phase20_in_memory_paper_runtime_execution_engine_blueprint()
        .report_required
    )
    audit = _audit()

    assert audit.validation_id == report.validation_id
    assert audit.validation_digest == report.validation_digest


def test_critical_all_safety_findings_pass() -> None:
    audit = _audit()

    assert tuple(item.name for item in audit.findings) == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_FINDINGS
    )
    assert audit.finding_count == 12
    assert audit.passed_count == 12
    assert all(item.passed for item in audit.findings)


def test_critical_state_market_and_fill_safety_are_exact() -> None:
    evidence = {item.name: item.evidence for item in _audit().findings}

    assert evidence["MARKET_SCOPE_RESTRICTED"] == (
        "symbol=XAUUSD;timeframes=H4,H1,M15,M5"
    )
    assert evidence["CONSERVATIVE_FILL_POLICY_CONFIRMED"] == (
        "entry_fill_policy=NEXT_EVENT_OPEN_AFTER_SIGNAL_CLOSE;"
        "same_bar_conflict_policy=STOP_FIRST"
    )
    assert evidence["STATE_MACHINE_FAIL_CLOSED"].endswith(
        "FLAT_TERMINATED"
    )


def test_critical_position_risk_and_protection_are_exact() -> None:
    evidence = {item.name: item.evidence for item in _audit().findings}

    assert evidence["POSITION_LIMIT_CONFIRMED"] == (
        "maximum_open_gold_positions=1"
    )
    assert evidence["RISK_LIMITS_CONFIRMED"] == (
        "maximum_open_gold_positions=1;"
        "aggregate_bps=50;"
        "stage_bps=(25, 25)"
    )
    assert evidence[
        "PROTECTION_AND_TERMINAL_FLATNESS_CONFIRMED"
    ] == (
        "oco_required=True;"
        "stop_loss_required=True;"
        "terminal_flat_required=True"
    )


def test_critical_boundaries_and_phase21_remain_blocked() -> None:
    audit = _audit()
    evidence = {item.name: item.evidence for item in audit.findings}

    assert evidence["IN_MEMORY_BOUNDARY_CONFIRMED"] == (
        "in_memory_only=True;"
        "simulation_execution_permitted=True;"
        "engine_invocation_permitted=False"
    )
    assert evidence["REAL_AND_EXTERNAL_EFFECTS_BLOCKED"] == (
        "real_runtime_access_permitted=False;"
        "external_effects_permitted=False"
    )
    assert evidence["PHASE_21_NOT_ADMITTED"] == "phase21_admitted=False"
    assert audit.in_memory_simulation_execution_admitted is True
    assert audit.engine_invocation_permitted is False
    assert audit.real_runtime_access_permitted is False
    assert audit.external_effects_permitted is False
    assert audit.phase21_admitted is False


def test_next_allowed_step_is_final_engine_handoff() -> None:
    assert _audit().next_allowed_step == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_NEXT_ALLOWED
    )


def test_safety_audit_digest_and_id_are_deterministic() -> None:
    first = _audit()
    second = _audit()

    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id
    assert len(first.audit_digest) == 64
    assert first.audit_id.endswith(f"SHA256[{first.audit_digest}]")


def test_invalid_engine_invocation_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot invoke the engine",
    ):
        replace(
            _audit(),
            engine_invocation_permitted=True,
        )


def test_invalid_phase21_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 21 cannot be admitted",
    ):
        replace(
            _audit(),
            phase21_admitted=True,
        )
