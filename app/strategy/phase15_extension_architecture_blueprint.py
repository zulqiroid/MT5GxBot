"""Phase 15 planning-only extension architecture blueprint.

Consumes the Step 15.1 planning admission permit. This module defines only a
future read-only observability architecture. It performs no real MT5 import,
terminal connection, broker access, account read, order operation, external
write, production activation, or live execution.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_15_BLUEPRINT_SCHEMA_VERSION = "1.0"
PHASE_15_BLUEPRINT_STATUS = "BLUEPRINT_READY"
PHASE_15_BLUEPRINT_MODE = "PLANNING_ONLY"
PHASE_15_BLUEPRINT_SOURCE = "PHASE_15_ADMISSION_PERMIT_ONLY"
PHASE_15_BLUEPRINT_NEXT_ALLOWED = "DETERMINISTIC_FAKE_VALIDATION"
PHASE_15_BLUEPRINT_COMPONENTS = (
    "HumanAuthorizationGate",
    "ReadOnlyPreflightOrchestrator",
    "TerminalDiscoveryBoundary",
    "BrokerCapabilitySnapshot",
    "GoldSymbolContractResolver",
    "ClosedCandleDataSnapshot",
    "RiskInvariantObserver",
    "SafetyTelemetryEnvelope",
)
PHASE_15_BLUEPRINT_REQUIREMENTS = (
    "explicit_human_authorization_required",
    "phase15_execution_not_admitted",
    "deterministic_in_memory_fakes_only",
    "xauusd_only",
    "closed_h4_h1_m15_m5_candles_only",
    "one_gold_position_maximum",
    "aggregate_risk_50_bps_as_25_plus_25",
    "oco_broker_sl_guards_and_flat_state_required",
    "martingale_grid_and_no_sl_prohibited",
    "real_terminal_broker_and_account_operations_blocked",
    "production_and_live_execution_blocked",
    "separate_safety_audit_required",
)


@dataclass(frozen=True, slots=True)
class Phase15ExtensionArchitectureBlueprint:
    """Immutable planning-only architecture blueprint."""

    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase14_final_handoff: object = field(repr=False)

    schema_version: str
    blueprint_status: str
    blueprint_mode: str
    blueprint_source: str
    next_allowed_step: str
    components: tuple[str, ...]
    requirements: tuple[str, ...]
    component_count: int
    requirement_count: int

    source_phase: int
    target_phase: int
    planning_admitted: bool
    execution_admitted: bool

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

    explicit_human_authorization_required: bool
    separate_runtime_execution_gate_required: bool
    separate_real_account_read_gate_required: bool
    separate_production_gate_required: bool

    real_preflight_execution_status: str
    mt5_import_status: str
    mt5_initialization_status: str
    terminal_connection_status: str
    broker_access_status: str
    real_account_read_status: str
    production_activation_status: str
    live_execution_status: str

    no_real_or_external_effects: bool
    ready_for_fake_validation: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_15_BLUEPRINT_SCHEMA_VERSION:
            raise ValueError("blueprint schema is inconsistent")
        if self.blueprint_status != PHASE_15_BLUEPRINT_STATUS:
            raise ValueError("blueprint status is inconsistent")
        if self.blueprint_mode != PHASE_15_BLUEPRINT_MODE:
            raise ValueError("blueprint mode is inconsistent")
        if self.blueprint_source != PHASE_15_BLUEPRINT_SOURCE:
            raise ValueError("blueprint source is inconsistent")
        if self.next_allowed_step != PHASE_15_BLUEPRINT_NEXT_ALLOWED:
            raise ValueError("next allowed step is inconsistent")
        if self.components != PHASE_15_BLUEPRINT_COMPONENTS:
            raise ValueError("components are inconsistent")
        if self.requirements != PHASE_15_BLUEPRINT_REQUIREMENTS:
            raise ValueError("requirements are inconsistent")
        if (self.component_count, self.requirement_count) != (8, 12):
            raise ValueError("component/requirement counts are inconsistent")
        if (self.source_phase, self.target_phase) != (14, 15):
            raise ValueError("phase lineage is inconsistent")
        if self.planning_admitted is not True or self.execution_admitted:
            raise ValueError("Phase 15 must remain planning-only")
        if self.symbol != "XAUUSD":
            raise ValueError("blueprint is XAUUSD-only")
        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("timeframes are inconsistent")
        if self.closed_candles_only is not True:
            raise ValueError("closed candles are required")
        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required")
        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps")
        if self.stage_risk_bps != (25, 25):
            raise ValueError("staged risk must be 25+25 bps")

        required = (
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.explicit_human_authorization_required,
            self.separate_runtime_execution_gate_required,
            self.separate_real_account_read_gate_required,
            self.separate_production_gate_required,
            self.no_real_or_external_effects,
            self.ready_for_fake_validation,
        )
        if not all(required):
            raise ValueError("blueprint lost a safety invariant")

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
        if statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def blueprint_digest(self) -> str:
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        material = "|".join(
            (
                self.schema_version,
                permit_id,
                self.blueprint_status,
                self.blueprint_mode,
                self.blueprint_source,
                self.next_allowed_step,
                ",".join(self.components),
                ",".join(self.requirements),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.no_real_or_external_effects),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def blueprint_id(self) -> str:
        return f"GOLDXBOT_PHASE_15_EXTENSION_ARCHITECTURE_BLUEPRINT:SHA256[{self.blueprint_digest}]"


@dataclass(frozen=True, slots=True)
class Phase15ExtensionArchitectureDecision:
    """Allowed or blocked blueprint decision."""

    is_allowed: bool
    blueprint: Phase15ExtensionArchitectureBlueprint | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.blueprint is None or self.blockers:
                raise ValueError("allowed blueprint decision is inconsistent")
        elif self.blueprint is not None or not self.blockers:
            raise ValueError("blocked blueprint decision is inconsistent")

    @property
    def blueprint_required(self) -> Phase15ExtensionArchitectureBlueprint:
        if self.blueprint is None:
            raise RuntimeError("Phase 15 architecture blueprint is blocked.")
        return self.blueprint


class Phase15ExtensionArchitecturePlanner:
    """Builds the planning-only Phase 15 architecture blueprint."""

    def build(
        self,
        admission_decision: object,
    ) -> Phase15ExtensionArchitectureDecision:
        if admission_decision is None:
            return Phase15ExtensionArchitectureDecision(
                False,
                None,
                ("phase15_admission_decision_missing",),
            )
        if getattr(admission_decision, "is_allowed", True) is not True:
            return Phase15ExtensionArchitectureDecision(
                False,
                None,
                ("phase15_admission_decision_blocked",),
            )

        try:
            permit = admission_decision.permit_required
            source = permit.source_bundle
            source_valid = (
                permit.admission_status == "ADMITTED_FOR_PLANNING_ONLY"
                and permit.phase15_planning_admitted is True
                and permit.phase15_execution_admitted is False
                and permit.phase15_foundation_ready is True
                and permit.no_real_or_external_effects is True
                and permit.planning_tracks
                == (
                    "REQUIREMENTS_PLANNING",
                    "ARCHITECTURE_PLANNING",
                    "DETERMINISTIC_VALIDATION_PLANNING",
                    "SAFETY_AUDIT_PLANNING",
                )
                and permit.validation_audit_counts == (8, 12, 20, 16)
                and permit.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)
                and permit.safety_requirements
                == (
                    "OCO_REQUIRED",
                    "BROKER_STOP_LOSS_REQUIRED",
                    "GUARDS_REQUIRED",
                    "TERMINAL_FLAT_STATE_REQUIRED",
                    "MARTINGALE_PROHIBITED",
                    "GRID_PROHIBITED",
                    "NO_STOP_LOSS_PROHIBITED",
                )
                and permit.future_gate_requirements
                == (
                    "EXPLICIT_HUMAN_AUTHORIZATION_REQUIRED",
                    "SEPARATE_RUNTIME_EXECUTION_GATE_REQUIRED",
                    "SEPARATE_REAL_ACCOUNT_READ_GATE_REQUIRED",
                    "SEPARATE_PRODUCTION_GATE_REQUIRED",
                )
                and permit.runtime_statuses == ("BLOCKED",) * 8
                and source.phase_status == "PHASE_14_COMPLETE"
                and source.handoff_status == "PHASE_14_EXTENSION_COMPLETE"
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase15ExtensionArchitectureDecision(
                False,
                None,
                (f"phase15_admission_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase15ExtensionArchitectureDecision(
                False,
                None,
                ("phase15_admission_contract_invalid",),
            )

        blueprint = Phase15ExtensionArchitectureBlueprint(
            admission_decision=admission_decision,
            admission_permit=permit,
            phase14_final_handoff=source,
            schema_version=PHASE_15_BLUEPRINT_SCHEMA_VERSION,
            blueprint_status=PHASE_15_BLUEPRINT_STATUS,
            blueprint_mode=PHASE_15_BLUEPRINT_MODE,
            blueprint_source=PHASE_15_BLUEPRINT_SOURCE,
            next_allowed_step=PHASE_15_BLUEPRINT_NEXT_ALLOWED,
            components=PHASE_15_BLUEPRINT_COMPONENTS,
            requirements=PHASE_15_BLUEPRINT_REQUIREMENTS,
            component_count=len(PHASE_15_BLUEPRINT_COMPONENTS),
            requirement_count=len(PHASE_15_BLUEPRINT_REQUIREMENTS),
            source_phase=permit.source_phase,
            target_phase=permit.target_phase,
            planning_admitted=permit.phase15_planning_admitted,
            execution_admitted=permit.phase15_execution_admitted,
            symbol=permit.symbol,
            timeframes=permit.timeframes,
            closed_candles_only=permit.closed_candles_only,
            max_gold_positions=permit.max_gold_positions,
            aggregate_risk_budget_bps=permit.aggregate_risk_budget_bps,
            stage_risk_bps=permit.stage_risk_bps,
            oco_required=("OCO_REQUIRED" in permit.safety_requirements),
            broker_stop_loss_required=("BROKER_STOP_LOSS_REQUIRED" in permit.safety_requirements),
            guards_required=("GUARDS_REQUIRED" in permit.safety_requirements),
            terminal_flat_state_required=(
                "TERMINAL_FLAT_STATE_REQUIRED" in permit.safety_requirements
            ),
            martingale_prohibited=("MARTINGALE_PROHIBITED" in permit.safety_requirements),
            grid_prohibited=("GRID_PROHIBITED" in permit.safety_requirements),
            no_stop_loss_prohibited=("NO_STOP_LOSS_PROHIBITED" in permit.safety_requirements),
            explicit_human_authorization_required=(
                "EXPLICIT_HUMAN_AUTHORIZATION_REQUIRED" in permit.future_gate_requirements
            ),
            separate_runtime_execution_gate_required=(
                "SEPARATE_RUNTIME_EXECUTION_GATE_REQUIRED" in permit.future_gate_requirements
            ),
            separate_real_account_read_gate_required=(
                "SEPARATE_REAL_ACCOUNT_READ_GATE_REQUIRED" in permit.future_gate_requirements
            ),
            separate_production_gate_required=(
                "SEPARATE_PRODUCTION_GATE_REQUIRED" in permit.future_gate_requirements
            ),
            real_preflight_execution_status=permit.runtime_statuses[0],
            mt5_import_status=permit.runtime_statuses[1],
            mt5_initialization_status=permit.runtime_statuses[2],
            terminal_connection_status=permit.runtime_statuses[3],
            broker_access_status=permit.runtime_statuses[4],
            real_account_read_status=permit.runtime_statuses[5],
            production_activation_status=permit.runtime_statuses[6],
            live_execution_status=permit.runtime_statuses[7],
            no_real_or_external_effects=True,
            ready_for_fake_validation=True,
        )
        return Phase15ExtensionArchitectureDecision(True, blueprint, ())


def build_phase15_extension_architecture(
    admission_decision: object,
) -> Phase15ExtensionArchitectureDecision:
    """Build the Phase 15 planning-only architecture blueprint."""

    return Phase15ExtensionArchitecturePlanner().build(admission_decision)


__all__ = (
    "PHASE_15_BLUEPRINT_SCHEMA_VERSION",
    "PHASE_15_BLUEPRINT_STATUS",
    "PHASE_15_BLUEPRINT_MODE",
    "PHASE_15_BLUEPRINT_SOURCE",
    "PHASE_15_BLUEPRINT_NEXT_ALLOWED",
    "PHASE_15_BLUEPRINT_COMPONENTS",
    "PHASE_15_BLUEPRINT_REQUIREMENTS",
    "Phase15ExtensionArchitectureBlueprint",
    "Phase15ExtensionArchitectureDecision",
    "Phase15ExtensionArchitecturePlanner",
    "build_phase15_extension_architecture",
)
