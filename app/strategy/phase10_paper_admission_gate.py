"""Immutable Phase 10 paper-only admission gate.

This module consumes the completed Phase 9 handoff and creates one
immutable permit for Phase 10 paper-trading planning only. It carries
forward the XAUUSD-only, closed-candle, one-position, staged-risk, OCO,
broker stop-loss, and kill-switch invariants. It does not execute a paper
trade, initialize MT5, contact a broker, write external state, or submit a
live order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_10_PAPER_ADMISSION_SCHEMA_VERSION = "1.0"
PHASE_10_PAPER_ADMISSION_MODE = "PAPER_ONLY"
PHASE_10_PAPER_ADMISSION_STATUS = "ADMITTED"
PHASE_10_LIVE_EXECUTION_STATUS = "BLOCKED"
PHASE_10_ALLOWED_SYMBOL = "XAUUSD"
PHASE_10_ALLOWED_TIMEFRAMES = ("H4", "H1", "M15", "M5")
PHASE_10_MAX_GOLD_POSITIONS = 1
PHASE_10_AGGREGATE_RISK_BUDGET_BPS = 50
PHASE_10_STAGE_RISK_BPS = (25, 25)


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
class Phase10PaperAdmissionPermit:
    """Immutable permit for Phase 10 paper-trading planning only."""

    phase9_handoff_decision: object
    phase9_handoff_bundle: object

    source_phase_number: int
    target_phase_number: int
    source_phase_status: str
    source_handoff_status: str
    source_simulation_mode: str
    source_live_execution_status: str
    source_safety_audit_status: str

    admission_mode: str
    admission_status: str
    live_execution_status: str

    allowed_symbol: str
    allowed_timeframes: tuple[str, ...]
    closed_candles_only: bool

    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]
    one_gold_position_max: bool
    staged_aggregate_risk_required: bool
    oco_required: bool
    broker_stop_loss_required: bool
    kill_switches_required: bool
    martingale_prohibited: bool
    grid_prohibited: bool
    no_stop_loss_prohibited: bool

    permits_paper_planning: bool
    permits_paper_execution: bool
    permits_strategy_evaluation: bool
    permits_mt5_initialization: bool
    permits_broker_requests: bool
    permits_external_writes: bool
    permits_live_order_submission: bool

    phase10_foundation_ready: bool

    def __post_init__(self) -> None:
        if self.source_phase_number != 9:
            raise ValueError("source phase must be 9.")

        if self.target_phase_number != 10:
            raise ValueError("target phase must be 10.")

        if self.source_phase_status != "PHASE_9_COMPLETE":
            raise ValueError("Phase 9 must be complete.")

        if self.source_handoff_status != "READY_FOR_PHASE_10":
            raise ValueError("Phase 9 handoff is not ready for Phase 10.")

        if self.source_simulation_mode != "IN_MEMORY_ONLY":
            raise ValueError("Phase 9 simulation mode is inconsistent.")

        if self.source_live_execution_status != "BLOCKED":
            raise ValueError("Phase 9 live execution must remain blocked.")

        if self.source_safety_audit_status != "PASSED":
            raise ValueError("Phase 9 safety audit must be PASSED.")

        if self.admission_mode != PHASE_10_PAPER_ADMISSION_MODE:
            raise ValueError("admission mode must be PAPER_ONLY.")

        if self.admission_status != PHASE_10_PAPER_ADMISSION_STATUS:
            raise ValueError("admission status must be ADMITTED.")

        if self.live_execution_status != PHASE_10_LIVE_EXECUTION_STATUS:
            raise ValueError("live execution must be BLOCKED.")

        if self.allowed_symbol != PHASE_10_ALLOWED_SYMBOL:
            raise ValueError("Phase 10 admission is XAUUSD only.")

        if self.allowed_timeframes != PHASE_10_ALLOWED_TIMEFRAMES:
            raise ValueError("allowed timeframes are inconsistent.")

        if self.max_gold_positions != PHASE_10_MAX_GOLD_POSITIONS:
            raise ValueError("only one Gold position is allowed.")

        if self.aggregate_risk_budget_bps != PHASE_10_AGGREGATE_RISK_BUDGET_BPS:
            raise ValueError("aggregate risk budget is inconsistent.")

        if self.stage_risk_bps != PHASE_10_STAGE_RISK_BPS:
            raise ValueError("stage risk allocation is inconsistent.")

        if sum(self.stage_risk_bps) != self.aggregate_risk_budget_bps:
            raise ValueError("stage risk must equal aggregate risk budget.")

        required_truths = (
            self.closed_candles_only,
            self.one_gold_position_max,
            self.staged_aggregate_risk_required,
            self.oco_required,
            self.broker_stop_loss_required,
            self.kill_switches_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.permits_paper_planning,
            self.phase10_foundation_ready,
        )
        if not all(required_truths):
            raise ValueError("Phase 10 admission lost a required invariant.")

        forbidden_capabilities = (
            self.permits_paper_execution,
            self.permits_strategy_evaluation,
            self.permits_mt5_initialization,
            self.permits_broker_requests,
            self.permits_external_writes,
            self.permits_live_order_submission,
        )
        if any(forbidden_capabilities):
            raise ValueError("Phase 10 admission gate cannot enable execution effects.")

    @property
    def permit_digest(self) -> str:
        source_handoff_id = str(getattr(self.phase9_handoff_bundle, "handoff_id", ""))
        material = "|".join(
            (
                PHASE_10_PAPER_ADMISSION_SCHEMA_VERSION,
                source_handoff_id,
                str(self.source_phase_number),
                str(self.target_phase_number),
                self.source_phase_status,
                self.source_handoff_status,
                self.source_simulation_mode,
                self.source_live_execution_status,
                self.source_safety_audit_status,
                self.admission_mode,
                self.admission_status,
                self.live_execution_status,
                self.allowed_symbol,
                ",".join(self.allowed_timeframes),
                str(self.closed_candles_only),
                str(self.max_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.one_gold_position_max),
                str(self.staged_aggregate_risk_required),
                str(self.oco_required),
                str(self.broker_stop_loss_required),
                str(self.kill_switches_required),
                str(self.martingale_prohibited),
                str(self.grid_prohibited),
                str(self.no_stop_loss_prohibited),
                str(self.permits_paper_planning),
                str(self.permits_paper_execution),
                str(self.permits_strategy_evaluation),
                str(self.permits_mt5_initialization),
                str(self.permits_broker_requests),
                str(self.permits_external_writes),
                str(self.permits_live_order_submission),
                str(self.phase10_foundation_ready),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def permit_id(self) -> str:
        return f"GOLDXBOT_PHASE_10_PAPER_ADMISSION:SHA256[{self.permit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase10PaperAdmissionDecision:
    """Allowed or blocked Phase 10 paper admission decision."""

    is_allowed: bool
    permit: Phase10PaperAdmissionPermit | None
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
    def permit_required(self) -> Phase10PaperAdmissionPermit:
        if self.permit is None:
            raise RuntimeError("Phase 10 paper admission is blocked.")
        return self.permit


class StrategyPhase10PaperAdmissionGate:
    """Admits only the Phase 10 paper-planning foundation."""

    def evaluate(
        self,
        phase9_handoff_decision: object,
    ) -> Phase10PaperAdmissionDecision:
        if phase9_handoff_decision is None:
            return Phase10PaperAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=("phase9_handoff_decision_missing",),
            )

        if getattr(phase9_handoff_decision, "is_allowed", True) is not True:
            return Phase10PaperAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=("phase9_handoff_decision_blocked",),
            )

        try:
            bundle = _required_attribute(
                phase9_handoff_decision,
                "bundle_required",
            )
            phase_number = _required_int(bundle, "phase_number")
            phase_status = _required_attribute(bundle, "phase_status")
            handoff_status = _required_attribute(bundle, "handoff_status")
            simulation_mode = _required_attribute(
                bundle,
                "simulation_mode",
            )
            source_live_execution_status = _required_attribute(
                bundle,
                "live_execution_status",
            )
            safety_audit_status = _required_attribute(
                bundle,
                "safety_audit_status",
            )
            symbol = _required_attribute(bundle, "symbol")
            timeframes = _required_attribute(bundle, "timeframes")
            closed_candles_only = _required_attribute(
                bundle,
                "closed_candles_only",
            )
            aggregate_risk_budget_bps = _required_int(
                bundle,
                "aggregate_risk_budget_bps",
            )
            stage_risk_bps = _required_attribute(
                bundle,
                "stage_risk_bps",
            )
            maximum_gold_position_count = _required_int(
                bundle,
                "maximum_gold_position_count",
            )
            phase_complete = _required_attribute(
                bundle,
                "phase_complete",
            )
            ready_for_phase_10 = _required_attribute(
                bundle,
                "ready_for_phase_10",
            )
            safety_audit_passed = _required_attribute(
                bundle,
                "safety_audit_passed",
            )
            no_live_or_external_effects = _required_attribute(
                bundle,
                "no_live_or_external_effects",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase10PaperAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=(f"phase9_handoff_invalid:{type(error).__name__}",),
            )

        source_valid = (
            phase_number == 9
            and phase_status == "PHASE_9_COMPLETE"
            and handoff_status == "READY_FOR_PHASE_10"
            and simulation_mode == "IN_MEMORY_ONLY"
            and source_live_execution_status == "BLOCKED"
            and safety_audit_status == "PASSED"
            and symbol == "XAUUSD"
            and timeframes == ("H4", "H1", "M15", "M5")
            and closed_candles_only is True
            and aggregate_risk_budget_bps == 50
            and stage_risk_bps == (25, 25)
            and maximum_gold_position_count == 1
            and phase_complete is True
            and ready_for_phase_10 is True
            and safety_audit_passed is True
            and no_live_or_external_effects is True
        )
        if not source_valid:
            return Phase10PaperAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=("phase9_handoff_contract_invalid",),
            )

        try:
            permit = Phase10PaperAdmissionPermit(
                phase9_handoff_decision=phase9_handoff_decision,
                phase9_handoff_bundle=bundle,
                source_phase_number=phase_number,
                target_phase_number=10,
                source_phase_status=str(phase_status),
                source_handoff_status=str(handoff_status),
                source_simulation_mode=str(simulation_mode),
                source_live_execution_status=str(source_live_execution_status),
                source_safety_audit_status=str(safety_audit_status),
                admission_mode=PHASE_10_PAPER_ADMISSION_MODE,
                admission_status=PHASE_10_PAPER_ADMISSION_STATUS,
                live_execution_status=PHASE_10_LIVE_EXECUTION_STATUS,
                allowed_symbol=PHASE_10_ALLOWED_SYMBOL,
                allowed_timeframes=PHASE_10_ALLOWED_TIMEFRAMES,
                closed_candles_only=True,
                max_gold_positions=PHASE_10_MAX_GOLD_POSITIONS,
                aggregate_risk_budget_bps=(PHASE_10_AGGREGATE_RISK_BUDGET_BPS),
                stage_risk_bps=PHASE_10_STAGE_RISK_BPS,
                one_gold_position_max=True,
                staged_aggregate_risk_required=True,
                oco_required=True,
                broker_stop_loss_required=True,
                kill_switches_required=True,
                martingale_prohibited=True,
                grid_prohibited=True,
                no_stop_loss_prohibited=True,
                permits_paper_planning=True,
                permits_paper_execution=False,
                permits_strategy_evaluation=False,
                permits_mt5_initialization=False,
                permits_broker_requests=False,
                permits_external_writes=False,
                permits_live_order_submission=False,
                phase10_foundation_ready=True,
            )
        except ValueError as error:
            return Phase10PaperAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=(f"phase10_paper_admission_failed:{type(error).__name__}",),
            )

        return Phase10PaperAdmissionDecision(
            is_allowed=True,
            permit=permit,
            blockers=(),
        )


def evaluate_phase10_paper_admission(
    phase9_handoff_decision: object,
) -> Phase10PaperAdmissionDecision:
    """Evaluate the immutable Phase 10 paper-only admission gate."""

    return StrategyPhase10PaperAdmissionGate().evaluate(phase9_handoff_decision)


__all__ = (
    "PHASE_10_PAPER_ADMISSION_SCHEMA_VERSION",
    "PHASE_10_PAPER_ADMISSION_MODE",
    "PHASE_10_PAPER_ADMISSION_STATUS",
    "PHASE_10_LIVE_EXECUTION_STATUS",
    "PHASE_10_ALLOWED_SYMBOL",
    "PHASE_10_ALLOWED_TIMEFRAMES",
    "PHASE_10_MAX_GOLD_POSITIONS",
    "PHASE_10_AGGREGATE_RISK_BUDGET_BPS",
    "PHASE_10_STAGE_RISK_BPS",
    "Phase10PaperAdmissionPermit",
    "Phase10PaperAdmissionDecision",
    "StrategyPhase10PaperAdmissionGate",
    "evaluate_phase10_paper_admission",
)
