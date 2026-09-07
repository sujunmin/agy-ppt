"""Tesseract availability/version/model provenance foundation (no OCR execution)."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
import csv

from .base import OCRProvider
from .errors import OCRError
from .models import OCRProviderCapabilities, OCRRequest, OCREvidence, OCRProvenance
from .process import ProcessRunner

_VERSION = re.compile(r"^tesseract\s+(\d+)\.(\d+)(?:\.(\d+))?", re.I | re.M)

def parse_tesseract_version(output: str) -> str:
    match = _VERSION.search(output or "")
    if not match:
        raise OCRError("could not determine Tesseract version", "OCR_PROVIDER_VERSION_UNAVAILABLE")
    version = ".".join(part for part in match.groups() if part is not None)
    if not version.startswith("5."):
        raise OCRError("unsupported Tesseract major version", "OCR_PROVIDER_VERSION_UNSUPPORTED")
    return version

@dataclass(frozen=True)
class Traineddata:
    model_id: str
    model_digest: str
    model_source: str

class TesseractProvider(OCRProvider):
    provider_id = "tesseract"
    provider_version = "phase15.1-c"
    capabilities = OCRProviderCapabilities(True, True, "local", False)

    def __init__(self, executable: str | None = None, *, runner: ProcessRunner | None = None,
                 tessdata_dir: str | Path | None = None):
        self.executable = executable
        self.runner = runner or ProcessRunner()
        self.tessdata_dir = Path(tessdata_dir) if tessdata_dir is not None else None
        self.effective_language_config: tuple[str, ...] = ()

    def resolve_executable(self) -> str:
        try:
            path = self.executable or shutil.which("tesseract")
        except (OSError, ValueError) as exc:
            raise OCRError("Tesseract executable unavailable", "OCR_PROVIDER_UNAVAILABLE") from exc
        if not path:
            raise OCRError("Tesseract executable unavailable", "OCR_PROVIDER_UNAVAILABLE")
        return path

    def detect_version(self) -> str:
        result = self.runner.run([self.resolve_executable(), "--version"])
        if result.returncode != 0:
            raise OCRError("Tesseract version probe failed", "OCR_PROVIDER_VERSION_UNAVAILABLE")
        return parse_tesseract_version(result.stdout)

    def discover_traineddata(self, languages: str | list[str]) -> tuple[Traineddata, ...]:
        names = languages.split("+") if isinstance(languages, str) else list(languages)
        if not names or len(set(names)) != len(names) or any(not name or "/" in name or "\\" in name for name in names):
            raise OCRError("invalid OCR language configuration", "OCR_LANGUAGE_UNSUPPORTED")
        self.effective_language_config = tuple(names)
        directory = self.tessdata_dir
        if directory is None and os.environ.get("TESSDATA_PREFIX"):
            prefix = Path(os.environ["TESSDATA_PREFIX"])
            directory = prefix / "tessdata" if (prefix / "tessdata").is_dir() else prefix
        if directory is None:
            raise OCRError("Tesseract traineddata directory unavailable", "OCR_LANGUAGE_UNSUPPORTED")
        found = []
        for name in names:
            path = directory / f"{name}.traineddata"
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise OCRError(f"traineddata unavailable: {name}", "OCR_LANGUAGE_UNSUPPORTED") from exc
            found.append(Traineddata(name, hashlib.sha256(data).hexdigest(), f"tessdata:{name}"))
        return tuple(sorted(found, key=lambda item: (item.model_id, item.model_digest, item.model_source)))

    def recognize(self, request: OCRRequest, *, expected_models: tuple[Traineddata, ...] | None = None,
                  languages: str | list[str] = "eng") -> OCREvidence:
        """Execute one prepared image; model bytes are revalidated immediately first."""
        models = self.discover_traineddata(languages)
        if expected_models is not None and tuple((m.model_id, m.model_digest) for m in models) != tuple((m.model_id, m.model_digest) for m in expected_models):
            raise OCRError("traineddata changed since inspection", "OCR_MODEL_CHANGED")
        with tempfile.TemporaryDirectory(prefix="agy-ocr-") as temp:
            image = Path(temp) / "input"
            image.write_bytes(request.image_bytes)
            tessdata = self.tessdata_dir
            if tessdata is None:
                prefix = os.environ.get("TESSDATA_PREFIX")
                tessdata = Path(prefix) / "tessdata" if prefix and (Path(prefix) / "tessdata").is_dir() else (Path(prefix) if prefix else None)
            if tessdata is None:
                raise OCRError("Tesseract traineddata directory unavailable", "OCR_LANGUAGE_UNSUPPORTED")
            result = self.runner.run([self.resolve_executable(), str(image), "stdout", "--tessdata-dir", str(tessdata), "tsv"])
        if result.returncode != 0:
            raise OCRError("Tesseract recognition failed", "OCR_PROVIDER_FAILED")
        raw_text, regions = parse_tsv(result.stdout, request.execution_config)
        provenance = OCRProvenance("tesseract", "tesseract", "local", False)
        evidence = OCREvidence("1.0", request.source_id, request.source_digest, request.locator, raw_text, tuple(regions), self.capabilities, "tesseract", self.provider_version, provenance, model_manifest=tuple({"model_id": m.model_id, "model_digest": m.model_digest, "model_source": m.model_source} for m in models), language_config={"languages": tuple(languages.split("+") if isinstance(languages, str) else languages)}, execution_config={"tessdata_dir": str(tessdata)})
        evidence.validate()
        return evidence

def parse_tsv(text: str, execution_config: dict | None = None) -> tuple[str, list[dict]]:
    rows = list(csv.DictReader(text.splitlines(), delimiter="\t"))
    required = {"level", "page_num", "block_num", "par_num", "line_num", "word_num", "left", "top", "width", "height", "conf", "text"}
    if not rows and text.strip() and not text.splitlines()[0].startswith("level\t"):
        raise OCRError("invalid Tesseract TSV header", "OCR_PROVIDER_OUTPUT_INVALID")
    if rows and not required.issubset(rows[0].keys()):
        raise OCRError("invalid Tesseract TSV columns", "OCR_PROVIDER_OUTPUT_INVALID")
    words = []
    for row in rows:
        try:
            level = int(row["level"]); conf = float(row["conf"])
            coords = [int(row[k]) for k in ("left", "top", "width", "height")]
        except (KeyError, TypeError, ValueError):
            raise OCRError("malformed Tesseract TSV row", "OCR_PROVIDER_OUTPUT_INVALID")
        if level != 5 or not row["text"]:
            continue
        if any(v < 0 for v in coords) or not (-1 <= conf <= 100):
            raise OCRError("invalid Tesseract TSV values", "OCR_PROVIDER_OUTPUT_INVALID")
        region = {"region_id": "w-" + "-".join(row[k] for k in ("page_num", "block_num", "par_num", "line_num", "word_num")), "text": row["text"], "confidence": {"raw_confidence": conf, "confidence_scale": "0-100", "confidence_source": "tesseract_word"}}
        dims = (execution_config or {}).get("image_dimensions")
        if dims:
            iw, ih = dims
            if iw <= 0 or ih <= 0: raise OCRError("invalid image dimensions", "OCR_PROVIDER_OUTPUT_INVALID")
            region["bounding_box"] = {"x": coords[0]/iw, "y": coords[1]/ih, "width": coords[2]/iw, "height": coords[3]/ih}
        words.append((row["page_num"], row["block_num"], row["par_num"], row["line_num"], row["word_num"], row["text"], region))
    words.sort(key=lambda x: tuple(int(v) for v in x[:5]))
    lines = {}
    for *key, word, region in words: lines.setdefault(tuple(key[:4]), []).append(word)
    raw = "\n".join(" ".join(lines[k]) for k in sorted(lines))
    return raw, [w[-1] for w in words]
