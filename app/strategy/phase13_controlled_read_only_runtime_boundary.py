"""Immutable Phase 13 controlled read-only runtime boundary contract.

This module consumes the successful Step 13.1 admission permit and defines
future adapter operations, snapshot mappings, and fail-closed error mappings
for a controlled read-only runtime boundary.

The contract is planning-only. It does not import or initialize real
MetaTrader 5, connect to a terminal, contact a broker, read a real account,
run order_check, send an order, write external state, activate production,
or submit a live order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_13_RUNTIME_BOUNDARY_SCHEMA_VERSION = "1.0"
PHASE_13_RUNTIME_BOUNDARY_STATUS = "CONTRACT_READY"
PHASE_13_RUNTIME_BOUNDARY_MODE = "CONTROLLED_READ_ONLY_RUNTIME_BOUNDARY_CONTRACT_ONLY"
PHASE_13_RUNTIME_BOUNDARY_SOURCE = "IMMUTABLE_PLANNING_ONLY"

PHASE_13_RUNTIME_OPERATION_NAMES = (
    "IMPORT_MT5_PACKAGE",
    "INITIALIZE_TERMINAL",
    "READ_TERMINAL_INFO",
    "READ_ACCOUNT_INFO",
    "RESOLVE_SYMBOL",
    "READ_SYMBOL_INFO",
    "READ_TICK",
    "READ_POSITIONS",
    "READ_ORDERS",
    "SHUTDOWN_TERMINAL",
)

PHASE_13_BLOCKED_WRITE_OPERATION_NAMES = (
    "ORDER_CHECK",
    "ORDER_SEND",
    "APPLICATION_OCO_CONTROL",
)

PHASE_13_ERROR_MAPPING_CODES = (
    "MT5_PACKAGE_UNAVAILABLE",
    "TERMINAL_INITIALIZATION_FAILED",
    "TERMINAL_DISCONNECTED",
    "ACCOUNT_INFO_UNAVAILABLE",
    "SYMBOL_RESOLUTION_FAILED",
    "SYMBOL_INFO_UNAVAILABLE",
    "TICK_UNAVAILABLE",
    "POSITION_READ_FAILED",
    "ORDER_READ_FAILED",
    "TERMINAL_SHUTDOWN_FAILED",
)

PHASE_13_SNAPSHOT_MAPPING_NAMES = (
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
class Phase13RuntimeBoundaryOperation:
    """One immutable future runtime-boundary operation."""

    operation_name: str
    access_class: str
    lifecycle_stage: str
    read_only: bool
    runtime_invocation_allowed: bool
    separate_runtime_gate_required: bool

    def __post_init__(self) -> None:
        if self.operation_name not in PHASE_13_RUNTIME_OPERATION_NAMES:
            raise ValueError("unsupported runtime-boundary operation.")

        if self.access_class not in (
            "READ_ONLY",
            "CONTROLLED_LIFECYCLE",
        ):
            raise ValueError("unsupported operation access class.")

        if self.lifecycle_stage not in (
            "IMPORT",
            "INITIALIZE",
            "READ",
            "SHUTDOWN",
        ):
            raise ValueError("unsupported lifecycle stage.")

        if self.read_only is not True:
            raise ValueError("Phase 13 boundary operations must be read-only.")

        if self.runtime_invocation_allowed:
            raise ValueError("Step 13.2 cannot invoke runtime operations.")

        if self.separate_runtime_gate_required is not True:
            raise ValueError("separate runtime gate is mandatory.")

    @property
    def operation_digest(self) -> str:
        material = "|".join(
            (
                self.operation_name,
                self.access_class,
                self.lifecycle_stage,
                str(self.read_only),
                str(self.runtime_invocation_allowed),
                str(self.separate_runtime_gate_required),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase13BlockedWriteOperation:
    """One immutable write-sensitive operation that remains blocked."""

    operation_name: str
    fail_closed: bool
    invocation_allowed: bool
    separate_production_gate_required: bool

    def __post_init__(self) -> None:
        if self.operation_name not in PHASE_13_BLOCKED_WRITE_OPERATION_NAMES:
            raise ValueError("unsupported blocked write operation.")

        if self.fail_closed is not True:
            raise ValueError("blocked writes must fail closed.")

        if self.invocation_allowed:
            raise ValueError("blocked writes cannot be invoked.")

        if self.separate_production_gate_required is not True:
            raise ValueError("separate production gate is mandatory.")


@dataclass(frozen=True, slots=True)
class Phase13FailClosedErrorMapping:
    """Immutable fail-closed mapping for one future adapter failure."""

    error_code: str
    source_operation: str
    outcome: str
    retry_allowed: bool
    side_effects_allowed: bool
    human_review_required: bool

    def __post_init__(self) -> None:
        if self.error_code not in PHASE_13_ERROR_MAPPING_CODES:
            raise ValueError("unsupported error mapping code.")

        if self.source_operation not in PHASE_13_RUNTIME_OPERATION_NAMES:
            raise ValueError("unsupported error mapping operation.")

        if self.outcome != "BLOCKED":
            raise ValueError("error mappings must block.")

        if self.retry_allowed:
            raise ValueError("automatic retry is not admitted in Step 13.2.")

        if self.side_effects_allowed:
            raise ValueError("error mappings cannot allow side effects.")

        if self.human_review_required is not True:
            raise ValueError("human review is mandatory.")


@dataclass(frozen=True, slots=True)
class Phase13SnapshotMappingContract:
    """Immutable future mapping for one read-only snapshot."""

    snapshot_name: str
    field_names: tuple[str, ...]
    deterministic_mapping_required: bool
    read_only: bool
    real_data_access_allowed: bool

    def __post_init__(self) -> None:
        if self.snapshot_name not in PHASE_13_SNAPSHOT_MAPPING_NAMES:
            raise ValueError("unsupported snapshot mapping.")

        if not self.field_names:
            raise ValueError("snapshot fields are required.")

        if len(set(self.field_names)) != len(self.field_names):
            raise ValueError("snapshot fields must be unique.")

        if self.deterministic_mapping_required is not True:
            raise ValueError("deterministic mapping is mandatory.")

        if self.read_only is not True:
            raise ValueError("snapshot mappings must be read-only.")

        if self.real_data_access_allowed:
            raise ValueError("Step 13.2 cannot access real data.")


@dataclass(frozen=True, slots=True)
class Phase13ControlledReadOnlyRuntimeBoundaryContract:
    """Immutable fail-closed Phase 13 runtime-boundary contract."""

    admission_decision: object
    admission_permit: object
    phase12_handoff_bundle: object

    schema_version: str
    contract_status: str
    contract_mode: str
    contract_source: str

    runtime_operations: tuple[Phase13RuntimeBoundaryOperation, ...]
    blocked_write_operations: tuple[Phase13BlockedWriteOperation, ...]
    error_mappings: tuple[Phase13FailClosedErrorMapping, ...]
    snapshot_mappings: tuple[Phase13SnapshotMappingContract, ...]

    runtime_operation_count: int
    blocked_write_operation_count: int
    error_mapping_count: int
    snapshot_mapping_count: int
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

    explicit_human_authorization_required: bool
    separate_runtime_execution_gate_required: bool
    separate_real_account_read_gate_required: bool
    separate_production_gate_required: bool

    permits_fake_boundary_validation: bool
    permits_fake_error_mapping_validation: bool
    permits_fake_snapshot_mapping_validation: bool

    permits_real_preflight_execution: bool
    permits_real_mt5_import: bool
    permits_mt5_initialization: bool
    permits_terminal_connection: bool
    permits_broker_access: bool
    permits_real_account_reads: bool
    permits_order_check: bool
    permits_order_send: bool
    permits_external_writes: bool
    permits_production_activation: bool
    permits_live_order_submission: bool

    real_preflight_execution_status: str
    mt5_import_status: str
    mt5_initialization_status: str
    terminal_connection_status: str
    broker_access_status: str
    real_account_read_status: str
    production_activation_status: str
    live_execution_status: str

    contract_ready_for_fake_validation: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_13_RUNTIME_BOUNDARY_SCHEMA_VERSION:
            raise ValueError("runtime boundary schema is inconsistent.")

        if self.contract_status != PHASE_13_RUNTIME_BOUNDARY_STATUS:
            raise ValueError("contract status must be CONTRACT_READY.")

        if self.contract_mode != PHASE_13_RUNTIME_BOUNDARY_MODE:
            raise ValueError("contract mode is inconsistent.")

        if self.contract_source != PHASE_13_RUNTIME_BOUNDARY_SOURCE:
            raise ValueError("contract source is inconsistent.")

        if (
            tuple(operation.operation_name for operation in self.runtime_operations)
            != PHASE_13_RUNTIME_OPERATION_NAMES
        ):
            raise ValueError("runtime operation ordering is inconsistent.")

        if (
            tuple(operation.operation_name for operation in self.blocked_write_operations)
            != PHASE_13_BLOCKED_WRITE_OPERATION_NAMES
        ):
            raise ValueError("blocked operation ordering is inconsistent.")

        if (
            tuple(mapping.error_code for mapping in self.error_mappings)
            != PHASE_13_ERROR_MAPPING_CODES
        ):
            raise ValueError("error mapping ordering is inconsistent.")

        if (
            tuple(mapping.snapshot_name for mapping in self.snapshot_mappings)
            != PHASE_13_SNAPSHOT_MAPPING_NAMES
        ):
            raise ValueError("snapshot mapping ordering is inconsistent.")

        if self.runtime_operation_count != 10:
            raise ValueError("ten runtime operations are required.")

        if self.blocked_write_operation_count != 3:
            raise ValueError("three write operations must remain blocked.")

        if self.error_mapping_count != 10:
            raise ValueError("ten fail-closed error mappings are required.")

        if self.snapshot_mapping_count != 5:
            raise ValueError("five snapshot mappings are required.")

        if self.total_snapshot_field_count != 32:
            raise ValueError("snapshot field count is inconsistent.")

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
            self.explicit_human_authorization_required,
            self.separate_runtime_execution_gate_required,
            self.separate_real_account_read_gate_required,
            self.separate_production_gate_required,
            self.permits_fake_boundary_validation,
            self.permits_fake_error_mapping_validation,
            self.permits_fake_snapshot_mapping_validation,
            self.contract_ready_for_fake_validation,
        )
        if not all(required):
            raise ValueError("runtime boundary lost a required invariant.")

        forbidden = (
            self.permits_real_preflight_execution,
            self.permits_real_mt5_import,
            self.permits_mt5_initialization,
            self.permits_terminal_connection,
            self.permits_broker_access,
            self.permits_real_account_reads,
            self.permits_order_check,
            self.permits_order_send,
            self.permits_external_writes,
            self.permits_production_activation,
            self.permits_live_order_submission,
        )
        if any(forbidden):
            raise ValueError("runtime boundary cannot enable real effects.")

        statuses = (
            self.real_preflight_execution_status,
            self.mt5_import_status,
            self.mt5_initialization_status,
            self.terminal_connection_status,
            self.broker_access_status,
            self.real_account_read_status,
            self.production_activation_status,
            self.live_execution_status,
        )
        if any(status != "BLOCKED" for status in statuses):
            raise ValueError("all runtime statuses must remain BLOCKED.")

    @property
    def contract_digest(self) -> str:
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase12_handoff_id = str(getattr(self.phase12_handoff_bundle, "handoff_id", ""))
        operation_material = ",".join(
            operation.operation_digest for operation in self.runtime_operations
        )
        error_material = ",".join(mapping.error_code for mapping in self.error_mappings)
        snapshot_material = ",".join(mapping.snapshot_name for mapping in self.snapshot_mappings)
        material = "|".join(
            (
                self.schema_version,
                permit_id,
                phase12_handoff_id,
                self.contract_status,
                self.contract_mode,
                self.contract_source,
                operation_material,
                error_material,
                snapshot_material,
                str(self.runtime_operation_count),
                str(self.blocked_write_operation_count),
                str(self.error_mapping_count),
                str(self.snapshot_mapping_count),
                str(self.total_snapshot_field_count),
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.contract_ready_for_fake_validation),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def contract_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_13_CONTROLLED_READ_ONLY_RUNTIME_BOUNDARY:"
            f"SHA256[{self.contract_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase13ControlledReadOnlyRuntimeBoundaryDecision:
    """Allowed or blocked runtime-boundary contract decision."""

    is_allowed: bool
    contract: Phase13ControlledReadOnlyRuntimeBoundaryContract | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.contract is None or self.blockers:
                raise ValueError("allowed contract decision is inconsistent.")
        elif self.contract is not None or not self.blockers:
            raise ValueError("blocked contract decision is inconsistent.")

    @property
    def contract_required(
        self,
    ) -> Phase13ControlledReadOnlyRuntimeBoundaryContract:
        if self.contract is None:
            raise RuntimeError("Phase 13 controlled read-only runtime boundary is blocked.")
        return self.contract


def _runtime_operations() -> tuple[Phase13RuntimeBoundaryOperation, ...]:
    definitions = (
        ("IMPORT_MT5_PACKAGE", "CONTROLLED_LIFECYCLE", "IMPORT"),
        ("INITIALIZE_TERMINAL", "CONTROLLED_LIFECYCLE", "INITIALIZE"),
        ("READ_TERMINAL_INFO", "READ_ONLY", "READ"),
        ("READ_ACCOUNT_INFO", "READ_ONLY", "READ"),
        ("RESOLVE_SYMBOL", "READ_ONLY", "READ"),
        ("READ_SYMBOL_INFO", "READ_ONLY", "READ"),
        ("READ_TICK", "READ_ONLY", "READ"),
        ("READ_POSITIONS", "READ_ONLY", "READ"),
        ("READ_ORDERS", "READ_ONLY", "READ"),
        ("SHUTDOWN_TERMINAL", "CONTROLLED_LIFECYCLE", "SHUTDOWN"),
    )
    return tuple(
        Phase13RuntimeBoundaryOperation(
            operation_name=name,
            access_class=access,
            lifecycle_stage=stage,
            read_only=True,
            runtime_invocation_allowed=False,
            separate_runtime_gate_required=True,
        )
        for name, access, stage in definitions
    )


def _blocked_writes() -> tuple[Phase13BlockedWriteOperation, ...]:
    return tuple(
        Phase13BlockedWriteOperation(
            operation_name=name,
            fail_closed=True,
            invocation_allowed=False,
            separate_production_gate_required=True,
        )
        for name in PHASE_13_BLOCKED_WRITE_OPERATION_NAMES
    )


def _error_mappings() -> tuple[Phase13FailClosedErrorMapping, ...]:
    operation_names = PHASE_13_RUNTIME_OPERATION_NAMES
    return tuple(
        Phase13FailClosedErrorMapping(
            error_code=code,
            source_operation=operation,
            outcome="BLOCKED",
            retry_allowed=False,
            side_effects_allowed=False,
            human_review_required=True,
        )
        for code, operation in zip(
            PHASE_13_ERROR_MAPPING_CODES,
            operation_names,
            strict=True,
        )
    )


def _snapshot_mappings() -> tuple[Phase13SnapshotMappingContract, ...]:
    definitions = (
        (
            "TERMINAL_SNAPSHOT",
            (
                "terminal_name",
                "build_number",
                "connected",
                "trade_allowed",
                "dlls_allowed",
                "lifecycle_state",
            ),
        ),
        (
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
        ),
        (
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
        ),
        (
            "EXPOSURE_SNAPSHOT",
            (
                "open_gold_position_count",
                "pending_gold_order_count",
                "reserved_risk_bps",
                "aggregate_risk_budget_bps",
                "stage_risk_bps",
            ),
        ),
        (
            "ORDER_POSITION_SNAPSHOT",
            (
                "position_ids",
                "order_ids",
                "oco_group_ids",
                "broker_stop_loss_attached",
                "terminal_flat_state",
            ),
        ),
    )
    return tuple(
        Phase13SnapshotMappingContract(
            snapshot_name=name,
            field_names=fields,
            deterministic_mapping_required=True,
            read_only=True,
            real_data_access_allowed=False,
        )
        for name, fields in definitions
    )


class StrategyPhase13ControlledReadOnlyRuntimeBoundaryFactory:
    """Creates the immutable Step 13.2 runtime-boundary contract."""

    def create(
        self,
        admission_decision: object,
    ) -> Phase13ControlledReadOnlyRuntimeBoundaryDecision:
        if admission_decision is None:
            return Phase13ControlledReadOnlyRuntimeBoundaryDecision(
                False,
                None,
                ("phase13_admission_decision_missing",),
            )

        if getattr(admission_decision, "is_allowed", True) is not True:
            return Phase13ControlledReadOnlyRuntimeBoundaryDecision(
                False,
                None,
                ("phase13_admission_decision_blocked",),
            )

        try:
            permit = _required(admission_decision, "permit_required")
            source_valid = (
                _required(permit, "admission_mode")
                == "CONTROLLED_READ_ONLY_RUNTIME_BOUNDARY_PLANNING_ONLY"
                and _required(permit, "admission_status") == "ADMITTED"
                and _required(permit, "phase13_foundation_ready") is True
                and _required(permit, "symbol") == "XAUUSD"
                and _required(permit, "timeframes") == ("H4", "H1", "M15", "M5")
                and _required(permit, "closed_candles_only") is True
                and _required(permit, "max_gold_positions") == 1
                and _required(permit, "aggregate_risk_budget_bps") == 50
                and _required(permit, "stage_risk_bps") == (25, 25)
                and _required(permit, "real_preflight_execution_status") == "BLOCKED"
                and _required(permit, "mt5_import_status") == "BLOCKED"
                and _required(permit, "mt5_initialization_status") == "BLOCKED"
                and _required(permit, "terminal_connection_status") == "BLOCKED"
                and _required(permit, "broker_access_status") == "BLOCKED"
                and _required(permit, "real_account_read_status") == "BLOCKED"
                and _required(permit, "production_activation_status") == "BLOCKED"
                and _required(permit, "live_execution_status") == "BLOCKED"
            )
            phase12_handoff_bundle = _required(
                permit,
                "phase12_handoff_bundle",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase13ControlledReadOnlyRuntimeBoundaryDecision(
                False,
                None,
                (f"phase13_admission_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase13ControlledReadOnlyRuntimeBoundaryDecision(
                False,
                None,
                ("phase13_admission_contract_invalid",),
            )

        operations = _runtime_operations()
        blocked_writes = _blocked_writes()
        errors = _error_mappings()
        snapshots = _snapshot_mappings()

        contract = Phase13ControlledReadOnlyRuntimeBoundaryContract(
            admission_decision=admission_decision,
            admission_permit=permit,
            phase12_handoff_bundle=phase12_handoff_bundle,
            schema_version=PHASE_13_RUNTIME_BOUNDARY_SCHEMA_VERSION,
            contract_status=PHASE_13_RUNTIME_BOUNDARY_STATUS,
            contract_mode=PHASE_13_RUNTIME_BOUNDARY_MODE,
            contract_source=PHASE_13_RUNTIME_BOUNDARY_SOURCE,
            runtime_operations=operations,
            blocked_write_operations=blocked_writes,
            error_mappings=errors,
            snapshot_mappings=snapshots,
            runtime_operation_count=len(operations),
            blocked_write_operation_count=len(blocked_writes),
            error_mapping_count=len(errors),
            snapshot_mapping_count=len(snapshots),
            total_snapshot_field_count=sum(len(mapping.field_names) for mapping in snapshots),
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
            explicit_human_authorization_required=True,
            separate_runtime_execution_gate_required=True,
            separate_real_account_read_gate_required=True,
            separate_production_gate_required=True,
            permits_fake_boundary_validation=True,
            permits_fake_error_mapping_validation=True,
            permits_fake_snapshot_mapping_validation=True,
            permits_real_preflight_execution=False,
            permits_real_mt5_import=False,
            permits_mt5_initialization=False,
            permits_terminal_connection=False,
            permits_broker_access=False,
            permits_real_account_reads=False,
            permits_order_check=False,
            permits_order_send=False,
            permits_external_writes=False,
            permits_production_activation=False,
            permits_live_order_submission=False,
            real_preflight_execution_status="BLOCKED",
            mt5_import_status="BLOCKED",
            mt5_initialization_status="BLOCKED",
            terminal_connection_status="BLOCKED",
            broker_access_status="BLOCKED",
            real_account_read_status="BLOCKED",
            production_activation_status="BLOCKED",
            live_execution_status="BLOCKED",
            contract_ready_for_fake_validation=True,
        )
        return Phase13ControlledReadOnlyRuntimeBoundaryDecision(
            True,
            contract,
            (),
        )


def create_phase13_controlled_read_only_runtime_boundary(
    admission_decision: object,
) -> Phase13ControlledReadOnlyRuntimeBoundaryDecision:
    """Create the immutable Step 13.2 runtime-boundary contract."""

    return StrategyPhase13ControlledReadOnlyRuntimeBoundaryFactory().create(admission_decision)


__all__ = (
    "PHASE_13_RUNTIME_BOUNDARY_SCHEMA_VERSION",
    "PHASE_13_RUNTIME_BOUNDARY_STATUS",
    "PHASE_13_RUNTIME_BOUNDARY_MODE",
    "PHASE_13_RUNTIME_BOUNDARY_SOURCE",
    "PHASE_13_RUNTIME_OPERATION_NAMES",
    "PHASE_13_BLOCKED_WRITE_OPERATION_NAMES",
    "PHASE_13_ERROR_MAPPING_CODES",
    "PHASE_13_SNAPSHOT_MAPPING_NAMES",
    "Phase13RuntimeBoundaryOperation",
    "Phase13BlockedWriteOperation",
    "Phase13FailClosedErrorMapping",
    "Phase13SnapshotMappingContract",
    "Phase13ControlledReadOnlyRuntimeBoundaryContract",
    "Phase13ControlledReadOnlyRuntimeBoundaryDecision",
    "StrategyPhase13ControlledReadOnlyRuntimeBoundaryFactory",
    "create_phase13_controlled_read_only_runtime_boundary",
)
