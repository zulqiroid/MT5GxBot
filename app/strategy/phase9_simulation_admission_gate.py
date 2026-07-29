"""Immutable Phase 9 simulation-only admission gate.

This module consumes the completed Phase 8 handoff and creates one
immutable permit for Phase 9 simulation planning only. The gate carries
forward the Gold-only, closed-candle, risk, OCO, broker stop-loss, and kill
switch invariants. It does not evaluate strategy logic, run a simulation,
initialize MT5, contact a broker, write external state, or submit orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_9_SIMULATION_ADMISSION_SCHEMA_VERSION = "1.0"
PHASE_9_SIMULATION_ADMISSION_MODE = "SIMULATION_ONLY"
PHASE_9_SIMULATION_ADMISSION_GRANTED = "ADMITTED"
PHASE_9_LIVE_EXECUTION_BLOCKED = "BLOCKED"
PHASE_9_ALLOWED_SYMBOL = "XAUUSD"
PHASE_9_ALLOWED_TIMEFRAMES = ("H4", "H1", "M15", "M5")


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
class Phase9SimulationAdmissionPermit:
    """Immutable permit for Phase 9 simulation planning only."""

    phase8_handoff_decision: object
    phase8_handoff_bundle: object

    source_phase_number: int
    target_phase_number: int
    source_phase_status: str
    source_handoff_status: str
    source_terminal_audit_status: str
    source_terminal_reentry_status: str

    source_total_event_count: int
    source_final_consumed_count: int
    source_final_remaining_count: int
    source_final_last_sequence_index: int
    source_next_event_sequence_index: None

    admission_mode: str
    admission_status: str
    live_execution_status: str

    allowed_symbol: str
    allowed_timeframes: tuple[str, ...]
    closed_candles_only: bool

    one_gold_position_max: bool
    staged_aggregate_risk_required: bool
    oco_required: bool
    broker_stop_loss_required: bool
    martingale_prohibited: bool
    grid_prohibited: bool
    no_stop_loss_prohibited: bool
    kill_switches_required: bool

    permits_simulation_planning: bool
    permits_simulation_execution: bool
    permits_strategy_evaluation: bool
    permits_mt5_initialization: bool
    permits_broker_requests: bool
    permits_external_writes: bool
    permits_order_submission: bool

    phase9_foundation_ready: bool

    def __post_init__(self) -> None:
        if self.source_phase_number != 8:
            raise ValueError("source phase must be 8.")

        if self.target_phase_number != 9:
            raise ValueError("target phase must be 9.")

        if self.source_phase_status != "PHASE_8_COMPLETE":
            raise ValueError("Phase 8 must be complete.")

        if self.source_handoff_status != "READY_FOR_PHASE_9":
            raise ValueError("Phase 8 handoff is not ready for Phase 9.")

        if self.source_terminal_audit_status != "PASSED":
            raise ValueError("terminal audit must be PASSED.")

        if self.source_terminal_reentry_status != "BLOCKED":
            raise ValueError("terminal re-entry must be BLOCKED.")

        if self.source_total_event_count != 800:
            raise ValueError("Phase 8 total event count must be 800.")

        if self.source_final_consumed_count != self.source_total_event_count:
            raise ValueError("Phase 8 final consumed count is incomplete.")

        if self.source_final_remaining_count != 0:
            raise ValueError("Phase 8 must have zero remaining events.")

        if self.source_final_last_sequence_index != self.source_total_event_count - 1:
            raise ValueError("Phase 8 final sequence is inconsistent.")

        if self.source_next_event_sequence_index is not None:
            raise ValueError("completed Phase 8 cannot expose a next event.")

        if self.admission_mode != PHASE_9_SIMULATION_ADMISSION_MODE:
            raise ValueError("admission mode must be SIMULATION_ONLY.")

        if self.admission_status != PHASE_9_SIMULATION_ADMISSION_GRANTED:
            raise ValueError("admission status must be ADMITTED.")

        if self.live_execution_status != PHASE_9_LIVE_EXECUTION_BLOCKED:
            raise ValueError("live execution must be BLOCKED.")

        if self.allowed_symbol != PHASE_9_ALLOWED_SYMBOL:
            raise ValueError("Phase 9 admission is Gold/XAUUSD only.")

        if self.allowed_timeframes != PHASE_9_ALLOWED_TIMEFRAMES:
            raise ValueError("allowed timeframes are inconsistent.")

        required_truths = (
            self.closed_candles_only,
            self.one_gold_position_max,
            self.staged_aggregate_risk_required,
            self.oco_required,
            self.broker_stop_loss_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.kill_switches_required,
            self.permits_simulation_planning,
            self.phase9_foundation_ready,
        )
        if not all(required_truths):
            raise ValueError("Phase 9 admission lost a required invariant.")

        forbidden_capabilities = (
            self.permits_simulation_execution,
            self.permits_strategy_evaluation,
            self.permits_mt5_initialization,
            self.permits_broker_requests,
            self.permits_external_writes,
            self.permits_order_submission,
        )
        if any(forbidden_capabilities):
            raise ValueError("Phase 9 admission gate cannot enable execution effects.")

    @property
    def permit_digest(self) -> str:
        handoff_id = str(getattr(self.phase8_handoff_bundle, "handoff_id", ""))
        material = "|".join(
            (
                PHASE_9_SIMULATION_ADMISSION_SCHEMA_VERSION,
                handoff_id,
                str(self.source_phase_number),
                str(self.target_phase_number),
                self.source_phase_status,
                self.source_handoff_status,
                self.source_terminal_audit_status,
                self.source_terminal_reentry_status,
                str(self.source_total_event_count),
                str(self.source_final_consumed_count),
                str(self.source_final_remaining_count),
                str(self.source_final_last_sequence_index),
                str(self.source_next_event_sequence_index),
                self.admission_mode,
                self.admission_status,
                self.live_execution_status,
                self.allowed_symbol,
                ",".join(self.allowed_timeframes),
                str(self.closed_candles_only),
                str(self.one_gold_position_max),
                str(self.staged_aggregate_risk_required),
                str(self.oco_required),
                str(self.broker_stop_loss_required),
                str(self.martingale_prohibited),
                str(self.grid_prohibited),
                str(self.no_stop_loss_prohibited),
                str(self.kill_switches_required),
                str(self.permits_simulation_planning),
                str(self.permits_simulation_execution),
                str(self.permits_strategy_evaluation),
                str(self.permits_mt5_initialization),
                str(self.permits_broker_requests),
                str(self.permits_external_writes),
                str(self.permits_order_submission),
                str(self.phase9_foundation_ready),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def permit_id(self) -> str:
        return f"GOLDXBOT_PHASE_9_SIMULATION_ADMISSION:SHA256[{self.permit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase9SimulationAdmissionDecision:
    """Allowed or blocked Phase 9 simulation admission decision."""

    is_allowed: bool
    permit: Phase9SimulationAdmissionPermit | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.permit is None:
                raise ValueError("Allowed decision requires a permit.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.permit is not None:
                raise ValueError("Blocked decision cannot have a permit.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def permit_required(self) -> Phase9SimulationAdmissionPermit:
        if self.permit is None:
            raise RuntimeError("Phase 9 simulation admission is blocked.")
        return self.permit


class StrategyPhase9SimulationAdmissionGate:
    """Admits only the Phase 9 simulation-planning foundation."""

    def evaluate(
        self,
        phase8_handoff_decision: object,
    ) -> Phase9SimulationAdmissionDecision:
        if phase8_handoff_decision is None:
            return Phase9SimulationAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=("phase8_handoff_decision_missing",),
            )

        if getattr(phase8_handoff_decision, "is_allowed", True) is not True:
            return Phase9SimulationAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=("phase8_handoff_decision_blocked",),
            )

        try:
            bundle = _required_attribute(
                phase8_handoff_decision,
                "bundle_required",
            )
            phase_number = _required_int(bundle, "phase_number")
            phase_status = _required_attribute(bundle, "phase_status")
            handoff_status = _required_attribute(bundle, "handoff_status")
            terminal_audit_status = _required_attribute(
                bundle,
                "terminal_audit_status",
            )
            terminal_reentry_status = _required_attribute(
                bundle,
                "terminal_reentry_status",
            )
            total_event_count = _required_int(
                bundle,
                "total_event_count",
            )
            final_consumed_count = _required_int(
                bundle,
                "final_consumed_count",
            )
            final_remaining_count = _required_int(
                bundle,
                "final_remaining_count",
            )
            final_last_sequence_index = _required_int(
                bundle,
                "final_last_consumed_sequence_index",
            )
            next_event_sequence_index = _required_attribute(
                bundle,
                "next_event_sequence_index",
            )
            phase_complete = _required_attribute(
                bundle,
                "phase_complete",
            )
            ready_for_phase_9 = _required_attribute(
                bundle,
                "ready_for_phase_9",
            )
            exact_total_preserved = _required_attribute(
                bundle,
                "exact_total_preserved",
            )
            terminal_counters_valid = _required_attribute(
                bundle,
                "terminal_counters_valid",
            )
            terminal_reentry_blocked = _required_attribute(
                bundle,
                "terminal_reentry_blocked",
            )
            safety_flags_valid = _required_attribute(
                bundle,
                "safety_flags_valid",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase9SimulationAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=(f"phase8_handoff_invalid:{type(error).__name__}",),
            )

        required_source_truths = (
            phase_complete,
            ready_for_phase_9,
            exact_total_preserved,
            terminal_counters_valid,
            terminal_reentry_blocked,
            safety_flags_valid,
        )
        if not all(value is True for value in required_source_truths):
            return Phase9SimulationAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=("phase8_handoff_invariants_failed",),
            )

        try:
            permit = Phase9SimulationAdmissionPermit(
                phase8_handoff_decision=phase8_handoff_decision,
                phase8_handoff_bundle=bundle,
                source_phase_number=phase_number,
                target_phase_number=9,
                source_phase_status=str(phase_status),
                source_handoff_status=str(handoff_status),
                source_terminal_audit_status=str(terminal_audit_status),
                source_terminal_reentry_status=str(terminal_reentry_status),
                source_total_event_count=total_event_count,
                source_final_consumed_count=final_consumed_count,
                source_final_remaining_count=final_remaining_count,
                source_final_last_sequence_index=(final_last_sequence_index),
                source_next_event_sequence_index=(next_event_sequence_index),
                admission_mode=PHASE_9_SIMULATION_ADMISSION_MODE,
                admission_status=PHASE_9_SIMULATION_ADMISSION_GRANTED,
                live_execution_status=PHASE_9_LIVE_EXECUTION_BLOCKED,
                allowed_symbol=PHASE_9_ALLOWED_SYMBOL,
                allowed_timeframes=PHASE_9_ALLOWED_TIMEFRAMES,
                closed_candles_only=True,
                one_gold_position_max=True,
                staged_aggregate_risk_required=True,
                oco_required=True,
                broker_stop_loss_required=True,
                martingale_prohibited=True,
                grid_prohibited=True,
                no_stop_loss_prohibited=True,
                kill_switches_required=True,
                permits_simulation_planning=True,
                permits_simulation_execution=False,
                permits_strategy_evaluation=False,
                permits_mt5_initialization=False,
                permits_broker_requests=False,
                permits_external_writes=False,
                permits_order_submission=False,
                phase9_foundation_ready=True,
            )
        except ValueError as error:
            return Phase9SimulationAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=(f"phase9_simulation_admission_failed:{type(error).__name__}",),
            )

        return Phase9SimulationAdmissionDecision(
            is_allowed=True,
            permit=permit,
            blockers=(),
        )


def evaluate_phase9_simulation_admission(
    phase8_handoff_decision: object,
) -> Phase9SimulationAdmissionDecision:
    """Evaluate the immutable Phase 9 simulation-only admission gate."""

    return StrategyPhase9SimulationAdmissionGate().evaluate(phase8_handoff_decision)


__all__ = (
    "PHASE_9_SIMULATION_ADMISSION_SCHEMA_VERSION",
    "PHASE_9_SIMULATION_ADMISSION_MODE",
    "PHASE_9_SIMULATION_ADMISSION_GRANTED",
    "PHASE_9_LIVE_EXECUTION_BLOCKED",
    "PHASE_9_ALLOWED_SYMBOL",
    "PHASE_9_ALLOWED_TIMEFRAMES",
    "Phase9SimulationAdmissionPermit",
    "Phase9SimulationAdmissionDecision",
    "StrategyPhase9SimulationAdmissionGate",
    "evaluate_phase9_simulation_admission",
)
