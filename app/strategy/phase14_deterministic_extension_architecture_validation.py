"""Deterministic fake validation for the Phase 14 architecture blueprint."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_14_ARCHITECTURE_VALIDATION_SCHEMA_VERSION = "1.0"
PHASE_14_ARCHITECTURE_VALIDATION_STATUS = "PASSED"
PHASE_14_ARCHITECTURE_VALIDATION_OUTCOME = "READY_FOR_ARCHITECTURE_SAFETY_AUDIT"
PHASE_14_ARCHITECTURE_VALIDATION_SOURCE = "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"


@dataclass(frozen=True, slots=True)
class Phase14ArchitectureValidationResult:
    sequence_index: int
    category: str
    name: str
    status: str
    fake_only: bool
    real_effect_performed: bool

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError("negative sequence")
        if self.category not in ("COMPONENT", "REQUIREMENT"):
            raise ValueError("invalid category")
        if not self.name:
            raise ValueError("name required")
        if self.status != "PASSED":
            raise ValueError("result must pass")
        if not self.fake_only or self.real_effect_performed:
            raise ValueError("validation must be fake-only")

    @property
    def digest(self) -> str:
        material = "|".join(
            (
                str(self.sequence_index),
                self.category,
                self.name,
                self.status,
                str(self.fake_only),
                str(self.real_effect_performed),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase14ArchitectureValidationReport:
    architecture_decision: object = field(repr=False)
    architecture_blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase13_handoff_bundle: object = field(repr=False)

    schema_version: str
    validation_status: str
    validation_outcome: str
    validation_source: str
    results: tuple[Phase14ArchitectureValidationResult, ...]
    component_results: int
    requirement_results: int
    total_results: int
    result_sequence_valid: bool
    component_order_valid: bool
    requirement_order_valid: bool
    all_results_fake_only: bool

    runtime_operations: int
    blocked_write_operations: int
    error_mappings: int
    snapshot_mappings: int
    snapshot_fields: int
    prior_validation_events: int
    prior_safety_findings: int

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    safety_invariants_preserved: bool
    future_gates_required: bool
    lineage_preserved: bool

    real_preflight_executed: bool
    real_mt5_imported: bool
    real_mt5_initialized: bool
    real_terminal_connected: bool
    real_broker_access_performed: bool
    real_account_read_performed: bool
    order_check_invoked: bool
    order_send_invoked: bool
    external_state_written: bool
    production_activated: bool
    live_order_submitted: bool

    real_preflight_status: str
    mt5_import_status: str
    mt5_initialization_status: str
    terminal_status: str
    broker_status: str
    account_read_status: str
    production_status: str
    live_status: str

    no_real_or_external_effects: bool
    ready_for_architecture_safety_audit: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_14_ARCHITECTURE_VALIDATION_SCHEMA_VERSION:
            raise ValueError("invalid schema")
        if self.validation_status != PHASE_14_ARCHITECTURE_VALIDATION_STATUS:
            raise ValueError("invalid status")
        if self.validation_outcome != PHASE_14_ARCHITECTURE_VALIDATION_OUTCOME:
            raise ValueError("invalid outcome")
        if self.validation_source != PHASE_14_ARCHITECTURE_VALIDATION_SOURCE:
            raise ValueError("invalid source")
        if (self.component_results, self.requirement_results, self.total_results) != (8, 12, 20):
            raise ValueError("invalid result counts")
        if tuple(item.sequence_index for item in self.results) != tuple(range(20)):
            raise ValueError("invalid result sequence")
        if (
            self.runtime_operations,
            self.blocked_write_operations,
            self.error_mappings,
            self.snapshot_mappings,
            self.snapshot_fields,
            self.prior_validation_events,
            self.prior_safety_findings,
        ) != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("invalid source counts")
        if self.symbol != "XAUUSD" or self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("invalid market scope")
        if not self.closed_candles_only or self.max_gold_positions != 1:
            raise ValueError("invalid position scope")
        if self.aggregate_risk_budget_bps != 50 or self.stage_risk_bps != (25, 25):
            raise ValueError("invalid risk scope")
        required = (
            self.result_sequence_valid,
            self.component_order_valid,
            self.requirement_order_valid,
            self.all_results_fake_only,
            self.safety_invariants_preserved,
            self.future_gates_required,
            self.lineage_preserved,
            self.no_real_or_external_effects,
            self.ready_for_architecture_safety_audit,
        )
        if not all(required):
            raise ValueError("required invariant missing")
        forbidden = (
            self.real_preflight_executed,
            self.real_mt5_imported,
            self.real_mt5_initialized,
            self.real_terminal_connected,
            self.real_broker_access_performed,
            self.real_account_read_performed,
            self.order_check_invoked,
            self.order_send_invoked,
            self.external_state_written,
            self.production_activated,
            self.live_order_submitted,
        )
        if any(forbidden):
            raise ValueError("real effect detected")
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
            raise ValueError("runtime status not blocked")

    @property
    def validation_digest(self) -> str:
        material = "|".join(
            (
                self.schema_version,
                self.validation_status,
                self.validation_outcome,
                self.validation_source,
                ",".join(item.digest for item in self.results),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.no_real_or_external_effects),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def validation_id(self) -> str:
        return f"GOLDXBOT_PHASE_14_ARCHITECTURE_VALIDATION:SHA256[{self.validation_digest}]"


@dataclass(frozen=True, slots=True)
class Phase14ArchitectureValidationDecision:
    is_allowed: bool
    report: Phase14ArchitectureValidationReport | None
    blockers: tuple[str, ...]

    @property
    def report_required(self) -> Phase14ArchitectureValidationReport:
        if self.report is None:
            raise RuntimeError("Phase 14 architecture validation is blocked.")
        return self.report


def _results(blueprint: object) -> tuple[Phase14ArchitectureValidationResult, ...]:
    components = tuple(
        Phase14ArchitectureValidationResult(i, "COMPONENT", name, "PASSED", True, False)
        for i, name in enumerate(blueprint.components)
    )
    requirements = tuple(
        Phase14ArchitectureValidationResult(i + 8, "REQUIREMENT", name, "PASSED", True, False)
        for i, name in enumerate(blueprint.requirements)
    )
    return components + requirements


class Phase14ArchitectureValidator:
    def validate(self, architecture_decision: object) -> Phase14ArchitectureValidationDecision:
        if architecture_decision is None:
            return Phase14ArchitectureValidationDecision(
                False, None, ("phase14_architecture_decision_missing",)
            )
        if getattr(architecture_decision, "is_allowed", True) is not True:
            return Phase14ArchitectureValidationDecision(
                False, None, ("phase14_architecture_decision_blocked",)
            )

        try:
            blueprint = architecture_decision.blueprint_required
            admission_decision = blueprint.admission_decision
            admission_permit = blueprint.admission_permit
            phase13 = blueprint.phase13_handoff_bundle
            valid = (
                blueprint.blueprint_status == "BLUEPRINT_READY"
                and blueprint.blueprint_mode
                == "HUMAN_AUTHORIZED_READ_ONLY_PREFLIGHT_OBSERVABILITY_PLANNING_ONLY"
                and blueprint.blueprint_source == "PHASE_14_EXTENSION_ADMISSION_ONLY"
                and len(blueprint.components) == 8
                and len(blueprint.requirements) == 12
                and blueprint.fake_validation_allowed is True
                and blueprint.real_execution_allowed is False
                and blueprint.ready_for_fake_validation is True
                and blueprint.live_status == "BLOCKED"
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase14ArchitectureValidationDecision(
                False, None, (f"phase14_architecture_invalid:{type(error).__name__}",)
            )

        if not valid:
            return Phase14ArchitectureValidationDecision(
                False, None, ("phase14_architecture_contract_invalid",)
            )

        results = _results(blueprint)
        component_names = tuple(item.name for item in results if item.category == "COMPONENT")
        requirement_names = tuple(item.name for item in results if item.category == "REQUIREMENT")
        safety = (
            blueprint.oco_required
            and blueprint.broker_sl_required
            and blueprint.guards_required
            and blueprint.flat_state_required
            and blueprint.martingale_prohibited
            and blueprint.grid_prohibited
            and blueprint.no_sl_prohibited
        )
        gates = (
            blueprint.human_authorization_required
            and blueprint.runtime_gate_required
            and blueprint.account_read_gate_required
            and blueprint.production_gate_required
        )
        lineage = (
            architecture_decision.blueprint_required is blueprint
            and blueprint.admission_decision is admission_decision
            and blueprint.admission_permit is admission_permit
            and admission_permit.source_bundle is phase13
            and phase13.phase_status == "PHASE_13_COMPLETE"
        )
        no_effects = (
            blueprint.real_execution_allowed is False
            and blueprint.real_account_read_allowed is False
            and blueprint.external_write_allowed is False
            and blueprint.production_allowed is False
            and blueprint.live_execution_allowed is False
        )

        report = Phase14ArchitectureValidationReport(
            architecture_decision=architecture_decision,
            architecture_blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=admission_permit,
            phase13_handoff_bundle=phase13,
            schema_version=PHASE_14_ARCHITECTURE_VALIDATION_SCHEMA_VERSION,
            validation_status=PHASE_14_ARCHITECTURE_VALIDATION_STATUS,
            validation_outcome=PHASE_14_ARCHITECTURE_VALIDATION_OUTCOME,
            validation_source=PHASE_14_ARCHITECTURE_VALIDATION_SOURCE,
            results=results,
            component_results=8,
            requirement_results=12,
            total_results=20,
            result_sequence_valid=tuple(item.sequence_index for item in results)
            == tuple(range(20)),
            component_order_valid=component_names == blueprint.components,
            requirement_order_valid=requirement_names == blueprint.requirements,
            all_results_fake_only=all(
                item.fake_only and not item.real_effect_performed for item in results
            ),
            runtime_operations=blueprint.runtime_operations,
            blocked_write_operations=blueprint.blocked_write_operations,
            error_mappings=blueprint.error_mappings,
            snapshot_mappings=blueprint.snapshot_mappings,
            snapshot_fields=blueprint.snapshot_fields,
            prior_validation_events=blueprint.validation_events,
            prior_safety_findings=blueprint.safety_findings,
            symbol=blueprint.symbol,
            timeframes=blueprint.timeframes,
            closed_candles_only=blueprint.closed_candles_only,
            max_gold_positions=blueprint.max_gold_positions,
            aggregate_risk_budget_bps=blueprint.aggregate_risk_budget_bps,
            stage_risk_bps=blueprint.stage_risk_bps,
            safety_invariants_preserved=safety,
            future_gates_required=gates,
            lineage_preserved=lineage,
            real_preflight_executed=False,
            real_mt5_imported=False,
            real_mt5_initialized=False,
            real_terminal_connected=False,
            real_broker_access_performed=False,
            real_account_read_performed=False,
            order_check_invoked=False,
            order_send_invoked=False,
            external_state_written=False,
            production_activated=False,
            live_order_submitted=False,
            real_preflight_status=blueprint.real_preflight_status,
            mt5_import_status=blueprint.mt5_import_status,
            mt5_initialization_status=blueprint.mt5_initialization_status,
            terminal_status=blueprint.terminal_status,
            broker_status=blueprint.broker_status,
            account_read_status=blueprint.account_read_status,
            production_status=blueprint.production_status,
            live_status=blueprint.live_status,
            no_real_or_external_effects=no_effects,
            ready_for_architecture_safety_audit=True,
        )
        return Phase14ArchitectureValidationDecision(True, report, ())


def validate_phase14_extension_architecture(
    architecture_decision: object,
) -> Phase14ArchitectureValidationDecision:
    return Phase14ArchitectureValidator().validate(architecture_decision)


__all__ = (
    "PHASE_14_ARCHITECTURE_VALIDATION_SCHEMA_VERSION",
    "PHASE_14_ARCHITECTURE_VALIDATION_STATUS",
    "PHASE_14_ARCHITECTURE_VALIDATION_OUTCOME",
    "PHASE_14_ARCHITECTURE_VALIDATION_SOURCE",
    "Phase14ArchitectureValidationResult",
    "Phase14ArchitectureValidationReport",
    "Phase14ArchitectureValidationDecision",
    "Phase14ArchitectureValidator",
    "validate_phase14_extension_architecture",
)
