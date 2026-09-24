#!/usr/bin/env python3
"""Exact-artifact visual qualification for v0.6 presentation hardening.

The module does not pretend to measure beauty.  It records which concrete
artifact was inspected at each production stage, localizes material loss, and
keeps automated assistance subordinate to exact-artifact human acceptance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from human_presentation_quality import (
    HumanPresentationQualityRecord,
    automated_quality_assistance,
)
from presentation_workflow import SampleArtifact


ERROR_VISUAL_QUALIFICATION_INVALID = "PRESENTATION_VISUAL_QUALIFICATION_INVALID"


class VisualStage(str, Enum):
    RAW_PLATE = "RAW_PLATE"
    HYBRID_PREVIEW = "HYBRID_PREVIEW"
    ACTUAL_CLIENT_RENDER = "ACTUAL_CLIENT_RENDER"


class VisualIssue(str, Enum):
    FONT = "FONT"
    GLYPH = "GLYPH"
    REFLOW = "REFLOW"
    OVERFLOW = "OVERFLOW"
    CROP = "CROP"
    POSITION = "POSITION"
    Z_ORDER = "Z_ORDER"
    CHART = "CHART"
    COLOR = "COLOR"
    HIERARCHY = "HIERARCHY"
    IMAGE = "IMAGE"
    OTHER = "OTHER"


class VisualDisposition(str, Enum):
    ACCEPT = "ACCEPT"
    WARNING = "WARNING"
    REPAIR = "REPAIR"
    BLOCK = "BLOCK"


class MaterialDegradation(str, Enum):
    NO_MATERIAL_DEGRADATION = "NO_MATERIAL_DEGRADATION"
    MINOR_DRIFT = "MINOR_DRIFT"
    MATERIAL_DEGRADATION = "MATERIAL_DEGRADATION"
    UNACCEPTABLE = "UNACCEPTABLE"


@dataclass(frozen=True)
class VisualObservation:
    """Deterministic facts extracted from an inspected comparison."""

    issue: VisualIssue
    semantic_content_changed: bool = False
    core_content_obscured: bool = False
    approved_quality_floor_violated: bool = False
    bounded_harmless_drift: bool = False
    repairable_degradation: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.issue, VisualIssue):
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        flags = (
            self.semantic_content_changed,
            self.core_content_obscured,
            self.approved_quality_floor_violated,
            self.bounded_harmless_drift,
            self.repairable_degradation,
        )
        if any(not isinstance(item, bool) for item in flags):
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        if self.bounded_harmless_drift and any(flags[:3]):
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)


def disposition_from_observation(observation: VisualObservation) -> VisualDisposition:
    """Apply the repository priority order to already-observed exact facts."""
    if not isinstance(observation, VisualObservation):
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    if (
        observation.semantic_content_changed
        or observation.core_content_obscured
        or observation.approved_quality_floor_violated
    ):
        return VisualDisposition.BLOCK
    if observation.bounded_harmless_drift:
        return VisualDisposition.ACCEPT
    if observation.repairable_degradation:
        return VisualDisposition.REPAIR
    return VisualDisposition.WARNING


_DISPOSITION_ORDER = {
    VisualDisposition.ACCEPT: 0,
    VisualDisposition.WARNING: 1,
    VisualDisposition.REPAIR: 2,
    VisualDisposition.BLOCK: 3,
}
_STAGE_ORDER = {
    VisualStage.RAW_PLATE: 0,
    VisualStage.HYBRID_PREVIEW: 1,
    VisualStage.ACTUAL_CLIENT_RENDER: 2,
}


def _sha(value: str) -> str:
    clean = value.strip() if isinstance(value, str) else ""
    if not re.fullmatch(r"[0-9a-f]{64}", clean):
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    return clean


@dataclass(frozen=True)
class RenderArtifactEvidence:
    slide_id: str
    stage: VisualStage
    artifact_sha256: str
    source_presentation_sha256: str
    environment: str
    actual_client: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r"slide_\d+", self.slide_id or ""):
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        if not isinstance(self.stage, VisualStage) or not isinstance(self.actual_client, bool):
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        object.__setattr__(self, "artifact_sha256", _sha(self.artifact_sha256))
        object.__setattr__(self, "source_presentation_sha256", _sha(self.source_presentation_sha256))
        environment = self.environment.strip() if isinstance(self.environment, str) else ""
        if not environment:
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        if self.stage is VisualStage.ACTUAL_CLIENT_RENDER and not self.actual_client:
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        if self.stage is not VisualStage.ACTUAL_CLIENT_RENDER and self.actual_client:
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        object.__setattr__(self, "environment", environment)


@dataclass(frozen=True)
class StageComparison:
    slide_id: str
    reference_stage: VisualStage
    delivered_stage: VisualStage
    reference_sha256: str
    delivered_sha256: str
    degradation: MaterialDegradation
    issue: VisualIssue
    disposition: VisualDisposition
    detail: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"slide_\d+", self.slide_id or ""):
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        if not all(isinstance(item, expected) for item, expected in (
            (self.reference_stage, VisualStage),
            (self.delivered_stage, VisualStage),
            (self.degradation, MaterialDegradation),
            (self.issue, VisualIssue),
            (self.disposition, VisualDisposition),
        )):
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        if _STAGE_ORDER[self.delivered_stage] <= _STAGE_ORDER[self.reference_stage]:
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        object.__setattr__(self, "reference_sha256", _sha(self.reference_sha256))
        object.__setattr__(self, "delivered_sha256", _sha(self.delivered_sha256))
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)


@dataclass(frozen=True)
class VisualQualificationReport:
    disposition: VisualDisposition
    comparisons: tuple[StageComparison, ...]
    earliest_material_loss: VisualStage | None
    actual_client_environment: str
    automated_human_gate: HumanPresentationQualityRecord

    @property
    def requires_human_review(self) -> bool:
        return True


def _validate_sample(sample: SampleArtifact, hybrid: RenderArtifactEvidence) -> None:
    if not isinstance(sample, SampleArtifact):
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    provenance = sample.provenance or {}
    if provenance.get("artifact_kind") != "HYBRID_PREVIEW":
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    if provenance.get("rendered_preview_sha256") != hybrid.artifact_sha256:
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)


def qualify_visual_pipeline(
    artifacts: Iterable[RenderArtifactEvidence],
    comparisons: Iterable[StageComparison],
    *,
    approved_sample: SampleArtifact,
) -> VisualQualificationReport:
    evidence = tuple(artifacts)
    checks = tuple(comparisons)
    if len(evidence) != 3 or any(not isinstance(item, RenderArtifactEvidence) for item in evidence):
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    by_stage = {item.stage: item for item in evidence}
    if set(by_stage) != set(VisualStage):
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    slide_ids = {item.slide_id for item in evidence}
    if len(slide_ids) != 1:
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    hybrid = by_stage[VisualStage.HYBRID_PREVIEW]
    actual = by_stage[VisualStage.ACTUAL_CLIENT_RENDER]
    _validate_sample(approved_sample, hybrid)
    if not checks or any(not isinstance(item, StageComparison) for item in checks):
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    required_edges = {
        (VisualStage.RAW_PLATE, VisualStage.HYBRID_PREVIEW),
        (VisualStage.HYBRID_PREVIEW, VisualStage.ACTUAL_CLIENT_RENDER),
    }
    if {(item.reference_stage, item.delivered_stage) for item in checks} != required_edges:
        raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    evidence_hashes = {(item.stage, item.artifact_sha256) for item in evidence}
    for check in checks:
        if check.slide_id not in slide_ids:
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        if (check.reference_stage, check.reference_sha256) not in evidence_hashes:
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
        if (check.delivered_stage, check.delivered_sha256) not in evidence_hashes:
            raise ValueError(ERROR_VISUAL_QUALIFICATION_INVALID)
    disposition = max(
        (item.disposition for item in checks),
        key=lambda item: _DISPOSITION_ORDER[item],
    )
    material = [
        item for item in checks
        if item.degradation in {MaterialDegradation.MATERIAL_DEGRADATION, MaterialDegradation.UNACCEPTABLE}
    ]
    earliest = min(
        (item.delivered_stage for item in material),
        key=lambda item: _STAGE_ORDER[item],
        default=None,
    )
    blocking = disposition is VisualDisposition.BLOCK
    automated_gate = automated_quality_assistance(
        actual.source_presentation_sha256,
        blocking=blocking,
        detail=(
            "Automated visual qualification found a blocking exact-artifact defect."
            if blocking
            else "Automated visual qualification completed; exact-artifact human acceptance is still required."
        ),
    )
    return VisualQualificationReport(
        disposition,
        checks,
        earliest,
        actual.environment,
        automated_gate,
    )


__all__ = [
    "ERROR_VISUAL_QUALIFICATION_INVALID",
    "MaterialDegradation",
    "RenderArtifactEvidence",
    "StageComparison",
    "VisualDisposition",
    "VisualIssue",
    "VisualObservation",
    "VisualQualificationReport",
    "VisualStage",
    "disposition_from_observation",
    "qualify_visual_pipeline",
]
