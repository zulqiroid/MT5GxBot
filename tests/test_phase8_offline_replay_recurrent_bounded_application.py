from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase8_offline_replay_recurrent_bounded_application import (
    PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_APPLICATION_SCHEMA_VERSION,
    StrategyPhase8OfflineReplayRecurrentBoundedApplication,
    apply_phase8_offline_replay_recurrent_bounded_plan,
)
from app.strategy.phase8_offline_replay_recurrent_bounded_plan import (
    generate_phase8_offline_replay_recurrent_bounded_plan,
)
from tests.test_phase8_offline_replay_recurrent_bounded_plan import (
    bullish_recurrent_bounded_plan_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedPlanDecision:
    is_allowed: bool = False


@dataclass(frozen=True, slots=True)
class FakeNearTerminalState:
    state_version: int = 199
    cursor_index: int = 798
    consumed_count: int = 798
    remaining_count: int = 2
    next_event_sequence_index: int = 798
    total_event_count: int = 800
    state_id: str = "RECURRENT_NEAR_TERMINAL_STATE"


@dataclass(frozen=True, slots=True)
class FakeAllowedNearTerminalDecision:
    is_allowed: bool = True
    state_required: FakeNearTerminalState = FakeNearTerminalState()


def bullish_recurrent_bounded_application_decision():
    return apply_phase8_offline_replay_recurrent_bounded_plan(
        bullish_recurrent_bounded_plan_decision()
    )


def test_schema_version_is_stable() -> None:
    assert PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_APPLICATION_SCHEMA_VERSION == "1.0"


def test_bullish_recurrent_bounded_application_is_created() -> None:
    decision = bullish_recurrent_bounded_application_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.receipt is not None


def test_recurrent_application_preserves_lineage_identity() -> None:
    plan_decision = bullish_recurrent_bounded_plan_decision()
    plan = plan_decision.plan_required

    receipt = apply_phase8_offline_replay_recurrent_bounded_plan(plan_decision).receipt_required

    assert receipt.plan_decision is plan_decision
    assert receipt.plan is plan
    assert receipt.source_decision is plan.source_decision
    assert receipt.source_state is plan.source_state


def test_default_recurrent_application_counters_are_exact() -> None:
    receipt = bullish_recurrent_bounded_application_decision().receipt_required

    assert receipt.source_state_version == 8
    assert receipt.start_cursor_index == 70
    assert receipt.resulting_cursor_index == 102
    assert receipt.initial_consumed_count == 70
    assert receipt.resulting_consumed_count == 102
    assert receipt.initial_remaining_count == 730
    assert receipt.resulting_remaining_count == 698
    assert receipt.consumed_event_count == 32
    assert receipt.next_event_sequence_index == 102
    assert receipt.total_event_count == 800
    assert receipt.reaches_terminal_state is False


def test_default_consumed_sequence_range_is_exact() -> None:
    receipt = bullish_recurrent_bounded_application_decision().receipt_required

    assert receipt.consumed_event_sequence_indices == tuple(range(70, 102))


def test_recurrent_application_preserves_total_count() -> None:
    receipt = bullish_recurrent_bounded_application_decision().receipt_required

    assert (
        receipt.resulting_consumed_count + receipt.resulting_remaining_count
        == receipt.total_event_count
    )


def test_application_id_is_deterministic() -> None:
    first = bullish_recurrent_bounded_application_decision().receipt_required
    second = bullish_recurrent_bounded_application_decision().receipt_required

    assert first.application_digest == second.application_digest
    assert first.application_id == second.application_id


def test_blocked_plan_blocks_recurrent_application() -> None:
    decision = apply_phase8_offline_replay_recurrent_bounded_plan(FakeBlockedPlanDecision())

    assert decision.is_allowed is False
    assert decision.receipt is None
    assert decision.blockers == ("plan_decision_blocked",)

    with pytest.raises(RuntimeError, match="application is blocked"):
        _ = decision.receipt_required


def test_missing_plan_blocks_recurrent_application() -> None:
    decision = apply_phase8_offline_replay_recurrent_bounded_plan(None)

    assert decision.is_allowed is False
    assert decision.receipt is None
    assert decision.blockers == ("plan_decision_missing",)


def test_terminal_recurrent_application_is_exact() -> None:
    plan_decision = generate_phase8_offline_replay_recurrent_bounded_plan(
        FakeAllowedNearTerminalDecision()
    )

    receipt = apply_phase8_offline_replay_recurrent_bounded_plan(plan_decision).receipt_required

    assert receipt.source_state_version == 199
    assert receipt.start_cursor_index == 798
    assert receipt.resulting_cursor_index == 800
    assert receipt.initial_consumed_count == 798
    assert receipt.resulting_consumed_count == 800
    assert receipt.initial_remaining_count == 2
    assert receipt.resulting_remaining_count == 0
    assert receipt.consumed_event_sequence_indices == (798, 799)
    assert receipt.consumed_event_count == 2
    assert receipt.next_event_sequence_index is None
    assert receipt.total_event_count == 800
    assert receipt.reaches_terminal_state is True


def test_source_state_is_not_mutated() -> None:
    plan_decision = bullish_recurrent_bounded_plan_decision()
    source_state = plan_decision.plan_required.source_state

    before = (
        source_state.state_version,
        source_state.cursor_index,
        source_state.consumed_count,
        source_state.remaining_count,
        source_state.last_consumed_sequence_index,
        source_state.next_event_sequence_index,
        source_state.total_event_count,
    )

    _ = apply_phase8_offline_replay_recurrent_bounded_plan(plan_decision).receipt_required

    after = (
        source_state.state_version,
        source_state.cursor_index,
        source_state.consumed_count,
        source_state.remaining_count,
        source_state.last_consumed_sequence_index,
        source_state.next_event_sequence_index,
        source_state.total_event_count,
    )

    assert after == before


def test_factory_and_function_api_match() -> None:
    plan_decision = bullish_recurrent_bounded_plan_decision()

    factory_decision = StrategyPhase8OfflineReplayRecurrentBoundedApplication().apply(plan_decision)
    function_decision = apply_phase8_offline_replay_recurrent_bounded_plan(plan_decision)

    assert (
        factory_decision.receipt_required.application_id
        == function_decision.receipt_required.application_id
    )


def test_recurrent_application_creates_no_state_or_external_effects() -> None:
    receipt = bullish_recurrent_bounded_application_decision().receipt_required

    assert receipt.creates_reusable_state is False
    assert receipt.executes_strategy is False
    assert receipt.executes_simulation is False
    assert receipt.initializes_mt5 is False
    assert receipt.sends_broker_request is False
    assert receipt.writes_external_state is False
    assert receipt.can_submit_order is False
