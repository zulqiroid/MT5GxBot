from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pytest

from app.strategy.phase17_deterministic_paper_mode_operational_validation import (
    PHASE_17_VALIDATION_OUTCOME,
    PHASE_17_VALIDATION_SOURCE,
    PHASE_17_VALIDATION_STATUS,
    Phase17PaperModeOperationalValidator,
    validate_phase17_paper_mode_operational_readiness,
)
from tests.test_phase17_paper_mode_operational_readiness_blueprint import (
    bullish_phase17_blueprint_decision,
)


@dataclass(frozen=True, slots=True)
class BlockedBlueprint:
    is_allowed: bool = False


@lru_cache(maxsize=1)
def bullish_phase17_validation_decision():
    return validate_phase17_paper_mode_operational_readiness(bullish_phase17_blueprint_decision())


def test_critical_validation_created() -> None:
    decision = bullish_phase17_validation_decision()
    report = decision.report_required
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert report.validation_status == PHASE_17_VALIDATION_STATUS
    assert report.validation_outcome == PHASE_17_VALIDATION_OUTCOME
    assert report.validation_source == PHASE_17_VALIDATION_SOURCE


def test_critical_blueprint_lineage_preserved() -> None:
    blueprint = bullish_phase17_blueprint_decision()
    report = validate_phase17_paper_mode_operational_readiness(blueprint).report_required
    assert report.blueprint_decision is blueprint
    assert report.blueprint is blueprint.blueprint_required
    assert report.admission_decision is blueprint.blueprint_required.admission_decision
    assert report.admission_permit is blueprint.blueprint_required.admission_permit
    assert report.lineage_preserved is True


def test_critical_result_contract_exact() -> None:
    report = bullish_phase17_validation_decision().report_required
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


def test_critical_phase16_and_source_evidence_preserved() -> None:
    report = bullish_phase17_validation_decision().report_required
    assert report.phase16_evidence_counts == (8, 12, 5, 25, 16)
    assert report.source_validation_audit_counts == (8, 12, 20, 16)
    assert report.source_evidence_counts == (10, 3, 10, 5, 32, 15, 16)


def test_critical_gold_scope_and_risk_exact() -> None:
    report = bullish_phase17_validation_decision().report_required
    assert report.symbol == "XAUUSD"
    assert report.timeframes == ("H4", "H1", "M15", "M5")
    assert report.closed_candles_only is True
    assert report.max_gold_positions == 1
    assert report.aggregate_risk_budget_bps == 50
    assert report.stage_risk_bps == (25, 25)


def test_critical_all_real_effects_blocked() -> None:
    report = bullish_phase17_validation_decision().report_required
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


def test_all_results_fake_only_and_passed() -> None:
    report = bullish_phase17_validation_decision().report_required
    assert len(report.results) == 25
    assert all(item.status == "PASSED" for item in report.results)
    assert all(item.fake_only for item in report.results)
    assert all(not item.real_effect_performed for item in report.results)


def test_operational_controls_preserved() -> None:
    report = bullish_phase17_validation_decision().report_required
    assert report.planning_only_preserved is True
    assert report.fail_closed_preserved is True
    assert report.evidence_handoff_preserved is True
    assert report.ready_for_operational_safety_audit is True


def test_release_baseline_preserved() -> None:
    report = bullish_phase17_validation_decision().report_required
    assert report.release_baseline_commit == "6ba3a00"
    assert report.release_baseline_tag == "goldxbot-phase-15-complete"


def test_validation_id_is_deterministic() -> None:
    first = bullish_phase17_validation_decision().report_required
    second = bullish_phase17_validation_decision().report_required
    assert first.validation_id == second.validation_id


def test_missing_blocked_and_factory_contract() -> None:
    missing = validate_phase17_paper_mode_operational_readiness(None)
    assert missing.is_allowed is False
    assert missing.blockers == ("phase17_blueprint_missing",)

    blocked = validate_phase17_paper_mode_operational_readiness(BlockedBlueprint())
    assert blocked.is_allowed is False
    assert blocked.blockers == ("phase17_blueprint_blocked",)
    with pytest.raises(RuntimeError, match="validation is blocked"):
        _ = blocked.report_required

    blueprint = bullish_phase17_blueprint_decision()
    first = Phase17PaperModeOperationalValidator().validate(blueprint).report_required
    second = validate_phase17_paper_mode_operational_readiness(blueprint).report_required
    assert first.validation_id == second.validation_id
