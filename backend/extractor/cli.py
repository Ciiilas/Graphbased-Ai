"""CLI for extracting Scala AST and symbols."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from backend.extractor.ast_serializer import AstSerializer
from backend.extractor.models import ParsedFile
from backend.extractor.parser import ScalaTreeSitterParser
from backend.extractor.relations import RelationExtractor
from backend.extractor.scanner import ScalaFileScanner
from backend.extractor.symbols import SymbolExtractor


logger = logging.getLogger(__name__)


@dataclass
class ScalaExtractionCli:
    """Run Scala extraction from command-line arguments."""

    scanner: ScalaFileScanner
    parser: ScalaTreeSitterParser
    serializer: AstSerializer
    symbol_extractor: SymbolExtractor
    relation_extractor: RelationExtractor = field(default_factory=RelationExtractor)

    def run(self, source: Path, output: Path, overwrite: bool) -> int:
        source_root: Path = source.resolve()
        output_root: Path = output.resolve()
        files_root: Path = output_root / "files"

        self._prepare_output(output_root, overwrite)
        files_root.mkdir(parents=True, exist_ok=True)

        scala_files: list[Path] = self.scanner.find_scala_files(source_root)
        parsed_count: int = 0
        failed_files: list[dict[str, str]] = []
        symbols_by_path: dict[str, list] = {}
        all_symbols: list = []

        for scala_file in scala_files:
            relative_path: str = scala_file.relative_to(source_root).as_posix()
            try:
                source_bytes: bytes = scala_file.read_bytes()
                tree = self.parser.parse_bytes(source_bytes)
                symbols = self.symbol_extractor.extract(
                    tree.root_node,
                    source_bytes,
                    relative_path,
                )
                symbols_by_path[relative_path] = symbols
                all_symbols.extend(symbols)
            except Exception as error:
                logger.exception("Failed to parse Scala file: %s", relative_path)
                failed_files.append(
                    {
                        "relative_path": relative_path,
                        "error": str(error),
                    }
                )

        failed_paths: set[str] = {
            failed_file["relative_path"] for failed_file in failed_files
        }
        for scala_file in scala_files:
            relative_path = scala_file.relative_to(source_root).as_posix()
            if relative_path in failed_paths:
                continue

            output_file: Path = files_root / f"{relative_path}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            parsed_file = self._parse_file(
                scala_file=scala_file,
                relative_path=relative_path,
                symbols=symbols_by_path[relative_path],
                all_symbols=all_symbols,
            )
            self._write_json(output_file, parsed_file.to_dict())
            parsed_count += 1

        manifest: dict[str, Any] = {
            "source_root": str(source_root),
            "output_root": str(output_root),
            "generated_at": datetime.now(UTC).isoformat(),
            "total_files": len(scala_files),
            "parsed_files": parsed_count,
            "failed_files": failed_files,
            "has_errors": bool(failed_files),
            "packages": {
                "tree-sitter": self._package_version("tree-sitter"),
                "tree-sitter-scala": self._package_version("tree-sitter-scala"),
            },
        }
        self._write_json(output_root / "manifest.json", manifest)
        return 1 if failed_files else 0

    def _parse_file(
        self,
        scala_file: Path,
        relative_path: str,
        symbols: list,
        all_symbols: list,
    ) -> ParsedFile:
        source_bytes: bytes = scala_file.read_bytes()
        tree = self.parser.parse_bytes(source_bytes)
        ast = self.serializer.serialize(tree.root_node, source_bytes)
        relations = self.relation_extractor.extract(
            root_node=tree.root_node,
            source_bytes=source_bytes,
            source_path=relative_path,
            symbols=symbols,
            all_symbols=all_symbols,
        )
        return ParsedFile(
            relative_path=relative_path,
            absolute_path=scala_file.resolve(),
            has_errors=tree.root_node.has_error,
            ast=ast,
            symbols=symbols,
            relations=relations,
        )

    def _prepare_output(self, output_root: Path, overwrite: bool) -> None:
        if output_root.exists() and any(output_root.iterdir()) and not overwrite:
            raise FileExistsError(
                f"Output directory is not empty: {output_root}. Use --overwrite."
            )

        if overwrite:
            files_root: Path = output_root / "files"
            manifest_path: Path = output_root / "manifest.json"
            if files_root.exists():
                shutil.rmtree(files_root)
            if manifest_path.exists():
                manifest_path.unlink()

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _package_version(self, package_name: str) -> str | None:
        try:
            return version(package_name)
        except PackageNotFoundError:
            return None


def build_argument_parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Extract graph-ready AST JSON from Scala source files."
    )
    argument_parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Scala project root to scan.",
    )
    argument_parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Directory where JSON files will be written.",
    )
    argument_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow writing into a non-empty output directory.",
    )
    return argument_parser


def main() -> int:
    argument_parser: argparse.ArgumentParser = build_argument_parser()
    arguments: argparse.Namespace = argument_parser.parse_args()
    cli = ScalaExtractionCli(
        scanner=ScalaFileScanner(),
        parser=ScalaTreeSitterParser(),
        serializer=AstSerializer(),
        symbol_extractor=SymbolExtractor(),
        relation_extractor=RelationExtractor(),
    )
    return cli.run(
        source=arguments.source,
        output=arguments.output,
        overwrite=arguments.overwrite,
    )


if __name__ == "__main__":
    raise SystemExit(main())
