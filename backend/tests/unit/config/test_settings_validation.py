"""
Unit tests for the startup pipeline-config validation.

The Settings model rejects internally-inconsistent config (confidence weights
that don't sum to 1.0, or reranking top_n exceeding aggregation max_articles) so
misconfiguration fails fast instead of silently mis-scoring.
"""

import pytest
from pydantic import ValidationError

from app.config.settings import (
    Settings,
    _build_retrieval_settings,
    _build_verification_settings,
)


def _valid_kwargs():
    """Minimal kwargs to construct Settings with valid nested config."""
    return dict(
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        POSTGRES_DB="d",
        retrieval=_build_retrieval_settings(),
        verification=_build_verification_settings(),
    )


@pytest.mark.unit
class TestPipelineConfigValidation:
    def test_valid_config_constructs(self):
        settings = Settings(**_valid_kwargs())
        # Sanity: confidence weights indeed sum to ~1.0
        weights = settings.retrieval.confidence_scoring.weights.model_dump()
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_retrieval_weights_must_sum_to_one(self):
        retrieval = _build_retrieval_settings()
        retrieval.confidence_scoring.weights.top_article_score = 0.99  # breaks sum
        kwargs = _valid_kwargs()
        kwargs["retrieval"] = retrieval
        with pytest.raises(ValidationError, match="weights must sum to 1.0"):
            Settings(**kwargs)

    def test_top_n_must_not_exceed_max_articles(self):
        retrieval = _build_retrieval_settings()
        retrieval.reranking.top_n = retrieval.aggregation.max_articles + 5
        kwargs = _valid_kwargs()
        kwargs["retrieval"] = retrieval
        with pytest.raises(ValidationError, match="must be <="):
            Settings(**kwargs)
