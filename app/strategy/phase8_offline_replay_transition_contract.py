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
    StrategyPhase8OfflineReplaySessionContract,
)
from app.strategy.phase8_offline_replay_session_plan import (
    StrategyPhase8OfflineReplaySessionPlan,
)
from app.strategy.phase8_offline_replay_session_state import (
    Phase8OfflineReplaySessionStateDecision,
    StrategyPhase8OfflineReplaySessionState,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_TRANSITION_CONTRACT_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplayTransitionContractMode(
    str,
    Enum,
):
    IMMUTABLE_SINGLE_EVENT = "IMMUTABLE_SINGLE_EVENT"


class Phase8OfflineReplayTransitionAction(str, Enum):
    CONSUME_CURRENT_EVENT = "CONSUME_CURRENT_EVENT"


class Phase8OfflineReplayTransitionCursorRule(str, Enum):
    INCREMENT_BY_ONE = "INCREMENT_BY_ONE"


class Phase8OfflineReplayTransitionCounterRule(
    str,
    Enum,
):
    CONSUMED_PLUS_REMAINING_EQUALS_TOTAL = "CONSUMED_PLUS_REMAINING_EQUALS_TOTAL"


class Phase8OfflineReplayTransitionContractStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplayTransitionContractReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    SESSION_STATE_BLOCKED = "SESSION_STATE_BLOCKED"


class Phase8OfflineReplayTransitionContractBlocker(
    str,
    Enum,
):
    SESSION_STATE_BLOCKED = "SESSION_STATE_BLOCKED"


class Phase8OfflineReplayTransitionContractErrorReason(
    str,
    Enum,
):
    INVALID_SESSION_STATE_DECISION = "INVALID_SESSION_STATE_DECISION"


class Phase8OfflineReplayTransitionContractError(
    RuntimeError,
):
    """Structured replay-transition contract failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplayTransitionContractErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplayTransitionContractErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 offline replay-transition contract "
            f"error [{self.reason.value}]: {self.message}"
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
class Phase8OfflineReplayTransitionContractPolicy:
    """Strict first-transition contract requirements."""

    source_state_immutable: bool = True
    current_event_bound: bool = True
    one_event_transition: bool = True
    cursor_increment_by_one: bool = True
    counters_remain_consistent: bool = True
    in_memory_only: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "source_state_immutable",
            "current_event_bound",
            "one_event_transition",
            "cursor_increment_by_one",
            "counters_remain_consistent",
            "in_memory_only",
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
                self.source_state_immutable,
                self.current_event_bound,
                self.one_event_transition,
                self.cursor_increment_by_one,
                self.counters_remain_consistent,
                self.in_memory_only,
                self.no_lookahead,
                self.no_external_io,
            )
        )


def _canonical_transition_payload(
    *,
    schema_version: str,
    session_state_id: str,
    session_state_digest: str,
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
    contract_mode: Phase8OfflineReplayTransitionContractMode,
    action: Phase8OfflineReplayTransitionAction,
    cursor_rule: Phase8OfflineReplayTransitionCursorRule,
    counter_rule: Phase8OfflineReplayTransitionCounterRule,
    transition_index: int,
    current_cursor_index: int,
    current_consumed_count: int,
    current_remaining_count: int,
    current_event_sequence_index: int,
    current_event_id: str,
    current_event_digest: str,
    current_event_time: datetime,
    current_event_timeframe: Phase8Timeframe,
    resulting_cursor_index: int,
    resulting_consumed_count: int,
    resulting_remaining_count: int,
    last_consumed_sequence_index: int,
    completion_after_transition: bool,
    total_event_count: int,
    policy: Phase8OfflineReplayTransitionContractPolicy,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"SESSION_STATE_ID={session_state_id}",
            f"SESSION_STATE_DIGEST={session_state_digest}",
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
            f"CONTRACT_MODE={contract_mode.value}",
            f"ACTION={action.value}",
            f"CURSOR_RULE={cursor_rule.value}",
            f"COUNTER_RULE={counter_rule.value}",
            f"TRANSITION_INDEX={transition_index}",
            f"CURRENT_CURSOR_INDEX={current_cursor_index}",
            (f"CURRENT_CONSUMED_COUNT={current_consumed_count}"),
            (f"CURRENT_REMAINING_COUNT={current_remaining_count}"),
            (f"CURRENT_EVENT_SEQUENCE_INDEX={current_event_sequence_index}"),
            f"CURRENT_EVENT_ID={current_event_id}",
            f"CURRENT_EVENT_DIGEST={current_event_digest}",
            (f"CURRENT_EVENT_TIME={_canonical_datetime(current_event_time)}"),
            (f"CURRENT_EVENT_TIMEFRAME={current_event_timeframe.value}"),
            (f"RESULTING_CURSOR_INDEX={resulting_cursor_index}"),
            (f"RESULTING_CONSUMED_COUNT={resulting_consumed_count}"),
            (f"RESULTING_REMAINING_COUNT={resulting_remaining_count}"),
            (f"LAST_CONSUMED_SEQUENCE_INDEX={last_consumed_sequence_index}"),
            (f"COMPLETION_AFTER_TRANSITION={str(completion_after_transition).lower()}"),
            f"TOTAL_EVENT_COUNT={total_event_count}",
            (f"SOURCE_STATE_IMMUTABLE={str(policy.source_state_immutable).lower()}"),
            (f"CURRENT_EVENT_BOUND={str(policy.current_event_bound).lower()}"),
            (f"ONE_EVENT_TRANSITION={str(policy.one_event_transition).lower()}"),
            (f"CURSOR_INCREMENT_BY_ONE={str(policy.cursor_increment_by_one).lower()}"),
            (f"COUNTERS_REMAIN_CONSISTENT={str(policy.counters_remain_consistent).lower()}"),
            (f"IN_MEMORY_ONLY={str(policy.in_memory_only).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "TRANSITION_CONTRACT_CREATED=true",
            "TRANSITION_EXECUTED=false",
            "NEXT_STATE_CREATED=false",
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
class StrategyPhase8OfflineReplayTransitionContract:
    """
    Immutable contract for the first replay transition.

    The contract binds the initial cursor to its current
    event and defines expected post-transition counters.
    It does not execute the transition, advance the cursor,
    consume the event, create a next state, evaluate
    strategy logic, perform external I/O, contact a broker,
    or submit an order.
    """

    session_state_decision: Phase8OfflineReplaySessionStateDecision = field(repr=False)
    policy: Phase8OfflineReplayTransitionContractPolicy
    schema_version: str
    session_state_id: str
    session_state_digest: str
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
    contract_mode: Phase8OfflineReplayTransitionContractMode
    action: Phase8OfflineReplayTransitionAction
    cursor_rule: Phase8OfflineReplayTransitionCursorRule
    counter_rule: Phase8OfflineReplayTransitionCounterRule
    transition_index: int
    current_cursor_index: int
    current_consumed_count: int
    current_remaining_count: int
    current_event_sequence_index: int
    current_event_id: str
    current_event_digest: str
    current_event_time: datetime
    current_event_timeframe: Phase8Timeframe
    resulting_cursor_index: int
    resulting_consumed_count: int
    resulting_remaining_count: int
    last_consumed_sequence_index: int
    completion_after_transition: bool
    total_event_count: int
    transition_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.session_state_decision,
            Phase8OfflineReplaySessionStateDecision,
        ):
            raise ValueError(
                "session_state_decision must be a Phase8OfflineReplaySessionStateDecision."
            )

        if not self.session_state_decision.is_created:
            raise ValueError(
                "A replay-transition contract requires a created replay-session state."
            )

        if not isinstance(
            self.policy,
            Phase8OfflineReplayTransitionContractPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayTransitionContractPolicy.")

        if not self.policy.is_strict:
            raise ValueError(
                "Replay-transition contract policy must remain strict and no-lookahead."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_REPLAY_TRANSITION_CONTRACT_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current replay-transition contract schema."
            )

        string_fields = (
            ("session_state_id", self.session_state_id),
            (
                "session_state_digest",
                self.session_state_digest,
            ),
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
            ("current_event_id", self.current_event_id),
            (
                "current_event_digest",
                self.current_event_digest,
            ),
            ("transition_digest", self.transition_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "session_state_digest",
            "session_contract_digest",
            "session_plan_digest",
            "event_batch_digest",
            "materialization_plan_digest",
            "event_contract_digest",
            "replay_plan_digest",
            "specification_digest",
            "input_digest",
            "snapshot_digest",
            "current_event_digest",
            "transition_digest",
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
                "contract_mode",
                self.contract_mode,
                Phase8OfflineReplayTransitionContractMode,
            ),
            (
                "action",
                self.action,
                Phase8OfflineReplayTransitionAction,
            ),
            (
                "cursor_rule",
                self.cursor_rule,
                Phase8OfflineReplayTransitionCursorRule,
            ),
            (
                "counter_rule",
                self.counter_rule,
                Phase8OfflineReplayTransitionCounterRule,
            ),
        )

        for field_name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(f"{field_name} must be a {enum_type.__name__} member.")

        if self.contract_mode != (Phase8OfflineReplayTransitionContractMode.IMMUTABLE_SINGLE_EVENT):
            raise ValueError("contract_mode must remain IMMUTABLE_SINGLE_EVENT.")

        if self.action != (Phase8OfflineReplayTransitionAction.CONSUME_CURRENT_EVENT):
            raise ValueError("action must remain CONSUME_CURRENT_EVENT.")

        if self.cursor_rule != (Phase8OfflineReplayTransitionCursorRule.INCREMENT_BY_ONE):
            raise ValueError("cursor_rule must remain INCREMENT_BY_ONE.")

        if self.counter_rule != (
            Phase8OfflineReplayTransitionCounterRule.CONSUMED_PLUS_REMAINING_EQUALS_TOTAL
        ):
            raise ValueError("counter_rule must preserve the exact counter invariant.")

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )
        current_event_time = _aware_datetime(
            self.current_event_time,
            "current_event_time",
        )

        if current_event_time > captured_at:
            raise ValueError("current_event_time cannot exceed captured_at.")

        if not isinstance(
            self.current_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("current_event_timeframe must be a Phase8Timeframe member.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        if not all(isinstance(timeframe, Phase8Timeframe) for timeframe in self.timeframes):
            raise ValueError("timeframes must contain Phase8Timeframe members.")

        transition_index = _non_negative_integer(
            self.transition_index,
            "transition_index",
        )
        current_cursor_index = _non_negative_integer(
            self.current_cursor_index,
            "current_cursor_index",
        )
        current_consumed_count = _non_negative_integer(
            self.current_consumed_count,
            "current_consumed_count",
        )
        current_remaining_count = _positive_integer(
            self.current_remaining_count,
            "current_remaining_count",
        )
        current_event_sequence_index = _non_negative_integer(
            self.current_event_sequence_index,
            "current_event_sequence_index",
        )
        resulting_cursor_index = _positive_integer(
            self.resulting_cursor_index,
            "resulting_cursor_index",
        )
        resulting_consumed_count = _positive_integer(
            self.resulting_consumed_count,
            "resulting_consumed_count",
        )
        resulting_remaining_count = _positive_integer(
            self.resulting_remaining_count,
            "resulting_remaining_count",
        )
        last_consumed_sequence_index = _non_negative_integer(
            self.last_consumed_sequence_index,
            "last_consumed_sequence_index",
        )
        completion_after_transition = _strict_boolean(
            self.completion_after_transition,
            "completion_after_transition",
        )
        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )

        if total_event_count <= 1:
            raise ValueError("The initial transition contract requires more than one replay event.")

        if transition_index != 0:
            raise ValueError("transition_index must be zero for the initial transition.")

        if current_cursor_index != 0:
            raise ValueError("current_cursor_index must be zero for the initial transition.")

        if current_consumed_count != 0:
            raise ValueError("current_consumed_count must be zero for the initial transition.")

        if current_remaining_count != total_event_count:
            raise ValueError("current_remaining_count must equal total_event_count.")

        if current_event_sequence_index != current_cursor_index:
            raise ValueError("current_event_sequence_index must equal current_cursor_index.")

        if resulting_cursor_index != current_cursor_index + 1:
            raise ValueError("resulting_cursor_index must increment the cursor by exactly one.")

        if resulting_consumed_count != current_consumed_count + 1:
            raise ValueError("resulting_consumed_count must increment by exactly one.")

        if resulting_remaining_count != current_remaining_count - 1:
            raise ValueError("resulting_remaining_count must decrement by exactly one.")

        if current_consumed_count + current_remaining_count != total_event_count:
            raise ValueError(
                "Current consumed and remaining counters must equal total_event_count."
            )

        if resulting_consumed_count + resulting_remaining_count != total_event_count:
            raise ValueError(
                "Resulting consumed and remaining counters must equal total_event_count."
            )

        if last_consumed_sequence_index != current_event_sequence_index:
            raise ValueError("last_consumed_sequence_index must equal the current event sequence.")

        expected_completion = resulting_cursor_index == total_event_count

        if completion_after_transition != expected_completion:
            raise ValueError("completion_after_transition does not match the resulting cursor.")

        if completion_after_transition:
            raise ValueError("The initial transition cannot complete an 800-event replay session.")

        state = self.session_state_decision.state_required
        session_contract = state.session_contract
        session_plan = state.session_plan
        event_batch = state.event_batch
        materialization_plan = state.materialization_plan
        event_contract = state.event_contract
        replay_plan = state.replay_plan
        specification = state.specification
        input_package = state.input_package
        snapshot = state.snapshot

        comparisons = (
            (
                "session_state_id",
                normalized_strings["session_state_id"],
                state.stable_id,
            ),
            (
                "session_state_digest",
                normalized_strings["session_state_digest"],
                state.state_digest,
            ),
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
                state.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                state.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable replay-session state lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Replay-transition contracts support Gold/XAUUSD only.")

        if self.direction != state.direction:
            raise ValueError("direction must match the replay-session state.")

        if self.side != state.side:
            raise ValueError("side must match the replay-session state.")

        if captured_at != state.captured_at:
            raise ValueError("captured_at must match the replay-session state.")

        if self.timeframes != state.timeframes:
            raise ValueError("timeframes must match the replay-session state.")

        if not state.is_initial_state:
            raise ValueError("The initial transition requires the immutable initial session state.")

        if not state.has_next_event:
            raise ValueError("The replay-session state has no current event available.")

        if state.completion_reached:
            raise ValueError(
                "A completed replay-session state cannot create a transition contract."
            )

        numeric_state_comparisons = (
            (
                "current_cursor_index",
                current_cursor_index,
                state.cursor_index,
            ),
            (
                "current_consumed_count",
                current_consumed_count,
                state.consumed_count,
            ),
            (
                "current_remaining_count",
                current_remaining_count,
                state.remaining_count,
            ),
            (
                "current_event_sequence_index",
                current_event_sequence_index,
                state.next_event_sequence_index,
            ),
            (
                "total_event_count",
                total_event_count,
                state.total_event_count,
            ),
        )

        for field_name, supplied, expected in numeric_state_comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the replay-session state.")

        current_event = state.next_event

        if normalized_strings["current_event_id"] != (current_event.stable_id):
            raise ValueError("current_event_id must match the event at the session cursor.")

        if normalized_strings["current_event_digest"] != current_event.event_digest:
            raise ValueError("current_event_digest must match the event at the session cursor.")

        if current_event_time != current_event.event_time:
            raise ValueError("current_event_time must match the event at the session cursor.")

        if self.current_event_timeframe != current_event.timeframe:
            raise ValueError("current_event_timeframe must match the event at the session cursor.")

        if current_event.event_time != (current_event.close_time):
            raise ValueError("The current event must represent a closed candle.")

        if not state.forward_only:
            raise ValueError("Replay-session state must remain forward-only.")

        if not state.no_lookahead:
            raise ValueError("Replay-session state must remain no-lookahead.")

        safe_subjects = (
            self.session_state_decision,
            state,
            state.session_contract_decision,
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
            state.verification_receipt,
            snapshot,
            state.contract,
            state.dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Replay-transition lineage violates the non-I/O or non-execution boundary."
            )

        canonical_payload = _canonical_transition_payload(
            schema_version=schema_version,
            session_state_id=normalized_strings["session_state_id"],
            session_state_digest=normalized_strings["session_state_digest"],
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
            contract_mode=self.contract_mode,
            action=self.action,
            cursor_rule=self.cursor_rule,
            counter_rule=self.counter_rule,
            transition_index=transition_index,
            current_cursor_index=current_cursor_index,
            current_consumed_count=current_consumed_count,
            current_remaining_count=current_remaining_count,
            current_event_sequence_index=(current_event_sequence_index),
            current_event_id=normalized_strings["current_event_id"],
            current_event_digest=normalized_strings["current_event_digest"],
            current_event_time=current_event_time,
            current_event_timeframe=(self.current_event_timeframe),
            resulting_cursor_index=resulting_cursor_index,
            resulting_consumed_count=(resulting_consumed_count),
            resulting_remaining_count=(resulting_remaining_count),
            last_consumed_sequence_index=(last_consumed_sequence_index),
            completion_after_transition=(completion_after_transition),
            total_event_count=total_event_count,
            policy=self.policy,
        )

        if normalized_strings["transition_digest"] != _sha256_digest(canonical_payload):
            raise ValueError(
                "transition_digest does not match the canonical replay-transition contract."
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
            "current_event_time",
            current_event_time,
        )
        object.__setattr__(
            self,
            "transition_index",
            transition_index,
        )
        object.__setattr__(
            self,
            "current_cursor_index",
            current_cursor_index,
        )
        object.__setattr__(
            self,
            "current_consumed_count",
            current_consumed_count,
        )
        object.__setattr__(
            self,
            "current_remaining_count",
            current_remaining_count,
        )
        object.__setattr__(
            self,
            "current_event_sequence_index",
            current_event_sequence_index,
        )
        object.__setattr__(
            self,
            "resulting_cursor_index",
            resulting_cursor_index,
        )
        object.__setattr__(
            self,
            "resulting_consumed_count",
            resulting_consumed_count,
        )
        object.__setattr__(
            self,
            "resulting_remaining_count",
            resulting_remaining_count,
        )
        object.__setattr__(
            self,
            "last_consumed_sequence_index",
            last_consumed_sequence_index,
        )
        object.__setattr__(
            self,
            "completion_after_transition",
            completion_after_transition,
        )
        object.__setattr__(
            self,
            "total_event_count",
            total_event_count,
        )

    @property
    def session_state(
        self,
    ) -> StrategyPhase8OfflineReplaySessionState:
        return self.session_state_decision.state_required

    @property
    def session_contract(
        self,
    ) -> StrategyPhase8OfflineReplaySessionContract:
        return self.session_state.session_contract

    @property
    def session_plan(
        self,
    ) -> StrategyPhase8OfflineReplaySessionPlan:
        return self.session_state.session_plan

    @property
    def event_batch(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        return self.session_state.event_batch

    @property
    def materialization_plan(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        return self.session_state.materialization_plan

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.session_state.event_contract

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.session_state.replay_plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.session_state.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.session_state.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.session_state.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.session_state.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.session_state.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.session_state.dry_run_package

    @property
    def current_event(self) -> Phase8OfflineReplayEvent:
        return self.session_state.next_event

    @property
    def canonical_payload(self) -> str:
        return _canonical_transition_payload(
            schema_version=self.schema_version,
            session_state_id=self.session_state_id,
            session_state_digest=self.session_state_digest,
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
            contract_mode=self.contract_mode,
            action=self.action,
            cursor_rule=self.cursor_rule,
            counter_rule=self.counter_rule,
            transition_index=self.transition_index,
            current_cursor_index=self.current_cursor_index,
            current_consumed_count=(self.current_consumed_count),
            current_remaining_count=(self.current_remaining_count),
            current_event_sequence_index=(self.current_event_sequence_index),
            current_event_id=self.current_event_id,
            current_event_digest=self.current_event_digest,
            current_event_time=self.current_event_time,
            current_event_timeframe=(self.current_event_timeframe),
            resulting_cursor_index=(self.resulting_cursor_index),
            resulting_consumed_count=(self.resulting_consumed_count),
            resulting_remaining_count=(self.resulting_remaining_count),
            last_consumed_sequence_index=(self.last_consumed_sequence_index),
            completion_after_transition=(self.completion_after_transition),
            total_event_count=self.total_event_count,
            policy=self.policy,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def contract_only(self) -> bool:
        return True

    @property
    def source_state_immutable(self) -> bool:
        return self.policy.source_state_immutable

    @property
    def current_event_bound(self) -> bool:
        return self.policy.current_event_bound

    @property
    def one_event_transition(self) -> bool:
        return self.policy.one_event_transition

    @property
    def forward_only(self) -> bool:
        return self.policy.cursor_increment_by_one

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def executes_transition(self) -> bool:
        return False

    @property
    def creates_next_state(self) -> bool:
        return False

    @property
    def advances_cursor(self) -> bool:
        return False

    @property
    def consumes_events(self) -> bool:
        return False

    @property
    def starts_session(self) -> bool:
        return False

    @property
    def starts_replay(self) -> bool:
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
    def can_continue_to_transition_application(
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
    def transition_contract_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_TRANSITION_CONTRACT:"
            f"TRANSITION_SHA256[{self.transition_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.session_state_decision.stable_id}:{self.transition_contract_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayTransitionContractDecision:
    """Immutable replay-transition contract decision."""

    session_state_decision: Phase8OfflineReplaySessionStateDecision = field(repr=False)
    status: Phase8OfflineReplayTransitionContractStatus
    reason: Phase8OfflineReplayTransitionContractReason
    blockers: tuple[
        Phase8OfflineReplayTransitionContractBlocker,
        ...,
    ]
    transition_contract: StrategyPhase8OfflineReplayTransitionContract | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.session_state_decision,
            Phase8OfflineReplaySessionStateDecision,
        ):
            raise ValueError(
                "session_state_decision must be a Phase8OfflineReplaySessionStateDecision."
            )

        try:
            status = Phase8OfflineReplayTransitionContractStatus(self.status)
            reason = Phase8OfflineReplayTransitionContractReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported replay-transition contract status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplayTransitionContractBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Replay-transition blockers cannot contain duplicates.")

        if self.session_state_decision.is_blocked:
            if (
                status != (Phase8OfflineReplayTransitionContractStatus.BLOCKED)
                or reason != (Phase8OfflineReplayTransitionContractReason.SESSION_STATE_BLOCKED)
                or blockers != (Phase8OfflineReplayTransitionContractBlocker.SESSION_STATE_BLOCKED,)
                or self.transition_contract is not None
            ):
                raise ValueError(
                    "Blocked replay-transition result does not match its session state."
                )
        else:
            if (
                status != (Phase8OfflineReplayTransitionContractStatus.CREATED)
                or reason != (Phase8OfflineReplayTransitionContractReason.CREATED)
                or blockers
                or not isinstance(
                    self.transition_contract,
                    StrategyPhase8OfflineReplayTransitionContract,
                )
                or self.transition_contract.session_state_decision
                is not self.session_state_decision
            ):
                raise ValueError(
                    "Created replay-transition result does not match its session state."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.session_state_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.session_state_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineReplayTransitionContractStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_transition_contract(self) -> bool:
        return self.transition_contract is not None

    @property
    def transition_contract_required(
        self,
    ) -> StrategyPhase8OfflineReplayTransitionContract:
        if self.transition_contract is None:
            raise ValueError("No Phase 8 offline replay-transition contract was created.")

        return self.transition_contract

    @property
    def executes_transition(self) -> bool:
        return False

    @property
    def creates_next_state(self) -> bool:
        return False

    @property
    def advances_cursor(self) -> bool:
        return False

    @property
    def consumes_events(self) -> bool:
        return False

    @property
    def starts_session(self) -> bool:
        return False

    @property
    def starts_replay(self) -> bool:
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
    def can_continue_to_transition_application(
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
            f"{self.session_state_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_TRANSITION_"
            "CONTRACT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplayTransitionContractFactory:
    """Pure immutable initial-transition contract factory."""

    def generate(
        self,
        session_state_decision: (Phase8OfflineReplaySessionStateDecision),
        policy: (Phase8OfflineReplayTransitionContractPolicy | None) = None,
    ) -> Phase8OfflineReplayTransitionContractDecision:
        if not isinstance(
            session_state_decision,
            Phase8OfflineReplaySessionStateDecision,
        ):
            raise Phase8OfflineReplayTransitionContractError(
                Phase8OfflineReplayTransitionContractErrorReason.INVALID_SESSION_STATE_DECISION,
                "session_state_decision must be a Phase8OfflineReplaySessionStateDecision.",
            )

        selected_policy = policy or Phase8OfflineReplayTransitionContractPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplayTransitionContractPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayTransitionContractPolicy.")

        if session_state_decision.is_blocked:
            return Phase8OfflineReplayTransitionContractDecision(
                session_state_decision=(session_state_decision),
                status=(Phase8OfflineReplayTransitionContractStatus.BLOCKED),
                reason=(Phase8OfflineReplayTransitionContractReason.SESSION_STATE_BLOCKED),
                blockers=(Phase8OfflineReplayTransitionContractBlocker.SESSION_STATE_BLOCKED,),
                transition_contract=None,
            )

        state = session_state_decision.state_required
        session_contract = state.session_contract
        session_plan = state.session_plan
        event_batch = state.event_batch
        materialization_plan = state.materialization_plan
        event_contract = state.event_contract
        replay_plan = state.replay_plan
        specification = state.specification
        input_package = state.input_package
        snapshot = state.snapshot
        current_event = state.next_event

        transition_index = 0
        resulting_cursor_index = state.cursor_index + 1
        resulting_consumed_count = state.consumed_count + 1
        resulting_remaining_count = state.remaining_count - 1
        last_consumed_sequence_index = current_event.sequence_index
        completion_after_transition = resulting_cursor_index == state.total_event_count

        canonical_payload = _canonical_transition_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_TRANSITION_CONTRACT_SCHEMA_VERSION),
            session_state_id=state.stable_id,
            session_state_digest=state.state_digest,
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
            broker_symbol=state.broker_symbol,
            direction=state.direction,
            side=state.side,
            source_name=state.source_name,
            captured_at=state.captured_at,
            timeframes=state.timeframes,
            contract_mode=(Phase8OfflineReplayTransitionContractMode.IMMUTABLE_SINGLE_EVENT),
            action=(Phase8OfflineReplayTransitionAction.CONSUME_CURRENT_EVENT),
            cursor_rule=(Phase8OfflineReplayTransitionCursorRule.INCREMENT_BY_ONE),
            counter_rule=(
                Phase8OfflineReplayTransitionCounterRule.CONSUMED_PLUS_REMAINING_EQUALS_TOTAL
            ),
            transition_index=transition_index,
            current_cursor_index=state.cursor_index,
            current_consumed_count=state.consumed_count,
            current_remaining_count=state.remaining_count,
            current_event_sequence_index=(current_event.sequence_index),
            current_event_id=current_event.stable_id,
            current_event_digest=(current_event.event_digest),
            current_event_time=current_event.event_time,
            current_event_timeframe=(current_event.timeframe),
            resulting_cursor_index=(resulting_cursor_index),
            resulting_consumed_count=(resulting_consumed_count),
            resulting_remaining_count=(resulting_remaining_count),
            last_consumed_sequence_index=(last_consumed_sequence_index),
            completion_after_transition=(completion_after_transition),
            total_event_count=state.total_event_count,
            policy=selected_policy,
        )

        transition_contract = StrategyPhase8OfflineReplayTransitionContract(
            session_state_decision=(session_state_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_TRANSITION_CONTRACT_SCHEMA_VERSION),
            session_state_id=state.stable_id,
            session_state_digest=state.state_digest,
            session_contract_id=(session_contract.stable_id),
            session_contract_digest=(session_contract.contract_digest),
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
            broker_symbol=state.broker_symbol,
            direction=state.direction,
            side=state.side,
            source_name=state.source_name,
            captured_at=state.captured_at,
            timeframes=state.timeframes,
            contract_mode=(Phase8OfflineReplayTransitionContractMode.IMMUTABLE_SINGLE_EVENT),
            action=(Phase8OfflineReplayTransitionAction.CONSUME_CURRENT_EVENT),
            cursor_rule=(Phase8OfflineReplayTransitionCursorRule.INCREMENT_BY_ONE),
            counter_rule=(
                Phase8OfflineReplayTransitionCounterRule.CONSUMED_PLUS_REMAINING_EQUALS_TOTAL
            ),
            transition_index=transition_index,
            current_cursor_index=state.cursor_index,
            current_consumed_count=(state.consumed_count),
            current_remaining_count=(state.remaining_count),
            current_event_sequence_index=(current_event.sequence_index),
            current_event_id=(current_event.stable_id),
            current_event_digest=(current_event.event_digest),
            current_event_time=(current_event.event_time),
            current_event_timeframe=(current_event.timeframe),
            resulting_cursor_index=(resulting_cursor_index),
            resulting_consumed_count=(resulting_consumed_count),
            resulting_remaining_count=(resulting_remaining_count),
            last_consumed_sequence_index=(last_consumed_sequence_index),
            completion_after_transition=(completion_after_transition),
            total_event_count=(state.total_event_count),
            transition_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplayTransitionContractDecision(
            session_state_decision=(session_state_decision),
            status=(Phase8OfflineReplayTransitionContractStatus.CREATED),
            reason=(Phase8OfflineReplayTransitionContractReason.CREATED),
            blockers=(),
            transition_contract=transition_contract,
        )

    def build(
        self,
        session_state_decision: (Phase8OfflineReplaySessionStateDecision),
        policy: (Phase8OfflineReplayTransitionContractPolicy | None) = None,
    ) -> Phase8OfflineReplayTransitionContractDecision:
        return self.generate(
            session_state_decision,
            policy,
        )

    def evaluate(
        self,
        session_state_decision: (Phase8OfflineReplaySessionStateDecision),
        policy: (Phase8OfflineReplayTransitionContractPolicy | None) = None,
    ) -> Phase8OfflineReplayTransitionContractDecision:
        return self.generate(
            session_state_decision,
            policy,
        )


def generate_phase8_offline_replay_transition_contract(
    session_state_decision: (Phase8OfflineReplaySessionStateDecision),
    policy: (Phase8OfflineReplayTransitionContractPolicy | None) = None,
) -> Phase8OfflineReplayTransitionContractDecision:
    return StrategyPhase8OfflineReplayTransitionContractFactory().generate(
        session_state_decision,
        policy,
    )


Phase8OfflineReplayTransitionContract = StrategyPhase8OfflineReplayTransitionContract
Phase8OfflineReplayTransitionContractFactory = StrategyPhase8OfflineReplayTransitionContractFactory
