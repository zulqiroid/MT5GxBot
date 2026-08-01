"""Phase 16 offline release-readiness safety audit.

Consumes the successful Step 16.3 deterministic offline validation decision
and produces an immutable safety-audit report for the planning-only release
readiness architecture.

No real .env read, MT5 import or initialization, terminal connection, broker
access, account read, order operation, external write, production activation,
or live execution is performed or admitted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_STATUS = "PASSED"
PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_HANDOFF_STATUS = "READY_FOR_PHASE_16_FINAL_HANDOFF"
PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SOURCE = (
    "DETERMINISTIC_OFFLINE_RELEASE_VALIDATION_EVIDENCE_ONLY"
)

PHASE_16_OFFLINE_RELEASE_SAFETY_FINDINGS = (
    "PHASE_15_FINAL_HANDOFF_LINEAGE_PRESERVED",
    "PHASE_16_ADMISSION_LINEAGE_PRESERVED",
    "OFFLINE_RELEASE_BLUEPRINT_LINEAGE_PRESERVED",
    "DETERMINISTIC_OFFLINE_VALIDATION_PASSED",
    "ALL_TWENTY_FIVE_RESULTS_FAKE_ONLY",
    "PHASE_15_RELEASE_BASELINE_COMMIT_PRESERVED",
    "PHASE_15_RELEASE_BASELINE_TAG_PRESERVED",
    "REAL_ENV_ACCESS_PROHIBITED",
    "PAPER_MODE_ONLY_PRESERVED",
    "BACKUP_AND_ROLLBACK_REQUIRED",
    "INCIDENT_RECOVERY_REQUIRED",
    "XAUUSD_CLOSED_CANDLE_SCOPE_PRESERVED",
    "ONE_POSITION_AND_50_BPS_RISK_PRESERVED",
    "OCO_STOP_LOSS_GUARDS_AND_FLAT_STATE_REQUIRED",
    "MARTINGALE_GRID_AND_NO_STOP_LOSS_PROHIBITED",
    "ALL_REAL_RUNTIME_AND_LIVE_EFFECTS_BLOCKED",
)


@dataclass(frozen=True, slots=True)
class Phase16OfflineReleaseSafetyFinding:
    """One immutable Phase 16 offline release safety finding."""

    ordinal: int
    name: str
    status: str
    evidence: str

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise ValueError("finding ordinal must be positive")
        if self.name not in PHASE_16_OFFLINE_RELEASE_SAFETY_FINDINGS:
            raise ValueError("unknown Phase 16 safety finding")
        if self.status != "PASSED":
            raise ValueError("safety finding must pass")
        if not self.evidence.strip():
            raise ValueError("safety finding evidence is required")

    @property
    def digest(self) -> str:
        material = "|".join(
            (
                str(self.ordinal),
                self.name,
                self.status,
                self.evidence,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase16OfflineReleaseSafetyAuditReport:
    """Immutable Phase 16 offline release safety-audit report."""

    validation_decision: object = field(repr=False)
    validation_report: object = field(repr=False)
    blueprint_decision: object = field(repr=False)
    blueprint: object = field(repr=False)
    admission_decision: object = field(repr=False)
    admission_permit: object = field(repr=False)
    phase15_final_handoff: object = field(repr=False)

    schema_version: str
    audit_status: str
    handoff_status: str
    audit_source: str

    findings: tuple[Phase16OfflineReleaseSafetyFinding, ...]
    finding_count: int

    component_results: int
    requirement_results: int
    track_results: int
    total_results: int

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

    release_controls_valid: bool
    safety_invariants_valid: bool
    lineage_preserved: bool
    real_env_protected: bool

    runtime_statuses: tuple[str, ...]
    no_real_effects: bool
    safety_audit_passed: bool
    ready_for_final_handoff: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SCHEMA_VERSION:
            raise ValueError("audit schema is inconsistent")
        if self.audit_status != PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_STATUS:
            raise ValueError("audit status is inconsistent")
        if self.handoff_status != PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_HANDOFF_STATUS:
            raise ValueError("audit handoff status is inconsistent")
        if self.audit_source != PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SOURCE:
            raise ValueError("audit source is inconsistent")

        if self.finding_count != 16 or len(self.findings) != 16:
            raise ValueError("exactly sixteen findings are required")
        if tuple(item.ordinal for item in self.findings) != tuple(range(1, 17)):
            raise ValueError("finding order is inconsistent")
        if tuple(item.name for item in self.findings) != (PHASE_16_OFFLINE_RELEASE_SAFETY_FINDINGS):
            raise ValueError("finding names are inconsistent")
        if not all(item.status == "PASSED" for item in self.findings):
            raise ValueError("all findings must pass")

        if (
            self.component_results,
            self.requirement_results,
            self.track_results,
            self.total_results,
        ) != (8, 12, 5, 25):
            raise ValueError("offline validation counts are inconsistent")

        if self.release_baseline_commit != "6ba3a00":
            raise ValueError("release baseline commit changed")
        if self.release_baseline_tag != "goldxbot-phase-15-complete":
            raise ValueError("release baseline tag changed")
        if self.source_validation_audit_counts != (8, 12, 20, 16):
            raise ValueError("source validation/audit counts changed")
        if self.source_evidence_counts != (10, 3, 10, 5, 32, 15, 16):
            raise ValueError("source evidence counts changed")

        if self.symbol != "XAUUSD":
            raise ValueError("audit is XAUUSD-only")
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
            self.release_controls_valid,
            self.safety_invariants_valid,
            self.lineage_preserved,
            self.real_env_protected,
            self.no_real_effects,
            self.safety_audit_passed,
            self.ready_for_final_handoff,
        )
        if not all(required):
            raise ValueError("audit lost a required invariant")
        if self.runtime_statuses != ("BLOCKED",) * 8:
            raise ValueError("all real runtime statuses must remain blocked")

    @property
    def audit_digest(self) -> str:
        validation_id = str(getattr(self.validation_report, "validation_id", ""))
        material = "|".join(
            (
                self.schema_version,
                validation_id,
                self.audit_status,
                self.handoff_status,
                self.audit_source,
                ",".join(item.digest for item in self.findings),
                str(self.component_results),
                str(self.requirement_results),
                str(self.track_results),
                str(self.total_results),
                self.release_baseline_commit,
                self.release_baseline_tag,
                ",".join(map(str, self.source_validation_audit_counts)),
                ",".join(map(str, self.source_evidence_counts)),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.no_real_effects),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return f"GOLDXBOT_PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT:SHA256[{self.audit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase16OfflineReleaseSafetyAuditDecision:
    """Allowed or blocked Phase 16 safety-audit decision."""

    is_allowed: bool
    report: Phase16OfflineReleaseSafetyAuditReport | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.report is None or self.blockers:
                raise ValueError("allowed safety-audit decision is inconsistent")
        elif self.report is not None or not self.blockers:
            raise ValueError("blocked safety-audit decision is inconsistent")

    @property
    def report_required(self) -> Phase16OfflineReleaseSafetyAuditReport:
        if self.report is None:
            raise RuntimeError("Phase 16 offline release safety audit is blocked.")
        return self.report


def _build_findings() -> tuple[Phase16OfflineReleaseSafetyFinding, ...]:
    evidence = (
        "Phase 15 final handoff object is preserved by identity.",
        "Phase 16 admission decision and permit are preserved by identity.",
        "Offline release blueprint decision and object are preserved.",
        "Step 16.3 validation status and outcome passed.",
        "Twenty-five ordered component, requirement, and track results are fake-only.",
        "Verified Phase 15 baseline commit 6ba3a00 is preserved.",
        "Annotated tag goldxbot-phase-15-complete is preserved.",
        "The architecture prohibits access to the real .env file.",
        "Only paper-mode planning is admitted.",
        "Backup and rollback procedures remain mandatory.",
        "Incident recovery procedures remain mandatory.",
        "XAUUSD with closed H4/H1/M15/M5 candles remains the only scope.",
        "One Gold position and 50 bps as 25+25 bps remain mandatory.",
        "OCO, broker stop-loss, guards, and terminal-flat state remain mandatory.",
        "Martingale, grid, and no-stop-loss behavior remain prohibited.",
        "All real runtime, production, and live effects remain blocked.",
    )
    return tuple(
        Phase16OfflineReleaseSafetyFinding(
            ordinal=index,
            name=name,
            status="PASSED",
            evidence=evidence[index - 1],
        )
        for index, name in enumerate(
            PHASE_16_OFFLINE_RELEASE_SAFETY_FINDINGS,
            start=1,
        )
    )


class Phase16OfflineReleaseSafetyAuditor:
    """Audits Step 16.3 deterministic offline release evidence."""

    def audit(
        self,
        validation_decision: object,
    ) -> Phase16OfflineReleaseSafetyAuditDecision:
        if validation_decision is None:
            return Phase16OfflineReleaseSafetyAuditDecision(
                False,
                None,
                ("phase16_validation_decision_missing",),
            )
        if getattr(validation_decision, "is_allowed", True) is not True:
            return Phase16OfflineReleaseSafetyAuditDecision(
                False,
                None,
                ("phase16_validation_decision_blocked",),
            )

        try:
            validation = validation_decision.report_required
            blueprint_decision = validation.blueprint_decision
            blueprint = validation.blueprint
            admission_decision = validation.admission_decision
            permit = validation.admission_permit
            phase15 = validation.phase15_final_handoff

            validation_valid = (
                validation.validation_status == "PASSED"
                and validation.validation_outcome == "READY_FOR_OFFLINE_RELEASE_SAFETY_AUDIT"
                and validation.validation_source == "DETERMINISTIC_IN_MEMORY_RELEASE_FAKE_ONLY"
                and validation.component_results == 8
                and validation.requirement_results == 12
                and validation.track_results == 5
                and validation.total_results == 25
                and validation.result_sequence_valid is True
                and validation.component_order_valid is True
                and validation.requirement_order_valid is True
                and validation.track_order_valid is True
                and validation.all_results_fake_only is True
                and validation.release_controls_preserved is True
                and validation.safety_invariants_preserved is True
                and validation.real_env_access_performed is False
                and validation.no_real_or_external_effects is True
                and validation.ready_for_offline_release_safety_audit is True
            )

            lineage_preserved = (
                validation_decision.report_required is validation
                and blueprint_decision.blueprint_required is blueprint
                and blueprint.admission_decision is admission_decision
                and blueprint.admission_permit is permit
                and blueprint.phase15_final_handoff is phase15
                and admission_decision.permit_required is permit
                and permit.source_bundle is phase15
                and validation.lineage_preserved is True
                and phase15.phase_status == "PHASE_15_COMPLETE"
                and phase15.handoff_status == "PHASE_15_EXTENSION_COMPLETE"
            )

            blueprint_valid = (
                blueprint.blueprint_status == "BLUEPRINT_READY"
                and blueprint.blueprint_mode == "OFFLINE_PLANNING_ONLY"
                and blueprint.next_allowed_step == "DETERMINISTIC_OFFLINE_RELEASE_VALIDATION"
                and blueprint.release_baseline_commit == "6ba3a00"
                and blueprint.release_baseline_tag == "goldxbot-phase-15-complete"
                and blueprint.component_count == 8
                and blueprint.requirement_count == 12
                and blueprint.release_readiness_track_count == 5
                and blueprint.execution_admitted is False
                and blueprint.real_env_access_allowed is False
                and blueprint.no_real_or_external_effects is True
            )

            release_controls_valid = (
                validation.release_controls_preserved is True
                and blueprint.deterministic_fakes_only is True
                and blueprint.paper_mode_only is True
                and blueprint.backup_and_rollback_required is True
                and blueprint.incident_recovery_required is True
                and blueprint.real_env_access_allowed is False
            )

            safety_valid = (
                validation.safety_invariants_preserved is True
                and validation.symbol == "XAUUSD"
                and validation.timeframes == ("H4", "H1", "M15", "M5")
                and validation.closed_candles_only is True
                and validation.max_gold_positions == 1
                and validation.aggregate_risk_budget_bps == 50
                and validation.stage_risk_bps == (25, 25)
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
            runtime_statuses = validation.runtime_statuses
            no_real_effects = (
                not any(forbidden_effects)
                and runtime_statuses == ("BLOCKED",) * 8
                and all(
                    result.fake_only and not result.real_effect_performed
                    for result in validation.results
                )
                and validation.no_real_or_external_effects is True
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase16OfflineReleaseSafetyAuditDecision(
                False,
                None,
                (f"phase16_validation_invalid:{type(error).__name__}",),
            )

        if not all(
            (
                validation_valid,
                lineage_preserved,
                blueprint_valid,
                release_controls_valid,
                safety_valid,
                no_real_effects,
            )
        ):
            return Phase16OfflineReleaseSafetyAuditDecision(
                False,
                None,
                ("phase16_offline_release_safety_contract_invalid",),
            )

        findings = _build_findings()
        report = Phase16OfflineReleaseSafetyAuditReport(
            validation_decision=validation_decision,
            validation_report=validation,
            blueprint_decision=blueprint_decision,
            blueprint=blueprint,
            admission_decision=admission_decision,
            admission_permit=permit,
            phase15_final_handoff=phase15,
            schema_version=(PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SCHEMA_VERSION),
            audit_status=PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_STATUS,
            handoff_status=(PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_HANDOFF_STATUS),
            audit_source=PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SOURCE,
            findings=findings,
            finding_count=len(findings),
            component_results=validation.component_results,
            requirement_results=validation.requirement_results,
            track_results=validation.track_results,
            total_results=validation.total_results,
            release_baseline_commit=validation.release_baseline_commit,
            release_baseline_tag=validation.release_baseline_tag,
            source_validation_audit_counts=(validation.source_validation_audit_counts),
            source_evidence_counts=validation.source_evidence_counts,
            symbol=validation.symbol,
            timeframes=validation.timeframes,
            closed_candles_only=validation.closed_candles_only,
            max_gold_positions=validation.max_gold_positions,
            aggregate_risk_budget_bps=(validation.aggregate_risk_budget_bps),
            stage_risk_bps=validation.stage_risk_bps,
            release_controls_valid=release_controls_valid,
            safety_invariants_valid=safety_valid,
            lineage_preserved=lineage_preserved,
            real_env_protected=(
                validation.real_env_access_performed is False
                and blueprint.real_env_access_allowed is False
            ),
            runtime_statuses=runtime_statuses,
            no_real_effects=no_real_effects,
            safety_audit_passed=True,
            ready_for_final_handoff=True,
        )
        return Phase16OfflineReleaseSafetyAuditDecision(
            True,
            report,
            (),
        )


def audit_phase16_offline_release_readiness_safety(
    validation_decision: object,
) -> Phase16OfflineReleaseSafetyAuditDecision:
    """Audit Step 16.3 deterministic offline release evidence."""

    return Phase16OfflineReleaseSafetyAuditor().audit(validation_decision)


__all__ = (
    "PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SCHEMA_VERSION",
    "PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_STATUS",
    "PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_HANDOFF_STATUS",
    "PHASE_16_OFFLINE_RELEASE_SAFETY_AUDIT_SOURCE",
    "PHASE_16_OFFLINE_RELEASE_SAFETY_FINDINGS",
    "Phase16OfflineReleaseSafetyFinding",
    "Phase16OfflineReleaseSafetyAuditReport",
    "Phase16OfflineReleaseSafetyAuditDecision",
    "Phase16OfflineReleaseSafetyAuditor",
    "audit_phase16_offline_release_readiness_safety",
)
