from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase18_paper_runtime_simulation_validation import (
    PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_CHECKS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_STATUS,
    Phase18PaperRuntimeSimulationValidationReport,
    validate_phase18_paper_runtime_simulation_blueprint,
)

PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_SOURCE = (
    PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_STATUS
)
PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_STATUS = (
    "PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_PASSED"
)
PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_HANDOFF_STATUS = (
    "READY_FOR_PHASE_18_FINAL_HANDOFF"
)

PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_FINDINGS = (
    "VALIDATION_LINEAGE_INTACT",
    "ALL_VALIDATION_CHECKS_PASSED",
    "PAPER_MODE_ENFORCED",
    "XAUUSD_SCOPE_ENFORCED",
    "CLOSED_CANDLES_ENFORCED",
    "ONE_POSITION_LIMIT_ENFORCED",
    "FIFTY_BPS_RISK_LIMIT_ENFORCED",
    "REAL_RUNTIME_ACCESS_BLOCKED",
    "SIMULATION_EXECUTION_STILL_BLOCKED",
    "PHASE_19_NOT_ADMITTED",
)


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationSafetyFinding:
    """One immutable Phase 18 paper-runtime safety finding."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_FINDINGS:
            raise ValueError("Unknown Phase 18 safety finding.")

        if not self.evidence:
            raise ValueError("Phase 18 safety evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationSafetyAuditReport:
    """Fail-closed Phase 18 paper-runtime simulation safety report."""

    validation_id: str
    validation_digest: str
    findings: tuple[Phase18PaperRuntimeSimulationSafetyFinding, ...]
    schema_version: str = (
        PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION
    )
    source: str = PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_SOURCE
    status: str = PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_STATUS
    handoff_status: str = (
        PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_HANDOFF_STATUS
    )
    simulation_execution_permitted: bool = False
    real_runtime_access_permitted: bool = False
    phase19_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.validation_id or len(self.validation_digest) != 64:
            raise ValueError("Phase 18 validation lineage is invalid.")

        if self.schema_version != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION
        ):
            raise ValueError("Phase 18 safety schema version is invalid.")

        if self.source != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_SOURCE
        ):
            raise ValueError("Phase 18 safety source is invalid.")

        if self.status != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_STATUS
        ):
            raise ValueError("Phase 18 safety status is invalid.")

        if self.handoff_status != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_HANDOFF_STATUS
        ):
            raise ValueError("Phase 18 safety handoff status is invalid.")

        if tuple(item.name for item in self.findings) != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_FINDINGS
        ):
            raise ValueError("Phase 18 safety finding set is incomplete.")

        if not all(item.passed for item in self.findings):
            raise ValueError("Phase 18 safety audit contains failed findings.")

        if self.simulation_execution_permitted:
            raise ValueError("Phase 18.4 cannot permit simulation execution.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 18.4 cannot permit real runtime access.")

        if self.phase19_admitted:
            raise ValueError("Phase 19 cannot be admitted by Phase 18.4.")

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.findings)

    @property
    def audit_digest(self) -> str:
        """Hash bounded fields without recursive lineage expansion."""

        material = "|".join(
            (
                self.validation_digest,
                self.schema_version,
                self.source,
                self.status,
                self.handoff_status,
                ",".join(
                    f"{item.name}:{item.passed}:{item.evidence}"
                    for item in self.findings
                ),
                str(self.simulation_execution_permitted),
                str(self.real_runtime_access_permitted),
                str(self.phase19_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT:"
            f"SHA256[{self.audit_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationSafetyAuditDecision:
    """Decision wrapper for the Phase 18 simulation safety audit."""

    passed: bool
    reason: str
    report: Phase18PaperRuntimeSimulationSafetyAuditReport | None

    @property
    def report_required(self) -> Phase18PaperRuntimeSimulationSafetyAuditReport:
        if not self.passed or self.report is None:
            raise RuntimeError("Phase 18 safety audit report is unavailable.")
        return self.report


class Phase18PaperRuntimeSimulationSafetyAuditor:
    """Audit the validated Phase 18 blueprint without runtime effects."""

    def audit(
        self,
        validation: Phase18PaperRuntimeSimulationValidationReport,
    ) -> Phase18PaperRuntimeSimulationSafetyAuditDecision:
        validation_evidence = {
            item.name: item.evidence for item in validation.results
        }

        checks = (
            (
                "VALIDATION_LINEAGE_INTACT",
                bool(validation.validation_id)
                and len(validation.validation_digest) == 64,
                validation.validation_id,
            ),
            (
                "ALL_VALIDATION_CHECKS_PASSED",
                validation.result_count
                == len(PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_CHECKS)
                and validation.passed_count == validation.result_count,
                (
                    f"passed={validation.passed_count};"
                    f"total={validation.result_count}"
                ),
            ),
            (
                "PAPER_MODE_ENFORCED",
                "mode=PAPER" in validation_evidence["MARKET_SCOPE_EXACT"],
                validation_evidence["MARKET_SCOPE_EXACT"],
            ),
            (
                "XAUUSD_SCOPE_ENFORCED",
                "symbol=XAUUSD" in validation_evidence["MARKET_SCOPE_EXACT"],
                validation_evidence["MARKET_SCOPE_EXACT"],
            ),
            (
                "CLOSED_CANDLES_ENFORCED",
                validation_evidence["CLOSED_CANDLES_REQUIRED"]
                == "closed_candles_only=True",
                validation_evidence["CLOSED_CANDLES_REQUIRED"],
            ),
            (
                "ONE_POSITION_LIMIT_ENFORCED",
                validation_evidence["POSITION_LIMIT_EXACT"]
                == "maximum_open_gold_positions=1",
                validation_evidence["POSITION_LIMIT_EXACT"],
            ),
            (
                "FIFTY_BPS_RISK_LIMIT_ENFORCED",
                validation_evidence["RISK_BUDGET_EXACT"]
                == "aggregate_bps=50;stage_bps=(25, 25)",
                validation_evidence["RISK_BUDGET_EXACT"],
            ),
            (
                "REAL_RUNTIME_ACCESS_BLOCKED",
                all(
                    token in validation_evidence[
                        "REAL_RUNTIME_STATUSES_BLOCKED"
                    ]
                    for token in (
                        "MT5_INITIALIZATION_BLOCKED",
                        "BROKER_WRITE_BLOCKED",
                        "LIVE_TRADING_BLOCKED",
                    )
                ),
                validation_evidence["REAL_RUNTIME_STATUSES_BLOCKED"],
            ),
            (
                "SIMULATION_EXECUTION_STILL_BLOCKED",
                validation_evidence["SIMULATION_EXECUTION_BLOCKED"]
                == "simulation_execution_permitted=False",
                validation_evidence["SIMULATION_EXECUTION_BLOCKED"],
            ),
            (
                "PHASE_19_NOT_ADMITTED",
                validation_evidence["PHASE_19_BLOCKED"]
                == "phase19_admitted=False",
                validation_evidence["PHASE_19_BLOCKED"],
            ),
        )

        if not all(passed for _, passed, _ in checks):
            return Phase18PaperRuntimeSimulationSafetyAuditDecision(
                passed=False,
                reason="PHASE_18_SIMULATION_SAFETY_AUDIT_FAILED",
                report=None,
            )

        findings = tuple(
            Phase18PaperRuntimeSimulationSafetyFinding(
                name=name,
                passed=passed,
                evidence=evidence,
            )
            for name, passed, evidence in checks
        )

        report = Phase18PaperRuntimeSimulationSafetyAuditReport(
            validation_id=validation.validation_id,
            validation_digest=validation.validation_digest,
            findings=findings,
        )

        return Phase18PaperRuntimeSimulationSafetyAuditDecision(
            passed=True,
            reason="PHASE_18_SIMULATION_SAFETY_AUDIT_PASSED",
            report=report,
        )


def audit_phase18_paper_runtime_simulation_safety(
) -> Phase18PaperRuntimeSimulationSafetyAuditDecision:
    """Run the fail-closed Phase 18 simulation safety audit."""

    validation = (
        validate_phase18_paper_runtime_simulation_blueprint().report_required
    )
    return Phase18PaperRuntimeSimulationSafetyAuditor().audit(validation)


__all__ = (
    "PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_SOURCE",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_STATUS",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_HANDOFF_STATUS",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_FINDINGS",
    "Phase18PaperRuntimeSimulationSafetyFinding",
    "Phase18PaperRuntimeSimulationSafetyAuditReport",
    "Phase18PaperRuntimeSimulationSafetyAuditDecision",
    "Phase18PaperRuntimeSimulationSafetyAuditor",
    "audit_phase18_paper_runtime_simulation_safety",
)
