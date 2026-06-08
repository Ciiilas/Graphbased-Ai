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
        relative_path: str = parsed_file["relative_path"]
        self.upsert_file(
            relative_path=relative_path,
            absolute_path=parsed_file["absolute_path"],
            has_errors=parsed_file["has_errors"],
        )

        for symbol in parsed_file.get("symbols", []):
            symbol_id: str = self._symbol_id(symbol)
            self.upsert_symbol(symbol_id, symbol)
            self.link_file_to_symbol(relative_path, symbol_id)

    def upsert_file(
        self,
        relative_path: str,
        absolute_path: str,
        has_errors: bool,
    ) -> None:
        self.connection.execute_write(
            """
            MERGE (file:File {path: $relative_path})
            SET file.absolute_path = $absolute_path,
                file.has_errors = $has_errors
            """,
            {
                "relative_path": relative_path,
                "absolute_path": absolute_path,
                "has_errors": has_errors,
            },
        )

    def upsert_symbol(self, symbol_id: str, symbol: dict[str, Any]) -> None:
        symbol_range: dict[str, Any] = symbol["range"]
        self.connection.execute_write(
            """
            MERGE (symbol:Symbol {id: $symbol_id})
            SET symbol.kind = $kind,
                symbol.name = $name,
                symbol.source_path = $source_path,
                symbol.start_byte = $start_byte,
                symbol.end_byte = $end_byte
            """,
            {
                "symbol_id": symbol_id,
                "kind": symbol["kind"],
                "name": symbol["name"],
                "source_path": symbol["source_path"],
                "start_byte": symbol_range["start_byte"],
                "end_byte": symbol_range["end_byte"],
            },
        )

    def link_file_to_symbol(self, relative_path: str, symbol_id: str) -> None:
        self.connection.execute_write(
            """
            MATCH (file:File {path: $relative_path})
            MATCH (symbol:Symbol {id: $symbol_id})
            MERGE (file)-[:DECLARES]->(symbol)
            """,
            {
                "relative_path": relative_path,
                "symbol_id": symbol_id,
            },
        )

    def _symbol_id(self, symbol: dict[str, Any]) -> str:
        symbol_range: dict[str, Any] = symbol["range"]
        return (
            f"{symbol['source_path']}:{symbol['kind']}:{symbol['name']}:"
            f"{symbol_range['start_byte']}:{symbol_range['end_byte']}"
        )
