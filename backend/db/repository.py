"""Repository for writing extracted graph data into Neo4j."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol


class WriteConnection(Protocol):
    def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Execute a write query."""


@dataclass(frozen=True)
class Neo4jGraphRepository:
    """Write file, symbol, external import and relation graph facts."""

    connection: WriteConnection

    def clear_graph(self) -> None:
        """Remove all nodes and relationships.

        The Neo4j instance is dedicated to this tool, so a full wipe gives a
        clean slate before a re-import and avoids mixing data from earlier
        extractor runs or schema versions (additive MERGE never deletes).
        """
        self.connection.execute_write("MATCH (n) DETACH DELETE n")

    def create_constraints(self) -> None:
        constraints: list[str] = [
            """
            CREATE CONSTRAINT file_path_unique IF NOT EXISTS
            FOR (file:File)
            REQUIRE file.path IS UNIQUE
            """,
            """
            CREATE CONSTRAINT symbol_id_unique IF NOT EXISTS
            FOR (symbol:Symbol)
            REQUIRE symbol.id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT external_import_id_unique IF NOT EXISTS
            FOR (external:ExternalImport)
            REQUIRE external.id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT call_id_unique IF NOT EXISTS
            FOR (call:Call)
            REQUIRE call.id IS UNIQUE
            """,
        ]
        for constraint in constraints:
            self.connection.execute_write(constraint)

    def import_parsed_file(self, parsed_file: dict[str, Any]) -> None:
        """Write one parsed file document into Neo4j."""

        # ``import`` symbols are an extraction-time intermediate used to build
        # IMPORTS relations; they are never linked in the graph, so persisting
        # them would only create orphan nodes. Imports live as IMPORTS edges.
        symbol_rows: list[dict[str, Any]] = [
            self._symbol_row(symbol)
            for symbol in parsed_file.get("symbols", [])
            if symbol.get("kind") != "import"
        ]
        relation_rows: list[dict[str, Any]] = [
            self._relation_row(relation)
            for relation in parsed_file.get("relations", [])
        ]

        self._write_file_and_symbols(parsed_file, symbol_rows)
        self._write_declarations(relation_rows)
        self._write_imports(relation_rows)
        self._write_extends(relation_rows)
        self._write_instantiations(relation_rows)
        self._write_uses(relation_rows)
        self._write_calls(relation_rows)
        self._write_depends_on(relation_rows)

    def _write_file_and_symbols(
        self,
        parsed_file: dict[str, Any],
        symbol_rows: list[dict[str, Any]],
    ) -> None:
        self.connection.execute_write(
            """
            MERGE (file:File {path: $relative_path})
            SET file.absolute_path = $absolute_path,
                file.has_errors = $has_errors
            WITH file
            UNWIND $symbols AS symbol
            MERGE (node:Symbol {id: symbol.id})
            SET node.kind = symbol.kind,
                node.name = symbol.name,
                node.fqn = symbol.fqn,
                node.parent_id = symbol.parent_id,
                node.source_path = symbol.source_path,
                node.start_byte = symbol.start_byte,
                node.end_byte = symbol.end_byte,
                node.metadata_json = symbol.metadata_json
            """,
            {
                "relative_path": parsed_file["relative_path"],
                "absolute_path": parsed_file["absolute_path"],
                "has_errors": parsed_file["has_errors"],
                "symbols": symbol_rows,
            },
        )

    def _write_declarations(self, relation_rows: list[dict[str, Any]]) -> None:
        declarations: list[dict[str, Any]] = self._relations_of_type(
            relation_rows,
            "DECLARES",
        )
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            OPTIONAL MATCH (source_file:File {path: relation.source_id})
            OPTIONAL MATCH (source_symbol:Symbol {id: relation.source_id})
            MERGE (target:Symbol {id: relation.target_id})
            WITH relation, target, coalesce(source_symbol, source_file) AS source
            WHERE source IS NOT NULL
            MERGE (source)-[:DECLARES]->(target)
            """,
            {"relations": declarations},
        )

    def _write_imports(self, relation_rows: list[dict[str, Any]]) -> None:
        imports: list[dict[str, Any]] = self._relations_of_type(relation_rows, "IMPORTS")
        internal_imports: list[dict[str, Any]] = [
            relation for relation in imports if relation["target_kind"] == "symbol"
        ]
        external_imports: list[dict[str, Any]] = [
            relation
            for relation in imports
            if relation["target_kind"] == "external_import"
        ]
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            MERGE (source:File {path: relation.source_id})
            MERGE (target:Symbol {id: relation.target_id})
            MERGE (source)-[:IMPORTS]->(target)
            """,
            {"relations": internal_imports},
        )
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            MERGE (source:File {path: relation.source_id})
            MERGE (target:ExternalImport {id: relation.target_id})
            SET target.fqn = relation.metadata.fqn,
                target.library = relation.metadata.library
            MERGE (source)-[:IMPORTS]->(target)
            """,
            {"relations": external_imports},
        )

    def _write_extends(self, relation_rows: list[dict[str, Any]]) -> None:
        extends_relations: list[dict[str, Any]] = self._relations_of_type(
            relation_rows,
            "EXTENDS",
        )
        internal_extends: list[dict[str, Any]] = [
            relation
            for relation in extends_relations
            if relation["target_kind"] == "symbol"
        ]
        external_extends: list[dict[str, Any]] = [
            relation
            for relation in extends_relations
            if relation["target_kind"] == "external_import"
        ]
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            MERGE (source:Symbol {id: relation.source_id})
            MERGE (target:Symbol {id: relation.target_id})
            MERGE (source)-[:EXTENDS]->(target)
            """,
            {"relations": internal_extends},
        )
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            MERGE (source:Symbol {id: relation.source_id})
            MERGE (target:ExternalImport {id: relation.target_id})
            SET target.fqn = relation.metadata.fqn,
                target.library = relation.metadata.library
            MERGE (source)-[:EXTENDS]->(target)
            """,
            {"relations": external_extends},
        )

    def _write_instantiations(self, relation_rows: list[dict[str, Any]]) -> None:
        instantiations: list[dict[str, Any]] = self._relations_of_type(
            relation_rows,
            "INSTANTIATES",
        )
        internal: list[dict[str, Any]] = [
            relation
            for relation in instantiations
            if relation["target_kind"] == "symbol"
        ]
        external: list[dict[str, Any]] = [
            relation
            for relation in instantiations
            if relation["target_kind"] == "external_import"
        ]
        # The source is the enclosing symbol, or the file when an instantiation
        # sits outside any symbol, so it is resolved against both labels.
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            OPTIONAL MATCH (source_file:File {path: relation.source_id})
            OPTIONAL MATCH (source_symbol:Symbol {id: relation.source_id})
            WITH relation, coalesce(source_symbol, source_file) AS source
            WHERE source IS NOT NULL
            MERGE (target:Symbol {id: relation.target_id})
            MERGE (source)-[:INSTANTIATES]->(target)
            """,
            {"relations": internal},
        )
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            OPTIONAL MATCH (source_file:File {path: relation.source_id})
            OPTIONAL MATCH (source_symbol:Symbol {id: relation.source_id})
            WITH relation, coalesce(source_symbol, source_file) AS source
            WHERE source IS NOT NULL
            MERGE (target:ExternalImport {id: relation.target_id})
            SET target.fqn = relation.metadata.fqn,
                target.library = relation.metadata.library
            MERGE (source)-[:INSTANTIATES]->(target)
            """,
            {"relations": external},
        )

    def _write_uses(self, relation_rows: list[dict[str, Any]]) -> None:
        uses: list[dict[str, Any]] = self._relations_of_type(relation_rows, "USES")
        internal: list[dict[str, Any]] = [
            relation for relation in uses if relation["target_kind"] == "symbol"
        ]
        external: list[dict[str, Any]] = [
            relation
            for relation in uses
            if relation["target_kind"] == "external_import"
        ]
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            MERGE (source:Symbol {id: relation.source_id})
            MERGE (target:Symbol {id: relation.target_id})
            MERGE (source)-[:USES]->(target)
            """,
            {"relations": internal},
        )
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            MERGE (source:Symbol {id: relation.source_id})
            MERGE (target:ExternalImport {id: relation.target_id})
            SET target.fqn = relation.metadata.fqn,
                target.library = relation.metadata.library
            MERGE (source)-[:USES]->(target)
            """,
            {"relations": external},
        )

    def _write_calls(self, relation_rows: list[dict[str, Any]]) -> None:
        calls: list[dict[str, Any]] = self._relations_of_type(relation_rows, "CALLS")
        resolved_calls: list[dict[str, Any]] = [
            relation for relation in calls if relation["target_kind"] == "symbol"
        ]
        unresolved_calls: list[dict[str, Any]] = [
            relation for relation in calls if relation["target_kind"] == "call"
        ]
        # ``paren_free`` (a method call written without parentheses, which is
        # indistinguishable from a field read in Scala) is kept on the CALLS
        # relationship so it stays filterable for both resolved and unresolved
        # calls. It is absent from metadata unless true, hence the coalesce.
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            MERGE (source:Symbol {id: relation.source_id})
            MERGE (target:Symbol {id: relation.target_id})
            MERGE (source)-[call:CALLS]->(target)
            SET call.paren_free = coalesce(relation.metadata.paren_free, false)
            """,
            {"relations": resolved_calls},
        )
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            MERGE (source:Symbol {id: relation.source_id})
            MERGE (target:Call {id: relation.call_id})
            SET target.callee_name = relation.metadata.callee_name,
                target.receiver = relation.metadata.receiver,
                target.resolved = false
            MERGE (source)-[call:CALLS]->(target)
            SET call.paren_free = coalesce(relation.metadata.paren_free, false)
            """,
            {"relations": unresolved_calls},
        )

    def _write_depends_on(self, relation_rows: list[dict[str, Any]]) -> None:
        depends_on: list[dict[str, Any]] = self._relations_of_type(
            relation_rows,
            "DEPENDS_ON",
        )
        self.connection.execute_write(
            """
            UNWIND $relations AS relation
            MERGE (source:File {path: relation.source_id})
            MERGE (target:File {path: relation.target_id})
            MERGE (source)-[:DEPENDS_ON]->(target)
            """,
            {"relations": depends_on},
        )

    def _symbol_row(self, symbol: dict[str, Any]) -> dict[str, Any]:
        symbol_range: dict[str, Any] = symbol["range"]
        return {
            "id": symbol.get("id") or self._symbol_id(symbol),
            "kind": symbol["kind"],
            "name": symbol["name"],
            "fqn": symbol.get("fqn"),
            "parent_id": symbol.get("parent_id"),
            "metadata_json": json.dumps(symbol.get("metadata", {}), ensure_ascii=False),
            "source_path": symbol["source_path"],
            "start_byte": symbol_range["start_byte"],
            "end_byte": symbol_range["end_byte"],
        }

    def _relation_row(self, relation: dict[str, Any]) -> dict[str, Any]:
        metadata: dict[str, Any] = relation.get("metadata", {})
        return {
            "type": relation["type"],
            "source_id": relation["source_id"],
            "target_id": relation.get("target_id"),
            "target_kind": relation.get("target_kind", "symbol"),
            "metadata": metadata,
            "call_id": self._call_id(relation, metadata),
        }

    def _relations_of_type(
        self,
        relation_rows: list[dict[str, Any]],
        relation_type: str,
    ) -> list[dict[str, Any]]:
        return [
            relation for relation in relation_rows if relation["type"] == relation_type
        ]

    def _call_id(self, relation: dict[str, Any], metadata: dict[str, Any]) -> str:
        callee_name: str = str(metadata.get("callee_name", "unknown"))
        receiver: str = str(metadata.get("receiver") or "")
        return f"{relation['source_id']}:call:{receiver}:{callee_name}"

    def _symbol_id(self, symbol: dict[str, Any]) -> str:
        symbol_range: dict[str, Any] = symbol["range"]
        return (
            f"{symbol['source_path']}:{symbol['kind']}:{symbol['name']}:"
            f"{symbol_range['start_byte']}:{symbol_range['end_byte']}"
        )
