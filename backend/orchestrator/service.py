"""Orchestrate semantic retrieval, graph expansion and prompt assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.orchestrator.assembler import ContextAssembler, SnippetRepository
from backend.orchestrator.models import (
    GraphExpansion,
    OrchestratorResponse,
    SemanticHit,
)
from backend.orchestrator.llm import AnswerProvider
from backend.vector.embeddings import EmbeddingProvider
from backend.vector.repository import SearchResult


class VectorSearchRepository(SnippetRepository, Protocol):
    def query(self, query_embedding: list[float], limit: int) -> list[SearchResult]:
        """Run vector search with an already-created query embedding."""


class GraphExpansionRepository(Protocol):
    def expand(self, seed_symbol_ids: list[str], max_neighbors: int) -> GraphExpansion:
        """Return graph neighbors and relationships around seed symbols."""


@dataclass(frozen=True)
class CodeQuestionOrchestrator:
    """Run the v1 question-answer context pipeline."""

    embedding_provider: EmbeddingProvider
    vector_repository: VectorSearchRepository
    graph_repository: GraphExpansionRepository
    answer_provider: AnswerProvider | None = None

    def answer(
        self,
        query: str,
        top_k: int = 5,
        max_neighbors: int = 20,
        max_snippets: int = 12,
        generate: bool = True,
    ) -> OrchestratorResponse:
        query_embedding: list[float] = self.embedding_provider.embed_query(query)
        vector_results: list[SearchResult] = self.vector_repository.query(
            query_embedding=query_embedding,
            limit=top_k,
        )
        semantic_hits: list[SemanticHit] = self._semantic_hits(vector_results)
        seed_symbol_ids: list[str] = [
            hit.symbol_id for hit in semantic_hits if hit.symbol_id
        ]
        graph_expansion: GraphExpansion = self.graph_repository.expand(
            seed_symbol_ids=seed_symbol_ids,
            max_neighbors=max_neighbors,
        )
        assembler = ContextAssembler(self.vector_repository)
        assembled_context = assembler.assemble(
            query=query,
            semantic_hits=semantic_hits,
            graph_expansion=graph_expansion,
            max_snippets=max_snippets,
        )
        generated_answer: str | None = None
        if generate and self.answer_provider is not None:
            generated_answer = self.answer_provider.generate_answer(
                assembled_context.prompt
            )

        return OrchestratorResponse(
            query=query,
            answer=generated_answer,
            prompt=assembled_context.prompt,
            semantic_hits=assembled_context.semantic_hits,
            graph_relations=assembled_context.graph_relations,
            snippets=assembled_context.snippets,
            warnings=assembled_context.warnings,
        )

    def _semantic_hits(self, vector_results: list[SearchResult]) -> list[SemanticHit]:
        hits: list[SemanticHit] = []
        for result in sorted(
            vector_results,
            key=lambda item: item.score if item.score is not None else -1.0,
            reverse=True,
        ):
            symbol_id: str = self._symbol_id_from_result(result)
            if not symbol_id:
                continue
            hits.append(
                SemanticHit(
                    symbol_id=symbol_id,
                    text=result.text,
                    score=result.score,
                    metadata=result.metadata,
                )
            )
        return hits

    def _symbol_id_from_result(self, result: SearchResult) -> str:
        metadata_symbol_id: Any = result.metadata.get("symbol_id")
        if metadata_symbol_id:
            return str(metadata_symbol_id)
        if result.id.startswith("file:"):
            return ""
        return result.id
