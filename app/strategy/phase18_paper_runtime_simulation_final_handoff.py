from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.strategy.phase18_paper_runtime_simulation_safety_audit import (
    PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_HANDOFF_STATUS,
    PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_STATUS,
    Phase18PaperRuntimeSimulationSafetyAuditReport,
    audit_phase18_paper_runtime_simulation_safety,
)

PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_SCHEMA_VERSION = "1.0"
PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_SOURCE = (
    PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_STATUS
)
PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_STATUS = (
    "PHASE_18_FINAL_PAPER_RUNTIME_SIMULATION_HANDOFF_ESTABLISHED"
)
PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_NEXT_ALLOWED = (
    "PHASE_18_LOCAL_RELEASE_TAG"
)
PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG = (
    "goldxbot-phase-18-complete"
)

PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_GUARDS = (
    "SAFETY_AUDIT_LINEAGE_INTACT",
    "SAFETY_AUDIT_STATUS_PASSED",
    "SAFETY_AUDIT_FINDINGS_COMPLETE",
    "FINAL_HANDOFF_READINESS_CONFIRMED",
    "PAPER_MODE_SCOPE_CONFIRMED",
    "XAUUSD_SCOPE_CONFIRMED",
    "CLOSED_CANDLE_SCOPE_CONFIRMED",
    "RISK_AND_POSITION_LIMITS_CONFIRMED",
    "REAL_AND_SIMULATION_EXECUTION_BLOCKED",
    "PHASE_19_NOT_ADMITTED",
)


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationFinalHandoffGuard:
    """One immutable guard for the Phase 18 final handoff."""

    name: str
    passed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.name not in (
            PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_GUARDS
        ):
            raise ValueError("Unknown Phase 18 final handoff guard.")

        if not self.evidence:
            raise ValueError("Phase 18 final handoff evidence is required.")


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationFinalHandoff:
    """Final fail-closed handoff for Phase 18 paper-runtime planning."""

    audit_id: str
    audit_digest: str
    guards: tuple[Phase18PaperRuntimeSimulationFinalHandoffGuard, ...]
    schema_version: str = (
        PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_SCHEMA_VERSION
    )
    source: str = PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_SOURCE
    status: str = PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_STATUS
    next_allowed_step: str = (
        PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_NEXT_ALLOWED
    )
    release_tag: str = PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG
    release_tag_creation_permitted: bool = True
    remote_push_permitted: bool = False
    simulation_execution_permitted: bool = False
    real_runtime_access_permitted: bool = False
    phase19_admitted: bool = False

    def __post_init__(self) -> None:
        if not self.audit_id or len(self.audit_digest) != 64:
            raise ValueError("Phase 18 safety-audit lineage is invalid.")

        if self.schema_version != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_SCHEMA_VERSION
        ):
            raise ValueError("Phase 18 final handoff schema is invalid.")

        if self.source != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_SOURCE
        ):
            raise ValueError("Phase 18 final handoff source is invalid.")

        if self.status != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_STATUS
        ):
            raise ValueError("Phase 18 final handoff status is invalid.")

        if self.next_allowed_step != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_NEXT_ALLOWED
        ):
            raise ValueError("Phase 18 final handoff next step is invalid.")

        if self.release_tag != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG
        ):
            raise ValueError("Phase 18 release tag is invalid.")

        if not self.release_tag_creation_permitted:
            raise ValueError("Phase 18 local release tag must be permitted.")

        if self.remote_push_permitted:
            raise ValueError("Phase 18.5 cannot permit a remote push.")

        if tuple(item.name for item in self.guards) != (
            PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_GUARDS
        ):
            raise ValueError("Phase 18 final handoff guards are incomplete.")

        if not all(item.passed for item in self.guards):
            raise ValueError("Phase 18 final handoff contains failed guards.")

        if self.simulation_execution_permitted:
            raise ValueError("Phase 18.5 cannot permit simulation execution.")

        if self.real_runtime_access_permitted:
            raise ValueError("Phase 18.5 cannot permit real runtime access.")

        if self.phase19_admitted:
            raise ValueError("Phase 19 cannot be admitted by Phase 18.5.")

    @property
    def guard_count(self) -> int:
        return len(self.guards)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.guards)

    @property
    def handoff_digest(self) -> str:
        """Hash bounded final-handoff fields without recursive expansion."""

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
                str(self.phase19_admitted),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def handoff_id(self) -> str:
        return (
            "GOLDXBOT_PHASE_18_FINAL_PAPER_RUNTIME_SIMULATION_HANDOFF:"
            f"SHA256[{self.handoff_digest}]"
        )


@dataclass(frozen=True, slots=True)
class Phase18PaperRuntimeSimulationFinalHandoffDecision:
    """Decision wrapper for the Phase 18 final handoff."""

    ready: bool
    reason: str
    handoff: Phase18PaperRuntimeSimulationFinalHandoff | None

    @property
    def handoff_required(self) -> Phase18PaperRuntimeSimulationFinalHandoff:
        if not self.ready or self.handoff is None:
            raise RuntimeError("Phase 18 final handoff is unavailable.")
        return self.handoff


class Phase18PaperRuntimeSimulationFinalHandoffFactory:
    """Build the final Phase 18 fail-closed handoff."""

    def build(
        self,
        audit: Phase18PaperRuntimeSimulationSafetyAuditReport,
    ) -> Phase18PaperRuntimeSimulationFinalHandoffDecision:
        evidence = {
            item.name: item.evidence for item in audit.findings
        }

        checks = (
            (
                "SAFETY_AUDIT_LINEAGE_INTACT",
                bool(audit.audit_id) and len(audit.audit_digest) == 64,
                audit.audit_id,
            ),
            (
                "SAFETY_AUDIT_STATUS_PASSED",
                audit.status
                == PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_STATUS,
                audit.status,
            ),
            (
                "SAFETY_AUDIT_FINDINGS_COMPLETE",
                audit.finding_count == 10 and audit.passed_count == 10,
                f"passed={audit.passed_count};total={audit.finding_count}",
            ),
            (
                "FINAL_HANDOFF_READINESS_CONFIRMED",
                audit.handoff_status
                == PHASE_18_PAPER_RUNTIME_SIMULATION_SAFETY_AUDIT_HANDOFF_STATUS,
                audit.handoff_status,
            ),
            (
                "PAPER_MODE_SCOPE_CONFIRMED",
                "mode=PAPER" in evidence["PAPER_MODE_ENFORCED"],
                evidence["PAPER_MODE_ENFORCED"],
            ),
            (
                "XAUUSD_SCOPE_CONFIRMED",
                "symbol=XAUUSD" in evidence["XAUUSD_SCOPE_ENFORCED"],
                evidence["XAUUSD_SCOPE_ENFORCED"],
            ),
            (
                "CLOSED_CANDLE_SCOPE_CONFIRMED",
                evidence["CLOSED_CANDLES_ENFORCED"]
                == "closed_candles_only=True",
                evidence["CLOSED_CANDLES_ENFORCED"],
            ),
            (
                "RISK_AND_POSITION_LIMITS_CONFIRMED",
                evidence["ONE_POSITION_LIMIT_ENFORCED"]
                == "maximum_open_gold_positions=1"
                and evidence["FIFTY_BPS_RISK_LIMIT_ENFORCED"]
                == "aggregate_bps=50;stage_bps=(25, 25)",
                (
                    f'{evidence["ONE_POSITION_LIMIT_ENFORCED"]};'
                    f'{evidence["FIFTY_BPS_RISK_LIMIT_ENFORCED"]}'
                ),
            ),
            (
                "REAL_AND_SIMULATION_EXECUTION_BLOCKED",
                not audit.real_runtime_access_permitted
                and not audit.simulation_execution_permitted,
                (
                    "real_runtime_access_permitted="
                    f"{audit.real_runtime_access_permitted};"
                    "simulation_execution_permitted="
                    f"{audit.simulation_execution_permitted}"
                ),
            ),
            (
                "PHASE_19_NOT_ADMITTED",
                not audit.phase19_admitted,
                f"phase19_admitted={audit.phase19_admitted}",
            ),
        )

        if not all(passed for _, passed, _ in checks):
            return Phase18PaperRuntimeSimulationFinalHandoffDecision(
                ready=False,
                reason="PHASE_18_FINAL_HANDOFF_BLOCKED",
                handoff=None,
            )

        guards = tuple(
            Phase18PaperRuntimeSimulationFinalHandoffGuard(
                name=name,
                passed=passed,
                evidence=guard_evidence,
            )
            for name, passed, guard_evidence in checks
        )

        handoff = Phase18PaperRuntimeSimulationFinalHandoff(
            audit_id=audit.audit_id,
            audit_digest=audit.audit_digest,
            guards=guards,
        )

        return Phase18PaperRuntimeSimulationFinalHandoffDecision(
            ready=True,
            reason="PHASE_18_FINAL_HANDOFF_ESTABLISHED",
            handoff=handoff,
        )


def generate_phase18_paper_runtime_simulation_final_handoff(
) -> Phase18PaperRuntimeSimulationFinalHandoffDecision:
    """Generate the final Phase 18 fail-closed handoff."""

    audit = audit_phase18_paper_runtime_simulation_safety().report_required
    return Phase18PaperRuntimeSimulationFinalHandoffFactory().build(audit)


__all__ = (
    "PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_SCHEMA_VERSION",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_SOURCE",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_STATUS",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_NEXT_ALLOWED",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_RELEASE_TAG",
    "PHASE_18_PAPER_RUNTIME_SIMULATION_FINAL_HANDOFF_GUARDS",
    "Phase18PaperRuntimeSimulationFinalHandoffGuard",
    "Phase18PaperRuntimeSimulationFinalHandoff",
    "Phase18PaperRuntimeSimulationFinalHandoffDecision",
    "Phase18PaperRuntimeSimulationFinalHandoffFactory",
    "generate_phase18_paper_runtime_simulation_final_handoff",
)
