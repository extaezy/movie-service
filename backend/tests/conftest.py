import os
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.integrations.tmdb import TMDBSettings


@pytest.fixture
def tmdb_settings():
    return TMDBSettings(
        _env_file=None,
        tmdb_access_token=SecretStr("local-tmdb-test-token"),
        tmdb_base_url="https://tmdb.example/3/",
        tmdb_timeout_seconds=2,
        tmdb_language="ru-RU",
    )


@pytest.fixture
def tmdb_search_payload():
    return {
        "page": 2,
        "total_pages": 3,
        "total_results": 41,
        "results": [
            {
                "id": 603,
                "title": "Матрица",
                "original_title": "The Matrix",
                "overview": "Описание фильма",
                "release_date": "1999-03-31",
                "poster_path": "/matrix.jpg",
                "original_language": "en",
                "genre_ids": [28, 878],
            }
        ],
    }


@pytest.fixture
def tmdb_details_payload():
    return {
        "id": 603,
        "title": "Матрица",
        "original_title": "The Matrix",
        "overview": "Описание фильма",
        "release_date": "1999-03-31",
        "poster_path": "/matrix.jpg",
        "original_language": "en",
        "runtime": 136,
        "adult": False,
        "genres": [{"id": 28, "name": "Боевик"}],
    }


@pytest.fixture
def token_context(monkeypatch):
    secret = "local-jwt-test-secret-used-only-by-automated-tests-0123456789abcdef"
    database_url = os.getenv("MOVIE_SERVICE_TEST_DATABASE_URL") or (
        "postgresql+asyncpg://offline:offline@127.0.0.1:1/offline_tests"
    )
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DATABASE_SSL", "disable")
    monkeypatch.setenv("JWT_SECRET_KEY", secret)

    from app.core import tokens

    monkeypatch.setattr(tokens.settings, "jwt_secret_key", SecretStr(secret))
    user_id = uuid4()
    creation_started_at = int(datetime.now(UTC).timestamp())
    valid_token = tokens.create_access_token(str(user_id))
    creation_finished_at = int(datetime.now(UTC).timestamp())
    return SimpleNamespace(
        tokens=tokens,
        secret=secret,
        user_id=user_id,
        valid_token=valid_token,
        creation_started_at=creation_started_at,
        creation_finished_at=creation_finished_at,
        claims={
            "sub": str(user_id),
            "iat": creation_started_at,
            "exp": creation_started_at + 1800,
        },
    )


@pytest.fixture(scope="session")
def auth_password_hash():
    from app.core.security import hash_password

    return hash_password("testing-password-123")
