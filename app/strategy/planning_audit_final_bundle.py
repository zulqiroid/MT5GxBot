from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256

from app.strategy.directional_permission import (
    DirectionalPermissionDirection,
)
from app.strategy.order_intent_blueprint import (
    StrategyOrderSide,
)
from app.strategy.planning_audit_persistence_completion import (
    PlanningAuditPersistenceCompletionDecision,
    StrategyPlanningAuditPersistenceCompletionCertificate,
)
from app.strategy.planning_audit_persistence_outcome_contract import (
    PlanningAuditPersistenceOutcomeKind,
)
from app.strategy.planning_audit_storage_admission import (
    PlanningAuditStorageTarget,
)

PLANNING_AUDIT_FINAL_BUNDLE_SCHEMA_VERSION = "1.0"


class PlanningAuditFinalBundleComponent(str, Enum):
    ADAPTER_BINDING_VERIFICATION = "ADAPTER_BINDING_VERIFICATION"
    PERSISTENCE_REQUEST = "PERSISTENCE_REQUEST"
    REQUEST_VERIFICATION = "REQUEST_VERIFICATION"
    OUTCOME_CONTRACT = "OUTCOME_CONTRACT"
    OUTCOME_EVIDENCE = "OUTCOME_EVIDENCE"
    OUTCOME_RECEIPT = "OUTCOME_RECEIPT"
    COMPLETION_CERTIFICATE = "COMPLETION_CERTIFICATE"


_REQUIRED_COMPONENTS = (
    PlanningAuditFinalBundleComponent.ADAPTER_BINDING_VERIFICATION,
    PlanningAuditFinalBundleComponent.PERSISTENCE_REQUEST,
    PlanningAuditFinalBundleComponent.REQUEST_VERIFICATION,
    PlanningAuditFinalBundleComponent.OUTCOME_CONTRACT,
    PlanningAuditFinalBundleComponent.OUTCOME_EVIDENCE,
    PlanningAuditFinalBundleComponent.OUTCOME_RECEIPT,
    PlanningAuditFinalBundleComponent.COMPLETION_CERTIFICATE,
)


class PlanningAuditFinalBundleStatus(str, Enum):
    CREATED = "CREATED"
    BLOCKED = "BLOCKED"


class PlanningAuditFinalBundleReason(str, Enum):
    CREATED = "CREATED"
    PERSISTENCE_COMPLETION_BLOCKED = "PERSISTENCE_COMPLETION_BLOCKED"


class PlanningAuditFinalBundleBlocker(str, Enum):
    PERSISTENCE_COMPLETION_BLOCKED = "PERSISTENCE_COMPLETION_BLOCKED"


class PlanningAuditFinalBundleErrorReason(str, Enum):
    INVALID_PERSISTENCE_COMPLETION_DECISION = "INVALID_PERSISTENCE_COMPLETION_DECISION"


class PlanningAuditFinalBundleError(RuntimeError):
    """Structured analytical final-bundle failure."""

    def __init__(
        self,
        reason: PlanningAuditFinalBundleErrorReason,
        message: str,
    ) -> None:
        self.reason = PlanningAuditFinalBundleErrorReason(reason)
        self.message = str(message)

        super().__init__(f"Planning-audit final-bundle error [{self.reason.value}]: {self.message}")


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


def _expected_component_ids(
    certificate: (StrategyPlanningAuditPersistenceCompletionCertificate),
) -> tuple[str, ...]:
    request = certificate.contract.request

    return (
        request.binding_verification.stable_id,
        request.stable_id,
        certificate.contract.request_verification.stable_id,
        certificate.contract.stable_id,
        certificate.receipt.outcome_evidence.stable_id,
        certificate.outcome_receipt.stable_id,
        certificate.stable_id,
    )


def _expected_component_digests(
    certificate: (StrategyPlanningAuditPersistenceCompletionCertificate),
) -> tuple[str, ...]:
    return (
        certificate.binding_receipt_digest,
        certificate.request_digest,
        (certificate.contract.verification_receipt.verification_digest),
        certificate.outcome_contract_digest,
        certificate.evidence_digest,
        certificate.outcome_receipt_digest,
        certificate.completion_digest,
    )


def _canonical_bundle_payload(
    *,
    schema_version: str,
    components: tuple[
        PlanningAuditFinalBundleComponent,
        ...,
    ],
    component_ids: tuple[str, ...],
    component_digests: tuple[str, ...],
    target: PlanningAuditStorageTarget,
    outcome_kind: PlanningAuditPersistenceOutcomeKind,
    source_name: str,
    storage_record_reference: str,
    request_id: str,
    content_length_bytes: int,
    content_digest: str,
    manifest_digest: str,
    idempotency_key: str,
    binding_id: str,
    snapshot_id: str,
    adapter_contract_id: str,
) -> str:
    lines = [
        f"SCHEMA_VERSION={schema_version}",
        ("COMPONENTS=" + ",".join(component.value for component in components)),
    ]

    for index, (
        component,
        component_id,
        component_digest,
    ) in enumerate(
        zip(
            components,
            component_ids,
            component_digests,
            strict=True,
        ),
        start=1,
    ):
        lines.extend(
            (
                (f"COMPONENT_{index}_NAME={component.value}"),
                (f"COMPONENT_{index}_ID={component_id}"),
                (f"COMPONENT_{index}_DIGEST={component_digest}"),
            )
        )

    lines.extend(
        (
            f"TARGET={target.value}",
            f"OUTCOME_KIND={outcome_kind.value}",
            f"SOURCE_NAME={source_name}",
            (f"STORAGE_RECORD_REFERENCE={storage_record_reference}"),
            f"REQUEST_ID={request_id}",
            (f"CONTENT_LENGTH_BYTES={content_length_bytes}"),
            f"CONTENT_DIGEST={content_digest}",
            f"MANIFEST_DIGEST={manifest_digest}",
            f"IDEMPOTENCY_KEY={idempotency_key}",
            f"BINDING_ID={binding_id}",
            f"SNAPSHOT_ID={snapshot_id}",
            (f"ADAPTER_CONTRACT_ID={adapter_contract_id}"),
        )
    )

    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class StrategyPlanningAuditFinalBundle:
    """
    Immutable final analytical bundle for Phase 7.

    The bundle seals the verified persistence lineage from
    adapter-binding verification through the completion
    certificate. It records an externally verified storage
    outcome but performs and authorizes no persistence,
    adapter invocation, network, broker, MT5, or trading
    execution operation.
    """

    persistence_completion: PlanningAuditPersistenceCompletionDecision
    schema_version: str
    components: tuple[
        PlanningAuditFinalBundleComponent,
        ...,
    ]
    component_ids: tuple[str, ...]
    component_digests: tuple[str, ...]
    target: PlanningAuditStorageTarget
    outcome_kind: PlanningAuditPersistenceOutcomeKind
    source_name: str
    storage_record_reference: str
    request_id: str
    content_length_bytes: int
    content_digest: str
    manifest_digest: str
    idempotency_key: str
    binding_id: str
    snapshot_id: str
    adapter_contract_id: str
    bundle_digest: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.persistence_completion,
            PlanningAuditPersistenceCompletionDecision,
        ):
            raise ValueError(
                "persistence_completion must be a PlanningAuditPersistenceCompletionDecision."
            )

        if not self.persistence_completion.is_completed:
            raise ValueError("A final audit bundle requires a completed persistence decision.")

        schema_version = _non_empty_string(
            self.schema_version,
            "schema_version",
        )

        if schema_version != PLANNING_AUDIT_FINAL_BUNDLE_SCHEMA_VERSION:
            raise ValueError("schema_version must match the current final audit-bundle schema.")

        if not isinstance(self.components, tuple):
            raise ValueError("components must be a tuple.")

        if not all(
            isinstance(
                component,
                PlanningAuditFinalBundleComponent,
            )
            for component in self.components
        ):
            raise ValueError("components must contain final audit-bundle component members.")

        if len(set(self.components)) != len(self.components):
            raise ValueError("Final audit-bundle components cannot contain duplicates.")

        if self.components != _REQUIRED_COMPONENTS:
            raise ValueError(
                "Final audit-bundle components must contain "
                "all seven required components in "
                "deterministic order."
            )

        if not isinstance(self.component_ids, tuple):
            raise ValueError("component_ids must be a tuple.")

        if not isinstance(self.component_digests, tuple):
            raise ValueError("component_digests must be a tuple.")

        if len(self.component_ids) != len(self.components):
            raise ValueError("component_ids must contain one identity for every bundle component.")

        if len(self.component_digests) != len(self.components):
            raise ValueError(
                "component_digests must contain one digest for every bundle component."
            )

        component_ids = tuple(
            _non_empty_string(
                component_id,
                f"component_ids[{index}]",
            )
            for index, component_id in enumerate(self.component_ids)
        )
        component_digests = tuple(
            _non_empty_string(
                digest,
                f"component_digests[{index}]",
            )
            for index, digest in enumerate(self.component_digests)
        )

        for index, digest in enumerate(component_digests):
            if not _is_lowercase_sha256(digest):
                raise ValueError(
                    f"component_digests[{index}] must be a lowercase SHA-256 hexadecimal value."
                )

        if len(set(component_ids)) != len(component_ids):
            raise ValueError("Final audit-bundle component identities must be unique.")

        if not isinstance(
            self.target,
            PlanningAuditStorageTarget,
        ):
            raise ValueError("target must be a PlanningAuditStorageTarget member.")

        if not isinstance(
            self.outcome_kind,
            PlanningAuditPersistenceOutcomeKind,
        ):
            raise ValueError("outcome_kind must be a PlanningAuditPersistenceOutcomeKind member.")

        source_name = _non_empty_string(
            self.source_name,
            "source_name",
        )
        storage_record_reference = _non_empty_string(
            self.storage_record_reference,
            "storage_record_reference",
        )
        request_id = _non_empty_string(
            self.request_id,
            "request_id",
        )
        content_length = _positive_integer(
            self.content_length_bytes,
            "content_length_bytes",
        )
        content_digest = _non_empty_string(
            self.content_digest,
            "content_digest",
        )
        manifest_digest = _non_empty_string(
            self.manifest_digest,
            "manifest_digest",
        )
        idempotency_key = _non_empty_string(
            self.idempotency_key,
            "idempotency_key",
        )
        binding_id = _non_empty_string(
            self.binding_id,
            "binding_id",
        )
        snapshot_id = _non_empty_string(
            self.snapshot_id,
            "snapshot_id",
        )
        adapter_contract_id = _non_empty_string(
            self.adapter_contract_id,
            "adapter_contract_id",
        )
        bundle_digest = _non_empty_string(
            self.bundle_digest,
            "bundle_digest",
        )

        for field_name, digest in (
            ("content_digest", content_digest),
            ("manifest_digest", manifest_digest),
            ("idempotency_key", idempotency_key),
            ("bundle_digest", bundle_digest),
        ):
            if not _is_lowercase_sha256(digest):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal value.")

        certificate = self.persistence_completion.certificate_required
        request = certificate.contract.request

        expected_ids = _expected_component_ids(certificate)
        expected_digests = _expected_component_digests(certificate)

        if component_ids != expected_ids:
            raise ValueError(
                "component_ids must exactly match the complete verified persistence lineage."
            )

        if component_digests != expected_digests:
            raise ValueError(
                "component_digests must exactly match the complete verified persistence lineage."
            )

        if self.target != certificate.target:
            raise ValueError("target must match the persistence completion certificate.")

        if self.outcome_kind != certificate.outcome_kind:
            raise ValueError("outcome_kind must match the persistence completion certificate.")

        if source_name != certificate.source_name:
            raise ValueError("source_name must match the persistence completion certificate.")

        if storage_record_reference != certificate.storage_record_reference:
            raise ValueError(
                "storage_record_reference must match the persistence completion certificate."
            )

        comparisons = (
            (
                "request_id",
                request_id,
                certificate.request_id,
            ),
            (
                "content_length_bytes",
                content_length,
                certificate.content_length_bytes,
            ),
            (
                "content_digest",
                content_digest,
                certificate.content_digest,
            ),
            (
                "manifest_digest",
                manifest_digest,
                certificate.manifest_digest,
            ),
            (
                "idempotency_key",
                idempotency_key,
                certificate.idempotency_key,
            ),
            (
                "binding_id",
                binding_id,
                certificate.binding_id,
            ),
            (
                "snapshot_id",
                snapshot_id,
                certificate.snapshot_id,
            ),
            (
                "adapter_contract_id",
                adapter_contract_id,
                certificate.contract_id,
            ),
        )

        for field_name, supplied, expected in comparisons:
            if supplied != expected:
                raise ValueError(f"{field_name} must match the persistence completion certificate.")

        if request_id != request.request_id:
            raise ValueError("request_id must match the verified persistence request.")

        if content_length != request.content_length_bytes:
            raise ValueError("content_length_bytes must match the verified persistence request.")

        if content_digest != request.content_digest:
            raise ValueError("content_digest must match the verified persistence request.")

        if manifest_digest != request.manifest_digest:
            raise ValueError("manifest_digest must match the verified persistence request.")

        if idempotency_key != request.idempotency_key:
            raise ValueError("idempotency_key must match the verified persistence request.")

        if binding_id != request.binding_id:
            raise ValueError("binding_id must match the verified adapter binding.")

        if snapshot_id != request.snapshot_id:
            raise ValueError("snapshot_id must match the verified capability snapshot.")

        if adapter_contract_id != request.contract_id:
            raise ValueError("adapter_contract_id must match the verified adapter contract.")

        if not certificate.is_completed:
            raise ValueError("Final bundle requires a completed persistence certificate.")

        if not certificate.is_verified:
            raise ValueError("Final bundle requires a verified persistence certificate.")

        if not certificate.is_tamper_evident:
            raise ValueError("Final bundle requires a tamper-evident persistence certificate.")

        if not certificate.records_external_persistence:
            raise ValueError("Final bundle requires recorded external persistence evidence.")

        if certificate.performed_persistence:
            raise ValueError("Final bundle cannot claim analytical persistence execution.")

        if not (certificate.can_continue_to_final_audit_bundle_design):
            raise ValueError("Persistence completion does not permit final audit-bundle design.")

        if certificate.has_adapter_instance:
            raise ValueError("Final audit bundle cannot contain an adapter instance.")

        if certificate.request_submission_authorized:
            raise ValueError("Final audit bundle cannot inherit request-submission authorization.")

        if certificate.adapter_invocation_authorized:
            raise ValueError("Final audit bundle cannot inherit adapter-invocation authorization.")

        if certificate.storage_write_authorized:
            raise ValueError("Final audit bundle cannot inherit storage-write authorization.")

        if certificate.can_write_storage:
            raise ValueError("Final audit bundle cannot write storage.")

        if certificate.can_write_network:
            raise ValueError("Final audit bundle cannot write to the network.")

        if certificate.execution_authorized:
            raise ValueError("Final audit bundle cannot contain trading execution authorization.")

        if certificate.has_broker_request:
            raise ValueError("Final audit bundle cannot contain a broker request.")

        if certificate.can_submit_order:
            raise ValueError("Final audit bundle cannot submit an order.")

        if certificate.is_executable:
            raise ValueError("Final audit bundle cannot be executable.")

        canonical_payload = _canonical_bundle_payload(
            schema_version=schema_version,
            components=self.components,
            component_ids=component_ids,
            component_digests=component_digests,
            target=self.target,
            outcome_kind=self.outcome_kind,
            source_name=source_name,
            storage_record_reference=(storage_record_reference),
            request_id=request_id,
            content_length_bytes=content_length,
            content_digest=content_digest,
            manifest_digest=manifest_digest,
            idempotency_key=idempotency_key,
            binding_id=binding_id,
            snapshot_id=snapshot_id,
            adapter_contract_id=adapter_contract_id,
        )
        expected_bundle_digest = _sha256_digest(canonical_payload)

        if bundle_digest != expected_bundle_digest:
            raise ValueError(
                "bundle_digest does not match the canonical final audit-bundle payload."
            )

        object.__setattr__(
            self,
            "schema_version",
            schema_version,
        )
        object.__setattr__(
            self,
            "component_ids",
            component_ids,
        )
        object.__setattr__(
            self,
            "component_digests",
            component_digests,
        )
        object.__setattr__(
            self,
            "source_name",
            source_name,
        )
        object.__setattr__(
            self,
            "storage_record_reference",
            storage_record_reference,
        )
        object.__setattr__(
            self,
            "request_id",
            request_id,
        )
        object.__setattr__(
            self,
            "content_length_bytes",
            content_length,
        )
        object.__setattr__(
            self,
            "content_digest",
            content_digest,
        )
        object.__setattr__(
            self,
            "manifest_digest",
            manifest_digest,
        )
        object.__setattr__(
            self,
            "idempotency_key",
            idempotency_key,
        )
        object.__setattr__(
            self,
            "binding_id",
            binding_id,
        )
        object.__setattr__(
            self,
            "snapshot_id",
            snapshot_id,
        )
        object.__setattr__(
            self,
            "adapter_contract_id",
            adapter_contract_id,
        )
        object.__setattr__(
            self,
            "bundle_digest",
            bundle_digest,
        )

    @property
    def certificate(
        self,
    ) -> StrategyPlanningAuditPersistenceCompletionCertificate:
        return self.persistence_completion.certificate_required

    @property
    def receipt(self):
        return self.certificate.receipt

    @property
    def evidence(self):
        return self.certificate.evidence

    @property
    def outcome_contract(self):
        return self.certificate.contract

    @property
    def request_verification_receipt(self):
        return self.outcome_contract.verification_receipt

    @property
    def request(self):
        return self.outcome_contract.request

    @property
    def binding_verification_receipt(self):
        return self.request.receipt

    @property
    def broker_symbol(self) -> str:
        return self.certificate.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.certificate.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.certificate.direction

    @property
    def side(self) -> StrategyOrderSide:
        return self.certificate.side

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def canonical_payload(self) -> str:
        return _canonical_bundle_payload(
            schema_version=self.schema_version,
            components=self.components,
            component_ids=self.component_ids,
            component_digests=self.component_digests,
            target=self.target,
            outcome_kind=self.outcome_kind,
            source_name=self.source_name,
            storage_record_reference=(self.storage_record_reference),
            request_id=self.request_id,
            content_length_bytes=self.content_length_bytes,
            content_digest=self.content_digest,
            manifest_digest=self.manifest_digest,
            idempotency_key=self.idempotency_key,
            binding_id=self.binding_id,
            snapshot_id=self.snapshot_id,
            adapter_contract_id=self.adapter_contract_id,
        )

    @property
    def digest_algorithm(self) -> str:
        return "SHA-256"

    @property
    def is_complete(self) -> bool:
        return True

    @property
    def is_verified(self) -> bool:
        return True

    @property
    def is_tamper_evident(self) -> bool:
        return True

    @property
    def phase_7_complete(self) -> bool:
        return True

    @property
    def records_external_persistence(self) -> bool:
        return True

    @property
    def performed_persistence(self) -> bool:
        return False

    @property
    def can_continue_to_phase_8_design(self) -> bool:
        return True

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
    def bundle_id(self) -> str:
        return (
            f"{self.broker_symbol}:"
            f"{self.side.value}:"
            f"FINAL_PLANNING_AUDIT_BUNDLE:"
            f"{self.outcome_kind.value}:"
            f"RECORD[{self.storage_record_reference}]:"
            f"BUNDLE_SHA256[{self.bundle_digest}]"
        )

    @property
    def stable_id(self) -> str:
        return (
            f"{self.persistence_completion.stable_id}:FINAL_PLANNING_AUDIT_BUNDLE:{self.bundle_id}"
        )


@dataclass(frozen=True, slots=True)
class _FinalBundleEvaluation:
    status: PlanningAuditFinalBundleStatus
    reason: PlanningAuditFinalBundleReason
    blockers: tuple[
        PlanningAuditFinalBundleBlocker,
        ...,
    ]
    bundle: StrategyPlanningAuditFinalBundle | None


def _derive_bundle(
    persistence_completion: (PlanningAuditPersistenceCompletionDecision),
) -> _FinalBundleEvaluation:
    if persistence_completion.is_blocked:
        return _FinalBundleEvaluation(
            status=PlanningAuditFinalBundleStatus.BLOCKED,
            reason=(PlanningAuditFinalBundleReason.PERSISTENCE_COMPLETION_BLOCKED),
            blockers=(PlanningAuditFinalBundleBlocker.PERSISTENCE_COMPLETION_BLOCKED,),
            bundle=None,
        )

    certificate = persistence_completion.certificate_required
    component_ids = _expected_component_ids(certificate)
    component_digests = _expected_component_digests(certificate)

    canonical_payload = _canonical_bundle_payload(
        schema_version=(PLANNING_AUDIT_FINAL_BUNDLE_SCHEMA_VERSION),
        components=_REQUIRED_COMPONENTS,
        component_ids=component_ids,
        component_digests=component_digests,
        target=certificate.target,
        outcome_kind=certificate.outcome_kind,
        source_name=certificate.source_name,
        storage_record_reference=(certificate.storage_record_reference),
        request_id=certificate.request_id,
        content_length_bytes=(certificate.content_length_bytes),
        content_digest=certificate.content_digest,
        manifest_digest=certificate.manifest_digest,
        idempotency_key=certificate.idempotency_key,
        binding_id=certificate.binding_id,
        snapshot_id=certificate.snapshot_id,
        adapter_contract_id=certificate.contract_id,
    )

    bundle = StrategyPlanningAuditFinalBundle(
        persistence_completion=persistence_completion,
        schema_version=(PLANNING_AUDIT_FINAL_BUNDLE_SCHEMA_VERSION),
        components=_REQUIRED_COMPONENTS,
        component_ids=component_ids,
        component_digests=component_digests,
        target=certificate.target,
        outcome_kind=certificate.outcome_kind,
        source_name=certificate.source_name,
        storage_record_reference=(certificate.storage_record_reference),
        request_id=certificate.request_id,
        content_length_bytes=(certificate.content_length_bytes),
        content_digest=certificate.content_digest,
        manifest_digest=certificate.manifest_digest,
        idempotency_key=certificate.idempotency_key,
        binding_id=certificate.binding_id,
        snapshot_id=certificate.snapshot_id,
        adapter_contract_id=certificate.contract_id,
        bundle_digest=_sha256_digest(canonical_payload),
    )

    return _FinalBundleEvaluation(
        status=PlanningAuditFinalBundleStatus.CREATED,
        reason=PlanningAuditFinalBundleReason.CREATED,
        blockers=(),
        bundle=bundle,
    )


@dataclass(frozen=True, slots=True)
class PlanningAuditFinalBundleDecision:
    """Validated final Phase 7 audit-bundle result."""

    persistence_completion: PlanningAuditPersistenceCompletionDecision
    status: PlanningAuditFinalBundleStatus
    reason: PlanningAuditFinalBundleReason
    blockers: tuple[
        PlanningAuditFinalBundleBlocker,
        ...,
    ]
    bundle: StrategyPlanningAuditFinalBundle | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.persistence_completion,
            PlanningAuditPersistenceCompletionDecision,
        ):
            raise ValueError(
                "persistence_completion must be a PlanningAuditPersistenceCompletionDecision."
            )

        try:
            status = PlanningAuditFinalBundleStatus(self.status)
            reason = PlanningAuditFinalBundleReason(self.reason)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported final audit-bundle status or reason.") from error

        blockers = tuple(PlanningAuditFinalBundleBlocker(blocker) for blocker in self.blockers)

        if len(set(blockers)) != len(blockers):
            raise ValueError("Final audit-bundle blockers cannot contain duplicates.")

        if self.bundle is not None and not isinstance(
            self.bundle,
            StrategyPlanningAuditFinalBundle,
        ):
            raise ValueError("bundle must be a StrategyPlanningAuditFinalBundle or None.")

        expected = _derive_bundle(self.persistence_completion)
        supplied = _FinalBundleEvaluation(
            status=status,
            reason=reason,
            blockers=blockers,
            bundle=self.bundle,
        )

        if supplied != expected:
            raise ValueError(
                "Final audit-bundle result does not match its persistence-completion decision."
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "blockers", blockers)

    @property
    def broker_symbol(self) -> str:
        return self.persistence_completion.broker_symbol

    @property
    def observed_at(self) -> datetime:
        return self.persistence_completion.observed_at

    @property
    def direction(
        self,
    ) -> DirectionalPermissionDirection:
        return self.persistence_completion.direction

    @property
    def is_created(self) -> bool:
        return self.status == PlanningAuditFinalBundleStatus.CREATED

    @property
    def is_blocked(self) -> bool:
        return not self.is_created

    @property
    def has_bundle(self) -> bool:
        return self.bundle is not None

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def bundle_required(
        self,
    ) -> StrategyPlanningAuditFinalBundle:
        if self.bundle is None:
            raise ValueError("No final planning audit bundle was created.")

        return self.bundle

    @property
    def phase_7_complete(self) -> bool:
        return self.is_created

    @property
    def can_continue_to_phase_8_design(self) -> bool:
        return self.is_created

    @property
    def performed_persistence(self) -> bool:
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
            f"{self.persistence_completion.stable_id}:"
            f"FINAL_PLANNING_AUDIT_BUNDLE_GENERATION:"
            f"{self.status.value}:"
            f"{self.reason.value}:"
            f"{blocker_fragment}"
        )


class StrategyPlanningAuditFinalBundleFactory:
    """
    Pure factory for the final Phase 7 audit bundle.

    CREATED marks analytical Phase 7 completion only.
    It performs and authorizes no persistence, adapter
    invocation, request submission, network, broker, MT5,
    or trading execution operation.
    """

    def generate(
        self,
        persistence_completion: (PlanningAuditPersistenceCompletionDecision),
    ) -> PlanningAuditFinalBundleDecision:
        if not isinstance(
            persistence_completion,
            PlanningAuditPersistenceCompletionDecision,
        ):
            raise PlanningAuditFinalBundleError(
                PlanningAuditFinalBundleErrorReason.INVALID_PERSISTENCE_COMPLETION_DECISION,
                "persistence_completion must be a PlanningAuditPersistenceCompletionDecision.",
            )

        evaluation = _derive_bundle(persistence_completion)

        return PlanningAuditFinalBundleDecision(
            persistence_completion=persistence_completion,
            status=evaluation.status,
            reason=evaluation.reason,
            blockers=evaluation.blockers,
            bundle=evaluation.bundle,
        )

    def build(
        self,
        persistence_completion: (PlanningAuditPersistenceCompletionDecision),
    ) -> PlanningAuditFinalBundleDecision:
        """Compatibility alias for generate()."""

        return self.generate(persistence_completion)

    def evaluate(
        self,
        persistence_completion: (PlanningAuditPersistenceCompletionDecision),
    ) -> PlanningAuditFinalBundleDecision:
        """Compatibility alias for generate()."""

        return self.generate(persistence_completion)


def generate_planning_audit_final_bundle(
    persistence_completion: (PlanningAuditPersistenceCompletionDecision),
) -> PlanningAuditFinalBundleDecision:
    return StrategyPlanningAuditFinalBundleFactory().generate(persistence_completion)


AuditFinalBundle = StrategyPlanningAuditFinalBundle
AuditFinalBundleComponent = PlanningAuditFinalBundleComponent
AuditFinalBundleDecision = PlanningAuditFinalBundleDecision
AuditFinalBundleFactory = StrategyPlanningAuditFinalBundleFactory
PlanningAuditFinalBundle = StrategyPlanningAuditFinalBundle
PlanningAuditFinalBundleFactory = StrategyPlanningAuditFinalBundleFactory
StrategyAuditFinalBundle = StrategyPlanningAuditFinalBundle
StrategyAuditFinalBundleFactory = StrategyPlanningAuditFinalBundleFactory
