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
from app.strategy.phase8_simulation_input_package import (
    Phase8SimulationInputPackageDecision,
    StrategyPhase8SimulationInputPackage,
)

PHASE_8_OFFLINE_SIMULATION_RUN_SPECIFICATION_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8OfflineSimulationRunMode(str, Enum):
    OFFLINE_REPLAY_ONLY = "OFFLINE_REPLAY_ONLY"


class Phase8OfflineSimulationReplayOrder(str, Enum):
    OLDEST_TO_NEWEST = "OLDEST_TO_NEWEST"


class Phase8OfflineSimulationDataAccess(str, Enum):
    SNAPSHOT_ONLY = "SNAPSHOT_ONLY"


class Phase8OfflineSimulationRunSpecificationStatus(
    str,
    Enum,
):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8OfflineSimulationRunSpecificationReason(
    str,
    Enum,
):
    CREATED = "CREATED"
    SIMULATION_INPUT_BLOCKED = "SIMULATION_INPUT_BLOCKED"


class Phase8OfflineSimulationRunSpecificationBlocker(
    str,
    Enum,
):
    SIMULATION_INPUT_BLOCKED = "SIMULATION_INPUT_BLOCKED"


class Phase8OfflineSimulationRunSpecificationErrorReason(
    str,
    Enum,
):
    INVALID_INPUT_PACKAGE_DECISION = "INVALID_INPUT_PACKAGE_DECISION"


class Phase8OfflineSimulationRunSpecificationError(
    RuntimeError,
):
    """Structured offline run-specification failure."""

    def __init__(
        self,
        reason: (Phase8OfflineSimulationRunSpecificationErrorReason),
        message: str,
    ) -> None:
        self.reason = Phase8OfflineSimulationRunSpecificationErrorReason(reason)
        self.message = str(message)

        super().__init__(
            "Phase 8 offline simulation run-specification "
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

    if hasattr(subject, "fetches_data") and getattr(subject, "fetches_data"):
        return False

    if not hasattr(subject, "initializes_mt5"):
        return False

    if getattr(subject, "initializes_mt5"):
        return False

    return True


@dataclass(frozen=True, slots=True)
class Phase8OfflineSimulationRunPolicy:
    """Strict deterministic replay requirements."""

    strict_chronology: bool = True
    no_lookahead: bool = True
    closed_candles_only: bool = True
    deterministic_replay: bool = True
    preserve_source_prices: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "strict_chronology",
            "no_lookahead",
            "closed_candles_only",
            "deterministic_replay",
            "preserve_source_prices",
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
                self.strict_chronology,
                self.no_lookahead,
                self.closed_candles_only,
                self.deterministic_replay,
                self.preserve_source_prices,
            )
        )


def _canonical_specification_payload(
    *,
    schema_version: str,
    input_package_id: str,
    input_digest: str,
    verification_receipt_id: str,
    verification_receipt_digest: str,
    snapshot_id: str,
    snapshot_digest: str,
    contract_id: str,
    contract_digest: str,
    dry_run_package_id: str,
    dry_run_package_digest: str,
    broker_symbol: str,
    direction: DirectionalPermissionDirection,
    side: StrategyOrderSide,
    source_name: str,
    captured_at: datetime,
    timeframes: tuple[Phase8Timeframe, ...],
    series_counts: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ],
    total_candle_count: int,
    run_mode: Phase8OfflineSimulationRunMode,
    replay_order: Phase8OfflineSimulationReplayOrder,
    data_access: Phase8OfflineSimulationDataAccess,
    policy: Phase8OfflineSimulationRunPolicy,
) -> str:
    timeframe_fragment = ",".join(timeframe.value for timeframe in timeframes)

    lines = [
        f"SCHEMA_VERSION={schema_version}",
        f"INPUT_PACKAGE_ID={input_package_id}",
        f"INPUT_DIGEST={input_digest}",
        (f"VERIFICATION_RECEIPT_ID={verification_receipt_id}"),
        (f"VERIFICATION_RECEIPT_DIGEST={verification_receipt_digest}"),
        f"SNAPSHOT_ID={snapshot_id}",
        f"SNAPSHOT_DIGEST={snapshot_digest}",
        f"CONTRACT_ID={contract_id}",
        f"CONTRACT_DIGEST={contract_digest}",
        f"DRY_RUN_PACKAGE_ID={dry_run_package_id}",
        (f"DRY_RUN_PACKAGE_DIGEST={dry_run_package_digest}"),
        f"BROKER_SYMBOL={broker_symbol}",
        f"DIRECTION={direction.value}",
        f"SIDE={side.value}",
        f"SOURCE_NAME={source_name}",
        (f"CAPTURED_AT={_canonical_datetime(captured_at)}"),
        f"TIMEFRAMES={timeframe_fragment}",
        f"SERIES_COUNT={len(series_counts)}",
        f"TOTAL_CANDLE_COUNT={total_candle_count}",
        f"RUN_MODE={run_mode.value}",
        f"REPLAY_ORDER={replay_order.value}",
        f"DATA_ACCESS={data_access.value}",
    ]

    for index, (
        timeframe,
        count,
    ) in enumerate(
        series_counts,
        start=1,
    ):
        lines.extend(
            (
                (f"SERIES_{index}_TIMEFRAME={timeframe.value}"),
                f"SERIES_{index}_CANDLE_COUNT={count}",
            )
        )

    lines.extend(
        (
            (f"STRICT_CHRONOLOGY={str(policy.strict_chronology).lower()}"),
            (f"NO_LOOKAHEAD={str(policy.no_lookahead).lower()}"),
            (f"CLOSED_CANDLES_ONLY={str(policy.closed_candles_only).lower()}"),
            (f"DETERMINISTIC_REPLAY={str(policy.deterministic_replay).lower()}"),
            (f"PRESERVE_SOURCE_PRICES={str(policy.preserve_source_prices).lower()}"),
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
class StrategyPhase8OfflineSimulationRunSpecification:
    """
    Immutable requirements for a future offline replay.

    This specification does not execute a simulation,
    initialize MT5, fetch market data, invoke an adapter,
    write storage, contact a broker, or submit an order.
    """

    input_decision: Phase8SimulationInputPackageDecision = field(repr=False)
    policy: Phase8OfflineSimulationRunPolicy
    schema_version: str
    input_package_id: str
    input_digest: str
    verification_receipt_id: str
    verification_receipt_digest: str
    snapshot_id: str
    snapshot_digest: str
    contract_id: str
    contract_digest: str
    dry_run_package_id: str
    dry_run_package_digest: str
    broker_symbol: str
    direction: DirectionalPermissionDirection
    side: StrategyOrderSide
    source_name: str
    captured_at: datetime
    timeframes: tuple[Phase8Timeframe, ...]
    series_counts: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ]
    total_candle_count: int
    run_mode: Phase8OfflineSimulationRunMode
    replay_order: Phase8OfflineSimulationReplayOrder
    data_access: Phase8OfflineSimulationDataAccess
    specification_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.input_decision,
            Phase8SimulationInputPackageDecision,
        ):
            raise ValueError("input_decision must be a Phase8SimulationInputPackageDecision.")

        if not self.input_decision.is_created:
            raise ValueError(
                "An offline run specification requires a created simulation-input package."
            )

        if not isinstance(
            self.policy,
            Phase8OfflineSimulationRunPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineSimulationRunPolicy.")

        if not self.policy.is_strict:
            raise ValueError(
                "Offline simulation policy must remain strict, deterministic, and no-lookahead."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != (PHASE_8_OFFLINE_SIMULATION_RUN_SPECIFICATION_SCHEMA_VERSION):
            raise ValueError(
                "schema_version must match the current offline run-specification schema."
            )

        string_fields = (
            ("input_package_id", self.input_package_id),
            ("input_digest", self.input_digest),
            (
                "verification_receipt_id",
                self.verification_receipt_id,
            ),
            (
                "verification_receipt_digest",
                self.verification_receipt_digest,
            ),
            ("snapshot_id", self.snapshot_id),
            ("snapshot_digest", self.snapshot_digest),
            ("contract_id", self.contract_id),
            ("contract_digest", self.contract_digest),
            (
                "dry_run_package_id",
                self.dry_run_package_id,
            ),
            (
                "dry_run_package_digest",
                self.dry_run_package_digest,
            ),
            ("broker_symbol", self.broker_symbol),
            ("source_name", self.source_name),
            (
                "specification_digest",
                self.specification_digest,
            ),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        for field_name in (
            "input_digest",
            "verification_receipt_digest",
            "snapshot_digest",
            "contract_digest",
            "dry_run_package_digest",
            "specification_digest",
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
            self.run_mode,
            Phase8OfflineSimulationRunMode,
        ):
            raise ValueError("run_mode must be a Phase8OfflineSimulationRunMode member.")

        if self.run_mode != Phase8OfflineSimulationRunMode.OFFLINE_REPLAY_ONLY:
            raise ValueError("run_mode must remain OFFLINE_REPLAY_ONLY.")

        if not isinstance(
            self.replay_order,
            Phase8OfflineSimulationReplayOrder,
        ):
            raise ValueError("replay_order must be a Phase8OfflineSimulationReplayOrder member.")

        if self.replay_order != Phase8OfflineSimulationReplayOrder.OLDEST_TO_NEWEST:
            raise ValueError("replay_order must remain OLDEST_TO_NEWEST.")

        if not isinstance(
            self.data_access,
            Phase8OfflineSimulationDataAccess,
        ):
            raise ValueError("data_access must be a Phase8OfflineSimulationDataAccess member.")

        if self.data_access != Phase8OfflineSimulationDataAccess.SNAPSHOT_ONLY:
            raise ValueError("data_access must remain SNAPSHOT_ONLY.")

        captured_at = _aware_datetime(
            self.captured_at,
            "captured_at",
        )

        if not isinstance(self.timeframes, tuple):
            raise ValueError("timeframes must be a tuple.")

        if not all(isinstance(timeframe, Phase8Timeframe) for timeframe in self.timeframes):
            raise ValueError("timeframes must contain Phase8Timeframe members.")

        if self.timeframes != _REQUIRED_TIMEFRAMES:
            raise ValueError("timeframes must contain H4, H1, M15, and M5 in deterministic order.")

        if not isinstance(self.series_counts, tuple):
            raise ValueError("series_counts must be a tuple.")

        if len(self.series_counts) != 4:
            raise ValueError("series_counts must contain four entries.")

        for item in self.series_counts:
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(
                    item[0],
                    Phase8Timeframe,
                )
            ):
                raise ValueError("series_counts must contain (Phase8Timeframe, count) tuples.")

            _positive_integer(
                item[1],
                "series candle count",
            )

        if tuple(timeframe for timeframe, _ in self.series_counts) != _REQUIRED_TIMEFRAMES:
            raise ValueError("series_counts must preserve exact timeframe order.")

        total_candle_count = _positive_integer(
            self.total_candle_count,
            "total_candle_count",
        )

        if total_candle_count != sum(count for _, count in self.series_counts):
            raise ValueError("total_candle_count must equal the sum of series_counts.")

        input_package = self.input_decision.package_required
        receipt = input_package.verification_receipt
        snapshot = input_package.snapshot
        contract = input_package.contract
        dry_run_package = input_package.dry_run_package

        comparisons = (
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
                "verification_receipt_id",
                normalized_strings["verification_receipt_id"],
                receipt.stable_id,
            ),
            (
                "verification_receipt_digest",
                normalized_strings["verification_receipt_digest"],
                receipt.receipt_digest,
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
                "contract_id",
                normalized_strings["contract_id"],
                contract.stable_id,
            ),
            (
                "contract_digest",
                normalized_strings["contract_digest"],
                contract.contract_digest,
            ),
            (
                "dry_run_package_id",
                normalized_strings["dry_run_package_id"],
                dry_run_package.stable_id,
            ),
            (
                "dry_run_package_digest",
                normalized_strings["dry_run_package_digest"],
                dry_run_package.package_digest,
            ),
            (
                "broker_symbol",
                normalized_strings["broker_symbol"],
                input_package.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                input_package.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the sealed simulation-input lineage.")

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Offline simulation specifications support Gold/XAUUSD only.")

        if self.direction != input_package.direction:
            raise ValueError("direction must match the simulation-input package.")

        if self.side != input_package.side:
            raise ValueError("side must match the simulation-input package.")

        if captured_at != input_package.captured_at:
            raise ValueError("captured_at must match the simulation-input package.")

        if self.timeframes != input_package.timeframes:
            raise ValueError("timeframes must match the simulation-input package.")

        if self.series_counts != input_package.series_counts:
            raise ValueError("series_counts must match the simulation-input package.")

        if total_candle_count != input_package.total_candle_count:
            raise ValueError("total_candle_count must match the simulation-input package.")

        if not input_package.is_verified_input:
            raise ValueError("Input package must remain verified.")

        if not input_package.simulation_only:
            raise ValueError("Input package must remain simulation-only.")

        if not input_package.uses_closed_candles_only:
            raise ValueError("Input package must use closed candles only.")

        safe_subjects = (
            self.input_decision,
            input_package,
            receipt,
            snapshot,
            contract,
            dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError("Offline run lineage violates the non-I/O or non-execution boundary.")

        canonical_payload = _canonical_specification_payload(
            schema_version=schema_version,
            input_package_id=normalized_strings["input_package_id"],
            input_digest=normalized_strings["input_digest"],
            verification_receipt_id=(normalized_strings["verification_receipt_id"]),
            verification_receipt_digest=(normalized_strings["verification_receipt_digest"]),
            snapshot_id=normalized_strings["snapshot_id"],
            snapshot_digest=normalized_strings["snapshot_digest"],
            contract_id=normalized_strings["contract_id"],
            contract_digest=normalized_strings["contract_digest"],
            dry_run_package_id=normalized_strings["dry_run_package_id"],
            dry_run_package_digest=(normalized_strings["dry_run_package_digest"]),
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=normalized_strings["source_name"],
            captured_at=captured_at,
            timeframes=self.timeframes,
            series_counts=self.series_counts,
            total_candle_count=total_candle_count,
            run_mode=self.run_mode,
            replay_order=self.replay_order,
            data_access=self.data_access,
            policy=self.policy,
        )

        if normalized_strings["specification_digest"] != _sha256_digest(canonical_payload):
            raise ValueError(
                "specification_digest does not match the canonical offline run specification."
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
            "total_candle_count",
            total_candle_count,
        )

    @property
    def input_package(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        return self.input_decision.package_required

    @property
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.input_package.verification_receipt

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.input_package.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.input_package.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.input_package.dry_run_package

    @property
    def canonical_payload(self) -> str:
        return _canonical_specification_payload(
            schema_version=self.schema_version,
            input_package_id=self.input_package_id,
            input_digest=self.input_digest,
            verification_receipt_id=(self.verification_receipt_id),
            verification_receipt_digest=(self.verification_receipt_digest),
            snapshot_id=self.snapshot_id,
            snapshot_digest=self.snapshot_digest,
            contract_id=self.contract_id,
            contract_digest=self.contract_digest,
            dry_run_package_id=self.dry_run_package_id,
            dry_run_package_digest=(self.dry_run_package_digest),
            broker_symbol=self.broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=self.source_name,
            captured_at=self.captured_at,
            timeframes=self.timeframes,
            series_counts=self.series_counts,
            total_candle_count=self.total_candle_count,
            run_mode=self.run_mode,
            replay_order=self.replay_order,
            data_access=self.data_access,
            policy=self.policy,
        )

    @property
    def series_count(self) -> int:
        return len(self.series_counts)

    @property
    def replay_event_count(self) -> int:
        return self.total_candle_count

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
    def strict_chronology(self) -> bool:
        return self.policy.strict_chronology

    @property
    def executes_simulation(self) -> bool:
        return False

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def can_continue_to_offline_replay_plan(
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
    def specification_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_OFFLINE_SIMULATION_RUN_SPECIFICATION:"
            f"SPEC_SHA256[{self.specification_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.input_decision.stable_id}:{self.specification_id}"


@dataclass(frozen=True, slots=True)
class Phase8OfflineSimulationRunSpecificationDecision:
    """Immutable offline run-specification decision."""

    input_decision: Phase8SimulationInputPackageDecision = field(repr=False)
    status: Phase8OfflineSimulationRunSpecificationStatus
    reason: Phase8OfflineSimulationRunSpecificationReason
    blockers: tuple[
        Phase8OfflineSimulationRunSpecificationBlocker,
        ...,
    ]
    specification: StrategyPhase8OfflineSimulationRunSpecification | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.input_decision,
            Phase8SimulationInputPackageDecision,
        ):
            raise ValueError("input_decision must be a Phase8SimulationInputPackageDecision.")

        try:
            status = Phase8OfflineSimulationRunSpecificationStatus(self.status)
            reason = Phase8OfflineSimulationRunSpecificationReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported offline run-specification status or reason.") from error

        blockers = tuple(
            Phase8OfflineSimulationRunSpecificationBlocker(blocker) for blocker in self.blockers
        )

        if len(set(blockers)) != len(blockers):
            raise ValueError("Run-specification blockers cannot contain duplicates.")

        if self.input_decision.is_blocked:
            if (
                status != (Phase8OfflineSimulationRunSpecificationStatus.BLOCKED)
                or reason
                != (Phase8OfflineSimulationRunSpecificationReason.SIMULATION_INPUT_BLOCKED)
                or blockers
                != (Phase8OfflineSimulationRunSpecificationBlocker.SIMULATION_INPUT_BLOCKED,)
                or self.specification is not None
            ):
                raise ValueError(
                    "Blocked run-specification result does not match its input decision."
                )
        else:
            if (
                status != (Phase8OfflineSimulationRunSpecificationStatus.CREATED)
                or reason != (Phase8OfflineSimulationRunSpecificationReason.CREATED)
                or blockers
                or not isinstance(
                    self.specification,
                    StrategyPhase8OfflineSimulationRunSpecification,
                )
                or self.specification.input_decision is not self.input_decision
            ):
                raise ValueError(
                    "Created run-specification result does not match its input decision."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.input_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.input_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == (Phase8OfflineSimulationRunSpecificationStatus.CREATED)

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_specification(self) -> bool:
        return self.specification is not None

    @property
    def specification_required(
        self,
    ) -> StrategyPhase8OfflineSimulationRunSpecification:
        if self.specification is None:
            raise ValueError("No Phase 8 offline simulation run specification was created.")

        return self.specification

    @property
    def can_continue_to_offline_replay_plan(
        self,
    ) -> bool:
        return self.is_created

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
            f"{self.input_decision.stable_id}:"
            "PHASE_8_OFFLINE_SIMULATION_RUN_SPECIFICATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8OfflineSimulationRunSpecificationFactory:
    """Pure offline run-specification factory."""

    def generate(
        self,
        input_decision: Phase8SimulationInputPackageDecision,
        policy: Phase8OfflineSimulationRunPolicy | None = None,
    ) -> Phase8OfflineSimulationRunSpecificationDecision:
        if not isinstance(
            input_decision,
            Phase8SimulationInputPackageDecision,
        ):
            raise (
                Phase8OfflineSimulationRunSpecificationError(
                    Phase8OfflineSimulationRunSpecificationErrorReason.INVALID_INPUT_PACKAGE_DECISION,
                    "input_decision must be a Phase8SimulationInputPackageDecision.",
                )
            )

        selected_policy = policy or Phase8OfflineSimulationRunPolicy()

        if not isinstance(
            selected_policy,
            Phase8OfflineSimulationRunPolicy,
        ):
            raise ValueError("policy must be a Phase8OfflineSimulationRunPolicy.")

        if input_decision.is_blocked:
            return Phase8OfflineSimulationRunSpecificationDecision(
                input_decision=input_decision,
                status=(Phase8OfflineSimulationRunSpecificationStatus.BLOCKED),
                reason=(Phase8OfflineSimulationRunSpecificationReason.SIMULATION_INPUT_BLOCKED),
                blockers=(Phase8OfflineSimulationRunSpecificationBlocker.SIMULATION_INPUT_BLOCKED,),
                specification=None,
            )

        input_package = input_decision.package_required

        canonical_payload = _canonical_specification_payload(
            schema_version=(PHASE_8_OFFLINE_SIMULATION_RUN_SPECIFICATION_SCHEMA_VERSION),
            input_package_id=input_package.stable_id,
            input_digest=input_package.input_digest,
            verification_receipt_id=(input_package.verification_receipt_id),
            verification_receipt_digest=(input_package.verification_receipt_digest),
            snapshot_id=input_package.snapshot_id,
            snapshot_digest=input_package.snapshot_digest,
            contract_id=input_package.contract_id,
            contract_digest=input_package.contract_digest,
            dry_run_package_id=(input_package.dry_run_package_id),
            dry_run_package_digest=(input_package.dry_run_package_digest),
            broker_symbol=input_package.broker_symbol,
            direction=input_package.direction,
            side=input_package.side,
            source_name=input_package.source_name,
            captured_at=input_package.captured_at,
            timeframes=input_package.timeframes,
            series_counts=input_package.series_counts,
            total_candle_count=(input_package.total_candle_count),
            run_mode=(Phase8OfflineSimulationRunMode.OFFLINE_REPLAY_ONLY),
            replay_order=(Phase8OfflineSimulationReplayOrder.OLDEST_TO_NEWEST),
            data_access=(Phase8OfflineSimulationDataAccess.SNAPSHOT_ONLY),
            policy=selected_policy,
        )

        specification = StrategyPhase8OfflineSimulationRunSpecification(
            input_decision=input_decision,
            policy=selected_policy,
            schema_version=(PHASE_8_OFFLINE_SIMULATION_RUN_SPECIFICATION_SCHEMA_VERSION),
            input_package_id=input_package.stable_id,
            input_digest=input_package.input_digest,
            verification_receipt_id=(input_package.verification_receipt_id),
            verification_receipt_digest=(input_package.verification_receipt_digest),
            snapshot_id=input_package.snapshot_id,
            snapshot_digest=input_package.snapshot_digest,
            contract_id=input_package.contract_id,
            contract_digest=input_package.contract_digest,
            dry_run_package_id=(input_package.dry_run_package_id),
            dry_run_package_digest=(input_package.dry_run_package_digest),
            broker_symbol=input_package.broker_symbol,
            direction=input_package.direction,
            side=input_package.side,
            source_name=input_package.source_name,
            captured_at=input_package.captured_at,
            timeframes=input_package.timeframes,
            series_counts=input_package.series_counts,
            total_candle_count=(input_package.total_candle_count),
            run_mode=(Phase8OfflineSimulationRunMode.OFFLINE_REPLAY_ONLY),
            replay_order=(Phase8OfflineSimulationReplayOrder.OLDEST_TO_NEWEST),
            data_access=(Phase8OfflineSimulationDataAccess.SNAPSHOT_ONLY),
            specification_digest=_sha256_digest(canonical_payload),
        )

        return Phase8OfflineSimulationRunSpecificationDecision(
            input_decision=input_decision,
            status=(Phase8OfflineSimulationRunSpecificationStatus.CREATED),
            reason=(Phase8OfflineSimulationRunSpecificationReason.CREATED),
            blockers=(),
            specification=specification,
        )

    def build(
        self,
        input_decision: Phase8SimulationInputPackageDecision,
        policy: Phase8OfflineSimulationRunPolicy | None = None,
    ) -> Phase8OfflineSimulationRunSpecificationDecision:
        return self.generate(
            input_decision,
            policy,
        )

    def evaluate(
        self,
        input_decision: Phase8SimulationInputPackageDecision,
        policy: Phase8OfflineSimulationRunPolicy | None = None,
    ) -> Phase8OfflineSimulationRunSpecificationDecision:
        return self.generate(
            input_decision,
            policy,
        )


def generate_phase8_offline_simulation_run_specification(
    input_decision: Phase8SimulationInputPackageDecision,
    policy: Phase8OfflineSimulationRunPolicy | None = None,
) -> Phase8OfflineSimulationRunSpecificationDecision:
    return StrategyPhase8OfflineSimulationRunSpecificationFactory().generate(
        input_decision,
        policy,
    )


Phase8OfflineSimulationRunSpecification = StrategyPhase8OfflineSimulationRunSpecification
Phase8OfflineSimulationRunSpecificationFactory = (
    StrategyPhase8OfflineSimulationRunSpecificationFactory
)
