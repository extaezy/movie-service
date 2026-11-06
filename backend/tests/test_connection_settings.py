import pytest
from app.db.models import Base
from app.db.settings import DatabaseSettings, connection_options
from pydantic import SecretStr


def test_supabase_url_preserves_encoded_password_and_ssl():
    config = DatabaseSettings(
        _env_file=None,
        database_url=SecretStr(
            "postgresql://postgres.example:p%40ss%2Fword%25@pooler.example:5432/postgres?sslmode=require"
        ),
    )
    url, options = connection_options(config)
    assert url.drivername == "postgresql+asyncpg"
    assert url.password == "p@ss/word%"
    assert "sslmode" not in url.query
    assert options["ssl"] == "require"


def test_transaction_pooler_is_rejected():
    config = DatabaseSettings(
        _env_file=None,
        database_url=SecretStr(
            "postgresql://postgres:example@pooler.example:6543/postgres"
        ),
    )
    with pytest.raises(ValueError, match="Session pooler"):
        connection_options(config)


def test_metadata_is_scoped_to_application_schema():
    assert len(Base.metadata.tables) == 12
    assert {table.schema for table in Base.metadata.tables.values()} == {
        "movie_service"
    }
