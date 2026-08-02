from __future__ import annotations

from dataclasses import replace

import pytest

from app.strategy.phase20_in_memory_paper_runtime_execution_engine_final_handoff import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_GUARDS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_NEXT_ALLOWED,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_STATUS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_RELEASE_TAG,
    Phase20InMemoryPaperRuntimeEngineFinalHandoff,
    generate_phase20_in_memory_paper_runtime_execution_engine_final_handoff,
)
from app.strategy.phase20_in_memory_paper_runtime_execution_engine_safety_audit import (
    audit_phase20_in_memory_paper_runtime_execution_engine_safety,
)


def _handoff() -> Phase20InMemoryPaperRuntimeEngineFinalHandoff:
    return (
        generate_phase20_in_memory_paper_runtime_execution_engine_final_handoff()
        .handoff_required
    )


def test_critical_final_engine_handoff_is_established() -> None:
    decision = (
        generate_phase20_in_memory_paper_runtime_execution_engine_final_handoff()
    )

    assert decision.established is True
    assert decision.reason == "PHASE_20_FINAL_ENGINE_HANDOFF_ESTABLISHED"
    assert decision.handoff_required.status == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_STATUS
    )


def test_critical_safety_audit_lineage_is_preserved() -> None:
    audit = (
        audit_phase20_in_memory_paper_runtime_execution_engine_safety()
        .audit_required
    )
    handoff = _handoff()

    assert handoff.audit_id == audit.audit_id
    assert handoff.audit_digest == audit.audit_digest


def test_critical_all_final_handoff_guards_pass() -> None:
    handoff = _handoff()

    assert tuple(item.name for item in handoff.guards) == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_GUARDS
    )
    assert handoff.guard_count == 12
    assert handoff.passed_count == 12
    assert all(item.passed for item in handoff.guards)


def test_critical_local_release_tag_is_exact() -> None:
    handoff = _handoff()

    assert handoff.release_tag == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_RELEASE_TAG
    )
    assert handoff.release_tag_creation_permitted is True
    assert handoff.remote_push_permitted is False


def test_critical_in_memory_admission_and_engine_block_are_preserved() -> None:
    handoff = _handoff()

    assert handoff.in_memory_simulation_execution_admitted is True
    assert handoff.engine_invocation_permitted is False


def test_critical_real_external_and_phase21_boundaries_remain_blocked() -> None:
    handoff = _handoff()

    assert handoff.real_runtime_access_permitted is False
    assert handoff.external_effects_permitted is False
    assert handoff.phase21_admitted is False


def test_next_allowed_step_is_local_annotated_tag() -> None:
    assert _handoff().next_allowed_step == (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_NEXT_ALLOWED
    )


def test_handoff_digest_and_id_are_deterministic() -> None:
    first = _handoff()
    second = _handoff()

    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id
    assert len(first.handoff_digest) == 64
    assert first.handoff_id.endswith(f"SHA256[{first.handoff_digest}]")


def test_invalid_engine_invocation_permission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cannot invoke the engine",
    ):
        replace(
            _handoff(),
            engine_invocation_permitted=True,
        )


def test_invalid_phase21_admission_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Phase 21 cannot be admitted",
    ):
        replace(
            _handoff(),
            phase21_admitted=True,
        )
