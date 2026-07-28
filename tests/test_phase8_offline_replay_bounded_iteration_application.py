from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase8_offline_replay_bounded_iteration_application import (
    PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_APPLICATION_SCHEMA_VERSION,
    StrategyPhase8OfflineReplayBoundedIterationApplication,
    apply_phase8_offline_replay_bounded_iteration_plan,
)
from app.strategy.phase8_offline_replay_bounded_iteration_plan import (
    generate_phase8_offline_replay_bounded_iteration_plan,
)
from tests.test_phase8_offline_replay_bounded_iteration_plan import (
    FakeAllowedDecision,
    FakeBlockedDecision,
    FakeReplayState,
    bullish_plan_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedPlanDecision:
    is_allowed: bool = False


def bullish_application_decision():
    return apply_phase8_offline_replay_bounded_iteration_plan(bullish_plan_decision())


def test_schema_version_is_stable() -> None:
    assert PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_APPLICATION_SCHEMA_VERSION == "1.0"


def test_bullish_bounded_application_is_created() -> None:
    decision = bullish_application_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.receipt is not None


def test_application_preserves_plan_and_source_identity() -> None:
    plan_decision = bullish_plan_decision()
    plan = plan_decision.plan_required

    receipt = apply_phase8_offline_replay_bounded_iteration_plan(plan_decision).receipt_required

    assert receipt.plan_decision is plan_decision
    assert receipt.plan is plan
    assert receipt.source_decision is plan.source_decision
    assert receipt.source_state is plan.source_state


def test_default_application_counters_are_exact() -> None:
    receipt = bullish_application_decision().receipt_required

    assert receipt.source_state_version == 6
    assert receipt.start_cursor_index == 6
    assert receipt.resulting_cursor_index == 38
    assert receipt.initial_consumed_count == 6
    assert receipt.resulting_consumed_count == 38
    assert receipt.initial_remaining_count == 794
    assert receipt.resulting_remaining_count == 762
    assert receipt.consumed_event_count == 32
    assert receipt.next_event_sequence_index == 38
    assert receipt.total_event_count == 800
    assert receipt.reaches_terminal_state is False


def test_consumed_event_sequence_indices_are_exact() -> None:
    receipt = bullish_application_decision().receipt_required
    assert receipt.consumed_event_sequence_indices == tuple(range(6, 38))


def test_application_preserves_total_event_count() -> None:
    receipt = bullish_application_decision().receipt_required

    assert (
        receipt.initial_consumed_count + receipt.initial_remaining_count
        == receipt.total_event_count
    )
    assert (
        receipt.resulting_consumed_count + receipt.resulting_remaining_count
        == receipt.total_event_count
    )


def test_application_id_is_deterministic() -> None:
    first = bullish_application_decision().receipt_required
    second = bullish_application_decision().receipt_required

    assert first.application_digest == second.application_digest
    assert first.application_id == second.application_id


def test_blocked_plan_decision_blocks_application() -> None:
    decision = apply_phase8_offline_replay_bounded_iteration_plan(FakeBlockedPlanDecision())

    assert decision.is_allowed is False
    assert decision.receipt is None
    assert decision.blockers == ("plan_decision_blocked",)

    with pytest.raises(RuntimeError, match="application is blocked"):
        _ = decision.receipt_required


def test_missing_plan_decision_blocks_application() -> None:
    decision = apply_phase8_offline_replay_bounded_iteration_plan(None)

    assert decision.is_allowed is False
    assert decision.receipt is None
    assert decision.blockers == ("plan_decision_missing",)


def test_terminal_bounded_plan_application_is_exact() -> None:
    state = FakeReplayState(
        state_version=99,
        cursor_index=798,
        consumed_count=798,
        remaining_count=2,
        last_consumed_sequence_index=797,
        next_event_sequence_index=798,
    )
    plan_decision = generate_phase8_offline_replay_bounded_iteration_plan(
        FakeAllowedDecision(state_required=state)
    )

    receipt = apply_phase8_offline_replay_bounded_iteration_plan(plan_decision).receipt_required

    assert receipt.start_cursor_index == 798
    assert receipt.resulting_cursor_index == 800
    assert receipt.initial_consumed_count == 798
    assert receipt.resulting_consumed_count == 800
    assert receipt.initial_remaining_count == 2
    assert receipt.resulting_remaining_count == 0
    assert receipt.consumed_event_sequence_indices == (798, 799)
    assert receipt.consumed_event_count == 2
    assert receipt.next_event_sequence_index is None
    assert receipt.reaches_terminal_state is True


def test_source_state_is_not_mutated() -> None:
    plan_decision = bullish_plan_decision()
    source_state = plan_decision.plan_required.source_state
    state_before = (
        source_state.state_version,
        source_state.cursor_index,
        source_state.consumed_count,
        source_state.remaining_count,
        source_state.last_consumed_sequence_index,
        source_state.next_event_sequence_index,
    )

    _ = apply_phase8_offline_replay_bounded_iteration_plan(plan_decision).receipt_required

    state_after = (
        source_state.state_version,
        source_state.cursor_index,
        source_state.consumed_count,
        source_state.remaining_count,
        source_state.last_consumed_sequence_index,
        source_state.next_event_sequence_index,
    )

    assert state_after == state_before


def test_factory_and_function_api_match() -> None:
    plan_decision = bullish_plan_decision()

    factory_decision = StrategyPhase8OfflineReplayBoundedIterationApplication().apply(plan_decision)
    function_decision = apply_phase8_offline_replay_bounded_iteration_plan(plan_decision)

    assert (
        factory_decision.receipt_required.application_id
        == function_decision.receipt_required.application_id
    )


def test_application_creates_no_reusable_state_or_external_effects() -> None:
    receipt = bullish_application_decision().receipt_required

    assert receipt.creates_reusable_state is False
    assert receipt.executes_strategy is False
    assert receipt.executes_simulation is False
    assert receipt.initializes_mt5 is False
    assert receipt.sends_broker_request is False
    assert receipt.writes_external_state is False
    assert receipt.can_submit_order is False


def test_unrelated_blocked_source_fixture_remains_blocked() -> None:
    plan_decision = generate_phase8_offline_replay_bounded_iteration_plan(FakeBlockedDecision())
    application_decision = apply_phase8_offline_replay_bounded_iteration_plan(plan_decision)

    assert application_decision.is_allowed is False
    assert application_decision.receipt is None
    assert application_decision.blockers == ("plan_decision_blocked",)
