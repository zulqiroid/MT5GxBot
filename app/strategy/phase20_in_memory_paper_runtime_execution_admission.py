from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase19_paper_runtime_simulation_execution_final_handoff import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_STATUS,
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG,
    Phase19PaperRuntimeSimulationExecutionFinalHandoff,
    generate_phase19_paper_runtime_simulation_execution_final_handoff,
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_SCHEMA_VERSION = "1.0"
PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_SOURCE = (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_STATUS
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_STATUS = (
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMITTED"
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_NEXT_ALLOWED = (
    "DETERMINISTIC_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ENGINE_BLUEPRINT"
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_REQUIREMENTS = (
    "PHASE_19_RELEASE_LINEAGE_VERIFIED",
    "PAPER_MODE_ONLY",
    "IN_MEMORY_EXECUTION_ONLY",
    "XAUUSD_ONLY",
    "H4_H1_M15_M5_ONLY",
    "CLOSED_CANDLES_ONLY",
    "ONE_OPEN_GOLD_POSITION_MAXIMUM",
    "AGGREGATE_RISK_50_BPS",
    "STAGED_RISK_25_PLUS_25_BPS",
    "OCO_STOP_LOSS_AND_TERMINAL_FLAT_REQUIRED",
    "MARTINGALE_GRID_NO_SL_FORBIDDEN",
    "NO_REAL_OR_EXTERNAL_EFFECTS",
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_BLOCKED_CAPABILITIES = (
    "REAL_PREFLIGHT_BLOCKED",
    "MT5_INITIALIZATION_BLOCKED",
    "TERMINAL_ACCESS_BLOCKED",
    "BROKER_READ_BLOCKED",
    "BROKER_WRITE_BLOCKED",
    "ACCOUNT_ACCESS_BLOCKED",
    "PRODUCTION_MODE_BLOCKED",
    "LIVE_TRADING_BLOCKED",
    "NETWORK_SIDE_EFFECTS_BLOCKED",
    "FILESYSTEM_TRADE_SIDE_EFFECTS_BLOCKED",
)


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeExecutionAdmissionRequirement:
    """One immutable Phase 20 in-memory execution requirement."""

    name: str
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_REQUIREMENTS
        ):
            raise ValueError("Unknown Phase 20 admission requirement.")

        if not self.evidence:
            raise ValueError("Phase 20 admission evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeExecutionAdmission:
    """Fail-closed admission for in-memory paper simulation execution."""

    phase19_handoff_id: str
    phase19_handoff_digest: str
    requirements: tuple[
        Phase20InMemoryPaperRuntimeExecutionAdmissionRequirement,
        ...,
    ]
    schema_version: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_SCHEMA_VERSION
    )
    source: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_SOURCE
    )
    status: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_STATUS
    )
    next_allowed_step: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_NEXT_ALLOWED
    )
    release_tag: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG
    )
    symbol: str = "XAUUSD"
    timeframes: tuple[str, ...] = ("H4", "H1", "M15", "M5")
    closed_candles_only: bool = True
    maximum_open_gold_positions: int = 1
    aggregate_risk_budget_bps: int = 50
    stage_risk_bps: tuple[int, int] = (25, 25)
    blocked_capabilities: tuple[str, ...] = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_BLOCKED_CAPABILITIES
    )
    in_memory_only: bool = True
    simulation_execution_permitted: bool = True
    real_runtime_access_permitted: bool = False
    external_effects_permitted: bool = False
    remote_push_permitted: bool = False
    phase21_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.phase19_handoff_id:
            raise ValueError("Phase 19 handoff ID is required.")

        if len(self.phase19_handoff_digest) != 64:
            raise ValueError("Phase 19 handoff digest is invalid.")

        if self.schema_version != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_SCHEMA_VERSION
        ):
            raise ValueError("Phase 20 admission schema is invalid.")

        if self.source != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_SOURCE
        ):
            raise ValueError("Phase 20 admission source is invalid.")

        if self.status != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_STATUS
        ):
            raise ValueError("Phase 20 admission status is invalid.")

        if self.next_allowed_step != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_NEXT_ALLOWED
        ):
            raise ValueError("Phase 20 next step is invalid.")

        if self.release_tag != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG
        ):
            raise ValueError("Phase 19 release-tag lineage is invalid.")

        if tuple(item.name for item in self.requirements) != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_REQUIREMENTS
        ):
            raise ValueError("Phase 20 admission requirements are incomplete.")

        if self.symbol != "XAUUSD":
            raise ValueError("Phase 20 is restricted to XAUUSD.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 20 timeframe scope is invalid.")

        if not self.closed_candles_only:
            raise ValueError("Phase 20 requires closed candles only.")

        if self.maximum_open_gold_positions != 1:
            raise ValueError("Phase 20 permits one Gold position maximum.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("Phase 20 aggregate risk must remain 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("Phase 20 staged risk must remain 25 + 25 bps.")

        if self.blocked_capabilities != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_BLOCKED_CAPABILITIES
        ):
            raise ValueError("Phase 20 blocked capabilities are incomplete.")

        if not self.in_memory_only:
            raise ValueError("Phase 20.1 must remain in-memory only.")

        if not self.simulation_execution_permitted:
            raise ValueError("Phase 20.1 must admit paper simulation execution.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 20.1 cannot permit real runtime access.")

        if self.external_effects_permitted:
            raise ValueError("Phase 20.1 cannot permit external effects.")

        if self.remote_push_permitted:
            raise ValueError("Phase 20.1 cannot permit remote push.")

        if self.phase21_admitted:
            raise ValueError("Phase 21 cannot be admitted by Phase 20.1.")

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    @property
    def admission_digest(self) -> str:
        """Hash bounded Phase 20 admission fields."""

        material = "|".join(
            (
                self.phase19_handoff_digest,
                self.schema_version,
                self.source,
                self.status,
                self.next_allowed_step,
                self.release_tag,
                self.symbol,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                str(self.maximum_open_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                ",".join(
                    f"{item.name}:{item.evidence}"
                    for item in self.requirements
                ),
                ",".join(self.blocked_capabilities),
                str(self.in_memory_only),
                str(self.simulation_execution_permitted),
                str(self.real_runtime_access_permitted),
                str(self.external_effects_permitted),
                str(self.remote_push_permitted),
                str(self.phase21_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def admission_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_20_IN_MEMORY_PAPER_RUNTIME_"
            "SIMULATION_EXECUTION_ADMISSION:"
            f"SHA256[{self.admission_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeExecutionAdmissionDecision:
    """Decision wrapper for Phase 20 in-memory execution admission."""

    admitted: bool
    reason: str
    admission: Phase20InMemoryPaperRuntimeExecutionAdmission | None

    @property
    def admission_required(
        self,
    ) -> Phase20InMemoryPaperRuntimeExecutionAdmission:
        if not self.admitted or self.admission is None:
            raise RuntimeError("Phase 20 execution admission is unavailable.")
        return self.admission


class Phase20InMemoryPaperRuntimeExecutionAdmissionGate:
    """Admit deterministic in-memory paper execution only."""

    def evaluate(
        self,
        handoff: Phase19PaperRuntimeSimulationExecutionFinalHandoff,
    ) -> Phase20InMemoryPaperRuntimeExecutionAdmissionDecision:
        guard_evidence = {
            item.name: item.evidence for item in handoff.guards
        }

        admitted = (
            handoff.status
            == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_STATUS
            and handoff.guard_count == 10
            and handoff.passed_count == 10
            and handoff.release_tag
            == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG
            and handoff.release_tag_creation_permitted
            and not handoff.remote_push_permitted
            and not handoff.simulation_execution_permitted
            and not handoff.real_runtime_access_permitted
            and not handoff.external_effects_permitted
            and not handoff.phase20_admitted
        )

        if not admitted:
            return Phase20InMemoryPaperRuntimeExecutionAdmissionDecision(
                admitted=False,
                reason="PHASE_20_IN_MEMORY_EXECUTION_ADMISSION_BLOCKED",
                admission=None,
            )

        requirement_evidence = (
            (
                "handoff="
                f"{handoff.handoff_id};release_tag={handoff.release_tag}"
            ),
            "mode=PAPER",
            "execution_scope=IN_MEMORY_ONLY",
            "symbol=XAUUSD",
            "timeframes=H4,H1,M15,M5",
            "closed_candles_only=True",
            "maximum_open_gold_positions=1",
            "aggregate_risk_budget_bps=50",
            "stage_risk_bps=25,25",
            guard_evidence["OCO_STOP_LOSS_AND_FLATNESS_PRESERVED"],
            guard_evidence["UNSAFE_POSITIONING_PATTERNS_BLOCKED"],
            guard_evidence["REAL_AND_EXTERNAL_EFFECTS_BLOCKED"],
        )

        requirements = tuple(
            Phase20InMemoryPaperRuntimeExecutionAdmissionRequirement(
                name=name,
                evidence=evidence,
            )
            for name, evidence in zip(
                PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_REQUIREMENTS,
                requirement_evidence,
                strict=True,
            )
        )

        admission = Phase20InMemoryPaperRuntimeExecutionAdmission(
            phase19_handoff_id=handoff.handoff_id,
            phase19_handoff_digest=handoff.handoff_digest,
            requirements=requirements,
        )

        return Phase20InMemoryPaperRuntimeExecutionAdmissionDecision(
            admitted=True,
            reason="PHASE_20_IN_MEMORY_EXECUTION_ADMITTED",
            admission=admission,
        )


def admit_phase20_in_memory_paper_runtime_simulation_execution(
) -> Phase20InMemoryPaperRuntimeExecutionAdmissionDecision:
    """Admit paper simulation execution with zero external effects."""

    handoff = (
        generate_phase19_paper_runtime_simulation_execution_final_handoff()
        .handoff_required
    )
    return Phase20InMemoryPaperRuntimeExecutionAdmissionGate().evaluate(
        handoff
    )


__all__ = (
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_SCHEMA_VERSION",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_SOURCE",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_STATUS",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_NEXT_ALLOWED",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ADMISSION_REQUIREMENTS",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_EXECUTION_BLOCKED_CAPABILITIES",
    "Phase20InMemoryPaperRuntimeExecutionAdmissionRequirement",
    "Phase20InMemoryPaperRuntimeExecutionAdmission",
    "Phase20InMemoryPaperRuntimeExecutionAdmissionDecision",
    "Phase20InMemoryPaperRuntimeExecutionAdmissionGate",
    "admit_phase20_in_memory_paper_runtime_simulation_execution",
)
