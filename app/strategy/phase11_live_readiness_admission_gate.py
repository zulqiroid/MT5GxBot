"""Fail-closed Phase 11 live-readiness admission gate.

This module consumes the completed Phase 10 handoff and creates one
immutable permit for Phase 11 live-readiness planning only. It carries
forward the XAUUSD-only, closed-candle, one-position, staged-risk, OCO,
broker stop-loss, guard, ledger, and terminal-flat-state invariants.

The permit does not authorize MT5 initialization, broker communication,
paper execution, production activation, external writes, or live orders.
A separate future production gate and explicit human authorization remain
mandatory.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_11_LIVE_READINESS_SCHEMA_VERSION = "1.0"
PHASE_11_LIVE_READINESS_ADMISSION_MODE = "LIVE_READINESS_ONLY"
PHASE_11_LIVE_READINESS_ADMISSION_STATUS = "ADMITTED"
PHASE_11_LIVE_EXECUTION_STATUS = "BLOCKED"
PHASE_11_PRODUCTION_ACTIVATION_STATUS = "BLOCKED"
PHASE_11_ALLOWED_SYMBOL = "XAUUSD"
PHASE_11_ALLOWED_TIMEFRAMES = ("H4", "H1", "M15", "M5")
PHASE_11_MAX_GOLD_POSITIONS = 1
PHASE_11_AGGREGATE_RISK_BUDGET_BPS = 50
PHASE_11_STAGE_RISK_BPS = (25, 25)


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
class Phase11LiveReadinessAdmissionPermit:
    """Immutable permit for fail-closed live-readiness planning."""

    phase10_handoff_decision: object
    phase10_handoff_bundle: object

    source_phase_number: int
    target_phase_number: int
    source_phase_status: str
    source_handoff_status: str
    source_execution_mode: str
    source_live_execution_status: str
    source_safety_audit_status: str

    admission_mode: str
    admission_status: str
    live_execution_status: str
    production_activation_status: str

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
    guards_required: bool
    terminal_flat_state_required: bool
    martingale_prohibited: bool
    grid_prohibited: bool
    no_stop_loss_prohibited: bool

    permits_readiness_planning: bool
    permits_capability_inventory_planning: bool
    permits_preflight_execution: bool
    permits_paper_execution: bool
    permits_mt5_initialization: bool
    permits_broker_requests: bool
    permits_external_writes: bool
    permits_live_order_submission: bool

    requires_explicit_human_authorization: bool
    requires_separate_production_gate: bool
    phase11_foundation_ready: bool

    def __post_init__(self) -> None:
        if self.source_phase_number != 10:
            raise ValueError("source phase must be 10.")

        if self.target_phase_number != 11:
            raise ValueError("target phase must be 11.")

        if self.source_phase_status != "PHASE_10_COMPLETE":
            raise ValueError("Phase 10 must be complete.")

        if self.source_handoff_status != "READY_FOR_PHASE_11":
            raise ValueError("Phase 10 handoff is not ready for Phase 11.")

        if self.source_execution_mode != "IN_MEMORY_PAPER":
            raise ValueError("Phase 10 execution mode is inconsistent.")

        if self.source_live_execution_status != "BLOCKED":
            raise ValueError("Phase 10 live execution must remain blocked.")

        if self.source_safety_audit_status != "PASSED":
            raise ValueError("Phase 10 safety audit must be PASSED.")

        if self.admission_mode != PHASE_11_LIVE_READINESS_ADMISSION_MODE:
            raise ValueError("admission mode must be LIVE_READINESS_ONLY.")

        if self.admission_status != PHASE_11_LIVE_READINESS_ADMISSION_STATUS:
            raise ValueError("admission status must be ADMITTED.")

        if self.live_execution_status != PHASE_11_LIVE_EXECUTION_STATUS:
            raise ValueError("live execution must remain BLOCKED.")

        if self.production_activation_status != PHASE_11_PRODUCTION_ACTIVATION_STATUS:
            raise ValueError("production activation must remain BLOCKED.")

        if self.allowed_symbol != PHASE_11_ALLOWED_SYMBOL:
            raise ValueError("Phase 11 admission is XAUUSD only.")

        if self.allowed_timeframes != PHASE_11_ALLOWED_TIMEFRAMES:
            raise ValueError("allowed timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("Phase 11 requires closed candles only.")

        if self.max_gold_positions != PHASE_11_MAX_GOLD_POSITIONS:
            raise ValueError("only one Gold position is allowed.")

        if self.aggregate_risk_budget_bps != PHASE_11_AGGREGATE_RISK_BUDGET_BPS:
            raise ValueError("aggregate risk budget is inconsistent.")

        if self.stage_risk_bps != PHASE_11_STAGE_RISK_BPS:
            raise ValueError("stage risk allocation is inconsistent.")

        if sum(self.stage_risk_bps) != self.aggregate_risk_budget_bps:
            raise ValueError("stage risk must equal aggregate risk.")

        required_truths = (
            self.one_gold_position_max,
            self.staged_aggregate_risk_required,
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.permits_readiness_planning,
            self.permits_capability_inventory_planning,
            self.requires_explicit_human_authorization,
            self.requires_separate_production_gate,
            self.phase11_foundation_ready,
        )
        if not all(required_truths):
            raise ValueError("Phase 11 admission lost a required invariant.")

        forbidden_capabilities = (
            self.permits_preflight_execution,
            self.permits_paper_execution,
            self.permits_mt5_initialization,
            self.permits_broker_requests,
            self.permits_external_writes,
            self.permits_live_order_submission,
        )
        if any(forbidden_capabilities):
            raise ValueError("Phase 11 admission cannot enable execution effects.")

    @property
    def permit_digest(self) -> str:
        source_handoff_id = str(getattr(self.phase10_handoff_bundle, "handoff_id", ""))
        material = "|".join(
            (
                PHASE_11_LIVE_READINESS_SCHEMA_VERSION,
                source_handoff_id,
                str(self.source_phase_number),
                str(self.target_phase_number),
                self.source_phase_status,
                self.source_handoff_status,
                self.source_execution_mode,
                self.source_live_execution_status,
                self.source_safety_audit_status,
                self.admission_mode,
                self.admission_status,
                self.live_execution_status,
                self.production_activation_status,
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
                str(self.guards_required),
                str(self.terminal_flat_state_required),
                str(self.martingale_prohibited),
                str(self.grid_prohibited),
                str(self.no_stop_loss_prohibited),
                str(self.permits_readiness_planning),
                str(self.permits_capability_inventory_planning),
                str(self.permits_preflight_execution),
                str(self.permits_paper_execution),
                str(self.permits_mt5_initialization),
                str(self.permits_broker_requests),
                str(self.permits_external_writes),
                str(self.permits_live_order_submission),
                str(self.requires_explicit_human_authorization),
                str(self.requires_separate_production_gate),
                str(self.phase11_foundation_ready),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def permit_id(self) -> str:
        return f"GOLDXBOT_PHASE_11_LIVE_READINESS_ADMISSION:SHA256[{self.permit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase11LiveReadinessAdmissionDecision:
    """Allowed or blocked Phase 11 admission decision."""

    is_allowed: bool
    permit: Phase11LiveReadinessAdmissionPermit | None
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
    def permit_required(self) -> Phase11LiveReadinessAdmissionPermit:
        if self.permit is None:
            raise RuntimeError("Phase 11 live-readiness admission is blocked.")
        return self.permit


class StrategyPhase11LiveReadinessAdmissionGate:
    """Admits only the fail-closed Phase 11 planning foundation."""

    def evaluate(
        self,
        phase10_handoff_decision: object,
    ) -> Phase11LiveReadinessAdmissionDecision:
        if phase10_handoff_decision is None:
            return Phase11LiveReadinessAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=("phase10_handoff_decision_missing",),
            )

        if getattr(phase10_handoff_decision, "is_allowed", True) is not True:
            return Phase11LiveReadinessAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=("phase10_handoff_decision_blocked",),
            )

        try:
            bundle = _required_attribute(
                phase10_handoff_decision,
                "bundle_required",
            )
            phase_number = _required_int(bundle, "phase_number")
            phase_status = _required_attribute(bundle, "phase_status")
            handoff_status = _required_attribute(bundle, "handoff_status")
            execution_mode = _required_attribute(
                bundle,
                "execution_mode",
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
            terminal_gold_position_count = _required_int(
                bundle,
                "terminal_gold_position_count",
            )
            terminal_active_oco_order_count = _required_int(
                bundle,
                "terminal_active_oco_order_count",
            )
            terminal_reserved_risk_bps = _required_int(
                bundle,
                "terminal_reserved_risk_bps",
            )
            phase_complete = _required_attribute(
                bundle,
                "phase_complete",
            )
            ready_for_phase_11 = _required_attribute(
                bundle,
                "ready_for_phase_11",
            )
            safety_audit_passed = _required_attribute(
                bundle,
                "safety_audit_passed",
            )
            oco_contract_valid = _required_attribute(
                bundle,
                "oco_contract_valid",
            )
            guard_contract_valid = _required_attribute(
                bundle,
                "guard_contract_valid",
            )
            no_live_or_external_effects = _required_attribute(
                bundle,
                "no_live_or_external_effects",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase11LiveReadinessAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=(f"phase10_handoff_invalid:{type(error).__name__}",),
            )

        source_valid = (
            phase_number == 10
            and phase_status == "PHASE_10_COMPLETE"
            and handoff_status == "READY_FOR_PHASE_11"
            and execution_mode == "IN_MEMORY_PAPER"
            and source_live_execution_status == "BLOCKED"
            and safety_audit_status == "PASSED"
            and symbol == "XAUUSD"
            and timeframes == ("H4", "H1", "M15", "M5")
            and closed_candles_only is True
            and aggregate_risk_budget_bps == 50
            and stage_risk_bps == (25, 25)
            and maximum_gold_position_count == 1
            and terminal_gold_position_count == 0
            and terminal_active_oco_order_count == 0
            and terminal_reserved_risk_bps == 0
            and phase_complete is True
            and ready_for_phase_11 is True
            and safety_audit_passed is True
            and oco_contract_valid is True
            and guard_contract_valid is True
            and no_live_or_external_effects is True
        )
        if not source_valid:
            return Phase11LiveReadinessAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=("phase10_handoff_contract_invalid",),
            )

        try:
            permit = Phase11LiveReadinessAdmissionPermit(
                phase10_handoff_decision=phase10_handoff_decision,
                phase10_handoff_bundle=bundle,
                source_phase_number=phase_number,
                target_phase_number=11,
                source_phase_status=str(phase_status),
                source_handoff_status=str(handoff_status),
                source_execution_mode=str(execution_mode),
                source_live_execution_status=str(source_live_execution_status),
                source_safety_audit_status=str(safety_audit_status),
                admission_mode=(PHASE_11_LIVE_READINESS_ADMISSION_MODE),
                admission_status=(PHASE_11_LIVE_READINESS_ADMISSION_STATUS),
                live_execution_status=PHASE_11_LIVE_EXECUTION_STATUS,
                production_activation_status=(PHASE_11_PRODUCTION_ACTIVATION_STATUS),
                allowed_symbol=PHASE_11_ALLOWED_SYMBOL,
                allowed_timeframes=PHASE_11_ALLOWED_TIMEFRAMES,
                closed_candles_only=True,
                max_gold_positions=PHASE_11_MAX_GOLD_POSITIONS,
                aggregate_risk_budget_bps=(PHASE_11_AGGREGATE_RISK_BUDGET_BPS),
                stage_risk_bps=PHASE_11_STAGE_RISK_BPS,
                one_gold_position_max=True,
                staged_aggregate_risk_required=True,
                oco_required=True,
                broker_stop_loss_required=True,
                guards_required=True,
                terminal_flat_state_required=True,
                martingale_prohibited=True,
                grid_prohibited=True,
                no_stop_loss_prohibited=True,
                permits_readiness_planning=True,
                permits_capability_inventory_planning=True,
                permits_preflight_execution=False,
                permits_paper_execution=False,
                permits_mt5_initialization=False,
                permits_broker_requests=False,
                permits_external_writes=False,
                permits_live_order_submission=False,
                requires_explicit_human_authorization=True,
                requires_separate_production_gate=True,
                phase11_foundation_ready=True,
            )
        except ValueError as error:
            return Phase11LiveReadinessAdmissionDecision(
                is_allowed=False,
                permit=None,
                blockers=(f"phase11_live_readiness_admission_failed:{type(error).__name__}",),
            )

        return Phase11LiveReadinessAdmissionDecision(
            is_allowed=True,
            permit=permit,
            blockers=(),
        )


def evaluate_phase11_live_readiness_admission(
    phase10_handoff_decision: object,
) -> Phase11LiveReadinessAdmissionDecision:
    """Evaluate the fail-closed Phase 11 admission gate."""

    return StrategyPhase11LiveReadinessAdmissionGate().evaluate(phase10_handoff_decision)


__all__ = (
    "PHASE_11_LIVE_READINESS_SCHEMA_VERSION",
    "PHASE_11_LIVE_READINESS_ADMISSION_MODE",
    "PHASE_11_LIVE_READINESS_ADMISSION_STATUS",
    "PHASE_11_LIVE_EXECUTION_STATUS",
    "PHASE_11_PRODUCTION_ACTIVATION_STATUS",
    "PHASE_11_ALLOWED_SYMBOL",
    "PHASE_11_ALLOWED_TIMEFRAMES",
    "PHASE_11_MAX_GOLD_POSITIONS",
    "PHASE_11_AGGREGATE_RISK_BUDGET_BPS",
    "PHASE_11_STAGE_RISK_BPS",
    "Phase11LiveReadinessAdmissionPermit",
    "Phase11LiveReadinessAdmissionDecision",
    "StrategyPhase11LiveReadinessAdmissionGate",
    "evaluate_phase11_live_readiness_admission",
)
