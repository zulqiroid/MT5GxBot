"""Immutable terminal exhaustion audit for Phase 8 offline replay.

This module audits the terminal state produced by the generic remaining
bounded completion engine. It verifies complete sequence coverage, chunk
continuity, terminal counters, lineage, safety flags, and terminal re-entry
blocking. It performs no strategy evaluation, simulation, MT5 operation,
broker request, external write, or order submission.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_PASSED = "PASSED"
PHASE_8_OFFLINE_REPLAY_TERMINAL_REENTRY_BLOCKED = "BLOCKED"


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
class Phase8OfflineReplayTerminalExhaustionAuditReport:
    """Immutable proof that the offline replay is terminal and exhausted."""

    completion_decision: object
    completion_state: object

    source_state_version: int
    terminal_state_version: int
    initial_cursor_index: int
    final_cursor_index: int
    total_event_count: int
    consumed_count: int
    remaining_count: int
    last_consumed_sequence_index: int
    next_event_sequence_index: None

    chunk_limit: int
    chunk_count: int
    first_chunk_start_index: int
    last_chunk_end_index: int
    audited_event_sequence_indices: tuple[int, ...]
    lifecycle: str

    complete_sequence_coverage: bool
    chunk_indices_contiguous: bool
    chunk_cursors_contiguous: bool
    chunk_counters_contiguous: bool
    no_duplicate_sequences: bool
    no_missing_sequences: bool
    no_reordered_sequences: bool
    final_chunk_terminal: bool
    terminal_counters_valid: bool
    terminal_reentry_allowed: bool
    additional_event_count: int
    safety_flags_valid: bool
    status: str

    executes_strategy: bool = False
    executes_simulation: bool = False
    initializes_mt5: bool = False
    sends_broker_request: bool = False
    writes_external_state: bool = False
    can_submit_order: bool = False

    def __post_init__(self) -> None:
        if self.source_state_version < 1:
            raise ValueError("source_state_version must be positive.")

        if self.terminal_state_version != self.source_state_version + 1:
            raise ValueError("terminal state version is inconsistent.")

        if self.initial_cursor_index < 0:
            raise ValueError("initial cursor cannot be negative.")

        if self.final_cursor_index != self.total_event_count:
            raise ValueError("terminal cursor must equal total event count.")

        if self.consumed_count != self.total_event_count:
            raise ValueError("terminal consumed count must equal total.")

        if self.remaining_count != 0:
            raise ValueError("terminal remaining count must be zero.")

        if self.last_consumed_sequence_index != self.total_event_count - 1:
            raise ValueError("terminal last sequence is inconsistent.")

        if self.next_event_sequence_index is not None:
            raise ValueError("terminal audit cannot expose a next event.")

        if self.chunk_limit < 1:
            raise ValueError("chunk limit must be positive.")

        if self.chunk_count < 1:
            raise ValueError("chunk count must be positive.")

        if self.first_chunk_start_index != self.initial_cursor_index:
            raise ValueError("first chunk start is inconsistent.")

        if self.last_chunk_end_index != self.total_event_count:
            raise ValueError("last chunk end is inconsistent.")

        expected_indices = tuple(range(self.initial_cursor_index, self.total_event_count))
        if self.audited_event_sequence_indices != expected_indices:
            raise ValueError("audited sequence indices are inconsistent.")

        required_truths = (
            self.complete_sequence_coverage,
            self.chunk_indices_contiguous,
            self.chunk_cursors_contiguous,
            self.chunk_counters_contiguous,
            self.no_duplicate_sequences,
            self.no_missing_sequences,
            self.no_reordered_sequences,
            self.final_chunk_terminal,
            self.terminal_counters_valid,
            self.safety_flags_valid,
        )
        if not all(required_truths):
            raise ValueError("terminal audit contains a failed invariant.")

        if self.terminal_reentry_allowed:
            raise ValueError("terminal replay re-entry must be blocked.")

        if self.additional_event_count != 0:
            raise ValueError("terminal audit cannot expose extra events.")

        if self.status != PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_PASSED:
            raise ValueError("terminal audit status must be PASSED.")

    @property
    def audit_digest(self) -> str:
        completion_id = str(getattr(self.completion_state, "completion_id", ""))
        material = "|".join(
            (
                PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_SCHEMA_VERSION,
                completion_id,
                str(self.source_state_version),
                str(self.terminal_state_version),
                str(self.initial_cursor_index),
                str(self.final_cursor_index),
                str(self.total_event_count),
                str(self.consumed_count),
                str(self.remaining_count),
                str(self.last_consumed_sequence_index),
                str(self.next_event_sequence_index),
                str(self.chunk_limit),
                str(self.chunk_count),
                str(self.first_chunk_start_index),
                str(self.last_chunk_end_index),
                str(self.complete_sequence_coverage),
                str(self.chunk_indices_contiguous),
                str(self.chunk_cursors_contiguous),
                str(self.chunk_counters_contiguous),
                str(self.no_duplicate_sequences),
                str(self.no_missing_sequences),
                str(self.no_reordered_sequences),
                str(self.final_chunk_terminal),
                str(self.terminal_counters_valid),
                str(self.terminal_reentry_allowed),
                str(self.additional_event_count),
                str(self.safety_flags_valid),
                self.status,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return f"PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT:SHA256[{self.audit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayTerminalExhaustionAuditDecision:
    """Allowed or blocked terminal exhaustion audit."""

    is_allowed: bool
    report: Phase8OfflineReplayTerminalExhaustionAuditReport | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.report is None:
                raise ValueError("Allowed decision requires a report.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.report is not None:
                raise ValueError("Blocked decision cannot have a report.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def report_required(
        self,
    ) -> Phase8OfflineReplayTerminalExhaustionAuditReport:
        if self.report is None:
            raise RuntimeError("Phase 8 terminal exhaustion audit is blocked.")
        return self.report


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayTerminalReentryDecision:
    """Immutable terminal re-entry guard result."""

    is_allowed: bool
    status: str
    blockers: tuple[str, ...]
    additional_event_count: int
    next_event_sequence_index: None

    executes_strategy: bool = False
    executes_simulation: bool = False
    initializes_mt5: bool = False
    sends_broker_request: bool = False
    writes_external_state: bool = False
    can_submit_order: bool = False

    def __post_init__(self) -> None:
        if self.is_allowed:
            raise ValueError("terminal re-entry must never be allowed.")

        if self.status != PHASE_8_OFFLINE_REPLAY_TERMINAL_REENTRY_BLOCKED:
            raise ValueError("terminal re-entry status must be BLOCKED.")

        if self.blockers != ("offline_replay_already_completed",):
            raise ValueError("terminal re-entry blocker is inconsistent.")

        if self.additional_event_count != 0:
            raise ValueError("terminal re-entry cannot expose events.")

        if self.next_event_sequence_index is not None:
            raise ValueError("terminal re-entry cannot expose next event.")


class StrategyPhase8OfflineReplayTerminalExhaustionAuditor:
    """Audits terminal replay completion without executing anything."""

    def audit(
        self,
        completion_decision: object,
    ) -> Phase8OfflineReplayTerminalExhaustionAuditDecision:
        if completion_decision is None:
            return Phase8OfflineReplayTerminalExhaustionAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("completion_decision_missing",),
            )

        if getattr(completion_decision, "is_allowed", True) is not True:
            return Phase8OfflineReplayTerminalExhaustionAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("completion_decision_blocked",),
            )

        try:
            state = _required_attribute(
                completion_decision,
                "state_required",
            )
            source_state_version = _required_int(
                state,
                "source_state_version",
            )
            terminal_state_version = _required_int(
                state,
                "state_version",
            )
            initial_cursor_index = _required_int(
                state,
                "initial_cursor_index",
            )
            final_cursor_index = _required_int(
                state,
                "cursor_index",
            )
            total_event_count = _required_int(
                state,
                "total_event_count",
            )
            consumed_count = _required_int(
                state,
                "consumed_count",
            )
            remaining_count = _required_int(
                state,
                "remaining_count",
            )
            last_consumed_sequence_index = _required_int(
                state,
                "last_consumed_sequence_index",
            )
            next_event_sequence_index = _required_attribute(
                state,
                "next_event_sequence_index",
            )
            chunk_limit = _required_int(state, "chunk_limit")
            chunk_receipts = _required_attribute(
                state,
                "chunk_receipts",
            )
            consumed_indices = _required_attribute(
                state,
                "consumed_event_sequence_indices",
            )
            lifecycle = _required_attribute(state, "lifecycle")
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase8OfflineReplayTerminalExhaustionAuditDecision(
                is_allowed=False,
                report=None,
                blockers=(f"completion_state_invalid:{type(error).__name__}",),
            )

        if (
            not isinstance(chunk_receipts, tuple)
            or not chunk_receipts
            or not isinstance(consumed_indices, tuple)
            or not isinstance(lifecycle, str)
        ):
            return Phase8OfflineReplayTerminalExhaustionAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("completion_state_shape_invalid",),
            )

        flattened_indices = tuple(
            sequence_index
            for receipt in chunk_receipts
            for sequence_index in getattr(
                receipt,
                "event_sequence_indices",
                (),
            )
        )
        expected_indices = tuple(range(initial_cursor_index, total_event_count))

        chunk_indices = tuple(getattr(receipt, "chunk_index", None) for receipt in chunk_receipts)
        expected_chunk_indices = tuple(range(len(chunk_receipts)))

        chunk_cursors_contiguous = all(
            current.start_cursor_index == prior.resulting_cursor_index
            for prior, current in zip(
                chunk_receipts[:-1],
                chunk_receipts[1:],
                strict=True,
            )
        )
        chunk_counters_contiguous = all(
            (
                current.initial_consumed_count == prior.resulting_consumed_count
                and current.initial_remaining_count == prior.resulting_remaining_count
            )
            for prior, current in zip(
                chunk_receipts[:-1],
                chunk_receipts[1:],
                strict=True,
            )
        )

        state_safety_flags_valid = all(
            getattr(state, attribute, None) is False
            for attribute in (
                "executes_strategy",
                "executes_simulation",
                "initializes_mt5",
                "sends_broker_request",
                "writes_external_state",
                "can_submit_order",
            )
        )
        chunk_safety_flags_valid = all(
            getattr(receipt, attribute, None) is False
            for receipt in chunk_receipts
            for attribute in (
                "executes_strategy",
                "executes_simulation",
                "initializes_mt5",
                "sends_broker_request",
                "writes_external_state",
                "can_submit_order",
            )
        )

        complete_sequence_coverage = (
            consumed_indices == expected_indices and flattened_indices == expected_indices
        )
        no_duplicate_sequences = len(flattened_indices) == len(set(flattened_indices))
        no_missing_sequences = set(flattened_indices) == set(expected_indices)
        no_reordered_sequences = flattened_indices == expected_indices
        final_chunk_terminal = (
            chunk_receipts[-1].reaches_terminal_state is True
            and chunk_receipts[-1].next_event_sequence_index is None
            and chunk_receipts[-1].resulting_cursor_index == total_event_count
        )
        terminal_counters_valid = (
            final_cursor_index == total_event_count
            and consumed_count == total_event_count
            and remaining_count == 0
            and last_consumed_sequence_index == total_event_count - 1
            and next_event_sequence_index is None
            and lifecycle == "COMPLETED"
        )
        chunk_sizes_valid = all(
            1 <= receipt.event_count <= chunk_limit for receipt in chunk_receipts
        )
        safety_flags_valid = (
            state_safety_flags_valid and chunk_safety_flags_valid and chunk_sizes_valid
        )

        try:
            report = Phase8OfflineReplayTerminalExhaustionAuditReport(
                completion_decision=completion_decision,
                completion_state=state,
                source_state_version=source_state_version,
                terminal_state_version=terminal_state_version,
                initial_cursor_index=initial_cursor_index,
                final_cursor_index=final_cursor_index,
                total_event_count=total_event_count,
                consumed_count=consumed_count,
                remaining_count=remaining_count,
                last_consumed_sequence_index=(last_consumed_sequence_index),
                next_event_sequence_index=next_event_sequence_index,
                chunk_limit=chunk_limit,
                chunk_count=len(chunk_receipts),
                first_chunk_start_index=(chunk_receipts[0].start_cursor_index),
                last_chunk_end_index=(chunk_receipts[-1].resulting_cursor_index),
                audited_event_sequence_indices=flattened_indices,
                lifecycle=lifecycle,
                complete_sequence_coverage=complete_sequence_coverage,
                chunk_indices_contiguous=(chunk_indices == expected_chunk_indices),
                chunk_cursors_contiguous=chunk_cursors_contiguous,
                chunk_counters_contiguous=chunk_counters_contiguous,
                no_duplicate_sequences=no_duplicate_sequences,
                no_missing_sequences=no_missing_sequences,
                no_reordered_sequences=no_reordered_sequences,
                final_chunk_terminal=final_chunk_terminal,
                terminal_counters_valid=terminal_counters_valid,
                terminal_reentry_allowed=False,
                additional_event_count=0,
                safety_flags_valid=safety_flags_valid,
                status=(PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_PASSED),
            )
        except ValueError as error:
            return Phase8OfflineReplayTerminalExhaustionAuditDecision(
                is_allowed=False,
                report=None,
                blockers=(f"terminal_audit_failed:{type(error).__name__}",),
            )

        return Phase8OfflineReplayTerminalExhaustionAuditDecision(
            is_allowed=True,
            report=report,
            blockers=(),
        )


def audit_phase8_offline_replay_terminal_exhaustion(
    completion_decision: object,
) -> Phase8OfflineReplayTerminalExhaustionAuditDecision:
    """Audit the completed Phase 8 offline replay terminal state."""

    return StrategyPhase8OfflineReplayTerminalExhaustionAuditor().audit(completion_decision)


def block_phase8_offline_replay_terminal_reentry(
    audit_decision: object,
) -> Phase8OfflineReplayTerminalReentryDecision:
    """Return the immutable terminal replay re-entry guard result."""

    if audit_decision is None:
        raise ValueError("audit_decision is required.")

    if getattr(audit_decision, "is_allowed", False) is not True:
        raise ValueError("successful terminal audit is required.")

    report = _required_attribute(audit_decision, "report_required")

    if getattr(report, "terminal_reentry_allowed", True) is not False:
        raise ValueError("terminal audit did not block re-entry.")

    return Phase8OfflineReplayTerminalReentryDecision(
        is_allowed=False,
        status=PHASE_8_OFFLINE_REPLAY_TERMINAL_REENTRY_BLOCKED,
        blockers=("offline_replay_already_completed",),
        additional_event_count=0,
        next_event_sequence_index=None,
    )


__all__ = (
    "PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_SCHEMA_VERSION",
    "PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_PASSED",
    "PHASE_8_OFFLINE_REPLAY_TERMINAL_REENTRY_BLOCKED",
    "Phase8OfflineReplayTerminalExhaustionAuditReport",
    "Phase8OfflineReplayTerminalExhaustionAuditDecision",
    "Phase8OfflineReplayTerminalReentryDecision",
    "StrategyPhase8OfflineReplayTerminalExhaustionAuditor",
    "audit_phase8_offline_replay_terminal_exhaustion",
    "block_phase8_offline_replay_terminal_reentry",
)
