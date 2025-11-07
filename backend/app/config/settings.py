"""
Application Settings Module

Loads configuration from two sources:
1. Environment variables (.env) - for secrets and infrastructure settings
2. YAML file (config.yaml) - for application logic and business rules
"""

import yaml
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_yaml_config() -> dict:
    """
    Load YAML configuration file.

    Returns:
        Dictionary containing YAML configuration, or empty dict if file not found
    """
    # Try multiple paths for config.yaml
    possible_paths = [
        Path("config/config.yaml"),  # Run from backend root
        Path(__file__).parent.parent.parent
        / "config"
        / "config.yaml",  # Relative to this file
    ]

    for config_path in possible_paths:
        if config_path.is_file():
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}

    return {}


# Load YAML configuration at module level
yaml_config = load_yaml_config()


class CelerySettings(BaseSettings):
    """Celery configuration for task queue"""

    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"
    worker_count: int = 4
    task_time_limit: int = 300


class SchedulerSettings(BaseSettings):
    """Scheduler configuration for periodic tasks"""

    crawler_interval_minutes: int = 60
    article_expiration_hours: int = 24


class CrawlerSettings(BaseSettings):
    """News crawler configuration"""

    max_articles_per_feed: int = 100
    max_content_length: int = 50000
    fetch_timeout_seconds: int = 30
    user_agent: str = "VeriNews/1.0"


class AISettings(BaseSettings):
    """AI/ML service configuration"""

    provider: str = "openai"  # openai, anthropic, local
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    max_retries: int = 3
    timeout_seconds: int = 30


class Settings(BaseSettings):
    """
    Main application settings.

    Loads from environment variables and YAML configuration.
    Environment files are loaded from the project root (VeriNews/.env).
    """

    model_config = SettingsConfigDict(
        env_file=[
            "../.env",
            "../../.env",
            "../../../.env",
        ],  # Search from backend/app/config up to project root
        env_ignore_empty=True,
        extra="ignore",
    )

    # General Configuration
    API_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "VeriNews"
    ENVIRONMENT: Literal["local", "production"] = "local"

    # Server Configuration
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_CORS_ORIGINS: list[str] = ["*"]
    SECRET_KEY: str

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_ROTATION: str = "500 MB"
    LOG_RETENTION: str = "10 days"
    LOG_COMPRESSION: str = "zip"

    # Database Configuration
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # AI/ML Configuration
    AI_SERVICE_API_KEY: str = ""  # Unified API key for all AI providers

    # YAML-based configurations
    celery: CelerySettings = CelerySettings(**yaml_config.get("celery", {}))
    scheduler: SchedulerSettings = SchedulerSettings(**yaml_config.get("scheduler", {}))
    crawler: CrawlerSettings = CrawlerSettings(**yaml_config.get("crawler", {}))
    ai: AISettings = AISettings(**yaml_config.get("ai", {}))

    @property
    def openai_api_key(self) -> str:
        """Get API key for OpenAI (uses unified AI_SERVICE_API_KEY)"""
        return self.AI_SERVICE_API_KEY

    @property
    def anthropic_api_key(self) -> str:
        """Get API key for Anthropic (uses unified AI_SERVICE_API_KEY)"""
        return self.AI_SERVICE_API_KEY

    @property
    def POSTGRES_URL(self) -> str:
        """Asynchronous PostgreSQL URL for SQLAlchemy with asyncpg driver"""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def POSTGRES_URL_SYNC(self) -> str:
        """Synchronous PostgreSQL URL for Alembic migrations with psycopg2 driver"""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


# Global settings instance
settings = Settings()
