"""Phase 14 immutable architecture blueprint.

Consumes Step 14.1 admission and defines planning-only architecture for a
future human-authorized, read-only preflight observability boundary.
No real MT5, broker, account, order, production, or live effect is allowed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_14_BLUEPRINT_SCHEMA_VERSION = "1.0"
PHASE_14_BLUEPRINT_STATUS = "BLUEPRINT_READY"
PHASE_14_BLUEPRINT_MODE = "HUMAN_AUTHORIZED_READ_ONLY_PREFLIGHT_OBSERVABILITY_PLANNING_ONLY"
PHASE_14_BLUEPRINT_SOURCE = "PHASE_14_EXTENSION_ADMISSION_ONLY"

PHASE_14_BLUEPRINT_COMPONENTS = (
    "AUTHORIZATION_RECORD",
    "RUNTIME_LIFECYCLE_BOUNDARY",
    "TERMINAL_SNAPSHOT",
    "ACCOUNT_SNAPSHOT",
    "SYMBOL_MARKET_SNAPSHOT",
    "EXPOSURE_ORDER_SNAPSHOT",
    "FAIL_CLOSED_ERROR_ROUTING",
    "AUDIT_EVIDENCE_HANDOFF",
)

PHASE_14_BLUEPRINT_REQUIREMENTS = (
    "PHASE_13_LINEAGE",
    "PHASE_14_ADMISSION",
    "EXPLICIT_HUMAN_AUTHORIZATION",
    "SEPARATE_RUNTIME_EXECUTION_GATE",
    "SEPARATE_REAL_ACCOUNT_READ_GATE",
    "SEPARATE_PRODUCTION_GATE",
    "XAUUSD_ONLY",
    "CLOSED_CANDLES_ONLY",
    "ONE_GOLD_POSITION_MAXIMUM",
    "FIFTY_BPS_AGGREGATE_RISK",
    "OCO_BROKER_SL_AND_GUARDS",
    "NO_REAL_OR_EXTERNAL_EFFECTS",
)


@dataclass(frozen=True, slots=True)
class Phase14ExtensionArchitectureBlueprint:
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase13_handoff_bundle: object = field(repr=False)

    schema_version: str
    blueprint_status: str
    blueprint_mode: str
    blueprint_source: str
    components: tuple[str, ...]
    requirements: tuple[str, ...]

    runtime_operations: int
    blocked_write_operations: int
    error_mappings: int
    snapshot_mappings: int
    snapshot_fields: int
    validation_events: int
    safety_findings: int

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

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

    fake_validation_allowed: bool
    safety_audit_allowed: bool
    real_execution_allowed: bool
    real_account_read_allowed: bool
    external_write_allowed: bool
    production_allowed: bool
    live_execution_allowed: bool

    real_preflight_status: str
    mt5_import_status: str
    mt5_initialization_status: str
    terminal_status: str
    broker_status: str
    account_read_status: str
    production_status: str
    live_status: str

    ready_for_fake_validation: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_14_BLUEPRINT_SCHEMA_VERSION:
            raise ValueError("invalid blueprint schema")
        if self.blueprint_status != PHASE_14_BLUEPRINT_STATUS:
            raise ValueError("invalid blueprint status")
        if self.blueprint_mode != PHASE_14_BLUEPRINT_MODE:
            raise ValueError("invalid blueprint mode")
        if self.blueprint_source != PHASE_14_BLUEPRINT_SOURCE:
            raise ValueError("invalid blueprint source")
        if self.components != PHASE_14_BLUEPRINT_COMPONENTS:
            raise ValueError("invalid component plan")
        if self.requirements != PHASE_14_BLUEPRINT_REQUIREMENTS:
            raise ValueError("invalid requirement plan")
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
            raise ValueError("staged risk must be 25+25 bps")

        required = (
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
            self.fake_validation_allowed,
            self.safety_audit_allowed,
            self.ready_for_fake_validation,
        )
        if not all(required):
            raise ValueError("required blueprint invariant missing")

        forbidden = (
            self.real_execution_allowed,
            self.real_account_read_allowed,
            self.external_write_allowed,
            self.production_allowed,
            self.live_execution_allowed,
        )
        if any(forbidden):
            raise ValueError("blueprint cannot enable real effects")

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
        if statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must be blocked")

    @property
    def blueprint_digest(self) -> str:
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        handoff_id = str(getattr(self.phase13_handoff_bundle, "handoff_id", ""))
        material = "|".join(
            (
                self.schema_version,
                permit_id,
                handoff_id,
                self.blueprint_status,
                self.blueprint_mode,
                ",".join(self.components),
                ",".join(self.requirements),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.ready_for_fake_validation),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def blueprint_id(self) -> str:
        return f"GOLDXBOT_PHASE_14_BLUEPRINT:SHA256[{self.blueprint_digest}]"


@dataclass(frozen=True, slots=True)
class Phase14ExtensionArchitectureDecision:
    is_allowed: bool
    blueprint: Phase14ExtensionArchitectureBlueprint | None
    blockers: tuple[str, ...]

    @property
    def blueprint_required(self) -> Phase14ExtensionArchitectureBlueprint:
        if self.blueprint is None:
            raise RuntimeError("Phase 14 architecture blueprint is blocked.")
        return self.blueprint


class Phase14ExtensionArchitectureFactory:
    def create(
        self,
        admission_decision: object,
    ) -> Phase14ExtensionArchitectureDecision:
        if admission_decision is None:
            return Phase14ExtensionArchitectureDecision(
                False, None, ("phase14_admission_decision_missing",)
            )
        if getattr(admission_decision, "is_allowed", True) is not True:
            return Phase14ExtensionArchitectureDecision(
                False, None, ("phase14_admission_decision_blocked",)
            )

        try:
            permit = admission_decision.permit_required
            valid = (
                permit.source_phase == 13
                and permit.target_phase == 14
                and permit.admission_mode == "CONTROLLED_ROADMAP_EXTENSION_PLANNING_ONLY"
                and permit.phase14_planning_admitted is True
                and permit.phase14_execution_admitted is False
                and permit.phase14_foundation_ready is True
                and permit.symbol == "XAUUSD"
                and permit.aggregate_risk_budget_bps == 50
                and permit.stage_risk_bps == (25, 25)
                and permit.live_status == "BLOCKED"
            )
            source_bundle = permit.source_bundle
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase14ExtensionArchitectureDecision(
                False,
                None,
                (f"phase14_admission_invalid:{type(error).__name__}",),
            )

        if not valid:
            return Phase14ExtensionArchitectureDecision(
                False, None, ("phase14_admission_contract_invalid",)
            )

        blueprint = Phase14ExtensionArchitectureBlueprint(
            admission_decision=admission_decision,
            admission_permit=permit,
            phase13_handoff_bundle=source_bundle,
            schema_version=PHASE_14_BLUEPRINT_SCHEMA_VERSION,
            blueprint_status=PHASE_14_BLUEPRINT_STATUS,
            blueprint_mode=PHASE_14_BLUEPRINT_MODE,
            blueprint_source=PHASE_14_BLUEPRINT_SOURCE,
            components=PHASE_14_BLUEPRINT_COMPONENTS,
            requirements=PHASE_14_BLUEPRINT_REQUIREMENTS,
            runtime_operations=permit.runtime_operations,
            blocked_write_operations=permit.blocked_write_operations,
            error_mappings=permit.error_mappings,
            snapshot_mappings=permit.snapshot_mappings,
            snapshot_fields=permit.snapshot_fields,
            validation_events=permit.validation_events,
            safety_findings=permit.safety_findings,
            symbol=permit.symbol,
            timeframes=permit.timeframes,
            closed_candles_only=permit.closed_candles_only,
            max_gold_positions=permit.max_gold_positions,
            aggregate_risk_budget_bps=permit.aggregate_risk_budget_bps,
            stage_risk_bps=permit.stage_risk_bps,
            oco_required=permit.oco_required,
            broker_sl_required=permit.broker_sl_required,
            guards_required=permit.guards_required,
            flat_state_required=permit.flat_state_required,
            martingale_prohibited=permit.martingale_prohibited,
            grid_prohibited=permit.grid_prohibited,
            no_sl_prohibited=permit.no_sl_prohibited,
            human_authorization_required=permit.human_authorization_required,
            runtime_gate_required=permit.runtime_gate_required,
            account_read_gate_required=permit.account_read_gate_required,
            production_gate_required=permit.production_gate_required,
            fake_validation_allowed=True,
            safety_audit_allowed=True,
            real_execution_allowed=False,
            real_account_read_allowed=False,
            external_write_allowed=False,
            production_allowed=False,
            live_execution_allowed=False,
            real_preflight_status="BLOCKED",
            mt5_import_status="BLOCKED",
            mt5_initialization_status="BLOCKED",
            terminal_status="BLOCKED",
            broker_status="BLOCKED",
            account_read_status="BLOCKED",
            production_status="BLOCKED",
            live_status="BLOCKED",
            ready_for_fake_validation=True,
        )
        return Phase14ExtensionArchitectureDecision(True, blueprint, ())


def create_phase14_extension_architecture(
    admission_decision: object,
) -> Phase14ExtensionArchitectureDecision:
    return Phase14ExtensionArchitectureFactory().create(admission_decision)


__all__ = (
    "PHASE_14_BLUEPRINT_SCHEMA_VERSION",
    "PHASE_14_BLUEPRINT_STATUS",
    "PHASE_14_BLUEPRINT_MODE",
    "PHASE_14_BLUEPRINT_SOURCE",
    "PHASE_14_BLUEPRINT_COMPONENTS",
    "PHASE_14_BLUEPRINT_REQUIREMENTS",
    "Phase14ExtensionArchitectureBlueprint",
    "Phase14ExtensionArchitectureDecision",
    "Phase14ExtensionArchitectureFactory",
    "create_phase14_extension_architecture",
)
