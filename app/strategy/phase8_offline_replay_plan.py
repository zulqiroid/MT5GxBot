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
from app.strategy.phase8_offline_simulation_run_specification import (
    Phase8OfflineSimulationRunSpecificationDecision,
    StrategyPhase8OfflineSimulationRunSpecification,
)
from app.strategy.phase8_simulation_input_package import (
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_REPLAY_PLAN_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


_EXPECTED_PRIORITIES = {
    Phase8Timeframe.H4: 0,
    Phase8Timeframe.H1: 1,
    Phase8Timeframe.M15: 2,
    Phase8Timeframe.M5: 3,
}


class Phase8OfflineReplayClock(str, Enum):
    CANDLE_CLOSE = "CANDLE_CLOSE"


class Phase8OfflineReplayMergeMode(str, Enum):
    CHRONOLOGICAL_STABLE = "CHRONOLOGICAL_STABLE"


class Phase8OfflineReplayTieBreak(str, Enum):
    TIMEFRAME_PRIORITY = "TIMEFRAME_PRIORITY"


class Phase8OfflineReplayPlanStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineReplayPlanReason(str, Enum):
    CREATED = "CREATED"
    RUN_SPECIFICATION_BLOCKED = "RUN_SPECIFICATION_BLOCKED"


class Phase8OfflineReplayPlanBlocker(str, Enum):
    RUN_SPECIFICATION_BLOCKED = "RUN_SPECIFICATION_BLOCKED"


class Phase8OfflineReplayPlanErrorReason(str, Enum):
    INVALID_RUN_SPECIFICATION_DECISION = "INVALID_RUN_SPECIFICATION_DECISION"


class Phase8OfflineReplayPlanError(RuntimeError):
    """Structured offline replay-plan failure."""

    def __init__(
        self,
        reason: Phase8OfflineReplayPlanErrorReason,
        message: str,
    ) -> None:
        self.reason = Phase8OfflineReplayPlanErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Phase 8 offline replay-plan error [{self.reason.value}]: {self.message}")


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
class Phase8OfflineReplayPlanPolicy:
    """Strict deterministic offline replay-plan rules."""

    emit_on_candle_close: bool = True
    preserve_series_order: bool = True
    deterministic_tie_break: bool = True
    no_lookahead: bool = True
    include_warmup_candles: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "emit_on_candle_close",
            "preserve_series_order",
            "deterministic_tie_break",
            "no_lookahead",
            "include_warmup_candles",
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
                self.emit_on_candle_close,
                self.preserve_series_order,
                self.deterministic_tie_break,
                self.no_lookahead,
                self.include_warmup_candles,
            )
        )


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplaySeriesPlan:
    """Immutable replay bounds for one timeframe."""

    timeframe: Phase8Timeframe
    priority: int
    candle_count: int
    start_index: int
    end_index: int
    first_open_time: datetime
    first_close_time: datetime
    latest_open_time: datetime
    latest_close_time: datetime
    series_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.timeframe,
            Phase8Timeframe,
        ):
            raise ValueError("timeframe must be a Phase8Timeframe member.")

        priority = _non_negative_integer(
            self.priority,
            "priority",
        )
        candle_count = _positive_integer(
            self.candle_count,
            "candle_count",
        )
        start_index = _non_negative_integer(
            self.start_index,
            "start_index",
        )
        end_index = _non_negative_integer(
            self.end_index,
            "end_index",
        )

        if start_index != 0:
            raise ValueError("start_index must be zero.")

        if end_index != candle_count - 1:
            raise ValueError("end_index must equal candle_count minus one.")

        first_open_time = _aware_datetime(
            self.first_open_time,
            "first_open_time",
        )
        first_close_time = _aware_datetime(
            self.first_close_time,
            "first_close_time",
        )
        latest_open_time = _aware_datetime(
            self.latest_open_time,
            "latest_open_time",
        )
        latest_close_time = _aware_datetime(
            self.latest_close_time,
            "latest_close_time",
        )

        if first_close_time <= first_open_time:
            raise ValueError("first_close_time must be later than first_open_time.")

        if latest_close_time <= latest_open_time:
            raise ValueError("latest_close_time must be later than latest_open_time.")

        if latest_open_time < first_open_time:
            raise ValueError("latest_open_time cannot precede first_open_time.")

        if latest_close_time < first_close_time:
            raise ValueError("latest_close_time cannot precede first_close_time.")

        series_digest = _non_empty_string(
            self.series_digest,
            "series_digest",
        )

        if not _is_lowercase_sha256(series_digest):
            raise ValueError("series_digest must be a lowercase SHA-256 hexadecimal value.")

        object.__setattr__(self, "priority", priority)
        object.__setattr__(
            self,
            "candle_count",
            candle_count,
        )
        object.__setattr__(
            self,
            "start_index",
            start_index,
        )
        object.__setattr__(
            self,
            "end_index",
            end_index,
        )
        object.__setattr__(
            self,
            "first_open_time",
            first_open_time,
        )
        object.__setattr__(
            self,
            "first_close_time",
            first_close_time,
        )
        object.__setattr__(
            self,
            "latest_open_time",
            latest_open_time,
        )
        object.__setattr__(
            self,
            "latest_close_time",
            latest_close_time,
        )
        object.__setattr__(
            self,
            "series_digest",
            series_digest,
        )

    @property
    def canonical_row(self) -> str:
        return "|".join(
            (
                self.timeframe.value,
                str(self.priority),
                str(self.candle_count),
                str(self.start_index),
                str(self.end_index),
                _canonical_datetime(self.first_open_time),
                _canonical_datetime(self.first_close_time),
                _canonical_datetime(self.latest_open_time),
                _canonical_datetime(self.latest_close_time),
                self.series_digest,
            )
        )

    @property
    def planned_event_count(self) -> int:
        return self.candle_count

    @property
    def is_complete_series(self) -> bool:
        return self.start_index == 0 and self.end_index == self.candle_count - 1


def _canonical_plan_payload(
    *,
    schema_version: str,
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
    replay_clock: Phase8OfflineReplayClock,
    merge_mode: Phase8OfflineReplayMergeMode,
    tie_break: Phase8OfflineReplayTieBreak,
    policy: Phase8OfflineReplayPlanPolicy,
    series_plans: tuple[
        Phase8OfflineReplaySeriesPlan,
        ...,
    ],
    total_event_count: int,
) -> str:
    lines = [
        f"SCHEMA_VERSION={schema_version}",
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
        f"REPLAY_CLOCK={replay_clock.value}",
        f"MERGE_MODE={merge_mode.value}",
        f"TIE_BREAK={tie_break.value}",
        f"SERIES_COUNT={len(series_plans)}",
        f"TOTAL_EVENT_COUNT={total_event_count}",
    ]

    for index, series_plan in enumerate(
        series_plans,
        start=1,
    ):
        lines.append(f"SERIES_PLAN_{index}={series_plan.canonical_row}")

    lines.extend(
        (
            (f"EMIT_ON_CANDLE_CLOSE={str(policy.emit_on_candle_close).lower()}"),
            (f"PRESERVE_SERIES_ORDER={str(policy.preserve_series_order).lower()}"),
            (f"DETERMINISTIC_TIE_BREAK={str(policy.deterministic_tie_break).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"INCLUDE_WARMUP_CANDLES={str(policy.include_warmup_candles).lower()}"),
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
class StrategyPhase8OfflineReplayPlan:
    """
    Immutable deterministic replay plan.

    This plan defines replay bounds and ordering only. It
    does not iterate candles, evaluate the strategy, fetch
    data, initialize MT5, write storage, contact a broker,
    or submit an order.
    """

    specification_decision: Phase8OfflineSimulationRunSpecificationDecision = field(repr=False)
    policy: Phase8OfflineReplayPlanPolicy
    schema_version: str
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
    replay_clock: Phase8OfflineReplayClock
    merge_mode: Phase8OfflineReplayMergeMode
    tie_break: Phase8OfflineReplayTieBreak
    series_plans: tuple[
        Phase8OfflineReplaySeriesPlan,
        ...,
    ] = field(repr=False)
    total_event_count: int
    plan_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.specification_decision,
            Phase8OfflineSimulationRunSpecificationDecision,
        ):
            raise ValueError(
                "specification_decision must be a Phase8OfflineSimulationRunSpecificationDecision."
            )

        if not self.specification_decision.is_created:
            raise ValueError(
                "An offline replay plan requires a created offline simulation run specification."
            )

        if not isinstance(
            self.policy,
            Phase8OfflineReplayPlanPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayPlanPolicy.")

        if not self.policy.is_strict:
            raise ValueError("Offline replay-plan policy must remain strict and no-lookahead.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PHASE_8_OFFLINE_REPLAY_PLAN_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current offline replay-plan schema.")

        string_fields = (
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
            ("plan_digest", self.plan_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "specification_digest",
            "input_digest",
            "snapshot_digest",
            "plan_digest",
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

        if not isinstance(self.series_plans, tuple):
            raise ValueError("series_plans must be a tuple.")

        if len(self.series_plans) != 4:
            raise ValueError("series_plans must contain four entries.")

        if not all(
            isinstance(
                series_plan,
                Phase8OfflineReplaySeriesPlan,
            )
            for series_plan in self.series_plans
        ):
            raise ValueError("series_plans must contain Phase8OfflineReplaySeriesPlan members.")

        planned_timeframes = tuple(item.timeframe for item in self.series_plans)

        if planned_timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("series_plans must preserve H4, H1, M15, and M5 deterministic order.")

        expected_priorities = tuple(
            _EXPECTED_PRIORITIES[timeframe] for timeframe in _REQUIRED_TIMEFRAMES
        )
        supplied_priorities = tuple(item.priority for item in self.series_plans)

        if supplied_priorities != expected_priorities:
            raise ValueError("series_plans must preserve exact timeframe priorities.")

        total_event_count = _positive_integer(
            self.total_event_count,
            "total_event_count",
        )

        if total_event_count != sum(item.planned_event_count for item in self.series_plans):
            raise ValueError("total_event_count must equal the sum of planned series events.")

        specification = self.specification_decision.specification_required
        input_package = specification.input_package
        snapshot = specification.snapshot

        comparisons = (
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
                specification.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                specification.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the offline run-specification lineage.")

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Offline replay plans support Gold/XAUUSD only.")

        if self.direction != specification.direction:
            raise ValueError("direction must match the offline run specification.")

        if self.side != specification.side:
            raise ValueError("side must match the offline run specification.")

        if captured_at != specification.captured_at:
            raise ValueError("captured_at must match the offline run specification.")

        if planned_timeframes != specification.timeframes:
            raise ValueError("series_plans must match specification timeframes.")

        for source_series, series_plan in zip(
            snapshot.series,
            self.series_plans,
            strict=True,
        ):
            expected_values = (
                source_series.timeframe,
                _EXPECTED_PRIORITIES[source_series.timeframe],
                source_series.candle_count,
                0,
                source_series.candle_count - 1,
                source_series.first_open_time,
                source_series.candles[0].close_time,
                source_series.latest_open_time,
                source_series.latest_close_time,
                source_series.series_digest,
            )
            supplied_values = (
                series_plan.timeframe,
                series_plan.priority,
                series_plan.candle_count,
                series_plan.start_index,
                series_plan.end_index,
                series_plan.first_open_time,
                series_plan.first_close_time,
                series_plan.latest_open_time,
                series_plan.latest_close_time,
                series_plan.series_digest,
            )

            if supplied_values != expected_values:
                raise ValueError(
                    f"{source_series.timeframe.value} "
                    "series plan must match the immutable "
                    "closed-candle snapshot."
                )

            if series_plan.latest_close_time > captured_at:
                raise ValueError(
                    f"{series_plan.timeframe.value} replay bounds cannot include an open candle."
                )

        if total_event_count != specification.total_candle_count:
            raise ValueError("total_event_count must match the offline run specification.")

        if not specification.no_lookahead:
            raise ValueError("Run specification must remain no-lookahead.")

        if not specification.strict_chronology:
            raise ValueError("Run specification must preserve strict chronology.")

        safe_subjects = (
            self.specification_decision,
            specification,
            specification.input_decision,
            input_package,
            specification.verification_receipt,
            snapshot,
            specification.contract,
            specification.dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Offline replay lineage violates the non-I/O or non-execution boundary."
            )

        canonical_payload = _canonical_plan_payload(
            schema_version=schema_version,
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
            replay_clock=self.replay_clock,
            merge_mode=self.merge_mode,
            tie_break=self.tie_break,
            policy=self.policy,
            series_plans=self.series_plans,
            total_event_count=total_event_count,
        )

        if normalized_strings["plan_digest"] != _sha256_digest(canonical_payload):
            raise ValueError("plan_digest does not match the canonical offline replay plan.")

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
    def specification(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        return self.specification_decision.specification_required

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.specification.input_package

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.specification.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.specification.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.specification.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.specification.dry_run_package

    @property
    def timeframes(self) -> tuple[Phase8Timeframe, ...]:
        return tuple(item.timeframe for item in self.series_plans)

    @property
    def series_count(self) -> int:
        return len(self.series_plans)

    @property
    def replay_event_count(self) -> int:
        return self.total_event_count

    @property
    def earliest_open_time(self) -> datetime:
        return min(item.first_open_time for item in self.series_plans)

    @property
    def latest_close_time(self) -> datetime:
        return max(item.latest_close_time for item in self.series_plans)

    @property
    def canonical_payload(self) -> str:
        return _canonical_plan_payload(
            schema_version=self.schema_version,
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
            replay_clock=self.replay_clock,
            merge_mode=self.merge_mode,
            tie_break=self.tie_break,
            policy=self.policy,
            series_plans=self.series_plans,
            total_event_count=self.total_event_count,
        )

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def offline_only(self) -> bool:
        return True

    @property
    def snapshot_only(self) -> bool:
        return True

    @property
    def no_lookahead(self) -> bool:
        return self.policy.no_lookahead

    @property
    def deterministic(self) -> bool:
        return True

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
    def can_continue_to_replay_event_contract(
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
    def plan_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_REPLAY_PLAN:"
            f"PLAN_SHA256[{self.plan_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.specification_decision.stable_id}:{self.plan_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineReplayPlanDecision:
    """Immutable offline replay-plan decision."""

    specification_decision: Phase8OfflineSimulationRunSpecificationDecision = field(repr=False)
    status: Phase8OfflineReplayPlanStatus
    reason: Phase8OfflineReplayPlanReason
    blockers: tuple[
        Phase8OfflineReplayPlanBlocker,
        ...,
    ]
    plan: StrategyPhase8OfflineReplayPlan | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.specification_decision,
            Phase8OfflineSimulationRunSpecificationDecision,
        ):
            raise ValueError(
                "specification_decision must be a Phase8OfflineSimulationRunSpecificationDecision."
            )

        try:
            status = Phase8OfflineReplayPlanStatus(self.status)
            reason = Phase8OfflineReplayPlanReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported offline replay-plan status or reason.") from error

        blockers = tuple(Phase8OfflineReplayPlanBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Offline replay-plan blockers cannot contain duplicates.")

        if self.specification_decision.is_blocked:
            if (
                status != Phase8OfflineReplayPlanStatus.BLOCKED
                or reason != (Phase8OfflineReplayPlanReason.RUN_SPECIFICATION_BLOCKED)
                or blockers != (Phase8OfflineReplayPlanBlocker.RUN_SPECIFICATION_BLOCKED,)
                or self.plan is not None
            ):
                raise ValueError("Blocked replay-plan result does not match its run specification.")
        else:
            if (
                status != Phase8OfflineReplayPlanStatus.CREATED
                or reason != Phase8OfflineReplayPlanReason.CREATED
                or blockers
                or not isinstance(
                    self.plan,
                    StrategyPhase8OfflineReplayPlan,
                )
                or self.plan.specification_decision is not self.specification_decision
            ):
                raise ValueError("Created replay-plan result does not match its run specification.")

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.specification_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.specification_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == Phase8OfflineReplayPlanStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_plan(self) -> bool:
        return self.plan is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def plan_required(
        self,
    ) -> StrategyPhase8OfflineReplayPlan:
        if self.plan is None:
            raise ValueError("No Phase 8 offline replay plan was created.")

        return self.plan

    @property
    def can_continue_to_replay_event_contract(
        self,
    ) -> bool:
        return self.is_created

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
            f"{self.specification_decision.stable_id}:"
            "PHASE_8_OFFLINE_REPLAY_PLAN_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineReplayPlanFactory:
    """Pure immutable offline replay-plan factory."""

    def generate(
        self,
        specification_decision: (Phase8OfflineSimulationRunSpecificationDecision),
        policy: Phase8OfflineReplayPlanPolicy | None = None,
    ) -> Phase8OfflineReplayPlanDecision:
        if not isinstance(
            specification_decision,
            Phase8OfflineSimulationRunSpecificationDecision,
        ):
            raise Phase8OfflineReplayPlanError(
                Phase8OfflineReplayPlanErrorReason.INVALID_RUN_SPECIFICATION_DECISION,
                "specification_decision must be a Phase8OfflineSimulationRunSpecificationDecision.",
            )

        selected_policy = policy or Phase8OfflineReplayPlanPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineReplayPlanPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineReplayPlanPolicy.")

        if specification_decision.is_blocked:
            return Phase8OfflineReplayPlanDecision(
                specification_decision=specification_decision,
                status=Phase8OfflineReplayPlanStatus.BLOCKED,
                reason=(Phase8OfflineReplayPlanReason.RUN_SPECIFICATION_BLOCKED),
                blockers=(Phase8OfflineReplayPlanBlocker.RUN_SPECIFICATION_BLOCKED,),
                plan=None,
            )

        specification = specification_decision.specification_required
        snapshot = specification.snapshot

        series_plans = tuple(
            Phase8OfflineReplaySeriesPlan(
                timeframe=source_series.timeframe,
                priority=_EXPECTED_PRIORITIES[source_series.timeframe],
                candle_count=source_series.candle_count,
                start_index=0,
                end_index=source_series.candle_count - 1,
                first_open_time=source_series.first_open_time,
                first_close_time=(source_series.candles[0].close_time),
                latest_open_time=source_series.latest_open_time,
                latest_close_time=source_series.latest_close_time,
                series_digest=source_series.series_digest,
            )
            for source_series in snapshot.series
        )

        total_event_count = sum(item.planned_event_count for item in series_plans)

        canonical_payload = _canonical_plan_payload(
            schema_version=(PHASE_8_OFFLINE_REPLAY_PLAN_SCHEMA_VERSION),
            specification_id=specification.stable_id,
            specification_digest=(specification.specification_digest),
            input_package_id=(specification.input_package.stable_id),
            input_digest=(specification.input_package.input_digest),
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            broker_symbol=specification.broker_symbol,
            direction=specification.direction,
            side=specification.side,
            source_name=specification.source_name,
            captured_at=specification.captured_at,
            replay_clock=Phase8OfflineReplayClock.CANDLE_CLOSE,
            merge_mode=(Phase8OfflineReplayMergeMode.CHRONOLOGICAL_STABLE),
            tie_break=(Phase8OfflineReplayTieBreak.TIMEFRAME_PRIORITY),
            policy=selected_policy,
            series_plans=series_plans,
            total_event_count=total_event_count,
        )

        plan = StrategyPhase8OfflineReplayPlan(
            specification_decision=specification_decision,
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_REPLAY_PLAN_SCHEMA_VERSION),
            specification_id=specification.stable_id,
            specification_digest=(specification.specification_digest),
            input_package_id=(specification.input_package.stable_id),
            input_digest=(specification.input_package.input_digest),
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            broker_symbol=specification.broker_symbol,
            direction=specification.direction,
            side=specification.side,
            source_name=specification.source_name,
            captured_at=specification.captured_at,
            replay_clock=Phase8OfflineReplayClock.CANDLE_CLOSE,
            merge_mode=(Phase8OfflineReplayMergeMode.CHRONOLOGICAL_STABLE),
            tie_break=(Phase8OfflineReplayTieBreak.TIMEFRAME_PRIORITY),
            series_plans=series_plans,
            total_event_count=total_event_count,
            plan_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineReplayPlanDecision(
            specification_decision=specification_decision,
            status=Phase8OfflineReplayPlanStatus.CREATED,
            reason=Phase8OfflineReplayPlanReason.CREATED,
            blockers=(),
            plan=plan,
        )

    def build(
        self,
        specification_decision: (Phase8OfflineSimulationRunSpecificationDecision),
        policy: Phase8OfflineReplayPlanPolicy | None = None,
    ) -> Phase8OfflineReplayPlanDecision:
        return self.generate(
            specification_decision,
            policy,
        )

    def evaluate(
        self,
        specification_decision: (Phase8OfflineSimulationRunSpecificationDecision),
        policy: Phase8OfflineReplayPlanPolicy | None = None,
    ) -> Phase8OfflineReplayPlanDecision:
        return self.generate(
            specification_decision,
            policy,
        )


def generate_phase8_offline_replay_plan(
    specification_decision: (Phase8OfflineSimulationRunSpecificationDecision),
    policy: Phase8OfflineReplayPlanPolicy | None = None,
) -> Phase8OfflineReplayPlanDecision:
    return StrategyPhase8OfflineReplayPlanFactory().generate(
        specification_decision,
        policy,
    )


Phase8OfflineReplayPlan = StrategyPhase8OfflineReplayPlan
Phase8OfflineReplayPlanFactory = StrategyPhase8OfflineReplayPlanFactory
