"""Deterministic offline release validation for Phase 16.

This module validates only immutable, in-memory release-readiness planning
contracts. It does not read the real .env file, import or initialize real MT5,
connect to a terminal, access a broker, read a real account, invoke order
operations, write external state, activate production, or submit live orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_16_OFFLINE_VALIDATION_SCHEMA_VERSION = "1.0"
PHASE_16_OFFLINE_VALIDATION_STATUS = "PASSED"
PHASE_16_OFFLINE_VALIDATION_OUTCOME = "READY_FOR_OFFLINE_RELEASE_SAFETY_AUDIT"
PHASE_16_OFFLINE_VALIDATION_SOURCE = "DETERMINISTIC_IN_MEMORY_RELEASE_FAKE_ONLY"


@dataclass(frozen=True, slots=True)
class Phase16OfflineReleaseValidationResult:
    """One deterministic offline release-readiness validation result."""

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
class Phase16OfflineReleaseValidationReport:
    """Immutable Phase 16 deterministic offline validation report."""

    blueprint_decision: object = field(repr=False)
    blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase15_final_handoff: object = field(repr=False)

    schema_version: str
    validation_status: str
    validation_outcome: str
    validation_source: str

    results: tuple[Phase16OfflineReleaseValidationResult, ...]
    component_results: int
    requirement_results: int
    track_results: int
    total_results: int

    result_sequence_valid: bool
    component_order_valid: bool
    requirement_order_valid: bool
    track_order_valid: bool
    all_results_fake_only: bool

    release_baseline_commit: str
    release_baseline_tag: str
    source_validation_audit_counts: tuple[int, ...]
    source_evidence_counts: tuple[int, ...]

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    release_controls_preserved: bool
    safety_invariants_preserved: bool
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
    ready_for_offline_release_safety_audit: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_16_OFFLINE_VALIDATION_SCHEMA_VERSION:
            raise ValueError("validation schema is inconsistent")
        if self.validation_status != PHASE_16_OFFLINE_VALIDATION_STATUS:
            raise ValueError("validation status is inconsistent")
        if self.validation_outcome != PHASE_16_OFFLINE_VALIDATION_OUTCOME:
            raise ValueError("validation outcome is inconsistent")
        if self.validation_source != PHASE_16_OFFLINE_VALIDATION_SOURCE:
            raise ValueError("validation source is inconsistent")

        if (
            self.component_results,
            self.requirement_results,
            self.track_results,
            self.total_results,
        ) != (8, 12, 5, 25):
            raise ValueError("validation result counts are inconsistent")
        if len(self.results) != 25:
            raise ValueError("exactly twenty-five results are required")
        if tuple(item.sequence_index for item in self.results) != tuple(range(25)):
            raise ValueError("validation result sequence is inconsistent")

        if self.release_baseline_commit != "6ba3a00":
            raise ValueError("release baseline commit changed")
        if self.release_baseline_tag != "goldxbot-phase-15-complete":
            raise ValueError("release baseline tag changed")
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
            self.track_order_valid,
            self.all_results_fake_only,
            self.release_controls_preserved,
            self.safety_invariants_preserved,
            self.lineage_preserved,
            self.no_real_or_external_effects,
            self.ready_for_offline_release_safety_audit,
        )
        if not all(required):
            raise ValueError("validation lost a required invariant")

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
    def validation_digest(self) -> str:
        blueprint_id = str(getattr(self.blueprint, "blueprint_id", ""))
        material = "|".join(
            (
                self.schema_version,
                blueprint_id,
                self.validation_status,
                self.validation_outcome,
                self.validation_source,
                ",".join(item.digest for item in self.results),
                self.release_baseline_commit,
                self.release_baseline_tag,
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
        return f"GOLDXBOT_PHASE_16_OFFLINE_RELEASE_VALIDATION:SHA256[{self.validation_digest}]"


@dataclass(frozen=True, slots=True)
class Phase16OfflineReleaseValidationDecision:
    """Allowed or blocked Phase 16 offline validation decision."""

    is_allowed: bool
    report: Phase16OfflineReleaseValidationReport | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.report is None or self.blockers:
                raise ValueError("allowed validation decision is inconsistent")
        elif self.report is not None or not self.blockers:
            raise ValueError("blocked validation decision is inconsistent")

    @property
    def report_required(self) -> Phase16OfflineReleaseValidationReport:
        if self.report is None:
            raise RuntimeError("Phase 16 offline release validation is blocked.")
        return self.report


def _build_results(
    blueprint: object,
) -> tuple[Phase16OfflineReleaseValidationResult, ...]:
    component_results = tuple(
        Phase16OfflineReleaseValidationResult(
            sequence_index=index,
            category="COMPONENT",
            name=component.name,
            status="PASSED",
            fake_only=True,
            real_effect_performed=False,
        )
        for index, component in enumerate(blueprint.components)
    )
    requirement_results = tuple(
        Phase16OfflineReleaseValidationResult(
            sequence_index=index + 8,
            category="REQUIREMENT",
            name=requirement.code,
            status="PASSED",
            fake_only=True,
            real_effect_performed=False,
        )
        for index, requirement in enumerate(blueprint.requirements)
    )
    track_results = tuple(
        Phase16OfflineReleaseValidationResult(
            sequence_index=index + 20,
            category="TRACK",
            name=track,
            status="PASSED",
            fake_only=True,
            real_effect_performed=False,
        )
        for index, track in enumerate(blueprint.admission_permit.release_readiness_tracks)
    )
    return component_results + requirement_results + track_results


class Phase16OfflineReleaseValidator:
    """Validates the Phase 16 blueprint using deterministic fakes only."""

    def validate(
        self,
        blueprint_decision: object,
    ) -> Phase16OfflineReleaseValidationDecision:
        if blueprint_decision is None:
            return Phase16OfflineReleaseValidationDecision(
                False,
                None,
                ("phase16_blueprint_decision_missing",),
            )
        if getattr(blueprint_decision, "is_allowed", True) is not True:
            return Phase16OfflineReleaseValidationDecision(
                False,
                None,
                ("phase16_blueprint_decision_blocked",),
            )

        try:
            blueprint = blueprint_decision.blueprint_required
            admission_decision = blueprint.admission_decision
            permit = blueprint.admission_permit
            phase15 = blueprint.phase15_final_handoff

            blueprint_valid = (
                blueprint.blueprint_status == "BLUEPRINT_READY"
                and blueprint.blueprint_mode == "OFFLINE_PLANNING_ONLY"
                and blueprint.blueprint_source
                == "PHASE_16_OFFLINE_RELEASE_READINESS_ADMISSION_ONLY"
                and blueprint.next_allowed_step == "DETERMINISTIC_OFFLINE_RELEASE_VALIDATION"
                and blueprint.release_baseline_commit == "6ba3a00"
                and blueprint.release_baseline_tag == "goldxbot-phase-15-complete"
                and blueprint.component_count == 8
                and blueprint.requirement_count == 12
                and blueprint.release_readiness_track_count == 5
                and blueprint.planning_admitted is True
                and blueprint.execution_admitted is False
                and blueprint.real_env_access_allowed is False
                and blueprint.deterministic_fakes_only is True
                and blueprint.paper_mode_only is True
                and blueprint.ready_for_deterministic_offline_validation is True
                and blueprint.no_real_or_external_effects is True
            )

            lineage_preserved = (
                blueprint.admission_decision is admission_decision
                and blueprint.admission_permit is permit
                and blueprint.phase15_final_handoff is phase15
                and admission_decision.permit_required is permit
                and permit.source_bundle is phase15
                and phase15.phase_status == "PHASE_15_COMPLETE"
                and phase15.handoff_status == "PHASE_15_EXTENSION_COMPLETE"
            )

            release_controls_preserved = all(
                (
                    blueprint.deterministic_fakes_only,
                    blueprint.paper_mode_only,
                    blueprint.backup_and_rollback_required,
                    blueprint.incident_recovery_required,
                    not blueprint.real_env_access_allowed,
                )
            )

            safety_requirements = permit.safety_requirements
            safety_preserved = (
                "XAUUSD_ONLY" in safety_requirements
                and "CLOSED_H4_H1_M15_M5_ONLY" in safety_requirements
                and "ONE_GOLD_POSITION_MAXIMUM" in safety_requirements
                and "AGGREGATE_RISK_50_BPS" in safety_requirements
                and "STAGED_RISK_25_PLUS_25_BPS" in safety_requirements
                and "OCO_REQUIRED" in safety_requirements
                and "BROKER_STOP_LOSS_REQUIRED" in safety_requirements
                and "GUARDS_REQUIRED" in safety_requirements
                and "TERMINAL_FLAT_STATE_REQUIRED" in safety_requirements
                and "MARTINGALE_PROHIBITED" in safety_requirements
                and "GRID_PROHIBITED" in safety_requirements
                and "NO_STOP_LOSS_PROHIBITED" in safety_requirements
            )

            runtime_statuses = blueprint.runtime_statuses
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase16OfflineReleaseValidationDecision(
                False,
                None,
                (f"phase16_blueprint_invalid:{type(error).__name__}",),
            )

        if not all(
            (
                blueprint_valid,
                lineage_preserved,
                release_controls_preserved,
                safety_preserved,
                runtime_statuses == ("BLOCKED",) * 8,
            )
        ):
            return Phase16OfflineReleaseValidationDecision(
                False,
                None,
                ("phase16_blueprint_contract_invalid",),
            )

        results = _build_results(blueprint)
        component_names = tuple(component.name for component in blueprint.components)
        requirement_codes = tuple(requirement.code for requirement in blueprint.requirements)
        track_names = permit.release_readiness_tracks

        report = Phase16OfflineReleaseValidationReport(
            blueprint_decision=blueprint_decision,
            blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=permit,
            phase15_final_handoff=phase15,
            schema_version=PHASE_16_OFFLINE_VALIDATION_SCHEMA_VERSION,
            validation_status=PHASE_16_OFFLINE_VALIDATION_STATUS,
            validation_outcome=PHASE_16_OFFLINE_VALIDATION_OUTCOME,
            validation_source=PHASE_16_OFFLINE_VALIDATION_SOURCE,
            results=results,
            component_results=8,
            requirement_results=12,
            track_results=5,
            total_results=25,
            result_sequence_valid=tuple(item.sequence_index for item in results)
            == tuple(range(25)),
            component_order_valid=tuple(item.name for item in results[:8]) == component_names,
            requirement_order_valid=tuple(item.name for item in results[8:20]) == requirement_codes,
            track_order_valid=tuple(item.name for item in results[20:]) == track_names,
            all_results_fake_only=all(
                item.fake_only and not item.real_effect_performed for item in results
            ),
            release_baseline_commit=blueprint.release_baseline_commit,
            release_baseline_tag=blueprint.release_baseline_tag,
            source_validation_audit_counts=(blueprint.source_validation_audit_counts),
            source_evidence_counts=blueprint.source_evidence_counts,
            symbol=blueprint.symbol,
            timeframes=blueprint.timeframes,
            closed_candles_only=blueprint.closed_candles_only,
            max_gold_positions=blueprint.max_gold_positions,
            aggregate_risk_budget_bps=(blueprint.aggregate_risk_budget_bps),
            stage_risk_bps=blueprint.stage_risk_bps,
            release_controls_preserved=release_controls_preserved,
            safety_invariants_preserved=safety_preserved,
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
            runtime_statuses=runtime_statuses,
            no_real_or_external_effects=True,
            ready_for_offline_release_safety_audit=True,
        )
        return Phase16OfflineReleaseValidationDecision(
            True,
            report,
            (),
        )


def validate_phase16_offline_release_readiness(
    blueprint_decision: object,
) -> Phase16OfflineReleaseValidationDecision:
    """Validate the Phase 16 blueprint using deterministic fakes."""

    return Phase16OfflineReleaseValidator().validate(blueprint_decision)


__all__ = (
    "PHASE_16_OFFLINE_VALIDATION_SCHEMA_VERSION",
    "PHASE_16_OFFLINE_VALIDATION_STATUS",
    "PHASE_16_OFFLINE_VALIDATION_OUTCOME",
    "PHASE_16_OFFLINE_VALIDATION_SOURCE",
    "Phase16OfflineReleaseValidationResult",
    "Phase16OfflineReleaseValidationReport",
    "Phase16OfflineReleaseValidationDecision",
    "Phase16OfflineReleaseValidator",
    "validate_phase16_offline_release_readiness",
)
