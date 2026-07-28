from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError, replace
from functools import lru_cache

import pytest

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.order_intent_blueprint import (
    StrategyOrderSide,
)
from app.strategy.phase8_dry_run_foundation import (
    Phase8Timeframe,
)
from app.strategy.phase8_offline_replay_recurrent_progressed_session_state import (
    PHASE_8_OFFLINE_REPLAY_RECURRENT_PROGRESSED_SESSION_STATE_SCHEMA_VERSION,
    Phase8OfflineReplayRecurrentProgressedSessionLifecycle,
    Phase8OfflineReplayRecurrentProgressedSessionState,
    Phase8OfflineReplayRecurrentProgressedSessionStateBlocker,
    Phase8OfflineReplayRecurrentProgressedSessionStateError,
    Phase8OfflineReplayRecurrentProgressedSessionStateErrorReason,
    Phase8OfflineReplayRecurrentProgressedSessionStateFactory,
    Phase8OfflineReplayRecurrentProgressedSessionStateMode,
    Phase8OfflineReplayRecurrentProgressedSessionStatePolicy,
    Phase8OfflineReplayRecurrentProgressedSessionStateReason,
    Phase8OfflineReplayRecurrentProgressedSessionStateStatus,
    StrategyPhase8OfflineReplayRecurrentProgressedSessionState,
    StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory,
    generate_phase8_offline_replay_recurrent_progressed_session_state,
)
from app.strategy.phase8_offline_replay_recurrent_transition_application import (
    StrategyPhase8OfflineReplayRecurrentTransitionApplicationFactory,
)
from tests.test_phase8_offline_replay_recurrent_transition_application import (
    CAPTURED_AT,
    application_bearish_recurrent_contract_decision,
    application_blocked_recurrent_contract_decision,
    application_existing_recurrent_contract_decision,
    bullish_recurrent_transition_application_decision,
)


@lru_cache(maxsize=1)
def state_bearish_recurrent_application_decision():
    return StrategyPhase8OfflineReplayRecurrentTransitionApplicationFactory().generate(
        application_bearish_recurrent_contract_decision()
    )


@lru_cache(maxsize=1)
def state_existing_recurrent_application_decision():
    return StrategyPhase8OfflineReplayRecurrentTransitionApplicationFactory().generate(
        application_existing_recurrent_contract_decision()
    )


@lru_cache(maxsize=1)
def state_blocked_recurrent_application_decision():
    return StrategyPhase8OfflineReplayRecurrentTransitionApplicationFactory().generate(
        application_blocked_recurrent_contract_decision()
    )


@lru_cache(maxsize=1)
def bullish_recurrent_progressed_state_decision():
    return StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(
        bullish_recurrent_transition_application_decision()
    )


def test_invalid_application_decision_is_fail_safe() -> None:
    with pytest.raises(
        Phase8OfflineReplayRecurrentProgressedSessionStateError,
        match=("INVALID_RECURRENT_TRANSITION_APPLICATION_DECISION"),
    ) as captured:
        (StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate("invalid"))

    assert captured.value.reason == (
        Phase8OfflineReplayRecurrentProgressedSessionStateErrorReason.INVALID_RECURRENT_TRANSITION_APPLICATION_DECISION
    )


def test_default_policy_is_strict() -> None:
    policy = Phase8OfflineReplayRecurrentProgressedSessionStatePolicy()

    assert policy.is_strict is True
    assert policy.application_receipt_verified is True
    assert policy.prior_source_state_immutable is True
    assert policy.counters_match_receipt is True
    assert policy.sequence_continuity_verified is True
    assert policy.last_consumed_event_bound is True
    assert policy.next_event_bound is True
    assert policy.forward_only is True
    assert policy.in_memory_only is True
    assert policy.no_lookahead is True
    assert policy.no_external_io is True


@pytest.mark.parametrize(
    "field_name",
    [
        "application_receipt_verified",
        "prior_source_state_immutable",
        "counters_match_receipt",
        "sequence_continuity_verified",
        "last_consumed_event_bound",
        "next_event_bound",
        "forward_only",
        "in_memory_only",
        "no_lookahead",
        "no_external_io",
    ],
)
def test_policy_rejects_non_boolean(field_name) -> None:
    with pytest.raises(ValueError, match="boolean"):
        Phase8OfflineReplayRecurrentProgressedSessionStatePolicy(**{field_name: 1})


def test_bullish_recurrent_progressed_state_is_created() -> None:
    decision = bullish_recurrent_progressed_state_decision()

    assert decision.status == (Phase8OfflineReplayRecurrentProgressedSessionStateStatus.CREATED)
    assert decision.reason == (Phase8OfflineReplayRecurrentProgressedSessionStateReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_state is True


def test_bearish_recurrent_progressed_state_is_created() -> None:
    decision = StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(
        state_bearish_recurrent_application_decision()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.state_required.side == (StrategyOrderSide.SELL)


def test_existing_recurrent_progressed_state_is_created() -> None:
    decision = StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(
        state_existing_recurrent_application_decision()
    )

    assert decision.is_created is True


def test_blocked_application_blocks_state() -> None:
    decision = StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(
        state_blocked_recurrent_application_decision()
    )

    assert decision.is_blocked is True
    assert decision.state is None
    assert decision.reason == (
        Phase8OfflineReplayRecurrentProgressedSessionStateReason.RECURRENT_TRANSITION_APPLICATION_BLOCKED
    )
    assert decision.blockers == (
        Phase8OfflineReplayRecurrentProgressedSessionStateBlocker.RECURRENT_TRANSITION_APPLICATION_BLOCKED,
    )


def test_state_required_rejects_blocked_result() -> None:
    decision = StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(
        state_blocked_recurrent_application_decision()
    )

    with pytest.raises(
        ValueError,
        match="No Phase 8 recurrent progressed",
    ):
        _ = decision.state_required


def test_state_preserves_application_identity() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.recurrent_transition_application_decision is (
        bullish_recurrent_transition_application_decision()
    )
    assert state.application_receipt is (
        bullish_recurrent_transition_application_decision().receipt_required
    )


def test_state_preserves_lineage() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required
    receipt = state.application_receipt

    assert state.recurrent_transition_contract is (receipt.transition_contract)
    assert state.prior_source_state is receipt.source_state
    assert state.event_batch is receipt.event_batch


def test_state_preserves_identifiers() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.application_receipt_id == (state.application_receipt.stable_id)
    assert state.recurrent_transition_contract_id == (state.recurrent_transition_contract.stable_id)
    assert state.prior_source_state_id == (state.prior_source_state.stable_id)
    assert state.event_batch_id == (state.event_batch.stable_id)


def test_state_preserves_digests() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.application_digest == (state.application_receipt.application_digest)
    assert state.recurrent_transition_contract_digest == (
        state.recurrent_transition_contract.transition_digest
    )
    assert state.prior_source_state_digest == (state.prior_source_state.state_digest)
    assert state.event_batch_digest == (state.event_batch.batch_digest)


def test_state_preserves_metadata() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.broker_symbol == "XAUUSDm"
    assert state.direction == (DirectionalPermissionDirection.BULLISH)
    assert state.side == StrategyOrderSide.BUY
    assert state.source_name == "EXTERNAL_TEST_FIXTURE"
    assert state.captured_at == CAPTURED_AT
    assert state.schema_version == (
        PHASE_8_OFFLINE_REPLAY_RECURRENT_PROGRESSED_SESSION_STATE_SCHEMA_VERSION
    )


def test_timeframes_are_exact() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.timeframes == (
        Phase8Timeframe.H4,
        Phase8Timeframe.H1,
        Phase8Timeframe.M15,
        Phase8Timeframe.M5,
    )


def test_recurrent_progressed_counters_are_exact() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.state_version == 4
    assert state.cursor_index == 4
    assert state.consumed_count == 4
    assert state.remaining_count == 796
    assert state.total_event_count == 800
    assert state.last_consumed_sequence_index == 3
    assert state.next_event_sequence_index == 4
    assert state.completion_reached is False


def test_counters_preserve_total() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.consumed_count + state.remaining_count == state.total_event_count
    assert state.cursor_index == state.consumed_count
    assert state.last_consumed_sequence_index == (state.cursor_index - 1)
    assert state.next_event_sequence_index == (state.cursor_index)


def test_sequence_progresses_from_prior_state() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required
    prior = state.prior_source_state

    assert state.cursor_index == prior.cursor_index + 1
    assert state.consumed_count == prior.consumed_count + 1
    assert state.remaining_count == prior.remaining_count - 1
    assert state.last_consumed_sequence_index == (prior.last_consumed_sequence_index + 1)


def test_last_consumed_event_matches_receipt() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required
    expected = state.application_receipt.consumed_event

    assert state.last_consumed_event is expected
    assert state.last_consumed_event_id == expected.stable_id
    assert state.last_consumed_event_digest == (expected.event_digest)
    assert state.last_consumed_event_time == (expected.event_time)
    assert state.last_consumed_event_timeframe == (expected.timeframe)


def test_next_event_matches_receipt() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required
    expected = state.application_receipt.next_event

    assert state.next_event is expected
    assert state.next_event_id == expected.stable_id
    assert state.next_event_digest == (expected.event_digest)
    assert state.next_event_time == expected.event_time
    assert state.next_event_timeframe == (expected.timeframe)


def test_bound_events_are_closed() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.last_consumed_event.event_time == (state.last_consumed_event.close_time)
    assert state.next_event.event_time == (state.next_event.close_time)
    assert state.last_consumed_event.event_time <= (state.captured_at)
    assert state.next_event.event_time <= state.captured_at


def test_prior_source_state_remains_unchanged() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required
    prior = state.prior_source_state

    assert state.prior_state_preserved is True
    assert prior.cursor_index == 3
    assert prior.consumed_count == 3
    assert prior.remaining_count == 797
    assert prior.last_consumed_sequence_index == 2
    assert prior.next_event_sequence_index == 3
    assert prior.state_digest == (state.prior_source_state_digest)


def test_state_controls_are_exact() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.state_mode == (
        Phase8OfflineReplayRecurrentProgressedSessionStateMode.IMMUTABLE_RECURRENT_PROGRESSED_STATE
    )
    assert state.lifecycle == (Phase8OfflineReplayRecurrentProgressedSessionLifecycle.ACTIVE)


def test_state_digest_is_deterministic() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.state_digest == hashlib.sha256(state.canonical_payload.encode("utf-8")).hexdigest()
    assert state.digest_algorithm == "SHA-256"


def test_state_is_reusable_state_only() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.is_ready is True
    assert state.is_recurrent_progressed_state is True
    assert state.session_initialized is True
    assert state.session_active is True
    assert state.has_next_event is True
    assert state.prior_state_preserved is True
    assert state.represents_applied_transition is True
    assert state.creates_next_state is True
    assert state.executes_transition is False
    assert state.advances_cursor is False
    assert state.consumes_events is False
    assert state.starts_session is False
    assert state.starts_replay is False
    assert state.executes_replay is False
    assert state.evaluates_strategy is False
    assert state.executes_simulation is False
    assert state.emits_orders is False
    assert state.in_memory_only is True
    assert state.no_lookahead is True
    assert state.can_continue_to_future_recurrent_transition_contract is True


def test_state_performs_no_external_io() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.fetches_data is False
    assert state.initializes_mt5 is False
    assert state.has_adapter_instance is False
    assert state.request_submission_authorized is False
    assert state.adapter_invocation_authorized is False
    assert state.storage_write_authorized is False
    assert state.can_write_storage is False
    assert state.can_write_network is False
    assert state.execution_authorized is False
    assert state.has_broker_request is False
    assert state.can_submit_order is False
    assert state.is_executable is False


def test_decision_performs_no_additional_transition() -> None:
    decision = bullish_recurrent_progressed_state_decision()

    assert decision.creates_next_state is True
    assert decision.executes_transition is False
    assert decision.advances_cursor is False
    assert decision.consumes_events is False
    assert decision.starts_session is False
    assert decision.starts_replay is False
    assert decision.executes_replay is False
    assert decision.evaluates_strategy is False
    assert decision.executes_simulation is False
    assert decision.emits_orders is False
    assert decision.fetches_data is False
    assert decision.initializes_mt5 is False
    assert decision.has_adapter_instance is False
    assert decision.request_submission_authorized is False
    assert decision.adapter_invocation_authorized is False
    assert decision.storage_write_authorized is False
    assert decision.can_write_storage is False
    assert decision.can_write_network is False
    assert decision.execution_authorized is False
    assert decision.has_broker_request is False
    assert decision.can_submit_order is False
    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "apply_transition",
        "execute_transition",
        "advance_cursor",
        "consume_event",
        "run",
        "run_replay",
        "evaluate_strategy",
        "evaluate_signal",
        "run_simulation",
        "simulate",
        "fetch",
        "download",
        "copy_rates",
        "copy_rates_from",
        "adapter",
        "adapter_instance",
        "repository",
        "connection",
        "cursor",
        "transaction",
        "insert",
        "save",
        "persist",
        "write",
        "execute",
        "send",
        "submit_request",
        "order_request",
        "broker_ticket",
        "send_order",
        "order_send",
    ],
)
def test_state_has_no_execution_or_io_surface(
    attribute_name,
) -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert not hasattr(state, attribute_name)


def test_recurrent_progressed_state_id_is_deterministic() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    assert state.recurrent_progressed_state_id == (
        "XAUUSDm:BUY:"
        "PHASE_8_OFFLINE_REPLAY_RECURRENT_"
        "PROGRESSED_SESSION_STATE:"
        f"STATE_SHA256[{state.state_digest}]"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    source = bullish_recurrent_transition_application_decision()
    decision = bullish_recurrent_progressed_state_decision()

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_RECURRENT_"
        "PROGRESSED_SESSION_STATE_GENERATION:"
        "CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    source = state_blocked_recurrent_application_decision()
    decision = StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(source)

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_RECURRENT_"
        "PROGRESSED_SESSION_STATE_GENERATION:"
        "BLOCKED:"
        "RECURRENT_TRANSITION_APPLICATION_BLOCKED:"
        "RECURRENT_TRANSITION_APPLICATION_BLOCKED"
    )


def test_direct_state_rejects_wrong_schema() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="schema_version"):
        replace(
            state,
            schema_version="2.0",
        )


def test_direct_state_rejects_unsafe_policy() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="strict"):
        replace(
            state,
            policy=(Phase8OfflineReplayRecurrentProgressedSessionStatePolicy(no_lookahead=False)),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        (
            "application_receipt_id",
            "foreign-application-receipt",
        ),
        (
            "recurrent_transition_contract_id",
            "foreign-contract",
        ),
        (
            "prior_source_state_id",
            "foreign-state",
        ),
        ("event_batch_id", "foreign-batch"),
    ],
)
def test_direct_state_rejects_foreign_ids(
    field_name,
    value,
) -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            state,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "application_digest",
        "recurrent_transition_contract_digest",
        "prior_source_state_digest",
        "event_batch_digest",
    ],
)
def test_direct_state_rejects_foreign_digests(
    field_name,
) -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            state,
            **{field_name: "0" * 64},
        )


def test_direct_state_rejects_raw_mode() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match=("Phase8OfflineReplayRecurrentProgressedSessionStateMode"),
    ):
        replace(
            state,
            state_mode=("IMMUTABLE_RECURRENT_PROGRESSED_STATE"),
        )


def test_direct_state_rejects_raw_lifecycle() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match=("Phase8OfflineReplayRecurrentProgressedSessionLifecycle"),
    ):
        replace(
            state,
            lifecycle="ACTIVE",
        )


def test_direct_state_rejects_wrong_version() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="state_version"):
        replace(
            state,
            state_version=5,
        )


def test_direct_state_rejects_wrong_cursor() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(ValueError):
        replace(
            state,
            cursor_index=5,
            consumed_count=5,
            remaining_count=795,
            last_consumed_sequence_index=4,
            next_event_sequence_index=5,
        )


def test_direct_state_rejects_wrong_consumed_count() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="cursor_index must equal consumed_count",
    ):
        replace(
            state,
            consumed_count=5,
            remaining_count=795,
        )


def test_direct_state_rejects_wrong_remaining_count() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="total_event_count",
    ):
        replace(
            state,
            remaining_count=795,
        )


def test_direct_state_rejects_wrong_last_sequence() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="last_consumed_sequence_index",
    ):
        replace(
            state,
            last_consumed_sequence_index=4,
        )


def test_direct_state_rejects_wrong_next_sequence() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="next_event_sequence_index",
    ):
        replace(
            state,
            next_event_sequence_index=5,
        )


def test_direct_state_rejects_wrong_last_event_id() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="last_consumed_event_id",
    ):
        replace(
            state,
            last_consumed_event_id="foreign-event",
        )


def test_direct_state_rejects_wrong_next_event_id() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="next_event_id"):
        replace(
            state,
            next_event_id="foreign-next-event",
        )


def test_direct_state_rejects_completion() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="cannot be complete",
    ):
        replace(
            state,
            completion_reached=True,
        )


def test_direct_state_rejects_wrong_digest() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="state_digest"):
        replace(
            state,
            state_digest="0" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = bullish_recurrent_progressed_state_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            status=(Phase8OfflineReplayRecurrentProgressedSessionStateStatus.BLOCKED),
        )


def test_manual_decision_rejects_missing_state() -> None:
    decision = bullish_recurrent_progressed_state_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            state=None,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(
        state_blocked_recurrent_application_decision()
    )

    with pytest.raises(ValueError, match="duplicates"):
        replace(
            decision,
            blockers=(
                Phase8OfflineReplayRecurrentProgressedSessionStateBlocker.RECURRENT_TRANSITION_APPLICATION_BLOCKED,
                Phase8OfflineReplayRecurrentProgressedSessionStateBlocker.RECURRENT_TRANSITION_APPLICATION_BLOCKED,
            ),
        )


def test_policy_is_immutable() -> None:
    policy = Phase8OfflineReplayRecurrentProgressedSessionStatePolicy()

    with pytest.raises(FrozenInstanceError):
        policy.no_lookahead = False


def test_state_is_immutable() -> None:
    state = bullish_recurrent_progressed_state_decision().state_required

    with pytest.raises(FrozenInstanceError):
        state.cursor_index = 5


def test_decision_is_immutable() -> None:
    decision = bullish_recurrent_progressed_state_decision()

    with pytest.raises(FrozenInstanceError):
        decision.status = Phase8OfflineReplayRecurrentProgressedSessionStateStatus.BLOCKED


def test_state_generation_is_deterministic() -> None:
    factory = StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory()
    source = bullish_recurrent_transition_application_decision()

    first = factory.generate(source).state_required
    second = factory.generate(source).state_required

    assert first.state_digest == second.state_digest
    assert first.canonical_payload == second.canonical_payload
    assert first.last_consumed_event is second.last_consumed_event
    assert first.next_event is second.next_event


def test_function_api_delegates() -> None:
    decision = generate_phase8_offline_replay_recurrent_progressed_session_state(
        bullish_recurrent_transition_application_decision()
    )

    assert decision.is_created is True


def test_factory_aliases_delegate() -> None:
    factory = StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory()
    source = bullish_recurrent_transition_application_decision()
    generated = factory.generate(source)

    assert (
        factory.build(source).state_required.state_digest == generated.state_required.state_digest
    )
    assert (
        factory.evaluate(source).state_required.state_digest
        == generated.state_required.state_digest
    )


def test_public_aliases_are_preserved() -> None:
    assert (
        Phase8OfflineReplayRecurrentProgressedSessionState
        is StrategyPhase8OfflineReplayRecurrentProgressedSessionState
    )
    assert (
        Phase8OfflineReplayRecurrentProgressedSessionStateFactory
        is StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory
    )
