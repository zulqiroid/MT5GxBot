from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.order_intent_blueprint import (
    StrategyOrderSide,
)
from app.strategy.phase8_closed_candle_data_contract import (
    StrategyPhase8ClosedCandleDataContract,
)
from app.strategy.phase8_closed_candle_snapshot import (
    StrategyPhase8ClosedCandleSnapshot,
)
from app.strategy.phase8_closed_candle_snapshot_verification import (
    StrategyPhase8ClosedCandleSnapshotVerificationReceipt,
)
from app.strategy.phase8_dry_run_foundation import (
    Phase8Timeframe,
    StrategyPhase8DryRunPackage,
)
from app.strategy.phase8_offline_replay_event_contract import (
    StrategyPhase8OfflineReplayEventContract,
)
from app.strategy.phase8_offline_replay_event_materialization import (
    Phase8OfflineReplayEventMaterializationDecision,
    StrategyPhase8OfflineReplayEventBatch,
)
from app.strategy.phase8_offline_replay_event_materialization_plan import (
    StrategyPhase8OfflineReplayEventMaterializationPlan,
)
from app.strategy.phase8_offline_replay_plan import (
    StrategyPhase8OfflineReplayPlan,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_SESSION_PLAN_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplaySessionMode(str, Enum):
    IMMUTABLE_IN_MEMORY_REPLAY = "IMMUTABLE_IN_MEMORY_REPLAY"


class Phase8OfflineReplayCursorMode(str, Enum):
    ZERO_BASED_FORWARD_ONLY = "ZERO_BASED_FORWARD_ONLY"


class Phase8OfflineReplayTransitionMode(str, Enum):
    ONE_EVENT_PER_TRANSITION = "ONE_EVENT_PER_TRANSITION"


class Phase8OfflineReplayInitialStateMode(str, Enum):
    FRESH_STRATEGY_STATE = "FRESH_STRATEGY_STATE"


class Phase8OfflineReplaySessionPlanStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplaySessionPlanReason(str, Enum):
    CREATED = "CREATED"
    EVENT_BATCH_BLOCKED = "EVENT_BATCH_BLOCKED"


class Phase8OfflineReplaySessionPlanBlocker(str, Enum):
    EVENT_BATCH_BLOCKED = "EVENT_BATCH_BLOCKED"


class Phase8OfflineReplaySessionPlanErrorReason(
    str,
    Enum,
):
    INVALID_EVENT_MATERIALIZATION_DECISION = "INVALID_EVENT_MATERIALIZATION_DECISION"


class Phase8OfflineReplaySessionPlanError(RuntimeError):
    """Structured offline replay-session plan failure."""

    def __init__(
        self,
        reason: Phase8OfflineReplaySessionPlanErrorReason,
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplaySessionPlanErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Phase 8 offline replay-session plan error [{self.reason.value}]: {self.message}"
        )


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


def _aware_datetime(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")

    return value


def _strict_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return value


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return value


def _is_lowercase_sha256(value: str) -> bool:
    hexadecimal = set("0123456789abcdef")

    return (
        len(value) == 64
        and value == value.lower()
        and all(character in hexadecimal for character in value)
    )


def _sha256_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _canonical_datetime(value: datetime) -> str:
    return value.isoformat(timespec="microseconds")


def _is_gold_symbol(symbol: str) -> bool:
    return symbol.upper().startswith("XAUUSD")


def _has_safe_boundary(subject: object) -> bool:
    required_false_attributes = (
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

    for attribute_name in required_false_attributes:
        if not hasattr(subject, attribute_name):
            return False

        if getattr(subject, attribute_name):
            return False

    for optional_false_attribute in (
        "fetches_data",
        "executes_simulation",
        "executes_replay",
        "evaluates_strategy",
        "emits_orders",
    ):
        if hasattr(subject, optional_false_attribute) and getattr(
            subject, optional_false_attribute
        ):
            return False

    if not hasattr(subject, "initializes_mt5"):
        return False

    if getattr(subject, "initializes_mt5"):
        return False

    return True


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplaySessionPolicy:
    """Strict future offline replay-session rules."""

    in_memory_only: bool = True
    forward_only_cursor: bool = True
    one_event_per_transition: bool = True
    fresh_strategy_state: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "in_memory_only",
            "forward_only_cursor",
            "one_event_per_transition",
            "fresh_strategy_state",
            "no_lookahead",
            "no_external_io",
        ):
            object.__setattr__(
                self,
                field_name,
                _strict_boolean(
                    getattr(self, field_name),
                    field_name,
                ),
            )

    @property
    def is_strict(self) -> bool:
        return all(
            (
                self.in_memory_only,
                self.forward_only_cursor,
                self.one_event_per_transition,
                self.fresh_strategy_state,
                self.no_lookahead,
                self.no_external_io,
            )
        )


def _canonical_session_payload(
    *,
    schema_version: str,
    event_batch_id: str,
    event_batch_digest: str,
    materialization_plan_id: str,
    materialization_plan_digest: str,
    event_contract_id: str,
    event_contract_digest: str,
    replay_plan_id: str,
    replay_plan_digest: str,
    specification_id: str,
    specification_digest: str,
    input_package_id: str,
    input_digest: str,
    snapshot_id: str,
    snapshot_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    timeframes: tuple[Phase8Timeframe, ...],
    session_mode: Phase8OfflineReplaySessionMode,
    cursor_mode: Phase8OfflineReplayCursorMode,
    transition_mode: Phase8OfflineReplayTransitionMode,
    initial_state_mode: Phase8OfflineReplayInitialStateMode,
    sequence_start: int,
    sequence_end: int,
    initial_cursor_index: int,
    total_event_count: int,
    first_event_time: datetime,
    last_event_time: datetime,
    policy: Phase8OfflineReplaySessionPolicy,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"EVENT_BATCH_ID={event_batch_id}",
            f"EVENT_BATCH_DIGEST={event_batch_digest}",
            (f"MATERIALIZATION_PLAN_ID={materialization_plan_id}"),
            (f"MATERIALIZATION_PLAN_DIGEST={materialization_plan_digest}"),
            f"EVENT_CONTRACT_ID={event_contract_id}",
            (f"EVENT_CONTRACT_DIGEST={event_contract_digest}"),
            f"REPLAY_PLAN_ID={replay_plan_id}",
            f"REPLAY_PLAN_DIGEST={replay_plan_digest}",
            f"SPECIFICATION_ID={specification_id}",
            (f"SPECIFICATION_DIGEST={specification_digest}"),
            f"INPUT_PACKAGE_ID={input_package_id}",
            f"INPUT_DIGEST={input_digest}",
            f"SNAPSHOT_ID={snapshot_id}",
            f"SNAPSHOT_DIGEST={snapshot_digest}",
            f"BROKER_SYMBOL={broker_symbol}",
            f"DIRECTION={direction.value}",
            f"SIDE={side.value}",
            f"SOURCE_NAME={source_name}",
            (f"CAPTURED_AT={_canonical_datetime(captured_at)}"),
            ("TIMEFRAMES=" + ",".join(timeframe.value for timeframe in timeframes)),
            f"SESSION_MODE={session_mode.value}",
            f"CURSOR_MODE={cursor_mode.value}",
            f"TRANSITION_MODE={transition_mode.value}",
            (f"INITIAL_STATE_MODE={initial_state_mode.value}"),
            f"SEQUENCE_START={sequence_start}",
            f"SEQUENCE_END={sequence_end}",
            f"INITIAL_CURSOR_INDEX={initial_cursor_index}",
            f"TOTAL_EVENT_COUNT={total_event_count}",
            (f"FIRST_EVENT_TIME={_canonical_datetime(first_event_time)}"),
            (f"LAST_EVENT_TIME={_canonical_datetime(last_event_time)}"),
            (f"IN_MEMORY_ONLY={str(policy.in_memory_only).lower()}"),
            (f"FORWARD_ONLY_CURSOR={str(policy.forward_only_cursor).lower()}"),
            (f"ONE_EVENT_PER_TRANSITION={str(policy.one_event_per_transition).lower()}"),
            (f"FRESH_STRATEGY_STATE={str(policy.fresh_strategy_state).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "SESSION_PLANNED=true",
            "SESSION_STARTED=false",
            "REPLAY_EXECUTION=false",
            "STRATEGY_EVALUATION=false",
            "SIMULATION_EXECUTION=false",
            "DATA_FETCH=false",
            "MT5_INITIALIZATION=false",
            "ADAPTER_INVOCATION=false",
            "STORAGE_WRITE=false",
            "NETWORK_WRITE=false",
            "BROKER_WRITE=false",
            "ORDER_SUBMISSION=false",
            "EXECUTION_AUTHORIZED=false",
        )
    )


@dataclass(frozen=True, slots=True)
class StrategyPhase8OfflineReplaySessionPlan:
    """
    Immutable plan for a future in-memory replay session.

    It defines session boundaries, cursor rules and initial
    state only. It does not start replay, consume events,
    evaluate strategy logic, initialize MT5, write storage,
    contact a broker, or submit an order.
    """

    event_materialization_decision: Phase8OfflineReplayEventMaterializationDecision = field(
        repr=False
    )
    policy: Phase8OfflineReplaySessionPolicy
    schema_version: str
    event_batch_id: str
    event_batch_digest: str
    materialization_plan_id: str
    materialization_plan_digest: str
    event_contract_id: str
    event_contract_digest: str
    replay_plan_id: str
    replay_plan_digest: str
    specification_id: str
    specification_digest: str
    input_package_id: str
    input_digest: str
    snapshot_id: str
    snapshot_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    source_name: str
    captured_at: datetime
    timeframes: tuple[Phase8Timeframe, ...]
    session_mode: Phase8OfflineReplaySessionMode
    cursor_mode: Phase8OfflineReplayCursorMode
    transition_mode: Phase8OfflineReplayTransitionMode
    initial_state_mode: Phase8OfflineReplayInitialStateMode
    sequence_start: int
    sequence_end: int
    initial_cursor_index: int
    total_event_count: int
    first_event_time: datetime
    last_event_time: datetime
    session_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.event_materialization_decision,
            Phase8OfflineReplayEventMaterializationDecision,
        ):
            raise ValueError(
                "event_materialization_decision must be a "
                "Phase8OfflineReplayEventMaterializationDecision."
            )

        if not self.event_materialization_decision.is_created:
            raise ValueError("A replay-session plan requires a created offline replay-event batch.")

        if not isinstance(
            self.policy,
            Phase8OfflineReplaySessionPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplaySessionPolicy.")

        if not self.policy.is_strict:
            raise ValueError(
                "Replay-session policy must remain strict, forward-only and no-lookahead."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PHASE_8_OFFLINE_REPLAY_SESSION_PLAN_SCHEMA_VERSION:
            raise ValueError(
                "schema_version must match the current offline replay-session plan schema."
            )

        string_fields = (
            ("event_batch_id", self.event_batch_id),
            ("event_batch_digest", self.event_batch_digest),
            (
                "materialization_plan_id",
                self.materialization_plan_id,
            ),
            (
                "materialization_plan_digest",
                self.materialization_plan_digest,
            ),
            ("event_contract_id", self.event_contract_id),
            (
                "event_contract_digest",
                self.event_contract_digest,
            ),
            ("replay_plan_id", self.replay_plan_id),
            (
                "replay_plan_digest",
                self.replay_plan_digest,
            ),
            ("specification_id", self.specification_id),
            (
                "specification_digest",
                self.specification_digest,
            ),
            ("input_package_id", self.input_package_id),
            ("input_digest", self.input_digest),
            ("snapshot_id", self.snapshot_id),
            ("snapshot_digest", self.snapshot_digest),
            ("broker_symbol", self.broker_symbol),
            ("source_name", self.source_name),
            ("session_digest", self.session_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "event_batch_digest",
            "materialization_plan_digest",
            "event_contract_digest",
            "replay_plan_digest",
            "specification_digest",
            "input_digest",
            "snapshot_digest",
            "session_digest",
        ):
            if not _is_lowercase_sha256(normalized_strings[field_name]):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if not isinstance(self.side, StrategyOrderSide):
            raise ValueError("side must be a StrategyOrderSide member.")

        enum_fields = (
            (
                "session_mode",
                self.session_mode,
                Phase8OfflineReplaySessionMode,
            ),
            (
                "cursor_mode",
                self.cursor_mode,
                Phase8OfflineReplayCursorMode,
            ),
            (
                "transition_mode",
                self.transition_mode,
                Phase8OfflineReplayTransitionMode,
            ),
            (
                "initial_state_mode",
                self.initial_state_mode,
                Phase8OfflineReplayInitialStateMode,
            ),
        )

        for field_name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(f"{field_name} must be a {enum_type.__name__} member.")

        if self.session_mode != (Phase8OfflineReplaySessionMode.IMMUTABLE_IN_MEMORY_REPLAY):
            raise ValueError("session_mode must remain IMMUTABLE_IN_MEMORY_REPLAY.")

        if self.cursor_mode != (Phase8OfflineReplayCursorMode.ZERO_BASED_FORWARD_ONLY):
            raise ValueError("cursor_mode must remain ZERO_BASED_FORWARD_ONLY.")

        if self.transition_mode != (Phase8OfflineReplayTransitionMode.ONE_EVENT_PER_TRANSITION):
            raise ValueError("transition_mode must remain ONE_EVENT_PER_TRANSITION.")

        if self.initial_state_mode != (Phase8OfflineReplayInitialStateMode.FRESH_STRATEGY_STATE):
            raise ValueError("initial_state_mode must remain FRESH_STRATEGY_STATE.")

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )
        first_event_time = _aware_datetime(
            self.first_event_time,
            "first_event_time",
        )
        last_event_time = _aware_datetime(
            self.last_event_time,
            "last_event_time",
        )

        if last_event_time < first_event_time:
            raise ValueError("last_event_time cannot precede first_event_time.")

        if last_event_time > captured_at:
            raise ValueError("last_event_time cannot exceed captured_at.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        if not all(isinstance(timeframe, Phase8Timeframe) for timeframe in self.timeframes):
            raise ValueError("timeframes must contain Phase8Timeframe members.")

        sequence_start = _non_negative_integer(
            self.sequence_start,
            "sequence_start",
        )
        sequence_end = _non_negative_integer(
            self.sequence_end,
            "sequence_end",
        )
        initial_cursor_index = _non_negative_integer(
            self.initial_cursor_index,
            "initial_cursor_index",
        )
        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )

        if sequence_start != 0:
            raise ValueError("sequence_start must be zero.")

        if sequence_end != total_event_count - 1:
            raise ValueError("sequence_end must equal total_event_count minus one.")

        if initial_cursor_index != sequence_start:
            raise ValueError("initial_cursor_index must equal sequence_start.")

        event_batch = self.event_materialization_decision.batch_required
        materialization_plan = event_batch.materialization_plan
        event_contract = event_batch.event_contract
        replay_plan = event_batch.replay_plan
        specification = event_batch.specification
        input_package = event_batch.input_package
        snapshot = event_batch.snapshot

        comparisons = (
            (
                "event_batch_id",
                normalized_strings["event_batch_id"],
                event_batch.stable_id,
            ),
            (
                "event_batch_digest",
                normalized_strings["event_batch_digest"],
                event_batch.batch_digest,
            ),
            (
                "materialization_plan_id",
                normalized_strings["materialization_plan_id"],
                materialization_plan.stable_id,
            ),
            (
                "materialization_plan_digest",
                normalized_strings["materialization_plan_digest"],
                materialization_plan.materialization_digest,
            ),
            (
                "event_contract_id",
                normalized_strings["event_contract_id"],
                event_contract.stable_id,
            ),
            (
                "event_contract_digest",
                normalized_strings["event_contract_digest"],
                event_contract.contract_digest,
            ),
            (
                "replay_plan_id",
                normalized_strings["replay_plan_id"],
                replay_plan.stable_id,
            ),
            (
                "replay_plan_digest",
                normalized_strings["replay_plan_digest"],
                replay_plan.plan_digest,
            ),
            (
                "specification_id",
                normalized_strings["specification_id"],
                specification.stable_id,
            ),
            (
                "specification_digest",
                normalized_strings["specification_digest"],
                specification.specification_digest,
            ),
            (
                "input_package_id",
                normalized_strings["input_package_id"],
                input_package.stable_id,
            ),
            (
                "input_digest",
                normalized_strings["input_digest"],
                input_package.input_digest,
            ),
            (
                "snapshot_id",
                normalized_strings["snapshot_id"],
                snapshot.stable_id,
            ),
            (
                "snapshot_digest",
                normalized_strings["snapshot_digest"],
                snapshot.snapshot_digest,
            ),
            (
                "broker_symbol",
                normalized_strings["broker_symbol"],
                event_batch.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                event_batch.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable replay-event batch lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Replay-session plans support Gold/XAUUSD only.")

        if self.direction != event_batch.direction:
            raise ValueError("direction must match the replay-event batch.")

        if self.side != event_batch.side:
            raise ValueError("side must match the replay-event batch.")

        if captured_at != event_batch.captured_at:
            raise ValueError("captured_at must match the replay-event batch.")

        if self.timeframes != event_batch.timeframes:
            raise ValueError("timeframes must match the replay-event batch.")

        if sequence_start != event_batch.sequence_start:
            raise ValueError("sequence_start must match the replay-event batch.")

        if sequence_end != event_batch.sequence_end:
            raise ValueError("sequence_end must match the replay-event batch.")

        if total_event_count != event_batch.total_event_count:
            raise ValueError("total_event_count must match the replay-event batch.")

        if first_event_time != event_batch.first_event_time:
            raise ValueError("first_event_time must match the replay-event batch.")

        if last_event_time != event_batch.last_event_time:
            raise ValueError("last_event_time must match the replay-event batch.")

        if not event_batch.in_memory_only:
            raise ValueError("Replay-event batch must remain in-memory only.")

        if event_batch.executes_replay:
            raise ValueError("Replay-event batch cannot execute replay.")

        if event_batch.evaluates_strategy:
            raise ValueError("Replay-event batch cannot evaluate strategy logic.")

        if not materialization_plan.no_lookahead:
            raise ValueError("Materialization plan must remain no-lookahead.")

        safe_subjects = (
            self.event_materialization_decision,
            event_batch,
            event_batch.materialization_plan_decision,
            materialization_plan,
            materialization_plan.event_contract_decision,
            event_contract,
            event_contract.plan_decision,
            replay_plan,
            replay_plan.specification_decision,
            specification,
            specification.input_decision,
            input_package,
            event_batch.verification_receipt,
            snapshot,
            event_batch.contract,
            event_batch.dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Replay-session lineage violates the non-I/O or non-execution boundary."
            )

        canonical_payload = _canonical_session_payload(
            schema_version=schema_version,
            event_batch_id=normalized_strings["event_batch_id"],
            event_batch_digest=normalized_strings["event_batch_digest"],
            materialization_plan_id=normalized_strings["materialization_plan_id"],
            materialization_plan_digest=(normalized_strings["materialization_plan_digest"]),
            event_contract_id=normalized_strings["event_contract_id"],
            event_contract_digest=normalized_strings["event_contract_digest"],
            replay_plan_id=normalized_strings["replay_plan_id"],
            replay_plan_digest=normalized_strings["replay_plan_digest"],
            specification_id=normalized_strings["specification_id"],
            specification_digest=normalized_strings["specification_digest"],
            input_package_id=normalized_strings["input_package_id"],
            input_digest=normalized_strings["input_digest"],
            snapshot_id=normalized_strings["snapshot_id"],
            snapshot_digest=normalized_strings["snapshot_digest"],
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=normalized_strings["source_name"],
            captured_at=captured_at,
            timeframes=self.timeframes,
            session_mode=self.session_mode,
            cursor_mode=self.cursor_mode,
            transition_mode=self.transition_mode,
            initial_state_mode=self.initial_state_mode,
            sequence_start=sequence_start,
            sequence_end=sequence_end,
            initial_cursor_index=initial_cursor_index,
            total_event_count=total_event_count,
            first_event_time=first_event_time,
            last_event_time=last_event_time,
            policy=self.policy,
        )

        if normalized_strings["session_digest"] != _sha256_digest(canonical_payload):
            raise ValueError(
                "session_digest does not match the canonical offline replay-session plan."
            )

        for field_name, value in normalized_strings.items():
            object.__setattr__(
                self,
                field_name,
                value,
            )

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "captured_at",
            captured_at,
        )
        object.__setattr__(
            self,
            "sequence_start",
            sequence_start,
        )
        object.__setattr__(
            self,
            "sequence_end",
            sequence_end,
        )
        object.__setattr__(
            self,
            "initial_cursor_index",
            initial_cursor_index,
        )
        object.__setattr__(
            self,
            "total_event_count",
            total_event_count,
        )
        object.__setattr__(
            self,
            "first_event_time",
            first_event_time,
        )
        object.__setattr__(
            self,
            "last_event_time",
            last_event_time,
        )

    @property
    def event_batch(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        return self.event_materialization_decision.batch_required

    @property
    def materialization_plan(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        return self.event_batch.materialization_plan

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.event_batch.event_contract

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.event_batch.replay_plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.event_batch.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.event_batch.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.event_batch.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.event_batch.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.event_batch.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.event_batch.dry_run_package

    @property
    def canonical_payload(self) -> str:
        return _canonical_session_payload(
            schema_version=self.schema_version,
            event_batch_id=self.event_batch_id,
            event_batch_digest=self.event_batch_digest,
            materialization_plan_id=(self.materialization_plan_id),
            materialization_plan_digest=(self.materialization_plan_digest),
            event_contract_id=self.event_contract_id,
            event_contract_digest=(self.event_contract_digest),
            replay_plan_id=self.replay_plan_id,
            replay_plan_digest=self.replay_plan_digest,
            specification_id=self.specification_id,
            specification_digest=(self.specification_digest),
            input_package_id=self.input_package_id,
            input_digest=self.input_digest,
            snapshot_id=self.snapshot_id,
            snapshot_digest=self.snapshot_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=self.source_name,
            captured_at=self.captured_at,
            timeframes=self.timeframes,
            session_mode=self.session_mode,
            cursor_mode=self.cursor_mode,
            transition_mode=self.transition_mode,
            initial_state_mode=self.initial_state_mode,
            sequence_start=self.sequence_start,
            sequence_end=self.sequence_end,
            initial_cursor_index=self.initial_cursor_index,
            total_event_count=self.total_event_count,
            first_event_time=self.first_event_time,
            last_event_time=self.last_event_time,
            policy=self.policy,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def plans_replay_session(self) -> bool:
        return True

    @property
    def in_memory_only(self) -> bool:
        return self.policy.in_memory_only

    @property
    def forward_only(self) -> bool:
        return self.policy.forward_only_cursor

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def starts_at_first_event(self) -> bool:
        return self.initial_cursor_index == self.sequence_start

    @property
    def starts_replay(self) -> bool:
        return False

    @property
    def consumes_events(self) -> bool:
        return False

    @property
    def executes_replay(self) -> bool:
        return False

    @property
    def evaluates_strategy(self) -> bool:
        return False

    @property
    def executes_simulation(self) -> bool:
        return False

    @property
    def emits_orders(self) -> bool:
        return False

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def can_continue_to_offline_replay_session_contract(
        self,
    ) -> bool:
        return True

    @property
    def fetches_data(self) -> bool:
        return False

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

    @property
    def session_plan_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_SESSION_PLAN:"
            f"SESSION_SHA256[{self.session_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.event_materialization_decision.stable_id}:{self.session_plan_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplaySessionPlanDecision:
    """Immutable replay-session plan decision."""

    event_materialization_decision: Phase8OfflineReplayEventMaterializationDecision = field(
        repr=False
    )
    status: Phase8OfflineReplaySessionPlanStatus
    reason: Phase8OfflineReplaySessionPlanReason
    blockers: tuple[
        Phase8OfflineReplaySessionPlanBlocker,
        ...,
    ]
    plan: StrategyPhase8OfflineReplaySessionPlan | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.event_materialization_decision,
            Phase8OfflineReplayEventMaterializationDecision,
        ):
            raise ValueError(
                "event_materialization_decision must be a "
                "Phase8OfflineReplayEventMaterializationDecision."
            )

        try:
            status = Phase8OfflineReplaySessionPlanStatus(self.status)
            reason = Phase8OfflineReplaySessionPlanReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported replay-session plan status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplaySessionPlanBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Replay-session blockers cannot contain duplicates.")

        if self.event_materialization_decision.is_blocked:
            if (
                status != Phase8OfflineReplaySessionPlanStatus.BLOCKED
                or reason != (Phase8OfflineReplaySessionPlanReason.EVENT_BATCH_BLOCKED)
                or blockers != (Phase8OfflineReplaySessionPlanBlocker.EVENT_BATCH_BLOCKED,)
                or self.plan is not None
            ):
                raise ValueError(
                    "Blocked replay-session result does not match its event batch decision."
                )
        else:
            if (
                status != Phase8OfflineReplaySessionPlanStatus.CREATED
                or reason != Phase8OfflineReplaySessionPlanReason.CREATED
                or blockers
                or not isinstance(
                    self.plan,
                    StrategyPhase8OfflineReplaySessionPlan,
                )
                or self.plan.event_materialization_decision
                is not self.event_materialization_decision
            ):
                raise ValueError(
                    "Created replay-session result does not match its event batch decision."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.event_materialization_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.event_materialization_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == Phase8OfflineReplaySessionPlanStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_plan(self) -> bool:
        return self.plan is not None

    @property
    def plan_required(
        self,
    ) -> StrategyPhase8OfflineReplaySessionPlan:
        if self.plan is None:
            raise ValueError("No Phase 8 offline replay-session plan was created.")

        return self.plan

    @property
    def plans_replay_session(self) -> bool:
        return self.is_created

    @property
    def starts_replay(self) -> bool:
        return False

    @property
    def consumes_events(self) -> bool:
        return False

    @property
    def executes_replay(self) -> bool:
        return False

    @property
    def evaluates_strategy(self) -> bool:
        return False

    @property
    def executes_simulation(self) -> bool:
        return False

    @property
    def can_continue_to_offline_replay_session_contract(
        self,
    ) -> bool:
        return self.is_created

    @property
    def fetches_data(self) -> bool:
        return False

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

    @property
    def stable_id(self) -> str:
        blocker_fragment = (
            "NONE" if not self.blockers else ",".join(blocker.value for blocker in self.blockers)
        )

        return (
            f"{self.event_materialization_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_SESSION_PLAN_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplaySessionPlanFactory:
    """Pure immutable replay-session plan factory."""

    def generate(
        self,
        event_materialization_decision: (Phase8OfflineReplayEventMaterializationDecision),
        policy: (Phase8OfflineReplaySessionPolicy | None) = None,
    ) -> Phase8OfflineReplaySessionPlanDecision:
        if not isinstance(
            event_materialization_decision,
            Phase8OfflineReplayEventMaterializationDecision,
        ):
            raise Phase8OfflineReplaySessionPlanError(
                Phase8OfflineReplaySessionPlanErrorReason.INVALID_EVENT_MATERIALIZATION_DECISION,
                "event_materialization_decision must be a "
                "Phase8OfflineReplayEventMaterializationDecision.",
            )

        selected_policy = policy or Phase8OfflineReplaySessionPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplaySessionPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplaySessionPolicy.")

        if event_materialization_decision.is_blocked:
            return Phase8OfflineReplaySessionPlanDecision(
                event_materialization_decision=(event_materialization_decision),
                status=(Phase8OfflineReplaySessionPlanStatus.BLOCKED),
                reason=(Phase8OfflineReplaySessionPlanReason.EVENT_BATCH_BLOCKED),
                blockers=(Phase8OfflineReplaySessionPlanBlocker.EVENT_BATCH_BLOCKED,),
                plan=None,
            )

        event_batch = event_materialization_decision.batch_required
        materialization_plan = event_batch.materialization_plan
        event_contract = event_batch.event_contract
        replay_plan = event_batch.replay_plan
        specification = event_batch.specification
        input_package = event_batch.input_package
        snapshot = event_batch.snapshot

        canonical_payload = _canonical_session_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_SESSION_PLAN_SCHEMA_VERSION),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=event_batch.batch_digest,
            materialization_plan_id=(materialization_plan.stable_id),
            materialization_plan_digest=(materialization_plan.materialization_digest),
            event_contract_id=event_contract.stable_id,
            event_contract_digest=(event_contract.contract_digest),
            replay_plan_id=replay_plan.stable_id,
            replay_plan_digest=replay_plan.plan_digest,
            specification_id=specification.stable_id,
            specification_digest=(specification.specification_digest),
            input_package_id=input_package.stable_id,
            input_digest=input_package.input_digest,
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            broker_symbol=event_batch.broker_symbol,
            direction=event_batch.direction,
            side=event_batch.side,
            source_name=event_batch.source_name,
            captured_at=event_batch.captured_at,
            timeframes=event_batch.timeframes,
            session_mode=(Phase8OfflineReplaySessionMode.IMMUTABLE_IN_MEMORY_REPLAY),
            cursor_mode=(Phase8OfflineReplayCursorMode.ZERO_BASED_FORWARD_ONLY),
            transition_mode=(Phase8OfflineReplayTransitionMode.ONE_EVENT_PER_TRANSITION),
            initial_state_mode=(Phase8OfflineReplayInitialStateMode.FRESH_STRATEGY_STATE),
            sequence_start=event_batch.sequence_start,
            sequence_end=event_batch.sequence_end,
            initial_cursor_index=(event_batch.sequence_start),
            total_event_count=(event_batch.total_event_count),
            first_event_time=event_batch.first_event_time,
            last_event_time=event_batch.last_event_time,
            policy=selected_policy,
        )

        plan = StrategyPhase8OfflineReplaySessionPlan(
            event_materialization_decision=(event_materialization_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_SESSION_PLAN_SCHEMA_VERSION),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=event_batch.batch_digest,
            materialization_plan_id=(materialization_plan.stable_id),
            materialization_plan_digest=(materialization_plan.materialization_digest),
            event_contract_id=event_contract.stable_id,
            event_contract_digest=(event_contract.contract_digest),
            replay_plan_id=replay_plan.stable_id,
            replay_plan_digest=replay_plan.plan_digest,
            specification_id=specification.stable_id,
            specification_digest=(specification.specification_digest),
            input_package_id=input_package.stable_id,
            input_digest=input_package.input_digest,
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            broker_symbol=event_batch.broker_symbol,
            direction=event_batch.direction,
            side=event_batch.side,
            source_name=event_batch.source_name,
            captured_at=event_batch.captured_at,
            timeframes=event_batch.timeframes,
            session_mode=(Phase8OfflineReplaySessionMode.IMMUTABLE_IN_MEMORY_REPLAY),
            cursor_mode=(Phase8OfflineReplayCursorMode.ZERO_BASED_FORWARD_ONLY),
            transition_mode=(Phase8OfflineReplayTransitionMode.ONE_EVENT_PER_TRANSITION),
            initial_state_mode=(Phase8OfflineReplayInitialStateMode.FRESH_STRATEGY_STATE),
            sequence_start=event_batch.sequence_start,
            sequence_end=event_batch.sequence_end,
            initial_cursor_index=(event_batch.sequence_start),
            total_event_count=(event_batch.total_event_count),
            first_event_time=event_batch.first_event_time,
            last_event_time=event_batch.last_event_time,
            session_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplaySessionPlanDecision(
            event_materialization_decision=(event_materialization_decision),
            status=(Phase8OfflineReplaySessionPlanStatus.CREATED),
            reason=(Phase8OfflineReplaySessionPlanReason.CREATED),
            blockers=(),
            plan=plan,
        )

    def build(
        self,
        event_materialization_decision: (Phase8OfflineReplayEventMaterializationDecision),
        policy: (Phase8OfflineReplaySessionPolicy | None) = None,
    ) -> Phase8OfflineReplaySessionPlanDecision:
        return self.generate(
            event_materialization_decision,
            policy,
        )

    def evaluate(
        self,
        event_materialization_decision: (Phase8OfflineReplayEventMaterializationDecision),
        policy: (Phase8OfflineReplaySessionPolicy | None) = None,
    ) -> Phase8OfflineReplaySessionPlanDecision:
        return self.generate(
            event_materialization_decision,
            policy,
        )


def generate_phase8_offline_replay_session_plan(
    event_materialization_decision: (Phase8OfflineReplayEventMaterializationDecision),
    policy: Phase8OfflineReplaySessionPolicy | None = None,
) -> Phase8OfflineReplaySessionPlanDecision:
    return StrategyPhase8OfflineReplaySessionPlanFactory().generate(
        event_materialization_decision,
        policy,
    )


Phase8OfflineReplaySessionPlan = StrategyPhase8OfflineReplaySessionPlan
Phase8OfflineReplaySessionPlanFactory = StrategyPhase8OfflineReplaySessionPlanFactory
