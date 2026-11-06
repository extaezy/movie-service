import ssl
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

BASE_DIR = Path(__file__).resolve().parents[2]


class DatabaseSettings(BaseSettings):
    database_url: SecretStr
    database_ssl: Literal["require", "verify-full", "disable"] = "require"
    database_ssl_root_cert: Path | None = None
    database_pool_size: int = Field(default=2, ge=1, le=10)
    database_max_overflow: int = Field(default=0, ge=0, le=10)

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


def connection_options(config: DatabaseSettings) -> tuple[URL, dict]:
    url = make_url(config.database_url.get_secret_value())
    if url.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
    if url.port == 6543:
        raise ValueError(
            "Use Supabase Session pooler or Direct connection on port 5432"
        )
    ssl_mode = url.query.get("sslmode", config.database_ssl)
    if ssl_mode not in {"require", "verify-full", "disable"}:
        raise ValueError("Use sslmode=require, verify-full or disable")
    url = url.set(drivername="postgresql+asyncpg")
    root_cert = url.query.get("sslrootcert", config.database_ssl_root_cert)
    if root_cert and not Path(root_cert).is_absolute():
        root_cert = BASE_DIR / root_cert
    ssl_option = (
        ssl.create_default_context(cafile=str(root_cert) if root_cert else None)
        if ssl_mode == "verify-full"
        else ssl_mode
    )
    url = url.difference_update_query(["sslmode", "sslrootcert"])
    return url, {"ssl": ssl_option, "timeout": 10, "command_timeout": 30}
