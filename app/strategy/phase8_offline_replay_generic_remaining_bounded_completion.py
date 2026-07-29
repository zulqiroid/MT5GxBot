"""Generic bounded completion for the remaining Phase 8 offline replay.

This module consumes the already-approved Step 8.56 planning decision and
completes the remaining offline replay sequence in deterministic in-memory
chunks. It creates immutable chunk receipts and one terminal reusable state.
It does not evaluate strategy logic, initialize MT5, contact a broker, write
external state, or submit orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETION_SCHEMA_VERSION = "1.0"
PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_DEFAULT_CHUNK_LIMIT = 32
PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETED = "COMPLETED"


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
class Phase8OfflineReplayGenericBoundedChunkReceipt:
    """Immutable receipt for one in-memory bounded replay chunk."""

    chunk_index: int
    start_cursor_index: int
    resulting_cursor_index: int
    initial_consumed_count: int
    resulting_consumed_count: int
    initial_remaining_count: int
    resulting_remaining_count: int
    event_sequence_indices: tuple[int, ...]
    event_count: int
    next_event_sequence_index: int | None
    total_event_count: int
    reaches_terminal_state: bool

    executes_strategy: bool = False
    executes_simulation: bool = False
    initializes_mt5: bool = False
    sends_broker_request: bool = False
    writes_external_state: bool = False
    can_submit_order: bool = False

    def __post_init__(self) -> None:
        if self.chunk_index < 0:
            raise ValueError("chunk_index cannot be negative.")

        if self.event_count < 1:
            raise ValueError("event_count must be positive.")

        if len(self.event_sequence_indices) != self.event_count:
            raise ValueError("event sequence count is inconsistent.")

        expected_indices = tuple(range(self.start_cursor_index, self.resulting_cursor_index))
        if self.event_sequence_indices != expected_indices:
            raise ValueError("event sequence indices are inconsistent.")

        if self.resulting_cursor_index != self.start_cursor_index + self.event_count:
            raise ValueError("resulting cursor is inconsistent.")

        if self.resulting_consumed_count != self.initial_consumed_count + self.event_count:
            raise ValueError("resulting consumed count is inconsistent.")

        if self.resulting_remaining_count != self.initial_remaining_count - self.event_count:
            raise ValueError("resulting remaining count is inconsistent.")

        if self.resulting_consumed_count + self.resulting_remaining_count != self.total_event_count:
            raise ValueError("chunk counters do not preserve total.")

        if self.reaches_terminal_state:
            if self.resulting_remaining_count != 0:
                raise ValueError("terminal chunk must have zero remaining.")
            if self.next_event_sequence_index is not None:
                raise ValueError("terminal chunk cannot expose a next event.")
        else:
            if self.resulting_remaining_count < 1:
                raise ValueError("active chunk must retain events.")
            if self.next_event_sequence_index != self.resulting_cursor_index:
                raise ValueError("next event sequence is inconsistent.")

    @property
    def chunk_digest(self) -> str:
        sequence_material = ",".join(str(index) for index in self.event_sequence_indices)
        material = "|".join(
            (
                PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETION_SCHEMA_VERSION,
                str(self.chunk_index),
                str(self.start_cursor_index),
                str(self.resulting_cursor_index),
                str(self.initial_consumed_count),
                str(self.resulting_consumed_count),
                str(self.initial_remaining_count),
                str(self.resulting_remaining_count),
                sequence_material,
                str(self.event_count),
                str(self.next_event_sequence_index),
                str(self.total_event_count),
                str(self.reaches_terminal_state),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def chunk_id(self) -> str:
        return f"PHASE_8_OFFLINE_REPLAY_GENERIC_BOUNDED_CHUNK:SHA256[{self.chunk_digest}]"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayGenericRemainingCompletionState:
    """Immutable terminal state for the completed remaining replay."""

    plan_decision: object
    initial_plan: object
    source_decision: object
    source_state: object

    source_state_version: int
    state_version: int
    initial_cursor_index: int
    cursor_index: int
    initial_consumed_count: int
    consumed_count: int
    initial_remaining_count: int
    remaining_count: int
    last_consumed_sequence_index: int
    next_event_sequence_index: None
    total_event_count: int
    chunk_limit: int
    chunk_receipts: tuple[Phase8OfflineReplayGenericBoundedChunkReceipt, ...]
    consumed_event_sequence_indices: tuple[int, ...]
    lifecycle: str

    executes_strategy: bool = False
    executes_simulation: bool = False
    initializes_mt5: bool = False
    sends_broker_request: bool = False
    writes_external_state: bool = False
    can_submit_order: bool = False

    def __post_init__(self) -> None:
        if self.source_state_version < 1:
            raise ValueError("source_state_version must be positive.")

        if self.state_version != self.source_state_version + 1:
            raise ValueError("state_version must advance exactly once.")

        if self.chunk_limit < 1:
            raise ValueError("chunk_limit must be positive.")

        if not self.chunk_receipts:
            raise ValueError("completion requires chunk receipts.")

        if self.initial_cursor_index != self.initial_consumed_count:
            raise ValueError("initial cursor and consumed count differ.")

        if self.cursor_index != self.consumed_count:
            raise ValueError("final cursor and consumed count differ.")

        if self.initial_consumed_count + self.initial_remaining_count != (self.total_event_count):
            raise ValueError("initial counters do not preserve total.")

        if self.consumed_count != self.total_event_count:
            raise ValueError("completion must consume the full replay.")

        if self.remaining_count != 0:
            raise ValueError("completion must have zero remaining.")

        if self.last_consumed_sequence_index != self.total_event_count - 1:
            raise ValueError("last consumed sequence is inconsistent.")

        if self.next_event_sequence_index is not None:
            raise ValueError("completed state cannot expose a next event.")

        if self.lifecycle != PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETED:
            raise ValueError("completion lifecycle must be COMPLETED.")

        expected_indices = tuple(range(self.initial_cursor_index, self.total_event_count))
        if self.consumed_event_sequence_indices != expected_indices:
            raise ValueError("completion sequence has gaps or duplicates.")

        flattened_indices = tuple(
            sequence_index
            for receipt in self.chunk_receipts
            for sequence_index in receipt.event_sequence_indices
        )
        if flattened_indices != expected_indices:
            raise ValueError("chunk lineage has gaps or duplicates.")

        if self.chunk_receipts[0].start_cursor_index != (self.initial_cursor_index):
            raise ValueError("first chunk start is inconsistent.")

        if self.chunk_receipts[-1].resulting_cursor_index != (self.total_event_count):
            raise ValueError("last chunk cursor is inconsistent.")

        if not self.chunk_receipts[-1].reaches_terminal_state:
            raise ValueError("last chunk must reach terminal state.")

        for expected_index, receipt in enumerate(self.chunk_receipts):
            if receipt.chunk_index != expected_index:
                raise ValueError("chunk indices are not contiguous.")
            if receipt.event_count > self.chunk_limit:
                raise ValueError("chunk exceeds configured limit.")
            if expected_index > 0:
                prior = self.chunk_receipts[expected_index - 1]
                if receipt.start_cursor_index != (prior.resulting_cursor_index):
                    raise ValueError("chunk cursors are not contiguous.")

    @property
    def completion_digest(self) -> str:
        plan_id = str(getattr(self.initial_plan, "plan_id", ""))
        chunk_material = ",".join(receipt.chunk_digest for receipt in self.chunk_receipts)
        material = "|".join(
            (
                PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETION_SCHEMA_VERSION,
                plan_id,
                str(self.source_state_version),
                str(self.state_version),
                str(self.initial_cursor_index),
                str(self.cursor_index),
                str(self.initial_consumed_count),
                str(self.consumed_count),
                str(self.initial_remaining_count),
                str(self.remaining_count),
                str(self.last_consumed_sequence_index),
                str(self.next_event_sequence_index),
                str(self.total_event_count),
                str(self.chunk_limit),
                chunk_material,
                self.lifecycle,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def completion_id(self) -> str:
        return (
            f"PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_COMPLETION:SHA256[{self.completion_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayGenericRemainingCompletionDecision:
    """Allowed or blocked generic remaining replay completion."""

    is_allowed: bool
    state: Phase8OfflineReplayGenericRemainingCompletionState | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.state is None:
                raise ValueError("Allowed decision requires a state.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.state is not None:
                raise ValueError("Blocked decision cannot have a state.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def state_required(
        self,
    ) -> Phase8OfflineReplayGenericRemainingCompletionState:
        if self.state is None:
            raise RuntimeError("Generic remaining bounded replay completion is blocked.")
        return self.state


class StrategyPhase8OfflineReplayGenericRemainingBoundedCompletionEngine:
    """Completes all remaining offline events in deterministic chunks."""

    def complete(
        self,
        plan_decision: object,
        *,
        chunk_limit: int = (PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_DEFAULT_CHUNK_LIMIT),
    ) -> Phase8OfflineReplayGenericRemainingCompletionDecision:
        if plan_decision is None:
            return Phase8OfflineReplayGenericRemainingCompletionDecision(
                is_allowed=False,
                state=None,
                blockers=("plan_decision_missing",),
            )

        if getattr(plan_decision, "is_allowed", True) is not True:
            return Phase8OfflineReplayGenericRemainingCompletionDecision(
                is_allowed=False,
                state=None,
                blockers=("plan_decision_blocked",),
            )

        if isinstance(chunk_limit, bool) or not isinstance(chunk_limit, int) or chunk_limit < 1:
            return Phase8OfflineReplayGenericRemainingCompletionDecision(
                is_allowed=False,
                state=None,
                blockers=("chunk_limit_invalid",),
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
            total_event_count = _required_int(
                plan,
                "total_event_count",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase8OfflineReplayGenericRemainingCompletionDecision(
                is_allowed=False,
                state=None,
                blockers=(f"initial_plan_invalid:{type(error).__name__}",),
            )

        if (
            not isinstance(planned_indices, tuple)
            or not planned_indices
            or any(
                isinstance(index, bool) or not isinstance(index, int) for index in planned_indices
            )
        ):
            return Phase8OfflineReplayGenericRemainingCompletionDecision(
                is_allowed=False,
                state=None,
                blockers=("initial_plan_sequence_invalid",),
            )

        if planned_transition_count > chunk_limit:
            return Phase8OfflineReplayGenericRemainingCompletionDecision(
                is_allowed=False,
                state=None,
                blockers=("initial_plan_exceeds_chunk_limit",),
            )

        if planned_indices != tuple(range(start_cursor_index, resulting_cursor_index)):
            return Phase8OfflineReplayGenericRemainingCompletionDecision(
                is_allowed=False,
                state=None,
                blockers=("initial_plan_sequence_inconsistent",),
            )

        if resulting_consumed_count + resulting_remaining_count != (total_event_count):
            return Phase8OfflineReplayGenericRemainingCompletionDecision(
                is_allowed=False,
                state=None,
                blockers=("initial_plan_counters_inconsistent",),
            )

        receipts: list[Phase8OfflineReplayGenericBoundedChunkReceipt] = []

        try:
            first_receipt = Phase8OfflineReplayGenericBoundedChunkReceipt(
                chunk_index=0,
                start_cursor_index=start_cursor_index,
                resulting_cursor_index=resulting_cursor_index,
                initial_consumed_count=initial_consumed_count,
                resulting_consumed_count=resulting_consumed_count,
                initial_remaining_count=initial_remaining_count,
                resulting_remaining_count=resulting_remaining_count,
                event_sequence_indices=planned_indices,
                event_count=planned_transition_count,
                next_event_sequence_index=(
                    None if resulting_remaining_count == 0 else resulting_cursor_index
                ),
                total_event_count=total_event_count,
                reaches_terminal_state=resulting_remaining_count == 0,
            )
            receipts.append(first_receipt)

            cursor = resulting_cursor_index
            consumed = resulting_consumed_count
            remaining = resulting_remaining_count
            chunk_index = 1

            while remaining > 0:
                event_count = min(chunk_limit, remaining)
                next_cursor = cursor + event_count
                next_consumed = consumed + event_count
                next_remaining = remaining - event_count
                reaches_terminal = next_remaining == 0

                receipt = Phase8OfflineReplayGenericBoundedChunkReceipt(
                    chunk_index=chunk_index,
                    start_cursor_index=cursor,
                    resulting_cursor_index=next_cursor,
                    initial_consumed_count=consumed,
                    resulting_consumed_count=next_consumed,
                    initial_remaining_count=remaining,
                    resulting_remaining_count=next_remaining,
                    event_sequence_indices=tuple(range(cursor, next_cursor)),
                    event_count=event_count,
                    next_event_sequence_index=(None if reaches_terminal else next_cursor),
                    total_event_count=total_event_count,
                    reaches_terminal_state=reaches_terminal,
                )
                receipts.append(receipt)

                cursor = next_cursor
                consumed = next_consumed
                remaining = next_remaining
                chunk_index += 1

            state = Phase8OfflineReplayGenericRemainingCompletionState(
                plan_decision=plan_decision,
                initial_plan=plan,
                source_decision=source_decision,
                source_state=source_state,
                source_state_version=source_state_version,
                state_version=source_state_version + 1,
                initial_cursor_index=start_cursor_index,
                cursor_index=cursor,
                initial_consumed_count=initial_consumed_count,
                consumed_count=consumed,
                initial_remaining_count=initial_remaining_count,
                remaining_count=remaining,
                last_consumed_sequence_index=cursor - 1,
                next_event_sequence_index=None,
                total_event_count=total_event_count,
                chunk_limit=chunk_limit,
                chunk_receipts=tuple(receipts),
                consumed_event_sequence_indices=tuple(range(start_cursor_index, cursor)),
                lifecycle=(PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETED),
            )
        except ValueError as error:
            return Phase8OfflineReplayGenericRemainingCompletionDecision(
                is_allowed=False,
                state=None,
                blockers=(f"generic_completion_invalid:{type(error).__name__}",),
            )

        return Phase8OfflineReplayGenericRemainingCompletionDecision(
            is_allowed=True,
            state=state,
            blockers=(),
        )


def complete_phase8_offline_replay_remaining_with_generic_bounded_engine(
    plan_decision: object,
    *,
    chunk_limit: int = (PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_DEFAULT_CHUNK_LIMIT),
) -> Phase8OfflineReplayGenericRemainingCompletionDecision:
    """Complete all remaining replay events in deterministic chunks."""

    return StrategyPhase8OfflineReplayGenericRemainingBoundedCompletionEngine().complete(
        plan_decision,
        chunk_limit=chunk_limit,
    )


__all__ = (
    "PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETION_SCHEMA_VERSION",
    "PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_DEFAULT_CHUNK_LIMIT",
    "PHASE_8_OFFLINE_REPLAY_GENERIC_REMAINING_BOUNDED_COMPLETED",
    "Phase8OfflineReplayGenericBoundedChunkReceipt",
    "Phase8OfflineReplayGenericRemainingCompletionState",
    "Phase8OfflineReplayGenericRemainingCompletionDecision",
    "StrategyPhase8OfflineReplayGenericRemainingBoundedCompletionEngine",
    "complete_phase8_offline_replay_remaining_with_generic_bounded_engine",
)
