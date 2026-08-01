from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase18_paper_runtime_simulation_final_handoff import (
    PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_GUARDS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_NEXT_ALLOWED,
    PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_STATUS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG,
    Phase18PaperRuntimeSimulationFinalHandoff,
    generate_phase18_paper_runtime_simulation_final_handoff,
)
from app.strategy.phase18_paper_runtime_simulation_safety_audit import (
    audit_phase18_paper_runtime_simulation_safety,
)


def _handoff() -> Phase18PaperRuntimeSimulationFinalHandoff:
    return (
        generate_phase18_paper_runtime_simulation_final_handoff()
        .handoff_required
    )


def test_critical_final_handoff_is_established() -> None:
    decision = generate_phase18_paper_runtime_simulation_final_handoff()

    assert decision.ready is True
    assert decision.reason == "PHASE_18_FINAL_HANDOFF_ESTABLISHED"
    assert decision.handoff_required.status == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_STATUS
    )


def test_critical_safety_audit_lineage_is_preserved() -> None:
    audit = audit_phase18_paper_runtime_simulation_safety().report_required
    handoff = _handoff()

    assert handoff.audit_id == audit.audit_id
    assert handoff.audit_digest == audit.audit_digest


def test_critical_all_final_handoff_guards_pass() -> None:
    handoff = _handoff()

    assert tuple(item.name for item in handoff.guards) == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_GUARDS
    )
    assert handoff.guard_count == 10
    assert handoff.passed_count == 10
    assert all(item.passed for item in handoff.guards)


def test_critical_paper_gold_and_closed_candle_scope_is_preserved() -> None:
    evidence = {item.name: item.evidence for item in _handoff().guards}

    assert "mode=PAPER" in evidence["PAPER_MODE_SCOPE_CONFIRMED"]
    assert "symbol=XAUUSD" in evidence["XAUUSD_SCOPE_CONFIRMED"]
    assert evidence["CLOSED_CANDLE_SCOPE_CONFIRMED"] == (
        "closed_candles_only=True"
    )


def test_critical_risk_and_position_limits_are_preserved() -> None:
    evidence = {item.name: item.evidence for item in _handoff().guards}

    assert evidence["RISK_AND_POSITION_LIMITS_CONFIRMED"] == (
        "maximum_open_gold_positions=1;"
        "aggregate_bps=50;stage_bps=(25, 25)"
    )


def test_critical_all_runtime_execution_remains_blocked() -> None:
    handoff = _handoff()

    assert handoff.simulation_execution_permitted is False
    assert handoff.real_runtime_access_permitted is False
    assert handoff.remote_push_permitted is False
    assert handoff.phase19_admitted is False


def test_local_release_tag_is_the_only_next_step() -> None:
    handoff = _handoff()

    assert handoff.next_allowed_step == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_NEXT_ALLOWED
    )
    assert handoff.release_tag == (
        PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG
    )
    assert handoff.release_tag_creation_permitted is True


def test_handoff_digest_and_id_are_deterministic() -> None:
    first = _handoff()
    second = _handoff()

    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id
    assert len(first.handoff_digest) == 64
    assert first.handoff_id.endswith(f"SHA256[{first.handoff_digest}]")


def test_invalid_remote_push_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot permit a remote push",
    ):
        replace(
            _handoff(),
            remote_push_permitted=True,
        )


def test_invalid_phase19_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 19 cannot be admitted",
    ):
        replace(
            _handoff(),
            phase19_admitted=True,
        )
