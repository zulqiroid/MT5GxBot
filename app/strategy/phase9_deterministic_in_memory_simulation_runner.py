"""Deterministic in-memory simulation runner for Phase 9.

This module consumes the immutable Phase 9 XAUUSD scenario contract and
runs one deterministic simulation entirely in memory. It uses the already
fixed scenario direction, risk allocation, entry, stop-loss, take-profit,
OCO group, and kill-switch contract. It does not generate a strategy
signal, initialize MT5, contact a broker, write external state, or submit
a live order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_9_SIMULATION_RUNNER_SCHEMA_VERSION = "1.0"
PHASE_9_SIMULATION_RUN_STATUS_COMPLETED = "COMPLETED"
PHASE_9_SIMULATION_RUN_OUTCOME_TAKE_PROFIT = "TAKE_PROFIT"
PHASE_9_SIMULATION_RUN_EVENT_TYPES = (
    "SCENARIO_ACCEPTED",
    "STAGE_ONE_RISK_RESERVED",
    "STAGE_TWO_RISK_RESERVED",
    "COMPOSITE_LONG_POSITION_OPENED",
    "PRICE_ADVANCED",
    "TAKE_PROFIT_FILLED",
    "OCO_STOP_LOSS_CANCELED",
    "SIMULATION_COMPLETED",
)


def _required_attribute(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase9SimulationKillSwitchResult:
    """Immutable in-memory result for one required kill switch."""

    name: str
    passed: bool
    reason: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("kill-switch name is required.")

        if self.passed is not True:
            raise ValueError("deterministic scenario requires passed guards.")

        if not self.reason:
            raise ValueError("kill-switch reason is required.")

    @property
    def result_digest(self) -> str:
        material = "|".join(
            (
                self.name,
                str(self.passed),
                self.reason,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase9SimulationTraceEvent:
    """Immutable event emitted by the deterministic in-memory runner."""

    sequence_index: int
    event_type: str
    price_points: int
    open_gold_position_count: int
    active_oco_order_count: int
    reserved_aggregate_risk_bps: int
    description: str

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError("sequence_index cannot be negative.")

        if self.event_type not in PHASE_9_SIMULATION_RUN_EVENT_TYPES:
            raise ValueError("unsupported simulation event type.")

        if (
            isinstance(self.price_points, bool)
            or not isinstance(self.price_points, int)
            or self.price_points <= 0
        ):
            raise ValueError("price_points must be a positive integer.")

        if self.open_gold_position_count not in (0, 1):
            raise ValueError("only zero or one Gold position is allowed.")

        if self.active_oco_order_count not in (0, 1, 2):
            raise ValueError("active OCO order count is invalid.")

        if (
            isinstance(self.reserved_aggregate_risk_bps, bool)
            or not isinstance(self.reserved_aggregate_risk_bps, int)
            or self.reserved_aggregate_risk_bps < 0
        ):
            raise ValueError("reserved risk must be a non-negative integer.")

        if not self.description:
            raise ValueError("event description is required.")

    @property
    def event_digest(self) -> str:
        material = "|".join(
            (
                str(self.sequence_index),
                self.event_type,
                str(self.price_points),
                str(self.open_gold_position_count),
                str(self.active_oco_order_count),
                str(self.reserved_aggregate_risk_bps),
                self.description,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase9DeterministicSimulationRun:
    """Immutable completed deterministic in-memory simulation run."""

    scenario_decision: object
    scenario_contract: object

    schema_version: str
    status: str
    outcome: str
    symbol: str
    side: str

    entry_price_points: int
    stop_loss_price_points: int
    take_profit_price_points: int
    final_price_points: int
    price_scale: int

    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]
    risk_distance_points: int
    reward_distance_points: int
    realized_profit_points: int
    reward_risk_milli: int

    max_gold_position_count_observed: int
    terminal_gold_position_count: int
    terminal_active_oco_order_count: int

    oco_group_id: str
    broker_stop_loss_attached: bool
    take_profit_filled: bool
    stop_loss_filled: bool
    stop_loss_canceled_by_oco: bool

    kill_switch_results: tuple[Phase9SimulationKillSwitchResult, ...]
    kill_switches_passed: bool
    trace_events: tuple[Phase9SimulationTraceEvent, ...]

    uses_closed_candles_only: bool
    executes_in_memory_simulation: bool
    evaluates_strategy: bool
    initializes_mt5: bool
    sends_broker_request: bool
    writes_external_state: bool
    submits_live_order: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_9_SIMULATION_RUNNER_SCHEMA_VERSION:
            raise ValueError("runner schema version is inconsistent.")

        if self.status != PHASE_9_SIMULATION_RUN_STATUS_COMPLETED:
            raise ValueError("simulation status must be COMPLETED.")

        if self.outcome != PHASE_9_SIMULATION_RUN_OUTCOME_TAKE_PROFIT:
            raise ValueError("deterministic scenario outcome is inconsistent.")

        if self.symbol != "XAUUSD":
            raise ValueError("simulation must be XAUUSD only.")

        if self.side != "LONG":
            raise ValueError("deterministic scenario side must be LONG.")

        if not (
            self.stop_loss_price_points < self.entry_price_points < self.take_profit_price_points
        ):
            raise ValueError("LONG scenario prices are inconsistent.")

        if self.final_price_points != self.take_profit_price_points:
            raise ValueError("final price must equal the filled take-profit.")

        if self.price_scale != 100:
            raise ValueError("price scale is inconsistent.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk budget must be 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("stage risk allocation is inconsistent.")

        if sum(self.stage_risk_bps) != self.aggregate_risk_budget_bps:
            raise ValueError("stage risk does not equal aggregate risk.")

        if self.risk_distance_points != self.entry_price_points - self.stop_loss_price_points:
            raise ValueError("risk distance is inconsistent.")

        if self.reward_distance_points != self.take_profit_price_points - self.entry_price_points:
            raise ValueError("reward distance is inconsistent.")

        if self.realized_profit_points != self.reward_distance_points:
            raise ValueError("realized profit is inconsistent.")

        if (
            self.reward_risk_milli
            != self.reward_distance_points * 1000 // self.risk_distance_points
        ):
            raise ValueError("reward-risk ratio is inconsistent.")

        if self.max_gold_position_count_observed != 1:
            raise ValueError("simulation must observe one position maximum.")

        if self.terminal_gold_position_count != 0:
            raise ValueError("terminal Gold position count must be zero.")

        if self.terminal_active_oco_order_count != 0:
            raise ValueError("terminal active OCO count must be zero.")

        if self.oco_group_id != "SIM-XAUUSD-OCO-001":
            raise ValueError("OCO group is inconsistent.")

        required_truths = (
            self.broker_stop_loss_attached,
            self.take_profit_filled,
            self.stop_loss_canceled_by_oco,
            self.kill_switches_passed,
            self.uses_closed_candles_only,
            self.executes_in_memory_simulation,
        )
        if not all(required_truths):
            raise ValueError("simulation lost a required invariant.")

        if self.stop_loss_filled:
            raise ValueError("stop-loss cannot fill after take-profit.")

        if len(self.kill_switch_results) != 4:
            raise ValueError("four kill-switch results are required.")

        if not all(result.passed is True for result in self.kill_switch_results):
            raise ValueError("all kill switches must pass.")

        if len(self.trace_events) != len(PHASE_9_SIMULATION_RUN_EVENT_TYPES):
            raise ValueError("simulation trace event count is inconsistent.")

        if tuple(event.sequence_index for event in self.trace_events) != tuple(
            range(len(self.trace_events))
        ):
            raise ValueError("simulation event indices are not contiguous.")

        if (
            tuple(event.event_type for event in self.trace_events)
            != PHASE_9_SIMULATION_RUN_EVENT_TYPES
        ):
            raise ValueError("simulation event ordering is inconsistent.")

        if (
            max(event.open_gold_position_count for event in self.trace_events)
            != self.max_gold_position_count_observed
        ):
            raise ValueError("observed position count is inconsistent.")

        if any(
            event.reserved_aggregate_risk_bps > self.aggregate_risk_budget_bps
            for event in self.trace_events
        ):
            raise ValueError("simulation exceeds aggregate risk budget.")

        if self.evaluates_strategy:
            raise ValueError("runner cannot generate a strategy signal.")

        forbidden_effects = (
            self.initializes_mt5,
            self.sends_broker_request,
            self.writes_external_state,
            self.submits_live_order,
        )
        if any(forbidden_effects):
            raise ValueError("in-memory simulation cannot cause live effects.")

    @property
    def run_digest(self) -> str:
        contract_id = str(getattr(self.scenario_contract, "contract_id", ""))
        kill_switch_material = ",".join(result.result_digest for result in self.kill_switch_results)
        trace_material = ",".join(event.event_digest for event in self.trace_events)
        material = "|".join(
            (
                self.schema_version,
                contract_id,
                self.status,
                self.outcome,
                self.symbol,
                self.side,
                str(self.entry_price_points),
                str(self.stop_loss_price_points),
                str(self.take_profit_price_points),
                str(self.final_price_points),
                str(self.price_scale),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.risk_distance_points),
                str(self.reward_distance_points),
                str(self.realized_profit_points),
                str(self.reward_risk_milli),
                str(self.max_gold_position_count_observed),
                str(self.terminal_gold_position_count),
                str(self.terminal_active_oco_order_count),
                self.oco_group_id,
                str(self.broker_stop_loss_attached),
                str(self.take_profit_filled),
                str(self.stop_loss_filled),
                str(self.stop_loss_canceled_by_oco),
                kill_switch_material,
                str(self.kill_switches_passed),
                trace_material,
                str(self.uses_closed_candles_only),
                str(self.executes_in_memory_simulation),
                str(self.evaluates_strategy),
                str(self.initializes_mt5),
                str(self.sends_broker_request),
                str(self.writes_external_state),
                str(self.submits_live_order),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def run_id(self) -> str:
        return f"GOLDXBOT_PHASE_9_DETERMINISTIC_SIMULATION:SHA256[{self.run_digest}]"


@dataclass(frozen=True, slots=True)
class Phase9DeterministicSimulationDecision:
    """Allowed or blocked deterministic simulation decision."""

    is_allowed: bool
    run: Phase9DeterministicSimulationRun | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.run is None:
                raise ValueError("Allowed decision requires a run.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.run is not None:
                raise ValueError("Blocked decision cannot have a run.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def run_required(self) -> Phase9DeterministicSimulationRun:
        if self.run is None:
            raise RuntimeError("Phase 9 deterministic simulation is blocked.")
        return self.run


class StrategyPhase9DeterministicInMemorySimulationRunner:
    """Runs the fixed Phase 9 scenario without any external effects."""

    def run(
        self,
        scenario_decision: object,
    ) -> Phase9DeterministicSimulationDecision:
        if scenario_decision is None:
            return Phase9DeterministicSimulationDecision(
                is_allowed=False,
                run=None,
                blockers=("simulation_scenario_decision_missing",),
            )

        if getattr(scenario_decision, "is_allowed", True) is not True:
            return Phase9DeterministicSimulationDecision(
                is_allowed=False,
                run=None,
                blockers=("simulation_scenario_decision_blocked",),
            )

        try:
            contract = _required_attribute(
                scenario_decision,
                "contract_required",
            )
            status = _required_attribute(contract, "status")
            symbol = _required_attribute(contract, "symbol")
            side = _required_attribute(contract, "side")
            entry = _required_attribute(
                contract,
                "entry_price_points",
            )
            stop_loss = _required_attribute(
                contract,
                "stop_loss_price_points",
            )
            take_profit = _required_attribute(
                contract,
                "take_profit_price_points",
            )
            price_scale = _required_attribute(contract, "price_scale")
            aggregate_risk = _required_attribute(
                contract,
                "aggregate_risk_budget_bps",
            )
            stage_risk = _required_attribute(
                contract,
                "stage_risk_bps",
            )
            oco_group_id = _required_attribute(
                contract,
                "oco_group_id",
            )
            kill_switches = _required_attribute(
                contract,
                "kill_switches",
            )
            closed_candles = _required_attribute(
                contract,
                "closed_candles",
            )
            live_execution_status = _required_attribute(
                contract.admission_permit,
                "live_execution_status",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase9DeterministicSimulationDecision(
                is_allowed=False,
                run=None,
                blockers=(f"simulation_scenario_invalid:{type(error).__name__}",),
            )

        source_contract_valid = (
            status == "CONTRACT_READY"
            and symbol == "XAUUSD"
            and side == "LONG"
            and isinstance(entry, int)
            and isinstance(stop_loss, int)
            and isinstance(take_profit, int)
            and price_scale == 100
            and aggregate_risk == 50
            and stage_risk == (25, 25)
            and oco_group_id == "SIM-XAUUSD-OCO-001"
            and isinstance(kill_switches, tuple)
            and len(kill_switches) == 4
            and isinstance(closed_candles, tuple)
            and len(closed_candles) == 4
            and all(getattr(candle, "is_closed", False) is True for candle in closed_candles)
            and live_execution_status == "BLOCKED"
        )
        if not source_contract_valid:
            return Phase9DeterministicSimulationDecision(
                is_allowed=False,
                run=None,
                blockers=("simulation_scenario_contract_invalid",),
            )

        kill_switch_results = (
            Phase9SimulationKillSwitchResult(
                name="daily_loss_limit",
                passed=True,
                reason="synthetic daily loss remains below the limit",
            ),
            Phase9SimulationKillSwitchResult(
                name="spread_guard",
                passed=True,
                reason="deterministic spread is within scenario bounds",
            ),
            Phase9SimulationKillSwitchResult(
                name="stale_data_guard",
                passed=True,
                reason="all supplied scenario candles are closed",
            ),
            Phase9SimulationKillSwitchResult(
                name="duplicate_position_guard",
                passed=True,
                reason="maximum simulated Gold position count is one",
            ),
        )

        trace_events = (
            Phase9SimulationTraceEvent(
                sequence_index=0,
                event_type="SCENARIO_ACCEPTED",
                price_points=entry,
                open_gold_position_count=0,
                active_oco_order_count=0,
                reserved_aggregate_risk_bps=0,
                description="Immutable closed-candle scenario accepted.",
            ),
            Phase9SimulationTraceEvent(
                sequence_index=1,
                event_type="STAGE_ONE_RISK_RESERVED",
                price_points=entry,
                open_gold_position_count=0,
                active_oco_order_count=0,
                reserved_aggregate_risk_bps=25,
                description="First 25 bps risk stage reserved in memory.",
            ),
            Phase9SimulationTraceEvent(
                sequence_index=2,
                event_type="STAGE_TWO_RISK_RESERVED",
                price_points=entry,
                open_gold_position_count=0,
                active_oco_order_count=0,
                reserved_aggregate_risk_bps=50,
                description="Second risk stage completes the 50 bps budget.",
            ),
            Phase9SimulationTraceEvent(
                sequence_index=3,
                event_type="COMPOSITE_LONG_POSITION_OPENED",
                price_points=entry,
                open_gold_position_count=1,
                active_oco_order_count=2,
                reserved_aggregate_risk_bps=50,
                description="One synthetic Gold position opened with OCO.",
            ),
            Phase9SimulationTraceEvent(
                sequence_index=4,
                event_type="PRICE_ADVANCED",
                price_points=241400,
                open_gold_position_count=1,
                active_oco_order_count=2,
                reserved_aggregate_risk_bps=50,
                description="Synthetic price advances toward take-profit.",
            ),
            Phase9SimulationTraceEvent(
                sequence_index=5,
                event_type="TAKE_PROFIT_FILLED",
                price_points=take_profit,
                open_gold_position_count=0,
                active_oco_order_count=1,
                reserved_aggregate_risk_bps=0,
                description="Synthetic take-profit closes the position.",
            ),
            Phase9SimulationTraceEvent(
                sequence_index=6,
                event_type="OCO_STOP_LOSS_CANCELED",
                price_points=take_profit,
                open_gold_position_count=0,
                active_oco_order_count=0,
                reserved_aggregate_risk_bps=0,
                description="Paired synthetic stop-loss canceled by OCO.",
            ),
            Phase9SimulationTraceEvent(
                sequence_index=7,
                event_type="SIMULATION_COMPLETED",
                price_points=take_profit,
                open_gold_position_count=0,
                active_oco_order_count=0,
                reserved_aggregate_risk_bps=0,
                description="Deterministic in-memory simulation completed.",
            ),
        )

        try:
            simulation_run = Phase9DeterministicSimulationRun(
                scenario_decision=scenario_decision,
                scenario_contract=contract,
                schema_version=PHASE_9_SIMULATION_RUNNER_SCHEMA_VERSION,
                status=PHASE_9_SIMULATION_RUN_STATUS_COMPLETED,
                outcome=PHASE_9_SIMULATION_RUN_OUTCOME_TAKE_PROFIT,
                symbol=symbol,
                side=side,
                entry_price_points=entry,
                stop_loss_price_points=stop_loss,
                take_profit_price_points=take_profit,
                final_price_points=take_profit,
                price_scale=price_scale,
                aggregate_risk_budget_bps=aggregate_risk,
                stage_risk_bps=stage_risk,
                risk_distance_points=entry - stop_loss,
                reward_distance_points=take_profit - entry,
                realized_profit_points=take_profit - entry,
                reward_risk_milli=((take_profit - entry) * 1000 // (entry - stop_loss)),
                max_gold_position_count_observed=max(
                    event.open_gold_position_count for event in trace_events
                ),
                terminal_gold_position_count=(trace_events[-1].open_gold_position_count),
                terminal_active_oco_order_count=(trace_events[-1].active_oco_order_count),
                oco_group_id=oco_group_id,
                broker_stop_loss_attached=True,
                take_profit_filled=True,
                stop_loss_filled=False,
                stop_loss_canceled_by_oco=True,
                kill_switch_results=kill_switch_results,
                kill_switches_passed=True,
                trace_events=trace_events,
                uses_closed_candles_only=True,
                executes_in_memory_simulation=True,
                evaluates_strategy=False,
                initializes_mt5=False,
                sends_broker_request=False,
                writes_external_state=False,
                submits_live_order=False,
            )
        except (TypeError, ValueError, ZeroDivisionError) as error:
            return Phase9DeterministicSimulationDecision(
                is_allowed=False,
                run=None,
                blockers=(f"deterministic_simulation_failed:{type(error).__name__}",),
            )

        return Phase9DeterministicSimulationDecision(
            is_allowed=True,
            run=simulation_run,
            blockers=(),
        )


def run_phase9_deterministic_in_memory_simulation(
    scenario_decision: object,
) -> Phase9DeterministicSimulationDecision:
    """Run the fixed Phase 9 scenario entirely in memory."""

    return StrategyPhase9DeterministicInMemorySimulationRunner().run(scenario_decision)


__all__ = (
    "PHASE_9_SIMULATION_RUNNER_SCHEMA_VERSION",
    "PHASE_9_SIMULATION_RUN_STATUS_COMPLETED",
    "PHASE_9_SIMULATION_RUN_OUTCOME_TAKE_PROFIT",
    "PHASE_9_SIMULATION_RUN_EVENT_TYPES",
    "Phase9SimulationKillSwitchResult",
    "Phase9SimulationTraceEvent",
    "Phase9DeterministicSimulationRun",
    "Phase9DeterministicSimulationDecision",
    "StrategyPhase9DeterministicInMemorySimulationRunner",
    "run_phase9_deterministic_in_memory_simulation",
)
