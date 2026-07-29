import importlib

import pytest

PROJECT_MODULES = [
    "app.broker",
    "app.broker.account_service",
    "app.broker.exposure_service",
    "app.broker.mt5_client",
    "app.broker.symbol_service",
    "app.config.constants",
    "app.config.settings",
    "app.domain",
    "app.domain.exposure",
    "app.domain.lifecycle",
    "app.domain.risk",
    "app.domain.sizing",
    "app.domain.trading",
    "app.logs.logger",
    "app.market.candle_model",
    "app.market.closed_candle",
    "app.market.closed_candle_service",
    "app.market.market_data_service",
    "app.market.market_data_validator",
    "app.market.market_quality",
    "app.market.multi_timeframe_service",
    "app.market.timeframes",
    "app.safety.trading_permission_guard",
    "app.strategy.analysis_pipeline",
    "app.strategy.context_freshness",
    "app.strategy.dealing_ranges",
    "app.strategy.directional_permission",
    "app.strategy.displacement",
    "app.strategy.fair_value_gaps",
    "app.strategy.fvg_mitigation",
    "app.strategy.liquidity",
    "app.strategy.liquidity_sweeps",
    "app.strategy.market_structure",
    "app.strategy.ote_zones",
    "app.strategy.multi_timeframe_context",
    "app.strategy.order_block_lifecycle",
    "app.strategy.order_blocks",
    "app.strategy.setup_candidate",
    "app.strategy.price_planning_admission",
    "app.strategy.price_planning_blueprint",
    "app.strategy.price_reference_plan",
    "app.strategy.price_reference_availability",
    "app.strategy.price_reference_resolution",
    "app.strategy.reward_risk_analysis",
    "app.strategy.risk_budget_admission",
    "app.strategy.position_sizing_handoff",
    "app.strategy.position_sizing_specification",
    "app.strategy.position_size_calculation",
    "app.strategy.sized_trade_plan",
    "app.strategy.order_intent_blueprint",
    "app.strategy.order_intent_execution_lock",
    "app.strategy.planning_package",
    "app.strategy.planning_audit_manifest",
    "app.strategy.planning_audit_record",
    "app.strategy.planning_audit_export",
    "app.strategy.planning_audit_verification",
    "app.strategy.planning_audit_storage_admission",
    "app.strategy.planning_audit_storage_blueprint",
    "app.strategy.planning_audit_storage_adapter_contract",
    "app.strategy.planning_audit_storage_adapter_assessment",
    "app.strategy.planning_audit_storage_adapter_binding",
    "app.strategy.planning_audit_storage_adapter_binding_verification",
    "app.strategy.planning_audit_persistence_request",
    "app.strategy.planning_audit_persistence_request_verification",
    "app.strategy.planning_audit_persistence_outcome_contract",
    "app.strategy.planning_audit_persistence_outcome_evidence",
    "app.strategy.planning_audit_persistence_outcome_receipt",
    "app.strategy.planning_audit_persistence_completion",
    "app.strategy.planning_audit_final_bundle",
    "app.strategy.phase8_dry_run_foundation",
    "app.strategy.phase8_closed_candle_data_contract",
    "app.strategy.phase8_closed_candle_snapshot",
    "app.strategy.phase8_closed_candle_snapshot_verification",
    "app.strategy.phase8_simulation_input_package",
    "app.strategy.phase8_offline_simulation_run_specification",
    "app.strategy.phase8_offline_replay_plan",
    "app.strategy.phase8_offline_replay_event_contract",
    "app.strategy.phase8_offline_replay_event_materialization_plan",
    "app.strategy.phase8_offline_replay_event_materialization",
    "app.strategy.phase8_offline_replay_session_plan",
    "app.strategy.phase8_offline_replay_session_contract",
    "app.strategy.phase8_offline_replay_session_state",
    "app.strategy.phase8_offline_replay_transition_contract",
    "app.strategy.phase8_offline_replay_transition_application",
    "app.strategy.phase8_offline_replay_advanced_session_state",
    "app.strategy.phase8_offline_replay_next_transition_contract",
    "app.strategy.phase8_offline_replay_next_transition_application",
    "app.strategy.phase8_offline_replay_progressed_session_state",
    "app.strategy.phase8_offline_replay_subsequent_transition_contract",
    "app.strategy.phase8_offline_replay_subsequent_transition_application",
    "app.strategy.phase8_offline_replay_subsequent_progressed_session_state",
    "app.strategy.phase8_offline_replay_recurrent_transition_contract",
    "app.strategy.phase8_offline_replay_recurrent_transition_application",
    "app.strategy.phase8_offline_replay_recurrent_progressed_session_state",
    "app.strategy.phase8_offline_replay_iterative_transition_contract",
    "app.strategy.phase8_offline_replay_iterative_transition_application",
    "app.strategy.phase8_offline_replay_iterative_progressed_session_state",
    "app.strategy.phase8_offline_replay_iterative_continuation_transition_contract",
    "app.strategy.phase8_offline_replay_iterative_continuation_transition_application",
    "app.strategy.phase8_offline_replay_iterative_continuation_progressed_session_state",
    "app.strategy.setup_candidate_quality",
    "app.strategy.setup_qualification",
    "app.strategy.strategy_context",
    "app.strategy.strategy_readiness",
    "app.strategy.swings",
]


@pytest.mark.parametrize("module_name", PROJECT_MODULES)
def test_project_module_imports_without_starting_bot(
    module_name: str,
) -> None:
    imported_module = importlib.import_module(module_name)

    assert imported_module is not None


def test_phase8_offline_replay_bounded_iteration_plan_imports() -> None:
    import importlib

    module = importlib.import_module("app.strategy.phase8_offline_replay_bounded_iteration_plan")

    assert hasattr(
        module,
        "Phase8OfflineReplayBoundedIterationPlan",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayBoundedIterationPlanFactory",
    )


def test_phase8_offline_replay_bounded_iteration_application_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_bounded_iteration_application"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayBoundedIterationApplicationReceipt",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayBoundedIterationApplication",
    )


def test_phase8_offline_replay_bounded_progressed_session_state_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_bounded_progressed_session_state"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayBoundedProgressedSessionState",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayBoundedProgressedSessionStateFactory",
    )


def test_phase8_offline_replay_bounded_continuation_plan_imports() -> None:
    import importlib

    module = importlib.import_module("app.strategy.phase8_offline_replay_bounded_continuation_plan")

    assert hasattr(
        module,
        "Phase8OfflineReplayBoundedContinuationPlan",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayBoundedContinuationPlanner",
    )


def test_phase8_offline_replay_bounded_continuation_application_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_bounded_continuation_application"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayBoundedContinuationApplicationReceipt",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayBoundedContinuationApplication",
    )


def test_phase8_offline_replay_bounded_continuation_progressed_state_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_bounded_continuation_progressed_state"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayBoundedContinuationProgressedSessionState",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayBoundedContinuationProgressedStateFactory",
    )


def test_phase8_offline_replay_recurrent_bounded_plan_imports() -> None:
    import importlib

    module = importlib.import_module("app.strategy.phase8_offline_replay_recurrent_bounded_plan")

    assert hasattr(
        module,
        "Phase8OfflineReplayRecurrentBoundedPlan",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayRecurrentBoundedPlanner",
    )


def test_phase8_offline_replay_recurrent_bounded_application_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_recurrent_bounded_application"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayRecurrentBoundedApplicationReceipt",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayRecurrentBoundedApplication",
    )


def test_phase8_offline_replay_recurrent_bounded_progressed_state_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_recurrent_bounded_progressed_state"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayRecurrentBoundedProgressedSessionState",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayRecurrentBoundedProgressedStateFactory",
    )


def test_phase8_offline_replay_iterative_recurrent_bounded_plan_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_iterative_recurrent_bounded_plan"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayIterativeRecurrentBoundedPlan",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayIterativeRecurrentBoundedPlanner",
    )


def test_phase8_offline_replay_iterative_recurrent_bounded_application_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_iterative_recurrent_bounded_application"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayIterativeRecurrentBoundedApplicationReceipt",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayIterativeRecurrentBoundedApplication",
    )


def test_phase8_offline_replay_iterative_recurrent_bounded_progressed_state_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_iterative_recurrent_bounded_progressed_state"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayIterativeRecurrentBoundedProgressedSessionState",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayIterativeRecurrentBoundedProgressedStateFactory",
    )


def test_phase8_offline_replay_subsequent_iterative_recurrent_bounded_plan_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_subsequent_iterative_recurrent_bounded_plan"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplaySubsequentIterativeRecurrentBoundedPlan",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplaySubsequentIterativeRecurrentBoundedPlanner",
    )


def test_phase8_offline_replay_subsequent_iterative_recurrent_bounded_application_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_subsequent_iterative_recurrent_bounded_application"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplaySubsequentIterativeRecurrentBoundedApplicationReceipt",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplaySubsequentIterativeRecurrentBoundedApplication",
    )


def test_phase8_offline_replay_subsequent_iterative_recurrent_bounded_progressed_state_imports() -> (
    None
):
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_subsequent_iterative_recurrent_bounded_progressed_state"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplaySubsequentIterativeRecurrentBoundedProgressedSessionState",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplaySubsequentIterativeRecurrentBoundedProgressedStateFactory",
    )


def test_phase8_offline_replay_successive_iterative_recurrent_bounded_plan_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_successive_iterative_recurrent_bounded_plan"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplaySuccessiveIterativeRecurrentBoundedPlan",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplaySuccessiveIterativeRecurrentBoundedPlanner",
    )


def test_phase8_offline_replay_successive_iterative_recurrent_bounded_application_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_successive_iterative_recurrent_bounded_application"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplaySuccessiveIterativeRecurrentBoundedApplicationReceipt",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplaySuccessiveIterativeRecurrentBoundedApplication",
    )


def test_phase8_offline_replay_successive_iterative_recurrent_bounded_progressed_state_imports() -> (
    None
):
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_successive_iterative_recurrent_bounded_progressed_state"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplaySuccessiveIterativeRecurrentBoundedProgressedSessionState",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplaySuccessiveIterativeRecurrentBoundedProgressedStateFactory",
    )


def test_phase8_offline_replay_continued_successive_iterative_recurrent_bounded_plan_imports() -> (
    None
):
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_continued_successive_iterative_recurrent_bounded_plan"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayContinuedSuccessiveIterativeRecurrentBoundedPlan",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayContinuedSuccessiveIterativeRecurrentBoundedPlanner",
    )


def test_phase8_offline_replay_continued_successive_iterative_recurrent_bounded_application_imports() -> (
    None
):
    import importlib

    module = importlib.import_module(
        "app.strategy."
        "phase8_offline_replay_continued_successive_iterative_recurrent_bounded_application"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayContinuedSuccessiveIterativeRecurrentBoundedApplicationReceipt",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayContinuedSuccessiveIterativeRecurrentBoundedApplication",
    )


def test_phase8_offline_replay_continued_successive_iterative_recurrent_bounded_progressed_state_imports() -> (
    None
):
    import importlib

    module = importlib.import_module(
        "app.strategy."
        "phase8_offline_replay_continued_successive_iterative_recurrent_bounded_progressed_state"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayContinuedSuccessiveIterativeRecurrentBoundedProgressedSessionState",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayContinuedSuccessiveIterativeRecurrentBoundedProgressedStateFactory",
    )


def test_phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan_imports() -> (
    None
):
    import importlib

    module = importlib.import_module(
        "app.strategy."
        "phase8_offline_replay_further_continued_successive_iterative_recurrent_bounded_plan"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayFurtherContinuedSuccessiveIterativeRecurrentBoundedPlan",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayFurtherContinuedSuccessiveIterativeRecurrentBoundedPlanner",
    )


def test_phase8_offline_replay_generic_remaining_bounded_completion_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase8_offline_replay_generic_remaining_bounded_completion"
    )

    assert hasattr(
        module,
        "Phase8OfflineReplayGenericRemainingCompletionState",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayGenericRemainingBoundedCompletionEngine",
    )
    assert hasattr(
        module,
        "complete_phase8_offline_replay_remaining_with_generic_bounded_engine",
    )


def test_phase8_offline_replay_terminal_exhaustion_audit_imports() -> None:
    import importlib

    module = importlib.import_module("app.strategy.phase8_offline_replay_terminal_exhaustion_audit")

    assert hasattr(
        module,
        "Phase8OfflineReplayTerminalExhaustionAuditReport",
    )
    assert hasattr(
        module,
        "StrategyPhase8OfflineReplayTerminalExhaustionAuditor",
    )
    assert hasattr(
        module,
        "audit_phase8_offline_replay_terminal_exhaustion",
    )
    assert hasattr(
        module,
        "block_phase8_offline_replay_terminal_reentry",
    )


def test_phase8_final_audit_handoff_imports() -> None:
    import importlib

    module = importlib.import_module("app.strategy.phase8_final_audit_handoff")

    assert hasattr(module, "Phase8FinalAuditHandoffBundle")
    assert hasattr(module, "StrategyPhase8FinalAuditHandoffFactory")
    assert hasattr(module, "create_phase8_final_audit_handoff")


def test_phase9_simulation_admission_gate_imports() -> None:
    import importlib

    module = importlib.import_module("app.strategy.phase9_simulation_admission_gate")

    assert hasattr(module, "Phase9SimulationAdmissionPermit")
    assert hasattr(module, "StrategyPhase9SimulationAdmissionGate")
    assert hasattr(module, "evaluate_phase9_simulation_admission")


def test_phase9_simulation_scenario_contract_imports() -> None:
    import importlib

    module = importlib.import_module("app.strategy.phase9_simulation_scenario_contract")

    assert hasattr(module, "Phase9ClosedCandleSnapshot")
    assert hasattr(module, "Phase9SimulationScenarioContract")
    assert hasattr(module, "StrategyPhase9SimulationScenarioFactory")
    assert hasattr(module, "create_phase9_simulation_scenario")


def test_phase9_deterministic_in_memory_simulation_runner_imports() -> None:
    import importlib

    module = importlib.import_module(
        "app.strategy.phase9_deterministic_in_memory_simulation_runner"
    )

    assert hasattr(module, "Phase9DeterministicSimulationRun")
    assert hasattr(
        module,
        "StrategyPhase9DeterministicInMemorySimulationRunner",
    )
    assert hasattr(
        module,
        "run_phase9_deterministic_in_memory_simulation",
    )


def test_phase9_simulation_safety_audit_imports() -> None:
    import importlib

    module = importlib.import_module("app.strategy.phase9_simulation_safety_audit")

    assert hasattr(module, "Phase9SimulationSafetyAuditReport")
    assert hasattr(module, "StrategyPhase9SimulationSafetyAuditor")
    assert hasattr(
        module,
        "audit_phase9_deterministic_simulation_safety",
    )
