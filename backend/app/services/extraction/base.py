"""Base extractor interface for document table extraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractionWarning:
    """Warning generated during extraction."""
    type: str
    location: str
    message: str
    confidence: float | None = None


@dataclass
class ExtractedTableData:
    """Data extracted from a single table."""
    table_index: int
    source_location: str | None
    column_headers: list[str]
    row_data: list[dict[str, Any]]
    row_count: int
    column_count: int
    confidence_score: float | None = None
    warnings: list[ExtractionWarning] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Result of document extraction."""
    success: bool
    tables: list[ExtractedTableData] = field(default_factory=list)
    error_message: str | None = None
    error_details: dict[str, Any] | None = None
    partial: bool = False  # True if some tables extracted despite errors


class BaseExtractor(ABC):
    """Abstract base class for document extractors."""

    @property
    @abstractmethod
    def supported_mime_types(self) -> list[str]:
        """List of MIME types this extractor can handle."""
        pass

    def supports(self, mime_type: str) -> bool:
        """Check if this extractor supports the given MIME type."""
        return mime_type.lower() in [m.lower() for m in self.supported_mime_types]

    @abstractmethod
    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """
        Extract tables from file.

        Args:
            file_bytes: Raw file content
            filename: Original filename (for context)

        Returns:
            ExtractionResult with extracted tables or error info
        """
        pass

    def _create_error_result(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        partial_tables: list[ExtractedTableData] | None = None,
    ) -> ExtractionResult:
        """Helper to create error result."""
        return ExtractionResult(
            success=False,
            tables=partial_tables or [],
            error_message=message,
            error_details=details,
            partial=bool(partial_tables),
        )

    def _create_success_result(
        self,
        tables: list[ExtractedTableData],
    ) -> ExtractionResult:
        """Helper to create success result."""
        return ExtractionResult(
            success=True,
            tables=tables,
        )
