from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase19_paper_runtime_simulation_execution_admission import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_STATUS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLOCKED_CAPABILITIES,
    Phase19PaperRuntimeSimulationExecutionAdmission,
    admit_phase19_paper_runtime_simulation_execution_planning,
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_SCHEMA_VERSION = "1.0"
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_SOURCE = (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_STATUS
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_STATUS = (
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_READY"
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_NEXT_ALLOWED = (
    "DETERMINISTIC_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_VALIDATION"
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS = (
    "CLOSED_CANDLE_MARKET_FEED",
    "DETERMINISTIC_SIMULATION_CLOCK",
    "STRATEGY_ANALYSIS_PIPELINE",
    "PAPER_ORDER_INTENT_ADAPTER",
    "PAPER_EXECUTION_STATE_MACHINE",
    "RISK_AND_POSITION_GUARD",
    "OCO_PROTECTION_COORDINATOR",
    "IMMUTABLE_EXECUTION_LEDGER",
    "DETERMINISTIC_REPLAY_SUMMARY",
    "TERMINAL_FLATNESS_PROOF",
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_REQUIREMENTS = (
    "PAPER_MODE_ONLY",
    "XAUUSD_ONLY",
    "H4_H1_M15_M5_ONLY",
    "CLOSED_CANDLES_ONLY",
    "ONE_OPEN_GOLD_POSITION_MAXIMUM",
    "AGGREGATE_RISK_50_BPS",
    "STAGED_RISK_25_PLUS_25_BPS",
    "OCO_REQUIRED",
    "STOP_LOSS_REQUIRED",
    "TERMINAL_FLAT_REQUIRED",
    "MARTINGALE_GRID_NO_SL_FORBIDDEN",
    "NO_REAL_OR_EXTERNAL_EFFECTS",
)


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionComponent:
    """One deterministic component in the Phase 19 execution blueprint."""

    name: str
    order: int
    responsibility: str

    def __post_init__(self) -> None:
        if self.name not in PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS:
            raise ValueError("Unknown Phase 19 execution component.")
        if self.order < 1:
            raise ValueError("Phase 19 component order must be positive.")
        if not self.responsibility:
            raise ValueError("Phase 19 component responsibility is required.")


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionRequirement:
    """One immutable requirement in the Phase 19 execution blueprint."""

    name: str
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_REQUIREMENTS:
            raise ValueError("Unknown Phase 19 execution requirement.")
        if not self.evidence:
            raise ValueError("Phase 19 requirement evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionBlueprint:
    """Fail-closed deterministic paper-runtime execution blueprint."""

    admission_id: str
    admission_digest: str
    components: tuple[Phase19PaperRuntimeSimulationExecutionComponent, ...]
    requirements: tuple[Phase19PaperRuntimeSimulationExecutionRequirement, ...]
    schema_version: str = PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_SCHEMA_VERSION
    source: str = PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_SOURCE
    status: str = PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_STATUS
    next_allowed_step: str = PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_NEXT_ALLOWED
    symbol: str = "XAUUSD"
    timeframes: tuple[str, ...] = ("H4", "H1", "M15", "M5")
    closed_candles_only: bool = True
    maximum_open_gold_positions: int = 1
    aggregate_risk_budget_bps: int = 50
    stage_risk_bps: tuple[int, int] = (25, 25)
    blocked_capabilities: tuple[str, ...] = PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLOCKED_CAPABILITIES
    simulation_execution_permitted: bool = False
    real_runtime_access_permitted: bool = False
    phase20_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.admission_id or len(self.admission_digest) != 64:
            raise ValueError("Phase 19 admission lineage is invalid.")
        if self.schema_version != PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_SCHEMA_VERSION:
            raise ValueError("Phase 19 blueprint schema is invalid.")
        if self.source != PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_SOURCE:
            raise ValueError("Phase 19 blueprint source is invalid.")
        if self.status != PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_STATUS:
            raise ValueError("Phase 19 blueprint status is invalid.")
        if self.next_allowed_step != PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_NEXT_ALLOWED:
            raise ValueError("Phase 19 blueprint next step is invalid.")
        if tuple(item.name for item in self.components) != PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS:
            raise ValueError("Phase 19 execution components are incomplete.")
        if tuple(item.order for item in self.components) != tuple(range(1, len(self.components) + 1)):
            raise ValueError("Phase 19 execution component order is invalid.")
        if tuple(item.name for item in self.requirements) != PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_REQUIREMENTS:
            raise ValueError("Phase 19 execution requirements are incomplete.")
        if self.symbol != "XAUUSD":
            raise ValueError("Phase 19 blueprint is restricted to XAUUSD.")
        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 19 blueprint timeframe scope is invalid.")
        if not self.closed_candles_only:
            raise ValueError("Phase 19 blueprint requires closed candles.")
        if self.maximum_open_gold_positions != 1:
            raise ValueError("Phase 19 blueprint permits one Gold position.")
        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("Phase 19 blueprint risk must remain 50 bps.")
        if self.stage_risk_bps != (25, 25):
            raise ValueError("Phase 19 blueprint staged risk is invalid.")
        if self.blocked_capabilities != PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLOCKED_CAPABILITIES:
            raise ValueError("Phase 19 blocked capabilities are incomplete.")
        if self.simulation_execution_permitted:
            raise ValueError("Phase 19.2 cannot permit simulation execution.")
        if self.real_runtime_access_permitted:
            raise ValueError("Phase 19.2 cannot permit real runtime access.")
        if self.phase20_admitted:
            raise ValueError("Phase 20 cannot be admitted by Phase 19.2.")

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    @property
    def blueprint_digest(self) -> str:
        material = "|".join(
            (
                self.admission_digest,
                self.schema_version,
                self.source,
                self.status,
                self.next_allowed_step,
                self.symbol,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                str(self.maximum_open_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                ",".join(f"{item.order}:{item.name}:{item.responsibility}" for item in self.components),
                ",".join(f"{item.name}:{item.evidence}" for item in self.requirements),
                ",".join(self.blocked_capabilities),
                str(self.simulation_execution_permitted),
                str(self.real_runtime_access_permitted),
                str(self.phase20_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def blueprint_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT:"
            f"SHA256[{self.blueprint_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionBlueprintDecision:
    """Decision wrapper for the Phase 19 execution blueprint."""

    ready: bool
    reason: str
    blueprint: Phase19PaperRuntimeSimulationExecutionBlueprint | None

    @property
    def blueprint_required(self) -> Phase19PaperRuntimeSimulationExecutionBlueprint:
        if not self.ready or self.blueprint is None:
            raise RuntimeError("Phase 19 execution blueprint is unavailable.")
        return self.blueprint


class Phase19PaperRuntimeSimulationExecutionBlueprintPlanner:
    """Build the deterministic Phase 19 execution blueprint."""

    def build(
        self,
        admission: Phase19PaperRuntimeSimulationExecutionAdmission,
    ) -> Phase19PaperRuntimeSimulationExecutionBlueprintDecision:
        if (
            admission.status != PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_STATUS
            or not admission.planning_permitted
            or admission.simulation_execution_permitted
            or admission.real_runtime_access_permitted
            or admission.phase20_admitted
        ):
            return Phase19PaperRuntimeSimulationExecutionBlueprintDecision(
                ready=False,
                reason="PHASE_19_EXECUTION_BLUEPRINT_BLOCKED",
                blueprint=None,
            )

        responsibilities = (
            "Provide ordered immutable closed-candle observations only.",
            "Advance one deterministic timestamp per replay event.",
            "Evaluate strategy context without external side effects.",
            "Translate qualified setups into paper-only order intent.",
            "Model entry, protection, fill, exit, and cancellation states.",
            "Enforce position count and aggregate staged-risk limits.",
            "Maintain mandatory stop-loss and OCO relationships.",
            "Append immutable decisions, events, and state transitions.",
            "Produce bounded deterministic replay metrics and outcomes.",
            "Prove zero open positions and orders at termination.",
        )
        components = tuple(
            Phase19PaperRuntimeSimulationExecutionComponent(
                name=name,
                order=index,
                responsibility=responsibility,
            )
            for index, (name, responsibility) in enumerate(
                zip(PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS, responsibilities, strict=True),
                start=1,
            )
        )
        requirement_evidence = (
            "mode=PAPER",
            "symbol=XAUUSD",
            "timeframes=H4,H1,M15,M5",
            "closed_candles_only=True",
            "maximum_open_gold_positions=1",
            "aggregate_risk_budget_bps=50",
            "stage_risk_bps=25,25",
            "oco_required=True",
            "stop_loss_required=True",
            "terminal_flat_required=True",
            "martingale=False;grid=False;no_sl=False",
            "real_or_external_effects_permitted=False",
        )
        requirements = tuple(
            Phase19PaperRuntimeSimulationExecutionRequirement(name=name, evidence=evidence)
            for name, evidence in zip(
                PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_REQUIREMENTS,
                requirement_evidence,
                strict=True,
            )
        )
        blueprint = Phase19PaperRuntimeSimulationExecutionBlueprint(
            admission_id=admission.admission_id,
            admission_digest=admission.admission_digest,
            components=components,
            requirements=requirements,
        )
        return Phase19PaperRuntimeSimulationExecutionBlueprintDecision(
            ready=True,
            reason="PHASE_19_EXECUTION_BLUEPRINT_READY",
            blueprint=blueprint,
        )


def build_phase19_paper_runtime_simulation_execution_blueprint(
) -> Phase19PaperRuntimeSimulationExecutionBlueprintDecision:
    """Build the deterministic Phase 19 execution blueprint."""

    admission = admit_phase19_paper_runtime_simulation_execution_planning().admission_required
    return Phase19PaperRuntimeSimulationExecutionBlueprintPlanner().build(admission)


__all__ = (
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_SCHEMA_VERSION",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_SOURCE",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_STATUS",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT_NEXT_ALLOWED",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_COMPONENTS",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_REQUIREMENTS",
    "Phase19PaperRuntimeSimulationExecutionComponent",
    "Phase19PaperRuntimeSimulationExecutionRequirement",
    "Phase19PaperRuntimeSimulationExecutionBlueprint",
    "Phase19PaperRuntimeSimulationExecutionBlueprintDecision",
    "Phase19PaperRuntimeSimulationExecutionBlueprintPlanner",
    "build_phase19_paper_runtime_simulation_execution_blueprint",
)
