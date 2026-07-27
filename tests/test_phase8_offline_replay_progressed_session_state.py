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
from app.strategy.phase8_offline_replay_next_transition_application import (
    StrategyPhase8OfflineReplayNextTransitionApplicationFactory,
)
from app.strategy.phase8_offline_replay_progressed_session_state import (
    PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_STATE_SCHEMA_VERSION,
    Phase8OfflineReplayProgressedSessionLifecycle,
    Phase8OfflineReplayProgressedSessionState,
    Phase8OfflineReplayProgressedSessionStateBlocker,
    Phase8OfflineReplayProgressedSessionStateError,
    Phase8OfflineReplayProgressedSessionStateErrorReason,
    Phase8OfflineReplayProgressedSessionStateFactory,
    Phase8OfflineReplayProgressedSessionStateMode,
    Phase8OfflineReplayProgressedSessionStatePolicy,
    Phase8OfflineReplayProgressedSessionStateReason,
    Phase8OfflineReplayProgressedSessionStateStatus,
    StrategyPhase8OfflineReplayProgressedSessionState,
    StrategyPhase8OfflineReplayProgressedSessionStateFactory,
    generate_phase8_offline_replay_progressed_session_state,
)
from tests.test_phase8_offline_replay_next_transition_application import (
    CAPTURED_AT,
    application_bearish_next_contract_decision,
    application_blocked_next_contract_decision,
    application_existing_next_contract_decision,
    bullish_next_transition_application_decision,
)


@lru_cache(maxsize=1)
def progressed_bearish_application_decision():
    return StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(
        application_bearish_next_contract_decision()
    )


@lru_cache(maxsize=1)
def progressed_existing_application_decision():
    return StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(
        application_existing_next_contract_decision()
    )


@lru_cache(maxsize=1)
def progressed_blocked_application_decision():
    return StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(
        application_blocked_next_contract_decision()
    )


@lru_cache(maxsize=1)
def bullish_progressed_state_decision():
    return StrategyPhase8OfflineReplayProgressedSessionStateFactory().generate(
        bullish_next_transition_application_decision()
    )


def test_invalid_application_decision_is_fail_safe() -> None:
    with pytest.raises(
        Phase8OfflineReplayProgressedSessionStateError,
        match="INVALID_NEXT_TRANSITION_APPLICATION_DECISION",
    ) as captured:
        (StrategyPhase8OfflineReplayProgressedSessionStateFactory().generate("invalid"))

    assert captured.value.reason == (
        Phase8OfflineReplayProgressedSessionStateErrorReason.INVALID_NEXT_TRANSITION_APPLICATION_DECISION
    )


def test_default_progressed_policy_is_strict() -> None:
    policy = Phase8OfflineReplayProgressedSessionStatePolicy()

    assert policy.is_strict is True
    assert policy.transition_receipt_verified is True
    assert policy.prior_state_immutable is True
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
        "transition_receipt_verified",
        "prior_state_immutable",
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
def test_progressed_policy_rejects_non_boolean(
    field_name,
) -> None:
    with pytest.raises(ValueError, match="boolean"):
        Phase8OfflineReplayProgressedSessionStatePolicy(**{field_name: 1})


def test_bullish_progressed_state_is_created() -> None:
    decision = bullish_progressed_state_decision()

    assert decision.status == (Phase8OfflineReplayProgressedSessionStateStatus.CREATED)
    assert decision.reason == (Phase8OfflineReplayProgressedSessionStateReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_state is True


def test_bearish_progressed_state_is_created() -> None:
    decision = StrategyPhase8OfflineReplayProgressedSessionStateFactory().generate(
        progressed_bearish_application_decision()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.state_required.side == (StrategyOrderSide.SELL)


def test_existing_progressed_state_is_created() -> None:
    decision = StrategyPhase8OfflineReplayProgressedSessionStateFactory().generate(
        progressed_existing_application_decision()
    )

    assert decision.is_created is True


def test_blocked_application_blocks_progressed_state() -> None:
    decision = StrategyPhase8OfflineReplayProgressedSessionStateFactory().generate(
        progressed_blocked_application_decision()
    )

    assert decision.is_blocked is True
    assert decision.state is None
    assert decision.reason == (
        Phase8OfflineReplayProgressedSessionStateReason.NEXT_TRANSITION_APPLICATION_BLOCKED
    )
    assert decision.blockers == (
        Phase8OfflineReplayProgressedSessionStateBlocker.NEXT_TRANSITION_APPLICATION_BLOCKED,
    )


def test_state_required_rejects_blocked_result() -> None:
    decision = StrategyPhase8OfflineReplayProgressedSessionStateFactory().generate(
        progressed_blocked_application_decision()
    )

    with pytest.raises(
        ValueError,
        match="No Phase 8 progressed offline replay-session",
    ):
        _ = decision.state_required


def test_state_preserves_application_identity() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.next_transition_application_decision is (
        bullish_next_transition_application_decision()
    )
    assert state.application_receipt is (
        bullish_next_transition_application_decision().receipt_required
    )


def test_state_preserves_complete_lineage() -> None:
    state = bullish_progressed_state_decision().state_required
    receipt = state.application_receipt

    assert state.next_transition_contract is (receipt.next_transition_contract)
    assert state.prior_advanced_state is (receipt.advanced_state)
    assert state.prior_application_receipt is (receipt.prior_application_receipt)
    assert state.prior_transition_contract is (receipt.prior_transition_contract)
    assert state.source_state is receipt.source_state
    assert state.session_contract is (receipt.session_contract)
    assert state.session_plan is receipt.session_plan
    assert state.event_batch is receipt.event_batch
    assert state.materialization_plan is (receipt.materialization_plan)
    assert state.event_contract is receipt.event_contract
    assert state.replay_plan is receipt.replay_plan
    assert state.specification is receipt.specification
    assert state.input_package is receipt.input_package
    assert state.verification_receipt is (receipt.verification_receipt)
    assert state.snapshot is receipt.snapshot
    assert state.contract is receipt.contract
    assert state.dry_run_package is (receipt.dry_run_package)


def test_state_preserves_identifiers() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.application_receipt_id == (state.application_receipt.stable_id)
    assert state.next_transition_contract_id == (state.next_transition_contract.stable_id)
    assert state.prior_advanced_state_id == (state.prior_advanced_state.stable_id)
    assert state.prior_application_receipt_id == (state.prior_application_receipt.stable_id)
    assert state.prior_transition_contract_id == (state.prior_transition_contract.stable_id)
    assert state.event_batch_id == (state.event_batch.stable_id)


def test_state_preserves_digests() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.application_digest == (state.application_receipt.application_digest)
    assert state.next_transition_contract_digest == (
        state.next_transition_contract.transition_digest
    )
    assert state.prior_advanced_state_digest == (state.prior_advanced_state.state_digest)
    assert state.prior_application_digest == (state.prior_application_receipt.application_digest)
    assert state.prior_transition_contract_digest == (
        state.prior_transition_contract.transition_digest
    )
    assert state.event_batch_digest == (state.event_batch.batch_digest)


def test_state_preserves_metadata() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.broker_symbol == "XAUUSDm"
    assert state.direction == (DirectionalPermissionDirection.BULLISH)
    assert state.side == StrategyOrderSide.BUY
    assert state.source_name == "EXTERNAL_TEST_FIXTURE"
    assert state.captured_at == CAPTURED_AT
    assert state.schema_version == (PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_STATE_SCHEMA_VERSION)


def test_timeframes_are_exact() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.timeframes == (
        Phase8Timeframe.H4,
        Phase8Timeframe.H1,
        Phase8Timeframe.M15,
        Phase8Timeframe.M5,
    )


def test_progressed_counters_are_exact() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.state_version == 2
    assert state.cursor_index == 2
    assert state.consumed_count == 2
    assert state.remaining_count == 798
    assert state.total_event_count == 800
    assert state.last_consumed_sequence_index == 1
    assert state.next_event_sequence_index == 2
    assert state.completion_reached is False


def test_progressed_counters_preserve_total() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.consumed_count + state.remaining_count == state.total_event_count
    assert state.cursor_index == state.consumed_count
    assert state.last_consumed_sequence_index == (state.cursor_index - 1)
    assert state.next_event_sequence_index == (state.cursor_index)


def test_sequence_progresses_from_prior_state() -> None:
    state = bullish_progressed_state_decision().state_required
    prior = state.prior_advanced_state

    assert state.cursor_index == prior.cursor_index + 1
    assert state.consumed_count == prior.consumed_count + 1
    assert state.remaining_count == prior.remaining_count - 1
    assert state.last_consumed_sequence_index == (prior.last_consumed_sequence_index + 1)


def test_last_consumed_event_matches_receipt() -> None:
    state = bullish_progressed_state_decision().state_required
    expected = state.application_receipt.consumed_event

    assert state.last_consumed_event is expected
    assert state.last_consumed_event_id == expected.stable_id
    assert state.last_consumed_event_digest == (expected.event_digest)
    assert state.last_consumed_event_time == (expected.event_time)
    assert state.last_consumed_event_timeframe == (expected.timeframe)


def test_next_event_matches_receipt() -> None:
    state = bullish_progressed_state_decision().state_required
    expected = state.application_receipt.next_event

    assert state.next_event is expected
    assert state.next_event_id == expected.stable_id
    assert state.next_event_digest == (expected.event_digest)
    assert state.next_event_time == expected.event_time
    assert state.next_event_timeframe == (expected.timeframe)


def test_bound_events_are_closed() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.last_consumed_event.event_time == (state.last_consumed_event.close_time)
    assert state.next_event.event_time == (state.next_event.close_time)
    assert state.last_consumed_event.event_time <= (state.captured_at)
    assert state.next_event.event_time <= state.captured_at


def test_prior_advanced_state_remains_unchanged() -> None:
    state = bullish_progressed_state_decision().state_required
    prior = state.prior_advanced_state

    assert state.prior_state_preserved is True
    assert prior.cursor_index == 1
    assert prior.consumed_count == 1
    assert prior.remaining_count == 799
    assert prior.last_consumed_sequence_index == 0
    assert prior.next_event_sequence_index == 1
    assert prior.state_digest == (state.prior_advanced_state_digest)


def test_progressed_state_controls_are_exact() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.state_mode == (
        Phase8OfflineReplayProgressedSessionStateMode.IMMUTABLE_PROGRESSED_STATE
    )
    assert state.lifecycle == (Phase8OfflineReplayProgressedSessionLifecycle.ACTIVE)


def test_state_digest_is_deterministic() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.state_digest == hashlib.sha256(state.canonical_payload.encode("utf-8")).hexdigest()
    assert state.digest_algorithm == "SHA-256"


def test_state_is_reusable_state_only() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.is_ready is True
    assert state.is_progressed_state is True
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
    assert state.can_continue_to_future_transition_contract is True


def test_state_performs_no_external_io() -> None:
    state = bullish_progressed_state_decision().state_required

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
    decision = bullish_progressed_state_decision()

    assert decision.creates_next_state is True
    assert decision.executes_transition is False
    assert decision.advances_cursor is False
    assert decision.consumes_events is False
    assert decision.starts_session is False
    assert decision.starts_replay is False
    assert decision.executes_replay is False
    assert decision.evaluates_strategy is False
    assert decision.executes_simulation is False
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
    state = bullish_progressed_state_decision().state_required

    assert not hasattr(state, attribute_name)


def test_progressed_state_id_is_deterministic() -> None:
    state = bullish_progressed_state_decision().state_required

    assert state.progressed_state_id == (
        "XAUUSDm:BUY:"
        "PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_STATE:"
        f"STATE_SHA256[{state.state_digest}]"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    source = bullish_next_transition_application_decision()
    decision = bullish_progressed_state_decision()

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_"
        "STATE_GENERATION:"
        "CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    source = progressed_blocked_application_decision()
    decision = StrategyPhase8OfflineReplayProgressedSessionStateFactory().generate(source)

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_"
        "STATE_GENERATION:"
        "BLOCKED:NEXT_TRANSITION_APPLICATION_BLOCKED:"
        "NEXT_TRANSITION_APPLICATION_BLOCKED"
    )


def test_direct_state_rejects_wrong_schema() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="schema_version"):
        replace(
            state,
            schema_version="2.0",
        )


def test_direct_state_rejects_unsafe_policy() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="strict"):
        replace(
            state,
            policy=(Phase8OfflineReplayProgressedSessionStatePolicy(no_lookahead=False)),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        (
            "application_receipt_id",
            "foreign-application-receipt",
        ),
        (
            "next_transition_contract_id",
            "foreign-next-contract",
        ),
        (
            "prior_advanced_state_id",
            "foreign-prior-state",
        ),
        (
            "prior_application_receipt_id",
            "foreign-prior-receipt",
        ),
        (
            "prior_transition_contract_id",
            "foreign-prior-contract",
        ),
        ("event_batch_id", "foreign-event-batch"),
    ],
)
def test_direct_state_rejects_foreign_ids(
    field_name,
    value,
) -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            state,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "application_digest",
        "next_transition_contract_digest",
        "prior_advanced_state_digest",
        "prior_application_digest",
        "prior_transition_contract_digest",
        "event_batch_digest",
    ],
)
def test_direct_state_rejects_foreign_digests(
    field_name,
) -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            state,
            **{field_name: "0" * 64},
        )


def test_direct_state_rejects_raw_mode() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="Phase8OfflineReplayProgressedSessionStateMode",
    ):
        replace(
            state,
            state_mode="IMMUTABLE_PROGRESSED_STATE",
        )


def test_direct_state_rejects_raw_lifecycle() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="Phase8OfflineReplayProgressedSessionLifecycle",
    ):
        replace(
            state,
            lifecycle="ACTIVE",
        )


def test_direct_state_rejects_wrong_version() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="state_version"):
        replace(
            state,
            state_version=3,
        )


def test_direct_state_rejects_wrong_cursor() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(ValueError):
        replace(
            state,
            cursor_index=3,
            consumed_count=3,
            remaining_count=797,
            last_consumed_sequence_index=2,
            next_event_sequence_index=3,
        )


def test_direct_state_rejects_wrong_consumed_count() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="cursor_index must equal consumed_count",
    ):
        replace(
            state,
            consumed_count=3,
            remaining_count=797,
        )


def test_direct_state_rejects_wrong_remaining_count() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="total_event_count",
    ):
        replace(
            state,
            remaining_count=797,
        )


def test_direct_state_rejects_wrong_last_sequence() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="last_consumed_sequence_index",
    ):
        replace(
            state,
            last_consumed_sequence_index=2,
        )


def test_direct_state_rejects_wrong_next_sequence() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="next_event_sequence_index",
    ):
        replace(
            state,
            next_event_sequence_index=3,
        )


def test_direct_state_rejects_wrong_last_event_id() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="last_consumed_event_id",
    ):
        replace(
            state,
            last_consumed_event_id="foreign-event",
        )


def test_direct_state_rejects_wrong_last_event_digest() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="last_consumed_event_digest",
    ):
        replace(
            state,
            last_consumed_event_digest="0" * 64,
        )


def test_direct_state_rejects_wrong_next_event_id() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="next_event_id"):
        replace(
            state,
            next_event_id="foreign-next-event",
        )


def test_direct_state_rejects_wrong_next_event_digest() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="next_event_digest",
    ):
        replace(
            state,
            next_event_digest="0" * 64,
        )


def test_direct_state_rejects_completion() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="cannot be complete",
    ):
        replace(
            state,
            completion_reached=True,
        )


def test_direct_state_rejects_wrong_digest() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(ValueError, match="state_digest"):
        replace(
            state,
            state_digest="0" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = bullish_progressed_state_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            status=(Phase8OfflineReplayProgressedSessionStateStatus.BLOCKED),
        )


def test_manual_decision_rejects_missing_state() -> None:
    decision = bullish_progressed_state_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            state=None,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPhase8OfflineReplayProgressedSessionStateFactory().generate(
        progressed_blocked_application_decision()
    )

    with pytest.raises(ValueError, match="duplicates"):
        replace(
            decision,
            blockers=(
                Phase8OfflineReplayProgressedSessionStateBlocker.NEXT_TRANSITION_APPLICATION_BLOCKED,
                Phase8OfflineReplayProgressedSessionStateBlocker.NEXT_TRANSITION_APPLICATION_BLOCKED,
            ),
        )


def test_policy_is_immutable() -> None:
    policy = Phase8OfflineReplayProgressedSessionStatePolicy()

    with pytest.raises(FrozenInstanceError):
        policy.no_lookahead = False


def test_progressed_state_is_immutable() -> None:
    state = bullish_progressed_state_decision().state_required

    with pytest.raises(FrozenInstanceError):
        state.cursor_index = 3


def test_progressed_decision_is_immutable() -> None:
    decision = bullish_progressed_state_decision()

    with pytest.raises(FrozenInstanceError):
        decision.status = Phase8OfflineReplayProgressedSessionStateStatus.BLOCKED


def test_progressed_state_generation_is_deterministic() -> None:
    factory = StrategyPhase8OfflineReplayProgressedSessionStateFactory()
    source = bullish_next_transition_application_decision()

    first = factory.generate(source).state_required
    second = factory.generate(source).state_required

    assert first.state_digest == second.state_digest
    assert first.canonical_payload == second.canonical_payload
    assert first.last_consumed_event is second.last_consumed_event
    assert first.next_event is second.next_event


def test_progressed_state_function_api_delegates() -> None:
    decision = generate_phase8_offline_replay_progressed_session_state(
        bullish_next_transition_application_decision()
    )

    assert decision.is_created is True


def test_progressed_state_factory_aliases_delegate() -> None:
    factory = StrategyPhase8OfflineReplayProgressedSessionStateFactory()
    source = bullish_next_transition_application_decision()
    generated = factory.generate(source)

    assert (
        factory.build(source).state_required.state_digest == generated.state_required.state_digest
    )
    assert (
        factory.evaluate(source).state_required.state_digest
        == generated.state_required.state_digest
    )


def test_progressed_state_public_aliases_are_preserved() -> None:
    assert (
        Phase8OfflineReplayProgressedSessionState
        is StrategyPhase8OfflineReplayProgressedSessionState
    )
    assert (
        Phase8OfflineReplayProgressedSessionStateFactory
        is StrategyPhase8OfflineReplayProgressedSessionStateFactory
    )
