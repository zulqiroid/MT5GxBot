from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase19_paper_runtime_simulation_execution_final_handoff import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_GUARDS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_NEXT_ALLOWED,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_STATUS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG,
    Phase19PaperRuntimeSimulationExecutionFinalHandoff,
    generate_phase19_paper_runtime_simulation_execution_final_handoff,
)
from app.strategy.phase19_paper_runtime_simulation_execution_safety_audit import (
    audit_phase19_paper_runtime_simulation_execution_safety,
)


def _handoff() -> Phase19PaperRuntimeSimulationExecutionFinalHandoff:
    return (
        generate_phase19_paper_runtime_simulation_execution_final_handoff()
        .handoff_required
    )


def test_critical_final_execution_handoff_is_established() -> None:
    decision = (
        generate_phase19_paper_runtime_simulation_execution_final_handoff()
    )

    assert decision.established is True
    assert decision.reason == "PHASE_19_FINAL_EXECUTION_HANDOFF_ESTABLISHED"
    assert decision.handoff_required.status == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_STATUS
    )


def test_critical_safety_audit_lineage_is_preserved() -> None:
    audit = (
        audit_phase19_paper_runtime_simulation_execution_safety()
        .audit_required
    )
    handoff = _handoff()

    assert handoff.audit_id == audit.audit_id
    assert handoff.audit_digest == audit.audit_digest


def test_critical_all_final_handoff_guards_pass() -> None:
    handoff = _handoff()

    assert tuple(item.name for item in handoff.guards) == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_GUARDS
    )
    assert handoff.guard_count == 10
    assert handoff.passed_count == 10
    assert all(item.passed for item in handoff.guards)


def test_critical_local_release_tag_is_exact() -> None:
    handoff = _handoff()

    assert handoff.release_tag == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG
    )
    assert handoff.release_tag_creation_permitted is True
    assert handoff.remote_push_permitted is False


def test_critical_runtime_and_external_effects_remain_blocked() -> None:
    handoff = _handoff()

    assert handoff.simulation_execution_permitted is False
    assert handoff.real_runtime_access_permitted is False
    assert handoff.external_effects_permitted is False


def test_critical_phase20_remains_not_admitted() -> None:
    assert _handoff().phase20_admitted is False


def test_next_allowed_step_is_local_annotated_tag() -> None:
    assert _handoff().next_allowed_step == (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_NEXT_ALLOWED
    )


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
        match="cannot permit remote push",
    ):
        replace(
            _handoff(),
            remote_push_permitted=True,
        )


def test_invalid_phase20_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 20 cannot be admitted",
    ):
        replace(
            _handoff(),
            phase20_admitted=True,
        )
