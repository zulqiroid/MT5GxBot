# Immutable bounded offline replay iteration planning.

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_PLAN_SCHEMA_VERSION = "1.0"


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
class Phase8OfflineReplayBoundedIterationPlanPolicy:
    max_transition_count: int = 32

    def __post_init__(self) -> None:
        if isinstance(self.max_transition_count, bool) or not isinstance(
            self.max_transition_count,
            int,
        ):
            raise ValueError("max_transition_count must be an integer.")
        if self.max_transition_count < 1:
            raise ValueError("max_transition_count must be at least 1.")
        if self.max_transition_count > 64:
            raise ValueError("max_transition_count must not exceed 64.")


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayBoundedIterationPlan:
    policy: Phase8OfflineReplayBoundedIterationPlanPolicy
    source_decision: object
    source_state: object
    source_state_version: int
    start_cursor_index: int
    stop_cursor_index: int
    initial_consumed_count: int
    planned_consumed_count: int
    initial_remaining_count: int
    planned_remaining_count: int
    first_event_sequence_index: int
    last_event_sequence_index: int
    next_event_sequence_index: int | None
    planned_transition_count: int
    total_event_count: int
    reaches_terminal_state: bool
    executes_transition: bool = False
    consumes_events: bool = False
    advances_cursor: bool = False
    creates_next_state: bool = False
    executes_strategy: bool = False
    executes_simulation: bool = False
    initializes_mt5: bool = False
    sends_broker_request: bool = False
    writes_external_state: bool = False
    can_submit_order: bool = False

    def __post_init__(self) -> None:
        if self.planned_transition_count < 1:
            raise ValueError("planned_transition_count must be positive.")
        if self.planned_transition_count > self.policy.max_transition_count:
            raise ValueError("planned_transition_count exceeds policy.")
        if self.stop_cursor_index != self.start_cursor_index + self.planned_transition_count:
            raise ValueError("stop cursor is inconsistent.")
        if (
            self.planned_consumed_count
            != self.initial_consumed_count + self.planned_transition_count
        ):
            raise ValueError("planned consumed count is inconsistent.")
        if (
            self.planned_remaining_count
            != self.initial_remaining_count - self.planned_transition_count
        ):
            raise ValueError("planned remaining count is inconsistent.")
        if self.initial_consumed_count + self.initial_remaining_count != self.total_event_count:
            raise ValueError("initial counters do not preserve total.")
        if self.planned_consumed_count + self.planned_remaining_count != self.total_event_count:
            raise ValueError("planned counters do not preserve total.")
        expected_last = self.first_event_sequence_index + self.planned_transition_count - 1
        if self.last_event_sequence_index != expected_last:
            raise ValueError("last event sequence is inconsistent.")
        if self.reaches_terminal_state:
            if self.planned_remaining_count != 0:
                raise ValueError("terminal plan must have zero remaining.")
            if self.next_event_sequence_index is not None:
                raise ValueError("terminal plan cannot expose a next event.")
        else:
            if self.planned_remaining_count < 1:
                raise ValueError("active plan must retain events.")
            if self.next_event_sequence_index != self.last_event_sequence_index + 1:
                raise ValueError("next event sequence is inconsistent.")

    @property
    def plan_digest(self) -> str:
        material = "|".join(
            (
                PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_PLAN_SCHEMA_VERSION,
                str(self.source_state_version),
                str(self.start_cursor_index),
                str(self.stop_cursor_index),
                str(self.initial_consumed_count),
                str(self.planned_consumed_count),
                str(self.initial_remaining_count),
                str(self.planned_remaining_count),
                str(self.first_event_sequence_index),
                str(self.last_event_sequence_index),
                str(self.next_event_sequence_index),
                str(self.planned_transition_count),
                str(self.total_event_count),
                str(self.reaches_terminal_state),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def plan_id(self) -> str:
        return f"PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_PLAN:SHA256[{self.plan_digest}]"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayBoundedIterationPlanDecision:
    is_allowed: bool
    plan: Phase8OfflineReplayBoundedIterationPlan | None
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
    def plan_required(self) -> Phase8OfflineReplayBoundedIterationPlan:
        if self.plan is None:
            raise RuntimeError("Bounded replay iteration plan is blocked.")
        return self.plan


class StrategyPhase8OfflineReplayBoundedIterationPlanFactory:
    def __init__(
        self,
        policy: Phase8OfflineReplayBoundedIterationPlanPolicy | None = None,
    ) -> None:
        self._policy = policy or Phase8OfflineReplayBoundedIterationPlanPolicy()

    def generate(
        self,
        source_decision: object,
    ) -> Phase8OfflineReplayBoundedIterationPlanDecision:
        if source_decision is None:
            return Phase8OfflineReplayBoundedIterationPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("source_decision_missing",),
            )

        if getattr(source_decision, "is_allowed", True) is not True:
            return Phase8OfflineReplayBoundedIterationPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("source_decision_blocked",),
            )

        try:
            source_state = _required_attribute(
                source_decision,
                "state_required",
            )
            state_version = _required_int(source_state, "state_version")
            cursor_index = _required_int(source_state, "cursor_index")
            consumed_count = _required_int(source_state, "consumed_count")
            remaining_count = _required_int(source_state, "remaining_count")
            last_consumed_sequence_index = _required_int(
                source_state,
                "last_consumed_sequence_index",
            )
            next_event_sequence_index = _required_int(
                source_state,
                "next_event_sequence_index",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase8OfflineReplayBoundedIterationPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=(f"source_state_invalid:{type(error).__name__}",),
            )

        if remaining_count < 1:
            return Phase8OfflineReplayBoundedIterationPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("source_state_terminal",),
            )
        if cursor_index != consumed_count:
            return Phase8OfflineReplayBoundedIterationPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("cursor_consumed_mismatch",),
            )
        if last_consumed_sequence_index != cursor_index - 1:
            return Phase8OfflineReplayBoundedIterationPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("last_consumed_sequence_mismatch",),
            )
        if next_event_sequence_index != cursor_index:
            return Phase8OfflineReplayBoundedIterationPlanDecision(
                is_allowed=False,
                plan=None,
                blockers=("next_event_sequence_mismatch",),
            )

        total_event_count = consumed_count + remaining_count
        planned_transition_count = min(
            self._policy.max_transition_count,
            remaining_count,
        )
        stop_cursor_index = cursor_index + planned_transition_count
        planned_consumed_count = consumed_count + planned_transition_count
        planned_remaining_count = remaining_count - planned_transition_count
        first_event_sequence_index = next_event_sequence_index
        last_event_sequence_index = first_event_sequence_index + planned_transition_count - 1
        reaches_terminal_state = planned_remaining_count == 0
        planned_next_event_sequence_index = (
            None if reaches_terminal_state else last_event_sequence_index + 1
        )

        plan = Phase8OfflineReplayBoundedIterationPlan(
            policy=self._policy,
            source_decision=source_decision,
            source_state=source_state,
            source_state_version=state_version,
            start_cursor_index=cursor_index,
            stop_cursor_index=stop_cursor_index,
            initial_consumed_count=consumed_count,
            planned_consumed_count=planned_consumed_count,
            initial_remaining_count=remaining_count,
            planned_remaining_count=planned_remaining_count,
            first_event_sequence_index=first_event_sequence_index,
            last_event_sequence_index=last_event_sequence_index,
            next_event_sequence_index=planned_next_event_sequence_index,
            planned_transition_count=planned_transition_count,
            total_event_count=total_event_count,
            reaches_terminal_state=reaches_terminal_state,
        )

        return Phase8OfflineReplayBoundedIterationPlanDecision(
            is_allowed=True,
            plan=plan,
            blockers=(),
        )


def generate_phase8_offline_replay_bounded_iteration_plan(
    source_decision: object,
    *,
    policy: Phase8OfflineReplayBoundedIterationPlanPolicy | None = None,
) -> Phase8OfflineReplayBoundedIterationPlanDecision:
    return StrategyPhase8OfflineReplayBoundedIterationPlanFactory(policy=policy).generate(
        source_decision
    )


__all__ = (
    "PHASE_8_OFFLINE_REPLAY_BOUNDED_ITERATION_PLAN_SCHEMA_VERSION",
    "Phase8OfflineReplayBoundedIterationPlan",
    "Phase8OfflineReplayBoundedIterationPlanDecision",
    "Phase8OfflineReplayBoundedIterationPlanPolicy",
    "StrategyPhase8OfflineReplayBoundedIterationPlanFactory",
    "generate_phase8_offline_replay_bounded_iteration_plan",
)
