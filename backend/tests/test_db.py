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

        self.assertEqual(len(connection.writes), 4)
        self.assertIn("File", connection.writes[0][0])
        self.assertIn("Symbol", connection.writes[1][0])
        self.assertIn("ExternalImport", connection.writes[2][0])
        self.assertIn("Call", connection.writes[3][0])

    def test_import_parsed_file_writes_symbols_and_relations(self) -> None:
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
                    "id": "src/main/scala/Sample.scala:object:Sample:0:13",
                    "fqn": "sample.Sample",
                    "parent_id": None,
                    "metadata": {},
                    "source_path": "C:/project/src/main/scala/Sample.scala",
                    "range": {
                        "start_byte": 0,
                        "end_byte": 13,
                    },
                }
            ],
            "relations": [
                {
                    "type": "DECLARES",
                    "source_id": "src/main/scala/Sample.scala",
                    "target_id": "src/main/scala/Sample.scala:object:Sample:0:13",
                    "source_path": "src/main/scala/Sample.scala",
                    "target_kind": "symbol",
                    "metadata": {},
                },
                {
                    "type": "IMPORTS",
                    "source_id": "src/main/scala/Sample.scala",
                    "target_id": "external:scala.Option",
                    "source_path": "src/main/scala/Sample.scala",
                    "target_kind": "external_import",
                    "metadata": {"fqn": "scala.Option", "library": "scala"},
                },
                {
                    "type": "CALLS",
                    "source_id": "src/main/scala/Sample.scala:function:main:20:40",
                    "target_id": None,
                    "source_path": "src/main/scala/Sample.scala",
                    "target_kind": "call",
                    "metadata": {
                        "callee_name": "println",
                        "receiver": None,
                        "resolved": False,
                    },
                },
                {
                    "type": "DEPENDS_ON",
                    "source_id": "src/main/scala/Sample.scala",
                    "target_id": "src/main/scala/Base.scala",
                    "source_path": "src/main/scala/Sample.scala",
                    "target_kind": "file",
                    "metadata": {},
                },
            ],
        }

        repository.import_parsed_file(parsed_file)

        self.assertEqual(len(connection.writes), 9)
        query, parameters = connection.writes[0]
        self.assertIn("MERGE (file:File", query)
        self.assertIn("UNWIND $symbols", query)
        self.assertIn("MERGE (node:Symbol", query)

        assert parameters is not None
        self.assertEqual(parameters["relative_path"], "src/main/scala/Sample.scala")
        self.assertEqual(len(parameters["symbols"]), 1)
        symbol_row = parameters["symbols"][0]
        self.assertEqual(symbol_row["kind"], "object")
        self.assertEqual(symbol_row["name"], "Sample")
        self.assertEqual(
            symbol_row["id"],
            "src/main/scala/Sample.scala:object:Sample:0:13",
        )
        self.assertIn("DECLARES", connection.writes[1][0])
        self.assertIn("ExternalImport", connection.writes[3][0])
        self.assertIn("Call", connection.writes[7][0])
        self.assertIn("DEPENDS_ON", connection.writes[8][0])

    def test_import_symbols_are_not_persisted_as_nodes(self) -> None:
        connection = FakeConnection()
        repository = Neo4jGraphRepository(connection)
        parsed_file = {
            "relative_path": "Sample.scala",
            "absolute_path": "C:/project/Sample.scala",
            "has_errors": False,
            "symbols": [
                {
                    "kind": "import",
                    "name": "scala.Option",
                    "id": "Sample.scala:import:scala.Option:0:18",
                    "fqn": "scala.Option",
                    "parent_id": None,
                    "metadata": {},
                    "source_path": "Sample.scala",
                    "range": {"start_byte": 0, "end_byte": 18},
                },
                {
                    "kind": "object",
                    "name": "Sample",
                    "id": "Sample.scala:object:Sample:20:33",
                    "fqn": "Sample",
                    "parent_id": None,
                    "metadata": {},
                    "source_path": "Sample.scala",
                    "range": {"start_byte": 20, "end_byte": 33},
                },
            ],
            "relations": [],
        }

        repository.import_parsed_file(parsed_file)

        _, parameters = connection.writes[0]
        assert parameters is not None
        written_kinds = [symbol["kind"] for symbol in parameters["symbols"]]
        self.assertEqual(written_kinds, ["object"])

    def test_import_parsed_file_without_symbols_writes_only_file(self) -> None:
        connection = FakeConnection()
        repository = Neo4jGraphRepository(connection)
        parsed_file = {
            "relative_path": "Empty.scala",
            "absolute_path": "C:/project/Empty.scala",
            "has_errors": False,
            "symbols": [],
            "relations": [],
        }

        repository.import_parsed_file(parsed_file)

        self.assertEqual(len(connection.writes), 9)
        _, parameters = connection.writes[0]
        assert parameters is not None
        self.assertEqual(parameters["symbols"], [])


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
