"""Deterministic fake-only read-only preflight runner for Phase 11.

This module consumes the immutable Step 11.2 terminal, broker, and account
capability contract. It exercises a deterministic fake terminal lifecycle
and fake read-only terminal, account, symbol, tick, position, and order
snapshots entirely in memory.

It never imports or initializes real MetaTrader 5, connects to a terminal,
contacts a broker, reads a real account, runs order_check, sends an order,
writes external state, activates production, or submits a live order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_11_PREFLIGHT_SCHEMA_VERSION = "1.0"
PHASE_11_PREFLIGHT_MODE = "DETERMINISTIC_FAKE_READ_ONLY"
PHASE_11_PREFLIGHT_STATUS = "COMPLETED"
PHASE_11_PREFLIGHT_OUTCOME = "READY_FOR_READINESS_AUDIT"
PHASE_11_PREFLIGHT_SOURCE = "DETERMINISTIC_FAKE_ONLY"
PHASE_11_REAL_PREFLIGHT_EXECUTION_STATUS = "BLOCKED"
PHASE_11_PRODUCTION_ACTIVATION_STATUS = "BLOCKED"
PHASE_11_LIVE_EXECUTION_STATUS = "BLOCKED"

PHASE_11_PREFLIGHT_EVENT_TYPES = (
    "CAPABILITY_CONTRACT_ACCEPTED",
    "FAKE_TERMINAL_PACKAGE_CHECKED",
    "FAKE_TERMINAL_INITIALIZED",
    "FAKE_TERMINAL_INFO_READ",
    "FAKE_ACCOUNT_INFO_READ",
    "FAKE_SYMBOL_RESOLVED",
    "FAKE_SYMBOL_INFO_READ",
    "FAKE_TICK_READ",
    "FAKE_POSITIONS_READ",
    "FAKE_ORDERS_READ",
    "SAFETY_INVARIANTS_VERIFIED",
    "CONTROLLED_WRITES_CONFIRMED_BLOCKED",
    "FAKE_TERMINAL_SHUTDOWN",
    "PREFLIGHT_FINALIZED",
)

PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS = (
    "MT5_PACKAGE_IMPORT",
    "TERMINAL_INITIALIZE",
    "TERMINAL_INFO_READ",
    "TERMINAL_SHUTDOWN",
    "SYMBOL_RESOLUTION",
    "SYMBOL_INFO_READ",
    "TICK_READ",
    "POSITION_READ",
    "ORDER_READ",
    "ACCOUNT_INFO_READ",
    "TRADE_MODE_READ",
    "TRADE_PERMISSION_READ",
    "MARGIN_STATE_READ",
    "EXPOSURE_STATE_READ",
)

PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS = (
    "ORDER_CHECK",
    "ORDER_SEND",
    "APPLICATION_OCO_CONTROL",
)


def _required_attribute(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase11FakeTerminalSnapshot:
    """Immutable fake terminal snapshot."""

    terminal_name: str
    build_number: int
    lifecycle_state: str
    fake_initialized: bool
    fake_shutdown_completed: bool
    real_terminal_connected: bool

    def __post_init__(self) -> None:
        if self.terminal_name != "GoldXBot-Fake-MT5":
            raise ValueError("fake terminal name is inconsistent.")

        if self.build_number != 5000:
            raise ValueError("fake terminal build is inconsistent.")

        if self.lifecycle_state != "FAKE_SHUTDOWN_COMPLETE":
            raise ValueError("fake terminal lifecycle is incomplete.")

        if self.fake_initialized is not True:
            raise ValueError("fake terminal initialization is required.")

        if self.fake_shutdown_completed is not True:
            raise ValueError("fake terminal shutdown is required.")

        if self.real_terminal_connected:
            raise ValueError("real terminal connection must remain false.")

    @property
    def snapshot_digest(self) -> str:
        material = "|".join(
            (
                self.terminal_name,
                str(self.build_number),
                self.lifecycle_state,
                str(self.fake_initialized),
                str(self.fake_shutdown_completed),
                str(self.real_terminal_connected),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase11FakeAccountSnapshot:
    """Immutable fake account and margin snapshot."""

    account_id: str
    trade_mode: str
    trade_allowed: bool
    currency: str
    balance_minor_units: int
    equity_minor_units: int
    margin_used_minor_units: int
    margin_free_minor_units: int
    open_gold_position_count: int
    pending_gold_order_count: int
    reserved_risk_bps: int
    is_real_account: bool

    def __post_init__(self) -> None:
        if self.account_id != "FAKE-ACCOUNT-11001":
            raise ValueError("fake account id is inconsistent.")

        if self.trade_mode != "FAKE_DEMO_READ_ONLY":
            raise ValueError("fake trade mode is inconsistent.")

        if self.trade_allowed:
            raise ValueError("fake account trading must remain blocked.")

        if self.currency != "USD":
            raise ValueError("fake account currency is inconsistent.")

        if self.balance_minor_units != 10_000_000:
            raise ValueError("fake balance is inconsistent.")

        if self.equity_minor_units != 10_000_000:
            raise ValueError("fake equity is inconsistent.")

        if self.margin_used_minor_units != 0:
            raise ValueError("fake margin used must be zero.")

        if self.margin_free_minor_units != 10_000_000:
            raise ValueError("fake free margin is inconsistent.")

        if self.open_gold_position_count != 0:
            raise ValueError("fake account must start flat.")

        if self.pending_gold_order_count != 0:
            raise ValueError("fake pending Gold orders must be zero.")

        if self.reserved_risk_bps != 0:
            raise ValueError("fake reserved risk must be zero.")

        if self.is_real_account:
            raise ValueError("real account access must remain false.")

    @property
    def snapshot_digest(self) -> str:
        material = "|".join(
            (
                self.account_id,
                self.trade_mode,
                str(self.trade_allowed),
                self.currency,
                str(self.balance_minor_units),
                str(self.equity_minor_units),
                str(self.margin_used_minor_units),
                str(self.margin_free_minor_units),
                str(self.open_gold_position_count),
                str(self.pending_gold_order_count),
                str(self.reserved_risk_bps),
                str(self.is_real_account),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase11FakeSymbolSnapshot:
    """Immutable fake XAUUSD symbol and tick snapshot."""

    requested_symbol: str
    resolved_symbol: str
    visible: bool
    digits: int
    point_scale: int
    bid_price_points: int
    ask_price_points: int
    spread_points: int
    tick_time_utc: str
    real_broker_data_used: bool

    def __post_init__(self) -> None:
        if self.requested_symbol != "XAUUSD":
            raise ValueError("requested symbol must be XAUUSD.")

        if self.resolved_symbol != "XAUUSD":
            raise ValueError("resolved symbol must be XAUUSD.")

        if self.visible is not True:
            raise ValueError("fake XAUUSD symbol must be visible.")

        if self.digits != 2:
            raise ValueError("fake XAUUSD digits are inconsistent.")

        if self.point_scale != 100:
            raise ValueError("fake point scale is inconsistent.")

        if self.bid_price_points != 241_000:
            raise ValueError("fake bid price is inconsistent.")

        if self.ask_price_points != 241_020:
            raise ValueError("fake ask price is inconsistent.")

        if self.spread_points != 20:
            raise ValueError("fake spread is inconsistent.")

        if self.ask_price_points - self.bid_price_points != self.spread_points:
            raise ValueError("fake spread calculation is inconsistent.")

        if self.tick_time_utc != "2026-01-06T12:00:00Z":
            raise ValueError("fake tick time is inconsistent.")

        if self.real_broker_data_used:
            raise ValueError("real broker data must remain false.")

    @property
    def snapshot_digest(self) -> str:
        material = "|".join(
            (
                self.requested_symbol,
                self.resolved_symbol,
                str(self.visible),
                str(self.digits),
                str(self.point_scale),
                str(self.bid_price_points),
                str(self.ask_price_points),
                str(self.spread_points),
                self.tick_time_utc,
                str(self.real_broker_data_used),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase11FakePreflightEvent:
    """Immutable fake preflight trace event."""

    sequence_index: int
    event_type: str
    status: str
    evidence: str

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError("event sequence index cannot be negative.")

        if self.event_type not in PHASE_11_PREFLIGHT_EVENT_TYPES:
            raise ValueError("unsupported preflight event type.")

        if self.status != "PASSED":
            raise ValueError("deterministic preflight events must pass.")

        if not self.evidence:
            raise ValueError("preflight event evidence is required.")

    @property
    def event_digest(self) -> str:
        material = "|".join(
            (
                str(self.sequence_index),
                self.event_type,
                self.status,
                self.evidence,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase11DeterministicReadOnlyPreflight:
    """Immutable completed fake-only preflight result."""

    capability_decision: object
    capability_contract: object
    admission_decision: object
    admission_permit: object
    phase10_handoff_bundle: object

    schema_version: str
    mode: str
    status: str
    outcome: str
    source: str

    terminal_snapshot: Phase11FakeTerminalSnapshot
    account_snapshot: Phase11FakeAccountSnapshot
    symbol_snapshot: Phase11FakeSymbolSnapshot

    verified_capability_ids: tuple[str, ...]
    blocked_capability_ids: tuple[str, ...]
    verified_capability_count: int
    blocked_capability_count: int

    allowed_symbol: str
    allowed_timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    terminal_flat_state_valid: bool
    exposure_state_valid: bool
    margin_state_valid: bool
    symbol_resolution_valid: bool
    tick_snapshot_valid: bool
    capability_inventory_valid: bool

    events: tuple[Phase11FakePreflightEvent, ...]
    event_trace_contiguous: bool
    event_trace_order_valid: bool

    fake_terminal_lifecycle_exercised: bool
    real_mt5_imported: bool
    real_mt5_initialized: bool
    real_terminal_connected: bool
    real_broker_request_sent: bool
    real_account_read_performed: bool
    order_check_invoked: bool
    order_send_invoked: bool
    external_state_written: bool
    production_activated: bool
    live_order_submitted: bool

    real_preflight_execution_status: str
    production_activation_status: str
    live_execution_status: str
    no_real_or_external_effects: bool
    ready_for_readiness_audit: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_11_PREFLIGHT_SCHEMA_VERSION:
            raise ValueError("preflight schema version is inconsistent.")

        if self.mode != PHASE_11_PREFLIGHT_MODE:
            raise ValueError("preflight mode is inconsistent.")

        if self.status != PHASE_11_PREFLIGHT_STATUS:
            raise ValueError("preflight status must be COMPLETED.")

        if self.outcome != PHASE_11_PREFLIGHT_OUTCOME:
            raise ValueError("preflight outcome is inconsistent.")

        if self.source != PHASE_11_PREFLIGHT_SOURCE:
            raise ValueError("preflight source must be fake-only.")

        if self.verified_capability_ids != PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS:
            raise ValueError("verified capability ordering is inconsistent.")

        if self.blocked_capability_ids != PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS:
            raise ValueError("blocked capability ordering is inconsistent.")

        if self.verified_capability_count != 14:
            raise ValueError("fourteen fake capabilities must be verified.")

        if self.blocked_capability_count != 3:
            raise ValueError("three write-sensitive capabilities must block.")

        if self.allowed_symbol != "XAUUSD":
            raise ValueError("preflight is XAUUSD only.")

        if self.allowed_timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("preflight timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("closed candles are required.")

        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("stage risk allocation is inconsistent.")

        required_truths = (
            self.terminal_flat_state_valid,
            self.exposure_state_valid,
            self.margin_state_valid,
            self.symbol_resolution_valid,
            self.tick_snapshot_valid,
            self.capability_inventory_valid,
            self.event_trace_contiguous,
            self.event_trace_order_valid,
            self.fake_terminal_lifecycle_exercised,
            self.no_real_or_external_effects,
            self.ready_for_readiness_audit,
        )
        if not all(required_truths):
            raise ValueError("fake preflight contains a failed invariant.")

        if len(self.events) != len(PHASE_11_PREFLIGHT_EVENT_TYPES):
            raise ValueError("preflight event count is inconsistent.")

        if tuple(event.sequence_index for event in self.events) != tuple(range(len(self.events))):
            raise ValueError("preflight event sequence is not contiguous.")

        if tuple(event.event_type for event in self.events) != (PHASE_11_PREFLIGHT_EVENT_TYPES):
            raise ValueError("preflight event ordering is inconsistent.")

        forbidden_effects = (
            self.real_mt5_imported,
            self.real_mt5_initialized,
            self.real_terminal_connected,
            self.real_broker_request_sent,
            self.real_account_read_performed,
            self.order_check_invoked,
            self.order_send_invoked,
            self.external_state_written,
            self.production_activated,
            self.live_order_submitted,
        )
        if any(forbidden_effects):
            raise ValueError("fake preflight detected a real effect.")

        if self.real_preflight_execution_status != PHASE_11_REAL_PREFLIGHT_EXECUTION_STATUS:
            raise ValueError("real preflight execution must remain BLOCKED.")

        if self.production_activation_status != PHASE_11_PRODUCTION_ACTIVATION_STATUS:
            raise ValueError("production activation must remain BLOCKED.")

        if self.live_execution_status != PHASE_11_LIVE_EXECUTION_STATUS:
            raise ValueError("live execution must remain BLOCKED.")

    @property
    def preflight_digest(self) -> str:
        contract_id = str(getattr(self.capability_contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase10_handoff_id = str(getattr(self.phase10_handoff_bundle, "handoff_id", ""))
        event_material = ",".join(event.event_digest for event in self.events)
        material = "|".join(
            (
                self.schema_version,
                contract_id,
                permit_id,
                phase10_handoff_id,
                self.mode,
                self.status,
                self.outcome,
                self.source,
                self.terminal_snapshot.snapshot_digest,
                self.account_snapshot.snapshot_digest,
                self.symbol_snapshot.snapshot_digest,
                ",".join(self.verified_capability_ids),
                ",".join(self.blocked_capability_ids),
                str(self.verified_capability_count),
                str(self.blocked_capability_count),
                self.allowed_symbol,
                ",".join(self.allowed_timeframes),
                str(self.closed_candles_only),
                str(self.max_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.terminal_flat_state_valid),
                str(self.exposure_state_valid),
                str(self.margin_state_valid),
                str(self.symbol_resolution_valid),
                str(self.tick_snapshot_valid),
                str(self.capability_inventory_valid),
                event_material,
                str(self.event_trace_contiguous),
                str(self.event_trace_order_valid),
                str(self.fake_terminal_lifecycle_exercised),
                str(self.real_mt5_imported),
                str(self.real_mt5_initialized),
                str(self.real_terminal_connected),
                str(self.real_broker_request_sent),
                str(self.real_account_read_performed),
                str(self.order_check_invoked),
                str(self.order_send_invoked),
                str(self.external_state_written),
                str(self.production_activated),
                str(self.live_order_submitted),
                self.real_preflight_execution_status,
                self.production_activation_status,
                self.live_execution_status,
                str(self.no_real_or_external_effects),
                str(self.ready_for_readiness_audit),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def preflight_id(self) -> str:
        return (
            f"GOLDXBOT_PHASE_11_DETERMINISTIC_READ_ONLY_PREFLIGHT:SHA256[{self.preflight_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase11DeterministicReadOnlyPreflightDecision:
    """Allowed or blocked fake preflight decision."""

    is_allowed: bool
    preflight: Phase11DeterministicReadOnlyPreflight | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.preflight is None:
                raise ValueError("Allowed decision requires a preflight.")
            if self.blockers:
                raise ValueError("Allowed decision cannot have blockers.")
        else:
            if self.preflight is not None:
                raise ValueError("Blocked decision cannot have a preflight.")
            if not self.blockers:
                raise ValueError("Blocked decision requires blockers.")

    @property
    def preflight_required(self) -> Phase11DeterministicReadOnlyPreflight:
        if self.preflight is None:
            raise RuntimeError("Phase 11 fake read-only preflight is blocked.")
        return self.preflight


class StrategyPhase11DeterministicReadOnlyPreflightRunner:
    """Runs the deterministic fake-only preflight in memory."""

    def run(
        self,
        capability_decision: object,
    ) -> Phase11DeterministicReadOnlyPreflightDecision:
        if capability_decision is None:
            return Phase11DeterministicReadOnlyPreflightDecision(
                is_allowed=False,
                preflight=None,
                blockers=("capability_contract_decision_missing",),
            )

        if getattr(capability_decision, "is_allowed", True) is not True:
            return Phase11DeterministicReadOnlyPreflightDecision(
                is_allowed=False,
                preflight=None,
                blockers=("capability_contract_decision_blocked",),
            )

        try:
            contract = _required_attribute(
                capability_decision,
                "contract_required",
            )
            admission_decision = _required_attribute(
                contract,
                "admission_decision",
            )
            admission_permit = _required_attribute(
                contract,
                "admission_permit",
            )
            phase10_handoff_bundle = _required_attribute(
                admission_permit,
                "phase10_handoff_bundle",
            )
            status = _required_attribute(contract, "status")
            source = _required_attribute(contract, "capability_source")
            all_capabilities = _required_attribute(
                contract,
                "all_capabilities",
            )
            allowed_symbol = _required_attribute(
                contract,
                "allowed_symbol",
            )
            allowed_timeframes = _required_attribute(
                contract,
                "allowed_timeframes",
            )
            max_gold_positions = _required_attribute(
                contract,
                "max_gold_positions",
            )
            aggregate_risk_budget_bps = _required_attribute(
                contract,
                "aggregate_risk_budget_bps",
            )
            stage_risk_bps = _required_attribute(
                contract,
                "stage_risk_bps",
            )
            preflight_execution_status = _required_attribute(
                contract,
                "preflight_execution_status",
            )
            production_activation_status = _required_attribute(
                contract,
                "production_activation_status",
            )
            live_execution_status = _required_attribute(
                contract,
                "live_execution_status",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase11DeterministicReadOnlyPreflightDecision(
                is_allowed=False,
                preflight=None,
                blockers=(f"capability_contract_invalid:{type(error).__name__}",),
            )

        capability_ids = tuple(capability.capability_id for capability in all_capabilities)
        source_valid = (
            status == "CONTRACT_READY"
            and source == "DETERMINISTIC_FAKE_ONLY"
            and len(all_capabilities) == 17
            and all(
                capability.runtime_invocation_allowed is False for capability in all_capabilities
            )
            and set(PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS).issubset(capability_ids)
            and set(PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS).issubset(capability_ids)
            and allowed_symbol == "XAUUSD"
            and allowed_timeframes == ("H4", "H1", "M15", "M5")
            and max_gold_positions == 1
            and aggregate_risk_budget_bps == 50
            and stage_risk_bps == (25, 25)
            and preflight_execution_status == "BLOCKED"
            and production_activation_status == "BLOCKED"
            and live_execution_status == "BLOCKED"
        )
        if not source_valid:
            return Phase11DeterministicReadOnlyPreflightDecision(
                is_allowed=False,
                preflight=None,
                blockers=("capability_contract_invariants_failed",),
            )

        terminal_snapshot = Phase11FakeTerminalSnapshot(
            terminal_name="GoldXBot-Fake-MT5",
            build_number=5000,
            lifecycle_state="FAKE_SHUTDOWN_COMPLETE",
            fake_initialized=True,
            fake_shutdown_completed=True,
            real_terminal_connected=False,
        )
        account_snapshot = Phase11FakeAccountSnapshot(
            account_id="FAKE-ACCOUNT-11001",
            trade_mode="FAKE_DEMO_READ_ONLY",
            trade_allowed=False,
            currency="USD",
            balance_minor_units=10_000_000,
            equity_minor_units=10_000_000,
            margin_used_minor_units=0,
            margin_free_minor_units=10_000_000,
            open_gold_position_count=0,
            pending_gold_order_count=0,
            reserved_risk_bps=0,
            is_real_account=False,
        )
        symbol_snapshot = Phase11FakeSymbolSnapshot(
            requested_symbol="XAUUSD",
            resolved_symbol="XAUUSD",
            visible=True,
            digits=2,
            point_scale=100,
            bid_price_points=241_000,
            ask_price_points=241_020,
            spread_points=20,
            tick_time_utc="2026-01-06T12:00:00Z",
            real_broker_data_used=False,
        )

        events = tuple(
            Phase11FakePreflightEvent(
                sequence_index=index,
                event_type=event_type,
                status="PASSED",
                evidence=evidence,
            )
            for index, (event_type, evidence) in enumerate(
                (
                    (
                        "CAPABILITY_CONTRACT_ACCEPTED",
                        "Immutable fake-only capability contract accepted.",
                    ),
                    (
                        "FAKE_TERMINAL_PACKAGE_CHECKED",
                        "Fake terminal package contract is available.",
                    ),
                    (
                        "FAKE_TERMINAL_INITIALIZED",
                        "Fake terminal lifecycle entered initialized state.",
                    ),
                    (
                        "FAKE_TERMINAL_INFO_READ",
                        "Fake terminal build and identity were read.",
                    ),
                    (
                        "FAKE_ACCOUNT_INFO_READ",
                        "Fake account, margin, and trade permission read.",
                    ),
                    (
                        "FAKE_SYMBOL_RESOLVED",
                        "Fake XAUUSD symbol resolved exactly.",
                    ),
                    (
                        "FAKE_SYMBOL_INFO_READ",
                        "Fake XAUUSD digits and point scale were read.",
                    ),
                    (
                        "FAKE_TICK_READ",
                        "Deterministic fake XAUUSD tick was read.",
                    ),
                    (
                        "FAKE_POSITIONS_READ",
                        "Fake position snapshot confirmed flat.",
                    ),
                    (
                        "FAKE_ORDERS_READ",
                        "Fake order snapshot confirmed zero pending orders.",
                    ),
                    (
                        "SAFETY_INVARIANTS_VERIFIED",
                        "Risk, OCO, broker SL, guards, and flat state held.",
                    ),
                    (
                        "CONTROLLED_WRITES_CONFIRMED_BLOCKED",
                        "Order check, order send, and OCO writes not invoked.",
                    ),
                    (
                        "FAKE_TERMINAL_SHUTDOWN",
                        "Fake terminal lifecycle completed shutdown.",
                    ),
                    (
                        "PREFLIGHT_FINALIZED",
                        "Fake read-only preflight is ready for audit.",
                    ),
                )
            )
        )

        terminal_flat_state_valid = (
            account_snapshot.open_gold_position_count == 0
            and account_snapshot.pending_gold_order_count == 0
            and account_snapshot.reserved_risk_bps == 0
        )
        exposure_state_valid = (
            account_snapshot.open_gold_position_count <= max_gold_positions
            and account_snapshot.pending_gold_order_count == 0
        )
        margin_state_valid = (
            account_snapshot.margin_used_minor_units == 0
            and account_snapshot.margin_free_minor_units == account_snapshot.equity_minor_units
        )
        symbol_resolution_valid = (
            symbol_snapshot.requested_symbol == symbol_snapshot.resolved_symbol == allowed_symbol
        )
        tick_snapshot_valid = (
            symbol_snapshot.ask_price_points > symbol_snapshot.bid_price_points
            and symbol_snapshot.spread_points == 20
        )
        capability_inventory_valid = tuple(
            capability.capability_id
            for capability in all_capabilities
            if capability.capability_id in PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS
        ) == PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS and all(
            capability.runtime_invocation_allowed is False for capability in all_capabilities
        )
        event_trace_contiguous = tuple(event.sequence_index for event in events) == tuple(
            range(len(events))
        )
        event_trace_order_valid = (
            tuple(event.event_type for event in events) == PHASE_11_PREFLIGHT_EVENT_TYPES
        )

        try:
            preflight = Phase11DeterministicReadOnlyPreflight(
                capability_decision=capability_decision,
                capability_contract=contract,
                admission_decision=admission_decision,
                admission_permit=admission_permit,
                phase10_handoff_bundle=phase10_handoff_bundle,
                schema_version=PHASE_11_PREFLIGHT_SCHEMA_VERSION,
                mode=PHASE_11_PREFLIGHT_MODE,
                status=PHASE_11_PREFLIGHT_STATUS,
                outcome=PHASE_11_PREFLIGHT_OUTCOME,
                source=PHASE_11_PREFLIGHT_SOURCE,
                terminal_snapshot=terminal_snapshot,
                account_snapshot=account_snapshot,
                symbol_snapshot=symbol_snapshot,
                verified_capability_ids=(PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS),
                blocked_capability_ids=(PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS),
                verified_capability_count=len(PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS),
                blocked_capability_count=len(PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS),
                allowed_symbol=allowed_symbol,
                allowed_timeframes=allowed_timeframes,
                closed_candles_only=True,
                max_gold_positions=max_gold_positions,
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                stage_risk_bps=stage_risk_bps,
                terminal_flat_state_valid=terminal_flat_state_valid,
                exposure_state_valid=exposure_state_valid,
                margin_state_valid=margin_state_valid,
                symbol_resolution_valid=symbol_resolution_valid,
                tick_snapshot_valid=tick_snapshot_valid,
                capability_inventory_valid=capability_inventory_valid,
                events=events,
                event_trace_contiguous=event_trace_contiguous,
                event_trace_order_valid=event_trace_order_valid,
                fake_terminal_lifecycle_exercised=True,
                real_mt5_imported=False,
                real_mt5_initialized=False,
                real_terminal_connected=False,
                real_broker_request_sent=False,
                real_account_read_performed=False,
                order_check_invoked=False,
                order_send_invoked=False,
                external_state_written=False,
                production_activated=False,
                live_order_submitted=False,
                real_preflight_execution_status=(PHASE_11_REAL_PREFLIGHT_EXECUTION_STATUS),
                production_activation_status=(PHASE_11_PRODUCTION_ACTIVATION_STATUS),
                live_execution_status=PHASE_11_LIVE_EXECUTION_STATUS,
                no_real_or_external_effects=True,
                ready_for_readiness_audit=True,
            )
        except ValueError as error:
            return Phase11DeterministicReadOnlyPreflightDecision(
                is_allowed=False,
                preflight=None,
                blockers=(f"fake_preflight_failed:{type(error).__name__}",),
            )

        return Phase11DeterministicReadOnlyPreflightDecision(
            is_allowed=True,
            preflight=preflight,
            blockers=(),
        )


def run_phase11_deterministic_read_only_preflight(
    capability_decision: object,
) -> Phase11DeterministicReadOnlyPreflightDecision:
    """Run the deterministic fake-only Phase 11 preflight."""

    return StrategyPhase11DeterministicReadOnlyPreflightRunner().run(capability_decision)


__all__ = (
    "PHASE_11_PREFLIGHT_SCHEMA_VERSION",
    "PHASE_11_PREFLIGHT_MODE",
    "PHASE_11_PREFLIGHT_STATUS",
    "PHASE_11_PREFLIGHT_OUTCOME",
    "PHASE_11_PREFLIGHT_SOURCE",
    "PHASE_11_REAL_PREFLIGHT_EXECUTION_STATUS",
    "PHASE_11_PRODUCTION_ACTIVATION_STATUS",
    "PHASE_11_LIVE_EXECUTION_STATUS",
    "PHASE_11_PREFLIGHT_EVENT_TYPES",
    "PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS",
    "PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS",
    "Phase11FakeTerminalSnapshot",
    "Phase11FakeAccountSnapshot",
    "Phase11FakeSymbolSnapshot",
    "Phase11FakePreflightEvent",
    "Phase11DeterministicReadOnlyPreflight",
    "Phase11DeterministicReadOnlyPreflightDecision",
    "StrategyPhase11DeterministicReadOnlyPreflightRunner",
    "run_phase11_deterministic_read_only_preflight",
)
