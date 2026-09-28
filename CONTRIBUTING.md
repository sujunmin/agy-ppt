# Contributing to agy-ppt

Thanks for helping improve `agy-ppt`. Bug fixes, documentation, tests,
presentation-quality and layout improvements, PowerPoint compatibility fixes,
and new capabilities are all welcome.

Small, focused pull requests can be submitted directly. Please open an issue or
discussion first when a change would alter the product workflow, AGY's semantic
authority, a frozen contract, or a major architectural boundary.

## Product boundaries

The product runtime is:

```text
User
  → AGY
  → Codex presentation production worker
  → agy-ppt
  → PPTX
```

AGY remains the sole product orchestrator and semantic authority. It owns claim
meaning, source support, content coverage, segmentation, semantic QA, and
grounding decisions.

Jev is bounded development-time decision assistance only. It must not become a
product-runtime dependency, CI dependency, evidence authority, or release
authority. CI must pass without `TYPESAFE_API_KEY`.

## Development setup

Use Python 3.11 and the repository dependency declaration:

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r skills/agy-ppt/requirements.txt
```

Do not install the obsolete `docx` package; the project uses `python-docx`.

Run the canonical deterministic checks before opening a pull request:

```bash
.venv/bin/python -m unittest discover \
  -s skills/agy-ppt/tests \
  -t skills/agy-ppt/tests \
  -p "test_*.py"
.venv/bin/python skills/agy-ppt/scripts/run_recovery_tests.py
.venv/bin/python scripts/ci/check_readme_parity.py
.venv/bin/python scripts/ci/check_repository_hygiene.py
.venv/bin/python scripts/ci/check_frozen_contracts.py --base-ref origin/main
git diff --check
```

Live or quota-consuming AI checks are opt-in and are never part of the
deterministic CI suite.

## Visual and PowerPoint changes

Passing unit tests alone does not prove presentation quality. Any change that
affects generated output should be evaluated using rendered output.

Where practical, include:

- the reproduction prompt or input;
- the generated PPTX;
- a rendered PDF or slide images;
- a before/after comparison;
- the PowerPoint/client environment; and
- relevant deterministic tests.

Do not commit large generated binaries unless they are deliberate, reviewed
fixtures. Link or otherwise retain qualification artifacts outside the source
repository when possible, and never commit confidential decks.

## Pull requests

- Keep the change focused and use a Conventional Commit-style PR title.
- Explain the motivation, tests, compatibility impact, and architecture impact.
- Update both `README.md` and `README_en.md` when public behavior changes.
- Call out any frozen-contract change explicitly; such changes require the
  repository's governed exception process.
- Do not add credentials, private paths, generated confidential artifacts, or
  an unreviewed network/runtime dependency.
- Let the required `deterministic` and `repository` checks complete. Do not
  bypass branch protection.

Repository contribution, changelog, and release governance is defined in
`AGENTS.md`.

## 貢獻者摘要

歡迎提交錯誤修正、文件、測試、簡報品質與版面改善、PowerPoint 相容性修正及新功能。小而聚焦的 PR 可直接提出；若會改變產品流程、AGY 語意權限、凍結契約或主要架構，請先開 issue／discussion。視覺變更必須檢查實際 render，不能只以單元測試通過作為品質證明。
