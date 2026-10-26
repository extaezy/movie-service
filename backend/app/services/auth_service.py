from app.schemas.auth import UserRegister
from app.core.security import hash_password
from app.repositories.user_store import (
    UserAlreadyExistsError,
    create_user,
    get_user_by_email,
    get_user_by_username,
)
from fastapi import HTTPException, status
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.schemas.auth import UserLogin
from app.core.security import verify_password
from app.core.tokens import create_access_token


email_adapter = TypeAdapter(EmailStr)
dummy_password_hash = hash_password("dummy-password-for-timing")

def register_user(user: UserRegister):
    hashed_password = hash_password(user.password)
    try:
        create_user(user.username, str(user.email), hashed_password)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "username": user.username,
        "email": user.email,
    }

def authenticate_user(user: UserLogin):
    if "@" in user.identifier:
        try:
            email = email_adapter.validate_python(user.identifier)
        except ValidationError:
            existing_user = None
        else:
            existing_user = get_user_by_email(str(email))
    else:
        existing_user = get_user_by_username(user.identifier)

    password_hash = (
        existing_user["hashed_password"] if existing_user else dummy_password_hash
    )
    password_matches = verify_password(user.password, password_hash)
    if existing_user is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный username/email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(existing_user["id"]),
        "token_type": "bearer",
    }
