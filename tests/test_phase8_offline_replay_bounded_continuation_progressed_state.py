from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.strategy.phase8_offline_replay_bounded_continuation_application import (
    apply_phase8_offline_replay_bounded_continuation_plan,
)
from app.strategy.phase8_offline_replay_bounded_continuation_plan import (
    generate_phase8_offline_replay_bounded_continuation_plan,
)
from app.strategy.phase8_offline_replay_bounded_continuation_progressed_state import (
    PHASE_8_OFFLINE_REPLAY_BOUNDED_CONTINUATION_PROGRESSED_STATE_SCHEMA_VERSION,
    PHASE_8_OFFLINE_REPLAY_BOUNDED_CONTINUATION_STATE_ACTIVE,
    PHASE_8_OFFLINE_REPLAY_BOUNDED_CONTINUATION_STATE_COMPLETED,
    StrategyPhase8OfflineReplayBoundedContinuationProgressedStateFactory,
    create_phase8_offline_replay_bounded_continuation_progressed_state,
)
from tests.test_phase8_offline_replay_bounded_continuation_application import (
    FakeAllowedNearTerminalDecision,
    bullish_continuation_application_decision,
)


@dataclass(frozen=True, slots=True)
class FakeBlockedApplicationDecision:
    is_allowed: bool = False


def bullish_continuation_progressed_state_decision():
    return create_phase8_offline_replay_bounded_continuation_progressed_state(
        bullish_continuation_application_decision()
    )


def test_schema_version_is_stable() -> None:
    assert PHASE_8_OFFLINE_REPLAY_BOUNDED_CONTINUATION_PROGRESSED_STATE_SCHEMA_VERSION == "1.0"


def test_bullish_continuation_progressed_state_is_created() -> None:
    decision = bullish_continuation_progressed_state_decision()

    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.state is not None


def test_progressed_state_preserves_lineage_identity() -> None:
    application_decision = bullish_continuation_application_decision()
    receipt = application_decision.receipt_required

    state = create_phase8_offline_replay_bounded_continuation_progressed_state(
        application_decision
    ).state_required

    assert state.application_decision is application_decision
    assert state.application_receipt is receipt
    assert state.plan_decision is receipt.plan_decision
    assert state.plan is receipt.plan
    assert state.source_decision is receipt.source_decision
    assert state.prior_state is receipt.source_state


def test_default_progressed_state_counters_are_exact() -> None:
    state = bullish_continuation_progressed_state_decision().state_required

    assert state.state_version == 8
    assert state.cursor_index == 70
    assert state.consumed_count == 70
    assert state.remaining_count == 730
    assert state.last_consumed_sequence_index == 69
    assert state.next_event_sequence_index == 70
    assert state.total_event_count == 800
    assert state.lifecycle == PHASE_8_OFFLINE_REPLAY_BOUNDED_CONTINUATION_STATE_ACTIVE


def test_progressed_state_preserves_total_count() -> None:
    state = bullish_continuation_progressed_state_decision().state_required

    assert state.consumed_count + state.remaining_count == state.total_event_count


def test_progressed_state_id_is_deterministic() -> None:
    first = bullish_continuation_progressed_state_decision().state_required
    second = bullish_continuation_progressed_state_decision().state_required

    assert first.state_digest == second.state_digest
    assert first.state_id == second.state_id


def test_blocked_application_blocks_progressed_state() -> None:
    decision = create_phase8_offline_replay_bounded_continuation_progressed_state(
        FakeBlockedApplicationDecision()
    )

    assert decision.is_allowed is False
    assert decision.state is None
    assert decision.blockers == ("application_decision_blocked",)

    with pytest.raises(RuntimeError, match="state is blocked"):
        _ = decision.state_required


def test_missing_application_blocks_progressed_state() -> None:
    decision = create_phase8_offline_replay_bounded_continuation_progressed_state(None)

    assert decision.is_allowed is False
    assert decision.state is None
    assert decision.blockers == ("application_decision_missing",)


def test_terminal_progressed_state_is_exact() -> None:
    plan_decision = generate_phase8_offline_replay_bounded_continuation_plan(
        FakeAllowedNearTerminalDecision()
    )
    application_decision = apply_phase8_offline_replay_bounded_continuation_plan(plan_decision)

    state = create_phase8_offline_replay_bounded_continuation_progressed_state(
        application_decision
    ).state_required

    assert state.state_version == 100
    assert state.cursor_index == 800
    assert state.consumed_count == 800
    assert state.remaining_count == 0
    assert state.last_consumed_sequence_index == 799
    assert state.next_event_sequence_index is None
    assert state.total_event_count == 800
    assert state.lifecycle == PHASE_8_OFFLINE_REPLAY_BOUNDED_CONTINUATION_STATE_COMPLETED


def test_prior_state_is_not_mutated() -> None:
    application_decision = bullish_continuation_application_decision()
    prior_state = application_decision.receipt_required.source_state

    before = (
        prior_state.state_version,
        prior_state.cursor_index,
        prior_state.consumed_count,
        prior_state.remaining_count,
        prior_state.last_consumed_sequence_index,
        prior_state.next_event_sequence_index,
        prior_state.total_event_count,
    )

    _ = create_phase8_offline_replay_bounded_continuation_progressed_state(
        application_decision
    ).state_required

    after = (
        prior_state.state_version,
        prior_state.cursor_index,
        prior_state.consumed_count,
        prior_state.remaining_count,
        prior_state.last_consumed_sequence_index,
        prior_state.next_event_sequence_index,
        prior_state.total_event_count,
    )

    assert after == before


def test_factory_and_function_api_match() -> None:
    application_decision = bullish_continuation_application_decision()

    factory_decision = (
        StrategyPhase8OfflineReplayBoundedContinuationProgressedStateFactory().create(
            application_decision
        )
    )
    function_decision = create_phase8_offline_replay_bounded_continuation_progressed_state(
        application_decision
    )

    assert factory_decision.state_required.state_id == function_decision.state_required.state_id


def test_progressed_state_performs_no_execution_or_external_effects() -> None:
    state = bullish_continuation_progressed_state_decision().state_required

    assert state.executes_transition is False
    assert state.consumes_additional_events is False
    assert state.executes_strategy is False
    assert state.executes_simulation is False
    assert state.initializes_mt5 is False
    assert state.sends_broker_request is False
    assert state.writes_external_state is False
    assert state.can_submit_order is False
