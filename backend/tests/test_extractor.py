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

    def test_extract_finds_enum_cases_with_fqn(self) -> None:
        source = "package sample\nenum Color:\n  case Red\n  case Green\n"
        parser = ScalaTreeSitterParser()
        source_bytes = source.encode("utf-8")
        tree = parser.parse_bytes(source_bytes)

        symbols = SymbolExtractor().extract(tree.root_node, source_bytes, "Color.scala")
        enum_cases = {
            symbol.name: symbol for symbol in symbols if symbol.kind == "enum_case"
        }
        enum_symbol = next(symbol for symbol in symbols if symbol.kind == "enum")

        self.assertEqual(set(enum_cases), {"Red", "Green"})
        self.assertEqual(enum_cases["Red"].fqn, "sample.Color.Red")
        self.assertEqual(enum_cases["Red"].parent_id, enum_symbol.id)

    def test_extract_finds_abstract_trait_members(self) -> None:
        source = "package sample\ntrait Repo:\n  def find(): Int\n  val name: String\n"
        parser = ScalaTreeSitterParser()
        source_bytes = source.encode("utf-8")
        tree = parser.parse_bytes(source_bytes)

        symbols = SymbolExtractor().extract(tree.root_node, source_bytes, "Repo.scala")
        symbol_pairs = {(symbol.kind, symbol.name) for symbol in symbols}

        self.assertIn(("function", "find"), symbol_pairs)
        self.assertIn(("val", "name"), symbol_pairs)


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

    def test_extends_generic_internal_type_resolves_to_symbol(self) -> None:
        parser = ScalaTreeSitterParser()
        symbol_extractor = SymbolExtractor()
        relation_extractor = RelationExtractor()
        base_source = "package sample\ntrait Command[A]\n"
        sample_source = (
            "package sample\n"
            "class SetCommand extends Command[Game]\n"
        )
        base_bytes = base_source.encode("utf-8")
        sample_bytes = sample_source.encode("utf-8")
        base_tree = parser.parse_bytes(base_bytes)
        sample_tree = parser.parse_bytes(sample_bytes)
        base_symbols = symbol_extractor.extract(base_tree.root_node, base_bytes, "Command.scala")
        sample_symbols = symbol_extractor.extract(sample_tree.root_node, sample_bytes, "SetCommand.scala")

        relations = relation_extractor.extract(
            root_node=sample_tree.root_node,
            source_bytes=sample_bytes,
            source_path="SetCommand.scala",
            symbols=sample_symbols,
            all_symbols=[*base_symbols, *sample_symbols],
        )
        command_symbol = next(symbol for symbol in base_symbols if symbol.kind == "trait")

        extends_relations = [relation for relation in relations if relation.type == "EXTENDS"]
        self.assertTrue(
            any(
                relation.target_kind == "symbol"
                and relation.target_id == command_symbol.id
                for relation in extends_relations
            )
        )
        self.assertFalse(
            any(relation.target_kind == "external_import" for relation in extends_relations)
        )

    def _extract_single_file(self, source: str, source_path: str):
        parser = ScalaTreeSitterParser()
        symbol_extractor = SymbolExtractor()
        relation_extractor = RelationExtractor()
        source_bytes = source.encode("utf-8")
        tree = parser.parse_bytes(source_bytes)
        symbols = symbol_extractor.extract(tree.root_node, source_bytes, source_path)
        relations = relation_extractor.extract(
            root_node=tree.root_node,
            source_bytes=source_bytes,
            source_path=source_path,
            symbols=symbols,
            all_symbols=symbols,
        )
        return symbols, relations

    def test_instantiates_resolves_internal_and_marks_external(self) -> None:
        source = (
            "package sample\n"
            "class Widget\n"
            "object App {\n"
            "  val w = new Widget\n"
            "  def make(): Unit = { val x = new Missing() }\n"
            "}\n"
        )
        symbols, relations = self._extract_single_file(source, "App.scala")
        widget_symbol = next(s for s in symbols if s.kind == "class" and s.name == "Widget")
        w_val = next(s for s in symbols if s.kind == "val" and s.name == "w")
        instantiates = [r for r in relations if r.type == "INSTANTIATES"]

        self.assertTrue(
            any(
                r.target_kind == "symbol"
                and r.target_id == widget_symbol.id
                and r.source_id == w_val.id
                for r in instantiates
            )
        )
        self.assertTrue(
            any(
                r.target_kind == "external_import" and r.metadata["type_name"] == "Missing"
                for r in instantiates
            )
        )

    def test_paren_free_call_resolves_and_is_flagged(self) -> None:
        source = (
            "package sample\n"
            "object Service {\n"
            "  def run(): Unit = {}\n"
            "}\n"
            "object Client {\n"
            "  def go(): Unit = {\n"
            "    Service.run\n"
            "    config.value\n"
            "  }\n"
            "}\n"
        )
        symbols, relations = self._extract_single_file(source, "Service.scala")
        run_symbol = next(s for s in symbols if s.kind == "function" and s.name == "run")
        calls = [r for r in relations if r.type == "CALLS"]

        self.assertTrue(
            any(
                r.metadata.get("paren_free") is True
                and r.target_kind == "symbol"
                and r.target_id == run_symbol.id
                for r in calls
            )
        )
        self.assertTrue(
            any(
                r.metadata.get("paren_free") is True
                and r.metadata["callee_name"] == "value"
                and r.target_id is None
                and r.target_kind == "call"
                for r in calls
            )
        )

    def test_call_in_val_initializer_is_attributed_to_enclosing_symbol(self) -> None:
        source = (
            "package sample\n"
            "object App {\n"
            "  val n = compute()\n"
            "  def compute(): Int = 0\n"
            "}\n"
        )
        symbols, relations = self._extract_single_file(source, "App.scala")
        n_val = next(s for s in symbols if s.kind == "val" and s.name == "n")
        compute_symbol = next(s for s in symbols if s.kind == "function" and s.name == "compute")

        self.assertTrue(
            any(
                r.type == "CALLS"
                and r.source_id == n_val.id
                and r.target_id == compute_symbol.id
                for r in relations
            )
        )

    def test_uses_links_signature_types_to_symbols(self) -> None:
        source = (
            "package sample\n"
            "trait Repo\n"
            "class Service(repo: Repo) {\n"
            "  def find(): Repo = ???\n"
            "}\n"
        )
        symbols, relations = self._extract_single_file(source, "Service.scala")
        repo_symbol = next(s for s in symbols if s.kind == "trait" and s.name == "Repo")
        service_symbol = next(s for s in symbols if s.kind == "class" and s.name == "Service")
        find_symbol = next(s for s in symbols if s.kind == "function" and s.name == "find")
        uses = [r for r in relations if r.type == "USES"]

        self.assertTrue(
            any(
                r.source_id == service_symbol.id and r.target_id == repo_symbol.id
                for r in uses
            )
        )
        self.assertTrue(
            any(
                r.source_id == find_symbol.id and r.target_id == repo_symbol.id
                for r in uses
            )
        )

    def test_call_resolves_via_receiver_field_type(self) -> None:
        source = (
            "package p\n"
            "trait Repo:\n"
            "  def find(): Int\n"
            "class Service(repo: Repo):\n"
            "  def run(): Int = repo.find()\n"
        )
        symbols, relations = self._extract_single_file(source, "Service.scala")
        find_symbol = next(s for s in symbols if s.name == "find")

        self.assertTrue(
            any(
                r.type == "CALLS"
                and r.metadata["callee_name"] == "find"
                and r.target_id == find_symbol.id
                for r in relations
            )
        )

    def test_call_resolves_inherited_method(self) -> None:
        source = (
            "package p\n"
            "trait Base:\n"
            "  def hello(): Unit\n"
            "class Impl extends Base:\n"
            "  def go(): Unit = hello()\n"
        )
        symbols, relations = self._extract_single_file(source, "Impl.scala")
        hello_symbol = next(s for s in symbols if s.name == "hello")

        self.assertTrue(
            any(
                r.type == "CALLS"
                and r.metadata["callee_name"] == "hello"
                and r.target_id == hello_symbol.id
                for r in relations
            )
        )

    def test_chained_receiver_call_resolves(self) -> None:
        source = (
            "package p\n"
            "trait B:\n"
            "  def c(): Int\n"
            "trait A:\n"
            "  def b: B\n"
            "class U(a: A):\n"
            "  def run(): Int = a.b.c()\n"
        )
        symbols, relations = self._extract_single_file(source, "U.scala")
        c_symbol = next(s for s in symbols if s.name == "c")

        self.assertTrue(
            any(
                r.type == "CALLS"
                and r.metadata["callee_name"] == "c"
                and r.target_id == c_symbol.id
                for r in relations
            )
        )

    def test_enum_case_reference_resolves(self) -> None:
        source = (
            "package p\n"
            "enum Color:\n"
            "  case Red\n"
            "object App:\n"
            "  def pick(): Color = Color.Red\n"
        )
        symbols, relations = self._extract_single_file(source, "App.scala")
        red_symbol = next(s for s in symbols if s.kind == "enum_case" and s.name == "Red")

        self.assertTrue(
            any(
                r.type == "CALLS"
                and r.metadata["callee_name"] == "Red"
                and r.target_id == red_symbol.id
                for r in relations
            )
        )

    def test_call_resolves_to_unique_implementation_member(self) -> None:
        source = (
            "package p\n"
            "trait Repo\n"
            "class SqlRepo extends Repo:\n"
            "  def find(): Int = 1\n"
            "class Service(repo: Repo):\n"
            "  def run(): Int = repo.find()\n"
        )
        symbols, relations = self._extract_single_file(source, "Service.scala")
        find_symbol = next(s for s in symbols if s.kind == "function" and s.name == "find")

        self.assertTrue(
            any(
                r.type == "CALLS"
                and r.metadata["callee_name"] == "find"
                and r.target_id == find_symbol.id
                for r in relations
            )
        )

    def test_unqualified_enum_case_reference_resolves_when_unique(self) -> None:
        source = (
            "package p\n"
            "enum Color:\n"
            "  case Red\n"
            "object App:\n"
            "  def pick(): Color = Red\n"
        )
        symbols, relations = self._extract_single_file(source, "App.scala")
        red_symbol = next(s for s in symbols if s.kind == "enum_case" and s.name == "Red")

        self.assertTrue(
            any(
                r.type == "CALLS"
                and r.metadata["callee_name"] == "Red"
                and r.target_id == red_symbol.id
                for r in relations
            )
        )

    def test_inject_annotation_constructor_params_are_used_as_fields(self) -> None:
        source = (
            "package p\n"
            "class Inject\n"
            "trait GameApi:\n"
            "  def current(): Int\n"
            "class Controller @Inject() (var game: GameApi):\n"
            "  def run(): Int = game.current()\n"
        )
        symbols, relations = self._extract_single_file(source, "Controller.scala")
        current_symbol = next(
            s for s in symbols if s.kind == "function" and s.name == "current"
        )

        self.assertTrue(
            any(
                r.type == "CALLS"
                and r.metadata["callee_name"] == "current"
                and r.target_id == current_symbol.id
                for r in relations
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
