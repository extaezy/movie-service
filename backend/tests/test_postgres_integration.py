import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Base,
    Critic,
    CriticReview,
    CriticSource,
    Friendship,
    Movie,
    Profile,
    Rating,
    User,
    UserMovieEntry,
    UserReview,
)

TEST_DATABASE_URL = os.getenv("MOVIE_SERVICE_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason="Set MOVIE_SERVICE_TEST_DATABASE_URL to a disposable local PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="module"),
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def database():
    url = make_url(TEST_DATABASE_URL)
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail(
            "Integration tests require a disposable LOCAL database, never shared Supabase"
        )
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", TEST_DATABASE_URL)
        patch.setenv("DATABASE_SSL", "disable")
        patch.setenv(
            "JWT_SECRET_KEY",
            "local-integration-tests-secret-key-at-least-32-characters",
        )
        from app.db.database import async_session, engine
        from app.main import app

        yield SimpleNamespace(app=app, sessions=async_session, engine=engine)
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True, loop_scope="module")
async def clean_database(database):
    names = ", ".join(
        f'movie_service."{table.name}"' for table in Base.metadata.sorted_tables
    )
    async with database.engine.begin() as connection:
        await connection.execute(
            text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE")
        )


@pytest_asyncio.fixture(loop_scope="module")
async def client(database):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=database.app), base_url="http://test"
    ) as value:
        yield value


def registration():
    return {
        "username": "student_1",
        "email": "student@example.com",
        "password": "testing-password-123",
        "password_confirm": "testing-password-123",
    }


async def test_registration_commits_user_and_profile(client, database):
    result = await client.post("/auth/register", json=registration())
    assert result.status_code == 201
    assert set(result.json()) == {"username", "email"}
    async with database.sessions() as session:
        user = await session.scalar(select(User).where(User.username == "student_1"))
        assert user is not None
        assert user.hashed_password.startswith("$argon2id$")
        assert await session.get(Profile, user.id) is not None
    await database.engine.dispose()
    logged_in = await client.post(
        "/auth/login",
        json={"identifier": "student_1", "password": "testing-password-123"},
    )
    assert logged_in.status_code == 200


async def test_registration_requires_username(client, database):
    payload = registration()
    del payload["username"]

    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", "username"] and error["type"] == "missing"
        for error in response.json()["detail"]
    )
    async with database.sessions() as session:
        assert (await session.scalars(select(User))).all() == []
        assert (await session.scalars(select(Profile))).all() == []


async def test_registration_requires_email(client, database):
    payload = registration()
    del payload["email"]

    response = await client.post("auth/register", json = payload)

    assert response.status_code == 422
    assert any (
        error["loc"] == ["body", "email"] and error["type"] == "missing"
        for error in response.json()["detail"]
    )

    async with database.sessions() as session:
        assert (await session.scalars(select(User))).all() == []
        assert (await session.scalars(select(Profile))).all() == []

@pytest.mark.parametrize("email", ["invalid-email", "name@", "@example.com"])
async def test_registration_rejects_invalid_email(client, database, email):
    payload = registration()
    payload["email"] = email

    response = await client.post("auth/register", json = payload)

    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", "email"]
        for error in response.json()["detail"]
    )

    async with database.sessions() as session:
        assert (await session.scalars(select(User))).all() == []
        assert (await session.scalars(select(Profile))).all() == []

@pytest.mark.parametrize("username", ["abc", "abcd", "a" * 20, "a" * 21])
async def test_registration_validates_username_length(client, database, username):
    payload = registration()
    payload["username"] = username

    response = await client.post("auth/register", json = payload)

    if len(username) < 4 or len(username) > 20:
        assert response.status_code == 422
        assert any(
            error["loc"] == ["body", "username"]
            for error in response.json()["detail"]
        )

        async with database.sessions() as session:
            assert (await session.scalars(select(User))).all() == []
            assert (await session.scalars(select(Profile))).all() == []
    else:
        assert response.status_code == 201
        assert response.json() == {
            "username": username,
            "email": payload["email"],
        }

        async with database.sessions() as session:
            users = (await session.scalars(select(User))).all()
            profiles = (await session.scalars(select(Profile))).all()

            assert len(users) == 1
            assert len(profiles) == 1

            user = users[0]
            profile = profiles[0]

            assert user.username == username
            assert user.email == payload["email"]
            assert profile.user_id == user.id




async def test_me_returns_token_owner(client, database):
    first_user_data = registration()
    second_user_data = registration()
    second_user_data["username"] = "student_2"
    second_user_data["email"] = "second@example.com"

    first_registration = await client.post("/auth/register", json=first_user_data)
    assert first_registration.status_code == 201

    second_registration = await client.post("/auth/register", json=second_user_data)
    assert second_registration.status_code == 201

    first_login = await client.post(
        "/auth/login",
        json={
            "identifier": first_user_data["username"],
            "password": first_user_data["password"],
        },
    )
    assert first_login.status_code == 200
    first_token = first_login.json()["access_token"]

    second_login = await client.post(
        "/auth/login",
        json={
            "identifier": second_user_data["username"],
            "password": second_user_data["password"],
        },
    )
    assert second_login.status_code == 200
    second_token = second_login.json()["access_token"]

    first_me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert first_me.status_code == 200

    second_me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert second_me.status_code == 200

    async with database.sessions() as session:
        first_user = await session.scalar(
            select(User).where(
                User.username == first_user_data["username"]
            )
        )
        second_user = await session.scalar(
            select(User).where(
                User.username == second_user_data["username"]
            )
        )

        assert first_user is not None
        assert second_user is not None

        first_id = first_me.json()["id"]
        second_id = second_me.json()["id"]

        assert first_id != second_id

        assert first_id == str(first_user.id)
        assert second_id == str(second_user.id)

        assert first_me.json() == {
            "id": str(first_user.id),
            "username": first_user_data["username"],
            "email": first_user_data["email"],
        }

        assert second_me.json() == {
            "id": str(second_user.id),
            "username": second_user_data["username"],
            "email": second_user_data["email"],
        }





@pytest.mark.parametrize("duplicate_field", ["username", "email"])
async def test_duplicate_registration_is_conflict(client, database, duplicate_field):
    original = registration()
    assert (await client.post("/auth/register", json=original)).status_code == 201
    duplicate = {**original, "username": "student_2", "email": "second@example.com"}
    duplicate[duplicate_field] = original[duplicate_field]
    assert (await client.post("/auth/register", json=duplicate)).status_code == 409
    async with database.sessions() as session:
        assert len((await session.scalars(select(User))).all()) == 1
        assert len((await session.scalars(select(Profile))).all()) == 1


@pytest.mark.parametrize("identifier", ["student_1", "student@example.com"])
async def test_login_and_me(client, identifier):
    assert (await client.post("/auth/register", json=registration())).status_code == 201
    logged_in = await client.post(
        "/auth/login",
        json={"identifier": identifier, "password": "testing-password-123"},
    )
    assert logged_in.status_code == 200
    token = logged_in.json()["access_token"]
    result = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 200
    assert set(result.json()) == {"id", "username", "email"}
    assert result.json()["username"] == "student_1"
    assert (await client.get("/auth/me")).status_code == 401
    assert (
        await client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
    ).status_code == 401


async def test_inactive_user_and_wrong_credentials_are_rejected(client, database):
    await client.post("/auth/register", json=registration())
    login = {"identifier": "student_1", "password": "testing-password-123"}
    token = (await client.post("/auth/login", json=login)).json()["access_token"]
    missing = await client.post(
        "/auth/login", json={**login, "identifier": "missing_user"}
    )
    wrong = await client.post(
        "/auth/login", json={**login, "password": "wrong-password"}
    )
    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()
    async with database.sessions() as session, session.begin():
        user = await session.scalar(select(User))
        user.is_active = False
    assert (await client.post("/auth/login", json=login)).status_code == 401
    assert (
        await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401


@pytest_asyncio.fixture(loop_scope="module")
async def records(database):
    async with database.sessions() as session:
        async with session.begin():
            user = User(
                username="reviewer",
                email="reviewer@example.com",
                hashed_password="test-only",
            )
            movie = Movie(tmdb_id=12345, title="Test movie")
            session.add_all([user, movie])
        return user.id, movie.id


@pytest.mark.parametrize("score", [0, 11, None])
async def test_invalid_ratings_are_rejected(database, records, score):
    user_id, movie_id = records
    async with database.sessions() as session:
        with pytest.raises(IntegrityError):
            async with session.begin():
                session.add(Rating(user_id=user_id, movie_id=movie_id, score=score))


async def test_unique_content_and_multiple_lists(database, records):
    user_id, movie_id = records
    async with database.sessions() as session:
        async with session.begin():
            session.add_all(
                [
                    Rating(user_id=user_id, movie_id=movie_id, score=8),
                    UserReview(
                        user_id=user_id, movie_id=movie_id, text="Useful review"
                    ),
                    UserMovieEntry(
                        user_id=user_id, movie_id=movie_id, list_type="watched"
                    ),
                    UserMovieEntry(
                        user_id=user_id, movie_id=movie_id, list_type="favorite"
                    ),
                ]
            )
        for duplicate in [
            Rating(user_id=user_id, movie_id=movie_id, score=9),
            UserReview(user_id=user_id, movie_id=movie_id, text="Second review"),
            UserMovieEntry(user_id=user_id, movie_id=movie_id, list_type="watched"),
        ]:
            with pytest.raises(IntegrityError):
                async with session.begin():
                    session.add(duplicate)


async def test_friendship_cannot_be_self_or_have_unrelated_requester(database, records):
    user_id, _ = records
    async with database.sessions() as session:
        async with session.begin():
            second = User(
                username="second_user",
                email="second@example.com",
                hashed_password="test-only",
            )
            third = User(
                username="third_user",
                email="third@example.com",
                hashed_password="test-only",
            )
            session.add_all([second, third])
        low, high = sorted([user_id, second.id])
        for values in [
            (user_id, user_id, user_id),
            (high, low, low),
            (low, high, third.id),
        ]:
            with pytest.raises(IntegrityError):
                async with session.begin():
                    session.add(
                        Friendship(
                            user_low_id=values[0],
                            user_high_id=values[1],
                            requested_by_id=values[2],
                        )
                    )


async def test_critic_source_consistency_and_unknown_author(database, records):
    _, movie_id = records
    async with database.sessions() as session:
        async with session.begin():
            first = CriticSource(name="Source A")
            second = CriticSource(name="Source B")
            session.add_all([first, second])
            await session.flush()
            critic = Critic(name="Test Critic", source_id=first.id)
            session.add(critic)
        second_id, critic_id = second.id, critic.id
        values = {
            "movie_id": movie_id,
            "excerpt": "Excerpt",
            "external_url": "https://example.com/review",
            "language": "en",
            "verdict": "positive",
        }
        with pytest.raises(IntegrityError):
            async with session.begin():
                session.add(
                    CriticReview(**values, critic_id=critic_id, source_id=second_id)
                )
        async with session.begin():
            session.add(CriticReview(**values, source_id=second_id))


async def test_missing_foreign_key_and_cascade_delete(database, records):
    user_id, movie_id = records
    async with database.sessions() as session:
        with pytest.raises(IntegrityError):
            async with session.begin():
                session.add(Rating(user_id=uuid4(), movie_id=movie_id, score=8))
        async with session.begin():
            session.add(Rating(user_id=user_id, movie_id=movie_id, score=8))
        async with session.begin():
            user = await session.get(User, user_id)
            await session.delete(user)
        assert (await session.scalars(select(Rating))).all() == []


async def test_tables_have_rls_and_root_is_available(client, database):
    async with database.engine.connect() as connection:
        count = await connection.scalar(
            text(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='movie_service' AND c.relkind='r' AND c.relrowsecurity"
            )
        )
        assert count == 12
    assert (await client.get("/")).status_code == 200
