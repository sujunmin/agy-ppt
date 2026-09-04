# Changelog

All notable changes to `agy-ppt` will be documented in this file.

## [Unreleased]

### Added

- Repository contribution governance is now versioned in `AGENTS.md`, covering
  the pull-request flow, a single Conventional Commit PR-title policy, release
  PR naming, changelog format, real-PR-number-only changelog references, and the
  release and verification process. (#2)

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
