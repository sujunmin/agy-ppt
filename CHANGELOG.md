# Changelog

All notable changes to `agy-ppt` will be documented in this file.

## [Unreleased]

### Added

- Repository contribution governance is now versioned in `AGENTS.md`, covering
  the pull-request flow, a single Conventional Commit PR-title policy, release
  PR naming, changelog format, real-PR-number-only changelog references, and the
  release and verification process. (#2)
- Deterministic source ingestion and locator extraction
  (`skills/agy-ppt/scripts/source_ingestion.py`), the upstream producer for the
  source-grounding system: a local source file is turned into normalized
  extraction blocks with source-format-native locators, which AGY then
  semantically segments. Extraction is deliberately separate from grounding, and
  an extracted block is not a semantic source unit. (#3)
- Support for three initial source formats: PDF with an extractable text layer
  (page-level blocks, 1-based page locators), Markdown (H1–H6 heading hierarchy
  with `heading_path` and 1-based line ranges, where repeated heading names stay
  distinct and a heading inside a fenced code block is ignored), and plain text
  (blank-line paragraph blocks with 1-based line ranges). UTF-8 and
  UTF-8-with-BOM are supported. (#3)
- A single deterministic format-detection authority that validates the PDF file
  signature rather than trusting the file extension alone. (#3)
- Stable, resume-safe block identifiers derived from
  `(source_id, locator, ordinal)`, so re-ingesting identical bytes with the same
  extractor version reproduces the same block ids, locators, and ordering,
  independently of the file's absolute path. (#3)
- A persisted `extractor_version`, independent of the release version and of Git
  tags, so future changes to extraction behaviour remain identifiable. (#3)
- A dedicated ingestion error taxonomy — `SOURCE_FORMAT_UNSUPPORTED`,
  `SOURCE_FILE_NOT_FOUND`, `SOURCE_READ_FAILED`,
  `SOURCE_ENCODING_UNSUPPORTED`, `SOURCE_TEXT_UNAVAILABLE`, and
  `SOURCE_EXTRACTION_FAILED` — kept disjoint from the grounding and
  image-worker codes. A scanned or image-only PDF fails explicitly and there is
  no OCR fallback; a structurally broken PDF is reported separately from a
  validly textless one. (#3)
- A thin ingestion CLI adapter (`skills/agy-ppt/scripts/ingest_source.py`) that
  delegates entirely to the core module and reports a concise diagnostic with a
  stable error code instead of a stack trace on ordinary failures. (#3)
- Documentation for source ingestion
  (`skills/agy-ppt/docs/source-ingestion.md`), plus a README section and a
  minimal `SKILL.md` integration describing where deterministic ingestion sits
  ahead of AGY semantic segmentation. (#3)
- Official English README documentation (`README_en.md`), newly authored for
  `agy-ppt`, alongside the primary Traditional Chinese `README.md`, with
  repository-relative language-switch links and semantic parity between the two.
  `AGENTS.md` now records the bilingual README parity requirement. (#3)
- Deterministic DOCX source ingestion, handled through the same
  `ingest_source()` API and CLI as the existing formats. Extraction is
  structural: heading hierarchy from built-in Word heading styles, paragraphs,
  and tables, walked in true document order so interleaved paragraphs and tables
  keep their original sequence. Tables are flattened row-major, one line per row,
  and are never silently discarded. (#4)
- Structural DOCX locators using the existing `section` locator kind, carrying a
  heading path plus 1-based body element indices for sections and 1-based table
  and row indices for tables. DOCX is flow-based OOXML with no reliable rendered
  page boundaries without a layout engine, so no page number is fabricated. (#4)
- Structural OOXML package detection: a file is treated as DOCX only when the
  ZIP package actually contains `word/document.xml`, so an ordinary ZIP or a
  spreadsheet package is not misclassified. A `.docx` file with no ZIP signature,
  which is how a password-protected document appears, is still routed to DOCX so
  that extraction reports a DOCX-specific diagnostic. (#4)
- Deterministic DOCX failure semantics reusing the existing error codes: a
  document with no body or table text, including an image-only document, reports
  `SOURCE_TEXT_UNAVAILABLE`, while a corrupted or encrypted package reports
  `SOURCE_EXTRACTION_FAILED`. Encrypted documents fail without any interactive
  password prompt, and there is no OCR. (#4)
- Deterministic local HTML source ingestion, handled through the same
  `ingest_source()` API and CLI as the existing formats. Extraction is static and
  structural: heading hierarchy from real `h1`–`h6` elements, paragraphs, ordered
  and unordered lists including nested items, and tables, all produced in DOM
  document order so interleaved content keeps its original sequence. Inline
  markup contributes text to its enclosing paragraph rather than fragmenting it,
  and visible hyperlink text is retained. (#5)
- A network-free HTML ingestion contract: no JavaScript is executed, no browser
  or headless engine is used, no CSS is applied, and no remote or
  locally-referenced resource, stylesheet, image, iframe or hyperlink is ever
  fetched or opened. The parser is constructed with network access disabled, and
  tests assert this by intercepting socket and HTTP APIs rather than relying on
  the network being unavailable. (#5)
- Structural HTML locators using the existing `section` locator kind, carrying a
  heading path plus 1-based extraction-order element indices, list indices, and
  table and row indices. No page number, screen position or scroll offset is
  fabricated. (#5)
- Conservative HTML format detection: an `.html` or `.htm` extension is trusted
  only when the content actually contains element markup, an html-specific
  document marker is required to detect HTML without a recognised extension, and
  plain text is resolved first so a text file mentioning markup stays text. (#5)
- Deterministic HTML exclusions reusing the existing error codes: `script`
  including embedded JSON-LD, `style`, `template`, `noscript`, `svg`, `math`,
  HTML comments, and document head content are never ingested as source text.
  An empty document or a page whose content exists only after JavaScript reports
  `SOURCE_TEXT_UNAVAILABLE`, while malformed but recoverable HTML is extracted
  deterministically. (#5)

### Changed

- `skills/agy-ppt/requirements.txt` now includes `pypdf>=4.2.0`, used for
  deterministic PDF text extraction. (#3)
- `skills/agy-ppt/requirements.txt` now includes `python-docx>=1.1.0`, used for
  deterministic DOCX structural extraction. Its own requirements, `lxml` and
  `typing_extensions`, are already required by the declared `python-pptx`. (#4)
- The source-ingestion documentation, `SKILL.md`, and both READMEs now describe
  DOCX support, its structural locator model, and the DOCX features that are
  deliberately not ingested: headers, footers, footnotes, endnotes, comments,
  tracked-change reconstruction, and text inside embedded images. (#4)
- `skills/agy-ppt/requirements.txt` now declares `lxml>=4.9.0` explicitly, used
  for deterministic static HTML parsing with network access disabled. It was
  already present transitively via `python-pptx` and `python-docx`, so the
  environment does not grow. (#5)
- The source-ingestion documentation, `SKILL.md`, and both READMEs now describe
  local static HTML support, its structural locator model, the network-free
  contract, and its limitations: JavaScript-generated content is not ingested,
  CSS visibility and layout are not reconstructed, `rowspan` and `colspan` are
  not expanded, and only heading, paragraph, list and table elements become
  blocks. (#5)

## [0.2.0] - 2026-09-04

### Added

- Optional source-grounding capability for source-driven presentation projects
  (`skills/agy-ppt/scripts/source_grounding.py`), built on four sidecar
  contracts: `source_inventory.json`, `claim_traceability.json`,
  `source_coverage.json`, and `source_grounded_qa.json`. Purely creative decks
  with no source material are unaffected and require none of these artifacts. (#1)
- A reusable source inventory contract with stable source-unit identifiers
  derived deterministically from `(source_id, locator)`, optional source
  fingerprints for change detection, extensible source locators (`page`,
  `section`, `line_range`, `generic`), and HIGH/MEDIUM/LOW priority
  classification. A locator describes a position within a document and is
  never an absolute local path. (#1)
- Claim-to-source traceability that persists AGY's per-claim semantic support
  decision verbatim, together with optional numeric and modal evidence, using
  stable claim identifiers derived from `(slide_id, sequence)`. (#1)
- Source coverage accounting over `covered`, `speaker_notes_only`,
  `intentionally_omitted` (which requires a non-empty reason),
  `not_applicable`, and `unaccounted`, with deterministic completeness
  validation so that a HIGH-priority source unit can never silently disappear
  and coverage cannot be inflated by duplicate accounting. (#1)
- A source-grounded QA report that keeps AGY's `semantic_findings` strictly
  separate from the validator's computed `deterministic_findings`. (#1)
- A deterministic assembly precondition for grounding-enabled projects
  (`skills/agy-ppt/scripts/validate_source_grounding.py`) that must pass
  before assembly starts. A failure there is a recoverable grounding
  precondition failure, deliberately kept distinct from the Phase 9
  assembly-failure recovery path, and is not by itself a project blocker. (#1)
- Stale-evidence detection: when a recorded source digest no longer matches the
  current one, previously persisted grounding evidence is rejected rather than
  silently reused. (#1)
- Resume-safe grounding persistence: reloading from disk and re-applying the
  same source produces no source-unit or claim identifier drift, no duplicated
  evidence, and no lost support or coverage decisions. (#1)
- Integration of source grounding into the source-driven AGY workflow, so
  traceability and coverage validation run as a formal step before assembly. (#1)
- Public-source validation evidence for the source-grounding implementation
  (`skills/agy-ppt/docs/validation/phase-12.4-public-source-validation.md`),
  recording deterministic validation against NIST AI 100-1 (AI RMF 1.0) and
  RFC 2119 with official source URLs, SHA-256 fingerprints, the tested commit,
  and the validation outcomes. Validation runtime outputs and downloaded source
  files are deliberately not committed. (#1)
- An independent AGY semantic-authority attestation
  (`skills/agy-ppt/docs/validation/phase-12.4-agy-semantic-attestation.md`),
  kept separate from the deterministic engineering evidence so that the two
  provenances are never conflated. (#1)
- Architecture documentation for the two-layer grounding design
  (`skills/agy-ppt/docs/source-grounding.md`), and a README section covering the
  optional source-grounding workflow, the assembly gate, and its boundaries. (#1)

### Changed

- Source-driven AGY workflows now perform formal traceability and coverage
  validation before assembly, and Content QA for grounded projects persists
  structured source evidence and coverage decisions. AGY remains the semantic
  authority: the deterministic validators check schema, identifier and
  reference integrity, coverage accounting, source freshness, and the assembly
  readiness contract, and never independently prove factual truth. (#1)

## [0.1.0] - 2026-09-02

### Added

- AGY sole-orchestrator workflow: AGY owns the outline, storytelling, visual
  strategy, approval gates, and content/visual QA; workers only return
  results to AGY (`AGY -> worker -> AGY`), and worker-to-worker chaining is
  forbidden.
- Kiro V3 `ppt-engineer` engineering-worker integration
  (`scripts/kiro_acp_bridge.py`) with agent-scope enforcement as a
  turn-long runtime invariant.
- Codex CLI slide-image-worker integration (`scripts/codex_image_adapter.py`)
  using the authenticated Codex subscription session's built-in `image_gen`
  tool, with no production API-key fallback.
- Deterministic, AGY-owned Project State system (`scripts/project_state.py`,
  `scripts/validate_project.py`): a deck-level phase state machine, a
  per-slide state machine, a generation counter, full attempt history,
  worker-result validation, and deterministic resume/recovery.
- A consecutive generic-image-failure retry policy: at most one immediate
  retry per slide for the same `IMAGE_GENERATION_FAILED` error_code; a second
  consecutive occurrence blocks the slide and the project instead of
  retrying indefinitely, and an operator-confirmed quota decision is recorded
  separately from the worker's own error_code.
- A deterministic fault-injection and recovery test suite
  (`skills/agy-ppt/tests/recovery/`, `scripts/run_recovery_tests.py`) that
  consumes no AI subscription quota, plus an opt-in live failure and recovery
  harness (`skills/agy-ppt/tests/integration/test_phase9_live_*.py`,
  `scripts/run_live_recovery_tests.py`) for real, quota-consuming
  verification.
- An external `codex-ppt` runtime dependency resolver
  (`scripts/codex_ppt_dependency.py`): `agy-ppt` does not vendor or submodule
  the upstream `codex-ppt-skill` repository. When the unmodified upstream
  implementation is genuinely needed at runtime, it is resolved on demand
  from `https://github.com/ningzimu/codex-ppt-skill.git` (`main` branch,
  resolved to its current HEAD commit) into an OS application-cache location
  outside this repository, outside the Global AGY Skill install location,
  and outside any presentation workspace. Offline use reuses an existing
  cache with an explicit warning; no cache and no network raises a
  deterministic `CODEX_PPT_DEPENDENCY_UNAVAILABLE` error, kept separate from
  the image-generation retry policy above.

### Changed

- Prepared `agy-ppt` as a standalone public repository, independent of the
  upstream `codex-ppt-skill` repository's Git history, workflows, and
  documentation site.
- Removed the vendored upstream `codex-ppt` skill from the public repository
  model in favor of the external dependency resolver described above.
