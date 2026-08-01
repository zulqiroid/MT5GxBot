from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase18_paper_runtime_simulation_blueprint import (
    PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES,
    PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_STATUS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS,
    Phase18PaperRuntimeSimulationBlueprint,
    build_phase18_paper_runtime_simulation_blueprint,
)

PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_SCHEMA_VERSION = "1.0"
PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_SOURCE = (
    PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_STATUS
)
PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_STATUS = (
    "PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_PASSED"
)
PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_OUTCOME = (
    "DETERMINISTIC_PAPER_RUNTIME_SIMULATION_BLUEPRINT_VALID"
)
PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_NEXT_ALLOWED = (
    "PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT"
)

PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_CHECKS = (
    "BLUEPRINT_STATUS_VALID",
    "COMPONENT_CONTRACT_COMPLETE",
    "REQUIREMENT_CONTRACT_COMPLETE",
    "MARKET_SCOPE_EXACT",
    "CLOSED_CANDLES_REQUIRED",
    "POSITION_LIMIT_EXACT",
    "RISK_BUDGET_EXACT",
    "REAL_RUNTIME_STATUSES_BLOCKED",
    "SIMULATION_EXECUTION_BLOCKED",
    "PHASE_19_BLOCKED",
)


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationValidationResult:
    """One deterministic Phase 18 validation result."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_CHECKS:
            raise ValueError("Unknown Phase 18 validation check.")

        if not self.evidence:
            raise ValueError("Phase 18 validation evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationValidationReport:
    """Immutable report for the Phase 18 blueprint validation."""

    blueprint_id: str
    blueprint_digest: str
    results: tuple[Phase18PaperRuntimeSimulationValidationResult, ...]
    schema_version: str = (
        PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_SCHEMA_VERSION
    )
    source: str = PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_SOURCE
    status: str = PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_STATUS
    outcome: str = PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_OUTCOME
    next_allowed_step: str = (
        PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_NEXT_ALLOWED
    )
    no_real_or_external_effects: bool = True
    phase19_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.blueprint_id or len(self.blueprint_digest) != 64:
            raise ValueError("Phase 18 blueprint lineage is invalid.")

        if self.schema_version != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_SCHEMA_VERSION
        ):
            raise ValueError("Phase 18 validation schema version is invalid.")

        if self.source != PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_SOURCE:
            raise ValueError("Phase 18 validation source is invalid.")

        if self.status != PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_STATUS:
            raise ValueError("Phase 18 validation status is invalid.")

        if self.outcome != PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_OUTCOME:
            raise ValueError("Phase 18 validation outcome is invalid.")

        if self.next_allowed_step != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_NEXT_ALLOWED
        ):
            raise ValueError("Phase 18 validation next step is invalid.")

        if tuple(item.name for item in self.results) != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_CHECKS
        ):
            raise ValueError("Phase 18 validation result set is incomplete.")

        if not all(item.passed for item in self.results):
            raise ValueError("Phase 18 validation contains failed checks.")

        if not self.no_real_or_external_effects:
            raise ValueError("Phase 18.3 must have no real effects.")

        if self.phase19_admitted:
            raise ValueError("Phase 19 cannot be admitted by Phase 18.3.")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.results)

    @property
    def result_count(self) -> int:
        return len(self.results)

    @property
    def validation_digest(self) -> str:
        """Hash bounded validation fields without recursive object expansion."""

        material = "|".join(
            (
                self.blueprint_digest,
                self.schema_version,
                self.source,
                self.status,
                self.outcome,
                self.next_allowed_step,
                ",".join(
                    f"{item.name}:{item.passed}:{item.evidence}"
                    for item in self.results
                ),
                str(self.no_real_or_external_effects),
                str(self.phase19_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def validation_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION:"
            f"SHA256[{self.validation_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationValidationDecision:
    """Decision wrapper for deterministic Phase 18 validation."""

    valid: bool
    reason: str
    report: Phase18PaperRuntimeSimulationValidationReport | None

    @property
    def report_required(self) -> Phase18PaperRuntimeSimulationValidationReport:
        if not self.valid or self.report is None:
            raise RuntimeError("Phase 18 validation report is unavailable.")
        return self.report


class Phase18PaperRuntimeSimulationValidator:
    """Validate the Phase 18 paper-runtime simulation blueprint."""

    def validate(
        self,
        blueprint: Phase18PaperRuntimeSimulationBlueprint,
    ) -> Phase18PaperRuntimeSimulationValidationDecision:
        checks = (
            (
                "BLUEPRINT_STATUS_VALID",
                blueprint.status
                == PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_STATUS,
                blueprint.status,
            ),
            (
                "COMPONENT_CONTRACT_COMPLETE",
                tuple(item.name for item in blueprint.components)
                == PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS,
                f"components={blueprint.component_count}",
            ),
            (
                "REQUIREMENT_CONTRACT_COMPLETE",
                tuple(item.name for item in blueprint.requirements)
                == PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS,
                f"requirements={blueprint.requirement_count}",
            ),
            (
                "MARKET_SCOPE_EXACT",
                blueprint.mode == "PAPER"
                and blueprint.symbol == "XAUUSD"
                and blueprint.timeframes == ("H4", "H1", "M15", "M5"),
                (
                    f"mode={blueprint.mode};symbol={blueprint.symbol};"
                    f"timeframes={','.join(blueprint.timeframes)}"
                ),
            ),
            (
                "CLOSED_CANDLES_REQUIRED",
                blueprint.closed_candles_only,
                f"closed_candles_only={blueprint.closed_candles_only}",
            ),
            (
                "POSITION_LIMIT_EXACT",
                blueprint.maximum_open_gold_positions == 1,
                (
                    "maximum_open_gold_positions="
                    f"{blueprint.maximum_open_gold_positions}"
                ),
            ),
            (
                "RISK_BUDGET_EXACT",
                blueprint.aggregate_risk_budget_bps == 50
                and blueprint.stage_risk_bps == (25, 25),
                (
                    f"aggregate_bps={blueprint.aggregate_risk_budget_bps};"
                    f"stage_bps={blueprint.stage_risk_bps}"
                ),
            ),
            (
                "REAL_RUNTIME_STATUSES_BLOCKED",
                blueprint.blocked_runtime_statuses
                == PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES,
                ",".join(blueprint.blocked_runtime_statuses),
            ),
            (
                "SIMULATION_EXECUTION_BLOCKED",
                not blueprint.simulation_execution_permitted,
                (
                    "simulation_execution_permitted="
                    f"{blueprint.simulation_execution_permitted}"
                ),
            ),
            (
                "PHASE_19_BLOCKED",
                not blueprint.phase19_admitted,
                f"phase19_admitted={blueprint.phase19_admitted}",
            ),
        )

        if not all(passed for _, passed, _ in checks):
            return Phase18PaperRuntimeSimulationValidationDecision(
                valid=False,
                reason="PHASE_18_BLUEPRINT_VALIDATION_FAILED",
                report=None,
            )

        results = tuple(
            Phase18PaperRuntimeSimulationValidationResult(
                name=name,
                passed=passed,
                evidence=evidence,
            )
            for name, passed, evidence in checks
        )

        report = Phase18PaperRuntimeSimulationValidationReport(
            blueprint_id=blueprint.blueprint_id,
            blueprint_digest=blueprint.blueprint_digest,
            results=results,
        )

        return Phase18PaperRuntimeSimulationValidationDecision(
            valid=True,
            reason="PHASE_18_BLUEPRINT_VALIDATION_PASSED",
            report=report,
        )


def validate_phase18_paper_runtime_simulation_blueprint(
) -> Phase18PaperRuntimeSimulationValidationDecision:
    """Validate the deterministic Phase 18 paper-runtime blueprint."""

    blueprint = (
        build_phase18_paper_runtime_simulation_blueprint().blueprint_required
    )
    return Phase18PaperRuntimeSimulationValidator().validate(blueprint)


__all__ = (
    "PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_SCHEMA_VERSION",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_SOURCE",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_STATUS",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_OUTCOME",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_NEXT_ALLOWED",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_VALIDATION_CHECKS",
    "Phase18PaperRuntimeSimulationValidationResult",
    "Phase18PaperRuntimeSimulationValidationReport",
    "Phase18PaperRuntimeSimulationValidationDecision",
    "Phase18PaperRuntimeSimulationValidator",
    "validate_phase18_paper_runtime_simulation_blueprint",
)
