"""Extract basic Scala symbols from Tree-sitter ASTs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tree_sitter import Node

from backend.extractor.models import ScalaSymbol, SourcePoint, SourceRange


SYMBOL_NODE_TYPES: dict[str, str] = {
    "import_declaration": "import",
    "object_definition": "object",
    "class_definition": "class",
    "trait_definition": "trait",
    "enum_definition": "enum",
    "function_definition": "function",
}


@dataclass(frozen=True)
class SymbolExtractor:
    """Extract first graph-relevant symbols from a Scala AST."""

    def extract(
        self,
        root_node: Node,
        source_bytes: bytes,
        source_path: str,
    ) -> list[ScalaSymbol]:
        """Extract symbols. ``source_path`` should be the file's relative POSIX
        path so symbol ``source_path`` matches the graph's ``File.path``."""
        symbols: list[ScalaSymbol] = []
        package_symbol: ScalaSymbol | None = self._extract_package(
            root_node,
            source_bytes,
            source_path,
        )
        if package_symbol is not None:
            symbols.append(package_symbol)
        self._visit(root_node, source_bytes, source_path, symbols)
        return symbols

    def _extract_package(
        self,
        root_node: Node,
        source_bytes: bytes,
        source_path: str,
    ) -> ScalaSymbol | None:
        """Merge consecutive top-level ``package`` clauses into one symbol.

        Scala allows a chained package header such as
        ``package de.htwg.se`` / ``package muehle`` / ``package util``. Each
        clause is its own AST node, so they are joined into a single dotted
        package name to reflect the file's actual package.
        """
        package_parts: list[str] = []
        first_clause: Node | None = None
        for child in root_node.children:
            if child.type != "package_clause":
                continue
            part: str | None = self._package_clause_name(child, source_bytes)
            if part:
                package_parts.append(part)
                if first_clause is None:
                    first_clause = child

        if not package_parts or first_clause is None:
            return None

        return ScalaSymbol(
            kind="package",
            name=".".join(package_parts),
            range=self._source_range(first_clause),
            source_path=source_path,
        )

    def _package_clause_name(self, node: Node, source_bytes: bytes) -> str | None:
        package_name: Node | None = node.child_by_field_name("name")
        if package_name is not None:
            return self._node_text(package_name, source_bytes)
        return self._node_text(node, source_bytes).removeprefix("package").strip()

    def _visit(
        self,
        node: Node,
        source_bytes: bytes,
        source_path: str,
        symbols: list[ScalaSymbol],
    ) -> None:
        kind: str | None = SYMBOL_NODE_TYPES.get(node.type)
        if kind is not None:
            name: str | None = self._symbol_name(node, source_bytes, kind)
            if name:
                symbols.append(
                    ScalaSymbol(
                        kind=kind,
                        name=name,
                        range=self._source_range(node),
                        source_path=source_path,
                    )
                )

        for child in node.children:
            self._visit(child, source_bytes, source_path, symbols)

    def _symbol_name(self, node: Node, source_bytes: bytes, kind: str) -> str | None:
        if kind == "import":
            return self._node_text(node, source_bytes).removeprefix("import").strip()

        named_child: Node | None = node.child_by_field_name("name")
        if named_child is not None:
            return self._node_text(named_child, source_bytes)

        identifier: Node | None = self._first_identifier(node)
        if identifier is not None:
            return self._node_text(identifier, source_bytes)
        return None

    def _first_identifier(self, node: Node) -> Node | None:
        if node.type == "identifier":
            return node

        for child in node.children:
            identifier: Node | None = self._first_identifier(child)
            if identifier is not None:
                return identifier
        return None

    def _node_text(self, node: Node, source_bytes: bytes) -> str:
        return source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        ).strip()

    def _source_range(self, node: Node) -> SourceRange:
        start_point: Any = node.start_point
        end_point: Any = node.end_point
        return SourceRange(
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_point=SourcePoint(row=start_point[0], column=start_point[1]),
            end_point=SourcePoint(row=end_point[0], column=end_point[1]),
        )
