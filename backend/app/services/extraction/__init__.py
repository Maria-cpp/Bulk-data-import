"""Document extraction services."""

from app.services.extraction.base import BaseExtractor, ExtractionResult, ExtractedTableData
from app.services.extraction.excel import ExcelExtractor
from app.services.extraction.csv_extractor import CSVExtractor
from app.services.extraction.pdf import PDFExtractor
from app.services.extraction.image import ImageExtractor
from app.services.extraction.word import WordExtractor

# Extractor registry
_extractors: list[BaseExtractor] = [
    ExcelExtractor(),
    CSVExtractor(),
    PDFExtractor(),
    ImageExtractor(),
    WordExtractor(),
]


def register_extractor(extractor: BaseExtractor) -> None:
    """Register an extractor."""
    _extractors.append(extractor)


def get_extractor(mime_type: str) -> BaseExtractor | None:
    """Get appropriate extractor for mime type."""
    for extractor in _extractors:
        if extractor.supports(mime_type):
            return extractor
    return None


def get_extractor_for_file_type(file_type: str) -> BaseExtractor | None:
    """Get extractor by file type string (PDF, EXCEL, WORD, IMAGE, CSV)."""
    type_mime_map = {
        "EXCEL": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "CSV": "text/csv",
        "PDF": "application/pdf",
        "WORD": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "IMAGE": "image/png",
    }
    mime_type = type_mime_map.get(file_type.upper())
    if mime_type:
        return get_extractor(mime_type)
    return None


def get_all_supported_mime_types() -> list[str]:
    """Get all supported MIME types."""
    mime_types = []
    for extractor in _extractors:
        mime_types.extend(extractor.supported_mime_types)
    return mime_types


__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "ExtractedTableData",
    "ExcelExtractor",
    "CSVExtractor",
    "PDFExtractor",
    "ImageExtractor",
    "WordExtractor",
    "register_extractor",
    "get_extractor",
    "get_extractor_for_file_type",
    "get_all_supported_mime_types",
]
