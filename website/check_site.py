#!/usr/bin/env python3
"""Dependency-free structural, link, privacy, and base-path checks for the site."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from build import ROOT, WEBSITE


BASE_URL = "https://sujunmin.github.io/agy-ppt/"
PAGES = (Path("index.html"), Path("en/index.html"))
REQUIRED_META = {
    "name:description",
    "property:og:title",
    "property:og:description",
    "property:og:url",
    "property:og:image",
    "name:twitter:card",
    "name:twitter:image",
}
REQUIRED_COMMANDS = (
    "git clone https://github.com/sujunmin/agy-ppt.git",
    "cd agy-ppt",
    "python3 skills/agy-ppt/scripts/codex_ppt_runtime.py bootstrap",
    "mkdir -p ~/.gemini/config/skills",
    "rsync -a --delete ./skills/agy-ppt/ ~/.gemini/config/skills/agy-ppt/",
)
PRIVATE_PATTERNS = (
    "/Users/",
    "/private/tmp/",
    "TYPESAFE_API_KEY",
    "thread_id",
    "codex_thread_id",
    "authorization: bearer",
    "BEGIN OPENSSH PRIVATE KEY",
)
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class PageAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.images: list[dict[str, str | None]] = []
        self.links: list[dict[str, str | None]] = []
        self.scripts: list[dict[str, str | None]] = []
        self.data_assets: list[dict[str, str | None]] = []
        self.carousels: list[dict[str, str | None]] = []
        self.carousel_dots: list[dict[str, str | None]] = []
        self.carousel_buttons: list[dict[str, str | None]] = []
        self.meta: set[str] = set()
        self.h1_count = 0
        self.errors: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if data.get("id"):
            if data["id"] in self.ids:
                self.errors.append(f"duplicate id: {data['id']}")
            self.ids.add(data["id"])
        if tag == "h1":
            self.h1_count += 1
        if tag == "img":
            self.images.append(data)
        if tag == "a":
            self.links.append(data)
        if tag == "script":
            self.scripts.append(data)
        if data.get("data-src"):
            self.data_assets.append(data)
        if "data-carousel" in data:
            self.carousels.append(data)
        if data.get("data-slide-to") is not None:
            self.carousel_dots.append(data)
        if any(name in data for name in ("data-previous", "data-next", "data-autoplay-toggle")):
            self.carousel_buttons.append(data)
        if tag == "meta":
            key = "name" if data.get("name") else "property"
            if data.get(key):
                self.meta.add(f"{key}:{data[key]}")
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            self.errors.append(f"void element has closing tag: {tag}")
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"mismatched closing tag: {tag}")
            return
        self.stack.pop()


def audit_page(site_root: Path, relative_page: Path) -> list[str]:
    errors: list[str] = []
    page = site_root / relative_page
    parser = PageAudit()
    parser.feed(page.read_text(encoding="utf-8"))
    parser.close()
    if parser.stack:
        errors.append(f"{relative_page}: unclosed tags: {parser.stack}")
    errors.extend(f"{relative_page}: {error}" for error in parser.errors)
    if parser.h1_count != 1:
        errors.append(f"{relative_page}: expected one h1, found {parser.h1_count}")
    if any(not image.get("alt", "").strip() for image in parser.images):
        errors.append(f"{relative_page}: every image needs useful alt text")
    if REQUIRED_META - parser.meta:
        errors.append(f"{relative_page}: missing metadata {sorted(REQUIRED_META - parser.meta)}")

    source_text = page.read_text(encoding="utf-8")
    canonical = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', source_text)
    if not canonical or not canonical.group(1).startswith(BASE_URL):
        errors.append(f"{relative_page}: canonical URL must use the /agy-ppt/ Pages base path")
    for attr_group in (parser.links, parser.images, parser.scripts, parser.data_assets):
        for attrs in attr_group:
            for key in ("href", "src", "data-src"):
                value = attrs.get(key)
                if not value:
                    continue
                parsed = urlsplit(value)
                if parsed.scheme or parsed.netloc or value.startswith("#"):
                    continue
                if value.startswith("/"):
                    errors.append(f"{relative_page}: root-relative asset/link breaks project-site base path: {value}")
                    continue
                target = (page.parent / unquote(parsed.path)).resolve()
                if target.is_dir():
                    target /= "index.html"
                if not target.is_file():
                    errors.append(f"{relative_page}: missing local target {value}")
            if attrs.get("target") == "_blank" and "noopener" not in (attrs.get("rel") or ""):
                errors.append(f"{relative_page}: external new-tab link should include rel=noopener")

    if len(parser.carousels) != 2:
        errors.append(f"{relative_page}: expected two named example carousels, found {len(parser.carousels)}")
    elif any(item.get("role") != "region" or item.get("aria-roledescription") != "carousel" or not item.get("aria-label") for item in parser.carousels):
        errors.append(f"{relative_page}: each carousel needs a named accessible region")
    if len(parser.carousel_dots) != 8:
        errors.append(f"{relative_page}: expected four slide selectors per carousel, found {len(parser.carousel_dots)}")
    else:
        indices = [item.get("data-slide-to") for item in parser.carousel_dots]
        if indices != ["0", "1", "2", "3"] * 2:
            errors.append(f"{relative_page}: each carousel must provide ordered selectors for slides 1–4")
        if any(not item.get("data-src") or not item.get("data-alt") or not item.get("aria-label") for item in parser.carousel_dots):
            errors.append(f"{relative_page}: every slide selector needs a local image, alt text, and accessible label")
    for attribute in ("data-previous", "data-next", "data-autoplay-toggle"):
        if sum(attribute in item for item in parser.carousel_buttons) != 2:
            errors.append(f"{relative_page}: expected one {attribute} control in each carousel")

    for command in REQUIRED_COMMANDS:
        if command not in source_text:
            errors.append(f"{relative_page}: quick-start command is missing: {command}")
    if relative_page == Path("index.html") and 'href="./en/"' not in source_text:
        errors.append("Traditional Chinese page must link to the English page with a relative URL")
    if relative_page == Path("en/index.html") and 'href="../"' not in source_text:
        errors.append("English page must link to Traditional Chinese with a relative URL")
    return errors


def main() -> None:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agy-ppt-pages-check-") as temporary:
        site_root = Path(temporary) / "site"
        subprocess.run(
            [sys.executable, str(WEBSITE / "build.py"), "--output-dir", str(site_root)],
            check=True,
        )
        for page in PAGES:
            errors.extend(audit_page(site_root, page))
        images = sorted((site_root / "assets/img").glob("*.png"))
        if len(images) != 8:
            errors.append(f"expected 8 approved slide previews in the artifact, found {len(images)}")
        artifact_files = [p for p in site_root.rglob("*") if p.is_file()]
        for path in artifact_files:
            if path.suffix.lower() in {".pptx", ".pdf"}:
                errors.append(f"qualification or presentation binary must not enter Pages artifact: {path.name}")
            if path.suffix.lower() in {".html", ".css", ".js"}:
                content = path.read_text(encoding="utf-8")
                for marker in PRIVATE_PATTERNS:
                    if marker.lower() in content.lower():
                        errors.append(f"private/internal marker found in Pages artifact: {marker}")
        css = (site_root / "assets/css/site.css").read_text(encoding="utf-8")
        if "@import" in css or "url(http" in css:
            errors.append("CSS must not depend on external font/CDN assets")

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("WEBSITE CHECK: PASS (bilingual structure, metadata, links, base path, assets, privacy, and quick-start parity)")


if __name__ == "__main__":
    main()
