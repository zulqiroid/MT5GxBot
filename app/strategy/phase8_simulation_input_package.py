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
    Phase8ClosedCandleSnapshotVerificationDecision,
    StrategyPhase8ClosedCandleSnapshotVerificationReceipt,
)
from app.strategy.phase8_dry_run_foundation import (
    Phase8MarketDataMode,
    Phase8RunMode,
    Phase8Timeframe,
    StrategyPhase8DryRunPackage,
)

PHASE_8_SIMULATION_INPUT_PACKAGE_SCHEMA_VERSION = "1.0"


_REQUIRED_TIMEFRAMES = (
    Phase8Timeframe.H4,
    Phase8Timeframe.H1,
    Phase8Timeframe.M15,
    Phase8Timeframe.M5,
)


class Phase8SimulationInputPackageStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class Phase8SimulationInputPackageReason(str, Enum):
    CREATED = "CREATED"
    SNAPSHOT_VERIFICATION_BLOCKED = "SNAPSHOT_VERIFICATION_BLOCKED"


class Phase8SimulationInputPackageBlocker(str, Enum):
    SNAPSHOT_VERIFICATION_BLOCKED = "SNAPSHOT_VERIFICATION_BLOCKED"


class Phase8SimulationInputPackageErrorReason(str, Enum):
    INVALID_VERIFICATION_DECISION = "INVALID_VERIFICATION_DECISION"


class Phase8SimulationInputPackageError(RuntimeError):
    """Structured simulation-input package failure."""

    def __init__(
        self,
        reason: Phase8SimulationInputPackageErrorReason,
        message: str,
    ) -> None:
        self.reason = Phase8SimulationInputPackageErrorReason(reason)
        self.message = str(message)

        super().__init__(
            f"Phase 8 simulation-input package error [{self.reason.value}]: {self.message}"
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

    if hasattr(subject, "fetches_data"):
        if getattr(subject, "fetches_data"):
            return False

    if not hasattr(subject, "initializes_mt5"):
        return False

    if getattr(subject, "initializes_mt5"):
        return False

    return True


def _canonical_input_payload(
    *,
    schema_version: str,
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
    series_digests: tuple[
        tuple[Phase8Timeframe, str],
        ...,
    ],
    series_counts: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ],
    total_candle_count: int,
) -> str:
    timeframe_fragment = ",".join(timeframe.value for timeframe in timeframes)

    lines = [
        f"SCHEMA_VERSION={schema_version}",
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
        f"SERIES_COUNT={len(series_digests)}",
        f"TOTAL_CANDLE_COUNT={total_candle_count}",
    ]

    for index, (
        digest_item,
        count_item,
    ) in enumerate(
        zip(
            series_digests,
            series_counts,
            strict=True,
        ),
        start=1,
    ):
        digest_timeframe, digest = digest_item
        count_timeframe, count = count_item

        lines.extend(
            (
                (f"SERIES_{index}_TIMEFRAME={digest_timeframe.value}"),
                (f"SERIES_{index}_COUNT_TIMEFRAME={count_timeframe.value}"),
                f"SERIES_{index}_CANDLE_COUNT={count}",
                f"SERIES_{index}_DIGEST={digest}",
            )
        )

    lines.extend(
        (
            "RUN_MODE=SIMULATION_ONLY",
            "MARKET_DATA_MODE=CLOSED_CANDLES_ONLY",
            "GOLD_ONLY=true",
            "VERIFIED_INPUT_ONLY=true",
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
class StrategyPhase8SimulationInputPackage:
    """
    Immutable verified input package for future offline
    simulation design.

    This object does not execute a simulation, fetch data,
    initialize MT5, invoke an adapter, contact a broker,
    write storage, or submit an order.
    """

    verification_decision: Phase8ClosedCandleSnapshotVerificationDecision = field(repr=False)
    schema_version: str
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
    series_digests: tuple[
        tuple[Phase8Timeframe, str],
        ...,
    ]
    series_counts: tuple[
        tuple[Phase8Timeframe, int],
        ...,
    ]
    total_candle_count: int
    input_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.verification_decision,
            Phase8ClosedCandleSnapshotVerificationDecision,
        ):
            raise ValueError(
                "verification_decision must be a Phase8ClosedCandleSnapshotVerificationDecision."
            )

        if not self.verification_decision.is_verified:
            raise ValueError(
                "A simulation-input package requires a verified closed-candle snapshot."
            )

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PHASE_8_SIMULATION_INPUT_PACKAGE_SCHEMA_VERSION:
            raise ValueError(
                "schema_version must match the current simulation-input package schema."
            )

        string_fields = (
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
            ("input_digest", self.input_digest),
        )

        normalized_strings = {
            field_name: _non_empty_string(
                value,
                field_name,
            )
            for field_name, value in string_fields
        }

        digest_fields = (
            "verification_receipt_digest",
            "snapshot_digest",
            "contract_digest",
            "dry_run_package_digest",
            "input_digest",
        )

        for field_name in digest_fields:
            if not _is_lowercase_sha256(normalized_strings[field_name]):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        if not isinstance(
            self.direction,
            DirectionalPermissionDirection,
        ):
            raise ValueError("direction must be a DirectionalPermissionDirection member.")

        if not isinstance(self.side, StrategyOrderSide):
            raise ValueError("side must be a StrategyOrderSide member.")

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

        if not isinstance(self.series_digests, tuple):
            raise ValueError("series_digests must be a tuple.")

        if not isinstance(self.series_counts, tuple):
            raise ValueError("series_counts must be a tuple.")

        if len(self.series_digests) != 4:
            raise ValueError("series_digests must contain four entries.")

        if len(self.series_counts) != 4:
            raise ValueError("series_counts must contain four entries.")

        total_candle_count = _positive_integer(
            self.total_candle_count,
            "total_candle_count",
        )

        receipt = self.verification_decision.receipt_required
        snapshot = receipt.snapshot
        contract = snapshot.contract
        dry_run_package = contract.package

        comparisons = (
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
                snapshot.broker_symbol,
            ),
            (
                "source_name",
                normalized_strings["source_name"],
                snapshot.source_name,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the verified simulation-input lineage.")

        broker_symbol = normalized_strings["broker_symbol"]

        if not _is_gold_symbol(broker_symbol):
            raise ValueError("Simulation-input packages support Gold/XAUUSD only.")

        if self.direction != snapshot.direction:
            raise ValueError("direction must match the verified snapshot.")

        if self.side != snapshot.side:
            raise ValueError("side must match the verified snapshot.")

        if captured_at != snapshot.captured_at:
            raise ValueError("captured_at must match the verified snapshot.")

        if self.timeframes != snapshot.timeframes:
            raise ValueError("timeframes must match the verified snapshot.")

        if self.series_digests != receipt.series_digests:
            raise ValueError("series_digests must match the verification receipt.")

        if self.series_counts != receipt.series_counts:
            raise ValueError("series_counts must match the verification receipt.")

        if total_candle_count != receipt.total_candle_count:
            raise ValueError("total_candle_count must match the verification receipt.")

        if tuple(timeframe for timeframe, _ in self.series_digests) != _REQUIRED_TIMEFRAMES:
            raise ValueError("series_digests must preserve exact timeframe order.")

        if tuple(timeframe for timeframe, _ in self.series_counts) != _REQUIRED_TIMEFRAMES:
            raise ValueError("series_counts must preserve exact timeframe order.")

        for _, digest in self.series_digests:
            if not _is_lowercase_sha256(digest):
                raise ValueError(
                    "Every series digest must be a lowercase SHA-256 hexadecimal value."
                )

        for _, count in self.series_counts:
            _positive_integer(
                count,
                "series candle count",
            )

        if dry_run_package.scenario.run_mode != (Phase8RunMode.SIMULATION_ONLY):
            raise ValueError("Dry-run package must remain SIMULATION_ONLY.")

        if dry_run_package.scenario.market_data_mode != (Phase8MarketDataMode.CLOSED_CANDLES_ONLY):
            raise ValueError("Dry-run package must remain CLOSED_CANDLES_ONLY.")

        if not dry_run_package.simulation_only:
            raise ValueError("Dry-run package must remain simulation-only.")

        if not dry_run_package.uses_closed_candles_only:
            raise ValueError("Dry-run package must use closed candles only.")

        safe_subjects = (
            self.verification_decision,
            receipt,
            snapshot,
            contract,
            dry_run_package,
        )

        if not all(_has_safe_boundary(subject) for subject in safe_subjects):
            raise ValueError(
                "Simulation-input lineage violates the non-I/O or non-execution boundary."
            )

        canonical_payload = _canonical_input_payload(
            schema_version=schema_version,
            verification_receipt_id=(normalized_strings["verification_receipt_id"]),
            verification_receipt_digest=(normalized_strings["verification_receipt_digest"]),
            snapshot_id=normalized_strings["snapshot_id"],
            snapshot_digest=(normalized_strings["snapshot_digest"]),
            contract_id=normalized_strings["contract_id"],
            contract_digest=(normalized_strings["contract_digest"]),
            dry_run_package_id=(normalized_strings["dry_run_package_id"]),
            dry_run_package_digest=(normalized_strings["dry_run_package_digest"]),
            broker_symbol=broker_symbol,
            direction=self.direction,
            side=self.side,
            source_name=normalized_strings["source_name"],
            captured_at=captured_at,
            timeframes=self.timeframes,
            series_digests=self.series_digests,
            series_counts=self.series_counts,
            total_candle_count=total_candle_count,
        )

        if normalized_strings["input_digest"] != _sha256_digest(canonical_payload):
            raise ValueError("input_digest does not match the canonical simulation-input package.")

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
    def verification_receipt(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshotVerificationReceipt:
        return self.verification_decision.receipt_required

    @property
    def snapshot(
        self,
    ) -> StrategyPhase8ClosedCandleSnapshot:
        return self.verification_receipt.snapshot

    @property
    def contract(
        self,
    ) -> StrategyPhase8ClosedCandleDataContract:
        return self.snapshot.contract

    @property
    def dry_run_package(
        self,
    ) -> StrategyPhase8DryRunPackage:
        return self.contract.package

    @property
    def canonical_payload(self) -> str:
        return _canonical_input_payload(
            schema_version=self.schema_version,
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
            series_digests=self.series_digests,
            series_counts=self.series_counts,
            total_candle_count=self.total_candle_count,
        )

    @property
    def series_count(self) -> int:
        return len(self.series_digests)

    @property
    def is_ready(self) -> bool:
        return True

    @property
    def is_verified_input(self) -> bool:
        return True

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def uses_closed_candles_only(self) -> bool:
        return True

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def can_continue_to_offline_simulation_design(
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
    def input_package_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            "PHASE_8_SIMULATION_INPUT_PACKAGE:"
            f"INPUT_SHA256[{self.input_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return f"{self.verification_decision.stable_id}:{self.input_package_id}"


@dataclass(frozen=True, slots=True)
class Phase8SimulationInputPackageDecision:
    """Immutable simulation-input package decision."""

    verification_decision: Phase8ClosedCandleSnapshotVerificationDecision = field(repr=False)
    status: Phase8SimulationInputPackageStatus
    reason: Phase8SimulationInputPackageReason
    blockers: tuple[
        Phase8SimulationInputPackageBlocker,
        ...,
    ]
    package: StrategyPhase8SimulationInputPackage | None = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.verification_decision,
            Phase8ClosedCandleSnapshotVerificationDecision,
        ):
            raise ValueError(
                "verification_decision must be a Phase8ClosedCandleSnapshotVerificationDecision."
            )

        try:
            status = Phase8SimulationInputPackageStatus(self.status)
            reason = Phase8SimulationInputPackageReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported simulation-input package status or reason.") from error

        blockers = tuple(Phase8SimulationInputPackageBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Simulation-input blockers cannot contain duplicates.")

        if self.verification_decision.is_blocked:
            if (
                status != Phase8SimulationInputPackageStatus.BLOCKED
                or reason != (Phase8SimulationInputPackageReason.SNAPSHOT_VERIFICATION_BLOCKED)
                or blockers != (Phase8SimulationInputPackageBlocker.SNAPSHOT_VERIFICATION_BLOCKED,)
                or self.package is not None
            ):
                raise ValueError(
                    "Blocked simulation-input result does not match its verification decision."
                )
        else:
            if (
                status != Phase8SimulationInputPackageStatus.CREATED
                or reason != Phase8SimulationInputPackageReason.CREATED
                or blockers
                or not isinstance(
                    self.package,
                    StrategyPhase8SimulationInputPackage,
                )
                or self.package.verification_decision is not self.verification_decision
            ):
                raise ValueError(
                    "Created simulation-input result does not match its verification decision."
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.verification_decision.broker_symbol

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.verification_decision.direction

    @property
    def is_created(self) -> bool:
        return self.status == Phase8SimulationInputPackageStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_package(self) -> bool:
        return self.package is not None

    @property
    def package_required(
        self,
    ) -> StrategyPhase8SimulationInputPackage:
        if self.package is None:
            raise ValueError("No Phase 8 simulation-input package was created.")

        return self.package

    @property
    def can_continue_to_offline_simulation_design(
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
            f"{self.verification_decision.stable_id}:"
            "PHASE_8_SIMULATION_INPUT_PACKAGE_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPhase8SimulationInputPackageFactory:
    """Pure immutable simulation-input package factory."""

    def generate(
        self,
        verification_decision: (Phase8ClosedCandleSnapshotVerificationDecision),
    ) -> Phase8SimulationInputPackageDecision:
        if not isinstance(
            verification_decision,
            Phase8ClosedCandleSnapshotVerificationDecision,
        ):
            raise Phase8SimulationInputPackageError(
                Phase8SimulationInputPackageErrorReason.INVALID_VERIFICATION_DECISION,
                "verification_decision must be a Phase8ClosedCandleSnapshotVerificationDecision.",
            )

        if verification_decision.is_blocked:
            return Phase8SimulationInputPackageDecision(
                verification_decision=verification_decision,
                status=Phase8SimulationInputPackageStatus.BLOCKED,
                reason=(Phase8SimulationInputPackageReason.SNAPSHOT_VERIFICATION_BLOCKED),
                blockers=(Phase8SimulationInputPackageBlocker.SNAPSHOT_VERIFICATION_BLOCKED,),
                package=None,
            )

        receipt = verification_decision.receipt_required
        snapshot = receipt.snapshot
        contract = snapshot.contract
        dry_run_package = contract.package

        canonical_payload = _canonical_input_payload(
            schema_version=(PHASE_8_SIMULATION_INPUT_PACKAGE_SCHEMA_VERSION),
            verification_receipt_id=receipt.stable_id,
            verification_receipt_digest=(receipt.receipt_digest),
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            contract_id=contract.stable_id,
            contract_digest=contract.contract_digest,
            dry_run_package_id=dry_run_package.stable_id,
            dry_run_package_digest=(dry_run_package.package_digest),
            broker_symbol=snapshot.broker_symbol,
            direction=snapshot.direction,
            side=snapshot.side,
            source_name=snapshot.source_name,
            captured_at=snapshot.captured_at,
            timeframes=snapshot.timeframes,
            series_digests=receipt.series_digests,
            series_counts=receipt.series_counts,
            total_candle_count=receipt.total_candle_count,
        )

        package = StrategyPhase8SimulationInputPackage(
            verification_decision=verification_decision,
            schema_version=(PHASE_8_SIMULATION_INPUT_PACKAGE_SCHEMA_VERSION),
            verification_receipt_id=receipt.stable_id,
            verification_receipt_digest=(receipt.receipt_digest),
            snapshot_id=snapshot.stable_id,
            snapshot_digest=snapshot.snapshot_digest,
            contract_id=contract.stable_id,
            contract_digest=contract.contract_digest,
            dry_run_package_id=dry_run_package.stable_id,
            dry_run_package_digest=(dry_run_package.package_digest),
            broker_symbol=snapshot.broker_symbol,
            direction=snapshot.direction,
            side=snapshot.side,
            source_name=snapshot.source_name,
            captured_at=snapshot.captured_at,
            timeframes=snapshot.timeframes,
            series_digests=receipt.series_digests,
            series_counts=receipt.series_counts,
            total_candle_count=receipt.total_candle_count,
            input_digest=_sha256_digest(canonical_payload),
        )

        return Phase8SimulationInputPackageDecision(
            verification_decision=verification_decision,
            status=Phase8SimulationInputPackageStatus.CREATED,
            reason=Phase8SimulationInputPackageReason.CREATED,
            blockers=(),
            package=package,
        )

    def build(
        self,
        verification_decision: (Phase8ClosedCandleSnapshotVerificationDecision),
    ) -> Phase8SimulationInputPackageDecision:
        return self.generate(verification_decision)

    def evaluate(
        self,
        verification_decision: (Phase8ClosedCandleSnapshotVerificationDecision),
    ) -> Phase8SimulationInputPackageDecision:
        return self.generate(verification_decision)


def generate_phase8_simulation_input_package(
    verification_decision: (Phase8ClosedCandleSnapshotVerificationDecision),
) -> Phase8SimulationInputPackageDecision:
    return StrategyPhase8SimulationInputPackageFactory().generate(verification_decision)


Phase8SimulationInputPackage = StrategyPhase8SimulationInputPackage
Phase8SimulationInputPackageFactory = StrategyPhase8SimulationInputPackageFactory
