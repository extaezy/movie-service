import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile, User

pytestmark = [
    pytest.mark.skipif(
        os.getenv("MOVIE_SERVICE_RUN_DATABASE_SMOKE") != "1",
        reason="Set MOVIE_SERVICE_RUN_DATABASE_SMOKE=1 to check the configured database",
    ),
    pytest.mark.asyncio,
]


async def test_database_auth_with_rollback():
    from app.db.database import engine, get_db
    from app.main import app

    username = f"probe_{uuid4().hex[:14]}"
    registration = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "database-check-password",
        "password_confirm": "database-check-password",
    }
    previous_overrides = app.dependency_overrides.copy()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()

            async def test_session():
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    yield session

            app.dependency_overrides[get_db] = test_session
            try:
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post("/auth/register", json=registration)
                    assert response.status_code == 201
                    assert response.json() == {
                        "username": username,
                        "email": registration["email"],
                    }
                    async with AsyncSession(
                        bind=connection, join_transaction_mode="create_savepoint"
                    ) as session:
                        user = await session.scalar(
                            select(User).where(User.username == username)
                        )
                        assert user is not None
                        user_id = user.id
                        assert user.hashed_password.startswith("$argon2id$")
                        assert await session.get(Profile, user_id) is not None
                    for duplicate in (
                        {**registration, "email": f"other_{username}@example.com"},
                        {**registration, "username": f"other_{uuid4().hex[:14]}"},
                    ):
                        response = await client.post("/auth/register", json=duplicate)
                        assert response.status_code == 409
                    for identifier in (username, registration["email"]):
                        login = await client.post(
                            "/auth/login",
                            json={
                                "identifier": identifier,
                                "password": registration["password"],
                            },
                        )
                        assert login.status_code == 200
                        token = login.json()["access_token"]
                        me = await client.get(
                            "/auth/me", headers={"Authorization": f"Bearer {token}"}
                        )
                        assert me.status_code == 200
                        assert me.json() == {
                            "id": str(user_id),
                            "username": username,
                            "email": registration["email"],
                        }
                    assert (await client.get("/auth/me")).status_code == 401
                    wrong = await client.post(
                        "/auth/login",
                        json={"identifier": username, "password": "wrong-password"},
                    )
                    assert wrong.status_code == 401
                    async with AsyncSession(
                        bind=connection, join_transaction_mode="create_savepoint"
                    ) as session, session.begin():
                        user = await session.get(User, user_id)
                        user.is_active = False
                    inactive = await client.post(
                        "/auth/login",
                        json={
                            "identifier": username,
                            "password": registration["password"],
                        },
                    )
                    assert inactive.status_code == 401
                    assert (
                        await client.get(
                            "/auth/me", headers={"Authorization": f"Bearer {token}"}
                        )
                    ).status_code == 401
            finally:
                await transaction.rollback()
                app.dependency_overrides.clear()
                app.dependency_overrides.update(previous_overrides)
        async with engine.connect() as connection:
            assert await connection.scalar(
                select(User.id).where(User.username == username)
            ) is None
    finally:
        await engine.dispose()
