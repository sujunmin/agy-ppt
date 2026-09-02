# Changelog

All notable changes to `agy-ppt` will be documented in this file.

## [Unreleased]

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
