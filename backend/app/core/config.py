from pydantic import Field, SecretStr

from app.db.settings import DatabaseSettings


class Settings(DatabaseSettings):
    app_name: str = "MOVIE_SERVICE"
    app_version: str = "1.0.0"

    jwt_secret_key: SecretStr = Field(min_length=32)


settings = Settings()
