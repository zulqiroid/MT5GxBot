from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase15_deterministic_architecture_validation import (
    PHASE_15_ARCHITECTURE_VALIDATION_OUTCOME,
    PHASE_15_ARCHITECTURE_VALIDATION_SOURCE,
    PHASE_15_ARCHITECTURE_VALIDATION_STATUS,
    Phase15ArchitectureValidator,
    validate_phase15_extension_architecture,
)
from tests.test_phase15_extension_architecture_blueprint import (
    bullish_phase15_architecture_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedArchitecture:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase15_architecture_validation_decision():
    return validate_phase15_extension_architecture(bullish_phase15_architecture_decision())


def test_validation_created_and_static_contract() -> None:
    decision = bullish_phase15_architecture_validation_decision()
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.report is not None
    assert PHASE_15_ARCHITECTURE_VALIDATION_STATUS == "PASSED"
    assert PHASE_15_ARCHITECTURE_VALIDATION_OUTCOME == "READY_FOR_ARCHITECTURE_SAFETY_AUDIT"
    assert PHASE_15_ARCHITECTURE_VALIDATION_SOURCE == "DETERMINISTIC_IN_MEMORY_FAKE_ONLY"


def test_complete_lineage_preserved() -> None:
    architecture = bullish_phase15_architecture_decision()
    report = validate_phase15_extension_architecture(architecture).report_required
    assert report.architecture_decision is architecture
    assert report.architecture_blueprint is architecture.blueprint_required
    assert report.admission_decision is architecture.blueprint_required.admission_decision
    assert report.admission_permit is architecture.blueprint_required.admission_permit
    assert report.phase14_final_handoff is architecture.blueprint_required.phase14_final_handoff
    assert report.lineage_preserved is True


def test_result_contract_exact_and_fake_only() -> None:
    report = bullish_phase15_architecture_validation_decision().report_required
    assert (
        report.component_results,
        report.requirement_results,
        report.total_results,
    ) == (8, 12, 20)
    assert report.result_sequence_valid is True
    assert report.component_order_valid is True
    assert report.requirement_order_valid is True
    assert report.all_results_fake_only is True
    assert all(item.status == "PASSED" for item in report.results)
    assert all(item.fake_only is True for item in report.results)
    assert all(item.real_effect_performed is False for item in report.results)


def test_source_counts_preserved() -> None:
    report = bullish_phase15_architecture_validation_decision().report_required
    assert report.source_validation_audit_counts == (8, 12, 20, 16)
    assert report.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_gold_scope_and_risk_exact() -> None:
    report = bullish_phase15_architecture_validation_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)


def test_safety_gates_and_outcome_exact() -> None:
    report = bullish_phase15_architecture_validation_decision().report_required
    assert report.validation_status == "PASSED"
    assert report.validation_outcome == "READY_FOR_ARCHITECTURE_SAFETY_AUDIT"
    assert report.safety_invariants_preserved is True
    assert report.future_gates_required is True
    assert report.ready_for_architecture_safety_audit is True


def test_all_real_effects_and_runtime_statuses_blocked() -> None:
    report = bullish_phase15_architecture_validation_decision().report_required
    forbidden = (
        report.real_preflight_executed,
        report.real_mt5_imported,
        report.real_mt5_initialized,
        report.real_terminal_connected,
        report.real_broker_access_performed,
        report.real_account_read_performed,
        report.order_check_invoked,
        report.order_send_invoked,
        report.external_state_written,
        report.production_activated,
        report.live_order_submitted,
    )
    assert forbidden == (False,) * 11
    assert report.runtime_statuses == ("BLOCKED",) * 8
    assert report.no_real_or_external_effects is True


def test_validation_id_is_deterministic() -> None:
    first = bullish_phase15_architecture_validation_decision().report_required
    second = bullish_phase15_architecture_validation_decision().report_required
    assert first.validation_digest == second.validation_digest
    assert first.validation_id == second.validation_id


def test_missing_and_blocked_architecture_block() -> None:
    missing = validate_phase15_extension_architecture(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase15_architecture_decision_missing",)

    blocked = validate_phase15_extension_architecture(BlockedArchitecture())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase15_architecture_decision_blocked",)
    with pytest.raises(RuntimeError, match="validation is blocked"):
        _ = blocked.report_required


def test_factory_and_function_match() -> None:
    architecture = bullish_phase15_architecture_decision()
    first = Phase15ArchitectureValidator().validate(architecture).report_required
    second = validate_phase15_extension_architecture(architecture).report_required
    assert first.validation_id == second.validation_id
