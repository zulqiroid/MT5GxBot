from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.order_intent_blueprint import (
    StrategyOrderSide,
)
from app.strategy.planning_audit_final_bundle import (
    PlanningAuditFinalBundleDecision,
    StrategyPlanningAuditFinalBundle,
)
from app.strategy.planning_audit_persistence_outcome_contract import (
    PlanningAuditPersistenceOutcomeKind,
)

PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION = "1.0"


class Phase8RunMode(str, Enum):
    SIMULATION_ONLY = "SIMULATION_ONLY"


class Phase8MarketDataMode(str, Enum):
    CLOSED_CANDLES_ONLY = "CLOSED_CANDLES_ONLY"


class Phase8Timeframe(str, Enum):
    H4 = "H4"
    H1 = "H1"
    M15 = "M15"
    M5 = "M5"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8HandoffStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8HandoffReason(str, Enum):
    CREATED = "CREATED"
    FINAL_BUNDLE_BLOCKED = "FINAL_BUNDLE_BLOCKED"


class Phase8HandoffBlocker(str, Enum):
    FINAL_BUNDLE_BLOCKED = "FINAL_BUNDLE_BLOCKED"


class Phase8DryRunScenarioStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8DryRunScenarioReason(str, Enum):
    CREATED = "CREATED"
    HANDOFF_BLOCKED = "HANDOFF_BLOCKED"


class Phase8DryRunScenarioBlocker(str, Enum):
    HANDOFF_BLOCKED = "HANDOFF_BLOCKED"


class Phase8SimulationAdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"
    BLOCKED = "BLOCKED"


class Phase8SimulationAdmissionReason(str, Enum):
    ADMITTED = "ADMITTED"
    SCENARIO_BLOCKED = "SCENARIO_BLOCKED"


class Phase8SimulationAdmissionBlocker(str, Enum):
    SCENARIO_BLOCKED = "SCENARIO_BLOCKED"


class Phase8DryRunPackageStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8DryRunPackageReason(str, Enum):
    CREATED = "CREATED"
    SIMULATION_ADMISSION_BLOCKED = "SIMULATION_ADMISSION_BLOCKED"


class Phase8DryRunPackageBlocker(str, Enum):
    SIMULATION_ADMISSION_BLOCKED = "SIMULATION_ADMISSION_BLOCKED"


class Phase8DryRunFoundationErrorReason(str, Enum):
    INVALID_FINAL_BUNDLE_DECISION = "INVALID_FINAL_BUNDLE_DECISION"
    INVALID_HANDOFF_DECISION = "INVALID_HANDOFF_DECISION"
    INVALID_SCENARIO_DECISION = "INVALID_SCENARIO_DECISION"
    INVALID_ADMISSION_DECISION = "INVALID_ADMISSION_DECISION"


class Phase8DryRunFoundationError(RuntimeError):
    """Structured Phase 8 dry-run foundation failure."""

    def __init__(
        self,
        reason: Phase8DryRunFoundationErrorReason,
        message: str,
    ) -> None:
        self.reason = Phase8DryRunFoundationErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Phase 8 dry-run foundation error [{self.reason.value}]: {self.message}")


def _non_empty_string(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} cannot contain line breaks.")

    return normalized


def _is_lowercase_sha256(value: str) -> bool:
    hexadecimal = set("0123456789abcdef")

    return (
        len(value) == 64
        and value == value.lower()
        and all(character in hexadecimal for character in value)
    )


def _sha256_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _is_gold_symbol(symbol: str) -> bool:
    return symbol.upper().startswith("XAUUSD")


def _assert_non_executable_boundary(
    subject: object,
    subject_name: str,
) -> None:
    expected_false_attributes = (
        "has_adapter_instance",
        "request_submission_authorized",
        "adapter_invocation_authorized",
        "storage_write_authorized",
        "can_write_storage",
        "can_write_network",
        "execution_authorized",
        "has_broker_request",
        "can_submit_order",
        "is_executable",
    )

    for attribute_name in expected_false_attributes:
        if not hasattr(subject, attribute_name):
            raise ValueError(f"{subject_name} must expose {attribute_name}.")

        if getattr(subject, attribute_name):
            raise ValueError(f"{subject_name}.{attribute_name} must remain False.")


def _canonical_handoff_payload(
    *,
    schema_version: str,
    final_bundle_id: str,
    final_bundle_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    outcome_kind: PlanningAuditPersistenceOutcomeKind,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"FINAL_BUNDLE_ID={final_bundle_id}",
            (f"FINAL_BUNDLE_DIGEST={final_bundle_digest}"),
            f"BROKER_SYMBOL={broker_symbol}",
            f"DIRECTION={direction.value}",
            f"SIDE={side.value}",
            f"OUTCOME_KIND={outcome_kind.value}",
        )
    )


def _canonical_scenario_payload(
    *,
    schema_version: str,
    handoff_id: str,
    run_mode: Phase8RunMode,
    market_data_mode: Phase8MarketDataMode,
    timeframes: tuple[Phase8Timeframe, ...],
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
) -> str:
    timeframe_fragment = ",".join(timeframe.value for timeframe in timeframes)

    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"HANDOFF_ID={handoff_id}",
            f"RUN_MODE={run_mode.value}",
            f"MARKET_DATA_MODE={market_data_mode.value}",
            f"TIMEFRAMES={timeframe_fragment}",
            f"BROKER_SYMBOL={broker_symbol}",
            f"DIRECTION={direction.value}",
            f"SIDE={side.value}",
        )
    )


def _canonical_admission_payload(
    *,
    schema_version: str,
    scenario_id: str,
    scenario_digest: str,
    broker_symbol: str,
    run_mode: Phase8RunMode,
    market_data_mode: Phase8MarketDataMode,
    timeframes: tuple[Phase8Timeframe, ...],
) -> str:
    timeframe_fragment = ",".join(timeframe.value for timeframe in timeframes)

    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"SCENARIO_ID={scenario_id}",
            f"SCENARIO_DIGEST={scenario_digest}",
            f"BROKER_SYMBOL={broker_symbol}",
            f"RUN_MODE={run_mode.value}",
            f"MARKET_DATA_MODE={market_data_mode.value}",
            f"TIMEFRAMES={timeframe_fragment}",
            "GOLD_ONLY=true",
            "CLOSED_CANDLES_ONLY=true",
            "SIMULATION_ONLY=true",
            "ORDER_SUBMISSION=false",
            "BROKER_WRITE=false",
        )
    )


def _canonical_package_payload(
    *,
    schema_version: str,
    final_bundle_id: str,
    final_bundle_digest: str,
    handoff_id: str,
    handoff_digest: str,
    scenario_id: str,
    scenario_digest: str,
    admission_id: str,
    admission_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    outcome_kind: PlanningAuditPersistenceOutcomeKind,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"FINAL_BUNDLE_ID={final_bundle_id}",
            (f"FINAL_BUNDLE_DIGEST={final_bundle_digest}"),
            f"HANDOFF_ID={handoff_id}",
            f"HANDOFF_DIGEST={handoff_digest}",
            f"SCENARIO_ID={scenario_id}",
            f"SCENARIO_DIGEST={scenario_digest}",
            f"ADMISSION_ID={admission_id}",
            f"ADMISSION_DIGEST={admission_digest}",
            f"BROKER_SYMBOL={broker_symbol}",
            f"DIRECTION={direction.value}",
            f"SIDE={side.value}",
            f"OUTCOME_KIND={outcome_kind.value}",
            "PHASE_8_BATCH_1_COMPLETE=true",
            "SIMULATION_ONLY=true",
            "ORDER_SUBMISSION=false",
            "BROKER_WRITE=false",
            "MT5_INITIALIZATION=false",
        )
    )


# ============================================================
# Step 8.1 — Phase 8 handoff
# ============================================================


@dataclass(frozen=True, slots=True)
class StrategyPhase8Handoff:
    final_bundle_decision: PlanningAuditFinalBundleDecision
    schema_version: str
    final_bundle_id: str
    final_bundle_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    outcome_kind: PlanningAuditPersistenceOutcomeKind
    handoff_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.final_bundle_decision,
            PlanningAuditFinalBundleDecision,
        ):
            raise ValueError("final_bundle_decision must be a PlanningAuditFinalBundleDecision.")

        if not self.final_bundle_decision.is_created:
            raise ValueError("A Phase 8 handoff requires a created final audit bundle.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION:
            raise ValueError("schema_version must match the Phase 8 dry-run foundation schema.")

        final_bundle_id = _non_empty_string(
            self.final_bundle_id,
            "final_bundle_id",
        )
        final_bundle_digest = _non_empty_string(
            self.final_bundle_digest,
            "final_bundle_digest",
        )
        broker_symbol = _non_empty_string(
            self.broker_symbol,
            "broker_symbol",
        )
        handoff_digest = _non_empty_string(
            self.handoff_digest,
            "handoff_digest",
        )

        if not _is_lowercase_sha256(final_bundle_digest):
            raise ValueError("final_bundle_digest must be a lowercase SHA-256 hexadecimal value.")

        if not _is_lowercase_sha256(handoff_digest):
            raise ValueError("handoff_digest must be a lowercase SHA-256 hexadecimal value.")

        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if not isinstance(self.side, StrategyOrderSide):
            raise ValueError("side must be a StrategyOrderSide member.")

        if not isinstance(
            self.outcome_kind,
            PlanningAuditPersistenceOutcomeKind,
        ):
            raise ValueError("outcome_kind must be a PlanningAuditPersistenceOutcomeKind member.")

        bundle = self.final_bundle_decision.bundle_required

        if final_bundle_id != bundle.stable_id:
            raise ValueError("final_bundle_id must match the final audit bundle.")

        if final_bundle_digest != bundle.bundle_digest:
            raise ValueError("final_bundle_digest must match the final audit bundle.")

        if broker_symbol != bundle.broker_symbol:
            raise ValueError("broker_symbol must match the final audit bundle.")

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Phase 8 handoff supports Gold/XAUUSD only.")

        if self.direction != bundle.direction:
            raise ValueError("direction must match the final audit bundle.")

        if self.side != bundle.side:
            raise ValueError("side must match the final audit bundle.")

        if self.outcome_kind != bundle.outcome_kind:
            raise ValueError("outcome_kind must match the final audit bundle.")

        if not bundle.phase_7_complete:
            raise ValueError("Phase 7 must be complete before the Phase 8 handoff.")

        if not bundle.can_continue_to_phase_8_design:
            raise ValueError("Final bundle does not permit Phase 8 design.")

        _assert_non_executable_boundary(
            bundle,
            "final audit bundle",
        )

        canonical_payload = _canonical_handoff_payload(
            schema_version=schema_version,
            final_bundle_id=final_bundle_id,
            final_bundle_digest=final_bundle_digest,
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            outcome_kind=self.outcome_kind,
        )

        if handoff_digest != _sha256_digest(canonical_payload):
            raise ValueError("handoff_digest does not match the canonical Phase 8 handoff payload.")

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "final_bundle_id",
            final_bundle_id,
        )
        object.__setattr__(
            self,
            "final_bundle_digest",
            final_bundle_digest,
        )
        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(
            self,
            "handoff_digest",
            handoff_digest,
        )

    @property
    def final_bundle(
        self,
    ) -> StrategyPlanningAuditFinalBundle:
        return self.final_bundle_decision.bundle_required

    @property
    def observed_at(self) -> datetime:
        return self.final_bundle.observed_at

    @property
    def canonical_payload(self) -> str:
        return _canonical_handoff_payload(
            schema_version=self.schema_version,
            final_bundle_id=self.final_bundle_id,
            final_bundle_digest=self.final_bundle_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            outcome_kind=self.outcome_kind,
        )

    @property
    def handoff_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_HANDOFF:"
            f"BUNDLE_SHA256[{self.final_bundle_digest}]:"
            f"HANDOFF_SHA256[{self.handoff_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.final_bundle_decision.stable_id}:{self.handoff_id}"

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def has_adapter_instance(self) -> bool:
        return False

    @property
    def request_submission_authorized(self) -> bool:
        return False

    @property
    def adapter_invocation_authorized(self) -> bool:
        return False

    @property
    def storage_write_authorized(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def can_write_network(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def can_submit_order(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Phase8HandoffDecision:
    final_bundle_decision: PlanningAuditFinalBundleDecision
    status: Phase8HandoffStatus
    reason: Phase8HandoffReason
    blockers: tuple[Phase8HandoffBlocker, ...]
    handoff: StrategyPhase8Handoff | None

    @property
    def is_created(self) -> bool:
        return self.status == Phase8HandoffStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def handoff_required(self) -> StrategyPhase8Handoff:
        if self.handoff is None:
            raise ValueError("No Phase 8 handoff was created.")

        return self.handoff

    @property
    def broker_symbol(self) -> str:
        return self.final_bundle_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.final_bundle_decision.direction

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.final_bundle_decision.stable_id}:"
            "PHASE_8_HANDOFF_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8HandoffFactory:
    def generate(
        self,
        final_bundle_decision: PlanningAuditFinalBundleDecision,
    ) -> Phase8HandoffDecision:
        if not isinstance(
            final_bundle_decision,
            PlanningAuditFinalBundleDecision,
        ):
            raise Phase8DryRunFoundationError(
                Phase8DryRunFoundationErrorReason.INVALID_FINAL_BUNDLE_DECISION,
                "final_bundle_decision must be a PlanningAuditFinalBundleDecision.",
            )

        if final_bundle_decision.is_blocked:
            return Phase8HandoffDecision(
                final_bundle_decision=final_bundle_decision,
                status=Phase8HandoffStatus.BLOCKED,
                reason=(Phase8HandoffReason.FINAL_BUNDLE_BLOCKED),
                blockers=(Phase8HandoffBlocker.FINAL_BUNDLE_BLOCKED,),
                handoff=None,
            )

        bundle = final_bundle_decision.bundle_required
        canonical_payload = _canonical_handoff_payload(
            schema_version=(PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION),
            final_bundle_id=bundle.stable_id,
            final_bundle_digest=bundle.bundle_digest,
            broker_symbol=bundle.broker_symbol,
            direction=bundle.direction,
            side=bundle.side,
            outcome_kind=bundle.outcome_kind,
        )

        handoff = StrategyPhase8Handoff(
            final_bundle_decision=final_bundle_decision,
            schema_version=(PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION),
            final_bundle_id=bundle.stable_id,
            final_bundle_digest=bundle.bundle_digest,
            broker_symbol=bundle.broker_symbol,
            direction=bundle.direction,
            side=bundle.side,
            outcome_kind=bundle.outcome_kind,
            handoff_digest=_sha256_digest(canonical_payload),
        )

        return Phase8HandoffDecision(
            final_bundle_decision=final_bundle_decision,
            status=Phase8HandoffStatus.CREATED,
            reason=Phase8HandoffReason.CREATED,
            blockers=(),
            handoff=handoff,
        )

    def build(
        self,
        final_bundle_decision: PlanningAuditFinalBundleDecision,
    ) -> Phase8HandoffDecision:
        return self.generate(final_bundle_decision)

    def evaluate(
        self,
        final_bundle_decision: PlanningAuditFinalBundleDecision,
    ) -> Phase8HandoffDecision:
        return self.generate(final_bundle_decision)


# ============================================================
# Step 8.2 — Closed-candle dry-run scenario
# ============================================================


@dataclass(frozen=True, slots=True)
class StrategyPhase8DryRunScenario:
    handoff_decision: Phase8HandoffDecision
    schema_version: str
    run_mode: Phase8RunMode
    market_data_mode: Phase8MarketDataMode
    timeframes: tuple[Phase8Timeframe, ...]
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    scenario_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.handoff_decision,
            Phase8HandoffDecision,
        ):
            raise ValueError("handoff_decision must be a Phase8HandoffDecision.")

        if not self.handoff_decision.is_created:
            raise ValueError("A dry-run scenario requires a created Phase 8 handoff.")

        if self.schema_version != PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION:
            raise ValueError("schema_version must match the Phase 8 dry-run foundation schema.")

        if self.run_mode != Phase8RunMode.SIMULATION_ONLY:
            raise ValueError("run_mode must remain SIMULATION_ONLY.")

        if self.market_data_mode != Phase8MarketDataMode.CLOSED_CANDLES_ONLY:
            raise ValueError("market_data_mode must remain CLOSED_CANDLES_ONLY.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must be H4, H1, M15, and M5 in deterministic order.")

        if not all(isinstance(timeframe, Phase8Timeframe) for timeframe in self.timeframes):
            raise ValueError("timeframes must contain Phase8Timeframe members.")

        broker_symbol = _non_empty_string(
            self.broker_symbol,
            "broker_symbol",
        )
        scenario_digest = _non_empty_string(
            self.scenario_digest,
            "scenario_digest",
        )
        handoff = self.handoff_decision.handoff_required

        if broker_symbol != handoff.broker_symbol:
            raise ValueError("broker_symbol must match the Phase 8 handoff.")

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Dry-run scenarios support Gold/XAUUSD only.")

        if self.direction != handoff.direction:
            raise ValueError("direction must match the Phase 8 handoff.")

        if self.side != handoff.side:
            raise ValueError("side must match the Phase 8 handoff.")

        if not _is_lowercase_sha256(scenario_digest):
            raise ValueError("scenario_digest must be a lowercase SHA-256 hexadecimal value.")

        canonical_payload = _canonical_scenario_payload(
            schema_version=self.schema_version,
            handoff_id=handoff.stable_id,
            run_mode=self.run_mode,
            market_data_mode=self.market_data_mode,
            timeframes=self.timeframes,
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
        )

        if scenario_digest != _sha256_digest(canonical_payload):
            raise ValueError(
                "scenario_digest does not match the canonical dry-run scenario payload."
            )

        _assert_non_executable_boundary(
            handoff,
            "Phase 8 handoff",
        )

        object.__setattr__(
            self,
            "broker_symbol",
            broker_symbol,
        )
        object.__setattr__(
            self,
            "scenario_digest",
            scenario_digest,
        )

    @property
    def handoff(self) -> StrategyPhase8Handoff:
        return self.handoff_decision.handoff_required

    @property
    def observed_at(self) -> datetime:
        return self.handoff.observed_at

    @property
    def canonical_payload(self) -> str:
        return _canonical_scenario_payload(
            schema_version=self.schema_version,
            handoff_id=self.handoff.stable_id,
            run_mode=self.run_mode,
            market_data_mode=self.market_data_mode,
            timeframes=self.timeframes,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
        )

    @property
    def scenario_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_DRY_RUN_SCENARIO:"
            f"{self.run_mode.value}:"
            f"{self.market_data_mode.value}:"
            f"SCENARIO_SHA256[{self.scenario_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.handoff_decision.stable_id}:{self.scenario_id}"

    @property
    def uses_closed_candles_only(self) -> bool:
        return True

    @property
    def uses_required_timeframes(self) -> bool:
        return self.timeframes == _REQUIRED_TIMEFRAMES

    @property
    def initializes_mt5(self) -> bool:
        return False

    @property
    def has_adapter_instance(self) -> bool:
        return False

    @property
    def request_submission_authorized(self) -> bool:
        return False

    @property
    def adapter_invocation_authorized(self) -> bool:
        return False

    @property
    def storage_write_authorized(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def can_write_network(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def can_submit_order(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Phase8DryRunScenarioDecision:
    handoff_decision: Phase8HandoffDecision
    status: Phase8DryRunScenarioStatus
    reason: Phase8DryRunScenarioReason
    blockers: tuple[Phase8DryRunScenarioBlocker, ...]
    scenario: StrategyPhase8DryRunScenario | None

    @property
    def is_created(self) -> bool:
        return self.status == Phase8DryRunScenarioStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def scenario_required(
        self,
    ) -> StrategyPhase8DryRunScenario:
        if self.scenario is None:
            raise ValueError("No Phase 8 dry-run scenario was created.")

        return self.scenario

    @property
    def broker_symbol(self) -> str:
        return self.handoff_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.handoff_decision.direction

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.handoff_decision.stable_id}:"
            "PHASE_8_DRY_RUN_SCENARIO_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8DryRunScenarioFactory:
    def generate(
        self,
        handoff_decision: Phase8HandoffDecision,
    ) -> Phase8DryRunScenarioDecision:
        if not isinstance(
            handoff_decision,
            Phase8HandoffDecision,
        ):
            raise Phase8DryRunFoundationError(
                Phase8DryRunFoundationErrorReason.INVALID_HANDOFF_DECISION,
                "handoff_decision must be a Phase8HandoffDecision.",
            )

        if handoff_decision.is_blocked:
            return Phase8DryRunScenarioDecision(
                handoff_decision=handoff_decision,
                status=Phase8DryRunScenarioStatus.BLOCKED,
                reason=(Phase8DryRunScenarioReason.HANDOFF_BLOCKED),
                blockers=(Phase8DryRunScenarioBlocker.HANDOFF_BLOCKED,),
                scenario=None,
            )

        handoff = handoff_decision.handoff_required
        canonical_payload = _canonical_scenario_payload(
            schema_version=(PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION),
            handoff_id=handoff.stable_id,
            run_mode=Phase8RunMode.SIMULATION_ONLY,
            market_data_mode=(Phase8MarketDataMode.CLOSED_CANDLES_ONLY),
            timeframes=_REQUIRED_TIMEFRAMES,
            broker_symbol=handoff.broker_symbol,
            direction=handoff.direction,
            side=handoff.side,
        )

        scenario = StrategyPhase8DryRunScenario(
            handoff_decision=handoff_decision,
            schema_version=(PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION),
            run_mode=Phase8RunMode.SIMULATION_ONLY,
            market_data_mode=(Phase8MarketDataMode.CLOSED_CANDLES_ONLY),
            timeframes=_REQUIRED_TIMEFRAMES,
            broker_symbol=handoff.broker_symbol,
            direction=handoff.direction,
            side=handoff.side,
            scenario_digest=_sha256_digest(canonical_payload),
        )

        return Phase8DryRunScenarioDecision(
            handoff_decision=handoff_decision,
            status=Phase8DryRunScenarioStatus.CREATED,
            reason=Phase8DryRunScenarioReason.CREATED,
            blockers=(),
            scenario=scenario,
        )

    def build(
        self,
        handoff_decision: Phase8HandoffDecision,
    ) -> Phase8DryRunScenarioDecision:
        return self.generate(handoff_decision)

    def evaluate(
        self,
        handoff_decision: Phase8HandoffDecision,
    ) -> Phase8DryRunScenarioDecision:
        return self.generate(handoff_decision)


# ============================================================
# Step 8.3 — Simulation admission gate
# ============================================================


@dataclass(frozen=True, slots=True)
class StrategyPhase8SimulationAdmission:
    scenario_decision: Phase8DryRunScenarioDecision
    schema_version: str
    scenario_id: str
    scenario_digest: str
    admission_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.scenario_decision,
            Phase8DryRunScenarioDecision,
        ):
            raise ValueError("scenario_decision must be a Phase8DryRunScenarioDecision.")

        if not self.scenario_decision.is_created:
            raise ValueError("Simulation admission requires a created dry-run scenario.")

        if self.schema_version != PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION:
            raise ValueError("schema_version must match the Phase 8 dry-run foundation schema.")

        scenario_id = _non_empty_string(
            self.scenario_id,
            "scenario_id",
        )
        scenario_digest = _non_empty_string(
            self.scenario_digest,
            "scenario_digest",
        )
        admission_digest = _non_empty_string(
            self.admission_digest,
            "admission_digest",
        )
        scenario = self.scenario_decision.scenario_required

        if scenario_id != scenario.stable_id:
            raise ValueError("scenario_id must match the dry-run scenario.")

        if scenario_digest != scenario.scenario_digest:
            raise ValueError("scenario_digest must match the dry-run scenario.")

        if not _is_lowercase_sha256(scenario_digest):
            raise ValueError("scenario_digest must be a lowercase SHA-256 hexadecimal value.")

        if not _is_lowercase_sha256(admission_digest):
            raise ValueError("admission_digest must be a lowercase SHA-256 hexadecimal value.")

        if not _is_gold_symbol(scenario.broker_symbol):
            raise ValueError("Simulation admission supports Gold/XAUUSD only.")

        if scenario.run_mode != Phase8RunMode.SIMULATION_ONLY:
            raise ValueError("Simulation admission requires SIMULATION_ONLY mode.")

        if scenario.market_data_mode != Phase8MarketDataMode.CLOSED_CANDLES_ONLY:
            raise ValueError("Simulation admission requires closed candles only.")

        if scenario.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("Simulation admission requires H4, H1, M15, and M5.")

        if scenario.initializes_mt5:
            raise ValueError("Simulation admission cannot initialize MT5.")

        _assert_non_executable_boundary(
            scenario,
            "dry-run scenario",
        )

        canonical_payload = _canonical_admission_payload(
            schema_version=self.schema_version,
            scenario_id=scenario_id,
            scenario_digest=scenario_digest,
            broker_symbol=scenario.broker_symbol,
            run_mode=scenario.run_mode,
            market_data_mode=scenario.market_data_mode,
            timeframes=scenario.timeframes,
        )

        if admission_digest != _sha256_digest(canonical_payload):
            raise ValueError(
                "admission_digest does not match the canonical simulation-admission payload."
            )

        object.__setattr__(
            self,
            "scenario_id",
            scenario_id,
        )
        object.__setattr__(
            self,
            "scenario_digest",
            scenario_digest,
        )
        object.__setattr__(
            self,
            "admission_digest",
            admission_digest,
        )

    @property
    def scenario(self) -> StrategyPhase8DryRunScenario:
        return self.scenario_decision.scenario_required

    @property
    def broker_symbol(self) -> str:
        return self.scenario.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.scenario.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.scenario.side

    @property
    def admission_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_SIMULATION_ADMISSION:"
            f"ADMISSION_SHA256[{self.admission_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.scenario_decision.stable_id}:{self.admission_id}"

    @property
    def is_admitted(self) -> bool:
        return True

    @property
    def initializes_mt5(self) -> bool:
        return False

    @property
    def has_adapter_instance(self) -> bool:
        return False

    @property
    def request_submission_authorized(self) -> bool:
        return False

    @property
    def adapter_invocation_authorized(self) -> bool:
        return False

    @property
    def storage_write_authorized(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def can_write_network(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def can_submit_order(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Phase8SimulationAdmissionDecision:
    scenario_decision: Phase8DryRunScenarioDecision
    status: Phase8SimulationAdmissionStatus
    reason: Phase8SimulationAdmissionReason
    blockers: tuple[
        Phase8SimulationAdmissionBlocker,
        ...,
    ]
    admission: StrategyPhase8SimulationAdmission | None

    @property
    def is_admitted(self) -> bool:
        return self.status == Phase8SimulationAdmissionStatus.ADMITTED

    @property
    def is_blocked(self) -> bool:
        return not self.is_admitted

    @property
    def admission_required(
        self,
    ) -> StrategyPhase8SimulationAdmission:
        if self.admission is None:
            raise ValueError("No Phase 8 simulation admission was created.")

        return self.admission

    @property
    def broker_symbol(self) -> str:
        return self.scenario_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.scenario_decision.direction

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.scenario_decision.stable_id}:"
            "PHASE_8_SIMULATION_ADMISSION_GATE:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8SimulationAdmissionGate:
    def assess(
        self,
        scenario_decision: Phase8DryRunScenarioDecision,
    ) -> Phase8SimulationAdmissionDecision:
        if not isinstance(
            scenario_decision,
            Phase8DryRunScenarioDecision,
        ):
            raise Phase8DryRunFoundationError(
                Phase8DryRunFoundationErrorReason.INVALID_SCENARIO_DECISION,
                "scenario_decision must be a Phase8DryRunScenarioDecision.",
            )

        if scenario_decision.is_blocked:
            return Phase8SimulationAdmissionDecision(
                scenario_decision=scenario_decision,
                status=(Phase8SimulationAdmissionStatus.BLOCKED),
                reason=(Phase8SimulationAdmissionReason.SCENARIO_BLOCKED),
                blockers=(Phase8SimulationAdmissionBlocker.SCENARIO_BLOCKED,),
                admission=None,
            )

        scenario = scenario_decision.scenario_required
        canonical_payload = _canonical_admission_payload(
            schema_version=(PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION),
            scenario_id=scenario.stable_id,
            scenario_digest=scenario.scenario_digest,
            broker_symbol=scenario.broker_symbol,
            run_mode=scenario.run_mode,
            market_data_mode=scenario.market_data_mode,
            timeframes=scenario.timeframes,
        )

        admission = StrategyPhase8SimulationAdmission(
            scenario_decision=scenario_decision,
            schema_version=(PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION),
            scenario_id=scenario.stable_id,
            scenario_digest=scenario.scenario_digest,
            admission_digest=_sha256_digest(canonical_payload),
        )

        return Phase8SimulationAdmissionDecision(
            scenario_decision=scenario_decision,
            status=(Phase8SimulationAdmissionStatus.ADMITTED),
            reason=(Phase8SimulationAdmissionReason.ADMITTED),
            blockers=(),
            admission=admission,
        )

    def evaluate(
        self,
        scenario_decision: Phase8DryRunScenarioDecision,
    ) -> Phase8SimulationAdmissionDecision:
        return self.assess(scenario_decision)

    def check(
        self,
        scenario_decision: Phase8DryRunScenarioDecision,
    ) -> Phase8SimulationAdmissionDecision:
        return self.assess(scenario_decision)


# ============================================================
# Step 8.4 — Immutable dry-run package
# ============================================================


@dataclass(frozen=True, slots=True)
class StrategyPhase8DryRunPackage:
    admission_decision: Phase8SimulationAdmissionDecision
    schema_version: str
    final_bundle_id: str
    final_bundle_digest: str
    handoff_id: str
    handoff_digest: str
    scenario_id: str
    scenario_digest: str
    admission_id: str
    admission_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    outcome_kind: PlanningAuditPersistenceOutcomeKind
    package_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.admission_decision,
            Phase8SimulationAdmissionDecision,
        ):
            raise ValueError("admission_decision must be a Phase8SimulationAdmissionDecision.")

        if not self.admission_decision.is_admitted:
            raise ValueError("A dry-run package requires an admitted simulation scenario.")

        if self.schema_version != PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION:
            raise ValueError("schema_version must match the Phase 8 dry-run foundation schema.")

        admission = self.admission_decision.admission_required
        scenario = admission.scenario
        handoff = scenario.handoff
        bundle = handoff.final_bundle

        comparisons = (
            (
                "final_bundle_id",
                self.final_bundle_id,
                bundle.stable_id,
            ),
            (
                "final_bundle_digest",
                self.final_bundle_digest,
                bundle.bundle_digest,
            ),
            (
                "handoff_id",
                self.handoff_id,
                handoff.stable_id,
            ),
            (
                "handoff_digest",
                self.handoff_digest,
                handoff.handoff_digest,
            ),
            (
                "scenario_id",
                self.scenario_id,
                scenario.stable_id,
            ),
            (
                "scenario_digest",
                self.scenario_digest,
                scenario.scenario_digest,
            ),
            (
                "admission_id",
                self.admission_id,
                admission.stable_id,
            ),
            (
                "admission_digest",
                self.admission_digest,
                admission.admission_digest,
            ),
            (
                "broker_symbol",
                self.broker_symbol,
                scenario.broker_symbol,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the complete Phase 8 dry-run lineage.")

        if self.direction != scenario.direction:
            raise ValueError("direction must match the dry-run scenario.")

        if self.side != scenario.side:
            raise ValueError("side must match the dry-run scenario.")

        if self.outcome_kind != handoff.outcome_kind:
            raise ValueError("outcome_kind must match the Phase 8 handoff.")

        digest_fields = (
            ("final_bundle_digest", self.final_bundle_digest),
            ("handoff_digest", self.handoff_digest),
            ("scenario_digest", self.scenario_digest),
            ("admission_digest", self.admission_digest),
            ("package_digest", self.package_digest),
        )

        for field_name, value in digest_fields:
            if not _is_lowercase_sha256(value):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        _assert_non_executable_boundary(
            admission,
            "simulation admission",
        )

        canonical_payload = _canonical_package_payload(
            schema_version=self.schema_version,
            final_bundle_id=self.final_bundle_id,
            final_bundle_digest=self.final_bundle_digest,
            handoff_id=self.handoff_id,
            handoff_digest=self.handoff_digest,
            scenario_id=self.scenario_id,
            scenario_digest=self.scenario_digest,
            admission_id=self.admission_id,
            admission_digest=self.admission_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            outcome_kind=self.outcome_kind,
        )

        if self.package_digest != _sha256_digest(canonical_payload):
            raise ValueError("package_digest does not match the canonical Phase 8 dry-run package.")

    @property
    def admission(
        self,
    ) -> StrategyPhase8SimulationAdmission:
        return self.admission_decision.admission_required

    @property
    def scenario(self) -> StrategyPhase8DryRunScenario:
        return self.admission.scenario

    @property
    def handoff(self) -> StrategyPhase8Handoff:
        return self.scenario.handoff

    @property
    def final_bundle(
        self,
    ) -> StrategyPlanningAuditFinalBundle:
        return self.handoff.final_bundle

    @property
    def observed_at(self) -> datetime:
        return self.final_bundle.observed_at

    @property
    def canonical_payload(self) -> str:
        return _canonical_package_payload(
            schema_version=self.schema_version,
            final_bundle_id=self.final_bundle_id,
            final_bundle_digest=self.final_bundle_digest,
            handoff_id=self.handoff_id,
            handoff_digest=self.handoff_digest,
            scenario_id=self.scenario_id,
            scenario_digest=self.scenario_digest,
            admission_id=self.admission_id,
            admission_digest=self.admission_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            outcome_kind=self.outcome_kind,
        )

    @property
    def package_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_DRY_RUN_PACKAGE:"
            f"{self.outcome_kind.value}:"
            f"PACKAGE_SHA256[{self.package_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.admission_decision.stable_id}:{self.package_id}"

    @property
    def phase_8_batch_1_complete(self) -> bool:
        return True

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def uses_closed_candles_only(self) -> bool:
        return True

    @property
    def initializes_mt5(self) -> bool:
        return False

    @property
    def performed_persistence(self) -> bool:
        return False

    @property
    def has_adapter_instance(self) -> bool:
        return False

    @property
    def request_submission_authorized(self) -> bool:
        return False

    @property
    def adapter_invocation_authorized(self) -> bool:
        return False

    @property
    def storage_write_authorized(self) -> bool:
        return False

    @property
    def can_write_storage(self) -> bool:
        return False

    @property
    def can_write_network(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def has_broker_request(self) -> bool:
        return False

    @property
    def can_submit_order(self) -> bool:
        return False

    @property
    def is_executable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Phase8DryRunPackageDecision:
    admission_decision: Phase8SimulationAdmissionDecision
    status: Phase8DryRunPackageStatus
    reason: Phase8DryRunPackageReason
    blockers: tuple[Phase8DryRunPackageBlocker, ...]
    package: StrategyPhase8DryRunPackage | None

    @property
    def is_created(self) -> bool:
        return self.status == Phase8DryRunPackageStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def package_required(
        self,
    ) -> StrategyPhase8DryRunPackage:
        if self.package is None:
            raise ValueError("No Phase 8 dry-run package was created.")

        return self.package

    @property
    def phase_8_batch_1_complete(self) -> bool:
        return self.is_created

    @property
    def broker_symbol(self) -> str:
        return self.admission_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.admission_decision.direction

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.admission_decision.stable_id}:"
            "PHASE_8_DRY_RUN_PACKAGE_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8DryRunPackageFactory:
    def generate(
        self,
        admission_decision: Phase8SimulationAdmissionDecision,
    ) -> Phase8DryRunPackageDecision:
        if not isinstance(
            admission_decision,
            Phase8SimulationAdmissionDecision,
        ):
            raise Phase8DryRunFoundationError(
                Phase8DryRunFoundationErrorReason.INVALID_ADMISSION_DECISION,
                "admission_decision must be a Phase8SimulationAdmissionDecision.",
            )

        if admission_decision.is_blocked:
            return Phase8DryRunPackageDecision(
                admission_decision=admission_decision,
                status=Phase8DryRunPackageStatus.BLOCKED,
                reason=(Phase8DryRunPackageReason.SIMULATION_ADMISSION_BLOCKED),
                blockers=(Phase8DryRunPackageBlocker.SIMULATION_ADMISSION_BLOCKED,),
                package=None,
            )

        admission = admission_decision.admission_required
        scenario = admission.scenario
        handoff = scenario.handoff
        bundle = handoff.final_bundle

        canonical_payload = _canonical_package_payload(
            schema_version=(PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION),
            final_bundle_id=bundle.stable_id,
            final_bundle_digest=bundle.bundle_digest,
            handoff_id=handoff.stable_id,
            handoff_digest=handoff.handoff_digest,
            scenario_id=scenario.stable_id,
            scenario_digest=scenario.scenario_digest,
            admission_id=admission.stable_id,
            admission_digest=admission.admission_digest,
            broker_symbol=scenario.broker_symbol,
            direction=scenario.direction,
            side=scenario.side,
            outcome_kind=handoff.outcome_kind,
        )

        package = StrategyPhase8DryRunPackage(
            admission_decision=admission_decision,
            schema_version=(PHASE_8_DRY_RUN_FOUNDATION_SCHEMA_VERSION),
            final_bundle_id=bundle.stable_id,
            final_bundle_digest=bundle.bundle_digest,
            handoff_id=handoff.stable_id,
            handoff_digest=handoff.handoff_digest,
            scenario_id=scenario.stable_id,
            scenario_digest=scenario.scenario_digest,
            admission_id=admission.stable_id,
            admission_digest=admission.admission_digest,
            broker_symbol=scenario.broker_symbol,
            direction=scenario.direction,
            side=scenario.side,
            outcome_kind=handoff.outcome_kind,
            package_digest=_sha256_digest(canonical_payload),
        )

        return Phase8DryRunPackageDecision(
            admission_decision=admission_decision,
            status=Phase8DryRunPackageStatus.CREATED,
            reason=Phase8DryRunPackageReason.CREATED,
            blockers=(),
            package=package,
        )

    def build(
        self,
        admission_decision: Phase8SimulationAdmissionDecision,
    ) -> Phase8DryRunPackageDecision:
        return self.generate(admission_decision)

    def evaluate(
        self,
        admission_decision: Phase8SimulationAdmissionDecision,
    ) -> Phase8DryRunPackageDecision:
        return self.generate(admission_decision)


def build_phase8_dry_run_foundation(
    final_bundle_decision: PlanningAuditFinalBundleDecision,
) -> Phase8DryRunPackageDecision:
    handoff = StrategyPhase8HandoffFactory().generate(final_bundle_decision)
    scenario = StrategyPhase8DryRunScenarioFactory().generate(handoff)
    admission = StrategyPhase8SimulationAdmissionGate().assess(scenario)

    return StrategyPhase8DryRunPackageFactory().generate(admission)


Phase8Handoff = StrategyPhase8Handoff
Phase8DryRunScenario = StrategyPhase8DryRunScenario
Phase8SimulationAdmission = StrategyPhase8SimulationAdmission
Phase8DryRunPackage = StrategyPhase8DryRunPackage
