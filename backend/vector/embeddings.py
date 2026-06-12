"""Embedding providers for vector search."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.vector.config import GeminiEmbeddingSettings


class EmbeddingProvider(Protocol):
    """Embeds documents and search queries."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""

    def embed_query(self, query: str) -> list[float]:
        """Return one embedding vector for a search query."""


@dataclass
class LlamaIndexGeminiEmbeddingProvider:
    """Gemini embedding provider using LlamaIndex.

    The LlamaIndex import is intentionally lazy so unit tests can exercise the
    vector pipeline without installing optional dependencies or calling Gemini.
    """

    settings: GeminiEmbeddingSettings
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
        embeddings = self.embedding_model.get_text_embedding_batch(texts)
        return [self._float_vector(embedding) for embedding in embeddings]

    def embed_query(self, query: str) -> list[float]:
        embedding = self.embedding_model.get_query_embedding(query)
        return self._float_vector(embedding)

    def _float_vector(self, embedding: list[float]) -> list[float]:
        return [float(value) for value in embedding]
