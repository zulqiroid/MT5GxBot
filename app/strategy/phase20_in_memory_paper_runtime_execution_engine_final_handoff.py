from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase20_in_memory_paper_runtime_execution_engine_blueprint import (
    build_phase20_in_memory_paper_runtime_execution_engine_blueprint,
)
from app.strategy.phase20_in_memory_paper_runtime_execution_engine_safety_audit import (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_STATUS,
    Phase20InMemoryPaperRuntimeEngineSafetyAudit,
    audit_phase20_in_memory_paper_runtime_execution_engine_safety,
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_SOURCE = (
    PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_STATUS
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_STATUS = (
    "PHASE_20_FINAL_IN_MEMORY_PAPER_RUNTIME_EXECUTION_ENGINE_HANDOFF_ESTABLISHED"
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_NEXT_ALLOWED = (
    "LOCAL_ANNOTATED_PHASE_20_RELEASE_TAG"
)
PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_RELEASE_TAG = (
    "goldxbot-phase-20-complete"
)

PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_GUARDS = (
    "SAFETY_AUDIT_LINEAGE_VERIFIED",
    "SAFETY_FINDINGS_COMPLETE",
    "DETERMINISTIC_COMPONENT_CHAIN_PRESERVED",
    "STATE_MACHINE_AND_TERMINAL_FLATNESS_PRESERVED",
    "MARKET_CANDLE_AND_NO_LOOKAHEAD_SCOPE_PRESERVED",
    "CONSERVATIVE_FILL_POLICY_PRESERVED",
    "POSITION_AND_RISK_LIMITS_PRESERVED",
    "PROTECTION_CONTRACT_PRESERVED",
    "IN_MEMORY_ONLY_AND_REAL_EFFECT_BOUNDARIES_PRESERVED",
    "LOCAL_RELEASE_TAG_ONLY",
    "ENGINE_INVOCATION_REMAINS_BLOCKED",
    "PHASE_21_NOT_ADMITTED",
)


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineFinalHandoffGuard:
    """One immutable guard in the Phase 20 final engine handoff."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_GUARDS
        ):
            raise ValueError("Unknown Phase 20 final-handoff guard.")

        if not self.evidence:
            raise ValueError("Phase 20 final-handoff evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineFinalHandoff:
    """Fail-closed Phase 20 final in-memory engine handoff."""

    audit_id: str
    audit_digest: str
    guards: tuple[
        Phase20InMemoryPaperRuntimeEngineFinalHandoffGuard,
        ...,
    ]
    schema_version: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_SCHEMA_VERSION
    )
    source: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_SOURCE
    )
    status: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_STATUS
    )
    next_allowed_step: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_NEXT_ALLOWED
    )
    release_tag: str = (
        PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_RELEASE_TAG
    )
    release_tag_creation_permitted: bool = True
    in_memory_simulation_execution_admitted: bool = True
    engine_invocation_permitted: bool = False
    remote_push_permitted: bool = False
    real_runtime_access_permitted: bool = False
    external_effects_permitted: bool = False
    phase21_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.audit_id or len(self.audit_digest) != 64:
            raise ValueError("Phase 20 safety-audit lineage is invalid.")

        if self.schema_version != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_SCHEMA_VERSION
        ):
            raise ValueError("Phase 20 final-handoff schema is invalid.")

        if self.source != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_SOURCE
        ):
            raise ValueError("Phase 20 final-handoff source is invalid.")

        if self.status != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_STATUS
        ):
            raise ValueError("Phase 20 final-handoff status is invalid.")

        if self.next_allowed_step != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_NEXT_ALLOWED
        ):
            raise ValueError("Phase 20 final-handoff next step is invalid.")

        if self.release_tag != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_RELEASE_TAG
        ):
            raise ValueError("Phase 20 release tag is invalid.")

        if tuple(item.name for item in self.guards) != (
            PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_GUARDS
        ):
            raise ValueError("Phase 20 final-handoff guards are incomplete.")

        if not all(item.passed for item in self.guards):
            raise ValueError("Phase 20 final handoff contains failed guards.")

        if not self.release_tag_creation_permitted:
            raise ValueError("Phase 20 local release-tag creation is required.")

        if not self.in_memory_simulation_execution_admitted:
            raise ValueError("Phase 20 simulation admission must be preserved.")

        if self.engine_invocation_permitted:
            raise ValueError("Phase 20.5 cannot invoke the engine.")

        if self.remote_push_permitted:
            raise ValueError("Phase 20.5 cannot permit remote push.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 20.5 cannot permit real runtime access.")

        if self.external_effects_permitted:
            raise ValueError("Phase 20.5 cannot permit external effects.")

        if self.phase21_admitted:
            raise ValueError("Phase 21 cannot be admitted by Phase 20.5.")

    @property
    def guard_count(self) -> int:
        return len(self.guards)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.guards)

    @property
    def handoff_digest(self) -> str:
        """Hash bounded handoff fields without recursive expansion."""

        material = "|".join(
            (
                self.audit_digest,
                self.schema_version,
                self.source,
                self.status,
                self.next_allowed_step,
                self.release_tag,
                ",".join(
                    f"{item.name}:{item.passed}:{item.evidence}"
                    for item in self.guards
                ),
                str(self.release_tag_creation_permitted),
                str(self.in_memory_simulation_execution_admitted),
                str(self.engine_invocation_permitted),
                str(self.remote_push_permitted),
                str(self.real_runtime_access_permitted),
                str(self.external_effects_permitted),
                str(self.phase21_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_20_IN_MEMORY_PAPER_RUNTIME_"
            "EXECUTION_ENGINE_FINAL_HANDOFF:"
            f"SHA256[{self.handoff_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase20InMemoryPaperRuntimeEngineFinalHandoffDecision:
    """Decision wrapper for the Phase 20 final engine handoff."""

    established: bool
    reason: str
    handoff: Phase20InMemoryPaperRuntimeEngineFinalHandoff | None

    @property
    def handoff_required(
        self,
    ) -> Phase20InMemoryPaperRuntimeEngineFinalHandoff:
        if not self.established or self.handoff is None:
            raise RuntimeError("Phase 20 final engine handoff is unavailable.")
        return self.handoff


class Phase20InMemoryPaperRuntimeEngineFinalHandoffBuilder:
    """Establish the Phase 20 final handoff without invoking the engine."""

    def build(
        self,
        audit: Phase20InMemoryPaperRuntimeEngineSafetyAudit,
    ) -> Phase20InMemoryPaperRuntimeEngineFinalHandoffDecision:
        blueprint = (
            build_phase20_in_memory_paper_runtime_execution_engine_blueprint()
            .blueprint_required
        )
        finding_evidence = {
            item.name: item.evidence for item in audit.findings
        }

        guards = (
            (
                "SAFETY_AUDIT_LINEAGE_VERIFIED",
                audit.status
                == PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_SAFETY_AUDIT_STATUS
                and bool(audit.audit_id)
                and len(audit.audit_digest) == 64,
                audit.audit_id,
            ),
            (
                "SAFETY_FINDINGS_COMPLETE",
                audit.finding_count == 12
                and audit.passed_count == 12,
                f"findings={audit.passed_count}/{audit.finding_count}",
            ),
            (
                "DETERMINISTIC_COMPONENT_CHAIN_PRESERVED",
                blueprint.component_count == 12,
                finding_evidence["COMPONENT_CHAIN_DETERMINISTIC"],
            ),
            (
                "STATE_MACHINE_AND_TERMINAL_FLATNESS_PRESERVED",
                blueprint.states[-1] == "FLAT_TERMINATED",
                (
                    f'{finding_evidence["STATE_MACHINE_FAIL_CLOSED"]};'
                    f'{finding_evidence["PROTECTION_AND_TERMINAL_FLATNESS_CONFIRMED"]}'
                ),
            ),
            (
                "MARKET_CANDLE_AND_NO_LOOKAHEAD_SCOPE_PRESERVED",
                blueprint.symbol == "XAUUSD"
                and blueprint.timeframes == ("H4", "H1", "M15", "M5")
                and blueprint.signal_evaluation_policy == "CANDLE_CLOSE_ONLY",
                (
                    f'{finding_evidence["MARKET_SCOPE_RESTRICTED"]};'
                    f'{finding_evidence["CLOSED_CANDLE_NO_LOOKAHEAD_ENFORCED"]}'
                ),
            ),
            (
                "CONSERVATIVE_FILL_POLICY_PRESERVED",
                blueprint.entry_fill_policy
                == "NEXT_EVENT_OPEN_AFTER_SIGNAL_CLOSE"
                and blueprint.same_bar_conflict_policy == "STOP_FIRST",
                finding_evidence["CONSERVATIVE_FILL_POLICY_CONFIRMED"],
            ),
            (
                "POSITION_AND_RISK_LIMITS_PRESERVED",
                blueprint.maximum_open_gold_positions == 1
                and blueprint.aggregate_risk_budget_bps == 50
                and blueprint.stage_risk_bps == (25, 25),
                (
                    f'{finding_evidence["POSITION_LIMIT_CONFIRMED"]};'
                    f'{finding_evidence["RISK_LIMITS_CONFIRMED"]}'
                ),
            ),
            (
                "PROTECTION_CONTRACT_PRESERVED",
                finding_evidence[
                    "PROTECTION_AND_TERMINAL_FLATNESS_CONFIRMED"
                ]
                == (
                    "oco_required=True;"
                    "stop_loss_required=True;"
                    "terminal_flat_required=True"
                ),
                finding_evidence[
                    "PROTECTION_AND_TERMINAL_FLATNESS_CONFIRMED"
                ],
            ),
            (
                "IN_MEMORY_ONLY_AND_REAL_EFFECT_BOUNDARIES_PRESERVED",
                audit.in_memory_simulation_execution_admitted
                and not audit.real_runtime_access_permitted
                and not audit.external_effects_permitted,
                (
                    f'{finding_evidence["IN_MEMORY_BOUNDARY_CONFIRMED"]};'
                    f'{finding_evidence["REAL_AND_EXTERNAL_EFFECTS_BLOCKED"]}'
                ),
            ),
            (
                "LOCAL_RELEASE_TAG_ONLY",
                True,
                (
                    "release_tag="
                    f"{PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_RELEASE_TAG};"
                    "remote_push_permitted=False"
                ),
            ),
            (
                "ENGINE_INVOCATION_REMAINS_BLOCKED",
                not audit.engine_invocation_permitted,
                "engine_invocation_permitted=False",
            ),
            (
                "PHASE_21_NOT_ADMITTED",
                not audit.phase21_admitted,
                finding_evidence["PHASE_21_NOT_ADMITTED"],
            ),
        )

        if not all(passed for _, passed, _ in guards):
            return Phase20InMemoryPaperRuntimeEngineFinalHandoffDecision(
                established=False,
                reason="PHASE_20_FINAL_ENGINE_HANDOFF_BLOCKED",
                handoff=None,
            )

        handoff = Phase20InMemoryPaperRuntimeEngineFinalHandoff(
            audit_id=audit.audit_id,
            audit_digest=audit.audit_digest,
            guards=tuple(
                Phase20InMemoryPaperRuntimeEngineFinalHandoffGuard(
                    name=name,
                    passed=passed,
                    evidence=evidence,
                )
                for name, passed, evidence in guards
            ),
        )

        return Phase20InMemoryPaperRuntimeEngineFinalHandoffDecision(
            established=True,
            reason="PHASE_20_FINAL_ENGINE_HANDOFF_ESTABLISHED",
            handoff=handoff,
        )


def generate_phase20_in_memory_paper_runtime_execution_engine_final_handoff(
) -> Phase20InMemoryPaperRuntimeEngineFinalHandoffDecision:
    """Generate the fail-closed Phase 20 final engine handoff."""

    audit = (
        audit_phase20_in_memory_paper_runtime_execution_engine_safety()
        .audit_required
    )
    return Phase20InMemoryPaperRuntimeEngineFinalHandoffBuilder().build(
        audit
    )


__all__ = (
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_SOURCE",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_STATUS",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_NEXT_ALLOWED",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_RELEASE_TAG",
    "PHASE_20_IN_MEMORY_PAPER_RUNTIME_ENGINE_FINAL_HANDOFF_GUARDS",
    "Phase20InMemoryPaperRuntimeEngineFinalHandoffGuard",
    "Phase20InMemoryPaperRuntimeEngineFinalHandoff",
    "Phase20InMemoryPaperRuntimeEngineFinalHandoffDecision",
    "Phase20InMemoryPaperRuntimeEngineFinalHandoffBuilder",
    "generate_phase20_in_memory_paper_runtime_execution_engine_final_handoff",
)
