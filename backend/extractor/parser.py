"""Tree-sitter parser wrapper for Scala source code."""

from __future__ import annotations

from dataclasses import dataclass

import tree_sitter_scala
from tree_sitter import Language, Parser, Tree


@dataclass
class ScalaTreeSitterParser:
    """Small wrapper that owns the configured Scala parser."""

    parser: Parser | None = None

    def __post_init__(self) -> None:
        if self.parser is None:
            scala_language: Language = Language(tree_sitter_scala.language())
            self.parser = Parser(scala_language)

    def parse_source(self, source: str) -> Tree:
        source_bytes: bytes = source.encode("utf-8")
        return self.parse_bytes(source_bytes)

    def parse_bytes(self, source_bytes: bytes) -> Tree:
        if self.parser is None:
            raise RuntimeError("Scala parser is not initialized.")

        tree: Tree | None = self.parser.parse(source_bytes)
        if tree is None:
            raise RuntimeError("Tree-sitter failed to parse Scala source.")
        return tree
