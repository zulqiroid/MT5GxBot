"""Phase 14 fail-closed roadmap-extension planning admission."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

SCHEMA_VERSION = "1.0"
ADMISSION_MODE = "CONTROLLED_ROADMAP_EXTENSION_PLANNING_ONLY"
ADMISSION_STATUS = "ADMITTED"
ADMISSION_SOURCE = "PHASE_13_DEFINED_ROADMAP_COMPLETION"
BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class Phase14RoadmapExtensionPermit:
    source_decision: object = field(repr=False)
    source_bundle: object = field(repr=False)

    schema_version: str
    source_phase: int
    target_phase: int
    admission_mode: str
    admission_status: str
    admission_source: str

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    runtime_operations: int
    blocked_write_operations: int
    error_mappings: int
    snapshot_mappings: int
    snapshot_fields: int
    validation_events: int
    safety_findings: int

    requirements_planning_allowed: bool
    architecture_planning_allowed: bool
    test_blueprint_planning_allowed: bool
    safety_gate_planning_allowed: bool
    phase14_planning_admitted: bool
    phase14_execution_admitted: bool

    oco_required: bool
    broker_sl_required: bool
    guards_required: bool
    flat_state_required: bool
    martingale_prohibited: bool
    grid_prohibited: bool
    no_sl_prohibited: bool

    human_authorization_required: bool
    runtime_gate_required: bool
    account_read_gate_required: bool
    production_gate_required: bool

    real_preflight_status: str
    mt5_import_status: str
    mt5_initialization_status: str
    terminal_status: str
    broker_status: str
    account_read_status: str
    production_status: str
    live_status: str

    phase14_foundation_ready: bool

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid schema version")
        if (self.source_phase, self.target_phase) != (13, 14):
            raise ValueError("invalid phase transition")
        if self.admission_mode != ADMISSION_MODE:
            raise ValueError("invalid admission mode")
        if self.admission_status != ADMISSION_STATUS:
            raise ValueError("invalid admission status")
        if self.admission_source != ADMISSION_SOURCE:
            raise ValueError("invalid admission source")
        if self.symbol != "XAUUSD":
            raise ValueError("XAUUSD only")
        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("invalid timeframes")
        if not self.closed_candles_only:
            raise ValueError("closed candles required")
        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum")
        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps")
        if self.stage_risk_bps != (25, 25):
            raise ValueError("staged risk must be 25+25")
        if (
            self.runtime_operations,
            self.blocked_write_operations,
            self.error_mappings,
            self.snapshot_mappings,
            self.snapshot_fields,
            self.validation_events,
            self.safety_findings,
        ) != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence counts are inconsistent")

        required = (
            self.requirements_planning_allowed,
            self.architecture_planning_allowed,
            self.test_blueprint_planning_allowed,
            self.safety_gate_planning_allowed,
            self.phase14_planning_admitted,
            self.oco_required,
            self.broker_sl_required,
            self.guards_required,
            self.flat_state_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_sl_prohibited,
            self.human_authorization_required,
            self.runtime_gate_required,
            self.account_read_gate_required,
            self.production_gate_required,
            self.phase14_foundation_ready,
        )
        if not all(required):
            raise ValueError("required invariant missing")
        if self.phase14_execution_admitted:
            raise ValueError("Phase 14 execution is not admitted")

        statuses = (
            self.real_preflight_status,
            self.mt5_import_status,
            self.mt5_initialization_status,
            self.terminal_status,
            self.broker_status,
            self.account_read_status,
            self.production_status,
            self.live_status,
        )
        if any(status != BLOCKED for status in statuses):
            raise ValueError("all real runtime statuses must be blocked")

    @property
    def permit_digest(self) -> str:
        source_id = str(getattr(self.source_bundle, "handoff_id", ""))
        material = "|".join(
            (
                self.schema_version,
                source_id,
                str(self.source_phase),
                str(self.target_phase),
                self.admission_mode,
                self.admission_status,
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.phase14_planning_admitted),
                str(self.phase14_execution_admitted),
            )
        )
        return hashlib.sha256(material.encode()).hexdigest()

    @property
    def permit_id(self) -> str:
        return f"GOLDXBOT_PHASE_14_EXTENSION:SHA256[{self.permit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase14RoadmapExtensionDecision:
    is_allowed: bool
    permit: Phase14RoadmapExtensionPermit | None
    blockers: tuple[str, ...]

    @property
    def permit_required(self) -> Phase14RoadmapExtensionPermit:
        if self.permit is None:
            raise RuntimeError("Phase 14 roadmap-extension admission is blocked.")
        return self.permit


class Phase14RoadmapExtensionAdmissionGate:
    def evaluate(self, source_decision: object) -> Phase14RoadmapExtensionDecision:
        if source_decision is None:
            return Phase14RoadmapExtensionDecision(
                False, None, ("phase13_handoff_decision_missing",)
            )
        if getattr(source_decision, "is_allowed", True) is not True:
            return Phase14RoadmapExtensionDecision(
                False, None, ("phase13_handoff_decision_blocked",)
            )

        try:
            bundle = source_decision.bundle_required
            valid = (
                bundle.phase_number == 13
                and bundle.phase_status == "PHASE_13_COMPLETE"
                and bundle.handoff_status == "DEFINED_ROADMAP_COMPLETE"
                and bundle.next_phase_number is None
                and bundle.phase14_admitted is False
                and bundle.phase_complete is True
                and bundle.defined_roadmap_complete is True
                and bundle.no_real_or_external_effects is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase14RoadmapExtensionDecision(
                False, None, (f"phase13_handoff_invalid:{type(error).__name__}",)
            )

        if not valid:
            return Phase14RoadmapExtensionDecision(
                False, None, ("phase13_handoff_contract_invalid",)
            )

        permit = Phase14RoadmapExtensionPermit(
            source_decision=source_decision,
            source_bundle=bundle,
            schema_version=SCHEMA_VERSION,
            source_phase=13,
            target_phase=14,
            admission_mode=ADMISSION_MODE,
            admission_status=ADMISSION_STATUS,
            admission_source=ADMISSION_SOURCE,
            symbol=bundle.symbol,
            timeframes=bundle.timeframes,
            closed_candles_only=bundle.closed_candles_only,
            max_gold_positions=bundle.max_gold_positions,
            aggregate_risk_budget_bps=bundle.aggregate_risk_budget_bps,
            stage_risk_bps=bundle.stage_risk_bps,
            runtime_operations=bundle.runtime_operation_count,
            blocked_write_operations=bundle.blocked_write_operation_count,
            error_mappings=bundle.error_mapping_count,
            snapshot_mappings=bundle.snapshot_mapping_count,
            snapshot_fields=bundle.total_snapshot_field_count,
            validation_events=bundle.validation_event_count,
            safety_findings=bundle.runtime_safety_finding_count,
            requirements_planning_allowed=True,
            architecture_planning_allowed=True,
            test_blueprint_planning_allowed=True,
            safety_gate_planning_allowed=True,
            phase14_planning_admitted=True,
            phase14_execution_admitted=False,
            oco_required=True,
            broker_sl_required=True,
            guards_required=True,
            flat_state_required=True,
            martingale_prohibited=True,
            grid_prohibited=True,
            no_sl_prohibited=True,
            human_authorization_required=True,
            runtime_gate_required=True,
            account_read_gate_required=True,
            production_gate_required=True,
            real_preflight_status=BLOCKED,
            mt5_import_status=BLOCKED,
            mt5_initialization_status=BLOCKED,
            terminal_status=BLOCKED,
            broker_status=BLOCKED,
            account_read_status=BLOCKED,
            production_status=BLOCKED,
            live_status=BLOCKED,
            phase14_foundation_ready=True,
        )
        return Phase14RoadmapExtensionDecision(True, permit, ())


def evaluate_phase14_roadmap_extension(
    source_decision: object,
) -> Phase14RoadmapExtensionDecision:
    return Phase14RoadmapExtensionAdmissionGate().evaluate(source_decision)


__all__ = (
    "SCHEMA_VERSION",
    "ADMISSION_MODE",
    "ADMISSION_STATUS",
    "ADMISSION_SOURCE",
    "BLOCKED",
    "Phase14RoadmapExtensionPermit",
    "Phase14RoadmapExtensionDecision",
    "Phase14RoadmapExtensionAdmissionGate",
    "evaluate_phase14_roadmap_extension",
)
