"""Immutable Phase 10 final audit and handoff bundle.

This module consumes the successful Step 10.4 paper-execution safety audit
and creates one immutable Phase 10 completion handoff. It preserves the
complete Phase 9 handoff, Phase 10 admission, paper scenario, order-intent,
in-memory paper execution, paper ledger, and safety-audit lineage while
keeping live execution blocked. It performs no strategy evaluation, MT5
initialization, broker request, external write, or live order submission.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_10_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_10_FINAL_HANDOFF_PHASE_STATUS = "PHASE_10_COMPLETE"
PHASE_10_FINAL_HANDOFF_STATUS = "READY_FOR_PHASE_11"
PHASE_10_FINAL_HANDOFF_EXECUTION_MODE = "IN_MEMORY_PAPER"
PHASE_10_FINAL_HANDOFF_LIVE_EXECUTION_STATUS = "BLOCKED"


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
class Phase10FinalAuditHandoffBundle:
    """Immutable proof that Phase 10 is complete and safe to hand off."""

    safety_audit_decision: object
    safety_audit_report: object
    execution_decision: object
    execution: object
    contract_decision: object
    contract: object
    admission_decision: object
    admission_permit: object
    phase9_handoff_bundle: object

    schema_version: str
    phase_number: int
    source_phase_number: int
    target_phase_number: int

    phase_status: str
    handoff_status: str
    execution_mode: str
    live_execution_status: str

    execution_status: str
    execution_outcome: str
    safety_audit_status: str
    safety_handoff_status: str

    symbol: str
    side: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool

    stage_risk_bps: tuple[int, ...]
    aggregate_risk_budget_bps: int
    maximum_reserved_risk_bps: int

    maximum_gold_position_count: int
    terminal_gold_position_count: int
    terminal_active_oco_order_count: int
    terminal_reserved_risk_bps: int

    position_group_id: str
    oco_group_id: str
    broker_stop_loss_attached: bool
    take_profit_filled: bool
    stop_loss_filled: bool
    stop_loss_canceled_by_oco: bool

    guard_count: int
    all_guards_passed: bool

    ledger_entry_count: int
    ledger_contiguous: bool
    ledger_order_valid: bool

    event_count: int
    event_trace_contiguous: bool
    event_trace_order_valid: bool

    realized_profit_points: int
    reward_risk_milli: int

    phase9_lineage_preserved: bool
    admission_lineage_preserved: bool
    contract_lineage_preserved: bool
    execution_lineage_preserved: bool
    safety_audit_lineage_preserved: bool

    risk_contract_valid: bool
    position_contract_valid: bool
    oco_contract_valid: bool
    guard_contract_valid: bool
    ledger_contract_valid: bool
    event_trace_contract_valid: bool
    profit_contract_valid: bool
    terminal_state_valid: bool
    safety_audit_passed: bool

    phase_complete: bool
    ready_for_phase_11: bool

    executes_paper_orders_in_memory: bool
    evaluates_strategy: bool
    initializes_mt5: bool
    sends_broker_request: bool
    writes_external_state: bool
    submits_live_order: bool
    no_live_or_external_effects: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_10_FINAL_HANDOFF_SCHEMA_VERSION:
            raise ValueError("final handoff schema version is inconsistent.")

        if self.phase_number != 10:
            raise ValueError("phase_number must be 10.")

        if self.source_phase_number != 9:
            raise ValueError("source_phase_number must be 9.")

        if self.target_phase_number != 11:
            raise ValueError("target_phase_number must be 11.")

        if self.phase_status != PHASE_10_FINAL_HANDOFF_PHASE_STATUS:
            raise ValueError("phase status must be PHASE_10_COMPLETE.")

        if self.handoff_status != PHASE_10_FINAL_HANDOFF_STATUS:
            raise ValueError("handoff status must be READY_FOR_PHASE_11.")

        if self.execution_mode != PHASE_10_FINAL_HANDOFF_EXECUTION_MODE:
            raise ValueError("execution mode must be IN_MEMORY_PAPER.")

        if self.live_execution_status != PHASE_10_FINAL_HANDOFF_LIVE_EXECUTION_STATUS:
            raise ValueError("live execution must remain BLOCKED.")

        if self.execution_status != "COMPLETED":
            raise ValueError("paper execution status must be COMPLETED.")

        if self.execution_outcome != "TAKE_PROFIT":
            raise ValueError("paper execution outcome must be TAKE_PROFIT.")

        if self.safety_audit_status != "PASSED":
            raise ValueError("paper safety audit status must be PASSED.")

        if self.safety_handoff_status != "READY_FOR_FINAL_HANDOFF":
            raise ValueError("paper safety handoff must be READY_FOR_FINAL_HANDOFF.")

        if self.symbol != "XAUUSD":
            raise ValueError("Phase 10 handoff is XAUUSD only.")

        if self.side != "LONG":
            raise ValueError("deterministic paper side must be LONG.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("Phase 10 timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("Phase 10 must use closed candles only.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("stage risk allocation is inconsistent.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk budget must be 50 bps.")

        if self.maximum_reserved_risk_bps != 50:
            raise ValueError("maximum reserved risk must be 50 bps.")

        if self.maximum_gold_position_count != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.terminal_gold_position_count != 0:
            raise ValueError("terminal Gold position count must be zero.")

        if self.terminal_active_oco_order_count != 0:
            raise ValueError("terminal active OCO count must be zero.")

        if self.terminal_reserved_risk_bps != 0:
            raise ValueError("terminal reserved risk must be zero.")

        if self.position_group_id != "PAPER-XAUUSD-POSITION-001":
            raise ValueError("paper position group is inconsistent.")

        if self.oco_group_id != "PAPER-XAUUSD-OCO-001":
            raise ValueError("paper OCO group is inconsistent.")

        if self.broker_stop_loss_attached is not True:
            raise ValueError("broker stop-loss attachment is required.")

        if self.take_profit_filled is not True:
            raise ValueError("paper take-profit must be filled.")

        if self.stop_loss_filled is not False:
            raise ValueError("stop-loss cannot fill after take-profit.")

        if self.stop_loss_canceled_by_oco is not True:
            raise ValueError("paired stop-loss must be OCO-canceled.")

        if self.guard_count != 4:
            raise ValueError("four paper guards are required.")

        if self.all_guards_passed is not True:
            raise ValueError("all paper guards must pass.")

        if self.ledger_entry_count != 6:
            raise ValueError("six paper ledger entries are required.")

        if self.event_count != 11:
            raise ValueError("eleven paper execution events are required.")

        if self.realized_profit_points != 2000:
            raise ValueError("realized paper profit must be 2000 points.")

        if self.reward_risk_milli != 2000:
            raise ValueError("paper reward-risk ratio must be 2.000R.")

        required_truths = (
            self.ledger_contiguous,
            self.ledger_order_valid,
            self.event_trace_contiguous,
            self.event_trace_order_valid,
            self.phase9_lineage_preserved,
            self.admission_lineage_preserved,
            self.contract_lineage_preserved,
            self.execution_lineage_preserved,
            self.safety_audit_lineage_preserved,
            self.risk_contract_valid,
            self.position_contract_valid,
            self.oco_contract_valid,
            self.guard_contract_valid,
            self.ledger_contract_valid,
            self.event_trace_contract_valid,
            self.profit_contract_valid,
            self.terminal_state_valid,
            self.safety_audit_passed,
            self.phase_complete,
            self.ready_for_phase_11,
            self.executes_paper_orders_in_memory,
            self.no_live_or_external_effects,
        )
        if not all(required_truths):
            raise ValueError("Phase 10 final handoff has a failed invariant.")

        forbidden_effects = (
            self.evaluates_strategy,
            self.initializes_mt5,
            self.sends_broker_request,
            self.writes_external_state,
            self.submits_live_order,
        )
        if any(forbidden_effects):
            raise ValueError("Phase 10 final handoff detected a live effect.")

    @property
    def handoff_digest(self) -> str:
        safety_audit_id = str(getattr(self.safety_audit_report, "audit_id", ""))
        execution_id = str(getattr(self.execution, "execution_id", ""))
        contract_id = str(getattr(self.contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase9_handoff_id = str(getattr(self.phase9_handoff_bundle, "handoff_id", ""))

        material = "|".join(
            (
                self.schema_version,
                safety_audit_id,
                execution_id,
                contract_id,
                permit_id,
                phase9_handoff_id,
                str(self.phase_number),
                str(self.source_phase_number),
                str(self.target_phase_number),
                self.phase_status,
                self.handoff_status,
                self.execution_mode,
                self.live_execution_status,
                self.execution_status,
                self.execution_outcome,
                self.safety_audit_status,
                self.safety_handoff_status,
                self.symbol,
                self.side,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.aggregate_risk_budget_bps),
                str(self.maximum_reserved_risk_bps),
                str(self.maximum_gold_position_count),
                str(self.terminal_gold_position_count),
                str(self.terminal_active_oco_order_count),
                str(self.terminal_reserved_risk_bps),
                self.position_group_id,
                self.oco_group_id,
                str(self.broker_stop_loss_attached),
                str(self.take_profit_filled),
                str(self.stop_loss_filled),
                str(self.stop_loss_canceled_by_oco),
                str(self.guard_count),
                str(self.all_guards_passed),
                str(self.ledger_entry_count),
                str(self.ledger_contiguous),
                str(self.ledger_order_valid),
                str(self.event_count),
                str(self.event_trace_contiguous),
                str(self.event_trace_order_valid),
                str(self.realized_profit_points),
                str(self.reward_risk_milli),
                str(self.phase9_lineage_preserved),
                str(self.admission_lineage_preserved),
                str(self.contract_lineage_preserved),
                str(self.execution_lineage_preserved),
                str(self.safety_audit_lineage_preserved),
                str(self.risk_contract_valid),
                str(self.position_contract_valid),
                str(self.oco_contract_valid),
                str(self.guard_contract_valid),
                str(self.ledger_contract_valid),
                str(self.event_trace_contract_valid),
                str(self.profit_contract_valid),
                str(self.terminal_state_valid),
                str(self.safety_audit_passed),
                str(self.phase_complete),
                str(self.ready_for_phase_11),
                str(self.executes_paper_orders_in_memory),
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
        return f"GOLDXBOT_PHASE_10_FINAL_AUDIT_HANDOFF:SHA256[{self.handoff_digest}]"


@dataclass(frozen=True, slots=True)
class Phase10FinalAuditHandoffDecision:
    """Allowed or blocked Phase 10 final handoff decision."""

    is_allowed: bool
    bundle: Phase10FinalAuditHandoffBundle | None
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
    def bundle_required(self) -> Phase10FinalAuditHandoffBundle:
        if self.bundle is None:
            raise RuntimeError("Phase 10 final audit handoff is blocked.")
        return self.bundle


class StrategyPhase10FinalAuditHandoffFactory:
    """Creates the immutable Phase 10 completion handoff."""

    def create(
        self,
        safety_audit_decision: object,
    ) -> Phase10FinalAuditHandoffDecision:
        if safety_audit_decision is None:
            return Phase10FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=("paper_safety_audit_decision_missing",),
            )

        if getattr(safety_audit_decision, "is_allowed", True) is not True:
            return Phase10FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=("paper_safety_audit_decision_blocked",),
            )

        try:
            report = _required_attribute(
                safety_audit_decision,
                "report_required",
            )
            execution_decision = _required_attribute(
                report,
                "execution_decision",
            )
            execution = _required_attribute(report, "execution")
            contract_decision = _required_attribute(
                execution,
                "contract_decision",
            )
            contract = _required_attribute(execution, "contract")
            admission_decision = _required_attribute(
                contract,
                "admission_decision",
            )
            admission_permit = _required_attribute(
                contract,
                "admission_permit",
            )
            phase9_handoff_decision = _required_attribute(
                admission_permit,
                "phase9_handoff_decision",
            )
            phase9_handoff_bundle = _required_attribute(
                admission_permit,
                "phase9_handoff_bundle",
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
            execution_mode = _required_attribute(
                report,
                "execution_mode",
            )
            execution_status = _required_attribute(
                report,
                "execution_status",
            )
            execution_outcome = _required_attribute(
                report,
                "execution_outcome",
            )
            symbol = _required_attribute(report, "symbol")
            side = _required_attribute(report, "side")
            stage_risk_bps = _required_attribute(
                report,
                "stage_risk_bps",
            )
            aggregate_risk_budget_bps = _required_int(
                report,
                "aggregate_risk_budget_bps",
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
            terminal_reserved_risk_bps = _required_int(
                report,
                "terminal_reserved_risk_bps",
            )
            position_group_id = _required_attribute(
                report,
                "position_group_id",
            )
            oco_group_id = _required_attribute(report, "oco_group_id")
            guard_count = _required_int(report, "guard_count")
            ledger_entry_count = _required_int(
                report,
                "ledger_entry_count",
            )
            event_count = _required_int(report, "event_count")
            realized_profit_points = _required_int(
                report,
                "realized_profit_points",
            )
            reward_risk_milli = _required_int(
                report,
                "reward_risk_milli",
            )
            timeframes = _required_attribute(contract, "timeframes")
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase10FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=(f"phase10_final_handoff_source_invalid:{type(error).__name__}",),
            )

        complete_lineage_valid = (
            report.execution_decision is execution_decision
            and execution_decision.execution_required is execution
            and execution.contract_decision is contract_decision
            and contract_decision.contract_required is contract
            and contract.admission_decision is admission_decision
            and admission_decision.permit_required is admission_permit
            and admission_permit.phase9_handoff_decision is phase9_handoff_decision
            and phase9_handoff_decision.bundle_required is phase9_handoff_bundle
        )

        phase9_lineage_preserved = (
            admission_permit.phase9_handoff_bundle is phase9_handoff_bundle
            and phase9_handoff_bundle.phase_number == 9
            and phase9_handoff_bundle.phase_status == "PHASE_9_COMPLETE"
        )
        admission_lineage_preserved = contract.admission_permit is admission_permit
        contract_lineage_preserved = execution.contract is contract
        execution_lineage_preserved = report.execution is execution
        safety_audit_lineage_preserved = (
            report is safety_audit_decision.report_required and complete_lineage_valid
        )

        risk_contract_valid = (
            stage_risk_bps == (25, 25)
            and aggregate_risk_budget_bps == 50
            and maximum_reserved_risk_bps == 50
            and report.aggregate_risk_never_exceeded is True
            and report.stage_risk_sum_valid is True
        )
        position_contract_valid = (
            maximum_gold_position_count == 1
            and terminal_gold_position_count == 0
            and report.one_gold_position_limit_preserved is True
        )
        oco_contract_valid = (
            report.oco_contract_valid is True
            and report.broker_stop_loss_attached is True
            and report.take_profit_filled is True
            and report.stop_loss_filled is False
            and report.stop_loss_canceled_by_oco is True
            and terminal_active_oco_order_count == 0
        )
        guard_contract_valid = guard_count == 4 and report.all_guards_passed is True
        ledger_contract_valid = (
            ledger_entry_count == 6
            and report.ledger_contiguous is True
            and report.ledger_order_valid is True
        )
        event_trace_contract_valid = (
            event_count == 11
            and report.event_trace_contiguous is True
            and report.event_trace_order_valid is True
        )
        profit_contract_valid = (
            realized_profit_points == 2000
            and reward_risk_milli == 2000
            and report.profit_metrics_valid is True
        )
        terminal_state_valid = (
            terminal_gold_position_count == 0
            and terminal_active_oco_order_count == 0
            and terminal_reserved_risk_bps == 0
            and report.terminal_flat_state_valid is True
        )
        no_live_or_external_effects = (
            live_execution_status == "BLOCKED"
            and report.no_live_or_external_effects is True
            and report.evaluates_strategy is False
            and report.initializes_mt5 is False
            and report.sends_broker_request is False
            and report.writes_external_state is False
            and report.submits_live_order is False
        )

        try:
            bundle = Phase10FinalAuditHandoffBundle(
                safety_audit_decision=safety_audit_decision,
                safety_audit_report=report,
                execution_decision=execution_decision,
                execution=execution,
                contract_decision=contract_decision,
                contract=contract,
                admission_decision=admission_decision,
                admission_permit=admission_permit,
                phase9_handoff_bundle=phase9_handoff_bundle,
                schema_version=PHASE_10_FINAL_HANDOFF_SCHEMA_VERSION,
                phase_number=10,
                source_phase_number=9,
                target_phase_number=11,
                phase_status=PHASE_10_FINAL_HANDOFF_PHASE_STATUS,
                handoff_status=PHASE_10_FINAL_HANDOFF_STATUS,
                execution_mode=str(execution_mode),
                live_execution_status=str(live_execution_status),
                execution_status=str(execution_status),
                execution_outcome=str(execution_outcome),
                safety_audit_status=str(audit_status),
                safety_handoff_status=str(safety_handoff_status),
                symbol=str(symbol),
                side=str(side),
                timeframes=timeframes,
                closed_candles_only=(report.uses_closed_candles_only is True),
                stage_risk_bps=stage_risk_bps,
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                maximum_reserved_risk_bps=maximum_reserved_risk_bps,
                maximum_gold_position_count=(maximum_gold_position_count),
                terminal_gold_position_count=(terminal_gold_position_count),
                terminal_active_oco_order_count=(terminal_active_oco_order_count),
                terminal_reserved_risk_bps=terminal_reserved_risk_bps,
                position_group_id=str(position_group_id),
                oco_group_id=str(oco_group_id),
                broker_stop_loss_attached=(report.broker_stop_loss_attached is True),
                take_profit_filled=report.take_profit_filled is True,
                stop_loss_filled=report.stop_loss_filled is True,
                stop_loss_canceled_by_oco=(report.stop_loss_canceled_by_oco is True),
                guard_count=guard_count,
                all_guards_passed=report.all_guards_passed is True,
                ledger_entry_count=ledger_entry_count,
                ledger_contiguous=report.ledger_contiguous is True,
                ledger_order_valid=report.ledger_order_valid is True,
                event_count=event_count,
                event_trace_contiguous=(report.event_trace_contiguous is True),
                event_trace_order_valid=(report.event_trace_order_valid is True),
                realized_profit_points=realized_profit_points,
                reward_risk_milli=reward_risk_milli,
                phase9_lineage_preserved=phase9_lineage_preserved,
                admission_lineage_preserved=(admission_lineage_preserved),
                contract_lineage_preserved=contract_lineage_preserved,
                execution_lineage_preserved=(execution_lineage_preserved),
                safety_audit_lineage_preserved=(safety_audit_lineage_preserved),
                risk_contract_valid=risk_contract_valid,
                position_contract_valid=position_contract_valid,
                oco_contract_valid=oco_contract_valid,
                guard_contract_valid=guard_contract_valid,
                ledger_contract_valid=ledger_contract_valid,
                event_trace_contract_valid=(event_trace_contract_valid),
                profit_contract_valid=profit_contract_valid,
                terminal_state_valid=terminal_state_valid,
                safety_audit_passed=(report.safety_audit_passed is True),
                phase_complete=True,
                ready_for_phase_11=True,
                executes_paper_orders_in_memory=(report.executes_paper_orders_in_memory is True),
                evaluates_strategy=report.evaluates_strategy is True,
                initializes_mt5=report.initializes_mt5 is True,
                sends_broker_request=report.sends_broker_request is True,
                writes_external_state=report.writes_external_state is True,
                submits_live_order=report.submits_live_order is True,
                no_live_or_external_effects=(no_live_or_external_effects),
            )
        except ValueError as error:
            return Phase10FinalAuditHandoffDecision(
                is_allowed=False,
                bundle=None,
                blockers=(f"phase10_final_handoff_invalid:{type(error).__name__}",),
            )

        return Phase10FinalAuditHandoffDecision(
            is_allowed=True,
            bundle=bundle,
            blockers=(),
        )


def create_phase10_final_audit_handoff(
    safety_audit_decision: object,
) -> Phase10FinalAuditHandoffDecision:
    """Create the immutable Phase 10 final audit handoff."""

    return StrategyPhase10FinalAuditHandoffFactory().create(safety_audit_decision)


__all__ = (
    "PHASE_10_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_10_FINAL_HANDOFF_PHASE_STATUS",
    "PHASE_10_FINAL_HANDOFF_STATUS",
    "PHASE_10_FINAL_HANDOFF_EXECUTION_MODE",
    "PHASE_10_FINAL_HANDOFF_LIVE_EXECUTION_STATUS",
    "Phase10FinalAuditHandoffBundle",
    "Phase10FinalAuditHandoffDecision",
    "StrategyPhase10FinalAuditHandoffFactory",
    "create_phase10_final_audit_handoff",
)
