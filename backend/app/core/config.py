from pydantic import Field, SecretStr

from app.db.settings import DatabaseSettings


class Settings(DatabaseSettings):
    app_name: str = "MOVIE_SERVICE"
    app_version: str = "1.0.0"

    jwt_secret_key: SecretStr = Field(min_length=32)
    auth_cookie_secure: bool = True
    auth_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    )


settings = Settings()
