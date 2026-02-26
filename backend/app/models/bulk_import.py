"""BulkImport and ExtractedTable SQLAlchemy models."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Enum,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship

from app.models import Base


class ImportStatus(str, PyEnum):
    """Status of an import operation."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileType(str, PyEnum):
    """Supported file types for import."""
    PDF = "PDF"
    EXCEL = "EXCEL"
    WORD = "WORD"
    IMAGE = "IMAGE"
    CSV = "CSV"


class BulkImport(Base):
    """Represents a single file import operation."""
    __tablename__ = "bulk_imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(
        Enum(ImportStatus, name="import_status"),
        nullable=False,
        default=ImportStatus.PENDING
    )
    source_file_name = Column(String(255), nullable=False)
    source_file_type = Column(
        Enum(FileType, name="file_type"),
        nullable=False
    )
    source_file_size = Column(Integer, nullable=False)
    source_file_hash = Column(String(64), nullable=False)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)
    processing_started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    processing_completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    correlation_id = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    tables = relationship(
        "ExtractedTable",
        back_populates="bulk_import",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        Index("idx_bulk_import_user_status", "user_id", "status", "deleted_at"),
        Index("idx_bulk_import_hash", "user_id", "source_file_hash"),
        Index(
            "idx_bulk_import_stuck",
            "status",
            "processing_started_at",
            postgresql_where="status = 'PROCESSING'"
        ),
    )

    @property
    def can_retry(self) -> bool:
        """Check if import can be retried."""
        from app.config import get_settings
        settings = get_settings()
        return (
            self.status == ImportStatus.FAILED
            and self.retry_count < settings.BULK_IMPORT_MAX_RETRIES
        )

    @property
    def total_rows(self) -> int:
        """Get total rows across all extracted tables."""
        return sum(table.row_count for table in self.tables)


class ExtractedTable(Base):
    """Represents a table extracted from a document."""
    __tablename__ = "extracted_tables"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bulk_import_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bulk_imports.id", ondelete="CASCADE"),
        nullable=False
    )
    table_index = Column(Integer, nullable=False)
    source_location = Column(String(100), nullable=True)
    column_headers = Column(JSONB, nullable=False)
    row_data = Column(JSONB, nullable=False)
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    confidence_score = Column(Float, nullable=True)
    extraction_warnings = Column(JSONB, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )

    # Relationships
    bulk_import = relationship("BulkImport", back_populates="tables")

    __table_args__ = (
        Index("idx_extracted_table_import", "bulk_import_id"),
    )
