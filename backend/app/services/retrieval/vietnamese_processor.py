"""
Vietnamese Text Processing Service

Provides Vietnamese-specific text tokenization for BM25 keyword search.
Uses pyvi library for word segmentation.
"""

import re

from pyvi import ViTokenizer

from app.config.settings import settings


async def tokenize_vietnamese(text: str) -> str:
    """
    Tokenize Vietnamese text for BM25 indexing.

    Vietnamese is a monosyllabic language where multi-word compounds are common.
    This function uses word segmentation to properly identify compound words.

    Example:
        Input:  "Công ty VinTech xây dựng nhà máy mới"
        Output: "công_ty vintech xây_dựng nhà_máy mới"

    Args:
        text: Vietnamese text to tokenize

    Returns:
        Tokenized text with compound words connected by underscores, lowercased
    """
    if not settings.retrieval.vietnamese_processing.enabled:
        # If Vietnamese processing is disabled, just lowercase and return
        return text.lower().strip()

    # Perform word segmentation
    # ViTokenizer.tokenize() connects compound words with underscores
    tokenized = ViTokenizer.tokenize(text)

    # Lowercase for case-insensitive search
    return tokenized.lower().strip()


def prepare_for_tsvector(text: str) -> str:
    """
    Prepare tokenized Vietnamese text for PostgreSQL tsvector.

    PostgreSQL expects space-separated tokens.
    This function is synchronous and can be used in SQL queries.

    Args:
        text: Already tokenized Vietnamese text

    Returns:
        Space-separated tokens ready for to_tsvector()
    """
    # Already tokenized text just needs to be returned as-is
    # PostgreSQL's to_tsvector() will handle the rest
    return text


async def tokenize_for_search(query: str) -> str:
    """
    Tokenize and sanitize a search query in Vietnamese for tsquery.

    This function prepares a raw query string for PostgreSQL's to_tsquery
    by performing tokenization, sanitization, and formatting.

    Args:
        query: Vietnamese search query

    Returns:
        Tokenized and sanitized query string ready for to_tsquery()
    """
    # 1. Tokenize Vietnamese text (e.g., "nhà máy" -> "nhà_máy")
    tokenized = await tokenize_vietnamese(query)

    # 2. Sanitize: Remove characters that are invalid in tsquery.
    #    Allowed characters: letters, numbers, underscores, whitespace.
    sanitized = re.sub(r"[^\w\s]", "", tokenized)

    # 3. Format for tsquery: Join tokens with '&' for AND logic.
    tokens = sanitized.split()
    if not tokens:
        return ""  # Return empty string if no valid tokens remain
    return " & ".join(tokens)
