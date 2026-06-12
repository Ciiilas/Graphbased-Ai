from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.vector.chunks import CodeChunk, CodeChunkBuilder
from backend.vector.config import (
    ChromaSettings,
    GeminiEmbeddingSettings,
    GeminiGenerationSettings,
)
from backend.vector.importer import AstVectorImporter, VectorSearchService
from backend.vector.repository import ChromaVectorRepository, SearchResult


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.document_batches: list[list[str]] = []
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_batches.append(texts)
        return [[float(index), 1.0] for index, _text in enumerate(texts)]

    def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return [0.5, 1.0]


class FakeVectorRepository:
    def __init__(self) -> None:
        self.was_reset = False
        self.upserts: list[tuple[list[CodeChunk], list[list[float]]]] = []

    def reset_collection(self) -> None:
        self.was_reset = True

    def upsert_chunks(
        self,
        chunks: list[CodeChunk],
        embeddings: list[list[float]],
    ) -> None:
        self.upserts.append((chunks, embeddings))


class FakeSearchRepository:
    def __init__(self) -> None:
        self.query_embedding: list[float] | None = None
        self.limit: int | None = None

    def query(self, query_embedding: list[float], limit: int) -> list[SearchResult]:
        self.query_embedding = query_embedding
        self.limit = limit
        return [
            SearchResult(
                id="Sample.scala:function:main:0:10",
                text="def main(): Unit = println(\"hello\")",
                score=0.9,
                metadata={"relative_path": "Sample.scala"},
            )
        ]


class VectorSettingsTest(unittest.TestCase):
    def test_chroma_settings_from_env(self) -> None:
        environment = {
            "CHROMA_HOST": "example",
            "CHROMA_PORT": "9000",
            "CHROMA_COLLECTION": "code",
        }

        with patch.dict(os.environ, environment, clear=False):
            settings = ChromaSettings.from_env()

        self.assertEqual(settings.host, "example")
        self.assertEqual(settings.port, 9000)
        self.assertEqual(settings.collection, "code")

    def test_gemini_embedding_settings_from_env(self) -> None:
        environment = {
            "GEMINI_SECRET_KEY": "secret",
            "GEMINI_EMBEDDING_MODEL": "custom-model",
        }

        with patch.dict(os.environ, environment, clear=False):
            settings = GeminiEmbeddingSettings.from_env()

        self.assertEqual(settings.api_key, "secret")
        self.assertEqual(settings.model_name, "custom-model")

    def test_gemini_generation_settings_from_env(self) -> None:
        environment = {
            "GEMINI_SECRET_KEY": "secret",
            "GEMINI_GENERATION_MODEL": "gemini-3.5-flash",
        }

        with patch.dict(os.environ, environment, clear=False):
            settings = GeminiGenerationSettings.from_env()

        self.assertEqual(settings.api_key, "secret")
        self.assertEqual(settings.model_name, "gemini-3.5-flash")


class CodeChunkBuilderTest(unittest.TestCase):
    def test_builds_symbol_chunks_and_skips_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_file = root / "Sample.scala"
            source = (
                "package sample\n"
                "import scala.Option\n"
                "object Sample {\n"
                "  def main(): Unit = println(\"hello\")\n"
                "}\n"
            )
            source_file.write_text(source, encoding="utf-8")
            object_start = source.index("object Sample")
            object_end = len(source)
            function_start = source.index("def main")
            function_end = source.index("\n}", function_start)

            parsed_file = {
                "relative_path": "Sample.scala",
                "absolute_path": str(source_file),
                "symbols": [
                    self._symbol("import-1", "import", "scala.Option", 15, 34),
                    self._symbol(
                        "object-1",
                        "object",
                        "Sample",
                        object_start,
                        object_end,
                        fqn="sample.Sample",
                    ),
                    self._symbol(
                        "function-1",
                        "function",
                        "main",
                        function_start,
                        function_end,
                        fqn="sample.Sample.main",
                        parent_id="object-1",
                    ),
                ],
                "ast": {"range": {"start_byte": 0, "end_byte": len(source.encode())}},
            }

            chunks = CodeChunkBuilder().build_from_parsed_file(parsed_file)

        self.assertEqual([chunk.id for chunk in chunks], ["object-1", "function-1"])
        self.assertIn("object Sample", chunks[0].text)
        self.assertEqual(chunks[0].metadata["relative_path"], "Sample.scala")
        self.assertEqual(chunks[1].metadata["parent_id"], "object-1")

    def test_builds_file_fallback_when_no_indexable_symbols_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_file = Path(temporary_directory) / "package.scala"
            source_file.write_text("package sample\n", encoding="utf-8")
            parsed_file = {
                "relative_path": "package.scala",
                "absolute_path": str(source_file),
                "symbols": [
                    self._symbol("package-1", "package", "sample", 0, 14),
                ],
                "ast": {"range": {"start_byte": 0, "end_byte": 15}},
            }

            chunks = CodeChunkBuilder().build_from_parsed_file(parsed_file)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].id, "file:package.scala")
        self.assertEqual(chunks[0].metadata["kind"], "file")

    def _symbol(
        self,
        symbol_id: str,
        kind: str,
        name: str,
        start_byte: int,
        end_byte: int,
        fqn: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, object]:
        return {
            "id": symbol_id,
            "kind": kind,
            "name": name,
            "fqn": fqn,
            "parent_id": parent_id,
            "metadata": {},
            "range": {
                "start_byte": start_byte,
                "end_byte": end_byte,
                "start_point": {"row": 0, "column": start_byte},
                "end_point": {"row": 0, "column": end_byte},
            },
        }


class AstVectorImporterTest(unittest.TestCase):
    def test_import_directory_batches_embeddings_and_upserts_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ast_root = root / "ast"
            files_root = ast_root / "files"
            files_root.mkdir(parents=True)
            source_file = root / "Sample.scala"
            source_file.write_text("object Sample\n", encoding="utf-8")
            parsed_file = {
                "relative_path": "Sample.scala",
                "absolute_path": str(source_file),
                "symbols": [
                    {
                        "id": "object-1",
                        "kind": "object",
                        "name": "Sample",
                        "fqn": "Sample",
                        "parent_id": None,
                        "metadata": {},
                        "range": {
                            "start_byte": 0,
                            "end_byte": 13,
                            "start_point": {"row": 0, "column": 0},
                            "end_point": {"row": 0, "column": 13},
                        },
                    }
                ],
                "ast": {"range": {"start_byte": 0, "end_byte": 14}},
            }
            (files_root / "Sample.scala.json").write_text(
                json.dumps(parsed_file),
                encoding="utf-8",
            )
            repository = FakeVectorRepository()
            embedding_provider = FakeEmbeddingProvider()
            importer = AstVectorImporter(
                repository=repository,
                embedding_provider=embedding_provider,
                batch_size=1,
            )

            summary = importer.import_directory(ast_root, reset=True)

        self.assertTrue(repository.was_reset)
        self.assertEqual(summary.imported_files, 1)
        self.assertEqual(summary.total_chunks, 1)
        self.assertEqual(summary.imported_chunks, 1)
        self.assertFalse(summary.has_errors)
        self.assertEqual(len(embedding_provider.document_batches), 1)
        self.assertEqual(repository.upserts[0][0][0].id, "object-1")

    def test_import_directory_records_embedding_failures_per_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ast_root = root / "ast"
            files_root = ast_root / "files"
            files_root.mkdir(parents=True)
            source_file = root / "Sample.scala"
            source_file.write_text("object Sample\n", encoding="utf-8")
            parsed_file = {
                "relative_path": "Sample.scala",
                "absolute_path": str(source_file),
                "symbols": [
                    {
                        "id": "object-1",
                        "kind": "object",
                        "name": "Sample",
                        "fqn": "Sample",
                        "parent_id": None,
                        "metadata": {},
                        "range": {
                            "start_byte": 0,
                            "end_byte": 13,
                            "start_point": {"row": 0, "column": 0},
                            "end_point": {"row": 0, "column": 13},
                        },
                    }
                ],
                "ast": {"range": {"start_byte": 0, "end_byte": 14}},
            }
            (files_root / "Sample.scala.json").write_text(
                json.dumps(parsed_file),
                encoding="utf-8",
            )

            class FailingEmbeddingProvider:
                def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    raise RuntimeError("gemini unavailable")

                def embed_query(self, query: str) -> list[float]:
                    return [0.0]

            importer = AstVectorImporter(
                repository=FakeVectorRepository(),
                embedding_provider=FailingEmbeddingProvider(),
            )

            summary = importer.import_directory(ast_root)

        self.assertEqual(summary.imported_files, 1)
        self.assertEqual(summary.total_chunks, 1)
        self.assertEqual(summary.imported_chunks, 0)
        self.assertTrue(summary.has_errors)
        self.assertIn("Sample.scala", summary.failed_files[0]["path"])
        self.assertIn("gemini unavailable", summary.failed_files[0]["error"])

    def test_import_directory_reports_missing_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ast_root = Path(temporary_directory) / "ast"
            files_root = ast_root / "files"
            files_root.mkdir(parents=True)
            parsed_file = {
                "relative_path": "Missing.scala",
                "absolute_path": str(Path(temporary_directory) / "Missing.scala"),
                "symbols": [],
                "ast": {"range": {"start_byte": 0, "end_byte": 0}},
            }
            (files_root / "Missing.scala.json").write_text(
                json.dumps(parsed_file),
                encoding="utf-8",
            )
            importer = AstVectorImporter(
                repository=FakeVectorRepository(),
                embedding_provider=FakeEmbeddingProvider(),
            )

            summary = importer.import_directory(ast_root)

        self.assertTrue(summary.has_errors)
        self.assertEqual(summary.imported_files, 0)
        self.assertIn("Missing.scala", summary.failed_files[0]["path"])


class VectorSearchServiceTest(unittest.TestCase):
    def test_search_embeds_query_and_returns_result_dicts(self) -> None:
        repository = FakeSearchRepository()
        embedding_provider = FakeEmbeddingProvider()
        service = VectorSearchService(
            repository=repository,
            embedding_provider=embedding_provider,
        )

        results = service.search("main entry point", limit=3)

        self.assertEqual(embedding_provider.queries, ["main entry point"])
        self.assertEqual(repository.query_embedding, [0.5, 1.0])
        self.assertEqual(repository.limit, 3)
        self.assertEqual(results[0]["id"], "Sample.scala:function:main:0:10")


class ChromaVectorRepositoryTest(unittest.TestCase):
    def test_get_by_ids_converts_chroma_get_response(self) -> None:
        class FakeCollection:
            def __init__(self) -> None:
                self.ids: list[str] = []
                self.include: list[str] = []

            def get(self, ids: list[str], include: list[str]) -> dict[str, object]:
                self.ids = ids
                self.include = include
                return {
                    "ids": ["symbol-1"],
                    "documents": ["def run(): Unit = ()"],
                    "metadatas": [{"symbol_id": "symbol-1"}],
                }

        repository = object.__new__(ChromaVectorRepository)
        collection = FakeCollection()
        repository.collection = collection

        results = repository.get_by_ids(["symbol-1"])

        self.assertEqual(collection.ids, ["symbol-1"])
        self.assertEqual(collection.include, ["documents", "metadatas"])
        self.assertEqual(results[0].id, "symbol-1")
        self.assertEqual(results[0].text, "def run(): Unit = ()")
        self.assertIsNone(results[0].score)

    def test_get_by_ids_realigns_to_requested_order_and_drops_missing(self) -> None:
        class ShuffledCollection:
            def get(self, ids: list[str], include: list[str]) -> dict[str, object]:
                # Chroma may return rows in a different order and omit unknown
                # ids: requested [a, b, c], returns [c, a] (b unknown).
                return {
                    "ids": ["c", "a"],
                    "documents": ["code-c", "code-a"],
                    "metadatas": [{"symbol_id": "c"}, {"symbol_id": "a"}],
                }

        repository = object.__new__(ChromaVectorRepository)
        repository.collection = ShuffledCollection()

        results = repository.get_by_ids(["a", "b", "c"])

        self.assertEqual([result.id for result in results], ["a", "c"])
        self.assertEqual(results[0].text, "code-a")

    def test_get_by_ids_returns_empty_for_no_ids(self) -> None:
        repository = object.__new__(ChromaVectorRepository)
        self.assertEqual(repository.get_by_ids([]), [])


if __name__ == "__main__":
    unittest.main()
