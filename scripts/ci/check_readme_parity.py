#!/usr/bin/env python3
"""Deterministic verification gate for bilingual README parity and link integrity.

Validates:
1. Both README.md (Traditional Chinese) and README_en.md (English) exist.
2. Both READMEs contain valid repository-relative mutual links.
3. Every local repository-relative link in both READMEs resolves to an existing file
   (and heading anchor if specified).
4. Semantic section parity between README.md and README_en.md across key architectural,
   installation, workflow, testing, security, and limitation topics.

Usage:
    python3 scripts/ci/check_readme_parity.py
    python3 scripts/ci/check_readme_parity.py --repo-root /path/to/repo
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple


class LinkCheckResult(NamedTuple):
    source_file: str
    link_text: str
    target: str
    error: str


# Semantic sections that must be present in both READMEs (key concepts / pairs)
# Format: (label, regex_for_zh, regex_for_en)
SEMANTIC_TOPIC_PAIRS: list[tuple[str, str, str]] = [
    ("Standalone Repository", r"^##\s+Standalone Repository", r"^##\s+Standalone Repository"),
    ("Purpose / Summary", r"^##\s+(?:一句話用途|What It Does)", r"^##\s+What It Does"),
    ("Architecture", r"^##\s+Architecture", r"^##\s+Architecture"),
    ("Key Features", r"^##\s+Key Features", r"^##\s+Key Features"),
    ("OAuth / Subscription Runtime", r"^##\s+OAuth / Subscription Runtime", r"^##\s+OAuth / Subscription Runtime"),
    ("No Production API-Key Fallback", r"^##\s+No Production API-Key Fallback", r"^##\s+No Production API-Key Fallback"),
    ("codex-ppt Dependency", r"^##\s+codex-ppt Dependency", r"^##\s+codex-ppt Dependency"),
    ("Installation", r"^##\s+Installation", r"^##\s+Installation"),
    ("Requirements", r"^###\s+.*(?:需求|Requirements)", r"^###\s+Requirements"),
    ("Quick Start", r"^##\s+Quick Start", r"^##\s+Quick Start"),
    ("External Workspace", r"^##\s+External Project Workspace", r"^##\s+External Project Workspace"),
    ("State / Resume / Recovery", r"^##\s+State / Resume / Recovery", r"^##\s+State / Resume / Recovery"),
    ("Source Grounding", r"^##\s+Source Grounding", r"^##\s+Source Grounding"),
    ("Source Ingestion", r"^##\s+Source Ingestion", r"^##\s+Source Ingestion"),
    ("Remote Acquisition", r"^##\s+Remote Source Acquisition", r"^##\s+Remote Source Acquisition"),
    ("Testing", r"^##\s+Testing", r"^##\s+Testing"),
    ("CI Quality Gates", r"^###\s+.*(?:CI 品質門檻|CI Quality Gates)", r"^###\s+.*(?:CI Quality Gates)"),
    ("Security and Privacy", r"^##\s+Security and Privacy", r"^##\s+Security and Privacy"),
    ("Limitations", r"^##\s+Limitations", r"^##\s+Limitations"),
    ("Upstream & Attribution", r"^##\s+Upstream & Attribution", r"^##\s+Upstream & Attribution"),
    ("License", r"^##\s+License", r"^##\s+License"),
]


def github_slug(title: str) -> str:
    """Derive GitHub-compatible anchor slug from heading text."""
    s = title.strip().lower()
    s = re.sub(r'[^\w\s-]', '', s)
    s = s.replace(' ', '-')
    return s


def extract_headings_and_slugs(text: str) -> set[str]:
    """Extract all markdown heading slugs from text."""
    headings = re.findall(r'^#+\s+(.+)$', text, flags=re.MULTILINE)
    return {github_slug(h) for h in headings}


def find_markdown_links(text: str) -> list[tuple[str, str]]:
    """Extract all [text](url) links from markdown text."""
    # Match markdown links while ignoring image references ![alt](url)
    matches = re.findall(r'(?<!\!)\[([^\]]+)\]\(([^)]+)\)', text)
    return [(text.strip(), url.strip()) for text, url in matches]


def check_readme_links(
    readme_path: Path,
    repo_root: Path,
) -> list[LinkCheckResult]:
    """Validate all repository-relative links in a README file."""
    if not readme_path.is_file():
        return [LinkCheckResult(str(readme_path), "", "", "File does not exist")]

    text = readme_path.read_text(encoding="utf-8")
    own_slugs = extract_headings_and_slugs(text)
    links = find_markdown_links(text)
    broken: list[LinkCheckResult] = []

    for link_text, target in links:
        # Ignore external links, mailto, etc.
        if target.startswith(("http://", "https://", "mailto:", "ftp://")):
            continue

        # In-page anchor link: #heading
        if target.startswith("#"):
            slug = target.lstrip("#")
            if slug not in own_slugs:
                broken.append(LinkCheckResult(
                    source_file=readme_path.name,
                    link_text=link_text,
                    target=target,
                    error=f"In-page anchor '{slug}' does not match any heading in {readme_path.name}",
                ))
            continue

        # Target is a relative file path, optionally with an anchor: path/to/file.md#anchor
        parts = target.split("#", 1)
        rel_path = parts[0]
        anchor = parts[1] if len(parts) > 1 else None

        target_file = (readme_path.parent / rel_path).resolve()
        try:
            target_file.relative_to(repo_root.resolve())
        except ValueError:
            broken.append(LinkCheckResult(
                source_file=readme_path.name,
                link_text=link_text,
                target=target,
                error=f"Path '{rel_path}' escapes repository root",
            ))
            continue

        if not target_file.exists():
            broken.append(LinkCheckResult(
                source_file=readme_path.name,
                link_text=link_text,
                target=target,
                error=f"Referenced target file does not exist: {rel_path}",
            ))
            continue

        if anchor and target_file.suffix in (".md", ".markdown"):
            target_text = target_file.read_text(encoding="utf-8", errors="ignore")
            target_slugs = extract_headings_and_slugs(target_text)
            if anchor not in target_slugs:
                broken.append(LinkCheckResult(
                    source_file=readme_path.name,
                    link_text=link_text,
                    target=target,
                    error=f"Anchor '{anchor}' not found in target file {rel_path}",
                ))

    return broken


def check_mutual_links(
    readme_zh: Path,
    readme_en: Path,
) -> list[str]:
    """Verify README.md and README_en.md link to each other."""
    errors: list[str] = []
    if not readme_zh.is_file():
        return ["README.md does not exist"]
    if not readme_en.is_file():
        return ["README_en.md does not exist"]

    zh_text = readme_zh.read_text(encoding="utf-8")
    en_text = readme_en.read_text(encoding="utf-8")

    # README.md must link to README_en.md
    if "README_en.md" not in zh_text:
        errors.append("README.md does not contain a repository-relative link to README_en.md")

    # README_en.md must link to README.md
    if "README.md" not in en_text:
        errors.append("README_en.md does not contain a repository-relative link to README.md")

    return errors


def check_semantic_parity(
    readme_zh: Path,
    readme_en: Path,
) -> list[str]:
    """Verify both READMEs maintain semantic parity across major sections."""
    errors: list[str] = []
    zh_text = readme_zh.read_text(encoding="utf-8")
    en_text = readme_en.read_text(encoding="utf-8")

    for label, zh_pattern, en_pattern in SEMANTIC_TOPIC_PAIRS:
        zh_found = bool(re.search(zh_pattern, zh_text, flags=re.MULTILINE))
        en_found = bool(re.search(en_pattern, en_text, flags=re.MULTILINE))

        if not zh_found and not en_found:
            errors.append(f"Section '{label}' missing from both README.md and README_en.md")
        elif not zh_found:
            errors.append(f"Section '{label}' present in README_en.md but missing from README.md")
        elif not en_found:
            errors.append(f"Section '{label}' present in README.md but missing from README_en.md")

    return errors


def run_readme_parity_checks(repo_root: Path) -> tuple[bool, list[str]]:
    """Run all README parity and link checks against the repository."""
    readme_zh = repo_root / "README.md"
    readme_en = repo_root / "README_en.md"

    errors: list[str] = []

    # 1. Existence and mutual cross-linking
    mutual_errors = check_mutual_links(readme_zh, readme_en)
    errors.extend(mutual_errors)

    if not readme_zh.is_file() or not readme_en.is_file():
        return False, errors

    # 2. Local relative link validation in both files
    zh_link_errors = check_readme_links(readme_zh, repo_root)
    for err in zh_link_errors:
        errors.append(f"[{err.source_file}] Broken link '{err.target}' ({err.link_text}): {err.error}")

    en_link_errors = check_readme_links(readme_en, repo_root)
    for err in en_link_errors:
        errors.append(f"[{err.source_file}] Broken link '{err.target}' ({err.link_text}): {err.error}")

    # 3. Semantic parity across required sections
    parity_errors = check_semantic_parity(readme_zh, readme_en)
    errors.extend(parity_errors)

    success = len(errors) == 0
    return success, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check bilingual README parity and link integrity.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path to repository root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    print(f"Checking README bilingual parity and links in {repo_root}...")

    success, errors = run_readme_parity_checks(repo_root)
    if success:
        print("README BILINGUAL GATE: PASS")
        print("- README.md and README_en.md exist and cross-link.")
        print("- All local repository-relative links resolve successfully (0 broken).")
        print("- Semantic topic parity verified across all 20 required sections.")
        return 0
    else:
        print(f"README BILINGUAL GATE: FAIL ({len(errors)} errors found)", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
