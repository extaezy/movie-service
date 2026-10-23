from fastapi import HTTPException

from app.schemas.auth import UserRegister
from app.core.security import hash_password


users_db = {}


def register_user(user: UserRegister):
    if user.email in users_db:
        raise HTTPException(
            status_code=409,
            detail="Email уже зарегистрирован"
        )

    for existing_user in users_db.values():
        if existing_user["username"] == user.username:
            raise HTTPException(
                status_code=409,
                detail="Никнейм уже занят"
            )

    hashed_password = hash_password(user.password)

    users_db[user.email] = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_password,
    }

    return {
        "username": user.username,
        "email": user.email,
    }

from fastapi import HTTPException, status

from app.schemas.auth import UserLogin
from app.core.security import verify_password


def authenticate_user(user: UserLogin):
    existing_user = users_db.get(user.email)

    if existing_user is None or not verify_password(
        user.password,
        existing_user["hashed_password"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )

    return {
        "username": existing_user["username"],
        "email": existing_user["email"],
    }