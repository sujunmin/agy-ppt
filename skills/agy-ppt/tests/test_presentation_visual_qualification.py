#!/usr/bin/env python3
"""Q4 exact-artifact visual qualification and escalation tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from human_presentation_quality import HumanPresentationQualityState, ReviewAuthority  # noqa: E402
from presentation_visual_qualification import (  # noqa: E402
    MaterialDegradation,
    RenderArtifactEvidence,
    StageComparison,
    VisualDisposition,
    VisualIssue,
    VisualObservation,
    VisualStage,
    disposition_from_observation,
    qualify_visual_pipeline,
)
from presentation_workflow import SampleArtifact  # noqa: E402


PLATE = "1" * 64
HYBRID = "2" * 64
ACTUAL = "3" * 64
PPTX = "4" * 64


def artifacts():
    return (
        RenderArtifactEvidence("slide_02", VisualStage.RAW_PLATE, PLATE, PPTX, "agy-ppt plate renderer"),
        RenderArtifactEvidence("slide_02", VisualStage.HYBRID_PREVIEW, HYBRID, PPTX, "agy-ppt hybrid preview"),
        RenderArtifactEvidence("slide_02", VisualStage.ACTUAL_CLIENT_RENDER, ACTUAL, PPTX, "Microsoft PowerPoint for macOS", True),
    )


def sample(sha=HYBRID):
    return SampleArtifact("sample.pptx", {
        "artifact_kind": "HYBRID_PREVIEW",
        "rendered_preview_sha256": sha,
        "hybrid_manifest_sha256": "5" * 64,
    })


def comparison(reference, delivered, degradation, issue, disposition, detail="fixture comparison"):
    hashes = {VisualStage.RAW_PLATE: PLATE, VisualStage.HYBRID_PREVIEW: HYBRID, VisualStage.ACTUAL_CLIENT_RENDER: ACTUAL}
    return StageComparison(
        "slide_02", reference, delivered, hashes[reference], hashes[delivered],
        degradation, issue, disposition, detail,
    )


def good_comparisons():
    return (
        comparison(VisualStage.RAW_PLATE, VisualStage.HYBRID_PREVIEW, MaterialDegradation.NO_MATERIAL_DEGRADATION, VisualIssue.OTHER, VisualDisposition.ACCEPT),
        comparison(VisualStage.HYBRID_PREVIEW, VisualStage.ACTUAL_CLIENT_RENDER, MaterialDegradation.MINOR_DRIFT, VisualIssue.REFLOW, VisualDisposition.WARNING),
    )


class PresentationVisualQualificationTests(unittest.TestCase):
    def test_semantic_number_change_blocks(self):
        observation = VisualObservation(VisualIssue.OTHER, semantic_content_changed=True)
        self.assertEqual(disposition_from_observation(observation), VisualDisposition.BLOCK)

    def test_clipped_core_title_blocks(self):
        observation = VisualObservation(VisualIssue.OVERFLOW, core_content_obscured=True)
        self.assertEqual(disposition_from_observation(observation), VisualDisposition.BLOCK)

    def test_subject_losing_crop_requires_repair(self):
        observation = VisualObservation(VisualIssue.CROP, repairable_degradation=True)
        self.assertEqual(disposition_from_observation(observation), VisualDisposition.REPAIR)

    def test_harmless_wrap_and_small_shift_are_accepted(self):
        for issue in (VisualIssue.REFLOW, VisualIssue.POSITION, VisualIssue.COLOR):
            with self.subTest(issue=issue):
                observation = VisualObservation(issue, bounded_harmless_drift=True)
                self.assertEqual(disposition_from_observation(observation), VisualDisposition.ACCEPT)

    def test_approved_hierarchy_floor_violation_blocks(self):
        observation = VisualObservation(VisualIssue.HIERARCHY, approved_quality_floor_violated=True)
        self.assertEqual(disposition_from_observation(observation), VisualDisposition.BLOCK)

    def test_default_chart_degradation_requires_repair(self):
        observation = VisualObservation(VisualIssue.CHART, repairable_degradation=True)
        self.assertEqual(disposition_from_observation(observation), VisualDisposition.REPAIR)

    def test_core_z_order_overlap_blocks(self):
        observation = VisualObservation(VisualIssue.Z_ORDER, core_content_obscured=True)
        self.assertEqual(disposition_from_observation(observation), VisualDisposition.BLOCK)

    def test_no_material_degradation_still_requires_human_review(self):
        report = qualify_visual_pipeline(artifacts(), good_comparisons(), approved_sample=sample())
        self.assertEqual(report.disposition, VisualDisposition.WARNING)
        self.assertIsNone(report.earliest_material_loss)
        self.assertTrue(report.requires_human_review)
        self.assertEqual(report.automated_human_gate.state, HumanPresentationQualityState.REVIEW_REQUIRED)
        self.assertEqual(report.automated_human_gate.authority, ReviewAuthority.AUTOMATED_ASSISTANCE)

    def test_hybrid_reconstruction_loss_is_localized(self):
        report = qualify_visual_pipeline(artifacts(), (
            comparison(VisualStage.RAW_PLATE, VisualStage.HYBRID_PREVIEW, MaterialDegradation.MATERIAL_DEGRADATION, VisualIssue.HIERARCHY, VisualDisposition.REPAIR),
            comparison(VisualStage.HYBRID_PREVIEW, VisualStage.ACTUAL_CLIENT_RENDER, MaterialDegradation.NO_MATERIAL_DEGRADATION, VisualIssue.OTHER, VisualDisposition.ACCEPT),
        ), approved_sample=sample())
        self.assertEqual(report.earliest_material_loss, VisualStage.HYBRID_PREVIEW)
        self.assertEqual(report.disposition, VisualDisposition.REPAIR)

    def test_actual_client_loss_is_localized(self):
        report = qualify_visual_pipeline(artifacts(), (
            comparison(VisualStage.RAW_PLATE, VisualStage.HYBRID_PREVIEW, MaterialDegradation.NO_MATERIAL_DEGRADATION, VisualIssue.OTHER, VisualDisposition.ACCEPT),
            comparison(VisualStage.HYBRID_PREVIEW, VisualStage.ACTUAL_CLIENT_RENDER, MaterialDegradation.UNACCEPTABLE, VisualIssue.OVERFLOW, VisualDisposition.BLOCK),
        ), approved_sample=sample())
        self.assertEqual(report.earliest_material_loss, VisualStage.ACTUAL_CLIENT_RENDER)
        self.assertEqual(report.automated_human_gate.state, HumanPresentationQualityState.BLOCK)

    def test_sample_must_be_exact_hybrid_preview(self):
        with self.assertRaises(ValueError):
            qualify_visual_pipeline(artifacts(), good_comparisons(), approved_sample=sample("9" * 64))

    def test_raw_plate_cannot_masquerade_as_sample(self):
        bad = SampleArtifact("plate.png", {"artifact_kind": "RAW_PLATE", "rendered_preview_sha256": HYBRID})
        with self.assertRaises(ValueError):
            qualify_visual_pipeline(artifacts(), good_comparisons(), approved_sample=bad)

    def test_actual_client_evidence_cannot_be_claimed_by_proxy(self):
        with self.assertRaises(ValueError):
            RenderArtifactEvidence("slide_02", VisualStage.ACTUAL_CLIENT_RENDER, ACTUAL, PPTX, "structural proxy", False)

    def test_comparison_hash_must_match_recorded_artifact(self):
        bad = StageComparison(
            "slide_02", VisualStage.RAW_PLATE, VisualStage.HYBRID_PREVIEW,
            "9" * 64, HYBRID, MaterialDegradation.MINOR_DRIFT,
            VisualIssue.COLOR, VisualDisposition.WARNING, "wrong reference",
        )
        with self.assertRaises(ValueError):
            qualify_visual_pipeline(artifacts(), (bad, good_comparisons()[1]), approved_sample=sample())

    def test_cross_slide_comparison_fails_closed(self):
        bad = comparison(
            VisualStage.RAW_PLATE, VisualStage.HYBRID_PREVIEW,
            MaterialDegradation.MINOR_DRIFT, VisualIssue.POSITION, VisualDisposition.WARNING,
        )
        object.__setattr__(bad, "slide_id", "slide_03")
        with self.assertRaises(ValueError):
            qualify_visual_pipeline(artifacts(), (bad, good_comparisons()[1]), approved_sample=sample())

    def test_report_contains_no_beauty_score(self):
        report = qualify_visual_pipeline(artifacts(), good_comparisons(), approved_sample=sample())
        self.assertFalse(hasattr(report, "score"))
        self.assertFalse(hasattr(report, "percentage"))

    def test_contradictory_harmless_and_blocking_observation_fails(self):
        with self.assertRaises(ValueError):
            VisualObservation(
                VisualIssue.HIERARCHY,
                approved_quality_floor_violated=True,
                bounded_harmless_drift=True,
            )

    def test_both_stage_comparisons_are_required(self):
        with self.assertRaises(ValueError):
            qualify_visual_pipeline(artifacts(), (good_comparisons()[0],), approved_sample=sample())


if __name__ == "__main__":
    unittest.main()
