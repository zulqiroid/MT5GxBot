"""Deterministic fake validation for the Phase 15 architecture blueprint.

This module validates only immutable, in-memory planning contracts. It does
not import or initialize real MT5, connect to a terminal, access a broker,
read a real account, invoke order operations, write external state, activate
production, or submit live orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_15_ARCHITECTURE_VALIDATION_SCHEMA_VERSION = "1.0"
PHASE_15_ARCHITECTURE_VALIDATION_STATUS = "PASSED"
PHASE_15_ARCHITECTURE_VALIDATION_OUTCOME = "READY_FOR_ARCHITECTURE_SAFETY_AUDIT"
PHASE_15_ARCHITECTURE_VALIDATION_SOURCE = "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"


@dataclass(frozen=True, slots=True)
class Phase15ArchitectureValidationResult:
    """One deterministic fake validation result."""

    sequence_index: int
    category: str
    name: str
    status: str
    fake_only: bool
    real_effect_performed: bool

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError("sequence index cannot be negative")
        if self.category not in ("COMPONENT", "REQUIREMENT"):
            raise ValueError("invalid validation category")
        if not self.name:
            raise ValueError("validation result name is required")
        if self.status != "PASSED":
            raise ValueError("validation result must pass")
        if self.fake_only is not True or self.real_effect_performed:
            raise ValueError("validation result must remain fake-only")

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
class Phase15ArchitectureValidationReport:
    """Immutable Phase 15 deterministic architecture validation report."""

    architecture_decision: object = field(repr=False)
    architecture_blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase14_final_handoff: object = field(repr=False)

    schema_version: str
    validation_status: str
    validation_outcome: str
    validation_source: str

    results: tuple[Phase15ArchitectureValidationResult, ...]
    component_results: int
    requirement_results: int
    total_results: int
    result_sequence_valid: bool
    component_order_valid: bool
    requirement_order_valid: bool
    all_results_fake_only: bool

    source_validation_audit_counts: tuple[int, ...]
    source_evidence_counts: tuple[int, ...]

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

    runtime_statuses: tuple[str, ...]
    no_real_or_external_effects: bool
    ready_for_architecture_safety_audit: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_15_ARCHITECTURE_VALIDATION_SCHEMA_VERSION:
            raise ValueError("validation schema is inconsistent")
        if self.validation_status != PHASE_15_ARCHITECTURE_VALIDATION_STATUS:
            raise ValueError("validation status is inconsistent")
        if self.validation_outcome != PHASE_15_ARCHITECTURE_VALIDATION_OUTCOME:
            raise ValueError("validation outcome is inconsistent")
        if self.validation_source != PHASE_15_ARCHITECTURE_VALIDATION_SOURCE:
            raise ValueError("validation source is inconsistent")

        if (
            self.component_results,
            self.requirement_results,
            self.total_results,
        ) != (8, 12, 20):
            raise ValueError("validation result counts are inconsistent")
        if len(self.results) != 20:
            raise ValueError("exactly twenty results are required")
        if tuple(item.sequence_index for item in self.results) != tuple(range(20)):
            raise ValueError("validation result sequence is inconsistent")

        if self.source_validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("source validation/audit counts changed")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence counts changed")

        if self.symbol != "XAUUSD":
            raise ValueError("validation is XAUUSD-only")
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
            raise ValueError("validation lost a required invariant")

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
            raise ValueError("a real or external effect was detected")
        if self.runtime_statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def validation_digest(self) -> str:
        material = "|".join(
            (
                self.schema_version,
                self.validation_status,
                self.validation_outcome,
                self.validation_source,
                ",".join(item.digest for item in self.results),
                ",".join(map(str, self.source_validation_audit_counts)),
                ",".join(map(str, self.source_evidence_counts)),
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
        return f"GOLDXBOT_PHASE_15_ARCHITECTURE_VALIDATION:SHA256[{self.validation_digest}]"


@dataclass(frozen=True, slots=True)
class Phase15ArchitectureValidationDecision:
    """Allowed or blocked Phase 15 validation decision."""

    is_allowed: bool
    report: Phase15ArchitectureValidationReport | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.report is None or self.blockers:
                raise ValueError("allowed validation decision is inconsistent")
        elif self.report is not None or not self.blockers:
            raise ValueError("blocked validation decision is inconsistent")

    @property
    def report_required(self) -> Phase15ArchitectureValidationReport:
        if self.report is None:
            raise RuntimeError("Phase 15 architecture validation is blocked.")
        return self.report


def _build_results(
    blueprint: object,
) -> tuple[Phase15ArchitectureValidationResult, ...]:
    components = tuple(
        Phase15ArchitectureValidationResult(
            index,
            "COMPONENT",
            name,
            "PASSED",
            True,
            False,
        )
        for index, name in enumerate(blueprint.components)
    )
    requirements = tuple(
        Phase15ArchitectureValidationResult(
            index + 8,
            "REQUIREMENT",
            name,
            "PASSED",
            True,
            False,
        )
        for index, name in enumerate(blueprint.requirements)
    )
    return components + requirements


class Phase15ArchitectureValidator:
    """Validates the Phase 15 blueprint with deterministic fakes only."""

    def validate(
        self,
        architecture_decision: object,
    ) -> Phase15ArchitectureValidationDecision:
        if architecture_decision is None:
            return Phase15ArchitectureValidationDecision(
                False,
                None,
                ("phase15_architecture_decision_missing",),
            )
        if getattr(architecture_decision, "is_allowed", True) is not True:
            return Phase15ArchitectureValidationDecision(
                False,
                None,
                ("phase15_architecture_decision_blocked",),
            )

        try:
            blueprint = architecture_decision.blueprint_required
            admission_decision = blueprint.admission_decision
            permit = blueprint.admission_permit
            phase14 = blueprint.phase14_final_handoff

            blueprint_valid = (
                blueprint.blueprint_status == "BLUEPRINT_READY"
                and blueprint.blueprint_mode == "PLANNING_ONLY"
                and blueprint.blueprint_source == "PHASE_15_ADMISSION_PERMIT_ONLY"
                and blueprint.next_allowed_step == "DETERMINISTIC_FAKE_VALIDATION"
                and blueprint.component_count == 8
                and blueprint.requirement_count == 12
                and len(blueprint.components) == 8
                and len(blueprint.requirements) == 12
                and blueprint.planning_admitted is True
                and blueprint.execution_admitted is False
                and blueprint.ready_for_fake_validation is True
                and blueprint.no_real_or_external_effects is True
            )

            lineage_preserved = (
                blueprint.admission_decision is admission_decision
                and blueprint.admission_permit is permit
                and blueprint.phase14_final_handoff is phase14
                and admission_decision.permit_required is permit
                and permit.source_bundle is phase14
                and phase14.phase_status == "PHASE_14_COMPLETE"
                and phase14.handoff_status == "PHASE_14_EXTENSION_COMPLETE"
            )

            safety_preserved = all(
                (
                    blueprint.oco_required,
                    blueprint.broker_stop_loss_required,
                    blueprint.guards_required,
                    blueprint.terminal_flat_state_required,
                    blueprint.martingale_prohibited,
                    blueprint.grid_prohibited,
                    blueprint.no_stop_loss_prohibited,
                )
            )
            future_gates_required = all(
                (
                    blueprint.explicit_human_authorization_required,
                    blueprint.separate_runtime_execution_gate_required,
                    blueprint.separate_real_account_read_gate_required,
                    blueprint.separate_production_gate_required,
                )
            )

            runtime_statuses = (
                blueprint.real_preflight_execution_status,
                blueprint.mt5_import_status,
                blueprint.mt5_initialization_status,
                blueprint.terminal_connection_status,
                blueprint.broker_access_status,
                blueprint.real_account_read_status,
                blueprint.production_activation_status,
                blueprint.live_execution_status,
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase15ArchitectureValidationDecision(
                False,
                None,
                (f"phase15_architecture_invalid:{type(error).__name__}",),
            )

        if not all(
            (
                blueprint_valid,
                lineage_preserved,
                safety_preserved,
                future_gates_required,
                runtime_statuses == ("BLOCKED",) * 8,
            )
        ):
            return Phase15ArchitectureValidationDecision(
                False,
                None,
                ("phase15_architecture_contract_invalid",),
            )

        results = _build_results(blueprint)
        report = Phase15ArchitectureValidationReport(
            architecture_decision=architecture_decision,
            architecture_blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=permit,
            phase14_final_handoff=phase14,
            schema_version=PHASE_15_ARCHITECTURE_VALIDATION_SCHEMA_VERSION,
            validation_status=PHASE_15_ARCHITECTURE_VALIDATION_STATUS,
            validation_outcome=PHASE_15_ARCHITECTURE_VALIDATION_OUTCOME,
            validation_source=PHASE_15_ARCHITECTURE_VALIDATION_SOURCE,
            results=results,
            component_results=8,
            requirement_results=12,
            total_results=20,
            result_sequence_valid=tuple(item.sequence_index for item in results)
            == tuple(range(20)),
            component_order_valid=tuple(item.name for item in results[:8]) == blueprint.components,
            requirement_order_valid=tuple(item.name for item in results[8:])
            == blueprint.requirements,
            all_results_fake_only=all(
                item.fake_only and not item.real_effect_performed for item in results
            ),
            source_validation_audit_counts=permit.validation_audit_counts,
            source_evidence_counts=permit.source_evidence_counts,
            symbol=blueprint.symbol,
            timeframes=blueprint.timeframes,
            closed_candles_only=blueprint.closed_candles_only,
            max_gold_positions=blueprint.max_gold_positions,
            aggregate_risk_budget_bps=blueprint.aggregate_risk_budget_bps,
            stage_risk_bps=blueprint.stage_risk_bps,
            safety_invariants_preserved=safety_preserved,
            future_gates_required=future_gates_required,
            lineage_preserved=lineage_preserved,
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
            runtime_statuses=runtime_statuses,
            no_real_or_external_effects=True,
            ready_for_architecture_safety_audit=True,
        )
        return Phase15ArchitectureValidationDecision(True, report, ())


def validate_phase15_extension_architecture(
    architecture_decision: object,
) -> Phase15ArchitectureValidationDecision:
    """Validate the Phase 15 architecture with deterministic fakes."""

    return Phase15ArchitectureValidator().validate(architecture_decision)


__all__ = (
    "PHASE_15_ARCHITECTURE_VALIDATION_SCHEMA_VERSION",
    "PHASE_15_ARCHITECTURE_VALIDATION_STATUS",
    "PHASE_15_ARCHITECTURE_VALIDATION_OUTCOME",
    "PHASE_15_ARCHITECTURE_VALIDATION_SOURCE",
    "Phase15ArchitectureValidationResult",
    "Phase15ArchitectureValidationReport",
    "Phase15ArchitectureValidationDecision",
    "Phase15ArchitectureValidator",
    "validate_phase15_extension_architecture",
)
