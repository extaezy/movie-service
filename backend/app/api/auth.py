from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.auth import (
    CurrentUserResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserRegisterResponse,
)
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserRegisterResponse)
async def register(
    user: UserRegister, session: Annotated[AsyncSession, Depends(get_db)]
):
    return await register_user(user, session)


@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin, session: Annotated[AsyncSession, Depends(get_db)]):
    return await authenticate_user(user, session)


@router.get("/me", response_model=CurrentUserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user
