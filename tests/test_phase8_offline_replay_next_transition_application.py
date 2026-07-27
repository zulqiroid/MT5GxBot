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
    PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_APPLICATION_SCHEMA_VERSION,
    Phase8OfflineReplayNextTransitionApplicationBlocker,
    Phase8OfflineReplayNextTransitionApplicationError,
    Phase8OfflineReplayNextTransitionApplicationErrorReason,
    Phase8OfflineReplayNextTransitionApplicationFactory,
    Phase8OfflineReplayNextTransitionApplicationMode,
    Phase8OfflineReplayNextTransitionApplicationPolicy,
    Phase8OfflineReplayNextTransitionApplicationReason,
    Phase8OfflineReplayNextTransitionApplicationReceipt,
    Phase8OfflineReplayNextTransitionApplicationStatus,
    StrategyPhase8OfflineReplayNextTransitionApplicationFactory,
    StrategyPhase8OfflineReplayNextTransitionApplicationReceipt,
    apply_phase8_offline_replay_next_transition,
)
from app.strategy.phase8_offline_replay_next_transition_contract import (
    StrategyPhase8OfflineReplayNextTransitionContractFactory,
)
from tests.test_phase8_offline_replay_next_transition_contract import (
    CAPTURED_AT,
    bullish_next_transition_contract_decision,
    next_bearish_advanced_state_decision,
    next_blocked_advanced_state_decision,
    next_existing_advanced_state_decision,
)


@lru_cache(maxsize=1)
def application_bearish_next_contract_decision():
    return StrategyPhase8OfflineReplayNextTransitionContractFactory().generate(
        next_bearish_advanced_state_decision()
    )


@lru_cache(maxsize=1)
def application_existing_next_contract_decision():
    return StrategyPhase8OfflineReplayNextTransitionContractFactory().generate(
        next_existing_advanced_state_decision()
    )


@lru_cache(maxsize=1)
def application_blocked_next_contract_decision():
    return StrategyPhase8OfflineReplayNextTransitionContractFactory().generate(
        next_blocked_advanced_state_decision()
    )


@lru_cache(maxsize=1)
def bullish_next_transition_application_decision():
    return StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(
        bullish_next_transition_contract_decision()
    )


def test_invalid_next_contract_is_fail_safe() -> None:
    with pytest.raises(
        Phase8OfflineReplayNextTransitionApplicationError,
        match="INVALID_NEXT_TRANSITION_CONTRACT_DECISION",
    ) as captured:
        (StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate("invalid"))

    assert captured.value.reason == (
        Phase8OfflineReplayNextTransitionApplicationErrorReason.INVALID_NEXT_TRANSITION_CONTRACT_DECISION
    )


def test_default_application_policy_is_strict() -> None:
    policy = Phase8OfflineReplayNextTransitionApplicationPolicy()

    assert policy.is_strict is True
    assert policy.advanced_state_immutable is True
    assert policy.contract_verified is True
    assert policy.consume_exactly_one_event is True
    assert policy.continuity_verified is True
    assert policy.cursor_increment_by_one is True
    assert policy.counters_remain_consistent is True
    assert policy.next_event_bound is True
    assert policy.in_memory_only is True
    assert policy.no_lookahead is True
    assert policy.no_external_io is True


@pytest.mark.parametrize(
    "field_name",
    [
        "advanced_state_immutable",
        "contract_verified",
        "consume_exactly_one_event",
        "continuity_verified",
        "cursor_increment_by_one",
        "counters_remain_consistent",
        "next_event_bound",
        "in_memory_only",
        "no_lookahead",
        "no_external_io",
    ],
)
def test_policy_rejects_non_boolean(field_name) -> None:
    with pytest.raises(ValueError, match="boolean"):
        Phase8OfflineReplayNextTransitionApplicationPolicy(**{field_name: 1})


def test_bullish_next_transition_is_applied() -> None:
    decision = bullish_next_transition_application_decision()

    assert decision.status == (Phase8OfflineReplayNextTransitionApplicationStatus.APPLIED)
    assert decision.reason == (Phase8OfflineReplayNextTransitionApplicationReason.APPLIED)
    assert decision.blockers == ()
    assert decision.is_applied is True
    assert decision.has_receipt is True


def test_bearish_next_transition_is_applied() -> None:
    decision = StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(
        application_bearish_next_contract_decision()
    )

    assert decision.is_applied is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.receipt_required.side == (StrategyOrderSide.SELL)


def test_existing_next_transition_is_applied() -> None:
    decision = StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(
        application_existing_next_contract_decision()
    )

    assert decision.is_applied is True


def test_blocked_contract_blocks_application() -> None:
    decision = StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(
        application_blocked_next_contract_decision()
    )

    assert decision.is_blocked is True
    assert decision.receipt is None
    assert decision.reason == (
        Phase8OfflineReplayNextTransitionApplicationReason.NEXT_TRANSITION_CONTRACT_BLOCKED
    )
    assert decision.blockers == (
        Phase8OfflineReplayNextTransitionApplicationBlocker.NEXT_TRANSITION_CONTRACT_BLOCKED,
    )


def test_receipt_required_rejects_blocked_result() -> None:
    decision = StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(
        application_blocked_next_contract_decision()
    )

    with pytest.raises(
        ValueError,
        match="No Phase 8 next offline replay-transition",
    ):
        _ = decision.receipt_required


def test_receipt_preserves_contract_identity() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.next_transition_contract_decision is (
        bullish_next_transition_contract_decision()
    )
    assert receipt.next_transition_contract is (
        bullish_next_transition_contract_decision().transition_contract_required
    )


def test_receipt_preserves_lineage() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required
    contract = receipt.next_transition_contract

    assert receipt.advanced_state is (contract.advanced_state)
    assert receipt.prior_application_receipt is (contract.application_receipt)
    assert receipt.prior_transition_contract is (contract.prior_transition_contract)
    assert receipt.source_state is contract.source_state
    assert receipt.session_contract is (contract.session_contract)
    assert receipt.session_plan is contract.session_plan
    assert receipt.event_batch is contract.event_batch
    assert receipt.materialization_plan is (contract.materialization_plan)
    assert receipt.event_contract is (contract.event_contract)
    assert receipt.replay_plan is contract.replay_plan
    assert receipt.specification is contract.specification
    assert receipt.input_package is contract.input_package
    assert receipt.verification_receipt is (contract.verification_receipt)
    assert receipt.snapshot is contract.snapshot
    assert receipt.contract is contract.contract
    assert receipt.dry_run_package is (contract.dry_run_package)


def test_receipt_preserves_identifiers() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.next_transition_contract_id == (receipt.next_transition_contract.stable_id)
    assert receipt.advanced_state_id == (receipt.advanced_state.stable_id)
    assert receipt.prior_application_receipt_id == (receipt.prior_application_receipt.stable_id)
    assert receipt.prior_transition_contract_id == (receipt.prior_transition_contract.stable_id)
    assert receipt.event_batch_id == (receipt.event_batch.stable_id)


def test_receipt_preserves_digests() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.next_transition_contract_digest == (
        receipt.next_transition_contract.transition_digest
    )
    assert receipt.advanced_state_digest == (receipt.advanced_state.state_digest)
    assert receipt.prior_application_digest == (
        receipt.prior_application_receipt.application_digest
    )
    assert receipt.prior_transition_contract_digest == (
        receipt.prior_transition_contract.transition_digest
    )
    assert receipt.event_batch_digest == (receipt.event_batch.batch_digest)


def test_receipt_preserves_metadata() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.broker_symbol == "XAUUSDm"
    assert receipt.direction == (DirectionalPermissionDirection.BULLISH)
    assert receipt.side == StrategyOrderSide.BUY
    assert receipt.source_name == "EXTERNAL_TEST_FIXTURE"
    assert receipt.captured_at == CAPTURED_AT
    assert receipt.schema_version == (
        PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_APPLICATION_SCHEMA_VERSION
    )


def test_timeframes_are_exact() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.timeframes == (
        Phase8Timeframe.H4,
        Phase8Timeframe.H1,
        Phase8Timeframe.M15,
        Phase8Timeframe.M5,
    )


def test_prior_state_is_exact() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.transition_index == 1
    assert receipt.prior_cursor_index == 1
    assert receipt.prior_consumed_count == 1
    assert receipt.prior_remaining_count == 799
    assert receipt.prior_last_consumed_sequence_index == 0
    assert receipt.total_event_count == 800


def test_resulting_state_is_exact() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.resulting_cursor_index == 2
    assert receipt.resulting_consumed_count == 2
    assert receipt.resulting_remaining_count == 798
    assert receipt.last_consumed_sequence_index == 1
    assert receipt.completion_reached is False
    assert receipt.next_event_available is True
    assert receipt.next_event_sequence_index == 2


def test_counters_preserve_total() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.prior_consumed_count + receipt.prior_remaining_count == receipt.total_event_count
    assert (
        receipt.resulting_consumed_count + receipt.resulting_remaining_count
        == receipt.total_event_count
    )


def test_sequence_continuity_is_exact() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.consumed_event_sequence_index == (receipt.prior_last_consumed_sequence_index + 1)
    assert receipt.last_consumed_sequence_index == (receipt.consumed_event_sequence_index)
    assert receipt.next_event_sequence_index == (receipt.consumed_event_sequence_index + 1)


def test_consumed_event_matches_contract() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required
    expected = receipt.next_transition_contract.current_event

    assert receipt.consumed_event is expected
    assert receipt.consumed_event_sequence_index == 1
    assert receipt.consumed_event_id == expected.stable_id
    assert receipt.consumed_event_digest == (expected.event_digest)
    assert receipt.consumed_event_time == (expected.event_time)
    assert receipt.consumed_event_timeframe == (expected.timeframe)


def test_next_event_matches_contract() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required
    expected = receipt.next_transition_contract.next_event

    assert receipt.next_event is expected
    assert receipt.next_event_sequence_index == 2
    assert receipt.next_event_id == expected.stable_id
    assert receipt.next_event_digest == (expected.event_digest)
    assert receipt.next_event_time == expected.event_time
    assert receipt.next_event_timeframe == (expected.timeframe)


def test_events_are_closed() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.consumed_event.event_time == (receipt.consumed_event.close_time)
    assert receipt.next_event.event_time == (receipt.next_event.close_time)
    assert receipt.consumed_event.event_time <= (receipt.captured_at)
    assert receipt.next_event.event_time <= (receipt.captured_at)


def test_advanced_source_state_remains_unchanged() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required
    source = receipt.advanced_state

    assert receipt.advanced_source_state_preserved is True
    assert source.cursor_index == 1
    assert source.consumed_count == 1
    assert source.remaining_count == 799
    assert source.last_consumed_sequence_index == 0
    assert source.next_event_sequence_index == 1
    assert source.state_digest == (receipt.advanced_state_digest)


def test_application_mode_is_exact() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.application_mode == (
        Phase8OfflineReplayNextTransitionApplicationMode.PURE_IMMUTABLE_IN_MEMORY
    )


def test_application_digest_is_deterministic() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert (
        receipt.application_digest
        == hashlib.sha256(receipt.canonical_payload.encode("utf-8")).hexdigest()
    )
    assert receipt.digest_algorithm == "SHA-256"


def test_receipt_applies_one_transition_only() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.is_applied is True
    assert receipt.executes_transition is True
    assert receipt.advances_cursor is True
    assert receipt.consumes_events is True
    assert receipt.creates_next_state is False
    assert receipt.in_memory_only is True
    assert receipt.no_lookahead is True
    assert receipt.starts_session is False
    assert receipt.starts_replay is False
    assert receipt.executes_replay is False
    assert receipt.evaluates_strategy is False
    assert receipt.executes_simulation is False
    assert receipt.emits_orders is False
    assert receipt.can_continue_to_next_advanced_state is True


def test_receipt_performs_no_external_io() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.fetches_data is False
    assert receipt.initializes_mt5 is False
    assert receipt.has_adapter_instance is False
    assert receipt.request_submission_authorized is False
    assert receipt.adapter_invocation_authorized is False
    assert receipt.storage_write_authorized is False
    assert receipt.can_write_storage is False
    assert receipt.can_write_network is False
    assert receipt.execution_authorized is False
    assert receipt.has_broker_request is False
    assert receipt.can_submit_order is False
    assert receipt.is_executable is False


def test_decision_has_no_external_execution() -> None:
    decision = bullish_next_transition_application_decision()

    assert decision.executes_transition is True
    assert decision.advances_cursor is True
    assert decision.consumes_events is True
    assert decision.creates_next_state is False
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
        "create_next_state",
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
def test_receipt_has_no_external_execution_surface(
    attribute_name,
) -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert not hasattr(receipt, attribute_name)


def test_application_receipt_id_is_deterministic() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    assert receipt.application_receipt_id == (
        "XAUUSDm:BUY:"
        "PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_"
        "APPLICATION:"
        "APPLICATION_SHA256["
        f"{receipt.application_digest}]"
    )


def test_created_decision_stable_id_is_deterministic() -> None:
    source = bullish_next_transition_contract_decision()
    decision = bullish_next_transition_application_decision()

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_"
        "APPLICATION:"
        "APPLIED:APPLIED:NONE"
    )


def test_blocked_decision_stable_id_is_deterministic() -> None:
    source = application_blocked_next_contract_decision()
    decision = StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(source)

    assert decision.stable_id == (
        f"{source.stable_id}:"
        "PHASE_8_OFFLINE_REPLAY_NEXT_TRANSITION_"
        "APPLICATION:"
        "BLOCKED:NEXT_TRANSITION_CONTRACT_BLOCKED:"
        "NEXT_TRANSITION_CONTRACT_BLOCKED"
    )


def test_direct_receipt_rejects_wrong_schema() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(ValueError, match="schema_version"):
        replace(
            receipt,
            schema_version="2.0",
        )


def test_direct_receipt_rejects_unsafe_policy() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(ValueError, match="strict"):
        replace(
            receipt,
            policy=(Phase8OfflineReplayNextTransitionApplicationPolicy(no_lookahead=False)),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        (
            "next_transition_contract_id",
            "foreign-next-contract",
        ),
        ("advanced_state_id", "foreign-state"),
        (
            "prior_application_receipt_id",
            "foreign-receipt",
        ),
        (
            "prior_transition_contract_id",
            "foreign-prior-contract",
        ),
        ("event_batch_id", "foreign-event-batch"),
    ],
)
def test_direct_receipt_rejects_foreign_ids(
    field_name,
    value,
) -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            receipt,
            **{field_name: value},
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "next_transition_contract_digest",
        "advanced_state_digest",
        "prior_application_digest",
        "prior_transition_contract_digest",
        "event_batch_digest",
    ],
)
def test_direct_receipt_rejects_foreign_digests(
    field_name,
) -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(ValueError, match=field_name):
        replace(
            receipt,
            **{field_name: "0" * 64},
        )


def test_direct_receipt_rejects_raw_mode() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(
        ValueError,
        match=("Phase8OfflineReplayNextTransitionApplicationMode"),
    ):
        replace(
            receipt,
            application_mode="PURE_IMMUTABLE_IN_MEMORY",
        )


def test_direct_receipt_rejects_wrong_transition_index() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(ValueError, match="transition_index"):
        replace(
            receipt,
            transition_index=2,
        )


def test_direct_receipt_rejects_wrong_prior_cursor() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(ValueError):
        replace(
            receipt,
            prior_cursor_index=2,
            prior_consumed_count=2,
            prior_remaining_count=798,
            prior_last_consumed_sequence_index=1,
            consumed_event_sequence_index=2,
            resulting_cursor_index=3,
            resulting_consumed_count=3,
            resulting_remaining_count=797,
            last_consumed_sequence_index=2,
            next_event_sequence_index=3,
        )


def test_direct_receipt_rejects_wrong_consumed_id() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(ValueError, match="consumed_event_id"):
        replace(
            receipt,
            consumed_event_id="foreign-event",
        )


def test_direct_receipt_rejects_wrong_consumed_digest() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(
        ValueError,
        match="consumed_event_digest",
    ):
        replace(
            receipt,
            consumed_event_digest="0" * 64,
        )


def test_direct_receipt_rejects_wrong_result_cursor() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(
        ValueError,
        match="resulting_cursor_index",
    ):
        replace(
            receipt,
            resulting_cursor_index=3,
            next_event_sequence_index=3,
        )


def test_direct_receipt_rejects_wrong_next_id() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(ValueError, match="next_event_id"):
        replace(
            receipt,
            next_event_id="foreign-next-event",
        )


def test_direct_receipt_rejects_wrong_next_digest() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(
        ValueError,
        match="next_event_digest",
    ):
        replace(
            receipt,
            next_event_digest="0" * 64,
        )


def test_direct_receipt_rejects_completion() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(
        ValueError,
        match="completion_reached",
    ):
        replace(
            receipt,
            completion_reached=True,
        )


def test_direct_receipt_rejects_missing_next_event() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(
        ValueError,
        match="following replay event",
    ):
        replace(
            receipt,
            next_event_available=False,
        )


def test_direct_receipt_rejects_wrong_digest() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(
        ValueError,
        match="application_digest",
    ):
        replace(
            receipt,
            application_digest="0" * 64,
        )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = bullish_next_transition_application_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            status=(Phase8OfflineReplayNextTransitionApplicationStatus.BLOCKED),
        )


def test_manual_decision_rejects_missing_receipt() -> None:
    decision = bullish_next_transition_application_decision()

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            receipt=None,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPhase8OfflineReplayNextTransitionApplicationFactory().generate(
        application_blocked_next_contract_decision()
    )

    with pytest.raises(ValueError, match="duplicates"):
        replace(
            decision,
            blockers=(
                Phase8OfflineReplayNextTransitionApplicationBlocker.NEXT_TRANSITION_CONTRACT_BLOCKED,
                Phase8OfflineReplayNextTransitionApplicationBlocker.NEXT_TRANSITION_CONTRACT_BLOCKED,
            ),
        )


def test_policy_is_immutable() -> None:
    policy = Phase8OfflineReplayNextTransitionApplicationPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.no_lookahead = False


def test_receipt_is_immutable() -> None:
    receipt = bullish_next_transition_application_decision().receipt_required

    with pytest.raises(FrozenInstanceError):
        receipt.resulting_cursor_index = 3


def test_decision_is_immutable() -> None:
    decision = bullish_next_transition_application_decision()

    with pytest.raises(FrozenInstanceError):
        decision.status = Phase8OfflineReplayNextTransitionApplicationStatus.BLOCKED


def test_application_is_deterministic() -> None:
    factory = StrategyPhase8OfflineReplayNextTransitionApplicationFactory()
    source = bullish_next_transition_contract_decision()

    first = factory.generate(source).receipt_required
    second = factory.generate(source).receipt_required

    assert first.application_digest == (second.application_digest)
    assert first.canonical_payload == (second.canonical_payload)
    assert first.consumed_event is second.consumed_event
    assert first.next_event is second.next_event


def test_function_api_delegates() -> None:
    decision = apply_phase8_offline_replay_next_transition(
        bullish_next_transition_contract_decision()
    )

    assert decision.is_applied is True


def test_factory_aliases_delegate() -> None:
    factory = StrategyPhase8OfflineReplayNextTransitionApplicationFactory()
    source = bullish_next_transition_contract_decision()
    generated = factory.generate(source)

    assert (
        factory.apply(source).receipt_required.application_digest
        == generated.receipt_required.application_digest
    )
    assert (
        factory.build(source).receipt_required.application_digest
        == generated.receipt_required.application_digest
    )
    assert (
        factory.evaluate(source).receipt_required.application_digest
        == generated.receipt_required.application_digest
    )


def test_public_aliases_are_preserved() -> None:
    assert (
        Phase8OfflineReplayNextTransitionApplicationReceipt
        is StrategyPhase8OfflineReplayNextTransitionApplicationReceipt
    )
    assert (
        Phase8OfflineReplayNextTransitionApplicationFactory
        is StrategyPhase8OfflineReplayNextTransitionApplicationFactory
    )
