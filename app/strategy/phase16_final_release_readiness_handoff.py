"""Phase 16 final offline release-readiness handoff.

Consumes the successful Step 16.4 offline release safety-audit decision and
closes the Phase 16 planning-only roadmap with an immutable final handoff.

This handoff is not a production, broker, terminal, or live-trading
authorization. Real .env access, MT5 import and initialization, terminal
connection, broker access, real account reads, order operations, external
writes, production activation, and live execution remain blocked.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_16_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_16_FINAL_STATUS = "PHASE_16_COMPLETE"
PHASE_16_FINAL_HANDOFF_STATUS = "PHASE_16_OFFLINE_RELEASE_READINESS_COMPLETE"
PHASE_16_FINAL_HANDOFF_SOURCE = "PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_ONLY"
PHASE_16_FINAL_RELEASE_DECISION = "OFFLINE_RELEASE_READINESS_ESTABLISHED"
PHASE_16_FINAL_NEXT_PHASE_STATUS = "NOT_DEFINED"
PHASE_16_FINAL_BLOCKED_STATUS = "BLOCKED"


@dataclass(frozen=True, slots=True)
class Phase16FinalReleaseReadinessHandoff:
    """Immutable final handoff for Phase 16 offline release readiness."""

    safety_audit_decision: object = field(repr=False)
    safety_audit_report: object = field(repr=False)
    validation_decision: object = field(repr=False)
    validation_report: object = field(repr=False)
    blueprint_decision: object = field(repr=False)
    blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase15_final_handoff: object = field(repr=False)

    schema_version: str
    phase_status: str
    handoff_status: str
    handoff_source: str
    release_decision: str

    release_baseline_commit: str
    release_baseline_tag: str

    component_results: int
    requirement_results: int
    track_results: int
    total_results: int
    safety_finding_count: int

    source_validation_audit_counts: tuple[int, ...]
    source_evidence_counts: tuple[int, ...]

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    planning_admitted: bool
    execution_admitted: bool
    release_controls_preserved: bool
    safety_invariants_preserved: bool
    lineage_preserved: bool
    real_env_protected: bool

    phase16_roadmap_complete: bool
    next_phase_status: str
    phase17_admitted: bool

    runtime_statuses: tuple[str, ...]
    no_real_or_external_effects: bool
    final_handoff_ready: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_16_FINAL_HANDOFF_SCHEMA_VERSION:
            raise ValueError("final handoff schema is inconsistent")
        if self.phase_status != PHASE_16_FINAL_STATUS:
            raise ValueError("Phase 16 status is inconsistent")
        if self.handoff_status != PHASE_16_FINAL_HANDOFF_STATUS:
            raise ValueError("final handoff status is inconsistent")
        if self.handoff_source != PHASE_16_FINAL_HANDOFF_SOURCE:
            raise ValueError("final handoff source is inconsistent")
        if self.release_decision != PHASE_16_FINAL_RELEASE_DECISION:
            raise ValueError("release decision is inconsistent")

        if self.release_baseline_commit != "6ba3a00":
            raise ValueError("release baseline commit changed")
        if self.release_baseline_tag != "goldxbot-phase-15-complete":
            raise ValueError("release baseline tag changed")

        if (
            self.component_results,
            self.requirement_results,
            self.track_results,
            self.total_results,
            self.safety_finding_count,
        ) != (8, 12, 5, 25, 16):
            raise ValueError("Phase 16 evidence counts are inconsistent")
        if self.source_validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("source validation/audit counts changed")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence counts changed")

        if self.symbol != "XAUUSD":
            raise ValueError("final handoff is XAUUSD-only")
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

        if self.planning_admitted is not True or self.execution_admitted:
            raise ValueError("Phase 16 must remain planning-only")
        required = (
            self.release_controls_preserved,
            self.safety_invariants_preserved,
            self.lineage_preserved,
            self.real_env_protected,
            self.phase16_roadmap_complete,
            self.no_real_or_external_effects,
            self.final_handoff_ready,
        )
        if not all(required):
            raise ValueError("final handoff lost a required invariant")

        if self.next_phase_status != PHASE_16_FINAL_NEXT_PHASE_STATUS:
            raise ValueError("next phase must remain undefined")
        if self.phase17_admitted:
            raise ValueError("Phase 17 must not be admitted")
        if self.runtime_statuses != (PHASE_16_FINAL_BLOCKED_STATUS,) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def handoff_digest(self) -> str:
        audit_id = str(getattr(self.safety_audit_report, "audit_id", ""))
        material = "|".join(
            (
                self.schema_version,
                audit_id,
                self.phase_status,
                self.handoff_status,
                self.handoff_source,
                self.release_decision,
                self.release_baseline_commit,
                self.release_baseline_tag,
                str(self.component_results),
                str(self.requirement_results),
                str(self.track_results),
                str(self.total_results),
                str(self.safety_finding_count),
                ",".join(map(str, self.source_validation_audit_counts)),
                ",".join(map(str, self.source_evidence_counts)),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                self.next_phase_status,
                str(self.phase17_admitted),
                ",".join(self.runtime_statuses),
                str(self.no_real_or_external_effects),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_16_FINAL_OFFLINE_RELEASE_READINESS_HANDOFF:"
            f"SHA256[{self.handoff_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase16FinalReleaseReadinessHandoffDecision:
    """Allowed or blocked Phase 16 final-handoff decision."""

    is_allowed: bool
    handoff: Phase16FinalReleaseReadinessHandoff | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.handoff is None or self.blockers:
                raise ValueError("allowed final-handoff decision is inconsistent")
        elif self.handoff is not None or not self.blockers:
            raise ValueError("blocked final-handoff decision is inconsistent")

    @property
    def handoff_required(self) -> Phase16FinalReleaseReadinessHandoff:
        if self.handoff is None:
            raise RuntimeError("Phase 16 final offline release-readiness handoff is blocked.")
        return self.handoff


class Phase16FinalReleaseReadinessHandoffGate:
    """Closes Phase 16 from audited offline release-readiness evidence."""

    def finalize(
        self,
        safety_audit_decision: object,
    ) -> Phase16FinalReleaseReadinessHandoffDecision:
        if safety_audit_decision is None:
            return Phase16FinalReleaseReadinessHandoffDecision(
                False,
                None,
                ("phase16_safety_audit_decision_missing",),
            )
        if getattr(safety_audit_decision, "is_allowed", True) is not True:
            return Phase16FinalReleaseReadinessHandoffDecision(
                False,
                None,
                ("phase16_safety_audit_decision_blocked",),
            )

        try:
            audit = safety_audit_decision.report_required
            validation_decision = audit.validation_decision
            validation = audit.validation_report
            blueprint_decision = audit.blueprint_decision
            blueprint = audit.blueprint
            admission_decision = audit.admission_decision
            permit = audit.admission_permit
            phase15 = audit.phase15_final_handoff

            audit_valid = (
                audit.audit_status == "PASSED"
                and audit.handoff_status == "READY_FOR_PHASE_16_FINAL_HANDOFF"
                and audit.audit_source == "DETERMINISTIC_OFFLINE_RELEASE_VALIDATION_EVIDENCE_ONLY"
                and audit.finding_count == 16
                and all(finding.status == "PASSED" for finding in audit.findings)
                and audit.component_results == 8
                and audit.requirement_results == 12
                and audit.track_results == 5
                and audit.total_results == 25
                and audit.release_baseline_commit == "6ba3a00"
                and audit.release_baseline_tag == "goldxbot-phase-15-complete"
                and audit.release_controls_valid is True
                and audit.safety_invariants_valid is True
                and audit.real_env_protected is True
                and audit.no_real_effects is True
                and audit.safety_audit_passed is True
                and audit.ready_for_final_handoff is True
            )

            lineage_preserved = (
                safety_audit_decision.report_required is audit
                and validation_decision.report_required is validation
                and blueprint_decision.blueprint_required is blueprint
                and blueprint.admission_decision is admission_decision
                and blueprint.admission_permit is permit
                and blueprint.phase15_final_handoff is phase15
                and admission_decision.permit_required is permit
                and permit.source_bundle is phase15
                and audit.lineage_preserved is True
                and validation.lineage_preserved is True
                and phase15.phase_status == "PHASE_15_COMPLETE"
                and phase15.handoff_status == "PHASE_15_EXTENSION_COMPLETE"
            )

            evidence_preserved = (
                audit.source_validation_audit_counts == (8, 12, 20, 16)
                and audit.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)
                and validation.validation_status == "PASSED"
                and validation.total_results == 25
                and blueprint.blueprint_status == "BLUEPRINT_READY"
                and blueprint.component_count == 8
                and blueprint.requirement_count == 12
                and blueprint.release_readiness_track_count == 5
                and permit.phase16_planning_admitted is True
                and permit.phase16_execution_admitted is False
            )

            forbidden_effects = (
                validation.real_env_access_performed,
                validation.real_preflight_executed,
                validation.real_mt5_imported,
                validation.real_mt5_initialized,
                validation.real_terminal_connected,
                validation.real_broker_access_performed,
                validation.real_account_read_performed,
                validation.order_check_invoked,
                validation.order_send_invoked,
                validation.external_state_written,
                validation.production_activated,
                validation.live_order_submitted,
            )
            runtime_statuses = audit.runtime_statuses
            no_real_effects = (
                not any(forbidden_effects)
                and runtime_statuses == ("BLOCKED",) * 8
                and validation.no_real_or_external_effects is True
                and audit.no_real_effects is True
                and blueprint.no_real_or_external_effects is True
                and permit.no_real_or_external_effects is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase16FinalReleaseReadinessHandoffDecision(
                False,
                None,
                (f"phase16_safety_audit_invalid:{type(error).__name__}",),
            )

        if not all(
            (
                audit_valid,
                lineage_preserved,
                evidence_preserved,
                no_real_effects,
            )
        ):
            return Phase16FinalReleaseReadinessHandoffDecision(
                False,
                None,
                ("phase16_final_handoff_contract_invalid",),
            )

        handoff = Phase16FinalReleaseReadinessHandoff(
            safety_audit_decision=safety_audit_decision,
            safety_audit_report=audit,
            validation_decision=validation_decision,
            validation_report=validation,
            blueprint_decision=blueprint_decision,
            blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=permit,
            phase15_final_handoff=phase15,
            schema_version=PHASE_16_FINAL_HANDOFF_SCHEMA_VERSION,
            phase_status=PHASE_16_FINAL_STATUS,
            handoff_status=PHASE_16_FINAL_HANDOFF_STATUS,
            handoff_source=PHASE_16_FINAL_HANDOFF_SOURCE,
            release_decision=PHASE_16_FINAL_RELEASE_DECISION,
            release_baseline_commit=audit.release_baseline_commit,
            release_baseline_tag=audit.release_baseline_tag,
            component_results=audit.component_results,
            requirement_results=audit.requirement_results,
            track_results=audit.track_results,
            total_results=audit.total_results,
            safety_finding_count=audit.finding_count,
            source_validation_audit_counts=(audit.source_validation_audit_counts),
            source_evidence_counts=audit.source_evidence_counts,
            symbol=audit.symbol,
            timeframes=audit.timeframes,
            closed_candles_only=audit.closed_candles_only,
            max_gold_positions=audit.max_gold_positions,
            aggregate_risk_budget_bps=audit.aggregate_risk_budget_bps,
            stage_risk_bps=audit.stage_risk_bps,
            planning_admitted=True,
            execution_admitted=False,
            release_controls_preserved=audit.release_controls_valid,
            safety_invariants_preserved=audit.safety_invariants_valid,
            lineage_preserved=lineage_preserved,
            real_env_protected=audit.real_env_protected,
            phase16_roadmap_complete=True,
            next_phase_status=PHASE_16_FINAL_NEXT_PHASE_STATUS,
            phase17_admitted=False,
            runtime_statuses=runtime_statuses,
            no_real_or_external_effects=no_real_effects,
            final_handoff_ready=True,
        )
        return Phase16FinalReleaseReadinessHandoffDecision(
            True,
            handoff,
            (),
        )


def finalize_phase16_offline_release_readiness(
    safety_audit_decision: object,
) -> Phase16FinalReleaseReadinessHandoffDecision:
    """Finalize Phase 16 from audited offline release-readiness evidence."""

    return Phase16FinalReleaseReadinessHandoffGate().finalize(safety_audit_decision)


__all__ = (
    "PHASE_16_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_16_FINAL_STATUS",
    "PHASE_16_FINAL_HANDOFF_STATUS",
    "PHASE_16_FINAL_HANDOFF_SOURCE",
    "PHASE_16_FINAL_RELEASE_DECISION",
    "PHASE_16_FINAL_NEXT_PHASE_STATUS",
    "PHASE_16_FINAL_BLOCKED_STATUS",
    "Phase16FinalReleaseReadinessHandoff",
    "Phase16FinalReleaseReadinessHandoffDecision",
    "Phase16FinalReleaseReadinessHandoffGate",
    "finalize_phase16_offline_release_readiness",
)
