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

    # AI provider selection ("groq" | "opencode")
    ai_provider: str = "groq"
    ai_model_groq: str = "openai/gpt-oss-120b"
    ai_model_opencode: str = "hy3-free"
    ai_base_url_groq: str = "https://api.groq.com/openai/v1"
    ai_base_url_opencode: str = "https://opencode.ai/zen/v1"
    google_client_id: str = ""
    google_client_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def async_database_url(self) -> str:
        """Return database URL with async driver for PostgreSQL or SQLite."""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        if "sslmode=" in url:
            url = url.replace("sslmode=", "ssl=")
        return url


settings = Settings()
