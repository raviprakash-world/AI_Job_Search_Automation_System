from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError
from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthError("Missing authentication token")

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise AuthError("Expected an access token")

    user = await db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return user
