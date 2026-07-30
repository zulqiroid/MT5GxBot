from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase14_deterministic_extension_architecture_validation import (
    PHASE_14_ARCHITECTURE_VALIDATION_OUTCOME,
    PHASE_14_ARCHITECTURE_VALIDATION_SCHEMA_VERSION,
    PHASE_14_ARCHITECTURE_VALIDATION_SOURCE,
    PHASE_14_ARCHITECTURE_VALIDATION_STATUS,
    Phase14ArchitectureValidator,
    validate_phase14_extension_architecture,
)
from tests.test_phase14_controlled_extension_architecture_blueprint import (
    bullish_phase14_architecture_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedArchitecture:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase14_architecture_validation_decision():
    return validate_phase14_extension_architecture(bullish_phase14_architecture_decision())


def test_static_contract() -> None:
    assert PHASE_14_ARCHITECTURE_VALIDATION_SCHEMA_VERSION == "1.0"
    assert PHASE_14_ARCHITECTURE_VALIDATION_STATUS == "PASSED"
    assert PHASE_14_ARCHITECTURE_VALIDATION_OUTCOME == "READY_FOR_ARCHITECTURE_SAFETY_AUDIT"
    assert PHASE_14_ARCHITECTURE_VALIDATION_SOURCE == "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"


def test_validation_created() -> None:
    decision = bullish_phase14_architecture_validation_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None


def test_lineage_preserved() -> None:
    architecture = bullish_phase14_architecture_decision()
    report = validate_phase14_extension_architecture(architecture).report_required
    assert report.architecture_decision is architecture
    assert report.architecture_blueprint is architecture.blueprint_required
    assert report.lineage_preserved is True


def test_status_outcome_source_exact() -> None:
    report = bullish_phase14_architecture_validation_decision().report_required
    assert report.validation_status == "PASSED"
    assert report.validation_outcome == "READY_FOR_ARCHITECTURE_SAFETY_AUDIT"
    assert report.validation_source == "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"
    assert report.ready_for_architecture_safety_audit is True


def test_result_counts_exact() -> None:
    report = bullish_phase14_architecture_validation_decision().report_required
    assert (report.component_results, report.requirement_results, report.total_results) == (
        8,
        12,
        20,
    )
    assert report.result_sequence_valid is True
    assert report.component_order_valid is True
    assert report.requirement_order_valid is True


def test_results_fake_only() -> None:
    report = bullish_phase14_architecture_validation_decision().report_required
    assert report.all_results_fake_only is True
    assert all(item.status == "PASSED" for item in report.results)


def test_source_counts_preserved() -> None:
    report = bullish_phase14_architecture_validation_decision().report_required
    assert (
        report.runtime_operations,
        report.blocked_write_operations,
        report.error_mappings,
        report.snapshot_mappings,
        report.snapshot_fields,
        report.prior_validation_events,
        report.prior_safety_findings,
    ) == (10, 3, 10, 5, 32, 15, 16)


def test_gold_scope_exact() -> None:
    report = bullish_phase14_architecture_validation_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)


def test_safety_and_gates_preserved() -> None:
    report = bullish_phase14_architecture_validation_decision().report_required
    assert report.safety_invariants_preserved is True
    assert report.future_gates_required is True


def test_all_real_effects_blocked() -> None:
    report = bullish_phase14_architecture_validation_decision().report_required
    assert report.real_preflight_executed is False
    assert report.real_mt5_imported is False
    assert report.real_mt5_initialized is False
    assert report.real_terminal_connected is False
    assert report.real_broker_access_performed is False
    assert report.real_account_read_performed is False
    assert report.order_check_invoked is False
    assert report.order_send_invoked is False
    assert report.external_state_written is False
    assert report.production_activated is False
    assert report.live_order_submitted is False
    assert report.no_real_or_external_effects is True


def test_all_runtime_statuses_blocked() -> None:
    report = bullish_phase14_architecture_validation_decision().report_required
    assert (
        report.real_preflight_status,
        report.mt5_import_status,
        report.mt5_initialization_status,
        report.terminal_status,
        report.broker_status,
        report.account_read_status,
        report.production_status,
        report.live_status,
    ) == ("BLOCKED",) * 8


def test_validation_id_deterministic() -> None:
    first = bullish_phase14_architecture_validation_decision().report_required
    second = bullish_phase14_architecture_validation_decision().report_required
    assert first.validation_digest == second.validation_digest
    assert first.validation_id == second.validation_id


def test_missing_architecture_blocks() -> None:
    decision = validate_phase14_extension_architecture(None)
    assert decision.is_allowed is False
    assert decision.blockers == ("phase14_architecture_decision_missing",)


def test_blocked_architecture_blocks() -> None:
    decision = validate_phase14_extension_architecture(BlockedArchitecture())
    assert decision.is_allowed is False
    assert decision.blockers == ("phase14_architecture_decision_blocked",)
    with pytest.raises(RuntimeError, match="validation is blocked"):
        _ = decision.report_required


def test_factory_and_function_match() -> None:
    architecture = bullish_phase14_architecture_decision()
    first = Phase14ArchitectureValidator().validate(architecture).report_required
    second = validate_phase14_extension_architecture(architecture).report_required
    assert first.validation_id == second.validation_id
