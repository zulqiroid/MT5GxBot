"""Deterministic fake validation for the Phase 12 runtime contract.

This module consumes the immutable Step 12.2 runtime, adapter, and snapshot
planning contract. It validates every planned capability and snapshot schema
using deterministic in-memory fakes only.

It never imports or initializes real MetaTrader 5, connects to a terminal,
contacts a broker, reads a real account, runs order_check, sends an order,
writes external state, activates production, or submits a live order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

PHASE_12_FAKE_VALIDATION_SCHEMA_VERSION = "1.0"
PHASE_12_FAKE_VALIDATION_STATUS = "PASSED"
PHASE_12_FAKE_VALIDATION_OUTCOME = "READY_FOR_READINESS_AUDIT"
PHASE_12_FAKE_VALIDATION_SOURCE = "DETERMINISTIC_IN_MEMORY_FAKE"
PHASE_12_FAKE_VALIDATION_REAL_PREFLIGHT_STATUS = "BLOCKED"
PHASE_12_FAKE_VALIDATION_MT5_STATUS = "BLOCKED"
PHASE_12_FAKE_VALIDATION_TERMINAL_STATUS = "BLOCKED"
PHASE_12_FAKE_VALIDATION_BROKER_STATUS = "BLOCKED"
PHASE_12_FAKE_VALIDATION_PRODUCTION_STATUS = "BLOCKED"
PHASE_12_FAKE_VALIDATION_LIVE_STATUS = "BLOCKED"

PHASE_12_FAKE_VALIDATION_EVENT_TYPES = (
    "RUNTIME_CONTRACT_ACCEPTED",
    "VERIFIED_CAPABILITY_CONTRACTS_CHECKED",
    "BLOCKED_CAPABILITY_CONTRACTS_CHECKED",
    "TERMINAL_SNAPSHOT_SCHEMA_VALIDATED",
    "ACCOUNT_SNAPSHOT_SCHEMA_VALIDATED",
    "SYMBOL_TICK_SNAPSHOT_SCHEMA_VALIDATED",
    "EXPOSURE_SNAPSHOT_SCHEMA_VALIDATED",
    "ORDER_POSITION_SNAPSHOT_SCHEMA_VALIDATED",
    "XAUUSD_SCOPE_VALIDATED",
    "RISK_CONTRACT_VALIDATED",
    "OCO_BROKER_SL_GUARDS_VALIDATED",
    "TERMINAL_FLAT_STATE_VALIDATED",
    "REAL_EFFECTS_CONFIRMED_BLOCKED",
    "FAKE_VALIDATION_FINALIZED",
)


def _required(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise ValueError(f"{name} is required.")
    return getattr(value, name)


@dataclass(frozen=True, slots=True)
class Phase12FakeSnapshotPayload:
    """Immutable deterministic payload for one planned snapshot schema."""

    schema_name: str
    field_names: tuple[str, ...]
    values: tuple[object, ...]
    read_only: bool
    deterministic: bool
    real_data_used: bool

    def __post_init__(self) -> None:
        if not self.schema_name:
            raise ValueError("schema_name is required.")

        if not self.field_names:
            raise ValueError("field_names are required.")

        if len(self.field_names) != len(self.values):
            raise ValueError("snapshot field/value lengths must match.")

        if len(set(self.field_names)) != len(self.field_names):
            raise ValueError("snapshot field names must be unique.")

        if self.read_only is not True:
            raise ValueError("fake snapshots must be read-only.")

        if self.deterministic is not True:
            raise ValueError("fake snapshots must be deterministic.")

        if self.real_data_used:
            raise ValueError("real data use must remain false.")

    @property
    def payload_digest(self) -> str:
        material = "|".join(
            (
                self.schema_name,
                ",".join(self.field_names),
                ",".join(repr(value) for value in self.values),
                str(self.read_only),
                str(self.deterministic),
                str(self.real_data_used),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Phase12FakeValidationEvent:
    """Immutable deterministic validation event."""

    sequence_index: int
    event_type: str
    status: str
    evidence: str

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError("event sequence cannot be negative.")

        if self.event_type not in PHASE_12_FAKE_VALIDATION_EVENT_TYPES:
            raise ValueError("unsupported validation event type.")

        if self.status != "PASSED":
            raise ValueError("deterministic validation events must pass.")

        if not self.evidence:
            raise ValueError("event evidence is required.")

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
class Phase12DeterministicFakeRuntimeValidationReport:
    """Immutable proof that the Step 12.2 contract validates with fakes."""

    contract_decision: object
    runtime_contract: object
    admission_decision: object
    admission_permit: object
    phase11_handoff_bundle: object

    schema_version: str
    validation_status: str
    validation_outcome: str
    validation_source: str

    verified_capability_ids: tuple[str, ...]
    blocked_capability_ids: tuple[str, ...]
    verified_capability_count: int
    blocked_capability_count: int
    verified_capability_contracts_valid: bool
    blocked_capability_contracts_valid: bool

    snapshot_payloads: tuple[Phase12FakeSnapshotPayload, ...]
    snapshot_schema_names: tuple[str, ...]
    snapshot_schema_count: int
    total_snapshot_field_count: int
    snapshot_schema_coverage_valid: bool
    snapshot_payloads_deterministic: bool
    snapshot_payloads_read_only: bool
    no_real_snapshot_data_used: bool

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
    risk_contract_valid: bool
    oco_broker_sl_guard_contract_valid: bool
    terminal_flat_state_valid: bool

    events: tuple[Phase12FakeValidationEvent, ...]
    event_count: int
    event_trace_contiguous: bool
    event_trace_order_valid: bool

    admission_lineage_preserved: bool
    contract_lineage_preserved: bool
    phase11_lineage_preserved: bool

    explicit_human_authorization_required: bool
    separate_runtime_gate_required: bool
    separate_production_gate_required: bool

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
    mt5_initialization_status: str
    terminal_connection_status: str
    broker_access_status: str
    production_activation_status: str
    live_execution_status: str

    no_real_or_external_effects: bool
    ready_for_readiness_audit: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_12_FAKE_VALIDATION_SCHEMA_VERSION:
            raise ValueError("validation schema version is inconsistent.")

        if self.validation_status != PHASE_12_FAKE_VALIDATION_STATUS:
            raise ValueError("validation status must be PASSED.")

        if self.validation_outcome != PHASE_12_FAKE_VALIDATION_OUTCOME:
            raise ValueError("validation outcome is inconsistent.")

        if self.validation_source != PHASE_12_FAKE_VALIDATION_SOURCE:
            raise ValueError("validation source is inconsistent.")

        if self.verified_capability_count != 14:
            raise ValueError("fourteen capabilities must validate.")

        if self.blocked_capability_count != 3:
            raise ValueError("three write capabilities must remain blocked.")

        if self.snapshot_schema_count != 5:
            raise ValueError("five snapshot schemas must validate.")

        if self.total_snapshot_field_count != 32:
            raise ValueError("snapshot field count is inconsistent.")

        if self.symbol != "XAUUSD":
            raise ValueError("validation is XAUUSD only.")

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

        if self.event_count != 14:
            raise ValueError("fourteen validation events are required.")

        if tuple(event.event_type for event in self.events) != (
            PHASE_12_FAKE_VALIDATION_EVENT_TYPES
        ):
            raise ValueError("validation event ordering is inconsistent.")

        if tuple(event.sequence_index for event in self.events) != tuple(range(self.event_count)):
            raise ValueError("validation event sequence is inconsistent.")

        required_truths = (
            self.verified_capability_contracts_valid,
            self.blocked_capability_contracts_valid,
            self.snapshot_schema_coverage_valid,
            self.snapshot_payloads_deterministic,
            self.snapshot_payloads_read_only,
            self.no_real_snapshot_data_used,
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.risk_contract_valid,
            self.oco_broker_sl_guard_contract_valid,
            self.terminal_flat_state_valid,
            self.event_trace_contiguous,
            self.event_trace_order_valid,
            self.admission_lineage_preserved,
            self.contract_lineage_preserved,
            self.phase11_lineage_preserved,
            self.explicit_human_authorization_required,
            self.separate_runtime_gate_required,
            self.separate_production_gate_required,
            self.no_real_or_external_effects,
            self.ready_for_readiness_audit,
        )
        if not all(required_truths):
            raise ValueError("fake validation contains a failed invariant.")

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
            raise ValueError("fake validation detected a real effect.")

        statuses = (
            self.real_preflight_execution_status,
            self.mt5_initialization_status,
            self.terminal_connection_status,
            self.broker_access_status,
            self.production_activation_status,
            self.live_execution_status,
        )
        if any(status != "BLOCKED" for status in statuses):
            raise ValueError("all real runtime statuses must remain BLOCKED.")

    @property
    def validation_digest(self) -> str:
        contract_id = str(getattr(self.runtime_contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase11_handoff_id = str(getattr(self.phase11_handoff_bundle, "handoff_id", ""))
        payload_material = ",".join(payload.payload_digest for payload in self.snapshot_payloads)
        event_material = ",".join(event.event_digest for event in self.events)
        material = "|".join(
            (
                self.schema_version,
                contract_id,
                permit_id,
                phase11_handoff_id,
                self.validation_status,
                self.validation_outcome,
                self.validation_source,
                ",".join(self.verified_capability_ids),
                ",".join(self.blocked_capability_ids),
                payload_material,
                event_material,
                self.symbol,
                ",".join(self.timeframes),
                str(self.aggregate_risk_budget_bps),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.no_real_or_external_effects),
                str(self.ready_for_readiness_audit),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def validation_id(self) -> str:
        return f"GOLDXBOT_PHASE_12_DETERMINISTIC_FAKE_VALIDATION:SHA256[{self.validation_digest}]"


@dataclass(frozen=True, slots=True)
class Phase12DeterministicFakeRuntimeValidationDecision:
    """Allowed or blocked fake-validation decision."""

    is_allowed: bool
    report: Phase12DeterministicFakeRuntimeValidationReport | None
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.is_allowed:
            if self.report is None or self.blockers:
                raise ValueError("allowed validation decision is inconsistent.")
        elif self.report is not None or not self.blockers:
            raise ValueError("blocked validation decision is inconsistent.")

    @property
    def report_required(self) -> Phase12DeterministicFakeRuntimeValidationReport:
        if self.report is None:
            raise RuntimeError("Phase 12 deterministic fake validation is blocked.")
        return self.report


def _payloads() -> tuple[Phase12FakeSnapshotPayload, ...]:
    return (
        Phase12FakeSnapshotPayload(
            "TERMINAL_SNAPSHOT",
            (
                "terminal_name",
                "build_number",
                "connected",
                "trade_allowed",
                "dlls_allowed",
                "lifecycle_state",
            ),
            (
                "GoldXBot-Fake-MT5",
                5000,
                False,
                False,
                False,
                "FAKE_VALIDATION_COMPLETE",
            ),
            True,
            True,
            False,
        ),
        Phase12FakeSnapshotPayload(
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
            (
                "FAKE-ACCOUNT-12001",
                "FAKE_DEMO_READ_ONLY",
                False,
                "USD",
                10_000_000,
                10_000_000,
                0,
                10_000_000,
            ),
            True,
            True,
            False,
        ),
        Phase12FakeSnapshotPayload(
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
            (
                "XAUUSD",
                "XAUUSD",
                True,
                2,
                100,
                241_000,
                241_020,
                20,
            ),
            True,
            True,
            False,
        ),
        Phase12FakeSnapshotPayload(
            "EXPOSURE_SNAPSHOT",
            (
                "open_gold_position_count",
                "pending_gold_order_count",
                "reserved_risk_bps",
                "aggregate_risk_budget_bps",
                "stage_risk_bps",
            ),
            (
                0,
                0,
                0,
                50,
                (25, 25),
            ),
            True,
            True,
            False,
        ),
        Phase12FakeSnapshotPayload(
            "ORDER_POSITION_SNAPSHOT",
            (
                "position_ids",
                "order_ids",
                "oco_group_ids",
                "broker_stop_loss_attached",
                "terminal_flat_state",
            ),
            (
                (),
                (),
                (),
                True,
                True,
            ),
            True,
            True,
            False,
        ),
    )


class StrategyPhase12DeterministicFakeRuntimeValidator:
    """Validates the Step 12.2 contract using deterministic fakes."""

    def validate(
        self,
        contract_decision: object,
    ) -> Phase12DeterministicFakeRuntimeValidationDecision:
        if contract_decision is None:
            return Phase12DeterministicFakeRuntimeValidationDecision(
                False,
                None,
                ("runtime_contract_decision_missing",),
            )

        if getattr(contract_decision, "is_allowed", True) is not True:
            return Phase12DeterministicFakeRuntimeValidationDecision(
                False,
                None,
                ("runtime_contract_decision_blocked",),
            )

        try:
            contract = _required(contract_decision, "contract_required")
            admission_decision = _required(
                contract,
                "admission_decision",
            )
            admission_permit = _required(
                contract,
                "admission_permit",
            )
            phase11_handoff_bundle = _required(
                contract,
                "phase11_handoff_bundle",
            )

            source_valid = (
                _required(contract, "contract_status") == "CONTRACT_READY"
                and _required(contract, "contract_mode") == "REAL_PREFLIGHT_CONTRACT_ONLY"
                and _required(contract, "contract_source") == "IMMUTABLE_PLANNING_ONLY"
                and _required(contract, "verified_capability_count") == 14
                and _required(contract, "blocked_capability_count") == 3
                and _required(contract, "snapshot_schema_count") == 5
                and _required(contract, "total_snapshot_field_count") == 32
                and _required(contract, "contract_ready_for_fake_validation") is True
                and _required(contract, "real_preflight_execution_status") == "BLOCKED"
                and _required(contract, "mt5_initialization_status") == "BLOCKED"
                and _required(contract, "terminal_connection_status") == "BLOCKED"
                and _required(contract, "broker_access_status") == "BLOCKED"
                and _required(contract, "production_activation_status") == "BLOCKED"
                and _required(contract, "live_execution_status") == "BLOCKED"
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase12DeterministicFakeRuntimeValidationDecision(
                False,
                None,
                (f"runtime_contract_invalid:{type(error).__name__}",),
            )

        if not source_valid:
            return Phase12DeterministicFakeRuntimeValidationDecision(
                False,
                None,
                ("runtime_contract_invariants_failed",),
            )

        payloads = _payloads()
        schema_names = tuple(schema.schema_name for schema in contract.snapshot_schemas)
        payload_schema_names = tuple(payload.schema_name for payload in payloads)

        verified_capability_ids = tuple(
            capability.capability_id for capability in contract.verified_adapter_capabilities
        )
        blocked_capability_ids = tuple(
            capability.capability_id for capability in contract.blocked_adapter_capabilities
        )

        verified_capability_contracts_valid = len(verified_capability_ids) == 14 and all(
            capability.runtime_invocation_allowed is False
            for capability in contract.verified_adapter_capabilities
        )
        blocked_capability_contracts_valid = blocked_capability_ids == (
            "ORDER_CHECK",
            "ORDER_SEND",
            "APPLICATION_OCO_CONTROL",
        ) and all(
            capability.runtime_invocation_allowed is False
            for capability in contract.blocked_adapter_capabilities
        )

        snapshot_schema_coverage_valid = payload_schema_names == schema_names and all(
            payload.field_names == schema.required_fields
            for payload, schema in zip(
                payloads,
                contract.snapshot_schemas,
                strict=True,
            )
        )
        snapshot_payloads_deterministic = all(payload.deterministic is True for payload in payloads)
        snapshot_payloads_read_only = all(payload.read_only is True for payload in payloads)
        no_real_snapshot_data_used = all(payload.real_data_used is False for payload in payloads)

        exposure_payload = next(
            payload for payload in payloads if payload.schema_name == "EXPOSURE_SNAPSHOT"
        )
        exposure = dict(
            zip(
                exposure_payload.field_names,
                exposure_payload.values,
                strict=True,
            )
        )
        terminal_flat_state_valid = (
            exposure["open_gold_position_count"] == 0
            and exposure["pending_gold_order_count"] == 0
            and exposure["reserved_risk_bps"] == 0
        )
        risk_contract_valid = (
            contract.stage_risk_bps == (25, 25)
            and contract.aggregate_risk_budget_bps == 50
            and sum(contract.stage_risk_bps) == contract.aggregate_risk_budget_bps
            and contract.max_gold_positions == 1
        )
        oco_broker_sl_guard_contract_valid = (
            contract.oco_required is True
            and contract.broker_stop_loss_required is True
            and contract.guards_required is True
            and contract.terminal_flat_state_required is True
        )

        events = tuple(
            Phase12FakeValidationEvent(
                sequence_index=index,
                event_type=event_type,
                status="PASSED",
                evidence=evidence,
            )
            for index, (event_type, evidence) in enumerate(
                (
                    (
                        "RUNTIME_CONTRACT_ACCEPTED",
                        "Immutable Step 12.2 contract accepted.",
                    ),
                    (
                        "VERIFIED_CAPABILITY_CONTRACTS_CHECKED",
                        "Fourteen read/lifecycle capability contracts valid.",
                    ),
                    (
                        "BLOCKED_CAPABILITY_CONTRACTS_CHECKED",
                        "Three write-sensitive capability contracts blocked.",
                    ),
                    (
                        "TERMINAL_SNAPSHOT_SCHEMA_VALIDATED",
                        "Terminal schema matched deterministic fake payload.",
                    ),
                    (
                        "ACCOUNT_SNAPSHOT_SCHEMA_VALIDATED",
                        "Account schema matched deterministic fake payload.",
                    ),
                    (
                        "SYMBOL_TICK_SNAPSHOT_SCHEMA_VALIDATED",
                        "XAUUSD symbol/tick schema matched fake payload.",
                    ),
                    (
                        "EXPOSURE_SNAPSHOT_SCHEMA_VALIDATED",
                        "Exposure schema matched flat fake payload.",
                    ),
                    (
                        "ORDER_POSITION_SNAPSHOT_SCHEMA_VALIDATED",
                        "Order/position schema matched empty fake payload.",
                    ),
                    (
                        "XAUUSD_SCOPE_VALIDATED",
                        "XAUUSD and H4/H1/M15/M5 scope preserved.",
                    ),
                    (
                        "RISK_CONTRACT_VALIDATED",
                        "25+25 bps equals 50 bps with one position max.",
                    ),
                    (
                        "OCO_BROKER_SL_GUARDS_VALIDATED",
                        "OCO, broker SL, and guards remain mandatory.",
                    ),
                    (
                        "TERMINAL_FLAT_STATE_VALIDATED",
                        "Position, order, and reserved risk are zero.",
                    ),
                    (
                        "REAL_EFFECTS_CONFIRMED_BLOCKED",
                        "MT5, broker, account, writes, and orders blocked.",
                    ),
                    (
                        "FAKE_VALIDATION_FINALIZED",
                        "Validation is ready for readiness audit.",
                    ),
                )
            )
        )

        no_real_or_external_effects = (
            contract.permits_real_mt5_import is False
            and contract.permits_mt5_initialization is False
            and contract.permits_terminal_connection is False
            and contract.permits_broker_requests is False
            and contract.permits_real_account_reads is False
            and contract.permits_order_check is False
            and contract.permits_order_send is False
            and contract.permits_external_writes is False
            and contract.permits_production_activation is False
            and contract.permits_live_order_submission is False
        )

        report = Phase12DeterministicFakeRuntimeValidationReport(
            contract_decision=contract_decision,
            runtime_contract=contract,
            admission_decision=admission_decision,
            admission_permit=admission_permit,
            phase11_handoff_bundle=phase11_handoff_bundle,
            schema_version=PHASE_12_FAKE_VALIDATION_SCHEMA_VERSION,
            validation_status=PHASE_12_FAKE_VALIDATION_STATUS,
            validation_outcome=PHASE_12_FAKE_VALIDATION_OUTCOME,
            validation_source=PHASE_12_FAKE_VALIDATION_SOURCE,
            verified_capability_ids=verified_capability_ids,
            blocked_capability_ids=blocked_capability_ids,
            verified_capability_count=len(verified_capability_ids),
            blocked_capability_count=len(blocked_capability_ids),
            verified_capability_contracts_valid=(verified_capability_contracts_valid),
            blocked_capability_contracts_valid=(blocked_capability_contracts_valid),
            snapshot_payloads=payloads,
            snapshot_schema_names=payload_schema_names,
            snapshot_schema_count=len(payloads),
            total_snapshot_field_count=sum(len(payload.field_names) for payload in payloads),
            snapshot_schema_coverage_valid=snapshot_schema_coverage_valid,
            snapshot_payloads_deterministic=snapshot_payloads_deterministic,
            snapshot_payloads_read_only=snapshot_payloads_read_only,
            no_real_snapshot_data_used=no_real_snapshot_data_used,
            symbol=contract.symbol,
            timeframes=contract.timeframes,
            closed_candles_only=contract.closed_candles_only,
            max_gold_positions=contract.max_gold_positions,
            aggregate_risk_budget_bps=contract.aggregate_risk_budget_bps,
            stage_risk_bps=contract.stage_risk_bps,
            oco_required=contract.oco_required,
            broker_stop_loss_required=contract.broker_stop_loss_required,
            guards_required=contract.guards_required,
            terminal_flat_state_required=(contract.terminal_flat_state_required),
            risk_contract_valid=risk_contract_valid,
            oco_broker_sl_guard_contract_valid=(oco_broker_sl_guard_contract_valid),
            terminal_flat_state_valid=terminal_flat_state_valid,
            events=events,
            event_count=len(events),
            event_trace_contiguous=tuple(event.sequence_index for event in events)
            == tuple(range(len(events))),
            event_trace_order_valid=tuple(event.event_type for event in events)
            == PHASE_12_FAKE_VALIDATION_EVENT_TYPES,
            admission_lineage_preserved=(
                contract.admission_decision is admission_decision
                and contract.admission_permit is admission_permit
            ),
            contract_lineage_preserved=(contract_decision.contract_required is contract),
            phase11_lineage_preserved=(
                admission_permit.phase11_handoff_bundle is phase11_handoff_bundle
                and phase11_handoff_bundle.phase_status == "PHASE_11_COMPLETE"
            ),
            explicit_human_authorization_required=(contract.explicit_human_authorization_required),
            separate_runtime_gate_required=(contract.separate_runtime_gate_required),
            separate_production_gate_required=(contract.separate_production_gate_required),
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
            real_preflight_execution_status=(contract.real_preflight_execution_status),
            mt5_initialization_status=contract.mt5_initialization_status,
            terminal_connection_status=contract.terminal_connection_status,
            broker_access_status=contract.broker_access_status,
            production_activation_status=(contract.production_activation_status),
            live_execution_status=contract.live_execution_status,
            no_real_or_external_effects=no_real_or_external_effects,
            ready_for_readiness_audit=True,
        )
        return Phase12DeterministicFakeRuntimeValidationDecision(
            True,
            report,
            (),
        )


def validate_phase12_runtime_contract_with_fakes(
    contract_decision: object,
) -> Phase12DeterministicFakeRuntimeValidationDecision:
    """Validate the Step 12.2 runtime contract with deterministic fakes."""

    return StrategyPhase12DeterministicFakeRuntimeValidator().validate(contract_decision)


__all__ = (
    "PHASE_12_FAKE_VALIDATION_SCHEMA_VERSION",
    "PHASE_12_FAKE_VALIDATION_STATUS",
    "PHASE_12_FAKE_VALIDATION_OUTCOME",
    "PHASE_12_FAKE_VALIDATION_SOURCE",
    "PHASE_12_FAKE_VALIDATION_REAL_PREFLIGHT_STATUS",
    "PHASE_12_FAKE_VALIDATION_MT5_STATUS",
    "PHASE_12_FAKE_VALIDATION_TERMINAL_STATUS",
    "PHASE_12_FAKE_VALIDATION_BROKER_STATUS",
    "PHASE_12_FAKE_VALIDATION_PRODUCTION_STATUS",
    "PHASE_12_FAKE_VALIDATION_LIVE_STATUS",
    "PHASE_12_FAKE_VALIDATION_EVENT_TYPES",
    "Phase12FakeSnapshotPayload",
    "Phase12FakeValidationEvent",
    "Phase12DeterministicFakeRuntimeValidationReport",
    "Phase12DeterministicFakeRuntimeValidationDecision",
    "StrategyPhase12DeterministicFakeRuntimeValidator",
    "validate_phase12_runtime_contract_with_fakes",
)
