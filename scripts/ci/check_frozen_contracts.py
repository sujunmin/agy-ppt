#!/usr/bin/env python3
"""Deterministic verification gate for Frozen Phase 12 and Phase 13 production contracts.

Designated Frozen Production Surfaces:
  Phase 12:
    - skills/agy-ppt/scripts/source_grounding.py
    - skills/agy-ppt/scripts/validate_source_grounding.py
    - skills/agy-ppt/schemas/source_inventory.schema.json
    - skills/agy-ppt/schemas/claim_traceability.schema.json
    - skills/agy-ppt/schemas/source_coverage.schema.json
    - skills/agy-ppt/schemas/source_grounded_qa.schema.json
    - skills/agy-ppt/schemas/project_state.schema.json
    - skills/agy-ppt/scripts/project_state.py
    - skills/agy-ppt/scripts/assemble_ppt.py
    - skills/agy-ppt/scripts/codex_image_adapter.py
    - skills/agy-ppt/scripts/kiro_acp_bridge.py

  Phase 13:
    - skills/agy-ppt/scripts/source_ingestion.py
    - skills/agy-ppt/scripts/source_acquisition.py

Contract Policy:
- A pull request that modifies any designated Frozen file without the maintainer
  approval label 'frozen-contract-change-approved' fails immediately.
- If the maintainer label 'frozen-contract-change-approved' is attached to the PR,
  the gate logs explicit approval notice and exits 0. All other regression CI gates
  remain mandatory.
- On push to main, the guard verifies all designated Frozen files remain present and accounted for.

Usage:
    python3 scripts/ci/check_frozen_contracts.py [--base-ref origin/main] [--labels "label1,label2"]
    python3 scripts/ci/check_frozen_contracts.py --changed-files file1 file2
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

FROZEN_FILES: tuple[str, ...] = (
    # Phase 12: Source Grounding & Project State
    "skills/agy-ppt/scripts/source_grounding.py",
    "skills/agy-ppt/scripts/validate_source_grounding.py",
    "skills/agy-ppt/schemas/source_inventory.schema.json",
    "skills/agy-ppt/schemas/claim_traceability.schema.json",
    "skills/agy-ppt/schemas/source_coverage.schema.json",
    "skills/agy-ppt/schemas/source_grounded_qa.schema.json",
    "skills/agy-ppt/schemas/project_state.schema.json",
    "skills/agy-ppt/scripts/project_state.py",
    "skills/agy-ppt/scripts/assemble_ppt.py",
    "skills/agy-ppt/scripts/codex_image_adapter.py",
    "skills/agy-ppt/scripts/kiro_acp_bridge.py",
    # Phase 13: Source Ingestion & Remote Acquisition
    "skills/agy-ppt/scripts/source_ingestion.py",
    "skills/agy-ppt/scripts/source_acquisition.py",
)

APPROVAL_LABEL = "frozen-contract-change-approved"


def get_changed_files_from_git(repo_root: Path, base_ref: str) -> list[str]:
    """Retrieve list of files changed between base_ref and HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        # Fallback to diff against HEAD~1 if base_ref is not resolvable
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1...HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        return []


def check_frozen_modifications(
    changed_files: list[str],
    labels: list[str],
) -> tuple[bool, list[str], bool]:
    """Inspect changed files for frozen contracts.
    
    Returns:
        (passed, modified_frozen_files, is_approved)
    """
    normalized_changed = {f.replace("\\", "/") for f in changed_files}
    frozen_set = set(FROZEN_FILES)

    touched = sorted(normalized_changed.intersection(frozen_set))
    if not touched:
        return True, [], False

    # Check for maintainer approval label
    clean_labels = [l.strip().lower() for l in labels]
    has_approval = APPROVAL_LABEL.lower() in clean_labels

    if has_approval:
        return True, touched, True
    else:
        return False, touched, False


def verify_frozen_files_exist(repo_root: Path) -> list[str]:
    """Verify that all designated frozen files exist in the repository."""
    missing: list[str] = []
    for rel_path in FROZEN_FILES:
        target = repo_root / rel_path
        if not target.is_file():
            missing.append(rel_path)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Frozen Contract modifications and approval.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path to repository root",
    )
    parser.add_argument(
        "--base-ref",
        type=str,
        default=os.environ.get("GITHUB_BASE_REF", "origin/main"),
        help="Git base reference for PR diff (default: GITHUB_BASE_REF or origin/main)",
    )
    parser.add_argument(
        "--labels",
        type=str,
        default=os.environ.get("PR_LABELS", ""),
        help="Comma-separated list of labels attached to the PR",
    )
    parser.add_argument(
        "--changed-files",
        nargs="*",
        default=None,
        help="Explicit list of changed files (overrides git diff)",
    )
    parser.add_argument(
        "--verify-all-exist",
        action="store_true",
        help="Verify all designated frozen files exist in repository",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    # If requested or in non-PR push mode, verify all frozen files exist
    missing = verify_frozen_files_exist(repo_root)
    if missing:
        print("FROZEN CONTRACT GUARD: FAIL (missing frozen files)", file=sys.stderr)
        for m in missing:
            print(f"  - Missing designated frozen file: {m}", file=sys.stderr)
        return 1

    if args.verify_all_exist:
        print(f"FROZEN CONTRACT GUARD: All {len(FROZEN_FILES)} designated frozen files verified present.")
        return 0

    labels = [l.strip() for l in args.labels.split(",") if l.strip()]

    if args.changed_files is not None:
        changed_files = args.changed_files
    else:
        changed_files = get_changed_files_from_git(repo_root, args.base_ref)

    passed, touched, is_approved = check_frozen_modifications(changed_files, labels)

    if not touched:
        print(f"FROZEN CONTRACT GUARD: PASS (0 frozen files modified out of {len(changed_files)} changed files).")
        return 0

    if is_approved:
        print("=" * 70)
        print("FROZEN PRODUCTION CONTRACT MODIFIED WITH MAINTAINER APPROVAL:")
        for t in touched:
            print(f"  - {t}")
        print(f"Maintainer approval label '{APPROVAL_LABEL}' verified.")
        print("All regular regression CI tests remain mandatory.")
        print("=" * 70)
        return 0
    else:
        print("=" * 70, file=sys.stderr)
        print("FROZEN PRODUCTION CONTRACT MODIFIED", file=sys.stderr)
        print("The following designated Frozen Phase 12 / Phase 13 production files were modified:", file=sys.stderr)
        for t in touched:
            print(f"  - {t}", file=sys.stderr)
        print(f"\nPolicy requires explicit maintainer approval via GitHub PR label: '{APPROVAL_LABEL}'.", file=sys.stderr)
        print("If this modification was intentional, request a repository maintainer apply the label.", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
