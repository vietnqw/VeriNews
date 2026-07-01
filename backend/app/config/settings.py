"""
Application Settings Module

Loads configuration from two sources:
1. Environment variables (.env) - for secrets and infrastructure settings
2. YAML file (config.yaml) - for application logic and business rules
"""

import math
import yaml
from pathlib import Path
from typing import Literal
from pydantic import model_validator
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


class CrawlerSettings(BaseSettings):
    """News crawler configuration"""

    max_articles_per_feed: int = 100
    max_content_length: int = 50000
    # Ingest cutoff: skip fetching articles if published_at < now - ingest_max_age_hours.
    ingest_max_age_hours: int = 24
    # Retention window: delete stored articles if created_at < now - retention_hours.
    retention_hours: int = 24
    fetch_timeout_seconds: int = 30
    user_agent: str = "VeriNews/1.0"


class AISettings(BaseSettings):
    """AI/ML service configuration"""

    provider: str = "openai"  # openai, anthropic, local
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    max_retries: int = 3
    timeout_seconds: int = 30


class VietnameseProcessingSettings(BaseSettings):
    """Vietnamese text processing configuration"""

    enabled: bool = True
    library: str = "pyvi"


class VectorSearchSettings(BaseSettings):
    """Vector similarity search configuration"""

    top_k: int = 100
    similarity_metric: str = "cosine"


class BM25SearchSettings(BaseSettings):
    """BM25 keyword search configuration"""

    top_k: int = 100


class HybridSearchSettings(BaseSettings):
    """Hybrid search configuration"""

    enable_bm25: bool = True
    enable_vector: bool = True


class QueryExtractionSettings(BaseSettings):
    """Query extraction configuration"""

    # Defaults mirror config.yaml so a missing YAML section behaves identically.
    enabled: bool = True
    max_claims: int = 10
    min_factual_confidence: float = 2.0
    enable_similarity_filter: bool = True
    similarity_threshold: float = 0.9


class FusionSettings(BaseSettings):
    """Result fusion configuration"""

    method: str = "rrf"
    rrf_k: int = 60


class EntityFilterSettings(BaseSettings):
    """Entity filtering configuration for reranking"""

    enabled: bool = True
    min_entity_match_ratio: float = 0.6  # mirrors config.yaml


class ArticleLevelRerankingSettings(BaseSettings):
    """Article-level reranking configuration"""

    enabled: bool = True
    num_parallel_workers: int = 8
    worker_timeout_seconds: float = 5.0
    max_concurrent_calls: int = 8
    score_threshold: float = 7.0  # mirrors config.yaml
    max_articles_to_rerank: int = 15
    min_items_for_split: int = 4
    # Skip reranking when there is a single article already this confident (0-10).
    early_exit_score: float = 9.0


class RerankingSettings(BaseSettings):
    """Reranking configuration"""

    enabled: bool = True
    top_n: int = 10
    num_parallel_workers: int = 4
    worker_timeout_seconds: float = 7.0
    max_concurrent_calls: int = 4
    score_threshold: int = 5  # Minimum score (0-10 scale)
    entity_filter: EntityFilterSettings = EntityFilterSettings()
    article_level: ArticleLevelRerankingSettings = ArticleLevelRerankingSettings()


class AggregationSettings(BaseSettings):
    """Article aggregation configuration"""

    max_articles: int = 10
    include_chunks: bool = True
    min_chunk_score: float = 5.0  # Minimum max chunk score for article (0-10 scale)


class ConfidenceScoringWeights(BaseSettings):
    """Weights for confidence scoring components"""

    top_article_score: float = 0.35
    score_gap_ratio: float = 0.25
    entity_coverage: float = 0.20
    temporal_alignment: float = 0.10
    title_similarity: float = 0.10


class ConfidenceScoringThresholds(BaseSettings):
    """Thresholds for confidence tiers"""

    high: float = 0.75
    medium: float = 0.50
    low: float = 0.25


class ConfidenceScoringSettings(BaseSettings):
    """Confidence scoring configuration"""

    enabled: bool = True
    min_confidence_threshold: float = 0.25
    weights: ConfidenceScoringWeights = ConfidenceScoringWeights()
    thresholds: ConfidenceScoringThresholds = ConfidenceScoringThresholds()


class FallbackRetrievalSettings(BaseSettings):
    """Fallback ('related mode') retrieval configuration.

    Used only when strict retrieval returns no articles; relaxes filtering to
    surface loosely-related articles instead of nothing.
    """

    rerank_score_threshold: int = 3


class CacheSettings(BaseSettings):
    """Caching configuration"""

    enabled: bool = True
    ttl_hours: int = 24
    redis_key_prefix: str = "retrieval:"

    @property
    def ttl_seconds(self) -> int:
        """Get TTL in seconds"""
        return self.ttl_hours * 3600


# Verification Pipeline Settings
class StanceClassificationSettings(BaseSettings):
    """Stance classification (NLI) configuration"""

    num_parallel_workers: int = 4
    worker_timeout_seconds: float = 10.0
    min_confidence: float = 0.6


class VerificationAggregationSettings(BaseSettings):
    """Verification verdict aggregation configuration"""

    min_evidence_per_claim: int = 1
    conflict_mode: str = "conservative"  # conservative, majority, recency


class VerdictSettings(BaseSettings):
    """Overall verdict generation configuration"""

    mode: str = "worst_case"  # worst_case, majority, weighted
    types: list[str] = [
        "FULLY_SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "REFUTED",
        "NOT_ENOUGH_INFO",
    ]


class VerificationConfidenceWeights(BaseSettings):
    """Weights for verification confidence scoring"""

    evidence_quality: float = 0.45
    source_agreement: float = 0.30
    source_quantity: float = 0.15
    temporal_relevance: float = 0.10


class VerificationConfidenceScoringSettings(BaseSettings):
    """Verification confidence scoring configuration"""

    weights: VerificationConfidenceWeights = VerificationConfidenceWeights()


class ExplanationSettings(BaseSettings):
    """Explanation generation configuration"""

    language: str = "vi"
    max_length: int = 500


class VerificationSettings(BaseSettings):
    """Verification pipeline configuration"""

    enabled: bool = True
    stance_classification: StanceClassificationSettings
    aggregation: VerificationAggregationSettings
    verdict: VerdictSettings
    confidence_scoring: VerificationConfidenceScoringSettings
    explanation: ExplanationSettings


class RetrievalSettings(BaseSettings):
    """Retrieval pipeline configuration"""

    vietnamese_processing: VietnameseProcessingSettings
    vector_search: VectorSearchSettings
    bm25_search: BM25SearchSettings
    hybrid: HybridSearchSettings
    query_extraction: QueryExtractionSettings
    fusion: FusionSettings
    reranking: RerankingSettings
    aggregation: AggregationSettings
    confidence_scoring: ConfidenceScoringSettings
    cache: CacheSettings
    fallback: FallbackRetrievalSettings


def _build_retrieval_settings() -> RetrievalSettings:
    """Build the retrieval settings tree from the (module-level) YAML config."""
    retrieval_config = yaml_config.get("retrieval", {})
    return RetrievalSettings(
        vietnamese_processing=VietnameseProcessingSettings(
            **retrieval_config.get("vietnamese_processing", {})
        ),
        vector_search=VectorSearchSettings(**retrieval_config.get("vector_search", {})),
        bm25_search=BM25SearchSettings(**retrieval_config.get("bm25_search", {})),
        hybrid=HybridSearchSettings(**retrieval_config.get("hybrid", {})),
        query_extraction=QueryExtractionSettings(
            **retrieval_config.get("query_extraction", {})
        ),
        fusion=FusionSettings(**retrieval_config.get("fusion", {})),
        reranking=RerankingSettings(**retrieval_config.get("reranking", {})),
        aggregation=AggregationSettings(**retrieval_config.get("aggregation", {})),
        confidence_scoring=ConfidenceScoringSettings(
            **retrieval_config.get("confidence_scoring", {})
        ),
        cache=CacheSettings(**retrieval_config.get("cache", {})),
        fallback=FallbackRetrievalSettings(**retrieval_config.get("fallback", {})),
    )


def _build_verification_settings() -> VerificationSettings:
    """Build the verification settings tree from the (module-level) YAML config."""
    verification_config = yaml_config.get("verification", {})
    return VerificationSettings(
        enabled=verification_config.get("enabled", True),
        stance_classification=StanceClassificationSettings(
            **verification_config.get("stance_classification", {})
        ),
        aggregation=VerificationAggregationSettings(
            **verification_config.get("aggregation", {})
        ),
        verdict=VerdictSettings(**verification_config.get("verdict", {})),
        confidence_scoring=VerificationConfidenceScoringSettings(
            **verification_config.get("confidence_scoring", {})
        ),
        explanation=ExplanationSettings(**verification_config.get("explanation", {})),
    )


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

    # Retrieval & verification pipeline configuration.
    # Built once at construction (the nested trees have required fields) instead
    # of being reconstructed from YAML on every access.
    retrieval: RetrievalSettings = _build_retrieval_settings()
    verification: VerificationSettings = _build_verification_settings()

    @model_validator(mode="after")
    def _validate_pipeline_config(self) -> "Settings":
        """Fail fast on internally-inconsistent pipeline config.

        Catches the mistakes that otherwise surface as silently wrong scoring:
        confidence-weight groups that don't sum to 1.0, and a reranking ``top_n``
        larger than the number of articles aggregation will keep.
        """
        errors: list[str] = []

        def _check_weights(label: str, weights: dict[str, float]) -> None:
            total = sum(weights.values())
            if not math.isclose(total, 1.0, abs_tol=0.01):
                errors.append(f"{label} weights must sum to 1.0 (got {total:.3f})")

        _check_weights(
            "retrieval.confidence_scoring",
            self.retrieval.confidence_scoring.weights.model_dump(),
        )
        _check_weights(
            "verification.confidence_scoring",
            self.verification.confidence_scoring.weights.model_dump(),
        )

        top_n = self.retrieval.reranking.top_n
        max_articles = self.retrieval.aggregation.max_articles
        if top_n > max_articles:
            errors.append(
                f"retrieval.reranking.top_n ({top_n}) must be <= "
                f"retrieval.aggregation.max_articles ({max_articles})"
            )

        if errors:
            raise ValueError("Invalid pipeline configuration: " + "; ".join(errors))

        return self

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
