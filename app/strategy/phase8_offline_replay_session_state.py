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
    Phase8OfflineReplayEvent,
    StrategyPhase8OfflineReplayEventBatch,
)
from app.strategy.phase8_offline_replay_event_materialization_plan import (
    StrategyPhase8OfflineReplayEventMaterializationPlan,
)
from app.strategy.phase8_offline_replay_plan import (
    StrategyPhase8OfflineReplayPlan,
)
from app.strategy.phase8_offline_replay_session_contract import (
    Phase8OfflineReplayCompletionRule,
    Phase8OfflineReplayCursorSemantics,
    Phase8OfflineReplaySessionContractDecision,
    StrategyPhase8OfflineReplaySessionContract,
)
from app.strategy.phase8_offline_replay_session_plan import (
    StrategyPhase8OfflineReplaySessionPlan,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_SESSION_STATE_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplaySessionStateMode(str, Enum):
    IMMUTABLE_INITIAL_STATE = "IMMUTABLE_INITIAL_STATE"


class Phase8OfflineReplaySessionLifecycle(str, Enum):
    INITIALIZED = "INITIALIZED"


class Phase8OfflineReplaySessionStateStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplaySessionStateReason(str, Enum):
    CREATED = "CREATED"
    SESSION_CONTRACT_BLOCKED = "SESSION_CONTRACT_BLOCKED"


class Phase8OfflineReplaySessionStateBlocker(str, Enum):
    SESSION_CONTRACT_BLOCKED = "SESSION_CONTRACT_BLOCKED"


class Phase8OfflineReplaySessionStateErrorReason(
    str,
    Enum,
):
    INVALID_SESSION_CONTRACT_DECISION = "INVALID_SESSION_CONTRACT_DECISION"


class Phase8OfflineReplaySessionStateError(RuntimeError):
    """Structured replay-session initial-state failure."""

    def __init__(
        self,
        reason: Phase8OfflineReplaySessionStateErrorReason,
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplaySessionStateErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Phase 8 offline replay-session state error [{self.reason.value}]: {self.message}"
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
        "starts_session",
        "starts_replay",
        "advances_cursor",
        "consumes_events",
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
class Phase8OfflineReplaySessionStatePolicy:
    """Strict initial replay-session state requirements."""

    initial_cursor_at_sequence_start: bool = True
    no_events_consumed: bool = True
    next_event_bound: bool = True
    no_previous_event: bool = True
    in_memory_only: bool = True
    forward_only: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "initial_cursor_at_sequence_start",
            "no_events_consumed",
            "next_event_bound",
            "no_previous_event",
            "in_memory_only",
            "forward_only",
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
                self.initial_cursor_at_sequence_start,
                self.no_events_consumed,
                self.next_event_bound,
                self.no_previous_event,
                self.in_memory_only,
                self.forward_only,
                self.no_lookahead,
                self.no_external_io,
            )
        )


def _canonical_state_payload(
    *,
    schema_version: str,
    session_contract_id: str,
    session_contract_digest: str,
    session_plan_id: str,
    session_plan_digest: str,
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
    state_mode: Phase8OfflineReplaySessionStateMode,
    lifecycle: Phase8OfflineReplaySessionLifecycle,
    cursor_semantics: Phase8OfflineReplayCursorSemantics,
    completion_rule: Phase8OfflineReplayCompletionRule,
    cursor_index: int,
    consumed_count: int,
    remaining_count: int,
    total_event_count: int,
    next_event_sequence_index: int,
    next_event_id: str,
    next_event_digest: str,
    last_consumed_sequence_index: int | None,
    policy: Phase8OfflineReplaySessionStatePolicy,
) -> str:
    last_consumed = (
        "NONE" if last_consumed_sequence_index is None else str(last_consumed_sequence_index)
    )

    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"SESSION_CONTRACT_ID={session_contract_id}",
            (f"SESSION_CONTRACT_DIGEST={session_contract_digest}"),
            f"SESSION_PLAN_ID={session_plan_id}",
            f"SESSION_PLAN_DIGEST={session_plan_digest}",
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
            f"STATE_MODE={state_mode.value}",
            f"LIFECYCLE={lifecycle.value}",
            f"CURSOR_SEMANTICS={cursor_semantics.value}",
            f"COMPLETION_RULE={completion_rule.value}",
            f"CURSOR_INDEX={cursor_index}",
            f"CONSUMED_COUNT={consumed_count}",
            f"REMAINING_COUNT={remaining_count}",
            f"TOTAL_EVENT_COUNT={total_event_count}",
            (f"NEXT_EVENT_SEQUENCE_INDEX={next_event_sequence_index}"),
            f"NEXT_EVENT_ID={next_event_id}",
            f"NEXT_EVENT_DIGEST={next_event_digest}",
            (f"LAST_CONSUMED_SEQUENCE_INDEX={last_consumed}"),
            (
                "INITIAL_CURSOR_AT_SEQUENCE_START="
                f"{str(policy.initial_cursor_at_sequence_start).lower()}"
            ),
            (f"NO_EVENTS_CONSUMED={str(policy.no_events_consumed).lower()}"),
            (f"NEXT_EVENT_BOUND={str(policy.next_event_bound).lower()}"),
            (f"NO_PREVIOUS_EVENT={str(policy.no_previous_event).lower()}"),
            (f"IN_MEMORY_ONLY={str(policy.in_memory_only).lower()}"),
            (f"FORWARD_ONLY={str(policy.forward_only).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "SESSION_INITIALIZED=true",
            "SESSION_STARTED=false",
            "CURSOR_ADVANCED=false",
            "EVENT_CONSUMPTION=false",
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
class StrategyPhase8OfflineReplaySessionState:
    """
    Immutable initial in-memory replay-session state.

    The state binds cursor zero to the first materialized
    event. It does not start replay, advance the cursor,
    consume an event, evaluate strategy logic, perform
    external I/O, contact a broker, or submit an order.
    """

    session_contract_decision: Phase8OfflineReplaySessionContractDecision = field(repr=False)
    policy: Phase8OfflineReplaySessionStatePolicy
    schema_version: str
    session_contract_id: str
    session_contract_digest: str
    session_plan_id: str
    session_plan_digest: str
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
    state_mode: Phase8OfflineReplaySessionStateMode
    lifecycle: Phase8OfflineReplaySessionLifecycle
    cursor_semantics: Phase8OfflineReplayCursorSemantics
    completion_rule: Phase8OfflineReplayCompletionRule
    cursor_index: int
    consumed_count: int
    remaining_count: int
    total_event_count: int
    next_event_sequence_index: int
    next_event_id: str
    next_event_digest: str
    last_consumed_sequence_index: int | None
    state_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.session_contract_decision,
            Phase8OfflineReplaySessionContractDecision,
        ):
            raise ValueError(
                "session_contract_decision must be a Phase8OfflineReplaySessionContractDecision."
            )

        if not self.session_contract_decision.is_created:
            raise ValueError("An initial session state requires a created replay-session contract.")

        if not isinstance(
            self.policy,
            Phase8OfflineReplaySessionStatePolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplaySessionStatePolicy.")

        if not self.policy.is_strict:
            raise ValueError("Replay-session state policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PHASE_8_OFFLINE_REPLAY_SESSION_STATE_SCHEMA_VERSION:
            raise ValueError(
                "schema_version must match the current offline replay-session state schema."
            )

        string_fields = (
            (
                "session_contract_id",
                self.session_contract_id,
            ),
            (
                "session_contract_digest",
                self.session_contract_digest,
            ),
            ("session_plan_id", self.session_plan_id),
            (
                "session_plan_digest",
                self.session_plan_digest,
            ),
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
            ("next_event_id", self.next_event_id),
            ("next_event_digest", self.next_event_digest),
            ("state_digest", self.state_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "session_contract_digest",
            "session_plan_digest",
            "event_batch_digest",
            "materialization_plan_digest",
            "event_contract_digest",
            "replay_plan_digest",
            "specification_digest",
            "input_digest",
            "snapshot_digest",
            "next_event_digest",
            "state_digest",
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
                "state_mode",
                self.state_mode,
                Phase8OfflineReplaySessionStateMode,
            ),
            (
                "lifecycle",
                self.lifecycle,
                Phase8OfflineReplaySessionLifecycle,
            ),
            (
                "cursor_semantics",
                self.cursor_semantics,
                Phase8OfflineReplayCursorSemantics,
            ),
            (
                "completion_rule",
                self.completion_rule,
                Phase8OfflineReplayCompletionRule,
            ),
        )

        for field_name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(f"{field_name} must be a {enum_type.__name__} member.")

        if self.state_mode != (Phase8OfflineReplaySessionStateMode.IMMUTABLE_INITIAL_STATE):
            raise ValueError("state_mode must remain IMMUTABLE_INITIAL_STATE.")

        if self.lifecycle != Phase8OfflineReplaySessionLifecycle.INITIALIZED:
            raise ValueError("lifecycle must remain INITIALIZED.")

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        if not all(isinstance(timeframe, Phase8Timeframe) for timeframe in self.timeframes):
            raise ValueError("timeframes must contain Phase8Timeframe members.")

        cursor_index = _non_negative_integer(
            self.cursor_index,
            "cursor_index",
        )
        consumed_count = _non_negative_integer(
            self.consumed_count,
            "consumed_count",
        )
        remaining_count = _positive_integer(
            self.remaining_count,
            "remaining_count",
        )
        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )
        next_event_sequence_index = _non_negative_integer(
            self.next_event_sequence_index,
            "next_event_sequence_index",
        )

        if self.last_consumed_sequence_index is not None:
            raise ValueError("last_consumed_sequence_index must be None for the initial state.")

        if cursor_index != 0:
            raise ValueError("cursor_index must be zero for the initial state.")

        if consumed_count != 0:
            raise ValueError("consumed_count must be zero for the initial state.")

        if remaining_count != total_event_count:
            raise ValueError("remaining_count must equal total_event_count.")

        if next_event_sequence_index != cursor_index:
            raise ValueError("next_event_sequence_index must equal cursor_index.")

        session_contract = self.session_contract_decision.session_contract_required
        session_plan = session_contract.session_plan
        event_batch = session_contract.event_batch
        materialization_plan = session_contract.materialization_plan
        event_contract = session_contract.event_contract
        replay_plan = session_contract.replay_plan
        specification = session_contract.specification
        input_package = session_contract.input_package
        snapshot = session_contract.snapshot

        comparisons = (
            (
                "session_contract_id",
                normalized_strings["session_contract_id"],
                session_contract.stable_id,
            ),
            (
                "session_contract_digest",
                normalized_strings["session_contract_digest"],
                session_contract.contract_digest,
            ),
            (
                "session_plan_id",
                normalized_strings["session_plan_id"],
                session_plan.stable_id,
            ),
            (
                "session_plan_digest",
                normalized_strings["session_plan_digest"],
                session_plan.session_digest,
            ),
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
                session_contract.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                session_contract.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable replay-session contract lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Replay-session states support Gold/XAUUSD only.")

        if self.direction != session_contract.direction:
            raise ValueError("direction must match the replay-session contract.")

        if self.side != session_contract.side:
            raise ValueError("side must match the replay-session contract.")

        if captured_at != session_contract.captured_at:
            raise ValueError("captured_at must match the replay-session contract.")

        if self.timeframes != session_contract.timeframes:
            raise ValueError("timeframes must match the replay-session contract.")

        if self.cursor_semantics != (session_contract.cursor_semantics):
            raise ValueError("cursor_semantics must match the replay-session contract.")

        if self.completion_rule != (session_contract.completion_rule):
            raise ValueError("completion_rule must match the replay-session contract.")

        if cursor_index != (session_contract.initial_cursor_index):
            raise ValueError("cursor_index must match the contract initial cursor.")

        if consumed_count != (session_contract.initial_consumed_count):
            raise ValueError("consumed_count must match the contract initial consumed count.")

        if remaining_count != (session_contract.initial_remaining_count):
            raise ValueError("remaining_count must match the contract initial remaining count.")

        if total_event_count != (session_contract.total_event_count):
            raise ValueError("total_event_count must match the replay-session contract.")

        next_event = event_batch.events[cursor_index]

        if next_event.sequence_index != cursor_index:
            raise ValueError("The event batch does not preserve the contract cursor sequence.")

        if normalized_strings["next_event_id"] != (next_event.stable_id):
            raise ValueError("next_event_id must match the event at the initial cursor.")

        if normalized_strings["next_event_digest"] != (next_event.event_digest):
            raise ValueError("next_event_digest must match the event at the initial cursor.")

        if next_event.event_time > captured_at:
            raise ValueError("The initial next event cannot represent an open candle.")

        if not session_contract.cursor_points_to_next_event:
            raise ValueError("Session contract must preserve next-event cursor semantics.")

        if not session_contract.forward_only:
            raise ValueError("Session contract must remain forward-only.")

        if not session_contract.no_lookahead:
            raise ValueError("Session contract must remain no-lookahead.")

        safe_subjects = (
            self.session_contract_decision,
            session_contract,
            session_contract.session_plan_decision,
            session_plan,
            session_plan.event_materialization_decision,
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
            session_contract.verification_receipt,
            snapshot,
            session_contract.contract,
            session_contract.dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Replay-session state lineage violates the non-I/O or non-execution boundary."
            )

        canonical_payload = _canonical_state_payload(
            schema_version=schema_version,
            session_contract_id=normalized_strings["session_contract_id"],
            session_contract_digest=normalized_strings["session_contract_digest"],
            session_plan_id=normalized_strings["session_plan_id"],
            session_plan_digest=normalized_strings["session_plan_digest"],
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
            state_mode=self.state_mode,
            lifecycle=self.lifecycle,
            cursor_semantics=self.cursor_semantics,
            completion_rule=self.completion_rule,
            cursor_index=cursor_index,
            consumed_count=consumed_count,
            remaining_count=remaining_count,
            total_event_count=total_event_count,
            next_event_sequence_index=(next_event_sequence_index),
            next_event_id=normalized_strings["next_event_id"],
            next_event_digest=normalized_strings["next_event_digest"],
            last_consumed_sequence_index=(self.last_consumed_sequence_index),
            policy=self.policy,
        )

        if normalized_strings["state_digest"] != _sha256_digest(canonical_payload):
            raise ValueError("state_digest does not match the canonical replay-session state.")

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
            "cursor_index",
            cursor_index,
        )
        object.__setattr__(
            self,
            "consumed_count",
            consumed_count,
        )
        object.__setattr__(
            self,
            "remaining_count",
            remaining_count,
        )
        object.__setattr__(
            self,
            "total_event_count",
            total_event_count,
        )
        object.__setattr__(
            self,
            "next_event_sequence_index",
            next_event_sequence_index,
        )

    @property
    def session_contract(
        self,
    ) -> StrategyPhase8OfflineReplaySessionContract:
        return self.session_contract_decision.session_contract_required

    @property
    def session_plan(
        self,
    ) -> StrategyPhase8OfflineReplaySessionPlan:
        return self.session_contract.session_plan

    @property
    def event_batch(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        return self.session_contract.event_batch

    @property
    def materialization_plan(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        return self.session_contract.materialization_plan

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.session_contract.event_contract

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.session_contract.replay_plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.session_contract.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.session_contract.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.session_contract.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.session_contract.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.session_contract.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.session_contract.dry_run_package

    @property
    def next_event(self) -> Phase8OfflineReplayEvent:
        return self.event_batch.events[self.cursor_index]

    @property
    def canonical_payload(self) -> str:
        return _canonical_state_payload(
            schema_version=self.schema_version,
            session_contract_id=self.session_contract_id,
            session_contract_digest=(self.session_contract_digest),
            session_plan_id=self.session_plan_id,
            session_plan_digest=self.session_plan_digest,
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
            state_mode=self.state_mode,
            lifecycle=self.lifecycle,
            cursor_semantics=self.cursor_semantics,
            completion_rule=self.completion_rule,
            cursor_index=self.cursor_index,
            consumed_count=self.consumed_count,
            remaining_count=self.remaining_count,
            total_event_count=self.total_event_count,
            next_event_sequence_index=(self.next_event_sequence_index),
            next_event_id=self.next_event_id,
            next_event_digest=self.next_event_digest,
            last_consumed_sequence_index=(self.last_consumed_sequence_index),
            policy=self.policy,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def is_initial_state(self) -> bool:
        return True

    @property
    def session_initialized(self) -> bool:
        return True

    @property
    def initializes_session(self) -> bool:
        return True

    @property
    def in_memory_only(self) -> bool:
        return self.policy.in_memory_only

    @property
    def forward_only(self) -> bool:
        return self.policy.forward_only

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def has_next_event(self) -> bool:
        return self.remaining_count > 0

    @property
    def completion_reached(self) -> bool:
        return False

    @property
    def starts_session(self) -> bool:
        return False

    @property
    def starts_replay(self) -> bool:
        return False

    @property
    def advances_cursor(self) -> bool:
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
    def can_continue_to_offline_replay_transition_contract(
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
    def session_state_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_SESSION_STATE:"
            f"STATE_SHA256[{self.state_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.session_contract_decision.stable_id}:{self.session_state_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplaySessionStateDecision:
    """Immutable replay-session state creation decision."""

    session_contract_decision: Phase8OfflineReplaySessionContractDecision = field(repr=False)
    status: Phase8OfflineReplaySessionStateStatus
    reason: Phase8OfflineReplaySessionStateReason
    blockers: tuple[
        Phase8OfflineReplaySessionStateBlocker,
        ...,
    ]
    state: StrategyPhase8OfflineReplaySessionState | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.session_contract_decision,
            Phase8OfflineReplaySessionContractDecision,
        ):
            raise ValueError(
                "session_contract_decision must be a Phase8OfflineReplaySessionContractDecision."
            )

        try:
            status = Phase8OfflineReplaySessionStateStatus(self.status)
            reason = Phase8OfflineReplaySessionStateReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported replay-session state status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplaySessionStateBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Replay-session state blockers cannot contain duplicates.")

        if self.session_contract_decision.is_blocked:
            if (
                status != Phase8OfflineReplaySessionStateStatus.BLOCKED
                or reason != (Phase8OfflineReplaySessionStateReason.SESSION_CONTRACT_BLOCKED)
                or blockers != (Phase8OfflineReplaySessionStateBlocker.SESSION_CONTRACT_BLOCKED,)
                or self.state is not None
            ):
                raise ValueError(
                    "Blocked replay-session state result does not match its session contract."
                )
        else:
            if (
                status != Phase8OfflineReplaySessionStateStatus.CREATED
                or reason != Phase8OfflineReplaySessionStateReason.CREATED
                or blockers
                or not isinstance(
                    self.state,
                    StrategyPhase8OfflineReplaySessionState,
                )
                or self.state.session_contract_decision is not self.session_contract_decision
            ):
                raise ValueError(
                    "Created replay-session state result does not match its session contract."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.session_contract_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.session_contract_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == Phase8OfflineReplaySessionStateStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_state(self) -> bool:
        return self.state is not None

    @property
    def state_required(
        self,
    ) -> StrategyPhase8OfflineReplaySessionState:
        if self.state is None:
            raise ValueError("No Phase 8 offline replay-session state was created.")

        return self.state

    @property
    def initializes_session(self) -> bool:
        return self.is_created

    @property
    def starts_session(self) -> bool:
        return False

    @property
    def starts_replay(self) -> bool:
        return False

    @property
    def advances_cursor(self) -> bool:
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
    def can_continue_to_offline_replay_transition_contract(
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
            f"{self.session_contract_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_SESSION_STATE_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplaySessionStateFactory:
    """Pure immutable initial session-state factory."""

    def generate(
        self,
        session_contract_decision: (Phase8OfflineReplaySessionContractDecision),
        policy: (Phase8OfflineReplaySessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplaySessionStateDecision:
        if not isinstance(
            session_contract_decision,
            Phase8OfflineReplaySessionContractDecision,
        ):
            raise Phase8OfflineReplaySessionStateError(
                Phase8OfflineReplaySessionStateErrorReason.INVALID_SESSION_CONTRACT_DECISION,
                "session_contract_decision must be a Phase8OfflineReplaySessionContractDecision.",
            )

        selected_policy = policy or Phase8OfflineReplaySessionStatePolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplaySessionStatePolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplaySessionStatePolicy.")

        if session_contract_decision.is_blocked:
            return Phase8OfflineReplaySessionStateDecision(
                session_contract_decision=(session_contract_decision),
                status=(Phase8OfflineReplaySessionStateStatus.BLOCKED),
                reason=(Phase8OfflineReplaySessionStateReason.SESSION_CONTRACT_BLOCKED),
                blockers=(Phase8OfflineReplaySessionStateBlocker.SESSION_CONTRACT_BLOCKED,),
                state=None,
            )

        session_contract = session_contract_decision.session_contract_required
        session_plan = session_contract.session_plan
        event_batch = session_contract.event_batch
        materialization_plan = session_contract.materialization_plan
        event_contract = session_contract.event_contract
        replay_plan = session_contract.replay_plan
        specification = session_contract.specification
        input_package = session_contract.input_package
        snapshot = session_contract.snapshot

        cursor_index = session_contract.initial_cursor_index
        consumed_count = session_contract.initial_consumed_count
        remaining_count = session_contract.initial_remaining_count
        next_event = event_batch.events[cursor_index]

        canonical_payload = _canonical_state_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_SESSION_STATE_SCHEMA_VERSION),
            session_contract_id=session_contract.stable_id,
            session_contract_digest=(session_contract.contract_digest),
            session_plan_id=session_plan.stable_id,
            session_plan_digest=session_plan.session_digest,
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
            broker_symbol=session_contract.broker_symbol,
            direction=session_contract.direction,
            side=session_contract.side,
            source_name=session_contract.source_name,
            captured_at=session_contract.captured_at,
            timeframes=session_contract.timeframes,
            state_mode=(Phase8OfflineReplaySessionStateMode.IMMUTABLE_INITIAL_STATE),
            lifecycle=(Phase8OfflineReplaySessionLifecycle.INITIALIZED),
            cursor_semantics=(session_contract.cursor_semantics),
            completion_rule=(session_contract.completion_rule),
            cursor_index=cursor_index,
            consumed_count=consumed_count,
            remaining_count=remaining_count,
            total_event_count=(session_contract.total_event_count),
            next_event_sequence_index=(next_event.sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=next_event.event_digest,
            last_consumed_sequence_index=None,
            policy=selected_policy,
        )

        state = StrategyPhase8OfflineReplaySessionState(
            session_contract_decision=(session_contract_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_SESSION_STATE_SCHEMA_VERSION),
            session_contract_id=session_contract.stable_id,
            session_contract_digest=(session_contract.contract_digest),
            session_plan_id=session_plan.stable_id,
            session_plan_digest=session_plan.session_digest,
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
            broker_symbol=session_contract.broker_symbol,
            direction=session_contract.direction,
            side=session_contract.side,
            source_name=session_contract.source_name,
            captured_at=session_contract.captured_at,
            timeframes=session_contract.timeframes,
            state_mode=(Phase8OfflineReplaySessionStateMode.IMMUTABLE_INITIAL_STATE),
            lifecycle=(Phase8OfflineReplaySessionLifecycle.INITIALIZED),
            cursor_semantics=(session_contract.cursor_semantics),
            completion_rule=(session_contract.completion_rule),
            cursor_index=cursor_index,
            consumed_count=consumed_count,
            remaining_count=remaining_count,
            total_event_count=(session_contract.total_event_count),
            next_event_sequence_index=(next_event.sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=next_event.event_digest,
            last_consumed_sequence_index=None,
            state_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplaySessionStateDecision(
            session_contract_decision=(session_contract_decision),
            status=(Phase8OfflineReplaySessionStateStatus.CREATED),
            reason=(Phase8OfflineReplaySessionStateReason.CREATED),
            blockers=(),
            state=state,
        )

    def build(
        self,
        session_contract_decision: (Phase8OfflineReplaySessionContractDecision),
        policy: (Phase8OfflineReplaySessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplaySessionStateDecision:
        return self.generate(
            session_contract_decision,
            policy,
        )

    def evaluate(
        self,
        session_contract_decision: (Phase8OfflineReplaySessionContractDecision),
        policy: (Phase8OfflineReplaySessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplaySessionStateDecision:
        return self.generate(
            session_contract_decision,
            policy,
        )


def generate_phase8_offline_replay_session_state(
    session_contract_decision: (Phase8OfflineReplaySessionContractDecision),
    policy: (Phase8OfflineReplaySessionStatePolicy | None) = None,
) -> Phase8OfflineReplaySessionStateDecision:
    return StrategyPhase8OfflineReplaySessionStateFactory().generate(
        session_contract_decision,
        policy,
    )


Phase8OfflineReplaySessionState = StrategyPhase8OfflineReplaySessionState
Phase8OfflineReplaySessionStateFactory = StrategyPhase8OfflineReplaySessionStateFactory
