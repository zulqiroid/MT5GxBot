"""Fail-closed Phase 13 controlled read-only runtime admission gate.

This module consumes the completed Phase 12 handoff and creates one
immutable permit for controlled read-only runtime boundary planning only.

It does not authorize importing or initializing real MetaTrader 5,
connecting to a terminal, contacting a broker, reading a real account,
running order_check, sending an order, writing external state, activating
production, or submitting a live order. Explicit human authorization and
separate runtime, account-read, and production gates remain mandatory.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_13_RUNTIME_ADMISSION_SCHEMA_VERSION = "1.0"
PHASE_13_RUNTIME_ADMISSION_MODE = "CONTROLLED_READ_ONLY_RUNTIME_BOUNDARY_PLANNING_ONLY"
PHASE_13_RUNTIME_ADMISSION_STATUS = "ADMITTED"
PHASE_13_REAL_PREFLIGHT_EXECUTION_STATUS = "BLOCKED"
PHASE_13_MT5_IMPORT_STATUS = "BLOCKED"
PHASE_13_MT5_INITIALIZATION_STATUS = "BLOCKED"
PHASE_13_TERMINAL_CONNECTION_STATUS = "BLOCKED"
PHASE_13_BROKER_ACCESS_STATUS = "BLOCKED"
PHASE_13_REAL_ACCOUNT_READ_STATUS = "BLOCKED"
PHASE_13_PRODUCTION_ACTIVATION_STATUS = "BLOCKED"
PHASE_13_LIVE_EXECUTION_STATUS = "BLOCKED"


def _required(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase13ControlledReadOnlyRuntimeAdmissionPermit:
    """Immutable permit for Phase 13 runtime-boundary planning only."""

    phase12_handoff_decision: object
    phase12_handoff_bundle: object

    schema_version: str
    source_phase_number: int
    target_phase_number: int
    source_phase_status: str
    source_handoff_status: str
    source_contract_mode: str
    source_evidence: str

    admission_mode: str
    admission_status: str

    symbol: str
    timeframes: tuple[str, ...]
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
    snapshot_schema_count: int
    total_snapshot_field_count: int
    validation_event_count: int
    readiness_finding_count: int

    permits_runtime_boundary_planning: bool
    permits_adapter_interface_planning: bool
    permits_read_only_snapshot_mapping_planning: bool
    permits_fail_closed_error_mapping_planning: bool

    permits_real_preflight_execution: bool
    permits_real_mt5_import: bool
    permits_mt5_initialization: bool
    permits_terminal_connection: bool
    permits_broker_access: bool
    permits_real_account_reads: bool
    permits_order_check: bool
    permits_order_send: bool
    permits_external_writes: bool
    permits_production_activation: bool
    permits_live_order_submission: bool

    requires_explicit_human_authorization: bool
    requires_separate_runtime_execution_gate: bool
    requires_separate_real_account_read_gate: bool
    requires_separate_production_gate: bool

    real_preflight_execution_status: str
    mt5_import_status: str
    mt5_initialization_status: str
    terminal_connection_status: str
    broker_access_status: str
    real_account_read_status: str
    production_activation_status: str
    live_execution_status: str

    phase13_foundation_ready: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_13_RUNTIME_ADMISSION_SCHEMA_VERSION:
            raise ValueError("Phase 13 admission schema is inconsistent.")

        if (self.source_phase_number, self.target_phase_number) != (12, 13):
            raise ValueError("Phase transition must be 12 to 13.")

        if self.source_phase_status != "PHASE_12_COMPLETE":
            raise ValueError("Phase 12 must be complete.")

        if self.source_handoff_status != "READY_FOR_PHASE_13":
            raise ValueError("Phase 12 handoff is not ready for Phase 13.")

        if self.source_contract_mode != "REAL_PREFLIGHT_CONTRACT_ONLY":
            raise ValueError("Phase 12 contract mode is inconsistent.")

        if self.source_evidence != "DETERMINISTIC_FAKE_EVIDENCE_ONLY":
            raise ValueError("Phase 12 evidence source is inconsistent.")

        if self.admission_mode != PHASE_13_RUNTIME_ADMISSION_MODE:
            raise ValueError("Phase 13 admission mode is inconsistent.")

        if self.admission_status != PHASE_13_RUNTIME_ADMISSION_STATUS:
            raise ValueError("Phase 13 admission status must be ADMITTED.")

        if self.symbol != "XAUUSD":
            raise ValueError("Phase 13 admission is XAUUSD only.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 13 timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("Closed candles are required.")

        if self.max_gold_positions != 1:
            raise ValueError("One Gold position maximum is required.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("Aggregate risk must be 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("Staged risk must be 25+25 bps.")

        if (
            self.verified_capability_count,
            self.blocked_capability_count,
        ) != (14, 3):
            raise ValueError("Capability evidence is inconsistent.")

        if (
            self.snapshot_schema_count,
            self.total_snapshot_field_count,
        ) != (5, 32):
            raise ValueError("Snapshot evidence is inconsistent.")

        if (
            self.validation_event_count,
            self.readiness_finding_count,
        ) != (14, 14):
            raise ValueError("Validation evidence is inconsistent.")

        required = (
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.permits_runtime_boundary_planning,
            self.permits_adapter_interface_planning,
            self.permits_read_only_snapshot_mapping_planning,
            self.permits_fail_closed_error_mapping_planning,
            self.requires_explicit_human_authorization,
            self.requires_separate_runtime_execution_gate,
            self.requires_separate_real_account_read_gate,
            self.requires_separate_production_gate,
            self.phase13_foundation_ready,
        )
        if not all(required):
            raise ValueError("Phase 13 admission lost a required invariant.")

        forbidden = (
            self.permits_real_preflight_execution,
            self.permits_real_mt5_import,
            self.permits_mt5_initialization,
            self.permits_terminal_connection,
            self.permits_broker_access,
            self.permits_real_account_reads,
            self.permits_order_check,
            self.permits_order_send,
            self.permits_external_writes,
            self.permits_production_activation,
            self.permits_live_order_submission,
        )
        if any(forbidden):
            raise ValueError("Phase 13 planning cannot enable real effects.")

        statuses = (
            self.real_preflight_execution_status,
            self.mt5_import_status,
            self.mt5_initialization_status,
            self.terminal_connection_status,
            self.broker_access_status,
            self.real_account_read_status,
            self.production_activation_status,
            self.live_execution_status,
        )
        if any(status != "BLOCKED" for status in statuses):
            raise ValueError("All Phase 13 runtime statuses must be BLOCKED.")

    @property
    def permit_digest(self) -> str:
        handoff_id = str(getattr(self.phase12_handoff_bundle, "handoff_id", ""))
        material = "|".join(
            (
                self.schema_version,
                handoff_id,
                str(self.source_phase_number),
                str(self.target_phase_number),
                self.source_phase_status,
                self.source_handoff_status,
                self.source_contract_mode,
                self.source_evidence,
                self.admission_mode,
                self.admission_status,
                self.symbol,
                ",".join(self.timeframes),
                str(self.max_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.verified_capability_count),
                str(self.blocked_capability_count),
                str(self.snapshot_schema_count),
                str(self.total_snapshot_field_count),
                str(self.validation_event_count),
                str(self.readiness_finding_count),
                self.real_preflight_execution_status,
                self.mt5_import_status,
                self.mt5_initialization_status,
                self.terminal_connection_status,
                self.broker_access_status,
                self.real_account_read_status,
                self.production_activation_status,
                self.live_execution_status,
                str(self.phase13_foundation_ready),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def permit_id(self) -> str:
        return (
            f"GOLDXBOT_PHASE_13_CONTROLLED_READ_ONLY_RUNTIME_ADMISSION:SHA256[{self.permit_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase13ControlledReadOnlyRuntimeAdmissionDecision:
    """Allowed or blocked Phase 13 admission decision."""

    is_allowed: bool
    permit: Phase13ControlledReadOnlyRuntimeAdmissionPermit | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.permit is None or self.blockers:
                raise ValueError("Allowed admission decision is inconsistent.")
        elif self.permit is not None or not self.blockers:
            raise ValueError("Blocked admission decision is inconsistent.")

    @property
    def permit_required(self) -> Phase13ControlledReadOnlyRuntimeAdmissionPermit:
        if self.permit is None:
            raise RuntimeError("Phase 13 controlled read-only runtime admission is blocked.")
        return self.permit


class StrategyPhase13ControlledReadOnlyRuntimeAdmissionGate:
    """Admits only fail-closed Phase 13 runtime-boundary planning."""

    def evaluate(
        self,
        phase12_handoff_decision: object,
    ) -> Phase13ControlledReadOnlyRuntimeAdmissionDecision:
        if phase12_handoff_decision is None:
            return Phase13ControlledReadOnlyRuntimeAdmissionDecision(
                False,
                None,
                ("phase12_handoff_decision_missing",),
            )

        if getattr(phase12_handoff_decision, "is_allowed", True) is not True:
            return Phase13ControlledReadOnlyRuntimeAdmissionDecision(
                False,
                None,
                ("phase12_handoff_decision_blocked",),
            )

        try:
            bundle = _required(
                phase12_handoff_decision,
                "bundle_required",
            )
            source_valid = (
                _required(bundle, "phase_number") == 12
                and _required(bundle, "phase_status") == "PHASE_12_COMPLETE"
                and _required(bundle, "handoff_status") == "READY_FOR_PHASE_13"
                and _required(bundle, "contract_mode") == "REAL_PREFLIGHT_CONTRACT_ONLY"
                and _required(bundle, "evidence_source") == "DETERMINISTIC_FAKE_EVIDENCE_ONLY"
                and _required(bundle, "readiness_audit_status") == "PASSED"
                and _required(bundle, "validation_status") == "PASSED"
                and _required(bundle, "symbol") == "XAUUSD"
                and _required(bundle, "timeframes") == ("H4", "H1", "M15", "M5")
                and _required(bundle, "closed_candles_only") is True
                and _required(bundle, "max_gold_positions") == 1
                and _required(bundle, "aggregate_risk_budget_bps") == 50
                and _required(bundle, "stage_risk_bps") == (25, 25)
                and _required(bundle, "verified_capability_count") == 14
                and _required(bundle, "blocked_capability_count") == 3
                and _required(bundle, "snapshot_schema_count") == 5
                and _required(bundle, "total_snapshot_field_count") == 32
                and _required(bundle, "validation_event_count") == 14
                and _required(bundle, "readiness_finding_count") == 14
                and _required(bundle, "no_real_or_external_effects") is True
                and _required(bundle, "phase_complete") is True
                and _required(bundle, "ready_for_phase_13") is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase13ControlledReadOnlyRuntimeAdmissionDecision(
                False,
                None,
                (f"phase12_handoff_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase13ControlledReadOnlyRuntimeAdmissionDecision(
                False,
                None,
                ("phase12_handoff_contract_invalid",),
            )

        permit = Phase13ControlledReadOnlyRuntimeAdmissionPermit(
            phase12_handoff_decision=phase12_handoff_decision,
            phase12_handoff_bundle=bundle,
            schema_version=PHASE_13_RUNTIME_ADMISSION_SCHEMA_VERSION,
            source_phase_number=12,
            target_phase_number=13,
            source_phase_status="PHASE_12_COMPLETE",
            source_handoff_status="READY_FOR_PHASE_13",
            source_contract_mode="REAL_PREFLIGHT_CONTRACT_ONLY",
            source_evidence="DETERMINISTIC_FAKE_EVIDENCE_ONLY",
            admission_mode=PHASE_13_RUNTIME_ADMISSION_MODE,
            admission_status=PHASE_13_RUNTIME_ADMISSION_STATUS,
            symbol="XAUUSD",
            timeframes=("H4", "H1", "M15", "M5"),
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
            snapshot_schema_count=5,
            total_snapshot_field_count=32,
            validation_event_count=14,
            readiness_finding_count=14,
            permits_runtime_boundary_planning=True,
            permits_adapter_interface_planning=True,
            permits_read_only_snapshot_mapping_planning=True,
            permits_fail_closed_error_mapping_planning=True,
            permits_real_preflight_execution=False,
            permits_real_mt5_import=False,
            permits_mt5_initialization=False,
            permits_terminal_connection=False,
            permits_broker_access=False,
            permits_real_account_reads=False,
            permits_order_check=False,
            permits_order_send=False,
            permits_external_writes=False,
            permits_production_activation=False,
            permits_live_order_submission=False,
            requires_explicit_human_authorization=True,
            requires_separate_runtime_execution_gate=True,
            requires_separate_real_account_read_gate=True,
            requires_separate_production_gate=True,
            real_preflight_execution_status=(PHASE_13_REAL_PREFLIGHT_EXECUTION_STATUS),
            mt5_import_status=PHASE_13_MT5_IMPORT_STATUS,
            mt5_initialization_status=PHASE_13_MT5_INITIALIZATION_STATUS,
            terminal_connection_status=PHASE_13_TERMINAL_CONNECTION_STATUS,
            broker_access_status=PHASE_13_BROKER_ACCESS_STATUS,
            real_account_read_status=PHASE_13_REAL_ACCOUNT_READ_STATUS,
            production_activation_status=(PHASE_13_PRODUCTION_ACTIVATION_STATUS),
            live_execution_status=PHASE_13_LIVE_EXECUTION_STATUS,
            phase13_foundation_ready=True,
        )
        return Phase13ControlledReadOnlyRuntimeAdmissionDecision(
            True,
            permit,
            (),
        )


def evaluate_phase13_controlled_read_only_runtime_admission(
    phase12_handoff_decision: object,
) -> Phase13ControlledReadOnlyRuntimeAdmissionDecision:
    """Evaluate the fail-closed Phase 13 admission gate."""

    return StrategyPhase13ControlledReadOnlyRuntimeAdmissionGate().evaluate(
        phase12_handoff_decision
    )


__all__ = (
    "PHASE_13_RUNTIME_ADMISSION_SCHEMA_VERSION",
    "PHASE_13_RUNTIME_ADMISSION_MODE",
    "PHASE_13_RUNTIME_ADMISSION_STATUS",
    "PHASE_13_REAL_PREFLIGHT_EXECUTION_STATUS",
    "PHASE_13_MT5_IMPORT_STATUS",
    "PHASE_13_MT5_INITIALIZATION_STATUS",
    "PHASE_13_TERMINAL_CONNECTION_STATUS",
    "PHASE_13_BROKER_ACCESS_STATUS",
    "PHASE_13_REAL_ACCOUNT_READ_STATUS",
    "PHASE_13_PRODUCTION_ACTIVATION_STATUS",
    "PHASE_13_LIVE_EXECUTION_STATUS",
    "Phase13ControlledReadOnlyRuntimeAdmissionPermit",
    "Phase13ControlledReadOnlyRuntimeAdmissionDecision",
    "StrategyPhase13ControlledReadOnlyRuntimeAdmissionGate",
    "evaluate_phase13_controlled_read_only_runtime_admission",
)
