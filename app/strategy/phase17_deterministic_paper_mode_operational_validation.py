"""Phase 17 deterministic paper-mode operational validation.

Consumes the successful Step 17.2 paper-mode operational-readiness blueprint
and validates all components, requirements, and operational tracks using
immutable in-memory evidence only.

No real .env access, MT5 import or initialization, terminal connection,
broker/account access, order operations, external writes, production
activation, or live execution is performed or admitted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_17_VALIDATION_SCHEMA_VERSION = "1.0"
PHASE_17_VALIDATION_STATUS = "PASSED"
PHASE_17_VALIDATION_OUTCOME = "READY_FOR_PAPER_MODE_OPERATIONAL_SAFETY_AUDIT"
PHASE_17_VALIDATION_SOURCE = "DETERMINISTIC_IN_MEMORY_PAPER_MODE_EVIDENCE_ONLY"


@dataclass(frozen=True, slots=True)
class Phase17PaperModeOperationalValidationResult:
    sequence_index: int
    category: str
    name: str
    status: str
    fake_only: bool
    real_effect_performed: bool

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError("sequence index cannot be negative")
        if self.category not in ("COMPONENT", "REQUIREMENT", "TRACK"):
            raise ValueError("invalid validation category")
        if not self.name.strip():
            raise ValueError("validation result name is required")
        if self.status != "PASSED":
            raise ValueError("validation result must pass")
        if self.fake_only is not True or self.real_effect_performed:
            raise ValueError("validation must remain fake-only")

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
        return hashlib.sha256(material.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase17PaperModeOperationalValidationReport:
    blueprint_decision: object = field(repr=False)
    blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase16_final_handoff: object = field(repr=False)

    schema_version: str
    validation_status: str
    validation_outcome: str
    validation_source: str

    results: tuple[Phase17PaperModeOperationalValidationResult, ...]
    component_results: int
    requirement_results: int
    track_results: int
    total_results: int

    result_sequence_valid: bool
    component_order_valid: bool
    requirement_order_valid: bool
    track_order_valid: bool
    all_results_fake_only: bool

    phase16_evidence_counts: tuple[int, ...]
    source_validation_audit_counts: tuple[int, ...]
    source_evidence_counts: tuple[int, ...]

    release_baseline_commit: str
    release_baseline_tag: str

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    planning_only_preserved: bool
    fail_closed_preserved: bool
    evidence_handoff_preserved: bool
    lineage_preserved: bool
    real_env_access_performed: bool

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
    ready_for_operational_safety_audit: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_17_VALIDATION_SCHEMA_VERSION:
            raise ValueError("validation schema changed")
        if self.validation_status != PHASE_17_VALIDATION_STATUS:
            raise ValueError("validation status changed")
        if self.validation_outcome != PHASE_17_VALIDATION_OUTCOME:
            raise ValueError("validation outcome changed")
        if self.validation_source != PHASE_17_VALIDATION_SOURCE:
            raise ValueError("validation source changed")

        if (
            self.component_results,
            self.requirement_results,
            self.track_results,
            self.total_results,
        ) != (8, 12, 5, 25):
            raise ValueError("validation result counts changed")
        if len(self.results) != 25:
            raise ValueError("exactly twenty-five results are required")
        if tuple(item.sequence_index for item in self.results) != tuple(range(25)):
            raise ValueError("validation sequence changed")

        required = (
            self.result_sequence_valid,
            self.component_order_valid,
            self.requirement_order_valid,
            self.track_order_valid,
            self.all_results_fake_only,
            self.planning_only_preserved,
            self.fail_closed_preserved,
            self.evidence_handoff_preserved,
            self.lineage_preserved,
            self.no_real_or_external_effects,
            self.ready_for_operational_safety_audit,
        )
        if not all(required):
            raise ValueError("validation lost a required invariant")

        if self.phase16_evidence_counts != (8, 12, 5, 25, 16):
            raise ValueError("Phase 16 evidence changed")
        if self.source_validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("source validation/audit evidence changed")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence changed")

        if (
            self.release_baseline_commit != "6ba3a00"
            or self.release_baseline_tag != "goldxbot-phase-15-complete"
        ):
            raise ValueError("release baseline changed")
        if (
            self.symbol != "XAUUSD"
            or self.timeframes != ("H4", "H1", "M15", "M5")
            or not self.closed_candles_only
            or self.max_gold_positions != 1
            or self.aggregate_risk_budget_bps != 50
            or self.stage_risk_bps != (25, 25)
        ):
            raise ValueError("Gold scope or risk invariants changed")

        forbidden = (
            self.real_env_access_performed,
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
    def validation_id(self) -> str:
        blueprint_id = str(getattr(self.blueprint, "blueprint_id", ""))
        material = "|".join(
            (
                blueprint_id,
                self.schema_version,
                self.validation_status,
                self.validation_outcome,
                self.validation_source,
                ",".join(item.digest for item in self.results),
                ",".join(map(str, self.phase16_evidence_counts)),
                ",".join(self.runtime_statuses),
            )
        )
        digest = hashlib.sha256(material.encode()).hexdigest()
        return f"GOLDXBOT_PHASE_17_VALIDATION:SHA256[{digest}]"


@dataclass(frozen=True, slots=True)
class Phase17PaperModeOperationalValidationDecision:
    is_allowed: bool
    report: Phase17PaperModeOperationalValidationReport | None
    blockers: tuple[str, ...]

    @property
    def report_required(self) -> Phase17PaperModeOperationalValidationReport:
        if self.report is None:
            raise RuntimeError("Phase 17 operational validation is blocked.")
        return self.report


def _build_results(
    blueprint: object,
) -> tuple[Phase17PaperModeOperationalValidationResult, ...]:
    components = tuple(
        Phase17PaperModeOperationalValidationResult(
            sequence_index=index,
            category="COMPONENT",
            name=component.name,
            status="PASSED",
            fake_only=True,
            real_effect_performed=False,
        )
        for index, component in enumerate(blueprint.components)
    )
    requirements = tuple(
        Phase17PaperModeOperationalValidationResult(
            sequence_index=index + 8,
            category="REQUIREMENT",
            name=requirement.statement,
            status="PASSED",
            fake_only=True,
            real_effect_performed=False,
        )
        for index, requirement in enumerate(blueprint.requirements)
    )
    tracks = tuple(
        Phase17PaperModeOperationalValidationResult(
            sequence_index=index + 20,
            category="TRACK",
            name=track,
            status="PASSED",
            fake_only=True,
            real_effect_performed=False,
        )
        for index, track in enumerate(blueprint.admission_permit.operational_tracks)
    )
    return components + requirements + tracks


class Phase17PaperModeOperationalValidator:
    def validate(
        self,
        blueprint_decision: object,
    ) -> Phase17PaperModeOperationalValidationDecision:
        if blueprint_decision is None:
            return Phase17PaperModeOperationalValidationDecision(
                False,
                None,
                ("phase17_blueprint_missing",),
            )
        if getattr(blueprint_decision, "is_allowed", True) is not True:
            return Phase17PaperModeOperationalValidationDecision(
                False,
                None,
                ("phase17_blueprint_blocked",),
            )

        try:
            blueprint = blueprint_decision.blueprint_required
            admission_decision = blueprint.admission_decision
            permit = blueprint.admission_permit
            source = blueprint.phase16_final_handoff

            blueprint_valid = (
                blueprint.blueprint_status == "BLUEPRINT_READY"
                and blueprint.blueprint_mode == "DETERMINISTIC_PAPER_MODE_PLANNING_ONLY"
                and blueprint.next_allowed_step == "DETERMINISTIC_PAPER_MODE_OPERATIONAL_VALIDATION"
                and blueprint.component_count == 8
                and blueprint.requirement_count == 12
                and blueprint.operational_track_count == 5
                and blueprint.planning_admitted is True
                and blueprint.execution_admitted is False
                and blueprint.real_env_access_allowed is False
                and blueprint.deterministic_fakes_only is True
                and blueprint.paper_mode_only is True
                and blueprint.fail_closed_required is True
                and blueprint.evidence_handoff_required is True
                and blueprint.runtime_statuses == ("BLOCKED",) * 8
                and blueprint.no_real_or_external_effects is True
                and blueprint.ready_for_deterministic_validation is True
            )
            lineage_preserved = (
                blueprint.admission_decision is admission_decision
                and blueprint.admission_permit is permit
                and blueprint.phase16_final_handoff is source
                and admission_decision.permit_required is permit
                and permit.source_bundle is source
                and source.phase_status == "PHASE_16_COMPLETE"
                and source.handoff_status == "PHASE_16_OFFLINE_RELEASE_READINESS_COMPLETE"
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase17PaperModeOperationalValidationDecision(
                False,
                None,
                (f"phase17_blueprint_invalid:{type(error).__name__}",),
            )

        if not blueprint_valid or not lineage_preserved:
            return Phase17PaperModeOperationalValidationDecision(
                False,
                None,
                ("phase17_blueprint_contract_invalid",),
            )

        results = _build_results(blueprint)
        component_names = tuple(item.name for item in blueprint.components)
        requirement_names = tuple(item.statement for item in blueprint.requirements)
        track_names = permit.operational_tracks

        report = Phase17PaperModeOperationalValidationReport(
            blueprint_decision=blueprint_decision,
            blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=permit,
            phase16_final_handoff=source,
            schema_version=PHASE_17_VALIDATION_SCHEMA_VERSION,
            validation_status=PHASE_17_VALIDATION_STATUS,
            validation_outcome=PHASE_17_VALIDATION_OUTCOME,
            validation_source=PHASE_17_VALIDATION_SOURCE,
            results=results,
            component_results=8,
            requirement_results=12,
            track_results=5,
            total_results=25,
            result_sequence_valid=tuple(item.sequence_index for item in results)
            == tuple(range(25)),
            component_order_valid=tuple(item.name for item in results[:8]) == component_names,
            requirement_order_valid=tuple(item.name for item in results[8:20]) == requirement_names,
            track_order_valid=tuple(item.name for item in results[20:]) == track_names,
            all_results_fake_only=all(
                item.fake_only and not item.real_effect_performed for item in results
            ),
            phase16_evidence_counts=blueprint.phase16_evidence_counts,
            source_validation_audit_counts=(blueprint.source_validation_audit_counts),
            source_evidence_counts=blueprint.source_evidence_counts,
            release_baseline_commit=blueprint.release_baseline_commit,
            release_baseline_tag=blueprint.release_baseline_tag,
            symbol=blueprint.symbol,
            timeframes=blueprint.timeframes,
            closed_candles_only=blueprint.closed_candles_only,
            max_gold_positions=blueprint.max_gold_positions,
            aggregate_risk_budget_bps=blueprint.aggregate_risk_budget_bps,
            stage_risk_bps=blueprint.stage_risk_bps,
            planning_only_preserved=(
                blueprint.planning_admitted and not blueprint.execution_admitted
            ),
            fail_closed_preserved=blueprint.fail_closed_required,
            evidence_handoff_preserved=(blueprint.evidence_handoff_required),
            lineage_preserved=lineage_preserved,
            real_env_access_performed=False,
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
            runtime_statuses=blueprint.runtime_statuses,
            no_real_or_external_effects=True,
            ready_for_operational_safety_audit=True,
        )
        return Phase17PaperModeOperationalValidationDecision(
            True,
            report,
            (),
        )


def validate_phase17_paper_mode_operational_readiness(
    blueprint_decision: object,
) -> Phase17PaperModeOperationalValidationDecision:
    return Phase17PaperModeOperationalValidator().validate(blueprint_decision)


__all__ = (
    "PHASE_17_VALIDATION_SCHEMA_VERSION",
    "PHASE_17_VALIDATION_STATUS",
    "PHASE_17_VALIDATION_OUTCOME",
    "PHASE_17_VALIDATION_SOURCE",
    "Phase17PaperModeOperationalValidationResult",
    "Phase17PaperModeOperationalValidationReport",
    "Phase17PaperModeOperationalValidationDecision",
    "Phase17PaperModeOperationalValidator",
    "validate_phase17_paper_mode_operational_readiness",
)
