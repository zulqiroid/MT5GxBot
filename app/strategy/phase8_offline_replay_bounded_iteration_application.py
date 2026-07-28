"""Pure in-memory application of a bounded offline replay plan.

This module applies only the immutable counter and event-sequence effects
already authorized by a bounded replay iteration plan. It does not create
a reusable replay session state, evaluate a strategy, initialize MT5,
contact a broker, write external state, or submit an order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_APPLICATION_SCHEMA_VERSION = "1.0"


def _required_attribute(value: object, attribute_name: str) -> object:
    if not hasattr(value, attribute_name):
        raise ValueError(f"{attribute_name} is required.")
    return getattr(value, attribute_name)


def _required_int(value: object, attribute_name: str) -> int:
    attribute_value = _required_attribute(value, attribute_name)
    if isinstance(attribute_value, bool) or not isinstance(attribute_value, int):
        raise ValueError(f"{attribute_name} must be an integer.")
    return attribute_value


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayBoundedIterationApplicationReceipt:
    """Immutable receipt for one bounded in-memory application."""

    plan_decision: object
    plan: object
    source_decision: object
    source_state: object

    source_state_version: int
    start_cursor_index: int
    resulting_cursor_index: int

    initial_consumed_count: int
    resulting_consumed_count: int

    initial_remaining_count: int
    resulting_remaining_count: int

    consumed_event_sequence_indices: tuple[int, ...]
    consumed_event_count: int
    next_event_sequence_index: int | None

    total_event_count: int
    reaches_terminal_state: bool

    creates_reusable_state: bool = False
    executes_strategy: bool = False
    executes_simulation: bool = False
    initializes_mt5: bool = False
    sends_broker_request: bool = False
    writes_external_state: bool = False
    can_submit_order: bool = False

    def __post_init__(self) -> None:
        if self.consumed_event_count < 1:
            raise ValueError("consumed_event_count must be positive.")

        if len(self.consumed_event_sequence_indices) != self.consumed_event_count:
            raise ValueError("consumed event sequence count is inconsistent.")

        expected_indices = tuple(
            range(
                self.start_cursor_index,
                self.resulting_cursor_index,
            )
        )

        if self.consumed_event_sequence_indices != expected_indices:
            raise ValueError("consumed event sequence indices are inconsistent.")

        if self.resulting_cursor_index != self.start_cursor_index + self.consumed_event_count:
            raise ValueError("resulting cursor is inconsistent.")

        if self.resulting_consumed_count != self.initial_consumed_count + self.consumed_event_count:
            raise ValueError("resulting consumed count is inconsistent.")

        if (
            self.resulting_remaining_count
            != self.initial_remaining_count - self.consumed_event_count
        ):
            raise ValueError("resulting remaining count is inconsistent.")

        if self.initial_consumed_count + self.initial_remaining_count != self.total_event_count:
            raise ValueError("initial counters do not preserve total.")

        if self.resulting_consumed_count + self.resulting_remaining_count != self.total_event_count:
            raise ValueError("resulting counters do not preserve total.")

        if self.resulting_cursor_index != self.resulting_consumed_count:
            raise ValueError("resulting cursor and consumed count differ.")

        if self.reaches_terminal_state:
            if self.resulting_remaining_count != 0:
                raise ValueError("terminal receipt must have zero remaining.")
            if self.next_event_sequence_index is not None:
                raise ValueError("terminal receipt cannot expose a next event.")
        else:
            if self.resulting_remaining_count < 1:
                raise ValueError("active receipt must retain events.")
            if self.next_event_sequence_index != self.resulting_cursor_index:
                raise ValueError("next event sequence is inconsistent.")

    @property
    def application_digest(self) -> str:
        material = "|".join(
            (
                PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_APPLICATION_SCHEMA_VERSION,
                str(self.source_state_version),
                str(self.start_cursor_index),
                str(self.resulting_cursor_index),
                str(self.initial_consumed_count),
                str(self.resulting_consumed_count),
                str(self.initial_remaining_count),
                str(self.resulting_remaining_count),
                ",".join(str(index) for index in self.consumed_event_sequence_indices),
                str(self.consumed_event_count),
                str(self.next_event_sequence_index),
                str(self.total_event_count),
                str(self.reaches_terminal_state),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def application_id(self) -> str:
        return (
            "PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_APPLICATION:"
            f"SHA256[{self.application_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayBoundedIterationApplicationDecision:
    """Allowed or blocked bounded replay application result."""

    is_allowed: bool
    receipt: Phase8OfflineReplayBoundedIterationApplicationReceipt | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.receipt is None:
                raise ValueError("Allowed decision requires a receipt.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.receipt is not None:
                raise ValueError("Blocked decision cannot have a receipt.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def receipt_required(
        self,
    ) -> Phase8OfflineReplayBoundedIterationApplicationReceipt:
        if self.receipt is None:
            raise RuntimeError("Bounded replay iteration application is blocked.")
        return self.receipt


class StrategyPhase8OfflineReplayBoundedIterationApplication:
    """Applies an allowed bounded plan without external side effects."""

    def apply(
        self,
        plan_decision: object,
    ) -> Phase8OfflineReplayBoundedIterationApplicationDecision:
        if plan_decision is None:
            return Phase8OfflineReplayBoundedIterationApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("plan_decision_missing",),
            )

        if getattr(plan_decision, "is_allowed", True) is not True:
            return Phase8OfflineReplayBoundedIterationApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("plan_decision_blocked",),
            )

        try:
            plan = _required_attribute(plan_decision, "plan_required")
            source_decision = _required_attribute(plan, "source_decision")
            source_state = _required_attribute(plan, "source_state")

            source_state_version = _required_int(plan, "source_state_version")
            start_cursor_index = _required_int(plan, "start_cursor_index")
            resulting_cursor_index = _required_int(plan, "stop_cursor_index")
            initial_consumed_count = _required_int(
                plan,
                "initial_consumed_count",
            )
            resulting_consumed_count = _required_int(
                plan,
                "planned_consumed_count",
            )
            initial_remaining_count = _required_int(
                plan,
                "initial_remaining_count",
            )
            resulting_remaining_count = _required_int(
                plan,
                "planned_remaining_count",
            )
            first_event_sequence_index = _required_int(
                plan,
                "first_event_sequence_index",
            )
            last_event_sequence_index = _required_int(
                plan,
                "last_event_sequence_index",
            )
            consumed_event_count = _required_int(
                plan,
                "planned_transition_count",
            )
            total_event_count = _required_int(plan, "total_event_count")
            reaches_terminal_state = _required_attribute(
                plan,
                "reaches_terminal_state",
            )
            next_event_sequence_index = _required_attribute(
                plan,
                "next_event_sequence_index",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase8OfflineReplayBoundedIterationApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=(f"plan_invalid:{type(error).__name__}",),
            )

        if not isinstance(reaches_terminal_state, bool):
            return Phase8OfflineReplayBoundedIterationApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("plan_terminal_flag_invalid",),
            )

        if next_event_sequence_index is not None and (
            isinstance(next_event_sequence_index, bool)
            or not isinstance(next_event_sequence_index, int)
        ):
            return Phase8OfflineReplayBoundedIterationApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("plan_next_event_sequence_invalid",),
            )

        if first_event_sequence_index != start_cursor_index:
            return Phase8OfflineReplayBoundedIterationApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("plan_first_event_sequence_mismatch",),
            )

        if last_event_sequence_index != resulting_cursor_index - 1:
            return Phase8OfflineReplayBoundedIterationApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("plan_last_event_sequence_mismatch",),
            )

        consumed_event_sequence_indices = tuple(
            range(
                first_event_sequence_index,
                last_event_sequence_index + 1,
            )
        )

        try:
            receipt = Phase8OfflineReplayBoundedIterationApplicationReceipt(
                plan_decision=plan_decision,
                plan=plan,
                source_decision=source_decision,
                source_state=source_state,
                source_state_version=source_state_version,
                start_cursor_index=start_cursor_index,
                resulting_cursor_index=resulting_cursor_index,
                initial_consumed_count=initial_consumed_count,
                resulting_consumed_count=resulting_consumed_count,
                initial_remaining_count=initial_remaining_count,
                resulting_remaining_count=resulting_remaining_count,
                consumed_event_sequence_indices=consumed_event_sequence_indices,
                consumed_event_count=consumed_event_count,
                next_event_sequence_index=next_event_sequence_index,
                total_event_count=total_event_count,
                reaches_terminal_state=reaches_terminal_state,
            )
        except ValueError as error:
            return Phase8OfflineReplayBoundedIterationApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=(f"application_invalid:{type(error).__name__}",),
            )

        return Phase8OfflineReplayBoundedIterationApplicationDecision(
            is_allowed=True,
            receipt=receipt,
            blockers=(),
        )


def apply_phase8_offline_replay_bounded_iteration_plan(
    plan_decision: object,
) -> Phase8OfflineReplayBoundedIterationApplicationDecision:
    """Apply one allowed bounded replay plan in memory."""

    return StrategyPhase8OfflineReplayBoundedIterationApplication().apply(plan_decision)


__all__ = (
    "PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_APPLICATION_SCHEMA_VERSION",
    "Phase8OfflineReplayBoundedIterationApplicationDecision",
    "Phase8OfflineReplayBoundedIterationApplicationReceipt",
    "StrategyPhase8OfflineReplayBoundedIterationApplication",
    "apply_phase8_offline_replay_bounded_iteration_plan",
)
