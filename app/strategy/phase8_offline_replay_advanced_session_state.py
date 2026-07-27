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
    StrategyPhase8OfflineReplaySessionState,
)
from app.strategy.phase8_offline_replay_transition_application import (
    Phase8OfflineReplayTransitionApplicationDecision,
    StrategyPhase8OfflineReplayTransitionApplicationReceipt,
)
from app.strategy.phase8_offline_replay_transition_contract import (
    StrategyPhase8OfflineReplayTransitionContract,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_STATE_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplayAdvancedSessionStateMode(
    str,
    Enum,
):
    IMMUTABLE_ADVANCED_STATE = "IMMUTABLE_ADVANCED_STATE"


class Phase8OfflineReplayAdvancedSessionLifecycle(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"


class Phase8OfflineReplayAdvancedSessionStateStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplayAdvancedSessionStateReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    TRANSITION_APPLICATION_BLOCKED = "TRANSITION_APPLICATION_BLOCKED"


class Phase8OfflineReplayAdvancedSessionStateBlocker(
    str,
    Enum,
):
    TRANSITION_APPLICATION_BLOCKED = "TRANSITION_APPLICATION_BLOCKED"


class Phase8OfflineReplayAdvancedSessionStateErrorReason(
    str,
    Enum,
):
    INVALID_TRANSITION_APPLICATION_DECISION = "INVALID_TRANSITION_APPLICATION_DECISION"


class Phase8OfflineReplayAdvancedSessionStateError(
    RuntimeError,
):
    """Structured advanced replay-session state failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplayAdvancedSessionStateErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplayAdvancedSessionStateErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 advanced offline replay-session state "
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

    for optional_false_attribute in (
        "fetches_data",
        "executes_simulation",
        "executes_replay",
        "evaluates_strategy",
        "emits_orders",
        "starts_session",
        "starts_replay",
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
class Phase8OfflineReplayAdvancedSessionStatePolicy:
    """Strict reusable advanced-state requirements."""

    transition_receipt_verified: bool = True
    source_state_immutable: bool = True
    counters_match_receipt: bool = True
    last_consumed_event_bound: bool = True
    next_event_bound: bool = True
    forward_only: bool = True
    in_memory_only: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "transition_receipt_verified",
            "source_state_immutable",
            "counters_match_receipt",
            "last_consumed_event_bound",
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
                self.transition_receipt_verified,
                self.source_state_immutable,
                self.counters_match_receipt,
                self.last_consumed_event_bound,
                self.next_event_bound,
                self.forward_only,
                self.in_memory_only,
                self.no_lookahead,
                self.no_external_io,
            )
        )


def _canonical_state_payload(
    *,
    schema_version: str,
    application_receipt_id: str,
    application_digest: str,
    transition_contract_id: str,
    transition_contract_digest: str,
    source_state_id: str,
    source_state_digest: str,
    session_contract_id: str,
    session_contract_digest: str,
    session_plan_id: str,
    session_plan_digest: str,
    event_batch_id: str,
    event_batch_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    timeframes: tuple[Phase8Timeframe, ...],
    state_mode: (Phase8OfflineReplayAdvancedSessionStateMode),
    lifecycle: Phase8OfflineReplayAdvancedSessionLifecycle,
    cursor_index: int,
    consumed_count: int,
    remaining_count: int,
    total_event_count: int,
    last_consumed_sequence_index: int,
    last_consumed_event_id: str,
    last_consumed_event_digest: str,
    last_consumed_event_time: datetime,
    last_consumed_event_timeframe: Phase8Timeframe,
    next_event_sequence_index: int,
    next_event_id: str,
    next_event_digest: str,
    next_event_time: datetime,
    next_event_timeframe: Phase8Timeframe,
    completion_reached: bool,
    policy: Phase8OfflineReplayAdvancedSessionStatePolicy,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"APPLICATION_RECEIPT_ID={application_receipt_id}",
            f"APPLICATION_DIGEST={application_digest}",
            f"TRANSITION_CONTRACT_ID={transition_contract_id}",
            (f"TRANSITION_CONTRACT_DIGEST={transition_contract_digest}"),
            f"SOURCE_STATE_ID={source_state_id}",
            f"SOURCE_STATE_DIGEST={source_state_digest}",
            f"SESSION_CONTRACT_ID={session_contract_id}",
            (f"SESSION_CONTRACT_DIGEST={session_contract_digest}"),
            f"SESSION_PLAN_ID={session_plan_id}",
            f"SESSION_PLAN_DIGEST={session_plan_digest}",
            f"EVENT_BATCH_ID={event_batch_id}",
            f"EVENT_BATCH_DIGEST={event_batch_digest}",
            f"BROKER_SYMBOL={broker_symbol}",
            f"DIRECTION={direction.value}",
            f"SIDE={side.value}",
            f"SOURCE_NAME={source_name}",
            (f"CAPTURED_AT={_canonical_datetime(captured_at)}"),
            ("TIMEFRAMES=" + ",".join(timeframe.value for timeframe in timeframes)),
            f"STATE_MODE={state_mode.value}",
            f"LIFECYCLE={lifecycle.value}",
            f"CURSOR_INDEX={cursor_index}",
            f"CONSUMED_COUNT={consumed_count}",
            f"REMAINING_COUNT={remaining_count}",
            f"TOTAL_EVENT_COUNT={total_event_count}",
            (f"LAST_CONSUMED_SEQUENCE_INDEX={last_consumed_sequence_index}"),
            (f"LAST_CONSUMED_EVENT_ID={last_consumed_event_id}"),
            (f"LAST_CONSUMED_EVENT_DIGEST={last_consumed_event_digest}"),
            (f"LAST_CONSUMED_EVENT_TIME={_canonical_datetime(last_consumed_event_time)}"),
            (f"LAST_CONSUMED_EVENT_TIMEFRAME={last_consumed_event_timeframe.value}"),
            (f"NEXT_EVENT_SEQUENCE_INDEX={next_event_sequence_index}"),
            f"NEXT_EVENT_ID={next_event_id}",
            f"NEXT_EVENT_DIGEST={next_event_digest}",
            (f"NEXT_EVENT_TIME={_canonical_datetime(next_event_time)}"),
            (f"NEXT_EVENT_TIMEFRAME={next_event_timeframe.value}"),
            (f"COMPLETION_REACHED={str(completion_reached).lower()}"),
            (f"TRANSITION_RECEIPT_VERIFIED={str(policy.transition_receipt_verified).lower()}"),
            (f"SOURCE_STATE_IMMUTABLE={str(policy.source_state_immutable).lower()}"),
            (f"COUNTERS_MATCH_RECEIPT={str(policy.counters_match_receipt).lower()}"),
            (f"LAST_CONSUMED_EVENT_BOUND={str(policy.last_consumed_event_bound).lower()}"),
            (f"NEXT_EVENT_BOUND={str(policy.next_event_bound).lower()}"),
            (f"FORWARD_ONLY={str(policy.forward_only).lower()}"),
            (f"IN_MEMORY_ONLY={str(policy.in_memory_only).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "ADVANCED_STATE_CREATED=true",
            "ADDITIONAL_TRANSITION_EXECUTED=false",
            "ADDITIONAL_EVENT_CONSUMPTION=false",
            "ADDITIONAL_CURSOR_ADVANCEMENT=false",
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
class StrategyPhase8OfflineReplayAdvancedSessionState:
    """
    Immutable reusable state after the first transition.

    It preserves the transition receipt, resulting counters,
    last consumed event and next event. It performs no
    additional transition, event consumption, replay,
    strategy evaluation or external I/O.
    """

    transition_application_decision: Phase8OfflineReplayTransitionApplicationDecision = field(
        repr=False
    )
    policy: Phase8OfflineReplayAdvancedSessionStatePolicy
    schema_version: str
    application_receipt_id: str
    application_digest: str
    transition_contract_id: str
    transition_contract_digest: str
    source_state_id: str
    source_state_digest: str
    session_contract_id: str
    session_contract_digest: str
    session_plan_id: str
    session_plan_digest: str
    event_batch_id: str
    event_batch_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    source_name: str
    captured_at: datetime
    timeframes: tuple[Phase8Timeframe, ...]
    state_mode: Phase8OfflineReplayAdvancedSessionStateMode
    lifecycle: Phase8OfflineReplayAdvancedSessionLifecycle
    cursor_index: int
    consumed_count: int
    remaining_count: int
    total_event_count: int
    last_consumed_sequence_index: int
    last_consumed_event_id: str
    last_consumed_event_digest: str
    last_consumed_event_time: datetime
    last_consumed_event_timeframe: Phase8Timeframe
    next_event_sequence_index: int
    next_event_id: str
    next_event_digest: str
    next_event_time: datetime
    next_event_timeframe: Phase8Timeframe
    completion_reached: bool
    state_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.transition_application_decision,
            Phase8OfflineReplayTransitionApplicationDecision,
        ):
            raise ValueError(
                "transition_application_decision must be a "
                "Phase8OfflineReplayTransitionApplicationDecision."
            )

        if not self.transition_application_decision.is_applied:
            raise ValueError("An advanced session state requires an applied transition receipt.")

        if not isinstance(
            self.policy,
            Phase8OfflineReplayAdvancedSessionStatePolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayAdvancedSessionStatePolicy.")

        if not self.policy.is_strict:
            raise ValueError("Advanced session-state policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_STATE_SCHEMA_VERSION):
            raise ValueError("schema_version must match the current advanced session-state schema.")

        string_fields = (
            (
                "application_receipt_id",
                self.application_receipt_id,
            ),
            ("application_digest", self.application_digest),
            (
                "transition_contract_id",
                self.transition_contract_id,
            ),
            (
                "transition_contract_digest",
                self.transition_contract_digest,
            ),
            ("source_state_id", self.source_state_id),
            (
                "source_state_digest",
                self.source_state_digest,
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
            ("broker_symbol", self.broker_symbol),
            ("source_name", self.source_name),
            (
                "last_consumed_event_id",
                self.last_consumed_event_id,
            ),
            (
                "last_consumed_event_digest",
                self.last_consumed_event_digest,
            ),
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
            "application_digest",
            "transition_contract_digest",
            "source_state_digest",
            "session_contract_digest",
            "session_plan_digest",
            "event_batch_digest",
            "last_consumed_event_digest",
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

        if not isinstance(
            self.state_mode,
            Phase8OfflineReplayAdvancedSessionStateMode,
        ):
            raise ValueError(
                "state_mode must be a Phase8OfflineReplayAdvancedSessionStateMode member."
            )

        if self.state_mode != (
            Phase8OfflineReplayAdvancedSessionStateMode.IMMUTABLE_ADVANCED_STATE
        ):
            raise ValueError("state_mode must remain IMMUTABLE_ADVANCED_STATE.")

        if not isinstance(
            self.lifecycle,
            Phase8OfflineReplayAdvancedSessionLifecycle,
        ):
            raise ValueError(
                "lifecycle must be a Phase8OfflineReplayAdvancedSessionLifecycle member."
            )

        if self.lifecycle != (Phase8OfflineReplayAdvancedSessionLifecycle.ACTIVE):
            raise ValueError("lifecycle must remain ACTIVE.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        if not all(isinstance(timeframe, Phase8Timeframe) for timeframe in self.timeframes):
            raise ValueError("timeframes must contain Phase8Timeframe members.")

        if not isinstance(
            self.last_consumed_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("last_consumed_event_timeframe must be a Phase8Timeframe member.")

        if not isinstance(
            self.next_event_timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("next_event_timeframe must be a Phase8Timeframe member.")

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )
        last_consumed_event_time = _aware_datetime(
            self.last_consumed_event_time,
            "last_consumed_event_time",
        )
        next_event_time = _aware_datetime(
            self.next_event_time,
            "next_event_time",
        )

        if last_consumed_event_time > captured_at:
            raise ValueError("last_consumed_event_time cannot exceed captured_at.")

        if next_event_time > captured_at:
            raise ValueError("next_event_time cannot exceed captured_at.")

        if next_event_time < last_consumed_event_time:
            raise ValueError("next_event_time cannot precede the last consumed event.")

        cursor_index = _positive_integer(
            self.cursor_index,
            "cursor_index",
        )
        consumed_count = _positive_integer(
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
        last_consumed_sequence_index = _non_negative_integer(
            self.last_consumed_sequence_index,
            "last_consumed_sequence_index",
        )
        next_event_sequence_index = _positive_integer(
            self.next_event_sequence_index,
            "next_event_sequence_index",
        )
        completion_reached = _strict_boolean(
            self.completion_reached,
            "completion_reached",
        )

        if cursor_index != consumed_count:
            raise ValueError(
                "cursor_index must equal consumed_count under next-event cursor semantics."
            )

        if consumed_count + remaining_count != (total_event_count):
            raise ValueError("consumed_count plus remaining_count must equal total_event_count.")

        if last_consumed_sequence_index != cursor_index - 1:
            raise ValueError("last_consumed_sequence_index must equal cursor_index minus one.")

        if next_event_sequence_index != cursor_index:
            raise ValueError("next_event_sequence_index must equal cursor_index.")

        if completion_reached:
            raise ValueError("The first advanced state cannot be complete.")

        receipt = self.transition_application_decision.receipt_required
        transition_contract = receipt.transition_contract
        source_state = receipt.source_state
        session_contract = receipt.session_contract
        session_plan = receipt.session_plan
        event_batch = receipt.event_batch

        comparisons = (
            (
                "application_receipt_id",
                normalized_strings["application_receipt_id"],
                receipt.stable_id,
            ),
            (
                "application_digest",
                normalized_strings["application_digest"],
                receipt.application_digest,
            ),
            (
                "transition_contract_id",
                normalized_strings["transition_contract_id"],
                transition_contract.stable_id,
            ),
            (
                "transition_contract_digest",
                normalized_strings["transition_contract_digest"],
                transition_contract.transition_digest,
            ),
            (
                "source_state_id",
                normalized_strings["source_state_id"],
                source_state.stable_id,
            ),
            (
                "source_state_digest",
                normalized_strings["source_state_digest"],
                source_state.state_digest,
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
                "broker_symbol",
                normalized_strings["broker_symbol"],
                receipt.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                receipt.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable transition-application lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Advanced session states support Gold/XAUUSD only.")

        if self.direction != receipt.direction:
            raise ValueError("direction must match the transition application receipt.")

        if self.side != receipt.side:
            raise ValueError("side must match the transition application receipt.")

        if captured_at != receipt.captured_at:
            raise ValueError("captured_at must match the transition application receipt.")

        if self.timeframes != receipt.timeframes:
            raise ValueError("timeframes must match the transition application receipt.")

        numeric_comparisons = (
            (
                "cursor_index",
                cursor_index,
                receipt.resulting_cursor_index,
            ),
            (
                "consumed_count",
                consumed_count,
                receipt.resulting_consumed_count,
            ),
            (
                "remaining_count",
                remaining_count,
                receipt.resulting_remaining_count,
            ),
            (
                "total_event_count",
                total_event_count,
                receipt.total_event_count,
            ),
            (
                "last_consumed_sequence_index",
                last_consumed_sequence_index,
                receipt.last_consumed_sequence_index,
            ),
            (
                "next_event_sequence_index",
                next_event_sequence_index,
                receipt.next_event_sequence_index,
            ),
        )

        for field_name, supplied, expected in numeric_comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the transition application receipt.")

        if completion_reached != receipt.completion_reached:
            raise ValueError("completion_reached must match the transition application receipt.")

        last_consumed_event = receipt.consumed_event
        next_event = receipt.next_event

        if normalized_strings["last_consumed_event_id"] != last_consumed_event.stable_id:
            raise ValueError("last_consumed_event_id must match the consumed event.")

        if normalized_strings["last_consumed_event_digest"] != last_consumed_event.event_digest:
            raise ValueError("last_consumed_event_digest must match the consumed event.")

        if last_consumed_event_time != last_consumed_event.event_time:
            raise ValueError("last_consumed_event_time must match the consumed event.")

        if self.last_consumed_event_timeframe != last_consumed_event.timeframe:
            raise ValueError("last_consumed_event_timeframe must match the consumed event.")

        if normalized_strings["next_event_id"] != (next_event.stable_id):
            raise ValueError("next_event_id must match the event at the advanced cursor.")

        if normalized_strings["next_event_digest"] != (next_event.event_digest):
            raise ValueError("next_event_digest must match the event at the advanced cursor.")

        if next_event_time != next_event.event_time:
            raise ValueError("next_event_time must match the event at the advanced cursor.")

        if self.next_event_timeframe != next_event.timeframe:
            raise ValueError("next_event_timeframe must match the event at the advanced cursor.")

        if last_consumed_event.event_time != (last_consumed_event.close_time):
            raise ValueError("The last consumed event must represent a closed candle.")

        if next_event.event_time != next_event.close_time:
            raise ValueError("The next event must represent a closed candle.")

        if source_state.cursor_index != 0:
            raise ValueError("The immutable source state was altered.")

        if source_state.consumed_count != 0:
            raise ValueError("The immutable source consumed count was altered.")

        if source_state.remaining_count != total_event_count:
            raise ValueError("The immutable source remaining count was altered.")

        safe_subjects = (
            self.transition_application_decision,
            receipt,
            receipt.transition_contract_decision,
            transition_contract,
            transition_contract.session_state_decision,
            source_state,
            source_state.session_contract_decision,
            session_contract,
            session_contract.session_plan_decision,
            session_plan,
            session_plan.event_materialization_decision,
            event_batch,
            event_batch.materialization_plan_decision,
            receipt.materialization_plan,
            receipt.event_contract,
            receipt.replay_plan,
            receipt.specification,
            receipt.input_package,
            receipt.verification_receipt,
            receipt.snapshot,
            receipt.contract,
            receipt.dry_run_package,
        )

        if not all(_has_safe_external_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Advanced session-state lineage violates the external-I/O or broker boundary."
            )

        canonical_payload = _canonical_state_payload(
            schema_version=schema_version,
            application_receipt_id=normalized_strings["application_receipt_id"],
            application_digest=normalized_strings["application_digest"],
            transition_contract_id=normalized_strings["transition_contract_id"],
            transition_contract_digest=normalized_strings["transition_contract_digest"],
            source_state_id=normalized_strings["source_state_id"],
            source_state_digest=normalized_strings["source_state_digest"],
            session_contract_id=normalized_strings["session_contract_id"],
            session_contract_digest=normalized_strings["session_contract_digest"],
            session_plan_id=normalized_strings["session_plan_id"],
            session_plan_digest=normalized_strings["session_plan_digest"],
            event_batch_id=normalized_strings["event_batch_id"],
            event_batch_digest=normalized_strings["event_batch_digest"],
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=normalized_strings["source_name"],
            captured_at=captured_at,
            timeframes=self.timeframes,
            state_mode=self.state_mode,
            lifecycle=self.lifecycle,
            cursor_index=cursor_index,
            consumed_count=consumed_count,
            remaining_count=remaining_count,
            total_event_count=total_event_count,
            last_consumed_sequence_index=(last_consumed_sequence_index),
            last_consumed_event_id=normalized_strings["last_consumed_event_id"],
            last_consumed_event_digest=normalized_strings["last_consumed_event_digest"],
            last_consumed_event_time=(last_consumed_event_time),
            last_consumed_event_timeframe=(self.last_consumed_event_timeframe),
            next_event_sequence_index=(next_event_sequence_index),
            next_event_id=normalized_strings["next_event_id"],
            next_event_digest=normalized_strings["next_event_digest"],
            next_event_time=next_event_time,
            next_event_timeframe=self.next_event_timeframe,
            completion_reached=completion_reached,
            policy=self.policy,
        )

        if normalized_strings["state_digest"] != (_sha256_digest(canonical_payload)):
            raise ValueError("state_digest does not match the canonical advanced session state.")

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
            "last_consumed_event_time",
            last_consumed_event_time,
        )
        object.__setattr__(
            self,
            "next_event_time",
            next_event_time,
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
            "last_consumed_sequence_index",
            last_consumed_sequence_index,
        )
        object.__setattr__(
            self,
            "next_event_sequence_index",
            next_event_sequence_index,
        )
        object.__setattr__(
            self,
            "completion_reached",
            completion_reached,
        )

    @property
    def application_receipt(
        self,
    ) -> StrategyPhase8OfflineReplayTransitionApplicationReceipt:
        return self.transition_application_decision.receipt_required

    @property
    def transition_contract(
        self,
    ) -> StrategyPhase8OfflineReplayTransitionContract:
        return self.application_receipt.transition_contract

    @property
    def source_state(
        self,
    ) -> StrategyPhase8OfflineReplaySessionState:
        return self.application_receipt.source_state

    @property
    def session_contract(
        self,
    ) -> StrategyPhase8OfflineReplaySessionContract:
        return self.application_receipt.session_contract

    @property
    def session_plan(
        self,
    ) -> StrategyPhase8OfflineReplaySessionPlan:
        return self.application_receipt.session_plan

    @property
    def event_batch(
        self,
    ) -> StrategyPhase8OfflineReplayEventBatch:
        return self.application_receipt.event_batch

    @property
    def materialization_plan(
        self,
    ) -> StrategyPhase8OfflineReplayEventMaterializationPlan:
        return self.application_receipt.materialization_plan

    @property
    def event_contract(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        return self.application_receipt.event_contract

    @property
    def replay_plan(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        return self.application_receipt.replay_plan

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.application_receipt.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.application_receipt.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.application_receipt.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.application_receipt.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.application_receipt.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.application_receipt.dry_run_package

    @property
    def last_consumed_event(
        self,
    ) -> Phase8OfflineReplayEvent:
        return self.application_receipt.consumed_event

    @property
    def next_event(self) -> Phase8OfflineReplayEvent:
        return self.application_receipt.next_event

    @property
    def canonical_payload(self) -> str:
        return _canonical_state_payload(
            schema_version=self.schema_version,
            application_receipt_id=(self.application_receipt_id),
            application_digest=self.application_digest,
            transition_contract_id=(self.transition_contract_id),
            transition_contract_digest=(self.transition_contract_digest),
            source_state_id=self.source_state_id,
            source_state_digest=self.source_state_digest,
            session_contract_id=self.session_contract_id,
            session_contract_digest=(self.session_contract_digest),
            session_plan_id=self.session_plan_id,
            session_plan_digest=self.session_plan_digest,
            event_batch_id=self.event_batch_id,
            event_batch_digest=self.event_batch_digest,
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=self.source_name,
            captured_at=self.captured_at,
            timeframes=self.timeframes,
            state_mode=self.state_mode,
            lifecycle=self.lifecycle,
            cursor_index=self.cursor_index,
            consumed_count=self.consumed_count,
            remaining_count=self.remaining_count,
            total_event_count=self.total_event_count,
            last_consumed_sequence_index=(self.last_consumed_sequence_index),
            last_consumed_event_id=(self.last_consumed_event_id),
            last_consumed_event_digest=(self.last_consumed_event_digest),
            last_consumed_event_time=(self.last_consumed_event_time),
            last_consumed_event_timeframe=(self.last_consumed_event_timeframe),
            next_event_sequence_index=(self.next_event_sequence_index),
            next_event_id=self.next_event_id,
            next_event_digest=self.next_event_digest,
            next_event_time=self.next_event_time,
            next_event_timeframe=self.next_event_timeframe,
            completion_reached=self.completion_reached,
            policy=self.policy,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def is_advanced_state(self) -> bool:
        return True

    @property
    def session_initialized(self) -> bool:
        return True

    @property
    def session_active(self) -> bool:
        return True

    @property
    def has_next_event(self) -> bool:
        return not self.completion_reached

    @property
    def source_state_preserved(self) -> bool:
        return True

    @property
    def represents_applied_transition(self) -> bool:
        return True

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
        return True

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
    def in_memory_only(self) -> bool:
        return self.policy.in_memory_only

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def can_continue_to_next_transition_contract(
        self,
    ) -> bool:
        return self.has_next_event

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
    def advanced_state_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_STATE:"
            f"STATE_SHA256[{self.state_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.transition_application_decision.stable_id}:{self.advanced_state_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayAdvancedSessionStateDecision:
    """Immutable advanced-state creation decision."""

    transition_application_decision: Phase8OfflineReplayTransitionApplicationDecision = field(
        repr=False
    )
    status: Phase8OfflineReplayAdvancedSessionStateStatus
    reason: Phase8OfflineReplayAdvancedSessionStateReason
    blockers: tuple[
        Phase8OfflineReplayAdvancedSessionStateBlocker,
        ...,
    ]
    state: StrategyPhase8OfflineReplayAdvancedSessionState | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.transition_application_decision,
            Phase8OfflineReplayTransitionApplicationDecision,
        ):
            raise ValueError(
                "transition_application_decision must be a "
                "Phase8OfflineReplayTransitionApplicationDecision."
            )

        try:
            status = Phase8OfflineReplayAdvancedSessionStateStatus(self.status)
            reason = Phase8OfflineReplayAdvancedSessionStateReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported advanced session-state status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplayAdvancedSessionStateBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Advanced session-state blockers cannot contain duplicates.")

        if self.transition_application_decision.is_blocked:
            if (
                status != (Phase8OfflineReplayAdvancedSessionStateStatus.BLOCKED)
                or reason
                != (Phase8OfflineReplayAdvancedSessionStateReason.TRANSITION_APPLICATION_BLOCKED)
                or blockers
                != (Phase8OfflineReplayAdvancedSessionStateBlocker.TRANSITION_APPLICATION_BLOCKED,)
                or self.state is not None
            ):
                raise ValueError(
                    "Blocked advanced session-state result "
                    "does not match its transition "
                    "application decision."
                )
        else:
            if (
                status != (Phase8OfflineReplayAdvancedSessionStateStatus.CREATED)
                or reason != (Phase8OfflineReplayAdvancedSessionStateReason.CREATED)
                or blockers
                or not isinstance(
                    self.state,
                    StrategyPhase8OfflineReplayAdvancedSessionState,
                )
                or self.state.transition_application_decision
                is not self.transition_application_decision
            ):
                raise ValueError(
                    "Created advanced session-state result "
                    "does not match its transition "
                    "application decision."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.transition_application_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.transition_application_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineReplayAdvancedSessionStateStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_state(self) -> bool:
        return self.state is not None

    @property
    def state_required(
        self,
    ) -> StrategyPhase8OfflineReplayAdvancedSessionState:
        if self.state is None:
            raise ValueError("No Phase 8 advanced offline replay-session state was created.")

        return self.state

    @property
    def creates_next_state(self) -> bool:
        return self.is_created

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
    def can_continue_to_next_transition_contract(
        self,
    ) -> bool:
        return self.is_created and self.state_required.has_next_event

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
            f"{self.transition_application_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_"
            "STATE_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplayAdvancedSessionStateFactory:
    """Pure immutable advanced session-state factory."""

    def generate(
        self,
        transition_application_decision: (Phase8OfflineReplayTransitionApplicationDecision),
        policy: (Phase8OfflineReplayAdvancedSessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplayAdvancedSessionStateDecision:
        if not isinstance(
            transition_application_decision,
            Phase8OfflineReplayTransitionApplicationDecision,
        ):
            raise (
                Phase8OfflineReplayAdvancedSessionStateError(
                    Phase8OfflineReplayAdvancedSessionStateErrorReason.INVALID_TRANSITION_APPLICATION_DECISION,
                    "transition_application_decision must be "
                    "a Phase8OfflineReplayTransitionApplicationDecision.",
                )
            )

        selected_policy = policy or Phase8OfflineReplayAdvancedSessionStatePolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplayAdvancedSessionStatePolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayAdvancedSessionStatePolicy.")

        if transition_application_decision.is_blocked:
            return Phase8OfflineReplayAdvancedSessionStateDecision(
                transition_application_decision=(transition_application_decision),
                status=(Phase8OfflineReplayAdvancedSessionStateStatus.BLOCKED),
                reason=(
                    Phase8OfflineReplayAdvancedSessionStateReason.TRANSITION_APPLICATION_BLOCKED
                ),
                blockers=(
                    Phase8OfflineReplayAdvancedSessionStateBlocker.TRANSITION_APPLICATION_BLOCKED,
                ),
                state=None,
            )

        receipt = transition_application_decision.receipt_required
        transition_contract = receipt.transition_contract
        source_state = receipt.source_state
        session_contract = receipt.session_contract
        session_plan = receipt.session_plan
        event_batch = receipt.event_batch
        last_consumed_event = receipt.consumed_event
        next_event = receipt.next_event

        canonical_payload = _canonical_state_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_STATE_SCHEMA_VERSION),
            application_receipt_id=receipt.stable_id,
            application_digest=receipt.application_digest,
            transition_contract_id=(transition_contract.stable_id),
            transition_contract_digest=(transition_contract.transition_digest),
            source_state_id=source_state.stable_id,
            source_state_digest=source_state.state_digest,
            session_contract_id=session_contract.stable_id,
            session_contract_digest=(session_contract.contract_digest),
            session_plan_id=session_plan.stable_id,
            session_plan_digest=session_plan.session_digest,
            event_batch_id=event_batch.stable_id,
            event_batch_digest=event_batch.batch_digest,
            broker_symbol=receipt.broker_symbol,
            direction=receipt.direction,
            side=receipt.side,
            source_name=receipt.source_name,
            captured_at=receipt.captured_at,
            timeframes=receipt.timeframes,
            state_mode=(Phase8OfflineReplayAdvancedSessionStateMode.IMMUTABLE_ADVANCED_STATE),
            lifecycle=(Phase8OfflineReplayAdvancedSessionLifecycle.ACTIVE),
            cursor_index=receipt.resulting_cursor_index,
            consumed_count=(receipt.resulting_consumed_count),
            remaining_count=(receipt.resulting_remaining_count),
            total_event_count=receipt.total_event_count,
            last_consumed_sequence_index=(receipt.last_consumed_sequence_index),
            last_consumed_event_id=(last_consumed_event.stable_id),
            last_consumed_event_digest=(last_consumed_event.event_digest),
            last_consumed_event_time=(last_consumed_event.event_time),
            last_consumed_event_timeframe=(last_consumed_event.timeframe),
            next_event_sequence_index=(receipt.next_event_sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=next_event.event_digest,
            next_event_time=next_event.event_time,
            next_event_timeframe=next_event.timeframe,
            completion_reached=receipt.completion_reached,
            policy=selected_policy,
        )

        state = StrategyPhase8OfflineReplayAdvancedSessionState(
            transition_application_decision=(transition_application_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_ADVANCED_SESSION_STATE_SCHEMA_VERSION),
            application_receipt_id=receipt.stable_id,
            application_digest=(receipt.application_digest),
            transition_contract_id=(transition_contract.stable_id),
            transition_contract_digest=(transition_contract.transition_digest),
            source_state_id=source_state.stable_id,
            source_state_digest=(source_state.state_digest),
            session_contract_id=(session_contract.stable_id),
            session_contract_digest=(session_contract.contract_digest),
            session_plan_id=session_plan.stable_id,
            session_plan_digest=(session_plan.session_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=(event_batch.batch_digest),
            broker_symbol=receipt.broker_symbol,
            direction=receipt.direction,
            side=receipt.side,
            source_name=receipt.source_name,
            captured_at=receipt.captured_at,
            timeframes=receipt.timeframes,
            state_mode=(Phase8OfflineReplayAdvancedSessionStateMode.IMMUTABLE_ADVANCED_STATE),
            lifecycle=(Phase8OfflineReplayAdvancedSessionLifecycle.ACTIVE),
            cursor_index=(receipt.resulting_cursor_index),
            consumed_count=(receipt.resulting_consumed_count),
            remaining_count=(receipt.resulting_remaining_count),
            total_event_count=(receipt.total_event_count),
            last_consumed_sequence_index=(receipt.last_consumed_sequence_index),
            last_consumed_event_id=(last_consumed_event.stable_id),
            last_consumed_event_digest=(last_consumed_event.event_digest),
            last_consumed_event_time=(last_consumed_event.event_time),
            last_consumed_event_timeframe=(last_consumed_event.timeframe),
            next_event_sequence_index=(receipt.next_event_sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=(next_event.event_digest),
            next_event_time=next_event.event_time,
            next_event_timeframe=(next_event.timeframe),
            completion_reached=(receipt.completion_reached),
            state_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplayAdvancedSessionStateDecision(
            transition_application_decision=(transition_application_decision),
            status=(Phase8OfflineReplayAdvancedSessionStateStatus.CREATED),
            reason=(Phase8OfflineReplayAdvancedSessionStateReason.CREATED),
            blockers=(),
            state=state,
        )

    def build(
        self,
        transition_application_decision: (Phase8OfflineReplayTransitionApplicationDecision),
        policy: (Phase8OfflineReplayAdvancedSessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplayAdvancedSessionStateDecision:
        return self.generate(
            transition_application_decision,
            policy,
        )

    def evaluate(
        self,
        transition_application_decision: (Phase8OfflineReplayTransitionApplicationDecision),
        policy: (Phase8OfflineReplayAdvancedSessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplayAdvancedSessionStateDecision:
        return self.generate(
            transition_application_decision,
            policy,
        )


def generate_phase8_offline_replay_advanced_session_state(
    transition_application_decision: (Phase8OfflineReplayTransitionApplicationDecision),
    policy: (Phase8OfflineReplayAdvancedSessionStatePolicy | None) = None,
) -> Phase8OfflineReplayAdvancedSessionStateDecision:
    return StrategyPhase8OfflineReplayAdvancedSessionStateFactory().generate(
        transition_application_decision,
        policy,
    )


Phase8OfflineReplayAdvancedSessionState = StrategyPhase8OfflineReplayAdvancedSessionState
Phase8OfflineReplayAdvancedSessionStateFactory = (
    StrategyPhase8OfflineReplayAdvancedSessionStateFactory
)
