"""Recovery service for handling stuck imports."""

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.bulk_import import BulkImport, ImportStatus

logger = get_logger(__name__)

# Default timeout for PROCESSING status (5 minutes)
PROCESSING_TIMEOUT_MINUTES = 5


async def recover_stuck_imports(
    db: AsyncSession,
    timeout_minutes: int = PROCESSING_TIMEOUT_MINUTES,
) -> int:
    """
    Find and reset imports stuck in PROCESSING state.

    This job should be run periodically (e.g., every minute) to detect
    imports that started processing but never completed.

    Args:
        db: Database session
        timeout_minutes: Time after which PROCESSING imports are considered stuck

    Returns:
        Number of imports recovered
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    # Find stuck imports
    query = select(BulkImport).where(
        and_(
            BulkImport.status == ImportStatus.PROCESSING,
            BulkImport.processing_started_at < cutoff_time,
            BulkImport.deleted_at.is_(None),
        )
    )

    result = await db.execute(query)
    stuck_imports = result.scalars().all()

    if not stuck_imports:
        return 0

    recovered_count = 0

    for bulk_import in stuck_imports:
        # Only retry if under retry limit
        if bulk_import.retry_count < 3:
            bulk_import.status = ImportStatus.PENDING
            bulk_import.processing_started_at = None
            bulk_import.processing_completed_at = None
            bulk_import.retry_count += 1
            bulk_import.error_message = "Automatically recovered from stuck PROCESSING state"
            bulk_import.error_details = {
                "recovery_type": "automatic",
                "previous_started_at": bulk_import.processing_started_at.isoformat() if bulk_import.processing_started_at else None,
                "timeout_minutes": timeout_minutes,
            }

            logger.info(
                "bulk_import_recovered",
                import_id=str(bulk_import.id),
                user_id=str(bulk_import.user_id),
                retry_count=bulk_import.retry_count,
            )

            recovered_count += 1
        else:
            # Mark as failed if retry limit exceeded
            bulk_import.status = ImportStatus.FAILED
            bulk_import.processing_completed_at = datetime.now(timezone.utc)
            bulk_import.error_message = "Processing timed out and retry limit exceeded"
            bulk_import.error_details = {
                "recovery_type": "failed_max_retries",
                "retry_count": bulk_import.retry_count,
            }

            logger.warning(
                "bulk_import_recovery_failed_max_retries",
                import_id=str(bulk_import.id),
                user_id=str(bulk_import.user_id),
                retry_count=bulk_import.retry_count,
            )

    await db.commit()

    logger.info(
        "recovery_job_completed",
        stuck_found=len(stuck_imports),
        recovered=recovered_count,
    )

    return recovered_count


async def get_stuck_import_count(
    db: AsyncSession,
    timeout_minutes: int = PROCESSING_TIMEOUT_MINUTES,
) -> int:
    """Get count of currently stuck imports."""
    from sqlalchemy import func

    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    query = select(func.count()).select_from(BulkImport).where(
        and_(
            BulkImport.status == ImportStatus.PROCESSING,
            BulkImport.processing_started_at < cutoff_time,
            BulkImport.deleted_at.is_(None),
        )
    )

    result = await db.execute(query)
    return result.scalar() or 0
