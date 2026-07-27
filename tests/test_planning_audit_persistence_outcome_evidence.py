import hashlib
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache

import pytest

from app.config.constants import TimeframeName
from app.market.closed_candle import (
    ClosedCandle,
    ClosedCandleSeries,
)
from app.market.timeframes import get_timeframe_spec
from app.strategy.analysis_pipeline import (
    MultiTimeframeAnalysisPipeline,
)
from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.market_structure import (
    MarketStructureBias,
)
from app.strategy.multi_timeframe_context import (
    GOLD_TIMEFRAME_HIERARCHY,
    MultiTimeframeContextBuilder,
)
from app.strategy.order_intent_blueprint import (
    StrategyOrderIntentBlueprintFactory,
    StrategyOrderSide,
)
from app.strategy.order_intent_execution_lock import (
    StrategyExecutionBoundaryLockFactory,
)
from app.strategy.planning_audit_export import (
    StrategyPlanningAuditExportFactory,
)
from app.strategy.planning_audit_manifest import (
    StrategyPlanningAuditManifestFactory,
)
from app.strategy.planning_audit_persistence_outcome_contract import (
    PlanningAuditPersistenceOutcomeKind,
    StrategyPlanningAuditPersistenceOutcomeContractFactory,
)
from app.strategy.planning_audit_persistence_outcome_evidence import (
    AuditPersistenceOutcomeEvidenceBlocker,
    AuditPersistenceOutcomeEvidenceDecision,
    AuditPersistenceOutcomeEvidenceGate,
    AuditPersistenceOutcomeEvidencePolicy,
    AuditPersistenceOutcomeEvidenceReason,
    AuditPersistenceOutcomeEvidenceSnapshot,
    AuditPersistenceOutcomeEvidenceSourceMode,
    AuditPersistenceOutcomeEvidenceStatus,
    PlanningAuditPersistenceOutcomeEvidenceBlocker,
    PlanningAuditPersistenceOutcomeEvidenceDecision,
    PlanningAuditPersistenceOutcomeEvidenceError,
    PlanningAuditPersistenceOutcomeEvidenceErrorReason,
    PlanningAuditPersistenceOutcomeEvidencePolicy,
    PlanningAuditPersistenceOutcomeEvidenceReason,
    PlanningAuditPersistenceOutcomeEvidenceSnapshot,
    PlanningAuditPersistenceOutcomeEvidenceSourceMode,
    PlanningAuditPersistenceOutcomeEvidenceStatus,
    StrategyAuditPersistenceOutcomeEvidenceGate,
    StrategyPlanningAuditPersistenceOutcomeEvidenceGate,
    assess_planning_audit_persistence_outcome_evidence,
    create_planning_audit_persistence_outcome_evidence,
)
from app.strategy.planning_audit_persistence_request import (
    StrategyPlanningAuditPersistenceRequestFactory,
)
from app.strategy.planning_audit_persistence_request_verification import (
    StrategyPlanningAuditPersistenceRequestVerificationFactory,
)
from app.strategy.planning_audit_record import (
    StrategyPlanningAuditRecordFactory,
)
from app.strategy.planning_audit_storage_adapter_assessment import (
    PlanningAuditStorageAdapterCapability,
    PlanningAuditStorageAdapterCapabilitySnapshot,
    StrategyPlanningAuditStorageAdapterAssessmentGate,
)
from app.strategy.planning_audit_storage_adapter_binding import (
    StrategyPlanningAuditStorageAdapterBindingFactory,
)
from app.strategy.planning_audit_storage_adapter_binding_verification import (
    StrategyPlanningAuditStorageAdapterBindingVerificationFactory,
)
from app.strategy.planning_audit_storage_adapter_contract import (
    StrategyPlanningAuditStorageAdapterContractFactory,
)
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageSnapshot,
    PlanningAuditStorageTarget,
    StrategyPlanningAuditStorageAdmissionGate,
)
from app.strategy.planning_audit_storage_blueprint import (
    StrategyPlanningAuditStorageBlueprintFactory,
)
from app.strategy.planning_audit_verification import (
    StrategyPlanningAuditVerificationFactory,
)
from app.strategy.planning_package import (
    StrategyPlanningPackageFactory,
)
from app.strategy.position_size_calculation import (
    StrategyPositionSizeCalculator,
)
from app.strategy.position_sizing_handoff import (
    PositionSizingHandoffDecision,
    StrategyPositionSizingHandoffFactory,
)
from app.strategy.position_sizing_specification import (
    PositionSizingSpecification,
    StrategyPositionSizingSpecificationGate,
)
from app.strategy.price_planning_admission import (
    StrategyPricePlanningAdmissionGate,
)
from app.strategy.price_planning_blueprint import (
    StrategyPricePlanningBlueprintFactory,
)
from app.strategy.price_reference_availability import (
    PriceReferenceAvailabilityItem,
    PriceReferenceAvailabilitySnapshot,
    StrategyPriceReferenceAvailabilityGate,
)
from app.strategy.price_reference_plan import (
    PriceReferenceRole,
    StrategyPriceReferencePlanFactory,
)
from app.strategy.price_reference_resolution import (
    PriceReferenceValueObservation,
    PriceReferenceValueSnapshot,
    StrategyPriceReferenceResolutionGate,
)
from app.strategy.reward_risk_analysis import (
    StrategyRewardRiskAnalysisGate,
)
from app.strategy.risk_budget_admission import (
    StrategyRiskBudgetAdmissionGate,
    StrategyRiskBudgetSnapshot,
)
from app.strategy.setup_candidate import (
    StrategySetupCandidateFactory,
)
from app.strategy.setup_candidate_quality import (
    StrategySetupCandidateQualityGate,
)
from app.strategy.setup_qualification import (
    StrategySetupQualificationGate,
)
from app.strategy.sized_trade_plan import (
    StrategySizedTradePlanFactory,
)

OBSERVED_AT = datetime(
    2026,
    7,
    26,
    20,
    0,
    tzinfo=timezone.utc,
)


def create_series(
    timeframe: TimeframeName,
    *,
    count: int = 8,
) -> ClosedCandleSeries:
    duration = get_timeframe_spec(timeframe).duration
    first_open = OBSERVED_AT - duration * count
    candles: list[ClosedCandle] = []

    for index in range(count):
        open_time = first_open + duration * index

        if index % 2 == 0:
            open_price = Decimal("100")
            close_price = Decimal("101")
        else:
            open_price = Decimal("101")
            close_price = Decimal("100")

        candles.append(
            ClosedCandle(
                broker_symbol="XAUUSDm",
                timeframe=timeframe,
                open_time=open_time,
                observed_at=open_time + duration,
                open=open_price,
                high=Decimal("102"),
                low=Decimal("98"),
                close=close_price,
                tick_volume=1000,
                spread=20,
                real_volume=0,
            )
        )

    return ClosedCandleSeries(
        broker_symbol="XAUUSDm",
        timeframe=timeframe,
        candles=tuple(candles),
    )


@lru_cache(maxsize=1)
def neutral_context():
    mapping = {timeframe: create_series(timeframe) for timeframe in GOLD_TIMEFRAME_HIERARCHY}

    return MultiTimeframeContextBuilder().build(mapping)


def handoff_decision_for(
    direction: DirectionalPermissionDirection,
    *,
    blocked: bool = False,
) -> PositionSizingHandoffDecision:
    if direction == DirectionalPermissionDirection.BULLISH:
        selected_bias = MarketStructureBias.BULLISH
        entry_value = Decimal("2350")
        stop_value = Decimal("2340")
        target_value = Decimal("2370")
    elif direction == DirectionalPermissionDirection.BEARISH:
        selected_bias = MarketStructureBias.BEARISH
        entry_value = Decimal("2350")
        stop_value = Decimal("2360")
        target_value = Decimal("2325")
    else:
        raise ValueError("Direction must be resolved.")

    context = replace(
        neutral_context(),
        structure_biases=tuple(
            (
                timeframe,
                (
                    selected_bias
                    if timeframe
                    in {
                        TimeframeName.H4,
                        TimeframeName.H1,
                        TimeframeName.M15,
                    }
                    else MarketStructureBias.NEUTRAL
                ),
            )
            for timeframe in GOLD_TIMEFRAME_HIERARCHY
        ),
    )
    analysis = MultiTimeframeAnalysisPipeline().evaluate_context(context)
    qualification = StrategySetupQualificationGate().evaluate(analysis)
    candidate = StrategySetupCandidateFactory().generate(qualification).candidate_required
    quality = StrategySetupCandidateQualityGate().evaluate(candidate)
    admission = StrategyPricePlanningAdmissionGate().evaluate(quality)
    blueprint = StrategyPricePlanningBlueprintFactory().generate(admission)
    plan_decision = StrategyPriceReferencePlanFactory().generate(blueprint)
    plan = plan_decision.plan_required
    availability = StrategyPriceReferenceAvailabilityGate().evaluate(
        plan_decision,
        PriceReferenceAvailabilitySnapshot(
            plan=plan,
            items=tuple(
                PriceReferenceAvailabilityItem(
                    requirement=requirement,
                    available=True,
                )
                for requirement in plan.requirements
            ),
        ),
    )
    values = {
        PriceReferenceRole.ENTRY: entry_value,
        PriceReferenceRole.STOP: stop_value,
        PriceReferenceRole.TARGET: target_value,
    }
    resolution = StrategyPriceReferenceResolutionGate().evaluate(
        availability,
        PriceReferenceValueSnapshot(
            plan=plan,
            observations=tuple(
                PriceReferenceValueObservation(
                    requirement=requirement,
                    value=values[requirement.role],
                )
                for requirement in (
                    availability.selected_entry,
                    availability.selected_stop,
                    availability.selected_target,
                )
                if requirement is not None
            ),
        ),
    )
    reward_risk = StrategyRewardRiskAnalysisGate().evaluate(resolution)
    risk_admission = StrategyRiskBudgetAdmissionGate().evaluate(
        reward_risk,
        StrategyRiskBudgetSnapshot(
            observed_at=OBSERVED_AT,
            account_equity=Decimal("10000"),
            proposed_risk_amount=Decimal("100"),
            current_aggregate_risk_amount=Decimal("0"),
            realized_daily_loss_amount=Decimal("0"),
            open_gold_positions=0,
            kill_switch_active=blocked,
        ),
    )

    return StrategyPositionSizingHandoffFactory().generate(risk_admission)


@lru_cache(maxsize=1)
def bullish_handoff() -> PositionSizingHandoffDecision:
    return handoff_decision_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_handoff() -> PositionSizingHandoffDecision:
    return handoff_decision_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_handoff() -> PositionSizingHandoffDecision:
    return handoff_decision_for(
        DirectionalPermissionDirection.BULLISH,
        blocked=True,
    )


def sizing_specification(
    *,
    observed_at: datetime = OBSERVED_AT,
    broker_symbol: str = "XAUUSDm",
    digits: int = 2,
    point_size: Decimal = Decimal("0.01"),
    tick_size: Decimal = Decimal("0.01"),
    tick_value: Decimal = Decimal("1"),
    contract_size: Decimal = Decimal("100"),
    volume_min: Decimal = Decimal("0.01"),
    volume_max: Decimal = Decimal("100"),
    volume_step: Decimal = Decimal("0.01"),
) -> PositionSizingSpecification:
    return PositionSizingSpecification(
        observed_at=observed_at,
        broker_symbol=broker_symbol,
        digits=digits,
        point_size=point_size,
        tick_size=tick_size,
        tick_value=tick_value,
        contract_size=contract_size,
        volume_min=volume_min,
        volume_max=volume_max,
        volume_step=volume_step,
    )


def specification_decision_for(
    direction: DirectionalPermissionDirection,
    *,
    blocked: bool = False,
    tick_size: Decimal = Decimal("0.01"),
    tick_value: Decimal = Decimal("1"),
    volume_min: Decimal = Decimal("0.01"),
    volume_max: Decimal = Decimal("100"),
    volume_step: Decimal = Decimal("0.01"),
):
    handoff = (
        blocked_handoff()
        if blocked
        else (
            bullish_handoff()
            if direction == DirectionalPermissionDirection.BULLISH
            else bearish_handoff()
        )
    )
    gate = StrategyPositionSizingSpecificationGate()

    if blocked:
        return gate.evaluate(handoff)

    return gate.evaluate(
        handoff,
        sizing_specification(
            tick_size=tick_size,
            tick_value=tick_value,
            volume_min=volume_min,
            volume_max=volume_max,
            volume_step=volume_step,
        ),
    )


@lru_cache(maxsize=1)
def bullish_specification_decision():
    return specification_decision_for(DirectionalPermissionDirection.BULLISH)


@lru_cache(maxsize=1)
def bearish_specification_decision():
    return specification_decision_for(DirectionalPermissionDirection.BEARISH)


@lru_cache(maxsize=1)
def blocked_specification_decision():
    return specification_decision_for(
        DirectionalPermissionDirection.BULLISH,
        blocked=True,
    )


@lru_cache(maxsize=1)
def bullish_calculation():
    return StrategyPositionSizeCalculator().calculate(bullish_specification_decision())


@lru_cache(maxsize=1)
def bearish_calculation():
    return StrategyPositionSizeCalculator().calculate(bearish_specification_decision())


@lru_cache(maxsize=1)
def blocked_calculation():
    return StrategyPositionSizeCalculator().calculate(blocked_specification_decision())


@lru_cache(maxsize=1)
def bullish_sized_plan():
    return StrategySizedTradePlanFactory().generate(bullish_calculation())


@lru_cache(maxsize=1)
def bearish_sized_plan():
    return StrategySizedTradePlanFactory().generate(bearish_calculation())


@lru_cache(maxsize=1)
def blocked_sized_plan():
    return StrategySizedTradePlanFactory().generate(blocked_calculation())


@lru_cache(maxsize=1)
def bullish_order_intent():
    return StrategyOrderIntentBlueprintFactory().generate(bullish_sized_plan())


@lru_cache(maxsize=1)
def bearish_order_intent():
    return StrategyOrderIntentBlueprintFactory().generate(bearish_sized_plan())


@lru_cache(maxsize=1)
def blocked_order_intent():
    return StrategyOrderIntentBlueprintFactory().generate(blocked_sized_plan())


@lru_cache(maxsize=1)
def bullish_execution_lock():
    return StrategyExecutionBoundaryLockFactory().generate(bullish_order_intent())


@lru_cache(maxsize=1)
def bearish_execution_lock():
    return StrategyExecutionBoundaryLockFactory().generate(bearish_order_intent())


@lru_cache(maxsize=1)
def blocked_execution_lock():
    return StrategyExecutionBoundaryLockFactory().generate(blocked_order_intent())


@lru_cache(maxsize=1)
def bullish_planning_package():
    return StrategyPlanningPackageFactory().generate(bullish_execution_lock())


@lru_cache(maxsize=1)
def bearish_planning_package():
    return StrategyPlanningPackageFactory().generate(bearish_execution_lock())


@lru_cache(maxsize=1)
def blocked_planning_package():
    return StrategyPlanningPackageFactory().generate(blocked_execution_lock())


@lru_cache(maxsize=1)
def bullish_audit_manifest():
    return StrategyPlanningAuditManifestFactory().generate(bullish_planning_package())


@lru_cache(maxsize=1)
def bearish_audit_manifest():
    return StrategyPlanningAuditManifestFactory().generate(bearish_planning_package())


@lru_cache(maxsize=1)
def blocked_audit_manifest():
    return StrategyPlanningAuditManifestFactory().generate(blocked_planning_package())


@lru_cache(maxsize=1)
def bullish_audit_record():
    return StrategyPlanningAuditRecordFactory().generate(bullish_audit_manifest())


@lru_cache(maxsize=1)
def bearish_audit_record():
    return StrategyPlanningAuditRecordFactory().generate(bearish_audit_manifest())


@lru_cache(maxsize=1)
def blocked_audit_record():
    return StrategyPlanningAuditRecordFactory().generate(blocked_audit_manifest())


@lru_cache(maxsize=1)
def bullish_audit_export():
    return StrategyPlanningAuditExportFactory().generate(bullish_audit_record())


@lru_cache(maxsize=1)
def bearish_audit_export():
    return StrategyPlanningAuditExportFactory().generate(bearish_audit_record())


@lru_cache(maxsize=1)
def blocked_audit_export():
    return StrategyPlanningAuditExportFactory().generate(blocked_audit_record())


@lru_cache(maxsize=1)
def bullish_verification():
    return StrategyPlanningAuditVerificationFactory().verify(bullish_audit_export())


@lru_cache(maxsize=1)
def bearish_verification():
    return StrategyPlanningAuditVerificationFactory().verify(bearish_audit_export())


@lru_cache(maxsize=1)
def blocked_verification():
    return StrategyPlanningAuditVerificationFactory().verify(blocked_audit_export())


def storage_snapshot(
    *,
    observed_at: datetime = OBSERVED_AT,
    target: PlanningAuditStorageTarget = (PlanningAuditStorageTarget.AUDIT_ARCHIVE),
    storage_enabled: bool = True,
    encryption_at_rest: bool = True,
    append_only: bool = True,
    idempotency_supported: bool = True,
    retention_days: int = 365,
    available_capacity_bytes: int = 1_000_000,
) -> PlanningAuditStorageSnapshot:
    return PlanningAuditStorageSnapshot(
        observed_at=observed_at,
        target=target,
        storage_enabled=storage_enabled,
        encryption_at_rest=encryption_at_rest,
        append_only=append_only,
        idempotency_supported=idempotency_supported,
        retention_days=retention_days,
        available_capacity_bytes=(available_capacity_bytes),
    )


@lru_cache(maxsize=1)
def bullish_storage_admission():
    return StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(),
    )


@lru_cache(maxsize=1)
def bearish_storage_admission():
    return StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bearish_verification(),
        storage_snapshot(),
    )


@lru_cache(maxsize=1)
def blocked_storage_admission():
    return StrategyPlanningAuditStorageAdmissionGate().evaluate(
        bullish_verification(),
        storage_snapshot(storage_enabled=False),
    )


@lru_cache(maxsize=1)
def bullish_storage_blueprint():
    return StrategyPlanningAuditStorageBlueprintFactory().generate(bullish_storage_admission())


@lru_cache(maxsize=1)
def bearish_storage_blueprint():
    return StrategyPlanningAuditStorageBlueprintFactory().generate(bearish_storage_admission())


@lru_cache(maxsize=1)
def blocked_storage_blueprint():
    return StrategyPlanningAuditStorageBlueprintFactory().generate(blocked_storage_admission())


@lru_cache(maxsize=1)
def bullish_adapter_contract():
    return StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bullish_storage_blueprint()
    )


@lru_cache(maxsize=1)
def bearish_adapter_contract():
    return StrategyPlanningAuditStorageAdapterContractFactory().generate(
        bearish_storage_blueprint()
    )


@lru_cache(maxsize=1)
def blocked_adapter_contract():
    return StrategyPlanningAuditStorageAdapterContractFactory().generate(
        blocked_storage_blueprint()
    )


def capability_snapshot(
    *,
    observed_at: datetime = OBSERVED_AT,
    adapter_name: str = "injected-audit-adapter",
    target: PlanningAuditStorageTarget = (PlanningAuditStorageTarget.AUDIT_ARCHIVE),
    active: bool = True,
    invocation_enabled: bool = False,
    capabilities: tuple[
        PlanningAuditStorageAdapterCapability,
        ...,
    ] = (
        PlanningAuditStorageAdapterCapability.APPEND_IF_ABSENT,
        PlanningAuditStorageAdapterCapability.RETURN_EXISTING_ON_DUPLICATE,
        PlanningAuditStorageAdapterCapability.VERIFY_BEFORE_ACCEPT,
        PlanningAuditStorageAdapterCapability.ENCRYPTION_AT_REST,
        PlanningAuditStorageAdapterCapability.IDEMPOTENCY_KEY_LOOKUP,
        PlanningAuditStorageAdapterCapability.RETENTION_POLICY_ENFORCEMENT,
        PlanningAuditStorageAdapterCapability.DRY_RUN_ONLY,
    ),
    maximum_payload_bytes: int = 1_000_000,
    maximum_retention_days: int = 3650,
) -> PlanningAuditStorageAdapterCapabilitySnapshot:
    return PlanningAuditStorageAdapterCapabilitySnapshot(
        observed_at=observed_at,
        adapter_name=adapter_name,
        target=target,
        active=active,
        invocation_enabled=invocation_enabled,
        capabilities=capabilities,
        maximum_payload_bytes=maximum_payload_bytes,
        maximum_retention_days=maximum_retention_days,
    )


@lru_cache(maxsize=1)
def bullish_adapter_assessment():
    return StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(),
    )


@lru_cache(maxsize=1)
def bearish_adapter_assessment():
    return StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bearish_adapter_contract(),
        capability_snapshot(),
    )


@lru_cache(maxsize=1)
def blocked_adapter_assessment():
    return StrategyPlanningAuditStorageAdapterAssessmentGate().assess(
        bullish_adapter_contract(),
        capability_snapshot(active=False),
    )


@lru_cache(maxsize=1)
def bullish_adapter_binding():
    return StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bullish_adapter_assessment()
    )


@lru_cache(maxsize=1)
def bearish_adapter_binding():
    return StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        bearish_adapter_assessment()
    )


@lru_cache(maxsize=1)
def blocked_adapter_binding():
    return StrategyPlanningAuditStorageAdapterBindingFactory().generate(
        blocked_adapter_assessment()
    )


@lru_cache(maxsize=1)
def bullish_binding_verification():
    return StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bullish_adapter_binding()
    )


@lru_cache(maxsize=1)
def bearish_binding_verification():
    return StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        bearish_adapter_binding()
    )


@lru_cache(maxsize=1)
def blocked_binding_verification():
    return StrategyPlanningAuditStorageAdapterBindingVerificationFactory().verify(
        blocked_adapter_binding()
    )


@lru_cache(maxsize=1)
def bullish_persistence_request():
    return StrategyPlanningAuditPersistenceRequestFactory().generate(bullish_binding_verification())


@lru_cache(maxsize=1)
def bearish_persistence_request():
    return StrategyPlanningAuditPersistenceRequestFactory().generate(bearish_binding_verification())


@lru_cache(maxsize=1)
def blocked_persistence_request():
    return StrategyPlanningAuditPersistenceRequestFactory().generate(blocked_binding_verification())


@lru_cache(maxsize=1)
def bullish_request_verification():
    return StrategyPlanningAuditPersistenceRequestVerificationFactory().verify(
        bullish_persistence_request()
    )


@lru_cache(maxsize=1)
def bearish_request_verification():
    return StrategyPlanningAuditPersistenceRequestVerificationFactory().verify(
        bearish_persistence_request()
    )


@lru_cache(maxsize=1)
def blocked_request_verification():
    return StrategyPlanningAuditPersistenceRequestVerificationFactory().verify(
        blocked_persistence_request()
    )


@lru_cache(maxsize=1)
def bullish_outcome_contract():
    return StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bullish_request_verification()
    )


@lru_cache(maxsize=1)
def bearish_outcome_contract():
    return StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        bearish_request_verification()
    )


@lru_cache(maxsize=1)
def blocked_outcome_contract():
    return StrategyPlanningAuditPersistenceOutcomeContractFactory().generate(
        blocked_request_verification()
    )


def outcome_evidence(
    contract_decision=None,
    *,
    observed_at=OBSERVED_AT,
    source_name="external-audit-store",
    outcome_kind=(PlanningAuditPersistenceOutcomeKind.CREATED),
    storage_record_reference="AUDIT-RECORD-0001",
    request_id=None,
    request_digest=None,
    content_length_bytes=None,
    content_digest=None,
    manifest_digest=None,
    idempotency_key=None,
    binding_receipt_digest=None,
    binding_id=None,
    snapshot_id=None,
    contract_id=None,
):
    selected = contract_decision or bullish_outcome_contract()
    contract = selected.contract_required

    return PlanningAuditPersistenceOutcomeEvidenceSnapshot.create(
        observed_at=observed_at,
        source_name=source_name,
        target=contract.target,
        outcome_kind=outcome_kind,
        storage_record_reference=(storage_record_reference),
        request_id=(request_id or contract.expected_request_id),
        request_digest=(request_digest or contract.expected_request_digest),
        content_length_bytes=(
            content_length_bytes
            if content_length_bytes is not None
            else (contract.expected_content_length_bytes)
        ),
        content_digest=(content_digest or contract.expected_content_digest),
        manifest_digest=(manifest_digest or contract.expected_manifest_digest),
        idempotency_key=(idempotency_key or contract.expected_idempotency_key),
        binding_receipt_digest=(
            binding_receipt_digest or (contract.expected_binding_receipt_digest)
        ),
        binding_id=(binding_id or contract.expected_binding_id),
        snapshot_id=(snapshot_id or contract.expected_snapshot_id),
        contract_id=(contract_id or contract.expected_contract_id),
    )


def test_default_policy_is_strict() -> None:
    policy = PlanningAuditPersistenceOutcomeEvidencePolicy()

    assert policy.require_non_stale_evidence is True


def test_policy_rejects_non_boolean_value() -> None:
    with pytest.raises(ValueError, match="boolean"):
        PlanningAuditPersistenceOutcomeEvidencePolicy(require_non_stale_evidence=1)


def test_gate_requires_policy_type() -> None:
    with pytest.raises(
        ValueError,
        match="PlanningAuditPersistenceOutcomeEvidencePolicy",
    ):
        StrategyPlanningAuditPersistenceOutcomeEvidenceGate(policy="invalid")


def test_invalid_contract_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditPersistenceOutcomeEvidenceError,
        match="INVALID_OUTCOME_CONTRACT_DECISION",
    ) as captured:
        (StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess("invalid"))

    assert captured.value.reason == (
        PlanningAuditPersistenceOutcomeEvidenceErrorReason.INVALID_OUTCOME_CONTRACT_DECISION
    )


def test_created_contract_requires_evidence() -> None:
    with pytest.raises(
        PlanningAuditPersistenceOutcomeEvidenceError,
        match="INVALID_EVIDENCE_SNAPSHOT",
    ):
        (StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(bullish_outcome_contract()))


def test_invalid_evidence_type_is_fail_safe() -> None:
    with pytest.raises(
        PlanningAuditPersistenceOutcomeEvidenceError,
        match="INVALID_EVIDENCE_SNAPSHOT",
    ):
        (
            StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
                bullish_outcome_contract(),
                "invalid",
            )
        )


def test_blocked_contract_requires_no_evidence() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        blocked_outcome_contract()
    )

    assert decision.is_blocked is True
    assert decision.evidence is None
    assert decision.has_evidence is False
    assert decision.reason == (
        PlanningAuditPersistenceOutcomeEvidenceReason.OUTCOME_CONTRACT_BLOCKED
    )
    assert decision.blockers == (
        PlanningAuditPersistenceOutcomeEvidenceBlocker.OUTCOME_CONTRACT_BLOCKED,
    )


def test_created_outcome_evidence_is_accepted() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(),
    )

    assert decision.status == (PlanningAuditPersistenceOutcomeEvidenceStatus.ACCEPTED)
    assert decision.reason == (PlanningAuditPersistenceOutcomeEvidenceReason.ACCEPTED)
    assert decision.blockers == ()
    assert decision.is_accepted is True


def test_existing_outcome_evidence_is_accepted() -> None:
    evidence = outcome_evidence(
        outcome_kind=(PlanningAuditPersistenceOutcomeKind.EXISTING),
        storage_record_reference=("AUDIT-RECORD-EXISTING-0001"),
    )
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        evidence,
    )

    assert decision.is_accepted is True
    assert evidence.indicates_existing is True
    assert evidence.indicates_created is False


def test_bearish_evidence_is_accepted() -> None:
    contract = bearish_outcome_contract()
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        contract,
        outcome_evidence(contract),
    )

    assert decision.is_accepted is True
    assert decision.direction == (DirectionalPermissionDirection.BEARISH)
    assert decision.side == StrategyOrderSide.SELL


def test_evidence_is_external_read_only() -> None:
    evidence = outcome_evidence()

    assert evidence.source_mode == (
        PlanningAuditPersistenceOutcomeEvidenceSourceMode.EXTERNAL_READ_ONLY
    )
    assert evidence.is_read_only_evidence is True
    assert evidence.has_adapter_instance is False
    assert evidence.can_submit_request is False
    assert evidence.can_invoke_adapter is False
    assert evidence.can_write_storage is False
    assert evidence.can_write_network is False


def test_decision_preserves_contract_and_evidence() -> None:
    contract = bullish_outcome_contract()
    evidence = outcome_evidence(contract)
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(contract, evidence)

    assert decision.outcome_contract is contract
    assert decision.contract is contract.contract_required
    assert decision.evidence is evidence
    assert decision.evidence_required is evidence


def test_decision_preserves_metadata() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(),
    )

    assert decision.broker_symbol == "XAUUSDm"
    assert decision.observed_at == OBSERVED_AT
    assert decision.direction == (DirectionalPermissionDirection.BULLISH)
    assert decision.side == StrategyOrderSide.BUY


def test_evidence_digest_matches_canonical_payload() -> None:
    evidence = outcome_evidence()
    expected = hashlib.sha256(evidence.canonical_payload.encode("utf-8")).hexdigest()

    assert evidence.evidence_digest == expected
    assert evidence.digest_algorithm == "SHA-256"


def test_same_time_evidence_is_current() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(observed_at=OBSERVED_AT),
    )

    assert decision.is_accepted is True


def test_stale_evidence_is_blocked() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(observed_at=(OBSERVED_AT - timedelta(seconds=1))),
    )

    assert decision.blockers == (PlanningAuditPersistenceOutcomeEvidenceBlocker.EVIDENCE_STALE,)


def test_stale_evidence_can_be_allowed() -> None:
    policy = PlanningAuditPersistenceOutcomeEvidencePolicy(require_non_stale_evidence=False)
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate(policy).assess(
        bullish_outcome_contract(),
        outcome_evidence(observed_at=(OBSERVED_AT - timedelta(seconds=1))),
    )

    assert decision.is_accepted is True


@pytest.mark.parametrize(
    ("overrides", "expected_blocker"),
    [
        (
            {"request_id": "foreign-request"},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.REQUEST_ID_MISMATCH,
        ),
        (
            {"request_digest": "0" * 64},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.REQUEST_DIGEST_MISMATCH,
        ),
        (
            {"content_length_bytes": 1},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.CONTENT_LENGTH_MISMATCH,
        ),
        (
            {"content_digest": "0" * 64},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.CONTENT_DIGEST_MISMATCH,
        ),
        (
            {"manifest_digest": "0" * 64},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.MANIFEST_DIGEST_MISMATCH,
        ),
        (
            {"idempotency_key": "0" * 64},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.IDEMPOTENCY_KEY_MISMATCH,
        ),
        (
            {"binding_receipt_digest": "0" * 64},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.BINDING_RECEIPT_MISMATCH,
        ),
        (
            {"binding_id": "foreign-binding"},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.BINDING_ID_MISMATCH,
        ),
        (
            {"snapshot_id": "foreign-snapshot"},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.SNAPSHOT_ID_MISMATCH,
        ),
        (
            {"contract_id": "foreign-contract"},
            PlanningAuditPersistenceOutcomeEvidenceBlocker.CONTRACT_ID_MISMATCH,
        ),
    ],
)
def test_individual_evidence_blockers(
    overrides,
    expected_blocker,
) -> None:
    evidence = outcome_evidence(**overrides)
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        evidence,
    )

    assert decision.is_blocked is True
    assert decision.blockers == (expected_blocker,)


def test_target_mismatch_is_blocked() -> None:
    source = outcome_evidence()
    foreign = object.__new__(PlanningAuditPersistenceOutcomeEvidenceSnapshot)

    for field_name in (
        "schema_version",
        "observed_at",
        "source_name",
        "source_mode",
        "outcome_kind",
        "storage_record_reference",
        "request_id",
        "request_digest",
        "content_length_bytes",
        "content_digest",
        "manifest_digest",
        "idempotency_key",
        "binding_receipt_digest",
        "binding_id",
        "snapshot_id",
        "contract_id",
        "evidence_digest",
    ):
        object.__setattr__(
            foreign,
            field_name,
            getattr(source, field_name),
        )

    object.__setattr__(
        foreign,
        "target",
        "FOREIGN_AUDIT_TARGET",
    )

    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        foreign,
    )

    assert decision.blockers == (PlanningAuditPersistenceOutcomeEvidenceBlocker.TARGET_MISMATCH,)


def test_multiple_blockers_are_deterministic() -> None:
    evidence = outcome_evidence(
        observed_at=(OBSERVED_AT - timedelta(seconds=1)),
        request_id="foreign-request",
        request_digest="0" * 64,
        content_length_bytes=1,
        content_digest="0" * 64,
        manifest_digest="0" * 64,
        idempotency_key="0" * 64,
        binding_receipt_digest="0" * 64,
        binding_id="foreign-binding",
        snapshot_id="foreign-snapshot",
        contract_id="foreign-contract",
    )
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        evidence,
    )

    assert decision.reason == (
        PlanningAuditPersistenceOutcomeEvidenceReason.MULTIPLE_EVIDENCE_BLOCKERS
    )
    assert decision.blockers == (
        PlanningAuditPersistenceOutcomeEvidenceBlocker.EVIDENCE_STALE,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.REQUEST_ID_MISMATCH,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.REQUEST_DIGEST_MISMATCH,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.CONTENT_LENGTH_MISMATCH,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.CONTENT_DIGEST_MISMATCH,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.MANIFEST_DIGEST_MISMATCH,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.IDEMPOTENCY_KEY_MISMATCH,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.BINDING_RECEIPT_MISMATCH,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.BINDING_ID_MISMATCH,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.SNAPSHOT_ID_MISMATCH,
        PlanningAuditPersistenceOutcomeEvidenceBlocker.CONTRACT_ID_MISMATCH,
    )


def test_accepted_evidence_continues_only_to_receipt_design() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(),
    )

    assert decision.has_accepted_external_outcome is True
    assert decision.can_continue_to_outcome_receipt_design is True


def test_blocked_evidence_cannot_continue() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(request_id="foreign-request"),
    )

    assert decision.has_accepted_external_outcome is False
    assert decision.can_continue_to_outcome_receipt_design is False


def test_decision_performs_no_write_or_execution() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(),
    )

    assert decision.has_adapter_instance is False
    assert decision.request_submission_authorized is False
    assert decision.adapter_invocation_authorized is False
    assert decision.storage_write_authorized is False
    assert decision.is_persisted is False
    assert decision.can_write_storage is False
    assert decision.can_write_network is False
    assert decision.execution_authorized is False
    assert decision.has_broker_request is False
    assert decision.can_submit_order is False
    assert decision.is_executable is False


@pytest.mark.parametrize(
    "attribute_name",
    [
        "adapter",
        "adapter_instance",
        "repository",
        "callable",
        "callback",
        "filename",
        "file_path",
        "directory",
        "connection",
        "cursor",
        "transaction",
        "sql",
        "insert",
        "save",
        "persist",
        "write",
        "write_file",
        "invoke",
        "execute",
        "upload",
        "post",
        "send",
        "submit_request",
        "request_handle",
        "order_request",
        "broker_ticket",
        "authorize",
        "submit",
        "send_order",
        "order_send",
    ],
)
def test_evidence_contains_no_implementation_surface(
    attribute_name,
) -> None:
    evidence = outcome_evidence()

    assert not hasattr(evidence, attribute_name)


@pytest.mark.parametrize(
    "overrides",
    [
        {"observed_at": "invalid"},
        {
            "observed_at": datetime(
                2026,
                7,
                26,
                20,
                0,
            )
        },
        {"source_name": ""},
        {"target": "AUDIT_ARCHIVE"},
        {"outcome_kind": "CREATED"},
        {"storage_record_reference": ""},
        {"storage_record_reference": "C:\\audit\\record.json"},
        {"content_length_bytes": 0},
        {"content_length_bytes": True},
    ],
)
def test_create_rejects_invalid_snapshot_values(
    overrides,
) -> None:
    contract = bullish_outcome_contract().contract_required
    values = {
        "observed_at": OBSERVED_AT,
        "source_name": "external-audit-store",
        "target": contract.target,
        "outcome_kind": (PlanningAuditPersistenceOutcomeKind.CREATED),
        "storage_record_reference": ("AUDIT-RECORD-0001"),
        "request_id": contract.expected_request_id,
        "request_digest": (contract.expected_request_digest),
        "content_length_bytes": (contract.expected_content_length_bytes),
        "content_digest": (contract.expected_content_digest),
        "manifest_digest": (contract.expected_manifest_digest),
        "idempotency_key": (contract.expected_idempotency_key),
        "binding_receipt_digest": (contract.expected_binding_receipt_digest),
        "binding_id": contract.expected_binding_id,
        "snapshot_id": contract.expected_snapshot_id,
        "contract_id": contract.expected_contract_id,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        (PlanningAuditPersistenceOutcomeEvidenceSnapshot.create(**values))


def test_direct_snapshot_rejects_wrong_digest() -> None:
    evidence = outcome_evidence()

    with pytest.raises(
        ValueError,
        match="evidence_digest",
    ):
        replace(
            evidence,
            evidence_digest="0" * 64,
        )


def test_direct_snapshot_rejects_uppercase_digest() -> None:
    evidence = outcome_evidence()

    with pytest.raises(ValueError, match="lowercase"):
        replace(
            evidence,
            evidence_digest="A" * 64,
        )


def test_evidence_stable_id_is_deterministic() -> None:
    evidence = outcome_evidence()

    assert evidence.stable_id == (
        f"{OBSERVED_AT.isoformat()}:"
        "external-audit-store:"
        "AUDIT_ARCHIVE:"
        "CREATED:"
        "RECORD[AUDIT-RECORD-0001]:"
        f"EVIDENCE_SHA256[{evidence.evidence_digest}]"
    )


def test_accepted_decision_stable_id_is_deterministic() -> None:
    contract = bullish_outcome_contract()
    evidence = outcome_evidence(contract)
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(contract, evidence)

    assert decision.stable_id == (
        f"{contract.stable_id}:"
        "PLANNING_AUDIT_PERSISTENCE_OUTCOME_EVIDENCE:"
        "ACCEPTED:ACCEPTED:NONE:"
        f"{evidence.stable_id}"
    )


def test_blocked_contract_stable_id_is_deterministic() -> None:
    contract = blocked_outcome_contract()
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(contract)

    assert decision.stable_id == (
        f"{contract.stable_id}:"
        "PLANNING_AUDIT_PERSISTENCE_OUTCOME_EVIDENCE:"
        "BLOCKED:OUTCOME_CONTRACT_BLOCKED:"
        "OUTCOME_CONTRACT_BLOCKED:"
        "NO_OUTCOME_EVIDENCE"
    )


def test_manual_decision_rejects_wrong_status() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(),
    )

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            status=(PlanningAuditPersistenceOutcomeEvidenceStatus.BLOCKED),
        )


def test_manual_decision_rejects_wrong_reason() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(),
    )

    with pytest.raises(ValueError, match="does not match"):
        replace(
            decision,
            reason=(PlanningAuditPersistenceOutcomeEvidenceReason.REQUEST_ID_MISMATCH),
        )


def test_manual_decision_rejects_missing_evidence() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(),
    )

    with pytest.raises(
        PlanningAuditPersistenceOutcomeEvidenceError,
        match="INVALID_EVIDENCE_SNAPSHOT",
    ):
        replace(
            decision,
            evidence=None,
        )


def test_manual_decision_rejects_duplicate_blockers() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(request_id="foreign-request"),
    )

    with pytest.raises(ValueError, match="duplicates"):
        replace(
            decision,
            blockers=(
                PlanningAuditPersistenceOutcomeEvidenceBlocker.REQUEST_ID_MISMATCH,
                PlanningAuditPersistenceOutcomeEvidenceBlocker.REQUEST_ID_MISMATCH,
            ),
        )


def test_policy_is_immutable() -> None:
    policy = PlanningAuditPersistenceOutcomeEvidencePolicy()

    with pytest.raises(FrozenInstanceError):
        policy.require_non_stale_evidence = False


def test_evidence_is_immutable() -> None:
    evidence = outcome_evidence()

    with pytest.raises(FrozenInstanceError):
        evidence.request_id = "modified"


def test_decision_is_immutable() -> None:
    decision = StrategyPlanningAuditPersistenceOutcomeEvidenceGate().assess(
        bullish_outcome_contract(),
        outcome_evidence(),
    )

    with pytest.raises(FrozenInstanceError):
        decision.status = PlanningAuditPersistenceOutcomeEvidenceStatus.BLOCKED


def test_assessment_is_deterministic() -> None:
    gate = StrategyPlanningAuditPersistenceOutcomeEvidenceGate()
    contract = bullish_outcome_contract()
    evidence = outcome_evidence(contract)

    assert gate.assess(
        contract,
        evidence,
    ) == gate.assess(
        contract,
        evidence,
    )


def test_function_api_delegates() -> None:
    decision = assess_planning_audit_persistence_outcome_evidence(
        bullish_outcome_contract(),
        outcome_evidence(),
    )

    assert decision.is_accepted is True


def test_create_function_delegates() -> None:
    contract = bullish_outcome_contract().contract_required
    evidence = create_planning_audit_persistence_outcome_evidence(
        observed_at=OBSERVED_AT,
        source_name="external-audit-store",
        target=contract.target,
        outcome_kind=(PlanningAuditPersistenceOutcomeKind.CREATED),
        storage_record_reference=("AUDIT-RECORD-0002"),
        request_id=contract.expected_request_id,
        request_digest=(contract.expected_request_digest),
        content_length_bytes=(contract.expected_content_length_bytes),
        content_digest=(contract.expected_content_digest),
        manifest_digest=(contract.expected_manifest_digest),
        idempotency_key=(contract.expected_idempotency_key),
        binding_receipt_digest=(contract.expected_binding_receipt_digest),
        binding_id=(contract.expected_binding_id),
        snapshot_id=(contract.expected_snapshot_id),
        contract_id=(contract.expected_contract_id),
    )

    assert evidence.is_read_only_evidence is True


def test_gate_alias_methods_delegate() -> None:
    gate = StrategyPlanningAuditPersistenceOutcomeEvidenceGate()
    contract = bullish_outcome_contract()
    evidence = outcome_evidence(contract)

    assert gate.evaluate(
        contract,
        evidence,
    ) == gate.assess(
        contract,
        evidence,
    )
    assert gate.check(
        contract,
        evidence,
    ) == gate.assess(
        contract,
        evidence,
    )


def test_public_aliases_are_preserved() -> None:
    assert AuditPersistenceOutcomeEvidenceBlocker is PlanningAuditPersistenceOutcomeEvidenceBlocker
    assert (
        AuditPersistenceOutcomeEvidenceDecision is PlanningAuditPersistenceOutcomeEvidenceDecision
    )
    assert (
        AuditPersistenceOutcomeEvidenceGate is StrategyPlanningAuditPersistenceOutcomeEvidenceGate
    )
    assert AuditPersistenceOutcomeEvidencePolicy is PlanningAuditPersistenceOutcomeEvidencePolicy
    assert AuditPersistenceOutcomeEvidenceReason is PlanningAuditPersistenceOutcomeEvidenceReason
    assert (
        AuditPersistenceOutcomeEvidenceSnapshot is PlanningAuditPersistenceOutcomeEvidenceSnapshot
    )
    assert (
        AuditPersistenceOutcomeEvidenceSourceMode
        is PlanningAuditPersistenceOutcomeEvidenceSourceMode
    )
    assert AuditPersistenceOutcomeEvidenceStatus is PlanningAuditPersistenceOutcomeEvidenceStatus
    assert (
        StrategyAuditPersistenceOutcomeEvidenceGate
        is StrategyPlanningAuditPersistenceOutcomeEvidenceGate
    )
