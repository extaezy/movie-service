import logging
import os
from contextlib import asynccontextmanager
from copy import deepcopy
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.tmdb import open_tmdb_client
from app.schemas.movies import MovieDetailResponse, MoviePage

pytestmark = pytest.mark.asyncio


@pytest.fixture
def movie_api(monkeypatch, tmdb_settings, tmdb_details_payload):
    database_url = os.getenv(
        "MOVIE_SERVICE_TEST_DATABASE_URL",
        "postgresql+asyncpg://offline:offline@127.0.0.1:1/offline_tests",
    )
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DATABASE_SSL", "disable")
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "local-movie-api-tests-secret-key-at-least-32-characters"
    )

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
    movie = MovieDetailResponse(
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
        average_rating=None,
        ratings_count=0,
        tmdb_vote_average=None,
        tmdb_vote_count=None,
        tmdb_rating_updated_at=None,
    )
    get_by_id = AsyncMock(return_value=movie)
    get_by_tmdb_id = AsyncMock(return_value=None)
    save = AsyncMock(return_value=movie)
    list_movies = AsyncMock(
        return_value=MoviePage(
            page=1, page_size=20, total_results=0, total_pages=0, results=[]
        )
    )
    monkeypatch.setattr(movies, "get_movie_by_id", get_by_id)
    monkeypatch.setattr(movies, "get_movie_by_tmdb_id", get_by_tmdb_id)
    monkeypatch.setattr(movies, "save_movie", save)
    monkeypatch.setattr(movies, "list_movies", list_movies)

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
        list_movies=list_movies,
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


@pytest.fixture
def movie_database_api(movie_api, monkeypatch):
    from app.api import movies
    from app.db import database

    del movie_api.app.dependency_overrides[movies.get_db]
    movie_api.session.__aenter__.return_value = movie_api.session
    movie_api.session.__aexit__.return_value = False
    session_factory = MagicMock(return_value=movie_api.session)
    monkeypatch.setattr(database, "async_session", session_factory)
    movie_api.session_factory = session_factory
    return movie_api


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


@pytest.mark.parametrize(("query", "page"), [("a", 1), ("a" * 200, 500)])
async def test_search_accepts_parameter_boundaries(
    movies_client, movie_api, query, page
):
    payload = {"page": page, "total_pages": 500, "total_results": 0, "results": []}
    movie_api.use_upstream(lambda request: httpx.Response(200, json=payload))

    response = await movies_client.get("/movies/search", params={"q": query, "page": page})

    assert response.status_code == 200
    assert response.json() == payload
    assert movie_api.upstream_requests[0].url.params["query"] == query
    assert movie_api.upstream_requests[0].url.params["page"] == str(page)
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


async def test_unknown_local_movie_is_not_found_without_import(
    movies_client, movie_api
):
    movie_api.get_by_id.return_value = None
    response = await movies_client.get("/movies/99")
    assert response.status_code == 404
    movie_api.get_by_id.assert_awaited_once_with(movie_api.session, 99)
    movie_api.save.assert_not_awaited()
    assert movie_api.upstream_requests == []


async def test_failed_movie_import_does_not_save_data(
    movies_client, movie_api
):
    movie_api.use_upstream(lambda request: httpx.Response(500))
    response = await movies_client.get("/movies/tmdb/603")
    assert response.status_code == 502
    movie_api.save.assert_not_awaited()


@pytest.mark.parametrize(
    "path", ["/movies/search?q=Матрица", "/movies/tmdb/603", "/movies/discover"]
)
async def test_unconfigured_tmdb_returns_503_without_saving(
    movies_client, movie_api, tmdb_settings, path
):
    tmdb_settings.tmdb_access_token = SecretStr("")
    response = await movies_client.get(path)
    assert response.status_code == 503
    assert movie_api.upstream_requests == []
    movie_api.save.assert_not_awaited()


@pytest.mark.parametrize(
    "path", ["/movies/search?q=Матрица", "/movies/tmdb/603", "/movies/discover"]
)
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


@pytest.mark.parametrize(
    "endpoint, repository_name",
    [
        ("/movies/7", "get_by_id"),
        ("/movies/tmdb/603", "get_by_tmdb_id"),
        ("/movies", "list_movies"),
    ],
)
async def test_database_read_errors_return_safe_503(
    movies_client, movie_database_api, endpoint, repository_name
):
    read_movie = getattr(movie_database_api, repository_name)
    read_movie.side_effect = SQLAlchemyTimeoutError("fake-password-marker")

    response = await movies_client.get(endpoint)

    assert response.status_code == 503
    assert response.json() == {"detail": "База данных временно недоступна"}
    assert "fake-password-marker" not in response.text
    movie_database_api.save.assert_not_awaited()
    assert movie_database_api.upstream_requests == []


@pytest.mark.parametrize(
    "params, expected_arguments",
    [
        pytest.param(
            {},
            {"page": 1, "genre_id": None, "year": None, "sort": "release_date_desc"},
            id="defaults",
        ),
        pytest.param(
            {"page": 3, "genre_id": 31, "year": 1999, "sort": "release_date_asc"},
            {"page": 3, "genre_id": 31, "year": 1999, "sort": "release_date_asc"},
            id="combined-filters",
        ),
        pytest.param(
            {"page": 1, "genre_id": 1, "year": 1, "sort": "release_date_asc"},
            {"page": 1, "genre_id": 1, "year": 1, "sort": "release_date_asc"},
            id="lower-bounds",
        ),
        pytest.param(
            {"page": 2147483647, "genre_id": 2147483647, "year": 9999},
            {
                "page": 2147483647,
                "genre_id": 2147483647,
                "year": 9999,
                "sort": "release_date_desc",
            },
            id="upper-bounds",
        ),
    ],
)
async def test_catalog_is_public_and_passes_valid_parameters(
    movies_client, movie_api, params, expected_arguments
):
    expected_json = {
        "page": expected_arguments["page"],
        "page_size": 20,
        "total_results": 0,
        "total_pages": 0,
        "results": [],
    }
    movie_api.list_movies.return_value = MoviePage(**expected_json)

    response = await movies_client.get("/movies", params=params)

    assert response.status_code == 200
    assert response.json() == expected_json
    movie_api.list_movies.assert_awaited_once_with(
        movie_api.session, **expected_arguments
    )
    movie_api.get_by_id.assert_not_awaited()
    movie_api.get_by_tmdb_id.assert_not_awaited()
    movie_api.save.assert_not_awaited()
    assert movie_api.upstream_requests == []


@pytest.mark.parametrize(
    "field, value",
    [
        pytest.param("page", 0, id="page-below-minimum"),
        pytest.param("page", 2147483648, id="page-above-maximum"),
        pytest.param("page", "invalid", id="page-text"),
        pytest.param("page", "1.5", id="page-fraction"),
        pytest.param("genre_id", 0, id="genre-below-minimum"),
        pytest.param("genre_id", 2147483648, id="genre-above-maximum"),
        pytest.param("genre_id", "invalid", id="genre-text"),
        pytest.param("year", 0, id="year-below-minimum"),
        pytest.param("year", 10000, id="year-above-maximum"),
        pytest.param("year", "invalid", id="year-text"),
        pytest.param("sort", "rating_desc", id="unsupported-rating-sort"),
        pytest.param("sort", "release_date", id="incomplete-sort"),
        pytest.param("sort", "", id="empty-sort"),
    ],
)
async def test_catalog_rejects_invalid_parameters_before_repository_calls(
    movies_client, movie_api, field, value
):
    response = await movies_client.get("/movies", params={field: value})

    assert response.status_code == 422
    assert any(
        error["loc"] == ["query", field] for error in response.json()["detail"]
    )
    movie_api.list_movies.assert_not_awaited()
    movie_api.get_by_id.assert_not_awaited()
    movie_api.get_by_tmdb_id.assert_not_awaited()
    movie_api.save.assert_not_awaited()
    assert movie_api.upstream_requests == []


@pytest.mark.parametrize(
    "params, expected_filters",
    [
        pytest.param({}, {"sort_by": "popularity.desc"}, id="defaults"),
        pytest.param(
            {"tmdb_genre_id": 28},
            {"sort_by": "popularity.desc", "with_genres": "28"},
            id="genre-only",
        ),
        pytest.param(
            {"year": 1999},
            {"sort_by": "popularity.desc", "primary_release_year": "1999"},
            id="year-only",
        ),
        pytest.param(
            {"page": 2, "tmdb_genre_id": 878, "year": 1999, "sort": "release_date_asc"},
            {
                "sort_by": "primary_release_date.asc",
                "with_genres": "878",
                "primary_release_year": "1999",
            },
            id="combined-ascending",
        ),
        pytest.param(
            {"page": 2, "tmdb_genre_id": 28, "year": 1999, "sort": "release_date_desc"},
            {
                "sort_by": "primary_release_date.desc",
                "with_genres": "28",
                "primary_release_year": "1999",
            },
            id="combined-descending",
        ),
        pytest.param(
            {"page": 1, "tmdb_genre_id": 1, "year": 1},
            {
                "sort_by": "popularity.desc",
                "with_genres": "1",
                "primary_release_year": "1",
            },
            id="lower-bounds",
        ),
        pytest.param(
            {"page": 500, "tmdb_genre_id": 2147483647, "year": 9999},
            {
                "sort_by": "popularity.desc",
                "with_genres": "2147483647",
                "primary_release_year": "9999",
            },
            id="upper-bounds",
        ),
    ],
)
async def test_discover_is_public_and_translates_request_parameters(
    movies_client,
    movie_api,
    tmdb_settings,
    tmdb_search_payload,
    tmdb_search_expected_json,
    params,
    expected_filters,
):
    page = params.get("page", 1)
    tmdb_search_payload.update(page=page, total_pages=500, total_results=10000)
    expected_json = deepcopy(tmdb_search_expected_json)
    expected_json.update(page=page, total_pages=500, total_results=10000)
    movie_api.use_upstream(
        lambda request: httpx.Response(200, json=tmdb_search_payload)
    )

    response = await movies_client.get("/movies/discover", params=params)

    assert response.status_code == 200
    assert response.json() == expected_json
    assert len(movie_api.upstream_requests) == 1
    request = movie_api.upstream_requests[0]
    assert request.method == "GET"
    assert (
        str(request.url.copy_with(query=None)) == "https://tmdb.example/3/discover/movie"
    )
    assert dict(request.url.params) == {
        **expected_filters,
        "page": str(page),
        "language": "ru-RU",
        "include_adult": "false",
    }
    token = tmdb_settings.tmdb_access_token.get_secret_value()
    assert request.headers["Authorization"] == f"Bearer {token}"
    assert request.headers["Accept"] == "application/json"
    assert request.extensions["timeout"] == {
        "connect": 2,
        "read": 2,
        "write": 2,
        "pool": 2,
    }
    assert token not in response.text
    assert movie_api.database_calls == []
    movie_api.get_by_id.assert_not_awaited()
    movie_api.get_by_tmdb_id.assert_not_awaited()
    movie_api.list_movies.assert_not_awaited()
    movie_api.save.assert_not_awaited()


@pytest.mark.parametrize(
    "field, value",
    [
        pytest.param("page", 0, id="page-below-minimum"),
        pytest.param("page", 501, id="page-above-maximum"),
        pytest.param("page", "invalid", id="page-text"),
        pytest.param("page", "1.5", id="page-fraction"),
        pytest.param("tmdb_genre_id", 0, id="genre-below-minimum"),
        pytest.param("tmdb_genre_id", 2147483648, id="genre-above-maximum"),
        pytest.param("tmdb_genre_id", "invalid", id="genre-text"),
        pytest.param("year", 0, id="year-below-minimum"),
        pytest.param("year", 10000, id="year-above-maximum"),
        pytest.param("year", "invalid", id="year-text"),
        pytest.param("sort", "rating_desc", id="unsupported-rating-sort"),
        pytest.param("sort", "popularity.asc", id="external-sort-name"),
        pytest.param("sort", "", id="empty-sort"),
    ],
)
async def test_discover_rejects_invalid_parameters_without_http_or_database(
    movies_client, movie_api, field, value
):
    response = await movies_client.get("/movies/discover", params={field: value})

    assert response.status_code == 422
    assert any(
        error["loc"] == ["query", field] for error in response.json()["detail"]
    )
    assert movie_api.upstream_requests == []
    assert movie_api.database_calls == []
    movie_api.get_by_id.assert_not_awaited()
    movie_api.get_by_tmdb_id.assert_not_awaited()
    movie_api.list_movies.assert_not_awaited()
    movie_api.save.assert_not_awaited()


async def test_discover_returns_empty_page_without_database(movies_client, movie_api):
    payload = {"page": 1, "total_pages": 0, "total_results": 0, "results": []}
    movie_api.use_upstream(lambda request: httpx.Response(200, json=payload))

    response = await movies_client.get("/movies/discover")

    assert response.status_code == 200
    assert response.json() == payload
    assert len(movie_api.upstream_requests) == 1
    assert movie_api.database_calls == []
    movie_api.get_by_id.assert_not_awaited()
    movie_api.get_by_tmdb_id.assert_not_awaited()
    movie_api.list_movies.assert_not_awaited()
    movie_api.save.assert_not_awaited()


@pytest.mark.parametrize(
    "upstream_total_pages, expected_total_pages",
    [(499, 499), (500, 500), (501, 500)],
)
async def test_discover_caps_total_pages_and_preserves_results(
    movies_client,
    movie_api,
    tmdb_search_payload,
    tmdb_search_expected_json,
    upstream_total_pages,
    expected_total_pages,
):
    tmdb_search_payload["total_pages"] = upstream_total_pages
    tmdb_search_payload["page"] = 1
    expected_json = deepcopy(tmdb_search_expected_json)
    expected_json.update(page=1, total_pages=expected_total_pages)
    movie_api.use_upstream(
        lambda request: httpx.Response(200, json=tmdb_search_payload)
    )

    response = await movies_client.get("/movies/discover")

    assert response.status_code == 200
    assert response.json() == expected_json
    assert len(movie_api.upstream_requests) == 1
    assert movie_api.database_calls == []
    movie_api.save.assert_not_awaited()


async def test_discover_upstream_not_found_returns_safe_502(
    movies_client, movie_api, tmdb_settings, caplog
):
    token = tmdb_settings.tmdb_access_token.get_secret_value()
    movie_api.use_upstream(
        lambda request: httpx.Response(
            404,
            json={"message": token},
            headers={"Location": "https://other.example/steal-token"},
        )
    )

    with caplog.at_level(logging.WARNING, logger="app.integrations.tmdb"):
        response = await movies_client.get("/movies/discover")

    assert response.status_code == 502
    assert response.json() == {"detail": "TMDB временно недоступен"}
    assert len(movie_api.upstream_requests) == 1
    assert movie_api.upstream_requests[0].url.host == "tmdb.example"
    assert token not in response.text
    assert token not in caplog.text
    assert any(
        record.name == "app.integrations.tmdb" and record.levelno == logging.WARNING
        for record in caplog.records
    )
    assert movie_api.database_calls == []
    movie_api.save.assert_not_awaited()


@pytest.mark.parametrize(
    "failure",
    [
        "invalid-json",
        "missing-title",
        "invalid-date",
    ],
)
async def test_discover_invalid_upstream_data_returns_safe_502(
    movies_client, movie_api, tmdb_search_payload, failure
):
    payload = deepcopy(tmdb_search_payload)
    if failure == "missing-title":
        del payload["results"][0]["title"]
    elif failure == "invalid-date":
        payload["results"][0]["release_date"] = "invalid-date"
    upstream_response = (
        httpx.Response(200, content=b"not-json")
        if failure == "invalid-json"
        else httpx.Response(200, json=payload)
    )
    movie_api.use_upstream(lambda request: upstream_response)

    response = await movies_client.get("/movies/discover")

    assert response.status_code == 502
    assert response.json() == {"detail": "TMDB вернул некорректные данные"}
    assert len(movie_api.upstream_requests) == 1
    assert movie_api.database_calls == []
    movie_api.save.assert_not_awaited()


async def test_discover_recovers_after_network_failure_without_database(
    movies_client, movie_api, tmdb_search_payload, tmdb_search_expected_json
):
    def respond(request):
        if len(movie_api.upstream_requests) == 1:
            raise httpx.ConnectError("Simulated connection failure", request=request)
        return httpx.Response(200, json=tmdb_search_payload)

    movie_api.use_upstream(respond)
    parameters = {"page": 2}

    first_response = await movies_client.get("/movies/discover", params=parameters)
    assert first_response.status_code == 502
    assert first_response.json() == {"detail": "Не удалось подключиться к TMDB"}
    second_response = await movies_client.get("/movies/discover", params=parameters)
    assert second_response.status_code == 200
    assert second_response.json() == tmdb_search_expected_json
    assert len(movie_api.upstream_requests) == 2
    assert movie_api.database_calls == []
    movie_api.get_by_id.assert_not_awaited()
    movie_api.get_by_tmdb_id.assert_not_awaited()
    movie_api.list_movies.assert_not_awaited()
    movie_api.save.assert_not_awaited()


async def test_discover_ignores_unknown_upstream_fields(
    movies_client,
    movie_api,
    tmdb_search_payload,
    tmdb_search_expected_json,
):
    endpoint = "/movies/discover"
    parameters = {"page": 2}

    extended_payload = deepcopy(tmdb_search_payload)

    extra_field_name = "provider_debug"
    extra_field_value = {"marker": "provider-only-test-marker"}

    expected_json = deepcopy(tmdb_search_expected_json)
    expected_status = 200
    expected_upstream_count = 1
    expected_database_calls = []

    extended_payload[extra_field_name] = deepcopy(extra_field_value)
    extended_payload["results"][0][extra_field_name] = deepcopy(extra_field_value)

    movie_api.use_upstream(
        lambda request: httpx.Response(200, json=extended_payload)
    )

    extended_response = await movies_client.get(endpoint, params=parameters)
    assert extended_response.status_code == expected_status
    assert extended_response.json() == expected_json
    assert extra_field_value["marker"] not in extended_response.text
    assert len(movie_api.upstream_requests) == expected_upstream_count
    assert movie_api.database_calls == expected_database_calls
    movie_api.get_by_id.assert_not_awaited()
    movie_api.get_by_tmdb_id.assert_not_awaited()
    movie_api.list_movies.assert_not_awaited()
    movie_api.save.assert_not_awaited()
