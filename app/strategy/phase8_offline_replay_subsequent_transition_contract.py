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
from app.strategy.phase8_offline_replay_next_transition_application import (
    StrategyPhase8OfflineReplayNextTransitionApplicationReceipt,
)
from app.strategy.phase8_offline_replay_next_transition_contract import (
    StrategyPhase8OfflineReplayNextTransitionContract,
)
from app.strategy.phase8_offline_replay_plan import (
    StrategyPhase8OfflineReplayPlan,
)
from app.strategy.phase8_offline_replay_progressed_session_state import (
    Phase8OfflineReplayProgressedSessionStateDecision,
    StrategyPhase8OfflineReplayProgressedSessionState,
)
from app.strategy.phase8_offline_replay_session_contract import (
    StrategyPhase8OfflineReplaySessionContract,
)
from app.strategy.phase8_offline_replay_session_plan import (
    StrategyPhase8OfflineReplaySessionPlan,
)
from app.strategy.phase8_offline_replay_session_state import (
    StrategyPhase8OfflineReplaySessionState,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_TRANSITION_CONTRACT_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplaySubsequentTransitionContractMode(
    str,
    Enum,
):
    IMMUTABLE_SINGLE_EVENT = "IMMUTABLE_SINGLE_EVENT"


class Phase8OfflineReplaySubsequentTransitionAction(
    str,
    Enum,
):
    CONSUME_CURRENT_EVENT = "CONSUME_CURRENT_EVENT"


class Phase8OfflineReplaySubsequentTransitionContractStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplaySubsequentTransitionContractReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    PROGRESSED_STATE_BLOCKED = "PROGRESSED_STATE_BLOCKED"


class Phase8OfflineReplaySubsequentTransitionContractBlocker(
    str,
    Enum,
):
    PROGRESSED_STATE_BLOCKED = "PROGRESSED_STATE_BLOCKED"


class Phase8OfflineReplaySubsequentTransitionContractErrorReason(
    str,
    Enum,
):
    INVALID_PROGRESSED_STATE_DECISION = "INVALID_PROGRESSED_STATE_DECISION"


class Phase8OfflineReplaySubsequentTransitionContractError(
    RuntimeError,
):
    """Structured subsequent-transition contract failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplaySubsequentTransitionContractErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplaySubsequentTransitionContractErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 subsequent offline replay-transition "
            f"contract error [{self.reason.value}]: "
            f"{self.message}"
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


def _has_safe_external_boundary(subject: object) -> bool:
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

    for attribute_name in (
        "fetches_data",
        "initializes_mt5",
        "executes_replay",
        "evaluates_strategy",
        "executes_simulation",
        "emits_orders",
        "starts_session",
        "starts_replay",
    ):
        if hasattr(subject, attribute_name) and getattr(subject, attribute_name):
            return False

    return True


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplaySubsequentTransitionContractPolicy:
    """Strict subsequent single-event transition rules."""

    progressed_state_immutable: bool = True
    current_event_bound: bool = True
    sequence_continuity_verified: bool = True
    one_event_transition: bool = True
    cursor_increment_by_one: bool = True
    counters_remain_consistent: bool = True
    next_event_bound: bool = True
    forward_only: bool = True
    in_memory_only: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "progressed_state_immutable",
            "current_event_bound",
            "sequence_continuity_verified",
            "one_event_transition",
            "cursor_increment_by_one",
            "counters_remain_consistent",
            "next_event_bound",
            "forward_only",
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
                self.progressed_state_immutable,
                self.current_event_bound,
                self.sequence_continuity_verified,
                self.one_event_transition,
                self.cursor_increment_by_one,
                self.counters_remain_consistent,
                self.next_event_bound,
                self.forward_only,
                self.in_memory_only,
                self.no_lookahead,
                self.no_external_io,
            )
        )


def _canonical_transition_payload(
    *,
    schema_version: str,
    progressed_state_id: str,
    progressed_state_digest: str,
    application_receipt_id: str,
    application_digest: str,
    event_batch_id: str,
    event_batch_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    timeframes: tuple[Phase8Timeframe, ...],
    contract_mode: (Phase8OfflineReplaySubsequentTransitionContractMode),
    action: Phase8OfflineReplaySubsequentTransitionAction,
    transition_index: int,
    current_cursor_index: int,
    current_consumed_count: int,
    current_remaining_count: int,
    prior_last_consumed_sequence_index: int,
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
    next_event_sequence_index: int,
    next_event_id: str,
    next_event_digest: str,
    next_event_time: datetime,
    next_event_timeframe: Phase8Timeframe,
    total_event_count: int,
    policy: (Phase8OfflineReplaySubsequentTransitionContractPolicy),
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"PROGRESSED_STATE_ID={progressed_state_id}",
            (f"PROGRESSED_STATE_DIGEST={progressed_state_digest}"),
            (f"APPLICATION_RECEIPT_ID={application_receipt_id}"),
            f"APPLICATION_DIGEST={application_digest}",
            f"EVENT_BATCH_ID={event_batch_id}",
            f"EVENT_BATCH_DIGEST={event_batch_digest}",
            f"BROKER_SYMBOL={broker_symbol}",
            f"DIRECTION={direction.value}",
            f"SIDE={side.value}",
            f"SOURCE_NAME={source_name}",
            (f"CAPTURED_AT={_canonical_datetime(captured_at)}"),
            ("TIMEFRAMES=" + ",".join(timeframe.value for timeframe in timeframes)),
            f"CONTRACT_MODE={contract_mode.value}",
            f"ACTION={action.value}",
            f"TRANSITION_INDEX={transition_index}",
            f"CURRENT_CURSOR_INDEX={current_cursor_index}",
            (f"CURRENT_CONSUMED_COUNT={current_consumed_count}"),
            (f"CURRENT_REMAINING_COUNT={current_remaining_count}"),
            (f"PRIOR_LAST_CONSUMED_SEQUENCE_INDEX={prior_last_consumed_sequence_index}"),
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
            (f"NEXT_EVENT_SEQUENCE_INDEX={next_event_sequence_index}"),
            f"NEXT_EVENT_ID={next_event_id}",
            f"NEXT_EVENT_DIGEST={next_event_digest}",
            (f"NEXT_EVENT_TIME={_canonical_datetime(next_event_time)}"),
            (f"NEXT_EVENT_TIMEFRAME={next_event_timeframe.value}"),
            f"TOTAL_EVENT_COUNT={total_event_count}",
            (f"PROGRESSED_STATE_IMMUTABLE={str(policy.progressed_state_immutable).lower()}"),
            (f"CURRENT_EVENT_BOUND={str(policy.current_event_bound).lower()}"),
            (f"SEQUENCE_CONTINUITY_VERIFIED={str(policy.sequence_continuity_verified).lower()}"),
            (f"ONE_EVENT_TRANSITION={str(policy.one_event_transition).lower()}"),
            (f"CURSOR_INCREMENT_BY_ONE={str(policy.cursor_increment_by_one).lower()}"),
            (f"COUNTERS_REMAIN_CONSISTENT={str(policy.counters_remain_consistent).lower()}"),
            (f"NEXT_EVENT_BOUND={str(policy.next_event_bound).lower()}"),
            (f"FORWARD_ONLY={str(policy.forward_only).lower()}"),
            (f"IN_MEMORY_ONLY={str(policy.in_memory_only).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "SUBSEQUENT_TRANSITION_CONTRACT_CREATED=true",
            "TRANSITION_EXECUTED=false",
            "EVENT_CONSUMPTION=false",
            "CURSOR_ADVANCEMENT=false",
            "NEXT_STATE_CREATED=false",
            "REPLAY_LOOP_EXECUTION=false",
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
class StrategyPhase8OfflineReplaySubsequentTransitionContract:
    """
    Immutable contract for event sequence two.

    The progressed source state remains unchanged. This
    contract only defines the expected cursor and accounting
    after one future in-memory transition.
    """

    progressed_state_decision: Phase8OfflineReplayProgressedSessionStateDecision = field(repr=False)
    policy: Phase8OfflineReplaySubsequentTransitionContractPolicy
    schema_version: str
    progressed_state_id: str
    progressed_state_digest: str
    application_receipt_id: str
    application_digest: str
    event_batch_id: str
    event_batch_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    source_name: str
    captured_at: datetime
    timeframes: tuple[Phase8Timeframe, ...]
    contract_mode: Phase8OfflineReplaySubsequentTransitionContractMode
    action: Phase8OfflineReplaySubsequentTransitionAction
    transition_index: int
    current_cursor_index: int
    current_consumed_count: int
    current_remaining_count: int
    prior_last_consumed_sequence_index: int
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
    next_event_sequence_index: int
    next_event_id: str
    next_event_digest: str
    next_event_time: datetime
    next_event_timeframe: Phase8Timeframe
    total_event_count: int
    transition_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.progressed_state_decision,
            Phase8OfflineReplayProgressedSessionStateDecision,
        ):
            raise ValueError(
                "progressed_state_decision must be a "
                "Phase8OfflineReplayProgressedSessionStateDecision."
            )

        if not self.progressed_state_decision.is_created:
            raise ValueError(
                "A subsequent-transition contract requires a created progressed session state."
            )

        if not isinstance(
            self.policy,
            Phase8OfflineReplaySubsequentTransitionContractPolicy,
        ):
            raise ValueError(
                "policy must be a Phase8OfflineReplaySubsequentTransitionContractPolicy."
            )

        if not self.policy.is_strict:
            raise ValueError("Subsequent-transition policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_TRANSITION_CONTRACT_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current subsequent-transition contract schema."
            )

        string_fields = (
            ("progressed_state_id", self.progressed_state_id),
            (
                "progressed_state_digest",
                self.progressed_state_digest,
            ),
            (
                "application_receipt_id",
                self.application_receipt_id,
            ),
            ("application_digest", self.application_digest),
            ("event_batch_id", self.event_batch_id),
            ("event_batch_digest", self.event_batch_digest),
            ("broker_symbol", self.broker_symbol),
            ("source_name", self.source_name),
            ("current_event_id", self.current_event_id),
            (
                "current_event_digest",
                self.current_event_digest,
            ),
            ("next_event_id", self.next_event_id),
            ("next_event_digest", self.next_event_digest),
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
            "progressed_state_digest",
            "application_digest",
            "event_batch_digest",
            "current_event_digest",
            "next_event_digest",
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

        if not isinstance(
            self.contract_mode,
            Phase8OfflineReplaySubsequentTransitionContractMode,
        ):
            raise ValueError(
                "contract_mode must be a "
                "Phase8OfflineReplaySubsequentTransitionContractMode "
                "member."
            )

        if self.contract_mode != (
            Phase8OfflineReplaySubsequentTransitionContractMode.IMMUTABLE_SINGLE_EVENT
        ):
            raise ValueError("contract_mode must remain IMMUTABLE_SINGLE_EVENT.")

        if not isinstance(
            self.action,
            Phase8OfflineReplaySubsequentTransitionAction,
        ):
            raise ValueError(
                "action must be a Phase8OfflineReplaySubsequentTransitionAction member."
            )

        if self.action != (Phase8OfflineReplaySubsequentTransitionAction.CONSUME_CURRENT_EVENT):
            raise ValueError("action must remain CONSUME_CURRENT_EVENT.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        if not isinstance(
            self.current_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("current_event_timeframe must be a Phase8Timeframe member.")

        if not isinstance(
            self.next_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("next_event_timeframe must be a Phase8Timeframe member.")

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )
        current_event_time = _aware_datetime(
            self.current_event_time,
            "current_event_time",
        )
        next_event_time = _aware_datetime(
            self.next_event_time,
            "next_event_time",
        )

        if current_event_time > captured_at:
            raise ValueError("current_event_time cannot exceed captured_at.")

        if next_event_time > captured_at:
            raise ValueError("next_event_time cannot exceed captured_at.")

        if next_event_time < current_event_time:
            raise ValueError("next_event_time cannot precede the current event.")

        transition_index = _positive_integer(
            self.transition_index,
            "transition_index",
        )
        current_cursor_index = _positive_integer(
            self.current_cursor_index,
            "current_cursor_index",
        )
        current_consumed_count = _positive_integer(
            self.current_consumed_count,
            "current_consumed_count",
        )
        current_remaining_count = _positive_integer(
            self.current_remaining_count,
            "current_remaining_count",
        )
        prior_last_consumed_sequence_index = _positive_integer(
            self.prior_last_consumed_sequence_index,
            "prior_last_consumed_sequence_index",
        )
        current_event_sequence_index = _positive_integer(
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
        last_consumed_sequence_index = _positive_integer(
            self.last_consumed_sequence_index,
            "last_consumed_sequence_index",
        )
        next_event_sequence_index = _positive_integer(
            self.next_event_sequence_index,
            "next_event_sequence_index",
        )
        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )
        completion_after_transition = _strict_boolean(
            self.completion_after_transition,
            "completion_after_transition",
        )

        if transition_index != current_consumed_count:
            raise ValueError("transition_index must equal the current consumed count.")

        if current_cursor_index != current_consumed_count:
            raise ValueError("current_cursor_index must equal the current consumed count.")

        if current_consumed_count + current_remaining_count != total_event_count:
            raise ValueError("Current counters must preserve total_event_count.")

        if prior_last_consumed_sequence_index != (current_cursor_index - 1):
            raise ValueError(
                "prior_last_consumed_sequence_index must equal current_cursor_index minus one."
            )

        if current_event_sequence_index != (current_cursor_index):
            raise ValueError("current_event_sequence_index must equal current_cursor_index.")

        if current_event_sequence_index != (prior_last_consumed_sequence_index + 1):
            raise ValueError("Current-event sequence continuity is invalid.")

        if resulting_cursor_index != (current_cursor_index + 1):
            raise ValueError("resulting_cursor_index must increment by exactly one.")

        if resulting_consumed_count != (current_consumed_count + 1):
            raise ValueError("resulting_consumed_count must increment by exactly one.")

        if resulting_remaining_count != (current_remaining_count - 1):
            raise ValueError("resulting_remaining_count must decrement by exactly one.")

        if resulting_consumed_count + resulting_remaining_count != total_event_count:
            raise ValueError("Resulting counters must preserve total_event_count.")

        if last_consumed_sequence_index != (current_event_sequence_index):
            raise ValueError("last_consumed_sequence_index must equal the current event sequence.")

        expected_completion = resulting_cursor_index == total_event_count

        if completion_after_transition != expected_completion:
            raise ValueError("completion_after_transition does not match the resulting cursor.")

        if completion_after_transition:
            raise ValueError("The third transition cannot complete this 800-event replay session.")

        if next_event_sequence_index != (resulting_cursor_index):
            raise ValueError("next_event_sequence_index must equal the resulting cursor.")

        progressed_state = self.progressed_state_decision.state_required
        application_receipt = progressed_state.application_receipt
        event_batch = progressed_state.event_batch

        comparisons = (
            (
                "progressed_state_id",
                normalized_strings["progressed_state_id"],
                progressed_state.stable_id,
            ),
            (
                "progressed_state_digest",
                normalized_strings["progressed_state_digest"],
                progressed_state.state_digest,
            ),
            (
                "application_receipt_id",
                normalized_strings["application_receipt_id"],
                application_receipt.stable_id,
            ),
            (
                "application_digest",
                normalized_strings["application_digest"],
                application_receipt.application_digest,
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
                "broker_symbol",
                normalized_strings["broker_symbol"],
                progressed_state.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                progressed_state.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the immutable progressed-state lineage.")

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Subsequent-transition contracts support Gold/XAUUSD only.")

        if self.direction != progressed_state.direction:
            raise ValueError("direction must match the progressed state.")

        if self.side != progressed_state.side:
            raise ValueError("side must match the progressed state.")

        if captured_at != progressed_state.captured_at:
            raise ValueError("captured_at must match the progressed state.")

        if self.timeframes != progressed_state.timeframes:
            raise ValueError("timeframes must match the progressed state.")

        state_comparisons = (
            (
                "transition_index",
                transition_index,
                progressed_state.consumed_count,
            ),
            (
                "current_cursor_index",
                current_cursor_index,
                progressed_state.cursor_index,
            ),
            (
                "current_consumed_count",
                current_consumed_count,
                progressed_state.consumed_count,
            ),
            (
                "current_remaining_count",
                current_remaining_count,
                progressed_state.remaining_count,
            ),
            (
                "prior_last_consumed_sequence_index",
                prior_last_consumed_sequence_index,
                (progressed_state.last_consumed_sequence_index),
            ),
            (
                "current_event_sequence_index",
                current_event_sequence_index,
                progressed_state.next_event_sequence_index,
            ),
            (
                "total_event_count",
                total_event_count,
                progressed_state.total_event_count,
            ),
        )

        for field_name, supplied, expected in state_comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the progressed session state.")

        if progressed_state.state_version != 2:
            raise ValueError(
                "The progressed source state must represent exactly two consumed events."
            )

        if progressed_state.cursor_index != 2:
            raise ValueError("The progressed source cursor must remain two.")

        if progressed_state.completion_reached:
            raise ValueError("A completed state cannot create a subsequent-transition contract.")

        if not progressed_state.has_next_event:
            raise ValueError("The progressed state has no next event.")

        current_event = progressed_state.next_event

        if normalized_strings["current_event_id"] != (current_event.stable_id):
            raise ValueError("current_event_id must match the event at the progressed cursor.")

        if normalized_strings["current_event_digest"] != current_event.event_digest:
            raise ValueError("current_event_digest must match the event at the progressed cursor.")

        if current_event_time != current_event.event_time:
            raise ValueError("current_event_time must match the event at the progressed cursor.")

        if self.current_event_timeframe != (current_event.timeframe):
            raise ValueError(
                "current_event_timeframe must match the event at the progressed cursor."
            )

        next_event = event_batch.events[resulting_cursor_index]

        if next_event.sequence_index != (next_event_sequence_index):
            raise ValueError("Event batch does not preserve the resulting cursor sequence.")

        if normalized_strings["next_event_id"] != (next_event.stable_id):
            raise ValueError("next_event_id must match the event at the resulting cursor.")

        if normalized_strings["next_event_digest"] != (next_event.event_digest):
            raise ValueError("next_event_digest must match the event at the resulting cursor.")

        if next_event_time != next_event.event_time:
            raise ValueError("next_event_time must match the event at the resulting cursor.")

        if self.next_event_timeframe != next_event.timeframe:
            raise ValueError("next_event_timeframe must match the event at the resulting cursor.")

        if current_event.event_time != (current_event.close_time):
            raise ValueError("The current event must represent a closed candle.")

        if next_event.event_time != next_event.close_time:
            raise ValueError("The following event must represent a closed candle.")

        safe_subjects = (
            self.progressed_state_decision,
            progressed_state,
            progressed_state.next_transition_application_decision,
            application_receipt,
            (application_receipt.next_transition_contract_decision),
            progressed_state.next_transition_contract,
            progressed_state.prior_advanced_state,
            progressed_state.prior_application_receipt,
            progressed_state.prior_transition_contract,
            progressed_state.source_state,
            progressed_state.session_contract,
            progressed_state.session_plan,
            event_batch,
            progressed_state.materialization_plan,
            progressed_state.event_contract,
            progressed_state.replay_plan,
            progressed_state.specification,
            progressed_state.input_package,
            progressed_state.verification_receipt,
            progressed_state.snapshot,
            progressed_state.contract,
            progressed_state.dry_run_package,
        )

        if not all(_has_safe_external_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Subsequent-transition lineage violates the external-I/O or broker boundary."
            )

        canonical_payload = _canonical_transition_payload(
            schema_version=schema_version,
            progressed_state_id=normalized_strings["progressed_state_id"],
            progressed_state_digest=normalized_strings["progressed_state_digest"],
            application_receipt_id=normalized_strings["application_receipt_id"],
            application_digest=normalized_strings["application_digest"],
            event_batch_id=normalized_strings["event_batch_id"],
            event_batch_digest=normalized_strings["event_batch_digest"],
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=normalized_strings["source_name"],
            captured_at=captured_at,
            timeframes=self.timeframes,
            contract_mode=self.contract_mode,
            action=self.action,
            transition_index=transition_index,
            current_cursor_index=current_cursor_index,
            current_consumed_count=current_consumed_count,
            current_remaining_count=current_remaining_count,
            prior_last_consumed_sequence_index=(prior_last_consumed_sequence_index),
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
            next_event_sequence_index=(next_event_sequence_index),
            next_event_id=normalized_strings["next_event_id"],
            next_event_digest=normalized_strings["next_event_digest"],
            next_event_time=next_event_time,
            next_event_timeframe=self.next_event_timeframe,
            total_event_count=total_event_count,
            policy=self.policy,
        )

        if normalized_strings["transition_digest"] != (_sha256_digest(canonical_payload)):
            raise ValueError(
                "transition_digest does not match the canonical subsequent-transition contract."
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
            "next_event_time",
            next_event_time,
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
            "prior_last_consumed_sequence_index",
            prior_last_consumed_sequence_index,
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
            "next_event_sequence_index",
            next_event_sequence_index,
        )
        object.__setattr__(
            self,
            "total_event_count",
            total_event_count,
        )

    @property
    def progressed_state(
        self,
    ) -> StrategyPhase8OfflineReplayProgressedSessionState:
        return self.progressed_state_decision.state_required

    @property
    def application_receipt(
        self,
    ) -> StrategyPhase8OfflineReplayNextTransitionApplicationReceipt:
        return self.progressed_state.application_receipt

    @property
    def prior_transition_contract(
        self,
    ) -> StrategyPhase8OfflineReplayNextTransitionContract:
        return self.progressed_state.next_transition_contract

    @property
    def source_state(
        self,
    ) -> StrategyPhase8OfflineReplaySessionState:
        return self.progressed_state.source_state

    @property
    def session_contract(
        self,
    ) -> StrategyPhase8OfflineReplaySessionContract:
        return self.progressed_state.session_contract

    @property
    def session_plan(
        self,
    ) -> StrategyPhase8OfflineReplaySessionPlan:
        return self.progressed_state.session_plan

    @property
    def event_batch(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        return self.progressed_state.event_batch

    @property
    def materialization_plan(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        return self.progressed_state.materialization_plan

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.progressed_state.event_contract

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.progressed_state.replay_plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.progressed_state.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.progressed_state.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.progressed_state.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.progressed_state.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.progressed_state.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.progressed_state.dry_run_package

    @property
    def current_event(self) -> Phase8OfflineReplayEvent:
        return self.progressed_state.next_event

    @property
    def next_event(self) -> Phase8OfflineReplayEvent:
        return self.event_batch.events[self.resulting_cursor_index]

    @property
    def canonical_payload(self) -> str:
        return _canonical_transition_payload(
            schema_version=self.schema_version,
            progressed_state_id=self.progressed_state_id,
            progressed_state_digest=(self.progressed_state_digest),
            application_receipt_id=(self.application_receipt_id),
            application_digest=self.application_digest,
            event_batch_id=self.event_batch_id,
            event_batch_digest=self.event_batch_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=self.source_name,
            captured_at=self.captured_at,
            timeframes=self.timeframes,
            contract_mode=self.contract_mode,
            action=self.action,
            transition_index=self.transition_index,
            current_cursor_index=self.current_cursor_index,
            current_consumed_count=(self.current_consumed_count),
            current_remaining_count=(self.current_remaining_count),
            prior_last_consumed_sequence_index=(self.prior_last_consumed_sequence_index),
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
            next_event_sequence_index=(self.next_event_sequence_index),
            next_event_id=self.next_event_id,
            next_event_digest=self.next_event_digest,
            next_event_time=self.next_event_time,
            next_event_timeframe=self.next_event_timeframe,
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
    def one_event_transition(self) -> bool:
        return self.policy.one_event_transition

    @property
    def forward_only(self) -> bool:
        return self.policy.forward_only

    @property
    def in_memory_only(self) -> bool:
        return self.policy.in_memory_only

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def executes_transition(self) -> bool:
        return False

    @property
    def advances_cursor(self) -> bool:
        return False

    @property
    def consumes_events(self) -> bool:
        return False

    @property
    def creates_next_state(self) -> bool:
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
    def can_continue_to_subsequent_transition_application(
        self,
    ) -> bool:
        return True

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

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
    def subsequent_transition_contract_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_"
            "TRANSITION_CONTRACT:"
            f"TRANSITION_SHA256[{self.transition_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.progressed_state_decision.stable_id}:{self.subsequent_transition_contract_id}"
        )


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplaySubsequentTransitionContractDecision:
    """Immutable subsequent-transition contract decision."""

    progressed_state_decision: Phase8OfflineReplayProgressedSessionStateDecision = field(repr=False)
    status: Phase8OfflineReplaySubsequentTransitionContractStatus
    reason: Phase8OfflineReplaySubsequentTransitionContractReason
    blockers: tuple[
        Phase8OfflineReplaySubsequentTransitionContractBlocker,
        ...,
    ]
    transition_contract: StrategyPhase8OfflineReplaySubsequentTransitionContract | None = field(
        repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.progressed_state_decision,
            Phase8OfflineReplayProgressedSessionStateDecision,
        ):
            raise ValueError(
                "progressed_state_decision must be a "
                "Phase8OfflineReplayProgressedSessionStateDecision."
            )

        try:
            status = Phase8OfflineReplaySubsequentTransitionContractStatus(self.status)
            reason = Phase8OfflineReplaySubsequentTransitionContractReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Unsupported subsequent-transition contract status or reason."
            ) from error

        blockers = tuple(
            Phase8OfflineReplaySubsequentTransitionContractBlocker(blocker)
            for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Subsequent-transition blockers cannot contain duplicates.")

        if self.progressed_state_decision.is_blocked:
            if (
                status != (Phase8OfflineReplaySubsequentTransitionContractStatus.BLOCKED)
                or reason
                != (Phase8OfflineReplaySubsequentTransitionContractReason.PROGRESSED_STATE_BLOCKED)
                or blockers
                != (
                    Phase8OfflineReplaySubsequentTransitionContractBlocker.PROGRESSED_STATE_BLOCKED,
                )
                or self.transition_contract is not None
            ):
                raise ValueError(
                    "Blocked subsequent-transition result does not match its progressed state."
                )
        else:
            if (
                status != (Phase8OfflineReplaySubsequentTransitionContractStatus.CREATED)
                or reason != (Phase8OfflineReplaySubsequentTransitionContractReason.CREATED)
                or blockers
                or not isinstance(
                    self.transition_contract,
                    StrategyPhase8OfflineReplaySubsequentTransitionContract,
                )
                or (
                    self.transition_contract.progressed_state_decision
                    is not self.progressed_state_decision
                )
            ):
                raise ValueError(
                    "Created subsequent-transition result does not match its progressed state."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.progressed_state_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.progressed_state_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineReplaySubsequentTransitionContractStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_transition_contract(self) -> bool:
        return self.transition_contract is not None

    @property
    def transition_contract_required(
        self,
    ) -> StrategyPhase8OfflineReplaySubsequentTransitionContract:
        if self.transition_contract is None:
            raise ValueError(
                "No Phase 8 subsequent offline replay-transition contract was created."
            )

        return self.transition_contract

    @property
    def executes_transition(self) -> bool:
        return False

    @property
    def advances_cursor(self) -> bool:
        return False

    @property
    def consumes_events(self) -> bool:
        return False

    @property
    def creates_next_state(self) -> bool:
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
    def can_continue_to_subsequent_transition_application(
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
            f"{self.progressed_state_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_"
            "TRANSITION_CONTRACT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplaySubsequentTransitionContractFactory:
    """Pure immutable subsequent-transition factory."""

    def generate(
        self,
        progressed_state_decision: (Phase8OfflineReplayProgressedSessionStateDecision),
        policy: (Phase8OfflineReplaySubsequentTransitionContractPolicy | None) = None,
    ) -> Phase8OfflineReplaySubsequentTransitionContractDecision:
        if not isinstance(
            progressed_state_decision,
            Phase8OfflineReplayProgressedSessionStateDecision,
        ):
            raise (
                Phase8OfflineReplaySubsequentTransitionContractError(
                    Phase8OfflineReplaySubsequentTransitionContractErrorReason.INVALID_PROGRESSED_STATE_DECISION,
                    "progressed_state_decision must be a "
                    "Phase8OfflineReplayProgressedSessionStateDecision.",
                )
            )

        selected_policy = policy or Phase8OfflineReplaySubsequentTransitionContractPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplaySubsequentTransitionContractPolicy,
        ):
            raise ValueError(
                "policy must be a Phase8OfflineReplaySubsequentTransitionContractPolicy."
            )

        if progressed_state_decision.is_blocked:
            return Phase8OfflineReplaySubsequentTransitionContractDecision(
                progressed_state_decision=(progressed_state_decision),
                status=(Phase8OfflineReplaySubsequentTransitionContractStatus.BLOCKED),
                reason=(
                    Phase8OfflineReplaySubsequentTransitionContractReason.PROGRESSED_STATE_BLOCKED
                ),
                blockers=(
                    Phase8OfflineReplaySubsequentTransitionContractBlocker.PROGRESSED_STATE_BLOCKED,
                ),
                transition_contract=None,
            )

        progressed_state = progressed_state_decision.state_required
        application_receipt = progressed_state.application_receipt
        event_batch = progressed_state.event_batch
        current_event = progressed_state.next_event

        resulting_cursor_index = progressed_state.cursor_index + 1
        resulting_consumed_count = progressed_state.consumed_count + 1
        resulting_remaining_count = progressed_state.remaining_count - 1
        completion_after_transition = resulting_cursor_index == progressed_state.total_event_count
        next_event = event_batch.events[resulting_cursor_index]

        canonical_payload = _canonical_transition_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_TRANSITION_CONTRACT_SCHEMA_VERSION),
            progressed_state_id=progressed_state.stable_id,
            progressed_state_digest=progressed_state.state_digest,
            application_receipt_id=(application_receipt.stable_id),
            application_digest=(application_receipt.application_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=event_batch.batch_digest,
            broker_symbol=progressed_state.broker_symbol,
            direction=progressed_state.direction,
            side=progressed_state.side,
            source_name=progressed_state.source_name,
            captured_at=progressed_state.captured_at,
            timeframes=progressed_state.timeframes,
            contract_mode=(
                Phase8OfflineReplaySubsequentTransitionContractMode.IMMUTABLE_SINGLE_EVENT
            ),
            action=(Phase8OfflineReplaySubsequentTransitionAction.CONSUME_CURRENT_EVENT),
            transition_index=progressed_state.consumed_count,
            current_cursor_index=progressed_state.cursor_index,
            current_consumed_count=(progressed_state.consumed_count),
            current_remaining_count=(progressed_state.remaining_count),
            prior_last_consumed_sequence_index=(progressed_state.last_consumed_sequence_index),
            current_event_sequence_index=(current_event.sequence_index),
            current_event_id=current_event.stable_id,
            current_event_digest=current_event.event_digest,
            current_event_time=current_event.event_time,
            current_event_timeframe=current_event.timeframe,
            resulting_cursor_index=resulting_cursor_index,
            resulting_consumed_count=(resulting_consumed_count),
            resulting_remaining_count=(resulting_remaining_count),
            last_consumed_sequence_index=(current_event.sequence_index),
            completion_after_transition=(completion_after_transition),
            next_event_sequence_index=(next_event.sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=next_event.event_digest,
            next_event_time=next_event.event_time,
            next_event_timeframe=next_event.timeframe,
            total_event_count=(progressed_state.total_event_count),
            policy=selected_policy,
        )

        transition_contract = StrategyPhase8OfflineReplaySubsequentTransitionContract(
            progressed_state_decision=(progressed_state_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_SUBSEQUENT_TRANSITION_CONTRACT_SCHEMA_VERSION),
            progressed_state_id=(progressed_state.stable_id),
            progressed_state_digest=(progressed_state.state_digest),
            application_receipt_id=(application_receipt.stable_id),
            application_digest=(application_receipt.application_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=(event_batch.batch_digest),
            broker_symbol=(progressed_state.broker_symbol),
            direction=progressed_state.direction,
            side=progressed_state.side,
            source_name=progressed_state.source_name,
            captured_at=progressed_state.captured_at,
            timeframes=progressed_state.timeframes,
            contract_mode=(
                Phase8OfflineReplaySubsequentTransitionContractMode.IMMUTABLE_SINGLE_EVENT
            ),
            action=(Phase8OfflineReplaySubsequentTransitionAction.CONSUME_CURRENT_EVENT),
            transition_index=(progressed_state.consumed_count),
            current_cursor_index=(progressed_state.cursor_index),
            current_consumed_count=(progressed_state.consumed_count),
            current_remaining_count=(progressed_state.remaining_count),
            prior_last_consumed_sequence_index=(progressed_state.last_consumed_sequence_index),
            current_event_sequence_index=(current_event.sequence_index),
            current_event_id=current_event.stable_id,
            current_event_digest=(current_event.event_digest),
            current_event_time=(current_event.event_time),
            current_event_timeframe=(current_event.timeframe),
            resulting_cursor_index=(resulting_cursor_index),
            resulting_consumed_count=(resulting_consumed_count),
            resulting_remaining_count=(resulting_remaining_count),
            last_consumed_sequence_index=(current_event.sequence_index),
            completion_after_transition=(completion_after_transition),
            next_event_sequence_index=(next_event.sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=(next_event.event_digest),
            next_event_time=next_event.event_time,
            next_event_timeframe=(next_event.timeframe),
            total_event_count=(progressed_state.total_event_count),
            transition_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplaySubsequentTransitionContractDecision(
            progressed_state_decision=(progressed_state_decision),
            status=(Phase8OfflineReplaySubsequentTransitionContractStatus.CREATED),
            reason=(Phase8OfflineReplaySubsequentTransitionContractReason.CREATED),
            blockers=(),
            transition_contract=transition_contract,
        )

    def build(
        self,
        progressed_state_decision: (Phase8OfflineReplayProgressedSessionStateDecision),
        policy: (Phase8OfflineReplaySubsequentTransitionContractPolicy | None) = None,
    ) -> Phase8OfflineReplaySubsequentTransitionContractDecision:
        return self.generate(
            progressed_state_decision,
            policy,
        )

    def evaluate(
        self,
        progressed_state_decision: (Phase8OfflineReplayProgressedSessionStateDecision),
        policy: (Phase8OfflineReplaySubsequentTransitionContractPolicy | None) = None,
    ) -> Phase8OfflineReplaySubsequentTransitionContractDecision:
        return self.generate(
            progressed_state_decision,
            policy,
        )


def generate_phase8_offline_replay_subsequent_transition_contract(
    progressed_state_decision: (Phase8OfflineReplayProgressedSessionStateDecision),
    policy: (Phase8OfflineReplaySubsequentTransitionContractPolicy | None) = None,
) -> Phase8OfflineReplaySubsequentTransitionContractDecision:
    return StrategyPhase8OfflineReplaySubsequentTransitionContractFactory().generate(
        progressed_state_decision,
        policy,
    )


Phase8OfflineReplaySubsequentTransitionContract = (
    StrategyPhase8OfflineReplaySubsequentTransitionContract
)
Phase8OfflineReplaySubsequentTransitionContractFactory = (
    StrategyPhase8OfflineReplaySubsequentTransitionContractFactory
)
