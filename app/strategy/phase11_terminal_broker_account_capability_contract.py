"""Immutable Phase 11 terminal, broker, and account capability contract.

This module consumes the fail-closed Phase 11 admission permit and creates
a deterministic capability inventory for terminal, broker, and account
readiness planning. The inventory is verified with immutable fake
descriptors only. It does not import or initialize a real MT5 terminal,
contact a broker, read a real account, write external state, activate
production, or submit an order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_11_CAPABILITY_SCHEMA_VERSION = "1.0"
PHASE_11_CAPABILITY_STATUS = "CONTRACT_READY"
PHASE_11_CAPABILITY_MODE = "READINESS_CAPABILITY_INVENTORY"
PHASE_11_CAPABILITY_SOURCE = "DETERMINISTIC_FAKE_ONLY"
PHASE_11_CAPABILITY_LIVE_EXECUTION_STATUS = "BLOCKED"
PHASE_11_CAPABILITY_PREFLIGHT_EXECUTION_STATUS = "BLOCKED"
PHASE_11_CAPABILITY_PRODUCTION_ACTIVATION_STATUS = "BLOCKED"

PHASE_11_TERMINAL_CAPABILITY_IDS = (
    "MT5_PACKAGE_IMPORT",
    "TERMINAL_INITIALIZE",
    "TERMINAL_INFO_READ",
    "TERMINAL_SHUTDOWN",
)
PHASE_11_BROKER_CAPABILITY_IDS = (
    "SYMBOL_RESOLUTION",
    "SYMBOL_INFO_READ",
    "TICK_READ",
    "POSITION_READ",
    "ORDER_READ",
    "ORDER_CHECK",
    "ORDER_SEND",
    "APPLICATION_OCO_CONTROL",
)
PHASE_11_ACCOUNT_CAPABILITY_IDS = (
    "ACCOUNT_INFO_READ",
    "TRADE_MODE_READ",
    "TRADE_PERMISSION_READ",
    "MARGIN_STATE_READ",
    "EXPOSURE_STATE_READ",
)


def _required_attribute(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase11ReadinessCapability:
    """Immutable fake-verified capability requirement."""

    capability_id: str
    domain: str
    access_class: str
    required_for_readiness: bool
    verified_with_fake_contract: bool
    runtime_invocation_allowed: bool
    future_gate_required: bool

    def __post_init__(self) -> None:
        if not self.capability_id:
            raise ValueError("capability id is required.")

        if self.domain not in ("TERMINAL", "BROKER", "ACCOUNT"):
            raise ValueError("unsupported capability domain.")

        if self.access_class not in (
            "READ_ONLY",
            "CONTROLLED_LIFECYCLE",
            "CONTROLLED_WRITE",
        ):
            raise ValueError("unsupported capability access class.")

        required_truths = (
            self.required_for_readiness,
            self.verified_with_fake_contract,
            self.future_gate_required,
        )
        if not all(required_truths):
            raise ValueError("capability lost a required readiness invariant.")

        if self.runtime_invocation_allowed:
            raise ValueError("Step 11.2 cannot invoke terminal or broker capabilities.")

    @property
    def capability_digest(self) -> str:
        material = "|".join(
            (
                self.capability_id,
                self.domain,
                self.access_class,
                str(self.required_for_readiness),
                str(self.verified_with_fake_contract),
                str(self.runtime_invocation_allowed),
                str(self.future_gate_required),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase11TerminalBrokerAccountCapabilityContract:
    """Immutable fake-only live-readiness capability inventory."""

    admission_decision: object
    admission_permit: object

    schema_version: str
    status: str
    capability_mode: str
    capability_source: str

    terminal_capabilities: tuple[Phase11ReadinessCapability, ...]
    broker_capabilities: tuple[Phase11ReadinessCapability, ...]
    account_capabilities: tuple[Phase11ReadinessCapability, ...]

    total_capability_count: int
    read_only_capability_count: int
    controlled_lifecycle_capability_count: int
    controlled_write_capability_count: int

    allowed_symbol: str
    allowed_timeframes: tuple[str, ...]
    closed_candles_only: bool
    max_gold_positions: int
    aggregate_risk_budget_bps: int
    stage_risk_bps: tuple[int, ...]

    oco_required: bool
    broker_stop_loss_required: bool
    guards_required: bool
    terminal_flat_state_required: bool
    martingale_prohibited: bool
    grid_prohibited: bool
    no_stop_loss_prohibited: bool

    fake_inventory_only: bool
    readiness_planning_only: bool
    explicit_human_authorization_required: bool
    separate_preflight_gate_required: bool
    separate_production_gate_required: bool

    preflight_execution_status: str
    production_activation_status: str
    live_execution_status: str

    permits_real_mt5_import: bool
    permits_mt5_initialization: bool
    permits_terminal_connection: bool
    permits_broker_requests: bool
    permits_real_account_reads: bool
    permits_external_writes: bool
    permits_live_order_submission: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_11_CAPABILITY_SCHEMA_VERSION:
            raise ValueError("capability schema version is inconsistent.")

        if self.status != PHASE_11_CAPABILITY_STATUS:
            raise ValueError("capability status must be CONTRACT_READY.")

        if self.capability_mode != PHASE_11_CAPABILITY_MODE:
            raise ValueError("capability mode must be READINESS_CAPABILITY_INVENTORY.")

        if self.capability_source != PHASE_11_CAPABILITY_SOURCE:
            raise ValueError("capability source must be DETERMINISTIC_FAKE_ONLY.")

        if (
            tuple(capability.capability_id for capability in self.terminal_capabilities)
            != PHASE_11_TERMINAL_CAPABILITY_IDS
        ):
            raise ValueError("terminal capability ordering is inconsistent.")

        if (
            tuple(capability.capability_id for capability in self.broker_capabilities)
            != PHASE_11_BROKER_CAPABILITY_IDS
        ):
            raise ValueError("broker capability ordering is inconsistent.")

        if (
            tuple(capability.capability_id for capability in self.account_capabilities)
            != PHASE_11_ACCOUNT_CAPABILITY_IDS
        ):
            raise ValueError("account capability ordering is inconsistent.")

        all_capabilities = self.all_capabilities

        if self.total_capability_count != 17:
            raise ValueError("seventeen readiness capabilities are required.")

        if len(all_capabilities) != self.total_capability_count:
            raise ValueError("capability count is inconsistent.")

        if self.read_only_capability_count != 13:
            raise ValueError("thirteen read-only capabilities are required.")

        if self.controlled_lifecycle_capability_count != 2:
            raise ValueError("two controlled lifecycle capabilities are required.")

        if self.controlled_write_capability_count != 2:
            raise ValueError("two controlled write capabilities are required.")

        if not all(
            capability.runtime_invocation_allowed is False for capability in all_capabilities
        ):
            raise ValueError("capability inventory must remain non-executable.")

        if not all(
            capability.verified_with_fake_contract is True for capability in all_capabilities
        ):
            raise ValueError("all capabilities must be fake-verified.")

        if self.allowed_symbol != "XAUUSD":
            raise ValueError("Phase 11 capability contract is XAUUSD only.")

        if self.allowed_timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("allowed timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("closed candles are required.")

        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("stage risk allocation is inconsistent.")

        if sum(self.stage_risk_bps) != self.aggregate_risk_budget_bps:
            raise ValueError("stage risk must equal aggregate risk.")

        required_truths = (
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.fake_inventory_only,
            self.readiness_planning_only,
            self.explicit_human_authorization_required,
            self.separate_preflight_gate_required,
            self.separate_production_gate_required,
        )
        if not all(required_truths):
            raise ValueError("capability contract lost a safety invariant.")

        if self.preflight_execution_status != PHASE_11_CAPABILITY_PREFLIGHT_EXECUTION_STATUS:
            raise ValueError("preflight execution must remain BLOCKED.")

        if self.production_activation_status != PHASE_11_CAPABILITY_PRODUCTION_ACTIVATION_STATUS:
            raise ValueError("production activation must remain BLOCKED.")

        if self.live_execution_status != PHASE_11_CAPABILITY_LIVE_EXECUTION_STATUS:
            raise ValueError("live execution must remain BLOCKED.")

        forbidden_capabilities = (
            self.permits_real_mt5_import,
            self.permits_mt5_initialization,
            self.permits_terminal_connection,
            self.permits_broker_requests,
            self.permits_real_account_reads,
            self.permits_external_writes,
            self.permits_live_order_submission,
        )
        if any(forbidden_capabilities):
            raise ValueError("Step 11.2 cannot enable real terminal or broker effects.")

    @property
    def all_capabilities(self) -> tuple[Phase11ReadinessCapability, ...]:
        return self.terminal_capabilities + self.broker_capabilities + self.account_capabilities

    @property
    def contract_digest(self) -> str:
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        capability_material = ",".join(
            capability.capability_digest for capability in self.all_capabilities
        )
        material = "|".join(
            (
                self.schema_version,
                permit_id,
                self.status,
                self.capability_mode,
                self.capability_source,
                capability_material,
                str(self.total_capability_count),
                str(self.read_only_capability_count),
                str(self.controlled_lifecycle_capability_count),
                str(self.controlled_write_capability_count),
                self.allowed_symbol,
                ",".join(self.allowed_timeframes),
                str(self.closed_candles_only),
                str(self.max_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.oco_required),
                str(self.broker_stop_loss_required),
                str(self.guards_required),
                str(self.terminal_flat_state_required),
                str(self.martingale_prohibited),
                str(self.grid_prohibited),
                str(self.no_stop_loss_prohibited),
                str(self.fake_inventory_only),
                str(self.readiness_planning_only),
                str(self.explicit_human_authorization_required),
                str(self.separate_preflight_gate_required),
                str(self.separate_production_gate_required),
                self.preflight_execution_status,
                self.production_activation_status,
                self.live_execution_status,
                str(self.permits_real_mt5_import),
                str(self.permits_mt5_initialization),
                str(self.permits_terminal_connection),
                str(self.permits_broker_requests),
                str(self.permits_real_account_reads),
                str(self.permits_external_writes),
                str(self.permits_live_order_submission),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def contract_id(self) -> str:
        return (
            f"GOLDXBOT_PHASE_11_TERMINAL_BROKER_ACCOUNT_CAPABILITY:SHA256[{self.contract_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase11TerminalBrokerAccountCapabilityDecision:
    """Allowed or blocked Phase 11 capability-contract decision."""

    is_allowed: bool
    contract: Phase11TerminalBrokerAccountCapabilityContract | None
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
    def contract_required(
        self,
    ) -> Phase11TerminalBrokerAccountCapabilityContract:
        if self.contract is None:
            raise RuntimeError("Phase 11 terminal, broker, and account contract is blocked.")
        return self.contract


class StrategyPhase11TerminalBrokerAccountCapabilityFactory:
    """Creates the deterministic fake-only capability inventory."""

    def create(
        self,
        admission_decision: object,
    ) -> Phase11TerminalBrokerAccountCapabilityDecision:
        if admission_decision is None:
            return Phase11TerminalBrokerAccountCapabilityDecision(
                is_allowed=False,
                contract=None,
                blockers=("live_readiness_admission_missing",),
            )

        if getattr(admission_decision, "is_allowed", True) is not True:
            return Phase11TerminalBrokerAccountCapabilityDecision(
                is_allowed=False,
                contract=None,
                blockers=("live_readiness_admission_blocked",),
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
            preflight_execution_allowed = _required_attribute(
                permit,
                "permits_preflight_execution",
            )
            mt5_initialization_allowed = _required_attribute(
                permit,
                "permits_mt5_initialization",
            )
            broker_requests_allowed = _required_attribute(
                permit,
                "permits_broker_requests",
            )
            live_order_allowed = _required_attribute(
                permit,
                "permits_live_order_submission",
            )
            production_activation_status = _required_attribute(
                permit,
                "production_activation_status",
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
            aggregate_risk_budget_bps = _required_attribute(
                permit,
                "aggregate_risk_budget_bps",
            )
            stage_risk_bps = _required_attribute(
                permit,
                "stage_risk_bps",
            )
            max_gold_positions = _required_attribute(
                permit,
                "max_gold_positions",
            )
            phase11_foundation_ready = _required_attribute(
                permit,
                "phase11_foundation_ready",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase11TerminalBrokerAccountCapabilityDecision(
                is_allowed=False,
                contract=None,
                blockers=(f"live_readiness_admission_invalid:{type(error).__name__}",),
            )

        source_valid = (
            admission_mode == "LIVE_READINESS_ONLY"
            and admission_status == "ADMITTED"
            and preflight_execution_allowed is False
            and mt5_initialization_allowed is False
            and broker_requests_allowed is False
            and live_order_allowed is False
            and production_activation_status == "BLOCKED"
            and live_execution_status == "BLOCKED"
            and allowed_symbol == "XAUUSD"
            and allowed_timeframes == ("H4", "H1", "M15", "M5")
            and aggregate_risk_budget_bps == 50
            and stage_risk_bps == (25, 25)
            and max_gold_positions == 1
            and phase11_foundation_ready is True
        )
        if not source_valid:
            return Phase11TerminalBrokerAccountCapabilityDecision(
                is_allowed=False,
                contract=None,
                blockers=("live_readiness_admission_contract_invalid",),
            )

        terminal_capabilities = (
            Phase11ReadinessCapability(
                capability_id="MT5_PACKAGE_IMPORT",
                domain="TERMINAL",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="TERMINAL_INITIALIZE",
                domain="TERMINAL",
                access_class="CONTROLLED_LIFECYCLE",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="TERMINAL_INFO_READ",
                domain="TERMINAL",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="TERMINAL_SHUTDOWN",
                domain="TERMINAL",
                access_class="CONTROLLED_LIFECYCLE",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
        )

        broker_capabilities = (
            Phase11ReadinessCapability(
                capability_id="SYMBOL_RESOLUTION",
                domain="BROKER",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="SYMBOL_INFO_READ",
                domain="BROKER",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="TICK_READ",
                domain="BROKER",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="POSITION_READ",
                domain="BROKER",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="ORDER_READ",
                domain="BROKER",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="ORDER_CHECK",
                domain="BROKER",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="ORDER_SEND",
                domain="BROKER",
                access_class="CONTROLLED_WRITE",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="APPLICATION_OCO_CONTROL",
                domain="BROKER",
                access_class="CONTROLLED_WRITE",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
        )

        account_capabilities = (
            Phase11ReadinessCapability(
                capability_id="ACCOUNT_INFO_READ",
                domain="ACCOUNT",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="TRADE_MODE_READ",
                domain="ACCOUNT",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="TRADE_PERMISSION_READ",
                domain="ACCOUNT",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="MARGIN_STATE_READ",
                domain="ACCOUNT",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
            Phase11ReadinessCapability(
                capability_id="EXPOSURE_STATE_READ",
                domain="ACCOUNT",
                access_class="READ_ONLY",
                required_for_readiness=True,
                verified_with_fake_contract=True,
                runtime_invocation_allowed=False,
                future_gate_required=True,
            ),
        )

        all_capabilities = terminal_capabilities + broker_capabilities + account_capabilities

        try:
            contract = Phase11TerminalBrokerAccountCapabilityContract(
                admission_decision=admission_decision,
                admission_permit=permit,
                schema_version=PHASE_11_CAPABILITY_SCHEMA_VERSION,
                status=PHASE_11_CAPABILITY_STATUS,
                capability_mode=PHASE_11_CAPABILITY_MODE,
                capability_source=PHASE_11_CAPABILITY_SOURCE,
                terminal_capabilities=terminal_capabilities,
                broker_capabilities=broker_capabilities,
                account_capabilities=account_capabilities,
                total_capability_count=len(all_capabilities),
                read_only_capability_count=sum(
                    capability.access_class == "READ_ONLY" for capability in all_capabilities
                ),
                controlled_lifecycle_capability_count=sum(
                    capability.access_class == "CONTROLLED_LIFECYCLE"
                    for capability in all_capabilities
                ),
                controlled_write_capability_count=sum(
                    capability.access_class == "CONTROLLED_WRITE" for capability in all_capabilities
                ),
                allowed_symbol=allowed_symbol,
                allowed_timeframes=allowed_timeframes,
                closed_candles_only=True,
                max_gold_positions=max_gold_positions,
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                stage_risk_bps=stage_risk_bps,
                oco_required=True,
                broker_stop_loss_required=True,
                guards_required=True,
                terminal_flat_state_required=True,
                martingale_prohibited=True,
                grid_prohibited=True,
                no_stop_loss_prohibited=True,
                fake_inventory_only=True,
                readiness_planning_only=True,
                explicit_human_authorization_required=True,
                separate_preflight_gate_required=True,
                separate_production_gate_required=True,
                preflight_execution_status=(PHASE_11_CAPABILITY_PREFLIGHT_EXECUTION_STATUS),
                production_activation_status=(PHASE_11_CAPABILITY_PRODUCTION_ACTIVATION_STATUS),
                live_execution_status=(PHASE_11_CAPABILITY_LIVE_EXECUTION_STATUS),
                permits_real_mt5_import=False,
                permits_mt5_initialization=False,
                permits_terminal_connection=False,
                permits_broker_requests=False,
                permits_real_account_reads=False,
                permits_external_writes=False,
                permits_live_order_submission=False,
            )
        except ValueError as error:
            return Phase11TerminalBrokerAccountCapabilityDecision(
                is_allowed=False,
                contract=None,
                blockers=(f"capability_contract_failed:{type(error).__name__}",),
            )

        return Phase11TerminalBrokerAccountCapabilityDecision(
            is_allowed=True,
            contract=contract,
            blockers=(),
        )


def create_phase11_terminal_broker_account_capability_contract(
    admission_decision: object,
) -> Phase11TerminalBrokerAccountCapabilityDecision:
    """Create the immutable fake-only Phase 11 capability contract."""

    return StrategyPhase11TerminalBrokerAccountCapabilityFactory().create(admission_decision)


__all__ = (
    "PHASE_11_CAPABILITY_SCHEMA_VERSION",
    "PHASE_11_CAPABILITY_STATUS",
    "PHASE_11_CAPABILITY_MODE",
    "PHASE_11_CAPABILITY_SOURCE",
    "PHASE_11_CAPABILITY_LIVE_EXECUTION_STATUS",
    "PHASE_11_CAPABILITY_PREFLIGHT_EXECUTION_STATUS",
    "PHASE_11_CAPABILITY_PRODUCTION_ACTIVATION_STATUS",
    "PHASE_11_TERMINAL_CAPABILITY_IDS",
    "PHASE_11_BROKER_CAPABILITY_IDS",
    "PHASE_11_ACCOUNT_CAPABILITY_IDS",
    "Phase11ReadinessCapability",
    "Phase11TerminalBrokerAccountCapabilityContract",
    "Phase11TerminalBrokerAccountCapabilityDecision",
    "StrategyPhase11TerminalBrokerAccountCapabilityFactory",
    "create_phase11_terminal_broker_account_capability_contract",
)
