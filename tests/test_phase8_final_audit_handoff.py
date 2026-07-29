from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase8_final_audit_handoff import (
    PHASE_8_FINAL_AUDIT_HANDOFF_COMPLETE,
    PHASE_8_FINAL_AUDIT_HANDOFF_READY_FOR_PHASE_9,
    PHASE_8_FINAL_AUDIT_HANDOFF_SCHEMA_VERSION,
    StrategyPhase8FinalAuditHandoffFactory,
    create_phase8_final_audit_handoff,
)
from tests.test_phase8_offline_replay_terminal_exhaustion_audit import (
    bullish_terminal_exhaustion_audit_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedTerminalAuditDecision:
    is_allowed: bool = False


def bullish_phase8_final_handoff_decision():
    return create_phase8_final_audit_handoff(bullish_terminal_exhaustion_audit_decision())


def test_schema_version_is_stable() -> None:
    assert PHASE_8_FINAL_AUDIT_HANDOFF_SCHEMA_VERSION == "1.0"


def test_phase8_final_handoff_is_created() -> None:
    decision = bullish_phase8_final_handoff_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.bundle is not None


def test_handoff_preserves_terminal_lineage() -> None:
    audit_decision = bullish_terminal_exhaustion_audit_decision()
    report = audit_decision.report_required
    completion_state = report.completion_state

    bundle = create_phase8_final_audit_handoff(audit_decision).bundle_required

    assert bundle.terminal_audit_decision is audit_decision
    assert bundle.terminal_audit_report is report
    assert bundle.completion_state is completion_state
    assert bundle.prior_reusable_state is completion_state.source_state


def test_phase_and_version_contract_is_exact() -> None:
    bundle = bullish_phase8_final_handoff_decision().bundle_required

    assert bundle.phase_number == 8
    assert bundle.prior_state_version == 13
    assert bundle.terminal_state_version == 14


def test_global_event_totals_are_exact() -> None:
    bundle = bullish_phase8_final_handoff_decision().bundle_required

    assert bundle.total_event_count == 800
    assert bundle.prior_consumed_count == 230
    assert bundle.completed_remaining_event_count == 570
    assert bundle.final_consumed_count == 800
    assert bundle.final_remaining_count == 0
    assert bundle.exact_total_preserved is True


def test_global_sequence_boundaries_are_exact() -> None:
    bundle = bullish_phase8_final_handoff_decision().bundle_required

    assert bundle.first_event_sequence_index == 0
    assert bundle.prior_last_consumed_sequence_index == 229
    assert bundle.completion_first_sequence_index == 230
    assert bundle.final_last_consumed_sequence_index == 799
    assert bundle.next_event_sequence_index is None
    assert bundle.prior_boundary_contiguous is True
    assert bundle.completed_sequence_contiguous is True


def test_terminal_chunk_and_lifecycle_contract_is_exact() -> None:
    bundle = bullish_phase8_final_handoff_decision().bundle_required

    assert bundle.bounded_chunk_count == 18
    assert bundle.bounded_chunk_limit == 32
    assert bundle.terminal_lifecycle == "COMPLETED"
    assert bundle.terminal_counters_valid is True


def test_terminal_audit_and_reentry_contract_is_exact() -> None:
    bundle = bullish_phase8_final_handoff_decision().bundle_required

    assert bundle.terminal_audit_status == "PASSED"
    assert bundle.terminal_reentry_status == "BLOCKED"
    assert bundle.terminal_reentry_blocked is True


def test_phase8_is_complete_and_ready_for_phase9() -> None:
    bundle = bullish_phase8_final_handoff_decision().bundle_required

    assert bundle.phase_status == PHASE_8_FINAL_AUDIT_HANDOFF_COMPLETE
    assert bundle.handoff_status == PHASE_8_FINAL_AUDIT_HANDOFF_READY_FOR_PHASE_9
    assert bundle.phase_complete is True
    assert bundle.ready_for_phase_9 is True


def test_handoff_id_is_deterministic() -> None:
    first = bullish_phase8_final_handoff_decision().bundle_required
    second = bullish_phase8_final_handoff_decision().bundle_required

    assert first.handoff_digest == second.handoff_digest
    assert first.handoff_id == second.handoff_id


def test_missing_terminal_audit_blocks_handoff() -> None:
    decision = create_phase8_final_audit_handoff(None)

    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("terminal_audit_decision_missing",)


def test_blocked_terminal_audit_blocks_handoff() -> None:
    decision = create_phase8_final_audit_handoff(FakeBlockedTerminalAuditDecision())

    assert decision.is_allowed is False
    assert decision.bundle is None
    assert decision.blockers == ("terminal_audit_decision_blocked",)

    with pytest.raises(RuntimeError, match="handoff is blocked"):
        _ = decision.bundle_required


def test_factory_and_function_api_match() -> None:
    audit_decision = bullish_terminal_exhaustion_audit_decision()

    factory_decision = StrategyPhase8FinalAuditHandoffFactory().create(audit_decision)
    function_decision = create_phase8_final_audit_handoff(audit_decision)

    assert (
        factory_decision.bundle_required.handoff_id == function_decision.bundle_required.handoff_id
    )


def test_handoff_safety_flags_are_valid() -> None:
    bundle = bullish_phase8_final_handoff_decision().bundle_required

    assert bundle.safety_flags_valid is True
    assert bundle.executes_strategy is False
    assert bundle.executes_simulation is False
    assert bundle.initializes_mt5 is False
    assert bundle.sends_broker_request is False
    assert bundle.writes_external_state is False
    assert bundle.can_submit_order is False


def test_handoff_creation_does_not_mutate_terminal_state() -> None:
    audit_decision = bullish_terminal_exhaustion_audit_decision()
    state = audit_decision.report_required.completion_state

    before = (
        state.state_version,
        state.cursor_index,
        state.consumed_count,
        state.remaining_count,
        state.last_consumed_sequence_index,
        state.next_event_sequence_index,
        state.lifecycle,
    )

    _ = create_phase8_final_audit_handoff(audit_decision).bundle_required

    after = (
        state.state_version,
        state.cursor_index,
        state.consumed_count,
        state.remaining_count,
        state.last_consumed_sequence_index,
        state.next_event_sequence_index,
        state.lifecycle,
    )

    assert after == before
