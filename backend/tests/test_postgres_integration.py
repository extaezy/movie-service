import asyncio
import os
from datetime import date
from functools import partial
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    Base,
    Critic,
    CriticReview,
    CriticSource,
    Friendship,
    Genre,
    Movie,
    MovieGenre,
    Profile,
    Rating,
    User,
    UserMovieEntry,
    UserReview,
)
from app.integrations.tmdb import open_tmdb_client

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


@pytest.fixture
def catalog_tmdb(monkeypatch, tmdb_settings):
    from app.api import movies

    upstream_requests = []

    def use_upstream(handler):
        def record_request(request):
            upstream_requests.append(request)
            return handler(request)

        monkeypatch.setattr(
            movies,
            "open_tmdb_client",
            partial(
                open_tmdb_client,
                config=tmdb_settings,
                transport=httpx.MockTransport(record_request),
            ),
        )

    def unexpected_request(request):
        pytest.fail("This request must read the local catalog without calling TMDB")

    use_upstream(unexpected_request)
    return SimpleNamespace(
        use_upstream=use_upstream,
        upstream_requests=upstream_requests,
        settings=tmdb_settings,
    )


@pytest_asyncio.fixture(loop_scope="module")
async def isolated_movie_database(database, records, monkeypatch):
    from app.db import database as database_module

    application_name = f"movie-service-recovery-{uuid4().hex}"
    recovery_engine = create_async_engine(
        database.engine.url,
        connect_args={
            **database_module.connect_args,
            "server_settings": {"application_name": application_name},
        },
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        pool_timeout=2,
        hide_parameters=True,
    )
    sessions = async_sessionmaker(recovery_engine, expire_on_commit=False)
    terminated_pids = []

    async def terminate_connection(pid):
        async with database.engine.begin() as connection:
            terminated = await connection.scalar(
                text(
                    "SELECT pg_terminate_backend(pid, 5000) "
                    "FROM pg_stat_activity "
                    "WHERE pid = :pid AND application_name = :application_name "
                    "AND datname = current_database() AND pid <> pg_backend_pid()"
                ),
                {"pid": pid, "application_name": application_name},
            )
        assert terminated is True
        terminated_pids.append(pid)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(database_module, "async_session", sessions)
            yield SimpleNamespace(
                engine=recovery_engine,
                sessions=sessions,
                endpoint=f"/movies/{records[1]}",
                movie_id=records[1],
                terminate_connection=terminate_connection,
                terminated_pids=terminated_pids,
            )
    finally:
        await recovery_engine.dispose()


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


@pytest.mark.parametrize("missing_field", ["password", "password_confirm"])
async def test_registration_requires_password_fields(client, database, missing_field):
    payload = registration()
    endpoint = "/auth/register"
    expected_status = 422
    expected_location = ["body", missing_field]
    expected_error_type = "missing"

    del payload[missing_field]

    response = await client.post(endpoint, json=payload)

    assert response.status_code == expected_status
    assert any(
        error["loc"] == expected_location and error["type"] == expected_error_type
        for error in response.json()["detail"]
    )

    async with database.sessions() as session:
        assert (await session.scalars(select(User))).all() == []
        assert (await session.scalars(select(Profile))).all() == []


@pytest.mark.parametrize(
    "field_name",
    ["username", "email", "password", "password_confirm"],
)
@pytest.mark.parametrize(
    "invalid_value",
    [None, {"value": "invalid"}],
    ids=["null", "object"],
)
async def test_registration_rejects_invalid_field_types(
    client, database, field_name, invalid_value
):
    payload = registration()
    endpoint = "/auth/register"
    expected_status = 422
    expected_location = ["body", field_name]

    payload[field_name] = invalid_value

    response = await client.post(endpoint, json=payload)

    assert response.status_code == expected_status
    assert any(
        error["loc"] == expected_location
        for error in response.json()["detail"]
    )

    async with database.sessions() as session:
        assert (await session.scalars(select(User))).all() == []
        assert (await session.scalars(select(Profile))).all() == []


@pytest.mark.parametrize(
    ("username", "expected_status"),
    [
        ("abcd", 201),
        ("qa_123", 201),
        ("_abcd", 422),
        ("abcd_", 422),
        ("ab__cd", 422),
        ("ab cd", 422),
        ("тест", 422),
    ],
)
async def test_registration_validates_username_format(
    client, database, username, expected_status
):
    payload = registration()
    endpoint = "/auth/register"
    expected_location = ["body", "username"]

    payload["username"] = username

    response = await client.post(endpoint, json=payload)
    assert response.status_code == expected_status

    async with database.sessions() as session:
        if expected_status == 201:
            assert response.json() == {
                "username": username,
                "email": payload["email"],
            }
            users = (await session.scalars(select(User))).all()
            profiles = (await session.scalars(select(Profile))).all()
            assert len(users) == 1
            assert len(profiles) == 1

            user = users[0]
            profile = profiles[0]

            assert user.username == username
            assert user.email == payload["email"]
            assert profile.user_id == user.id
        else:
            assert any(
                error["loc"] == expected_location
                for error in response.json()["detail"]
            )
            assert (await session.scalars(select(User))).all() == []
            assert (await session.scalars(select(Profile))).all() == []


async def test_registration_treats_usernames_as_case_sensitive(client, database):
    first_payload = registration()
    second_payload = registration()
    first_username = "qa_alpha"
    second_username = "QA_ALPHA"
    second_email = "second@example.com"
    endpoint = "/auth/register"
    expected_status = 201
    expected_users_count = 2
    expected_profiles_count = 2

    first_payload["username"] = first_username
    second_payload["username"] = second_username
    second_payload["email"] = second_email

    first_response = await client.post(endpoint, json=first_payload)
    assert first_response.status_code == expected_status
    second_response = await client.post(endpoint, json=second_payload)
    assert second_response.status_code == expected_status
    async with database.sessions() as session:
        assert first_response.json() == {
            "username": first_username,
            "email": first_payload["email"],
        }
        assert second_response.json() == {
            "username": second_username,
            "email": second_email,
        }
        users = (await session.scalars(select(User))).all()
        profiles = (await session.scalars(select(Profile))).all()
        assert len(users) == expected_users_count
        assert len(profiles) == expected_profiles_count
        first_user = next(user for user in users if user.username == first_username)
        second_user = next(user for user in users if user.username == second_username)
        first_profile = next(
            profile for profile in profiles if profile.user_id == first_user.id
        )
        second_profile = next(
            profile for profile in profiles if profile.user_id == second_user.id
        )
        assert first_user.id != second_user.id
        assert first_user.email == first_payload["email"]
        assert second_user.email == second_payload["email"]
        assert first_profile.user_id == first_user.id
        assert second_profile.user_id == second_user.id


@pytest.mark.parametrize("duplicate_field", ["username", "email"])
async def test_concurrent_registration_rejects_duplicates(
    client, database, duplicate_field
):
    first_payload = registration()
    second_payload = registration()
    second_username = "student_2"
    second_email = "second@example.com"
    endpoint = "/auth/register"
    expected_statuses = [201, 409]
    expected_users_count = 1
    expected_profiles_count = 1

    second_payload["username"] = second_username
    second_payload["email"] = second_email
    second_payload[duplicate_field] = first_payload[duplicate_field]

    first_response, second_response = await asyncio.gather(
        client.post(endpoint, json=first_payload),
        client.post(endpoint, json=second_payload),
    )
    assert sorted([first_response.status_code, second_response.status_code]) == expected_statuses
    async with database.sessions() as session:
        if first_response.status_code == 201:
            successful_payload = first_payload
            successful_response = first_response
        else:
            successful_payload = second_payload
            successful_response = second_response
        assert successful_response.json() == {
            "username": successful_payload["username"],
            "email": successful_payload["email"],
        }
        users = (await session.scalars(select(User))).all()
        profiles = (await session.scalars(select(Profile))).all()
        assert len(users) == expected_users_count
        assert len(profiles) == expected_profiles_count
        user = users[0]
        profile = profiles[0]
        assert user.username == successful_payload["username"]
        assert user.email == successful_payload["email"]
        assert profile.user_id == user.id


async def test_registration_rolls_back_when_profile_creation_fails(
    client, database, monkeypatch
):
    payload = registration()
    endpoint = "/auth/register"
    expected_status = 503
    profile_creation_user_ids = []
    error_message = "Simulated profile creation timeout"

    def fail_profile_creation(*, user_id):
        profile_creation_user_ids.append(user_id)
        raise SQLAlchemyTimeoutError(error_message)

    monkeypatch.setattr(
        "app.repositories.user_repository.Profile",
        fail_profile_creation
    )

    response = await client.post(endpoint, json=payload)
    assert response.status_code == expected_status

    assert len(profile_creation_user_ids) == 1
    assert profile_creation_user_ids[0] is not None

    async with database.sessions() as session:
        assert (await session.scalars(select(User))).all() == []
        assert (await session.scalars(select(Profile))).all() == []


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


async def test_movie_import_commits_movie_genres_and_links(
    client, database, catalog_tmdb, tmdb_details_payload
):
    payload = tmdb_details_payload
    payload["genres"] = [
        {"id": 878, "name": "Фантастика"},
        {"id": 28, "name": "Боевик"},
    ]
    catalog_tmdb.use_upstream(lambda request: httpx.Response(200, json=payload))

    response = await client.get(f"/movies/tmdb/{payload['id']}")

    assert response.status_code == 200
    async with database.sessions() as session:
        movies = (await session.scalars(select(Movie))).all()
        genres = (await session.scalars(select(Genre))).all()
        links = (await session.scalars(select(MovieGenre))).all()
        assert len(movies) == 1
        assert len(genres) == 2
        assert len(links) == 2
        movie = movies[0]
        assert movie.tmdb_id == payload["id"]
        assert movie.release_date == date(1999, 3, 31)
        assert movie.runtime == payload["runtime"]
        assert {(link.movie_id, link.genre_id) for link in links} == {
            (movie.id, genre.id) for genre in genres
        }
        expected_response = {
            "id": movie.id,
            "tmdb_id": payload["id"],
            "title": payload["title"],
            "original_title": payload["original_title"],
            "overview": payload["overview"],
            "release_date": payload["release_date"],
            "poster_path": payload["poster_path"],
            "runtime": payload["runtime"],
            "original_language": payload["original_language"],
            "genres": [
                {"id": genre.id, "tmdb_id": genre.tmdb_id, "name": genre.name}
                for genre in sorted(genres, key=lambda genre: genre.tmdb_id)
            ],
        }
        assert {(genre.tmdb_id, genre.name) for genre in genres} == {
            (28, "Боевик"), (878, "Фантастика")
        }
    assert response.json() == expected_response
    local_response = await client.get(f"/movies/{movie.id}")
    assert local_response.status_code == 200
    assert local_response.json() == expected_response
    assert len(catalog_tmdb.upstream_requests) == 1


async def test_movie_import_persists_unknown_date_and_runtime(
    client, database, catalog_tmdb, tmdb_details_payload
):
    payload = tmdb_details_payload
    payload.update(release_date="", runtime=0, genres=[])
    catalog_tmdb.use_upstream(lambda request: httpx.Response(200, json=payload))

    response = await client.get(f"/movies/tmdb/{payload['id']}")

    assert response.status_code == 200
    assert response.json()["release_date"] is None
    assert response.json()["runtime"] is None
    assert response.json()["genres"] == []
    async with database.sessions() as session:
        movies = (await session.scalars(select(Movie))).all()
        assert len(movies) == 1
        assert movies[0].id == response.json()["id"]
        assert movies[0].tmdb_id == payload["id"]
        assert movies[0].release_date is None
        assert movies[0].runtime is None
        assert (await session.scalars(select(Genre))).all() == []
        assert (await session.scalars(select(MovieGenre))).all() == []


async def test_movie_import_reuses_existing_genres_and_deduplicates_links(
    client, database, catalog_tmdb, tmdb_details_payload
):
    async with database.sessions() as session, session.begin():
        existing_genre = Genre(tmdb_id=28, name="Сохранённый боевик")
        session.add(existing_genre)
    first_payload = {
        **tmdb_details_payload,
        "genres": [
            {"id": 28, "name": "Новое название"},
            {"id": 878, "name": "Фантастика"},
        ],
    }
    second_payload = {
        **tmdb_details_payload,
        "id": 604,
        "title": "Второй фильм",
        "genres": [
            {"id": 28, "name": "Новое название"},
            {"id": 18, "name": "Драма"},
            {"id": 18, "name": "Драма"},
        ],
    }
    payloads = {603: first_payload, 604: second_payload}
    catalog_tmdb.use_upstream(
        lambda request: httpx.Response(
            200, json=payloads[int(request.url.path.rsplit("/", 1)[-1])]
        )
    )

    first_response = await client.get("/movies/tmdb/603")
    second_response = await client.get("/movies/tmdb/604")

    assert first_response.status_code == second_response.status_code == 200
    assert first_response.json()["id"] != second_response.json()["id"]
    async with database.sessions() as session:
        movies = (await session.scalars(select(Movie))).all()
        genres = (await session.scalars(select(Genre))).all()
        links = (await session.scalars(select(MovieGenre))).all()
        assert len(movies) == 2
        assert len(genres) == 3
        assert len(links) == 4
        genres_by_tmdb_id = {genre.tmdb_id: genre for genre in genres}
        assert genres_by_tmdb_id[28].id == existing_genre.id
        assert genres_by_tmdb_id[28].name == "Сохранённый боевик"
        assert {(link.movie_id, link.genre_id) for link in links} == {
            (first_response.json()["id"], genres_by_tmdb_id[28].id),
            (first_response.json()["id"], genres_by_tmdb_id[878].id),
            (second_response.json()["id"], genres_by_tmdb_id[28].id),
            (second_response.json()["id"], genres_by_tmdb_id[18].id),
        }
        for response, genre_ids in [
            (first_response, [28, 878]),
            (second_response, [18, 28]),
        ]:
            assert response.json()["genres"] == [
                {
                    "id": genres_by_tmdb_id[tmdb_id].id,
                    "tmdb_id": tmdb_id,
                    "name": genres_by_tmdb_id[tmdb_id].name,
                }
                for tmdb_id in genre_ids
            ]
    assert len(catalog_tmdb.upstream_requests) == 2


@pytest.mark.parametrize("token", ["", "local-tmdb-test-token"], ids=["no-token", "configured"])
async def test_cached_movie_is_read_from_database_without_tmdb(
    client, database, catalog_tmdb, tmdb_details_payload, token
):
    payload = tmdb_details_payload
    catalog_tmdb.use_upstream(lambda request: httpx.Response(200, json=payload))
    imported_response = await client.get(f"/movies/tmdb/{payload['id']}")
    assert imported_response.status_code == 200
    original_card = imported_response.json()
    payload["title"] = "Изменённое название TMDB"
    payload["genres"] = [{"id": 18, "name": "Драма"}]
    catalog_tmdb.settings.tmdb_access_token = SecretStr(token)

    def unavailable_upstream(request):
        pytest.fail("Cached cards must not call the unavailable external service")

    catalog_tmdb.use_upstream(unavailable_upstream)

    repeated_response = await client.get(f"/movies/tmdb/{payload['id']}")
    local_response = await client.get(f"/movies/{original_card['id']}")

    assert repeated_response.status_code == local_response.status_code == 200
    assert repeated_response.json() == local_response.json() == original_card
    assert len(catalog_tmdb.upstream_requests) == 1
    async with database.sessions() as session:
        movies = (await session.scalars(select(Movie))).all()
        genres = (await session.scalars(select(Genre))).all()
        links = (await session.scalars(select(MovieGenre))).all()
        assert len(movies) == len(genres) == len(links) == 1
        assert movies[0].id == original_card["id"]
        assert movies[0].title == original_card["title"]
        assert genres[0].tmdb_id == 28
        assert (links[0].movie_id, links[0].genre_id) == (movies[0].id, genres[0].id)


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [("not-found", 404), ("adult", 404), ("wrong-id", 502), ("timeout", 502)],
)
async def test_failed_movie_import_leaves_catalog_empty(
    client, database, catalog_tmdb, tmdb_details_payload, failure, expected_status
):
    payload = tmdb_details_payload
    if failure == "adult":
        payload["adult"] = True
    elif failure == "wrong-id":
        payload["id"] += 1

    def upstream(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("Simulated TMDB timeout", request=request)
        return httpx.Response(404 if failure == "not-found" else 200, json=payload)

    catalog_tmdb.use_upstream(upstream)

    response = await client.get("/movies/tmdb/603")

    assert response.status_code == expected_status
    assert set(response.json()) == {"detail"}
    assert len(catalog_tmdb.upstream_requests) == 1
    async with database.sessions() as session:
        assert (await session.scalars(select(Movie))).all() == []
        assert (await session.scalars(select(Genre))).all() == []
        assert (await session.scalars(select(MovieGenre))).all() == []


async def test_movie_import_rolls_back_all_catalog_rows_after_database_failure(
    client, database, catalog_tmdb, tmdb_details_payload, monkeypatch
):
    from app.repositories import movie_repository

    payload = tmdb_details_payload
    catalog_tmdb.use_upstream(lambda request: httpx.Response(200, json=payload))
    pending_rows = []

    async def fail_after_inserts(session, movie):
        movies = (await session.scalars(select(Movie))).all()
        genres = (await session.scalars(select(Genre))).all()
        links = (await session.scalars(select(MovieGenre))).all()
        pending_rows.append((len(movies), len(genres), len(links)))
        raise SQLAlchemyTimeoutError("Simulated database failure after catalog inserts")

    with monkeypatch.context() as patch:
        patch.setattr(movie_repository, "movie_response", fail_after_inserts)
        failed_response = await client.get(f"/movies/tmdb/{payload['id']}")

    assert failed_response.status_code == 503
    assert failed_response.json() == {"detail": "База данных временно недоступна"}
    assert pending_rows == [(1, 1, 1)]
    async with database.sessions() as session:
        assert (await session.scalars(select(Movie))).all() == []
        assert (await session.scalars(select(Genre))).all() == []
        assert (await session.scalars(select(MovieGenre))).all() == []

    recovered_response = await client.get(f"/movies/tmdb/{payload['id']}")

    assert recovered_response.status_code == 200
    assert recovered_response.json()["tmdb_id"] == payload["id"]
    async with database.sessions() as session:
        movies = (await session.scalars(select(Movie))).all()
        genres = (await session.scalars(select(Genre))).all()
        links = (await session.scalars(select(MovieGenre))).all()
        assert len(movies) == len(genres) == len(links) == 1
        assert movies[0].id == recovered_response.json()["id"]
        assert (links[0].movie_id, links[0].genre_id) == (movies[0].id, genres[0].id)
    assert len(catalog_tmdb.upstream_requests) == 2


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


async def test_concurrent_movie_imports_keep_one_card(
    client, database, catalog_tmdb, tmdb_details_payload
):
    endpoint = "/movies/tmdb/603"
    request_count = 2
    barrier = asyncio.Barrier(request_count)
    timeout_seconds = 5

    payloads = [
        {
            **tmdb_details_payload,
            "title": "Первая версия",
            "genres": [{"id": 28, "name": "Боевик"}],
        },
        {
            **tmdb_details_payload,
            "title": "Вторая версия",
            "genres": [{"id": 18, "name": "Драма"}],
        },
    ]

    expected_status = 200
    expected_movie_count = 1
    expected_genre_count = 1
    expected_link_count = 1
    expected_upstream_request_count = 2

    async def upstream(request):
        payload = payloads[len(catalog_tmdb.upstream_requests) - 1]
        await barrier.wait()
        return httpx.Response(status_code=200, json=payload)

    catalog_tmdb.use_upstream(upstream)
    responses = await asyncio.wait_for(
        asyncio.gather(
            client.get(endpoint),
            client.get(endpoint),
        ),
        timeout=timeout_seconds,
    )
    assert responses[0].status_code == expected_status
    assert responses[1].status_code == expected_status

    first_card = responses[0].json()
    second_card = responses[1].json()
    allowed_versions = []
    for payload in payloads:
        allowed_versions.append(
            (payload["title"], payload["genres"][0]["id"], payload["genres"][0]["name"])
        )
    actual_version = (
        first_card["title"],
        first_card["genres"][0]["tmdb_id"],
        first_card["genres"][0]["name"],
    )
    assert actual_version in allowed_versions
    assert first_card == second_card
    assert first_card["tmdb_id"] == tmdb_details_payload["id"]
    assert len(catalog_tmdb.upstream_requests) == expected_upstream_request_count
    async with database.sessions() as session:
        movies = (await session.scalars(select(Movie))).all()
        genres = (await session.scalars(select(Genre))).all()
        links = (await session.scalars(select(MovieGenre))).all()
        assert len(movies) == expected_movie_count
        assert len(genres) == expected_genre_count
        assert len(links) == expected_link_count
        movie = movies[0]
        genre = genres[0]
        link = links[0]
        assert movie.id == first_card["id"]
        assert movie.tmdb_id == first_card["tmdb_id"]
        assert movie.title == first_card["title"]
        assert first_card["genres"] == [
            {"id": genre.id, "tmdb_id": genre.tmdb_id, "name": genre.name}
        ]
        assert (link.movie_id, link.genre_id) == (movie.id, genre.id)

    def unexpected_request(request):
        pytest.fail("Repeated opening must use the saved card without calling TMDB")

    catalog_tmdb.use_upstream(unexpected_request)
    repeated_response = await client.get(endpoint)
    assert repeated_response.status_code == expected_status
    assert repeated_response.json() == first_card
    assert len(catalog_tmdb.upstream_requests) == expected_upstream_request_count


async def test_concurrent_movie_imports_share_one_genre(
    client, database, catalog_tmdb, tmdb_details_payload
):
    tmdb_ids = (603, 604)
    endpoints = (
        "/movies/tmdb/603",
        "/movies/tmdb/604",
    )

    request_count = 2
    barrier = asyncio.Barrier(request_count)
    timeout_seconds = 5

    shared_genre = {"id": 28, "name": "Боевик"}

    payloads = {
        603: {
            **tmdb_details_payload,
            "id": 603,
            "title": "Первый фильм",
            "genres": [shared_genre.copy()],
        },
        604: {
            **tmdb_details_payload,
            "id": 604,
            "title": "Второй фильм",
            "genres": [shared_genre.copy()],
        },
    }

    expected_status = 200
    expected_movie_count = 2
    expected_genre_count = 1
    expected_link_count = 2
    expected_upstream_request_count = 2

    async def upstream(request):
        payload_id = int(request.url.path.split("/")[-1])
        payload = payloads[payload_id]
        await barrier.wait()
        return httpx.Response(status_code=200, json=payload)

    catalog_tmdb.use_upstream(upstream)
    responses = await asyncio.wait_for(
        asyncio.gather(
            client.get(endpoints[0]),
            client.get(endpoints[1]),
        ),
        timeout=timeout_seconds,
    )
    assert responses[0].status_code == expected_status
    assert responses[1].status_code == expected_status
    first_card = responses[0].json()
    second_card = responses[1].json()
    assert first_card["tmdb_id"] == tmdb_ids[0]
    assert second_card["tmdb_id"] == tmdb_ids[1]
    assert first_card["title"] == payloads[603]["title"]
    assert second_card["title"] == payloads[604]["title"]
    assert first_card["id"] != second_card["id"]
    assert len(first_card["genres"]) == expected_genre_count
    assert len(second_card["genres"]) == expected_genre_count
    assert first_card["genres"][0]["tmdb_id"] == shared_genre["id"]
    assert second_card["genres"][0]["tmdb_id"] == shared_genre["id"]
    assert first_card["genres"][0]["name"] == shared_genre["name"]
    assert second_card["genres"][0]["name"] == shared_genre["name"]
    assert first_card["genres"] == second_card["genres"]
    assert len(catalog_tmdb.upstream_requests) == expected_upstream_request_count
    async with database.sessions() as session:
        result_movies = await session.scalars(select(Movie))
        movies = result_movies.all()
        assert len(movies) == expected_movie_count
        result_genres = await session.scalars(select(Genre))
        genres = result_genres.all()
        assert len(genres) == expected_genre_count
        result_links = await session.scalars(select(MovieGenre))
        links = result_links.all()
        assert len(links) == expected_link_count
        movies_by_tmdb_id = {movie.tmdb_id: movie for movie in movies}
        assert set(movies_by_tmdb_id) == set(tmdb_ids)
        genre = genres[0]
        assert genre.tmdb_id == shared_genre["id"]
        assert genre.name == shared_genre["name"]
        for card in [first_card, second_card]:
            movie = movies_by_tmdb_id[card["tmdb_id"]]
            assert movie.id == card["id"]
            assert movie.title == card["title"]
            assert card["genres"] == [
                {"id": genre.id, "tmdb_id": genre.tmdb_id, "name": genre.name}
            ]
        assert {(link.movie_id, link.genre_id) for link in links} == {
            (movies_by_tmdb_id[tmdb_id].id, genre.id) for tmdb_id in tmdb_ids
        }


async def test_local_movie_read_recovers_after_connection_termination(
    client, database, isolated_movie_database, catalog_tmdb, monkeypatch
):
    from app.api import movies

    endpoint = isolated_movie_database.endpoint
    initial_response = await client.get(endpoint)
    assert initial_response.status_code == 200
    expected_card = initial_response.json()
    original_read = movies.get_movie_by_id
    interrupted_pids = []

    async def terminate_before_read(session, movie_id):
        pid = await session.scalar(text("SELECT pg_backend_pid()"))
        interrupted_pids.append(pid)
        await isolated_movie_database.terminate_connection(pid)
        return await original_read(session, movie_id)

    with monkeypatch.context() as patch:
        patch.setattr(movies, "get_movie_by_id", terminate_before_read)
        failed_response = await asyncio.wait_for(client.get(endpoint), timeout=10)

    assert failed_response.status_code == 503
    assert failed_response.json() == {"detail": "База данных временно недоступна"}
    assert len(interrupted_pids) == 1
    assert isolated_movie_database.terminated_pids == interrupted_pids

    recovered_response = await client.get(endpoint)

    assert recovered_response.status_code == 200
    assert recovered_response.json() == expected_card
    async with isolated_movie_database.sessions() as session:
        recovered_pid = await session.scalar(text("SELECT pg_backend_pid()"))
    assert recovered_pid not in interrupted_pids
    async with database.sessions() as session:
        movie = await session.get(Movie, isolated_movie_database.movie_id)
        assert movie is not None
        assert movie.title == expected_card["title"]
    assert catalog_tmdb.upstream_requests == []


async def test_local_movie_read_replaces_dead_idle_connection(
    client, isolated_movie_database, catalog_tmdb
):
    endpoint = isolated_movie_database.endpoint
    pid_query = text("SELECT pg_backend_pid()")

    expected_status = 200
    expected_terminated_count = 1

    initial_response = await client.get(endpoint)
    assert initial_response.status_code == expected_status
    expected_card = initial_response.json()

    async with isolated_movie_database.sessions() as session:
        before_pid = await session.scalar(pid_query)

    await isolated_movie_database.terminate_connection(before_pid)
    response = await client.get(endpoint)
    assert response.status_code == expected_status
    assert response.json() == expected_card

    async with isolated_movie_database.sessions() as session:
        after_pid = await session.scalar(pid_query)

    assert after_pid != before_pid
    assert len(isolated_movie_database.terminated_pids) == expected_terminated_count
    assert isolated_movie_database.terminated_pids == [before_pid]
    assert catalog_tmdb.upstream_requests == []
