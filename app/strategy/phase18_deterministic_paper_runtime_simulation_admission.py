from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMISSION_SCHEMA_VERSION = "1.0"
PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED = (
    "PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED"
)
PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_BLUEPRINT = (
    "DETERMINISTIC_PAPER_RUNTIME_SIMULATION_BLUEPRINT"
)

_GOLD_SYMBOL = "XAUUSD"
_TIMEFRAMES = ("H4", "H1", "M15", "M5")
_STAGE_RISK_BPS = (25, 25)
_BLOCKED_RUNTIME_STATUSES = (
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
class Phase18DeterministicPaperRuntimeSimulationAdmissionPermit:
    """Fail-closed permit for Phase 18 planning only."""

    schema_version: str = (
        PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMISSION_SCHEMA_VERSION
    )
    phase_status: str = PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED
    next_allowed_step: str = (
        PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_BLUEPRINT
    )
    mode: str = "PAPER"
    symbol: str = _GOLD_SYMBOL
    timeframes: tuple[str, ...] = _TIMEFRAMES
    closed_candles_only: bool = True
    planning_permitted: bool = True
    simulation_execution_permitted: bool = False
    maximum_open_gold_positions: int = 1
    aggregate_risk_budget_bps: int = 50
    stage_risk_bps: tuple[int, int] = _STAGE_RISK_BPS
    oco_required: bool = True
    broker_stop_loss_required: bool = True
    terminal_flat_required: bool = True
    martingale_forbidden: bool = True
    grid_forbidden: bool = True
    no_stop_loss_forbidden: bool = True
    blocked_runtime_statuses: tuple[str, ...] = _BLOCKED_RUNTIME_STATUSES
    no_real_or_external_effects: bool = True
    phase19_admitted: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != (
            PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMISSION_SCHEMA_VERSION
        ):
            raise ValueError("Phase 18 admission schema version is invalid.")

        if self.phase_status != (
            PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED
        ):
            raise ValueError("Phase 18 admission status is invalid.")

        if self.next_allowed_step != (
            PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_BLUEPRINT
        ):
            raise ValueError("Phase 18 next step is invalid.")

        if self.mode != "PAPER":
            raise ValueError("Phase 18 admission must remain in PAPER mode.")

        if self.symbol != _GOLD_SYMBOL:
            raise ValueError("Phase 18 admission is Gold-only.")

        if self.timeframes != _TIMEFRAMES:
            raise ValueError("Phase 18 timeframes are invalid.")

        if not self.closed_candles_only:
            raise ValueError("Phase 18 must use closed candles only.")

        if not self.planning_permitted:
            raise ValueError("Phase 18 planning must be permitted.")

        if self.simulation_execution_permitted:
            raise ValueError("Phase 18.1 cannot permit simulation execution.")

        if self.maximum_open_gold_positions != 1:
            raise ValueError("Only one Gold position may be open.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("Aggregate staged risk must remain 50 bps.")

        if self.stage_risk_bps != _STAGE_RISK_BPS:
            raise ValueError("Stage risk must remain 25 + 25 bps.")

        if not (
            self.oco_required
            and self.broker_stop_loss_required
            and self.terminal_flat_required
        ):
            raise ValueError("Execution safety invariants are incomplete.")

        if not (
            self.martingale_forbidden
            and self.grid_forbidden
            and self.no_stop_loss_forbidden
        ):
            raise ValueError("Forbidden strategy invariants are incomplete.")

        if self.blocked_runtime_statuses != _BLOCKED_RUNTIME_STATUSES:
            raise ValueError("Real runtime statuses must remain blocked.")

        if not self.no_real_or_external_effects:
            raise ValueError("Phase 18.1 must have no real effects.")

        if self.phase19_admitted:
            raise ValueError("Phase 19 cannot be admitted by Phase 18.1.")

    @property
    def admission_digest(self) -> str:
        """Return a deterministic digest without recursive lineage expansion."""

        material = "|".join(
            (
                self.schema_version,
                self.phase_status,
                self.next_allowed_step,
                self.mode,
                self.symbol,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                str(self.planning_permitted),
                str(self.simulation_execution_permitted),
                str(self.maximum_open_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(map(str, self.stage_risk_bps)),
                str(self.oco_required),
                str(self.broker_stop_loss_required),
                str(self.terminal_flat_required),
                str(self.martingale_forbidden),
                str(self.grid_forbidden),
                str(self.no_stop_loss_forbidden),
                ",".join(self.blocked_runtime_statuses),
                str(self.no_real_or_external_effects),
                str(self.phase19_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def admission_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_18_DETERMINISTIC_PAPER_RUNTIME_"
            f"SIMULATION_ADMISSION:SHA256[{self.admission_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase18DeterministicPaperRuntimeSimulationAdmissionDecision:
    """Decision wrapper that exposes the permit only after admission."""

    admitted: bool
    reason: str
    permit: Phase18DeterministicPaperRuntimeSimulationAdmissionPermit | None

    @property
    def permit_required(
        self,
    ) -> Phase18DeterministicPaperRuntimeSimulationAdmissionPermit:
        if not self.admitted or self.permit is None:
            raise RuntimeError("Phase 18 admission permit is unavailable.")
        return self.permit


def admit_phase18_deterministic_paper_runtime_simulation(
) -> Phase18DeterministicPaperRuntimeSimulationAdmissionDecision:
    """Admit Phase 18 planning while keeping every runtime effect blocked."""

    permit = Phase18DeterministicPaperRuntimeSimulationAdmissionPermit()

    return Phase18DeterministicPaperRuntimeSimulationAdmissionDecision(
        admitted=True,
        reason="PHASE_18_ADMISSION_READY_FOR_BLUEPRINT",
        permit=permit,
    )


__all__ = (
    "PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMISSION_SCHEMA_VERSION",
    "PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_ADMITTED",
    "PHASE_18_DETERMINISTIC_PAPER_RUNTIME_SIMULATION_BLUEPRINT",
    "Phase18DeterministicPaperRuntimeSimulationAdmissionPermit",
    "Phase18DeterministicPaperRuntimeSimulationAdmissionDecision",
    "admit_phase18_deterministic_paper_runtime_simulation",
)
