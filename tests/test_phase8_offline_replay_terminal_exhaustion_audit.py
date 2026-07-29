from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase8_offline_replay_terminal_exhaustion_audit import (
    PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_PASSED,
    PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_SCHEMA_VERSION,
    PHASE_8_OFFLINE_REPLAY_TERMINAL_REENTRY_BLOCKED,
    StrategyPhase8OfflineReplayTerminalExhaustionAuditor,
    audit_phase8_offline_replay_terminal_exhaustion,
    block_phase8_offline_replay_terminal_reentry,
)
from tests.test_phase8_offline_replay_generic_remaining_bounded_completion import (
    bullish_generic_remaining_completion_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedCompletionDecision:
    is_allowed: bool = False


def bullish_terminal_exhaustion_audit_decision():
    return audit_phase8_offline_replay_terminal_exhaustion(
        bullish_generic_remaining_completion_decision()
    )


def test_schema_version_is_stable() -> None:
    assert PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_SCHEMA_VERSION == "1.0"


def test_terminal_exhaustion_audit_is_created() -> None:
    decision = bullish_terminal_exhaustion_audit_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None


def test_audit_preserves_completion_lineage() -> None:
    completion_decision = bullish_generic_remaining_completion_decision()
    completion_state = completion_decision.state_required

    report = audit_phase8_offline_replay_terminal_exhaustion(completion_decision).report_required

    assert report.completion_decision is completion_decision
    assert report.completion_state is completion_state


def test_terminal_versions_and_counters_are_exact() -> None:
    report = bullish_terminal_exhaustion_audit_decision().report_required

    assert report.source_state_version == 13
    assert report.terminal_state_version == 14
    assert report.initial_cursor_index == 230
    assert report.final_cursor_index == 800
    assert report.total_event_count == 800
    assert report.consumed_count == 800
    assert report.remaining_count == 0
    assert report.last_consumed_sequence_index == 799
    assert report.next_event_sequence_index is None
    assert report.lifecycle == "COMPLETED"


def test_chunk_audit_is_exact() -> None:
    report = bullish_terminal_exhaustion_audit_decision().report_required

    assert report.chunk_limit == 32
    assert report.chunk_count == 18
    assert report.first_chunk_start_index == 230
    assert report.last_chunk_end_index == 800


def test_complete_sequence_coverage_is_exact() -> None:
    report = bullish_terminal_exhaustion_audit_decision().report_required

    assert report.audited_event_sequence_indices == tuple(range(230, 800))
    assert report.complete_sequence_coverage is True
    assert report.no_duplicate_sequences is True
    assert report.no_missing_sequences is True
    assert report.no_reordered_sequences is True


def test_chunk_lineage_is_contiguous() -> None:
    report = bullish_terminal_exhaustion_audit_decision().report_required

    assert report.chunk_indices_contiguous is True
    assert report.chunk_cursors_contiguous is True
    assert report.chunk_counters_contiguous is True
    assert report.final_chunk_terminal is True


def test_terminal_invariants_and_status_are_valid() -> None:
    report = bullish_terminal_exhaustion_audit_decision().report_required

    assert report.terminal_counters_valid is True
    assert report.terminal_reentry_allowed is False
    assert report.additional_event_count == 0
    assert report.safety_flags_valid is True
    assert report.status == PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_PASSED


def test_audit_id_is_deterministic() -> None:
    first = bullish_terminal_exhaustion_audit_decision().report_required
    second = bullish_terminal_exhaustion_audit_decision().report_required

    assert first.audit_digest == second.audit_digest
    assert first.audit_id == second.audit_id


def test_terminal_reentry_is_explicitly_blocked() -> None:
    audit_decision = bullish_terminal_exhaustion_audit_decision()
    guard = block_phase8_offline_replay_terminal_reentry(audit_decision)

    assert guard.is_allowed is False
    assert guard.status == PHASE_8_OFFLINE_REPLAY_TERMINAL_REENTRY_BLOCKED
    assert guard.blockers == ("offline_replay_already_completed",)
    assert guard.additional_event_count == 0
    assert guard.next_event_sequence_index is None


def test_blocked_completion_blocks_audit() -> None:
    decision = audit_phase8_offline_replay_terminal_exhaustion(FakeBlockedCompletionDecision())

    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("completion_decision_blocked",)

    with pytest.raises(RuntimeError, match="audit is blocked"):
        _ = decision.report_required


def test_missing_completion_blocks_audit() -> None:
    decision = audit_phase8_offline_replay_terminal_exhaustion(None)

    assert decision.is_allowed is False
    assert decision.report is None
    assert decision.blockers == ("completion_decision_missing",)


def test_reentry_guard_requires_successful_audit() -> None:
    with pytest.raises(ValueError, match="successful terminal audit"):
        block_phase8_offline_replay_terminal_reentry(FakeBlockedCompletionDecision())


def test_factory_and_function_api_match() -> None:
    completion_decision = bullish_generic_remaining_completion_decision()

    factory_decision = StrategyPhase8OfflineReplayTerminalExhaustionAuditor().audit(
        completion_decision
    )
    function_decision = audit_phase8_offline_replay_terminal_exhaustion(completion_decision)

    assert factory_decision.report_required.audit_id == function_decision.report_required.audit_id


def test_audit_and_reentry_guard_have_no_external_effects() -> None:
    audit_decision = bullish_terminal_exhaustion_audit_decision()
    report = audit_decision.report_required
    guard = block_phase8_offline_replay_terminal_reentry(audit_decision)

    for value in (report, guard):
        assert value.executes_strategy is False
        assert value.executes_simulation is False
        assert value.initializes_mt5 is False
        assert value.sends_broker_request is False
        assert value.writes_external_state is False
        assert value.can_submit_order is False
