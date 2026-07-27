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
    StrategyPhase8OfflineReplayEventBatch,
)
from app.strategy.phase8_offline_replay_event_materialization_plan import (
    StrategyPhase8OfflineReplayEventMaterializationPlan,
)
from app.strategy.phase8_offline_replay_plan import (
    StrategyPhase8OfflineReplayPlan,
)
from app.strategy.phase8_offline_replay_session_plan import (
    Phase8OfflineReplayCursorMode,
    Phase8OfflineReplayInitialStateMode,
    Phase8OfflineReplaySessionMode,
    Phase8OfflineReplaySessionPlanDecision,
    Phase8OfflineReplayTransitionMode,
    StrategyPhase8OfflineReplaySessionPlan,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_SESSION_CONTRACT_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplaySessionContractMode(
    str,
    Enum,
):
    IMMUTABLE_FORWARD_ONLY = "IMMUTABLE_FORWARD_ONLY"


class Phase8OfflineReplayCursorSemantics(
    str,
    Enum,
):
    NEXT_EVENT_INDEX = "NEXT_EVENT_INDEX"


class Phase8OfflineReplayCompletionRule(
    str,
    Enum,
):
    CURSOR_EQUALS_EVENT_COUNT = "CURSOR_EQUALS_EVENT_COUNT"


class Phase8OfflineReplayTransitionCommitMode(
    str,
    Enum,
):
    ATOMIC_IN_MEMORY = "ATOMIC_IN_MEMORY"


class Phase8OfflineReplaySessionContractStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplaySessionContractReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    SESSION_PLAN_BLOCKED = "SESSION_PLAN_BLOCKED"


class Phase8OfflineReplaySessionContractBlocker(
    str,
    Enum,
):
    SESSION_PLAN_BLOCKED = "SESSION_PLAN_BLOCKED"


class Phase8OfflineReplaySessionContractErrorReason(
    str,
    Enum,
):
    INVALID_SESSION_PLAN_DECISION = "INVALID_SESSION_PLAN_DECISION"


class Phase8OfflineReplaySessionContractError(
    RuntimeError,
):
    """Structured replay-session contract failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplaySessionContractErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplaySessionContractErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Phase 8 offline replay-session contract error [{self.reason.value}]: {self.message}"
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
        "starts_replay",
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
class Phase8OfflineReplaySessionContractPolicy:
    """Strict deterministic replay-session semantics."""

    cursor_points_to_next_event: bool = True
    forward_only_cursor: bool = True
    one_event_per_transition: bool = True
    atomic_in_memory_transition: bool = True
    deterministic_completion: bool = True
    fresh_strategy_state: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "cursor_points_to_next_event",
            "forward_only_cursor",
            "one_event_per_transition",
            "atomic_in_memory_transition",
            "deterministic_completion",
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
                self.cursor_points_to_next_event,
                self.forward_only_cursor,
                self.one_event_per_transition,
                self.atomic_in_memory_transition,
                self.deterministic_completion,
                self.fresh_strategy_state,
                self.no_lookahead,
                self.no_external_io,
            )
        )


def _canonical_contract_payload(
    *,
    schema_version: str,
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
    session_mode: Phase8OfflineReplaySessionMode,
    cursor_mode: Phase8OfflineReplayCursorMode,
    transition_mode: Phase8OfflineReplayTransitionMode,
    initial_state_mode: Phase8OfflineReplayInitialStateMode,
    contract_mode: Phase8OfflineReplaySessionContractMode,
    cursor_semantics: Phase8OfflineReplayCursorSemantics,
    completion_rule: Phase8OfflineReplayCompletionRule,
    transition_commit_mode: (Phase8OfflineReplayTransitionCommitMode),
    sequence_start: int,
    sequence_end: int,
    initial_cursor_index: int,
    completion_cursor_index: int,
    transition_count: int,
    initial_consumed_count: int,
    initial_remaining_count: int,
    total_event_count: int,
    first_event_time: datetime,
    last_event_time: datetime,
    policy: Phase8OfflineReplaySessionContractPolicy,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
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
            f"SESSION_MODE={session_mode.value}",
            f"CURSOR_MODE={cursor_mode.value}",
            f"TRANSITION_MODE={transition_mode.value}",
            (f"INITIAL_STATE_MODE={initial_state_mode.value}"),
            f"CONTRACT_MODE={contract_mode.value}",
            f"CURSOR_SEMANTICS={cursor_semantics.value}",
            f"COMPLETION_RULE={completion_rule.value}",
            (f"TRANSITION_COMMIT_MODE={transition_commit_mode.value}"),
            f"SEQUENCE_START={sequence_start}",
            f"SEQUENCE_END={sequence_end}",
            f"INITIAL_CURSOR_INDEX={initial_cursor_index}",
            (f"COMPLETION_CURSOR_INDEX={completion_cursor_index}"),
            f"TRANSITION_COUNT={transition_count}",
            (f"INITIAL_CONSUMED_COUNT={initial_consumed_count}"),
            (f"INITIAL_REMAINING_COUNT={initial_remaining_count}"),
            f"TOTAL_EVENT_COUNT={total_event_count}",
            (f"FIRST_EVENT_TIME={_canonical_datetime(first_event_time)}"),
            (f"LAST_EVENT_TIME={_canonical_datetime(last_event_time)}"),
            (f"CURSOR_POINTS_TO_NEXT_EVENT={str(policy.cursor_points_to_next_event).lower()}"),
            (f"FORWARD_ONLY_CURSOR={str(policy.forward_only_cursor).lower()}"),
            (f"ONE_EVENT_PER_TRANSITION={str(policy.one_event_per_transition).lower()}"),
            (f"ATOMIC_IN_MEMORY_TRANSITION={str(policy.atomic_in_memory_transition).lower()}"),
            (f"DETERMINISTIC_COMPLETION={str(policy.deterministic_completion).lower()}"),
            (f"FRESH_STRATEGY_STATE={str(policy.fresh_strategy_state).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "CONTRACT_CREATED=true",
            "SESSION_INITIALIZED=false",
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
class StrategyPhase8OfflineReplaySessionContract:
    """
    Immutable replay-session cursor and completion contract.

    It defines deterministic session semantics only. It does
    not initialize or start a session, advance a cursor,
    consume an event, evaluate strategy logic, perform I/O,
    contact a broker, or submit an order.
    """

    session_plan_decision: Phase8OfflineReplaySessionPlanDecision = field(repr=False)
    policy: Phase8OfflineReplaySessionContractPolicy
    schema_version: str
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
    session_mode: Phase8OfflineReplaySessionMode
    cursor_mode: Phase8OfflineReplayCursorMode
    transition_mode: Phase8OfflineReplayTransitionMode
    initial_state_mode: Phase8OfflineReplayInitialStateMode
    contract_mode: Phase8OfflineReplaySessionContractMode
    cursor_semantics: Phase8OfflineReplayCursorSemantics
    completion_rule: Phase8OfflineReplayCompletionRule
    transition_commit_mode: Phase8OfflineReplayTransitionCommitMode
    sequence_start: int
    sequence_end: int
    initial_cursor_index: int
    completion_cursor_index: int
    transition_count: int
    initial_consumed_count: int
    initial_remaining_count: int
    total_event_count: int
    first_event_time: datetime
    last_event_time: datetime
    contract_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.session_plan_decision,
            Phase8OfflineReplaySessionPlanDecision,
        ):
            raise ValueError(
                "session_plan_decision must be a Phase8OfflineReplaySessionPlanDecision."
            )

        if not self.session_plan_decision.is_created:
            raise ValueError("A replay-session contract requires a created replay-session plan.")

        if not isinstance(
            self.policy,
            Phase8OfflineReplaySessionContractPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplaySessionContractPolicy.")

        if not self.policy.is_strict:
            raise ValueError("Replay-session contract policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_REPLAY_SESSION_CONTRACT_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current replay-session contract schema."
            )

        string_fields = (
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
            ("contract_digest", self.contract_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "session_plan_digest",
            "event_batch_digest",
            "materialization_plan_digest",
            "event_contract_digest",
            "replay_plan_digest",
            "specification_digest",
            "input_digest",
            "snapshot_digest",
            "contract_digest",
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
            (
                "contract_mode",
                self.contract_mode,
                Phase8OfflineReplaySessionContractMode,
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
            (
                "transition_commit_mode",
                self.transition_commit_mode,
                Phase8OfflineReplayTransitionCommitMode,
            ),
        )

        for field_name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(f"{field_name} must be a {enum_type.__name__} member.")

        if self.contract_mode != (Phase8OfflineReplaySessionContractMode.IMMUTABLE_FORWARD_ONLY):
            raise ValueError("contract_mode must remain IMMUTABLE_FORWARD_ONLY.")

        if self.cursor_semantics != (Phase8OfflineReplayCursorSemantics.NEXT_EVENT_INDEX):
            raise ValueError("cursor_semantics must remain NEXT_EVENT_INDEX.")

        if self.completion_rule != (Phase8OfflineReplayCompletionRule.CURSOR_EQUALS_EVENT_COUNT):
            raise ValueError("completion_rule must remain CURSOR_EQUALS_EVENT_COUNT.")

        if self.transition_commit_mode != (
            Phase8OfflineReplayTransitionCommitMode.ATOMIC_IN_MEMORY
        ):
            raise ValueError("transition_commit_mode must remain ATOMIC_IN_MEMORY.")

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
        completion_cursor_index = _non_negative_integer(
            self.completion_cursor_index,
            "completion_cursor_index",
        )
        transition_count = _positive_integer(
            self.transition_count,
            "transition_count",
        )
        initial_consumed_count = _non_negative_integer(
            self.initial_consumed_count,
            "initial_consumed_count",
        )
        initial_remaining_count = _positive_integer(
            self.initial_remaining_count,
            "initial_remaining_count",
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

        if completion_cursor_index != total_event_count:
            raise ValueError("completion_cursor_index must equal total_event_count.")

        if transition_count != total_event_count:
            raise ValueError("transition_count must equal total_event_count.")

        if initial_consumed_count != 0:
            raise ValueError("initial_consumed_count must be zero.")

        if initial_remaining_count != total_event_count:
            raise ValueError("initial_remaining_count must equal total_event_count.")

        session_plan = self.session_plan_decision.plan_required
        event_batch = session_plan.event_batch
        materialization_plan = session_plan.materialization_plan
        event_contract = session_plan.event_contract
        replay_plan = session_plan.replay_plan
        specification = session_plan.specification
        input_package = session_plan.input_package
        snapshot = session_plan.snapshot

        comparisons = (
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
                session_plan.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                session_plan.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable replay-session plan lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Replay-session contracts support Gold/XAUUSD only.")

        if self.direction != session_plan.direction:
            raise ValueError("direction must match the replay-session plan.")

        if self.side != session_plan.side:
            raise ValueError("side must match the replay-session plan.")

        if captured_at != session_plan.captured_at:
            raise ValueError("captured_at must match the replay-session plan.")

        if self.timeframes != session_plan.timeframes:
            raise ValueError("timeframes must match the replay-session plan.")

        plan_controls = (
            (
                "session_mode",
                self.session_mode,
                session_plan.session_mode,
            ),
            (
                "cursor_mode",
                self.cursor_mode,
                session_plan.cursor_mode,
            ),
            (
                "transition_mode",
                self.transition_mode,
                session_plan.transition_mode,
            ),
            (
                "initial_state_mode",
                self.initial_state_mode,
                session_plan.initial_state_mode,
            ),
        )

        for field_name, supplied, expected in plan_controls:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the replay-session plan.")

        numeric_comparisons = (
            (
                "sequence_start",
                sequence_start,
                session_plan.sequence_start,
            ),
            (
                "sequence_end",
                sequence_end,
                session_plan.sequence_end,
            ),
            (
                "initial_cursor_index",
                initial_cursor_index,
                session_plan.initial_cursor_index,
            ),
            (
                "total_event_count",
                total_event_count,
                session_plan.total_event_count,
            ),
        )

        for field_name, supplied, expected in numeric_comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the replay-session plan.")

        if first_event_time != session_plan.first_event_time:
            raise ValueError("first_event_time must match the replay-session plan.")

        if last_event_time != session_plan.last_event_time:
            raise ValueError("last_event_time must match the replay-session plan.")

        if not session_plan.in_memory_only:
            raise ValueError("Replay-session plan must remain in-memory only.")

        if not session_plan.forward_only:
            raise ValueError("Replay-session plan must remain forward-only.")

        if not session_plan.no_lookahead:
            raise ValueError("Replay-session plan must remain no-lookahead.")

        safe_subjects = (
            self.session_plan_decision,
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
            session_plan.verification_receipt,
            snapshot,
            session_plan.contract,
            session_plan.dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Replay-session contract lineage violates the non-I/O or non-execution boundary."
            )

        canonical_payload = _canonical_contract_payload(
            schema_version=schema_version,
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
            session_mode=self.session_mode,
            cursor_mode=self.cursor_mode,
            transition_mode=self.transition_mode,
            initial_state_mode=self.initial_state_mode,
            contract_mode=self.contract_mode,
            cursor_semantics=self.cursor_semantics,
            completion_rule=self.completion_rule,
            transition_commit_mode=(self.transition_commit_mode),
            sequence_start=sequence_start,
            sequence_end=sequence_end,
            initial_cursor_index=initial_cursor_index,
            completion_cursor_index=(completion_cursor_index),
            transition_count=transition_count,
            initial_consumed_count=(initial_consumed_count),
            initial_remaining_count=(initial_remaining_count),
            total_event_count=total_event_count,
            first_event_time=first_event_time,
            last_event_time=last_event_time,
            policy=self.policy,
        )

        if normalized_strings["contract_digest"] != _sha256_digest(canonical_payload):
            raise ValueError(
                "contract_digest does not match the canonical replay-session contract."
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
            "completion_cursor_index",
            completion_cursor_index,
        )
        object.__setattr__(
            self,
            "transition_count",
            transition_count,
        )
        object.__setattr__(
            self,
            "initial_consumed_count",
            initial_consumed_count,
        )
        object.__setattr__(
            self,
            "initial_remaining_count",
            initial_remaining_count,
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
    def session_plan(
        self,
    ) -> StrategyPhase8OfflineReplaySessionPlan:
        return self.session_plan_decision.plan_required

    @property
    def event_batch(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        return self.session_plan.event_batch

    @property
    def materialization_plan(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        return self.session_plan.materialization_plan

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.session_plan.event_contract

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.session_plan.replay_plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.session_plan.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.session_plan.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.session_plan.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.session_plan.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.session_plan.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.session_plan.dry_run_package

    @property
    def canonical_payload(self) -> str:
        return _canonical_contract_payload(
            schema_version=self.schema_version,
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
            session_mode=self.session_mode,
            cursor_mode=self.cursor_mode,
            transition_mode=self.transition_mode,
            initial_state_mode=self.initial_state_mode,
            contract_mode=self.contract_mode,
            cursor_semantics=self.cursor_semantics,
            completion_rule=self.completion_rule,
            transition_commit_mode=(self.transition_commit_mode),
            sequence_start=self.sequence_start,
            sequence_end=self.sequence_end,
            initial_cursor_index=self.initial_cursor_index,
            completion_cursor_index=(self.completion_cursor_index),
            transition_count=self.transition_count,
            initial_consumed_count=(self.initial_consumed_count),
            initial_remaining_count=(self.initial_remaining_count),
            total_event_count=self.total_event_count,
            first_event_time=self.first_event_time,
            last_event_time=self.last_event_time,
            policy=self.policy,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def contract_only(self) -> bool:
        return True

    @property
    def cursor_points_to_next_event(self) -> bool:
        return self.policy.cursor_points_to_next_event

    @property
    def forward_only(self) -> bool:
        return self.policy.forward_only_cursor

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def completion_is_deterministic(self) -> bool:
        return self.policy.deterministic_completion

    @property
    def initializes_session(self) -> bool:
        return False

    @property
    def starts_session(self) -> bool:
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
    def can_continue_to_offline_replay_session_state(
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
    def session_contract_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_SESSION_CONTRACT:"
            f"CONTRACT_SHA256[{self.contract_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.session_plan_decision.stable_id}:{self.session_contract_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplaySessionContractDecision:
    """Immutable replay-session contract decision."""

    session_plan_decision: Phase8OfflineReplaySessionPlanDecision = field(repr=False)
    status: Phase8OfflineReplaySessionContractStatus
    reason: Phase8OfflineReplaySessionContractReason
    blockers: tuple[
        Phase8OfflineReplaySessionContractBlocker,
        ...,
    ]
    session_contract: StrategyPhase8OfflineReplaySessionContract | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.session_plan_decision,
            Phase8OfflineReplaySessionPlanDecision,
        ):
            raise ValueError(
                "session_plan_decision must be a Phase8OfflineReplaySessionPlanDecision."
            )

        try:
            status = Phase8OfflineReplaySessionContractStatus(self.status)
            reason = Phase8OfflineReplaySessionContractReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported replay-session contract status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplaySessionContractBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Replay-session contract blockers cannot contain duplicates.")

        if self.session_plan_decision.is_blocked:
            if (
                status != (Phase8OfflineReplaySessionContractStatus.BLOCKED)
                or reason != (Phase8OfflineReplaySessionContractReason.SESSION_PLAN_BLOCKED)
                or blockers != (Phase8OfflineReplaySessionContractBlocker.SESSION_PLAN_BLOCKED,)
                or self.session_contract is not None
            ):
                raise ValueError(
                    "Blocked replay-session contract result does not match its session plan."
                )
        else:
            if (
                status != (Phase8OfflineReplaySessionContractStatus.CREATED)
                or reason != (Phase8OfflineReplaySessionContractReason.CREATED)
                or blockers
                or not isinstance(
                    self.session_contract,
                    StrategyPhase8OfflineReplaySessionContract,
                )
                or self.session_contract.session_plan_decision is not self.session_plan_decision
            ):
                raise ValueError(
                    "Created replay-session contract result does not match its session plan."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.session_plan_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.session_plan_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineReplaySessionContractStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_session_contract(self) -> bool:
        return self.session_contract is not None

    @property
    def session_contract_required(
        self,
    ) -> StrategyPhase8OfflineReplaySessionContract:
        if self.session_contract is None:
            raise ValueError("No Phase 8 offline replay-session contract was created.")

        return self.session_contract

    @property
    def initializes_session(self) -> bool:
        return False

    @property
    def starts_session(self) -> bool:
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
    def can_continue_to_offline_replay_session_state(
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
            f"{self.session_plan_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_SESSION_"
            "CONTRACT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplaySessionContractFactory:
    """Pure immutable replay-session contract factory."""

    def generate(
        self,
        session_plan_decision: (Phase8OfflineReplaySessionPlanDecision),
        policy: (Phase8OfflineReplaySessionContractPolicy | None) = None,
    ) -> Phase8OfflineReplaySessionContractDecision:
        if not isinstance(
            session_plan_decision,
            Phase8OfflineReplaySessionPlanDecision,
        ):
            raise Phase8OfflineReplaySessionContractError(
                Phase8OfflineReplaySessionContractErrorReason.INVALID_SESSION_PLAN_DECISION,
                "session_plan_decision must be a Phase8OfflineReplaySessionPlanDecision.",
            )

        selected_policy = policy or Phase8OfflineReplaySessionContractPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplaySessionContractPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplaySessionContractPolicy.")

        if session_plan_decision.is_blocked:
            return Phase8OfflineReplaySessionContractDecision(
                session_plan_decision=(session_plan_decision),
                status=(Phase8OfflineReplaySessionContractStatus.BLOCKED),
                reason=(Phase8OfflineReplaySessionContractReason.SESSION_PLAN_BLOCKED),
                blockers=(Phase8OfflineReplaySessionContractBlocker.SESSION_PLAN_BLOCKED,),
                session_contract=None,
            )

        session_plan = session_plan_decision.plan_required
        event_batch = session_plan.event_batch
        materialization_plan = session_plan.materialization_plan
        event_contract = session_plan.event_contract
        replay_plan = session_plan.replay_plan
        specification = session_plan.specification
        input_package = session_plan.input_package
        snapshot = session_plan.snapshot

        completion_cursor_index = session_plan.total_event_count
        transition_count = session_plan.total_event_count
        initial_consumed_count = 0
        initial_remaining_count = session_plan.total_event_count

        canonical_payload = _canonical_contract_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_SESSION_CONTRACT_SCHEMA_VERSION),
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
            broker_symbol=session_plan.broker_symbol,
            direction=session_plan.direction,
            side=session_plan.side,
            source_name=session_plan.source_name,
            captured_at=session_plan.captured_at,
            timeframes=session_plan.timeframes,
            session_mode=session_plan.session_mode,
            cursor_mode=session_plan.cursor_mode,
            transition_mode=session_plan.transition_mode,
            initial_state_mode=(session_plan.initial_state_mode),
            contract_mode=(Phase8OfflineReplaySessionContractMode.IMMUTABLE_FORWARD_ONLY),
            cursor_semantics=(Phase8OfflineReplayCursorSemantics.NEXT_EVENT_INDEX),
            completion_rule=(Phase8OfflineReplayCompletionRule.CURSOR_EQUALS_EVENT_COUNT),
            transition_commit_mode=(Phase8OfflineReplayTransitionCommitMode.ATOMIC_IN_MEMORY),
            sequence_start=session_plan.sequence_start,
            sequence_end=session_plan.sequence_end,
            initial_cursor_index=(session_plan.initial_cursor_index),
            completion_cursor_index=(completion_cursor_index),
            transition_count=transition_count,
            initial_consumed_count=(initial_consumed_count),
            initial_remaining_count=(initial_remaining_count),
            total_event_count=(session_plan.total_event_count),
            first_event_time=session_plan.first_event_time,
            last_event_time=session_plan.last_event_time,
            policy=selected_policy,
        )

        session_contract = StrategyPhase8OfflineReplaySessionContract(
            session_plan_decision=(session_plan_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_SESSION_CONTRACT_SCHEMA_VERSION),
            session_plan_id=session_plan.stable_id,
            session_plan_digest=(session_plan.session_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=(event_batch.batch_digest),
            materialization_plan_id=(materialization_plan.stable_id),
            materialization_plan_digest=(materialization_plan.materialization_digest),
            event_contract_id=(event_contract.stable_id),
            event_contract_digest=(event_contract.contract_digest),
            replay_plan_id=replay_plan.stable_id,
            replay_plan_digest=(replay_plan.plan_digest),
            specification_id=(specification.stable_id),
            specification_digest=(specification.specification_digest),
            input_package_id=(input_package.stable_id),
            input_digest=input_package.input_digest,
            snapshot_id=snapshot.stable_id,
            snapshot_digest=(snapshot.snapshot_digest),
            broker_symbol=session_plan.broker_symbol,
            direction=session_plan.direction,
            side=session_plan.side,
            source_name=session_plan.source_name,
            captured_at=session_plan.captured_at,
            timeframes=session_plan.timeframes,
            session_mode=session_plan.session_mode,
            cursor_mode=session_plan.cursor_mode,
            transition_mode=(session_plan.transition_mode),
            initial_state_mode=(session_plan.initial_state_mode),
            contract_mode=(Phase8OfflineReplaySessionContractMode.IMMUTABLE_FORWARD_ONLY),
            cursor_semantics=(Phase8OfflineReplayCursorSemantics.NEXT_EVENT_INDEX),
            completion_rule=(Phase8OfflineReplayCompletionRule.CURSOR_EQUALS_EVENT_COUNT),
            transition_commit_mode=(Phase8OfflineReplayTransitionCommitMode.ATOMIC_IN_MEMORY),
            sequence_start=(session_plan.sequence_start),
            sequence_end=session_plan.sequence_end,
            initial_cursor_index=(session_plan.initial_cursor_index),
            completion_cursor_index=(completion_cursor_index),
            transition_count=transition_count,
            initial_consumed_count=(initial_consumed_count),
            initial_remaining_count=(initial_remaining_count),
            total_event_count=(session_plan.total_event_count),
            first_event_time=(session_plan.first_event_time),
            last_event_time=(session_plan.last_event_time),
            contract_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplaySessionContractDecision(
            session_plan_decision=session_plan_decision,
            status=(Phase8OfflineReplaySessionContractStatus.CREATED),
            reason=(Phase8OfflineReplaySessionContractReason.CREATED),
            blockers=(),
            session_contract=session_contract,
        )

    def build(
        self,
        session_plan_decision: (Phase8OfflineReplaySessionPlanDecision),
        policy: (Phase8OfflineReplaySessionContractPolicy | None) = None,
    ) -> Phase8OfflineReplaySessionContractDecision:
        return self.generate(
            session_plan_decision,
            policy,
        )

    def evaluate(
        self,
        session_plan_decision: (Phase8OfflineReplaySessionPlanDecision),
        policy: (Phase8OfflineReplaySessionContractPolicy | None) = None,
    ) -> Phase8OfflineReplaySessionContractDecision:
        return self.generate(
            session_plan_decision,
            policy,
        )


def generate_phase8_offline_replay_session_contract(
    session_plan_decision: (Phase8OfflineReplaySessionPlanDecision),
    policy: (Phase8OfflineReplaySessionContractPolicy | None) = None,
) -> Phase8OfflineReplaySessionContractDecision:
    return StrategyPhase8OfflineReplaySessionContractFactory().generate(
        session_plan_decision,
        policy,
    )


Phase8OfflineReplaySessionContract = StrategyPhase8OfflineReplaySessionContract
Phase8OfflineReplaySessionContractFactory = StrategyPhase8OfflineReplaySessionContractFactory
