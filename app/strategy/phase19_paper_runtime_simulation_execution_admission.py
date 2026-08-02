from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase18_paper_runtime_simulation_final_handoff import (
    PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_NEXT_ALLOWED,
    PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_STATUS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG,
    Phase18PaperRuntimeSimulationFinalHandoff,
    generate_phase18_paper_runtime_simulation_final_handoff,
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_SCHEMA_VERSION = "1.0"
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_SOURCE = (
    PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_STATUS
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_STATUS = (
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_PLANNING_ADMITTED"
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_NEXT_ALLOWED = (
    "DETERMINISTIC_PAPER_RUNTIME_SIMULATION_EXECUTION_BLUEPRINT"
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_REQUIREMENTS = (
    "PHASE_18_RELEASE_LINEAGE_VERIFIED",
    "PAPER_MODE_ONLY",
    "XAUUSD_ONLY",
    "H4_H1_M15_M5_ONLY",
    "CLOSED_CANDLES_ONLY",
    "ONE_OPEN_GOLD_POSITION_MAXIMUM",
    "AGGREGATE_RISK_50_BPS",
    "STAGED_RISK_25_PLUS_25_BPS",
    "NO_REAL_OR_EXTERNAL_EFFECTS",
    "EXECUTION_REMAINS_BLOCKED_PENDING_BLUEPRINT",
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLOCKED_CAPABILITIES = (
    "REAL_PREFLIGHT_BLOCKED",
    "MT5_INITIALIZATION_BLOCKED",
    "TERMINAL_ACCESS_BLOCKED",
    "BROKER_READ_BLOCKED",
    "BROKER_WRITE_BLOCKED",
    "ACCOUNT_ACCESS_BLOCKED",
    "PRODUCTION_MODE_BLOCKED",
    "LIVE_TRADING_BLOCKED",
    "SIMULATION_EXECUTION_BLOCKED",
)


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionAdmissionRequirement:
    """One immutable Phase 19 execution-planning requirement."""

    name: str
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_REQUIREMENTS
        ):
            raise ValueError("Unknown Phase 19 admission requirement.")

        if not self.evidence:
            raise ValueError("Phase 19 admission evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionAdmission:
    """Fail-closed Phase 19 execution-planning admission."""

    phase18_handoff_id: str
    phase18_handoff_digest: str
    requirements: tuple[
        Phase19PaperRuntimeSimulationExecutionAdmissionRequirement,
        ...,
    ]
    schema_version: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_SCHEMA_VERSION
    )
    source: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_SOURCE
    )
    status: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_STATUS
    )
    next_allowed_step: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_NEXT_ALLOWED
    )
    release_tag: str = PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG
    symbol: str = "XAUUSD"
    timeframes: tuple[str, ...] = ("H4", "H1", "M15", "M5")
    closed_candles_only: bool = True
    maximum_open_gold_positions: int = 1
    aggregate_risk_budget_bps: int = 50
    stage_risk_bps: tuple[int, int] = (25, 25)
    blocked_capabilities: tuple[str, ...] = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLOCKED_CAPABILITIES
    )
    planning_permitted: bool = True
    simulation_execution_permitted: bool = False
    real_runtime_access_permitted: bool = False
    phase20_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.phase18_handoff_id:
            raise ValueError("Phase 18 handoff ID is required.")

        if len(self.phase18_handoff_digest) != 64:
            raise ValueError("Phase 18 handoff digest is invalid.")

        if self.schema_version != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_SCHEMA_VERSION
        ):
            raise ValueError("Phase 19 admission schema is invalid.")

        if self.source != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_SOURCE
        ):
            raise ValueError("Phase 19 admission source is invalid.")

        if self.status != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_STATUS
        ):
            raise ValueError("Phase 19 admission status is invalid.")

        if self.next_allowed_step != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_NEXT_ALLOWED
        ):
            raise ValueError("Phase 19 next step is invalid.")

        if self.release_tag != PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG:
            raise ValueError("Phase 18 release tag lineage is invalid.")

        if tuple(item.name for item in self.requirements) != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_REQUIREMENTS
        ):
            raise ValueError("Phase 19 admission requirements are incomplete.")

        if self.symbol != "XAUUSD":
            raise ValueError("Phase 19 is restricted to XAUUSD.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 19 timeframe scope is invalid.")

        if not self.closed_candles_only:
            raise ValueError("Phase 19 requires closed candles only.")

        if self.maximum_open_gold_positions != 1:
            raise ValueError("Phase 19 permits one Gold position maximum.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("Phase 19 aggregate risk must remain 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("Phase 19 staged risk must remain 25 + 25 bps.")

        if self.blocked_capabilities != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLOCKED_CAPABILITIES
        ):
            raise ValueError("Phase 19 blocked capabilities are incomplete.")

        if not self.planning_permitted:
            raise ValueError("Phase 19 execution planning must be permitted.")

        if self.simulation_execution_permitted:
            raise ValueError("Phase 19.1 cannot permit simulation execution.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 19.1 cannot permit real runtime access.")

        if self.phase20_admitted:
            raise ValueError("Phase 20 cannot be admitted by Phase 19.1.")

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    @property
    def admission_digest(self) -> str:
        """Hash bounded Phase 19 admission fields."""

        material = "|".join(
            (
                self.phase18_handoff_digest,
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
                str(self.planning_permitted),
                str(self.simulation_execution_permitted),
                str(self.real_runtime_access_permitted),
                str(self.phase20_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def admission_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_19_PAPER_RUNTIME_SIMULATION_"
            "EXECUTION_ADMISSION:"
            f"SHA256[{self.admission_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionAdmissionDecision:
    """Decision wrapper for Phase 19 execution-planning admission."""

    admitted: bool
    reason: str
    admission: Phase19PaperRuntimeSimulationExecutionAdmission | None

    @property
    def admission_required(
        self,
    ) -> Phase19PaperRuntimeSimulationExecutionAdmission:
        if not self.admitted or self.admission is None:
            raise RuntimeError("Phase 19 admission is unavailable.")
        return self.admission


class Phase19PaperRuntimeSimulationExecutionAdmissionGate:
    """Admit Phase 19 planning while keeping all execution blocked."""

    def evaluate(
        self,
        handoff: Phase18PaperRuntimeSimulationFinalHandoff,
    ) -> Phase19PaperRuntimeSimulationExecutionAdmissionDecision:
        guard_evidence = {
            item.name: item.evidence for item in handoff.guards
        }

        admitted = (
            handoff.status
            == PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_STATUS
            and handoff.guard_count == 10
            and handoff.passed_count == 10
            and handoff.next_allowed_step
            == PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_NEXT_ALLOWED
            and handoff.release_tag
            == PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG
            and handoff.release_tag_creation_permitted
            and not handoff.remote_push_permitted
            and not handoff.simulation_execution_permitted
            and not handoff.real_runtime_access_permitted
            and not handoff.phase19_admitted
        )

        if not admitted:
            return Phase19PaperRuntimeSimulationExecutionAdmissionDecision(
                admitted=False,
                reason="PHASE_19_EXECUTION_PLANNING_ADMISSION_BLOCKED",
                admission=None,
            )

        requirements = (
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="PHASE_18_RELEASE_LINEAGE_VERIFIED",
                evidence=(
                    f"handoff={handoff.handoff_id};"
                    f"release_tag={handoff.release_tag}"
                ),
            ),
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="PAPER_MODE_ONLY",
                evidence=guard_evidence["PAPER_MODE_SCOPE_CONFIRMED"],
            ),
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="XAUUSD_ONLY",
                evidence=guard_evidence["XAUUSD_SCOPE_CONFIRMED"],
            ),
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="H4_H1_M15_M5_ONLY",
                evidence="timeframes=H4,H1,M15,M5",
            ),
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="CLOSED_CANDLES_ONLY",
                evidence=guard_evidence["CLOSED_CANDLE_SCOPE_CONFIRMED"],
            ),
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="ONE_OPEN_GOLD_POSITION_MAXIMUM",
                evidence="maximum_open_gold_positions=1",
            ),
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="AGGREGATE_RISK_50_BPS",
                evidence="aggregate_risk_budget_bps=50",
            ),
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="STAGED_RISK_25_PLUS_25_BPS",
                evidence="stage_risk_bps=25,25",
            ),
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="NO_REAL_OR_EXTERNAL_EFFECTS",
                evidence=(
                    "real_runtime_access_permitted=False;"
                    "external_effects_permitted=False"
                ),
            ),
            Phase19PaperRuntimeSimulationExecutionAdmissionRequirement(
                name="EXECUTION_REMAINS_BLOCKED_PENDING_BLUEPRINT",
                evidence="simulation_execution_permitted=False",
            ),
        )

        admission = Phase19PaperRuntimeSimulationExecutionAdmission(
            phase18_handoff_id=handoff.handoff_id,
            phase18_handoff_digest=handoff.handoff_digest,
            requirements=requirements,
        )

        return Phase19PaperRuntimeSimulationExecutionAdmissionDecision(
            admitted=True,
            reason="PHASE_19_EXECUTION_PLANNING_ADMITTED",
            admission=admission,
        )


def admit_phase19_paper_runtime_simulation_execution_planning(
) -> Phase19PaperRuntimeSimulationExecutionAdmissionDecision:
    """Admit Phase 19 planning without permitting execution."""

    handoff = (
        generate_phase18_paper_runtime_simulation_final_handoff()
        .handoff_required
    )
    return Phase19PaperRuntimeSimulationExecutionAdmissionGate().evaluate(
        handoff
    )


__all__ = (
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_SCHEMA_VERSION",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_SOURCE",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_STATUS",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_NEXT_ALLOWED",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_ADMISSION_REQUIREMENTS",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_BLOCKED_CAPABILITIES",
    "Phase19PaperRuntimeSimulationExecutionAdmissionRequirement",
    "Phase19PaperRuntimeSimulationExecutionAdmission",
    "Phase19PaperRuntimeSimulationExecutionAdmissionDecision",
    "Phase19PaperRuntimeSimulationExecutionAdmissionGate",
    "admit_phase19_paper_runtime_simulation_execution_planning",
)
