"""Immutable deterministic simulation scenario contract for Phase 9.

This module consumes the Phase 9 simulation-only admission permit and
creates one immutable XAUUSD scenario contract. The contract contains only
closed-candle snapshots for H4, H1, M15, and M5 plus explicit risk, OCO,
broker stop-loss, and kill-switch constraints. It does not evaluate a
strategy, execute a simulation, initialize MT5, contact a broker, write
external state, or submit orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_9_SIMULATION_SCENARIO_SCHEMA_VERSION = "1.0"
PHASE_9_SIMULATION_SCENARIO_STATUS = "CONTRACT_READY"
PHASE_9_SIMULATION_SCENARIO_ID = "XAUUSD_CLOSED_CANDLE_SCENARIO_001"
PHASE_9_SIMULATION_SCENARIO_SYMBOL = "XAUUSD"
PHASE_9_SIMULATION_SCENARIO_TIMEFRAMES = ("H4", "H1", "M15", "M5")
PHASE_9_SIMULATION_SCENARIO_SIDE = "LONG"
PHASE_9_SIMULATION_PRICE_SCALE = 100
PHASE_9_SIMULATION_MAX_GOLD_POSITIONS = 1
PHASE_9_SIMULATION_AGGREGATE_RISK_BPS = 50
PHASE_9_SIMULATION_STAGE_RISK_BPS = (25, 25)
PHASE_9_SIMULATION_OCO_GROUP_ID = "SIM-XAUUSD-OCO-001"
PHASE_9_SIMULATION_KILL_SWITCHES = (
    "daily_loss_limit",
    "spread_guard",
    "stale_data_guard",
    "duplicate_position_guard",
)


def _required_attribute(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase9ClosedCandleSnapshot:
    """Immutable closed-candle snapshot using integer price points."""

    timeframe: str
    close_time_utc: str
    open_price_points: int
    high_price_points: int
    low_price_points: int
    close_price_points: int
    tick_volume: int
    is_closed: bool

    def __post_init__(self) -> None:
        if self.timeframe not in PHASE_9_SIMULATION_SCENARIO_TIMEFRAMES:
            raise ValueError("unsupported timeframe.")

        if not self.close_time_utc.endswith("Z"):
            raise ValueError("close_time_utc must be UTC.")

        prices = (
            self.open_price_points,
            self.high_price_points,
            self.low_price_points,
            self.close_price_points,
        )
        if any(
            isinstance(price, bool) or not isinstance(price, int) or price <= 0 for price in prices
        ):
            raise ValueError("candle prices must be positive integers.")

        if self.high_price_points < max(
            self.open_price_points,
            self.close_price_points,
        ):
            raise ValueError("high price is inconsistent.")

        if self.low_price_points > min(
            self.open_price_points,
            self.close_price_points,
        ):
            raise ValueError("low price is inconsistent.")

        if self.low_price_points > self.high_price_points:
            raise ValueError("candle range is inconsistent.")

        if (
            isinstance(self.tick_volume, bool)
            or not isinstance(self.tick_volume, int)
            or self.tick_volume < 1
        ):
            raise ValueError("tick_volume must be positive.")

        if self.is_closed is not True:
            raise ValueError("Phase 9 accepts closed candles only.")

    @property
    def candle_digest(self) -> str:
        material = "|".join(
            (
                self.timeframe,
                self.close_time_utc,
                str(self.open_price_points),
                str(self.high_price_points),
                str(self.low_price_points),
                str(self.close_price_points),
                str(self.tick_volume),
                str(self.is_closed),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase9SimulationScenarioContract:
    """Immutable deterministic simulation scenario contract."""

    admission_decision: object
    admission_permit: object

    scenario_id: str
    schema_version: str
    status: str
    symbol: str
    timeframes: tuple[str, ...]
    closed_candles: tuple[Phase9ClosedCandleSnapshot, ...]

    side: str
    entry_price_points: int
    stop_loss_price_points: int
    take_profit_price_points: int
    price_scale: int

    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]
    oco_group_id: str
    broker_stop_loss_required: bool
    kill_switches: tuple[str, ...]

    closed_candles_only: bool
    one_gold_position_max: bool
    staged_aggregate_risk_required: bool
    oco_required: bool
    martingale_prohibited: bool
    grid_prohibited: bool
    no_stop_loss_prohibited: bool
    kill_switches_required: bool

    permits_simulation_planning: bool
    permits_simulation_execution: bool
    permits_strategy_evaluation: bool
    permits_mt5_initialization: bool
    permits_broker_requests: bool
    permits_external_writes: bool
    permits_order_submission: bool

    def __post_init__(self) -> None:
        if self.scenario_id != PHASE_9_SIMULATION_SCENARIO_ID:
            raise ValueError("scenario_id is inconsistent.")

        if self.schema_version != PHASE_9_SIMULATION_SCENARIO_SCHEMA_VERSION:
            raise ValueError("schema version is inconsistent.")

        if self.status != PHASE_9_SIMULATION_SCENARIO_STATUS:
            raise ValueError("scenario status must be CONTRACT_READY.")

        if self.symbol != PHASE_9_SIMULATION_SCENARIO_SYMBOL:
            raise ValueError("scenario must be XAUUSD only.")

        if self.timeframes != PHASE_9_SIMULATION_SCENARIO_TIMEFRAMES:
            raise ValueError("scenario timeframes are inconsistent.")

        if len(self.closed_candles) != len(self.timeframes):
            raise ValueError("one closed candle is required per timeframe.")

        candle_timeframes = tuple(candle.timeframe for candle in self.closed_candles)
        if candle_timeframes != self.timeframes:
            raise ValueError("closed candles are not timeframe ordered.")

        if any(candle.is_closed is not True for candle in self.closed_candles):
            raise ValueError("scenario contains an open candle.")

        if self.side != PHASE_9_SIMULATION_SCENARIO_SIDE:
            raise ValueError("scenario side is inconsistent.")

        price_values = (
            self.entry_price_points,
            self.stop_loss_price_points,
            self.take_profit_price_points,
        )
        if any(
            isinstance(price, bool) or not isinstance(price, int) or price <= 0
            for price in price_values
        ):
            raise ValueError("scenario prices must be positive integers.")

        if not (
            self.stop_loss_price_points < self.entry_price_points < self.take_profit_price_points
        ):
            raise ValueError("LONG scenario price ordering is invalid.")

        if self.price_scale != PHASE_9_SIMULATION_PRICE_SCALE:
            raise ValueError("price scale is inconsistent.")

        if self.max_gold_positions != 1:
            raise ValueError("only one Gold position is allowed.")

        if self.aggregate_risk_budget_bps <= 0:
            raise ValueError("aggregate risk budget must be positive.")

        if not self.stage_risk_bps:
            raise ValueError("stage risk allocation is required.")

        if any(
            isinstance(risk_bps, bool) or not isinstance(risk_bps, int) or risk_bps <= 0
            for risk_bps in self.stage_risk_bps
        ):
            raise ValueError("stage risk values must be positive integers.")

        if sum(self.stage_risk_bps) != self.aggregate_risk_budget_bps:
            raise ValueError("stage risk must equal aggregate risk budget.")

        if self.oco_group_id != PHASE_9_SIMULATION_OCO_GROUP_ID:
            raise ValueError("OCO group is inconsistent.")

        if self.kill_switches != PHASE_9_SIMULATION_KILL_SWITCHES:
            raise ValueError("kill-switch contract is inconsistent.")

        required_truths = (
            self.broker_stop_loss_required,
            self.closed_candles_only,
            self.one_gold_position_max,
            self.staged_aggregate_risk_required,
            self.oco_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.kill_switches_required,
            self.permits_simulation_planning,
        )
        if not all(required_truths):
            raise ValueError("scenario lost a required invariant.")

        forbidden_capabilities = (
            self.permits_simulation_execution,
            self.permits_strategy_evaluation,
            self.permits_mt5_initialization,
            self.permits_broker_requests,
            self.permits_external_writes,
            self.permits_order_submission,
        )
        if any(forbidden_capabilities):
            raise ValueError("scenario contract cannot enable execution.")

    @property
    def scenario_digest(self) -> str:
        admission_id = str(getattr(self.admission_permit, "permit_id", ""))
        candle_material = ",".join(candle.candle_digest for candle in self.closed_candles)
        material = "|".join(
            (
                self.schema_version,
                admission_id,
                self.scenario_id,
                self.status,
                self.symbol,
                ",".join(self.timeframes),
                candle_material,
                self.side,
                str(self.entry_price_points),
                str(self.stop_loss_price_points),
                str(self.take_profit_price_points),
                str(self.price_scale),
                str(self.max_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                self.oco_group_id,
                str(self.broker_stop_loss_required),
                ",".join(self.kill_switches),
                str(self.closed_candles_only),
                str(self.one_gold_position_max),
                str(self.staged_aggregate_risk_required),
                str(self.oco_required),
                str(self.martingale_prohibited),
                str(self.grid_prohibited),
                str(self.no_stop_loss_prohibited),
                str(self.kill_switches_required),
                str(self.permits_simulation_planning),
                str(self.permits_simulation_execution),
                str(self.permits_strategy_evaluation),
                str(self.permits_mt5_initialization),
                str(self.permits_broker_requests),
                str(self.permits_external_writes),
                str(self.permits_order_submission),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def contract_id(self) -> str:
        return f"GOLDXBOT_PHASE_9_SIMULATION_SCENARIO:SHA256[{self.scenario_digest}]"


@dataclass(frozen=True, slots=True)
class Phase9SimulationScenarioDecision:
    """Allowed or blocked simulation scenario decision."""

    is_allowed: bool
    contract: Phase9SimulationScenarioContract | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.contract is None:
                raise ValueError("Allowed decision requires a contract.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.contract is not None:
                raise ValueError("Blocked decision cannot have a contract.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def contract_required(self) -> Phase9SimulationScenarioContract:
        if self.contract is None:
            raise RuntimeError("Phase 9 simulation scenario is blocked.")
        return self.contract


class StrategyPhase9SimulationScenarioFactory:
    """Creates the immutable deterministic simulation scenario."""

    def create(
        self,
        admission_decision: object,
    ) -> Phase9SimulationScenarioDecision:
        if admission_decision is None:
            return Phase9SimulationScenarioDecision(
                is_allowed=False,
                contract=None,
                blockers=("simulation_admission_decision_missing",),
            )

        if getattr(admission_decision, "is_allowed", True) is not True:
            return Phase9SimulationScenarioDecision(
                is_allowed=False,
                contract=None,
                blockers=("simulation_admission_decision_blocked",),
            )

        try:
            permit = _required_attribute(
                admission_decision,
                "permit_required",
            )
            admission_mode = _required_attribute(
                permit,
                "admission_mode",
            )
            admission_status = _required_attribute(
                permit,
                "admission_status",
            )
            live_execution_status = _required_attribute(
                permit,
                "live_execution_status",
            )
            allowed_symbol = _required_attribute(
                permit,
                "allowed_symbol",
            )
            allowed_timeframes = _required_attribute(
                permit,
                "allowed_timeframes",
            )
            closed_candles_only = _required_attribute(
                permit,
                "closed_candles_only",
            )
            phase9_foundation_ready = _required_attribute(
                permit,
                "phase9_foundation_ready",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase9SimulationScenarioDecision(
                is_allowed=False,
                contract=None,
                blockers=(f"simulation_admission_invalid:{type(error).__name__}",),
            )

        source_contract_valid = (
            admission_mode == "SIMULATION_ONLY"
            and admission_status == "ADMITTED"
            and live_execution_status == "BLOCKED"
            and allowed_symbol == PHASE_9_SIMULATION_SCENARIO_SYMBOL
            and allowed_timeframes == PHASE_9_SIMULATION_SCENARIO_TIMEFRAMES
            and closed_candles_only is True
            and phase9_foundation_ready is True
        )
        if not source_contract_valid:
            return Phase9SimulationScenarioDecision(
                is_allowed=False,
                contract=None,
                blockers=("simulation_admission_contract_invalid",),
            )

        candles = (
            Phase9ClosedCandleSnapshot(
                timeframe="H4",
                close_time_utc="2026-01-05T12:00:00Z",
                open_price_points=239850,
                high_price_points=241250,
                low_price_points=239400,
                close_price_points=240900,
                tick_volume=18420,
                is_closed=True,
            ),
            Phase9ClosedCandleSnapshot(
                timeframe="H1",
                close_time_utc="2026-01-05T12:00:00Z",
                open_price_points=240250,
                high_price_points=241050,
                low_price_points=240100,
                close_price_points=240900,
                tick_volume=7310,
                is_closed=True,
            ),
            Phase9ClosedCandleSnapshot(
                timeframe="M15",
                close_time_utc="2026-01-05T12:00:00Z",
                open_price_points=240620,
                high_price_points=241000,
                low_price_points=240500,
                close_price_points=240900,
                tick_volume=2640,
                is_closed=True,
            ),
            Phase9ClosedCandleSnapshot(
                timeframe="M5",
                close_time_utc="2026-01-05T12:00:00Z",
                open_price_points=240760,
                high_price_points=240980,
                low_price_points=240700,
                close_price_points=240900,
                tick_volume=980,
                is_closed=True,
            ),
        )

        try:
            contract = Phase9SimulationScenarioContract(
                admission_decision=admission_decision,
                admission_permit=permit,
                scenario_id=PHASE_9_SIMULATION_SCENARIO_ID,
                schema_version=PHASE_9_SIMULATION_SCENARIO_SCHEMA_VERSION,
                status=PHASE_9_SIMULATION_SCENARIO_STATUS,
                symbol=PHASE_9_SIMULATION_SCENARIO_SYMBOL,
                timeframes=PHASE_9_SIMULATION_SCENARIO_TIMEFRAMES,
                closed_candles=candles,
                side=PHASE_9_SIMULATION_SCENARIO_SIDE,
                entry_price_points=240900,
                stop_loss_price_points=239900,
                take_profit_price_points=242900,
                price_scale=PHASE_9_SIMULATION_PRICE_SCALE,
                max_gold_positions=(PHASE_9_SIMULATION_MAX_GOLD_POSITIONS),
                aggregate_risk_budget_bps=(PHASE_9_SIMULATION_AGGREGATE_RISK_BPS),
                stage_risk_bps=PHASE_9_SIMULATION_STAGE_RISK_BPS,
                oco_group_id=PHASE_9_SIMULATION_OCO_GROUP_ID,
                broker_stop_loss_required=True,
                kill_switches=PHASE_9_SIMULATION_KILL_SWITCHES,
                closed_candles_only=True,
                one_gold_position_max=True,
                staged_aggregate_risk_required=True,
                oco_required=True,
                martingale_prohibited=True,
                grid_prohibited=True,
                no_stop_loss_prohibited=True,
                kill_switches_required=True,
                permits_simulation_planning=True,
                permits_simulation_execution=False,
                permits_strategy_evaluation=False,
                permits_mt5_initialization=False,
                permits_broker_requests=False,
                permits_external_writes=False,
                permits_order_submission=False,
            )
        except ValueError as error:
            return Phase9SimulationScenarioDecision(
                is_allowed=False,
                contract=None,
                blockers=(f"simulation_scenario_invalid:{type(error).__name__}",),
            )

        return Phase9SimulationScenarioDecision(
            is_allowed=True,
            contract=contract,
            blockers=(),
        )


def create_phase9_simulation_scenario(
    admission_decision: object,
) -> Phase9SimulationScenarioDecision:
    """Create the deterministic immutable Phase 9 scenario contract."""

    return StrategyPhase9SimulationScenarioFactory().create(admission_decision)


__all__ = (
    "PHASE_9_SIMULATION_SCENARIO_SCHEMA_VERSION",
    "PHASE_9_SIMULATION_SCENARIO_STATUS",
    "PHASE_9_SIMULATION_SCENARIO_ID",
    "PHASE_9_SIMULATION_SCENARIO_SYMBOL",
    "PHASE_9_SIMULATION_SCENARIO_TIMEFRAMES",
    "PHASE_9_SIMULATION_SCENARIO_SIDE",
    "PHASE_9_SIMULATION_PRICE_SCALE",
    "PHASE_9_SIMULATION_MAX_GOLD_POSITIONS",
    "PHASE_9_SIMULATION_AGGREGATE_RISK_BPS",
    "PHASE_9_SIMULATION_STAGE_RISK_BPS",
    "PHASE_9_SIMULATION_OCO_GROUP_ID",
    "PHASE_9_SIMULATION_KILL_SWITCHES",
    "Phase9ClosedCandleSnapshot",
    "Phase9SimulationScenarioContract",
    "Phase9SimulationScenarioDecision",
    "StrategyPhase9SimulationScenarioFactory",
    "create_phase9_simulation_scenario",
)
