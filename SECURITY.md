# Security Policy

## What must never be committed to this repository

Do not commit, attach, or paste into an issue/PR any of the following:

- OAuth sessions, refresh tokens, access tokens, or ID tokens
- API keys (e.g. `OPENAI_API_KEY`, `GEMINI_API_KEY`, any provider key)
- GitHub personal access tokens, SSH/private keys, or other credential
  material
- Cookies or `Authorization` header values
- Confidential source documents (contracts, customer documents, internal
  reports) or anything derived from them
- Generated decks (`.pptx`) or generated slide images produced from private
  or confidential project workspaces
- `project_state.json`, Codex invocation ledgers, or runtime logs from a real
  (non-test) project workspace

Environment variable **names** (e.g. `OPENAI_API_KEY`, `CODEX_HOME`) are fine
to reference in documentation and code. Their **values** must never appear in
source, tests, issues, or commit messages.

The adapter and bridge code in this repository (`scripts/codex_image_adapter.py`,
`scripts/kiro_acp_bridge.py`) already strip API-key-style environment
variables from child processes and redact credential-shaped strings before
returning any result. If you find a case where that redaction fails, please
report it privately (see below) rather than opening a public issue with the
leaked value included.

## Reporting a security issue

If you believe you have found a security issue (e.g. a credential leak path,
an unsafe path-traversal, or a way this project could be made to call a paid
API without the user's consent), please open a private report through
GitHub's "Report a vulnerability" feature on this repository, or open a
regular issue describing the problem **without** including any real secret
value, token, or confidential document.

Please include:

- the affected file(s) and, if applicable, the exact command or workflow
  that triggers the issue
- what you expected to happen vs. what actually happened
- whether real credentials or confidential data were involved (without
  pasting them)

There is no guaranteed response time; this is a community-maintained project.

## Scope

This policy covers the source code, tests, schemas, prompts, and
documentation in this repository. It does not cover the security posture of
the Codex CLI, Kiro CLI, or any third-party API provider you choose to
configure yourself.
