"""Immutable Phase 9 final audit and handoff bundle.

This module consumes the successful Step 9.4 safety audit and creates one
immutable Phase 9 completion handoff. It preserves the full admission,
scenario, simulation, and safety-audit lineage while keeping live execution
blocked. It performs no strategy evaluation, MT5 initialization, broker
request, external write, or live order submission.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_9_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_9_FINAL_HANDOFF_PHASE_STATUS = "PHASE_9_COMPLETE"
PHASE_9_FINAL_HANDOFF_STATUS = "READY_FOR_PHASE_10"
PHASE_9_FINAL_HANDOFF_SIMULATION_MODE = "IN_MEMORY_ONLY"
PHASE_9_FINAL_HANDOFF_LIVE_EXECUTION_STATUS = "BLOCKED"


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
class Phase9FinalAuditHandoffBundle:
    """Immutable proof that Phase 9 is complete and safe to hand off."""

    safety_audit_decision: object
    safety_audit_report: object
    simulation_run: object
    scenario_contract: object
    admission_permit: object
    phase8_handoff_bundle: object

    schema_version: str
    phase_number: int
    source_phase_number: int
    target_phase_number: int

    phase_status: str
    handoff_status: str
    simulation_mode: str
    live_execution_status: str

    simulation_status: str
    simulation_outcome: str
    safety_audit_status: str
    safety_handoff_status: str

    symbol: str
    side: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool

    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]
    maximum_reserved_risk_bps: int
    maximum_gold_position_count: int
    terminal_gold_position_count: int
    terminal_active_oco_order_count: int

    oco_group_id: str
    broker_stop_loss_attached: bool
    take_profit_filled: bool
    stop_loss_filled: bool
    stop_loss_canceled_by_oco: bool

    kill_switch_count: int
    all_kill_switches_passed: bool
    trace_event_count: int
    trace_contiguous: bool
    trace_order_valid: bool

    admission_lineage_preserved: bool
    scenario_lineage_preserved: bool
    simulation_lineage_preserved: bool
    safety_audit_lineage_preserved: bool

    risk_contract_valid: bool
    position_contract_valid: bool
    oco_contract_valid: bool
    kill_switch_contract_valid: bool
    terminal_state_valid: bool
    safety_audit_passed: bool

    phase_complete: bool
    ready_for_phase_10: bool

    executes_in_memory_simulation: bool
    evaluates_strategy: bool
    initializes_mt5: bool
    sends_broker_request: bool
    writes_external_state: bool
    submits_live_order: bool
    no_live_or_external_effects: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_9_FINAL_HANDOFF_SCHEMA_VERSION:
            raise ValueError("final handoff schema version is inconsistent.")

        if self.phase_number != 9:
            raise ValueError("phase_number must be 9.")

        if self.source_phase_number != 8:
            raise ValueError("source_phase_number must be 8.")

        if self.target_phase_number != 10:
            raise ValueError("target_phase_number must be 10.")

        if self.phase_status != PHASE_9_FINAL_HANDOFF_PHASE_STATUS:
            raise ValueError("phase status must be PHASE_9_COMPLETE.")

        if self.handoff_status != PHASE_9_FINAL_HANDOFF_STATUS:
            raise ValueError("handoff status must be READY_FOR_PHASE_10.")

        if self.simulation_mode != PHASE_9_FINAL_HANDOFF_SIMULATION_MODE:
            raise ValueError("simulation mode must be IN_MEMORY_ONLY.")

        if self.live_execution_status != PHASE_9_FINAL_HANDOFF_LIVE_EXECUTION_STATUS:
            raise ValueError("live execution must remain BLOCKED.")

        if self.simulation_status != "COMPLETED":
            raise ValueError("simulation status must be COMPLETED.")

        if self.simulation_outcome != "TAKE_PROFIT":
            raise ValueError("simulation outcome must be TAKE_PROFIT.")

        if self.safety_audit_status != "PASSED":
            raise ValueError("safety audit status must be PASSED.")

        if self.safety_handoff_status != "READY_FOR_FINAL_HANDOFF":
            raise ValueError("safety handoff status must be READY_FOR_FINAL_HANDOFF.")

        if self.symbol != "XAUUSD":
            raise ValueError("Phase 9 handoff is XAUUSD only.")

        if self.side != "LONG":
            raise ValueError("deterministic Phase 9 side must be LONG.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 9 timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("Phase 9 must use closed candles only.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk budget must be 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("stage risk allocation is inconsistent.")

        if self.maximum_reserved_risk_bps != 50:
            raise ValueError("maximum reserved risk must be 50 bps.")

        if self.maximum_gold_position_count != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.terminal_gold_position_count != 0:
            raise ValueError("terminal Gold position count must be zero.")

        if self.terminal_active_oco_order_count != 0:
            raise ValueError("terminal active OCO count must be zero.")

        if self.oco_group_id != "SIM-XAUUSD-OCO-001":
            raise ValueError("OCO group is inconsistent.")

        if self.broker_stop_loss_attached is not True:
            raise ValueError("broker stop-loss attachment is required.")

        if self.take_profit_filled is not True:
            raise ValueError("deterministic take-profit must be filled.")

        if self.stop_loss_filled is not False:
            raise ValueError("stop-loss cannot fill after take-profit.")

        if self.stop_loss_canceled_by_oco is not True:
            raise ValueError("paired stop-loss must be canceled by OCO.")

        if self.kill_switch_count != 4:
            raise ValueError("four kill switches are required.")

        if self.all_kill_switches_passed is not True:
            raise ValueError("all kill switches must pass.")

        if self.trace_event_count != 8:
            raise ValueError("eight trace events are required.")

        required_truths = (
            self.trace_contiguous,
            self.trace_order_valid,
            self.admission_lineage_preserved,
            self.scenario_lineage_preserved,
            self.simulation_lineage_preserved,
            self.safety_audit_lineage_preserved,
            self.risk_contract_valid,
            self.position_contract_valid,
            self.oco_contract_valid,
            self.kill_switch_contract_valid,
            self.terminal_state_valid,
            self.safety_audit_passed,
            self.phase_complete,
            self.ready_for_phase_10,
            self.executes_in_memory_simulation,
            self.no_live_or_external_effects,
        )
        if not all(required_truths):
            raise ValueError("Phase 9 final handoff contains a failed invariant.")

        forbidden_effects = (
            self.evaluates_strategy,
            self.initializes_mt5,
            self.sends_broker_request,
            self.writes_external_state,
            self.submits_live_order,
        )
        if any(forbidden_effects):
            raise ValueError("Phase 9 final handoff detected a live effect.")

    @property
    def handoff_digest(self) -> str:
        safety_audit_id = str(getattr(self.safety_audit_report, "audit_id", ""))
        simulation_run_id = str(getattr(self.simulation_run, "run_id", ""))
        scenario_contract_id = str(getattr(self.scenario_contract, "contract_id", ""))
        admission_permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase8_handoff_id = str(getattr(self.phase8_handoff_bundle, "handoff_id", ""))

        material = "|".join(
            (
                self.schema_version,
                safety_audit_id,
                simulation_run_id,
                scenario_contract_id,
                admission_permit_id,
                phase8_handoff_id,
                str(self.phase_number),
                str(self.source_phase_number),
                str(self.target_phase_number),
                self.phase_status,
                self.handoff_status,
                self.simulation_mode,
                self.live_execution_status,
                self.simulation_status,
                self.simulation_outcome,
                self.safety_audit_status,
                self.safety_handoff_status,
                self.symbol,
                self.side,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.maximum_reserved_risk_bps),
                str(self.maximum_gold_position_count),
                str(self.terminal_gold_position_count),
                str(self.terminal_active_oco_order_count),
                self.oco_group_id,
                str(self.broker_stop_loss_attached),
                str(self.take_profit_filled),
                str(self.stop_loss_filled),
                str(self.stop_loss_canceled_by_oco),
                str(self.kill_switch_count),
                str(self.all_kill_switches_passed),
                str(self.trace_event_count),
                str(self.trace_contiguous),
                str(self.trace_order_valid),
                str(self.admission_lineage_preserved),
                str(self.scenario_lineage_preserved),
                str(self.simulation_lineage_preserved),
                str(self.safety_audit_lineage_preserved),
                str(self.risk_contract_valid),
                str(self.position_contract_valid),
                str(self.oco_contract_valid),
                str(self.kill_switch_contract_valid),
                str(self.terminal_state_valid),
                str(self.safety_audit_passed),
                str(self.phase_complete),
                str(self.ready_for_phase_10),
                str(self.executes_in_memory_simulation),
                str(self.evaluates_strategy),
                str(self.initializes_mt5),
                str(self.sends_broker_request),
                str(self.writes_external_state),
                str(self.submits_live_order),
                str(self.no_live_or_external_effects),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return f"GOLDXBOT_PHASE_9_FINAL_AUDIT_HANDOFF:SHA256[{self.handoff_digest}]"


@dataclass(frozen=True, slots=True)
class Phase9FinalAuditHandoffDecision:
    """Allowed or blocked Phase 9 final handoff decision."""

    is_allowed: bool
    bundle: Phase9FinalAuditHandoffBundle | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.bundle is None:
                raise ValueError("Allowed decision requires a bundle.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.bundle is not None:
                raise ValueError("Blocked decision cannot have a bundle.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def bundle_required(self) -> Phase9FinalAuditHandoffBundle:
        if self.bundle is None:
            raise RuntimeError("Phase 9 final audit handoff is blocked.")
        return self.bundle


class StrategyPhase9FinalAuditHandoffFactory:
    """Creates the immutable Phase 9 completion handoff."""

    def create(
        self,
        safety_audit_decision: object,
    ) -> Phase9FinalAuditHandoffDecision:
        if safety_audit_decision is None:
            return Phase9FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=("safety_audit_decision_missing",),
            )

        if getattr(safety_audit_decision, "is_allowed", True) is not True:
            return Phase9FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=("safety_audit_decision_blocked",),
            )

        try:
            report = _required_attribute(
                safety_audit_decision,
                "report_required",
            )
            simulation_decision = _required_attribute(
                report,
                "simulation_decision",
            )
            simulation_run = _required_attribute(
                report,
                "simulation_run",
            )
            scenario_decision = _required_attribute(
                simulation_run,
                "scenario_decision",
            )
            scenario_contract = _required_attribute(
                simulation_run,
                "scenario_contract",
            )
            admission_decision = _required_attribute(
                scenario_contract,
                "admission_decision",
            )
            admission_permit = _required_attribute(
                scenario_contract,
                "admission_permit",
            )
            phase8_handoff_decision = _required_attribute(
                admission_permit,
                "phase8_handoff_decision",
            )
            phase8_handoff_bundle = _required_attribute(
                admission_permit,
                "phase8_handoff_bundle",
            )

            audit_status = _required_attribute(report, "audit_status")
            safety_handoff_status = _required_attribute(
                report,
                "final_handoff_status",
            )
            live_execution_status = _required_attribute(
                report,
                "live_execution_status",
            )
            run_status = _required_attribute(report, "run_status")
            run_outcome = _required_attribute(report, "run_outcome")
            symbol = _required_attribute(report, "symbol")
            side = _required_attribute(report, "side")
            aggregate_risk_budget_bps = _required_int(
                report,
                "aggregate_risk_budget_bps",
            )
            stage_risk_bps = _required_attribute(
                report,
                "stage_risk_bps",
            )
            maximum_reserved_risk_bps = _required_int(
                report,
                "maximum_reserved_risk_bps",
            )
            maximum_gold_position_count = _required_int(
                report,
                "maximum_gold_position_count",
            )
            terminal_gold_position_count = _required_int(
                report,
                "terminal_gold_position_count",
            )
            terminal_active_oco_order_count = _required_int(
                report,
                "terminal_active_oco_order_count",
            )
            oco_group_id = _required_attribute(
                report,
                "oco_group_id",
            )
            kill_switch_count = _required_int(
                report,
                "kill_switch_count",
            )
            trace_event_types = _required_attribute(
                report,
                "trace_event_types",
            )
            timeframes = _required_attribute(
                scenario_contract,
                "timeframes",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase9FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=(f"phase9_final_handoff_source_invalid:{type(error).__name__}",),
            )

        lineage_valid = (
            report.simulation_decision is simulation_decision
            and simulation_decision.run_required is simulation_run
            and simulation_run.scenario_decision is scenario_decision
            and scenario_decision.contract_required is scenario_contract
            and scenario_contract.admission_decision is admission_decision
            and admission_decision.permit_required is admission_permit
            and admission_permit.phase8_handoff_decision is phase8_handoff_decision
            and phase8_handoff_decision.bundle_required is phase8_handoff_bundle
        )

        admission_lineage_preserved = (
            scenario_contract.admission_permit is admission_permit
            and admission_permit.phase8_handoff_bundle is phase8_handoff_bundle
        )
        scenario_lineage_preserved = simulation_run.scenario_contract is scenario_contract
        simulation_lineage_preserved = report.simulation_run is simulation_run
        safety_audit_lineage_preserved = (
            report is safety_audit_decision.report_required and lineage_valid
        )

        risk_contract_valid = (
            aggregate_risk_budget_bps == 50
            and stage_risk_bps == (25, 25)
            and maximum_reserved_risk_bps == 50
            and report.aggregate_risk_never_exceeded is True
            and report.stage_risk_sum_valid is True
        )
        position_contract_valid = (
            maximum_gold_position_count == 1
            and terminal_gold_position_count == 0
            and report.one_gold_position_limit_preserved is True
            and report.terminal_flat_state_valid is True
        )
        oco_contract_valid = (
            report.oco_contract_valid is True
            and report.broker_stop_loss_attached is True
            and report.take_profit_filled is True
            and report.stop_loss_filled is False
            and report.stop_loss_canceled_by_oco is True
            and terminal_active_oco_order_count == 0
        )
        kill_switch_contract_valid = (
            kill_switch_count == 4 and report.all_kill_switches_passed is True
        )
        terminal_state_valid = (
            run_status == "COMPLETED"
            and run_outcome == "TAKE_PROFIT"
            and terminal_gold_position_count == 0
            and terminal_active_oco_order_count == 0
            and report.trace_contiguous is True
            and report.trace_order_valid is True
        )
        no_live_or_external_effects = (
            report.no_live_or_external_effects is True
            and report.evaluates_strategy is False
            and report.initializes_mt5 is False
            and report.sends_broker_request is False
            and report.writes_external_state is False
            and report.submits_live_order is False
        )

        try:
            bundle = Phase9FinalAuditHandoffBundle(
                safety_audit_decision=safety_audit_decision,
                safety_audit_report=report,
                simulation_run=simulation_run,
                scenario_contract=scenario_contract,
                admission_permit=admission_permit,
                phase8_handoff_bundle=phase8_handoff_bundle,
                schema_version=PHASE_9_FINAL_HANDOFF_SCHEMA_VERSION,
                phase_number=9,
                source_phase_number=8,
                target_phase_number=10,
                phase_status=PHASE_9_FINAL_HANDOFF_PHASE_STATUS,
                handoff_status=PHASE_9_FINAL_HANDOFF_STATUS,
                simulation_mode=PHASE_9_FINAL_HANDOFF_SIMULATION_MODE,
                live_execution_status=str(live_execution_status),
                simulation_status=str(run_status),
                simulation_outcome=str(run_outcome),
                safety_audit_status=str(audit_status),
                safety_handoff_status=str(safety_handoff_status),
                symbol=str(symbol),
                side=str(side),
                timeframes=timeframes,
                closed_candles_only=(report.uses_closed_candles_only is True),
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                stage_risk_bps=stage_risk_bps,
                maximum_reserved_risk_bps=maximum_reserved_risk_bps,
                maximum_gold_position_count=(maximum_gold_position_count),
                terminal_gold_position_count=(terminal_gold_position_count),
                terminal_active_oco_order_count=(terminal_active_oco_order_count),
                oco_group_id=str(oco_group_id),
                broker_stop_loss_attached=(report.broker_stop_loss_attached is True),
                take_profit_filled=report.take_profit_filled is True,
                stop_loss_filled=report.stop_loss_filled is True,
                stop_loss_canceled_by_oco=(report.stop_loss_canceled_by_oco is True),
                kill_switch_count=kill_switch_count,
                all_kill_switches_passed=(report.all_kill_switches_passed is True),
                trace_event_count=len(trace_event_types),
                trace_contiguous=report.trace_contiguous is True,
                trace_order_valid=report.trace_order_valid is True,
                admission_lineage_preserved=(admission_lineage_preserved),
                scenario_lineage_preserved=scenario_lineage_preserved,
                simulation_lineage_preserved=(simulation_lineage_preserved),
                safety_audit_lineage_preserved=(safety_audit_lineage_preserved),
                risk_contract_valid=risk_contract_valid,
                position_contract_valid=position_contract_valid,
                oco_contract_valid=oco_contract_valid,
                kill_switch_contract_valid=(kill_switch_contract_valid),
                terminal_state_valid=terminal_state_valid,
                safety_audit_passed=(report.safety_audit_passed is True),
                phase_complete=True,
                ready_for_phase_10=True,
                executes_in_memory_simulation=(report.executes_in_memory_simulation is True),
                evaluates_strategy=report.evaluates_strategy is True,
                initializes_mt5=report.initializes_mt5 is True,
                sends_broker_request=report.sends_broker_request is True,
                writes_external_state=report.writes_external_state is True,
                submits_live_order=report.submits_live_order is True,
                no_live_or_external_effects=(no_live_or_external_effects),
            )
        except ValueError as error:
            return Phase9FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=(f"phase9_final_handoff_invalid:{type(error).__name__}",),
            )

        return Phase9FinalAuditHandoffDecision(
            is_allowed=True,
            bundle=bundle,
            blockers=(),
        )


def create_phase9_final_audit_handoff(
    safety_audit_decision: object,
) -> Phase9FinalAuditHandoffDecision:
    """Create the immutable Phase 9 final audit handoff."""

    return StrategyPhase9FinalAuditHandoffFactory().create(safety_audit_decision)


__all__ = (
    "PHASE_9_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_9_FINAL_HANDOFF_PHASE_STATUS",
    "PHASE_9_FINAL_HANDOFF_STATUS",
    "PHASE_9_FINAL_HANDOFF_SIMULATION_MODE",
    "PHASE_9_FINAL_HANDOFF_LIVE_EXECUTION_STATUS",
    "Phase9FinalAuditHandoffBundle",
    "Phase9FinalAuditHandoffDecision",
    "StrategyPhase9FinalAuditHandoffFactory",
    "create_phase9_final_audit_handoff",
)
