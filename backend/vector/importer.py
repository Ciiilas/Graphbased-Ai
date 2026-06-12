"""Import extractor JSON files into ChromaDB."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from backend.vector.chunks import CodeChunk, CodeChunkBuilder
from backend.vector.embeddings import EmbeddingProvider


class VectorRepository(Protocol):
    """Repository operations needed by the vector importer."""

    def reset_collection(self) -> None:
        """Reset the target vector collection."""

    def upsert_chunks(
        self,
        chunks: list[CodeChunk],
        embeddings: list[list[float]],
    ) -> None:
        """Upsert chunks and their embeddings."""


@dataclass
class VectorImportSummary:
    """Result of importing extractor JSON files into the vector store."""

    total_files: int = 0
    imported_files: int = 0
    total_chunks: int = 0
    imported_chunks: int = 0
    failed_files: list[dict[str, str]] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.failed_files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "imported_files": self.imported_files,
            "total_chunks": self.total_chunks,
            "imported_chunks": self.imported_chunks,
            "failed_files": self.failed_files,
            "has_errors": self.has_errors,
        }


@dataclass(frozen=True)
class AstVectorImporter:
    """Load extractor output, build chunks, embed them, and store them."""

    repository: VectorRepository
    embedding_provider: EmbeddingProvider
    chunk_builder: CodeChunkBuilder = field(default_factory=CodeChunkBuilder)
    batch_size: int = 16

    def import_directory(self, ast_root: Path, reset: bool = False) -> VectorImportSummary:
        files_root: Path = ast_root.resolve() / "files"
        if not files_root.exists():
            raise FileNotFoundError(f"AST files directory does not exist: {files_root}")

        if reset:
            self.repository.reset_collection()

        ast_files: list[Path] = sorted(files_root.rglob("*.json"))
        summary = VectorImportSummary(total_files=len(ast_files))
        pending_chunks: list[CodeChunk] = []

        for ast_file in ast_files:
            try:
                parsed_file: dict[str, Any] = json.loads(
                    ast_file.read_text(encoding="utf-8")
                )
                chunks: list[CodeChunk] = self.chunk_builder.build_from_parsed_file(
                    parsed_file
                )
                summary.imported_files += 1
                summary.total_chunks += len(chunks)
                pending_chunks.extend(chunks)
            except Exception as error:
                summary.failed_files.append(
                    {"path": str(ast_file), "error": str(error)}
                )

        for chunk_batch in self._batches(pending_chunks):
            try:
                embeddings: list[list[float]] = self.embedding_provider.embed_documents(
                    [chunk.text for chunk in chunk_batch]
                )
                self.repository.upsert_chunks(chunk_batch, embeddings)
                summary.imported_chunks += len(chunk_batch)
            except Exception as error:
                summary.failed_files.append(
                    {
                        "path": self._batch_paths(chunk_batch),
                        "error": str(error),
                    }
                )

        return summary

    def _batches(self, chunks: list[CodeChunk]) -> list[list[CodeChunk]]:
        return [
            chunks[index : index + self.batch_size]
            for index in range(0, len(chunks), self.batch_size)
        ]

    def _batch_paths(self, chunks: list[CodeChunk]) -> str:
        paths: list[str] = sorted(
            {str(chunk.metadata.get("relative_path", "")) for chunk in chunks}
        )
        return ", ".join(path for path in paths if path)


@dataclass(frozen=True)
class VectorSearchService:
    """Semantic search service that embeds the query before querying Chroma."""

    repository: Any
    embedding_provider: EmbeddingProvider

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        query_embedding: list[float] = self.embedding_provider.embed_query(query)
        results = self.repository.query(query_embedding=query_embedding, limit=limit)
        return [result.to_dict() for result in results]

