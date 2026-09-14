#!/usr/bin/env python3
"""Approval policy for interactive presentation generation.

AGY owns this workflow.  Generators are injected as narrow callbacks: they may
render one requested sample or the approved deck, but they never receive the
project state and cannot approve or skip a gate.

The module is additive to the frozen :mod:`project_state` contract.  It stores
revision fingerprints in the gate objects that the schema already permits so
that a resumed session can prove that an approval belongs to the current
outline and style.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from project_state import (
    PHASE_INTAKE,
    PHASE_OUTLINE,
    PHASE_SAMPLE,
    PHASE_SLIDE_GENERATION,
    PHASE_STYLE,
    ProjectState,
)

OUTLINE_PENDING_APPROVAL = "OUTLINE_PENDING_APPROVAL"
STYLE_PENDING_APPROVAL = "STYLE_PENDING_APPROVAL"
SAMPLE_PENDING_APPROVAL = "SAMPLE_PENDING_APPROVAL"
READY_FOR_FULL_GENERATION = "READY_FOR_FULL_GENERATION"

ERROR_APPROVAL_REQUIRED = "PRESENTATION_APPROVAL_REQUIRED"
ERROR_WORKFLOW_INVALID = "PRESENTATION_WORKFLOW_INVALID"

_COVER_ROLES = frozenset({"cover", "cover slide", "title", "title slide"})


class PresentationWorkflowError(Exception):
    """Deterministic orchestration error with a stable machine identity."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class SampleResult:
    """One real sample-render result awaiting user approval."""

    slide_number: int
    artifact_ref: str
    status: str = SAMPLE_PENDING_APPROVAL


@dataclass(frozen=True)
class FullGenerationResult:
    """Opaque result returned by the approved full-deck generation callback."""

    value: Any


def _canonical_copy(value: Any, label: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise PresentationWorkflowError(
            ERROR_WORKFLOW_INVALID, f"{label} must be deterministic JSON data"
        ) from exc


def _digest(value: Any, label: str) -> str:
    canonical = json.dumps(
        _canonical_copy(value, label),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class PresentationApprovalWorkflow:
    """Enforce outline, style, and one-sample approval before full generation."""

    def __init__(
        self,
        state: ProjectState,
        *,
        outline: Sequence[Mapping[str, Any]] | None = None,
        style: Mapping[str, Any] | None = None,
    ) -> None:
        self._state = state
        copied_outline = _canonical_copy(list(outline), "outline") if outline is not None else None
        copied_style = _canonical_copy(dict(style), "style") if style is not None else None
        self._outline: tuple[dict[str, Any], ...] | None = (
            tuple(copied_outline) if copied_outline is not None else None
        )
        self._style: dict[str, Any] | None = copied_style

    @property
    def status(self) -> str:
        outline = self._state.data["outline"]
        style = self._state.data["style"]
        sample = self._state.data["sample"]
        if not self._gate_matches(outline):
            return OUTLINE_PENDING_APPROVAL
        if not self._gate_matches(style):
            return STYLE_PENDING_APPROVAL
        if not self._sample_matches(sample, outline, style):
            return SAMPLE_PENDING_APPROVAL
        return READY_FOR_FULL_GENERATION

    def submit_outline(self, slides: Sequence[Mapping[str, Any]]) -> str:
        """Record a new outline and invalidate every dependent approval."""
        copied = _canonical_copy(list(slides), "outline")
        if not copied:
            raise PresentationWorkflowError(ERROR_WORKFLOW_INVALID, "outline must contain slides")
        numbers = [slide.get("number") for slide in copied if isinstance(slide, dict)]
        if len(numbers) != len(copied) or any(type(number) is not int or number < 1 for number in numbers):
            raise PresentationWorkflowError(
                ERROR_WORKFLOW_INVALID, "every outline slide needs a positive integer number"
            )
        if len(set(numbers)) != len(numbers):
            raise PresentationWorkflowError(ERROR_WORKFLOW_INVALID, "outline slide numbers must be unique")
        self._outline = tuple(copied)
        self._set_gate("outline", "pending", content_digest=_digest(copied, "outline"))
        self._set_gate("style", "pending")
        self._set_gate("sample", "pending")
        if self._state.phase == PHASE_INTAKE:
            self._state.set_phase(PHASE_OUTLINE, note="outline prepared for user approval")
        return self.status

    def approve_outline(self) -> str:
        outline = self._require_current_outline()
        self._set_gate(
            "outline",
            "approved",
            content_digest=outline["content_digest"],
            approved_digest=outline["content_digest"],
        )
        if self._state.phase == PHASE_OUTLINE:
            self._state.set_phase(PHASE_STYLE, note="outline approved by user")
        return self.status

    def reject_outline(self) -> str:
        outline = self._state.data["outline"]
        self._set_gate("outline", "rejected", content_digest=outline.get("content_digest"))
        self._set_gate("style", "pending")
        self._set_gate("sample", "pending")
        return self.status

    def submit_style(self, style: Mapping[str, Any]) -> str:
        self._require_outline_approved()
        copied = _canonical_copy(dict(style), "style")
        if not copied:
            raise PresentationWorkflowError(ERROR_WORKFLOW_INVALID, "style must not be empty")
        self._style = copied
        self._set_gate("style", "pending", content_digest=_digest(copied, "style"))
        self._set_gate("sample", "pending")
        return self.status

    def approve_style(self) -> str:
        self._require_outline_approved()
        style = self._state.data["style"]
        if not style.get("content_digest"):
            raise PresentationWorkflowError(ERROR_APPROVAL_REQUIRED, "a style must be submitted first")
        self._set_gate(
            "style",
            "approved",
            content_digest=style["content_digest"],
            approved_digest=style["content_digest"],
        )
        self._set_gate("sample", "pending")
        if self._state.phase == PHASE_STYLE:
            self._state.set_phase(PHASE_SAMPLE, note="style approved by user")
        return self.status

    def reject_style(self) -> str:
        self._require_outline_approved()
        style = self._state.data["style"]
        self._set_gate("style", "rejected", content_digest=style.get("content_digest"))
        self._set_gate("sample", "pending")
        return self.status

    def generate_sample(
        self,
        generator: Callable[[Mapping[str, Any]], str | Path],
        *,
        slide_number: int | None = None,
    ) -> SampleResult:
        """Render exactly one representative slide through the supplied real path."""
        self._require_outline_approved()
        self._require_style_approved()
        outline = self._require_loaded_outline()
        selected = self._select_sample(outline, slide_number)
        # The callback receives one defensive copy, never the workflow state or full deck.
        generated = generator(_canonical_copy(selected, "sample slide"))
        if not isinstance(generated, (str, Path)):
            raise PresentationWorkflowError(
                ERROR_WORKFLOW_INVALID, "sample generator returned an invalid artifact reference"
            )
        artifact = str(generated).strip()
        if not artifact:
            raise PresentationWorkflowError(ERROR_WORKFLOW_INVALID, "sample generator returned no artifact")
        outline_gate = self._state.data["outline"]
        style_gate = self._state.data["style"]
        self._set_gate(
            "sample",
            "pending",
            slide_number=selected["number"],
            artifact_ref=artifact,
            outline_digest=outline_gate["approved_digest"],
            style_digest=style_gate["approved_digest"],
        )
        return SampleResult(slide_number=selected["number"], artifact_ref=artifact)

    def approve_sample(self) -> str:
        self._require_outline_approved()
        self._require_style_approved()
        sample = self._state.data["sample"]
        outline = self._state.data["outline"]
        style = self._state.data["style"]
        if not sample.get("artifact_ref") or not self._sample_dependencies_match(sample, outline, style):
            raise PresentationWorkflowError(
                ERROR_APPROVAL_REQUIRED, "a sample for the current outline and style must be generated first"
            )
        self._set_gate("sample", "approved", **{key: value for key, value in sample.items() if key != "status"})
        if self._state.phase == PHASE_SAMPLE:
            self._state.set_phase(PHASE_SLIDE_GENERATION, note="sample approved by user")
        return self.status

    def reject_sample(self) -> str:
        sample = self._state.data["sample"]
        self._set_gate("sample", "rejected", **{key: value for key, value in sample.items() if key != "status"})
        return self.status

    def generate_full(self, generator: Callable[[Sequence[Mapping[str, Any]], Mapping[str, Any], str], Any]) -> FullGenerationResult:
        """Invoke full-deck generation only when all current approvals are valid."""
        if self.status != READY_FOR_FULL_GENERATION:
            raise PresentationWorkflowError(
                ERROR_APPROVAL_REQUIRED,
                "outline, style, and current sample must all be approved before full generation",
            )
        outline = self._require_loaded_outline()
        if self._style is None:
            raise PresentationWorkflowError(ERROR_WORKFLOW_INVALID, "current style data is not loaded")
        artifact = self._state.data["sample"]["artifact_ref"]
        value = generator(
            tuple(_canonical_copy(list(outline), "outline")),
            _canonical_copy(self._style, "style"),
            artifact,
        )
        return FullGenerationResult(value=value)

    def _set_gate(self, gate: str, status: str, **metadata: Any) -> None:
        self._state.set_gate(gate, status)
        self._state.data[gate] = {"status": status, **{k: v for k, v in metadata.items() if v is not None}}

    @staticmethod
    def _gate_matches(gate: Mapping[str, Any]) -> bool:
        return bool(
            gate.get("status") == "approved"
            and gate.get("content_digest")
            and gate.get("approved_digest") == gate.get("content_digest")
        )

    def _require_current_outline(self) -> Mapping[str, Any]:
        self._require_loaded_outline()
        outline = self._state.data["outline"]
        if not outline.get("content_digest"):
            raise PresentationWorkflowError(ERROR_APPROVAL_REQUIRED, "an outline must be submitted first")
        return outline

    def _require_outline_approved(self) -> None:
        if not self._gate_matches(self._state.data["outline"]):
            raise PresentationWorkflowError(ERROR_APPROVAL_REQUIRED, "current outline requires approval")

    def _require_style_approved(self) -> None:
        if not self._gate_matches(self._state.data["style"]):
            raise PresentationWorkflowError(ERROR_APPROVAL_REQUIRED, "current style requires approval")

    def _require_loaded_outline(self) -> tuple[dict[str, Any], ...]:
        if self._outline is None:
            raise PresentationWorkflowError(ERROR_WORKFLOW_INVALID, "current outline data is not loaded")
        expected = self._state.data["outline"].get("content_digest")
        if expected != _digest(list(self._outline), "outline"):
            raise PresentationWorkflowError(ERROR_WORKFLOW_INVALID, "loaded outline does not match project state")
        return self._outline

    @classmethod
    def _sample_dependencies_match(
        cls,
        sample: Mapping[str, Any],
        outline: Mapping[str, Any],
        style: Mapping[str, Any],
    ) -> bool:
        return bool(
            sample.get("outline_digest") == outline.get("approved_digest")
            and sample.get("style_digest") == style.get("approved_digest")
        )

    @classmethod
    def _sample_matches(
        cls,
        sample: Mapping[str, Any],
        outline: Mapping[str, Any],
        style: Mapping[str, Any],
    ) -> bool:
        return bool(
            sample.get("status") == "approved"
            and sample.get("artifact_ref")
            and cls._sample_dependencies_match(sample, outline, style)
        )

    @staticmethod
    def _select_sample(
        outline: Sequence[Mapping[str, Any]], slide_number: int | None
    ) -> Mapping[str, Any]:
        if slide_number is not None:
            if type(slide_number) is not int or slide_number < 1:
                raise PresentationWorkflowError(ERROR_WORKFLOW_INVALID, "sample slide number is invalid")
            for slide in outline:
                if slide.get("number") == slide_number:
                    return slide
            raise PresentationWorkflowError(ERROR_WORKFLOW_INVALID, "sample slide is not in the outline")
        for slide in outline:
            role = str(slide.get("role", "")).strip().lower()
            if role not in _COVER_ROLES:
                return slide
        return outline[0]


__all__ = [
    "ERROR_APPROVAL_REQUIRED",
    "ERROR_WORKFLOW_INVALID",
    "OUTLINE_PENDING_APPROVAL",
    "STYLE_PENDING_APPROVAL",
    "SAMPLE_PENDING_APPROVAL",
    "READY_FOR_FULL_GENERATION",
    "FullGenerationResult",
    "PresentationApprovalWorkflow",
    "PresentationWorkflowError",
    "SampleResult",
]
