"""
Text Chunking Service

Provides a modular API to split article content into chunks. Default strategy
is paragraph-level splitting by newlines with smart merging for optimal chunk sizes.
"""

from __future__ import annotations

import re
from typing import List, Protocol


class TextChunker(Protocol):
    def chunk(self, text: str) -> List[str]: ...


class ParagraphChunker:
    """
    Smart paragraph chunker that splits text into semantic chunks.

    Strategy:
    1. Split on paragraph boundaries (single or double newlines)
    2. Merge small paragraphs to create optimal chunk sizes (500-2000 chars)
    3. Split very long paragraphs by sentences if needed
    """

    def __init__(self, min_chunk_size: int = 500, max_chunk_size: int = 2000):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def chunk(self, text: str) -> List[str]:
        # Normalize line endings
        text = text.replace("\r\n", "\n")

        # Split into paragraphs (handle both \n\n and single \n)
        # First try double newlines, if that doesn't work, use single newlines
        if "\n\n" in text:
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        else:
            # Split on single newlines and filter empty lines
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        # Merge small paragraphs and split large ones
        chunks = self._optimize_chunks(paragraphs)

        return chunks

    def _optimize_chunks(self, paragraphs: List[str]) -> List[str]:
        """Merge small paragraphs and split large ones for optimal chunk sizes."""
        if not paragraphs:
            return []

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            # If paragraph is very long, split it by sentences
            if para_size > self.max_chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_size = 0

                # Split long paragraph into sentences
                sentences = self._split_sentences(para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    if (
                        current_size + len(sentence) > self.max_chunk_size
                        and current_chunk
                    ):
                        chunks.append("\n\n".join(current_chunk))
                        current_chunk = [sentence]
                        current_size = len(sentence)
                    else:
                        current_chunk.append(sentence)
                        current_size += len(sentence)

                continue

            # Try to add paragraph to current chunk
            if current_size + para_size <= self.max_chunk_size:
                current_chunk.append(para)
                current_size += para_size
            else:
                # Current chunk is full, start a new one
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_size = para_size

        # Don't forget the last chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences using common Vietnamese sentence endings."""
        # Split on common sentence endings: . ! ? followed by space or newline
        # Use regex to preserve the punctuation
        sentences = re.split(r"([.!?]+(?:\s+|$))", text)

        # Recombine sentence with its punctuation
        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
                result.append(sentence.strip())

        # Handle last sentence if no punctuation
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())

        return result


def chunk_text(content: str, strategy: str = "paragraph") -> List[str]:
    if not content:
        return []
    if strategy == "paragraph":
        return ParagraphChunker().chunk(content)
    # Future strategies can be added here (e.g., token-length based)
    return ParagraphChunker().chunk(content)
