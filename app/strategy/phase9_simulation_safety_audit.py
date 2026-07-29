"""Immutable Phase 9 simulation safety audit.

This module audits the deterministic in-memory simulation run created in
Step 9.3. It verifies staged aggregate risk, the one-Gold-position limit,
OCO behavior, broker stop-loss attachment, kill-switch results, trace
continuity, terminal flat state, and the absence of all live or external
side effects.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase9_deterministic_in_memory_simulation_runner import (
    PHASE_9_SIMULATION_RUN_EVENT_TYPES,
)

PHASE_9_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_9_SIMULATION_SAFETY_AUDIT_STATUS_PASSED = "PASSED"
PHASE_9_SIMULATION_SAFETY_AUDIT_LIVE_EXECUTION_BLOCKED = "BLOCKED"
PHASE_9_SIMULATION_SAFETY_AUDIT_READY_FOR_FINAL_HANDOFF = "READY_FOR_FINAL_HANDOFF"
PHASE_9_SIMULATION_SAFETY_REQUIRED_KILL_SWITCHES = (
    "daily_loss_limit",
    "spread_guard",
    "stale_data_guard",
    "duplicate_position_guard",
)


def _required_attribute(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


def _required_int(value: object, name: str) -> int:
    attribute = _required_attribute(value, name)
    if isinstance(attribute, bool) or not isinstance(attribute, int):
        raise ValueError(f"{name} must be an integer.")
    return attribute


@dataclass(frozen=True, slots=True)
class Phase9SimulationSafetyAuditFinding:
    """Immutable result for one Phase 9 safety invariant."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("finding name is required.")

        if self.passed is not True:
            raise ValueError("successful audit findings must pass.")

        if not self.evidence:
            raise ValueError("finding evidence is required.")

    @property
    def finding_digest(self) -> str:
        material = "|".join(
            (
                self.name,
                str(self.passed),
                self.evidence,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase9SimulationSafetyAuditReport:
    """Immutable proof that the Step 9.3 simulation remained safe."""

    simulation_decision: object
    simulation_run: object

    schema_version: str
    audit_status: str
    final_handoff_status: str
    live_execution_status: str

    run_status: str
    run_outcome: str
    symbol: str
    side: str

    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]
    maximum_reserved_risk_bps: int
    aggregate_risk_never_exceeded: bool
    stage_risk_sum_valid: bool

    maximum_gold_position_count: int
    terminal_gold_position_count: int
    one_gold_position_limit_preserved: bool
    terminal_flat_state_valid: bool

    oco_group_id: str
    broker_stop_loss_attached: bool
    take_profit_filled: bool
    stop_loss_filled: bool
    stop_loss_canceled_by_oco: bool
    terminal_active_oco_order_count: int
    oco_contract_valid: bool

    kill_switch_names: tuple[str, ...]
    kill_switch_count: int
    all_kill_switches_passed: bool

    trace_event_types: tuple[str, ...]
    trace_sequence_indices: tuple[int, ...]
    trace_contiguous: bool
    trace_order_valid: bool

    uses_closed_candles_only: bool
    executes_in_memory_simulation: bool
    evaluates_strategy: bool
    initializes_mt5: bool
    sends_broker_request: bool
    writes_external_state: bool
    submits_live_order: bool
    no_live_or_external_effects: bool

    findings: tuple[Phase9SimulationSafetyAuditFinding, ...]
    safety_audit_passed: bool
    ready_for_final_handoff: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_9_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION:
            raise ValueError("safety audit schema version is inconsistent.")

        if self.audit_status != PHASE_9_SIMULATION_SAFETY_AUDIT_STATUS_PASSED:
            raise ValueError("safety audit status must be PASSED.")

        if self.final_handoff_status != PHASE_9_SIMULATION_SAFETY_AUDIT_READY_FOR_FINAL_HANDOFF:
            raise ValueError("final handoff status must be READY_FOR_FINAL_HANDOFF.")

        if self.live_execution_status != PHASE_9_SIMULATION_SAFETY_AUDIT_LIVE_EXECUTION_BLOCKED:
            raise ValueError("live execution must be BLOCKED.")

        if self.run_status != "COMPLETED":
            raise ValueError("simulation run must be COMPLETED.")

        if self.run_outcome != "TAKE_PROFIT":
            raise ValueError("deterministic outcome must be TAKE_PROFIT.")

        if self.symbol != "XAUUSD":
            raise ValueError("audit is XAUUSD only.")

        if self.side != "LONG":
            raise ValueError("audited deterministic side must be LONG.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk budget must be 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("stage risk allocation is inconsistent.")

        if self.maximum_reserved_risk_bps != 50:
            raise ValueError("maximum reserved risk must be 50 bps.")

        if self.maximum_gold_position_count != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.terminal_gold_position_count != 0:
            raise ValueError("simulation must finish flat.")

        if self.oco_group_id != "SIM-XAUUSD-OCO-001":
            raise ValueError("OCO group is inconsistent.")

        if self.terminal_active_oco_order_count != 0:
            raise ValueError("terminal active OCO count must be zero.")

        if self.kill_switch_names != PHASE_9_SIMULATION_SAFETY_REQUIRED_KILL_SWITCHES:
            raise ValueError("kill-switch names are inconsistent.")

        if self.kill_switch_count != 4:
            raise ValueError("four kill switches are required.")

        if self.trace_event_types != PHASE_9_SIMULATION_RUN_EVENT_TYPES:
            raise ValueError("trace event ordering is inconsistent.")

        if self.trace_sequence_indices != tuple(range(len(PHASE_9_SIMULATION_RUN_EVENT_TYPES))):
            raise ValueError("trace sequence indices are inconsistent.")

        required_truths = (
            self.aggregate_risk_never_exceeded,
            self.stage_risk_sum_valid,
            self.one_gold_position_limit_preserved,
            self.terminal_flat_state_valid,
            self.broker_stop_loss_attached,
            self.take_profit_filled,
            self.stop_loss_canceled_by_oco,
            self.oco_contract_valid,
            self.all_kill_switches_passed,
            self.trace_contiguous,
            self.trace_order_valid,
            self.uses_closed_candles_only,
            self.executes_in_memory_simulation,
            self.no_live_or_external_effects,
            self.safety_audit_passed,
            self.ready_for_final_handoff,
        )
        if not all(required_truths):
            raise ValueError("safety audit contains a failed invariant.")

        if self.stop_loss_filled:
            raise ValueError("stop loss cannot fill after take profit.")

        forbidden_effects = (
            self.evaluates_strategy,
            self.initializes_mt5,
            self.sends_broker_request,
            self.writes_external_state,
            self.submits_live_order,
        )
        if any(forbidden_effects):
            raise ValueError("safety audit detected a forbidden effect.")

        if len(self.findings) != 8:
            raise ValueError("eight immutable safety findings are required.")

        if not all(finding.passed is True for finding in self.findings):
            raise ValueError("all safety findings must pass.")

    @property
    def audit_digest(self) -> str:
        run_id = str(getattr(self.simulation_run, "run_id", ""))
        findings_material = ",".join(finding.finding_digest for finding in self.findings)
        material = "|".join(
            (
                self.schema_version,
                run_id,
                self.audit_status,
                self.final_handoff_status,
                self.live_execution_status,
                self.run_status,
                self.run_outcome,
                self.symbol,
                self.side,
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.maximum_reserved_risk_bps),
                str(self.aggregate_risk_never_exceeded),
                str(self.stage_risk_sum_valid),
                str(self.maximum_gold_position_count),
                str(self.terminal_gold_position_count),
                str(self.one_gold_position_limit_preserved),
                str(self.terminal_flat_state_valid),
                self.oco_group_id,
                str(self.broker_stop_loss_attached),
                str(self.take_profit_filled),
                str(self.stop_loss_filled),
                str(self.stop_loss_canceled_by_oco),
                str(self.terminal_active_oco_order_count),
                str(self.oco_contract_valid),
                ",".join(self.kill_switch_names),
                str(self.kill_switch_count),
                str(self.all_kill_switches_passed),
                ",".join(self.trace_event_types),
                ",".join(str(value) for value in self.trace_sequence_indices),
                str(self.trace_contiguous),
                str(self.trace_order_valid),
                str(self.uses_closed_candles_only),
                str(self.executes_in_memory_simulation),
                str(self.evaluates_strategy),
                str(self.initializes_mt5),
                str(self.sends_broker_request),
                str(self.writes_external_state),
                str(self.submits_live_order),
                str(self.no_live_or_external_effects),
                findings_material,
                str(self.safety_audit_passed),
                str(self.ready_for_final_handoff),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return f"GOLDXBOT_PHASE_9_SIMULATION_SAFETY_AUDIT:SHA256[{self.audit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase9SimulationSafetyAuditDecision:
    """Allowed or blocked Phase 9 safety audit decision."""

    is_allowed: bool
    report: Phase9SimulationSafetyAuditReport | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.report is None:
                raise ValueError("Allowed decision requires a report.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.report is not None:
                raise ValueError("Blocked decision cannot have a report.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def report_required(self) -> Phase9SimulationSafetyAuditReport:
        if self.report is None:
            raise RuntimeError("Phase 9 simulation safety audit is blocked.")
        return self.report


class StrategyPhase9SimulationSafetyAuditor:
    """Audits the deterministic run without creating new effects."""

    def audit(
        self,
        simulation_decision: object,
    ) -> Phase9SimulationSafetyAuditDecision:
        if simulation_decision is None:
            return Phase9SimulationSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("simulation_decision_missing",),
            )

        if getattr(simulation_decision, "is_allowed", True) is not True:
            return Phase9SimulationSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("simulation_decision_blocked",),
            )

        try:
            simulation_run = _required_attribute(
                simulation_decision,
                "run_required",
            )
            run_status = _required_attribute(simulation_run, "status")
            run_outcome = _required_attribute(simulation_run, "outcome")
            symbol = _required_attribute(simulation_run, "symbol")
            side = _required_attribute(simulation_run, "side")
            aggregate_risk_budget_bps = _required_int(
                simulation_run,
                "aggregate_risk_budget_bps",
            )
            stage_risk_bps = _required_attribute(
                simulation_run,
                "stage_risk_bps",
            )
            maximum_gold_position_count = _required_int(
                simulation_run,
                "max_gold_position_count_observed",
            )
            terminal_gold_position_count = _required_int(
                simulation_run,
                "terminal_gold_position_count",
            )
            terminal_active_oco_order_count = _required_int(
                simulation_run,
                "terminal_active_oco_order_count",
            )
            oco_group_id = _required_attribute(
                simulation_run,
                "oco_group_id",
            )
            broker_stop_loss_attached = _required_attribute(
                simulation_run,
                "broker_stop_loss_attached",
            )
            take_profit_filled = _required_attribute(
                simulation_run,
                "take_profit_filled",
            )
            stop_loss_filled = _required_attribute(
                simulation_run,
                "stop_loss_filled",
            )
            stop_loss_canceled_by_oco = _required_attribute(
                simulation_run,
                "stop_loss_canceled_by_oco",
            )
            kill_switch_results = _required_attribute(
                simulation_run,
                "kill_switch_results",
            )
            trace_events = _required_attribute(
                simulation_run,
                "trace_events",
            )
            uses_closed_candles_only = _required_attribute(
                simulation_run,
                "uses_closed_candles_only",
            )
            executes_in_memory_simulation = _required_attribute(
                simulation_run,
                "executes_in_memory_simulation",
            )
            evaluates_strategy = _required_attribute(
                simulation_run,
                "evaluates_strategy",
            )
            initializes_mt5 = _required_attribute(
                simulation_run,
                "initializes_mt5",
            )
            sends_broker_request = _required_attribute(
                simulation_run,
                "sends_broker_request",
            )
            writes_external_state = _required_attribute(
                simulation_run,
                "writes_external_state",
            )
            submits_live_order = _required_attribute(
                simulation_run,
                "submits_live_order",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase9SimulationSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=(f"simulation_run_invalid:{type(error).__name__}",),
            )

        if (
            not isinstance(stage_risk_bps, tuple)
            or not isinstance(kill_switch_results, tuple)
            or not isinstance(trace_events, tuple)
        ):
            return Phase9SimulationSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("simulation_run_shape_invalid",),
            )

        maximum_reserved_risk_bps = max(event.reserved_aggregate_risk_bps for event in trace_events)
        aggregate_risk_never_exceeded = all(
            event.reserved_aggregate_risk_bps <= aggregate_risk_budget_bps for event in trace_events
        )
        stage_risk_sum_valid = sum(stage_risk_bps) == aggregate_risk_budget_bps
        one_gold_position_limit_preserved = maximum_gold_position_count == 1 and all(
            event.open_gold_position_count <= 1 for event in trace_events
        )
        terminal_flat_state_valid = (
            terminal_gold_position_count == 0 and terminal_active_oco_order_count == 0
        )
        oco_contract_valid = (
            oco_group_id == "SIM-XAUUSD-OCO-001"
            and broker_stop_loss_attached is True
            and take_profit_filled is True
            and stop_loss_filled is False
            and stop_loss_canceled_by_oco is True
            and terminal_active_oco_order_count == 0
        )
        kill_switch_names = tuple(result.name for result in kill_switch_results)
        all_kill_switches_passed = (
            kill_switch_names == PHASE_9_SIMULATION_SAFETY_REQUIRED_KILL_SWITCHES
            and all(result.passed is True for result in kill_switch_results)
        )
        trace_event_types = tuple(event.event_type for event in trace_events)
        trace_sequence_indices = tuple(event.sequence_index for event in trace_events)
        trace_contiguous = trace_sequence_indices == tuple(range(len(trace_events)))
        trace_order_valid = trace_event_types == PHASE_9_SIMULATION_RUN_EVENT_TYPES
        no_live_or_external_effects = (
            evaluates_strategy is False
            and initializes_mt5 is False
            and sends_broker_request is False
            and writes_external_state is False
            and submits_live_order is False
        )

        findings = (
            Phase9SimulationSafetyAuditFinding(
                name="aggregate_risk",
                passed=(
                    aggregate_risk_never_exceeded
                    and stage_risk_sum_valid
                    and maximum_reserved_risk_bps == aggregate_risk_budget_bps
                ),
                evidence="25 + 25 bps stages remained within 50 bps.",
            ),
            Phase9SimulationSafetyAuditFinding(
                name="one_gold_position",
                passed=one_gold_position_limit_preserved,
                evidence="Maximum observed Gold position count was one.",
            ),
            Phase9SimulationSafetyAuditFinding(
                name="terminal_flat_state",
                passed=terminal_flat_state_valid,
                evidence="Terminal position and active OCO counts are zero.",
            ),
            Phase9SimulationSafetyAuditFinding(
                name="oco_and_broker_stop_loss",
                passed=oco_contract_valid,
                evidence="TP filled and the paired broker SL was OCO-canceled.",
            ),
            Phase9SimulationSafetyAuditFinding(
                name="kill_switches",
                passed=all_kill_switches_passed,
                evidence="All four required kill switches passed.",
            ),
            Phase9SimulationSafetyAuditFinding(
                name="trace_integrity",
                passed=trace_contiguous and trace_order_valid,
                evidence="Eight trace events are contiguous and ordered.",
            ),
            Phase9SimulationSafetyAuditFinding(
                name="closed_candle_scope",
                passed=uses_closed_candles_only is True,
                evidence="Simulation used the closed-candle scenario only.",
            ),
            Phase9SimulationSafetyAuditFinding(
                name="no_live_effects",
                passed=no_live_or_external_effects,
                evidence="No MT5, broker, external write, or live order effect.",
            ),
        )

        safety_audit_passed = all(finding.passed is True for finding in findings)

        try:
            report = Phase9SimulationSafetyAuditReport(
                simulation_decision=simulation_decision,
                simulation_run=simulation_run,
                schema_version=(PHASE_9_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION),
                audit_status=(PHASE_9_SIMULATION_SAFETY_AUDIT_STATUS_PASSED),
                final_handoff_status=(PHASE_9_SIMULATION_SAFETY_AUDIT_READY_FOR_FINAL_HANDOFF),
                live_execution_status=(PHASE_9_SIMULATION_SAFETY_AUDIT_LIVE_EXECUTION_BLOCKED),
                run_status=str(run_status),
                run_outcome=str(run_outcome),
                symbol=str(symbol),
                side=str(side),
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                stage_risk_bps=stage_risk_bps,
                maximum_reserved_risk_bps=maximum_reserved_risk_bps,
                aggregate_risk_never_exceeded=(aggregate_risk_never_exceeded),
                stage_risk_sum_valid=stage_risk_sum_valid,
                maximum_gold_position_count=(maximum_gold_position_count),
                terminal_gold_position_count=(terminal_gold_position_count),
                one_gold_position_limit_preserved=(one_gold_position_limit_preserved),
                terminal_flat_state_valid=terminal_flat_state_valid,
                oco_group_id=str(oco_group_id),
                broker_stop_loss_attached=(broker_stop_loss_attached is True),
                take_profit_filled=take_profit_filled is True,
                stop_loss_filled=stop_loss_filled is True,
                stop_loss_canceled_by_oco=(stop_loss_canceled_by_oco is True),
                terminal_active_oco_order_count=(terminal_active_oco_order_count),
                oco_contract_valid=oco_contract_valid,
                kill_switch_names=kill_switch_names,
                kill_switch_count=len(kill_switch_results),
                all_kill_switches_passed=all_kill_switches_passed,
                trace_event_types=trace_event_types,
                trace_sequence_indices=trace_sequence_indices,
                trace_contiguous=trace_contiguous,
                trace_order_valid=trace_order_valid,
                uses_closed_candles_only=(uses_closed_candles_only is True),
                executes_in_memory_simulation=(executes_in_memory_simulation is True),
                evaluates_strategy=evaluates_strategy is True,
                initializes_mt5=initializes_mt5 is True,
                sends_broker_request=sends_broker_request is True,
                writes_external_state=writes_external_state is True,
                submits_live_order=submits_live_order is True,
                no_live_or_external_effects=no_live_or_external_effects,
                findings=findings,
                safety_audit_passed=safety_audit_passed,
                ready_for_final_handoff=safety_audit_passed,
            )
        except ValueError as error:
            return Phase9SimulationSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=(f"simulation_safety_audit_failed:{type(error).__name__}",),
            )

        return Phase9SimulationSafetyAuditDecision(
            is_allowed=True,
            report=report,
            blockers=(),
        )


def audit_phase9_deterministic_simulation_safety(
    simulation_decision: object,
) -> Phase9SimulationSafetyAuditDecision:
    """Audit the deterministic Phase 9 run and all safety invariants."""

    return StrategyPhase9SimulationSafetyAuditor().audit(simulation_decision)


__all__ = (
    "PHASE_9_SIMULATION_SAFETY_AUDIT_SCHEMA_VERSION",
    "PHASE_9_SIMULATION_SAFETY_AUDIT_STATUS_PASSED",
    "PHASE_9_SIMULATION_SAFETY_AUDIT_LIVE_EXECUTION_BLOCKED",
    "PHASE_9_SIMULATION_SAFETY_AUDIT_READY_FOR_FINAL_HANDOFF",
    "PHASE_9_SIMULATION_SAFETY_REQUIRED_KILL_SWITCHES",
    "Phase9SimulationSafetyAuditFinding",
    "Phase9SimulationSafetyAuditReport",
    "Phase9SimulationSafetyAuditDecision",
    "StrategyPhase9SimulationSafetyAuditor",
    "audit_phase9_deterministic_simulation_safety",
)
