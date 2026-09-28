#!/usr/bin/env python3
"""Assemble the static GitHub Pages artifact from reviewed source assets."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
PREVIEWS = {
    "dense-slide-1.png": ROOT / "examples/dense-executive/previews/slide-1.png",
    "dense-slide-2.png": ROOT / "examples/dense-executive/previews/slide-2.png",
    "dense-slide-3.png": ROOT / "examples/dense-executive/previews/slide-3.png",
    "dense-slide-4.png": ROOT / "examples/dense-executive/previews/slide-4.png",
    "balanced-slide-1.png": ROOT / "examples/balanced-executive/previews/slide-1.png",
    "balanced-slide-2.png": ROOT / "examples/balanced-executive/previews/slide-2.png",
    "balanced-slide-3.png": ROOT / "examples/balanced-executive/previews/slide-3.png",
    "balanced-slide-4.png": ROOT / "examples/balanced-executive/previews/slide-4.png",
}


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise SystemExit(f"Refusing to build into non-empty output directory: {output}")

    shutil.copy2(WEBSITE / "index.html", output / "index.html")
    shutil.copytree(WEBSITE / "en", output / "en")
    shutil.copytree(WEBSITE / "assets", output / "assets")

    image_dir = output / "assets" / "img"
    image_dir.mkdir(parents=True, exist_ok=True)
    for name, source in PREVIEWS.items():
        if not source.is_file():
            raise SystemExit(f"Required reviewed preview is missing: {source}")
        shutil.copy2(source, image_dir / name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.output_dir.resolve())
    print(f"Built static Pages site at {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
