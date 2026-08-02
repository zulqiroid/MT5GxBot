from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase20_in_memory_paper_runtime_execution_engine_blueprint import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_STATUS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_INVARIANTS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES,
    Phase20InMemoryPaperRuntimeEngineBlueprint,
    build_phase20_in_memory_paper_runtime_execution_engine_blueprint,
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_SCHEMA_VERSION = "1.0"
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_SOURCE = (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_STATUS
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_STATUS = (
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ENGINE_BLUEPRINT_VALIDATED"
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_NEXT_ALLOWED = (
    "IN_MEMORY_PAPER_RUNTIME_EXECUTION_ENGINE_SAFETY_AUDIT"
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_CHECKS = (
    "BLUEPRINT_LINEAGE_INTACT",
    "BLUEPRINT_STATUS_READY",
    "COMPONENT_CHAIN_COMPLETE",
    "INVARIANT_CONTRACT_COMPLETE",
    "STATE_MACHINE_CONTRACT_EXACT",
    "MARKET_SCOPE_EXACT",
    "CLOSED_CANDLE_AND_NO_LOOKAHEAD_ENFORCED",
    "FILL_POLICIES_CONSERVATIVE",
    "POSITION_AND_RISK_LIMITS_EXACT",
    "PROTECTION_AND_TERMINAL_FLATNESS_PRESENT",
    "IN_MEMORY_AND_REAL_EFFECT_BOUNDARIES_PRESERVED",
    "PHASE_21_NOT_ADMITTED",
)


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineValidationCheck:
    """One deterministic validation check for the Phase 20 engine blueprint."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_CHECKS
        ):
            raise ValueError("Unknown Phase 20 engine-validation check.")

        if not self.evidence:
            raise ValueError("Phase 20 validation evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineValidationReport:
    """Immutable validation report for the in-memory engine blueprint."""

    blueprint_id: str
    blueprint_digest: str
    checks: tuple[
        Phase20InMemoryPaperRuntimeEngineValidationCheck,
        ...,
    ]
    schema_version: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_SCHEMA_VERSION
    )
    source: str = PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_SOURCE
    status: str = PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_STATUS
    next_allowed_step: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_NEXT_ALLOWED
    )
    in_memory_simulation_execution_admitted: bool = True
    engine_invocation_permitted: bool = False
    real_runtime_access_permitted: bool = False
    external_effects_permitted: bool = False
    phase21_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.blueprint_id or len(self.blueprint_digest) != 64:
            raise ValueError("Phase 20 engine-blueprint lineage is invalid.")

        if self.schema_version != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_SCHEMA_VERSION
        ):
            raise ValueError("Phase 20 engine-validation schema is invalid.")

        if self.source != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_SOURCE
        ):
            raise ValueError("Phase 20 engine-validation source is invalid.")

        if self.status != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_STATUS
        ):
            raise ValueError("Phase 20 engine-validation status is invalid.")

        if self.next_allowed_step != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_NEXT_ALLOWED
        ):
            raise ValueError("Phase 20 engine-validation next step is invalid.")

        if tuple(item.name for item in self.checks) != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_CHECKS
        ):
            raise ValueError("Phase 20 engine-validation checks are incomplete.")

        if not all(item.passed for item in self.checks):
            raise ValueError("Phase 20 engine validation contains failed checks.")

        if not self.in_memory_simulation_execution_admitted:
            raise ValueError("Phase 20 simulation admission must be preserved.")

        if self.engine_invocation_permitted:
            raise ValueError("Phase 20.3 cannot invoke the engine.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 20.3 cannot permit real runtime access.")

        if self.external_effects_permitted:
            raise ValueError("Phase 20.3 cannot permit external effects.")

        if self.phase21_admitted:
            raise ValueError("Phase 21 cannot be admitted by Phase 20.3.")

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
                str(self.in_memory_simulation_execution_admitted),
                str(self.engine_invocation_permitted),
                str(self.real_runtime_access_permitted),
                str(self.external_effects_permitted),
                str(self.phase21_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def validation_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_20_IN_MEMORY_PAPER_RUNTIME_"
            "EXECUTION_ENGINE_VALIDATION:"
            f"SHA256[{self.validation_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineValidationDecision:
    """Decision wrapper for Phase 20 engine-blueprint validation."""

    valid: bool
    reason: str
    report: Phase20InMemoryPaperRuntimeEngineValidationReport | None

    @property
    def report_required(
        self,
    ) -> Phase20InMemoryPaperRuntimeEngineValidationReport:
        if not self.valid or self.report is None:
            raise RuntimeError("Phase 20 engine validation report is unavailable.")
        return self.report


class Phase20InMemoryPaperRuntimeEngineBlueprintValidator:
    """Validate the deterministic in-memory engine without invoking it."""

    def validate(
        self,
        blueprint: Phase20InMemoryPaperRuntimeEngineBlueprint,
    ) -> Phase20InMemoryPaperRuntimeEngineValidationDecision:
        invariant_evidence = {
            item.name: item.evidence for item in blueprint.invariants
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
                == PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_STATUS,
                blueprint.status,
            ),
            (
                "COMPONENT_CHAIN_COMPLETE",
                tuple(item.name for item in blueprint.components)
                == PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS
                and tuple(item.order for item in blueprint.components)
                == tuple(range(1, 13)),
                f"components={blueprint.component_count}",
            ),
            (
                "INVARIANT_CONTRACT_COMPLETE",
                tuple(item.name for item in blueprint.invariants)
                == PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_INVARIANTS,
                f"invariants={blueprint.invariant_count}",
            ),
            (
                "STATE_MACHINE_CONTRACT_EXACT",
                blueprint.states
                == PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES,
                f"states={','.join(blueprint.states)}",
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
                "CLOSED_CANDLE_AND_NO_LOOKAHEAD_ENFORCED",
                blueprint.signal_evaluation_policy == "CANDLE_CLOSE_ONLY"
                and invariant_evidence["NO_LOOKAHEAD"]
                == "lookahead_permitted=False",
                (
                    "signal_evaluation_policy="
                    f"{blueprint.signal_evaluation_policy};"
                    f'{invariant_evidence["NO_LOOKAHEAD"]}'
                ),
            ),
            (
                "FILL_POLICIES_CONSERVATIVE",
                blueprint.entry_fill_policy
                == "NEXT_EVENT_OPEN_AFTER_SIGNAL_CLOSE"
                and blueprint.same_bar_conflict_policy == "STOP_FIRST",
                (
                    f"entry_fill_policy={blueprint.entry_fill_policy};"
                    "same_bar_conflict_policy="
                    f"{blueprint.same_bar_conflict_policy}"
                ),
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
                "PROTECTION_AND_TERMINAL_FLATNESS_PRESENT",
                invariant_evidence["OCO_REQUIRED"] == "oco_required=True"
                and invariant_evidence["STOP_LOSS_REQUIRED"]
                == "stop_loss_required=True"
                and invariant_evidence["TERMINAL_FLAT_REQUIRED"]
                == "terminal_flat_required=True",
                (
                    f'{invariant_evidence["OCO_REQUIRED"]};'
                    f'{invariant_evidence["STOP_LOSS_REQUIRED"]};'
                    f'{invariant_evidence["TERMINAL_FLAT_REQUIRED"]}'
                ),
            ),
            (
                "IN_MEMORY_AND_REAL_EFFECT_BOUNDARIES_PRESERVED",
                blueprint.in_memory_only
                and blueprint.simulation_execution_permitted
                and not blueprint.engine_invocation_permitted
                and not blueprint.real_runtime_access_permitted
                and not blueprint.external_effects_permitted,
                (
                    f"in_memory_only={blueprint.in_memory_only};"
                    "simulation_execution_permitted="
                    f"{blueprint.simulation_execution_permitted};"
                    "engine_invocation_permitted="
                    f"{blueprint.engine_invocation_permitted};"
                    "real_runtime_access_permitted="
                    f"{blueprint.real_runtime_access_permitted};"
                    "external_effects_permitted="
                    f"{blueprint.external_effects_permitted}"
                ),
            ),
            (
                "PHASE_21_NOT_ADMITTED",
                not blueprint.phase21_admitted,
                f"phase21_admitted={blueprint.phase21_admitted}",
            ),
        )

        if not all(passed for _, passed, _ in checks):
            return Phase20InMemoryPaperRuntimeEngineValidationDecision(
                valid=False,
                reason="PHASE_20_ENGINE_BLUEPRINT_VALIDATION_FAILED",
                report=None,
            )

        report = Phase20InMemoryPaperRuntimeEngineValidationReport(
            blueprint_id=blueprint.blueprint_id,
            blueprint_digest=blueprint.blueprint_digest,
            checks=tuple(
                Phase20InMemoryPaperRuntimeEngineValidationCheck(
                    name=name,
                    passed=passed,
                    evidence=evidence,
                )
                for name, passed, evidence in checks
            ),
        )

        return Phase20InMemoryPaperRuntimeEngineValidationDecision(
            valid=True,
            reason="PHASE_20_ENGINE_BLUEPRINT_VALIDATED",
            report=report,
        )


def validate_phase20_in_memory_paper_runtime_execution_engine_blueprint(
) -> Phase20InMemoryPaperRuntimeEngineValidationDecision:
    """Validate the Phase 20 in-memory execution-engine blueprint."""

    blueprint = (
        build_phase20_in_memory_paper_runtime_execution_engine_blueprint()
        .blueprint_required
    )
    return Phase20InMemoryPaperRuntimeEngineBlueprintValidator().validate(
        blueprint
    )


__all__ = (
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_SCHEMA_VERSION",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_SOURCE",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_STATUS",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_NEXT_ALLOWED",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_VALIDATION_CHECKS",
    "Phase20InMemoryPaperRuntimeEngineValidationCheck",
    "Phase20InMemoryPaperRuntimeEngineValidationReport",
    "Phase20InMemoryPaperRuntimeEngineValidationDecision",
    "Phase20InMemoryPaperRuntimeEngineBlueprintValidator",
    "validate_phase20_in_memory_paper_runtime_execution_engine_blueprint",
)
