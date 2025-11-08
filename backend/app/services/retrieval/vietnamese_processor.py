"""
Vietnamese Text Processing Service

Provides Vietnamese-specific text tokenization for BM25 keyword search.
Uses pyvi library for word segmentation.
"""

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
    Tokenize a search query in Vietnamese.

    This is used when constructing tsquery for search.

    Args:
        query: Vietnamese search query

    Returns:
        Tokenized query string ready for to_tsquery()
    """
    tokenized = await tokenize_vietnamese(query)

    # Replace spaces with & for AND operator in tsquery
    # Example: "công_ty vintech" -> "công_ty & vintech"
    tokens = tokenized.split()
    return " & ".join(tokens)
