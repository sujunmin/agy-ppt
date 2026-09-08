"""Internal Phase 15.2 PDF OCR contract primitives."""

from .errors import ERROR_CODES, PDFOCRError, PDFOCRErrorCode
from .models import (
    PDFAdmissionResult,
    PDFPageIdentity,
    PDFSourceIdentity,
    PageClassification,
    RasterConfiguration,
    RasterProvenance,
    ResourceLimits,
    WorkerIsolationPolicy,
)
from .rasterizer import PDFRasterizer, RasterRequest, RasterResult

__all__ = [
    "ERROR_CODES",
    "PDFAdmissionResult",
    "PDFOCRError",
    "PDFOCRErrorCode",
    "PDFPageIdentity",
    "PDFRasterizer",
    "PDFSourceIdentity",
    "PageClassification",
    "RasterConfiguration",
    "RasterProvenance",
    "RasterRequest",
    "RasterResult",
    "ResourceLimits",
    "WorkerIsolationPolicy",
]
