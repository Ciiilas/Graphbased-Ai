"""Neo4j read repository for graph context expansion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.orchestrator.models import GraphExpansion, GraphNeighbor, GraphRelation


class ReadConnection(Protocol):
    def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read query."""


@dataclass(frozen=True)
class GraphContextRepository:
    """Read graph context around seed symbols from Neo4j."""

    connection: ReadConnection

    def expand(self, seed_symbol_ids: list[str], max_neighbors: int) -> GraphExpansion:
        if not seed_symbol_ids:
            return GraphExpansion()

        direct_rows: list[dict[str, Any]] = self.connection.execute_read(
            self._direct_symbol_query(),
            {"seed_ids": seed_symbol_ids, "max_neighbors": max_neighbors},
        )
        file_rows: list[dict[str, Any]] = self.connection.execute_read(
            self._file_dependency_query(),
            {"seed_ids": seed_symbol_ids, "max_neighbors": max_neighbors},
        )
        declaration_rows: list[dict[str, Any]] = self.connection.execute_read(
            self._declaration_query(),
            {"seed_ids": seed_symbol_ids},
        )

        neighbors: list[GraphNeighbor] = []
        relations: list[GraphRelation] = []

        for row in direct_rows:
            self._append_row(row, neighbors, relations, reason="direct_graph")
        for row in file_rows:
            self._append_row(row, neighbors, relations, reason="dependent_file")
        for row in declaration_rows:
            relation = self._relation_from_row(row.get("relation"))
            if relation is not None:
                relations.append(relation)

        return GraphExpansion(
            neighbors=self._dedupe_neighbors(neighbors, max_neighbors),
            relations=self._dedupe_relations(relations),
        )

    def _append_row(
        self,
        row: dict[str, Any],
        neighbors: list[GraphNeighbor],
        relations: list[GraphRelation],
        reason: str,
    ) -> None:
        neighbor = self._neighbor_from_row(row.get("neighbor"), reason)
        relation = self._relation_from_row(row.get("relation"))
        if neighbor is not None:
            neighbors.append(neighbor)
        if relation is not None:
            relations.append(relation)

    def _neighbor_from_row(
        self,
        data: Any,
        reason: str,
    ) -> GraphNeighbor | None:
        if not isinstance(data, dict) or not data.get("id"):
            return None
        return GraphNeighbor(
            symbol_id=str(data["id"]),
            kind=self._optional_string(data.get("kind")),
            name=self._optional_string(data.get("name")),
            fqn=self._optional_string(data.get("fqn")),
            source_path=self._optional_string(data.get("source_path")),
            reason=reason,
        )

    def _relation_from_row(self, data: Any) -> GraphRelation | None:
        if not isinstance(data, dict):
            return None
        if not data.get("type") or not data.get("source_id") or not data.get("target_id"):
            return None
        return GraphRelation(
            type=str(data["type"]),
            source_id=str(data["source_id"]),
            target_id=str(data["target_id"]),
            source_kind=str(data.get("source_kind", "unknown")),
            target_kind=str(data.get("target_kind", "unknown")),
            direction=str(data.get("direction", "related")),
        )

    def _dedupe_neighbors(
        self,
        neighbors: list[GraphNeighbor],
        max_neighbors: int,
    ) -> list[GraphNeighbor]:
        deduped: list[GraphNeighbor] = []
        seen_ids: set[str] = set()
        for neighbor in neighbors:
            if neighbor.symbol_id in seen_ids:
                continue
            seen_ids.add(neighbor.symbol_id)
            deduped.append(neighbor)
            if len(deduped) >= max_neighbors:
                break
        return deduped

    def _dedupe_relations(self, relations: list[GraphRelation]) -> list[GraphRelation]:
        deduped: list[GraphRelation] = []
        seen_keys: set[tuple[str, str, str]] = set()
        for relation in relations:
            key = (relation.type, relation.source_id, relation.target_id)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(relation)
        return deduped

    def _optional_string(self, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def _direct_symbol_query(self) -> str:
        return """
        MATCH (seed:Symbol)
        WHERE seed.id IN $seed_ids
        MATCH (seed)-[relationship:CALLS|EXTENDS]-(neighbor:Symbol)
        RETURN
          {
            id: neighbor.id,
            kind: neighbor.kind,
            name: neighbor.name,
            fqn: neighbor.fqn,
            source_path: neighbor.source_path
          } AS neighbor,
          {
            type: type(relationship),
            source_id: startNode(relationship).id,
            target_id: endNode(relationship).id,
            source_kind: head(labels(startNode(relationship))),
            target_kind: head(labels(endNode(relationship))),
            direction: CASE
              WHEN startNode(relationship).id IN $seed_ids THEN 'outgoing'
              ELSE 'incoming'
            END
          } AS relation
        LIMIT $max_neighbors
        """

    def _file_dependency_query(self) -> str:
        return """
        MATCH (seedFile:File)-[:DECLARES]->(seed:Symbol)
        WHERE seed.id IN $seed_ids
        MATCH (seedFile)-[relationship:DEPENDS_ON]-(neighborFile:File)
        MATCH (neighborFile)-[:DECLARES]->(neighbor:Symbol)
        RETURN
          {
            id: neighbor.id,
            kind: neighbor.kind,
            name: neighbor.name,
            fqn: neighbor.fqn,
            source_path: neighbor.source_path
          } AS neighbor,
          {
            type: type(relationship),
            source_id: startNode(relationship).path,
            target_id: endNode(relationship).path,
            source_kind: head(labels(startNode(relationship))),
            target_kind: head(labels(endNode(relationship))),
            direction: CASE
              WHEN startNode(relationship).path = seedFile.path THEN 'outgoing'
              ELSE 'incoming'
            END
          } AS relation
        LIMIT $max_neighbors
        """

    def _declaration_query(self) -> str:
        return """
        MATCH (file:File)-[relationship:DECLARES]->(seed:Symbol)
        WHERE seed.id IN $seed_ids
        RETURN
          {
            type: type(relationship),
            source_id: file.path,
            target_id: seed.id,
            source_kind: head(labels(file)),
            target_kind: head(labels(seed)),
            direction: 'declares'
          } AS relation
        """

