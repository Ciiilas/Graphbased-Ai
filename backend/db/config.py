"""Configuration for Neo4j connections."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Neo4jSettings:
    """Neo4j connection settings loaded from environment variables."""

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "graphbased-ai"
    database: str = "neo4j"

    @classmethod
    def from_env(cls) -> "Neo4jSettings":
        return cls(
            uri=os.getenv("NEO4J_URI", cls.uri),
            username=os.getenv("NEO4J_USERNAME", cls.username),
            password=os.getenv("NEO4J_PASSWORD", cls.password),
            database=os.getenv("NEO4J_DATABASE", cls.database),
        )
