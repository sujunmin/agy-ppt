"""Provider-neutral OCR contract primitives (Phase 15.1)."""

from .base import OCRProvider
from .errors import OCRError
from .models import (
    OCRDiagnostic, OCREvidence, OCRProviderCapabilities, OCRProvenance,
    OCRRequest, OCRResolution,
)
from .validation import validate_evidence, validate_provider, validate_request
from .resolution import execute_with_fallback, resolve_provider

__all__ = [
    "OCRProvider", "OCRError", "OCRDiagnostic", "OCREvidence",
    "OCRProviderCapabilities", "OCRProvenance", "OCRRequest", "OCRResolution",
    "validate_evidence", "validate_provider", "validate_request",
    "resolve_provider", "execute_with_fallback",
]
