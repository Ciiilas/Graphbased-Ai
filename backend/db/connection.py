"""Neo4j driver wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neo4j import Driver, GraphDatabase

from backend.db.config import Neo4jSettings


@dataclass
class Neo4jConnection:
    """Owns a Neo4j driver and exposes small query helpers."""

    settings: Neo4jSettings
    driver: Driver = field(init=False)

    def __post_init__(self) -> None:
        self.driver = GraphDatabase.driver(
            self.settings.uri,
            auth=(self.settings.username, self.settings.password),
        )

    def __enter__(self) -> "Neo4jConnection":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def close(self) -> None:
        self.driver.close()

    def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        with self.driver.session(database=self.settings.database) as session:
            session.execute_write(self._run_query, query, parameters or {})

    def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        with self.driver.session(database=self.settings.database) as session:
            return session.execute_read(self._read_query, query, parameters or {})

    @staticmethod
    def _run_query(transaction: Any, query: str, parameters: dict[str, Any]) -> None:
        transaction.run(query, parameters)

    @staticmethod
    def _read_query(
        transaction: Any,
        query: str,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        result = transaction.run(query, parameters)
        return [dict(record) for record in result]
