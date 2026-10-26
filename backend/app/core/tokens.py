from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=30)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp"]},
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidTokenError("Invalid claims") from exc
    if not isinstance(payload["sub"], str) or not payload["sub"]:
        raise InvalidTokenError("Invalid subject")
    if type(payload["iat"]) is not int or type(payload["exp"]) is not int:
        raise InvalidTokenError("Invalid timestamps")
    if payload["exp"] <= payload["iat"]:
        raise InvalidTokenError("Invalid lifetime")
    return payload["sub"]
