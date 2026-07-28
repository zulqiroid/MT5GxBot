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
from app.strategy.phase8_offline_replay_iterative_transition_contract import (
    PHASE_8_OFFLINE_REPLAY_ITERATIVE_TRANSITION_CONTRACT_SCHEMA_VERSION,
    Phase8OfflineReplayIterativeTransitionAction,
    Phase8OfflineReplayIterativeTransitionContract,
    Phase8OfflineReplayIterativeTransitionContractBlocker,
    Phase8OfflineReplayIterativeTransitionContractError,
    Phase8OfflineReplayIterativeTransitionContractErrorReason,
    Phase8OfflineReplayIterativeTransitionContractFactory,
    Phase8OfflineReplayIterativeTransitionContractMode,
    Phase8OfflineReplayIterativeTransitionContractPolicy,
    Phase8OfflineReplayIterativeTransitionContractReason,
    Phase8OfflineReplayIterativeTransitionContractStatus,
    StrategyPhase8OfflineReplayIterativeTransitionContract,
    StrategyPhase8OfflineReplayIterativeTransitionContractFactory,
    generate_phase8_offline_replay_iterative_transition_contract,
)
from app.strategy.phase8_offline_replay_recurrent_progressed_session_state import (
    StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory,
)
from tests.test_phase8_offline_replay_recurrent_progressed_session_state import (
    CAPTURED_AT,
    bullish_recurrent_progressed_state_decision,
    state_bearish_recurrent_application_decision,
    state_blocked_recurrent_application_decision,
    state_existing_recurrent_application_decision,
)


@lru_cache(maxsize=1)
def iterative_bearish_source_decision():
    return StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(
        state_bearish_recurrent_application_decision()
    )


@lru_cache(maxsize=1)
def iterative_existing_source_decision():
    return StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(
        state_existing_recurrent_application_decision()
    )


@lru_cache(maxsize=1)
def iterative_blocked_source_decision():
    return StrategyPhase8OfflineReplayRecurrentProgressedSessionStateFactory().generate(
        state_blocked_recurrent_application_decision()
    )


@lru_cache(maxsize=1)
def bullish_iterative_transition_contract_decision():
    return StrategyPhase8OfflineReplayIterativeTransitionContractFactory().generate(
        bullish_recurrent_progressed_state_decision()
    )


def test_invalid_source_decision_is_fail_safe() -> None:
    with pytest.raises(
        Phase8OfflineReplayIterativeTransitionContractError,
        match="INVALID_RECURRENT_PROGRESSED_STATE_DECISION",
    ) as captured:
        (StrategyPhase8OfflineReplayIterativeTransitionContractFactory().generate("invalid"))

    assert captured.value.reason == (
        Phase8OfflineReplayIterativeTransitionContractErrorReason.INVALID_RECURRENT_PROGRESSED_STATE_DECISION
    )


def test_default_policy_is_strict() -> None:
    policy = Phase8OfflineReplayIterativeTransitionContractPolicy()

    assert policy.is_strict is True
    assert policy.source_state_immutable is True
    assert policy.current_event_bound is True
    assert policy.sequence_continuity_verified is True
    assert policy.one_event_transition is True
    assert policy.cursor_increment_by_one is True
    assert policy.counters_remain_consistent is True
    assert policy.next_event_bound is True
    assert policy.forward_only is True
    assert policy.in_memory_only is True
    assert policy.no_lookahead is True
    assert policy.no_external_io is True


@pytest.mark.parametrize(
    "field_name",
    [
        "source_state_immutable",
        "current_event_bound",
        "sequence_continuity_verified",
        "one_event_transition",
        "cursor_increment_by_one",
        "counters_remain_consistent",
        "next_event_bound",
        "forward_only",
        "in_memory_only",
        "no_lookahead",
        "no_external_io",
    ],
)
def test_policy_rejects_non_boolean(field_name) -> None:
    with pytest.raises(ValueError, match="boolean"):
        Phase8OfflineReplayIterativeTransitionContractPolicy(**{field_name: 1})


def test_bullish_iterative_contract_is_created() -> None:
    decision = bullish_iterative_transition_contract_decision()

    assert decision.status == (Phase8OfflineReplayIterativeTransitionContractStatus.CREATED)
    assert decision.reason == (Phase8OfflineReplayIterativeTransitionContractReason.CREATED)
    assert decision.blockers == ()
    assert decision.is_created is True
    assert decision.has_transition_contract is True


def test_bearish_iterative_contract_is_created() -> None:
    decision = StrategyPhase8OfflineReplayIterativeTransitionContractFactory().generate(
        iterative_bearish_source_decision()
    )

    assert decision.is_created is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.transition_contract_required.side == (StrategyOrderSide.SELL)


def test_existing_iterative_contract_is_created() -> None:
    decision = StrategyPhase8OfflineReplayIterativeTransitionContractFactory().generate(
        iterative_existing_source_decision()
    )

    assert decision.is_created is True


def test_blocked_state_blocks_iterative_contract() -> None:
    decision = StrategyPhase8OfflineReplayIterativeTransitionContractFactory().generate(
        iterative_blocked_source_decision()
    )

    assert decision.is_blocked is True
    assert decision.transition_contract is None
    assert decision.reason == (
        Phase8OfflineReplayIterativeTransitionContractReason.RECURRENT_PROGRESSED_STATE_BLOCKED
    )
    assert decision.blockers == (
        Phase8OfflineReplayIterativeTransitionContractBlocker.RECURRENT_PROGRESSED_STATE_BLOCKED,
    )


def test_contract_required_rejects_blocked_result() -> None:
    decision = StrategyPhase8OfflineReplayIterativeTransitionContractFactory().generate(
        iterative_blocked_source_decision()
    )

    with pytest.raises(
        ValueError,
        match="No Phase 8 iterative offline",
    ):
        _ = decision.transition_contract_required


def test_contract_preserves_source_identity() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.recurrent_progressed_state_decision is (
        bullish_recurrent_progressed_state_decision()
    )
    assert contract.source_state is (bullish_recurrent_progressed_state_decision().state_required)


def test_contract_preserves_lineage() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required
    state = contract.source_state

    assert contract.prior_application_receipt is (state.application_receipt)
    assert contract.prior_transition_contract is (state.recurrent_transition_contract)
    assert contract.event_batch is state.event_batch


def test_contract_preserves_identifiers() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.source_state_id == (contract.source_state.stable_id)
    assert contract.prior_application_receipt_id == (contract.prior_application_receipt.stable_id)
    assert contract.prior_transition_contract_id == (contract.prior_transition_contract.stable_id)
    assert contract.event_batch_id == (contract.event_batch.stable_id)


def test_contract_preserves_digests() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.source_state_digest == (contract.source_state.state_digest)
    assert contract.prior_application_digest == (
        contract.prior_application_receipt.application_digest
    )
    assert contract.prior_transition_contract_digest == (
        contract.prior_transition_contract.transition_digest
    )
    assert contract.event_batch_digest == (contract.event_batch.batch_digest)


def test_contract_preserves_metadata() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.broker_symbol == "XAUUSDm"
    assert contract.direction == (DirectionalPermissionDirection.BULLISH)
    assert contract.side == StrategyOrderSide.BUY
    assert contract.source_name == "EXTERNAL_TEST_FIXTURE"
    assert contract.captured_at == CAPTURED_AT
    assert contract.schema_version == (
        PHASE_8_OFFLINE_REPLAY_ITERATIVE_TRANSITION_CONTRACT_SCHEMA_VERSION
    )


def test_timeframes_are_exact() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.timeframes == (
        Phase8Timeframe.H4,
        Phase8Timeframe.H1,
        Phase8Timeframe.M15,
        Phase8Timeframe.M5,
    )


def test_contract_controls_are_exact() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.contract_mode == (
        Phase8OfflineReplayIterativeTransitionContractMode.IMMUTABLE_SINGLE_EVENT
    )
    assert contract.action == (Phase8OfflineReplayIterativeTransitionAction.CONSUME_CURRENT_EVENT)


def test_current_transition_state_is_exact() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.transition_index == 4
    assert contract.current_cursor_index == 4
    assert contract.current_consumed_count == 4
    assert contract.current_remaining_count == 796
    assert contract.prior_last_consumed_sequence_index == 3
    assert contract.current_event_sequence_index == 4
    assert contract.total_event_count == 800


def test_resulting_transition_state_is_exact() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.resulting_cursor_index == 5
    assert contract.resulting_consumed_count == 5
    assert contract.resulting_remaining_count == 795
    assert contract.last_consumed_sequence_index == 4
    assert contract.completion_after_transition is False
    assert contract.next_event_sequence_index == 5


def test_transition_counters_preserve_total() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert (
        contract.current_consumed_count + contract.current_remaining_count
        == contract.total_event_count
    )
    assert (
        contract.resulting_consumed_count + contract.resulting_remaining_count
        == contract.total_event_count
    )


def test_transition_sequence_continuity_is_exact() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.current_event_sequence_index == (
        contract.prior_last_consumed_sequence_index + 1
    )
    assert contract.last_consumed_sequence_index == (contract.current_event_sequence_index)
    assert contract.next_event_sequence_index == (contract.current_event_sequence_index + 1)


def test_current_event_matches_source_cursor() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required
    expected = contract.source_state.next_event

    assert contract.current_event is expected
    assert contract.current_event_sequence_index == 4
    assert contract.current_event_id == expected.stable_id
    assert contract.current_event_digest == (expected.event_digest)
    assert contract.current_event_time == expected.event_time
    assert contract.current_event_timeframe == (expected.timeframe)


def test_next_event_matches_resulting_cursor() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required
    expected = contract.event_batch.events[5]

    assert contract.next_event is expected
    assert contract.next_event_sequence_index == 5
    assert contract.next_event_id == expected.stable_id
    assert contract.next_event_digest == (expected.event_digest)
    assert contract.next_event_time == expected.event_time
    assert contract.next_event_timeframe == (expected.timeframe)


def test_bound_events_are_closed() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.current_event.event_time == (contract.current_event.close_time)
    assert contract.next_event.event_time == (contract.next_event.close_time)
    assert contract.current_event.event_time <= (contract.captured_at)
    assert contract.next_event.event_time <= (contract.captured_at)


def test_source_state_remains_unchanged() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required
    source = contract.source_state

    assert contract.source_state_preserved is True
    assert source.state_version == 4
    assert source.cursor_index == 4
    assert source.consumed_count == 4
    assert source.remaining_count == 796
    assert source.last_consumed_sequence_index == 3
    assert source.next_event_sequence_index == 4
    assert source.state_digest == contract.source_state_digest


def test_transition_digest_is_deterministic() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert (
        contract.transition_digest
        == hashlib.sha256(contract.canonical_payload.encode("utf-8")).hexdigest()
    )
    assert contract.digest_algorithm == "SHA-256"


def test_contract_is_definition_only() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.is_ready is True
    assert contract.contract_only is True
    assert contract.source_state_preserved is True
    assert contract.one_event_transition is True
    assert contract.forward_only is True
    assert contract.in_memory_only is True
    assert contract.no_lookahead is True
    assert contract.executes_transition is False
    assert contract.advances_cursor is False
    assert contract.consumes_events is False
    assert contract.creates_next_state is False
    assert contract.starts_session is False
    assert contract.starts_replay is False
    assert contract.executes_replay is False
    assert contract.evaluates_strategy is False
    assert contract.executes_simulation is False
    assert contract.emits_orders is False
    assert contract.can_continue_to_iterative_transition_application is True


def test_contract_performs_no_external_io() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.fetches_data is False
    assert contract.initializes_mt5 is False
    assert contract.has_adapter_instance is False
    assert contract.request_submission_authorized is False
    assert contract.adapter_invocation_authorized is False
    assert contract.storage_write_authorized is False
    assert contract.can_write_storage is False
    assert contract.can_write_network is False
    assert contract.execution_authorized is False
    assert contract.has_broker_request is False
    assert contract.can_submit_order is False
    assert contract.is_executable is False


def test_decision_performs_no_transition() -> None:
    decision = bullish_iterative_transition_contract_decision()

    assert decision.executes_transition is False
    assert decision.advances_cursor is False
    assert decision.consumes_events is False
    assert decision.creates_next_state is False
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
        "apply",
        "apply_transition",
        "execute_transition",
        "advance_cursor",
        "consume_event",
        "create_next_state",
        "run",
        "run_replay",
        "evaluate_strategy",
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
        "transaction",
        "insert",
        "save",
        "persist",
        "write",
        "execute",
        "send",
        "submit_request",
        "order_request",
        "send_order",
        "order_send",
    ],
)
def test_contract_has_no_execution_or_io_surface(
    attribute_name,
) -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert not hasattr(contract, attribute_name)


def test_iterative_contract_id_is_deterministic() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    assert contract.iterative_transition_contract_id == (
        "XAUUSDm:BUY:"
        "PHASE_8_OFFLINE_REPLAY_ITERATIVE_"
        "TRANSITION_CONTRACT:"
        f"TRANSITION_SHA256[{contract.transition_digest}]"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    source = bullish_recurrent_progressed_state_decision()
    decision = bullish_iterative_transition_contract_decision()

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_ITERATIVE_"
        "TRANSITION_CONTRACT_GENERATION:"
        "CREATED:CREATED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    source = iterative_blocked_source_decision()
    decision = StrategyPhase8OfflineReplayIterativeTransitionContractFactory().generate(source)

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_ITERATIVE_"
        "TRANSITION_CONTRACT_GENERATION:"
        "BLOCKED:"
        "RECURRENT_PROGRESSED_STATE_BLOCKED:"
        "RECURRENT_PROGRESSED_STATE_BLOCKED"
    )


def test_direct_contract_rejects_wrong_schema() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(ValueError, match="schema_version"):
        replace(
            contract,
            schema_version="2.0",
        )


def test_direct_contract_rejects_unsafe_policy() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(ValueError, match="strict"):
        replace(
            contract,
            policy=(Phase8OfflineReplayIterativeTransitionContractPolicy(no_lookahead=False)),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("source_state_id", "foreign-state"),
        (
            "prior_application_receipt_id",
            "foreign-receipt",
        ),
        (
            "prior_transition_contract_id",
            "foreign-contract",
        ),
        ("event_batch_id", "foreign-batch"),
    ],
)
def test_direct_contract_rejects_foreign_ids(
    field_name,
    value,
) -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            contract,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "source_state_digest",
        "prior_application_digest",
        "prior_transition_contract_digest",
        "event_batch_digest",
    ],
)
def test_direct_contract_rejects_foreign_digests(
    field_name,
) -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            contract,
            **{field_name: "0" * 64},
        )


def test_direct_contract_rejects_raw_mode() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="IterativeTransitionContractMode",
    ):
        replace(
            contract,
            contract_mode="IMMUTABLE_SINGLE_EVENT",
        )


def test_direct_contract_rejects_raw_action() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="IterativeTransitionAction",
    ):
        replace(
            contract,
            action="CONSUME_CURRENT_EVENT",
        )


def test_direct_contract_rejects_wrong_transition_index() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(ValueError, match="transition_index"):
        replace(
            contract,
            transition_index=5,
        )


def test_direct_contract_rejects_wrong_consumed_count() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(ValueError, match="transition_index"):
        replace(
            contract,
            current_consumed_count=5,
            current_remaining_count=795,
        )


def test_direct_contract_rejects_wrong_remaining_count() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="total_event_count",
    ):
        replace(
            contract,
            current_remaining_count=795,
        )


def test_direct_contract_rejects_wrong_current_sequence() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="current_event_sequence_index",
    ):
        replace(
            contract,
            current_event_sequence_index=5,
            last_consumed_sequence_index=5,
        )


def test_direct_contract_rejects_wrong_current_event_id() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(ValueError, match="current_event_id"):
        replace(
            contract,
            current_event_id="foreign-event",
        )


def test_direct_contract_rejects_wrong_current_digest() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="current_event_digest",
    ):
        replace(
            contract,
            current_event_digest="0" * 64,
        )


def test_direct_contract_rejects_wrong_result_cursor() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="resulting_cursor_index",
    ):
        replace(
            contract,
            resulting_cursor_index=6,
            next_event_sequence_index=6,
        )


def test_direct_contract_rejects_wrong_result_consumed() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="resulting_consumed_count",
    ):
        replace(
            contract,
            resulting_consumed_count=6,
            resulting_remaining_count=794,
        )


def test_direct_contract_rejects_wrong_next_event_id() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(ValueError, match="next_event_id"):
        replace(
            contract,
            next_event_id="foreign-next-event",
        )


def test_direct_contract_rejects_wrong_next_digest() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="next_event_digest",
    ):
        replace(
            contract,
            next_event_digest="0" * 64,
        )


def test_direct_contract_rejects_completion() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="completion_after_transition",
    ):
        replace(
            contract,
            completion_after_transition=True,
        )


def test_direct_contract_rejects_wrong_digest() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(
        ValueError,
        match="transition_digest",
    ):
        replace(
            contract,
            transition_digest="0" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = bullish_iterative_transition_contract_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            status=(Phase8OfflineReplayIterativeTransitionContractStatus.BLOCKED),
        )


def test_manual_decision_rejects_missing_contract() -> None:
    decision = bullish_iterative_transition_contract_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            transition_contract=None,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPhase8OfflineReplayIterativeTransitionContractFactory().generate(
        iterative_blocked_source_decision()
    )

    with pytest.raises(ValueError, match="duplicates"):
        replace(
            decision,
            blockers=(
                Phase8OfflineReplayIterativeTransitionContractBlocker.RECURRENT_PROGRESSED_STATE_BLOCKED,
                Phase8OfflineReplayIterativeTransitionContractBlocker.RECURRENT_PROGRESSED_STATE_BLOCKED,
            ),
        )


def test_policy_is_immutable() -> None:
    policy = Phase8OfflineReplayIterativeTransitionContractPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.no_lookahead = False


def test_contract_is_immutable() -> None:
    contract = bullish_iterative_transition_contract_decision().transition_contract_required

    with pytest.raises(FrozenInstanceError):
        contract.resulting_cursor_index = 6


def test_decision_is_immutable() -> None:
    decision = bullish_iterative_transition_contract_decision()

    with pytest.raises(FrozenInstanceError):
        decision.status = Phase8OfflineReplayIterativeTransitionContractStatus.BLOCKED


def test_contract_generation_is_deterministic() -> None:
    factory = StrategyPhase8OfflineReplayIterativeTransitionContractFactory()
    source = bullish_recurrent_progressed_state_decision()

    first = factory.generate(source).transition_contract_required
    second = factory.generate(source).transition_contract_required

    assert first.transition_digest == (second.transition_digest)
    assert first.canonical_payload == (second.canonical_payload)
    assert first.current_event is second.current_event
    assert first.next_event is second.next_event


def test_function_api_delegates() -> None:
    decision = generate_phase8_offline_replay_iterative_transition_contract(
        bullish_recurrent_progressed_state_decision()
    )

    assert decision.is_created is True


def test_factory_aliases_delegate() -> None:
    factory = StrategyPhase8OfflineReplayIterativeTransitionContractFactory()
    source = bullish_recurrent_progressed_state_decision()
    generated = factory.generate(source)

    assert factory.build(source).transition_contract_required.transition_digest == (
        generated.transition_contract_required.transition_digest
    )
    assert factory.evaluate(source).transition_contract_required.transition_digest == (
        generated.transition_contract_required.transition_digest
    )


def test_public_aliases_are_preserved() -> None:
    assert (
        Phase8OfflineReplayIterativeTransitionContract
        is StrategyPhase8OfflineReplayIterativeTransitionContract
    )
    assert (
        Phase8OfflineReplayIterativeTransitionContractFactory
        is StrategyPhase8OfflineReplayIterativeTransitionContractFactory
    )
