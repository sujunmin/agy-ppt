"""Tesseract availability/version/model provenance foundation (no OCR execution)."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil

from .base import OCRProvider
from .errors import OCRError
from .models import OCRProviderCapabilities, OCRRequest, OCREvidence
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

    def recognize(self, request: OCRRequest) -> OCREvidence:
        raise OCRError("Tesseract recognition is deferred to Phase 15.1-D", "OCR_PROVIDER_FAILED")
