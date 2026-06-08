from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.db.config import Neo4jSettings
from backend.db.importer import AstJsonImporter
from backend.db.repository import Neo4jGraphRepository


class FakeConnection:
    def __init__(self) -> None:
        self.writes: list[tuple[str, dict[str, object] | None]] = []

    def execute_write(
        self,
        query: str,
        parameters: dict[str, object] | None = None,
    ) -> None:
        self.writes.append((query, parameters))


class FakeRepository:
    def __init__(self) -> None:
        self.files: list[dict[str, object]] = []

    def import_parsed_file(self, parsed_file: dict[str, object]) -> None:
        self.files.append(parsed_file)


class Neo4jSettingsTest(unittest.TestCase):
    def test_from_env_reads_neo4j_settings(self) -> None:
        environment = {
            "NEO4J_URI": "bolt://example:7687",
            "NEO4J_USERNAME": "user",
            "NEO4J_PASSWORD": "secret",
            "NEO4J_DATABASE": "graph",
        }

        with patch.dict(os.environ, environment, clear=False):
            settings = Neo4jSettings.from_env()

        self.assertEqual(settings.uri, "bolt://example:7687")
        self.assertEqual(settings.username, "user")
        self.assertEqual(settings.password, "secret")
        self.assertEqual(settings.database, "graph")


class Neo4jGraphRepositoryTest(unittest.TestCase):
    def test_create_constraints_writes_file_and_symbol_constraints(self) -> None:
        connection = FakeConnection()
        repository = Neo4jGraphRepository(connection)

        repository.create_constraints()

        self.assertEqual(len(connection.writes), 2)
        self.assertIn("File", connection.writes[0][0])
        self.assertIn("Symbol", connection.writes[1][0])

    def test_import_parsed_file_writes_file_symbol_and_relation(self) -> None:
        connection = FakeConnection()
        repository = Neo4jGraphRepository(connection)
        parsed_file = {
            "relative_path": "src/main/scala/Sample.scala",
            "absolute_path": "C:/project/src/main/scala/Sample.scala",
            "has_errors": False,
            "symbols": [
                {
                    "kind": "object",
                    "name": "Sample",
                    "source_path": "C:/project/src/main/scala/Sample.scala",
                    "range": {
                        "start_byte": 0,
                        "end_byte": 13,
                    },
                }
            ],
        }

        repository.import_parsed_file(parsed_file)

        self.assertEqual(len(connection.writes), 3)
        self.assertIn("MERGE (file:File", connection.writes[0][0])
        self.assertIn("MERGE (symbol:Symbol", connection.writes[1][0])
        self.assertIn("DECLARES", connection.writes[2][0])


class AstJsonImporterTest(unittest.TestCase):
    def test_import_directory_imports_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ast_root = Path(temporary_directory)
            files_root = ast_root / "files"
            files_root.mkdir()
            parsed_file = {
                "relative_path": "Sample.scala",
                "absolute_path": "C:/project/Sample.scala",
                "has_errors": False,
                "symbols": [],
            }
            (files_root / "Sample.scala.json").write_text(
                json.dumps(parsed_file),
                encoding="utf-8",
            )
            repository = FakeRepository()
            importer = AstJsonImporter(repository)

            summary = importer.import_directory(ast_root)

            self.assertFalse(summary.has_errors)
            self.assertEqual(summary.total_files, 1)
            self.assertEqual(summary.imported_files, 1)
            self.assertEqual(repository.files, [parsed_file])


if __name__ == "__main__":
    unittest.main()
