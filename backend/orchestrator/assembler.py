"""Assemble retrieved code and graph facts into a prompt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.orchestrator.models import (
    AssembledContext,
    CodeSnippet,
    GraphExpansion,
    GraphNeighbor,
    GraphRelation,
    SemanticHit,
)
from backend.vector.repository import SearchResult


class SnippetRepository(Protocol):
    def get_by_ids(self, ids: list[str]) -> list[SearchResult]:
        """Load code chunks by symbol ids."""


@dataclass(frozen=True)
class ContextAssembler:
    """Dedupe, rank and format snippets for the answer prompt."""

    snippet_repository: SnippetRepository

    def assemble(
        self,
        query: str,
        semantic_hits: list[SemanticHit],
        graph_expansion: GraphExpansion,
        max_snippets: int,
    ) -> AssembledContext:
        warnings: list[str] = []
        if not semantic_hits:
            warnings.append("No semantic hits found.")

        ranked_snippets: list[CodeSnippet] = []
        seen_symbol_ids: set[str] = set()

        for hit in semantic_hits:
            if not hit.symbol_id or hit.symbol_id in seen_symbol_ids:
                continue
            seen_symbol_ids.add(hit.symbol_id)
            ranked_snippets.append(
                self._snippet_from_hit(
                    hit=hit,
                    rank=len(ranked_snippets) + 1,
                    source="semantic",
                )
            )
            if len(ranked_snippets) >= max_snippets:
                break

        remaining_slots: int = max_snippets - len(ranked_snippets)
        if remaining_slots > 0:
            neighbor_ids: list[str] = self._ranked_neighbor_ids(
                graph_expansion.neighbors,
                seen_symbol_ids,
            )
            neighbor_results: list[SearchResult] = self.snippet_repository.get_by_ids(
                neighbor_ids[:remaining_slots]
            )
            neighbor_reasons: dict[str, str] = {
                neighbor.symbol_id: neighbor.reason
                for neighbor in graph_expansion.neighbors
            }
            for result in neighbor_results:
                symbol_id: str = self._symbol_id_from_result(result)
                if not symbol_id or symbol_id in seen_symbol_ids:
                    continue
                seen_symbol_ids.add(symbol_id)
                ranked_snippets.append(
                    self._snippet_from_result(
                        result=result,
                        symbol_id=symbol_id,
                        rank=len(ranked_snippets) + 1,
                        source=neighbor_reasons.get(symbol_id, "graph"),
                    )
                )
                if len(ranked_snippets) >= max_snippets:
                    break

        return AssembledContext(
            prompt=self._build_prompt(query, ranked_snippets, graph_expansion.relations),
            semantic_hits=semantic_hits,
            graph_relations=graph_expansion.relations,
            snippets=ranked_snippets,
            warnings=warnings,
        )

    def _ranked_neighbor_ids(
        self,
        neighbors: list[GraphNeighbor],
        seen_symbol_ids: set[str],
    ) -> list[str]:
        direct_ids: list[str] = []
        dependent_ids: list[str] = []
        for neighbor in neighbors:
            if neighbor.symbol_id in seen_symbol_ids:
                continue
            if neighbor.reason == "dependent_file":
                dependent_ids.append(neighbor.symbol_id)
            else:
                direct_ids.append(neighbor.symbol_id)
        return [*direct_ids, *dependent_ids]

    def _snippet_from_hit(
        self,
        hit: SemanticHit,
        rank: int,
        source: str,
    ) -> CodeSnippet:
        return CodeSnippet(
            symbol_id=hit.symbol_id,
            text=hit.text,
            rank=rank,
            source=source,
            score=hit.score,
            metadata=hit.metadata,
        )

    def _snippet_from_result(
        self,
        result: SearchResult,
        symbol_id: str,
        rank: int,
        source: str,
    ) -> CodeSnippet:
        return CodeSnippet(
            symbol_id=symbol_id,
            text=result.text,
            rank=rank,
            source=source,
            score=result.score,
            metadata=result.metadata,
        )

    def _symbol_id_from_result(self, result: SearchResult) -> str:
        metadata_symbol_id: Any = result.metadata.get("symbol_id")
        if metadata_symbol_id:
            return str(metadata_symbol_id)
        return result.id

    def _build_prompt(
        self,
        query: str,
        snippets: list[CodeSnippet],
        relations: list[GraphRelation],
    ) -> str:
        snippet_blocks: list[str] = []
        for snippet in snippets:
            snippet_blocks.append(
                "\n".join(
                    [
                        f"[Snippet {snippet.rank}]",
                        f"symbol_id: {snippet.symbol_id}",
                        f"source: {snippet.source}",
                        f"score: {snippet.score}",
                        f"path: {snippet.metadata.get('relative_path', '')}",
                        "code:",
                        snippet.text,
                    ]
                )
            )

        relation_lines: list[str] = [
            (
                f"- {relation.type}: {relation.source_id} -> "
                f"{relation.target_id} ({relation.direction})"
            )
            for relation in relations
        ]

        snippets_text: str = "\n\n".join(snippet_blocks) or "No code snippets found."
        relations_text: str = "\n".join(relation_lines) or "No graph relations found."

        return "\n".join(
            [
                "You are Graphbased-AI, a read-only assistant for Scala codebases.",
                "Answer only from the provided code snippets and graph relations.",
                "If the context is incomplete, say what is uncertain.",
                "",
                f"Question: {query}",
                "",
                "Code snippets:",
                snippets_text,
                "",
                "Graph relations:",
                relations_text,
                "",
                "Answer in the user's language when possible.",
            ]
        )

