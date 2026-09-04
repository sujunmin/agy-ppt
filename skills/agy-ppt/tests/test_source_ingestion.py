#!/usr/bin/env python3
"""Phase 13.1/13.2 -- deterministic tests for source ingestion & locators.

Every test here is deterministic: no real Codex/Kiro process is launched, no
subscription quota is consumed, no network request is made, and no real
third-party or confidential document is used. All PDF fixtures are synthesised
byte-by-byte by ``tests/helpers/synthetic_pdf.py``, and all Markdown/text
fixtures are written inline.

These tests cover extraction only. They never assert that an extracted block is
semantically important, nor that it constitutes a Phase 12 source unit --
promoting a block to a semantic source unit is an AGY decision that this layer
deliberately cannot make.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

HELPERS_DIR = Path(__file__).resolve().parent / "helpers"
if str(HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(HELPERS_DIR))

from synthetic_pdf import (  # noqa: E402
    build_corrupt_pdf,
    build_text_pdf,
    build_textless_pdf,
)

import source_ingestion as si  # noqa: E402
from source_grounding import (  # noqa: E402
    SourceInventory,
    compute_source_digest,
    validate_locator,
)

PAGE_TEXTS = [
    "Synthetic Governance Overview",
    "Synthetic Risk Controls",
    "Synthetic Appendix",
]

MARKDOWN_FIXTURE = """# Overview

Intro paragraph.

## Architecture

Architecture text.

### Validation

Validation text.

# Testing

## Architecture

Different architecture section.

```text
# Fake Heading
```
"""

TEXT_FIXTURE = (
    "\u7b2c\u4e00\u6bb5\u5167\u5bb9\u3002\n"
    "Second line of paragraph one.\n"
    "\n"
    "\u7b2c\u4e8c\u6bb5\u5167\u5bb9\u3002\n"
    "\n"
    "\n"
    "Third paragraph here.\n"
)


class IngestionTestCase(unittest.TestCase):
    """Shared temporary workspace; every fixture is synthetic."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, name: str, data: bytes | str) -> Path:
        path = self.root / name
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_bytes(data)
        return path

    def pdf(self, name: str = "doc.pdf") -> Path:
        return self.write(name, build_text_pdf(PAGE_TEXTS))

    def markdown(self, name: str = "notes.md") -> Path:
        return self.write(name, MARKDOWN_FIXTURE)

    def text(self, name: str = "plain.txt") -> Path:
        return self.write(name, TEXT_FIXTURE)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------
class TestFormatDetection(IngestionTestCase):
    def test_pdf_detected(self) -> None:
        self.assertEqual(si.detect_source_format(self.pdf()), si.FORMAT_PDF)

    def test_markdown_detected(self) -> None:
        self.assertEqual(si.detect_source_format(self.markdown()), si.FORMAT_MARKDOWN)

    def test_text_detected(self) -> None:
        self.assertEqual(si.detect_source_format(self.text()), si.FORMAT_TEXT)

    def test_unsupported_binary_rejected(self) -> None:
        png = self.write("image.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        self.assertEqual(si.detect_source_format(png), si.FORMAT_UNSUPPORTED)
        with self.assertRaises(si.SourceFormatUnsupported) as ctx:
            si.ingest_source(png, "src_png")
        self.assertEqual(ctx.exception.error_code, si.ERROR_SOURCE_FORMAT_UNSUPPORTED)

    def test_pdf_signature_wins_over_extension(self) -> None:
        """A PDF named .txt is still routed to the PDF extractor."""
        mislabelled = self.write("actually.txt", build_text_pdf(PAGE_TEXTS))
        self.assertEqual(si.detect_source_format(mislabelled), si.FORMAT_PDF)

    def test_pdf_extension_without_signature_is_unsupported(self) -> None:
        fake = self.write("fake.pdf", b"this is not a pdf at all")
        self.assertEqual(si.detect_source_format(fake), si.FORMAT_UNSUPPORTED)

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(si.SourceFileNotFound) as ctx:
            si.detect_source_format(self.root / "absent.md")
        self.assertEqual(ctx.exception.error_code, si.ERROR_SOURCE_FILE_NOT_FOUND)

    def test_invalid_source_id_rejected(self) -> None:
        with self.assertRaises(si.SourceIngestionError):
            si.ingest_source(self.markdown(), "not-a-valid-id")


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
class TestPdfExtraction(IngestionTestCase):
    def test_multi_page_extraction(self) -> None:
        result = si.ingest_source(self.pdf(), "src_pdf")
        self.assertEqual(result.source_format, si.FORMAT_PDF)
        self.assertEqual(result.block_count, 3)
        self.assertEqual([b.block_type for b in result.blocks], [si.BLOCK_PAGE] * 3)
        for block, expected in zip(result.blocks, PAGE_TEXTS):
            self.assertIn(expected, block.text)

    def test_page_locators_are_one_based(self) -> None:
        """Page 1 text must land on locator page 1, with no off-by-one."""
        result = si.ingest_source(self.pdf(), "src_pdf")
        pages = [b.locator["start"] for b in result.blocks]
        self.assertEqual(pages, [1, 2, 3])
        for block in result.blocks:
            page = block.locator["start"]
            self.assertEqual(block.locator["end"], page)
            self.assertEqual(block.metadata["page"], page)
            # The text on page N must be the fixture text authored for page N.
            self.assertIn(PAGE_TEXTS[page - 1], block.text)
        self.assertEqual(min(pages), 1, "page numbering must start at 1, not 0")

    def test_deterministic_block_ids(self) -> None:
        result = si.ingest_source(self.pdf(), "src_pdf")
        for block in result.blocks:
            self.assertEqual(
                block.block_id,
                si.compute_block_id("src_pdf", block.locator, block.ordinal),
            )
            self.assertTrue(block.block_id.startswith("blk:src_pdf:"))
        self.assertEqual(
            len({b.block_id for b in result.blocks}), result.block_count
        )

    def test_repeated_ingestion_is_identical(self) -> None:
        path = self.pdf()
        first = si.ingest_source(path, "src_pdf").to_dict()
        second = si.ingest_source(path, "src_pdf").to_dict()
        self.assertEqual(first, second)

    def test_block_ordering_is_deterministic(self) -> None:
        result = si.ingest_source(self.pdf(), "src_pdf")
        ordinals = [b.ordinal for b in result.blocks]
        self.assertEqual(ordinals, sorted(ordinals))
        self.assertEqual(ordinals, list(range(1, result.block_count + 1)))

    def test_textless_pdf_fails_clearly(self) -> None:
        """A scanned/image-only PDF must fail, never succeed with empty text."""
        scan = self.write("scan.pdf", build_textless_pdf(2))
        self.assertEqual(si.detect_source_format(scan), si.FORMAT_PDF)
        with self.assertRaises(si.SourceTextUnavailable) as ctx:
            si.ingest_source(scan, "src_scan")
        self.assertEqual(ctx.exception.error_code, si.ERROR_SOURCE_TEXT_UNAVAILABLE)
        self.assertIn("OCR is not supported", str(ctx.exception))

    def test_corrupted_pdf_fails_as_extraction_failure(self) -> None:
        """Structurally broken is distinct from validly textless."""
        broken = self.write("broken.pdf", build_corrupt_pdf())
        with self.assertRaises(si.SourceExtractionFailed) as ctx:
            si.ingest_source(broken, "src_broken")
        self.assertEqual(ctx.exception.error_code, si.ERROR_SOURCE_EXTRACTION_FAILED)
        self.assertNotEqual(
            ctx.exception.error_code,
            si.ERROR_SOURCE_TEXT_UNAVAILABLE,
            "a corrupt PDF must not be reported as a valid textless PDF",
        )

    def test_no_ocr_dependency_is_imported(self) -> None:
        si.ingest_source(self.pdf(), "src_pdf")
        forbidden = {"pytesseract", "tesserocr", "easyocr", "paddleocr"}
        self.assertEqual(forbidden & set(sys.modules), set())


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
class TestMarkdownExtraction(IngestionTestCase):
    def blocks(self):
        return si.ingest_source(self.markdown(), "src_md").blocks

    def test_heading_hierarchy_extracted(self) -> None:
        paths = [b.locator["heading_path"] for b in self.blocks()]
        self.assertEqual(
            paths,
            [
                ["Overview"],
                ["Overview", "Architecture"],
                ["Overview", "Architecture", "Validation"],
                ["Testing"],
                ["Testing", "Architecture"],
            ],
        )
        levels = [b.metadata["heading_level"] for b in self.blocks()]
        self.assertEqual(levels, [1, 2, 3, 1, 2])

    def test_repeated_headings_do_not_collide(self) -> None:
        """Two 'Architecture' sections under different parents stay distinct."""
        arch = [
            b for b in self.blocks() if b.metadata["heading_text"] == "Architecture"
        ]
        self.assertEqual(len(arch), 2)
        self.assertNotEqual(arch[0].locator["heading_path"], arch[1].locator["heading_path"])
        self.assertNotEqual(arch[0].locator["start_line"], arch[1].locator["start_line"])
        self.assertNotEqual(arch[0].block_id, arch[1].block_id)
        self.assertNotEqual(arch[0].locator["label"], arch[1].locator["label"])

    def test_line_ranges_are_one_based_and_ordered(self) -> None:
        lines = MARKDOWN_FIXTURE.split("\n")
        for block in self.blocks():
            start = block.locator["start_line"]
            end = block.locator["end_line"]
            self.assertGreaterEqual(start, 1)
            self.assertGreaterEqual(end, start)
            heading_text = block.metadata["heading_text"]
            if heading_text:
                # start_line must point at the actual heading line.
                self.assertIn(heading_text, lines[start - 1])
                self.assertTrue(lines[start - 1].lstrip().startswith("#"))

    def test_fenced_code_fake_heading_ignored(self) -> None:
        headings = [b.metadata["heading_text"] for b in self.blocks()]
        self.assertNotIn("Fake Heading", headings)
        for block in self.blocks():
            self.assertNotIn("Fake Heading", block.locator["label"])
        # The fence content is still carried inside its enclosing section.
        last = self.blocks()[-1]
        self.assertIn("# Fake Heading", last.text)

    def test_deterministic_ids_and_repeatability(self) -> None:
        path = self.markdown()
        first = si.ingest_source(path, "src_md").to_dict()
        second = si.ingest_source(path, "src_md").to_dict()
        self.assertEqual(first, second)
        for block in self.blocks():
            self.assertEqual(
                block.block_id,
                si.compute_block_id("src_md", block.locator, block.ordinal),
            )

    def test_utf8_and_traditional_chinese_preserved(self) -> None:
        content = "# \u6e2c\u8a66\u6587\u4ef6\n\n\u7e41\u9ad4\u4e2d\u6587\u5167\u5bb9\u3002\n"
        path = self.write("zh.md", content)
        blocks = si.ingest_source(path, "src_zh").blocks
        self.assertEqual(blocks[0].metadata["heading_text"], "\u6e2c\u8a66\u6587\u4ef6")
        self.assertIn("\u7e41\u9ad4\u4e2d\u6587\u5167\u5bb9\u3002", blocks[0].text)

    def test_preamble_before_first_heading_is_kept(self) -> None:
        path = self.write("pre.md", "Leading note.\n\n# Real Heading\n\nBody.\n")
        blocks = si.ingest_source(path, "src_pre").blocks
        self.assertEqual(blocks[0].locator["heading_path"], [])
        self.assertIn("Leading note.", blocks[0].text)
        self.assertEqual(blocks[1].metadata["heading_text"], "Real Heading")

    def test_markdown_without_headings_yields_one_block(self) -> None:
        path = self.write("flat.md", "Just prose, no headings at all.\n")
        blocks = si.ingest_source(path, "src_flat").blocks
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].locator["heading_path"], [])

    def test_crlf_and_lf_produce_identical_blocks(self) -> None:
        lf = self.write("lf.md", MARKDOWN_FIXTURE)
        crlf = self.write("crlf.md", MARKDOWN_FIXTURE.replace("\n", "\r\n").encode("utf-8"))
        lf_blocks = [b.to_dict() for b in si.ingest_source(lf, "src_x").blocks]
        crlf_blocks = [b.to_dict() for b in si.ingest_source(crlf, "src_x").blocks]
        self.assertEqual(lf_blocks, crlf_blocks)
        # ...but the raw digests differ, because the bytes genuinely differ.
        self.assertNotEqual(
            si.ingest_source(lf, "src_x").source_digest,
            si.ingest_source(crlf, "src_x").source_digest,
        )


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------
class TestTextExtraction(IngestionTestCase):
    def test_deterministic_paragraph_extraction(self) -> None:
        result = si.ingest_source(self.text(), "src_txt")
        self.assertEqual(result.block_count, 3)
        self.assertEqual([b.block_type for b in result.blocks], [si.BLOCK_PARAGRAPH] * 3)
        repeat = si.ingest_source(self.text("again.txt"), "src_txt")
        self.assertEqual(
            [b.block_id for b in result.blocks], [b.block_id for b in repeat.blocks]
        )

    def test_line_locators_are_one_based(self) -> None:
        blocks = si.ingest_source(self.text(), "src_txt").blocks
        ranges = [(b.locator["start"], b.locator["end"]) for b in blocks]
        self.assertEqual(ranges, [(1, 2), (4, 4), (7, 7)])
        for block in blocks:
            self.assertEqual(block.locator["kind"], "line_range")
            self.assertGreaterEqual(block.locator["start"], 1)

    def test_traditional_chinese_preserved(self) -> None:
        blocks = si.ingest_source(self.text(), "src_txt").blocks
        self.assertIn("\u7b2c\u4e00\u6bb5\u5167\u5bb9\u3002", blocks[0].text)
        self.assertIn("\u7b2c\u4e8c\u6bb5\u5167\u5bb9\u3002", blocks[1].text)

    def test_utf8_bom_handled(self) -> None:
        raw = b"\xef\xbb\xbf" + "\u7e41\u9ad4\u4e2d\u6587 with BOM.\n".encode("utf-8")
        path = self.write("bom.txt", raw)
        blocks = si.ingest_source(path, "src_bom").blocks
        self.assertEqual(len(blocks), 1)
        self.assertFalse(blocks[0].text.startswith("\ufeff"))
        self.assertTrue(blocks[0].text.startswith("\u7e41\u9ad4\u4e2d\u6587"))

    def test_unsupported_encoding_fails_deterministically(self) -> None:
        """Invalid UTF-8 must fail loudly rather than produce mojibake."""
        path = self.write("latin1.txt", b"caf\xe9 latin-1 bytes\n")
        with self.assertRaises(si.SourceEncodingUnsupported) as ctx:
            si.ingest_source(path, "src_latin1")
        self.assertEqual(ctx.exception.error_code, si.ERROR_SOURCE_ENCODING_UNSUPPORTED)

    def test_trailing_newline_does_not_shift_ranges(self) -> None:
        without = self.write("a.txt", "One paragraph.")
        with_nl = self.write("b.txt", "One paragraph.\n")
        a = si.ingest_source(without, "src_nl").blocks
        b = si.ingest_source(with_nl, "src_nl").blocks
        self.assertEqual(a[0].locator, b[0].locator)
        self.assertEqual(a[0].block_id, b[0].block_id)

    def test_empty_text_source_fails(self) -> None:
        path = self.write("empty.txt", "\n\n\n")
        with self.assertRaises(si.SourceTextUnavailable):
            si.ingest_source(path, "src_empty")


# ---------------------------------------------------------------------------
# Phase 12 compatibility (Phase 13 is an upstream producer, Phase 12 is frozen)
# ---------------------------------------------------------------------------
class TestPhase12Compatibility(IngestionTestCase):
    def test_source_digest_matches_phase12_definition(self) -> None:
        path = self.pdf()
        result = si.ingest_source(path, "src_pdf")
        self.assertEqual(result.source_digest, compute_source_digest(path.read_bytes()))
        # ...and is accepted verbatim by the Phase 12 inventory contract.
        inventory = SourceInventory.initialize(self.root, "proj")
        inventory.add_source("src_pdf", "pdf", source_digest=result.source_digest)
        inventory.save()
        self.assertFalse(inventory.source_changed("src_pdf", result.source_digest))
        self.assertTrue(inventory.source_changed("src_pdf", "0" * 64))

    def _assert_locator_accepted(self, path: Path, source_id: str, kind: str) -> None:
        result = si.ingest_source(path, source_id)
        inventory = SourceInventory.initialize(self.root, "proj")
        inventory.add_source(source_id, result.source_format, source_digest=result.source_digest)
        for block in result.blocks:
            locator = si.phase12_locator(block)
            self.assertEqual(locator["kind"], kind)
            # Frozen Phase 12 validator must accept the shape unchanged.
            self.assertEqual(validate_locator(locator), [])
            unit = inventory.add_unit(source_id, "generic", locator, "MEDIUM")
            self.assertTrue(unit["unit_id"].startswith(f"su:{source_id}:"))
        inventory.save()
        self.assertEqual(len(inventory.data["units"]), result.block_count)

    def test_pdf_locator_maps_into_phase12(self) -> None:
        self._assert_locator_accepted(self.pdf(), "src_pdf", "page")

    def test_markdown_locator_maps_into_phase12(self) -> None:
        self._assert_locator_accepted(self.markdown(), "src_md", "section")

    def test_text_locator_maps_into_phase12(self) -> None:
        self._assert_locator_accepted(self.text(), "src_txt", "line_range")

    def test_no_absolute_path_leaks_into_handoff(self) -> None:
        """Logical source identity must never depend on where the file lives."""
        for name, builder in (
            ("doc.pdf", lambda p: p.write_bytes(build_text_pdf(PAGE_TEXTS))),
            ("notes.md", lambda p: p.write_text(MARKDOWN_FIXTURE, encoding="utf-8")),
            ("plain.txt", lambda p: p.write_text(TEXT_FIXTURE, encoding="utf-8")),
        ):
            with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
                p1, p2 = Path(d1) / name, Path(d2) / name
                builder(p1)
                builder(p2)
                r1 = si.ingest_source(p1, "src_same")
                r2 = si.ingest_source(p2, "src_same")
                self.assertEqual(r1.to_dict(), r2.to_dict(), name)
                serialized = json.dumps(r1.to_dict(), ensure_ascii=False)
                self.assertNotIn(d1, serialized)
                self.assertNotIn(d2, serialized)
                self.assertNotIn(str(Path.home()), serialized)

    def test_blocks_are_not_auto_promoted_to_source_units(self) -> None:
        """Extraction must not write any Phase 12 grounding artifact."""
        si.ingest_source(self.pdf(), "src_pdf")
        for artifact in (
            "source_inventory.json",
            "claim_traceability.json",
            "source_coverage.json",
            "source_grounded_qa.json",
        ):
            self.assertFalse((self.root / artifact).exists(), artifact)

    def test_extraction_result_carries_versions(self) -> None:
        result = si.ingest_source(self.markdown(), "src_md")
        self.assertEqual(result.schema_version, si.SCHEMA_VERSION)
        self.assertEqual(result.extractor_version, si.EXTRACTOR_VERSION)
        # Extractor version is independent of the release/tag version.
        self.assertNotIn("v", result.extractor_version)
        self.assertNotIn(".", result.extractor_version)


# ---------------------------------------------------------------------------
# CLI adapter
# ---------------------------------------------------------------------------
class TestCliAdapter(IngestionTestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        import contextlib
        import io

        import ingest_source as cli

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_cli_writes_output_and_summary(self) -> None:
        out_path = self.root / "out" / "result.json"
        code, stdout, _ = self.run_cli(
            [
                "--source",
                str(self.pdf()),
                "--source-id",
                "src_cli",
                "--output",
                str(out_path),
            ]
        )
        self.assertEqual(code, 0)
        summary = json.loads(stdout)
        self.assertEqual(summary["source_id"], "src_cli")
        self.assertEqual(summary["source_format"], "pdf")
        self.assertEqual(summary["block_count"], 3)
        self.assertEqual(len(summary["source_digest"]), 64)
        written = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(len(written["blocks"]), 3)

    def test_cli_stdout_json_when_no_output(self) -> None:
        code, stdout, _ = self.run_cli(
            ["--source", str(self.markdown()), "--source-id", "src_cli"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(stdout)["blocks"]), 5)

    def test_cli_detect_only(self) -> None:
        code, stdout, _ = self.run_cli(
            ["--source", str(self.text()), "--source-id", "src_cli", "--detect-only"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["source_format"], "text")

    def test_cli_error_is_concise_with_stable_code(self) -> None:
        scan = self.write("scan.pdf", build_textless_pdf(1))
        code, stdout, stderr = self.run_cli(
            ["--source", str(scan), "--source-id", "src_scan"]
        )
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith(si.ERROR_SOURCE_TEXT_UNAVAILABLE))
        self.assertNotIn("Traceback", stderr)

    def test_cli_unsupported_format_error(self) -> None:
        docx = self.write("deck.docx", b"PK\x03\x04 not really a docx")
        code, _, stderr = self.run_cli(
            ["--source", str(docx), "--source-id", "src_docx"]
        )
        self.assertEqual(code, 1)
        self.assertTrue(stderr.startswith(si.ERROR_SOURCE_FORMAT_UNSUPPORTED))


if __name__ == "__main__":
    unittest.main(verbosity=2)
