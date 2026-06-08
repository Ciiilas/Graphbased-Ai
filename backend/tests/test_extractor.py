from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.extractor.ast_serializer import AstSerializer
from backend.extractor.cli import ScalaExtractionCli
from backend.extractor.parser import ScalaTreeSitterParser
from backend.extractor.relations import RelationExtractor
from backend.extractor.scanner import ScalaFileScanner
from backend.extractor.symbols import SymbolExtractor


SCALA_SOURCE = """
package de.htwg.se.muehle

import scala.collection.mutable.ListBuffer

object Sample {
  def main(args: Array[String]): Unit = {
    println("hello")
  }
}
"""


class ScalaTreeSitterParserTest(unittest.TestCase):
    def test_parse_source_returns_tree_without_errors(self) -> None:
        parser = ScalaTreeSitterParser()

        tree = parser.parse_source(SCALA_SOURCE)

        self.assertFalse(tree.root_node.has_error)
        self.assertGreater(tree.root_node.child_count, 0)


class ScalaFileScannerTest(unittest.TestCase):
    def test_find_scala_files_ignores_build_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            expected_file = root / "src" / "main" / "scala" / "Sample.scala"
            ignored_file = root / "target" / "Ignored.scala"
            expected_file.parent.mkdir(parents=True)
            ignored_file.parent.mkdir(parents=True)
            expected_file.write_text("object Sample", encoding="utf-8")
            ignored_file.write_text("object Ignored", encoding="utf-8")

            scanner = ScalaFileScanner()
            scala_files = scanner.find_scala_files(root)

            self.assertEqual(scala_files, [expected_file])


class AstSerializerTest(unittest.TestCase):
    def test_serialize_includes_children_and_positions(self) -> None:
        parser = ScalaTreeSitterParser()
        source_bytes = SCALA_SOURCE.encode("utf-8")
        tree = parser.parse_bytes(source_bytes)

        ast = AstSerializer().serialize(tree.root_node, source_bytes)
        data = ast.to_dict()

        self.assertIn("type", data)
        self.assertIn("range", data)
        self.assertIn("start_point", data["range"])
        self.assertIn("end_point", data["range"])
        self.assertGreater(len(data["children"]), 0)


class SymbolExtractorTest(unittest.TestCase):
    def test_extract_finds_basic_symbols(self) -> None:
        parser = ScalaTreeSitterParser()
        source_bytes = SCALA_SOURCE.encode("utf-8")
        tree = parser.parse_bytes(source_bytes)

        symbols = SymbolExtractor().extract(
            tree.root_node,
            source_bytes,
            "Sample.scala",
        )
        symbol_pairs = {(symbol.kind, symbol.name) for symbol in symbols}

        self.assertIn(("object", "Sample"), symbol_pairs)
        self.assertIn(("function", "main"), symbol_pairs)
        self.assertIn(("package", "de.htwg.se.muehle"), symbol_pairs)
        self.assertTrue(any(symbol.kind == "import" for symbol in symbols))

        object_symbol = next(symbol for symbol in symbols if symbol.kind == "object")
        function_symbol = next(symbol for symbol in symbols if symbol.kind == "function")
        self.assertEqual(object_symbol.fqn, "de.htwg.se.muehle.Sample")
        self.assertEqual(function_symbol.fqn, "de.htwg.se.muehle.Sample.main")
        self.assertEqual(function_symbol.parent_id, object_symbol.id)

    def test_extract_merges_chained_packages_and_finds_enum(self) -> None:
        source = (
            "package de.htwg.se\n"
            "package muehle\n"
            "package util\n"
            "\n"
            "enum Event:\n"
            "  case Set\n"
            "  case GameOver\n"
        )
        parser = ScalaTreeSitterParser()
        source_bytes = source.encode("utf-8")
        tree = parser.parse_bytes(source_bytes)

        symbols = SymbolExtractor().extract(
            tree.root_node,
            source_bytes,
            "Event.scala",
        )
        symbol_pairs = {(symbol.kind, symbol.name) for symbol in symbols}

        self.assertIn(("package", "de.htwg.se.muehle.util"), symbol_pairs)
        self.assertIn(("enum", "Event"), symbol_pairs)
        package_symbols = [symbol for symbol in symbols if symbol.kind == "package"]
        self.assertEqual(len(package_symbols), 1)

    def test_extract_finds_field_type_and_given_symbols(self) -> None:
        source = (
            "package sample\n"
            "object Config {\n"
            "  val answer: Int = 42\n"
            "  var enabled = true\n"
            "  type Name = String\n"
            "  given ordering: Ordering[String] = null\n"
            "}\n"
        )
        parser = ScalaTreeSitterParser()
        source_bytes = source.encode("utf-8")
        tree = parser.parse_bytes(source_bytes)

        symbols = SymbolExtractor().extract(
            tree.root_node,
            source_bytes,
            "Config.scala",
        )
        symbol_pairs = {(symbol.kind, symbol.name) for symbol in symbols}

        self.assertIn(("val", "answer"), symbol_pairs)
        self.assertIn(("var", "enabled"), symbol_pairs)
        self.assertIn(("type", "Name"), symbol_pairs)
        self.assertIn(("given", "ordering"), symbol_pairs)


class RelationExtractorTest(unittest.TestCase):
    def test_extracts_import_extends_calls_and_depends_on(self) -> None:
        parser = ScalaTreeSitterParser()
        symbol_extractor = SymbolExtractor()
        relation_extractor = RelationExtractor()
        base_source = "package sample\ntrait Base\n"
        sample_source = (
            "package sample\n"
            "import sample.Base\n"
            "import scala.collection.mutable.ListBuffer\n"
            "object Sample extends Base {\n"
            "  def main(): Unit = {\n"
            "    helper()\n"
            "    println(\"hello\")\n"
            "  }\n"
            "  def helper(): Unit = {}\n"
            "}\n"
        )
        base_bytes = base_source.encode("utf-8")
        sample_bytes = sample_source.encode("utf-8")
        base_tree = parser.parse_bytes(base_bytes)
        sample_tree = parser.parse_bytes(sample_bytes)
        base_symbols = symbol_extractor.extract(
            base_tree.root_node,
            base_bytes,
            "Base.scala",
        )
        sample_symbols = symbol_extractor.extract(
            sample_tree.root_node,
            sample_bytes,
            "Sample.scala",
        )

        relations = relation_extractor.extract(
            root_node=sample_tree.root_node,
            source_bytes=sample_bytes,
            source_path="Sample.scala",
            symbols=sample_symbols,
            all_symbols=[*base_symbols, *sample_symbols],
        )
        relation_types = {relation.type for relation in relations}
        base_symbol = next(symbol for symbol in base_symbols if symbol.kind == "trait")
        object_symbol = next(symbol for symbol in sample_symbols if symbol.kind == "object")
        main_symbol = next(
            symbol for symbol in sample_symbols if symbol.kind == "function" and symbol.name == "main"
        )
        helper_symbol = next(
            symbol for symbol in sample_symbols if symbol.kind == "function" and symbol.name == "helper"
        )

        self.assertIn("DECLARES", relation_types)
        self.assertIn("IMPORTS", relation_types)
        self.assertIn("EXTENDS", relation_types)
        self.assertIn("CALLS", relation_types)
        self.assertIn("DEPENDS_ON", relation_types)
        self.assertTrue(
            any(
                relation.type == "DECLARES"
                and relation.source_id == object_symbol.id
                and relation.target_id == main_symbol.id
                for relation in relations
            )
        )
        self.assertTrue(
            any(
                relation.type == "IMPORTS" and relation.target_id == base_symbol.id
                for relation in relations
            )
        )
        self.assertTrue(
            any(
                relation.type == "EXTENDS" and relation.target_id == base_symbol.id
                for relation in relations
            )
        )
        self.assertTrue(
            any(
                relation.type == "CALLS"
                and relation.source_id == main_symbol.id
                and relation.target_id == helper_symbol.id
                for relation in relations
            )
        )
        self.assertTrue(
            any(
                relation.type == "CALLS"
                and relation.target_id is None
                and relation.metadata["callee_name"] == "println"
                for relation in relations
            )
        )
        self.assertTrue(
            any(
                relation.type == "DEPENDS_ON" and relation.target_id == "Base.scala"
                for relation in relations
            )
        )
        self.assertTrue(
            any(
                relation.type == "IMPORTS"
                and relation.target_kind == "external_import"
                and relation.metadata["fqn"] == "scala.collection.mutable.ListBuffer"
                for relation in relations
            )
        )


class ScalaExtractionCliTest(unittest.TestCase):
    def test_cli_writes_manifest_and_file_json(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        source_root = repository_root / "testproject" / "Muehle"
        if not source_root.exists():
            self.skipTest("Scala test project is not available.")

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory) / "ast"
            cli = ScalaExtractionCli(
                scanner=ScalaFileScanner(),
                parser=ScalaTreeSitterParser(),
                serializer=AstSerializer(),
                symbol_extractor=SymbolExtractor(),
            )

            exit_code = cli.run(source=source_root, output=output_root, overwrite=True)

            manifest_path = output_root / "manifest.json"
            self.assertEqual(exit_code, 0)
            self.assertTrue(manifest_path.exists())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertGreater(manifest["total_files"], 0)
            self.assertEqual(manifest["parsed_files"], manifest["total_files"])
            self.assertTrue(any((output_root / "files").rglob("*.json")))


if __name__ == "__main__":
    unittest.main()
