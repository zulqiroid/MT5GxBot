from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Final, Mapping

from app.domain.trading import TradePlan, TradePlanStatus

_ALLOWED_TRANSITIONS_SOURCE: Final[dict[TradePlanStatus, frozenset[TradePlanStatus]]] = {
    TradePlanStatus.PLANNED: frozenset(
        {
            TradePlanStatus.ARMED,
            TradePlanStatus.CANCELLED,
            TradePlanStatus.REJECTED,
        }
    ),
    TradePlanStatus.ARMED: frozenset(
        {
            TradePlanStatus.SUBMITTED,
            TradePlanStatus.CANCELLED,
            TradePlanStatus.REJECTED,
        }
    ),
    TradePlanStatus.SUBMITTED: frozenset(
        {
            TradePlanStatus.FILLED,
            TradePlanStatus.CANCELLED,
            TradePlanStatus.REJECTED,
        }
    ),
    TradePlanStatus.FILLED: frozenset(
        {
            TradePlanStatus.CLOSED,
        }
    ),
    TradePlanStatus.CANCELLED: frozenset(),
    TradePlanStatus.REJECTED: frozenset(),
    TradePlanStatus.CLOSED: frozenset(),
}

ALLOWED_TRANSITIONS: Final[Mapping[TradePlanStatus, frozenset[TradePlanStatus]]] = MappingProxyType(
    _ALLOWED_TRANSITIONS_SOURCE
)

TERMINAL_STATUSES: Final[frozenset[TradePlanStatus]] = frozenset(
    {
        TradePlanStatus.CANCELLED,
        TradePlanStatus.REJECTED,
        TradePlanStatus.CLOSED,
    }
)


def _required_text(
    value: str,
    field_name: str,
    maximum_length: int = 64,
) -> str:
    normalized = str(value).strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be blank.")

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    if len(normalized) > maximum_length:
        raise ValueError(f"{field_name} cannot exceed {maximum_length} characters.")

    return normalized


def _normalize_reason(
    value: str | None,
    *,
    required: bool,
) -> str | None:
    if value is None:
        if required:
            raise ValueError("A reason is required for terminal lifecycle transitions.")

        return None

    normalized = str(value).strip()

    if not normalized:
        if required:
            raise ValueError("A reason is required for terminal lifecycle transitions.")

        return None

    if "\n" in normalized or "\r" in normalized:
        raise ValueError("reason cannot contain line breaks.")

    if len(normalized) > 256:
        raise ValueError("reason cannot exceed 256 characters.")

    return normalized


def _utc_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _positive_integer(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


def _normalize_status(
    value: TradePlanStatus,
    field_name: str,
) -> TradePlanStatus:
    try:
        return TradePlanStatus(value)
    except ValueError as error:
        raise ValueError(f"{field_name} contains an unsupported lifecycle status.") from error


def can_transition(
    current_status: TradePlanStatus,
    target_status: TradePlanStatus,
) -> bool:
    current = _normalize_status(current_status, "current_status")
    target = _normalize_status(target_status, "target_status")

    return target in ALLOWED_TRANSITIONS[current]


@dataclass(frozen=True, slots=True)
class TradeLifecycleEvent:
    """One immutable and auditable lifecycle transition."""

    sequence: int
    from_status: TradePlanStatus
    to_status: TradePlanStatus
    occurred_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        sequence = _positive_integer(self.sequence, "sequence")
        from_status = _normalize_status(
            self.from_status,
            "from_status",
        )
        to_status = _normalize_status(
            self.to_status,
            "to_status",
        )
        occurred_at = _utc_datetime(
            self.occurred_at,
            "occurred_at",
        )

        if from_status == to_status:
            raise ValueError("A lifecycle event cannot transition to the same status.")

        if not can_transition(from_status, to_status):
            raise ValueError(
                f"Invalid lifecycle transition: {from_status.value} -> {to_status.value}."
            )

        reason = _normalize_reason(
            self.reason,
            required=to_status in TERMINAL_STATUSES,
        )

        object.__setattr__(self, "sequence", sequence)
        object.__setattr__(self, "from_status", from_status)
        object.__setattr__(self, "to_status", to_status)
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True, slots=True)
class TradeLifecycle:
    """Immutable state machine and audit history for one trade plan."""

    trade_id: str
    plan: TradePlan
    status: TradePlanStatus
    created_at: datetime
    updated_at: datetime
    events: tuple[TradeLifecycleEvent, ...] = ()

    def __post_init__(self) -> None:
        trade_id = _required_text(
            self.trade_id,
            "trade_id",
        )

        if not isinstance(self.plan, TradePlan):
            raise ValueError("plan must be a TradePlan instance.")

        status = _normalize_status(
            self.status,
            "status",
        )
        created_at = _utc_datetime(
            self.created_at,
            "created_at",
        )
        updated_at = _utc_datetime(
            self.updated_at,
            "updated_at",
        )
        events = tuple(self.events)

        if updated_at < created_at:
            raise ValueError("updated_at cannot be earlier than created_at.")

        if not events:
            if status != TradePlanStatus.PLANNED:
                raise ValueError("A lifecycle without events must remain PLANNED.")

            if updated_at != created_at:
                raise ValueError(
                    "A lifecycle without events must have matching "
                    "created_at and updated_at values."
                )
        else:
            previous_status = TradePlanStatus.PLANNED
            previous_timestamp = created_at

            for expected_sequence, event in enumerate(
                events,
                start=1,
            ):
                if not isinstance(event, TradeLifecycleEvent):
                    raise ValueError("events must contain TradeLifecycleEvent instances.")

                if event.sequence != expected_sequence:
                    raise ValueError("Lifecycle event sequence must be contiguous and begin at 1.")

                if event.from_status != previous_status:
                    raise ValueError("Lifecycle event chain contains a status gap.")

                if event.occurred_at < previous_timestamp:
                    raise ValueError("Lifecycle event timestamps must be chronological.")

                previous_status = event.to_status
                previous_timestamp = event.occurred_at

            if previous_status != status:
                raise ValueError("Lifecycle status must match the final event status.")

            if updated_at != events[-1].occurred_at:
                raise ValueError("updated_at must match the final event timestamp.")

        object.__setattr__(self, "trade_id", trade_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)
        object.__setattr__(self, "events", events)

    @classmethod
    def create(
        cls,
        *,
        trade_id: str,
        plan: TradePlan,
        created_at: datetime,
    ) -> TradeLifecycle:
        normalized_created_at = _utc_datetime(
            created_at,
            "created_at",
        )

        return cls(
            trade_id=trade_id,
            plan=plan,
            status=TradePlanStatus.PLANNED,
            created_at=normalized_created_at,
            updated_at=normalized_created_at,
            events=(),
        )

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def next_sequence(self) -> int:
        return self.event_count + 1

    @property
    def available_transitions(
        self,
    ) -> frozenset[TradePlanStatus]:
        return ALLOWED_TRANSITIONS[self.status]

    def can_transition_to(
        self,
        target_status: TradePlanStatus,
    ) -> bool:
        return can_transition(
            self.status,
            target_status,
        )

    def transition_to(
        self,
        target_status: TradePlanStatus,
        *,
        occurred_at: datetime,
        reason: str | None = None,
    ) -> TradeLifecycle:
        target = _normalize_status(
            target_status,
            "target_status",
        )
        normalized_occurred_at = _utc_datetime(
            occurred_at,
            "occurred_at",
        )

        if normalized_occurred_at < self.updated_at:
            raise ValueError("occurred_at cannot be earlier than the current lifecycle timestamp.")

        event = TradeLifecycleEvent(
            sequence=self.next_sequence,
            from_status=self.status,
            to_status=target,
            occurred_at=normalized_occurred_at,
            reason=reason,
        )

        return TradeLifecycle(
            trade_id=self.trade_id,
            plan=self.plan,
            status=event.to_status,
            created_at=self.created_at,
            updated_at=event.occurred_at,
            events=(*self.events, event),
        )
