#!/usr/bin/env python3
"""Deterministic verification gate for repository hygiene, private paths, and credentials.

Validates:
1. Prohibited tracked artifacts:
   - No .env credential files
   - No .venv/ virtual environments
   - No __pycache__/ or compiled bytecode (*.pyc, *.pyo)
   - No temporary/partial download files (*.part)
   - No runtime public-source payloads (e.g. downloaded RFC 2119 / NIST runtime files)
   - No generated presentation files (*.pptx) or rendered slides (*.png) outside test fixtures
2. Private path gate:
   - No real hardcoded user absolute paths (/Users/<user>, /home/<user>, C:\\Users\\<user>)
     in production code, documentation, or contracts.
   - Documented allowlist for test fixtures verifying path handling or redaction.
3. Credential hygiene:
   - Low-false-positive scan for private key headers, tokens, and secret blocks.

Usage:
    python3 scripts/ci/check_repository_hygiene.py
    python3 scripts/ci/check_repository_hygiene.py --repo-root /path/to/repo
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

# Prohibited file path patterns (evaluated against git tracked files)
PROHIBITED_PATTERNS = [
    ".env",
    "*.env",
    ".env.*",
    "*.pyc",
    "*.pyo",
    "*.part",
    "*/__pycache__/*",
    "__pycache__/*",
    "*/.venv/*",
    ".venv/*",
    "*/.pytest_cache/*",
    ".pytest_cache/*",
    "*/rfc2119.txt",
    "rfc2119.txt",
    "*/NIST.AI.600-1.pdf",
    "NIST.AI.600-1.pdf",
    "*/src_rfc2119.txt",
    "src_rfc2119.txt",
]

# Patterns for generated runtime artifacts that must never be tracked in production
PROHIBITED_RUNTIME_PATTERNS = [
    "*.pptx",
    "slide_*.png",
    "src_*.txt",
    "src_*.json",
    "src_*.pdf",
    "src_*.docx",
    "src_*.html",
]

# Regex patterns detecting private local filesystem paths
PRIVATE_PATH_PATTERNS = [
    re.compile(r'/(?:Users|home)/[A-Za-z0-9_.-]+'),
    re.compile(r'[Cc]:\\Users\\[A-Za-z0-9_.-]+'),
]

# Documented allowlist for files containing synthetic path examples for test/verification
PRIVATE_PATH_ALLOWLIST = {
    # Test suite verifying subprocess / command / path handling with synthetic dummy paths
    "skills/agy-ppt/tests/test_codex_image_adapter.py",
    "skills/agy-ppt/tests/test_kiro_acp_bridge.py",
    # CI scripts and CI test fixtures themselves
    "scripts/ci/check_repository_hygiene.py",
    "skills/agy-ppt/tests/test_ci_gates.py",
}

# Unmistakable credential patterns (high confidence, low false-positive)
CREDENTIAL_PATTERNS = [
    (re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'), "Private key header"),
    (re.compile(r'(?i)(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}'), "GitHub personal access / oauth token"),
    (re.compile(r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*'), "Slack token"),
    (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS Access Key ID"),
]

# Allowlist for credential tests that intentionally inspect dummy token shapes
CREDENTIAL_ALLOWLIST = {
    "scripts/ci/check_repository_hygiene.py",
    "skills/agy-ppt/tests/test_ci_gates.py",
}


def list_tracked_files(repo_root: Path) -> list[str]:
    """Return list of all files tracked by git in repo_root."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def check_prohibited_artifacts(tracked_files: list[str]) -> list[str]:
    """Check that no prohibited artifacts are tracked in git."""
    errors: list[str] = []
    for rel_path in tracked_files:
        matched = False
        # Check standard prohibited patterns
        for pat in PROHIBITED_PATTERNS:
            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(Path(rel_path).name, pat):
                errors.append(f"Prohibited tracked artifact: '{rel_path}' matches rule '{pat}'")
                matched = True
                break

        if matched:
            continue

        # Check runtime artifact patterns
        for pat in PROHIBITED_RUNTIME_PATTERNS:
            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(Path(rel_path).name, pat):
                errors.append(f"Runtime presentation/extraction artifact tracked: '{rel_path}' matches '{pat}'")
                break

    return errors


def check_private_paths(repo_root: Path, tracked_files: list[str]) -> list[str]:
    """Scan tracked files for private user filesystem paths."""
    errors: list[str] = []
    for rel_path in tracked_files:
        if rel_path in PRIVATE_PATH_ALLOWLIST:
            continue

        file_path = repo_root / rel_path
        if not file_path.is_file():
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            errors.append(f"Failed to read '{rel_path}' for path scan: {exc}")
            continue

        for pat in PRIVATE_PATH_PATTERNS:
            matches = pat.findall(content)
            if matches:
                unique_matches = sorted(set(matches))
                errors.append(
                    f"Private absolute path found in '{rel_path}': {unique_matches}"
                )

    return errors


def check_credential_hygiene(repo_root: Path, tracked_files: list[str]) -> list[str]:
    """Scan tracked files for unmistakable credential artifacts."""
    errors: list[str] = []
    for rel_path in tracked_files:
        if rel_path in CREDENTIAL_ALLOWLIST:
            continue

        file_path = repo_root / rel_path
        if not file_path.is_file():
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            errors.append(f"Failed to read '{rel_path}' for credential scan: {exc}")
            continue

        for pat, desc in CREDENTIAL_PATTERNS:
            if pat.search(content):
                errors.append(f"Potential credential leak in '{rel_path}': {desc}")

    return errors


def run_hygiene_checks(repo_root: Path) -> tuple[bool, list[str]]:
    """Run all hygiene, private path, and credential checks."""
    tracked_files = list_tracked_files(repo_root)
    errors: list[str] = []

    artifact_errors = check_prohibited_artifacts(tracked_files)
    errors.extend(artifact_errors)

    path_errors = check_private_paths(repo_root, tracked_files)
    errors.extend(path_errors)

    cred_errors = check_credential_hygiene(repo_root, tracked_files)
    errors.extend(cred_errors)

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check repository hygiene, private paths, and credentials.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path to repository root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    print(f"Running repository hygiene, private path, and credential audit in {repo_root}...")

    success, errors = run_hygiene_checks(repo_root)
    if success:
        print("REPOSITORY HYGIENE GATE: PASS")
        print("- 0 prohibited tracked artifacts (.env, .venv, *.pyc, runtime payloads, pptx).")
        print("- 0 private absolute user paths leaked outside documented test allowlist.")
        print("- 0 credential or private key blocks detected.")
        return 0
    else:
        print(f"REPOSITORY HYGIENE GATE: FAIL ({len(errors)} violations found)", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
