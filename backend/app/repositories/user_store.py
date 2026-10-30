from threading import Lock
from uuid import uuid4

users_db: dict[str, dict[str, str]] = {}
_users_lock = Lock()


class UserAlreadyExistsError(Exception):
    pass


def create_user(username: str, email: str, hashed_password: str) -> None:
    with _users_lock:
        if email in users_db:
            raise UserAlreadyExistsError("Email уже зарегистрирован")

        if any(user["username"] == username for user in users_db.values()):
            raise UserAlreadyExistsError("Никнейм уже занят")

        users_db[email] = {
            "id": str(uuid4()),
            "username": username,
            "email": email,
            "hashed_password": hashed_password,
        }


def get_user_by_email(email: str) -> dict[str, str] | None:
    with _users_lock:
        user = users_db.get(email)
        return user.copy() if user is not None else None


def get_user_by_username(username: str) -> dict[str, str] | None:
    with _users_lock:
        for user in users_db.values():
            if user["username"] == username:
                return user.copy()
    return None


def get_user_by_id(user_id: str) -> dict[str, str] | None:
    with _users_lock:
        for user in users_db.values():
            if user["id"] == user_id:
                return user.copy()
    return None
