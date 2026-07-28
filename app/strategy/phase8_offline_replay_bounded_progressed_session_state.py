"""Immutable bounded progressed offline replay session state.

This module converts an allowed bounded replay application receipt into
one reusable immutable replay state. It performs no additional replay
transition, event consumption, strategy evaluation, simulation, MT5
operation, broker request, external write, or order submission.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_8_OFFLINE_REPLAY_BOUNDED_PROGRESSED_SESSION_STATE_SCHEMA_VERSION = "1.0"

PHASE_8_OFFLINE_REPLAY_BOUNDED_SESSION_ACTIVE = "ACTIVE"
PHASE_8_OFFLINE_REPLAY_BOUNDED_SESSION_COMPLETED = "COMPLETED"


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
class Phase8OfflineReplayBoundedProgressedSessionState:
    """Reusable immutable replay state after bounded application."""

    application_decision: object
    application_receipt: object
    plan_decision: object
    plan: object
    source_decision: object
    prior_state: object

    state_version: int
    cursor_index: int
    consumed_count: int
    remaining_count: int
    last_consumed_sequence_index: int
    next_event_sequence_index: int | None
    total_event_count: int
    lifecycle: str

    executes_transition: bool = False
    consumes_additional_events: bool = False
    executes_strategy: bool = False
    executes_simulation: bool = False
    initializes_mt5: bool = False
    sends_broker_request: bool = False
    writes_external_state: bool = False
    can_submit_order: bool = False

    def __post_init__(self) -> None:
        if self.state_version < 1:
            raise ValueError("state_version must be positive.")

        if self.cursor_index != self.consumed_count:
            raise ValueError("cursor_index and consumed_count must match.")

        if self.consumed_count + self.remaining_count != self.total_event_count:
            raise ValueError("State counters must preserve total_event_count.")

        if self.consumed_count < 1:
            raise ValueError("Bounded progressed state must contain consumed events.")

        if self.last_consumed_sequence_index != self.cursor_index - 1:
            raise ValueError("last_consumed_sequence_index is inconsistent.")

        if self.lifecycle == PHASE_8_OFFLINE_REPLAY_BOUNDED_SESSION_COMPLETED:
            if self.remaining_count != 0:
                raise ValueError("Completed state must have zero remaining events.")

            if self.next_event_sequence_index is not None:
                raise ValueError("Completed state cannot expose a next event.")

        elif self.lifecycle == PHASE_8_OFFLINE_REPLAY_BOUNDED_SESSION_ACTIVE:
            if self.remaining_count < 1:
                raise ValueError("Active state must retain replay events.")

            if self.next_event_sequence_index != self.cursor_index:
                raise ValueError("Active next event sequence is inconsistent.")

        else:
            raise ValueError("lifecycle is invalid.")

    @property
    def state_digest(self) -> str:
        material = "|".join(
            (
                PHASE_8_OFFLINE_REPLAY_BOUNDED_PROGRESSED_SESSION_STATE_SCHEMA_VERSION,
                str(self.state_version),
                str(self.cursor_index),
                str(self.consumed_count),
                str(self.remaining_count),
                str(self.last_consumed_sequence_index),
                str(self.next_event_sequence_index),
                str(self.total_event_count),
                self.lifecycle,
            )
        )

        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def state_id(self) -> str:
        return (
            f"PHASE_8_OFFLINE_REPLAY_BOUNDED_PROGRESSED_SESSION_STATE:SHA256[{self.state_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayBoundedProgressedSessionStateDecision:
    """Allowed or blocked bounded progressed-state decision."""

    is_allowed: bool
    state: Phase8OfflineReplayBoundedProgressedSessionState | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.state is None:
                raise ValueError("Allowed decision requires a state.")

            if self.blockers:
                raise ValueError("Allowed decision cannot contain blockers.")

        else:
            if self.state is not None:
                raise ValueError("Blocked decision cannot contain a state.")

            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def state_required(
        self,
    ) -> Phase8OfflineReplayBoundedProgressedSessionState:
        if self.state is None:
            raise RuntimeError("Bounded progressed replay state is blocked.")

        return self.state


class StrategyPhase8OfflineReplayBoundedProgressedSessionStateFactory:
    """Creates reusable state from an allowed application receipt."""

    def create(
        self,
        application_decision: object,
    ) -> Phase8OfflineReplayBoundedProgressedSessionStateDecision:
        if application_decision is None:
            return Phase8OfflineReplayBoundedProgressedSessionStateDecision(
                is_allowed=False,
                state=None,
                blockers=("application_decision_missing",),
            )

        if (
            getattr(
                application_decision,
                "is_allowed",
                True,
            )
            is not True
        ):
            return Phase8OfflineReplayBoundedProgressedSessionStateDecision(
                is_allowed=False,
                state=None,
                blockers=("application_decision_blocked",),
            )

        try:
            receipt = _required_attribute(
                application_decision,
                "receipt_required",
            )

            plan_decision = _required_attribute(
                receipt,
                "plan_decision",
            )
            plan = _required_attribute(
                receipt,
                "plan",
            )
            source_decision = _required_attribute(
                receipt,
                "source_decision",
            )
            prior_state = _required_attribute(
                receipt,
                "source_state",
            )

            source_state_version = _required_int(
                receipt,
                "source_state_version",
            )
            cursor_index = _required_int(
                receipt,
                "resulting_cursor_index",
            )
            consumed_count = _required_int(
                receipt,
                "resulting_consumed_count",
            )
            remaining_count = _required_int(
                receipt,
                "resulting_remaining_count",
            )
            total_event_count = _required_int(
                receipt,
                "total_event_count",
            )

            consumed_indices = _required_attribute(
                receipt,
                "consumed_event_sequence_indices",
            )
            next_event_sequence_index = _required_attribute(
                receipt,
                "next_event_sequence_index",
            )
            reaches_terminal_state = _required_attribute(
                receipt,
                "reaches_terminal_state",
            )

        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase8OfflineReplayBoundedProgressedSessionStateDecision(
                is_allowed=False,
                state=None,
                blockers=(f"application_receipt_invalid:{type(error).__name__}",),
            )

        if (
            not isinstance(consumed_indices, tuple)
            or not consumed_indices
            or any(
                isinstance(index, bool) or not isinstance(index, int) for index in consumed_indices
            )
        ):
            return Phase8OfflineReplayBoundedProgressedSessionStateDecision(
                is_allowed=False,
                state=None,
                blockers=("consumed_event_sequence_indices_invalid",),
            )

        if not isinstance(reaches_terminal_state, bool):
            return Phase8OfflineReplayBoundedProgressedSessionStateDecision(
                is_allowed=False,
                state=None,
                blockers=("terminal_flag_invalid",),
            )

        if next_event_sequence_index is not None and (
            isinstance(next_event_sequence_index, bool)
            or not isinstance(next_event_sequence_index, int)
        ):
            return Phase8OfflineReplayBoundedProgressedSessionStateDecision(
                is_allowed=False,
                state=None,
                blockers=("next_event_sequence_invalid",),
            )

        lifecycle = (
            PHASE_8_OFFLINE_REPLAY_BOUNDED_SESSION_COMPLETED
            if reaches_terminal_state
            else PHASE_8_OFFLINE_REPLAY_BOUNDED_SESSION_ACTIVE
        )

        try:
            state = Phase8OfflineReplayBoundedProgressedSessionState(
                application_decision=application_decision,
                application_receipt=receipt,
                plan_decision=plan_decision,
                plan=plan,
                source_decision=source_decision,
                prior_state=prior_state,
                state_version=source_state_version + 1,
                cursor_index=cursor_index,
                consumed_count=consumed_count,
                remaining_count=remaining_count,
                last_consumed_sequence_index=consumed_indices[-1],
                next_event_sequence_index=next_event_sequence_index,
                total_event_count=total_event_count,
                lifecycle=lifecycle,
            )

        except ValueError as error:
            return Phase8OfflineReplayBoundedProgressedSessionStateDecision(
                is_allowed=False,
                state=None,
                blockers=(f"progressed_state_invalid:{type(error).__name__}",),
            )

        return Phase8OfflineReplayBoundedProgressedSessionStateDecision(
            is_allowed=True,
            state=state,
            blockers=(),
        )


def create_phase8_offline_replay_bounded_progressed_session_state(
    application_decision: object,
) -> Phase8OfflineReplayBoundedProgressedSessionStateDecision:
    """Create one immutable bounded progressed replay state."""

    return StrategyPhase8OfflineReplayBoundedProgressedSessionStateFactory().create(
        application_decision
    )


__all__ = (
    "PHASE_8_OFFLINE_REPLAY_BOUNDED_PROGRESSED_SESSION_STATE_SCHEMA_VERSION",
    "PHASE_8_OFFLINE_REPLAY_BOUNDED_SESSION_ACTIVE",
    "PHASE_8_OFFLINE_REPLAY_BOUNDED_SESSION_COMPLETED",
    "Phase8OfflineReplayBoundedProgressedSessionState",
    "Phase8OfflineReplayBoundedProgressedSessionStateDecision",
    "StrategyPhase8OfflineReplayBoundedProgressedSessionStateFactory",
    "create_phase8_offline_replay_bounded_progressed_session_state",
)
