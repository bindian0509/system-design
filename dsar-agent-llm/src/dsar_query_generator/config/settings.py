"""Application settings configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Settings
    api_title: str = "DSAR Query Generator"
    api_version: str = "1.0.0"
    debug: bool = False

    # JWT Settings
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 3600  # 1 hour

    # LLM Settings
    llm_provider: str = "openai"  # "openai" or "anthropic"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gpt-4-turbo"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 2000

    # Validation Settings
    max_tables_per_query: int = 5

    # Schema Registry
    schema_registry_path: Path = Path("config/schema_registry.yaml")

    # Audit Logging
    audit_log_path: Path = Path("logs/audit.jsonl")

    model_config = {"env_prefix": "DSAR_", "env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
