"""Extract Scala symbols from Tree-sitter ASTs."""

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
    "val_definition": "val",
    "var_definition": "var",
    "type_definition": "type",
    "given_definition": "given",
}

OWNER_KINDS: frozenset[str] = frozenset({"object", "class", "trait", "enum"})


@dataclass(frozen=True)
class SymbolExtractor:
    """Extract graph-relevant symbols with stable ids and FQNs."""

    def extract(
        self,
        root_node: Node,
        source_bytes: bytes,
        source_path: str,
    ) -> list[ScalaSymbol]:
        package_name: str | None = self._package_name(root_node, source_bytes)
        symbols: list[ScalaSymbol] = []
        package_symbol: ScalaSymbol | None = self._package_symbol(
            root_node,
            source_bytes,
            source_path,
            package_name,
        )
        if package_symbol is not None:
            symbols.append(package_symbol)

        self._visit(
            node=root_node,
            source_bytes=source_bytes,
            source_path=source_path,
            package_name=package_name,
            owner_stack=[],
            symbols=symbols,
        )
        return symbols

    def _visit(
        self,
        node: Node,
        source_bytes: bytes,
        source_path: str,
        package_name: str | None,
        owner_stack: list[ScalaSymbol],
        symbols: list[ScalaSymbol],
    ) -> None:
        kind: str | None = SYMBOL_NODE_TYPES.get(node.type)
        current_owner_stack: list[ScalaSymbol] = owner_stack

        if kind is not None:
            name: str | None = self._symbol_name(node, source_bytes, kind)
            if name:
                parent_id: str | None = owner_stack[-1].id if owner_stack else None
                fqn: str | None = self._fqn(package_name, owner_stack, name, kind)
                metadata: dict[str, Any] = self._metadata(node, source_bytes, kind)
                symbol = ScalaSymbol(
                    id=self._symbol_id(source_path, kind, name, self._source_range(node)),
                    kind=kind,
                    name=name,
                    range=self._source_range(node),
                    source_path=source_path,
                    fqn=fqn,
                    parent_id=parent_id,
                    metadata=metadata,
                )
                symbols.append(symbol)
                if kind in OWNER_KINDS:
                    current_owner_stack = [*owner_stack, symbol]

        for child in node.children:
            self._visit(
                node=child,
                source_bytes=source_bytes,
                source_path=source_path,
                package_name=package_name,
                owner_stack=current_owner_stack,
                symbols=symbols,
            )

    def _package_symbol(
        self,
        root_node: Node,
        source_bytes: bytes,
        source_path: str,
        package_name: str | None,
    ) -> ScalaSymbol | None:
        if package_name is None:
            return None

        first_clause: Node | None = next(
            (child for child in root_node.children if child.type == "package_clause"),
            None,
        )
        if first_clause is None:
            return None

        source_range: SourceRange = self._source_range(first_clause)
        return ScalaSymbol(
            id=self._symbol_id(source_path, "package", package_name, source_range),
            kind="package",
            name=package_name,
            range=source_range,
            source_path=source_path,
            fqn=package_name,
        )

    def _package_name(self, root_node: Node, source_bytes: bytes) -> str | None:
        package_parts: list[str] = []
        for child in root_node.children:
            if child.type != "package_clause":
                continue
            part: str | None = self._package_clause_name(child, source_bytes)
            if part:
                package_parts.append(part)
        if not package_parts:
            return None
        return ".".join(package_parts)

    def _package_clause_name(self, node: Node, source_bytes: bytes) -> str | None:
        package_name: Node | None = node.child_by_field_name("name")
        if package_name is not None:
            return self._node_text(package_name, source_bytes)
        return self._node_text(node, source_bytes).removeprefix("package").strip()

    def _symbol_name(self, node: Node, source_bytes: bytes, kind: str) -> str | None:
        if kind == "import":
            return self._node_text(node, source_bytes).removeprefix("import").strip()

        field_names: tuple[str, ...] = ("name", "pattern")
        for field_name in field_names:
            named_child: Node | None = node.child_by_field_name(field_name)
            if named_child is not None:
                return self._node_text(named_child, source_bytes)

        identifier: Node | None = self._first_identifier(node)
        if identifier is not None:
            return self._node_text(identifier, source_bytes)
        return None

    def _first_identifier(self, node: Node) -> Node | None:
        if node.type in {"identifier", "type_identifier"}:
            return node

        for child in node.children:
            identifier: Node | None = self._first_identifier(child)
            if identifier is not None:
                return identifier
        return None

    def _fqn(
        self,
        package_name: str | None,
        owner_stack: list[ScalaSymbol],
        name: str,
        kind: str,
    ) -> str | None:
        if kind == "import":
            return name

        parts: list[str] = []
        if package_name:
            parts.append(package_name)
        parts.extend(owner.name for owner in owner_stack if owner.kind in OWNER_KINDS)
        parts.append(name)
        return ".".join(parts) if parts else name

    def _metadata(self, node: Node, source_bytes: bytes, kind: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if kind == "function":
            return_type: Node | None = node.child_by_field_name("return_type")
            parameters: Node | None = node.child_by_field_name("parameters")
            if return_type is not None:
                metadata["return_type"] = self._node_text(return_type, source_bytes)
            if parameters is not None:
                metadata["parameters"] = self._node_text(parameters, source_bytes)
        if kind in {"val", "var", "type", "given"}:
            symbol_type: Node | None = node.child_by_field_name("type")
            if symbol_type is not None:
                metadata["type"] = self._node_text(symbol_type, source_bytes)
        return metadata

    def _symbol_id(
        self,
        source_path: str,
        kind: str,
        name: str,
        source_range: SourceRange,
    ) -> str:
        return (
            f"{source_path}:{kind}:{name}:"
            f"{source_range.start_byte}:{source_range.end_byte}"
        )

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
