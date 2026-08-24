"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables / .env."""

    app_name: str = "UpGrade API"
    env: str = "development"
    database_url: str = "sqlite:///./upgrade.db"
    secret_key: str = "change-me-in-production-use-env-var"
    groq_api_key: str = ""
    opencode_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
