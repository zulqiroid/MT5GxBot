"""Immutable recurrent bounded offline replay plan.

This module plans one subsequent bounded replay window from the reusable
state produced by the bounded continuation cycle. It performs planning
only and does not apply transitions, consume events, execute strategy
logic, initialize MT5, contact a broker, write external state, or submit
orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_PLAN_SCHEMA_VERSION = "1.0"
PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_DEFAULT_LIMIT = 32


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
class Phase8OfflineReplayRecurrentBoundedPlan:
    """Immutable plan for one recurrent bounded replay window."""

    source_decision: object
    source_state: object

    source_state_version: int
    start_cursor_index: int
    resulting_cursor_index: int

    initial_consumed_count: int
    resulting_consumed_count: int

    initial_remaining_count: int
    resulting_remaining_count: int

    planned_event_sequence_indices: tuple[int, ...]
    planned_transition_count: int
    next_event_sequence_index: int | None
    total_event_count: int
    reaches_terminal_state: bool
    transition_limit: int

    applies_transition: bool = False
    consumes_events: bool = False
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

        if self.transition_limit < 1:
            raise ValueError("transition_limit must be positive.")

        if self.planned_transition_count < 1:
            raise ValueError("planned_transition_count must be positive.")

        if self.planned_transition_count > self.transition_limit:
            raise ValueError("planned transition count exceeds limit.")

        if len(self.planned_event_sequence_indices) != self.planned_transition_count:
            raise ValueError("planned sequence count is inconsistent.")

        expected_indices = tuple(
            range(
                self.start_cursor_index,
                self.resulting_cursor_index,
            )
        )
        if self.planned_event_sequence_indices != expected_indices:
            raise ValueError("planned sequence indices are inconsistent.")

        if self.resulting_cursor_index != self.start_cursor_index + self.planned_transition_count:
            raise ValueError("resulting cursor is inconsistent.")

        if (
            self.resulting_consumed_count
            != self.initial_consumed_count + self.planned_transition_count
        ):
            raise ValueError("resulting consumed count is inconsistent.")

        if (
            self.resulting_remaining_count
            != self.initial_remaining_count - self.planned_transition_count
        ):
            raise ValueError("resulting remaining count is inconsistent.")

        if self.resulting_consumed_count + self.resulting_remaining_count != self.total_event_count:
            raise ValueError("plan counters do not preserve total.")

        if self.reaches_terminal_state:
            if self.resulting_remaining_count != 0:
                raise ValueError("terminal plan must have zero remaining.")
            if self.next_event_sequence_index is not None:
                raise ValueError("terminal plan cannot expose a next event.")
        else:
            if self.resulting_remaining_count < 1:
                raise ValueError("active plan must retain events.")
            if self.next_event_sequence_index != self.resulting_cursor_index:
                raise ValueError("next event sequence is inconsistent.")

    @property
    def plan_digest(self) -> str:
        source_state_id = str(getattr(self.source_state, "state_id", ""))
        sequence_material = ",".join(str(index) for index in self.planned_event_sequence_indices)
        material = "|".join(
            (
                PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_PLAN_SCHEMA_VERSION,
                source_state_id,
                str(self.source_state_version),
                str(self.start_cursor_index),
                str(self.resulting_cursor_index),
                str(self.initial_consumed_count),
                str(self.resulting_consumed_count),
                str(self.initial_remaining_count),
                str(self.resulting_remaining_count),
                sequence_material,
                str(self.planned_transition_count),
                str(self.next_event_sequence_index),
                str(self.total_event_count),
                str(self.reaches_terminal_state),
                str(self.transition_limit),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def plan_id(self) -> str:
        return f"PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_PLAN:SHA256[{self.plan_digest}]"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayRecurrentBoundedPlanDecision:
    """Allowed or blocked recurrent bounded planning result."""

    is_allowed: bool
    plan: Phase8OfflineReplayRecurrentBoundedPlan | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.plan is None:
                raise ValueError("Allowed decision requires a plan.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.plan is not None:
                raise ValueError("Blocked decision cannot have a plan.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def plan_required(self) -> Phase8OfflineReplayRecurrentBoundedPlan:
        if self.plan is None:
            raise RuntimeError("Recurrent bounded replay plan is blocked.")
        return self.plan


class StrategyPhase8OfflineReplayRecurrentBoundedPlanner:
    """Plans one recurrent bounded replay window in memory."""

    def generate(
        self,
        source_decision: object,
        *,
        transition_limit: int = (PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_DEFAULT_LIMIT),
    ) -> Phase8OfflineReplayRecurrentBoundedPlanDecision:
        if source_decision is None:
            return Phase8OfflineReplayRecurrentBoundedPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("source_decision_missing",),
            )

        if getattr(source_decision, "is_allowed", True) is not True:
            return Phase8OfflineReplayRecurrentBoundedPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("source_decision_blocked",),
            )

        if isinstance(transition_limit, bool) or not isinstance(
            transition_limit,
            int,
        ):
            return Phase8OfflineReplayRecurrentBoundedPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("transition_limit_invalid",),
            )

        if transition_limit < 1:
            return Phase8OfflineReplayRecurrentBoundedPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("transition_limit_invalid",),
            )

        try:
            state = _required_attribute(
                source_decision,
                "state_required",
            )
            state_version = _required_int(state, "state_version")
            cursor_index = _required_int(state, "cursor_index")
            consumed_count = _required_int(state, "consumed_count")
            remaining_count = _required_int(state, "remaining_count")
            total_event_count = _required_int(
                state,
                "total_event_count",
            )
            next_event_sequence_index = _required_attribute(
                state,
                "next_event_sequence_index",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase8OfflineReplayRecurrentBoundedPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=(f"source_state_invalid:{type(error).__name__}",),
            )

        if remaining_count < 1:
            return Phase8OfflineReplayRecurrentBoundedPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("source_state_terminal",),
            )

        if next_event_sequence_index != cursor_index:
            return Phase8OfflineReplayRecurrentBoundedPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("source_state_next_event_inconsistent",),
            )

        planned_count = min(transition_limit, remaining_count)
        resulting_cursor = cursor_index + planned_count
        resulting_consumed = consumed_count + planned_count
        resulting_remaining = remaining_count - planned_count
        reaches_terminal = resulting_remaining == 0
        next_sequence = None if reaches_terminal else resulting_cursor

        try:
            plan = Phase8OfflineReplayRecurrentBoundedPlan(
                source_decision=source_decision,
                source_state=state,
                source_state_version=state_version,
                start_cursor_index=cursor_index,
                resulting_cursor_index=resulting_cursor,
                initial_consumed_count=consumed_count,
                resulting_consumed_count=resulting_consumed,
                initial_remaining_count=remaining_count,
                resulting_remaining_count=resulting_remaining,
                planned_event_sequence_indices=tuple(range(cursor_index, resulting_cursor)),
                planned_transition_count=planned_count,
                next_event_sequence_index=next_sequence,
                total_event_count=total_event_count,
                reaches_terminal_state=reaches_terminal,
                transition_limit=transition_limit,
            )
        except ValueError as error:
            return Phase8OfflineReplayRecurrentBoundedPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=(f"recurrent_plan_invalid:{type(error).__name__}",),
            )

        return Phase8OfflineReplayRecurrentBoundedPlanDecision(
            is_allowed=True,
            plan=plan,
            blockers=(),
        )


def generate_phase8_offline_replay_recurrent_bounded_plan(
    source_decision: object,
    *,
    transition_limit: int = (PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_DEFAULT_LIMIT),
) -> Phase8OfflineReplayRecurrentBoundedPlanDecision:
    """Generate one immutable recurrent bounded replay plan."""

    return StrategyPhase8OfflineReplayRecurrentBoundedPlanner().generate(
        source_decision,
        transition_limit=transition_limit,
    )


__all__ = (
    "PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_PLAN_SCHEMA_VERSION",
    "PHASE_8_OFFLINE_REPLAY_RECURRENT_BOUNDED_DEFAULT_LIMIT",
    "Phase8OfflineReplayRecurrentBoundedPlan",
    "Phase8OfflineReplayRecurrentBoundedPlanDecision",
    "StrategyPhase8OfflineReplayRecurrentBoundedPlanner",
    "generate_phase8_offline_replay_recurrent_bounded_plan",
)
