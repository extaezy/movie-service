import asyncio
import json
import os
import socket
import sys
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, Movie
from app.db.settings import DatabaseSettings, connection_options
from app.integrations.tmdb import open_tmdb_client

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.skipif(
        os.getenv("MOVIE_SERVICE_RUN_DATABASE_OUTAGE") != "1",
        reason="Set MOVIE_SERVICE_RUN_DATABASE_OUTAGE=1 to run disposable Docker outage tests",
    ),
    pytest.mark.asyncio(loop_scope="module"),
]


async def run_process(*arguments, environment=None, timeout=30, check=True):
    process = await asyncio.create_subprocess_exec(
        *arguments,
        cwd=BACKEND_DIRECTORY,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    result = SimpleNamespace(
        returncode=process.returncode,
        stdout=stdout.decode("utf-8", errors="replace").strip(),
        stderr=stderr.decode("utf-8", errors="replace").strip(),
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"{Path(arguments[0]).name} failed: {result.stderr}")
    return result


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def owned_postgres():
    owner_id = uuid4().hex
    password = uuid4().hex
    container_name = f"movie-service-outage-{owner_id}"
    with socket.socket() as port_reservation:
        port_reservation.bind(("127.0.0.1", 0))
        host_port = port_reservation.getsockname()[1]
        created = await run_process(
            "docker",
            "create",
            "--pull=never",
            "--name",
            container_name,
            "--label",
            f"movie-service.qa.owner={owner_id}",
            "--publish",
            f"127.0.0.1:{host_port}:5432",
            "--env",
            "POSTGRES_DB=movie_service_outage_test",
            "--env",
            "POSTGRES_USER=qa_outage",
            "--env",
            "POSTGRES_PASSWORD",
            "postgres:17",
            environment={**os.environ, "POSTGRES_PASSWORD": password},
        )
    container_id = created.stdout
    database_url = URL.create(
        "postgresql+asyncpg",
        username="qa_outage",
        password=password,
        host="127.0.0.1",
        port=host_port,
        database="movie_service_outage_test",
    )

    async def check_owner():
        inspected = await run_process(
            "docker", "inspect", "--format", "{{json .Config.Labels}}", container_id
        )
        if json.loads(inspected.stdout).get("movie-service.qa.owner") != owner_id:
            raise RuntimeError("Refusing to modify a container not owned by this test")

    async def wait_ready():
        deadline = asyncio.get_running_loop().time() + 45
        while asyncio.get_running_loop().time() < deadline:
            result = await run_process(
                "docker",
                "exec",
                container_id,
                "pg_isready",
                "-h",
                "127.0.0.1",
                "-U",
                "qa_outage",
                "-d",
                "movie_service_outage_test",
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                return
            await asyncio.sleep(0.25)
        raise TimeoutError("Disposable PostgreSQL did not become ready")

    @asynccontextmanager
    async def unavailable():
        await check_owner()
        try:
            await run_process("docker", "stop", "--timeout", "5", container_id)
            state = await run_process(
                "docker", "inspect", "--format", "{{.State.Running}}", container_id
            )
            assert state.stdout == "false"
            yield
        finally:
            await check_owner()
            await run_process("docker", "start", container_id)
            await wait_ready()

    try:
        await check_owner()
        await run_process("docker", "start", container_id)
        await wait_ready()
        await run_process(
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "head",
            environment={
                **os.environ,
                "DATABASE_URL": database_url.render_as_string(hide_password=False),
                "DATABASE_SSL": "disable",
            },
        )
        yield SimpleNamespace(database_url=database_url, unavailable=unavailable)
    finally:
        await check_owner()
        await run_process("docker", "rm", "--force", "--volumes", container_id)


@pytest_asyncio.fixture(loop_scope="module")
async def outage_service(
    owned_postgres, monkeypatch, tmdb_settings, tmdb_search_payload
):
    config = DatabaseSettings(
        _env_file=None,
        database_url=SecretStr(
            owned_postgres.database_url.render_as_string(hide_password=False)
        ),
        database_ssl="disable",
    )
    url, connect_args = connection_options(config)
    engine = create_async_engine(
        url,
        connect_args={**connect_args, "timeout": 2, "command_timeout": 5},
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
        pool_timeout=2,
        hide_parameters=True,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    upstream_requests = []

    def upstream(request):
        upstream_requests.append(request)
        assert request.url.path == "/3/search/movie"
        return httpx.Response(200, json=tmdb_search_payload)

    try:
        names = ", ".join(
            f'movie_service."{table.name}"' for table in Base.metadata.sorted_tables
        )
        async with engine.begin() as connection:
            await connection.execute(
                text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE")
            )
        with monkeypatch.context() as patch:
            patch.setenv(
                "DATABASE_URL",
                owned_postgres.database_url.render_as_string(hide_password=False),
            )
            patch.setenv("DATABASE_SSL", "disable")
            patch.setenv(
                "JWT_SECRET_KEY", "local-outage-tests-secret-key-at-least-32-characters"
            )

            from app.api import movies
            from app.core import tokens
            from app.db import database
            from app.main import app

            patch.setattr(database, "async_session", sessions)
            patch.setattr(
                tokens.settings,
                "jwt_secret_key",
                SecretStr("local-outage-tests-secret-key-at-least-32-characters"),
            )
            patch.setattr(
                movies,
                "open_tmdb_client",
                partial(
                    open_tmdb_client,
                    config=tmdb_settings,
                    transport=httpx.MockTransport(upstream),
                ),
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                registration = {
                    "username": "outage_user",
                    "email": "outage@example.com",
                    "password": "testing-password-123",
                    "password_confirm": "testing-password-123",
                }
                registered = await client.post("/auth/register", json=registration)
                assert registered.status_code == 201
                credentials = {
                    "identifier": registration["username"],
                    "password": registration["password"],
                }
                login = await client.post("/auth/login", json=credentials)
                assert login.status_code == 200
                headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
                me = await client.get("/auth/me", headers=headers)
                assert me.status_code == 200
                root = await client.get("/")
                assert root.status_code == 200
                async with sessions() as session, session.begin():
                    movie = Movie(tmdb_id=603, title="Фильм для проверки отказа БД")
                    session.add(movie)
                yield SimpleNamespace(
                    client=client,
                    unavailable=owned_postgres.unavailable,
                    headers=headers,
                    credentials=credentials,
                    me_json=me.json(),
                    root_json=root.json(),
                    movie_endpoint=f"/movies/{movie.id}",
                    tmdb_endpoint="/movies/tmdb/603",
                    upstream_requests=upstream_requests,
                )
    finally:
        await engine.dispose()


async def test_auth_returns_503_during_database_outage_and_recovers(outage_service):
    client = outage_service.client
    new_registration = {
        "username": "outage_new",
        "email": "outage.new@example.com",
        "password": "testing-password-123",
        "password_confirm": "testing-password-123",
    }
    async with outage_service.unavailable():
        responses = [
            await client.post("/auth/register", json=new_registration),
            await client.post("/auth/login", json=outage_service.credentials),
            await client.get("/auth/me", headers=outage_service.headers),
        ]
        for response in responses:
            assert response.status_code == 503
            assert response.json() == {"detail": "База данных временно недоступна"}
        root = await client.get("/")
        assert root.status_code == 200
        assert root.json() == outage_service.root_json
        search = await client.get("/movies/search", params={"q": "Матрица", "page": 2})
        assert search.status_code == 200
        assert search.json()["results"][0]["tmdb_id"] == 603

    login = await client.post("/auth/login", json=outage_service.credentials)
    assert login.status_code == 200
    recovered_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await client.get("/auth/me", headers=recovered_headers)
    assert me.status_code == 200
    assert me.json() == outage_service.me_json
    registered = await client.post("/auth/register", json=new_registration)
    assert registered.status_code == 201
    assert registered.json() == {
        "username": new_registration["username"],
        "email": new_registration["email"],
    }
    assert len(outage_service.upstream_requests) == 1


async def test_movie_reads_recover_after_database_outage(outage_service):
    client = outage_service.client
    local_endpoint = outage_service.movie_endpoint
    tmdb_endpoint = outage_service.tmdb_endpoint

    expected_success_status = 200
    expected_error_status = 503
    expected_error_json = {"detail": "База данных временно недоступна"}
    expected_upstream_requests = 0

    local_response = await client.get(local_endpoint)
    assert local_response.status_code == expected_success_status
    card = local_response.json()

    async with outage_service.unavailable():
        local_response = await client.get(local_endpoint)
        assert local_response.status_code == expected_error_status
        assert local_response.json() == expected_error_json

        tmdb_response = await client.get(tmdb_endpoint)
        assert tmdb_response.status_code == expected_error_status
        assert tmdb_response.json() == expected_error_json

    local_response = await client.get(local_endpoint)
    tmdb_response = await client.get(tmdb_endpoint)
    assert local_response.status_code == expected_success_status
    assert tmdb_response.status_code == expected_success_status
    assert local_response.json() == card
    assert tmdb_response.json() == card
    assert len(outage_service.upstream_requests) == expected_upstream_requests
