"""Immutable Phase 11 fake preflight readiness safety audit.

This module consumes the deterministic fake-only Step 11.3 preflight and
creates an immutable readiness audit report. It verifies Phase 10 and
Phase 11 lineage, terminal/account/symbol snapshots, staged and aggregate
risk, one Gold position maximum, OCO and broker stop-loss requirements,
guard requirements, terminal flat state, capability coverage, event-trace
continuity, and the absence of real terminal, broker, account, write,
production, or live-order effects.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase11_deterministic_read_only_preflight import (
    PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS,
    PHASE_11_PREFLIGHT_EVENT_TYPES,
    PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS,
)

PHASE_11_READINESS_AUDIT_SCHEMA_VERSION = "1.0"
PHASE_11_READINESS_AUDIT_STATUS = "PASSED"
PHASE_11_READINESS_AUDIT_HANDOFF_STATUS = "READY_FOR_FINAL_HANDOFF"
PHASE_11_READINESS_AUDIT_SOURCE = "DETERMINISTIC_FAKE_ONLY"
PHASE_11_READINESS_AUDIT_REAL_PREFLIGHT_STATUS = "BLOCKED"
PHASE_11_READINESS_AUDIT_PRODUCTION_STATUS = "BLOCKED"
PHASE_11_READINESS_AUDIT_LIVE_STATUS = "BLOCKED"


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
class Phase11ReadinessAuditFinding:
    """Immutable result for one Phase 11 readiness invariant."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("finding name is required.")

        if self.passed is not True:
            raise ValueError("successful readiness findings must pass.")

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
class Phase11ReadinessSafetyAuditReport:
    """Immutable proof that fake live-readiness preflight remained safe."""

    preflight_decision: object
    preflight: object
    capability_decision: object
    capability_contract: object
    admission_decision: object
    admission_permit: object
    phase10_handoff_bundle: object

    schema_version: str
    audit_status: str
    final_handoff_status: str
    source: str

    preflight_mode: str
    preflight_status: str
    preflight_outcome: str

    symbol: str
    timeframes: tuple[str, ...]
    closed_candles_only: bool

    stage_risk_bps: tuple[int, ...]
    aggregate_risk_budget_bps: int
    max_gold_positions: int
    risk_contract_valid: bool

    oco_required: bool
    broker_stop_loss_required: bool
    guards_required: bool
    terminal_flat_state_required: bool
    oco_and_stop_loss_contract_valid: bool

    terminal_snapshot_valid: bool
    account_snapshot_valid: bool
    symbol_snapshot_valid: bool
    terminal_lifecycle_valid: bool
    margin_state_valid: bool
    exposure_state_valid: bool
    terminal_flat_state_valid: bool

    verified_capability_ids: tuple[str, ...]
    blocked_capability_ids: tuple[str, ...]
    verified_capability_count: int
    blocked_capability_count: int
    capability_inventory_valid: bool

    event_types: tuple[str, ...]
    event_sequence_indices: tuple[int, ...]
    event_count: int
    event_trace_contiguous: bool
    event_trace_order_valid: bool

    phase10_lineage_preserved: bool
    admission_lineage_preserved: bool
    capability_lineage_preserved: bool
    preflight_lineage_preserved: bool

    explicit_human_authorization_required: bool
    separate_preflight_gate_required: bool
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
    production_activation_status: str
    live_execution_status: str
    no_real_or_external_effects: bool

    findings: tuple[Phase11ReadinessAuditFinding, ...]
    readiness_audit_passed: bool
    ready_for_final_handoff: bool

    def __post_init__(self) -> None:
        if self.schema_version != PHASE_11_READINESS_AUDIT_SCHEMA_VERSION:
            raise ValueError("readiness audit schema version is inconsistent.")

        if self.audit_status != PHASE_11_READINESS_AUDIT_STATUS:
            raise ValueError("readiness audit status must be PASSED.")

        if self.final_handoff_status != PHASE_11_READINESS_AUDIT_HANDOFF_STATUS:
            raise ValueError("readiness handoff must be READY_FOR_FINAL_HANDOFF.")

        if self.source != PHASE_11_READINESS_AUDIT_SOURCE:
            raise ValueError("readiness audit source must be fake-only.")

        if self.preflight_mode != "DETERMINISTIC_FAKE_READ_ONLY":
            raise ValueError("preflight mode is inconsistent.")

        if self.preflight_status != "COMPLETED":
            raise ValueError("preflight status must be COMPLETED.")

        if self.preflight_outcome != "READY_FOR_READINESS_AUDIT":
            raise ValueError("preflight outcome is inconsistent.")

        if self.symbol != "XAUUSD":
            raise ValueError("readiness audit is XAUUSD only.")

        if self.timeframes != ("H4", "H1", "M15", "M5"):
            raise ValueError("readiness timeframes are inconsistent.")

        if self.closed_candles_only is not True:
            raise ValueError("closed candles are required.")

        if self.stage_risk_bps != (25, 25):
            raise ValueError("stage risk allocation is inconsistent.")

        if self.aggregate_risk_budget_bps != 50:
            raise ValueError("aggregate risk must be 50 bps.")

        if self.max_gold_positions != 1:
            raise ValueError("one Gold position maximum is required.")

        if self.verified_capability_ids != PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS:
            raise ValueError("verified capability ordering is inconsistent.")

        if self.blocked_capability_ids != PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS:
            raise ValueError("blocked capability ordering is inconsistent.")

        if self.verified_capability_count != 14:
            raise ValueError("fourteen fake capabilities must be verified.")

        if self.blocked_capability_count != 3:
            raise ValueError("three write-sensitive capabilities must block.")

        if self.event_types != PHASE_11_PREFLIGHT_EVENT_TYPES:
            raise ValueError("preflight event ordering is inconsistent.")

        if self.event_sequence_indices != tuple(range(len(PHASE_11_PREFLIGHT_EVENT_TYPES))):
            raise ValueError("preflight event sequence is inconsistent.")

        if self.event_count != 14:
            raise ValueError("fourteen preflight events are required.")

        required_truths = (
            self.risk_contract_valid,
            self.oco_required,
            self.broker_stop_loss_required,
            self.guards_required,
            self.terminal_flat_state_required,
            self.oco_and_stop_loss_contract_valid,
            self.terminal_snapshot_valid,
            self.account_snapshot_valid,
            self.symbol_snapshot_valid,
            self.terminal_lifecycle_valid,
            self.margin_state_valid,
            self.exposure_state_valid,
            self.terminal_flat_state_valid,
            self.capability_inventory_valid,
            self.event_trace_contiguous,
            self.event_trace_order_valid,
            self.phase10_lineage_preserved,
            self.admission_lineage_preserved,
            self.capability_lineage_preserved,
            self.preflight_lineage_preserved,
            self.explicit_human_authorization_required,
            self.separate_preflight_gate_required,
            self.separate_production_gate_required,
            self.no_real_or_external_effects,
            self.readiness_audit_passed,
            self.ready_for_final_handoff,
        )
        if not all(required_truths):
            raise ValueError("readiness audit contains a failed invariant.")

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
            raise ValueError("readiness audit detected a real effect.")

        if self.real_preflight_execution_status != PHASE_11_READINESS_AUDIT_REAL_PREFLIGHT_STATUS:
            raise ValueError("real preflight execution must remain BLOCKED.")

        if self.production_activation_status != PHASE_11_READINESS_AUDIT_PRODUCTION_STATUS:
            raise ValueError("production activation must remain BLOCKED.")

        if self.live_execution_status != PHASE_11_READINESS_AUDIT_LIVE_STATUS:
            raise ValueError("live execution must remain BLOCKED.")

        if len(self.findings) != 12:
            raise ValueError("twelve readiness findings are required.")

        if not all(finding.passed is True for finding in self.findings):
            raise ValueError("all readiness findings must pass.")

    @property
    def audit_digest(self) -> str:
        preflight_id = str(getattr(self.preflight, "preflight_id", ""))
        contract_id = str(getattr(self.capability_contract, "contract_id", ""))
        permit_id = str(getattr(self.admission_permit, "permit_id", ""))
        phase10_handoff_id = str(getattr(self.phase10_handoff_bundle, "handoff_id", ""))
        finding_material = ",".join(finding.finding_digest for finding in self.findings)
        material = "|".join(
            (
                self.schema_version,
                preflight_id,
                contract_id,
                permit_id,
                phase10_handoff_id,
                self.audit_status,
                self.final_handoff_status,
                self.source,
                self.preflight_mode,
                self.preflight_status,
                self.preflight_outcome,
                self.symbol,
                ",".join(self.timeframes),
                str(self.closed_candles_only),
                ",".join(str(value) for value in self.stage_risk_bps),
                str(self.aggregate_risk_budget_bps),
                str(self.max_gold_positions),
                str(self.risk_contract_valid),
                str(self.oco_required),
                str(self.broker_stop_loss_required),
                str(self.guards_required),
                str(self.terminal_flat_state_required),
                str(self.oco_and_stop_loss_contract_valid),
                str(self.terminal_snapshot_valid),
                str(self.account_snapshot_valid),
                str(self.symbol_snapshot_valid),
                str(self.terminal_lifecycle_valid),
                str(self.margin_state_valid),
                str(self.exposure_state_valid),
                str(self.terminal_flat_state_valid),
                ",".join(self.verified_capability_ids),
                ",".join(self.blocked_capability_ids),
                str(self.verified_capability_count),
                str(self.blocked_capability_count),
                str(self.capability_inventory_valid),
                ",".join(self.event_types),
                ",".join(str(value) for value in self.event_sequence_indices),
                str(self.event_count),
                str(self.event_trace_contiguous),
                str(self.event_trace_order_valid),
                str(self.phase10_lineage_preserved),
                str(self.admission_lineage_preserved),
                str(self.capability_lineage_preserved),
                str(self.preflight_lineage_preserved),
                str(self.explicit_human_authorization_required),
                str(self.separate_preflight_gate_required),
                str(self.separate_production_gate_required),
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
                finding_material,
                str(self.readiness_audit_passed),
                str(self.ready_for_final_handoff),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def audit_id(self) -> str:
        return f"GOLDXBOT_PHASE_11_READINESS_SAFETY_AUDIT:SHA256[{self.audit_digest}]"


@dataclass(frozen=True, slots=True)
class Phase11ReadinessSafetyAuditDecision:
    """Allowed or blocked Phase 11 readiness-audit decision."""

    is_allowed: bool
    report: Phase11ReadinessSafetyAuditReport | None
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
    def report_required(self) -> Phase11ReadinessSafetyAuditReport:
        if self.report is None:
            raise RuntimeError("Phase 11 readiness safety audit is blocked.")
        return self.report


class StrategyPhase11ReadinessSafetyAuditor:
    """Audits fake preflight readiness without causing effects."""

    def audit(
        self,
        preflight_decision: object,
    ) -> Phase11ReadinessSafetyAuditDecision:
        if preflight_decision is None:
            return Phase11ReadinessSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("read_only_preflight_decision_missing",),
            )

        if getattr(preflight_decision, "is_allowed", True) is not True:
            return Phase11ReadinessSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("read_only_preflight_decision_blocked",),
            )

        try:
            preflight = _required_attribute(
                preflight_decision,
                "preflight_required",
            )
            capability_decision = _required_attribute(
                preflight,
                "capability_decision",
            )
            contract = _required_attribute(
                preflight,
                "capability_contract",
            )
            admission_decision = _required_attribute(
                preflight,
                "admission_decision",
            )
            admission_permit = _required_attribute(
                preflight,
                "admission_permit",
            )
            phase10_handoff_bundle = _required_attribute(
                preflight,
                "phase10_handoff_bundle",
            )

            mode = _required_attribute(preflight, "mode")
            status = _required_attribute(preflight, "status")
            outcome = _required_attribute(preflight, "outcome")
            source = _required_attribute(preflight, "source")

            symbol = _required_attribute(preflight, "allowed_symbol")
            timeframes = _required_attribute(
                preflight,
                "allowed_timeframes",
            )
            closed_candles_only = _required_attribute(
                preflight,
                "closed_candles_only",
            )
            stage_risk_bps = _required_attribute(
                preflight,
                "stage_risk_bps",
            )
            aggregate_risk_budget_bps = _required_int(
                preflight,
                "aggregate_risk_budget_bps",
            )
            max_gold_positions = _required_int(
                preflight,
                "max_gold_positions",
            )
            verified_capability_ids = _required_attribute(
                preflight,
                "verified_capability_ids",
            )
            blocked_capability_ids = _required_attribute(
                preflight,
                "blocked_capability_ids",
            )
            verified_capability_count = _required_int(
                preflight,
                "verified_capability_count",
            )
            blocked_capability_count = _required_int(
                preflight,
                "blocked_capability_count",
            )
            events = _required_attribute(preflight, "events")

            terminal_snapshot = _required_attribute(
                preflight,
                "terminal_snapshot",
            )
            account_snapshot = _required_attribute(
                preflight,
                "account_snapshot",
            )
            symbol_snapshot = _required_attribute(
                preflight,
                "symbol_snapshot",
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            return Phase11ReadinessSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=(f"read_only_preflight_invalid:{type(error).__name__}",),
            )

        if not isinstance(events, tuple):
            return Phase11ReadinessSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=("read_only_preflight_shape_invalid",),
            )

        risk_contract_valid = (
            stage_risk_bps == (25, 25)
            and aggregate_risk_budget_bps == 50
            and sum(stage_risk_bps) == aggregate_risk_budget_bps
            and max_gold_positions == 1
        )

        oco_and_stop_loss_contract_valid = (
            contract.oco_required is True
            and contract.broker_stop_loss_required is True
            and contract.guards_required is True
            and contract.terminal_flat_state_required is True
        )

        terminal_snapshot_valid = (
            terminal_snapshot.terminal_name == "GoldXBot-Fake-MT5"
            and terminal_snapshot.build_number == 5000
            and terminal_snapshot.real_terminal_connected is False
        )
        account_snapshot_valid = (
            account_snapshot.trade_allowed is False
            and account_snapshot.is_real_account is False
            and account_snapshot.open_gold_position_count == 0
            and account_snapshot.pending_gold_order_count == 0
            and account_snapshot.reserved_risk_bps == 0
        )
        symbol_snapshot_valid = (
            symbol_snapshot.requested_symbol == "XAUUSD"
            and symbol_snapshot.resolved_symbol == "XAUUSD"
            and symbol_snapshot.real_broker_data_used is False
            and symbol_snapshot.spread_points == 20
        )
        terminal_lifecycle_valid = (
            terminal_snapshot.fake_initialized is True
            and terminal_snapshot.fake_shutdown_completed is True
            and preflight.fake_terminal_lifecycle_exercised is True
        )

        capability_inventory_valid = (
            verified_capability_ids == PHASE_11_PREFLIGHT_VERIFIED_CAPABILITY_IDS
            and blocked_capability_ids == PHASE_11_PREFLIGHT_BLOCKED_CAPABILITY_IDS
            and verified_capability_count == 14
            and blocked_capability_count == 3
            and preflight.capability_inventory_valid is True
        )

        event_types = tuple(event.event_type for event in events)
        event_sequence_indices = tuple(event.sequence_index for event in events)
        event_trace_contiguous = event_sequence_indices == tuple(range(len(events)))
        event_trace_order_valid = event_types == PHASE_11_PREFLIGHT_EVENT_TYPES

        phase10_lineage_preserved = (
            admission_permit.phase10_handoff_bundle is phase10_handoff_bundle
            and phase10_handoff_bundle.phase_number == 10
            and phase10_handoff_bundle.phase_status == "PHASE_10_COMPLETE"
        )
        admission_lineage_preserved = (
            contract.admission_decision is admission_decision
            and contract.admission_permit is admission_permit
        )
        capability_lineage_preserved = capability_decision.contract_required is contract
        preflight_lineage_preserved = (
            preflight.capability_decision is capability_decision
            and preflight.capability_contract is contract
        )

        no_real_or_external_effects = (
            preflight.real_mt5_imported is False
            and preflight.real_mt5_initialized is False
            and preflight.real_terminal_connected is False
            and preflight.real_broker_request_sent is False
            and preflight.real_account_read_performed is False
            and preflight.order_check_invoked is False
            and preflight.order_send_invoked is False
            and preflight.external_state_written is False
            and preflight.production_activated is False
            and preflight.live_order_submitted is False
            and preflight.real_preflight_execution_status == "BLOCKED"
            and preflight.production_activation_status == "BLOCKED"
            and preflight.live_execution_status == "BLOCKED"
            and preflight.no_real_or_external_effects is True
        )

        findings = (
            Phase11ReadinessAuditFinding(
                name="phase_lineage",
                passed=phase10_lineage_preserved,
                evidence="Phase 10 complete handoff lineage is preserved.",
            ),
            Phase11ReadinessAuditFinding(
                name="admission_and_capability_lineage",
                passed=(
                    admission_lineage_preserved
                    and capability_lineage_preserved
                    and preflight_lineage_preserved
                ),
                evidence="Admission, capability, and preflight lineage match.",
            ),
            Phase11ReadinessAuditFinding(
                name="risk_and_position_limits",
                passed=risk_contract_valid,
                evidence="25+25 bps equals 50 bps with one Gold position max.",
            ),
            Phase11ReadinessAuditFinding(
                name="oco_broker_sl_and_guards",
                passed=oco_and_stop_loss_contract_valid,
                evidence="OCO, broker SL, guards, and flat state are required.",
            ),
            Phase11ReadinessAuditFinding(
                name="fake_terminal_snapshot",
                passed=terminal_snapshot_valid and terminal_lifecycle_valid,
                evidence="Fake terminal lifecycle completed without connection.",
            ),
            Phase11ReadinessAuditFinding(
                name="fake_account_snapshot",
                passed=account_snapshot_valid,
                evidence="Fake account is read-only, flat, and risk-free.",
            ),
            Phase11ReadinessAuditFinding(
                name="fake_symbol_tick_snapshot",
                passed=symbol_snapshot_valid,
                evidence="Fake XAUUSD symbol and deterministic tick are valid.",
            ),
            Phase11ReadinessAuditFinding(
                name="margin_and_exposure_state",
                passed=(
                    preflight.margin_state_valid is True
                    and preflight.exposure_state_valid is True
                    and preflight.terminal_flat_state_valid is True
                ),
                evidence="Margin, exposure, and terminal flat state are valid.",
            ),
            Phase11ReadinessAuditFinding(
                name="capability_inventory",
                passed=capability_inventory_valid,
                evidence="Fourteen verified and three blocked capabilities.",
            ),
            Phase11ReadinessAuditFinding(
                name="preflight_event_trace",
                passed=event_trace_contiguous and event_trace_order_valid,
                evidence="Fourteen preflight events are contiguous and ordered.",
            ),
            Phase11ReadinessAuditFinding(
                name="future_authorization_gates",
                passed=(
                    contract.explicit_human_authorization_required is True
                    and contract.separate_preflight_gate_required is True
                    and contract.separate_production_gate_required is True
                ),
                evidence="Human, preflight, and production gates remain required.",
            ),
            Phase11ReadinessAuditFinding(
                name="no_real_or_external_effects",
                passed=no_real_or_external_effects,
                evidence="No real MT5, broker, account, write, or order effect.",
            ),
        )

        readiness_audit_passed = all(finding.passed is True for finding in findings)

        try:
            report = Phase11ReadinessSafetyAuditReport(
                preflight_decision=preflight_decision,
                preflight=preflight,
                capability_decision=capability_decision,
                capability_contract=contract,
                admission_decision=admission_decision,
                admission_permit=admission_permit,
                phase10_handoff_bundle=phase10_handoff_bundle,
                schema_version=PHASE_11_READINESS_AUDIT_SCHEMA_VERSION,
                audit_status=PHASE_11_READINESS_AUDIT_STATUS,
                final_handoff_status=(PHASE_11_READINESS_AUDIT_HANDOFF_STATUS),
                source=str(source),
                preflight_mode=str(mode),
                preflight_status=str(status),
                preflight_outcome=str(outcome),
                symbol=str(symbol),
                timeframes=timeframes,
                closed_candles_only=closed_candles_only is True,
                stage_risk_bps=stage_risk_bps,
                aggregate_risk_budget_bps=aggregate_risk_budget_bps,
                max_gold_positions=max_gold_positions,
                risk_contract_valid=risk_contract_valid,
                oco_required=contract.oco_required is True,
                broker_stop_loss_required=(contract.broker_stop_loss_required is True),
                guards_required=contract.guards_required is True,
                terminal_flat_state_required=(contract.terminal_flat_state_required is True),
                oco_and_stop_loss_contract_valid=(oco_and_stop_loss_contract_valid),
                terminal_snapshot_valid=terminal_snapshot_valid,
                account_snapshot_valid=account_snapshot_valid,
                symbol_snapshot_valid=symbol_snapshot_valid,
                terminal_lifecycle_valid=terminal_lifecycle_valid,
                margin_state_valid=preflight.margin_state_valid is True,
                exposure_state_valid=preflight.exposure_state_valid is True,
                terminal_flat_state_valid=(preflight.terminal_flat_state_valid is True),
                verified_capability_ids=verified_capability_ids,
                blocked_capability_ids=blocked_capability_ids,
                verified_capability_count=verified_capability_count,
                blocked_capability_count=blocked_capability_count,
                capability_inventory_valid=capability_inventory_valid,
                event_types=event_types,
                event_sequence_indices=event_sequence_indices,
                event_count=len(events),
                event_trace_contiguous=event_trace_contiguous,
                event_trace_order_valid=event_trace_order_valid,
                phase10_lineage_preserved=phase10_lineage_preserved,
                admission_lineage_preserved=admission_lineage_preserved,
                capability_lineage_preserved=capability_lineage_preserved,
                preflight_lineage_preserved=preflight_lineage_preserved,
                explicit_human_authorization_required=(
                    contract.explicit_human_authorization_required is True
                ),
                separate_preflight_gate_required=(
                    contract.separate_preflight_gate_required is True
                ),
                separate_production_gate_required=(
                    contract.separate_production_gate_required is True
                ),
                real_mt5_imported=preflight.real_mt5_imported is True,
                real_mt5_initialized=preflight.real_mt5_initialized is True,
                real_terminal_connected=(preflight.real_terminal_connected is True),
                real_broker_request_sent=(preflight.real_broker_request_sent is True),
                real_account_read_performed=(preflight.real_account_read_performed is True),
                order_check_invoked=preflight.order_check_invoked is True,
                order_send_invoked=preflight.order_send_invoked is True,
                external_state_written=(preflight.external_state_written is True),
                production_activated=preflight.production_activated is True,
                live_order_submitted=preflight.live_order_submitted is True,
                real_preflight_execution_status=(str(preflight.real_preflight_execution_status)),
                production_activation_status=(str(preflight.production_activation_status)),
                live_execution_status=str(preflight.live_execution_status),
                no_real_or_external_effects=no_real_or_external_effects,
                findings=findings,
                readiness_audit_passed=readiness_audit_passed,
                ready_for_final_handoff=readiness_audit_passed,
            )
        except ValueError as error:
            return Phase11ReadinessSafetyAuditDecision(
                is_allowed=False,
                report=None,
                blockers=(f"readiness_safety_audit_failed:{type(error).__name__}",),
            )

        return Phase11ReadinessSafetyAuditDecision(
            is_allowed=True,
            report=report,
            blockers=(),
        )


def audit_phase11_readiness_safety(
    preflight_decision: object,
) -> Phase11ReadinessSafetyAuditDecision:
    """Audit the deterministic Phase 11 fake preflight."""

    return StrategyPhase11ReadinessSafetyAuditor().audit(preflight_decision)


__all__ = (
    "PHASE_11_READINESS_AUDIT_SCHEMA_VERSION",
    "PHASE_11_READINESS_AUDIT_STATUS",
    "PHASE_11_READINESS_AUDIT_HANDOFF_STATUS",
    "PHASE_11_READINESS_AUDIT_SOURCE",
    "PHASE_11_READINESS_AUDIT_REAL_PREFLIGHT_STATUS",
    "PHASE_11_READINESS_AUDIT_PRODUCTION_STATUS",
    "PHASE_11_READINESS_AUDIT_LIVE_STATUS",
    "Phase11ReadinessAuditFinding",
    "Phase11ReadinessSafetyAuditReport",
    "Phase11ReadinessSafetyAuditDecision",
    "StrategyPhase11ReadinessSafetyAuditor",
    "audit_phase11_readiness_safety",
)
