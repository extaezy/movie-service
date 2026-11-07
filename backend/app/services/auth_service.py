from fastapi import HTTPException, status
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.security import hash_password, verify_password
from app.core.tokens import create_access_token
from app.repositories.user_repository import (
    UserAlreadyExistsError,
    create_user,
    get_user_by_email,
    get_user_by_username,
)
from app.schemas.auth import UserLogin, UserRegister

email_adapter = TypeAdapter(EmailStr)
dummy_password_hash = hash_password("dummy-password-for-timing")


async def register_user(user: UserRegister, session: AsyncSession):
    hashed_password = await run_in_threadpool(hash_password, user.password)
    try:
        await create_user(session, user.username, str(user.email), hashed_password)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "username": user.username,
        "email": user.email,
    }


async def authenticate_user(user: UserLogin, session: AsyncSession):
    if "@" in user.identifier:
        try:
            email = email_adapter.validate_python(user.identifier)
        except ValidationError:
            existing_user = None
        else:
            existing_user = await get_user_by_email(session, str(email))
    else:
        existing_user = await get_user_by_username(session, user.identifier)

    password_hash = (
        existing_user.hashed_password if existing_user else dummy_password_hash
    )
    password_matches = await run_in_threadpool(
        verify_password, user.password, password_hash
    )
    if existing_user is None or not existing_user.is_active or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный username/email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(str(existing_user.id)),
        "token_type": "bearer",
    }
