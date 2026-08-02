from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase19_paper_runtime_simulation_execution_blueprint import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_STATUS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_REQUIREMENTS,
    Phase19PaperRuntimeSimulationExecutionBlueprint,
    build_phase19_paper_runtime_simulation_execution_blueprint,
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_SCHEMA_VERSION = "1.0"
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_SOURCE = (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_STATUS
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_STATUS = (
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_VALIDATED"
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_NEXT_ALLOWED = (
    "PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT"
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_CHECKS = (
    "BLUEPRINT_LINEAGE_INTACT",
    "BLUEPRINT_STATUS_READY",
    "COMPONENT_CONTRACT_COMPLETE",
    "REQUIREMENT_CONTRACT_COMPLETE",
    "MARKET_SCOPE_EXACT",
    "CLOSED_CANDLES_REQUIRED",
    "POSITION_AND_RISK_LIMITS_EXACT",
    "PROTECTION_REQUIREMENTS_PRESENT",
    "REAL_AND_SIMULATION_EXECUTION_BLOCKED",
    "PHASE_20_NOT_ADMITTED",
)


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionValidationCheck:
    """One deterministic Phase 19 execution-blueprint validation check."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_CHECKS
        ):
            raise ValueError("Unknown Phase 19 execution validation check.")

        if not self.evidence:
            raise ValueError("Phase 19 execution validation evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionValidationReport:
    """Immutable validation report for the Phase 19 execution blueprint."""

    blueprint_id: str
    blueprint_digest: str
    checks: tuple[
        Phase19PaperRuntimeSimulationExecutionValidationCheck,
        ...,
    ]
    schema_version: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_SCHEMA_VERSION
    )
    source: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_SOURCE
    )
    status: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_STATUS
    )
    next_allowed_step: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_NEXT_ALLOWED
    )
    simulation_execution_permitted: bool = False
    real_runtime_access_permitted: bool = False
    phase20_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.blueprint_id or len(self.blueprint_digest) != 64:
            raise ValueError("Phase 19 blueprint lineage is invalid.")

        if self.schema_version != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_SCHEMA_VERSION
        ):
            raise ValueError("Phase 19 validation schema is invalid.")

        if self.source != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_SOURCE
        ):
            raise ValueError("Phase 19 validation source is invalid.")

        if self.status != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_STATUS
        ):
            raise ValueError("Phase 19 validation status is invalid.")

        if self.next_allowed_step != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_NEXT_ALLOWED
        ):
            raise ValueError("Phase 19 validation next step is invalid.")

        if tuple(item.name for item in self.checks) != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_CHECKS
        ):
            raise ValueError("Phase 19 validation checks are incomplete.")

        if not all(item.passed for item in self.checks):
            raise ValueError("Phase 19 validation contains failed checks.")

        if self.simulation_execution_permitted:
            raise ValueError("Phase 19.3 cannot permit simulation execution.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 19.3 cannot permit real runtime access.")

        if self.phase20_admitted:
            raise ValueError("Phase 20 cannot be admitted by Phase 19.3.")

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def validation_digest(self) -> str:
        """Hash bounded validation fields without recursive expansion."""

        material = "|".join(
            (
                self.blueprint_digest,
                self.schema_version,
                self.source,
                self.status,
                self.next_allowed_step,
                ",".join(
                    f"{item.name}:{item.passed}:{item.evidence}"
                    for item in self.checks
                ),
                str(self.simulation_execution_permitted),
                str(self.real_runtime_access_permitted),
                str(self.phase20_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def validation_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_19_PAPER_RUNTIME_SIMULATION_"
            "EXECUTION_BLUEPRINT_VALIDATION:"
            f"SHA256[{self.validation_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionValidationDecision:
    """Decision wrapper for Phase 19 execution-blueprint validation."""

    valid: bool
    reason: str
    report: Phase19PaperRuntimeSimulationExecutionValidationReport | None

    @property
    def report_required(
        self,
    ) -> Phase19PaperRuntimeSimulationExecutionValidationReport:
        if not self.valid or self.report is None:
            raise RuntimeError("Phase 19 execution validation report is unavailable.")
        return self.report


class Phase19PaperRuntimeSimulationExecutionBlueprintValidator:
    """Validate the Phase 19 execution blueprint without runtime effects."""

    def validate(
        self,
        blueprint: Phase19PaperRuntimeSimulationExecutionBlueprint,
    ) -> Phase19PaperRuntimeSimulationExecutionValidationDecision:
        requirement_evidence = {
            item.name: item.evidence for item in blueprint.requirements
        }

        checks = (
            (
                "BLUEPRINT_LINEAGE_INTACT",
                bool(blueprint.blueprint_id)
                and len(blueprint.blueprint_digest) == 64,
                blueprint.blueprint_id,
            ),
            (
                "BLUEPRINT_STATUS_READY",
                blueprint.status
                == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_STATUS,
                blueprint.status,
            ),
            (
                "COMPONENT_CONTRACT_COMPLETE",
                tuple(item.name for item in blueprint.components)
                == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS
                and tuple(item.order for item in blueprint.components)
                == tuple(range(1, 11)),
                f"components={blueprint.component_count}",
            ),
            (
                "REQUIREMENT_CONTRACT_COMPLETE",
                tuple(item.name for item in blueprint.requirements)
                == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_REQUIREMENTS,
                f"requirements={blueprint.requirement_count}",
            ),
            (
                "MARKET_SCOPE_EXACT",
                blueprint.symbol == "XAUUSD"
                and blueprint.timeframes == ("H4", "H1", "M15", "M5"),
                (
                    f"symbol={blueprint.symbol};"
                    f"timeframes={','.join(blueprint.timeframes)}"
                ),
            ),
            (
                "CLOSED_CANDLES_REQUIRED",
                blueprint.closed_candles_only
                and requirement_evidence["CLOSED_CANDLES_ONLY"]
                == "closed_candles_only=True",
                requirement_evidence["CLOSED_CANDLES_ONLY"],
            ),
            (
                "POSITION_AND_RISK_LIMITS_EXACT",
                blueprint.maximum_open_gold_positions == 1
                and blueprint.aggregate_risk_budget_bps == 50
                and blueprint.stage_risk_bps == (25, 25),
                (
                    "maximum_open_gold_positions="
                    f"{blueprint.maximum_open_gold_positions};"
                    "aggregate_bps="
                    f"{blueprint.aggregate_risk_budget_bps};"
                    f"stage_bps={blueprint.stage_risk_bps}"
                ),
            ),
            (
                "PROTECTION_REQUIREMENTS_PRESENT",
                requirement_evidence["OCO_REQUIRED"] == "oco_required=True"
                and requirement_evidence["STOP_LOSS_REQUIRED"]
                == "stop_loss_required=True"
                and requirement_evidence["TERMINAL_FLAT_REQUIRED"]
                == "terminal_flat_required=True"
                and requirement_evidence["MARTINGALE_GRID_NO_SL_FORBIDDEN"]
                == "martingale=False;grid=False;no_sl=False",
                (
                    f'{requirement_evidence["OCO_REQUIRED"]};'
                    f'{requirement_evidence["STOP_LOSS_REQUIRED"]};'
                    f'{requirement_evidence["TERMINAL_FLAT_REQUIRED"]};'
                    f'{requirement_evidence["MARTINGALE_GRID_NO_SL_FORBIDDEN"]}'
                ),
            ),
            (
                "REAL_AND_SIMULATION_EXECUTION_BLOCKED",
                not blueprint.simulation_execution_permitted
                and not blueprint.real_runtime_access_permitted,
                (
                    "simulation_execution_permitted="
                    f"{blueprint.simulation_execution_permitted};"
                    "real_runtime_access_permitted="
                    f"{blueprint.real_runtime_access_permitted}"
                ),
            ),
            (
                "PHASE_20_NOT_ADMITTED",
                not blueprint.phase20_admitted,
                f"phase20_admitted={blueprint.phase20_admitted}",
            ),
        )

        if not all(passed for _, passed, _ in checks):
            return Phase19PaperRuntimeSimulationExecutionValidationDecision(
                valid=False,
                reason="PHASE_19_EXECUTION_BLUEPRINT_VALIDATION_FAILED",
                report=None,
            )

        report = Phase19PaperRuntimeSimulationExecutionValidationReport(
            blueprint_id=blueprint.blueprint_id,
            blueprint_digest=blueprint.blueprint_digest,
            checks=tuple(
                Phase19PaperRuntimeSimulationExecutionValidationCheck(
                    name=name,
                    passed=passed,
                    evidence=evidence,
                )
                for name, passed, evidence in checks
            ),
        )

        return Phase19PaperRuntimeSimulationExecutionValidationDecision(
            valid=True,
            reason="PHASE_19_EXECUTION_BLUEPRINT_VALIDATED",
            report=report,
        )


def validate_phase19_paper_runtime_simulation_execution_blueprint(
) -> Phase19PaperRuntimeSimulationExecutionValidationDecision:
    """Validate the deterministic Phase 19 execution blueprint."""

    blueprint = (
        build_phase19_paper_runtime_simulation_execution_blueprint()
        .blueprint_required
    )
    return Phase19PaperRuntimeSimulationExecutionBlueprintValidator().validate(
        blueprint
    )


__all__ = (
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_SCHEMA_VERSION",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_SOURCE",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_STATUS",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_NEXT_ALLOWED",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_VALIDATION_CHECKS",
    "Phase19PaperRuntimeSimulationExecutionValidationCheck",
    "Phase19PaperRuntimeSimulationExecutionValidationReport",
    "Phase19PaperRuntimeSimulationExecutionValidationDecision",
    "Phase19PaperRuntimeSimulationExecutionBlueprintValidator",
    "validate_phase19_paper_runtime_simulation_execution_blueprint",
)
