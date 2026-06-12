"""Typed orchestration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SemanticHit:
    """A semantic ChromaDB hit used as graph expansion seed."""

    symbol_id: str
    text: str
    score: float | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "text": self.text,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class GraphNeighbor:
    """A symbol found through graph expansion."""

    symbol_id: str
    kind: str | None = None
    name: str | None = None
    fqn: str | None = None
    source_path: str | None = None
    reason: str = "direct_graph"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "kind": self.kind,
            "name": self.name,
            "fqn": self.fqn,
            "source_path": self.source_path,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class GraphRelation:
    """A graph relationship relevant to the assembled context."""

    type: str
    source_id: str
    target_id: str
    source_kind: str
    target_kind: str
    direction: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "source_kind": self.source_kind,
            "target_kind": self.target_kind,
            "direction": self.direction,
        }


@dataclass(frozen=True)
class GraphExpansion:
    """Symbols and relationships returned by graph expansion."""

    neighbors: list[GraphNeighbor] = field(default_factory=list)
    relations: list[GraphRelation] = field(default_factory=list)


@dataclass(frozen=True)
class CodeSnippet:
    """A ranked code snippet included in the prompt."""

    symbol_id: str
    text: str
    rank: int
    source: str
    score: float | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "text": self.text,
            "rank": self.rank,
            "source": self.source,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class AssembledContext:
    """Prompt-ready context assembled from semantic and graph retrieval."""

    prompt: str
    semantic_hits: list[SemanticHit]
    graph_relations: list[GraphRelation]
    snippets: list[CodeSnippet]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OrchestratorResponse:
    """Structured response returned by the orchestrator."""

    query: str
    answer: str | None
    prompt: str
    semantic_hits: list[SemanticHit]
    graph_relations: list[GraphRelation]
    snippets: list[CodeSnippet]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "prompt": self.prompt,
            "semantic_hits": [hit.to_dict() for hit in self.semantic_hits],
            "graph_relations": [
                relation.to_dict() for relation in self.graph_relations
            ],
            "snippets": [snippet.to_dict() for snippet in self.snippets],
            "warnings": self.warnings,
        }

