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
from app.strategy.phase8_offline_replay_advanced_session_state import (
    StrategyPhase8OfflineReplayAdvancedSessionState,
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
    Phase8OfflineReplayNextTransitionApplicationDecision,
    StrategyPhase8OfflineReplayNextTransitionApplicationReceipt,
)
from app.strategy.phase8_offline_replay_next_transition_contract import (
    StrategyPhase8OfflineReplayNextTransitionContract,
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

PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_STATE_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineReplayProgressedSessionStateMode(
    str,
    Enum,
):
    IMMUTABLE_PROGRESSED_STATE = "IMMUTABLE_PROGRESSED_STATE"


class Phase8OfflineReplayProgressedSessionLifecycle(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"


class Phase8OfflineReplayProgressedSessionStateStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplayProgressedSessionStateReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    NEXT_TRANSITION_APPLICATION_BLOCKED = "NEXT_TRANSITION_APPLICATION_BLOCKED"


class Phase8OfflineReplayProgressedSessionStateBlocker(
    str,
    Enum,
):
    NEXT_TRANSITION_APPLICATION_BLOCKED = "NEXT_TRANSITION_APPLICATION_BLOCKED"


class Phase8OfflineReplayProgressedSessionStateErrorReason(
    str,
    Enum,
):
    INVALID_NEXT_TRANSITION_APPLICATION_DECISION = "INVALID_NEXT_TRANSITION_APPLICATION_DECISION"


class Phase8OfflineReplayProgressedSessionStateError(
    RuntimeError,
):
    """Structured progressed replay-session state failure."""

    def __init__(
        self,
        reason: (Phase8OfflineReplayProgressedSessionStateErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplayProgressedSessionStateErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 progressed offline replay-session "
            f"state error [{self.reason.value}]: "
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
class Phase8OfflineReplayProgressedSessionStatePolicy:
    """Strict reusable progressed-state requirements."""

    transition_receipt_verified: bool = True
    prior_state_immutable: bool = True
    counters_match_receipt: bool = True
    sequence_continuity_verified: bool = True
    last_consumed_event_bound: bool = True
    next_event_bound: bool = True
    forward_only: bool = True
    in_memory_only: bool = True
    no_lookahead: bool = True
    no_external_io: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "transition_receipt_verified",
            "prior_state_immutable",
            "counters_match_receipt",
            "sequence_continuity_verified",
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
                self.prior_state_immutable,
                self.counters_match_receipt,
                self.sequence_continuity_verified,
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
    next_transition_contract_id: str,
    next_transition_contract_digest: str,
    prior_advanced_state_id: str,
    prior_advanced_state_digest: str,
    prior_application_receipt_id: str,
    prior_application_digest: str,
    prior_transition_contract_id: str,
    prior_transition_contract_digest: str,
    event_batch_id: str,
    event_batch_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    timeframes: tuple[Phase8Timeframe, ...],
    state_mode: Phase8OfflineReplayProgressedSessionStateMode,
    lifecycle: Phase8OfflineReplayProgressedSessionLifecycle,
    state_version: int,
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
    policy: Phase8OfflineReplayProgressedSessionStatePolicy,
) -> str:
    return "\n".join(
        (
            f"SCHEMA_VERSION={schema_version}",
            f"APPLICATION_RECEIPT_ID={application_receipt_id}",
            f"APPLICATION_DIGEST={application_digest}",
            (f"NEXT_TRANSITION_CONTRACT_ID={next_transition_contract_id}"),
            (f"NEXT_TRANSITION_CONTRACT_DIGEST={next_transition_contract_digest}"),
            (f"PRIOR_ADVANCED_STATE_ID={prior_advanced_state_id}"),
            (f"PRIOR_ADVANCED_STATE_DIGEST={prior_advanced_state_digest}"),
            (f"PRIOR_APPLICATION_RECEIPT_ID={prior_application_receipt_id}"),
            (f"PRIOR_APPLICATION_DIGEST={prior_application_digest}"),
            (f"PRIOR_TRANSITION_CONTRACT_ID={prior_transition_contract_id}"),
            (f"PRIOR_TRANSITION_CONTRACT_DIGEST={prior_transition_contract_digest}"),
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
            f"STATE_VERSION={state_version}",
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
            (f"PRIOR_STATE_IMMUTABLE={str(policy.prior_state_immutable).lower()}"),
            (f"COUNTERS_MATCH_RECEIPT={str(policy.counters_match_receipt).lower()}"),
            (f"SEQUENCE_CONTINUITY_VERIFIED={str(policy.sequence_continuity_verified).lower()}"),
            (f"LAST_CONSUMED_EVENT_BOUND={str(policy.last_consumed_event_bound).lower()}"),
            (f"NEXT_EVENT_BOUND={str(policy.next_event_bound).lower()}"),
            (f"FORWARD_ONLY={str(policy.forward_only).lower()}"),
            (f"IN_MEMORY_ONLY={str(policy.in_memory_only).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"NO_EXTERNAL_IO={str(policy.no_external_io).lower()}"),
            "PROGRESSED_STATE_CREATED=true",
            "ADDITIONAL_TRANSITION_EXECUTED=false",
            "ADDITIONAL_EVENT_CONSUMPTION=false",
            "ADDITIONAL_CURSOR_ADVANCEMENT=false",
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
class StrategyPhase8OfflineReplayProgressedSessionState:
    """
    Immutable reusable state after two transitions.

    It preserves the Step 8.21 receipt, cursor two,
    consumed count two, last consumed event sequence one
    and next event sequence two. It performs no additional
    transition, replay, strategy evaluation or external I/O.
    """

    next_transition_application_decision: Phase8OfflineReplayNextTransitionApplicationDecision = (
        field(repr=False)
    )
    policy: Phase8OfflineReplayProgressedSessionStatePolicy
    schema_version: str
    application_receipt_id: str
    application_digest: str
    next_transition_contract_id: str
    next_transition_contract_digest: str
    prior_advanced_state_id: str
    prior_advanced_state_digest: str
    prior_application_receipt_id: str
    prior_application_digest: str
    prior_transition_contract_id: str
    prior_transition_contract_digest: str
    event_batch_id: str
    event_batch_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    source_name: str
    captured_at: datetime
    timeframes: tuple[Phase8Timeframe, ...]
    state_mode: Phase8OfflineReplayProgressedSessionStateMode
    lifecycle: Phase8OfflineReplayProgressedSessionLifecycle
    state_version: int
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
            self.next_transition_application_decision,
            Phase8OfflineReplayNextTransitionApplicationDecision,
        ):
            raise ValueError(
                "next_transition_application_decision must "
                "be a "
                "Phase8OfflineReplayNextTransitionApplicationDecision."
            )

        if not self.next_transition_application_decision.is_applied:
            raise ValueError(
                "A progressed session state requires an applied next-transition receipt."
            )

        if not isinstance(
            self.policy,
            Phase8OfflineReplayProgressedSessionStatePolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayProgressedSessionStatePolicy.")

        if not self.policy.is_strict:
            raise ValueError("Progressed session-state policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_STATE_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current progressed session-state schema."
            )

        string_fields = (
            (
                "application_receipt_id",
                self.application_receipt_id,
            ),
            ("application_digest", self.application_digest),
            (
                "next_transition_contract_id",
                self.next_transition_contract_id,
            ),
            (
                "next_transition_contract_digest",
                self.next_transition_contract_digest,
            ),
            (
                "prior_advanced_state_id",
                self.prior_advanced_state_id,
            ),
            (
                "prior_advanced_state_digest",
                self.prior_advanced_state_digest,
            ),
            (
                "prior_application_receipt_id",
                self.prior_application_receipt_id,
            ),
            (
                "prior_application_digest",
                self.prior_application_digest,
            ),
            (
                "prior_transition_contract_id",
                self.prior_transition_contract_id,
            ),
            (
                "prior_transition_contract_digest",
                self.prior_transition_contract_digest,
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
            "next_transition_contract_digest",
            "prior_advanced_state_digest",
            "prior_application_digest",
            "prior_transition_contract_digest",
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
            Phase8OfflineReplayProgressedSessionStateMode,
        ):
            raise ValueError(
                "state_mode must be a Phase8OfflineReplayProgressedSessionStateMode member."
            )

        if self.state_mode != (
            Phase8OfflineReplayProgressedSessionStateMode.IMMUTABLE_PROGRESSED_STATE
        ):
            raise ValueError("state_mode must remain IMMUTABLE_PROGRESSED_STATE.")

        if not isinstance(
            self.lifecycle,
            Phase8OfflineReplayProgressedSessionLifecycle,
        ):
            raise ValueError(
                "lifecycle must be a Phase8OfflineReplayProgressedSessionLifecycle member."
            )

        if self.lifecycle != (Phase8OfflineReplayProgressedSessionLifecycle.ACTIVE):
            raise ValueError("lifecycle must remain ACTIVE.")

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

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

        state_version = _positive_integer(
            self.state_version,
            "state_version",
        )
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
        last_consumed_sequence_index = _positive_integer(
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

        if state_version != 2:
            raise ValueError("state_version must remain two after the second replay transition.")

        if cursor_index != consumed_count:
            raise ValueError(
                "cursor_index must equal consumed_count under next-event cursor semantics."
            )

        if consumed_count + remaining_count != (total_event_count):
            raise ValueError("consumed_count plus remaining_count must equal total_event_count.")

        if last_consumed_sequence_index != (cursor_index - 1):
            raise ValueError("last_consumed_sequence_index must equal cursor_index minus one.")

        if next_event_sequence_index != cursor_index:
            raise ValueError("next_event_sequence_index must equal cursor_index.")

        if completion_reached:
            raise ValueError("The progressed state after two events cannot be complete.")

        application_receipt = self.next_transition_application_decision.receipt_required
        next_transition_contract = application_receipt.next_transition_contract
        prior_advanced_state = application_receipt.advanced_state
        prior_application_receipt = application_receipt.prior_application_receipt
        prior_transition_contract = application_receipt.prior_transition_contract
        event_batch = application_receipt.event_batch

        comparisons = (
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
                "next_transition_contract_id",
                normalized_strings["next_transition_contract_id"],
                next_transition_contract.stable_id,
            ),
            (
                "next_transition_contract_digest",
                normalized_strings["next_transition_contract_digest"],
                next_transition_contract.transition_digest,
            ),
            (
                "prior_advanced_state_id",
                normalized_strings["prior_advanced_state_id"],
                prior_advanced_state.stable_id,
            ),
            (
                "prior_advanced_state_digest",
                normalized_strings["prior_advanced_state_digest"],
                prior_advanced_state.state_digest,
            ),
            (
                "prior_application_receipt_id",
                normalized_strings["prior_application_receipt_id"],
                prior_application_receipt.stable_id,
            ),
            (
                "prior_application_digest",
                normalized_strings["prior_application_digest"],
                prior_application_receipt.application_digest,
            ),
            (
                "prior_transition_contract_id",
                normalized_strings["prior_transition_contract_id"],
                prior_transition_contract.stable_id,
            ),
            (
                "prior_transition_contract_digest",
                normalized_strings["prior_transition_contract_digest"],
                prior_transition_contract.transition_digest,
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
                application_receipt.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                application_receipt.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable next-transition application lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Progressed session states support Gold/XAUUSD only.")

        if self.direction != application_receipt.direction:
            raise ValueError("direction must match the next-transition application receipt.")

        if self.side != application_receipt.side:
            raise ValueError("side must match the next-transition application receipt.")

        if captured_at != application_receipt.captured_at:
            raise ValueError("captured_at must match the next-transition application receipt.")

        if self.timeframes != (application_receipt.timeframes):
            raise ValueError("timeframes must match the next-transition application receipt.")

        numeric_comparisons = (
            (
                "cursor_index",
                cursor_index,
                application_receipt.resulting_cursor_index,
            ),
            (
                "consumed_count",
                consumed_count,
                application_receipt.resulting_consumed_count,
            ),
            (
                "remaining_count",
                remaining_count,
                application_receipt.resulting_remaining_count,
            ),
            (
                "total_event_count",
                total_event_count,
                application_receipt.total_event_count,
            ),
            (
                "last_consumed_sequence_index",
                last_consumed_sequence_index,
                (application_receipt.last_consumed_sequence_index),
            ),
            (
                "next_event_sequence_index",
                next_event_sequence_index,
                (application_receipt.next_event_sequence_index),
            ),
        )

        for field_name, supplied, expected in numeric_comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the next-transition application receipt."
                )

        if completion_reached != (application_receipt.completion_reached):
            raise ValueError(
                "completion_reached must match the next-transition application receipt."
            )

        last_consumed_event = application_receipt.consumed_event
        next_event = application_receipt.next_event

        if normalized_strings["last_consumed_event_id"] != last_consumed_event.stable_id:
            raise ValueError("last_consumed_event_id must match the second consumed event.")

        if normalized_strings["last_consumed_event_digest"] != last_consumed_event.event_digest:
            raise ValueError("last_consumed_event_digest must match the second consumed event.")

        if last_consumed_event_time != (last_consumed_event.event_time):
            raise ValueError("last_consumed_event_time must match the second consumed event.")

        if self.last_consumed_event_timeframe != (last_consumed_event.timeframe):
            raise ValueError("last_consumed_event_timeframe must match the second consumed event.")

        if normalized_strings["next_event_id"] != (next_event.stable_id):
            raise ValueError("next_event_id must match the event at the progressed cursor.")

        if normalized_strings["next_event_digest"] != (next_event.event_digest):
            raise ValueError("next_event_digest must match the event at the progressed cursor.")

        if next_event_time != next_event.event_time:
            raise ValueError("next_event_time must match the event at the progressed cursor.")

        if self.next_event_timeframe != next_event.timeframe:
            raise ValueError("next_event_timeframe must match the event at the progressed cursor.")

        if last_consumed_event.event_time != (last_consumed_event.close_time):
            raise ValueError("The last consumed event must represent a closed candle.")

        if next_event.event_time != next_event.close_time:
            raise ValueError("The next event must represent a closed candle.")

        if prior_advanced_state.cursor_index != 1:
            raise ValueError("The immutable prior advanced cursor was altered.")

        if prior_advanced_state.consumed_count != 1:
            raise ValueError("The immutable prior advanced consumed count was altered.")

        if prior_advanced_state.remaining_count != 799:
            raise ValueError("The immutable prior advanced remaining count was altered.")

        if last_consumed_sequence_index != (prior_advanced_state.last_consumed_sequence_index + 1):
            raise ValueError("Progressed sequence continuity is invalid.")

        safe_subjects = (
            self.next_transition_application_decision,
            application_receipt,
            (application_receipt.next_transition_contract_decision),
            next_transition_contract,
            next_transition_contract.advanced_state_decision,
            prior_advanced_state,
            (prior_advanced_state.transition_application_decision),
            prior_application_receipt,
            (prior_application_receipt.transition_contract_decision),
            prior_transition_contract,
            prior_transition_contract.session_state_decision,
            application_receipt.source_state,
            (application_receipt.source_state.session_contract_decision),
            application_receipt.session_contract,
            (application_receipt.session_contract.session_plan_decision),
            application_receipt.session_plan,
            (application_receipt.session_plan.event_materialization_decision),
            event_batch,
            event_batch.materialization_plan_decision,
            application_receipt.materialization_plan,
            application_receipt.event_contract,
            application_receipt.replay_plan,
            application_receipt.specification,
            application_receipt.input_package,
            application_receipt.verification_receipt,
            application_receipt.snapshot,
            application_receipt.contract,
            application_receipt.dry_run_package,
        )

        if not all(_has_safe_external_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Progressed session-state lineage violates the external-I/O or broker boundary."
            )

        canonical_payload = _canonical_state_payload(
            schema_version=schema_version,
            application_receipt_id=normalized_strings["application_receipt_id"],
            application_digest=normalized_strings["application_digest"],
            next_transition_contract_id=(normalized_strings["next_transition_contract_id"]),
            next_transition_contract_digest=(normalized_strings["next_transition_contract_digest"]),
            prior_advanced_state_id=normalized_strings["prior_advanced_state_id"],
            prior_advanced_state_digest=normalized_strings["prior_advanced_state_digest"],
            prior_application_receipt_id=(normalized_strings["prior_application_receipt_id"]),
            prior_application_digest=normalized_strings["prior_application_digest"],
            prior_transition_contract_id=(normalized_strings["prior_transition_contract_id"]),
            prior_transition_contract_digest=(
                normalized_strings["prior_transition_contract_digest"]
            ),
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
            state_version=state_version,
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
            raise ValueError("state_digest does not match the canonical progressed session state.")

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
            "state_version",
            state_version,
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
    ) -> StrategyPhase8OfflineReplayNextTransitionApplicationReceipt:
        return self.next_transition_application_decision.receipt_required

    @property
    def next_transition_contract(
        self,
    ) -> StrategyPhase8OfflineReplayNextTransitionContract:
        return self.application_receipt.next_transition_contract

    @property
    def prior_advanced_state(
        self,
    ) -> StrategyPhase8OfflineReplayAdvancedSessionState:
        return self.application_receipt.advanced_state

    @property
    def prior_application_receipt(
        self,
    ) -> StrategyPhase8OfflineReplayTransitionApplicationReceipt:
        return self.application_receipt.prior_application_receipt

    @property
    def prior_transition_contract(
        self,
    ) -> StrategyPhase8OfflineReplayTransitionContract:
        return self.application_receipt.prior_transition_contract

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
            next_transition_contract_id=(self.next_transition_contract_id),
            next_transition_contract_digest=(self.next_transition_contract_digest),
            prior_advanced_state_id=(self.prior_advanced_state_id),
            prior_advanced_state_digest=(self.prior_advanced_state_digest),
            prior_application_receipt_id=(self.prior_application_receipt_id),
            prior_application_digest=(self.prior_application_digest),
            prior_transition_contract_id=(self.prior_transition_contract_id),
            prior_transition_contract_digest=(self.prior_transition_contract_digest),
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
            state_version=self.state_version,
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
    def is_progressed_state(self) -> bool:
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
    def prior_state_preserved(self) -> bool:
        return True

    @property
    def represents_applied_transition(self) -> bool:
        return True

    @property
    def creates_next_state(self) -> bool:
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
    def can_continue_to_future_transition_contract(
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
    def progressed_state_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_STATE:"
            f"STATE_SHA256[{self.state_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.next_transition_application_decision.stable_id}:{self.progressed_state_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayProgressedSessionStateDecision:
    """Immutable progressed-state creation decision."""

    next_transition_application_decision: Phase8OfflineReplayNextTransitionApplicationDecision = (
        field(repr=False)
    )
    status: Phase8OfflineReplayProgressedSessionStateStatus
    reason: Phase8OfflineReplayProgressedSessionStateReason
    blockers: tuple[
        Phase8OfflineReplayProgressedSessionStateBlocker,
        ...,
    ]
    state: StrategyPhase8OfflineReplayProgressedSessionState | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.next_transition_application_decision,
            Phase8OfflineReplayNextTransitionApplicationDecision,
        ):
            raise ValueError(
                "next_transition_application_decision must "
                "be a "
                "Phase8OfflineReplayNextTransitionApplicationDecision."
            )

        try:
            status = Phase8OfflineReplayProgressedSessionStateStatus(self.status)
            reason = Phase8OfflineReplayProgressedSessionStateReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported progressed session-state status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplayProgressedSessionStateBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Progressed session-state blockers cannot contain duplicates.")

        if self.next_transition_application_decision.is_blocked:
            if (
                status != (Phase8OfflineReplayProgressedSessionStateStatus.BLOCKED)
                or reason
                != (
                    Phase8OfflineReplayProgressedSessionStateReason.NEXT_TRANSITION_APPLICATION_BLOCKED
                )
                or blockers
                != (
                    Phase8OfflineReplayProgressedSessionStateBlocker.NEXT_TRANSITION_APPLICATION_BLOCKED,
                )
                or self.state is not None
            ):
                raise ValueError(
                    "Blocked progressed session-state result "
                    "does not match its application "
                    "decision."
                )
        else:
            if (
                status != (Phase8OfflineReplayProgressedSessionStateStatus.CREATED)
                or reason != (Phase8OfflineReplayProgressedSessionStateReason.CREATED)
                or blockers
                or not isinstance(
                    self.state,
                    StrategyPhase8OfflineReplayProgressedSessionState,
                )
                or (
                    self.state.next_transition_application_decision
                    is not self.next_transition_application_decision
                )
            ):
                raise ValueError(
                    "Created progressed session-state result "
                    "does not match its application "
                    "decision."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.next_transition_application_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.next_transition_application_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineReplayProgressedSessionStateStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_state(self) -> bool:
        return self.state is not None

    @property
    def state_required(
        self,
    ) -> StrategyPhase8OfflineReplayProgressedSessionState:
        if self.state is None:
            raise ValueError("No Phase 8 progressed offline replay-session state was created.")

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
    def can_continue_to_future_transition_contract(
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
            f"{self.next_transition_application_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_"
            "STATE_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplayProgressedSessionStateFactory:
    """Pure immutable progressed session-state factory."""

    def generate(
        self,
        next_transition_application_decision: (
            Phase8OfflineReplayNextTransitionApplicationDecision
        ),
        policy: (Phase8OfflineReplayProgressedSessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplayProgressedSessionStateDecision:
        if not isinstance(
            next_transition_application_decision,
            Phase8OfflineReplayNextTransitionApplicationDecision,
        ):
            raise Phase8OfflineReplayProgressedSessionStateError(
                Phase8OfflineReplayProgressedSessionStateErrorReason.INVALID_NEXT_TRANSITION_APPLICATION_DECISION,
                "next_transition_application_decision "
                "must be a "
                "Phase8OfflineReplayNextTransitionApplicationDecision.",
            )

        selected_policy = policy or Phase8OfflineReplayProgressedSessionStatePolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplayProgressedSessionStatePolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayProgressedSessionStatePolicy.")

        if next_transition_application_decision.is_blocked:
            return Phase8OfflineReplayProgressedSessionStateDecision(
                next_transition_application_decision=(next_transition_application_decision),
                status=(Phase8OfflineReplayProgressedSessionStateStatus.BLOCKED),
                reason=(
                    Phase8OfflineReplayProgressedSessionStateReason.NEXT_TRANSITION_APPLICATION_BLOCKED
                ),
                blockers=(
                    Phase8OfflineReplayProgressedSessionStateBlocker.NEXT_TRANSITION_APPLICATION_BLOCKED,
                ),
                state=None,
            )

        application_receipt = next_transition_application_decision.receipt_required
        next_transition_contract = application_receipt.next_transition_contract
        prior_advanced_state = application_receipt.advanced_state
        prior_application_receipt = application_receipt.prior_application_receipt
        prior_transition_contract = application_receipt.prior_transition_contract
        event_batch = application_receipt.event_batch
        last_consumed_event = application_receipt.consumed_event
        next_event = application_receipt.next_event

        canonical_payload = _canonical_state_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_STATE_SCHEMA_VERSION),
            application_receipt_id=(application_receipt.stable_id),
            application_digest=(application_receipt.application_digest),
            next_transition_contract_id=(next_transition_contract.stable_id),
            next_transition_contract_digest=(next_transition_contract.transition_digest),
            prior_advanced_state_id=(prior_advanced_state.stable_id),
            prior_advanced_state_digest=(prior_advanced_state.state_digest),
            prior_application_receipt_id=(prior_application_receipt.stable_id),
            prior_application_digest=(prior_application_receipt.application_digest),
            prior_transition_contract_id=(prior_transition_contract.stable_id),
            prior_transition_contract_digest=(prior_transition_contract.transition_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=event_batch.batch_digest,
            broker_symbol=application_receipt.broker_symbol,
            direction=application_receipt.direction,
            side=application_receipt.side,
            source_name=application_receipt.source_name,
            captured_at=application_receipt.captured_at,
            timeframes=application_receipt.timeframes,
            state_mode=(Phase8OfflineReplayProgressedSessionStateMode.IMMUTABLE_PROGRESSED_STATE),
            lifecycle=(Phase8OfflineReplayProgressedSessionLifecycle.ACTIVE),
            state_version=2,
            cursor_index=(application_receipt.resulting_cursor_index),
            consumed_count=(application_receipt.resulting_consumed_count),
            remaining_count=(application_receipt.resulting_remaining_count),
            total_event_count=(application_receipt.total_event_count),
            last_consumed_sequence_index=(application_receipt.last_consumed_sequence_index),
            last_consumed_event_id=(last_consumed_event.stable_id),
            last_consumed_event_digest=(last_consumed_event.event_digest),
            last_consumed_event_time=(last_consumed_event.event_time),
            last_consumed_event_timeframe=(last_consumed_event.timeframe),
            next_event_sequence_index=(application_receipt.next_event_sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=next_event.event_digest,
            next_event_time=next_event.event_time,
            next_event_timeframe=next_event.timeframe,
            completion_reached=(application_receipt.completion_reached),
            policy=selected_policy,
        )

        state = StrategyPhase8OfflineReplayProgressedSessionState(
            next_transition_application_decision=(next_transition_application_decision),
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_PROGRESSED_SESSION_STATE_SCHEMA_VERSION),
            application_receipt_id=(application_receipt.stable_id),
            application_digest=(application_receipt.application_digest),
            next_transition_contract_id=(next_transition_contract.stable_id),
            next_transition_contract_digest=(next_transition_contract.transition_digest),
            prior_advanced_state_id=(prior_advanced_state.stable_id),
            prior_advanced_state_digest=(prior_advanced_state.state_digest),
            prior_application_receipt_id=(prior_application_receipt.stable_id),
            prior_application_digest=(prior_application_receipt.application_digest),
            prior_transition_contract_id=(prior_transition_contract.stable_id),
            prior_transition_contract_digest=(prior_transition_contract.transition_digest),
            event_batch_id=event_batch.stable_id,
            event_batch_digest=event_batch.batch_digest,
            broker_symbol=application_receipt.broker_symbol,
            direction=application_receipt.direction,
            side=application_receipt.side,
            source_name=application_receipt.source_name,
            captured_at=application_receipt.captured_at,
            timeframes=application_receipt.timeframes,
            state_mode=(Phase8OfflineReplayProgressedSessionStateMode.IMMUTABLE_PROGRESSED_STATE),
            lifecycle=(Phase8OfflineReplayProgressedSessionLifecycle.ACTIVE),
            state_version=2,
            cursor_index=(application_receipt.resulting_cursor_index),
            consumed_count=(application_receipt.resulting_consumed_count),
            remaining_count=(application_receipt.resulting_remaining_count),
            total_event_count=(application_receipt.total_event_count),
            last_consumed_sequence_index=(application_receipt.last_consumed_sequence_index),
            last_consumed_event_id=(last_consumed_event.stable_id),
            last_consumed_event_digest=(last_consumed_event.event_digest),
            last_consumed_event_time=(last_consumed_event.event_time),
            last_consumed_event_timeframe=(last_consumed_event.timeframe),
            next_event_sequence_index=(application_receipt.next_event_sequence_index),
            next_event_id=next_event.stable_id,
            next_event_digest=next_event.event_digest,
            next_event_time=next_event.event_time,
            next_event_timeframe=next_event.timeframe,
            completion_reached=(application_receipt.completion_reached),
            state_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplayProgressedSessionStateDecision(
            next_transition_application_decision=(next_transition_application_decision),
            status=(Phase8OfflineReplayProgressedSessionStateStatus.CREATED),
            reason=(Phase8OfflineReplayProgressedSessionStateReason.CREATED),
            blockers=(),
            state=state,
        )

    def build(
        self,
        next_transition_application_decision: (
            Phase8OfflineReplayNextTransitionApplicationDecision
        ),
        policy: (Phase8OfflineReplayProgressedSessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplayProgressedSessionStateDecision:
        return self.generate(
            next_transition_application_decision,
            policy,
        )

    def evaluate(
        self,
        next_transition_application_decision: (
            Phase8OfflineReplayNextTransitionApplicationDecision
        ),
        policy: (Phase8OfflineReplayProgressedSessionStatePolicy | None) = None,
    ) -> Phase8OfflineReplayProgressedSessionStateDecision:
        return self.generate(
            next_transition_application_decision,
            policy,
        )


def generate_phase8_offline_replay_progressed_session_state(
    next_transition_application_decision: (Phase8OfflineReplayNextTransitionApplicationDecision),
    policy: (Phase8OfflineReplayProgressedSessionStatePolicy | None) = None,
) -> Phase8OfflineReplayProgressedSessionStateDecision:
    return StrategyPhase8OfflineReplayProgressedSessionStateFactory().generate(
        next_transition_application_decision,
        policy,
    )


Phase8OfflineReplayProgressedSessionState = StrategyPhase8OfflineReplayProgressedSessionState
Phase8OfflineReplayProgressedSessionStateFactory = (
    StrategyPhase8OfflineReplayProgressedSessionStateFactory
)
