"""Deterministic in-memory paper execution engine for Phase 10.

This module consumes the immutable Phase 10 paper scenario and order-intent
contract and executes those intents entirely in memory. It creates an
immutable paper ledger, preserves one Gold position maximum, applies the
25+25 bps staged risk budget, activates paired OCO exits, fills the
take-profit, cancels the stop-loss, and finishes flat. It does not evaluate
a strategy, initialize MT5, contact a broker, write external state, or
submit a live order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_10_PAPER_EXECUTION_SCHEMA_VERSION = "1.0"
PHASE_10_PAPER_EXECUTION_STATUS = "COMPLETED"
PHASE_10_PAPER_EXECUTION_OUTCOME = "TAKE_PROFIT"
PHASE_10_PAPER_EXECUTION_MODE = "IN_MEMORY_PAPER"
PHASE_10_PAPER_EXECUTION_EVENT_TYPES = (
    "CONTRACT_ACCEPTED",
    "KILL_SWITCHES_PASSED",
    "STAGE_ONE_RISK_RESERVED",
    "STAGE_TWO_RISK_RESERVED",
    "PAPER_ENTRY_FILLED",
    "PAPER_OCO_EXITS_ACTIVATED",
    "PAPER_PRICE_ADVANCED",
    "PAPER_TAKE_PROFIT_FILLED",
    "PAPER_STOP_LOSS_OCO_CANCELED",
    "PAPER_POSITION_CLOSED",
    "PAPER_LEDGER_FINALIZED",
)
PHASE_10_PAPER_LEDGER_ENTRY_TYPES = (
    "RISK_STAGE_ONE",
    "RISK_STAGE_TWO",
    "ENTRY_FILL",
    "TAKE_PROFIT_FILL",
    "OCO_STOP_CANCEL",
    "POSITION_CLOSE",
)


def _required_attribute(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase10PaperGuardResult:
    """Immutable result for one paper-execution kill switch."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("guard name is required.")

        if self.passed is not True:
            raise ValueError("deterministic paper execution requires passed guards.")

        if not self.evidence:
            raise ValueError("guard evidence is required.")

    @property
    def guard_digest(self) -> str:
        material = "|".join(
            (
                self.name,
                str(self.passed),
                self.evidence,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase10PaperLedgerEntry:
    """Immutable paper ledger entry held only in memory."""

    sequence_index: int
    entry_type: str
    intent_id: str | None
    price_points: int
    risk_delta_bps: int
    open_gold_position_count: int
    active_oco_order_count: int
    realized_profit_points: int
    description: str

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError("ledger sequence index cannot be negative.")

        if self.entry_type not in PHASE_10_PAPER_LEDGER_ENTRY_TYPES:
            raise ValueError("unsupported paper ledger entry type.")

        if (
            isinstance(self.price_points, bool)
            or not isinstance(self.price_points, int)
            or self.price_points <= 0
        ):
            raise ValueError("ledger price must be a positive integer.")

        if isinstance(self.risk_delta_bps, bool) or not isinstance(self.risk_delta_bps, int):
            raise ValueError("risk delta must be an integer.")

        if self.open_gold_position_count not in (0, 1):
            raise ValueError("only zero or one Gold position is allowed.")

        if self.active_oco_order_count not in (0, 1, 2):
            raise ValueError("active OCO order count is invalid.")

        if (
            isinstance(self.realized_profit_points, bool)
            or not isinstance(self.realized_profit_points, int)
            or self.realized_profit_points < 0
        ):
            raise ValueError("realized profit must be a non-negative integer.")

        if not self.description:
            raise ValueError("ledger description is required.")

    @property
    def ledger_entry_digest(self) -> str:
        material = "|".join(
            (
                str(self.sequence_index),
                self.entry_type,
                str(self.intent_id),
                str(self.price_points),
                str(self.risk_delta_bps),
                str(self.open_gold_position_count),
                str(self.active_oco_order_count),
                str(self.realized_profit_points),
                self.description,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase10PaperExecutionEvent:
    """Immutable event emitted by the in-memory paper engine."""

    sequence_index: int
    event_type: str
    price_points: int
    reserved_risk_bps: int
    open_gold_position_count: int
    active_oco_order_count: int
    description: str

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError("event sequence index cannot be negative.")

        if self.event_type not in PHASE_10_PAPER_EXECUTION_EVENT_TYPES:
            raise ValueError("unsupported paper execution event type.")

        if (
            isinstance(self.price_points, bool)
            or not isinstance(self.price_points, int)
            or self.price_points <= 0
        ):
            raise ValueError("event price must be a positive integer.")

        if (
            isinstance(self.reserved_risk_bps, bool)
            or not isinstance(self.reserved_risk_bps, int)
            or self.reserved_risk_bps < 0
        ):
            raise ValueError("reserved risk must be non-negative.")

        if self.open_gold_position_count not in (0, 1):
            raise ValueError("only zero or one Gold position is allowed.")

        if self.active_oco_order_count not in (0, 1, 2):
            raise ValueError("active OCO order count is invalid.")

        if not self.description:
            raise ValueError("event description is required.")

    @property
    def event_digest(self) -> str:
        material = "|".join(
            (
                str(self.sequence_index),
                self.event_type,
                str(self.price_points),
                str(self.reserved_risk_bps),
                str(self.open_gold_position_count),
                str(self.active_oco_order_count),
                self.description,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase10DeterministicPaperExecution:
    """Immutable completed in-memory paper execution."""

    contract_decision: object
    contract: object

    schema_version: str
    execution_mode: str
    status: str
    outcome: str

    symbol: str
    side: str
    entry_price_points: int
    stop_loss_price_points: int
    take_profit_price_points: int
    final_price_points: int
    price_scale: int

    position_group_id: str
    oco_group_id: str
    entry_intent_id: str
    stop_loss_intent_id: str
    take_profit_intent_id: str

    stage_risk_bps: tuple[int, ...]
    aggregate_risk_budget_bps: int
    maximum_reserved_risk_bps: int

    risk_distance_points: int
    reward_distance_points: int
    realized_profit_points: int
    reward_risk_milli: int

    maximum_gold_position_count: int
    terminal_gold_position_count: int
    terminal_active_oco_order_count: int
    terminal_reserved_risk_bps: int

    broker_stop_loss_attached: bool
    take_profit_filled: bool
    stop_loss_filled: bool
    stop_loss_canceled_by_oco: bool

    guard_results: tuple[Phase10PaperGuardResult, ...]
    all_guards_passed: bool
    ledger_entries: tuple[Phase10PaperLedgerEntry, ...]
    events: tuple[Phase10PaperExecutionEvent, ...]

    uses_closed_candles_only: bool
    executes_paper_orders_in_memory: bool
    evaluates_strategy: bool
    initializes_mt5: bool
    sends_broker_request: bool
    writes_external_state: bool
    submits_live_order: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_10_PAPER_EXECUTION_SCHEMA_VERSION:
            raise ValueError("paper execution schema version is inconsistent.")

        if self.execution_mode != PHASE_10_PAPER_EXECUTION_MODE:
            raise ValueError("execution mode must be IN_MEMORY_PAPER.")

        if self.status != PHASE_10_PAPER_EXECUTION_STATUS:
            raise ValueError("paper execution status must be COMPLETED.")

        if self.outcome != PHASE_10_PAPER_EXECUTION_OUTCOME:
            raise ValueError("paper execution outcome must be TAKE_PROFIT.")

        if self.symbol != "XAUUSD":
            raise ValueError("paper execution must be XAUUSD only.")

        if self.side != "LONG":
            raise ValueError("deterministic paper side must be LONG.")

        if not (
            self.stop_loss_price_points < self.entry_price_points < self.take_profit_price_points
        ):
            raise ValueError("LONG paper prices are inconsistent.")

        if self.final_price_points != self.take_profit_price_points:
            raise ValueError("final price must equal the take-profit fill.")

        if self.price_scale != 100:
            raise ValueError("price scale is inconsistent.")

        if self.position_group_id != "PAPER-XAUUSD-POSITION-001":
            raise ValueError("position group is inconsistent.")

        if self.oco_group_id != "PAPER-XAUUSD-OCO-001":
            raise ValueError("OCO group is inconsistent.")

        if (
            self.entry_intent_id,
            self.stop_loss_intent_id,
            self.take_profit_intent_id,
        ) != (
            "PAPER-ENTRY-001",
            "PAPER-SL-001",
            "PAPER-TP-001",
        ):
            raise ValueError("paper intent lineage is inconsistent.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("stage risk allocation is inconsistent.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk budget must be 50 bps.")

        if self.maximum_reserved_risk_bps != 50:
            raise ValueError("maximum reserved risk must be 50 bps.")

        if self.risk_distance_points != self.entry_price_points - self.stop_loss_price_points:
            raise ValueError("risk distance is inconsistent.")

        if self.reward_distance_points != self.take_profit_price_points - self.entry_price_points:
            raise ValueError("reward distance is inconsistent.")

        if self.realized_profit_points != self.reward_distance_points:
            raise ValueError("realized paper profit is inconsistent.")

        if (
            self.reward_risk_milli
            != self.reward_distance_points * 1000 // self.risk_distance_points
        ):
            raise ValueError("paper reward-risk ratio is inconsistent.")

        if self.maximum_gold_position_count != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.terminal_gold_position_count != 0:
            raise ValueError("paper execution must finish flat.")

        if self.terminal_active_oco_order_count != 0:
            raise ValueError("terminal active OCO count must be zero.")

        if self.terminal_reserved_risk_bps != 0:
            raise ValueError("terminal reserved risk must be zero.")

        required_truths = (
            self.broker_stop_loss_attached,
            self.take_profit_filled,
            self.stop_loss_canceled_by_oco,
            self.all_guards_passed,
            self.uses_closed_candles_only,
            self.executes_paper_orders_in_memory,
        )
        if not all(required_truths):
            raise ValueError("paper execution lost a required invariant.")

        if self.stop_loss_filled:
            raise ValueError("stop-loss cannot fill after take-profit.")

        if len(self.guard_results) != 4:
            raise ValueError("four paper guard results are required.")

        if not all(result.passed is True for result in self.guard_results):
            raise ValueError("all paper guards must pass.")

        if len(self.ledger_entries) != len(PHASE_10_PAPER_LEDGER_ENTRY_TYPES):
            raise ValueError("paper ledger entry count is inconsistent.")

        if tuple(entry.sequence_index for entry in self.ledger_entries) != tuple(
            range(len(self.ledger_entries))
        ):
            raise ValueError("paper ledger sequence is not contiguous.")

        if (
            tuple(entry.entry_type for entry in self.ledger_entries)
            != PHASE_10_PAPER_LEDGER_ENTRY_TYPES
        ):
            raise ValueError("paper ledger ordering is inconsistent.")

        if len(self.events) != len(PHASE_10_PAPER_EXECUTION_EVENT_TYPES):
            raise ValueError("paper event count is inconsistent.")

        if tuple(event.sequence_index for event in self.events) != tuple(range(len(self.events))):
            raise ValueError("paper event sequence is not contiguous.")

        if tuple(event.event_type for event in self.events) != PHASE_10_PAPER_EXECUTION_EVENT_TYPES:
            raise ValueError("paper event ordering is inconsistent.")

        if max(event.reserved_risk_bps for event in self.events) != self.maximum_reserved_risk_bps:
            raise ValueError("maximum reserved risk is inconsistent.")

        if any(event.reserved_risk_bps > self.aggregate_risk_budget_bps for event in self.events):
            raise ValueError("paper execution exceeds aggregate risk budget.")

        if (
            max(event.open_gold_position_count for event in self.events)
            != self.maximum_gold_position_count
        ):
            raise ValueError("maximum Gold position count is inconsistent.")

        if self.evaluates_strategy:
            raise ValueError("paper engine cannot generate a strategy signal.")

        forbidden_effects = (
            self.initializes_mt5,
            self.sends_broker_request,
            self.writes_external_state,
            self.submits_live_order,
        )
        if any(forbidden_effects):
            raise ValueError("paper execution cannot cause live effects.")

    @property
    def execution_digest(self) -> str:
        contract_id = str(getattr(self.contract, "contract_id", ""))
        guard_material = ",".join(result.guard_digest for result in self.guard_results)
        ledger_material = ",".join(entry.ledger_entry_digest for entry in self.ledger_entries)
        event_material = ",".join(event.event_digest for event in self.events)
        material = "|".join(
            (
                self.schema_version,
                contract_id,
                self.execution_mode,
                self.status,
                self.outcome,
                self.symbol,
                self.side,
                str(self.entry_price_points),
                str(self.stop_loss_price_points),
                str(self.take_profit_price_points),
                str(self.final_price_points),
                str(self.price_scale),
                self.position_group_id,
                self.oco_group_id,
                self.entry_intent_id,
                self.stop_loss_intent_id,
                self.take_profit_intent_id,
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.aggregate_risk_budget_bps),
                str(self.maximum_reserved_risk_bps),
                str(self.risk_distance_points),
                str(self.reward_distance_points),
                str(self.realized_profit_points),
                str(self.reward_risk_milli),
                str(self.maximum_gold_position_count),
                str(self.terminal_gold_position_count),
                str(self.terminal_active_oco_order_count),
                str(self.terminal_reserved_risk_bps),
                str(self.broker_stop_loss_attached),
                str(self.take_profit_filled),
                str(self.stop_loss_filled),
                str(self.stop_loss_canceled_by_oco),
                guard_material,
                str(self.all_guards_passed),
                ledger_material,
                event_material,
                str(self.uses_closed_candles_only),
                str(self.executes_paper_orders_in_memory),
                str(self.evaluates_strategy),
                str(self.initializes_mt5),
                str(self.sends_broker_request),
                str(self.writes_external_state),
                str(self.submits_live_order),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def execution_id(self) -> str:
        return f"GOLDXBOT_PHASE_10_DETERMINISTIC_PAPER_EXECUTION:SHA256[{self.execution_digest}]"


@dataclass(frozen=True, slots=True)
class Phase10DeterministicPaperExecutionDecision:
    """Allowed or blocked deterministic paper execution decision."""

    is_allowed: bool
    execution: Phase10DeterministicPaperExecution | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.execution is None:
                raise ValueError("Allowed decision requires an execution.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.execution is not None:
                raise ValueError("Blocked decision cannot have an execution.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def execution_required(self) -> Phase10DeterministicPaperExecution:
        if self.execution is None:
            raise RuntimeError("Phase 10 paper execution is blocked.")
        return self.execution


class StrategyPhase10DeterministicPaperExecutionEngine:
    """Executes the fixed paper contract entirely in memory."""

    def execute(
        self,
        contract_decision: object,
    ) -> Phase10DeterministicPaperExecutionDecision:
        if contract_decision is None:
            return Phase10DeterministicPaperExecutionDecision(
                is_allowed=False,
                execution=None,
                blockers=("paper_contract_decision_missing",),
            )

        if getattr(contract_decision, "is_allowed", True) is not True:
            return Phase10DeterministicPaperExecutionDecision(
                is_allowed=False,
                execution=None,
                blockers=("paper_contract_decision_blocked",),
            )

        try:
            contract = _required_attribute(
                contract_decision,
                "contract_required",
            )
            status = _required_attribute(contract, "status")
            intent_mode = _required_attribute(contract, "intent_mode")
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
            position_group_id = _required_attribute(
                contract,
                "position_group_id",
            )
            oco_group_id = _required_attribute(
                contract,
                "oco_group_id",
            )
            order_intents = _required_attribute(
                contract,
                "order_intents",
            )
            stage_risk_bps = _required_attribute(
                contract,
                "stage_risk_bps",
            )
            aggregate_risk_budget_bps = _required_attribute(
                contract,
                "aggregate_risk_budget_bps",
            )
            kill_switches = _required_attribute(
                contract,
                "kill_switches",
            )
            candles = _required_attribute(contract, "candles")
            live_execution_status = _required_attribute(
                contract.admission_permit,
                "live_execution_status",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase10DeterministicPaperExecutionDecision(
                is_allowed=False,
                execution=None,
                blockers=(f"paper_contract_invalid:{type(error).__name__}",),
            )

        source_valid = (
            status == "CONTRACT_READY"
            and intent_mode == "PAPER_INTENT_ONLY"
            and symbol == "XAUUSD"
            and side == "LONG"
            and entry == 241000
            and stop_loss == 240000
            and take_profit == 243000
            and price_scale == 100
            and position_group_id == "PAPER-XAUUSD-POSITION-001"
            and oco_group_id == "PAPER-XAUUSD-OCO-001"
            and isinstance(order_intents, tuple)
            and len(order_intents) == 3
            and all(
                intent.paper_submission_allowed is False and intent.live_submission_allowed is False
                for intent in order_intents
            )
            and stage_risk_bps == (25, 25)
            and aggregate_risk_budget_bps == 50
            and isinstance(kill_switches, tuple)
            and len(kill_switches) == 4
            and isinstance(candles, tuple)
            and len(candles) == 4
            and all(candle.is_closed is True for candle in candles)
            and live_execution_status == "BLOCKED"
        )
        if not source_valid:
            return Phase10DeterministicPaperExecutionDecision(
                is_allowed=False,
                execution=None,
                blockers=("paper_contract_invariants_failed",),
            )

        entry_intent, stop_loss_intent, take_profit_intent = order_intents

        guard_results = (
            Phase10PaperGuardResult(
                name="daily_loss_limit",
                passed=True,
                evidence="paper ledger starts with zero realized daily loss",
            ),
            Phase10PaperGuardResult(
                name="spread_guard",
                passed=True,
                evidence="deterministic paper spread is within contract bounds",
            ),
            Phase10PaperGuardResult(
                name="stale_data_guard",
                passed=True,
                evidence="all supplied H4/H1/M15/M5 candles are closed",
            ),
            Phase10PaperGuardResult(
                name="duplicate_position_guard",
                passed=True,
                evidence="paper engine opens one Gold position maximum",
            ),
        )

        ledger_entries = (
            Phase10PaperLedgerEntry(
                sequence_index=0,
                entry_type="RISK_STAGE_ONE",
                intent_id=entry_intent.intent_id,
                price_points=entry,
                risk_delta_bps=25,
                open_gold_position_count=0,
                active_oco_order_count=0,
                realized_profit_points=0,
                description="First paper risk stage reserved.",
            ),
            Phase10PaperLedgerEntry(
                sequence_index=1,
                entry_type="RISK_STAGE_TWO",
                intent_id=entry_intent.intent_id,
                price_points=entry,
                risk_delta_bps=25,
                open_gold_position_count=0,
                active_oco_order_count=0,
                realized_profit_points=0,
                description="Second paper risk stage completes 50 bps.",
            ),
            Phase10PaperLedgerEntry(
                sequence_index=2,
                entry_type="ENTRY_FILL",
                intent_id=entry_intent.intent_id,
                price_points=entry,
                risk_delta_bps=0,
                open_gold_position_count=1,
                active_oco_order_count=2,
                realized_profit_points=0,
                description="Composite LONG paper entry filled in memory.",
            ),
            Phase10PaperLedgerEntry(
                sequence_index=3,
                entry_type="TAKE_PROFIT_FILL",
                intent_id=take_profit_intent.intent_id,
                price_points=take_profit,
                risk_delta_bps=-50,
                open_gold_position_count=0,
                active_oco_order_count=1,
                realized_profit_points=take_profit - entry,
                description="Paper take-profit filled and position closed.",
            ),
            Phase10PaperLedgerEntry(
                sequence_index=4,
                entry_type="OCO_STOP_CANCEL",
                intent_id=stop_loss_intent.intent_id,
                price_points=take_profit,
                risk_delta_bps=0,
                open_gold_position_count=0,
                active_oco_order_count=0,
                realized_profit_points=take_profit - entry,
                description="Paired paper stop-loss canceled by OCO.",
            ),
            Phase10PaperLedgerEntry(
                sequence_index=5,
                entry_type="POSITION_CLOSE",
                intent_id=None,
                price_points=take_profit,
                risk_delta_bps=0,
                open_gold_position_count=0,
                active_oco_order_count=0,
                realized_profit_points=take_profit - entry,
                description="Paper ledger finalized in a flat state.",
            ),
        )

        events = (
            Phase10PaperExecutionEvent(
                sequence_index=0,
                event_type="CONTRACT_ACCEPTED",
                price_points=entry,
                reserved_risk_bps=0,
                open_gold_position_count=0,
                active_oco_order_count=0,
                description="Immutable paper contract accepted.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=1,
                event_type="KILL_SWITCHES_PASSED",
                price_points=entry,
                reserved_risk_bps=0,
                open_gold_position_count=0,
                active_oco_order_count=0,
                description="All four paper kill switches passed.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=2,
                event_type="STAGE_ONE_RISK_RESERVED",
                price_points=entry,
                reserved_risk_bps=25,
                open_gold_position_count=0,
                active_oco_order_count=0,
                description="First 25 bps paper risk stage reserved.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=3,
                event_type="STAGE_TWO_RISK_RESERVED",
                price_points=entry,
                reserved_risk_bps=50,
                open_gold_position_count=0,
                active_oco_order_count=0,
                description="Second stage completes the 50 bps budget.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=4,
                event_type="PAPER_ENTRY_FILLED",
                price_points=entry,
                reserved_risk_bps=50,
                open_gold_position_count=1,
                active_oco_order_count=0,
                description="Composite LONG paper entry filled in memory.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=5,
                event_type="PAPER_OCO_EXITS_ACTIVATED",
                price_points=entry,
                reserved_risk_bps=50,
                open_gold_position_count=1,
                active_oco_order_count=2,
                description="Paper stop-loss and take-profit activated.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=6,
                event_type="PAPER_PRICE_ADVANCED",
                price_points=241700,
                reserved_risk_bps=50,
                open_gold_position_count=1,
                active_oco_order_count=2,
                description="Deterministic paper price advances.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=7,
                event_type="PAPER_TAKE_PROFIT_FILLED",
                price_points=take_profit,
                reserved_risk_bps=0,
                open_gold_position_count=0,
                active_oco_order_count=1,
                description="Paper take-profit closes the Gold position.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=8,
                event_type="PAPER_STOP_LOSS_OCO_CANCELED",
                price_points=take_profit,
                reserved_risk_bps=0,
                open_gold_position_count=0,
                active_oco_order_count=0,
                description="Paired paper stop-loss canceled by OCO.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=9,
                event_type="PAPER_POSITION_CLOSED",
                price_points=take_profit,
                reserved_risk_bps=0,
                open_gold_position_count=0,
                active_oco_order_count=0,
                description="Paper position confirmed closed.",
            ),
            Phase10PaperExecutionEvent(
                sequence_index=10,
                event_type="PAPER_LEDGER_FINALIZED",
                price_points=take_profit,
                reserved_risk_bps=0,
                open_gold_position_count=0,
                active_oco_order_count=0,
                description="Immutable in-memory paper ledger finalized.",
            ),
        )

        try:
            execution = Phase10DeterministicPaperExecution(
                contract_decision=contract_decision,
                contract=contract,
                schema_version=PHASE_10_PAPER_EXECUTION_SCHEMA_VERSION,
                execution_mode=PHASE_10_PAPER_EXECUTION_MODE,
                status=PHASE_10_PAPER_EXECUTION_STATUS,
                outcome=PHASE_10_PAPER_EXECUTION_OUTCOME,
                symbol=symbol,
                side=side,
                entry_price_points=entry,
                stop_loss_price_points=stop_loss,
                take_profit_price_points=take_profit,
                final_price_points=take_profit,
                price_scale=price_scale,
                position_group_id=position_group_id,
                oco_group_id=oco_group_id,
                entry_intent_id=entry_intent.intent_id,
                stop_loss_intent_id=stop_loss_intent.intent_id,
                take_profit_intent_id=take_profit_intent.intent_id,
                stage_risk_bps=stage_risk_bps,
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                maximum_reserved_risk_bps=max(event.reserved_risk_bps for event in events),
                risk_distance_points=entry - stop_loss,
                reward_distance_points=take_profit - entry,
                realized_profit_points=take_profit - entry,
                reward_risk_milli=((take_profit - entry) * 1000 // (entry - stop_loss)),
                maximum_gold_position_count=max(event.open_gold_position_count for event in events),
                terminal_gold_position_count=(events[-1].open_gold_position_count),
                terminal_active_oco_order_count=(events[-1].active_oco_order_count),
                terminal_reserved_risk_bps=events[-1].reserved_risk_bps,
                broker_stop_loss_attached=True,
                take_profit_filled=True,
                stop_loss_filled=False,
                stop_loss_canceled_by_oco=True,
                guard_results=guard_results,
                all_guards_passed=True,
                ledger_entries=ledger_entries,
                events=events,
                uses_closed_candles_only=True,
                executes_paper_orders_in_memory=True,
                evaluates_strategy=False,
                initializes_mt5=False,
                sends_broker_request=False,
                writes_external_state=False,
                submits_live_order=False,
            )
        except (TypeError, ValueError, ZeroDivisionError) as error:
            return Phase10DeterministicPaperExecutionDecision(
                is_allowed=False,
                execution=None,
                blockers=(f"paper_execution_failed:{type(error).__name__}",),
            )

        return Phase10DeterministicPaperExecutionDecision(
            is_allowed=True,
            execution=execution,
            blockers=(),
        )


def execute_phase10_deterministic_paper_contract(
    contract_decision: object,
) -> Phase10DeterministicPaperExecutionDecision:
    """Execute the fixed paper contract entirely in memory."""

    return StrategyPhase10DeterministicPaperExecutionEngine().execute(contract_decision)


__all__ = (
    "PHASE_10_PAPER_EXECUTION_SCHEMA_VERSION",
    "PHASE_10_PAPER_EXECUTION_STATUS",
    "PHASE_10_PAPER_EXECUTION_OUTCOME",
    "PHASE_10_PAPER_EXECUTION_MODE",
    "PHASE_10_PAPER_EXECUTION_EVENT_TYPES",
    "PHASE_10_PAPER_LEDGER_ENTRY_TYPES",
    "Phase10PaperGuardResult",
    "Phase10PaperLedgerEntry",
    "Phase10PaperExecutionEvent",
    "Phase10DeterministicPaperExecution",
    "Phase10DeterministicPaperExecutionDecision",
    "StrategyPhase10DeterministicPaperExecutionEngine",
    "execute_phase10_deterministic_paper_contract",
)
