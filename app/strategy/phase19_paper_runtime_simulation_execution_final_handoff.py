from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase19_paper_runtime_simulation_execution_blueprint import (
    build_phase19_paper_runtime_simulation_execution_blueprint,
)
from app.strategy.phase19_paper_runtime_simulation_execution_safety_audit import (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_STATUS,
    Phase19PaperRuntimeSimulationExecutionSafetyAudit,
    audit_phase19_paper_runtime_simulation_execution_safety,
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_SOURCE = (
    PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_STATUS
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_STATUS = (
    "PHASE_19_FINAL_PAPER_RUNTIME_SIMULATION_EXECUTION_HANDOFF_ESTABLISHED"
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_NEXT_ALLOWED = (
    "LOCAL_ANNOTATED_PHASE_19_RELEASE_TAG"
)
PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG = (
    "goldxbot-phase-19-complete"
)

PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_GUARDS = (
    "SAFETY_AUDIT_LINEAGE_VERIFIED",
    "SAFETY_FINDINGS_COMPLETE",
    "DETERMINISTIC_COMPONENT_CHAIN_PRESERVED",
    "MARKET_AND_CANDLE_SCOPE_PRESERVED",
    "POSITION_AND_RISK_SCOPE_PRESERVED",
    "OCO_STOP_LOSS_AND_FLATNESS_PRESERVED",
    "UNSAFE_POSITIONING_PATTERNS_BLOCKED",
    "REAL_AND_EXTERNAL_EFFECTS_BLOCKED",
    "LOCAL_RELEASE_TAG_ONLY",
    "PHASE_20_NOT_ADMITTED",
)


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionFinalHandoffGuard:
    """One immutable guard in the Phase 19 final execution handoff."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_GUARDS
        ):
            raise ValueError("Unknown Phase 19 final-handoff guard.")

        if not self.evidence:
            raise ValueError("Phase 19 final-handoff evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionFinalHandoff:
    """Fail-closed Phase 19 final paper-runtime execution handoff."""

    audit_id: str
    audit_digest: str
    guards: tuple[
        Phase19PaperRuntimeSimulationExecutionFinalHandoffGuard,
        ...,
    ]
    schema_version: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_SCHEMA_VERSION
    )
    source: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_SOURCE
    )
    status: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_STATUS
    )
    next_allowed_step: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_NEXT_ALLOWED
    )
    release_tag: str = (
        PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG
    )
    release_tag_creation_permitted: bool = True
    remote_push_permitted: bool = False
    simulation_execution_permitted: bool = False
    real_runtime_access_permitted: bool = False
    external_effects_permitted: bool = False
    phase20_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.audit_id or len(self.audit_digest) != 64:
            raise ValueError("Phase 19 safety-audit lineage is invalid.")

        if self.schema_version != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_SCHEMA_VERSION
        ):
            raise ValueError("Phase 19 final-handoff schema is invalid.")

        if self.source != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_SOURCE
        ):
            raise ValueError("Phase 19 final-handoff source is invalid.")

        if self.status != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_STATUS
        ):
            raise ValueError("Phase 19 final-handoff status is invalid.")

        if self.next_allowed_step != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_NEXT_ALLOWED
        ):
            raise ValueError("Phase 19 final-handoff next step is invalid.")

        if self.release_tag != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG
        ):
            raise ValueError("Phase 19 release tag is invalid.")

        if tuple(item.name for item in self.guards) != (
            PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_GUARDS
        ):
            raise ValueError("Phase 19 final-handoff guards are incomplete.")

        if not all(item.passed for item in self.guards):
            raise ValueError("Phase 19 final handoff contains failed guards.")

        if not self.release_tag_creation_permitted:
            raise ValueError("Phase 19 local release-tag creation is required.")

        if self.remote_push_permitted:
            raise ValueError("Phase 19.5 cannot permit remote push.")

        if self.simulation_execution_permitted:
            raise ValueError("Phase 19.5 cannot permit simulation execution.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 19.5 cannot permit real runtime access.")

        if self.external_effects_permitted:
            raise ValueError("Phase 19.5 cannot permit external effects.")

        if self.phase20_admitted:
            raise ValueError("Phase 20 cannot be admitted by Phase 19.5.")

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
                str(self.remote_push_permitted),
                str(self.simulation_execution_permitted),
                str(self.real_runtime_access_permitted),
                str(self.external_effects_permitted),
                str(self.phase20_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_19_PAPER_RUNTIME_SIMULATION_"
            "EXECUTION_FINAL_HANDOFF:"
            f"SHA256[{self.handoff_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase19PaperRuntimeSimulationExecutionFinalHandoffDecision:
    """Decision wrapper for the Phase 19 final execution handoff."""

    established: bool
    reason: str
    handoff: Phase19PaperRuntimeSimulationExecutionFinalHandoff | None

    @property
    def handoff_required(
        self,
    ) -> Phase19PaperRuntimeSimulationExecutionFinalHandoff:
        if not self.established or self.handoff is None:
            raise RuntimeError("Phase 19 final execution handoff is unavailable.")
        return self.handoff


class Phase19PaperRuntimeSimulationExecutionFinalHandoffBuilder:
    """Establish Phase 19 final handoff without runtime execution."""

    def build(
        self,
        audit: Phase19PaperRuntimeSimulationExecutionSafetyAudit,
    ) -> Phase19PaperRuntimeSimulationExecutionFinalHandoffDecision:
        blueprint = (
            build_phase19_paper_runtime_simulation_execution_blueprint()
            .blueprint_required
        )
        finding_evidence = {
            item.name: item.evidence for item in audit.findings
        }

        guards = (
            (
                "SAFETY_AUDIT_LINEAGE_VERIFIED",
                audit.status
                == PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_SAFETY_AUDIT_STATUS
                and bool(audit.audit_id)
                and len(audit.audit_digest) == 64,
                audit.audit_id,
            ),
            (
                "SAFETY_FINDINGS_COMPLETE",
                audit.finding_count == 10
                and audit.passed_count == 10,
                f"findings={audit.passed_count}/{audit.finding_count}",
            ),
            (
                "DETERMINISTIC_COMPONENT_CHAIN_PRESERVED",
                blueprint.component_count == 10,
                finding_evidence[
                    "DETERMINISTIC_COMPONENT_CHAIN_CONFIRMED"
                ],
            ),
            (
                "MARKET_AND_CANDLE_SCOPE_PRESERVED",
                blueprint.symbol == "XAUUSD"
                and blueprint.timeframes == ("H4", "H1", "M15", "M5")
                and blueprint.closed_candles_only,
                (
                    f'{finding_evidence["MARKET_SCOPE_RESTRICTED"]};'
                    f'{finding_evidence["CLOSED_CANDLE_GATE_CONFIRMED"]}'
                ),
            ),
            (
                "POSITION_AND_RISK_SCOPE_PRESERVED",
                blueprint.maximum_open_gold_positions == 1
                and blueprint.aggregate_risk_budget_bps == 50
                and blueprint.stage_risk_bps == (25, 25),
                (
                    f'{finding_evidence["POSITION_LIMIT_CONFIRMED"]};'
                    f'{finding_evidence["RISK_LIMITS_CONFIRMED"]}'
                ),
            ),
            (
                "OCO_STOP_LOSS_AND_FLATNESS_PRESERVED",
                finding_evidence["PROTECTION_AND_FLATNESS_CONFIRMED"]
                == (
                    "oco_required=True;"
                    "stop_loss_required=True;"
                    "terminal_flat_required=True"
                ),
                finding_evidence["PROTECTION_AND_FLATNESS_CONFIRMED"],
            ),
            (
                "UNSAFE_POSITIONING_PATTERNS_BLOCKED",
                finding_evidence["UNSAFE_POSITIONING_PATTERNS_FORBIDDEN"]
                == "martingale=False;grid=False;no_sl=False",
                finding_evidence[
                    "UNSAFE_POSITIONING_PATTERNS_FORBIDDEN"
                ],
            ),
            (
                "REAL_AND_EXTERNAL_EFFECTS_BLOCKED",
                not audit.simulation_execution_permitted
                and not audit.real_runtime_access_permitted
                and not audit.external_effects_permitted,
                finding_evidence["REAL_AND_EXTERNAL_EFFECTS_BLOCKED"],
            ),
            (
                "LOCAL_RELEASE_TAG_ONLY",
                True,
                (
                    "release_tag="
                    f"{PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG};"
                    "remote_push_permitted=False"
                ),
            ),
            (
                "PHASE_20_NOT_ADMITTED",
                not audit.phase20_admitted,
                finding_evidence["PHASE_20_NOT_ADMITTED"],
            ),
        )

        if not all(passed for _, passed, _ in guards):
            return Phase19PaperRuntimeSimulationExecutionFinalHandoffDecision(
                established=False,
                reason="PHASE_19_FINAL_EXECUTION_HANDOFF_BLOCKED",
                handoff=None,
            )

        handoff = Phase19PaperRuntimeSimulationExecutionFinalHandoff(
            audit_id=audit.audit_id,
            audit_digest=audit.audit_digest,
            guards=tuple(
                Phase19PaperRuntimeSimulationExecutionFinalHandoffGuard(
                    name=name,
                    passed=passed,
                    evidence=evidence,
                )
                for name, passed, evidence in guards
            ),
        )

        return Phase19PaperRuntimeSimulationExecutionFinalHandoffDecision(
            established=True,
            reason="PHASE_19_FINAL_EXECUTION_HANDOFF_ESTABLISHED",
            handoff=handoff,
        )


def generate_phase19_paper_runtime_simulation_execution_final_handoff(
) -> Phase19PaperRuntimeSimulationExecutionFinalHandoffDecision:
    """Generate the fail-closed Phase 19 final execution handoff."""

    audit = (
        audit_phase19_paper_runtime_simulation_execution_safety()
        .audit_required
    )
    return Phase19PaperRuntimeSimulationExecutionFinalHandoffBuilder().build(
        audit
    )


__all__ = (
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_SOURCE",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_STATUS",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_NEXT_ALLOWED",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_RELEASE_TAG",
    "PHASE_19_PAPER_RUNTIME_SIMULATION_EXECUTION_FINAL_HANDOFF_GUARDS",
    "Phase19PaperRuntimeSimulationExecutionFinalHandoffGuard",
    "Phase19PaperRuntimeSimulationExecutionFinalHandoff",
    "Phase19PaperRuntimeSimulationExecutionFinalHandoffDecision",
    "Phase19PaperRuntimeSimulationExecutionFinalHandoffBuilder",
    "generate_phase19_paper_runtime_simulation_execution_final_handoff",
)
