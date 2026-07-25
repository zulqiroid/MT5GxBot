from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.lifecycle import (
    TERMINAL_STATUSES,
    TradeLifecycle,
    TradeLifecycleEvent,
    can_transition,
)
from app.domain.trading import (
    EntryType,
    TradePlan,
    TradePlanStatus,
    TradeSide,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def create_plan(**overrides: object) -> TradePlan:
    values: dict[str, object] = {
        "symbol": "XAUUSD",
        "side": TradeSide.BUY,
        "entry_type": EntryType.MARKET,
        "entry_price": "2400.00",
        "stop_loss": "2390.00",
        "take_profit": "2420.00",
        "risk_percent": "0.25",
        "strategy_id": "smc-continuation",
        "setup_id": "setup-001",
    }
    values.update(overrides)

    return TradePlan(**values)


def create_lifecycle() -> TradeLifecycle:
    return TradeLifecycle.create(
        trade_id="trade-001",
        plan=create_plan(),
        created_at=NOW,
    )


def test_new_lifecycle_starts_planned() -> None:
    lifecycle = create_lifecycle()

    assert lifecycle.trade_id == "trade-001"
    assert lifecycle.status == TradePlanStatus.PLANNED
    assert lifecycle.created_at == NOW
    assert lifecycle.updated_at == NOW
    assert lifecycle.events == ()
    assert lifecycle.event_count == 0
    assert lifecycle.next_sequence == 1
    assert lifecycle.is_terminal is False


def test_complete_happy_path_is_supported() -> None:
    planned = create_lifecycle()

    armed = planned.transition_to(
        TradePlanStatus.ARMED,
        occurred_at=NOW + timedelta(seconds=1),
    )
    submitted = armed.transition_to(
        TradePlanStatus.SUBMITTED,
        occurred_at=NOW + timedelta(seconds=2),
    )
    filled = submitted.transition_to(
        TradePlanStatus.FILLED,
        occurred_at=NOW + timedelta(seconds=3),
    )
    closed = filled.transition_to(
        TradePlanStatus.CLOSED,
        occurred_at=NOW + timedelta(seconds=4),
        reason="Take profit filled",
    )

    assert closed.status == TradePlanStatus.CLOSED
    assert closed.is_terminal is True
    assert closed.event_count == 4
    assert closed.next_sequence == 5
    assert closed.events[-1].reason == "Take profit filled"


def test_transition_returns_new_immutable_lifecycle() -> None:
    original = create_lifecycle()

    transitioned = original.transition_to(
        TradePlanStatus.ARMED,
        occurred_at=NOW + timedelta(seconds=1),
    )

    assert original.status == TradePlanStatus.PLANNED
    assert original.events == ()
    assert transitioned.status == TradePlanStatus.ARMED
    assert transitioned.event_count == 1

    with pytest.raises(FrozenInstanceError):
        transitioned.status = TradePlanStatus.CANCELLED


@pytest.mark.parametrize(
    ("current_status", "target_status", "expected"),
    [
        (
            TradePlanStatus.PLANNED,
            TradePlanStatus.ARMED,
            True,
        ),
        (
            TradePlanStatus.PLANNED,
            TradePlanStatus.SUBMITTED,
            False,
        ),
        (
            TradePlanStatus.ARMED,
            TradePlanStatus.SUBMITTED,
            True,
        ),
        (
            TradePlanStatus.SUBMITTED,
            TradePlanStatus.FILLED,
            True,
        ),
        (
            TradePlanStatus.FILLED,
            TradePlanStatus.CLOSED,
            True,
        ),
        (
            TradePlanStatus.CLOSED,
            TradePlanStatus.ARMED,
            False,
        ),
    ],
)
def test_transition_matrix(
    current_status: TradePlanStatus,
    target_status: TradePlanStatus,
    expected: bool,
) -> None:
    assert can_transition(current_status, target_status) is expected


def test_available_transitions_are_exposed() -> None:
    lifecycle = create_lifecycle()

    assert lifecycle.available_transitions == frozenset(
        {
            TradePlanStatus.ARMED,
            TradePlanStatus.CANCELLED,
            TradePlanStatus.REJECTED,
        }
    )


def test_invalid_state_jump_is_blocked() -> None:
    lifecycle = create_lifecycle()

    with pytest.raises(ValueError, match="Invalid lifecycle transition"):
        lifecycle.transition_to(
            TradePlanStatus.SUBMITTED,
            occurred_at=NOW + timedelta(seconds=1),
        )


def test_same_state_transition_is_blocked() -> None:
    lifecycle = create_lifecycle()

    with pytest.raises(ValueError, match="same status"):
        lifecycle.transition_to(
            TradePlanStatus.PLANNED,
            occurred_at=NOW + timedelta(seconds=1),
        )


@pytest.mark.parametrize(
    "terminal_status",
    [
        TradePlanStatus.CANCELLED,
        TradePlanStatus.REJECTED,
    ],
)
def test_terminal_transition_requires_reason(
    terminal_status: TradePlanStatus,
) -> None:
    lifecycle = create_lifecycle()

    with pytest.raises(ValueError, match="reason is required"):
        lifecycle.transition_to(
            terminal_status,
            occurred_at=NOW + timedelta(seconds=1),
        )


def test_closed_transition_requires_reason() -> None:
    lifecycle = (
        create_lifecycle()
        .transition_to(
            TradePlanStatus.ARMED,
            occurred_at=NOW + timedelta(seconds=1),
        )
        .transition_to(
            TradePlanStatus.SUBMITTED,
            occurred_at=NOW + timedelta(seconds=2),
        )
        .transition_to(
            TradePlanStatus.FILLED,
            occurred_at=NOW + timedelta(seconds=3),
        )
    )

    with pytest.raises(ValueError, match="reason is required"):
        lifecycle.transition_to(
            TradePlanStatus.CLOSED,
            occurred_at=NOW + timedelta(seconds=4),
        )


def test_terminal_reason_is_normalized() -> None:
    cancelled = create_lifecycle().transition_to(
        TradePlanStatus.CANCELLED,
        occurred_at=NOW + timedelta(seconds=1),
        reason="  Strategy invalidated  ",
    )

    assert cancelled.events[-1].reason == "Strategy invalidated"


def test_terminal_state_cannot_transition_again() -> None:
    cancelled = create_lifecycle().transition_to(
        TradePlanStatus.CANCELLED,
        occurred_at=NOW + timedelta(seconds=1),
        reason="Manual cancellation",
    )

    assert cancelled.status in TERMINAL_STATUSES

    with pytest.raises(ValueError, match="Invalid lifecycle transition"):
        cancelled.transition_to(
            TradePlanStatus.ARMED,
            occurred_at=NOW + timedelta(seconds=2),
        )


def test_event_sequences_are_contiguous() -> None:
    lifecycle = (
        create_lifecycle()
        .transition_to(
            TradePlanStatus.ARMED,
            occurred_at=NOW + timedelta(seconds=1),
        )
        .transition_to(
            TradePlanStatus.SUBMITTED,
            occurred_at=NOW + timedelta(seconds=2),
        )
        .transition_to(
            TradePlanStatus.FILLED,
            occurred_at=NOW + timedelta(seconds=3),
        )
    )

    assert [event.sequence for event in lifecycle.events] == [
        1,
        2,
        3,
    ]


def test_transition_timestamp_cannot_move_backwards() -> None:
    armed = create_lifecycle().transition_to(
        TradePlanStatus.ARMED,
        occurred_at=NOW + timedelta(seconds=5),
    )

    with pytest.raises(ValueError, match="earlier"):
        armed.transition_to(
            TradePlanStatus.SUBMITTED,
            occurred_at=NOW + timedelta(seconds=4),
        )


def test_equal_transition_timestamp_is_allowed() -> None:
    armed = create_lifecycle().transition_to(
        TradePlanStatus.ARMED,
        occurred_at=NOW,
    )

    assert armed.updated_at == NOW


def test_naive_creation_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TradeLifecycle.create(
            trade_id="trade-001",
            plan=create_plan(),
            created_at=datetime(2026, 7, 25, 12, 0),
        )


def test_naive_transition_timestamp_is_rejected() -> None:
    lifecycle = create_lifecycle()

    with pytest.raises(ValueError, match="timezone-aware"):
        lifecycle.transition_to(
            TradePlanStatus.ARMED,
            occurred_at=datetime(2026, 7, 25, 12, 1),
        )


@pytest.mark.parametrize(
    "trade_id",
    [
        "",
        "   ",
        "\n",
    ],
)
def test_invalid_trade_id_is_rejected(trade_id: str) -> None:
    with pytest.raises(ValueError):
        TradeLifecycle.create(
            trade_id=trade_id,
            plan=create_plan(),
            created_at=NOW,
        )


def test_non_trade_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="TradePlan"):
        TradeLifecycle(
            trade_id="trade-001",
            plan="invalid",
            status=TradePlanStatus.PLANNED,
            created_at=NOW,
            updated_at=NOW,
        )


def test_lifecycle_without_events_must_be_planned() -> None:
    with pytest.raises(ValueError, match="must remain PLANNED"):
        TradeLifecycle(
            trade_id="trade-001",
            plan=create_plan(),
            status=TradePlanStatus.ARMED,
            created_at=NOW,
            updated_at=NOW,
        )


def test_lifecycle_event_sequence_must_start_at_one() -> None:
    event = TradeLifecycleEvent(
        sequence=2,
        from_status=TradePlanStatus.PLANNED,
        to_status=TradePlanStatus.ARMED,
        occurred_at=NOW + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="contiguous"):
        TradeLifecycle(
            trade_id="trade-001",
            plan=create_plan(),
            status=TradePlanStatus.ARMED,
            created_at=NOW,
            updated_at=event.occurred_at,
            events=(event,),
        )


def test_lifecycle_event_chain_gap_is_rejected() -> None:
    first = TradeLifecycleEvent(
        sequence=1,
        from_status=TradePlanStatus.PLANNED,
        to_status=TradePlanStatus.ARMED,
        occurred_at=NOW + timedelta(seconds=1),
    )
    second = TradeLifecycleEvent(
        sequence=2,
        from_status=TradePlanStatus.PLANNED,
        to_status=TradePlanStatus.CANCELLED,
        occurred_at=NOW + timedelta(seconds=2),
        reason="Invalid chain",
    )

    with pytest.raises(ValueError, match="status gap"):
        TradeLifecycle(
            trade_id="trade-001",
            plan=create_plan(),
            status=TradePlanStatus.CANCELLED,
            created_at=NOW,
            updated_at=second.occurred_at,
            events=(first, second),
        )


def test_lifecycle_event_timestamps_must_be_chronological() -> None:
    first = TradeLifecycleEvent(
        sequence=1,
        from_status=TradePlanStatus.PLANNED,
        to_status=TradePlanStatus.ARMED,
        occurred_at=NOW + timedelta(seconds=2),
    )
    second = TradeLifecycleEvent(
        sequence=2,
        from_status=TradePlanStatus.ARMED,
        to_status=TradePlanStatus.SUBMITTED,
        occurred_at=NOW + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="chronological"):
        TradeLifecycle(
            trade_id="trade-001",
            plan=create_plan(),
            status=TradePlanStatus.SUBMITTED,
            created_at=NOW,
            updated_at=second.occurred_at,
            events=(first, second),
        )


def test_final_status_must_match_final_event() -> None:
    event = TradeLifecycleEvent(
        sequence=1,
        from_status=TradePlanStatus.PLANNED,
        to_status=TradePlanStatus.ARMED,
        occurred_at=NOW + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="final event status"):
        TradeLifecycle(
            trade_id="trade-001",
            plan=create_plan(),
            status=TradePlanStatus.SUBMITTED,
            created_at=NOW,
            updated_at=event.occurred_at,
            events=(event,),
        )


def test_updated_at_must_match_final_event_timestamp() -> None:
    event = TradeLifecycleEvent(
        sequence=1,
        from_status=TradePlanStatus.PLANNED,
        to_status=TradePlanStatus.ARMED,
        occurred_at=NOW + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="final event timestamp"):
        TradeLifecycle(
            trade_id="trade-001",
            plan=create_plan(),
            status=TradePlanStatus.ARMED,
            created_at=NOW,
            updated_at=NOW + timedelta(seconds=2),
            events=(event,),
        )


def test_event_reason_cannot_contain_line_breaks() -> None:
    lifecycle = create_lifecycle()

    with pytest.raises(ValueError, match="line breaks"):
        lifecycle.transition_to(
            TradePlanStatus.CANCELLED,
            occurred_at=NOW + timedelta(seconds=1),
            reason="Invalid\nreason",
        )


def test_event_reason_length_is_limited() -> None:
    lifecycle = create_lifecycle()

    with pytest.raises(ValueError, match="256"):
        lifecycle.transition_to(
            TradePlanStatus.CANCELLED,
            occurred_at=NOW + timedelta(seconds=1),
            reason="x" * 257,
        )
