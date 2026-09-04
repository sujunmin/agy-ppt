# agy-ppt

**Language:** [繁體中文](README.md) | English

An image-based PPT/PPTX generation workflow in which AGY is the sole
orchestrator and state owner, Kiro V3 `ppt-engineer` is a dedicated engineering
worker, and Codex CLI is a dedicated slide-image worker.

> This project is a derivative work of
> [`ningzimu/codex-ppt-skill`](https://github.com/ningzimu/codex-ppt-skill). It is
> not an official upstream release and is not endorsed by the upstream author.
> See [Upstream & Attribution](#upstream--attribution) below.

## Standalone Repository

`agy-ppt` is a standalone repository.

It does not vendor a full upstream `codex-ppt-skill` checkout, and it does not
include one as a Git submodule. `codex-ppt` is an **external runtime
dependency**: only when a feature genuinely needs the unmodified upstream
implementation does
[`skills/agy-ppt/scripts/codex_ppt_dependency.py`](skills/agy-ppt/scripts/codex_ppt_dependency.py)
resolve and download it on demand, into a cache located outside this repository.
See [codex-ppt Dependency](#codex-ppt-dependency) below.

## What It Does

Plans an article, report, or outline into a deck structure and visual style, then
generates each slide as a single full-page image, and finally assembles those
images into a `.pptx` where every slide carries its speaker notes.

## Architecture

```text
AGY -> worker -> AGY
```

This is the only permitted routing. The three roles have strictly separated
responsibilities:

| Role | Responsibility |
| --- | --- |
| **AGY** | The sole orchestrator and state owner. Decides the outline, page count, storyline, visual strategy, copy, approval gates, content QA and visual QA, whether an image is regenerated, and whether the project advances to assembly and completion. |
| **Kiro V3 `ppt-engineer`** | Engineering worker only. Writes and changes code, debugs, writes tests, defines schema/tool contracts, CLI/ACP adapters, dependency/build work, filesystem automation, and PPTX assembly tooling. It must not change deck content, approved copy, page count, visual strategy, or any slide image. |
| **Codex CLI** | Slide-image worker only. Generates or edits one full-page slide image and returns the result. It must not change copy or page count, write code, assemble the PPTX, or switch image backend on its own. |

The following routings are strictly forbidden — workers never call each other and
never hand the workflow to one another:

```text
AGY -> Kiro -> Codex   (forbidden)
AGY -> Codex -> Kiro   (forbidden)
Kiro -> Codex          (forbidden)
Codex -> Kiro          (forbidden)
```

A worker always returns its result to AGY, and AGY decides what happens next. A
worker holds no deck context and makes no follow-up decisions. For the full
rationale see
[`skills/agy-ppt/docs/agent-routing.md`](skills/agy-ppt/docs/agent-routing.md)
and
[`skills/agy-ppt/docs/architecture-and-design-rationale.md`](skills/agy-ppt/docs/architecture-and-design-rationale.md).

## Key Features

- **AGY-owned deterministic Project State** (`scripts/project_state.py`): a
  deck-level phase state machine, a per-slide state machine, a generation
  counter, full attempt history, resume/recovery, and worker-result validation.
  AGY is the only writer.
- **Image generation through the Codex subscription session**
  (`scripts/codex_image_adapter.py`): calls the built-in `image_gen` tool via an
  authenticated Codex CLI subscription session. No API key, and no automatic
  fallback to a paid API.
- **Kiro V3 ACP bridge** (`scripts/kiro_acp_bridge.py`): hands engineering work
  (code, debugging, tests) to Kiro V3 `ppt-engineer`. The agent scope is a
  turn-long runtime invariant; if it drifts, the bridge aborts and reports
  rather than assuming success.
- **A retry policy allowing at most one immediate retry**: a second consecutive
  identical `IMAGE_GENERATION_FAILED` on the same slide blocks the project
  instead of retrying indefinitely. An operator may separately record an
  explicit "quota exhausted" decision, which is never forged into a worker error
  code.
- **Deterministic fault-injection test suite**
  (`skills/agy-ppt/tests/recovery/`): covers generation failure, backend
  unavailable, ambiguous artifact, invalid output, interrupted generation, QA
  regeneration, assembly failure, and resume idempotency. It consumes no AI
  subscription quota.
- **External codex-ppt dependency resolver**
  (`scripts/codex_ppt_dependency.py`): a single dependency-resolver authority
  that deterministically defines "latest" as the current HEAD of the upstream
  `main` branch, with offline cache reuse, atomic cache updates, and explicit
  dependency-unavailable failure semantics. See
  [`skills/agy-ppt/docs/upstream-differences.md`](skills/agy-ppt/docs/upstream-differences.md).

## OAuth / Subscription Runtime

The default profile is subscription-login first, with zero API keys:

```text
AGY   = Google AI Pro login session (Antigravity / Gemini CLI)
Kiro  = Kiro Pro login session (Kiro CLI V3)
Codex = ChatGPT Plus / Codex login session
```

Each CLI manages its own credentials. This project's code never reads, copies,
or forwards any OAuth access token or refresh token. See
[`skills/agy-ppt/docs/oauth-subscription-runtime.md`](skills/agy-ppt/docs/oauth-subscription-runtime.md).

## No Production API-Key Fallback

The production workflow keeps the API-key path switched off by default:

- Before invoking Codex CLI, `codex_image_adapter.py` strips API-key variables
  such as `OPENAI_API_KEY` from the subprocess environment. It records variable
  **names** only, never values.
- If the current Codex session does not expose the built-in `image_gen` tool, it
  reports `IMAGE_BACKEND_UNAVAILABLE` and returns control to AGY. It does
  **not** switch to a paid API.
- `scripts/image_gen.py` and `scripts/image_providers/`, adapted from upstream,
  retain the API-key and third-party-provider path under
  `skills/agy-ppt/scripts/`. They exist for users who explicitly want that path;
  the default production route never triggers them automatically.

See
[`skills/agy-ppt/docs/cli-api-fallback.md`](skills/agy-ppt/docs/cli-api-fallback.md).

## codex-ppt Dependency

`codex-ppt` is not bundled or vendored in this repository.

- **First use**: the first time a feature genuinely needs the unmodified
  upstream implementation, `resolve_codex_ppt_dependency()` creates an external
  dependency cache directory — in an OS application-cache location, outside this
  repository, outside the Global AGY Skill install location, and outside any
  presentation workspace. It shallow-clones the `main` branch from the fixed
  upstream URL (`https://github.com/ningzimu/codex-ppt-skill.git`), validates the
  checkout, and returns the resolved dependency root.
- **Update**: on later use the resolver checks the current upstream version (the
  HEAD commit of `main`) according to the dependency resolver policy. If upstream
  has not changed it reuses the existing cache; if it has, the cache is updated
  via temporary checkout, validation, then atomic replace, so a failed update
  can never corrupt a working cache.
- **Offline**: if upstream is temporarily unreachable and a local cache exists,
  the cached copy is reused with a clear warning naming the cached commit SHA.
  This is not an API fallback. With no cache and no network, the result is an
  explicit, deterministic `CODEX_PPT_DEPENDENCY_UNAVAILABLE` error — a
  dependency/bootstrap failure kept entirely separate from the
  `IMAGE_GENERATION_FAILED` worker-retry semantics.
- **Authentication**: resolving public upstream code on GitHub uses ordinary,
  unauthenticated `git` operations only. It does not need and never reads
  `OPENAI_API_KEY`, `CODEX_API_KEY`, `KIRO_API_KEY`, `GEMINI_API_KEY`, or any
  AGY/Kiro/Codex OAuth session.
- **Local override (optional)**: for development or offline testing, set
  `AGY_PPT_CODEX_PPT_HOME=/path/to/codex-ppt` to point at an existing local
  checkout. The resolver uses that path directly, never copies its contents into
  this repository, and never writes the path into Project State.

The module docstring in
[`skills/agy-ppt/scripts/codex_ppt_dependency.py`](skills/agy-ppt/scripts/codex_ppt_dependency.py)
documents the full resolver design and failure semantics.

## Installation

### Requirements

- **Python 3.11+** (development and testing use 3.11; the type syntax used with
  `from __future__ import annotations` requires 3.10 or newer)
- **Git**: to obtain the source, and for the unauthenticated `git` operations
  `codex_ppt_dependency.py` uses to resolve the external dependency
- **Codex CLI**: an authenticated subscription session (see
  [Codex CLI Requirements](#codex-cli-requirements))
- **Kiro CLI V3**: an authenticated subscription session (see
  [Kiro `ppt-engineer` Setup](#kiro-ppt-engineer-setup))
- To assemble `.pptx` files, the Python packages listed in
  `skills/agy-ppt/requirements.txt` (`python-pptx`, `Pillow`, `openai`,
  `filelock`, `pypdf`, `python-docx`, `lxml`):

  ```bash
  python3 -m pip install -r skills/agy-ppt/requirements.txt
  ```

  You can also use `skills/agy-ppt/scripts/codex_ppt_runtime.py bootstrap` to
  create a separate shared runtime venv (see that script for details). There is
  no `pip install agy-ppt`, `brew install agy-ppt`, or `npm install agy-ppt`:
  installing means obtaining the source.

### Get the Source

```bash
git clone https://github.com/sujunmin/agy-ppt.git
cd agy-ppt
```

### Install the AGY Skill Globally

The AGY skill only needs the `skills/agy-ppt/` directory. Do not sync the whole
repository, `.git/`, or the codex-ppt external dependency cache.

Install into the Global AGY Skill location:

```bash
rsync -a --delete \
  ./skills/agy-ppt/ \
  ~/.gemini/config/skills/agy-ppt/
```

Or install into the project workspace you are working in:

```text
<your-workspace>/.agents/skills/agy-ppt/
```

For local development, a symlink is more convenient than copying:

```bash
mkdir -p ~/.gemini/config/skills
ln -s "$(pwd)/skills/agy-ppt" ~/.gemini/config/skills/agy-ppt
```

### Kiro `ppt-engineer` Setup

`ppt-engineer` is the dedicated custom agent on the Kiro side. Its definition
lives at:

```text
<repo>/.kiro/agents/ppt-engineer.md
```

The only supported runtime is **Kiro CLI V3**, started as:

```bash
kiro-cli --v3 acp --auth-method cli
```

The V2 engine is not supported: `kiro_acp_bridge.py` rejects it and reports
`UNSUPPORTED_KIRO_ENGINE`. `--auth-method cli` lets kiro-cli resolve its own
existing login session; omitting it would require the ACP client to supply a
token on its behalf, which this project forbids.

### Codex CLI Requirements

- An authenticated Codex CLI (ChatGPT Plus / Codex subscription session) whose
  current session exposes the built-in `image_gen` tool (the `$imagegen` skill).
- The standard invocation is `codex exec --json --skip-git-repo-check`, with the
  prompt passed on stdin.
- No `OPENAI_API_KEY` or third-party image-generation API key is required.

## Quick Start

1. Install and sign in to all three CLIs (AGY / Kiro / Codex) and confirm each
   subscription session works.
2. Load `skills/agy-ppt/SKILL.md` in your agent environment.
3. Describe the deck you want to AGY, for example:

   ```text
   Please turn /path/to/article.md into a deck of about 10 slides.
   ```

4. AGY walks you through confirming the outline, the visual style, and a sample
   slide, then generates each slide, reviews it, and assembles the `.pptx`.

## External Project Workspace

Each deck project gets its own workspace directory, kept separate from this
repository's source, for example:

```text
~/projects/my-presentation/
├── origin_image/           # Final slide images only
│   ├── slide_01.png
│   └── ...
├── prompts/                 # The full generation prompt for each slide
├── outline.md                # The confirmed outline
├── speech.md                  # Speaker notes, written into each slide's notes
├── project_state.json          # AGY-owned deterministic project state
└── my-presentation.pptx        # The assembled deck
```

`project_state.json` is AGY's deterministic state file, operated on by
`scripts/project_state.py` and `scripts/validate_project.py`. It should never be
committed to this source repository.

## State / Resume / Recovery

`project_state.json` records:

- The deck phase state machine: `intake -> outline -> style -> sample ->
  slide_generation -> visual_qa -> assembly -> complete`, with any phase able to
  move to `blocked`.
- The slide state machine: `planned -> ready -> generating -> generated ->
  qa_passed/qa_failed -> assembled`, where `generation_failed` can return to
  `ready` for regeneration.
- A `generation` counter and the complete `attempts` history per slide, which is
  never overwritten or discarded.

Resume behaviour:

- Slides already `qa_passed` or `assembled` are never regenerated; their image
  bytes do not change.
- A fresh process that reloads state from disk dispatches only unfinished
  slides.
- A slide interrupted while `generating` is judged `generated` only when both a
  completed worker result and a verified existing artifact are present.
  Otherwise it becomes `generation_failed`. Success is never assumed.
- Two consecutive identical `IMAGE_GENERATION_FAILED` results on one slide move
  the project to `phase -> blocked` and remember `phase_before_block`. It
  resumes only on an explicit AGY decision.

See
[`skills/agy-ppt/docs/runtime-state-and-routing.md`](skills/agy-ppt/docs/runtime-state-and-routing.md)
and
[`skills/agy-ppt/docs/recovery-testing.md`](skills/agy-ppt/docs/recovery-testing.md).

## Source Grounding & Traceability

Released in v0.2.0.

When a deck is built from existing source documents, the Phase 12 source
grounding mechanism can be enabled. This is an **optional capability**: purely
creative decks with no source material are entirely unaffected and need none of
the artifacts below.

Once enabled, the project workspace gains four sidecar artifacts:

| Artifact | Purpose |
| --- | --- |
| `source_inventory.json` | Sources and source units: stable unit ids, locators, priority, source fingerprint |
| `claim_traceability.json` | Which source units support each slide claim, plus AGY's support decision |
| `source_coverage.json` | Coverage accounting for every source unit |
| `source_grounded_qa.json` | The final grounded QA report, separating semantic from deterministic findings |

### Two-Layer Separation

- **AGY is the semantic authority**: source understanding, segmentation, claim
  support decisions, coverage decisions, and numeric/modal interpretation are all
  AGY's, and are persisted verbatim.
- **The deterministic validator only checks structure**: schema, identifier and
  reference integrity, coverage accounting, source freshness, and the assembly
  readiness contract. It does **not** independently prove that content is
  factually true.

### Assembly Gate

A source-grounding-enabled project must pass this before assembly:

```bash
python3 scripts/validate_source_grounding.py <workspace>
```

Exit code `0` means the grounding precondition is satisfied, or that source
grounding is not enabled for the project. Exit code `1` is a grounding
precondition failure: assembly must **not** start, and control returns to AGY for
repair. This is a recoverable workflow issue, deliberately kept separate from the
Phase 9 assembly-failure recovery path, and it is not a project blocker on its
own.

The gate checks structure and AGY's persisted decisions. It does **not** mean the
validator has independently proven the content true.

### Coverage Accounting

Every source unit must be explicitly accounted for as `covered`,
`speaker_notes_only`, `intentionally_omitted` (which requires a reason),
`not_applicable`, or `unaccounted`. A HIGH-priority source unit can never
silently disappear from the accounting, and duplicate entries cannot inflate
coverage.

### Source Fingerprint and Stale Evidence

Source unit ids are derived deterministically from `(source_id, locator)` and
claim ids from `(slide_id, sequence)`. Resuming on the same source therefore
causes no id drift, no duplicated evidence, and no loss of existing support or
coverage decisions.

If a source's SHA-256 fingerprint no longer matches the recorded one, the
existing grounding evidence is treated as stale and rejected rather than silently
reused.

### Public Validation Evidence

Phase 12 was validated against public sources including NIST AI RMF 1.0 and
RFC 2119.

The evidence is split by provenance:

- [`skills/agy-ppt/docs/validation/phase-12.4-public-source-validation.md`](skills/agy-ppt/docs/validation/phase-12.4-public-source-validation.md)
  — deterministic / engineering validation evidence
- [`skills/agy-ppt/docs/validation/phase-12.4-agy-semantic-attestation.md`](skills/agy-ppt/docs/validation/phase-12.4-agy-semantic-attestation.md)
  — independent AGY semantic-authority attestation

For the design, see
[`skills/agy-ppt/docs/source-grounding.md`](skills/agy-ppt/docs/source-grounding.md).

## Source Ingestion

Released in v0.3.0.

Source grounding needs source text before AGY can perform semantic segmentation.
Phase 13 provides deterministic ingestion, turning a **local** source file into
normalized extraction blocks and locators.

```bash
python3 skills/agy-ppt/scripts/ingest_source.py \
    --source /path/to/report.pdf \
    --source-id src_report \
    --output /path/to/workspace/extraction.json
```

Where it sits in the flow:

```text
local source
  -> deterministic ingestion (Phase 13)
  -> AGY semantic segmentation
  -> source units in source_inventory.json
  -> grounding workflow (Phase 12)
```

### Supported Formats

| Capability | Status |
| --- | --- |
| Local PDF with an extractable text layer | Supported |
| Local Markdown | Supported |
| Local plain text | Supported |
| Local DOCX | Supported |
| Local static HTML | Supported |
| Explicit public HTTP/HTTPS source acquisition | Supported |
| Authenticated / private web sources | Not supported |
| Web crawling | Not supported |
| Browser / JavaScript rendering | Not supported |
| OCR / scanned PDF | Not supported |

### Extraction Is Not Semantic Segmentation

This boundary matters:

```text
Phase 13 deterministic extraction  !=  semantic source understanding
```

Ingestion produces blocks and locators only — 1-based page numbers for PDF,
heading hierarchy and line numbers for Markdown, line ranges for plain text, and
heading hierarchy with structural element, list and table indices for DOCX and
HTML, all using 1-based numbering. It does **not** decide what is important, what
counts as HIGH priority, what a claim means, or how coverage is judged. AGY
performs semantic segmentation and every grounding decision, which is why an
extracted block is **not** a Phase 12 semantic source unit.

### PDF Limitation

PDF support **requires an extractable text layer**; this is not universal PDF
parsing. A scanned or image-only PDF fails explicitly with
`SOURCE_TEXT_UNAVAILABLE`, and there is **no OCR fallback**.

### DOCX Limitation

DOCX extraction is **structural, not rendered-page extraction**. DOCX is
flow-based OOXML: it does not provide stable rendered page boundaries without a
layout engine. Locators therefore use structural elements — heading hierarchy,
body element indices, and table and row indices — rather than page numbers, and
no page number is ever fabricated.

Extraction covers heading hierarchy, paragraphs, and tables, preserving the
document order of paragraphs and tables. Headings are identified from built-in
Word heading styles only, never inferred from font size or boldness. Headers,
footers, footnotes, endnotes, comments, tracked-change reconstruction, and text
inside embedded images are **not** ingested. Password-protected DOCX is not
supported and fails explicitly.

### HTML Limitation

HTML ingestion is static local-file extraction, not browser rendering.

Not supported:

```text
JavaScript-rendered content
browser rendering
remote resource loading
URL fetching
CSS visibility/layout reconstruction
```

Only local `.html` and `.htm` files are read. Extraction covers headings,
paragraphs, lists and tables in DOM document order. **No JavaScript is executed,
no browser or headless engine is used, no CSS is applied, no remote or
locally-referenced resource is downloaded, no hyperlink is followed, and no
iframe is fetched.** Network activity is zero, and this is proven by tests that
intercept socket and HTTP APIs rather than by relying on the network being
unavailable.

`script`, `style`, `template`, `noscript`, HTML comments and JSON-LD are
excluded. Visible hyperlink text is kept, while the link destination is never
followed or treated as source evidence. Tables do not expand `rowspan` or
`colspan`. Locators are structural: no page number or screen position is
fabricated.

Re-ingesting the same source with the same extractor version reproduces the same
block ids, locators, and ordering, and the result does not depend on the file's
absolute path. See
[`skills/agy-ppt/docs/source-ingestion.md`](skills/agy-ppt/docs/source-ingestion.md).

## Remote Source Acquisition

Released in v0.3.0.

When a source is not on disk, the acquisition layer fetches one **explicitly
supplied public URL** and hands the resulting local payload to the existing
extraction:

```bash
python3 skills/agy-ppt/scripts/acquire_source.py \
    --url https://example.org/source.pdf \
    --source-id src_example \
    --output-dir /path/to/workspace \
    --ingest
```

```text
explicit public URL
  -> bounded acquisition (Phase 13.5)
  -> local payload outside the repository
  -> existing extraction
  -> AGY semantic segmentation
  -> grounding workflow
```

`Acquisition != extraction`: this layer only fetches bytes. It does not parse the
payload, decide its format, or make any semantic judgement. The server's declared
`Content-Type` is metadata only, and format detection remains authoritative — a
response labelled `application/pdf` whose body is actually HTML is not treated as
a PDF.

### Security Boundary

```text
public unauthenticated URLs only
HTTP/HTTPS only
URLs with embedded credentials rejected
localhost, loopback, private, link-local and reserved destinations blocked
every redirect destination revalidated
redirect limit 5
response size limited to 25 MiB
timeout 30 seconds
TLS certificate verification preserved
no cookies, no .netrc, no cloud credentials, no auth tokens
no browser, no JavaScript execution
no crawling, no recursive asset / iframe / link fetching
```

The payload is written to the caller-provided directory — keep it outside this
repository — using an atomic rename, so a failed attempt never leaves a truncated
file. `source_digest` remains the Phase 12 fingerprint over the raw acquired
bytes, and `retrieved_at` is audit metadata that influences no identifier.

**Stated honestly: this is not a hardened multi-tenant SSRF sandbox.** Host
validation checks every address a hostname resolves to, but the subsequent HTTP
connection performs its own lookup, so a DNS-rebinding / TOCTOU window remains.
It is a CLI guardrail for sources an operator chose deliberately, not something
to place behind untrusted URL input in a web service.

Deterministic tests inject the HTTP transport and the DNS resolver, so the
ordinary suite never depends on network availability. A bounded live check is
opt-in and covers one source, one acquisition, one extraction:

```bash
AGY_PPT_LIVE_REMOTE=1 \
    python3 skills/agy-ppt/tests/integration/test_remote_acquisition_live.py
```

See
[`skills/agy-ppt/docs/source-acquisition.md`](skills/agy-ppt/docs/source-acquisition.md).

## Testing

Ordinary unit tests consume **no** AI subscription quota, never invoke the real
Codex or Kiro, and use deterministic fake workers throughout:

```bash
python3 -m unittest discover -s skills/agy-ppt/tests -t skills/agy-ppt/tests -p "test_*.py"
python3 skills/agy-ppt/scripts/run_recovery_tests.py
```

Live tests require explicit opt-in and do consume real subscription quota. Please
do not run them unnecessarily:

```bash
# End-to-end verification by generating one real image through Codex
AGY_PPT_LIVE_CODEX_IMAGE=1 python3 skills/agy-ppt/tests/integration/test_codex_imagegen_live.py

# Phase 9 live failure & recovery (partial resume / regenerate / assembly recovery)
AGY_PPT_LIVE_RECOVERY=1 python3 skills/agy-ppt/scripts/run_live_recovery_tests.py

# Additionally run the process-interruption scenario, which terminates a Codex
# process the test itself created and tracks
AGY_PPT_LIVE_RECOVERY=1 AGY_PPT_LIVE_RECOVERY_INTERRUPT=1 \
    python3 skills/agy-ppt/scripts/run_live_recovery_tests.py
```

See
[`skills/agy-ppt/docs/recovery-testing.md`](skills/agy-ppt/docs/recovery-testing.md).

## Security and Privacy

- This project does not read, copy, or forward any OAuth access token or refresh
  token; each CLI manages its own credentials.
- Never commit OAuth session material, API keys, confidential source documents,
  or generated confidential decks. Presentation workspaces, including
  `project_state.json`, stay outside this repository.
- Source ingestion reads local files only and makes no network requests.
- Test fixtures are synthetic; no real customer or third-party document is
  committed for testing purposes.

To report a security issue, see [`SECURITY.md`](SECURITY.md).

## Limitations

- The first version is `sequential_only`: one slide is generated at a time, and
  parallel generation is intentionally unsupported.
- Three CLIs must each be signed in to their own subscription account. This
  project neither provides nor manages any account or credential.
- The Codex built-in image tool currently produces relatively low resolution and
  does not accept an explicit resolution. Higher resolution requires switching to
  the API-key path this project retains (`skills/agy-ppt/scripts/image_gen.py`),
  which is never triggered automatically.
- Generated slides are full-page images: the text, shapes, and layout inside a
  slide cannot be edited individually. For an editable deck, the upstream
  author's
  [`image-to-editable-ppt-skill`](https://github.com/ningzimu/image-to-editable-ppt-skill)
  can convert them.
- Quota exhaustion cannot currently be determined deterministically from Codex
  CLI subprocess evidence (return code / stderr). A dedicated error class will be
  added only when an explicit machine-readable usage/quota/rate-limit signal
  appears. Operators can record quota exhaustion as an operator-confirmed
  decision, which is never forged into a worker error code.
- Source grounding bundles no universal PDF/DOCX/HTML parser: extracting source
  text and segmenting sources is AGY's responsibility. The deterministic
  validator does not replace Content QA and does not independently judge whether
  content is factually true.
- Source ingestion (released in v0.3.0) currently supports only local PDF with
  an extractable text layer, Markdown, plain text, DOCX, and static HTML. Remote
  sources must be fetched explicitly through the Phase 13.5 acquisition layer,
  which supports public unauthenticated HTTP/HTTPS URLs only: authenticated or
  private web sources, web crawling, browser rendering, and OCR are not
  supported. DOCX provides no rendered-page locators and no Word visual-layout
  reconstruction, and its headers, footers, footnotes, comments, and embedded
  image text are not ingested. HTML executes no JavaScript, applies no CSS, and
  loads no external resources, so JavaScript-generated content is not ingested.
  Remote acquisition is **not** a hardened SSRF sandbox and retains a
  DNS-rebinding limitation. Extraction is not semantic segmentation, and AGY
  remains the semantic authority.

## Upstream & Attribution

This project is derived from
[`ningzimu/codex-ppt-skill`](https://github.com/ningzimu/codex-ppt-skill)
(MIT License, `Copyright (c) 2026 ningzimu`). This repository contains no full
upstream checkout: `skills/agy-ppt/` holds implementations derived from and
adapted from upstream, while the unmodified upstream implementation is resolved
as an external runtime dependency when genuinely needed — see
[codex-ppt Dependency](#codex-ppt-dependency) above.

- Detailed comparison:
  [`skills/agy-ppt/docs/upstream-differences.md`](skills/agy-ppt/docs/upstream-differences.md)
- Full list of third-party sources and derived/dependent content:
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

**agy-ppt is not affiliated with or endorsed by the upstream author.**

## License

MIT License. See [`LICENSE`](LICENSE), which retains both upstream's
`Copyright (c) 2026 ningzimu` and the copyright for this project's own
contributions.

## Acknowledgements

- Thanks to
  [`ningzimu/codex-ppt-skill`](https://github.com/ningzimu/codex-ppt-skill) for
  providing a mature image-based PPT generation workflow and style library as a
  foundation.
