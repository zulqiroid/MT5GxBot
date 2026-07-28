"""Pure in-memory iterative recurrent bounded replay application.

This module applies one allowed iterative recurrent bounded replay plan
and creates only an immutable application receipt. It does not create a
reusable replay state, evaluate strategy logic, initialize MT5, contact
a broker, write external state, or submit orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_8_OFFLINE_REPLAY_ITERATIVE_RECURRENT_BOUNDED_APPLICATION_SCHEMA_VERSION = "1.0"


def _required_attribute(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


def _required_int(value: object, name: str) -> int:
    attribute = _required_attribute(value, name)
    if isinstance(attribute, bool) or not isinstance(attribute, int):
        raise ValueError(f"{name} must be an integer.")
    return attribute


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayIterativeRecurrentBoundedApplicationReceipt:
    """Immutable receipt for one iterative recurrent bounded application."""

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
        if self.source_state_version < 1:
            raise ValueError("source_state_version must be positive.")

        if self.consumed_event_count < 1:
            raise ValueError("consumed_event_count must be positive.")

        if len(self.consumed_event_sequence_indices) != self.consumed_event_count:
            raise ValueError("consumed sequence count is inconsistent.")

        expected_indices = tuple(
            range(
                self.start_cursor_index,
                self.resulting_cursor_index,
            )
        )
        if self.consumed_event_sequence_indices != expected_indices:
            raise ValueError("consumed sequence indices are inconsistent.")

        if self.resulting_cursor_index != self.start_cursor_index + self.consumed_event_count:
            raise ValueError("resulting cursor is inconsistent.")

        if self.resulting_consumed_count != self.initial_consumed_count + self.consumed_event_count:
            raise ValueError("resulting consumed count is inconsistent.")

        if (
            self.resulting_remaining_count
            != self.initial_remaining_count - self.consumed_event_count
        ):
            raise ValueError("resulting remaining count is inconsistent.")

        if self.resulting_consumed_count + self.resulting_remaining_count != self.total_event_count:
            raise ValueError("application counters do not preserve total.")

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
        plan_id = str(getattr(self.plan, "plan_id", ""))
        sequence_material = ",".join(str(index) for index in self.consumed_event_sequence_indices)
        material = "|".join(
            (
                PHASE_8_OFFLINE_REPLAY_ITERATIVE_RECURRENT_BOUNDED_APPLICATION_SCHEMA_VERSION,
                plan_id,
                str(self.source_state_version),
                str(self.start_cursor_index),
                str(self.resulting_cursor_index),
                str(self.initial_consumed_count),
                str(self.resulting_consumed_count),
                str(self.initial_remaining_count),
                str(self.resulting_remaining_count),
                sequence_material,
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
            "PHASE_8_OFFLINE_REPLAY_ITERATIVE_RECURRENT_BOUNDED_APPLICATION:"
            f"SHA256[{self.application_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision:
    """Allowed or blocked iterative recurrent bounded application."""

    is_allowed: bool
    receipt: Phase8OfflineReplayIterativeRecurrentBoundedApplicationReceipt | None
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
    ) -> Phase8OfflineReplayIterativeRecurrentBoundedApplicationReceipt:
        if self.receipt is None:
            raise RuntimeError("Iterative recurrent bounded replay application is blocked.")
        return self.receipt


class StrategyPhase8OfflineReplayIterativeRecurrentBoundedApplication:
    """Applies one iterative recurrent bounded replay plan in memory."""

    def apply(
        self,
        plan_decision: object,
    ) -> Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision:
        if plan_decision is None:
            return Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("plan_decision_missing",),
            )

        if getattr(plan_decision, "is_allowed", True) is not True:
            return Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("plan_decision_blocked",),
            )

        try:
            plan = _required_attribute(plan_decision, "plan_required")
            source_decision = _required_attribute(
                plan,
                "source_decision",
            )
            source_state = _required_attribute(plan, "source_state")

            source_state_version = _required_int(
                plan,
                "source_state_version",
            )
            start_cursor_index = _required_int(
                plan,
                "start_cursor_index",
            )
            resulting_cursor_index = _required_int(
                plan,
                "resulting_cursor_index",
            )
            initial_consumed_count = _required_int(
                plan,
                "initial_consumed_count",
            )
            resulting_consumed_count = _required_int(
                plan,
                "resulting_consumed_count",
            )
            initial_remaining_count = _required_int(
                plan,
                "initial_remaining_count",
            )
            resulting_remaining_count = _required_int(
                plan,
                "resulting_remaining_count",
            )
            planned_indices = _required_attribute(
                plan,
                "planned_event_sequence_indices",
            )
            planned_transition_count = _required_int(
                plan,
                "planned_transition_count",
            )
            next_event_sequence_index = _required_attribute(
                plan,
                "next_event_sequence_index",
            )
            total_event_count = _required_int(
                plan,
                "total_event_count",
            )
            reaches_terminal_state = _required_attribute(
                plan,
                "reaches_terminal_state",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=(f"iterative_recurrent_plan_invalid:{type(error).__name__}",),
            )

        if (
            not isinstance(planned_indices, tuple)
            or not planned_indices
            or any(
                isinstance(index, bool) or not isinstance(index, int) for index in planned_indices
            )
        ):
            return Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("planned_event_sequence_indices_invalid",),
            )

        if not isinstance(reaches_terminal_state, bool):
            return Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("terminal_flag_invalid",),
            )

        if next_event_sequence_index is not None and (
            isinstance(next_event_sequence_index, bool)
            or not isinstance(next_event_sequence_index, int)
        ):
            return Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=("next_event_sequence_invalid",),
            )

        try:
            receipt = Phase8OfflineReplayIterativeRecurrentBoundedApplicationReceipt(
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
                consumed_event_sequence_indices=planned_indices,
                consumed_event_count=planned_transition_count,
                next_event_sequence_index=next_event_sequence_index,
                total_event_count=total_event_count,
                reaches_terminal_state=reaches_terminal_state,
            )
        except ValueError as error:
            return Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision(
                is_allowed=False,
                receipt=None,
                blockers=(f"iterative_recurrent_application_invalid:{type(error).__name__}",),
            )

        return Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision(
            is_allowed=True,
            receipt=receipt,
            blockers=(),
        )


def apply_phase8_offline_replay_iterative_recurrent_bounded_plan(
    plan_decision: object,
) -> Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision:
    """Apply one immutable iterative recurrent bounded replay plan."""

    return StrategyPhase8OfflineReplayIterativeRecurrentBoundedApplication().apply(plan_decision)


__all__ = (
    "PHASE_8_OFFLINE_REPLAY_ITERATIVE_RECURRENT_BOUNDED_APPLICATION_SCHEMA_VERSION",
    "Phase8OfflineReplayIterativeRecurrentBoundedApplicationReceipt",
    "Phase8OfflineReplayIterativeRecurrentBoundedApplicationDecision",
    "StrategyPhase8OfflineReplayIterativeRecurrentBoundedApplication",
    "apply_phase8_offline_replay_iterative_recurrent_bounded_plan",
)
