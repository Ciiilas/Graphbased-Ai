"""Embedding providers for vector search."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, TypeVar

from backend.vector.config import GeminiEmbeddingSettings


class EmbeddingProvider(Protocol):
    """Embeds documents and search queries."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""

    def embed_query(self, query: str) -> list[float]:
        """Return one embedding vector for a search query."""


T = TypeVar("T")

# Gemini's 429 payload includes a hint like "Please retry in 19.238302492s".
# Honoring it is far better than blind backoff because the free-tier quota is a
# per-minute window, so the suggested delay is exactly how long until it refills.
_RETRY_DELAY_PATTERN = re.compile(r"retry in (\d+(?:\.\d+)?)s")


@dataclass
class LlamaIndexGeminiEmbeddingProvider:
    """Gemini embedding provider using LlamaIndex.

    The LlamaIndex import is intentionally lazy so unit tests can exercise the
    vector pipeline without installing optional dependencies or calling Gemini.

    The Gemini free tier caps embedding requests per minute; once the cap is hit
    every further call returns ``429 RESOURCE_EXHAUSTED``. We retry such calls
    with backoff so a transient quota error no longer drops a whole batch.
    """

    settings: GeminiEmbeddingSettings
    max_retries: int = 5
    base_delay_seconds: float = 2.0
    embedding_model: Any = field(init=False)

    def __post_init__(self) -> None:
        if not self.settings.api_key:
            raise ValueError("GEMINI_SECRET_KEY is required for Gemini embeddings.")

        from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

        self.embedding_model = GoogleGenAIEmbedding(
            model_name=self.settings.model_name,
            api_key=self.settings.api_key,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._with_retry(
            lambda: self.embedding_model.get_text_embedding_batch(texts)
        )
        return [self._float_vector(embedding) for embedding in embeddings]

    def embed_query(self, query: str) -> list[float]:
        embedding = self._with_retry(
            lambda: self.embedding_model.get_query_embedding(query)
        )
        return self._float_vector(embedding)

    def _with_retry(self, operation: Callable[[], T]) -> T:
        for attempt in range(self.max_retries + 1):
            try:
                return operation()
            except Exception as error:
                if attempt >= self.max_retries or not self._is_rate_limit(error):
                    raise
                time.sleep(self._retry_delay(error, attempt))
        raise AssertionError("unreachable")  # loop either returns or raises

    @staticmethod
    def _is_rate_limit(error: Exception) -> bool:
        message: str = str(error)
        return "429" in message or "RESOURCE_EXHAUSTED" in message

    def _retry_delay(self, error: Exception, attempt: int) -> float:
        match = _RETRY_DELAY_PATTERN.search(str(error))
        if match is not None:
            # Add a small buffer so we are safely past the quota window edge.
            return float(match.group(1)) + 1.0
        return self.base_delay_seconds * (2.0**attempt)

    def _float_vector(self, embedding: list[float]) -> list[float]:
        return [float(value) for value in embedding]
