"""API dependencies for dependency injection."""

from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import async_session_maker
from app.core.security import get_current_user, TokenPayload


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user_id(
    current_user: TokenPayload = Depends(get_current_user),
) -> UUID:
    """Get current user ID from token."""
    return current_user.user_id
