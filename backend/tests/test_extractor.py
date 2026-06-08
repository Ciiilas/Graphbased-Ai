from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.extractor.ast_serializer import AstSerializer
from backend.extractor.cli import ScalaExtractionCli
from backend.extractor.parser import ScalaTreeSitterParser
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
