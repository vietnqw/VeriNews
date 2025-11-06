"""
Text Chunking Service

Provides a modular API to split article content into chunks. Default strategy
is paragraph-level splitting by blank lines.
"""

from __future__ import annotations

from typing import List, Protocol


class TextChunker(Protocol):
    def chunk(self, text: str) -> List[str]: ...


class ParagraphChunker:
    def chunk(self, text: str) -> List[str]:
        # Normalize line endings and split on blank lines
        parts = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n")]
        return [p for p in parts if p]


def chunk_text(content: str, strategy: str = "paragraph") -> List[str]:
    if not content:
        return []
    if strategy == "paragraph":
        return ParagraphChunker().chunk(content)
    # Future strategies can be added here (e.g., token-length based)
    return ParagraphChunker().chunk(content)
