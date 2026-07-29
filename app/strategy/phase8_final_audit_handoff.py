"""Immutable Phase 8 final audit and handoff bundle.

This module converts the successful terminal exhaustion audit into one
immutable Phase 8 completion handoff. It verifies the prior reusable state,
the completed remaining replay, terminal counters, terminal re-entry guard,
and all no-effect safety flags. It performs no strategy evaluation,
simulation, MT5 operation, broker request, external write, or order
submission.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase8_offline_replay_terminal_exhaustion_audit import (
    PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_PASSED,
    PHASE_8_OFFLINE_REPLAY_TERMINAL_REENTRY_BLOCKED,
    block_phase8_offline_replay_terminal_reentry,
)

PHASE_8_FINAL_AUDIT_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_8_FINAL_AUDIT_HANDOFF_COMPLETE = "PHASE_8_COMPLETE"
PHASE_8_FINAL_AUDIT_HANDOFF_READY_FOR_PHASE_9 = "READY_FOR_PHASE_9"


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
class Phase8FinalAuditHandoffBundle:
    """Immutable proof that Phase 8 is complete and safe to hand off."""

    terminal_audit_decision: object
    terminal_audit_report: object
    terminal_reentry_guard: object
    completion_state: object
    prior_reusable_state: object

    phase_number: int
    prior_state_version: int
    terminal_state_version: int

    total_event_count: int
    prior_consumed_count: int
    completed_remaining_event_count: int
    final_consumed_count: int
    final_remaining_count: int

    first_event_sequence_index: int
    prior_last_consumed_sequence_index: int
    completion_first_sequence_index: int
    final_last_consumed_sequence_index: int
    next_event_sequence_index: None

    bounded_chunk_count: int
    bounded_chunk_limit: int
    terminal_lifecycle: str
    terminal_audit_status: str
    terminal_reentry_status: str

    phase_status: str
    handoff_status: str
    phase_complete: bool
    ready_for_phase_9: bool

    exact_total_preserved: bool
    prior_boundary_contiguous: bool
    completed_sequence_contiguous: bool
    terminal_counters_valid: bool
    terminal_reentry_blocked: bool
    safety_flags_valid: bool

    executes_strategy: bool = False
    executes_simulation: bool = False
    initializes_mt5: bool = False
    sends_broker_request: bool = False
    writes_external_state: bool = False
    can_submit_order: bool = False

    def __post_init__(self) -> None:
        if self.phase_number != 8:
            raise ValueError("phase_number must be 8.")

        if self.prior_state_version < 1:
            raise ValueError("prior_state_version must be positive.")

        if self.terminal_state_version != self.prior_state_version + 1:
            raise ValueError("terminal state version is inconsistent.")

        if self.total_event_count < 1:
            raise ValueError("total event count must be positive.")

        if self.prior_consumed_count < 0:
            raise ValueError("prior consumed count cannot be negative.")

        if self.completed_remaining_event_count < 1:
            raise ValueError("completed remaining count must be positive.")

        if (
            self.prior_consumed_count + self.completed_remaining_event_count
            != self.total_event_count
        ):
            raise ValueError("Phase 8 event totals are inconsistent.")

        if self.final_consumed_count != self.total_event_count:
            raise ValueError("final consumed count must equal total.")

        if self.final_remaining_count != 0:
            raise ValueError("final remaining count must be zero.")

        if self.first_event_sequence_index != 0:
            raise ValueError("Phase 8 sequence must begin at zero.")

        if self.prior_last_consumed_sequence_index != self.prior_consumed_count - 1:
            raise ValueError("prior last sequence is inconsistent.")

        if self.completion_first_sequence_index != self.prior_consumed_count:
            raise ValueError("completion boundary is inconsistent.")

        if self.final_last_consumed_sequence_index != self.total_event_count - 1:
            raise ValueError("final last sequence is inconsistent.")

        if self.next_event_sequence_index is not None:
            raise ValueError("completed phase cannot expose a next event.")

        if self.bounded_chunk_count < 1:
            raise ValueError("bounded chunk count must be positive.")

        if self.bounded_chunk_limit < 1:
            raise ValueError("bounded chunk limit must be positive.")

        if self.terminal_lifecycle != "COMPLETED":
            raise ValueError("terminal lifecycle must be COMPLETED.")

        if self.terminal_audit_status != PHASE_8_OFFLINE_REPLAY_TERMINAL_EXHAUSTION_AUDIT_PASSED:
            raise ValueError("terminal audit must be PASSED.")

        if self.terminal_reentry_status != PHASE_8_OFFLINE_REPLAY_TERMINAL_REENTRY_BLOCKED:
            raise ValueError("terminal re-entry must be BLOCKED.")

        if self.phase_status != PHASE_8_FINAL_AUDIT_HANDOFF_COMPLETE:
            raise ValueError("phase status must be PHASE_8_COMPLETE.")

        if self.handoff_status != PHASE_8_FINAL_AUDIT_HANDOFF_READY_FOR_PHASE_9:
            raise ValueError("handoff status must be READY_FOR_PHASE_9.")

        required_truths = (
            self.phase_complete,
            self.ready_for_phase_9,
            self.exact_total_preserved,
            self.prior_boundary_contiguous,
            self.completed_sequence_contiguous,
            self.terminal_counters_valid,
            self.terminal_reentry_blocked,
            self.safety_flags_valid,
        )
        if not all(required_truths):
            raise ValueError("final handoff contains a failed invariant.")

    @property
    def handoff_digest(self) -> str:
        audit_id = str(getattr(self.terminal_audit_report, "audit_id", ""))
        completion_id = str(getattr(self.completion_state, "completion_id", ""))
        prior_state_id = str(getattr(self.prior_reusable_state, "state_id", ""))
        material = "|".join(
            (
                PHASE_8_FINAL_AUDIT_HANDOFF_SCHEMA_VERSION,
                audit_id,
                completion_id,
                prior_state_id,
                str(self.phase_number),
                str(self.prior_state_version),
                str(self.terminal_state_version),
                str(self.total_event_count),
                str(self.prior_consumed_count),
                str(self.completed_remaining_event_count),
                str(self.final_consumed_count),
                str(self.final_remaining_count),
                str(self.first_event_sequence_index),
                str(self.prior_last_consumed_sequence_index),
                str(self.completion_first_sequence_index),
                str(self.final_last_consumed_sequence_index),
                str(self.next_event_sequence_index),
                str(self.bounded_chunk_count),
                str(self.bounded_chunk_limit),
                self.terminal_lifecycle,
                self.terminal_audit_status,
                self.terminal_reentry_status,
                self.phase_status,
                self.handoff_status,
                str(self.phase_complete),
                str(self.ready_for_phase_9),
                str(self.exact_total_preserved),
                str(self.prior_boundary_contiguous),
                str(self.completed_sequence_contiguous),
                str(self.terminal_counters_valid),
                str(self.terminal_reentry_blocked),
                str(self.safety_flags_valid),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return f"GOLDXBOT_PHASE_8_FINAL_AUDIT_HANDOFF:SHA256[{self.handoff_digest}]"


@dataclass(frozen=True, slots=True)
class Phase8FinalAuditHandoffDecision:
    """Allowed or blocked Phase 8 final handoff decision."""

    is_allowed: bool
    bundle: Phase8FinalAuditHandoffBundle | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.bundle is None:
                raise ValueError("Allowed decision requires a bundle.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.bundle is not None:
                raise ValueError("Blocked decision cannot have a bundle.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def bundle_required(self) -> Phase8FinalAuditHandoffBundle:
        if self.bundle is None:
            raise RuntimeError("Phase 8 final audit handoff is blocked.")
        return self.bundle


class StrategyPhase8FinalAuditHandoffFactory:
    """Creates the immutable Phase 8 completion handoff."""

    def create(
        self,
        terminal_audit_decision: object,
    ) -> Phase8FinalAuditHandoffDecision:
        if terminal_audit_decision is None:
            return Phase8FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=("terminal_audit_decision_missing",),
            )

        if getattr(terminal_audit_decision, "is_allowed", True) is not True:
            return Phase8FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=("terminal_audit_decision_blocked",),
            )

        try:
            report = _required_attribute(
                terminal_audit_decision,
                "report_required",
            )
            completion_state = _required_attribute(
                report,
                "completion_state",
            )
            prior_state = _required_attribute(
                completion_state,
                "source_state",
            )
            reentry_guard = block_phase8_offline_replay_terminal_reentry(terminal_audit_decision)

            prior_state_version = _required_int(
                prior_state,
                "state_version",
            )
            terminal_state_version = _required_int(
                completion_state,
                "state_version",
            )
            total_event_count = _required_int(
                completion_state,
                "total_event_count",
            )
            prior_consumed_count = _required_int(
                prior_state,
                "consumed_count",
            )
            prior_remaining_count = _required_int(
                prior_state,
                "remaining_count",
            )
            prior_last_consumed_sequence_index = _required_int(
                prior_state,
                "last_consumed_sequence_index",
            )
            prior_next_event_sequence_index = _required_int(
                prior_state,
                "next_event_sequence_index",
            )
            final_consumed_count = _required_int(
                completion_state,
                "consumed_count",
            )
            final_remaining_count = _required_int(
                completion_state,
                "remaining_count",
            )
            final_last_consumed_sequence_index = _required_int(
                completion_state,
                "last_consumed_sequence_index",
            )
            next_event_sequence_index = _required_attribute(
                completion_state,
                "next_event_sequence_index",
            )
            chunk_receipts = _required_attribute(
                completion_state,
                "chunk_receipts",
            )
            chunk_limit = _required_int(
                completion_state,
                "chunk_limit",
            )
            lifecycle = _required_attribute(
                completion_state,
                "lifecycle",
            )
            audited_indices = _required_attribute(
                report,
                "audited_event_sequence_indices",
            )
            audit_status = _required_attribute(report, "status")
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase8FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=(f"phase8_handoff_source_invalid:{type(error).__name__}",),
            )

        if (
            not isinstance(chunk_receipts, tuple)
            or not chunk_receipts
            or not isinstance(audited_indices, tuple)
            or not isinstance(lifecycle, str)
            or not isinstance(audit_status, str)
        ):
            return Phase8FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=("phase8_handoff_source_shape_invalid",),
            )

        completed_remaining_event_count = len(audited_indices)
        expected_remaining_indices = tuple(range(prior_consumed_count, total_event_count))

        exact_total_preserved = (
            prior_consumed_count + completed_remaining_event_count == total_event_count
            and prior_consumed_count + prior_remaining_count == total_event_count
        )
        prior_boundary_contiguous = (
            prior_last_consumed_sequence_index == prior_consumed_count - 1
            and prior_next_event_sequence_index == prior_consumed_count
            and audited_indices
            and audited_indices[0] == prior_next_event_sequence_index
        )
        completed_sequence_contiguous = audited_indices == expected_remaining_indices and len(
            audited_indices
        ) == len(set(audited_indices))
        terminal_counters_valid = (
            terminal_state_version == prior_state_version + 1
            and final_consumed_count == total_event_count
            and final_remaining_count == 0
            and final_last_consumed_sequence_index == total_event_count - 1
            and next_event_sequence_index is None
            and lifecycle == "COMPLETED"
        )
        terminal_reentry_blocked = (
            reentry_guard.is_allowed is False
            and reentry_guard.status == PHASE_8_OFFLINE_REPLAY_TERMINAL_REENTRY_BLOCKED
            and reentry_guard.blockers == ("offline_replay_already_completed",)
            and reentry_guard.additional_event_count == 0
            and reentry_guard.next_event_sequence_index is None
        )

        report_safety_valid = all(
            getattr(report, attribute, None) is False
            for attribute in (
                "executes_strategy",
                "executes_simulation",
                "initializes_mt5",
                "sends_broker_request",
                "writes_external_state",
                "can_submit_order",
            )
        )
        guard_safety_valid = all(
            getattr(reentry_guard, attribute, None) is False
            for attribute in (
                "executes_strategy",
                "executes_simulation",
                "initializes_mt5",
                "sends_broker_request",
                "writes_external_state",
                "can_submit_order",
            )
        )
        completion_safety_valid = all(
            getattr(completion_state, attribute, None) is False
            for attribute in (
                "executes_strategy",
                "executes_simulation",
                "initializes_mt5",
                "sends_broker_request",
                "writes_external_state",
                "can_submit_order",
            )
        )
        safety_flags_valid = (
            report_safety_valid
            and guard_safety_valid
            and completion_safety_valid
            and getattr(report, "safety_flags_valid", False) is True
        )

        try:
            bundle = Phase8FinalAuditHandoffBundle(
                terminal_audit_decision=terminal_audit_decision,
                terminal_audit_report=report,
                terminal_reentry_guard=reentry_guard,
                completion_state=completion_state,
                prior_reusable_state=prior_state,
                phase_number=8,
                prior_state_version=prior_state_version,
                terminal_state_version=terminal_state_version,
                total_event_count=total_event_count,
                prior_consumed_count=prior_consumed_count,
                completed_remaining_event_count=(completed_remaining_event_count),
                final_consumed_count=final_consumed_count,
                final_remaining_count=final_remaining_count,
                first_event_sequence_index=0,
                prior_last_consumed_sequence_index=(prior_last_consumed_sequence_index),
                completion_first_sequence_index=audited_indices[0],
                final_last_consumed_sequence_index=(final_last_consumed_sequence_index),
                next_event_sequence_index=next_event_sequence_index,
                bounded_chunk_count=len(chunk_receipts),
                bounded_chunk_limit=chunk_limit,
                terminal_lifecycle=lifecycle,
                terminal_audit_status=audit_status,
                terminal_reentry_status=reentry_guard.status,
                phase_status=PHASE_8_FINAL_AUDIT_HANDOFF_COMPLETE,
                handoff_status=(PHASE_8_FINAL_AUDIT_HANDOFF_READY_FOR_PHASE_9),
                phase_complete=True,
                ready_for_phase_9=True,
                exact_total_preserved=exact_total_preserved,
                prior_boundary_contiguous=prior_boundary_contiguous,
                completed_sequence_contiguous=(completed_sequence_contiguous),
                terminal_counters_valid=terminal_counters_valid,
                terminal_reentry_blocked=terminal_reentry_blocked,
                safety_flags_valid=safety_flags_valid,
            )
        except (IndexError, ValueError) as error:
            return Phase8FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=(f"phase8_final_handoff_invalid:{type(error).__name__}",),
            )

        return Phase8FinalAuditHandoffDecision(
            is_allowed=True,
            bundle=bundle,
            blockers=(),
        )


def create_phase8_final_audit_handoff(
    terminal_audit_decision: object,
) -> Phase8FinalAuditHandoffDecision:
    """Create the immutable Phase 8 final audit handoff."""

    return StrategyPhase8FinalAuditHandoffFactory().create(terminal_audit_decision)


__all__ = (
    "PHASE_8_FINAL_AUDIT_HANDOFF_SCHEMA_VERSION",
    "PHASE_8_FINAL_AUDIT_HANDOFF_COMPLETE",
    "PHASE_8_FINAL_AUDIT_HANDOFF_READY_FOR_PHASE_9",
    "Phase8FinalAuditHandoffBundle",
    "Phase8FinalAuditHandoffDecision",
    "StrategyPhase8FinalAuditHandoffFactory",
    "create_phase8_final_audit_handoff",
)
