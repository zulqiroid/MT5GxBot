from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase8_offline_replay_bounded_iteration_plan import (
    PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_PLAN_SCHEMA_VERSION,
    Phase8OfflineReplayBoundedIterationPlanPolicy,
    StrategyPhase8OfflineReplayBoundedIterationPlanFactory,
    generate_phase8_offline_replay_bounded_iteration_plan,
)
from tests.test_phase8_offline_replay_iterative_continuation_progressed_session_state import (
    bullish_iterative_continuation_progressed_state_decision,
)


@dataclass(frozen=True, slots=True)
class FakeReplayState:
    state_version: int
    cursor_index: int
    consumed_count: int
    remaining_count: int
    last_consumed_sequence_index: int
    next_event_sequence_index: int


@dataclass(frozen=True, slots=True)
class FakeAllowedDecision:
    state_required: FakeReplayState
    is_allowed: bool = True


@dataclass(frozen=True, slots=True)
class FakeBlockedDecision:
    is_allowed: bool = False


def bullish_plan_decision():
    return generate_phase8_offline_replay_bounded_iteration_plan(
        bullish_iterative_continuation_progressed_state_decision()
    )


def test_schema_version_is_stable() -> None:
    assert PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_PLAN_SCHEMA_VERSION == "1.0"


def test_bullish_bounded_plan_is_created() -> None:
    decision = bullish_plan_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.plan is not None


def test_bullish_plan_preserves_source_identity() -> None:
    source_decision = bullish_iterative_continuation_progressed_state_decision()
    plan = generate_phase8_offline_replay_bounded_iteration_plan(source_decision).plan_required
    assert plan.source_decision is source_decision
    assert plan.source_state is source_decision.state_required


def test_default_bounded_plan_counters_are_exact() -> None:
    plan = bullish_plan_decision().plan_required
    assert plan.source_state_version == 6
    assert plan.start_cursor_index == 6
    assert plan.stop_cursor_index == 38
    assert plan.initial_consumed_count == 6
    assert plan.planned_consumed_count == 38
    assert plan.initial_remaining_count == 794
    assert plan.planned_remaining_count == 762
    assert plan.first_event_sequence_index == 6
    assert plan.last_event_sequence_index == 37
    assert plan.next_event_sequence_index == 38
    assert plan.planned_transition_count == 32
    assert plan.total_event_count == 800
    assert plan.reaches_terminal_state is False


def test_default_plan_preserves_total_event_count() -> None:
    plan = bullish_plan_decision().plan_required
    assert plan.initial_consumed_count + plan.initial_remaining_count == plan.total_event_count
    assert plan.planned_consumed_count + plan.planned_remaining_count == plan.total_event_count


def test_plan_id_is_deterministic() -> None:
    first = bullish_plan_decision().plan_required
    second = bullish_plan_decision().plan_required
    assert first.plan_digest == second.plan_digest
    assert first.plan_id == second.plan_id


def test_custom_single_transition_limit_is_exact() -> None:
    policy = Phase8OfflineReplayBoundedIterationPlanPolicy(max_transition_count=1)
    plan = generate_phase8_offline_replay_bounded_iteration_plan(
        bullish_iterative_continuation_progressed_state_decision(),
        policy=policy,
    ).plan_required
    assert plan.start_cursor_index == 6
    assert plan.stop_cursor_index == 7
    assert plan.planned_transition_count == 1
    assert plan.planned_consumed_count == 7
    assert plan.planned_remaining_count == 793
    assert plan.first_event_sequence_index == 6
    assert plan.last_event_sequence_index == 6
    assert plan.next_event_sequence_index == 7


def test_plan_clamps_to_remaining_events() -> None:
    state = FakeReplayState(
        state_version=99,
        cursor_index=798,
        consumed_count=798,
        remaining_count=2,
        last_consumed_sequence_index=797,
        next_event_sequence_index=798,
    )
    plan = generate_phase8_offline_replay_bounded_iteration_plan(
        FakeAllowedDecision(state_required=state)
    ).plan_required
    assert plan.planned_transition_count == 2
    assert plan.stop_cursor_index == 800
    assert plan.planned_consumed_count == 800
    assert plan.planned_remaining_count == 0
    assert plan.first_event_sequence_index == 798
    assert plan.last_event_sequence_index == 799
    assert plan.next_event_sequence_index is None
    assert plan.reaches_terminal_state is True


def test_blocked_source_decision_blocks_plan() -> None:
    decision = generate_phase8_offline_replay_bounded_iteration_plan(FakeBlockedDecision())
    assert decision.is_allowed is False
    assert decision.plan is None
    assert decision.blockers == ("source_decision_blocked",)
    with pytest.raises(RuntimeError, match="plan is blocked"):
        _ = decision.plan_required


def test_terminal_source_state_blocks_plan() -> None:
    state = FakeReplayState(
        state_version=100,
        cursor_index=800,
        consumed_count=800,
        remaining_count=0,
        last_consumed_sequence_index=799,
        next_event_sequence_index=800,
    )
    decision = generate_phase8_offline_replay_bounded_iteration_plan(
        FakeAllowedDecision(state_required=state)
    )
    assert decision.is_allowed is False
    assert decision.plan is None
    assert decision.blockers == ("source_state_terminal",)


@pytest.mark.parametrize(
    "invalid_value",
    (0, -1, 65, True, 1.5),
)
def test_policy_rejects_invalid_limits(invalid_value: object) -> None:
    with pytest.raises(ValueError):
        Phase8OfflineReplayBoundedIterationPlanPolicy(
            max_transition_count=invalid_value  # type: ignore[arg-type]
        )


def test_factory_and_function_api_match() -> None:
    source_decision = bullish_iterative_continuation_progressed_state_decision()
    factory_decision = StrategyPhase8OfflineReplayBoundedIterationPlanFactory().generate(
        source_decision
    )
    function_decision = generate_phase8_offline_replay_bounded_iteration_plan(source_decision)
    assert factory_decision.plan_required.plan_id == function_decision.plan_required.plan_id


def test_plan_performs_no_external_io_or_execution() -> None:
    plan = bullish_plan_decision().plan_required
    assert plan.executes_transition is False
    assert plan.consumes_events is False
    assert plan.advances_cursor is False
    assert plan.creates_next_state is False
    assert plan.executes_strategy is False
    assert plan.executes_simulation is False
    assert plan.initializes_mt5 is False
    assert plan.sends_broker_request is False
    assert plan.writes_external_state is False
    assert plan.can_submit_order is False
