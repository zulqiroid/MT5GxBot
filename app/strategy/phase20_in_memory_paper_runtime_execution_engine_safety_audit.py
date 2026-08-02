from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase20_in_memory_paper_runtime_execution_engine_blueprint import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES,
    build_phase20_in_memory_paper_runtime_execution_engine_blueprint,
)
from app.strategy.phase20_in_memory_paper_runtime_execution_engine_validation import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_STATUS,
    Phase20InMemoryPaperRuntimeEngineValidationReport,
    validate_phase20_in_memory_paper_runtime_execution_engine_blueprint,
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_SOURCE = (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_STATUS
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_STATUS = (
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ENGINE_SAFETY_AUDIT_PASSED"
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_NEXT_ALLOWED = (
    "FINAL_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ENGINE_HANDOFF"
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_FINDINGS = (
    "VALIDATION_LINEAGE_INTACT",
    "COMPONENT_CHAIN_DETERMINISTIC",
    "STATE_MACHINE_FAIL_CLOSED",
    "MARKET_SCOPE_RESTRICTED",
    "CLOSED_CANDLE_NO_LOOKAHEAD_ENFORCED",
    "CONSERVATIVE_FILL_POLICY_CONFIRMED",
    "POSITION_LIMIT_CONFIRMED",
    "RISK_LIMITS_CONFIRMED",
    "PROTECTION_AND_TERMINAL_FLATNESS_CONFIRMED",
    "IN_MEMORY_BOUNDARY_CONFIRMED",
    "REAL_AND_EXTERNAL_EFFECTS_BLOCKED",
    "PHASE_21_NOT_ADMITTED",
)


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineSafetyFinding:
    """One immutable safety finding for the Phase 20 in-memory engine."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_FINDINGS
        ):
            raise ValueError("Unknown Phase 20 engine-safety finding.")

        if not self.evidence:
            raise ValueError("Phase 20 engine-safety evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineSafetyAudit:
    """Fail-closed safety audit for the Phase 20 in-memory engine."""

    validation_id: str
    validation_digest: str
    findings: tuple[
        Phase20InMemoryPaperRuntimeEngineSafetyFinding,
        ...,
    ]
    schema_version: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_SCHEMA_VERSION
    )
    source: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_SOURCE
    )
    status: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_STATUS
    )
    next_allowed_step: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_NEXT_ALLOWED
    )
    in_memory_simulation_execution_admitted: bool = True
    engine_invocation_permitted: bool = False
    real_runtime_access_permitted: bool = False
    external_effects_permitted: bool = False
    phase21_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.validation_id or len(self.validation_digest) != 64:
            raise ValueError("Phase 20 validation lineage is invalid.")

        if self.schema_version != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_SCHEMA_VERSION
        ):
            raise ValueError("Phase 20 engine-safety schema is invalid.")

        if self.source != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_SOURCE
        ):
            raise ValueError("Phase 20 engine-safety source is invalid.")

        if self.status != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_STATUS
        ):
            raise ValueError("Phase 20 engine-safety status is invalid.")

        if self.next_allowed_step != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_NEXT_ALLOWED
        ):
            raise ValueError("Phase 20 engine-safety next step is invalid.")

        if tuple(item.name for item in self.findings) != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_FINDINGS
        ):
            raise ValueError("Phase 20 engine-safety findings are incomplete.")

        if not all(item.passed for item in self.findings):
            raise ValueError("Phase 20 engine-safety audit contains failures.")

        if not self.in_memory_simulation_execution_admitted:
            raise ValueError("Phase 20 simulation admission must be preserved.")

        if self.engine_invocation_permitted:
            raise ValueError("Phase 20.4 cannot invoke the engine.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 20.4 cannot permit real runtime access.")

        if self.external_effects_permitted:
            raise ValueError("Phase 20.4 cannot permit external effects.")

        if self.phase21_admitted:
            raise ValueError("Phase 21 cannot be admitted by Phase 20.4.")

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.findings)

    @property
    def audit_digest(self) -> str:
        """Hash bounded safety fields without recursive expansion."""

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
                str(self.in_memory_simulation_execution_admitted),
                str(self.engine_invocation_permitted),
                str(self.real_runtime_access_permitted),
                str(self.external_effects_permitted),
                str(self.phase21_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_20_IN_MEMORY_PAPER_RUNTIME_"
            "EXECUTION_ENGINE_SAFETY_AUDIT:"
            f"SHA256[{self.audit_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineSafetyAuditDecision:
    """Decision wrapper for the Phase 20 in-memory engine safety audit."""

    passed: bool
    reason: str
    audit: Phase20InMemoryPaperRuntimeEngineSafetyAudit | None

    @property
    def audit_required(
        self,
    ) -> Phase20InMemoryPaperRuntimeEngineSafetyAudit:
        if not self.passed or self.audit is None:
            raise RuntimeError("Phase 20 engine-safety audit is unavailable.")
        return self.audit


class Phase20InMemoryPaperRuntimeEngineSafetyAuditor:
    """Audit the validated in-memory engine without invoking it."""

    def audit(
        self,
        report: Phase20InMemoryPaperRuntimeEngineValidationReport,
    ) -> Phase20InMemoryPaperRuntimeEngineSafetyAuditDecision:
        blueprint = (
            build_phase20_in_memory_paper_runtime_execution_engine_blueprint()
            .blueprint_required
        )
        check_evidence = {
            item.name: item.evidence for item in report.checks
        }
        invariant_evidence = {
            item.name: item.evidence for item in blueprint.invariants
        }

        findings = (
            (
                "VALIDATION_LINEAGE_INTACT",
                report.blueprint_id == blueprint.blueprint_id
                and report.blueprint_digest == blueprint.blueprint_digest
                and report.status
                == PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_STATUS,
                report.validation_id,
            ),
            (
                "COMPONENT_CHAIN_DETERMINISTIC",
                tuple(item.name for item in blueprint.components)
                == PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS
                and tuple(item.order for item in blueprint.components)
                == tuple(range(1, 13)),
                check_evidence["COMPONENT_CHAIN_COMPLETE"],
            ),
            (
                "STATE_MACHINE_FAIL_CLOSED",
                blueprint.states
                == PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES
                and blueprint.states[-1] == "FLAT_TERMINATED",
                check_evidence["STATE_MACHINE_CONTRACT_EXACT"],
            ),
            (
                "MARKET_SCOPE_RESTRICTED",
                blueprint.symbol == "XAUUSD"
                and blueprint.timeframes == ("H4", "H1", "M15", "M5"),
                check_evidence["MARKET_SCOPE_EXACT"],
            ),
            (
                "CLOSED_CANDLE_NO_LOOKAHEAD_ENFORCED",
                invariant_evidence["CLOSED_CANDLES_ONLY"]
                == "signal_evaluation_policy=CANDLE_CLOSE_ONLY"
                and invariant_evidence["NO_LOOKAHEAD"]
                == "lookahead_permitted=False",
                check_evidence[
                    "CLOSED_CANDLE_AND_NO_LOOKAHEAD_ENFORCED"
                ],
            ),
            (
                "CONSERVATIVE_FILL_POLICY_CONFIRMED",
                blueprint.entry_fill_policy
                == "NEXT_EVENT_OPEN_AFTER_SIGNAL_CLOSE"
                and blueprint.same_bar_conflict_policy == "STOP_FIRST",
                check_evidence["FILL_POLICIES_CONSERVATIVE"],
            ),
            (
                "POSITION_LIMIT_CONFIRMED",
                blueprint.maximum_open_gold_positions == 1
                and invariant_evidence[
                    "ONE_OPEN_GOLD_POSITION_MAXIMUM"
                ]
                == "maximum_open_gold_positions=1",
                "maximum_open_gold_positions=1",
            ),
            (
                "RISK_LIMITS_CONFIRMED",
                blueprint.aggregate_risk_budget_bps == 50
                and blueprint.stage_risk_bps == (25, 25)
                and invariant_evidence["AGGREGATE_RISK_50_BPS"]
                == "aggregate_risk_budget_bps=50"
                and invariant_evidence["STAGED_RISK_25_PLUS_25_BPS"]
                == "stage_risk_bps=25,25",
                check_evidence["POSITION_AND_RISK_LIMITS_EXACT"],
            ),
            (
                "PROTECTION_AND_TERMINAL_FLATNESS_CONFIRMED",
                invariant_evidence["OCO_REQUIRED"] == "oco_required=True"
                and invariant_evidence["STOP_LOSS_REQUIRED"]
                == "stop_loss_required=True"
                and invariant_evidence["TERMINAL_FLAT_REQUIRED"]
                == "terminal_flat_required=True",
                check_evidence[
                    "PROTECTION_AND_TERMINAL_FLATNESS_PRESENT"
                ],
            ),
            (
                "IN_MEMORY_BOUNDARY_CONFIRMED",
                blueprint.in_memory_only
                and blueprint.simulation_execution_permitted
                and not blueprint.engine_invocation_permitted,
                (
                    f"in_memory_only={blueprint.in_memory_only};"
                    "simulation_execution_permitted="
                    f"{blueprint.simulation_execution_permitted};"
                    "engine_invocation_permitted="
                    f"{blueprint.engine_invocation_permitted}"
                ),
            ),
            (
                "REAL_AND_EXTERNAL_EFFECTS_BLOCKED",
                not blueprint.real_runtime_access_permitted
                and not blueprint.external_effects_permitted
                and invariant_evidence["NO_REAL_OR_EXTERNAL_EFFECTS"]
                == "real_or_external_effects_permitted=False",
                (
                    "real_runtime_access_permitted=False;"
                    "external_effects_permitted=False"
                ),
            ),
            (
                "PHASE_21_NOT_ADMITTED",
                not blueprint.phase21_admitted
                and not report.phase21_admitted,
                "phase21_admitted=False",
            ),
        )

        if not all(passed for _, passed, _ in findings):
            return Phase20InMemoryPaperRuntimeEngineSafetyAuditDecision(
                passed=False,
                reason="PHASE_20_ENGINE_SAFETY_AUDIT_FAILED",
                audit=None,
            )

        audit = Phase20InMemoryPaperRuntimeEngineSafetyAudit(
            validation_id=report.validation_id,
            validation_digest=report.validation_digest,
            findings=tuple(
                Phase20InMemoryPaperRuntimeEngineSafetyFinding(
                    name=name,
                    passed=passed,
                    evidence=evidence,
                )
                for name, passed, evidence in findings
            ),
        )

        return Phase20InMemoryPaperRuntimeEngineSafetyAuditDecision(
            passed=True,
            reason="PHASE_20_ENGINE_SAFETY_AUDIT_PASSED",
            audit=audit,
        )


def audit_phase20_in_memory_paper_runtime_execution_engine_safety(
) -> Phase20InMemoryPaperRuntimeEngineSafetyAuditDecision:
    """Audit the Phase 20 in-memory execution-engine blueprint."""

    report = (
        validate_phase20_in_memory_paper_runtime_execution_engine_blueprint()
        .report_required
    )
    return Phase20InMemoryPaperRuntimeEngineSafetyAuditor().audit(report)


__all__ = (
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_SCHEMA_VERSION",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_SOURCE",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_STATUS",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_NEXT_ALLOWED",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_FINDINGS",
    "Phase20InMemoryPaperRuntimeEngineSafetyFinding",
    "Phase20InMemoryPaperRuntimeEngineSafetyAudit",
    "Phase20InMemoryPaperRuntimeEngineSafetyAuditDecision",
    "Phase20InMemoryPaperRuntimeEngineSafetyAuditor",
    "audit_phase20_in_memory_paper_runtime_execution_engine_safety",
)
