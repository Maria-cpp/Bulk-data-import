"""Pydantic schemas for bulk import API."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ImportStatus(str, Enum):
    """Status of an import operation."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileType(str, Enum):
    """Supported file types for import."""
    PDF = "PDF"
    EXCEL = "EXCEL"
    WORD = "WORD"
    IMAGE = "IMAGE"
    CSV = "CSV"


class BulkImportCreate(BaseModel):
    """Response after file upload."""
    id: UUID
    status: ImportStatus
    source_file_name: str
    source_file_type: FileType
    source_file_size: int
    created_at: datetime
    correlation_id: UUID


class ExtractedTableSummary(BaseModel):
    """Summary of an extracted table."""
    id: UUID
    table_index: int
    source_location: str | None = None
    row_count: int
    column_count: int
    column_headers: list[str]
    confidence_score: float | None = None


class ExtractedTableDetail(BaseModel):
    """Full details of an extracted table including preview rows."""
    id: UUID
    table_index: int
    source_location: str | None = None
    column_headers: list[str]
    row_count: int
    column_count: int
    confidence_score: float | None = None
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)
    extraction_warnings: dict | None = None


class BulkImportSummary(BaseModel):
    """Summary of an import for list view."""
    id: UUID
    status: ImportStatus
    source_file_name: str
    source_file_type: FileType
    source_file_size: int
    table_count: int = 0
    total_rows: int = 0
    created_at: datetime
    processing_completed_at: datetime | None = None


class BulkImportDetail(BaseModel):
    """Full details of an import."""
    id: UUID
    status: ImportStatus
    source_file_name: str
    source_file_type: FileType
    source_file_size: int
    created_at: datetime
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None
    correlation_id: UUID
    error_message: str | None = None
    error_details: dict | None = None
    retry_count: int = 0
    can_retry: bool = False
    tables: list[ExtractedTableSummary] = Field(default_factory=list)


class TableUpdateRequest(BaseModel):
    """Request to update table data."""
    column_headers: list[str]
    rows: list[dict[str, Any]]


class TableUpdateResponse(BaseModel):
    """Response after updating table data."""
    table_id: UUID
    column_headers: list[str]
    row_count: int
    column_count: int
    updated_at: datetime


class ExportResponse(BaseModel):
    """Response for table data export."""
    table_id: UUID
    source_location: str | None = None
    column_headers: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    exported_at: datetime


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    details: dict | None = None
    correlation_id: UUID | None = None


class DuplicateCheckResponse(BaseModel):
    """Response for duplicate check endpoint."""
    is_duplicate: bool
    existing_import: BulkImportSummary | None = None
    message: str | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int
    per_page: int
    total_items: int
    total_pages: int


class PaginatedResponse(BaseModel):
    """Paginated list response."""
    items: list[BulkImportSummary]
    pagination: PaginationMeta
