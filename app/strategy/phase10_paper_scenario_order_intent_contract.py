"""Immutable Phase 10 paper scenario and order-intent contract.

This module consumes the Phase 10 PAPER_ONLY admission permit and creates
one deterministic XAUUSD paper-trading scenario plus immutable order
intents. The contract contains closed H4/H1/M15/M5 candles, one composite
LONG entry intent, and paired stop-loss/take-profit exit intents under OCO.
It does not execute a paper trade, initialize MT5, contact a broker, write
external state, or submit a live order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_10_PAPER_SCENARIO_SCHEMA_VERSION = "1.0"
PHASE_10_PAPER_SCENARIO_STATUS = "CONTRACT_READY"
PHASE_10_PAPER_SCENARIO_ID = "XAUUSD_PAPER_SCENARIO_001"
PHASE_10_PAPER_INTENT_MODE = "PAPER_INTENT_ONLY"
PHASE_10_PAPER_SYMBOL = "XAUUSD"
PHASE_10_PAPER_TIMEFRAMES = ("H4", "H1", "M15", "M5")
PHASE_10_PAPER_SIDE = "LONG"
PHASE_10_PAPER_PRICE_SCALE = 100
PHASE_10_PAPER_ENTRY_PRICE_POINTS = 241000
PHASE_10_PAPER_STOP_LOSS_PRICE_POINTS = 240000
PHASE_10_PAPER_TAKE_PROFIT_PRICE_POINTS = 243000
PHASE_10_PAPER_POSITION_GROUP_ID = "PAPER-XAUUSD-POSITION-001"
PHASE_10_PAPER_OCO_GROUP_ID = "PAPER-XAUUSD-OCO-001"
PHASE_10_PAPER_STAGE_RISK_BPS = (25, 25)
PHASE_10_PAPER_AGGREGATE_RISK_BPS = 50
PHASE_10_PAPER_KILL_SWITCHES = (
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
class Phase10PaperClosedCandle:
    """Immutable closed candle represented with integer price points."""

    timeframe: str
    close_time_utc: str
    open_price_points: int
    high_price_points: int
    low_price_points: int
    close_price_points: int
    tick_volume: int
    is_closed: bool

    def __post_init__(self) -> None:
        if self.timeframe not in PHASE_10_PAPER_TIMEFRAMES:
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
            raise ValueError("tick volume must be positive.")

        if self.is_closed is not True:
            raise ValueError("Phase 10 accepts closed candles only.")

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
class Phase10PaperOrderIntent:
    """Immutable non-executable paper order intent."""

    intent_id: str
    role: str
    side: str
    order_type: str
    price_points: int
    risk_bps: int
    position_group_id: str
    oco_group_id: str | None
    reduce_only: bool
    broker_stop_loss_required: bool
    paper_submission_allowed: bool
    live_submission_allowed: bool

    def __post_init__(self) -> None:
        allowed_roles = ("ENTRY", "STOP_LOSS", "TAKE_PROFIT")
        if self.role not in allowed_roles:
            raise ValueError("unsupported intent role.")

        if self.side not in ("BUY", "SELL"):
            raise ValueError("unsupported intent side.")

        if self.order_type not in ("PAPER_MARKET", "PAPER_STOP", "PAPER_LIMIT"):
            raise ValueError("unsupported paper order type.")

        if (
            isinstance(self.price_points, bool)
            or not isinstance(self.price_points, int)
            or self.price_points <= 0
        ):
            raise ValueError("intent price must be a positive integer.")

        if (
            isinstance(self.risk_bps, bool)
            or not isinstance(self.risk_bps, int)
            or self.risk_bps < 0
        ):
            raise ValueError("intent risk must be a non-negative integer.")

        if self.position_group_id != PHASE_10_PAPER_POSITION_GROUP_ID:
            raise ValueError("position group is inconsistent.")

        if self.paper_submission_allowed:
            raise ValueError("Step 10.2 cannot submit paper orders.")

        if self.live_submission_allowed:
            raise ValueError("live submission must remain blocked.")

        if self.role == "ENTRY":
            if self.side != "BUY":
                raise ValueError("LONG entry intent must be BUY.")
            if self.order_type != "PAPER_MARKET":
                raise ValueError("entry intent type is inconsistent.")
            if self.risk_bps != PHASE_10_PAPER_AGGREGATE_RISK_BPS:
                raise ValueError("entry risk must equal aggregate risk.")
            if self.oco_group_id is not None:
                raise ValueError("entry intent cannot belong to exit OCO.")
            if self.reduce_only:
                raise ValueError("entry intent cannot be reduce-only.")
            if self.broker_stop_loss_required is not True:
                raise ValueError("entry intent requires broker stop-loss.")

        if self.role in ("STOP_LOSS", "TAKE_PROFIT"):
            if self.side != "SELL":
                raise ValueError("LONG exit intents must be SELL.")
            if self.risk_bps != 0:
                raise ValueError("exit intents cannot reserve new risk.")
            if self.oco_group_id != PHASE_10_PAPER_OCO_GROUP_ID:
                raise ValueError("exit intents must share the OCO group.")
            if self.reduce_only is not True:
                raise ValueError("exit intents must be reduce-only.")

        if self.role == "STOP_LOSS":
            if self.order_type != "PAPER_STOP":
                raise ValueError("stop-loss intent type is inconsistent.")
            if self.broker_stop_loss_required is not True:
                raise ValueError("stop-loss intent must be broker-protected.")

        if self.role == "TAKE_PROFIT":
            if self.order_type != "PAPER_LIMIT":
                raise ValueError("take-profit intent type is inconsistent.")
            if self.broker_stop_loss_required:
                raise ValueError("take-profit intent cannot declare itself as a stop-loss.")

    @property
    def intent_digest(self) -> str:
        material = "|".join(
            (
                self.intent_id,
                self.role,
                self.side,
                self.order_type,
                str(self.price_points),
                str(self.risk_bps),
                self.position_group_id,
                str(self.oco_group_id),
                str(self.reduce_only),
                str(self.broker_stop_loss_required),
                str(self.paper_submission_allowed),
                str(self.live_submission_allowed),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase10PaperScenarioOrderIntentContract:
    """Immutable paper scenario and order-intent contract."""

    admission_decision: object
    admission_permit: object

    schema_version: str
    scenario_id: str
    status: str
    intent_mode: str

    symbol: str
    timeframes: tuple[str, ...]
    candles: tuple[Phase10PaperClosedCandle, ...]
    closed_candles_only: bool

    side: str
    entry_price_points: int
    stop_loss_price_points: int
    take_profit_price_points: int
    price_scale: int

    position_group_id: str
    oco_group_id: str
    order_intents: tuple[Phase10PaperOrderIntent, ...]

    max_gold_positions: int
    stage_risk_bps: tuple[int, ...]
    aggregate_risk_budget_bps: int

    oco_required: bool
    broker_stop_loss_required: bool
    kill_switches: tuple[str, ...]
    martingale_prohibited: bool
    grid_prohibited: bool
    no_stop_loss_prohibited: bool

    permits_paper_planning: bool
    permits_paper_execution: bool
    permits_strategy_evaluation: bool
    permits_mt5_initialization: bool
    permits_broker_requests: bool
    permits_external_writes: bool
    permits_live_order_submission: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_10_PAPER_SCENARIO_SCHEMA_VERSION:
            raise ValueError("scenario schema version is inconsistent.")

        if self.scenario_id != PHASE_10_PAPER_SCENARIO_ID:
            raise ValueError("scenario id is inconsistent.")

        if self.status != PHASE_10_PAPER_SCENARIO_STATUS:
            raise ValueError("scenario status must be CONTRACT_READY.")

        if self.intent_mode != PHASE_10_PAPER_INTENT_MODE:
            raise ValueError("intent mode must be PAPER_INTENT_ONLY.")

        if self.symbol != PHASE_10_PAPER_SYMBOL:
            raise ValueError("scenario must be XAUUSD only.")

        if self.timeframes != PHASE_10_PAPER_TIMEFRAMES:
            raise ValueError("scenario timeframes are inconsistent.")

        if len(self.candles) != len(self.timeframes):
            raise ValueError("one closed candle is required per timeframe.")

        if tuple(candle.timeframe for candle in self.candles) != self.timeframes:
            raise ValueError("candles are not ordered by timeframe.")

        if any(candle.is_closed is not True for candle in self.candles):
            raise ValueError("scenario contains an open candle.")

        if self.closed_candles_only is not True:
            raise ValueError("scenario must be closed-candle only.")

        if self.side != PHASE_10_PAPER_SIDE:
            raise ValueError("scenario side is inconsistent.")

        if self.entry_price_points != PHASE_10_PAPER_ENTRY_PRICE_POINTS:
            raise ValueError("entry price is inconsistent.")

        if self.stop_loss_price_points != PHASE_10_PAPER_STOP_LOSS_PRICE_POINTS:
            raise ValueError("stop-loss price is inconsistent.")

        if self.take_profit_price_points != PHASE_10_PAPER_TAKE_PROFIT_PRICE_POINTS:
            raise ValueError("take-profit price is inconsistent.")

        if not (
            self.stop_loss_price_points < self.entry_price_points < self.take_profit_price_points
        ):
            raise ValueError("LONG scenario price ordering is invalid.")

        if self.price_scale != PHASE_10_PAPER_PRICE_SCALE:
            raise ValueError("price scale is inconsistent.")

        if self.position_group_id != PHASE_10_PAPER_POSITION_GROUP_ID:
            raise ValueError("position group id is inconsistent.")

        if self.oco_group_id != PHASE_10_PAPER_OCO_GROUP_ID:
            raise ValueError("OCO group id is inconsistent.")

        if len(self.order_intents) != 3:
            raise ValueError("exactly three paper order intents are required.")

        roles = tuple(intent.role for intent in self.order_intents)
        if roles != ("ENTRY", "STOP_LOSS", "TAKE_PROFIT"):
            raise ValueError("paper order intent ordering is inconsistent.")

        if tuple(intent.price_points for intent in self.order_intents) != (
            self.entry_price_points,
            self.stop_loss_price_points,
            self.take_profit_price_points,
        ):
            raise ValueError("order-intent prices are inconsistent.")

        if any(
            intent.paper_submission_allowed or intent.live_submission_allowed
            for intent in self.order_intents
        ):
            raise ValueError("Step 10.2 intents must be non-executable.")

        if self.max_gold_positions != 1:
            raise ValueError("only one Gold position is allowed.")

        if self.stage_risk_bps != PHASE_10_PAPER_STAGE_RISK_BPS:
            raise ValueError("stage risk allocation is inconsistent.")

        if self.aggregate_risk_budget_bps != PHASE_10_PAPER_AGGREGATE_RISK_BPS:
            raise ValueError("aggregate risk budget is inconsistent.")

        if sum(self.stage_risk_bps) != self.aggregate_risk_budget_bps:
            raise ValueError("stage risk must equal aggregate risk budget.")

        required_truths = (
            self.oco_required,
            self.broker_stop_loss_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.permits_paper_planning,
        )
        if not all(required_truths):
            raise ValueError("scenario lost a required safety invariant.")

        if self.kill_switches != PHASE_10_PAPER_KILL_SWITCHES:
            raise ValueError("kill-switch contract is inconsistent.")

        forbidden_capabilities = (
            self.permits_paper_execution,
            self.permits_strategy_evaluation,
            self.permits_mt5_initialization,
            self.permits_broker_requests,
            self.permits_external_writes,
            self.permits_live_order_submission,
        )
        if any(forbidden_capabilities):
            raise ValueError("scenario cannot enable execution effects.")

    @property
    def contract_digest(self) -> str:
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        candle_material = ",".join(candle.candle_digest for candle in self.candles)
        intent_material = ",".join(intent.intent_digest for intent in self.order_intents)
        material = "|".join(
            (
                self.schema_version,
                permit_id,
                self.scenario_id,
                self.status,
                self.intent_mode,
                self.symbol,
                ",".join(self.timeframes),
                candle_material,
                str(self.closed_candles_only),
                self.side,
                str(self.entry_price_points),
                str(self.stop_loss_price_points),
                str(self.take_profit_price_points),
                str(self.price_scale),
                self.position_group_id,
                self.oco_group_id,
                intent_material,
                str(self.max_gold_positions),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.aggregate_risk_budget_bps),
                str(self.oco_required),
                str(self.broker_stop_loss_required),
                ",".join(self.kill_switches),
                str(self.martingale_prohibited),
                str(self.grid_prohibited),
                str(self.no_stop_loss_prohibited),
                str(self.permits_paper_planning),
                str(self.permits_paper_execution),
                str(self.permits_strategy_evaluation),
                str(self.permits_mt5_initialization),
                str(self.permits_broker_requests),
                str(self.permits_external_writes),
                str(self.permits_live_order_submission),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def contract_id(self) -> str:
        return f"GOLDXBOT_PHASE_10_PAPER_SCENARIO_INTENT:SHA256[{self.contract_digest}]"


@dataclass(frozen=True, slots=True)
class Phase10PaperScenarioOrderIntentDecision:
    """Allowed or blocked paper scenario and intent decision."""

    is_allowed: bool
    contract: Phase10PaperScenarioOrderIntentContract | None
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
    def contract_required(self) -> Phase10PaperScenarioOrderIntentContract:
        if self.contract is None:
            raise RuntimeError("Phase 10 paper scenario and order intent is blocked.")
        return self.contract


class StrategyPhase10PaperScenarioOrderIntentFactory:
    """Creates the deterministic non-executable paper contract."""

    def create(
        self,
        admission_decision: object,
    ) -> Phase10PaperScenarioOrderIntentDecision:
        if admission_decision is None:
            return Phase10PaperScenarioOrderIntentDecision(
                is_allowed=False,
                contract=None,
                blockers=("paper_admission_decision_missing",),
            )

        if getattr(admission_decision, "is_allowed", True) is not True:
            return Phase10PaperScenarioOrderIntentDecision(
                is_allowed=False,
                contract=None,
                blockers=("paper_admission_decision_blocked",),
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
            max_gold_positions = _required_attribute(
                permit,
                "max_gold_positions",
            )
            aggregate_risk_budget_bps = _required_attribute(
                permit,
                "aggregate_risk_budget_bps",
            )
            stage_risk_bps = _required_attribute(
                permit,
                "stage_risk_bps",
            )
            phase10_foundation_ready = _required_attribute(
                permit,
                "phase10_foundation_ready",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase10PaperScenarioOrderIntentDecision(
                is_allowed=False,
                contract=None,
                blockers=(f"paper_admission_invalid:{type(error).__name__}",),
            )

        source_valid = (
            admission_mode == "PAPER_ONLY"
            and admission_status == "ADMITTED"
            and live_execution_status == "BLOCKED"
            and allowed_symbol == PHASE_10_PAPER_SYMBOL
            and allowed_timeframes == PHASE_10_PAPER_TIMEFRAMES
            and closed_candles_only is True
            and max_gold_positions == 1
            and aggregate_risk_budget_bps == 50
            and stage_risk_bps == (25, 25)
            and phase10_foundation_ready is True
        )
        if not source_valid:
            return Phase10PaperScenarioOrderIntentDecision(
                is_allowed=False,
                contract=None,
                blockers=("paper_admission_contract_invalid",),
            )

        candles = (
            Phase10PaperClosedCandle(
                timeframe="H4",
                close_time_utc="2026-01-06T12:00:00Z",
                open_price_points=239900,
                high_price_points=241350,
                low_price_points=239500,
                close_price_points=241000,
                tick_volume=19120,
                is_closed=True,
            ),
            Phase10PaperClosedCandle(
                timeframe="H1",
                close_time_utc="2026-01-06T12:00:00Z",
                open_price_points=240350,
                high_price_points=241200,
                low_price_points=240150,
                close_price_points=241000,
                tick_volume=7620,
                is_closed=True,
            ),
            Phase10PaperClosedCandle(
                timeframe="M15",
                close_time_utc="2026-01-06T12:00:00Z",
                open_price_points=240700,
                high_price_points=241100,
                low_price_points=240550,
                close_price_points=241000,
                tick_volume=2780,
                is_closed=True,
            ),
            Phase10PaperClosedCandle(
                timeframe="M5",
                close_time_utc="2026-01-06T12:00:00Z",
                open_price_points=240820,
                high_price_points=241050,
                low_price_points=240760,
                close_price_points=241000,
                tick_volume=1040,
                is_closed=True,
            ),
        )

        intents = (
            Phase10PaperOrderIntent(
                intent_id="PAPER-ENTRY-001",
                role="ENTRY",
                side="BUY",
                order_type="PAPER_MARKET",
                price_points=PHASE_10_PAPER_ENTRY_PRICE_POINTS,
                risk_bps=PHASE_10_PAPER_AGGREGATE_RISK_BPS,
                position_group_id=PHASE_10_PAPER_POSITION_GROUP_ID,
                oco_group_id=None,
                reduce_only=False,
                broker_stop_loss_required=True,
                paper_submission_allowed=False,
                live_submission_allowed=False,
            ),
            Phase10PaperOrderIntent(
                intent_id="PAPER-SL-001",
                role="STOP_LOSS",
                side="SELL",
                order_type="PAPER_STOP",
                price_points=PHASE_10_PAPER_STOP_LOSS_PRICE_POINTS,
                risk_bps=0,
                position_group_id=PHASE_10_PAPER_POSITION_GROUP_ID,
                oco_group_id=PHASE_10_PAPER_OCO_GROUP_ID,
                reduce_only=True,
                broker_stop_loss_required=True,
                paper_submission_allowed=False,
                live_submission_allowed=False,
            ),
            Phase10PaperOrderIntent(
                intent_id="PAPER-TP-001",
                role="TAKE_PROFIT",
                side="SELL",
                order_type="PAPER_LIMIT",
                price_points=PHASE_10_PAPER_TAKE_PROFIT_PRICE_POINTS,
                risk_bps=0,
                position_group_id=PHASE_10_PAPER_POSITION_GROUP_ID,
                oco_group_id=PHASE_10_PAPER_OCO_GROUP_ID,
                reduce_only=True,
                broker_stop_loss_required=False,
                paper_submission_allowed=False,
                live_submission_allowed=False,
            ),
        )

        try:
            contract = Phase10PaperScenarioOrderIntentContract(
                admission_decision=admission_decision,
                admission_permit=permit,
                schema_version=PHASE_10_PAPER_SCENARIO_SCHEMA_VERSION,
                scenario_id=PHASE_10_PAPER_SCENARIO_ID,
                status=PHASE_10_PAPER_SCENARIO_STATUS,
                intent_mode=PHASE_10_PAPER_INTENT_MODE,
                symbol=PHASE_10_PAPER_SYMBOL,
                timeframes=PHASE_10_PAPER_TIMEFRAMES,
                candles=candles,
                closed_candles_only=True,
                side=PHASE_10_PAPER_SIDE,
                entry_price_points=PHASE_10_PAPER_ENTRY_PRICE_POINTS,
                stop_loss_price_points=(PHASE_10_PAPER_STOP_LOSS_PRICE_POINTS),
                take_profit_price_points=(PHASE_10_PAPER_TAKE_PROFIT_PRICE_POINTS),
                price_scale=PHASE_10_PAPER_PRICE_SCALE,
                position_group_id=PHASE_10_PAPER_POSITION_GROUP_ID,
                oco_group_id=PHASE_10_PAPER_OCO_GROUP_ID,
                order_intents=intents,
                max_gold_positions=max_gold_positions,
                stage_risk_bps=stage_risk_bps,
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                oco_required=True,
                broker_stop_loss_required=True,
                kill_switches=PHASE_10_PAPER_KILL_SWITCHES,
                martingale_prohibited=True,
                grid_prohibited=True,
                no_stop_loss_prohibited=True,
                permits_paper_planning=True,
                permits_paper_execution=False,
                permits_strategy_evaluation=False,
                permits_mt5_initialization=False,
                permits_broker_requests=False,
                permits_external_writes=False,
                permits_live_order_submission=False,
            )
        except ValueError as error:
            return Phase10PaperScenarioOrderIntentDecision(
                is_allowed=False,
                contract=None,
                blockers=(f"paper_scenario_intent_invalid:{type(error).__name__}",),
            )

        return Phase10PaperScenarioOrderIntentDecision(
            is_allowed=True,
            contract=contract,
            blockers=(),
        )


def create_phase10_paper_scenario_order_intent(
    admission_decision: object,
) -> Phase10PaperScenarioOrderIntentDecision:
    """Create the immutable Phase 10 paper scenario and intents."""

    return StrategyPhase10PaperScenarioOrderIntentFactory().create(admission_decision)


__all__ = (
    "PHASE_10_PAPER_SCENARIO_SCHEMA_VERSION",
    "PHASE_10_PAPER_SCENARIO_STATUS",
    "PHASE_10_PAPER_SCENARIO_ID",
    "PHASE_10_PAPER_INTENT_MODE",
    "PHASE_10_PAPER_SYMBOL",
    "PHASE_10_PAPER_TIMEFRAMES",
    "PHASE_10_PAPER_SIDE",
    "PHASE_10_PAPER_PRICE_SCALE",
    "PHASE_10_PAPER_ENTRY_PRICE_POINTS",
    "PHASE_10_PAPER_STOP_LOSS_PRICE_POINTS",
    "PHASE_10_PAPER_TAKE_PROFIT_PRICE_POINTS",
    "PHASE_10_PAPER_POSITION_GROUP_ID",
    "PHASE_10_PAPER_OCO_GROUP_ID",
    "PHASE_10_PAPER_STAGE_RISK_BPS",
    "PHASE_10_PAPER_AGGREGATE_RISK_BPS",
    "PHASE_10_PAPER_KILL_SWITCHES",
    "Phase10PaperClosedCandle",
    "Phase10PaperOrderIntent",
    "Phase10PaperScenarioOrderIntentContract",
    "Phase10PaperScenarioOrderIntentDecision",
    "StrategyPhase10PaperScenarioOrderIntentFactory",
    "create_phase10_paper_scenario_order_intent",
)
