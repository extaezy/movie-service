from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import jwt
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

pytestmark = pytest.mark.asyncio


@pytest.fixture
def auth_api(monkeypatch, token_context, auth_password_hash):
    from app.api import auth, dependencies
    from app.services import auth_service

    app = FastAPI()
    app.include_router(auth.router)
    session = MagicMock(spec=AsyncSession)
    user = User(
        id=token_context.user_id,
        username="student_1",
        email="student@example.com",
        hashed_password=auth_password_hash,
        is_active=True,
    )
    get_by_username = AsyncMock(return_value=user)
    get_by_email = AsyncMock(return_value=user)
    get_by_id = AsyncMock(return_value=user)
    monkeypatch.setattr(auth_service, "get_user_by_username", get_by_username)
    monkeypatch.setattr(auth_service, "get_user_by_email", get_by_email)
    monkeypatch.setattr(dependencies, "get_user_by_id", get_by_id)

    async def offline_database():
        yield session

    app.dependency_overrides[auth.get_db] = offline_database
    return SimpleNamespace(
        app=app,
        session=session,
        user=user,
        password="testing-password-123",
        get_by_username=get_by_username,
        get_by_email=get_by_email,
        get_by_id=get_by_id,
        token_context=token_context,
    )


@pytest_asyncio.fixture
async def auth_client(auth_api):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=auth_api.app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.parametrize(
    ("identifier", "lookup"),
    [
        ("student_1", "username"),
        ("student@example.com", "email"),
        ("student@EXAMPLE.COM", "email"),
    ],
)
async def test_login_issues_usable_token_without_sensitive_fields(
    auth_client, auth_api, identifier, lookup
):
    started_at = int(datetime.now(UTC).timestamp())
    response = await auth_client.post(
        "/auth/login",
        json={"identifier": identifier, "password": auth_api.password},
    )
    assert response.status_code == 200
    finished_at = int(datetime.now(UTC).timestamp())
    body = response.json()
    assert set(body) == {"access_token", "token_type"}
    assert isinstance(body["access_token"], str)
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert auth_api.password not in response.text
    assert auth_api.user.hashed_password not in response.text
    claims = jwt.decode(
        body["access_token"],
        auth_api.token_context.secret,
        algorithms=["HS256"],
        options={"require": ["sub", "iat", "exp"]},
    )
    assert claims["sub"] == str(auth_api.user.id)
    assert type(claims["iat"]) is int
    assert type(claims["exp"]) is int
    assert claims["exp"] - claims["iat"] == 1800
    assert started_at <= claims["iat"] <= finished_at
    assert jwt.get_unverified_header(body["access_token"])["alg"] == "HS256"
    if lookup == "username":
        auth_api.get_by_username.assert_awaited_once_with(
            auth_api.session, auth_api.user.username
        )
        auth_api.get_by_email.assert_not_awaited()
    else:
        auth_api.get_by_email.assert_awaited_once_with(
            auth_api.session, auth_api.user.email
        )
        auth_api.get_by_username.assert_not_awaited()

    me = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json() == {
        "id": str(auth_api.user.id),
        "username": auth_api.user.username,
        "email": auth_api.user.email,
    }
    auth_api.get_by_id.assert_awaited_once_with(auth_api.session, auth_api.user.id)


@pytest.mark.parametrize("missing_field", ["identifier", "password"])
async def test_login_requires_fields_without_repository_calls(
    auth_client, auth_api, missing_field
):
    payload = {"identifier": auth_api.user.username, "password": auth_api.password}
    del payload[missing_field]
    response = await auth_client.post("/auth/login", json=payload)
    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", missing_field] and error["type"] == "missing"
        for error in response.json()["detail"]
    )
    assert "access_token" not in response.json()
    auth_api.get_by_username.assert_not_awaited()
    auth_api.get_by_email.assert_not_awaited()


@pytest.mark.parametrize("field_name", ["identifier", "password"])
@pytest.mark.parametrize(
    "invalid_value", [None, {"value": "invalid"}], ids=["null", "object"]
)
async def test_login_rejects_invalid_field_types_without_repository_calls(
    auth_client, auth_api, field_name, invalid_value
):
    payload = {"identifier": auth_api.user.username, "password": auth_api.password}
    payload[field_name] = invalid_value
    response = await auth_client.post("/auth/login", json=payload)
    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", field_name] for error in response.json()["detail"]
    )
    assert "access_token" not in response.json()
    auth_api.get_by_username.assert_not_awaited()
    auth_api.get_by_email.assert_not_awaited()


@pytest.mark.parametrize(
    "unknown_identifier", ["unknown_user", "unknown@example.com", "invalid@"]
)
async def test_unknown_user_and_wrong_password_have_same_unauthorized_response(
    auth_client, auth_api, unknown_identifier
):
    wrong_password = await auth_client.post(
        "/auth/login",
        json={"identifier": auth_api.user.username, "password": "wrong-password"},
    )
    auth_api.get_by_username.return_value = None
    auth_api.get_by_email.return_value = None
    unknown_user = await auth_client.post(
        "/auth/login",
        json={"identifier": unknown_identifier, "password": auth_api.password},
    )
    for response in (wrong_password, unknown_user):
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert "access_token" not in response.json()
        assert auth_api.password not in response.text
        assert auth_api.user.hashed_password not in response.text
    assert wrong_password.json() == unknown_user.json()


async def test_inactive_user_cannot_login(auth_client, auth_api):
    auth_api.user.is_active = False
    response = await auth_client.post(
        "/auth/login",
        json={"identifier": auth_api.user.username, "password": auth_api.password},
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "access_token" not in response.json()


async def test_login_preserves_username_case(auth_client, auth_api):
    auth_api.get_by_username.side_effect = lambda session, username: (
        auth_api.user if username == auth_api.user.username else None
    )
    response = await auth_client.post(
        "/auth/login",
        json={"identifier": "STUDENT_1", "password": auth_api.password},
    )
    assert response.status_code == 401
    auth_api.get_by_username.assert_awaited_once_with(auth_api.session, "STUDENT_1")
    auth_api.get_by_email.assert_not_awaited()


@pytest.mark.parametrize("position", ["leading", "trailing"])
async def test_login_does_not_trim_password(auth_client, auth_api, position):
    password = (
        " " + auth_api.password if position == "leading" else auth_api.password + " "
    )
    response = await auth_client.post(
        "/auth/login", json={"identifier": auth_api.user.username, "password": password}
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "access_token" not in response.json()


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic credentials"},
        {"Authorization": "Bearer invalid"},
    ],
    ids=["missing", "empty-bearer", "wrong-scheme", "malformed-token"],
)
async def test_me_rejects_missing_or_malformed_credentials_without_lookup(
    auth_client, auth_api, headers
):
    response = await auth_client.get("/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "id" not in response.json()
    assert "email" not in response.json()
    auth_api.get_by_id.assert_not_awaited()


@pytest.mark.parametrize("user_state", ["missing", "inactive"])
async def test_me_rejects_unknown_and_inactive_token_owners(
    auth_client, auth_api, user_state
):
    if user_state == "missing":
        auth_api.get_by_id.return_value = None
    else:
        auth_api.user.is_active = False
    response = await auth_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {auth_api.token_context.valid_token}"},
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    auth_api.get_by_id.assert_awaited_once_with(auth_api.session, auth_api.user.id)


async def test_me_returns_only_the_requested_token_owner(auth_client, auth_api):
    second_user = User(
        id=uuid4(),
        username="student_2",
        email="second@example.com",
        hashed_password=auth_api.user.hashed_password,
        is_active=True,
    )
    users = {auth_api.user.id: auth_api.user, second_user.id: second_user}
    auth_api.get_by_id.side_effect = lambda session, user_id: users.get(user_id)
    for user in users.values():
        token = auth_api.token_context.tokens.create_access_token(str(user.id))
        response = await auth_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json() == {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
        }
        assert user.hashed_password not in response.text
    assert auth_api.get_by_id.await_count == 2


@pytest.mark.parametrize(
    "invalid_case",
    [
        "expired",
        "future-issued",
        "wrong-key",
        "wrong-algorithm",
        "missing-sub",
        "missing-iat",
        "missing-exp",
        "invalid-subject",
        "empty-subject",
    ],
)
async def test_me_rejects_invalid_jwt_before_user_lookup(
    auth_client, auth_api, invalid_case
):
    context = auth_api.token_context
    claims = context.claims.copy()
    signing_key = context.secret
    algorithm = "HS256"
    if invalid_case == "expired":
        claims["iat"] -= 3600
        claims["exp"] -= 3600
    elif invalid_case == "future-issued":
        claims["iat"] += 300
        claims["exp"] += 300
    elif invalid_case == "wrong-key":
        signing_key += "-other"
    elif invalid_case == "wrong-algorithm":
        algorithm = "HS384"
    elif invalid_case.startswith("missing-"):
        del claims[invalid_case.removeprefix("missing-")]
    elif invalid_case == "invalid-subject":
        claims["sub"] = "not-a-uuid"
    else:
        claims["sub"] = ""

    token = jwt.encode(claims, signing_key, algorithm=algorithm)
    response = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert set(response.json()) == {"detail"}
    assert token not in response.text
    assert context.secret not in response.text
    auth_api.get_by_id.assert_not_awaited()
