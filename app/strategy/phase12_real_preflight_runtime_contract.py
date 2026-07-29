"""Immutable Phase 12 runtime, adapter, and snapshot planning contract.

This module consumes the fail-closed Step 12.1 planning admission permit
and creates a deterministic contract for future real-preflight runtime
adapters and read-only snapshots.

The contract is planning-only. It does not import or initialize real
MetaTrader 5, connect to a terminal, contact a broker, read a real account,
run order_check, send an order, write external state, activate production,
or submit a live order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_12_RUNTIME_CONTRACT_SCHEMA_VERSION = "1.0"
PHASE_12_RUNTIME_CONTRACT_STATUS = "CONTRACT_READY"
PHASE_12_RUNTIME_CONTRACT_MODE = "REAL_PREFLIGHT_CONTRACT_ONLY"
PHASE_12_RUNTIME_CONTRACT_SOURCE = "IMMUTABLE_PLANNING_ONLY"
PHASE_12_RUNTIME_CONTRACT_REAL_PREFLIGHT_STATUS = "BLOCKED"
PHASE_12_RUNTIME_CONTRACT_MT5_STATUS = "BLOCKED"
PHASE_12_RUNTIME_CONTRACT_TERMINAL_STATUS = "BLOCKED"
PHASE_12_RUNTIME_CONTRACT_BROKER_STATUS = "BLOCKED"
PHASE_12_RUNTIME_CONTRACT_PRODUCTION_STATUS = "BLOCKED"
PHASE_12_RUNTIME_CONTRACT_LIVE_STATUS = "BLOCKED"

PHASE_12_VERIFIED_ADAPTER_CAPABILITY_IDS = (
    "MT5_PACKAGE_IMPORT",
    "TERMINAL_INITIALIZE",
    "TERMINAL_INFO_READ",
    "TERMINAL_SHUTDOWN",
    "ACCOUNT_INFO_READ",
    "TRADE_MODE_READ",
    "TRADE_PERMISSION_READ",
    "MARGIN_STATE_READ",
    "EXPOSURE_STATE_READ",
    "SYMBOL_RESOLUTION",
    "SYMBOL_INFO_READ",
    "TICK_READ",
    "POSITION_READ",
    "ORDER_READ",
)

PHASE_12_BLOCKED_ADAPTER_CAPABILITY_IDS = (
    "ORDER_CHECK",
    "ORDER_SEND",
    "APPLICATION_OCO_CONTROL",
)

PHASE_12_SNAPSHOT_SCHEMA_NAMES = (
    "TERMINAL_SNAPSHOT",
    "ACCOUNT_SNAPSHOT",
    "SYMBOL_TICK_SNAPSHOT",
    "EXPOSURE_SNAPSHOT",
    "ORDER_POSITION_SNAPSHOT",
)


def _required(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase12RuntimeAdapterCapability:
    """Immutable runtime-adapter planning requirement."""

    capability_id: str
    domain: str
    access_class: str
    required_for_real_preflight: bool
    contract_defined: bool
    runtime_invocation_allowed: bool
    separate_runtime_gate_required: bool

    def __post_init__(self) -> None:
        if not self.capability_id:
            raise ValueError("capability_id is required.")

        if self.domain not in ("TERMINAL", "ACCOUNT", "BROKER"):
            raise ValueError("unsupported capability domain.")

        if self.access_class not in (
            "READ_ONLY",
            "CONTROLLED_LIFECYCLE",
            "CONTROLLED_WRITE",
        ):
            raise ValueError("unsupported access class.")

        required = (
            self.required_for_real_preflight,
            self.contract_defined,
            self.separate_runtime_gate_required,
        )
        if not all(required):
            raise ValueError("capability lost a required planning invariant.")

        if self.runtime_invocation_allowed:
            raise ValueError("Step 12.2 cannot enable runtime invocation.")

    @property
    def capability_digest(self) -> str:
        material = "|".join(
            (
                self.capability_id,
                self.domain,
                self.access_class,
                str(self.required_for_real_preflight),
                str(self.contract_defined),
                str(self.runtime_invocation_allowed),
                str(self.separate_runtime_gate_required),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase12ReadOnlySnapshotSchema:
    """Immutable schema for one future read-only snapshot."""

    schema_name: str
    required_fields: tuple[str, ...]
    read_only: bool
    deterministic_validation_required: bool
    real_data_access_allowed: bool

    def __post_init__(self) -> None:
        if self.schema_name not in PHASE_12_SNAPSHOT_SCHEMA_NAMES:
            raise ValueError("unsupported snapshot schema.")

        if not self.required_fields:
            raise ValueError("snapshot schema requires fields.")

        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValueError("snapshot fields must be unique.")

        if self.read_only is not True:
            raise ValueError("snapshot schema must be read-only.")

        if self.deterministic_validation_required is not True:
            raise ValueError("deterministic validation is required.")

        if self.real_data_access_allowed:
            raise ValueError("Step 12.2 cannot access real data.")

    @property
    def schema_digest(self) -> str:
        material = "|".join(
            (
                self.schema_name,
                ",".join(self.required_fields),
                str(self.read_only),
                str(self.deterministic_validation_required),
                str(self.real_data_access_allowed),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase12RealPreflightRuntimeContract:
    """Immutable fail-closed runtime, adapter, and snapshot contract."""

    admission_decision: object
    admission_permit: object
    phase11_handoff_bundle: object

    schema_version: str
    contract_status: str
    contract_mode: str
    contract_source: str

    verified_adapter_capabilities: tuple[Phase12RuntimeAdapterCapability, ...]
    blocked_adapter_capabilities: tuple[Phase12RuntimeAdapterCapability, ...]
    snapshot_schemas: tuple[Phase12ReadOnlySnapshotSchema, ...]

    verified_capability_count: int
    blocked_capability_count: int
    snapshot_schema_count: int
    total_snapshot_field_count: int

    symbol: str
    timeframes: tuple[str, ...]
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

    explicit_human_authorization_required: bool
    separate_runtime_gate_required: bool
    separate_production_gate_required: bool

    permits_contract_validation: bool
    permits_fake_adapter_validation: bool
    permits_fake_snapshot_validation: bool

    permits_real_mt5_import: bool
    permits_mt5_initialization: bool
    permits_terminal_connection: bool
    permits_broker_requests: bool
    permits_real_account_reads: bool
    permits_order_check: bool
    permits_order_send: bool
    permits_external_writes: bool
    permits_production_activation: bool
    permits_live_order_submission: bool

    real_preflight_execution_status: str
    mt5_initialization_status: str
    terminal_connection_status: str
    broker_access_status: str
    production_activation_status: str
    live_execution_status: str

    contract_ready_for_fake_validation: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_12_RUNTIME_CONTRACT_SCHEMA_VERSION:
            raise ValueError("contract schema version is inconsistent.")

        if self.contract_status != PHASE_12_RUNTIME_CONTRACT_STATUS:
            raise ValueError("contract status must be CONTRACT_READY.")

        if self.contract_mode != PHASE_12_RUNTIME_CONTRACT_MODE:
            raise ValueError("contract mode is inconsistent.")

        if self.contract_source != PHASE_12_RUNTIME_CONTRACT_SOURCE:
            raise ValueError("contract source is inconsistent.")

        verified_ids = tuple(
            capability.capability_id for capability in self.verified_adapter_capabilities
        )
        blocked_ids = tuple(
            capability.capability_id for capability in self.blocked_adapter_capabilities
        )
        schema_names = tuple(schema.schema_name for schema in self.snapshot_schemas)

        if verified_ids != PHASE_12_VERIFIED_ADAPTER_CAPABILITY_IDS:
            raise ValueError("verified capability ordering is inconsistent.")

        if blocked_ids != PHASE_12_BLOCKED_ADAPTER_CAPABILITY_IDS:
            raise ValueError("blocked capability ordering is inconsistent.")

        if schema_names != PHASE_12_SNAPSHOT_SCHEMA_NAMES:
            raise ValueError("snapshot schema ordering is inconsistent.")

        if self.verified_capability_count != 14:
            raise ValueError("fourteen capabilities must be defined.")

        if self.blocked_capability_count != 3:
            raise ValueError("three write capabilities must remain blocked.")

        if self.snapshot_schema_count != 5:
            raise ValueError("five snapshot schemas are required.")

        if self.total_snapshot_field_count != 32:
            raise ValueError("snapshot field count is inconsistent.")

        all_capabilities = self.verified_adapter_capabilities + self.blocked_adapter_capabilities
        if not all(
            capability.runtime_invocation_allowed is False for capability in all_capabilities
        ):
            raise ValueError("all runtime invocation must remain blocked.")

        if not all(schema.real_data_access_allowed is False for schema in self.snapshot_schemas):
            raise ValueError("real snapshot data access must remain blocked.")

        if self.symbol != "XAUUSD":
            raise ValueError("contract is XAUUSD only.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("closed candles are required.")

        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("staged risk must be 25+25 bps.")

        required = (
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.martingale_prohibited,
            self.grid_prohibited,
            self.no_stop_loss_prohibited,
            self.explicit_human_authorization_required,
            self.separate_runtime_gate_required,
            self.separate_production_gate_required,
            self.permits_contract_validation,
            self.permits_fake_adapter_validation,
            self.permits_fake_snapshot_validation,
            self.contract_ready_for_fake_validation,
        )
        if not all(required):
            raise ValueError("contract lost a required safety invariant.")

        forbidden = (
            self.permits_real_mt5_import,
            self.permits_mt5_initialization,
            self.permits_terminal_connection,
            self.permits_broker_requests,
            self.permits_real_account_reads,
            self.permits_order_check,
            self.permits_order_send,
            self.permits_external_writes,
            self.permits_production_activation,
            self.permits_live_order_submission,
        )
        if any(forbidden):
            raise ValueError("contract cannot enable real effects.")

        statuses = (
            self.real_preflight_execution_status,
            self.mt5_initialization_status,
            self.terminal_connection_status,
            self.broker_access_status,
            self.production_activation_status,
            self.live_execution_status,
        )
        if any(status != "BLOCKED" for status in statuses):
            raise ValueError("all runtime statuses must remain BLOCKED.")

    @property
    def contract_digest(self) -> str:
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase11_handoff_id = str(getattr(self.phase11_handoff_bundle, "handoff_id", ""))
        capability_material = ",".join(
            capability.capability_digest
            for capability in (
                self.verified_adapter_capabilities + self.blocked_adapter_capabilities
            )
        )
        schema_material = ",".join(schema.schema_digest for schema in self.snapshot_schemas)
        material = "|".join(
            (
                self.schema_version,
                permit_id,
                phase11_handoff_id,
                self.contract_status,
                self.contract_mode,
                self.contract_source,
                capability_material,
                schema_material,
                str(self.verified_capability_count),
                str(self.blocked_capability_count),
                str(self.snapshot_schema_count),
                str(self.total_snapshot_field_count),
                self.symbol,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                str(self.max_gold_positions),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.contract_ready_for_fake_validation),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def contract_id(self) -> str:
        return f"GOLDXBOT_PHASE_12_REAL_PREFLIGHT_RUNTIME_CONTRACT:SHA256[{self.contract_digest}]"


@dataclass(frozen=True, slots=True)
class Phase12RealPreflightRuntimeContractDecision:
    """Allowed or blocked Phase 12 runtime-contract decision."""

    is_allowed: bool
    contract: Phase12RealPreflightRuntimeContract | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.contract is None or self.blockers:
                raise ValueError("allowed contract decision is inconsistent.")
        elif self.contract is not None or not self.blockers:
            raise ValueError("blocked contract decision is inconsistent.")

    @property
    def contract_required(self) -> Phase12RealPreflightRuntimeContract:
        if self.contract is None:
            raise RuntimeError("Phase 12 real-preflight runtime contract is blocked.")
        return self.contract


def _capability(
    capability_id: str,
    domain: str,
    access_class: str,
) -> Phase12RuntimeAdapterCapability:
    return Phase12RuntimeAdapterCapability(
        capability_id=capability_id,
        domain=domain,
        access_class=access_class,
        required_for_real_preflight=True,
        contract_defined=True,
        runtime_invocation_allowed=False,
        separate_runtime_gate_required=True,
    )


class StrategyPhase12RealPreflightRuntimeContractFactory:
    """Creates the immutable fail-closed Step 12.2 contract."""

    def create(
        self,
        admission_decision: object,
    ) -> Phase12RealPreflightRuntimeContractDecision:
        if admission_decision is None:
            return Phase12RealPreflightRuntimeContractDecision(
                False,
                None,
                ("phase12_admission_decision_missing",),
            )

        if getattr(admission_decision, "is_allowed", True) is not True:
            return Phase12RealPreflightRuntimeContractDecision(
                False,
                None,
                ("phase12_admission_decision_blocked",),
            )

        try:
            permit = _required(admission_decision, "permit_required")
            source_valid = (
                _required(permit, "admission_mode") == "REAL_PREFLIGHT_PLANNING_ONLY"
                and _required(permit, "admission_status") == "ADMITTED"
                and _required(permit, "phase12_foundation_ready") is True
                and _required(permit, "allowed_symbol") == "XAUUSD"
                and _required(permit, "allowed_timeframes") == ("H4", "H1", "M15", "M5")
                and _required(permit, "closed_candles_only") is True
                and _required(permit, "max_gold_positions") == 1
                and _required(permit, "aggregate_risk_budget_bps") == 50
                and _required(permit, "stage_risk_bps") == (25, 25)
                and _required(permit, "verified_capability_count") == 14
                and _required(permit, "blocked_capability_count") == 3
                and _required(permit, "verified_event_count") == 14
                and _required(permit, "real_preflight_execution_status") == "BLOCKED"
                and _required(permit, "mt5_initialization_status") == "BLOCKED"
                and _required(permit, "terminal_connection_status") == "BLOCKED"
                and _required(permit, "broker_access_status") == "BLOCKED"
                and _required(permit, "production_activation_status") == "BLOCKED"
                and _required(permit, "live_execution_status") == "BLOCKED"
            )
            phase11_handoff_bundle = _required(
                permit,
                "phase11_handoff_bundle",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase12RealPreflightRuntimeContractDecision(
                False,
                None,
                (f"phase12_admission_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase12RealPreflightRuntimeContractDecision(
                False,
                None,
                ("phase12_admission_contract_invalid",),
            )

        verified = (
            _capability("MT5_PACKAGE_IMPORT", "TERMINAL", "READ_ONLY"),
            _capability(
                "TERMINAL_INITIALIZE",
                "TERMINAL",
                "CONTROLLED_LIFECYCLE",
            ),
            _capability("TERMINAL_INFO_READ", "TERMINAL", "READ_ONLY"),
            _capability(
                "TERMINAL_SHUTDOWN",
                "TERMINAL",
                "CONTROLLED_LIFECYCLE",
            ),
            _capability("ACCOUNT_INFO_READ", "ACCOUNT", "READ_ONLY"),
            _capability("TRADE_MODE_READ", "ACCOUNT", "READ_ONLY"),
            _capability(
                "TRADE_PERMISSION_READ",
                "ACCOUNT",
                "READ_ONLY",
            ),
            _capability("MARGIN_STATE_READ", "ACCOUNT", "READ_ONLY"),
            _capability("EXPOSURE_STATE_READ", "ACCOUNT", "READ_ONLY"),
            _capability("SYMBOL_RESOLUTION", "BROKER", "READ_ONLY"),
            _capability("SYMBOL_INFO_READ", "BROKER", "READ_ONLY"),
            _capability("TICK_READ", "BROKER", "READ_ONLY"),
            _capability("POSITION_READ", "BROKER", "READ_ONLY"),
            _capability("ORDER_READ", "BROKER", "READ_ONLY"),
        )
        blocked = (
            _capability("ORDER_CHECK", "BROKER", "CONTROLLED_WRITE"),
            _capability("ORDER_SEND", "BROKER", "CONTROLLED_WRITE"),
            _capability(
                "APPLICATION_OCO_CONTROL",
                "BROKER",
                "CONTROLLED_WRITE",
            ),
        )

        schemas = (
            Phase12ReadOnlySnapshotSchema(
                "TERMINAL_SNAPSHOT",
                (
                    "terminal_name",
                    "build_number",
                    "connected",
                    "trade_allowed",
                    "dlls_allowed",
                    "lifecycle_state",
                ),
                True,
                True,
                False,
            ),
            Phase12ReadOnlySnapshotSchema(
                "ACCOUNT_SNAPSHOT",
                (
                    "account_id",
                    "trade_mode",
                    "trade_allowed",
                    "currency",
                    "balance_minor_units",
                    "equity_minor_units",
                    "margin_used_minor_units",
                    "margin_free_minor_units",
                ),
                True,
                True,
                False,
            ),
            Phase12ReadOnlySnapshotSchema(
                "SYMBOL_TICK_SNAPSHOT",
                (
                    "requested_symbol",
                    "resolved_symbol",
                    "visible",
                    "digits",
                    "point_scale",
                    "bid_price_points",
                    "ask_price_points",
                    "spread_points",
                ),
                True,
                True,
                False,
            ),
            Phase12ReadOnlySnapshotSchema(
                "EXPOSURE_SNAPSHOT",
                (
                    "open_gold_position_count",
                    "pending_gold_order_count",
                    "reserved_risk_bps",
                    "aggregate_risk_budget_bps",
                    "stage_risk_bps",
                ),
                True,
                True,
                False,
            ),
            Phase12ReadOnlySnapshotSchema(
                "ORDER_POSITION_SNAPSHOT",
                (
                    "position_ids",
                    "order_ids",
                    "oco_group_ids",
                    "broker_stop_loss_attached",
                    "terminal_flat_state",
                ),
                True,
                True,
                False,
            ),
        )

        contract = Phase12RealPreflightRuntimeContract(
            admission_decision=admission_decision,
            admission_permit=permit,
            phase11_handoff_bundle=phase11_handoff_bundle,
            schema_version=PHASE_12_RUNTIME_CONTRACT_SCHEMA_VERSION,
            contract_status=PHASE_12_RUNTIME_CONTRACT_STATUS,
            contract_mode=PHASE_12_RUNTIME_CONTRACT_MODE,
            contract_source=PHASE_12_RUNTIME_CONTRACT_SOURCE,
            verified_adapter_capabilities=verified,
            blocked_adapter_capabilities=blocked,
            snapshot_schemas=schemas,
            verified_capability_count=len(verified),
            blocked_capability_count=len(blocked),
            snapshot_schema_count=len(schemas),
            total_snapshot_field_count=sum(len(schema.required_fields) for schema in schemas),
            symbol="XAUUSD",
            timeframes=("H4", "H1", "M15", "M5"),
            closed_candles_only=True,
            max_gold_positions=1,
            aggregate_risk_budget_bps=50,
            stage_risk_bps=(25, 25),
            oco_required=True,
            broker_stop_loss_required=True,
            guards_required=True,
            terminal_flat_state_required=True,
            martingale_prohibited=True,
            grid_prohibited=True,
            no_stop_loss_prohibited=True,
            explicit_human_authorization_required=True,
            separate_runtime_gate_required=True,
            separate_production_gate_required=True,
            permits_contract_validation=True,
            permits_fake_adapter_validation=True,
            permits_fake_snapshot_validation=True,
            permits_real_mt5_import=False,
            permits_mt5_initialization=False,
            permits_terminal_connection=False,
            permits_broker_requests=False,
            permits_real_account_reads=False,
            permits_order_check=False,
            permits_order_send=False,
            permits_external_writes=False,
            permits_production_activation=False,
            permits_live_order_submission=False,
            real_preflight_execution_status="BLOCKED",
            mt5_initialization_status="BLOCKED",
            terminal_connection_status="BLOCKED",
            broker_access_status="BLOCKED",
            production_activation_status="BLOCKED",
            live_execution_status="BLOCKED",
            contract_ready_for_fake_validation=True,
        )
        return Phase12RealPreflightRuntimeContractDecision(
            True,
            contract,
            (),
        )


def create_phase12_real_preflight_runtime_contract(
    admission_decision: object,
) -> Phase12RealPreflightRuntimeContractDecision:
    """Create the immutable Step 12.2 runtime planning contract."""

    return StrategyPhase12RealPreflightRuntimeContractFactory().create(admission_decision)


__all__ = (
    "PHASE_12_RUNTIME_CONTRACT_SCHEMA_VERSION",
    "PHASE_12_RUNTIME_CONTRACT_STATUS",
    "PHASE_12_RUNTIME_CONTRACT_MODE",
    "PHASE_12_RUNTIME_CONTRACT_SOURCE",
    "PHASE_12_RUNTIME_CONTRACT_REAL_PREFLIGHT_STATUS",
    "PHASE_12_RUNTIME_CONTRACT_MT5_STATUS",
    "PHASE_12_RUNTIME_CONTRACT_TERMINAL_STATUS",
    "PHASE_12_RUNTIME_CONTRACT_BROKER_STATUS",
    "PHASE_12_RUNTIME_CONTRACT_PRODUCTION_STATUS",
    "PHASE_12_RUNTIME_CONTRACT_LIVE_STATUS",
    "PHASE_12_VERIFIED_ADAPTER_CAPABILITY_IDS",
    "PHASE_12_BLOCKED_ADAPTER_CAPABILITY_IDS",
    "PHASE_12_SNAPSHOT_SCHEMA_NAMES",
    "Phase12RuntimeAdapterCapability",
    "Phase12ReadOnlySnapshotSchema",
    "Phase12RealPreflightRuntimeContract",
    "Phase12RealPreflightRuntimeContractDecision",
    "StrategyPhase12RealPreflightRuntimeContractFactory",
    "create_phase12_real_preflight_runtime_contract",
)
