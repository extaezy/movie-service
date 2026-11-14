import logging
import os
from contextlib import asynccontextmanager
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.tmdb import open_tmdb_client
from app.schemas.movies import MovieResponse

pytestmark = pytest.mark.asyncio


@pytest.fixture
def movie_api(monkeypatch, tmdb_settings, tmdb_details_payload):
    database_url = os.getenv(
        "MOVIE_SERVICE_TEST_DATABASE_URL",
        "postgresql+asyncpg://offline:offline@127.0.0.1:1/offline_tests",
    )
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DATABASE_SSL", "disable")

    from app.api import movies

    app = FastAPI()
    app.include_router(movies.router)
    session = MagicMock(spec=AsyncSession)
    database_calls = []
    upstream_requests = []

    @asynccontextmanager
    async def transaction():
        yield session

    session.begin.side_effect = transaction

    async def offline_database():
        database_calls.append(True)
        yield session

    app.dependency_overrides[movies.get_db] = offline_database
    movie = MovieResponse(
        id=7,
        tmdb_id=603,
        title=tmdb_details_payload["title"],
        original_title=tmdb_details_payload["original_title"],
        overview=tmdb_details_payload["overview"],
        release_date=tmdb_details_payload["release_date"],
        poster_path=tmdb_details_payload["poster_path"],
        runtime=136,
        original_language="en",
        genres=[{"id": 2, "tmdb_id": 28, "name": "Боевик"}],
    )
    get_by_id = AsyncMock(return_value=movie)
    get_by_tmdb_id = AsyncMock(return_value=None)
    save = AsyncMock(return_value=movie)
    monkeypatch.setattr(movies, "get_movie_by_id", get_by_id)
    monkeypatch.setattr(movies, "get_movie_by_tmdb_id", get_by_tmdb_id)
    monkeypatch.setattr(movies, "save_movie", save)

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
        pytest.fail("This route must not call TMDB")

    use_upstream(unexpected_request)
    return SimpleNamespace(
        app=app,
        session=session,
        movie=movie,
        get_by_id=get_by_id,
        get_by_tmdb_id=get_by_tmdb_id,
        save=save,
        database_calls=database_calls,
        upstream_requests=upstream_requests,
        use_upstream=use_upstream,
    )


@pytest_asyncio.fixture
async def movies_client(movie_api):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=movie_api.app), base_url="http://test"
    ) as client:
        yield client


async def test_search_is_public_and_uses_external_ids_without_database(
    movies_client, movie_api, tmdb_search_payload
):
    movie_api.use_upstream(
        lambda request: httpx.Response(200, json=tmdb_search_payload)
    )
    response = await movies_client.get(
        "/movies/search", params={"q": "  Матрица  ", "page": 2}
    )

    assert response.status_code == 200
    assert response.json() == {
        "page": 2,
        "total_pages": 3,
        "total_results": 41,
        "results": [
            {
                "tmdb_id": 603,
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
    assert movie_api.database_calls == []
    assert len(movie_api.upstream_requests) == 1
    assert movie_api.upstream_requests[0].url.params["query"] == "Матрица"
    assert "local-tmdb-test-token" not in response.text
    movie_api.save.assert_not_awaited()


async def test_search_returns_empty_results(movies_client, movie_api):
    payload = {"page": 1, "total_pages": 0, "total_results": 0, "results": []}
    movie_api.use_upstream(lambda request: httpx.Response(200, json=payload))
    response = await movies_client.get("/movies/search", params={"q": "Нет фильма"})
    assert response.status_code == 200
    assert response.json() == payload
    assert movie_api.database_calls == []


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BR-MOV-001: query length is validated before whitespace is trimmed",
)
async def test_search_validates_length_after_trimming(movies_client, movie_api):
    payload = {"page": 1, "total_pages": 0, "total_results": 0, "results": []}
    movie_api.use_upstream(lambda request: httpx.Response(200, json=payload))
    response = await movies_client.get(
        "/movies/search", params={"q": " " + "a" * 200 + " "}
    )
    assert response.status_code == 200
    assert response.json() == payload
    assert movie_api.upstream_requests[0].url.params["query"] == "a" * 200
    assert movie_api.database_calls == []


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": ""},
        {"q": "   "},
        {"q": "a" * 201},
        {"q": "Матрица", "page": 0},
        {"q": "Матрица", "page": 501},
        {"q": "Матрица", "page": "invalid"},
    ],
)
async def test_search_rejects_invalid_parameters_without_external_calls(
    movies_client, movie_api, params
):
    response = await movies_client.get("/movies/search", params=params)
    assert response.status_code == 422
    assert movie_api.upstream_requests == []
    assert movie_api.database_calls == []


@pytest.mark.parametrize(
    "path",
    [
        "/movies/0",
        "/movies/-1",
        "/movies/2147483648",
        "/movies/invalid",
        "/movies/tmdb/0",
        "/movies/tmdb/2147483648",
    ],
)
async def test_invalid_movie_ids_do_not_reach_repositories(
    movies_client, movie_api, path
):
    response = await movies_client.get(path)
    assert response.status_code == 422
    movie_api.get_by_id.assert_not_awaited()
    movie_api.get_by_tmdb_id.assert_not_awaited()
    movie_api.save.assert_not_awaited()
    assert movie_api.upstream_requests == []


async def test_local_movie_is_public_and_does_not_use_tmdb(movies_client, movie_api):
    response = await movies_client.get("/movies/7")
    assert response.status_code == 200
    assert response.json() == movie_api.movie.model_dump(mode="json")
    movie_api.get_by_id.assert_awaited_once_with(movie_api.session, 7)
    movie_api.get_by_tmdb_id.assert_not_awaited()
    movie_api.save.assert_not_awaited()
    assert movie_api.upstream_requests == []


async def test_unknown_local_movie_is_not_found_without_import(
    movies_client, movie_api
):
    movie_api.get_by_id.return_value = None
    response = await movies_client.get("/movies/99")
    assert response.status_code == 404
    movie_api.get_by_id.assert_awaited_once_with(movie_api.session, 99)
    movie_api.save.assert_not_awaited()
    assert movie_api.upstream_requests == []


async def test_cached_movie_is_available_without_tmdb_configuration(
    movies_client, movie_api, tmdb_settings
):
    tmdb_settings.tmdb_access_token = SecretStr("")
    movie_api.get_by_tmdb_id.return_value = movie_api.movie
    response = await movies_client.get("/movies/tmdb/603")
    assert response.status_code == 200
    assert response.json() == movie_api.movie.model_dump(mode="json")
    movie_api.get_by_tmdb_id.assert_awaited_once_with(movie_api.session, 603)
    movie_api.save.assert_not_awaited()
    assert movie_api.upstream_requests == []


async def test_missing_movie_is_fetched_and_passed_to_repository(
    movies_client, movie_api, tmdb_details_payload
):
    movie_api.use_upstream(
        lambda request: httpx.Response(200, json=tmdb_details_payload)
    )
    response = await movies_client.get("/movies/tmdb/603")

    assert response.status_code == 200
    assert response.json() == movie_api.movie.model_dump(mode="json")
    movie_api.get_by_tmdb_id.assert_awaited_once_with(movie_api.session, 603)
    movie_api.save.assert_awaited_once()
    session, details = movie_api.save.await_args.args
    assert session is movie_api.session
    assert details.tmdb_id == 603
    assert details.title == "Матрица"
    assert details.genres[0].tmdb_id == 28
    assert len(movie_api.upstream_requests) == 1
    assert movie_api.upstream_requests[0].url.path == "/3/movie/603"


@pytest.mark.parametrize(
    ("upstream_status", "expected_status"), [(404, 404), (429, 502), (500, 502)]
)
async def test_failed_movie_import_does_not_save_data(
    movies_client, movie_api, upstream_status, expected_status
):
    movie_api.use_upstream(lambda request: httpx.Response(upstream_status))
    response = await movies_client.get("/movies/tmdb/603")
    assert response.status_code == expected_status
    movie_api.save.assert_not_awaited()


async def test_adult_movie_is_not_saved(movies_client, movie_api, tmdb_details_payload):
    tmdb_details_payload["adult"] = True
    movie_api.use_upstream(
        lambda request: httpx.Response(200, json=tmdb_details_payload)
    )
    response = await movies_client.get("/movies/tmdb/603")
    assert response.status_code == 404
    movie_api.save.assert_not_awaited()


@pytest.mark.parametrize("path", ["/movies/search?q=Матрица", "/movies/tmdb/603"])
async def test_unconfigured_tmdb_returns_503_without_saving(
    movies_client, movie_api, tmdb_settings, path
):
    tmdb_settings.tmdb_access_token = SecretStr("")
    response = await movies_client.get(path)
    assert response.status_code == 503
    assert movie_api.upstream_requests == []
    movie_api.save.assert_not_awaited()


@pytest.mark.parametrize("path", ["/movies/search?q=Матрица", "/movies/tmdb/603"])
async def test_tmdb_timeout_reaches_http_client_as_safe_502(
    movies_client, movie_api, path
):
    def timeout(request):
        raise httpx.ReadTimeout("local-tmdb-test-token", request=request)

    movie_api.use_upstream(timeout)
    response = await movies_client.get(path)
    assert response.status_code == 502
    assert "local-tmdb-test-token" not in response.text
    movie_api.save.assert_not_awaited()


async def test_import_passes_normalized_fields_to_repository(
    movies_client, movie_api, tmdb_details_payload
):
    endpoint = "/movies/tmdb/603"
    expected_status = 200
    expected_tmdb_id = 603
    expected_upstream_requests = 1

    tmdb_details_payload["release_date"] = ""
    tmdb_details_payload["runtime"] = 0

    movie_api.use_upstream(
        lambda request: httpx.Response(200, json=tmdb_details_payload)
    )
    response = await movies_client.get(endpoint)
    assert response.status_code == expected_status
    movie_api.save.assert_awaited_once()
    session, details = movie_api.save.await_args.args

    assert session is movie_api.session
    assert details.tmdb_id == expected_tmdb_id
    assert len(movie_api.upstream_requests) == expected_upstream_requests
    assert details.release_date is None
    assert details.runtime is None


async def test_movie_import_recovers_after_timeout(
    movies_client, movie_api, tmdb_details_payload
):
    endpoint = "/movies/tmdb/603"
    expected_first_status = 502
    expected_second_status = 200
    expected_upstream_requests = 2
    attempts = []

    def respond(request):
        attempts.append(request)

        if len(attempts) == 1:
            raise httpx.ReadTimeout("Simulated timeout", request=request)

        return httpx.Response(200, json=tmdb_details_payload)

    movie_api.use_upstream(respond)
    first_response = await movies_client.get(endpoint)
    assert first_response.status_code == expected_first_status
    movie_api.save.assert_not_awaited()

    second_response = await movies_client.get(endpoint)
    assert second_response.status_code == expected_second_status
    movie_api.save.assert_awaited_once()
    assert len(movie_api.upstream_requests) == expected_upstream_requests
    assert second_response.json() == movie_api.movie.model_dump(mode="json")


async def test_tmdb_error_does_not_expose_token(
    movies_client, movie_api, tmdb_settings, caplog
):
    endpoint = "/movies/search?q=Матрица"
    token = tmdb_settings.tmdb_access_token.get_secret_value()

    movie_api.use_upstream(
        lambda request: httpx.Response(500, json={"message": token})
    )

    with caplog.at_level(logging.WARNING, logger="app.integrations.tmdb"):
        response = await movies_client.get(endpoint)

    assert response.status_code == 502
    movie_api.save.assert_not_awaited()

    assert token not in response.text
    assert token not in caplog.text
    assert any(
        record.name == "app.integrations.tmdb"
        and record.levelno == logging.WARNING
        for record in caplog.records
    )
