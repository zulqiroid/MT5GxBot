from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase19_paper_runtime_simulation_execution_blueprint import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS,
    build_phase19_paper_runtime_simulation_execution_blueprint,
)
from app.strategy.phase19_paper_runtime_simulation_execution_blueprint_validation import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_STATUS,
    Phase19PaperRuntimeSimulationExecutionValidationReport,
    validate_phase19_paper_runtime_simulation_execution_blueprint,
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_SOURCE = (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_STATUS
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_STATUS = (
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_PASSED"
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_NEXT_ALLOWED = (
    "FINAL_PAPER_RUNTIME_SIMULATION_EXECUTION_HANDOFF"
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_FINDINGS = (
    "VALIDATION_LINEAGE_INTACT",
    "DETERMINISTIC_COMPONENT_CHAIN_CONFIRMED",
    "MARKET_SCOPE_RESTRICTED",
    "CLOSED_CANDLE_GATE_CONFIRMED",
    "POSITION_LIMIT_CONFIRMED",
    "RISK_LIMITS_CONFIRMED",
    "PROTECTION_AND_FLATNESS_CONFIRMED",
    "UNSAFE_POSITIONING_PATTERNS_FORBIDDEN",
    "REAL_AND_EXTERNAL_EFFECTS_BLOCKED",
    "PHASE_20_NOT_ADMITTED",
)


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionSafetyFinding:
    """One immutable Phase 19 execution-safety finding."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_FINDINGS
        ):
            raise ValueError("Unknown Phase 19 execution-safety finding.")

        if not self.evidence:
            raise ValueError("Phase 19 safety evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionSafetyAudit:
    """Fail-closed Phase 19 paper-runtime execution-safety audit."""

    validation_id: str
    validation_digest: str
    findings: tuple[
        Phase19PaperRuntimeSimulationExecutionSafetyFinding,
        ...,
    ]
    schema_version: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_SCHEMA_VERSION
    )
    source: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_SOURCE
    )
    status: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_STATUS
    )
    next_allowed_step: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_NEXT_ALLOWED
    )
    simulation_execution_permitted: bool = False
    real_runtime_access_permitted: bool = False
    external_effects_permitted: bool = False
    phase20_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.validation_id or len(self.validation_digest) != 64:
            raise ValueError("Phase 19 validation lineage is invalid.")

        if self.schema_version != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_SCHEMA_VERSION
        ):
            raise ValueError("Phase 19 safety-audit schema is invalid.")

        if self.source != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_SOURCE
        ):
            raise ValueError("Phase 19 safety-audit source is invalid.")

        if self.status != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_STATUS
        ):
            raise ValueError("Phase 19 safety-audit status is invalid.")

        if self.next_allowed_step != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_NEXT_ALLOWED
        ):
            raise ValueError("Phase 19 safety-audit next step is invalid.")

        if tuple(item.name for item in self.findings) != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_FINDINGS
        ):
            raise ValueError("Phase 19 safety findings are incomplete.")

        if not all(item.passed for item in self.findings):
            raise ValueError("Phase 19 safety audit contains failed findings.")

        if self.simulation_execution_permitted:
            raise ValueError("Phase 19.4 cannot permit simulation execution.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 19.4 cannot permit real runtime access.")

        if self.external_effects_permitted:
            raise ValueError("Phase 19.4 cannot permit external effects.")

        if self.phase20_admitted:
            raise ValueError("Phase 20 cannot be admitted by Phase 19.4.")

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.findings)

    @property
    def audit_digest(self) -> str:
        """Hash bounded audit fields without recursive expansion."""

        material = "|".join(
            (
                self.validation_digest,
                self.schema_version,
                self.source,
                self.status,
                self.next_allowed_step,
                ",".join(
                    f"{item.name}:{item.passed}:{item.evidence}"
                    for item in self.findings
                ),
                str(self.simulation_execution_permitted),
                str(self.real_runtime_access_permitted),
                str(self.external_effects_permitted),
                str(self.phase20_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_19_PAPER_RUNTIME_SIMULATION_"
            "EXECUTION_SAFETY_AUDIT:"
            f"SHA256[{self.audit_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionSafetyAuditDecision:
    """Decision wrapper for the Phase 19 execution-safety audit."""

    passed: bool
    reason: str
    audit: Phase19PaperRuntimeSimulationExecutionSafetyAudit | None

    @property
    def audit_required(
        self,
    ) -> Phase19PaperRuntimeSimulationExecutionSafetyAudit:
        if not self.passed or self.audit is None:
            raise RuntimeError("Phase 19 execution-safety audit is unavailable.")
        return self.audit


class Phase19PaperRuntimeSimulationExecutionSafetyAuditor:
    """Audit the validated blueprint without executing a simulation."""

    def audit(
        self,
        report: Phase19PaperRuntimeSimulationExecutionValidationReport,
    ) -> Phase19PaperRuntimeSimulationExecutionSafetyAuditDecision:
        blueprint = (
            build_phase19_paper_runtime_simulation_execution_blueprint()
            .blueprint_required
        )
        requirement_evidence = {
            item.name: item.evidence for item in blueprint.requirements
        }
        validation_evidence = {
            item.name: item.evidence for item in report.checks
        }

        findings = (
            (
                "VALIDATION_LINEAGE_INTACT",
                report.blueprint_id == blueprint.blueprint_id
                and report.blueprint_digest == blueprint.blueprint_digest
                and report.status
                == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_STATUS,
                report.validation_id,
            ),
            (
                "DETERMINISTIC_COMPONENT_CHAIN_CONFIRMED",
                tuple(item.name for item in blueprint.components)
                == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS
                and tuple(item.order for item in blueprint.components)
                == tuple(range(1, 11)),
                validation_evidence["COMPONENT_CONTRACT_COMPLETE"],
            ),
            (
                "MARKET_SCOPE_RESTRICTED",
                blueprint.symbol == "XAUUSD"
                and blueprint.timeframes == ("H4", "H1", "M15", "M5"),
                validation_evidence["MARKET_SCOPE_EXACT"],
            ),
            (
                "CLOSED_CANDLE_GATE_CONFIRMED",
                blueprint.closed_candles_only
                and requirement_evidence["CLOSED_CANDLES_ONLY"]
                == "closed_candles_only=True",
                requirement_evidence["CLOSED_CANDLES_ONLY"],
            ),
            (
                "POSITION_LIMIT_CONFIRMED",
                blueprint.maximum_open_gold_positions == 1
                and requirement_evidence[
                    "ONE_OPEN_GOLD_POSITION_MAXIMUM"
                ]
                == "maximum_open_gold_positions=1",
                requirement_evidence[
                    "ONE_OPEN_GOLD_POSITION_MAXIMUM"
                ],
            ),
            (
                "RISK_LIMITS_CONFIRMED",
                blueprint.aggregate_risk_budget_bps == 50
                and blueprint.stage_risk_bps == (25, 25)
                and requirement_evidence["AGGREGATE_RISK_50_BPS"]
                == "aggregate_risk_budget_bps=50"
                and requirement_evidence["STAGED_RISK_25_PLUS_25_BPS"]
                == "stage_risk_bps=25,25",
                validation_evidence["POSITION_AND_RISK_LIMITS_EXACT"],
            ),
            (
                "PROTECTION_AND_FLATNESS_CONFIRMED",
                requirement_evidence["OCO_REQUIRED"] == "oco_required=True"
                and requirement_evidence["STOP_LOSS_REQUIRED"]
                == "stop_loss_required=True"
                and requirement_evidence["TERMINAL_FLAT_REQUIRED"]
                == "terminal_flat_required=True",
                (
                    f'{requirement_evidence["OCO_REQUIRED"]};'
                    f'{requirement_evidence["STOP_LOSS_REQUIRED"]};'
                    f'{requirement_evidence["TERMINAL_FLAT_REQUIRED"]}'
                ),
            ),
            (
                "UNSAFE_POSITIONING_PATTERNS_FORBIDDEN",
                requirement_evidence[
                    "MARTINGALE_GRID_NO_SL_FORBIDDEN"
                ]
                == "martingale=False;grid=False;no_sl=False",
                requirement_evidence[
                    "MARTINGALE_GRID_NO_SL_FORBIDDEN"
                ],
            ),
            (
                "REAL_AND_EXTERNAL_EFFECTS_BLOCKED",
                not blueprint.simulation_execution_permitted
                and not blueprint.real_runtime_access_permitted
                and requirement_evidence["NO_REAL_OR_EXTERNAL_EFFECTS"]
                == "real_or_external_effects_permitted=False",
                (
                    "simulation_execution_permitted=False;"
                    "real_runtime_access_permitted=False;"
                    "external_effects_permitted=False"
                ),
            ),
            (
                "PHASE_20_NOT_ADMITTED",
                not blueprint.phase20_admitted
                and not report.phase20_admitted,
                "phase20_admitted=False",
            ),
        )

        if not all(passed for _, passed, _ in findings):
            return Phase19PaperRuntimeSimulationExecutionSafetyAuditDecision(
                passed=False,
                reason="PHASE_19_EXECUTION_SAFETY_AUDIT_FAILED",
                audit=None,
            )

        audit = Phase19PaperRuntimeSimulationExecutionSafetyAudit(
            validation_id=report.validation_id,
            validation_digest=report.validation_digest,
            findings=tuple(
                Phase19PaperRuntimeSimulationExecutionSafetyFinding(
                    name=name,
                    passed=passed,
                    evidence=evidence,
                )
                for name, passed, evidence in findings
            ),
        )

        return Phase19PaperRuntimeSimulationExecutionSafetyAuditDecision(
            passed=True,
            reason="PHASE_19_EXECUTION_SAFETY_AUDIT_PASSED",
            audit=audit,
        )


def audit_phase19_paper_runtime_simulation_execution_safety(
) -> Phase19PaperRuntimeSimulationExecutionSafetyAuditDecision:
    """Audit the validated Phase 19 execution blueprint."""

    report = (
        validate_phase19_paper_runtime_simulation_execution_blueprint()
        .report_required
    )
    return Phase19PaperRuntimeSimulationExecutionSafetyAuditor().audit(report)


__all__ = (
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_SCHEMA_VERSION",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_SOURCE",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_STATUS",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_NEXT_ALLOWED",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_FINDINGS",
    "Phase19PaperRuntimeSimulationExecutionSafetyFinding",
    "Phase19PaperRuntimeSimulationExecutionSafetyAudit",
    "Phase19PaperRuntimeSimulationExecutionSafetyAuditDecision",
    "Phase19PaperRuntimeSimulationExecutionSafetyAuditor",
    "audit_phase19_paper_runtime_simulation_execution_safety",
)
