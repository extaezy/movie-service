import logging

import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError

from app.integrations.tmdb import TMDBSettings, open_tmdb_client

pytestmark = pytest.mark.asyncio


async def test_search_sends_expected_request_and_normalizes_response(
    tmdb_settings, tmdb_search_payload
):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=tmdb_search_payload)

    async with open_tmdb_client(tmdb_settings, httpx.MockTransport(respond)) as client:
        result = await client.search_movies("  Матрица  ", page=2)

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert (
        str(request.url.copy_with(query=None)) == "https://tmdb.example/3/search/movie"
    )
    assert dict(request.url.params) == {
        "query": "Матрица",
        "page": "2",
        "language": "ru-RU",
        "include_adult": "false",
    }
    assert request.headers["Authorization"] == "Bearer local-tmdb-test-token"
    assert request.headers["Accept"] == "application/json"
    assert request.extensions["timeout"] == {
        "connect": 2,
        "read": 2,
        "write": 2,
        "pool": 2,
    }
    assert result.model_dump(mode="json") == {
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


async def test_search_accepts_empty_results(tmdb_settings):
    payload = {"page": 1, "total_pages": 0, "total_results": 0, "results": []}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    async with open_tmdb_client(tmdb_settings, transport) as client:
        result = await client.search_movies("Неизвестный фильм")
    assert result.model_dump() == payload


@pytest.mark.parametrize(
    ("query", "page"),
    [("", 1), ("   ", 1), ("a" * 201, 1), ("Матрица", 0), ("Матрица", 501)],
)
async def test_search_rejects_invalid_parameters_before_http(
    tmdb_settings, query, page
):
    def unexpected_request(request):
        pytest.fail("Invalid search parameters must not reach TMDB")

    async with open_tmdb_client(
        tmdb_settings, httpx.MockTransport(unexpected_request)
    ) as client:
        with pytest.raises(ValueError):
            await client.search_movies(query, page)


@pytest.mark.parametrize(("query", "page"), [("a", 1), ("a" * 200, 500)])
async def test_search_accepts_parameter_boundaries(tmdb_settings, query, page):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={"page": page, "total_pages": 500, "total_results": 0, "results": []},
        )

    async with open_tmdb_client(tmdb_settings, httpx.MockTransport(respond)) as client:
        result = await client.search_movies(query, page)
    assert result.page == page
    assert requests[0].url.params["query"] == query
    assert requests[0].url.params["page"] == str(page)


async def test_get_movie_sends_id_and_normalizes_missing_values(
    tmdb_settings, tmdb_details_payload
):
    tmdb_details_payload.update(release_date="", runtime=0)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=tmdb_details_payload)

    async with open_tmdb_client(tmdb_settings, httpx.MockTransport(respond)) as client:
        result = await client.get_movie(603)

    assert len(requests) == 1
    assert requests[0].url.path == "/3/movie/603"
    assert dict(requests[0].url.params) == {"language": "ru-RU"}
    assert result.tmdb_id == 603
    assert result.release_date is None
    assert result.runtime is None
    assert result.genres[0].model_dump() == {"tmdb_id": 28, "name": "Боевик"}


@pytest.mark.parametrize("adult", [False, True])
async def test_get_movie_handles_adult_content(
    tmdb_settings, tmdb_details_payload, adult
):
    tmdb_details_payload["adult"] = adult
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=tmdb_details_payload)
    )
    async with open_tmdb_client(tmdb_settings, transport) as client:
        if adult:
            with pytest.raises(HTTPException) as caught:
                await client.get_movie(603)
            assert caught.value.status_code == 404
        else:
            result = await client.get_movie(603)
            assert result.runtime == 136
            assert result.release_date.isoformat() == "1999-03-31"


async def test_get_movie_preserves_not_found_status(tmdb_settings):
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    async with open_tmdb_client(tmdb_settings, transport) as client:
        with pytest.raises(HTTPException) as caught:
            await client.get_movie(603)
    assert caught.value.status_code == 404


@pytest.mark.parametrize("operation", ["search", "details"])
@pytest.mark.parametrize("status_code", [302, 401, 403, 429, 500, 503])
async def test_upstream_http_errors_are_safe_bad_gateway_responses(
    tmdb_settings, caplog, operation, status_code
):
    requests = []
    token = tmdb_settings.tmdb_access_token.get_secret_value()

    def respond(request):
        requests.append(request)
        return httpx.Response(
            status_code,
            json={"error": token},
            headers={"Location": "https://other.example/steal-token"},
        )

    with caplog.at_level(logging.WARNING, logger="app.integrations.tmdb"):
        async with open_tmdb_client(
            tmdb_settings, httpx.MockTransport(respond)
        ) as client:
            with pytest.raises(HTTPException) as caught:
                if operation == "search":
                    await client.search_movies("Матрица")
                else:
                    await client.get_movie(603)

    assert caught.value.status_code == 502
    assert token not in str(caught.value.detail)
    assert token not in caplog.text
    assert len(requests) == 1


@pytest.mark.parametrize("operation", ["search", "details"])
@pytest.mark.parametrize("failure", [httpx.ReadTimeout, httpx.ConnectError])
async def test_network_failures_become_safe_bad_gateway_responses(
    tmdb_settings, caplog, operation, failure
):
    token = tmdb_settings.tmdb_access_token.get_secret_value()

    def fail_request(request):
        raise failure(token, request=request)

    with caplog.at_level(logging.WARNING, logger="app.integrations.tmdb"):
        async with open_tmdb_client(
            tmdb_settings, httpx.MockTransport(fail_request)
        ) as client:
            with pytest.raises(HTTPException) as caught:
                if operation == "search":
                    await client.search_movies("Матрица")
                else:
                    await client.get_movie(603)
    assert caught.value.status_code == 502
    assert token not in str(caught.value.detail)
    assert token not in caplog.text


@pytest.mark.parametrize("operation", ["search", "details"])
async def test_invalid_json_becomes_bad_gateway(tmdb_settings, operation):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"not-json")
    )
    async with open_tmdb_client(tmdb_settings, transport) as client:
        with pytest.raises(HTTPException) as caught:
            if operation == "search":
                await client.search_movies("Матрица")
            else:
                await client.get_movie(603)
    assert caught.value.status_code == 502


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", 604),
        ("title", " "),
        ("release_date", "invalid-date"),
        ("runtime", -1),
        ("genres", None),
    ],
)
async def test_invalid_movie_details_become_bad_gateway(
    tmdb_settings, tmdb_details_payload, field, value
):
    tmdb_details_payload[field] = value
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=tmdb_details_payload)
    )
    async with open_tmdb_client(tmdb_settings, transport) as client:
        with pytest.raises(HTTPException) as caught:
            await client.get_movie(603)
    assert caught.value.status_code == 502


@pytest.mark.parametrize(
    ("field", "value"),
    [("page", 0), ("results", None), ("total_pages", -1), ("total_results", -1)],
)
async def test_invalid_search_response_becomes_bad_gateway(
    tmdb_settings, tmdb_search_payload, field, value
):
    tmdb_search_payload[field] = value
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=tmdb_search_payload)
    )
    async with open_tmdb_client(tmdb_settings, transport) as client:
        with pytest.raises(HTTPException) as caught:
            await client.search_movies("Матрица")
    assert caught.value.status_code == 502


@pytest.mark.parametrize("token", ["", "   "])
async def test_missing_token_is_configuration_error_without_http(tmdb_settings, token):
    tmdb_settings.tmdb_access_token = SecretStr(token)

    def unexpected_request(request):
        pytest.fail("Unconfigured TMDB must not send requests")

    with pytest.raises(HTTPException) as caught:
        async with open_tmdb_client(
            tmdb_settings, httpx.MockTransport(unexpected_request)
        ):
            pytest.fail("Unconfigured TMDB must not yield a client")
    assert caught.value.status_code == 503


@pytest.mark.parametrize(
    "base_url",
    [
        "http://tmdb.example/3/",
        "https://user:password@tmdb.example/3/",
        "https://tmdb.example/3/?api_key=secret",
        "https://tmdb.example/3/#fragment",
    ],
)
async def test_unsafe_base_url_is_rejected(base_url):
    with pytest.raises(ValidationError):
        TMDBSettings(_env_file=None, tmdb_base_url=base_url)
