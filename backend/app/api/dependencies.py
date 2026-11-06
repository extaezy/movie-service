from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tokens import decode_access_token
from app.db.database import get_db
from app.db.models import User
from app.repositories.user_store import get_user_by_id

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Недействительный токен",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        user_id = UUID(decode_access_token(credentials.credentials))
    except (InvalidTokenError, ValueError) as exc:
        raise unauthorized from exc
    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user
