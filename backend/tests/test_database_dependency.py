from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        OperationalError("SELECT movie", {}, OSError("private-database-marker")),
        SQLAlchemyTimeoutError("private-database-marker"),
        ConnectionRefusedError("private-database-marker"),
        TimeoutError("private-database-marker"),
    ],
    ids=["driver", "pool-timeout", "connection-refused", "timeout"],
)
async def test_database_dependency_returns_safe_503_and_rolls_back(
    monkeypatch, token_context, failure
):
    from app.db import database

    session = MagicMock(spec=AsyncSession)
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False
    monkeypatch.setattr(database, "async_session", MagicMock(return_value=session))
    dependency = database.get_db()

    assert await anext(dependency) is session
    with pytest.raises(HTTPException) as caught:
        await dependency.athrow(failure)

    assert caught.value.status_code == 503
    assert caught.value.detail == "База данных временно недоступна"
    assert "private-database-marker" not in caught.value.detail
    session.rollback.assert_awaited_once()
