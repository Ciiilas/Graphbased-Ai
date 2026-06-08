"""Extract graph relations from Scala ASTs and symbols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tree_sitter import Node

from backend.extractor.models import ScalaRelation, ScalaSymbol


TYPE_KINDS: frozenset[str] = frozenset({"class", "object", "trait", "enum"})


@dataclass(frozen=True)
class RelationExtractor:
    """Build graph relations from parsed Scala files."""

    def extract(
        self,
        root_node: Node,
        source_bytes: bytes,
        source_path: str,
        symbols: list[ScalaSymbol],
        all_symbols: list[ScalaSymbol],
    ) -> list[ScalaRelation]:
        symbol_by_id: dict[str, ScalaSymbol] = {
            symbol.id: symbol for symbol in all_symbols
        }
        symbols_by_fqn: dict[str, ScalaSymbol] = {
            symbol.fqn: symbol
            for symbol in all_symbols
            if symbol.fqn is not None and symbol.kind != "import"
        }
        relations: list[ScalaRelation] = []
        relations.extend(self._declaration_relations(source_path, symbols))
        relations.extend(
            self._import_relations(
                source_path=source_path,
                symbols=symbols,
                all_symbols=all_symbols,
                symbols_by_fqn=symbols_by_fqn,
            )
        )
        relations.extend(
            self._extends_relations(
                root_node=root_node,
                source_bytes=source_bytes,
                symbols=symbols,
                symbols_by_fqn=symbols_by_fqn,
            )
        )
        relations.extend(
            self._call_relations(
                root_node=root_node,
                source_bytes=source_bytes,
                source_path=source_path,
                symbols=symbols,
                all_symbols=all_symbols,
            )
        )
        relations.extend(self._depends_on_relations(source_path, relations, symbol_by_id))
        return relations

    def _declaration_relations(
        self,
        source_path: str,
        symbols: list[ScalaSymbol],
    ) -> list[ScalaRelation]:
        relations: list[ScalaRelation] = []
        for symbol in symbols:
            if symbol.kind == "import":
                continue
            source_id: str = symbol.parent_id or source_path
            source_kind: str = "symbol" if symbol.parent_id is not None else "file"
            relations.append(
                ScalaRelation(
                    type="DECLARES",
                    source_id=source_id,
                    target_id=symbol.id,
                    source_path=source_path,
                    target_kind="symbol",
                    metadata={"source_kind": source_kind},
                )
            )
        return relations

    def _import_relations(
        self,
        source_path: str,
        symbols: list[ScalaSymbol],
        all_symbols: list[ScalaSymbol],
        symbols_by_fqn: dict[str, ScalaSymbol],
    ) -> list[ScalaRelation]:
        relations: list[ScalaRelation] = []
        type_symbols: list[ScalaSymbol] = [
            symbol
            for symbol in all_symbols
            if symbol.kind in TYPE_KINDS and symbol.fqn is not None
        ]
        for import_symbol in (symbol for symbol in symbols if symbol.kind == "import"):
            expanded_imports: list[str] = self._expand_import(
                import_symbol.name,
                type_symbols,
            )
            for fqn in expanded_imports:
                target: ScalaSymbol | None = symbols_by_fqn.get(fqn)
                if target is None:
                    relations.append(
                        self._external_relation(
                            relation_type="IMPORTS",
                            source_id=source_path,
                            source_path=source_path,
                            fqn=fqn,
                            metadata={"import_id": import_symbol.id},
                        )
                    )
                    continue

                relations.append(
                    ScalaRelation(
                        type="IMPORTS",
                        source_id=source_path,
                        target_id=target.id,
                        source_path=source_path,
                        target_kind="symbol",
                        metadata={"fqn": fqn, "import_id": import_symbol.id},
                    )
                )
        return relations

    def _extends_relations(
        self,
        root_node: Node,
        source_bytes: bytes,
        symbols: list[ScalaSymbol],
        symbols_by_fqn: dict[str, ScalaSymbol],
    ) -> list[ScalaRelation]:
        owner_symbols: dict[tuple[int, int], ScalaSymbol] = {
            (symbol.range.start_byte, symbol.range.end_byte): symbol
            for symbol in symbols
            if symbol.kind in TYPE_KINDS
        }
        package_name: str | None = next(
            (symbol.fqn for symbol in symbols if symbol.kind == "package"),
            None,
        )
        relations: list[ScalaRelation] = []
        for owner_node in self._nodes(root_node):
            if owner_node.type not in {
                "object_definition",
                "class_definition",
                "trait_definition",
                "enum_definition",
            }:
                continue
            owner_symbol: ScalaSymbol | None = owner_symbols.get(
                (owner_node.start_byte, owner_node.end_byte)
            )
            if owner_symbol is None:
                continue
            extends_clause: Node | None = owner_node.child_by_field_name("extend")
            if extends_clause is None:
                continue
            for target_name in self._extends_targets(extends_clause, source_bytes):
                target: ScalaSymbol | None = self._resolve_type(
                    target_name,
                    package_name,
                    symbols_by_fqn,
                )
                if target is None:
                    relations.append(
                        self._external_relation(
                            relation_type="EXTENDS",
                            source_id=owner_symbol.id,
                            source_path=owner_symbol.source_path,
                            fqn=target_name,
                            metadata={"target_name": target_name},
                        )
                    )
                else:
                    relations.append(
                        ScalaRelation(
                            type="EXTENDS",
                            source_id=owner_symbol.id,
                            target_id=target.id,
                            source_path=owner_symbol.source_path,
                            target_kind="symbol",
                            metadata={"target_name": target_name},
                        )
                    )
        return relations

    def _call_relations(
        self,
        root_node: Node,
        source_bytes: bytes,
        source_path: str,
        symbols: list[ScalaSymbol],
        all_symbols: list[ScalaSymbol],
    ) -> list[ScalaRelation]:
        function_by_range: dict[tuple[int, int], ScalaSymbol] = {
            (symbol.range.start_byte, symbol.range.end_byte): symbol
            for symbol in symbols
            if symbol.kind == "function"
        }
        function_symbols: list[ScalaSymbol] = [
            symbol for symbol in all_symbols if symbol.kind == "function"
        ]
        relations: list[ScalaRelation] = []
        for function_node in self._nodes(root_node):
            if function_node.type != "function_definition":
                continue
            caller: ScalaSymbol | None = function_by_range.get(
                (function_node.start_byte, function_node.end_byte)
            )
            if caller is None:
                continue
            for call_node in self._nodes(function_node):
                if call_node.type != "call_expression":
                    continue
                callee_name, receiver = self._call_target(call_node, source_bytes)
                if callee_name is None:
                    continue
                target: ScalaSymbol | None = self._resolve_call(
                    callee_name,
                    receiver,
                    caller,
                    function_symbols,
                )
                metadata: dict[str, Any] = {
                    "callee_name": callee_name,
                    "receiver": receiver,
                    "resolved": target is not None,
                }
                relations.append(
                    ScalaRelation(
                        type="CALLS",
                        source_id=caller.id,
                        target_id=target.id if target is not None else None,
                        source_path=source_path,
                        target_kind="symbol" if target is not None else "call",
                        metadata=metadata,
                    )
                )
        return relations

    def _depends_on_relations(
        self,
        source_path: str,
        relations: list[ScalaRelation],
        symbol_by_id: dict[str, ScalaSymbol],
    ) -> list[ScalaRelation]:
        target_paths: set[str] = set()
        for relation in relations:
            if relation.type not in {"IMPORTS", "CALLS"}:
                continue
            if relation.target_id is None:
                continue
            target_symbol: ScalaSymbol | None = symbol_by_id.get(relation.target_id)
            if target_symbol is None or target_symbol.source_path == source_path:
                continue
            target_paths.add(target_symbol.source_path)

        return [
            ScalaRelation(
                type="DEPENDS_ON",
                source_id=source_path,
                target_id=target_path,
                source_path=source_path,
                target_kind="file",
            )
            for target_path in sorted(target_paths)
        ]

    def _expand_import(
        self,
        import_name: str,
        type_symbols: list[ScalaSymbol],
    ) -> list[str]:
        cleaned_import: str = import_name.strip()
        if ".{" in cleaned_import and cleaned_import.endswith("}"):
            prefix, selectors = cleaned_import.split(".{", 1)
            selector_names: list[str] = [
                selector.strip()
                for selector in selectors.removesuffix("}").split(",")
                if selector.strip()
            ]
            return [f"{prefix}.{selector}" for selector in selector_names]

        wildcard_suffixes: tuple[str, ...] = ("._", ".*")
        for suffix in wildcard_suffixes:
            if cleaned_import.endswith(suffix):
                package_name: str = cleaned_import[: -len(suffix)]
                return sorted(
                    symbol.fqn
                    for symbol in type_symbols
                    if symbol.fqn is not None
                    and symbol.fqn.rsplit(".", 1)[0] == package_name
                )

        return [cleaned_import]

    def _extends_targets(self, extends_clause: Node, source_bytes: bytes) -> list[str]:
        targets: list[str] = []
        for child in extends_clause.children_by_field_name("type"):
            if not child.is_named:
                continue
            targets.append(self._base_type_name(child, source_bytes))
        return targets

    def _base_type_name(self, node: Node, source_bytes: bytes) -> str:
        """Return the bare supertype name, dropping type arguments.

        ``Command[gameInterface]`` (a ``generic_type``) resolves to ``Command``
        so a parametrized internal supertype is matched against the symbol index
        instead of being treated as an external import.
        """
        if node.type == "generic_type":
            for child in node.children:
                if child.type in {
                    "type_identifier",
                    "stable_type_identifier",
                    "generic_type",
                }:
                    return self._base_type_name(child, source_bytes)
        return self._node_text(node, source_bytes)

    def _resolve_type(
        self,
        target_name: str,
        package_name: str | None,
        symbols_by_fqn: dict[str, ScalaSymbol],
    ) -> ScalaSymbol | None:
        if target_name in symbols_by_fqn:
            return symbols_by_fqn[target_name]
        if package_name:
            package_target: str = f"{package_name}.{target_name}"
            if package_target in symbols_by_fqn:
                return symbols_by_fqn[package_target]

        matches: list[ScalaSymbol] = [
            symbol
            for fqn, symbol in symbols_by_fqn.items()
            if fqn.endswith(f".{target_name}") and symbol.kind in TYPE_KINDS
        ]
        return matches[0] if len(matches) == 1 else None

    def _call_target(
        self,
        call_node: Node,
        source_bytes: bytes,
    ) -> tuple[str | None, str | None]:
        function_node: Node | None = call_node.child_by_field_name("function")
        if function_node is None:
            return None, None
        if function_node.type == "identifier":
            return self._node_text(function_node, source_bytes), None
        if function_node.type == "field_expression":
            field_node: Node | None = function_node.child_by_field_name("field")
            value_node: Node | None = function_node.child_by_field_name("value")
            field_name: str | None = (
                self._node_text(field_node, source_bytes)
                if field_node is not None
                else None
            )
            receiver: str | None = (
                self._node_text(value_node, source_bytes)
                if value_node is not None
                else None
            )
            return field_name, receiver
        return self._node_text(function_node, source_bytes), None

    def _resolve_call(
        self,
        callee_name: str,
        receiver: str | None,
        caller: ScalaSymbol,
        function_symbols: list[ScalaSymbol],
    ) -> ScalaSymbol | None:
        candidates: list[ScalaSymbol] = [
            symbol for symbol in function_symbols if symbol.name == callee_name
        ]
        if not candidates:
            return None

        same_parent: list[ScalaSymbol] = [
            symbol for symbol in candidates if symbol.parent_id == caller.parent_id
        ]
        if len(same_parent) == 1:
            return same_parent[0]

        same_file: list[ScalaSymbol] = [
            symbol for symbol in candidates if symbol.source_path == caller.source_path
        ]
        if len(same_file) == 1:
            return same_file[0]

        if receiver is None and len(candidates) == 1:
            return candidates[0]
        return None

    def _external_relation(
        self,
        relation_type: str,
        source_id: str,
        source_path: str,
        fqn: str,
        metadata: dict[str, Any] | None = None,
    ) -> ScalaRelation:
        external_id: str = f"external:{fqn}"
        relation_metadata: dict[str, Any] = {
            "fqn": fqn,
            "library": fqn.split(".", 1)[0],
        }
        if metadata:
            relation_metadata.update(metadata)
        return ScalaRelation(
            type=relation_type,
            source_id=source_id,
            target_id=external_id,
            source_path=source_path,
            target_kind="external_import",
            metadata=relation_metadata,
        )

    def _nodes(self, node: Node) -> list[Node]:
        nodes: list[Node] = [node]
        for child in node.children:
            nodes.extend(self._nodes(child))
        return nodes

    def _node_text(self, node: Node, source_bytes: bytes) -> str:
        return source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        ).strip()
