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
from app.strategy.phase8_offline_replay_advanced_session_state import (
    PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_STATE_SCHEMA_VERSION,
    Phase8OfflineReplayAdvancedSessionLifecycle,
    Phase8OfflineReplayAdvancedSessionState,
    Phase8OfflineReplayAdvancedSessionStateBlocker,
    Phase8OfflineReplayAdvancedSessionStateError,
    Phase8OfflineReplayAdvancedSessionStateErrorReason,
    Phase8OfflineReplayAdvancedSessionStateFactory,
    Phase8OfflineReplayAdvancedSessionStateMode,
    Phase8OfflineReplayAdvancedSessionStatePolicy,
    Phase8OfflineReplayAdvancedSessionStateReason,
    Phase8OfflineReplayAdvancedSessionStateStatus,
    StrategyPhase8OfflineReplayAdvancedSessionState,
    StrategyPhase8OfflineReplayAdvancedSessionStateFactory,
    generate_phase8_offline_replay_advanced_session_state,
)
from app.strategy.phase8_offline_replay_transition_application import (
    StrategyPhase8OfflineReplayTransitionApplicationFactory,
)
from tests.test_phase8_offline_replay_transition_application import (
    CAPTURED_AT,
    application_bearish_contract_decision,
    application_blocked_contract_decision,
    application_existing_contract_decision,
    bullish_transition_application_decision,
)


@lru_cache(maxsize=1)
def advanced_bearish_application_decision():
    return StrategyPhase8OfflineReplayTransitionApplicationFactory().generate(
        application_bearish_contract_decision()
    )


@lru_cache(maxsize=1)
def advanced_existing_application_decision():
    return StrategyPhase8OfflineReplayTransitionApplicationFactory().generate(
        application_existing_contract_decision()
    )


@lru_cache(maxsize=1)
def advanced_blocked_application_decision():
    return StrategyPhase8OfflineReplayTransitionApplicationFactory().generate(
        application_blocked_contract_decision()
    )


@lru_cache(maxsize=1)
def bullish_advanced_state_decision():
    return StrategyPhase8OfflineReplayAdvancedSessionStateFactory().generate(
        bullish_transition_application_decision()
    )


def test_invalid_application_decision_is_fail_safe() -> None:
    with pytest.raises(
        Phase8OfflineReplayAdvancedSessionStateError,
        match="INVALID_TRANSITION_APPLICATION_DECISION",
    ) as captured:
        (StrategyPhase8OfflineReplayAdvancedSessionStateFactory().generate("invalid"))

    assert captured.value.reason == (
        Phase8OfflineReplayAdvancedSessionStateErrorReason.INVALID_TRANSITION_APPLICATION_DECISION
    )


def test_default_advanced_state_policy_is_strict() -> None:
    policy = Phase8OfflineReplayAdvancedSessionStatePolicy()

    assert policy.is_strict is True
    assert policy.transition_receipt_verified is True
    assert policy.source_state_immutable is True
    assert policy.counters_match_receipt is True
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
        "source_state_immutable",
        "counters_match_receipt",
        "last_consumed_event_bound",
        "next_event_bound",
        "forward_only",
        "in_memory_only",
        "no_lookahead",
        "no_external_io",
    ],
)
def test_advanced_policy_rejects_non_boolean(
    field_name,
) -> None:
    with pytest.raises(ValueError, match="boolean"):
        Phase8OfflineReplayAdvancedSessionStatePolicy(**{field_name: 1})


def test_bullish_advanced_state_is_created() -> None:
    decision = bullish_advanced_state_decision()

    assert decision.status == (Phase8OfflineReplayAdvancedSessionStateStatus.CREATED)
    assert decision.reason == (Phase8OfflineReplayAdvancedSessionStateReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_state is True


def test_bearish_advanced_state_is_created() -> None:
    decision = StrategyPhase8OfflineReplayAdvancedSessionStateFactory().generate(
        advanced_bearish_application_decision()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.state_required.side == (StrategyOrderSide.SELL)


def test_existing_advanced_state_is_created() -> None:
    decision = StrategyPhase8OfflineReplayAdvancedSessionStateFactory().generate(
        advanced_existing_application_decision()
    )

    assert decision.is_created is True


def test_blocked_application_blocks_advanced_state() -> None:
    decision = StrategyPhase8OfflineReplayAdvancedSessionStateFactory().generate(
        advanced_blocked_application_decision()
    )

    assert decision.is_blocked is True
    assert decision.state is None
    assert decision.reason == (
        Phase8OfflineReplayAdvancedSessionStateReason.TRANSITION_APPLICATION_BLOCKED
    )
    assert decision.blockers == (
        Phase8OfflineReplayAdvancedSessionStateBlocker.TRANSITION_APPLICATION_BLOCKED,
    )


def test_state_required_rejects_blocked_result() -> None:
    decision = StrategyPhase8OfflineReplayAdvancedSessionStateFactory().generate(
        advanced_blocked_application_decision()
    )

    with pytest.raises(
        ValueError,
        match="No Phase 8 advanced offline replay-session",
    ):
        _ = decision.state_required


def test_state_preserves_application_identity() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.transition_application_decision is (bullish_transition_application_decision())
    assert state.application_receipt is (bullish_transition_application_decision().receipt_required)


def test_state_preserves_complete_lineage() -> None:
    state = bullish_advanced_state_decision().state_required
    receipt = state.application_receipt

    assert state.transition_contract is (receipt.transition_contract)
    assert state.source_state is receipt.source_state
    assert state.session_contract is (receipt.session_contract)
    assert state.session_plan is receipt.session_plan
    assert state.event_batch is receipt.event_batch
    assert state.materialization_plan is (receipt.materialization_plan)
    assert state.event_contract is (receipt.event_contract)
    assert state.replay_plan is receipt.replay_plan
    assert state.specification is receipt.specification
    assert state.input_package is receipt.input_package
    assert state.verification_receipt is (receipt.verification_receipt)
    assert state.snapshot is receipt.snapshot
    assert state.contract is receipt.contract
    assert state.dry_run_package is (receipt.dry_run_package)


def test_state_preserves_identifiers() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.application_receipt_id == (state.application_receipt.stable_id)
    assert state.transition_contract_id == (state.transition_contract.stable_id)
    assert state.source_state_id == (state.source_state.stable_id)
    assert state.session_contract_id == (state.session_contract.stable_id)
    assert state.session_plan_id == (state.session_plan.stable_id)
    assert state.event_batch_id == (state.event_batch.stable_id)


def test_state_preserves_digests() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.application_digest == (state.application_receipt.application_digest)
    assert state.transition_contract_digest == (state.transition_contract.transition_digest)
    assert state.source_state_digest == (state.source_state.state_digest)
    assert state.session_contract_digest == (state.session_contract.contract_digest)
    assert state.session_plan_digest == (state.session_plan.session_digest)
    assert state.event_batch_digest == (state.event_batch.batch_digest)


def test_state_preserves_metadata() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.broker_symbol == "XAUUSDm"
    assert state.direction == (DirectionalPermissionDirection.BULLISH)
    assert state.side == StrategyOrderSide.BUY
    assert state.source_name == "EXTERNAL_TEST_FIXTURE"
    assert state.captured_at == CAPTURED_AT
    assert state.schema_version == (PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_STATE_SCHEMA_VERSION)


def test_state_timeframes_are_exact() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.timeframes == (
        Phase8Timeframe.H4,
        Phase8Timeframe.H1,
        Phase8Timeframe.M15,
        Phase8Timeframe.M5,
    )


def test_advanced_counters_are_exact() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.cursor_index == 1
    assert state.consumed_count == 1
    assert state.remaining_count == 799
    assert state.total_event_count == 800
    assert state.last_consumed_sequence_index == 0
    assert state.next_event_sequence_index == 1
    assert state.completion_reached is False


def test_advanced_counters_preserve_total() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.consumed_count + state.remaining_count == state.total_event_count
    assert state.cursor_index == state.consumed_count
    assert state.last_consumed_sequence_index == (state.cursor_index - 1)
    assert state.next_event_sequence_index == (state.cursor_index)


def test_last_consumed_event_matches_receipt() -> None:
    state = bullish_advanced_state_decision().state_required
    expected = state.application_receipt.consumed_event

    assert state.last_consumed_event is expected
    assert state.last_consumed_event_id == expected.stable_id
    assert state.last_consumed_event_digest == (expected.event_digest)
    assert state.last_consumed_event_time == (expected.event_time)
    assert state.last_consumed_event_timeframe == (expected.timeframe)


def test_next_event_matches_receipt() -> None:
    state = bullish_advanced_state_decision().state_required
    expected = state.application_receipt.next_event

    assert state.next_event is expected
    assert state.next_event_id == expected.stable_id
    assert state.next_event_digest == (expected.event_digest)
    assert state.next_event_time == expected.event_time
    assert state.next_event_timeframe == (expected.timeframe)


def test_bound_events_are_closed() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.last_consumed_event.event_time == (state.last_consumed_event.close_time)
    assert state.next_event.event_time == (state.next_event.close_time)
    assert state.last_consumed_event.event_time <= state.captured_at
    assert state.next_event.event_time <= state.captured_at


def test_source_initial_state_remains_unchanged() -> None:
    state = bullish_advanced_state_decision().state_required
    source = state.source_state

    assert state.source_state_preserved is True
    assert source.cursor_index == 0
    assert source.consumed_count == 0
    assert source.remaining_count == 800
    assert source.next_event_sequence_index == 0
    assert source.state_digest == state.source_state_digest


def test_advanced_state_controls_are_exact() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.state_mode == (
        Phase8OfflineReplayAdvancedSessionStateMode.IMMUTABLE_ADVANCED_STATE
    )
    assert state.lifecycle == (Phase8OfflineReplayAdvancedSessionLifecycle.ACTIVE)


def test_state_digest_is_deterministic() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.state_digest == hashlib.sha256(state.canonical_payload.encode("utf-8")).hexdigest()
    assert state.digest_algorithm == "SHA-256"


def test_state_is_reusable_state_only() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.is_ready is True
    assert state.is_advanced_state is True
    assert state.session_initialized is True
    assert state.session_active is True
    assert state.has_next_event is True
    assert state.source_state_preserved is True
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
    assert state.can_continue_to_next_transition_contract is True


def test_state_performs_no_external_io() -> None:
    state = bullish_advanced_state_decision().state_required

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
    decision = bullish_advanced_state_decision()

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
    state = bullish_advanced_state_decision().state_required

    assert not hasattr(state, attribute_name)


def test_advanced_state_id_is_deterministic() -> None:
    state = bullish_advanced_state_decision().state_required

    assert state.advanced_state_id == (
        "XAUUSDm:BUY:"
        "PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_STATE:"
        f"STATE_SHA256[{state.state_digest}]"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    source = bullish_transition_application_decision()
    decision = bullish_advanced_state_decision()

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_"
        "STATE_GENERATION:"
        "CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    source = advanced_blocked_application_decision()
    decision = StrategyPhase8OfflineReplayAdvancedSessionStateFactory().generate(source)

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_"
        "STATE_GENERATION:"
        "BLOCKED:TRANSITION_APPLICATION_BLOCKED:"
        "TRANSITION_APPLICATION_BLOCKED"
    )


def test_direct_state_rejects_wrong_schema() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(ValueError, match="schema_version"):
        replace(
            state,
            schema_version="2.0",
        )


def test_direct_state_rejects_unsafe_policy() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(ValueError, match="strict"):
        replace(
            state,
            policy=(Phase8OfflineReplayAdvancedSessionStatePolicy(no_lookahead=False)),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        (
            "application_receipt_id",
            "foreign-application-receipt",
        ),
        (
            "transition_contract_id",
            "foreign-transition-contract",
        ),
        ("source_state_id", "foreign-source-state"),
        (
            "session_contract_id",
            "foreign-session-contract",
        ),
        ("session_plan_id", "foreign-session-plan"),
        ("event_batch_id", "foreign-event-batch"),
    ],
)
def test_direct_state_rejects_foreign_ids(
    field_name,
    value,
) -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            state,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "application_digest",
        "transition_contract_digest",
        "source_state_digest",
        "session_contract_digest",
        "session_plan_digest",
        "event_batch_digest",
    ],
)
def test_direct_state_rejects_foreign_digests(
    field_name,
) -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            state,
            **{field_name: "0" * 64},
        )


def test_direct_state_rejects_raw_mode() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="Phase8OfflineReplayAdvancedSessionStateMode",
    ):
        replace(
            state,
            state_mode="IMMUTABLE_ADVANCED_STATE",
        )


def test_direct_state_rejects_raw_lifecycle() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="Phase8OfflineReplayAdvancedSessionLifecycle",
    ):
        replace(
            state,
            lifecycle="ACTIVE",
        )


def test_direct_state_rejects_reordered_timeframes() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="deterministic order",
    ):
        replace(
            state,
            timeframes=tuple(reversed(state.timeframes)),
        )


def test_direct_state_rejects_wrong_cursor() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(ValueError):
        replace(
            state,
            cursor_index=2,
            consumed_count=2,
            remaining_count=798,
            last_consumed_sequence_index=1,
            next_event_sequence_index=2,
        )


def test_direct_state_rejects_wrong_consumed_count() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="cursor_index must equal consumed_count",
    ):
        replace(
            state,
            consumed_count=2,
            remaining_count=798,
        )


def test_direct_state_rejects_wrong_remaining_count() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="total_event_count",
    ):
        replace(
            state,
            remaining_count=798,
        )


def test_direct_state_rejects_wrong_last_sequence() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="last_consumed_sequence_index",
    ):
        replace(
            state,
            last_consumed_sequence_index=1,
        )


def test_direct_state_rejects_wrong_next_sequence() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="next_event_sequence_index",
    ):
        replace(
            state,
            next_event_sequence_index=2,
        )


def test_direct_state_rejects_wrong_last_event_id() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="last_consumed_event_id",
    ):
        replace(
            state,
            last_consumed_event_id="foreign-event",
        )


def test_direct_state_rejects_wrong_last_event_digest() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="last_consumed_event_digest",
    ):
        replace(
            state,
            last_consumed_event_digest="0" * 64,
        )


def test_direct_state_rejects_wrong_next_event_id() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(ValueError, match="next_event_id"):
        replace(
            state,
            next_event_id="foreign-next-event",
        )


def test_direct_state_rejects_wrong_next_event_digest() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="next_event_digest",
    ):
        replace(
            state,
            next_event_digest="0" * 64,
        )


def test_direct_state_rejects_completion() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(
        ValueError,
        match="cannot be complete",
    ):
        replace(
            state,
            completion_reached=True,
        )


def test_direct_state_rejects_wrong_digest() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(ValueError, match="state_digest"):
        replace(
            state,
            state_digest="0" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = bullish_advanced_state_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            status=(Phase8OfflineReplayAdvancedSessionStateStatus.BLOCKED),
        )


def test_manual_decision_rejects_missing_state() -> None:
    decision = bullish_advanced_state_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            state=None,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPhase8OfflineReplayAdvancedSessionStateFactory().generate(
        advanced_blocked_application_decision()
    )

    with pytest.raises(ValueError, match="duplicates"):
        replace(
            decision,
            blockers=(
                Phase8OfflineReplayAdvancedSessionStateBlocker.TRANSITION_APPLICATION_BLOCKED,
                Phase8OfflineReplayAdvancedSessionStateBlocker.TRANSITION_APPLICATION_BLOCKED,
            ),
        )


def test_policy_is_immutable() -> None:
    policy = Phase8OfflineReplayAdvancedSessionStatePolicy()

    with pytest.raises(FrozenInstanceError):
        policy.no_lookahead = False


def test_advanced_state_is_immutable() -> None:
    state = bullish_advanced_state_decision().state_required

    with pytest.raises(FrozenInstanceError):
        state.cursor_index = 2


def test_advanced_state_decision_is_immutable() -> None:
    decision = bullish_advanced_state_decision()

    with pytest.raises(FrozenInstanceError):
        decision.status = Phase8OfflineReplayAdvancedSessionStateStatus.BLOCKED


def test_advanced_state_generation_is_deterministic() -> None:
    factory = StrategyPhase8OfflineReplayAdvancedSessionStateFactory()
    source = bullish_transition_application_decision()

    first = factory.generate(source).state_required
    second = factory.generate(source).state_required

    assert first.state_digest == second.state_digest
    assert first.canonical_payload == second.canonical_payload
    assert first.last_consumed_event is second.last_consumed_event
    assert first.next_event is second.next_event


def test_advanced_state_function_api_delegates() -> None:
    decision = generate_phase8_offline_replay_advanced_session_state(
        bullish_transition_application_decision()
    )

    assert decision.is_created is True


def test_advanced_state_factory_aliases_delegate() -> None:
    factory = StrategyPhase8OfflineReplayAdvancedSessionStateFactory()
    source = bullish_transition_application_decision()
    generated = factory.generate(source)

    assert (
        factory.build(source).state_required.state_digest == generated.state_required.state_digest
    )
    assert (
        factory.evaluate(source).state_required.state_digest
        == generated.state_required.state_digest
    )


def test_advanced_state_public_aliases_are_preserved() -> None:
    assert (
        Phase8OfflineReplayAdvancedSessionState is StrategyPhase8OfflineReplayAdvancedSessionState
    )
    assert (
        Phase8OfflineReplayAdvancedSessionStateFactory
        is StrategyPhase8OfflineReplayAdvancedSessionStateFactory
    )
