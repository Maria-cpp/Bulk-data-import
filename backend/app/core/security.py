"""JWT authentication and security utilities."""

import os
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

settings = get_settings()
security = HTTPBearer(auto_error=False)

# Dev mode: bypass auth with a fixed user ID
DEV_MODE = os.environ.get("DEV_MODE", "true").lower() == "true"
DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class TokenPayload:
    """Decoded JWT token payload."""

    def __init__(self, user_id: UUID):
        self.user_id = user_id


def decode_token(token: str) -> TokenPayload:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return TokenPayload(user_id=UUID(user_id))
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenPayload:
    """Get current user from JWT token (or dev user in dev mode)."""
    # Dev mode bypass
    if DEV_MODE:
        return TokenPayload(user_id=DEV_USER_ID)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return decode_token(credentials.credentials)


def get_user_id(current_user: TokenPayload = Depends(get_current_user)) -> UUID:
    """Get user ID from current user."""
    return current_user.user_id
