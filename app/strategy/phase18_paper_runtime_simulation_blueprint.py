from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase18_deterministic_paper_runtime_simulation_admission import (
    PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED,
    Phase18DeterministicPaperRuntimeSimulationAdmissionPermit,
    admit_phase18_deterministic_paper_runtime_simulation,
)

PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_SCHEMA_VERSION = "1.0"
PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_STATUS = (
    "PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_READY"
)
PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_SOURCE = (
    PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED
)
PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_NEXT_ALLOWED = (
    "DETERMINISTIC_PAPER_RUNTIME_SIMULATION_VALIDATION"
)

PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS = (
    "CLOSED_CANDLE_MARKET_FEED",
    "DETERMINISTIC_SIMULATION_CLOCK",
    "STRATEGY_SIGNAL_ADAPTER",
    "PAPER_ORDER_LIFECYCLE_ENGINE",
    "RISK_AND_GUARD_EVALUATOR",
    "OCO_POSITION_STATE_MACHINE",
    "IMMUTABLE_SIMULATION_LEDGER",
    "DETERMINISTIC_REPLAY_SUMMARY",
)

PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS = (
    "XAUUSD_ONLY",
    "H4_H1_M15_M5_ONLY",
    "CLOSED_CANDLES_ONLY",
    "PAPER_MODE_ONLY",
    "ONE_OPEN_GOLD_POSITION_MAXIMUM",
    "AGGREGATE_RISK_50_BPS",
    "STAGED_RISK_25_PLUS_25_BPS",
    "OCO_REQUIRED",
    "STOP_LOSS_REQUIRED",
    "TERMINAL_FLAT_REQUIRED",
    "MARTINGALE_GRID_NO_SL_FORBIDDEN",
    "NO_REAL_OR_EXTERNAL_EFFECTS",
)

PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES = (
    "REAL_ENV_BLOCKED",
    "MT5_INITIALIZATION_BLOCKED",
    "TERMINAL_CONNECTION_BLOCKED",
    "BROKER_READ_BLOCKED",
    "BROKER_WRITE_BLOCKED",
    "ACCOUNT_ACCESS_BLOCKED",
    "PRODUCTION_BLOCKED",
    "LIVE_TRADING_BLOCKED",
)


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationComponent:
    """One deterministic paper-runtime simulation component."""

    name: str
    ordinal: int

    def __post_init__(self) -> None:
        if self.name not in PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS:
            raise ValueError("Unknown Phase 18 simulation component.")

        expected_ordinal = (
            PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS.index(self.name) + 1
        )
        if self.ordinal != expected_ordinal:
            raise ValueError("Phase 18 component ordinal is invalid.")


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationRequirement:
    """One fail-closed Phase 18 blueprint requirement."""

    name: str
    ordinal: int

    def __post_init__(self) -> None:
        if self.name not in PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS:
            raise ValueError("Unknown Phase 18 simulation requirement.")

        expected_ordinal = (
            PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS.index(self.name) + 1
        )
        if self.ordinal != expected_ordinal:
            raise ValueError("Phase 18 requirement ordinal is invalid.")


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationBlueprint:
    """Deterministic and side-effect-free Phase 18 simulation blueprint."""

    admission_id: str
    admission_digest: str
    schema_version: str = (
        PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_SCHEMA_VERSION
    )
    status: str = PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_STATUS
    source: str = PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_SOURCE
    next_allowed_step: str = (
        PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_NEXT_ALLOWED
    )
    mode: str = "PAPER"
    symbol: str = "XAUUSD"
    timeframes: tuple[str, ...] = ("H4", "H1", "M15", "M5")
    closed_candles_only: bool = True
    maximum_open_gold_positions: int = 1
    aggregate_risk_budget_bps: int = 50
    stage_risk_bps: tuple[int, int] = (25, 25)
    components: tuple[Phase18PaperRuntimeSimulationComponent, ...] = ()
    requirements: tuple[Phase18PaperRuntimeSimulationRequirement, ...] = ()
    blocked_runtime_statuses: tuple[str, ...] = (
        PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES
    )
    simulation_execution_permitted: bool = False
    phase19_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.admission_id or len(self.admission_digest) != 64:
            raise ValueError("Phase 18 admission lineage is invalid.")

        if self.schema_version != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_SCHEMA_VERSION
        ):
            raise ValueError("Phase 18 blueprint schema version is invalid.")

        if self.status != PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_STATUS:
            raise ValueError("Phase 18 blueprint status is invalid.")

        if self.source != PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_SOURCE:
            raise ValueError("Phase 18 blueprint source is invalid.")

        if self.next_allowed_step != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_NEXT_ALLOWED
        ):
            raise ValueError("Phase 18 next allowed step is invalid.")

        if self.mode != "PAPER" or self.symbol != "XAUUSD":
            raise ValueError("Phase 18 blueprint scope is invalid.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 18 blueprint timeframes are invalid.")

        if not self.closed_candles_only:
            raise ValueError("Phase 18 must use closed candles only.")

        if self.maximum_open_gold_positions != 1:
            raise ValueError("Only one Gold position may be open.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("Aggregate staged risk must remain 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("Stage risk must remain 25 + 25 bps.")

        if tuple(item.name for item in self.components) != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS
        ):
            raise ValueError("Phase 18 component set is incomplete.")

        if tuple(item.name for item in self.requirements) != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS
        ):
            raise ValueError("Phase 18 requirement set is incomplete.")

        if self.blocked_runtime_statuses != (
            PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES
        ):
            raise ValueError("Real runtime statuses must remain blocked.")

        if self.simulation_execution_permitted:
            raise ValueError("Phase 18.2 cannot permit simulation execution.")

        if self.phase19_admitted:
            raise ValueError("Phase 19 cannot be admitted by Phase 18.2.")

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    @property
    def blueprint_digest(self) -> str:
        """Hash bounded fields without recursively expanding prior objects."""

        material = "|".join(
            (
                self.admission_digest,
                self.schema_version,
                self.status,
                self.source,
                self.next_allowed_step,
                self.mode,
                self.symbol,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                str(self.maximum_open_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                ",".join(item.name for item in self.components),
                ",".join(item.name for item in self.requirements),
                ",".join(self.blocked_runtime_statuses),
                str(self.simulation_execution_permitted),
                str(self.phase19_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def blueprint_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT:"
            f"SHA256[{self.blueprint_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationBlueprintDecision:
    """Decision wrapper for the deterministic Phase 18 blueprint."""

    ready: bool
    reason: str
    blueprint: Phase18PaperRuntimeSimulationBlueprint | None

    @property
    def blueprint_required(self) -> Phase18PaperRuntimeSimulationBlueprint:
        if not self.ready or self.blueprint is None:
            raise RuntimeError("Phase 18 simulation blueprint is unavailable.")
        return self.blueprint


class Phase18PaperRuntimeSimulationBlueprintPlanner:
    """Build the Phase 18 paper-runtime simulation blueprint."""

    def build(
        self,
        permit: Phase18DeterministicPaperRuntimeSimulationAdmissionPermit,
    ) -> Phase18PaperRuntimeSimulationBlueprintDecision:
        if permit.phase_status != (
            PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED
        ):
            return Phase18PaperRuntimeSimulationBlueprintDecision(
                ready=False,
                reason="PHASE_18_ADMISSION_NOT_ESTABLISHED",
                blueprint=None,
            )

        components = tuple(
            Phase18PaperRuntimeSimulationComponent(
                name=name,
                ordinal=index,
            )
            for index, name in enumerate(
                PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS,
                start=1,
            )
        )
        requirements = tuple(
            Phase18PaperRuntimeSimulationRequirement(
                name=name,
                ordinal=index,
            )
            for index, name in enumerate(
                PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS,
                start=1,
            )
        )

        blueprint = Phase18PaperRuntimeSimulationBlueprint(
            admission_id=permit.admission_id,
            admission_digest=permit.admission_digest,
            components=components,
            requirements=requirements,
        )

        return Phase18PaperRuntimeSimulationBlueprintDecision(
            ready=True,
            reason="PHASE_18_BLUEPRINT_READY_FOR_VALIDATION",
            blueprint=blueprint,
        )


def build_phase18_paper_runtime_simulation_blueprint(
) -> Phase18PaperRuntimeSimulationBlueprintDecision:
    """Build the deterministic Phase 18 blueprint from its admission permit."""

    permit = (
        admit_phase18_deterministic_paper_runtime_simulation().permit_required
    )
    return Phase18PaperRuntimeSimulationBlueprintPlanner().build(permit)


__all__ = (
    "PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_SCHEMA_VERSION",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_STATUS",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_SOURCE",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_BLUEPRINT_NEXT_ALLOWED",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_COMPONENTS",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_REQUIREMENTS",
    "PHASE_18_PAPER_RUNTIME_BLOCKED_STATUSES",
    "Phase18PaperRuntimeSimulationComponent",
    "Phase18PaperRuntimeSimulationRequirement",
    "Phase18PaperRuntimeSimulationBlueprint",
    "Phase18PaperRuntimeSimulationBlueprintDecision",
    "Phase18PaperRuntimeSimulationBlueprintPlanner",
    "build_phase18_paper_runtime_simulation_blueprint",
)
