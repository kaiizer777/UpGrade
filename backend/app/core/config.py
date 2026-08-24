"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables / .env."""

    app_name: str = "UpGrade API"
    env: str = "development"
    database_url: str = "sqlite:///./upgrade.db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production-use-env-var"
    jwt_secret: str = "change-me-in-production-jwt-secret"
    groq_api_key: str = ""
    opencode_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
