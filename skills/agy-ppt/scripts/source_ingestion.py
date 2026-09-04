#!/usr/bin/env python3
"""Deterministic source ingestion & locator extraction (Phase 13.1 + 13.2).

This module turns a **local** source file into normalized, deterministically
identified extraction *blocks* with source-format-native *locators*. It is the
upstream producer for the Phase 12 grounding system:

    local source
      -> format detection
      -> deterministic extractor
      -> normalized extracted blocks + locators   <-- this module
      -> AGY semantic segmentation
      -> Phase 12 source_inventory.json
      -> Phase 12 grounding workflow

Hard boundary, and the reason this lives outside ``source_grounding.py``:

    extraction != semantic understanding

This module decides only what a document mechanically contains: which page a
run of text sits on, which Markdown heading encloses it, which line range a
paragraph spans. It never decides what is important, what a claim means,
whether a source supports a claim, what belongs on a slide, or how the source
should be semantically segmented. Those are AGY decisions, and an extracted
block is therefore **not** a Phase 12 semantic source unit.

Scope of Phase 13.2: PDF with an extractable text layer, Markdown, and plain
text, all read from the local filesystem. There is no OCR, no network
acquisition, and no DOCX/HTML support -- each of those fails deterministically
rather than silently degrading.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
import sys  # noqa: E402

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# The one canonical source-fingerprint definition lives in Phase 12; Phase 13
# delegates to it instead of inventing a second, incompatible digest meaning.
from source_grounding import compute_source_digest  # noqa: E402

# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------
#: Shape of the extraction result document.
SCHEMA_VERSION = "1"

#: Version of the *extraction behaviour*. Deliberately independent of the
#: release version and of Git tags: if extraction rules ever change, persisted
#: results stay identifiable. Bump this when block/locator output changes.
EXTRACTOR_VERSION = "1"

# ---------------------------------------------------------------------------
# Formats
# ---------------------------------------------------------------------------
FORMAT_PDF = "pdf"
FORMAT_MARKDOWN = "markdown"
FORMAT_TEXT = "text"
FORMAT_UNSUPPORTED = "unsupported"

SUPPORTED_FORMATS = (FORMAT_PDF, FORMAT_MARKDOWN, FORMAT_TEXT)

MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdown")
TEXT_SUFFIXES = (".txt", ".text")
PDF_SUFFIXES = (".pdf",)

#: Every PDF must start with this signature; extension alone is never trusted.
PDF_SIGNATURE = b"%PDF-"

# ---------------------------------------------------------------------------
# Block types
# ---------------------------------------------------------------------------
BLOCK_PAGE = "page"
BLOCK_MARKDOWN_SECTION = "markdown_section"
BLOCK_PARAGRAPH = "paragraph"

# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------
# Deliberately disjoint from the Phase 12 grounding codes and the image-worker
# codes: an ingestion problem must never be recorded as a traceability,
# coverage or image-generation failure.
ERROR_SOURCE_FORMAT_UNSUPPORTED = "SOURCE_FORMAT_UNSUPPORTED"
ERROR_SOURCE_FILE_NOT_FOUND = "SOURCE_FILE_NOT_FOUND"
ERROR_SOURCE_READ_FAILED = "SOURCE_READ_FAILED"
ERROR_SOURCE_ENCODING_UNSUPPORTED = "SOURCE_ENCODING_UNSUPPORTED"
ERROR_SOURCE_TEXT_UNAVAILABLE = "SOURCE_TEXT_UNAVAILABLE"
ERROR_SOURCE_EXTRACTION_FAILED = "SOURCE_EXTRACTION_FAILED"

_SOURCE_ID_RE = re.compile(r"^src_[A-Za-z0-9._-]+$")


class SourceIngestionError(Exception):
    """Base error carrying a stable error_code, matching project_state.py."""

    error_code = ERROR_SOURCE_EXTRACTION_FAILED

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code


class SourceFormatUnsupported(SourceIngestionError):
    error_code = ERROR_SOURCE_FORMAT_UNSUPPORTED


class SourceFileNotFound(SourceIngestionError):
    error_code = ERROR_SOURCE_FILE_NOT_FOUND


class SourceReadFailed(SourceIngestionError):
    error_code = ERROR_SOURCE_READ_FAILED


class SourceEncodingUnsupported(SourceIngestionError):
    error_code = ERROR_SOURCE_ENCODING_UNSUPPORTED


class SourceTextUnavailable(SourceIngestionError):
    error_code = ERROR_SOURCE_TEXT_UNAVAILABLE


class SourceExtractionFailed(SourceIngestionError):
    error_code = ERROR_SOURCE_EXTRACTION_FAILED


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
def compute_block_id(source_id: str, locator: dict[str, Any], ordinal: int) -> str:
    """Deterministic, resume-safe, source-local block id.

    Derived from ``(source_id, canonical locator, ordinal)`` only. It never
    depends on an absolute filesystem path, a temporary directory, a process
    id, a timestamp, or a bare random UUID, so re-ingesting identical bytes
    with the same extractor version always reproduces the same id.
    """
    if not _SOURCE_ID_RE.match(source_id or ""):
        raise SourceIngestionError(
            f"invalid source_id: {source_id!r} (expected ^src_[A-Za-z0-9._-]+$)"
        )
    canonical = json.dumps(locator, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(
        f"{source_id}\n{canonical}\n{ordinal}".encode("utf-8")
    ).hexdigest()[:12]
    return f"blk:{source_id}:{digest}"


# ---------------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExtractedBlock:
    """One mechanically extracted run of text plus where it came from."""

    block_id: str
    block_type: str
    text: str
    locator: dict[str, Any]
    ordinal: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "block_type": self.block_type,
            "text": self.text,
            "locator": dict(self.locator),
            "ordinal": self.ordinal,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ExtractionResult:
    """Normalized extraction result handed to AGY for semantic segmentation."""

    schema_version: str
    extractor_version: str
    source_id: str
    source_format: str
    source_digest: str
    blocks: tuple[ExtractedBlock, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "extractor_version": self.extractor_version,
            "source_id": self.source_id,
            "source_format": self.source_format,
            "source_digest": self.source_digest,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @property
    def block_count(self) -> int:
        return len(self.blocks)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------
def detect_source_format(path: str | Path) -> str:
    """The single deterministic format authority for Phase 13.

    Resolution order:

    1. If the file begins with the ``%PDF-`` signature it is treated as PDF,
       whatever the extension says. The signature wins so that a mislabelled
       or extension-less PDF is still routed to the PDF extractor.
    2. Otherwise the extension selects Markdown or plain text, since a text
       file has no signature to validate against.
    3. Anything else -- including a file merely *named* ``.pdf`` without a PDF
       signature -- is ``unsupported``.
    """
    p = Path(os.path.expanduser(str(path)))
    if not p.is_file():
        raise SourceFileNotFound(f"source file not found: {p.name}")
    try:
        with p.open("rb") as fh:
            head = fh.read(len(PDF_SIGNATURE))
    except OSError as exc:
        raise SourceReadFailed(f"could not read source file: {exc}")

    if head == PDF_SIGNATURE:
        return FORMAT_PDF

    suffix = p.suffix.lower()
    if suffix in MARKDOWN_SUFFIXES:
        return FORMAT_MARKDOWN
    if suffix in TEXT_SUFFIXES:
        return FORMAT_TEXT
    return FORMAT_UNSUPPORTED


# ---------------------------------------------------------------------------
# Text decoding
# ---------------------------------------------------------------------------
def _decode_text(raw: bytes) -> str:
    """Decode UTF-8 (with or without BOM) and normalize line endings.

    ``utf-8-sig`` transparently strips a leading BOM and is otherwise plain
    UTF-8. CRLF and lone CR are normalized to LF so that line numbering is
    identical across platforms. This normalization applies only to the
    *extracted text*: the Phase 12 source digest is always computed over the
    raw, unnormalized bytes.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceEncodingUnsupported(
            f"source is not valid UTF-8 (or UTF-8 with BOM): {exc.reason}"
        )
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def extract_pdf(raw: bytes, source_id: str) -> list[ExtractedBlock]:
    """Page-level extraction from a PDF that has a real text layer.

    Granularity is deliberately page-level: it is the one division a PDF
    reliably exposes without guessing at layout. Page numbers in the locator
    are 1-based, matching what a reader sees, never a library's 0-based index.

    A structurally broken PDF raises :class:`SourceExtractionFailed`. A
    structurally valid PDF with no extractable text -- the scanned/image-only
    case -- raises :class:`SourceTextUnavailable`. There is no OCR fallback,
    so neither case can silently return an empty success.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise SourceExtractionFailed(f"pypdf is required for PDF ingestion: {exc}")

    import io
    import logging

    # pypdf logs recovery warnings for damaged files; keep ordinary
    # unsupported-source handling quiet rather than noisy.
    pypdf_log = logging.getLogger("pypdf")
    previous_level = pypdf_log.level
    pypdf_log.setLevel(logging.ERROR)
    try:
        try:
            reader = PdfReader(io.BytesIO(raw))
            pages = list(reader.pages)
        except Exception as exc:
            raise SourceExtractionFailed(f"PDF structure could not be parsed: {exc}")

        blocks: list[ExtractedBlock] = []
        ordinal = 0
        for page_number, page in enumerate(pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                raise SourceExtractionFailed(
                    f"text extraction failed on page {page_number}: {exc}"
                )
            text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
            if not text:
                # An empty page is not an error on its own; only a document
                # with no extractable text at all is.
                continue
            ordinal += 1
            locator = {"kind": "page", "start": page_number, "end": page_number}
            blocks.append(
                ExtractedBlock(
                    block_id=compute_block_id(source_id, locator, ordinal),
                    block_type=BLOCK_PAGE,
                    text=text,
                    locator=locator,
                    ordinal=ordinal,
                    metadata={"page": page_number, "page_count": len(pages)},
                )
            )
    finally:
        pypdf_log.setLevel(previous_level)

    if not blocks:
        raise SourceTextUnavailable(
            "PDF has no extractable text layer (scanned or image-only PDF); "
            "OCR is not supported"
        )
    return blocks


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def _markdown_outline(lines: list[str]) -> list[tuple[int, int, str]]:
    """Return ``(line_number, level, heading_text)`` for real ATX headings.

    Lines inside fenced code blocks are skipped, so a ``# Fake Heading``
    written inside a fence never becomes a section.
    """
    outline: list[tuple[int, int, str]] = []
    fence: str | None = None
    for index, line in enumerate(lines, start=1):
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0] * 3
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is not None:
            continue
        heading = _ATX_HEADING_RE.match(line)
        if heading:
            outline.append((index, len(heading.group(1)), heading.group(2).strip()))
    return outline


def extract_markdown(raw: bytes, source_id: str) -> list[ExtractedBlock]:
    """Heading-scoped extraction from Markdown.

    A section runs from its heading line to the line before the next heading
    of any level. ``heading_path`` records the enclosing hierarchy, which is
    what keeps two identically-named headings (for example ``Overview`` under
    ``Architecture`` and ``Overview`` under ``Testing``) distinct: their
    heading paths differ, their line ranges differ, and therefore their block
    ids differ.

    This is a deterministic outline walk, not a Markdown renderer, and the
    resulting sections carry no claim of semantic importance.
    """
    text = _decode_text(raw)
    lines = text.split("\n")
    outline = _markdown_outline(lines)

    blocks: list[ExtractedBlock] = []
    ordinal = 0

    def _slice(start_line: int, end_line: int) -> str:
        return "\n".join(lines[start_line - 1 : end_line]).strip()

    # Content before the first heading is preserved rather than dropped.
    if outline:
        first_heading_line = outline[0][0]
        if first_heading_line > 1:
            preamble = _slice(1, first_heading_line - 1)
            if preamble:
                ordinal += 1
                locator = {
                    "kind": "section",
                    "label": "(preamble)",
                    "heading_path": [],
                    "start_line": 1,
                    "end_line": first_heading_line - 1,
                }
                blocks.append(
                    ExtractedBlock(
                        block_id=compute_block_id(source_id, locator, ordinal),
                        block_type=BLOCK_MARKDOWN_SECTION,
                        text=preamble,
                        locator=locator,
                        ordinal=ordinal,
                        metadata={"heading_level": 0, "heading_text": None},
                    )
                )
    else:
        # No headings at all: fall back to a single whole-document section so
        # that valid Markdown never silently yields zero blocks.
        body = text.strip()
        if not body:
            raise SourceTextUnavailable("Markdown source contains no text")
        locator = {
            "kind": "section",
            "label": "(document)",
            "heading_path": [],
            "start_line": 1,
            "end_line": len(lines),
        }
        return [
            ExtractedBlock(
                block_id=compute_block_id(source_id, locator, 1),
                block_type=BLOCK_MARKDOWN_SECTION,
                text=body,
                locator=locator,
                ordinal=1,
                metadata={"heading_level": 0, "heading_text": None},
            )
        ]

    path_stack: list[tuple[int, str]] = []
    for position, (line_number, level, heading_text) in enumerate(outline):
        while path_stack and path_stack[-1][0] >= level:
            path_stack.pop()
        path_stack.append((level, heading_text))
        heading_path = [name for _lvl, name in path_stack]

        end_line = (
            outline[position + 1][0] - 1 if position + 1 < len(outline) else len(lines)
        )
        ordinal += 1
        locator = {
            "kind": "section",
            "label": " > ".join(heading_path),
            "heading_path": list(heading_path),
            "start_line": line_number,
            "end_line": end_line,
        }
        blocks.append(
            ExtractedBlock(
                block_id=compute_block_id(source_id, locator, ordinal),
                block_type=BLOCK_MARKDOWN_SECTION,
                text=_slice(line_number, end_line),
                locator=locator,
                ordinal=ordinal,
                metadata={"heading_level": level, "heading_text": heading_text},
            )
        )
    return blocks


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------
def extract_text(raw: bytes, source_id: str) -> list[ExtractedBlock]:
    """Paragraph extraction from plain text, split on blank lines.

    Deliberately simple and purely mechanical: blank-line separation only. No
    semantic chunking, no sentence splitting, no topic detection. Line numbers
    are 1-based and refer to the first and last non-blank line of the
    paragraph.
    """
    text = _decode_text(raw)
    lines = text.split("\n")

    blocks: list[ExtractedBlock] = []
    ordinal = 0
    start: int | None = None
    for index, line in enumerate(lines, start=1):
        if line.strip():
            if start is None:
                start = index
            continue
        if start is not None:
            ordinal += 1
            blocks.append(_text_block(source_id, lines, start, index - 1, ordinal))
            start = None
    if start is not None:
        ordinal += 1
        blocks.append(_text_block(source_id, lines, start, len(lines), ordinal))

    if not blocks:
        raise SourceTextUnavailable("plain-text source contains no text")
    return blocks


def _text_block(
    source_id: str, lines: list[str], start: int, end: int, ordinal: int
) -> ExtractedBlock:
    while end > start and not lines[end - 1].strip():
        end -= 1
    locator = {"kind": "line_range", "start": start, "end": end}
    return ExtractedBlock(
        block_id=compute_block_id(source_id, locator, ordinal),
        block_type=BLOCK_PARAGRAPH,
        text="\n".join(lines[start - 1 : end]).strip(),
        locator=locator,
        ordinal=ordinal,
        metadata={"start_line": start, "end_line": end},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
_EXTRACTORS = {
    FORMAT_PDF: extract_pdf,
    FORMAT_MARKDOWN: extract_markdown,
    FORMAT_TEXT: extract_text,
}


def ingest_source(path: str | Path, source_id: str) -> ExtractionResult:
    """The single orchestration-facing ingestion entry point.

    Reads a local file, detects its format, extracts normalized blocks with
    format-native locators, and fingerprints the source using the Phase 12
    digest definition. The returned result is input for AGY's semantic
    segmentation; it is not a Phase 12 source inventory and no block is
    promoted to a semantic source unit here.
    """
    if not _SOURCE_ID_RE.match(source_id or ""):
        raise SourceIngestionError(
            f"invalid source_id: {source_id!r} (expected ^src_[A-Za-z0-9._-]+$)"
        )

    p = Path(os.path.expanduser(str(path)))
    source_format = detect_source_format(p)
    if source_format not in _EXTRACTORS:
        raise SourceFormatUnsupported(
            f"unsupported source format for {p.name!r}; Phase 13.2 supports "
            f"{', '.join(SUPPORTED_FORMATS)} (no DOCX, HTML or OCR)"
        )

    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise SourceReadFailed(f"could not read source file: {exc}")

    blocks = _EXTRACTORS[source_format](raw, source_id)
    return ExtractionResult(
        schema_version=SCHEMA_VERSION,
        extractor_version=EXTRACTOR_VERSION,
        source_id=source_id,
        source_format=source_format,
        # Always over the raw bytes, so it matches whatever Phase 12 recorded.
        source_digest=compute_source_digest(raw),
        blocks=tuple(blocks),
    )


# ---------------------------------------------------------------------------
# Phase 12 handoff
# ---------------------------------------------------------------------------
def phase12_locator(block: ExtractedBlock) -> dict[str, Any]:
    """The Phase 12 locator for an extracted block.

    Phase 13 locators are authored using the frozen Phase 12 locator kinds
    (``page``, ``section``, ``line_range``), so handoff needs no translation
    and no change to Phase 12: PDF pages use ``page``, Markdown sections use
    ``section`` with an additional ``heading_path``/line range, and plain-text
    paragraphs use ``line_range``. Nothing here contains a filesystem path --
    a locator describes a position *within* a source, and the source itself is
    identified by ``source_id``.

    Handing the result to :meth:`SourceInventory.add_unit` remains an AGY
    decision: this returns the locator for a block AGY has *chosen* to promote,
    and never promotes blocks on its own.
    """
    return dict(block.locator)
