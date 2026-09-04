# AGENTS.md

Contribution governance for `agy-ppt`. This file is the single authoritative
source for contribution flow, PR titles, changelog format, and release process.
It applies to human contributors and to AI agents working in this repository.

## Contribution Flow

- All non-trivial changes must go through a pull request. Do not push
  release-preparation or governance changes directly to `main`.
- PR titles must follow Conventional Commit style: a type prefix, a colon, and a
  short imperative summary.
- Use one of these types:
  - `feat:` — a new user-visible capability
  - `fix:` — a bug fix
  - `docs:` — documentation, changelog, or governance only
  - `test:` — tests only
  - `refactor:` — behaviour-preserving restructuring
  - `chore:` — build, dependency, or repository housekeeping
- Examples:
  - `feat: add source coverage accounting`
  - `fix: reject stale grounding evidence on digest change`
  - `docs: align repository contribution governance`
- Commit messages, PR titles, changelog entries, and code comments in shared
  contracts are written in English.
- User-facing documentation (`skills/agy-ppt/docs/**`) and GitHub Release notes
  are written primarily in Traditional Chinese, matching the existing
  documentation set.
- The repository maintains a bilingual public README:
  - `README.md` — the primary Traditional Chinese README
  - `README_en.md` — the official English README
  Both must link to each other with repository-relative Markdown links.
- When a pull request changes public user-facing behaviour, reviewers must ask
  whether `README.md` needs an update and whether `README_en.md` needs the same
  semantic update. The two READMEs must keep equivalent semantic coverage; they
  do not need to be literal line-for-line translations. A capability must not be
  documented in only one language without a stated reason.
- Translating every file under `skills/agy-ppt/docs/**` is not required.

## Release PR Naming

- A release PR whose content is documentation, changelog, and release evidence
  only uses:
  - `docs: prepare vX.Y.Z release`
- A release PR whose primary content is a production fix or feature uses the
  real change type instead, for example `fix:` or `feat:`. Do not relabel a
  substantive change as `docs:` merely because it is bundled into a release.

## Changelog

- User-visible changes must update `CHANGELOG.md`.
- Add new entries under `## [Unreleased]`.
- On release, rename that section to `## [X.Y.Z] - YYYY-MM-DD` and open a fresh
  empty `## [Unreleased]` above it.
- Use these section headings, matching the existing file:
  - `### Added`
  - `### Changed`
  - `### Fixed`
  - `### Removed`
- Changelog entries are written in English.
- Changelog entries must include the pull request reference, for example `(#12)`.
- Only a real, already-created GitHub PR number may be used. Fabricated,
  reserved, and predicted PR numbers are forbidden. Obtain the number after
  opening the PR, then add the references in a follow-up commit on the same
  branch.

## Release Process

- Versions use SemVer.
- Git tags must use a leading `v`, for example `v0.2.0`.
- Tags are annotated and must point at the merged release commit on `main`.
- GitHub Release notes must correspond to the matching `CHANGELOG.md` version
  section. They may be written directly so that they can carry the actual
  release-gate test results and the release-specific boundaries, but they must
  not claim capabilities absent from that changelog section.
- Never rewrite or move a published tag or release.

## Verification

- Run the full deterministic test suite before opening a release PR, and report
  the actual results from that run. Historical numbers must not be presented as
  the current release gate.
- Deterministic tests must not consume AI subscription quota. Live,
  quota-consuming tests are opt-in only.
- Before opening a PR, audit the diff for credentials, private absolute paths,
  and confidential artifacts.
- If GitHub workflow YAML is ever added, verify it parses, and syntax-check
  shell snippets with `bash -n`, when practical.

## Prohibited

- Force pushes and history rewrites on `main`.
- Fabricated PR numbers, test results, or validation evidence.
- Committing credentials, OAuth session material, confidential source
  documents, or generated confidential decks.

## Historical Exception

Historical commits and PRs created before this policy alignment are not
rewritten solely to normalize titles.
