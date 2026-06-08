"""Repository for writing extracted graph data into Neo4j."""

from __future__ import annotations

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
    """Write file and symbol nodes created by the extractor."""

    connection: WriteConnection

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
        ]
        for constraint in constraints:
            self.connection.execute_write(constraint)

    def import_parsed_file(self, parsed_file: dict[str, Any]) -> None:
        """Write one file node plus all its symbols in a single transaction.

        Using ``UNWIND`` keeps the import to one round-trip per file instead of
        ``1 + 2 * symbols``, which matters for large Scala codebases. The file
        node is created even when ``symbols`` is empty, because the file ``MERGE``
        runs before the ``UNWIND``.
        """
        symbol_rows: list[dict[str, Any]] = [
            self._symbol_row(symbol) for symbol in parsed_file.get("symbols", [])
        ]
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
                node.source_path = symbol.source_path,
                node.start_byte = symbol.start_byte,
                node.end_byte = symbol.end_byte
            MERGE (file)-[:DECLARES]->(node)
            """,
            {
                "relative_path": parsed_file["relative_path"],
                "absolute_path": parsed_file["absolute_path"],
                "has_errors": parsed_file["has_errors"],
                "symbols": symbol_rows,
            },
        )

    def _symbol_row(self, symbol: dict[str, Any]) -> dict[str, Any]:
        symbol_range: dict[str, Any] = symbol["range"]
        return {
            "id": self._symbol_id(symbol),
            "kind": symbol["kind"],
            "name": symbol["name"],
            "source_path": symbol["source_path"],
            "start_byte": symbol_range["start_byte"],
            "end_byte": symbol_range["end_byte"],
        }

    def _symbol_id(self, symbol: dict[str, Any]) -> str:
        symbol_range: dict[str, Any] = symbol["range"]
        return (
            f"{symbol['source_path']}:{symbol['kind']}:{symbol['name']}:"
            f"{symbol_range['start_byte']}:{symbol_range['end_byte']}"
        )
