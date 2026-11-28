from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.tokens import decode_access_token
from app.db.database import get_db
from app.db.models import User
from app.repositories.auth_session_repository import get_active_auth_session
from app.repositories.user_repository import get_user_by_id

bearer = HTTPBearer(auto_error=False)


def validate_auth_request(request: Request) -> None:
    if request.headers.get("X-Auth-Request") != "1":
        raise HTTPException(403, "Требуется заголовок X-Auth-Request")
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.auth_allowed_origins:
        raise HTTPException(403, "Недопустимый источник запроса")


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
        user_id, session_id = decode_access_token(credentials.credentials)
    except (InvalidTokenError, ValueError) as exc:
        raise unauthorized from exc
    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    if await get_active_auth_session(session, session_id, user_id) is None:
        raise unauthorized
    return user


async def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    if credentials is None:
        return None
    return await get_current_user(credentials, session)


async def get_current_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user
