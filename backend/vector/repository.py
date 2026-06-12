"""ChromaDB repository for code chunks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.vector.chunks import CodeChunk
from backend.vector.config import ChromaSettings


@dataclass(frozen=True)
class SearchResult:
    """One semantic search result from ChromaDB."""

    id: str
    text: str
    score: float | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class ChromaVectorRepository:
    """Read and write code chunks in a ChromaDB collection."""

    settings: ChromaSettings
    client: Any = field(init=False)
    collection: Any = field(init=False)

    # Gemini embeddings are designed for cosine similarity, so the collection
    # must use the cosine space. With the default L2 space the ``1 - distance``
    # score computed in ``_search_results`` would not be a meaningful similarity.
    _COLLECTION_METADATA: dict[str, str] = field(
        default_factory=lambda: {"hnsw:space": "cosine"},
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        import chromadb

        self.client = chromadb.HttpClient(
            host=self.settings.host,
            port=self.settings.port,
        )
        self.collection = self._get_or_create_collection()

    def reset_collection(self) -> None:
        existing_names: set[str] = self._collection_names()
        if self.settings.collection in existing_names:
            self.client.delete_collection(name=self.settings.collection)
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self) -> Any:
        return self.client.get_or_create_collection(
            name=self.settings.collection,
            metadata=self._COLLECTION_METADATA,
        )

    def upsert_chunks(
        self,
        chunks: list[CodeChunk],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts do not match.")

        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
            embeddings=embeddings,
        )

    def query(
        self,
        query_embedding: list[float],
        limit: int,
    ) -> list[SearchResult]:
        response: dict[str, Any] = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        return self._search_results(response)

    def get_by_ids(self, ids: list[str]) -> list[SearchResult]:
        if not ids:
            return []

        response: dict[str, Any] = self.collection.get(
            ids=ids,
            include=["documents", "metadatas"],
        )
        results: list[SearchResult] = self._get_results(response)

        # ChromaDB does not guarantee that get() returns rows in the requested
        # id order, and silently omits ids it does not know. Realign to the
        # caller's order so positional zipping in the orchestrator is safe.
        results_by_id: dict[str, SearchResult] = {
            result.id: result for result in results
        }
        return [results_by_id[item_id] for item_id in ids if item_id in results_by_id]

    def _collection_names(self) -> set[str]:
        collections: list[Any] = self.client.list_collections()
        names: set[str] = set()
        for collection in collections:
            if isinstance(collection, str):
                names.add(collection)
            else:
                names.add(str(collection.name))
        return names

    def _search_results(self, response: dict[str, Any]) -> list[SearchResult]:
        ids: list[str] = response.get("ids", [[]])[0]
        documents: list[str | None] = response.get("documents", [[]])[0]
        metadatas: list[dict[str, Any] | None] = response.get("metadatas", [[]])[0]
        distances: list[float | None] = response.get("distances", [[]])[0]

        results: list[SearchResult] = []
        for index, item_id in enumerate(ids):
            distance: float | None = distances[index] if index < len(distances) else None
            score: float | None = None if distance is None else 1.0 - float(distance)
            results.append(
                SearchResult(
                    id=str(item_id),
                    text=str(documents[index] or "") if index < len(documents) else "",
                    score=score,
                    metadata=metadatas[index] or {} if index < len(metadatas) else {},
                )
            )
        return results

    def _get_results(self, response: dict[str, Any]) -> list[SearchResult]:
        ids: list[str] = response.get("ids", [])
        documents: list[str | None] = response.get("documents", [])
        metadatas: list[dict[str, Any] | None] = response.get("metadatas", [])

        results: list[SearchResult] = []
        for index, item_id in enumerate(ids):
            results.append(
                SearchResult(
                    id=str(item_id),
                    text=str(documents[index] or "") if index < len(documents) else "",
                    score=None,
                    metadata=metadatas[index] or {} if index < len(metadatas) else {},
                )
            )
        return results
