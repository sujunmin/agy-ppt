# Third-Party Notices

`agy-ppt` is a standalone repository. It is derived in part from the upstream
project below, but does not vendor, submodule, or otherwise include the
upstream repository's source code. `agy-ppt` is **not affiliated with or
endorsed by the upstream author.**

## Upstream project

- **Name:** codex-ppt-skill
- **Author:** ningzimu
- **Repository:** https://github.com/ningzimu/codex-ppt-skill
- **License:** MIT License
- **Upstream copyright:**

  ```
  Copyright (c) 2026 ningzimu
  ```

The upstream MIT License text is reproduced in full, unmodified, in this
repository's root `LICENSE` file, alongside a separate copyright line for the
portions added in `agy-ppt`. The upstream copyright notice and permission
notice have not been removed or replaced.

## Derived from upstream (adapted into this repository)

`skills/agy-ppt/` contains implementations that were originally derived from
upstream `codex-ppt-skill` and then adapted for the AGY orchestration model
(AGY as sole orchestrator / state owner, Kiro V3 `ppt-engineer` as engineering
worker, Codex CLI as slide-image worker). These files live in this repository
as part of `skills/agy-ppt/` and are not a live dependency on upstream:

- PPTX assembly logic (`scripts/assemble_ppt.py`)
- Slide-prompt preparation (`scripts/prepare_slide_prompts.py`)
- Slide job / run-state bookkeeping (`scripts/slide_run_state.py`,
  `record_slide_dispatch.py`, `record_slide_result.py`,
  `record_slide_blocker.py`, `slide_job_status.py`)
- The API-key based image generation path (`scripts/image_gen.py`,
  `scripts/image_providers/`) and the shared runtime bootstrap script
  (`scripts/codex_ppt_runtime.py`)
- The chroma-key removal utility (`scripts/remove_chroma_key.py`)
- The style reference library (`references/*.md`)

## Runtime dependency (resolved externally, not vendored)

The full upstream `codex-ppt-skill` repository is **not included** in this
repository. When AGY genuinely needs the unmodified upstream skill's own
implementation at runtime (as opposed to the adapted copies listed above),
`agy-ppt` resolves it as an **external runtime dependency**:

- Resolver: `skills/agy-ppt/scripts/codex_ppt_dependency.py`
- Upstream source: `https://github.com/ningzimu/codex-ppt-skill.git`
  (`main` branch, resolved to its current HEAD commit)
- Cache location: an OS application-cache directory outside this repository,
  outside the Global AGY Skill install location, and outside any
  presentation workspace (see `default_cache_root()` in the resolver)

This dependency is fetched with a plain, unauthenticated `git` shallow clone
of a public repository. No OAuth session, API key, or other credential
belonging to AGY, Kiro, or Codex is read, stored, or required to resolve it.

## What was added or substantially changed in agy-ppt

The following is new work implementing the orchestration model itself, which
upstream does not have:

- `scripts/project_state.py` -- an AGY-owned deterministic project/slide state
  machine, resume/recovery logic, and worker-result validation
- `scripts/validate_project.py` -- a read-only state validator
- `scripts/codex_image_adapter.py` -- dispatches a single slide-image render
  turn to the Codex CLI using the already-authenticated subscription session
  (no API key), as an alternative default backend to the API-key-based
  `image_gen.py` path
- `scripts/kiro_acp_bridge.py` -- an ACP bridge that routes engineering work
  (code changes, debugging, tests, tooling) to a Kiro V3 `ppt-engineer` agent,
  always returning control to AGY
- `scripts/codex_ppt_dependency.py` -- the external runtime dependency
  resolver described above
- `scripts/run_recovery_tests.py`, `scripts/run_live_recovery_tests.py`, and
  the accompanying `tests/recovery/` and `tests/integration/` suites --
  deterministic fault-injection tests and opt-in, quota-consuming live
  recovery tests
- The `agy-ppt`-specific documentation under `skills/agy-ppt/docs/`
  describing this orchestration model, its routing rules, and the external
  dependency model

## Attribution statement

`agy-ppt` is a derivative work built on top of `codex-ppt-skill`. It does not
claim upstream's original work as its own, and it does not represent itself
as an official release of, or endorsed by, the upstream author. The upstream
repository is not vendored in this repository; when required, `agy-ppt`
resolves it as an external runtime dependency from the upstream repository
using the resolver described above.
