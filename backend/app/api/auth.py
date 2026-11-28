from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, validate_auth_request
from app.core.config import settings
from app.core.tokens import create_access_token, decode_access_token
from app.db.database import get_db
from app.db.models import AuthSession, RefreshToken, User
from app.repositories.auth_session_repository import (
    InvalidRefreshTokenError,
    refresh_token_hash,
    rotate_refresh_token,
)
from app.schemas.auth import (
    CurrentUserResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserRegisterResponse,
)
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE = "movie_service_refresh"
PRIVATE_HEADERS = {"Cache-Control": "no-store"}
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
AuthRequest = Annotated[None, Depends(validate_auth_request)]


def set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=max(0, int((expires_at - datetime.now(UTC)).total_seconds())),
        expires=expires_at,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )
    response.headers.update(PRIVATE_HEADERS)


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )
    response.headers.update(PRIVATE_HEADERS)


@router.post("/register", status_code=201, response_model=UserRegisterResponse)
async def register(
    user: UserRegister, session: Annotated[AsyncSession, Depends(get_db)]
):
    return await register_user(user, session)


@router.post("/login", response_model=TokenResponse)
async def login(
    user: UserLogin,
    session: DatabaseSession,
    response: Response,
    auth_request: AuthRequest,
):
    tokens, refresh, expires_at = await authenticate_user(user, session)
    set_refresh_cookie(response, refresh, expires_at)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: DatabaseSession,
    auth_request: AuthRequest,
):
    try:
        auth_session, replacement = await rotate_refresh_token(
            session, request.cookies.get(REFRESH_COOKIE, "")
        )
    except InvalidRefreshTokenError:
        await session.rollback()
        denied = JSONResponse(
            status_code=401,
            content={"detail": "Сессия недействительна"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        clear_refresh_cookie(denied)
        return denied
    access = create_access_token(
        str(auth_session.user_id), str(auth_session.id), auth_session.expires_at
    )
    set_refresh_cookie(response, replacement, auth_session.expires_at)
    return TokenResponse(access_token=access)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    session: DatabaseSession,
    auth_request: AuthRequest,
) -> Response:
    session_ids = set()
    cookie = request.cookies.get(REFRESH_COOKIE, "")
    if len(cookie) == 64:
        session_id = await session.scalar(
            select(RefreshToken.session_id).where(
                RefreshToken.token_hash == refresh_token_hash(cookie)
            )
        )
        if session_id:
            session_ids.add(session_id)
    authorization = request.headers.get("authorization", "").split()
    if len(authorization) == 2 and authorization[0].casefold() == "bearer":
        try:
            user_id, session_id = decode_access_token(authorization[1])
        except InvalidTokenError:
            pass
        else:
            matching_id = await session.scalar(
                select(AuthSession.id).where(
                    AuthSession.id == session_id, AuthSession.user_id == user_id
                )
            )
            if matching_id:
                session_ids.add(matching_id)
    sessions = await session.scalars(
        select(AuthSession)
        .where(AuthSession.id.in_(session_ids))
        .order_by(AuthSession.id)
        .with_for_update()
    )
    for auth_session in sessions:
        if auth_session.revoked_at is None:
            auth_session.revoked_at = datetime.now(UTC)
    await session.commit()
    response = Response(status_code=204)
    clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=CurrentUserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user
