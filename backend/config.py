"""
Konfiguration via Environment Variables (geladen aus .env).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Discord
    discord_token: str
    discord_guild_id: str | None = None

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-opus-4-7"

    # Database
    database_url: str = "postgresql://widerspruch:dev@localhost:5432/widerspruch"

    # AWS (later)
    aws_region: str = "eu-central-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_evidence_bucket: str | None = None

    # App
    log_level: str = "INFO"
    environment: str = "development"


settings = Settings()
