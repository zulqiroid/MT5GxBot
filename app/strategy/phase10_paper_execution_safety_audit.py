"""Immutable Phase 10 paper execution safety audit.

This module audits the deterministic in-memory paper execution created in
Step 10.3. It verifies staged and aggregate risk, one Gold position
maximum, terminal flat state, OCO and broker stop-loss behavior, four
passed guards, immutable paper-ledger integrity, execution-event
continuity, realized paper profit, and the absence of live or external
side effects.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase10_deterministic_paper_execution_engine import (
    PHASE_10_PAPER_EXECUTION_EVENT_TYPES,
    PHASE_10_PAPER_LEDGER_ENTRY_TYPES,
)

PHASE_10_PAPER_SAFETY_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_10_PAPER_SAFETY_AUDIT_STATUS = "PASSED"
PHASE_10_PAPER_SAFETY_HANDOFF_STATUS = "READY_FOR_FINAL_HANDOFF"
PHASE_10_PAPER_SAFETY_LIVE_EXECUTION_STATUS = "BLOCKED"
PHASE_10_PAPER_SAFETY_REQUIRED_GUARDS = (
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
class Phase10PaperSafetyAuditFinding:
    """Immutable result for one paper-execution safety invariant."""

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
class Phase10PaperExecutionSafetyAuditReport:
    """Immutable proof that the Step 10.3 paper execution remained safe."""

    execution_decision: object
    execution: object
    contract: object
    admission_permit: object

    schema_version: str
    audit_status: str
    final_handoff_status: str
    live_execution_status: str

    execution_mode: str
    execution_status: str
    execution_outcome: str
    symbol: str
    side: str

    stage_risk_bps: tuple[int, ...]
    aggregate_risk_budget_bps: int
    maximum_reserved_risk_bps: int
    aggregate_risk_never_exceeded: bool
    stage_risk_sum_valid: bool

    maximum_gold_position_count: int
    terminal_gold_position_count: int
    terminal_active_oco_order_count: int
    terminal_reserved_risk_bps: int
    one_gold_position_limit_preserved: bool
    terminal_flat_state_valid: bool

    position_group_id: str
    oco_group_id: str
    broker_stop_loss_attached: bool
    take_profit_filled: bool
    stop_loss_filled: bool
    stop_loss_canceled_by_oco: bool
    oco_contract_valid: bool

    guard_names: tuple[str, ...]
    guard_count: int
    all_guards_passed: bool

    ledger_entry_types: tuple[str, ...]
    ledger_sequence_indices: tuple[int, ...]
    ledger_entry_count: int
    ledger_contiguous: bool
    ledger_order_valid: bool

    event_types: tuple[str, ...]
    event_sequence_indices: tuple[int, ...]
    event_count: int
    event_trace_contiguous: bool
    event_trace_order_valid: bool

    realized_profit_points: int
    reward_risk_milli: int
    profit_metrics_valid: bool

    uses_closed_candles_only: bool
    executes_paper_orders_in_memory: bool
    evaluates_strategy: bool
    initializes_mt5: bool
    sends_broker_request: bool
    writes_external_state: bool
    submits_live_order: bool
    no_live_or_external_effects: bool

    findings: tuple[Phase10PaperSafetyAuditFinding, ...]
    safety_audit_passed: bool
    ready_for_final_handoff: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_10_PAPER_SAFETY_AUDIT_SCHEMA_VERSION:
            raise ValueError("paper safety schema version is inconsistent.")

        if self.audit_status != PHASE_10_PAPER_SAFETY_AUDIT_STATUS:
            raise ValueError("paper safety audit status must be PASSED.")

        if self.final_handoff_status != PHASE_10_PAPER_SAFETY_HANDOFF_STATUS:
            raise ValueError("paper safety handoff must be READY_FOR_FINAL_HANDOFF.")

        if self.live_execution_status != PHASE_10_PAPER_SAFETY_LIVE_EXECUTION_STATUS:
            raise ValueError("live execution must remain BLOCKED.")

        if self.execution_mode != "IN_MEMORY_PAPER":
            raise ValueError("execution mode must be IN_MEMORY_PAPER.")

        if self.execution_status != "COMPLETED":
            raise ValueError("paper execution status must be COMPLETED.")

        if self.execution_outcome != "TAKE_PROFIT":
            raise ValueError("paper execution outcome must be TAKE_PROFIT.")

        if self.symbol != "XAUUSD":
            raise ValueError("paper audit is XAUUSD only.")

        if self.side != "LONG":
            raise ValueError("deterministic paper side must be LONG.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("paper stage risk is inconsistent.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("paper aggregate risk must be 50 bps.")

        if self.maximum_reserved_risk_bps != 50:
            raise ValueError("maximum reserved risk must be 50 bps.")

        if self.maximum_gold_position_count != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.terminal_gold_position_count != 0:
            raise ValueError("paper execution must finish flat.")

        if self.terminal_active_oco_order_count != 0:
            raise ValueError("terminal active OCO count must be zero.")

        if self.terminal_reserved_risk_bps != 0:
            raise ValueError("terminal reserved risk must be zero.")

        if self.position_group_id != "PAPER-XAUUSD-POSITION-001":
            raise ValueError("paper position group is inconsistent.")

        if self.oco_group_id != "PAPER-XAUUSD-OCO-001":
            raise ValueError("paper OCO group is inconsistent.")

        if self.guard_names != PHASE_10_PAPER_SAFETY_REQUIRED_GUARDS:
            raise ValueError("paper guard names are inconsistent.")

        if self.guard_count != 4:
            raise ValueError("four paper guards are required.")

        if self.ledger_entry_types != PHASE_10_PAPER_LEDGER_ENTRY_TYPES:
            raise ValueError("paper ledger ordering is inconsistent.")

        if self.ledger_sequence_indices != tuple(range(len(PHASE_10_PAPER_LEDGER_ENTRY_TYPES))):
            raise ValueError("paper ledger sequence is inconsistent.")

        if self.ledger_entry_count != 6:
            raise ValueError("six paper ledger entries are required.")

        if self.event_types != PHASE_10_PAPER_EXECUTION_EVENT_TYPES:
            raise ValueError("paper event ordering is inconsistent.")

        if self.event_sequence_indices != tuple(range(len(PHASE_10_PAPER_EXECUTION_EVENT_TYPES))):
            raise ValueError("paper event sequence is inconsistent.")

        if self.event_count != 11:
            raise ValueError("eleven paper execution events are required.")

        if self.realized_profit_points != 2000:
            raise ValueError("realized paper profit must be 2000 points.")

        if self.reward_risk_milli != 2000:
            raise ValueError("paper reward-risk ratio must be 2.000R.")

        required_truths = (
            self.aggregate_risk_never_exceeded,
            self.stage_risk_sum_valid,
            self.one_gold_position_limit_preserved,
            self.terminal_flat_state_valid,
            self.broker_stop_loss_attached,
            self.take_profit_filled,
            self.stop_loss_canceled_by_oco,
            self.oco_contract_valid,
            self.all_guards_passed,
            self.ledger_contiguous,
            self.ledger_order_valid,
            self.event_trace_contiguous,
            self.event_trace_order_valid,
            self.profit_metrics_valid,
            self.uses_closed_candles_only,
            self.executes_paper_orders_in_memory,
            self.no_live_or_external_effects,
            self.safety_audit_passed,
            self.ready_for_final_handoff,
        )
        if not all(required_truths):
            raise ValueError("paper safety audit contains a failed invariant.")

        if self.stop_loss_filled:
            raise ValueError("stop-loss cannot fill after take-profit.")

        forbidden_effects = (
            self.evaluates_strategy,
            self.initializes_mt5,
            self.sends_broker_request,
            self.writes_external_state,
            self.submits_live_order,
        )
        if any(forbidden_effects):
            raise ValueError("paper safety audit detected a live effect.")

        if len(self.findings) != 10:
            raise ValueError("ten immutable paper findings are required.")

        if not all(finding.passed is True for finding in self.findings):
            raise ValueError("all paper safety findings must pass.")

    @property
    def audit_digest(self) -> str:
        execution_id = str(getattr(self.execution, "execution_id", ""))
        contract_id = str(getattr(self.contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        finding_material = ",".join(finding.finding_digest for finding in self.findings)
        material = "|".join(
            (
                self.schema_version,
                execution_id,
                contract_id,
                permit_id,
                self.audit_status,
                self.final_handoff_status,
                self.live_execution_status,
                self.execution_mode,
                self.execution_status,
                self.execution_outcome,
                self.symbol,
                self.side,
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.aggregate_risk_budget_bps),
                str(self.maximum_reserved_risk_bps),
                str(self.aggregate_risk_never_exceeded),
                str(self.stage_risk_sum_valid),
                str(self.maximum_gold_position_count),
                str(self.terminal_gold_position_count),
                str(self.terminal_active_oco_order_count),
                str(self.terminal_reserved_risk_bps),
                str(self.one_gold_position_limit_preserved),
                str(self.terminal_flat_state_valid),
                self.position_group_id,
                self.oco_group_id,
                str(self.broker_stop_loss_attached),
                str(self.take_profit_filled),
                str(self.stop_loss_filled),
                str(self.stop_loss_canceled_by_oco),
                str(self.oco_contract_valid),
                ",".join(self.guard_names),
                str(self.guard_count),
                str(self.all_guards_passed),
                ",".join(self.ledger_entry_types),
                ",".join(str(value) for value in self.ledger_sequence_indices),
                str(self.ledger_entry_count),
                str(self.ledger_contiguous),
                str(self.ledger_order_valid),
                ",".join(self.event_types),
                ",".join(str(value) for value in self.event_sequence_indices),
                str(self.event_count),
                str(self.event_trace_contiguous),
                str(self.event_trace_order_valid),
                str(self.realized_profit_points),
                str(self.reward_risk_milli),
                str(self.profit_metrics_valid),
                str(self.uses_closed_candles_only),
                str(self.executes_paper_orders_in_memory),
                str(self.evaluates_strategy),
                str(self.initializes_mt5),
                str(self.sends_broker_request),
                str(self.writes_external_state),
                str(self.submits_live_order),
                str(self.no_live_or_external_effects),
                finding_material,
                str(self.safety_audit_passed),
                str(self.ready_for_final_handoff),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return f"GOLDXBOT_PHASE_10_PAPER_EXECUTION_SAFETY_AUDIT:SHA256[{self.audit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase10PaperExecutionSafetyAuditDecision:
    """Allowed or blocked Phase 10 paper safety audit decision."""

    is_allowed: bool
    report: Phase10PaperExecutionSafetyAuditReport | None
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
    def report_required(self) -> Phase10PaperExecutionSafetyAuditReport:
        if self.report is None:
            raise RuntimeError("Phase 10 paper safety audit is blocked.")
        return self.report


class StrategyPhase10PaperExecutionSafetyAuditor:
    """Audits the in-memory paper execution without causing effects."""

    def audit(
        self,
        execution_decision: object,
    ) -> Phase10PaperExecutionSafetyAuditDecision:
        if execution_decision is None:
            return Phase10PaperExecutionSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("paper_execution_decision_missing",),
            )

        if getattr(execution_decision, "is_allowed", True) is not True:
            return Phase10PaperExecutionSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("paper_execution_decision_blocked",),
            )

        try:
            execution = _required_attribute(
                execution_decision,
                "execution_required",
            )
            contract = _required_attribute(execution, "contract")
            admission_permit = _required_attribute(
                contract,
                "admission_permit",
            )

            execution_mode = _required_attribute(
                execution,
                "execution_mode",
            )
            execution_status = _required_attribute(execution, "status")
            execution_outcome = _required_attribute(execution, "outcome")
            symbol = _required_attribute(execution, "symbol")
            side = _required_attribute(execution, "side")
            stage_risk_bps = _required_attribute(
                execution,
                "stage_risk_bps",
            )
            aggregate_risk_budget_bps = _required_int(
                execution,
                "aggregate_risk_budget_bps",
            )
            maximum_reserved_risk_bps = _required_int(
                execution,
                "maximum_reserved_risk_bps",
            )
            maximum_gold_position_count = _required_int(
                execution,
                "maximum_gold_position_count",
            )
            terminal_gold_position_count = _required_int(
                execution,
                "terminal_gold_position_count",
            )
            terminal_active_oco_order_count = _required_int(
                execution,
                "terminal_active_oco_order_count",
            )
            terminal_reserved_risk_bps = _required_int(
                execution,
                "terminal_reserved_risk_bps",
            )
            position_group_id = _required_attribute(
                execution,
                "position_group_id",
            )
            oco_group_id = _required_attribute(
                execution,
                "oco_group_id",
            )
            broker_stop_loss_attached = _required_attribute(
                execution,
                "broker_stop_loss_attached",
            )
            take_profit_filled = _required_attribute(
                execution,
                "take_profit_filled",
            )
            stop_loss_filled = _required_attribute(
                execution,
                "stop_loss_filled",
            )
            stop_loss_canceled_by_oco = _required_attribute(
                execution,
                "stop_loss_canceled_by_oco",
            )
            guard_results = _required_attribute(
                execution,
                "guard_results",
            )
            ledger_entries = _required_attribute(
                execution,
                "ledger_entries",
            )
            events = _required_attribute(execution, "events")
            realized_profit_points = _required_int(
                execution,
                "realized_profit_points",
            )
            reward_risk_milli = _required_int(
                execution,
                "reward_risk_milli",
            )
            uses_closed_candles_only = _required_attribute(
                execution,
                "uses_closed_candles_only",
            )
            executes_paper_orders_in_memory = _required_attribute(
                execution,
                "executes_paper_orders_in_memory",
            )
            evaluates_strategy = _required_attribute(
                execution,
                "evaluates_strategy",
            )
            initializes_mt5 = _required_attribute(
                execution,
                "initializes_mt5",
            )
            sends_broker_request = _required_attribute(
                execution,
                "sends_broker_request",
            )
            writes_external_state = _required_attribute(
                execution,
                "writes_external_state",
            )
            submits_live_order = _required_attribute(
                execution,
                "submits_live_order",
            )
            live_execution_status = _required_attribute(
                admission_permit,
                "live_execution_status",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase10PaperExecutionSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=(f"paper_execution_invalid:{type(error).__name__}",),
            )

        if (
            not isinstance(stage_risk_bps, tuple)
            or not isinstance(guard_results, tuple)
            or not isinstance(ledger_entries, tuple)
            or not isinstance(events, tuple)
        ):
            return Phase10PaperExecutionSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("paper_execution_shape_invalid",),
            )

        aggregate_risk_never_exceeded = all(
            event.reserved_risk_bps <= aggregate_risk_budget_bps for event in events
        )
        stage_risk_sum_valid = sum(stage_risk_bps) == aggregate_risk_budget_bps
        one_gold_position_limit_preserved = maximum_gold_position_count == 1 and all(
            event.open_gold_position_count <= 1 for event in events
        )
        terminal_flat_state_valid = (
            terminal_gold_position_count == 0
            and terminal_active_oco_order_count == 0
            and terminal_reserved_risk_bps == 0
        )
        oco_contract_valid = (
            position_group_id == "PAPER-XAUUSD-POSITION-001"
            and oco_group_id == "PAPER-XAUUSD-OCO-001"
            and broker_stop_loss_attached is True
            and take_profit_filled is True
            and stop_loss_filled is False
            and stop_loss_canceled_by_oco is True
            and terminal_active_oco_order_count == 0
        )

        guard_names = tuple(result.name for result in guard_results)
        all_guards_passed = guard_names == PHASE_10_PAPER_SAFETY_REQUIRED_GUARDS and all(
            result.passed is True for result in guard_results
        )

        ledger_entry_types = tuple(entry.entry_type for entry in ledger_entries)
        ledger_sequence_indices = tuple(entry.sequence_index for entry in ledger_entries)
        ledger_contiguous = ledger_sequence_indices == tuple(range(len(ledger_entries)))
        ledger_order_valid = ledger_entry_types == PHASE_10_PAPER_LEDGER_ENTRY_TYPES

        event_types = tuple(event.event_type for event in events)
        event_sequence_indices = tuple(event.sequence_index for event in events)
        event_trace_contiguous = event_sequence_indices == tuple(range(len(events)))
        event_trace_order_valid = event_types == PHASE_10_PAPER_EXECUTION_EVENT_TYPES

        profit_metrics_valid = (
            realized_profit_points == 2000
            and reward_risk_milli == 2000
            and execution.final_price_points == execution.take_profit_price_points
        )

        no_live_or_external_effects = (
            live_execution_status == "BLOCKED"
            and evaluates_strategy is False
            and initializes_mt5 is False
            and sends_broker_request is False
            and writes_external_state is False
            and submits_live_order is False
        )

        findings = (
            Phase10PaperSafetyAuditFinding(
                name="aggregate_risk",
                passed=(
                    aggregate_risk_never_exceeded
                    and stage_risk_sum_valid
                    and maximum_reserved_risk_bps == 50
                ),
                evidence="25+25 bps remained within the 50 bps budget.",
            ),
            Phase10PaperSafetyAuditFinding(
                name="one_gold_position",
                passed=one_gold_position_limit_preserved,
                evidence="Maximum paper Gold position count was one.",
            ),
            Phase10PaperSafetyAuditFinding(
                name="terminal_flat_state",
                passed=terminal_flat_state_valid,
                evidence="Position, OCO, and reserved risk finished at zero.",
            ),
            Phase10PaperSafetyAuditFinding(
                name="oco_and_broker_stop_loss",
                passed=oco_contract_valid,
                evidence="TP filled and paired broker SL was OCO-canceled.",
            ),
            Phase10PaperSafetyAuditFinding(
                name="kill_switches",
                passed=all_guards_passed,
                evidence="All four required paper guards passed.",
            ),
            Phase10PaperSafetyAuditFinding(
                name="paper_ledger_integrity",
                passed=ledger_contiguous and ledger_order_valid,
                evidence="Six immutable ledger entries are ordered.",
            ),
            Phase10PaperSafetyAuditFinding(
                name="execution_trace_integrity",
                passed=event_trace_contiguous and event_trace_order_valid,
                evidence="Eleven paper events are contiguous and ordered.",
            ),
            Phase10PaperSafetyAuditFinding(
                name="paper_profit_metrics",
                passed=profit_metrics_valid,
                evidence="Paper result is 2000 points at 2.000R.",
            ),
            Phase10PaperSafetyAuditFinding(
                name="closed_candle_scope",
                passed=uses_closed_candles_only is True,
                evidence="Paper execution used closed candles only.",
            ),
            Phase10PaperSafetyAuditFinding(
                name="no_live_effects",
                passed=no_live_or_external_effects,
                evidence="No MT5, broker, external write, or live order effect.",
            ),
        )

        safety_audit_passed = all(finding.passed is True for finding in findings)

        try:
            report = Phase10PaperExecutionSafetyAuditReport(
                execution_decision=execution_decision,
                execution=execution,
                contract=contract,
                admission_permit=admission_permit,
                schema_version=(PHASE_10_PAPER_SAFETY_AUDIT_SCHEMA_VERSION),
                audit_status=PHASE_10_PAPER_SAFETY_AUDIT_STATUS,
                final_handoff_status=(PHASE_10_PAPER_SAFETY_HANDOFF_STATUS),
                live_execution_status=str(live_execution_status),
                execution_mode=str(execution_mode),
                execution_status=str(execution_status),
                execution_outcome=str(execution_outcome),
                symbol=str(symbol),
                side=str(side),
                stage_risk_bps=stage_risk_bps,
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                maximum_reserved_risk_bps=maximum_reserved_risk_bps,
                aggregate_risk_never_exceeded=(aggregate_risk_never_exceeded),
                stage_risk_sum_valid=stage_risk_sum_valid,
                maximum_gold_position_count=(maximum_gold_position_count),
                terminal_gold_position_count=(terminal_gold_position_count),
                terminal_active_oco_order_count=(terminal_active_oco_order_count),
                terminal_reserved_risk_bps=terminal_reserved_risk_bps,
                one_gold_position_limit_preserved=(one_gold_position_limit_preserved),
                terminal_flat_state_valid=terminal_flat_state_valid,
                position_group_id=str(position_group_id),
                oco_group_id=str(oco_group_id),
                broker_stop_loss_attached=(broker_stop_loss_attached is True),
                take_profit_filled=take_profit_filled is True,
                stop_loss_filled=stop_loss_filled is True,
                stop_loss_canceled_by_oco=(stop_loss_canceled_by_oco is True),
                oco_contract_valid=oco_contract_valid,
                guard_names=guard_names,
                guard_count=len(guard_results),
                all_guards_passed=all_guards_passed,
                ledger_entry_types=ledger_entry_types,
                ledger_sequence_indices=ledger_sequence_indices,
                ledger_entry_count=len(ledger_entries),
                ledger_contiguous=ledger_contiguous,
                ledger_order_valid=ledger_order_valid,
                event_types=event_types,
                event_sequence_indices=event_sequence_indices,
                event_count=len(events),
                event_trace_contiguous=event_trace_contiguous,
                event_trace_order_valid=event_trace_order_valid,
                realized_profit_points=realized_profit_points,
                reward_risk_milli=reward_risk_milli,
                profit_metrics_valid=profit_metrics_valid,
                uses_closed_candles_only=(uses_closed_candles_only is True),
                executes_paper_orders_in_memory=(executes_paper_orders_in_memory is True),
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
            return Phase10PaperExecutionSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=(f"paper_safety_audit_failed:{type(error).__name__}",),
            )

        return Phase10PaperExecutionSafetyAuditDecision(
            is_allowed=True,
            report=report,
            blockers=(),
        )


def audit_phase10_paper_execution_safety(
    execution_decision: object,
) -> Phase10PaperExecutionSafetyAuditDecision:
    """Audit the deterministic Phase 10 paper execution."""

    return StrategyPhase10PaperExecutionSafetyAuditor().audit(execution_decision)


__all__ = (
    "PHASE_10_PAPER_SAFETY_AUDIT_SCHEMA_VERSION",
    "PHASE_10_PAPER_SAFETY_AUDIT_STATUS",
    "PHASE_10_PAPER_SAFETY_HANDOFF_STATUS",
    "PHASE_10_PAPER_SAFETY_LIVE_EXECUTION_STATUS",
    "PHASE_10_PAPER_SAFETY_REQUIRED_GUARDS",
    "Phase10PaperSafetyAuditFinding",
    "Phase10PaperExecutionSafetyAuditReport",
    "Phase10PaperExecutionSafetyAuditDecision",
    "StrategyPhase10PaperExecutionSafetyAuditor",
    "audit_phase10_paper_execution_safety",
)
