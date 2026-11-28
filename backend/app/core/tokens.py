from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


def create_access_token(
    user_id: str, session_id: str, expires_at: datetime | None = None
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "sid": session_id,
            "jti": str(uuid4()),
            "iat": now,
            "exp": min(now + timedelta(minutes=30), expires_at)
            if expires_at
            else now + timedelta(minutes=30),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> tuple[UUID, UUID]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "sid", "iat", "exp"]},
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidTokenError("Invalid claims") from exc
    if not isinstance(payload["sub"], str) or not payload["sub"]:
        raise InvalidTokenError("Invalid subject")
    if type(payload["iat"]) is not int or type(payload["exp"]) is not int:
        raise InvalidTokenError("Invalid timestamps")
    if payload["exp"] <= payload["iat"]:
        raise InvalidTokenError("Invalid lifetime")
    try:
        return UUID(payload["sub"]), UUID(payload["sid"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidTokenError("Invalid session") from exc
