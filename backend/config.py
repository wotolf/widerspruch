"""
Konfiguration via Environment Variables (geladen aus .env).
"""
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Discord
    discord_token: str
    discord_guild_id: str | None = None

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-opus-4-7"

    # Database — entweder DATABASE_URL direkt oder Einzelteile
    database_url: str = ""
    db_user: str = "widerspruch"
    db_host: str = "localhost"
    db_port: str = "5432"
    db_name: str = "widerspruch"
    db_password: str = "dev"

    # AWS (later)
    aws_region: str = "eu-central-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_evidence_bucket: str | None = None

    # Admin
    admin_discord_ids: list[str] = []

    # App
    log_level: str = "INFO"
    environment: str = "development"

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        if self.db_host != "localhost" or not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return self


settings = Settings()
