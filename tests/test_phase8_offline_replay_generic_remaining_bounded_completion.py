from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase8_offline_replay_generic_remaining_bounded_completion import (
    PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETED,
    PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETION_SCHEMA_VERSION,
    PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_DEFAULT_CHUNK_LIMIT,
    StrategyPhase8OfflineReplayGenericRemainingBoundedCompletionEngine,
    complete_phase8_offline_replay_remaining_with_generic_bounded_engine,
)
from tests.test_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan import (
    bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedPlanDecision:
    is_allowed: bool = False


def bullish_generic_remaining_completion_decision():
    return complete_phase8_offline_replay_remaining_with_generic_bounded_engine(
        bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision()
    )


def test_schema_and_default_chunk_limit_are_stable() -> None:
    assert PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETION_SCHEMA_VERSION == "1.0"
    assert PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_DEFAULT_CHUNK_LIMIT == 32


def test_generic_remaining_completion_is_created() -> None:
    decision = bullish_generic_remaining_completion_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.state is not None


def test_completion_preserves_initial_plan_lineage() -> None:
    plan_decision = bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision()
    plan = plan_decision.plan_required

    state = complete_phase8_offline_replay_remaining_with_generic_bounded_engine(
        plan_decision
    ).state_required

    assert state.plan_decision is plan_decision
    assert state.initial_plan is plan
    assert state.source_decision is plan.source_decision
    assert state.source_state is plan.source_state
    assert state.source_state_version == 13
    assert state.state_version == 14


def test_completion_counters_are_exact() -> None:
    state = bullish_generic_remaining_completion_decision().state_required

    assert state.initial_cursor_index == 230
    assert state.cursor_index == 800
    assert state.initial_consumed_count == 230
    assert state.consumed_count == 800
    assert state.initial_remaining_count == 570
    assert state.remaining_count == 0
    assert state.last_consumed_sequence_index == 799
    assert state.next_event_sequence_index is None
    assert state.total_event_count == 800
    assert state.lifecycle == (PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETED)


def test_completion_has_eighteen_bounded_chunks() -> None:
    state = bullish_generic_remaining_completion_decision().state_required

    assert len(state.chunk_receipts) == 18
    assert tuple(receipt.chunk_index for receipt in state.chunk_receipts) == tuple(range(18))
    assert all(receipt.event_count <= 32 for receipt in state.chunk_receipts)


def test_first_chunk_exactly_matches_step_8_56_plan() -> None:
    state = bullish_generic_remaining_completion_decision().state_required
    first = state.chunk_receipts[0]

    assert first.start_cursor_index == 230
    assert first.resulting_cursor_index == 262
    assert first.initial_consumed_count == 230
    assert first.resulting_consumed_count == 262
    assert first.initial_remaining_count == 570
    assert first.resulting_remaining_count == 538
    assert first.event_sequence_indices == tuple(range(230, 262))
    assert first.event_count == 32
    assert first.next_event_sequence_index == 262
    assert first.reaches_terminal_state is False


def test_last_chunk_is_terminal_and_contains_twenty_six_events() -> None:
    state = bullish_generic_remaining_completion_decision().state_required
    last = state.chunk_receipts[-1]

    assert last.chunk_index == 17
    assert last.start_cursor_index == 774
    assert last.resulting_cursor_index == 800
    assert last.initial_consumed_count == 774
    assert last.resulting_consumed_count == 800
    assert last.initial_remaining_count == 26
    assert last.resulting_remaining_count == 0
    assert last.event_sequence_indices == tuple(range(774, 800))
    assert last.event_count == 26
    assert last.next_event_sequence_index is None
    assert last.reaches_terminal_state is True


def test_completion_sequence_has_no_gaps_duplicates_or_reordering() -> None:
    state = bullish_generic_remaining_completion_decision().state_required

    assert state.consumed_event_sequence_indices == tuple(range(230, 800))

    flattened = tuple(
        sequence_index
        for receipt in state.chunk_receipts
        for sequence_index in receipt.event_sequence_indices
    )
    assert flattened == tuple(range(230, 800))
    assert len(flattened) == len(set(flattened)) == 570


def test_chunk_counters_are_contiguous() -> None:
    state = bullish_generic_remaining_completion_decision().state_required

    receipts = state.chunk_receipts

    for prior, current in zip(
        receipts[:-1],
        receipts[1:],
        strict=True,
    ):
        assert current.start_cursor_index == prior.resulting_cursor_index
        assert current.initial_consumed_count == prior.resulting_consumed_count
        assert current.initial_remaining_count == prior.resulting_remaining_count


def test_completion_id_is_deterministic() -> None:
    first = bullish_generic_remaining_completion_decision().state_required
    second = bullish_generic_remaining_completion_decision().state_required

    assert first.completion_digest == second.completion_digest
    assert first.completion_id == second.completion_id


def test_custom_chunk_limit_is_respected() -> None:
    state = complete_phase8_offline_replay_remaining_with_generic_bounded_engine(
        bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision(),
        chunk_limit=64,
    ).state_required

    assert len(state.chunk_receipts) == 10
    assert state.chunk_receipts[0].event_count == 32
    assert all(receipt.event_count <= 64 for receipt in state.chunk_receipts)
    assert state.cursor_index == 800
    assert state.remaining_count == 0


def test_invalid_chunk_limit_blocks_completion() -> None:
    decision = complete_phase8_offline_replay_remaining_with_generic_bounded_engine(
        bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision(),
        chunk_limit=0,
    )

    assert decision.is_allowed is False
    assert decision.state is None
    assert decision.blockers == ("chunk_limit_invalid",)


def test_blocked_plan_blocks_completion() -> None:
    decision = complete_phase8_offline_replay_remaining_with_generic_bounded_engine(
        FakeBlockedPlanDecision()
    )

    assert decision.is_allowed is False
    assert decision.state is None
    assert decision.blockers == ("plan_decision_blocked",)

    with pytest.raises(RuntimeError, match="completion is blocked"):
        _ = decision.state_required


def test_missing_plan_blocks_completion() -> None:
    decision = complete_phase8_offline_replay_remaining_with_generic_bounded_engine(None)

    assert decision.is_allowed is False
    assert decision.state is None
    assert decision.blockers == ("plan_decision_missing",)


def test_factory_and_function_api_match() -> None:
    plan_decision = bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision()

    factory_decision = (
        StrategyPhase8OfflineReplayGenericRemainingBoundedCompletionEngine().complete(plan_decision)
    )
    function_decision = complete_phase8_offline_replay_remaining_with_generic_bounded_engine(
        plan_decision
    )

    assert (
        factory_decision.state_required.completion_id
        == function_decision.state_required.completion_id
    )


def test_completion_performs_no_strategy_broker_or_external_effects() -> None:
    state = bullish_generic_remaining_completion_decision().state_required

    assert state.executes_strategy is False
    assert state.executes_simulation is False
    assert state.initializes_mt5 is False
    assert state.sends_broker_request is False
    assert state.writes_external_state is False
    assert state.can_submit_order is False

    for receipt in state.chunk_receipts:
        assert receipt.executes_strategy is False
        assert receipt.executes_simulation is False
        assert receipt.initializes_mt5 is False
        assert receipt.sends_broker_request is False
        assert receipt.writes_external_state is False
        assert receipt.can_submit_order is False
