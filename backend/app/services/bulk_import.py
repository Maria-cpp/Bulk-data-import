"""Bulk import service for orchestrating file extraction."""

import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.logging import get_logger, set_correlation_id
from app.models.bulk_import import BulkImport, ExtractedTable, ImportStatus, FileType
from app.schemas.bulk_import import (
    BulkImportCreate,
    BulkImportSummary,
    BulkImportDetail,
    ExtractedTableSummary,
    ExtractedTableDetail,
    PaginationMeta,
    PaginatedResponse,
)
from app.services.extraction import get_extractor_for_file_type
from app.services.file_validator import (
    validate_file_size,
    validate_file_type,
    sanitize_filename,
    compute_file_hash,
    FileValidationError,
)

settings = get_settings()
logger = get_logger(__name__)


class BulkImportService:
    """Service for managing bulk imports."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_import(
        self,
        user_id: uuid.UUID,
        file_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> BulkImport:
        """
        Create a new import record and validate the file.

        Args:
            user_id: ID of the user uploading the file
            file_bytes: Raw file content
            filename: Original filename
            content_type: MIME type from upload

        Returns:
            Created BulkImport record

        Raises:
            FileValidationError: If file validation fails
        """
        correlation_id = uuid.uuid4()
        set_correlation_id(correlation_id)

        logger.info(
            "bulk_import_create_started",
            user_id=str(user_id),
            filename=filename,
            file_size=len(file_bytes),
        )

        # Validate file size
        validate_file_size(len(file_bytes))

        # Validate and detect file type
        file_type = validate_file_type(file_bytes, filename, content_type)

        # Sanitize filename
        safe_filename = sanitize_filename(filename)

        # Compute file hash for duplicate detection
        file_hash = compute_file_hash(file_bytes)

        # Create import record
        bulk_import = BulkImport(
            id=uuid.uuid4(),
            user_id=user_id,
            status=ImportStatus.PENDING,
            source_file_name=safe_filename,
            source_file_type=file_type,
            source_file_size=len(file_bytes),
            source_file_hash=file_hash,
            correlation_id=correlation_id,
        )

        self.db.add(bulk_import)
        await self.db.flush()

        logger.info(
            "bulk_import_created",
            import_id=str(bulk_import.id),
            file_type=file_type.value,
        )

        return bulk_import

    async def process_import(
        self,
        import_id: uuid.UUID,
        file_bytes: bytes,
    ) -> BulkImport:
        """
        Process an import by extracting tables from the file.

        Args:
            import_id: ID of the import to process
            file_bytes: Raw file content

        Returns:
            Updated BulkImport record
        """
        # Get import record
        bulk_import = await self.get_import_by_id(import_id)
        if not bulk_import:
            raise ValueError(f"Import not found: {import_id}")

        set_correlation_id(bulk_import.correlation_id)

        logger.info(
            "bulk_import_processing_started",
            import_id=str(import_id),
            file_type=bulk_import.source_file_type.value,
        )

        # Update status to processing
        bulk_import.status = ImportStatus.PROCESSING
        bulk_import.processing_started_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Get appropriate extractor
        extractor = get_extractor_for_file_type(bulk_import.source_file_type.value)
        if not extractor:
            bulk_import.status = ImportStatus.FAILED
            bulk_import.error_message = f"No extractor available for {bulk_import.source_file_type.value}"
            await self.db.flush()
            return bulk_import

        # Extract data
        try:
            result = extractor.extract(file_bytes, bulk_import.source_file_name)

            if result.success or result.partial:
                # Save extracted tables
                for table_data in result.tables:
                    extracted_table = ExtractedTable(
                        id=uuid.uuid4(),
                        bulk_import_id=bulk_import.id,
                        table_index=table_data.table_index,
                        source_location=table_data.source_location,
                        column_headers=table_data.column_headers,
                        row_data=table_data.row_data,
                        row_count=table_data.row_count,
                        column_count=table_data.column_count,
                        confidence_score=table_data.confidence_score,
                        extraction_warnings=(
                            {"warnings": [w.__dict__ for w in table_data.warnings]}
                            if table_data.warnings
                            else None
                        ),
                    )
                    self.db.add(extracted_table)

                if result.success:
                    bulk_import.status = ImportStatus.COMPLETED
                else:
                    # Partial success
                    bulk_import.status = ImportStatus.COMPLETED
                    bulk_import.error_message = result.error_message
                    bulk_import.error_details = result.error_details

                logger.info(
                    "bulk_import_extraction_completed",
                    import_id=str(import_id),
                    tables_extracted=len(result.tables),
                    partial=result.partial,
                )
            else:
                bulk_import.status = ImportStatus.FAILED
                bulk_import.error_message = result.error_message
                bulk_import.error_details = result.error_details

                logger.warning(
                    "bulk_import_extraction_failed",
                    import_id=str(import_id),
                    error=result.error_message,
                )

        except Exception as e:
            bulk_import.status = ImportStatus.FAILED
            bulk_import.error_message = f"Extraction failed: {str(e)}"
            bulk_import.error_details = {"error_type": type(e).__name__}

            logger.exception(
                "bulk_import_extraction_error",
                import_id=str(import_id),
            )

        bulk_import.processing_completed_at = datetime.now(timezone.utc)
        await self.db.flush()

        return bulk_import

    async def get_import_by_id(
        self,
        import_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> BulkImport | None:
        """Get import by ID, optionally filtering by user."""
        query = select(BulkImport).options(
            selectinload(BulkImport.tables)
        ).where(
            and_(
                BulkImport.id == import_id,
                BulkImport.deleted_at.is_(None),
            )
        )

        if user_id:
            query = query.where(BulkImport.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_imports(
        self,
        user_id: uuid.UUID,
        status: ImportStatus | None = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedResponse:
        """Get paginated list of user's imports."""
        # Base query
        base_query = select(BulkImport).where(
            and_(
                BulkImport.user_id == user_id,
                BulkImport.deleted_at.is_(None),
            )
        )

        if status:
            base_query = base_query.where(BulkImport.status == status)

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total_items = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(BulkImport, sort_by, BulkImport.created_at)
        if sort_order.lower() == "desc":
            sort_column = sort_column.desc()
        else:
            sort_column = sort_column.asc()

        # Apply pagination
        query = (
            base_query
            .options(selectinload(BulkImport.tables))
            .order_by(sort_column)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        result = await self.db.execute(query)
        imports = result.scalars().all()

        # Convert to summaries
        items = [self._to_summary(imp) for imp in imports]

        return PaginatedResponse(
            items=items,
            pagination=PaginationMeta(
                page=page,
                per_page=per_page,
                total_items=total_items,
                total_pages=(total_items + per_page - 1) // per_page,
            ),
        )

    async def get_import_tables(
        self,
        import_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[ExtractedTableDetail]:
        """Get all tables for an import with preview data."""
        bulk_import = await self.get_import_by_id(import_id, user_id)
        if not bulk_import:
            return []

        return [
            ExtractedTableDetail(
                id=table.id,
                table_index=table.table_index,
                source_location=table.source_location,
                column_headers=table.column_headers,
                row_count=table.row_count,
                column_count=table.column_count,
                confidence_score=table.confidence_score,
                preview_rows=table.row_data[:10] if table.row_data else [],
                extraction_warnings=table.extraction_warnings,
            )
            for table in bulk_import.tables
        ]

    async def check_duplicate(
        self,
        user_id: uuid.UUID,
        filename: str,
        file_size: int,
    ) -> BulkImport | None:
        """Check if a similar file was already imported."""
        safe_filename = sanitize_filename(filename)

        query = select(BulkImport).where(
            and_(
                BulkImport.user_id == user_id,
                BulkImport.source_file_name == safe_filename,
                BulkImport.source_file_size == file_size,
                BulkImport.deleted_at.is_(None),
            )
        ).order_by(BulkImport.created_at.desc()).limit(1)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def soft_delete(
        self,
        import_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Soft delete an import."""
        bulk_import = await self.get_import_by_id(import_id, user_id)
        if not bulk_import:
            return False

        bulk_import.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "bulk_import_deleted",
            import_id=str(import_id),
            user_id=str(user_id),
        )

        return True

    async def retry_import(
        self,
        import_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BulkImport | None:
        """Retry a failed import."""
        bulk_import = await self.get_import_by_id(import_id, user_id)
        if not bulk_import:
            return None

        if not bulk_import.can_retry:
            return None

        bulk_import.status = ImportStatus.PENDING
        bulk_import.retry_count += 1
        bulk_import.error_message = None
        bulk_import.error_details = None
        bulk_import.processing_started_at = None
        bulk_import.processing_completed_at = None

        await self.db.flush()

        logger.info(
            "bulk_import_retry_queued",
            import_id=str(import_id),
            retry_count=bulk_import.retry_count,
        )

        return bulk_import

    def _to_summary(self, bulk_import: BulkImport) -> BulkImportSummary:
        """Convert BulkImport to summary schema."""
        return BulkImportSummary(
            id=bulk_import.id,
            status=bulk_import.status,
            source_file_name=bulk_import.source_file_name,
            source_file_type=bulk_import.source_file_type,
            source_file_size=bulk_import.source_file_size,
            table_count=len(bulk_import.tables),
            total_rows=sum(t.row_count for t in bulk_import.tables),
            created_at=bulk_import.created_at,
            processing_completed_at=bulk_import.processing_completed_at,
        )

    def to_detail(self, bulk_import: BulkImport) -> BulkImportDetail:
        """Convert BulkImport to detail schema."""
        return BulkImportDetail(
            id=bulk_import.id,
            status=bulk_import.status,
            source_file_name=bulk_import.source_file_name,
            source_file_type=bulk_import.source_file_type,
            source_file_size=bulk_import.source_file_size,
            created_at=bulk_import.created_at,
            processing_started_at=bulk_import.processing_started_at,
            processing_completed_at=bulk_import.processing_completed_at,
            correlation_id=bulk_import.correlation_id,
            error_message=bulk_import.error_message,
            error_details=bulk_import.error_details,
            retry_count=bulk_import.retry_count,
            can_retry=bulk_import.can_retry,
            tables=[
                ExtractedTableSummary(
                    id=t.id,
                    table_index=t.table_index,
                    source_location=t.source_location,
                    row_count=t.row_count,
                    column_count=t.column_count,
                    column_headers=t.column_headers,
                    confidence_score=t.confidence_score,
                )
                for t in bulk_import.tables
            ],
        )

    def to_create_response(self, bulk_import: BulkImport) -> BulkImportCreate:
        """Convert BulkImport to create response schema."""
        return BulkImportCreate(
            id=bulk_import.id,
            status=bulk_import.status,
            source_file_name=bulk_import.source_file_name,
            source_file_type=bulk_import.source_file_type,
            source_file_size=bulk_import.source_file_size,
            created_at=bulk_import.created_at,
            correlation_id=bulk_import.correlation_id,
        )
