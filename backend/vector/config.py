"""Configuration for ChromaDB and Gemini embeddings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ChromaSettings:
    """ChromaDB connection settings loaded from environment variables."""

    host: str = "localhost"
    port: int = 8001
    collection: str = "scala_code_chunks"

    @classmethod
    def from_env(cls) -> "ChromaSettings":
        return cls(
            host=os.getenv("CHROMA_HOST", cls.host),
            port=int(os.getenv("CHROMA_PORT", str(cls.port))),
            collection=os.getenv("CHROMA_COLLECTION", cls.collection),
        )


@dataclass(frozen=True)
class GeminiEmbeddingSettings:
    """Gemini embedding settings loaded from environment variables."""

    api_key: str | None = None
    model_name: str = "gemini-embedding-001"

    @classmethod
    def from_env(cls) -> "GeminiEmbeddingSettings":
        return cls(
            api_key=os.getenv("GEMINI_SECRET_KEY"),
            model_name=os.getenv("GEMINI_EMBEDDING_MODEL", cls.model_name),
        )

