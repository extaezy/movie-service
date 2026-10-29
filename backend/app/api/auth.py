from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user
from app.services.auth_service import register_user
from app.schemas.auth import UserLogin
from app.services.auth_service import authenticate_user

from app.schemas.auth import (
    UserRegister,
    UserRegisterResponse,
    TokenResponse,
    CurrentUserResponse,
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post(
    "/register",
    status_code=201,
    response_model=UserRegisterResponse
)
def register(user: UserRegister):
    return register_user(user)

@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin):
    return authenticate_user(user)


@router.get("/me", response_model=CurrentUserResponse)
def me(user: dict[str, str] = Depends(get_current_user)):
    return user
