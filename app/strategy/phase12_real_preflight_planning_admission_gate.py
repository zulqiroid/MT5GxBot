"""Fail-closed Phase 12 real-preflight planning admission gate."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_12_REAL_PREFLIGHT_SCHEMA_VERSION = "1.0"
PHASE_12_REAL_PREFLIGHT_ADMISSION_MODE = "REAL_PREFLIGHT_PLANNING_ONLY"
PHASE_12_REAL_PREFLIGHT_ADMISSION_STATUS = "ADMITTED"
PHASE_12_REAL_PREFLIGHT_EXECUTION_STATUS = "BLOCKED"
PHASE_12_MT5_INITIALIZATION_STATUS = "BLOCKED"
PHASE_12_TERMINAL_CONNECTION_STATUS = "BLOCKED"
PHASE_12_BROKER_ACCESS_STATUS = "BLOCKED"
PHASE_12_PRODUCTION_ACTIVATION_STATUS = "BLOCKED"
PHASE_12_LIVE_EXECUTION_STATUS = "BLOCKED"
PHASE_12_ALLOWED_SYMBOL = "XAUUSD"
PHASE_12_ALLOWED_TIMEFRAMES = ("H4", "H1", "M15", "M5")
PHASE_12_MAX_GOLD_POSITIONS = 1
PHASE_12_AGGREGATE_RISK_BUDGET_BPS = 50
PHASE_12_STAGE_RISK_BPS = (25, 25)


def _required(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase12RealPreflightPlanningAdmissionPermit:
    phase11_handoff_decision: object
    phase11_handoff_bundle: object
    source_phase_number: int
    target_phase_number: int
    source_phase_status: str
    source_handoff_status: str
    source_readiness_mode: str
    source_readiness_audit_status: str
    admission_mode: str
    admission_status: str
    real_preflight_execution_status: str
    mt5_initialization_status: str
    terminal_connection_status: str
    broker_access_status: str
    production_activation_status: str
    live_execution_status: str
    allowed_symbol: str
    allowed_timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]
    oco_required: bool
    broker_stop_loss_required: bool
    guards_required: bool
    terminal_flat_state_required: bool
    martingale_prohibited: bool
    grid_prohibited: bool
    no_stop_loss_prohibited: bool
    verified_capability_count: int
    blocked_capability_count: int
    verified_event_count: int
    permits_contract_planning: bool
    permits_adapter_planning: bool
    permits_snapshot_schema_planning: bool
    permits_real_mt5_import: bool
    permits_mt5_initialization: bool
    permits_terminal_connection: bool
    permits_broker_requests: bool
    permits_real_account_reads: bool
    permits_order_check: bool
    permits_order_send: bool
    permits_external_writes: bool
    permits_production_activation: bool
    permits_live_order_submission: bool
    requires_explicit_human_authorization: bool
    requires_separate_real_preflight_runtime_gate: bool
    requires_separate_production_gate: bool
    phase12_foundation_ready: bool

    def __post_init__(self) -> None:
        if (self.source_phase_number, self.target_phase_number) != (11, 12):
            raise ValueError("Phase transition must be 11 to 12.")
        if self.source_phase_status != "PHASE_11_COMPLETE":
            raise ValueError("Phase 11 must be complete.")
        if self.source_handoff_status != "READY_FOR_PHASE_12":
            raise ValueError("Phase 11 handoff is not ready.")
        if self.source_readiness_mode != "DETERMINISTIC_FAKE_READ_ONLY":
            raise ValueError("Source readiness mode is inconsistent.")
        if self.source_readiness_audit_status != "PASSED":
            raise ValueError("Source readiness audit must pass.")
        if self.admission_mode != PHASE_12_REAL_PREFLIGHT_ADMISSION_MODE:
            raise ValueError("Admission mode is inconsistent.")
        if self.admission_status != PHASE_12_REAL_PREFLIGHT_ADMISSION_STATUS:
            raise ValueError("Admission status is inconsistent.")
        blocked = (
            self.real_preflight_execution_status,
            self.mt5_initialization_status,
            self.terminal_connection_status,
            self.broker_access_status,
            self.production_activation_status,
            self.live_execution_status,
        )
        if any(value != "BLOCKED" for value in blocked):
            raise ValueError("All runtime statuses must remain BLOCKED.")
        if self.allowed_symbol != "XAUUSD":
            raise ValueError("Only XAUUSD is allowed.")
        if self.allowed_timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Timeframes are inconsistent.")
        if not self.closed_candles_only:
            raise ValueError("Closed candles are required.")
        if self.max_gold_positions != 1:
            raise ValueError("One Gold position maximum is required.")
        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("Aggregate risk must be 50 bps.")
        if self.stage_risk_bps != (25, 25):
            raise ValueError("Stage risk must be 25+25 bps.")
        if (self.verified_capability_count, self.blocked_capability_count) != (
            14,
            3,
        ):
            raise ValueError("Capability evidence is inconsistent.")
        if self.verified_event_count != 14:
            raise ValueError("Fourteen events must remain verified.")
        required = (
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.permits_contract_planning,
            self.permits_adapter_planning,
            self.permits_snapshot_schema_planning,
            self.requires_explicit_human_authorization,
            self.requires_separate_real_preflight_runtime_gate,
            self.requires_separate_production_gate,
            self.phase12_foundation_ready,
        )
        if not all(required):
            raise ValueError("A required safety invariant was lost.")
        forbidden = (
            self.permits_real_mt5_import,
            self.permits_mt5_initialization,
            self.permits_terminal_connection,
            self.permits_broker_requests,
            self.permits_real_account_reads,
            self.permits_order_check,
            self.permits_order_send,
            self.permits_external_writes,
            self.permits_production_activation,
            self.permits_live_order_submission,
        )
        if any(forbidden):
            raise ValueError("Planning admission cannot enable effects.")

    @property
    def permit_digest(self) -> str:
        source_id = str(getattr(self.phase11_handoff_bundle, "handoff_id", ""))
        material = "|".join(
            (
                PHASE_12_REAL_PREFLIGHT_SCHEMA_VERSION,
                source_id,
                str(self.source_phase_number),
                str(self.target_phase_number),
                self.source_phase_status,
                self.source_handoff_status,
                self.source_readiness_mode,
                self.source_readiness_audit_status,
                self.admission_mode,
                self.admission_status,
                self.real_preflight_execution_status,
                self.mt5_initialization_status,
                self.terminal_connection_status,
                self.broker_access_status,
                self.production_activation_status,
                self.live_execution_status,
                self.allowed_symbol,
                ",".join(self.allowed_timeframes),
                str(self.closed_candles_only),
                str(self.max_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(v) for v in self.stage_risk_bps),
                str(self.verified_capability_count),
                str(self.blocked_capability_count),
                str(self.verified_event_count),
                str(self.phase12_foundation_ready),
            )
        )
        return hashlib.sha256(material.encode()).hexdigest()

    @property
    def permit_id(self) -> str:
        return f"GOLDXBOT_PHASE_12_REAL_PREFLIGHT_PLANNING_ADMISSION:SHA256[{self.permit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase12RealPreflightPlanningAdmissionDecision:
    is_allowed: bool
    permit: Phase12RealPreflightPlanningAdmissionPermit | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed and (self.permit is None or self.blockers):
            raise ValueError("Allowed decision is inconsistent.")
        if not self.is_allowed and (self.permit is not None or not self.blockers):
            raise ValueError("Blocked decision is inconsistent.")

    @property
    def permit_required(self) -> Phase12RealPreflightPlanningAdmissionPermit:
        if self.permit is None:
            raise RuntimeError("Phase 12 real-preflight planning admission is blocked.")
        return self.permit


class StrategyPhase12RealPreflightPlanningAdmissionGate:
    def evaluate(
        self,
        phase11_handoff_decision: object,
    ) -> Phase12RealPreflightPlanningAdmissionDecision:
        if phase11_handoff_decision is None:
            return Phase12RealPreflightPlanningAdmissionDecision(
                False,
                None,
                ("phase11_handoff_decision_missing",),
            )
        if getattr(phase11_handoff_decision, "is_allowed", True) is not True:
            return Phase12RealPreflightPlanningAdmissionDecision(
                False,
                None,
                ("phase11_handoff_decision_blocked",),
            )
        try:
            bundle = _required(
                phase11_handoff_decision,
                "bundle_required",
            )
            valid = (
                _required(bundle, "phase_number") == 11
                and _required(bundle, "phase_status") == "PHASE_11_COMPLETE"
                and _required(bundle, "handoff_status") == "READY_FOR_PHASE_12"
                and _required(bundle, "readiness_mode") == "DETERMINISTIC_FAKE_READ_ONLY"
                and _required(bundle, "readiness_audit_status") == "PASSED"
                and _required(bundle, "real_preflight_execution_status") == "BLOCKED"
                and _required(bundle, "production_activation_status") == "BLOCKED"
                and _required(bundle, "live_execution_status") == "BLOCKED"
                and _required(bundle, "symbol") == "XAUUSD"
                and _required(bundle, "timeframes") == ("H4", "H1", "M15", "M5")
                and _required(bundle, "closed_candles_only") is True
                and _required(bundle, "stage_risk_bps") == (25, 25)
                and _required(bundle, "aggregate_risk_budget_bps") == 50
                and _required(bundle, "max_gold_positions") == 1
                and _required(bundle, "verified_capability_count") == 14
                and _required(bundle, "blocked_capability_count") == 3
                and _required(bundle, "event_count") == 14
                and _required(bundle, "risk_contract_valid") is True
                and _required(bundle, "oco_and_stop_loss_contract_valid") is True
                and _required(bundle, "terminal_flat_state_valid") is True
                and _required(bundle, "phase_complete") is True
                and _required(bundle, "ready_for_phase_12") is True
                and _required(bundle, "no_real_or_external_effects") is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase12RealPreflightPlanningAdmissionDecision(
                False,
                None,
                (f"phase11_handoff_invalid:{type(error).__name__}",),
            )
        if not valid:
            return Phase12RealPreflightPlanningAdmissionDecision(
                False,
                None,
                ("phase11_handoff_contract_invalid",),
            )
        permit = Phase12RealPreflightPlanningAdmissionPermit(
            phase11_handoff_decision=phase11_handoff_decision,
            phase11_handoff_bundle=bundle,
            source_phase_number=11,
            target_phase_number=12,
            source_phase_status="PHASE_11_COMPLETE",
            source_handoff_status="READY_FOR_PHASE_12",
            source_readiness_mode="DETERMINISTIC_FAKE_READ_ONLY",
            source_readiness_audit_status="PASSED",
            admission_mode=PHASE_12_REAL_PREFLIGHT_ADMISSION_MODE,
            admission_status=PHASE_12_REAL_PREFLIGHT_ADMISSION_STATUS,
            real_preflight_execution_status="BLOCKED",
            mt5_initialization_status="BLOCKED",
            terminal_connection_status="BLOCKED",
            broker_access_status="BLOCKED",
            production_activation_status="BLOCKED",
            live_execution_status="BLOCKED",
            allowed_symbol="XAUUSD",
            allowed_timeframes=("H4", "H1", "M15", "M5"),
            closed_candles_only=True,
            max_gold_positions=1,
            aggregate_risk_budget_bps=50,
            stage_risk_bps=(25, 25),
            oco_required=True,
            broker_stop_loss_required=True,
            guards_required=True,
            terminal_flat_state_required=True,
            martingale_prohibited=True,
            grid_prohibited=True,
            no_stop_loss_prohibited=True,
            verified_capability_count=14,
            blocked_capability_count=3,
            verified_event_count=14,
            permits_contract_planning=True,
            permits_adapter_planning=True,
            permits_snapshot_schema_planning=True,
            permits_real_mt5_import=False,
            permits_mt5_initialization=False,
            permits_terminal_connection=False,
            permits_broker_requests=False,
            permits_real_account_reads=False,
            permits_order_check=False,
            permits_order_send=False,
            permits_external_writes=False,
            permits_production_activation=False,
            permits_live_order_submission=False,
            requires_explicit_human_authorization=True,
            requires_separate_real_preflight_runtime_gate=True,
            requires_separate_production_gate=True,
            phase12_foundation_ready=True,
        )
        return Phase12RealPreflightPlanningAdmissionDecision(
            True,
            permit,
            (),
        )


def evaluate_phase12_real_preflight_planning_admission(
    phase11_handoff_decision: object,
) -> Phase12RealPreflightPlanningAdmissionDecision:
    return StrategyPhase12RealPreflightPlanningAdmissionGate().evaluate(phase11_handoff_decision)


__all__ = (
    "PHASE_12_REAL_PREFLIGHT_SCHEMA_VERSION",
    "PHASE_12_REAL_PREFLIGHT_ADMISSION_MODE",
    "PHASE_12_REAL_PREFLIGHT_ADMISSION_STATUS",
    "PHASE_12_REAL_PREFLIGHT_EXECUTION_STATUS",
    "PHASE_12_MT5_INITIALIZATION_STATUS",
    "PHASE_12_TERMINAL_CONNECTION_STATUS",
    "PHASE_12_BROKER_ACCESS_STATUS",
    "PHASE_12_PRODUCTION_ACTIVATION_STATUS",
    "PHASE_12_LIVE_EXECUTION_STATUS",
    "PHASE_12_ALLOWED_SYMBOL",
    "PHASE_12_ALLOWED_TIMEFRAMES",
    "PHASE_12_MAX_GOLD_POSITIONS",
    "PHASE_12_AGGREGATE_RISK_BUDGET_BPS",
    "PHASE_12_STAGE_RISK_BPS",
    "Phase12RealPreflightPlanningAdmissionPermit",
    "Phase12RealPreflightPlanningAdmissionDecision",
    "StrategyPhase12RealPreflightPlanningAdmissionGate",
    "evaluate_phase12_real_preflight_planning_admission",
)
