#!/usr/bin/env python3
"""Approval-driven presentation workflow tests (no real generation)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from presentation_workflow import (  # noqa: E402
    ERROR_APPROVAL_REQUIRED,
    OUTLINE_PENDING_APPROVAL,
    READY_FOR_FULL_GENERATION,
    SAMPLE_PENDING_APPROVAL,
    STYLE_PENDING_APPROVAL,
    PresentationApprovalWorkflow,
    PresentationWorkflowError,
)
from project_state import ProjectState  # noqa: E402


OUTLINE = (
    {"number": 1, "title": "Cover", "role": "cover", "purpose": "Open"},
    {"number": 2, "title": "Problem", "role": "content", "purpose": "Explain"},
    {"number": 3, "title": "Decision", "role": "summary", "purpose": "Close"},
)
STYLE = {"direction": "editorial", "palette": ["#112233", "#ffffff"], "density": "medium"}


class WorkflowCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.state = ProjectState.initialize(self.temp.name, "approval-demo")
        self.workflow = PresentationApprovalWorkflow(self.state)
        self.sample_calls: list[int] = []
        self.full_calls = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    def render_sample(self, slide):
        self.sample_calls.append(slide["number"])
        return f"origin_image/slide_{slide['number']:02d}.png"

    def render_full(self, slides, style, sample_ref):
        self.full_calls += 1
        return {"slides": len(slides), "style": style["direction"], "sample": sample_ref}

    def approved_to_sample(self) -> None:
        self.workflow.submit_outline(OUTLINE)
        self.workflow.approve_outline()
        self.workflow.submit_style(STYLE)
        self.workflow.approve_style()

    def approved_all(self) -> None:
        self.approved_to_sample()
        self.workflow.generate_sample(self.render_sample)
        self.workflow.approve_sample()

    def assert_blocked_full(self) -> None:
        with self.assertRaises(PresentationWorkflowError) as caught:
            self.workflow.generate_full(self.render_full)
        self.assertEqual(caught.exception.error_code, ERROR_APPROVAL_REQUIRED)
        self.assertEqual(self.full_calls, 0)


class StageTests(WorkflowCase):
    def test_fresh_request_stops_at_outline_approval(self):
        self.assertEqual(self.workflow.submit_outline(OUTLINE), OUTLINE_PENDING_APPROVAL)
        self.assertEqual(self.sample_calls, [])
        self.assert_blocked_full()

    def test_outline_approval_stops_at_style_approval(self):
        self.workflow.submit_outline(OUTLINE)
        self.assertEqual(self.workflow.approve_outline(), STYLE_PENDING_APPROVAL)
        self.assertEqual(self.sample_calls, [])
        self.assert_blocked_full()

    def test_style_approval_generates_no_deck_and_one_sample_when_requested(self):
        self.approved_to_sample()
        self.assertEqual(self.workflow.status, SAMPLE_PENDING_APPROVAL)
        result = self.workflow.generate_sample(self.render_sample)
        self.assertEqual(result.slide_number, 2)
        self.assertEqual(self.sample_calls, [2])
        self.assert_blocked_full()

    def test_sample_approval_is_the_full_generation_gate(self):
        self.approved_all()
        self.assertEqual(self.workflow.status, READY_FOR_FULL_GENERATION)
        result = self.workflow.generate_full(self.render_full)
        self.assertEqual(self.full_calls, 1)
        self.assertEqual(result.value["slides"], 3)

    def test_explicit_sample_selection_is_honored(self):
        self.approved_to_sample()
        result = self.workflow.generate_sample(self.render_sample, slide_number=3)
        self.assertEqual(result.slide_number, 3)
        self.assertEqual(self.sample_calls, [3])


class RejectionAndInvalidationTests(WorkflowCase):
    def test_outline_rejection_blocks_every_later_stage(self):
        self.workflow.submit_outline(OUTLINE)
        self.workflow.reject_outline()
        self.assertEqual(self.workflow.status, OUTLINE_PENDING_APPROVAL)
        self.assert_blocked_full()

    def test_outline_revision_invalidates_style_and_sample(self):
        self.approved_all()
        revised = (*OUTLINE, {"number": 4, "title": "Appendix", "role": "content"})
        self.workflow.submit_outline(revised)
        self.assertEqual(self.workflow.status, OUTLINE_PENDING_APPROVAL)
        self.assertEqual(self.state.data["style"]["status"], "pending")
        self.assertEqual(self.state.data["sample"]["status"], "pending")
        self.assert_blocked_full()

    def test_style_rejection_blocks_sample_and_full_generation(self):
        self.approved_to_sample()
        self.workflow.reject_style()
        self.assertEqual(self.workflow.status, STYLE_PENDING_APPROVAL)
        self.assert_blocked_full()

    def test_style_revision_invalidates_approved_sample(self):
        self.approved_all()
        self.workflow.submit_style({**STYLE, "density": "high"})
        self.assertEqual(self.workflow.status, STYLE_PENDING_APPROVAL)
        self.assertEqual(self.state.data["sample"]["status"], "pending")
        self.assert_blocked_full()

    def test_sample_rejection_and_revision_each_remain_sample_pending(self):
        self.approved_to_sample()
        self.workflow.generate_sample(self.render_sample)
        self.workflow.reject_sample()
        self.assertEqual(self.workflow.status, SAMPLE_PENDING_APPROVAL)
        self.workflow.generate_sample(self.render_sample)
        self.assertEqual(self.sample_calls, [2, 2])
        self.assertEqual(self.workflow.status, SAMPLE_PENDING_APPROVAL)
        self.assert_blocked_full()


class BoundaryAndResumeTests(WorkflowCase):
    def test_worker_receives_one_slide_and_cannot_mutate_outline(self):
        self.approved_to_sample()

        def mutating_worker(slide):
            slide["title"] = "worker rewrite"
            self.sample_calls.append(slide["number"])
            return "origin_image/sample.png"

        self.workflow.generate_sample(mutating_worker)
        self.assertEqual(self.sample_calls, [2])
        self.workflow.generate_sample(self.render_sample)
        self.assertEqual(self.sample_calls, [2, 2])

    def test_failed_sample_does_not_approve_or_generate_full(self):
        self.approved_to_sample()

        def failed(_slide):
            raise RuntimeError("renderer unavailable")

        with self.assertRaises(RuntimeError):
            self.workflow.generate_sample(failed)
        self.assertEqual(self.workflow.status, SAMPLE_PENDING_APPROVAL)
        self.assert_blocked_full()

    def test_resume_rejects_stale_approval_for_different_outline(self):
        self.approved_all()
        self.state.data["outline"]["content_digest"] = "0" * 64
        resumed = PresentationApprovalWorkflow(self.state, outline=OUTLINE, style=STYLE)
        self.assertEqual(resumed.status, OUTLINE_PENDING_APPROVAL)

    def test_resume_reuses_only_matching_current_approvals(self):
        self.approved_all()
        resumed = PresentationApprovalWorkflow(self.state, outline=OUTLINE, style=STYLE)
        self.assertEqual(resumed.status, READY_FOR_FULL_GENERATION)
        result = resumed.generate_full(self.render_full)
        self.assertEqual(result.value["slides"], 3)

    def test_full_generator_cannot_mutate_canonical_inputs(self):
        self.approved_all()

        def mutating_full(slides, style, _sample):
            slides[0]["title"] = "changed"
            style["direction"] = "changed"
            return "deck.pptx"

        self.workflow.generate_full(mutating_full)
        second = self.workflow.generate_full(self.render_full)
        self.assertEqual(second.value["style"], "editorial")


if __name__ == "__main__":
    unittest.main()
