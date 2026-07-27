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
from app.strategy.phase8_offline_replay_plan import (
    Phase8OfflineReplayClock,
    Phase8OfflineReplayMergeMode,
    Phase8OfflineReplayPlanDecision,
    Phase8OfflineReplayTieBreak,
    StrategyPhase8OfflineReplayPlan,
)
from app.strategy.phase8_offline_simulation_run_specification import (
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_EVENT_CONTRACT_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


_REQUIRED_PRIORITIES = (
    (Phase8Timeframe.H4, 0),
    (Phase8Timeframe.H1, 1),
    (Phase8Timeframe.M15, 2),
    (Phase8Timeframe.M5, 3),
)


class Phase8OfflineReplayEventKind(str, Enum):
    CANDLE_CLOSED = "CANDLE_CLOSED"


class Phase8OfflineReplayEventTimestampSource(str, Enum):
    CANDLE_CLOSE_TIME = "CANDLE_CLOSE_TIME"


class Phase8OfflineReplayEventField(str, Enum):
    SEQUENCE_INDEX = "sequence_index"
    TIMEFRAME = "timeframe"
    TIMEFRAME_PRIORITY = "timeframe_priority"
    SERIES_INDEX = "series_index"
    CANDLE_INDEX = "candle_index"
    EVENT_TIME = "event_time"
    OPEN_TIME = "open_time"
    CLOSE_TIME = "close_time"
    OPEN_PRICE = "open_price"
    HIGH_PRICE = "high_price"
    LOW_PRICE = "low_price"
    CLOSE_PRICE = "close_price"
    CANDLE_DIGEST = "candle_digest"
    SERIES_DIGEST = "series_digest"


_REQUIRED_EVENT_FIELDS = (
    Phase8OfflineReplayEventField.SEQUENCE_INDEX,
    Phase8OfflineReplayEventField.TIMEFRAME,
    Phase8OfflineReplayEventField.TIMEFRAME_PRIORITY,
    Phase8OfflineReplayEventField.SERIES_INDEX,
    Phase8OfflineReplayEventField.CANDLE_INDEX,
    Phase8OfflineReplayEventField.EVENT_TIME,
    Phase8OfflineReplayEventField.OPEN_TIME,
    Phase8OfflineReplayEventField.CLOSE_TIME,
    Phase8OfflineReplayEventField.OPEN_PRICE,
    Phase8OfflineReplayEventField.HIGH_PRICE,
    Phase8OfflineReplayEventField.LOW_PRICE,
    Phase8OfflineReplayEventField.CLOSE_PRICE,
    Phase8OfflineReplayEventField.CANDLE_DIGEST,
    Phase8OfflineReplayEventField.SERIES_DIGEST,
)


class Phase8OfflineReplayEventContractStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplayEventContractReason(str, Enum):
    CREATED = "CREATED"
    REPLAY_PLAN_BLOCKED = "REPLAY_PLAN_BLOCKED"


class Phase8OfflineReplayEventContractBlocker(str, Enum):
    REPLAY_PLAN_BLOCKED = "REPLAY_PLAN_BLOCKED"


class Phase8OfflineReplayEventContractErrorReason(str, Enum):
    INVALID_REPLAY_PLAN_DECISION = "INVALID_REPLAY_PLAN_DECISION"


class Phase8OfflineReplayEventContractError(RuntimeError):
    """Structured replay-event contract failure."""

    def __init__(
        self,
        reason: Phase8OfflineReplayEventContractErrorReason,
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplayEventContractErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Phase 8 offline replay-event contract error [{self.reason.value}]: {self.message}"
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
        "creates_events",
        "materializes_events",
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
class Phase8OfflineReplayEventContractPolicy:
    """Strict event-schema and replay-order requirements."""

    strict_sequence: bool = True
    zero_based_sequence: bool = True
    event_time_from_candle_close: bool = True
    include_full_ohlc: bool = True
    preserve_candle_digest: bool = True
    preserve_series_digest: bool = True
    no_lookahead: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "strict_sequence",
            "zero_based_sequence",
            "event_time_from_candle_close",
            "include_full_ohlc",
            "preserve_candle_digest",
            "preserve_series_digest",
            "no_lookahead",
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
                self.strict_sequence,
                self.zero_based_sequence,
                self.event_time_from_candle_close,
                self.include_full_ohlc,
                self.preserve_candle_digest,
                self.preserve_series_digest,
                self.no_lookahead,
            )
        )


def _canonical_contract_payload(
    *,
    schema_version: str,
    plan_id: str,
    plan_digest: str,
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
    event_kind: Phase8OfflineReplayEventKind,
    timestamp_source: Phase8OfflineReplayEventTimestampSource,
    replay_clock: Phase8OfflineReplayClock,
    merge_mode: Phase8OfflineReplayMergeMode,
    tie_break: Phase8OfflineReplayTieBreak,
    timeframes: tuple[Phase8Timeframe, ...],
    timeframe_priorities: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ],
    series_counts: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ],
    event_fields: tuple[
        Phase8OfflineReplayEventField,
        ...,
    ],
    total_event_count: int,
    policy: Phase8OfflineReplayEventContractPolicy,
) -> str:
    lines = [
        f"SCHEMA_VERSION={schema_version}",
        f"PLAN_ID={plan_id}",
        f"PLAN_DIGEST={plan_digest}",
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
        f"EVENT_KIND={event_kind.value}",
        f"TIMESTAMP_SOURCE={timestamp_source.value}",
        f"REPLAY_CLOCK={replay_clock.value}",
        f"MERGE_MODE={merge_mode.value}",
        f"TIE_BREAK={tie_break.value}",
        ("TIMEFRAMES=" + ",".join(timeframe.value for timeframe in timeframes)),
        f"SERIES_COUNT={len(series_counts)}",
        f"EVENT_FIELD_COUNT={len(event_fields)}",
        f"TOTAL_EVENT_COUNT={total_event_count}",
    ]

    for index, (
        priority_item,
        count_item,
    ) in enumerate(
        zip(
            timeframe_priorities,
            series_counts,
            strict=True,
        ),
        start=1,
    ):
        priority_timeframe, priority = priority_item
        count_timeframe, count = count_item

        lines.extend(
            (
                (f"SERIES_{index}_TIMEFRAME={priority_timeframe.value}"),
                (f"SERIES_{index}_COUNT_TIMEFRAME={count_timeframe.value}"),
                f"SERIES_{index}_PRIORITY={priority}",
                f"SERIES_{index}_CANDLE_COUNT={count}",
            )
        )

    for index, event_field in enumerate(
        event_fields,
        start=1,
    ):
        lines.append(f"EVENT_FIELD_{index}={event_field.value}")

    lines.extend(
        (
            (f"STRICT_SEQUENCE={str(policy.strict_sequence).lower()}"),
            (f"ZERO_BASED_SEQUENCE={str(policy.zero_based_sequence).lower()}"),
            (f"EVENT_TIME_FROM_CANDLE_CLOSE={str(policy.event_time_from_candle_close).lower()}"),
            (f"INCLUDE_FULL_OHLC={str(policy.include_full_ohlc).lower()}"),
            (f"PRESERVE_CANDLE_DIGEST={str(policy.preserve_candle_digest).lower()}"),
            (f"PRESERVE_SERIES_DIGEST={str(policy.preserve_series_digest).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            "EVENT_CREATION=false",
            "EVENT_MATERIALIZATION=false",
            "REPLAY_EXECUTION=false",
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

    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class StrategyPhase8OfflineReplayEventContract:
    """
    Immutable schema for future offline candle-close events.

    This contract does not materialize events, iterate
    candles, execute replay, evaluate strategy logic, fetch
    data, initialize MT5, write storage, contact a broker,
    or submit an order.
    """

    plan_decision: Phase8OfflineReplayPlanDecision = field(repr=False)
    policy: Phase8OfflineReplayEventContractPolicy
    schema_version: str
    plan_id: str
    plan_digest: str
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
    event_kind: Phase8OfflineReplayEventKind
    timestamp_source: Phase8OfflineReplayEventTimestampSource
    replay_clock: Phase8OfflineReplayClock
    merge_mode: Phase8OfflineReplayMergeMode
    tie_break: Phase8OfflineReplayTieBreak
    timeframes: tuple[Phase8Timeframe, ...]
    timeframe_priorities: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ]
    series_counts: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ]
    event_fields: tuple[
        Phase8OfflineReplayEventField,
        ...,
    ]
    total_event_count: int
    contract_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.plan_decision,
            Phase8OfflineReplayPlanDecision,
        ):
            raise ValueError("plan_decision must be a Phase8OfflineReplayPlanDecision.")

        if not self.plan_decision.is_created:
            raise ValueError("A replay-event contract requires a created offline replay plan.")

        if not isinstance(
            self.policy,
            Phase8OfflineReplayEventContractPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayEventContractPolicy.")

        if not self.policy.is_strict:
            raise ValueError("Replay-event contract policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PHASE_8_OFFLINE_REPLAY_EVENT_CONTRACT_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current replay-event contract schema.")

        string_fields = (
            ("plan_id", self.plan_id),
            ("plan_digest", self.plan_digest),
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
            "plan_digest",
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

        if not isinstance(
            self.event_kind,
            Phase8OfflineReplayEventKind,
        ):
            raise ValueError("event_kind must be a Phase8OfflineReplayEventKind member.")

        if self.event_kind != Phase8OfflineReplayEventKind.CANDLE_CLOSED:
            raise ValueError("event_kind must remain CANDLE_CLOSED.")

        if not isinstance(
            self.timestamp_source,
            Phase8OfflineReplayEventTimestampSource,
        ):
            raise ValueError(
                "timestamp_source must be a Phase8OfflineReplayEventTimestampSource member."
            )

        if self.timestamp_source != (Phase8OfflineReplayEventTimestampSource.CANDLE_CLOSE_TIME):
            raise ValueError("timestamp_source must remain CANDLE_CLOSE_TIME.")

        if not isinstance(
            self.replay_clock,
            Phase8OfflineReplayClock,
        ):
            raise ValueError("replay_clock must be a Phase8OfflineReplayClock member.")

        if self.replay_clock != Phase8OfflineReplayClock.CANDLE_CLOSE:
            raise ValueError("replay_clock must remain CANDLE_CLOSE.")

        if not isinstance(
            self.merge_mode,
            Phase8OfflineReplayMergeMode,
        ):
            raise ValueError("merge_mode must be a Phase8OfflineReplayMergeMode member.")

        if self.merge_mode != (Phase8OfflineReplayMergeMode.CHRONOLOGICAL_STABLE):
            raise ValueError("merge_mode must remain CHRONOLOGICAL_STABLE.")

        if not isinstance(
            self.tie_break,
            Phase8OfflineReplayTieBreak,
        ):
            raise ValueError("tie_break must be a Phase8OfflineReplayTieBreak member.")

        if self.tie_break != (Phase8OfflineReplayTieBreak.TIMEFRAME_PRIORITY):
            raise ValueError("tie_break must remain TIMEFRAME_PRIORITY.")

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

        if not isinstance(
            self.timeframe_priorities,
            tuple,
        ):
            raise ValueError("timeframe_priorities must be a tuple.")

        if self.timeframe_priorities != _REQUIRED_PRIORITIES:
            raise ValueError(
                "timeframe_priorities must preserve exact H4, H1, M15, and M5 priorities."
            )

        for timeframe, priority in self.timeframe_priorities:
            if not isinstance(timeframe, Phase8Timeframe):
                raise ValueError("Every priority timeframe must be a Phase8Timeframe member.")

            _non_negative_integer(
                priority,
                "timeframe priority",
            )

        if not isinstance(self.series_counts, tuple):
            raise ValueError("series_counts must be a tuple.")

        if len(self.series_counts) != 4:
            raise ValueError("series_counts must contain four entries.")

        if tuple(timeframe for timeframe, _ in self.series_counts) != _REQUIRED_TIMEFRAMES:
            raise ValueError("series_counts must preserve exact timeframe order.")

        for timeframe, count in self.series_counts:
            if not isinstance(timeframe, Phase8Timeframe):
                raise ValueError("Every count timeframe must be a Phase8Timeframe member.")

            _positive_integer(
                count,
                "series candle count",
            )

        if not isinstance(self.event_fields, tuple):
            raise ValueError("event_fields must be a tuple.")

        if not all(
            isinstance(
                event_field,
                Phase8OfflineReplayEventField,
            )
            for event_field in self.event_fields
        ):
            raise ValueError("event_fields must contain Phase8OfflineReplayEventField members.")

        if len(set(self.event_fields)) != len(self.event_fields):
            raise ValueError("event_fields cannot contain duplicates.")

        if self.event_fields != _REQUIRED_EVENT_FIELDS:
            raise ValueError("event_fields must preserve the exact replay-event schema and order.")

        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )

        if total_event_count != sum(count for _, count in self.series_counts):
            raise ValueError("total_event_count must equal the sum of series_counts.")

        plan = self.plan_decision.plan_required
        specification = plan.specification
        input_package = plan.input_package
        snapshot = plan.snapshot

        comparisons = (
            (
                "plan_id",
                normalized_strings["plan_id"],
                plan.stable_id,
            ),
            (
                "plan_digest",
                normalized_strings["plan_digest"],
                plan.plan_digest,
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
                plan.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                plan.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(
                    f"{field_name} must match the immutable offline replay-plan lineage."
                )

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Replay-event contracts support Gold/XAUUSD only.")

        if self.direction != plan.direction:
            raise ValueError("direction must match the offline replay plan.")

        if self.side != plan.side:
            raise ValueError("side must match the offline replay plan.")

        if captured_at != plan.captured_at:
            raise ValueError("captured_at must match the offline replay plan.")

        if self.timeframes != plan.timeframes:
            raise ValueError("timeframes must match the offline replay plan.")

        expected_priorities = tuple(
            (
                item.timeframe,
                item.priority,
            )
            for item in plan.series_plans
        )

        if self.timeframe_priorities != expected_priorities:
            raise ValueError("timeframe_priorities must match the offline replay plan.")

        expected_counts = tuple(
            (
                item.timeframe,
                item.candle_count,
            )
            for item in plan.series_plans
        )

        if self.series_counts != expected_counts:
            raise ValueError("series_counts must match the offline replay plan.")

        if total_event_count != plan.total_event_count:
            raise ValueError("total_event_count must match the offline replay plan.")

        if self.replay_clock != plan.replay_clock:
            raise ValueError("replay_clock must match the offline replay plan.")

        if self.merge_mode != plan.merge_mode:
            raise ValueError("merge_mode must match the offline replay plan.")

        if self.tie_break != plan.tie_break:
            raise ValueError("tie_break must match the offline replay plan.")

        if not plan.no_lookahead:
            raise ValueError("Offline replay plan must remain no-lookahead.")

        safe_subjects = (
            self.plan_decision,
            plan,
            plan.specification_decision,
            specification,
            specification.input_decision,
            input_package,
            plan.verification_receipt,
            snapshot,
            plan.contract,
            plan.dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError("Replay-event lineage violates the non-I/O or non-execution boundary.")

        canonical_payload = _canonical_contract_payload(
            schema_version=schema_version,
            plan_id=normalized_strings["plan_id"],
            plan_digest=normalized_strings["plan_digest"],
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
            event_kind=self.event_kind,
            timestamp_source=self.timestamp_source,
            replay_clock=self.replay_clock,
            merge_mode=self.merge_mode,
            tie_break=self.tie_break,
            timeframes=self.timeframes,
            timeframe_priorities=(self.timeframe_priorities),
            series_counts=self.series_counts,
            event_fields=self.event_fields,
            total_event_count=total_event_count,
            policy=self.policy,
        )

        if normalized_strings["contract_digest"] != _sha256_digest(canonical_payload):
            raise ValueError("contract_digest does not match the canonical replay-event contract.")

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
            "total_event_count",
            total_event_count,
        )

    @property
    def plan(self) -> StrategyPhase8OfflineReplayPlan:
        return self.plan_decision.plan_required

    @property
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.plan.specification

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.plan.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.plan.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.plan.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.plan.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.plan.dry_run_package

    @property
    def canonical_payload(self) -> str:
        return _canonical_contract_payload(
            schema_version=self.schema_version,
            plan_id=self.plan_id,
            plan_digest=self.plan_digest,
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
            event_kind=self.event_kind,
            timestamp_source=self.timestamp_source,
            replay_clock=self.replay_clock,
            merge_mode=self.merge_mode,
            tie_break=self.tie_break,
            timeframes=self.timeframes,
            timeframe_priorities=(self.timeframe_priorities),
            series_counts=self.series_counts,
            event_fields=self.event_fields,
            total_event_count=self.total_event_count,
            policy=self.policy,
        )

    @property
    def series_count(self) -> int:
        return len(self.series_counts)

    @property
    def event_field_count(self) -> int:
        return len(self.event_fields)

    @property
    def planned_event_count(self) -> int:
        return self.total_event_count

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def candle_close_events_only(self) -> bool:
        return True

    @property
    def zero_based_sequence(self) -> bool:
        return self.policy.zero_based_sequence

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def creates_events(self) -> bool:
        return False

    @property
    def materializes_events(self) -> bool:
        return False

    @property
    def executes_replay(self) -> bool:
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
    def can_continue_to_event_materialization_plan(
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
    def event_contract_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_EVENT_CONTRACT:"
            f"CONTRACT_SHA256[{self.contract_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.plan_decision.stable_id}:{self.event_contract_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayEventContractDecision:
    """Immutable replay-event contract decision."""

    plan_decision: Phase8OfflineReplayPlanDecision = field(repr=False)
    status: Phase8OfflineReplayEventContractStatus
    reason: Phase8OfflineReplayEventContractReason
    blockers: tuple[
        Phase8OfflineReplayEventContractBlocker,
        ...,
    ]
    event_contract: StrategyPhase8OfflineReplayEventContract | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.plan_decision,
            Phase8OfflineReplayPlanDecision,
        ):
            raise ValueError("plan_decision must be a Phase8OfflineReplayPlanDecision.")

        try:
            status = Phase8OfflineReplayEventContractStatus(self.status)
            reason = Phase8OfflineReplayEventContractReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported replay-event contract status or reason.") from error

        blockers = tuple(
            Phase8OfflineReplayEventContractBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Replay-event contract blockers cannot contain duplicates.")

        if self.plan_decision.is_blocked:
            if (
                status != (Phase8OfflineReplayEventContractStatus.BLOCKED)
                or reason != (Phase8OfflineReplayEventContractReason.REPLAY_PLAN_BLOCKED)
                or blockers != (Phase8OfflineReplayEventContractBlocker.REPLAY_PLAN_BLOCKED,)
                or self.event_contract is not None
            ):
                raise ValueError(
                    "Blocked replay-event contract result does not match its replay plan."
                )
        else:
            if (
                status != (Phase8OfflineReplayEventContractStatus.CREATED)
                or reason != (Phase8OfflineReplayEventContractReason.CREATED)
                or blockers
                or not isinstance(
                    self.event_contract,
                    StrategyPhase8OfflineReplayEventContract,
                )
                or self.event_contract.plan_decision is not self.plan_decision
            ):
                raise ValueError(
                    "Created replay-event contract result does not match its replay plan."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.plan_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.plan_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == Phase8OfflineReplayEventContractStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_event_contract(self) -> bool:
        return self.event_contract is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def event_contract_required(
        self,
    ) -> StrategyPhase8OfflineReplayEventContract:
        if self.event_contract is None:
            raise ValueError("No Phase 8 offline replay-event contract was created.")

        return self.event_contract

    @property
    def can_continue_to_event_materialization_plan(
        self,
    ) -> bool:
        return self.is_created

    @property
    def creates_events(self) -> bool:
        return False

    @property
    def materializes_events(self) -> bool:
        return False

    @property
    def executes_replay(self) -> bool:
        return False

    @property
    def executes_simulation(self) -> bool:
        return False

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
            f"{self.plan_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_EVENT_CONTRACT_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplayEventContractFactory:
    """Pure immutable replay-event contract factory."""

    def generate(
        self,
        plan_decision: Phase8OfflineReplayPlanDecision,
        policy: (Phase8OfflineReplayEventContractPolicy | None) = None,
    ) -> Phase8OfflineReplayEventContractDecision:
        if not isinstance(
            plan_decision,
            Phase8OfflineReplayPlanDecision,
        ):
            raise Phase8OfflineReplayEventContractError(
                Phase8OfflineReplayEventContractErrorReason.INVALID_REPLAY_PLAN_DECISION,
                "plan_decision must be a Phase8OfflineReplayPlanDecision.",
            )

        selected_policy = policy or Phase8OfflineReplayEventContractPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplayEventContractPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayEventContractPolicy.")

        if plan_decision.is_blocked:
            return Phase8OfflineReplayEventContractDecision(
                plan_decision=plan_decision,
                status=(Phase8OfflineReplayEventContractStatus.BLOCKED),
                reason=(Phase8OfflineReplayEventContractReason.REPLAY_PLAN_BLOCKED),
                blockers=(Phase8OfflineReplayEventContractBlocker.REPLAY_PLAN_BLOCKED,),
                event_contract=None,
            )

        plan = plan_decision.plan_required
        specification = plan.specification
        input_package = plan.input_package
        snapshot = plan.snapshot

        timeframe_priorities = tuple(
            (
                item.timeframe,
                item.priority,
            )
            for item in plan.series_plans
        )
        series_counts = tuple(
            (
                item.timeframe,
                item.candle_count,
            )
            for item in plan.series_plans
        )

        canonical_payload = _canonical_contract_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_EVENT_CONTRACT_SCHEMA_VERSION),
            plan_id=plan.stable_id,
            plan_digest=plan.plan_digest,
            specification_id=specification.stable_id,
            specification_digest=(specification.specification_digest),
            input_package_id=input_package.stable_id,
            input_digest=input_package.input_digest,
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            broker_symbol=plan.broker_symbol,
            direction=plan.direction,
            side=plan.side,
            source_name=plan.source_name,
            captured_at=plan.captured_at,
            event_kind=(Phase8OfflineReplayEventKind.CANDLE_CLOSED),
            timestamp_source=(Phase8OfflineReplayEventTimestampSource.CANDLE_CLOSE_TIME),
            replay_clock=plan.replay_clock,
            merge_mode=plan.merge_mode,
            tie_break=plan.tie_break,
            timeframes=plan.timeframes,
            timeframe_priorities=timeframe_priorities,
            series_counts=series_counts,
            event_fields=_REQUIRED_EVENT_FIELDS,
            total_event_count=plan.total_event_count,
            policy=selected_policy,
        )

        event_contract = StrategyPhase8OfflineReplayEventContract(
            plan_decision=plan_decision,
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_EVENT_CONTRACT_SCHEMA_VERSION),
            plan_id=plan.stable_id,
            plan_digest=plan.plan_digest,
            specification_id=specification.stable_id,
            specification_digest=(specification.specification_digest),
            input_package_id=input_package.stable_id,
            input_digest=input_package.input_digest,
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            broker_symbol=plan.broker_symbol,
            direction=plan.direction,
            side=plan.side,
            source_name=plan.source_name,
            captured_at=plan.captured_at,
            event_kind=(Phase8OfflineReplayEventKind.CANDLE_CLOSED),
            timestamp_source=(Phase8OfflineReplayEventTimestampSource.CANDLE_CLOSE_TIME),
            replay_clock=plan.replay_clock,
            merge_mode=plan.merge_mode,
            tie_break=plan.tie_break,
            timeframes=plan.timeframes,
            timeframe_priorities=(timeframe_priorities),
            series_counts=series_counts,
            event_fields=_REQUIRED_EVENT_FIELDS,
            total_event_count=plan.total_event_count,
            contract_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplayEventContractDecision(
            plan_decision=plan_decision,
            status=(Phase8OfflineReplayEventContractStatus.CREATED),
            reason=(Phase8OfflineReplayEventContractReason.CREATED),
            blockers=(),
            event_contract=event_contract,
        )

    def build(
        self,
        plan_decision: Phase8OfflineReplayPlanDecision,
        policy: (Phase8OfflineReplayEventContractPolicy | None) = None,
    ) -> Phase8OfflineReplayEventContractDecision:
        return self.generate(
            plan_decision,
            policy,
        )

    def evaluate(
        self,
        plan_decision: Phase8OfflineReplayPlanDecision,
        policy: (Phase8OfflineReplayEventContractPolicy | None) = None,
    ) -> Phase8OfflineReplayEventContractDecision:
        return self.generate(
            plan_decision,
            policy,
        )


def generate_phase8_offline_replay_event_contract(
    plan_decision: Phase8OfflineReplayPlanDecision,
    policy: (Phase8OfflineReplayEventContractPolicy | None) = None,
) -> Phase8OfflineReplayEventContractDecision:
    return StrategyPhase8OfflineReplayEventContractFactory().generate(
        plan_decision,
        policy,
    )


Phase8OfflineReplayEventContract = StrategyPhase8OfflineReplayEventContract
Phase8OfflineReplayEventContractFactory = StrategyPhase8OfflineReplayEventContractFactory
