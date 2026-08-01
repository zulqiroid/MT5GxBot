from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase16_deterministic_offline_release_validation import (
    PHASE_16_OFFLINE_VALIDATION_OUTCOME,
    PHASE_16_OFFLINE_VALIDATION_SOURCE,
    PHASE_16_OFFLINE_VALIDATION_STATUS,
    Phase16OfflineReleaseValidator,
    validate_phase16_offline_release_readiness,
)
from tests.test_phase16_offline_release_readiness_blueprint import (
    bullish_phase16_blueprint_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedBlueprint:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase16_offline_validation_decision():
    return validate_phase16_offline_release_readiness(bullish_phase16_blueprint_decision())


def test_critical_validation_created() -> None:
    decision = bullish_phase16_offline_validation_decision()
    report = decision.report_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert report.validation_status == PHASE_16_OFFLINE_VALIDATION_STATUS
    assert report.validation_outcome == PHASE_16_OFFLINE_VALIDATION_OUTCOME
    assert report.validation_source == PHASE_16_OFFLINE_VALIDATION_SOURCE


def test_critical_complete_lineage_preserved() -> None:
    blueprint = bullish_phase16_blueprint_decision()
    report = validate_phase16_offline_release_readiness(blueprint).report_required
    assert report.blueprint_decision is blueprint
    assert report.blueprint is blueprint.blueprint_required
    assert report.admission_decision is blueprint.blueprint_required.admission_decision
    assert report.admission_permit is blueprint.blueprint_required.admission_permit
    assert report.phase15_final_handoff is blueprint.blueprint_required.phase15_final_handoff
    assert report.lineage_preserved is True


def test_critical_result_contract_exact() -> None:
    report = bullish_phase16_offline_validation_decision().report_required
    assert (
        report.component_results,
        report.requirement_results,
        report.track_results,
        report.total_results,
    ) == (8, 12, 5, 25)
    assert report.result_sequence_valid is True
    assert report.component_order_valid is True
    assert report.requirement_order_valid is True
    assert report.track_order_valid is True
    assert report.all_results_fake_only is True


def test_critical_release_baseline_and_counts_preserved() -> None:
    report = bullish_phase16_offline_validation_decision().report_required
    assert report.release_baseline_commit == "6ba3a00"
    assert report.release_baseline_tag == "goldxbot-phase-15-complete"
    assert report.source_validation_audit_counts == (8, 12, 20, 16)
    assert report.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_critical_gold_scope_and_risk_exact() -> None:
    report = bullish_phase16_offline_validation_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)


def test_critical_no_real_effects_and_runtime_blocked() -> None:
    report = bullish_phase16_offline_validation_decision().report_required
    forbidden = (
        report.real_env_access_performed,
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
    assert forbidden == (False,) * 12
    assert report.runtime_statuses == ("BLOCKED",) * 8
    assert report.no_real_or_external_effects is True


def test_all_results_are_fake_only_and_passed() -> None:
    report = bullish_phase16_offline_validation_decision().report_required
    assert len(report.results) == 25
    assert all(item.status == "PASSED" for item in report.results)
    assert all(item.fake_only is True for item in report.results)
    assert all(item.real_effect_performed is False for item in report.results)


def test_release_controls_and_safety_preserved() -> None:
    report = bullish_phase16_offline_validation_decision().report_required
    assert report.release_controls_preserved is True
    assert report.safety_invariants_preserved is True
    assert report.ready_for_offline_release_safety_audit is True


def test_validation_id_is_deterministic() -> None:
    first = bullish_phase16_offline_validation_decision().report_required
    second = bullish_phase16_offline_validation_decision().report_required
    assert first.validation_digest == second.validation_digest
    assert first.validation_id == second.validation_id


def test_missing_blueprint_is_rejected() -> None:
    missing = validate_phase16_offline_release_readiness(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase16_blueprint_decision_missing",)


def test_blocked_blueprint_is_rejected() -> None:
    blocked = validate_phase16_offline_release_readiness(BlockedBlueprint())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase16_blueprint_decision_blocked",)
    with pytest.raises(RuntimeError, match="validation is blocked"):
        _ = blocked.report_required


def test_factory_and_function_match() -> None:
    blueprint = bullish_phase16_blueprint_decision()
    first = Phase16OfflineReleaseValidator().validate(blueprint).report_required
    second = validate_phase16_offline_release_readiness(blueprint).report_required
    assert first.validation_id == second.validation_id
