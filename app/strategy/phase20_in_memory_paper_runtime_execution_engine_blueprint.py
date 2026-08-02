from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase20_in_memory_paper_runtime_execution_admission import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_STATUS,
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_BLOCKED_CAPABILITIES,
    Phase20InMemoryPaperRuntimeExecutionAdmission,
    admit_phase20_in_memory_paper_runtime_simulation_execution,
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_SCHEMA_VERSION = "1.0"
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_SOURCE = (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_STATUS
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_STATUS = (
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ENGINE_BLUEPRINT_READY"
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_NEXT_ALLOWED = (
    "DETERMINISTIC_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ENGINE_VALIDATION"
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS = (
    "IMMUTABLE_CLOSED_CANDLE_FEED",
    "DETERMINISTIC_SIMULATION_CLOCK",
    "STRATEGY_SIGNAL_EVALUATOR",
    "PAPER_ORDER_INTENT_FACTORY",
    "RISK_BUDGET_ALLOCATOR",
    "DETERMINISTIC_PAPER_FILL_MODEL",
    "OCO_PROTECTION_ENGINE",
    "PAPER_POSITION_STATE_MACHINE",
    "IMMUTABLE_EXECUTION_EVENT_LEDGER",
    "TERMINAL_FLATNESS_ENFORCER",
    "DETERMINISTIC_METRICS_REDUCER",
    "REPLAY_RESULT_SEALER",
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_INVARIANTS = (
    "PAPER_MODE_ONLY",
    "IN_MEMORY_ONLY",
    "XAUUSD_ONLY",
    "H4_H1_M15_M5_ONLY",
    "CLOSED_CANDLES_ONLY",
    "NO_LOOKAHEAD",
    "ONE_OPEN_GOLD_POSITION_MAXIMUM",
    "AGGREGATE_RISK_50_BPS",
    "STAGED_RISK_25_PLUS_25_BPS",
    "OCO_REQUIRED",
    "STOP_LOSS_REQUIRED",
    "CONSERVATIVE_SAME_BAR_TIE_BREAK",
    "TERMINAL_FLAT_REQUIRED",
    "NO_REAL_OR_EXTERNAL_EFFECTS",
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES = (
    "READY",
    "OBSERVING",
    "INTENT_CREATED",
    "RISK_APPROVED",
    "POSITION_OPEN",
    "POSITION_PROTECTED",
    "POSITION_CLOSED",
    "FLAT_TERMINATED",
)


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineComponent:
    """One ordered component in the deterministic in-memory engine."""

    name: str
    order: int
    responsibility: str

    def __post_init__(self) -> None:
        if self.name not in PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS:
            raise ValueError("Unknown Phase 20 engine component.")

        if self.order < 1:
            raise ValueError("Phase 20 component order must be positive.")

        if not self.responsibility:
            raise ValueError("Phase 20 component responsibility is required.")


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineInvariant:
    """One immutable invariant in the Phase 20 engine blueprint."""

    name: str
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_INVARIANTS:
            raise ValueError("Unknown Phase 20 engine invariant.")

        if not self.evidence:
            raise ValueError("Phase 20 invariant evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineBlueprint:
    """Fail-closed deterministic in-memory paper execution blueprint."""

    admission_id: str
    admission_digest: str
    components: tuple[
        Phase20InMemoryPaperRuntimeEngineComponent,
        ...,
    ]
    invariants: tuple[
        Phase20InMemoryPaperRuntimeEngineInvariant,
        ...,
    ]
    schema_version: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_SCHEMA_VERSION
    )
    source: str = PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_SOURCE
    status: str = PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_STATUS
    next_allowed_step: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_NEXT_ALLOWED
    )
    symbol: str = "XAUUSD"
    timeframes: tuple[str, ...] = ("H4", "H1", "M15", "M5")
    states: tuple[str, ...] = PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES
    signal_evaluation_policy: str = "CANDLE_CLOSE_ONLY"
    entry_fill_policy: str = "NEXT_EVENT_OPEN_AFTER_SIGNAL_CLOSE"
    same_bar_conflict_policy: str = "STOP_FIRST"
    maximum_open_gold_positions: int = 1
    aggregate_risk_budget_bps: int = 50
    stage_risk_bps: tuple[int, int] = (25, 25)
    blocked_capabilities: tuple[str, ...] = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_BLOCKED_CAPABILITIES
    )
    in_memory_only: bool = True
    simulation_execution_permitted: bool = True
    engine_invocation_permitted: bool = False
    real_runtime_access_permitted: bool = False
    external_effects_permitted: bool = False
    phase21_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.admission_id or len(self.admission_digest) != 64:
            raise ValueError("Phase 20 admission lineage is invalid.")

        if self.schema_version != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_SCHEMA_VERSION
        ):
            raise ValueError("Phase 20 engine-blueprint schema is invalid.")

        if self.source != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_SOURCE
        ):
            raise ValueError("Phase 20 engine-blueprint source is invalid.")

        if self.status != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_STATUS
        ):
            raise ValueError("Phase 20 engine-blueprint status is invalid.")

        if self.next_allowed_step != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_NEXT_ALLOWED
        ):
            raise ValueError("Phase 20 engine-blueprint next step is invalid.")

        if tuple(item.name for item in self.components) != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS
        ):
            raise ValueError("Phase 20 engine components are incomplete.")

        if tuple(item.order for item in self.components) != tuple(
            range(1, len(self.components) + 1)
        ):
            raise ValueError("Phase 20 engine component order is invalid.")

        if tuple(item.name for item in self.invariants) != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_INVARIANTS
        ):
            raise ValueError("Phase 20 engine invariants are incomplete.")

        if self.symbol != "XAUUSD":
            raise ValueError("Phase 20 engine is restricted to XAUUSD.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 20 engine timeframe scope is invalid.")

        if self.states != PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES:
            raise ValueError("Phase 20 engine states are invalid.")

        if self.signal_evaluation_policy != "CANDLE_CLOSE_ONLY":
            raise ValueError("Phase 20 signal evaluation policy is invalid.")

        if self.entry_fill_policy != "NEXT_EVENT_OPEN_AFTER_SIGNAL_CLOSE":
            raise ValueError("Phase 20 entry-fill policy is invalid.")

        if self.same_bar_conflict_policy != "STOP_FIRST":
            raise ValueError("Phase 20 same-bar policy must be conservative.")

        if self.maximum_open_gold_positions != 1:
            raise ValueError("Phase 20 engine permits one Gold position.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("Phase 20 engine risk must remain 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("Phase 20 engine staged risk is invalid.")

        if self.blocked_capabilities != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_BLOCKED_CAPABILITIES
        ):
            raise ValueError("Phase 20 blocked capabilities are incomplete.")

        if not self.in_memory_only:
            raise ValueError("Phase 20.2 must remain in-memory only.")

        if not self.simulation_execution_permitted:
            raise ValueError("Phase 20.2 must preserve simulation admission.")

        if self.engine_invocation_permitted:
            raise ValueError("Phase 20.2 cannot invoke the engine.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 20.2 cannot permit real runtime access.")

        if self.external_effects_permitted:
            raise ValueError("Phase 20.2 cannot permit external effects.")

        if self.phase21_admitted:
            raise ValueError("Phase 21 cannot be admitted by Phase 20.2.")

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def invariant_count(self) -> int:
        return len(self.invariants)

    @property
    def blueprint_digest(self) -> str:
        """Hash bounded blueprint fields without recursive expansion."""

        material = "|".join(
            (
                self.admission_digest,
                self.schema_version,
                self.source,
                self.status,
                self.next_allowed_step,
                self.symbol,
                ",".join(self.timeframes),
                ",".join(self.states),
                self.signal_evaluation_policy,
                self.entry_fill_policy,
                self.same_bar_conflict_policy,
                str(self.maximum_open_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                ",".join(
                    (
                        f"{item.order}:{item.name}:"
                        f"{item.responsibility}"
                    )
                    for item in self.components
                ),
                ",".join(
                    f"{item.name}:{item.evidence}"
                    for item in self.invariants
                ),
                ",".join(self.blocked_capabilities),
                str(self.in_memory_only),
                str(self.simulation_execution_permitted),
                str(self.engine_invocation_permitted),
                str(self.real_runtime_access_permitted),
                str(self.external_effects_permitted),
                str(self.phase21_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def blueprint_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_20_IN_MEMORY_PAPER_RUNTIME_"
            "EXECUTION_ENGINE_BLUEPRINT:"
            f"SHA256[{self.blueprint_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineBlueprintDecision:
    """Decision wrapper for the Phase 20 engine blueprint."""

    ready: bool
    reason: str
    blueprint: Phase20InMemoryPaperRuntimeEngineBlueprint | None

    @property
    def blueprint_required(
        self,
    ) -> Phase20InMemoryPaperRuntimeEngineBlueprint:
        if not self.ready or self.blueprint is None:
            raise RuntimeError("Phase 20 engine blueprint is unavailable.")
        return self.blueprint


class Phase20InMemoryPaperRuntimeEngineBlueprintPlanner:
    """Build the deterministic in-memory paper execution blueprint."""

    def build(
        self,
        admission: Phase20InMemoryPaperRuntimeExecutionAdmission,
    ) -> Phase20InMemoryPaperRuntimeEngineBlueprintDecision:
        if (
            admission.status
            != PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_STATUS
            or not admission.in_memory_only
            or not admission.simulation_execution_permitted
            or admission.real_runtime_access_permitted
            or admission.external_effects_permitted
            or admission.phase21_admitted
        ):
            return Phase20InMemoryPaperRuntimeEngineBlueprintDecision(
                ready=False,
                reason="PHASE_20_ENGINE_BLUEPRINT_BLOCKED",
                blueprint=None,
            )

        responsibilities = (
            "Provide ordered immutable closed-candle events only.",
            "Advance one deterministic logical timestamp per event.",
            "Evaluate qualified signals at candle close without lookahead.",
            "Create paper-only intents with no broker representation.",
            "Enforce aggregate and staged risk before any paper fill.",
            "Apply deterministic entries, exits, and conservative ties.",
            "Attach mandatory stop-loss and OCO protection in memory.",
            "Model one-position lifecycle through terminal closure.",
            "Append immutable inputs, decisions, fills, and transitions.",
            "Cancel residual orders and prove terminal flatness.",
            "Reduce bounded trade, risk, and replay metrics.",
            "Seal deterministic output identity and replay summary.",
        )

        components = tuple(
            Phase20InMemoryPaperRuntimeEngineComponent(
                name=name,
                order=index,
                responsibility=responsibility,
            )
            for index, (name, responsibility) in enumerate(
                zip(
                    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS,
                    responsibilities,
                    strict=True,
                ),
                start=1,
            )
        )

        invariant_evidence = (
            "mode=PAPER",
            "execution_scope=IN_MEMORY_ONLY",
            "symbol=XAUUSD",
            "timeframes=H4,H1,M15,M5",
            "signal_evaluation_policy=CANDLE_CLOSE_ONLY",
            "lookahead_permitted=False",
            "maximum_open_gold_positions=1",
            "aggregate_risk_budget_bps=50",
            "stage_risk_bps=25,25",
            "oco_required=True",
            "stop_loss_required=True",
            "same_bar_conflict_policy=STOP_FIRST",
            "terminal_flat_required=True",
            "real_or_external_effects_permitted=False",
        )

        invariants = tuple(
            Phase20InMemoryPaperRuntimeEngineInvariant(
                name=name,
                evidence=evidence,
            )
            for name, evidence in zip(
                PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_INVARIANTS,
                invariant_evidence,
                strict=True,
            )
        )

        blueprint = Phase20InMemoryPaperRuntimeEngineBlueprint(
            admission_id=admission.admission_id,
            admission_digest=admission.admission_digest,
            components=components,
            invariants=invariants,
        )

        return Phase20InMemoryPaperRuntimeEngineBlueprintDecision(
            ready=True,
            reason="PHASE_20_ENGINE_BLUEPRINT_READY",
            blueprint=blueprint,
        )


def build_phase20_in_memory_paper_runtime_execution_engine_blueprint(
) -> Phase20InMemoryPaperRuntimeEngineBlueprintDecision:
    """Build the deterministic Phase 20 in-memory engine blueprint."""

    admission = (
        admit_phase20_in_memory_paper_runtime_simulation_execution()
        .admission_required
    )
    return Phase20InMemoryPaperRuntimeEngineBlueprintPlanner().build(
        admission
    )


__all__ = (
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_SCHEMA_VERSION",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_SOURCE",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_STATUS",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_BLUEPRINT_NEXT_ALLOWED",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_COMPONENTS",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_INVARIANTS",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_STATES",
    "Phase20InMemoryPaperRuntimeEngineComponent",
    "Phase20InMemoryPaperRuntimeEngineInvariant",
    "Phase20InMemoryPaperRuntimeEngineBlueprint",
    "Phase20InMemoryPaperRuntimeEngineBlueprintDecision",
    "Phase20InMemoryPaperRuntimeEngineBlueprintPlanner",
    "build_phase20_in_memory_paper_runtime_execution_engine_blueprint",
)
