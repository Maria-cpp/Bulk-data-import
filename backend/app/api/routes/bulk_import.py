"""API routes for bulk import operations."""

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user_id
from app.models import async_session_maker
from app.schemas.bulk_import import (
    BulkImportCreate,
    BulkImportDetail,
    DuplicateCheckResponse,
    ErrorResponse,
    ExportResponse,
    ExtractedTableDetail,
    ImportStatus,
    PaginatedResponse,
    TableUpdateRequest,
    TableUpdateResponse,
)
from app.services.bulk_import import BulkImportService
from app.services.file_validator import FileValidationError
from app.core.logging import get_logger

import csv
import io
from datetime import datetime, timezone

logger = get_logger(__name__)

router = APIRouter()


async def process_import_background(import_id: uuid.UUID, file_bytes: bytes):
    """Process import in background with its own session."""
    async with async_session_maker() as session:
        try:
            service = BulkImportService(session)
            await service.process_import(import_id, file_bytes)
            await session.commit()
        except Exception as e:
            logger.error(f"Background processing failed for {import_id}: {e}")
            await session.rollback()
            raise


@router.post(
    "",
    response_model=BulkImportCreate,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        413: {"model": ErrorResponse, "description": "File too large"},
    },
)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Upload a document and create a new import.

    Supported formats: PDF, Excel (.xlsx, .xls), Word (.docx, .doc),
    Image (.png, .jpg, .jpeg), CSV
    """
    service = BulkImportService(db)

    try:
        # Read file content
        file_bytes = await file.read()

        # Create import record
        bulk_import = await service.create_import(
            user_id=user_id,
            file_bytes=file_bytes,
            filename=file.filename or "unnamed",
            content_type=file.content_type,
        )

        await db.commit()

        # Schedule background processing (fire and forget)
        asyncio.create_task(process_import_background(bulk_import.id, file_bytes))

        return service.to_create_response(bulk_import)

    except FileValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                **e.details,
            },
        )


@router.get(
    "",
    response_model=PaginatedResponse,
)
async def list_imports(
    status_filter: Annotated[ImportStatus | None, Query(alias="status")] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """List imports for the authenticated user."""
    service = BulkImportService(db)

    return await service.get_user_imports(
        user_id=user_id,
        status=status_filter,
        page=page,
        per_page=per_page,
        sort_by=sort,
        sort_order=order,
    )


@router.get(
    "/check-duplicate",
    response_model=DuplicateCheckResponse,
)
async def check_duplicate(
    filename: str = Query(...),
    size: int = Query(..., ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Check if a file appears to be a duplicate before upload."""
    service = BulkImportService(db)

    existing = await service.check_duplicate(user_id, filename, size)

    if existing:
        return DuplicateCheckResponse(
            is_duplicate=True,
            existing_import=service._to_summary(existing),
            message=f"A file with the same name and size was imported on {existing.created_at.strftime('%b %d, %Y')}",
        )

    return DuplicateCheckResponse(is_duplicate=False)


@router.get(
    "/{import_id}",
    response_model=BulkImportDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_import_detail(
    import_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Get detailed information about a specific import."""
    service = BulkImportService(db)

    bulk_import = await service.get_import_by_id(import_id, user_id)
    if not bulk_import:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": "Import not found or access denied"},
        )

    return service.to_detail(bulk_import)


@router.get(
    "/{import_id}/tables",
    response_model=dict,
)
async def get_import_tables(
    import_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Get all extracted tables for an import."""
    service = BulkImportService(db)

    tables = await service.get_import_tables(import_id, user_id)

    return {
        "import_id": str(import_id),
        "tables": [t.model_dump() for t in tables],
    }


@router.get(
    "/{import_id}/tables/{table_id}/export",
    responses={
        200: {"description": "Export data in JSON or CSV format"},
        404: {"model": ErrorResponse},
    },
)
async def export_table(
    import_id: uuid.UUID,
    table_id: uuid.UUID,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Export table data in specified format (JSON or CSV)."""
    service = BulkImportService(db)

    bulk_import = await service.get_import_by_id(import_id, user_id)
    if not bulk_import:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": "Import not found or access denied"},
        )

    # Find the table
    table = next((t for t in bulk_import.tables if t.id == table_id), None)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": "Table not found"},
        )

    if format == "csv":
        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=table.column_headers)
        writer.writeheader()
        writer.writerows(table.row_data)

        # Create streaming response
        output.seek(0)
        filename = f"{bulk_import.source_file_name}_{table.table_index}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    else:
        # JSON format
        return ExportResponse(
            table_id=table.id,
            source_location=table.source_location,
            column_headers=table.column_headers,
            rows=table.row_data,
            row_count=table.row_count,
            exported_at=datetime.now(timezone.utc),
        )


@router.put(
    "/{import_id}/tables/{table_id}",
    response_model=TableUpdateResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_table(
    import_id: uuid.UUID,
    table_id: uuid.UUID,
    update_data: TableUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Update table data (headers and rows)."""
    service = BulkImportService(db)

    bulk_import = await service.get_import_by_id(import_id, user_id)
    if not bulk_import:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": "Import not found or access denied"},
        )

    # Find the table
    table = next((t for t in bulk_import.tables if t.id == table_id), None)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": "Table not found"},
        )

    # Update the table
    table.column_headers = update_data.column_headers
    table.row_data = update_data.rows
    table.row_count = len(update_data.rows)
    table.column_count = len(update_data.column_headers)

    await db.commit()

    return TableUpdateResponse(
        table_id=table.id,
        column_headers=table.column_headers,
        row_count=table.row_count,
        column_count=table.column_count,
        updated_at=datetime.now(timezone.utc),
    )


@router.delete(
    "/{import_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_import(
    import_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Soft delete an import record."""
    service = BulkImportService(db)

    deleted = await service.soft_delete(import_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": "Import not found or access denied"},
        )

    await db.commit()


@router.post(
    "/{import_id}/retry",
    response_model=BulkImportCreate,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def retry_import(
    import_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retry a failed import."""
    service = BulkImportService(db)

    bulk_import = await service.retry_import(import_id, user_id)
    if not bulk_import:
        # Check if import exists
        existing = await service.get_import_by_id(import_id, user_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Import not found or access denied"},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "RETRY_NOT_ALLOWED",
                    "message": "Import is not in FAILED status or has exceeded retry limit",
                    "current_status": existing.status.value,
                    "retry_count": existing.retry_count,
                    "max_retries": 3,
                },
            )

    await db.commit()

    return service.to_create_response(bulk_import)
