from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan import (
    PHASE_8_OFFLINE_REPLAY_FURTHER_CONTINUED_SUCCESSIVE_ITERATIVE_RECURRENT_BOUNDED_DEFAULT_LIMIT,
    PHASE_8_OFFLINE_REPLAY_FURTHER_CONTINUED_SUCCESSIVE_ITERATIVE_RECURRENT_BOUNDED_PLAN_SCHEMA_VERSION,
    StrategyPhase8OfflineReplayFurtherContinuedSuccessiveIterativeRecurrentBoundedPlanner,
    generate_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan,
)
from tests.test_phase8_offline_replay_continued_successive_iterative_recurrent_bounded_progressed_state import (
    bullish_continued_successive_iterative_recurrent_bounded_progressed_state_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedSourceDecision:
    is_allowed: bool = False


@dataclass(frozen=True, slots=True)
class FakeTerminalState:
    state_version: int = 13
    cursor_index: int = 800
    consumed_count: int = 800
    remaining_count: int = 0
    next_event_sequence_index: None = None
    total_event_count: int = 800
    state_id: str = "CONTINUED_SUCCESSIVE_TERMINAL_SOURCE"


@dataclass(frozen=True, slots=True)
class FakeAllowedTerminalDecision:
    is_allowed: bool = True
    state_required: FakeTerminalState = FakeTerminalState()


def bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision():
    return generate_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan(
        bullish_continued_successive_iterative_recurrent_bounded_progressed_state_decision()
    )


def test_schema_and_default_limit_are_stable() -> None:
    assert (
        PHASE_8_OFFLINE_REPLAY_FURTHER_CONTINUED_SUCCESSIVE_ITERATIVE_RECURRENT_BOUNDED_PLAN_SCHEMA_VERSION
        == "1.0"
    )
    assert (
        PHASE_8_OFFLINE_REPLAY_FURTHER_CONTINUED_SUCCESSIVE_ITERATIVE_RECURRENT_BOUNDED_DEFAULT_LIMIT
        == 32
    )


def test_bullish_further_continued_successive_plan_is_created() -> None:
    decision = bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.plan is not None


def test_plan_preserves_source_identity() -> None:
    source_decision = (
        bullish_continued_successive_iterative_recurrent_bounded_progressed_state_decision()
    )
    source_state = source_decision.state_required

    plan = generate_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan(
        source_decision
    ).plan_required

    assert plan.source_decision is source_decision
    assert plan.source_state is source_state
    assert plan.source_state_version == 13


def test_default_plan_counters_are_exact() -> None:
    plan = bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision().plan_required

    assert plan.start_cursor_index == 230
    assert plan.resulting_cursor_index == 262
    assert plan.initial_consumed_count == 230
    assert plan.resulting_consumed_count == 262
    assert plan.initial_remaining_count == 570
    assert plan.resulting_remaining_count == 538
    assert plan.planned_transition_count == 32
    assert plan.next_event_sequence_index == 262
    assert plan.total_event_count == 800
    assert plan.reaches_terminal_state is False
    assert plan.transition_limit == 32


def test_default_sequence_range_is_exact() -> None:
    plan = bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision().plan_required

    assert plan.planned_event_sequence_indices == tuple(range(230, 262))


def test_plan_preserves_total_count() -> None:
    plan = bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision().plan_required

    assert plan.resulting_consumed_count + plan.resulting_remaining_count == plan.total_event_count


def test_plan_id_is_deterministic() -> None:
    first = bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision().plan_required
    second = bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision().plan_required

    assert first.plan_digest == second.plan_digest
    assert first.plan_id == second.plan_id


def test_custom_limit_is_respected() -> None:
    plan = generate_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan(
        bullish_continued_successive_iterative_recurrent_bounded_progressed_state_decision(),
        transition_limit=5,
    ).plan_required

    assert plan.planned_transition_count == 5
    assert plan.start_cursor_index == 230
    assert plan.resulting_cursor_index == 235
    assert plan.resulting_consumed_count == 235
    assert plan.resulting_remaining_count == 565
    assert plan.planned_event_sequence_indices == tuple(range(230, 235))
    assert plan.next_event_sequence_index == 235


def test_blocked_source_blocks_plan() -> None:
    decision = generate_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan(
        FakeBlockedSourceDecision()
    )

    assert decision.is_allowed is False
    assert decision.plan is None
    assert decision.blockers == ("source_decision_blocked",)

    with pytest.raises(RuntimeError, match="plan is blocked"):
        _ = decision.plan_required


def test_missing_source_blocks_plan() -> None:
    decision = generate_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan(
        None
    )

    assert decision.is_allowed is False
    assert decision.plan is None
    assert decision.blockers == ("source_decision_missing",)


def test_terminal_source_blocks_plan() -> None:
    decision = generate_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan(
        FakeAllowedTerminalDecision()
    )

    assert decision.is_allowed is False
    assert decision.plan is None
    assert decision.blockers == ("source_state_terminal",)


def test_source_state_is_not_mutated() -> None:
    source_decision = (
        bullish_continued_successive_iterative_recurrent_bounded_progressed_state_decision()
    )
    state = source_decision.state_required

    before = (
        state.state_version,
        state.cursor_index,
        state.consumed_count,
        state.remaining_count,
        state.last_consumed_sequence_index,
        state.next_event_sequence_index,
        state.total_event_count,
    )

    _ = generate_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan(
        source_decision
    ).plan_required

    after = (
        state.state_version,
        state.cursor_index,
        state.consumed_count,
        state.remaining_count,
        state.last_consumed_sequence_index,
        state.next_event_sequence_index,
        state.total_event_count,
    )

    assert after == before


def test_factory_and_function_api_match() -> None:
    source_decision = (
        bullish_continued_successive_iterative_recurrent_bounded_progressed_state_decision()
    )

    factory_decision = StrategyPhase8OfflineReplayFurtherContinuedSuccessiveIterativeRecurrentBoundedPlanner().generate(
        source_decision
    )
    function_decision = generate_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan(
        source_decision
    )

    assert factory_decision.plan_required.plan_id == function_decision.plan_required.plan_id


def test_plan_performs_no_execution_or_external_effects() -> None:
    plan = bullish_further_continued_successive_iterative_recurrent_bounded_plan_decision().plan_required

    assert plan.applies_transition is False
    assert plan.consumes_events is False
    assert plan.creates_reusable_state is False
    assert plan.executes_strategy is False
    assert plan.executes_simulation is False
    assert plan.initializes_mt5 is False
    assert plan.sends_broker_request is False
    assert plan.writes_external_state is False
    assert plan.can_submit_order is False
