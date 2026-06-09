"""Extract graph relations from Scala ASTs and symbols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tree_sitter import Node

from backend.extractor.models import ScalaRelation, ScalaSymbol


TYPE_KINDS: frozenset[str] = frozenset({"class", "object", "trait", "enum"})

# Symbols whose source range can enclose a call/instantiation. The nearest
# (smallest) enclosing symbol becomes the relation source, so a call in a
# ``val`` initializer or class body is attributed to that ``val``/class instead
# of being dropped, and a call in a nested function is counted only once.
CONTAINER_KINDS: frozenset[str] = frozenset(
    {"function", "val", "var", "given", "class", "object", "trait", "enum"}
)

# Symbols that carry a signature whose type references become USES relations.
USES_SOURCE_KINDS: frozenset[str] = frozenset(
    {"function", "class", "trait", "val", "var", "given", "type"}
)

# Fields of a definition node that are not part of its type signature: the
# declared name, the body/initializer, and the supertype list (covered by
# EXTENDS). ``type_parameters`` is skipped separately by node type.
NON_SIGNATURE_FIELDS: frozenset[str] = frozenset(
    {"name", "pattern", "body", "extend", "value"}
)

# Member kinds that a call can resolve to: methods and enum cases (``Event.Set``).
CALLABLE_KINDS: frozenset[str] = frozenset({"function", "enum_case"})


@dataclass(frozen=True)
class ResolutionContext:
    """Pre-built indexes for resolving calls against types and the type hierarchy."""

    symbols_by_fqn: dict[str, ScalaSymbol]
    simple_types: dict[str, list[ScalaSymbol]]
    members_by_parent: dict[str, list[ScalaSymbol]]
    supertypes_by_id: dict[str, list[str]]
    import_simple: dict[str, str]
    import_wildcards: list[str]
    package_name: str | None
    func_params: dict[str, dict[str, str]]
    field_types: dict[str, dict[str, str]]
    function_symbols: list[ScalaSymbol]


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
        package_name: str | None = next(
            (symbol.fqn for symbol in symbols if symbol.kind == "package"),
            None,
        )
        containers: list[tuple[int, int, ScalaSymbol]] = self._containers(symbols)
        context: ResolutionContext = self._build_context(
            root_node=root_node,
            source_bytes=source_bytes,
            symbols=symbols,
            all_symbols=all_symbols,
            symbols_by_fqn=symbols_by_fqn,
            package_name=package_name,
        )
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
                containers=containers,
                context=context,
            )
        )
        relations.extend(
            self._instantiation_relations(
                root_node=root_node,
                source_bytes=source_bytes,
                source_path=source_path,
                containers=containers,
                package_name=package_name,
                symbols_by_fqn=symbols_by_fqn,
            )
        )
        relations.extend(
            self._uses_relations(
                root_node=root_node,
                source_bytes=source_bytes,
                symbols=symbols,
                package_name=package_name,
                symbols_by_fqn=symbols_by_fqn,
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
        containers: list[tuple[int, int, ScalaSymbol]],
        context: ResolutionContext,
    ) -> list[ScalaRelation]:
        nodes: list[Node] = self._nodes(root_node)
        call_nodes: list[Node] = [
            node for node in nodes if node.type == "call_expression"
        ]
        # ``field_expression`` nodes that are the callable of a parenthesized
        # call are handled below as that call, not as a separate paren-less call.
        called_function_ids: set[int] = set()
        for call_node in call_nodes:
            function_node: Node | None = call_node.child_by_field_name("function")
            if function_node is not None:
                called_function_ids.add(function_node.id)

        relations: list[ScalaRelation] = []
        for call_node in call_nodes:
            owner: ScalaSymbol | None = self._enclosing_symbol(call_node, containers)
            if owner is None:
                continue
            callee_name, receiver = self._call_target(call_node, source_bytes)
            if callee_name is None:
                continue
            function_node = call_node.child_by_field_name("function")
            receiver_node: Node | None = (
                function_node.child_by_field_name("value")
                if function_node is not None
                and function_node.type == "field_expression"
                else None
            )
            relations.append(
                self._call_relation(
                    owner=owner,
                    target=self._resolve_call_node(
                        call_node, callee_name, receiver_node, containers, context, source_bytes
                    ),
                    source_path=source_path,
                    callee_name=callee_name,
                    receiver=receiver,
                    paren_free=False,
                )
            )

        # Paren-less method calls (``a.method``) are ``field_expression`` nodes.
        # They are syntactically indistinguishable from field reads, so they are
        # captured and flagged ``paren_free`` for downstream filtering.
        for field_node in nodes:
            if field_node.type != "field_expression":
                continue
            if field_node.id in called_function_ids:
                continue
            owner = self._enclosing_symbol(field_node, containers)
            if owner is None:
                continue
            field_child: Node | None = field_node.child_by_field_name("field")
            value_child: Node | None = field_node.child_by_field_name("value")
            if field_child is None:
                continue
            callee_name = self._node_text(field_child, source_bytes)
            receiver = (
                self._node_text(value_child, source_bytes)
                if value_child is not None
                else None
            )
            relations.append(
                self._call_relation(
                    owner=owner,
                    target=self._resolve_call_node(
                        field_node, callee_name, value_child, containers, context, source_bytes
                    ),
                    source_path=source_path,
                    callee_name=callee_name,
                    receiver=receiver,
                    paren_free=True,
                )
            )
        return relations

    def _resolve_call_node(
        self,
        node: Node,
        callee_name: str,
        receiver_node: Node | None,
        containers: list[tuple[int, int, ScalaSymbol]],
        context: ResolutionContext,
        source_bytes: bytes,
    ) -> ScalaSymbol | None:
        enclosing_type: ScalaSymbol | None = self._enclosing_of_kinds(
            node, containers, TYPE_KINDS
        )
        enclosing_function: ScalaSymbol | None = self._enclosing_of_kinds(
            node, containers, frozenset({"function"})
        )
        # ``this``-call / no explicit receiver resolves against the enclosing type;
        # otherwise type the receiver expression (recursively, so ``a.b.c`` works).
        receiver_type: ScalaSymbol | None = (
            enclosing_type
            if receiver_node is None
            else self._expr_type(
                receiver_node, enclosing_type, enclosing_function, context, source_bytes
            )
        )
        if receiver_type is not None:
            target: ScalaSymbol | None = self._find_member(
                callee_name, receiver_type, context
            )
            if target is not None:
                return target
        return self._resolve_call_byname(
            callee_name,
            self._node_text(receiver_node, source_bytes) if receiver_node else None,
            enclosing_type,
            context.function_symbols,
        )

    def _expr_type(
        self,
        node: Node,
        enclosing_type: ScalaSymbol | None,
        enclosing_function: ScalaSymbol | None,
        context: ResolutionContext,
        source_bytes: bytes,
    ) -> ScalaSymbol | None:
        """Best-effort static type (as a type symbol) of an expression node."""
        if node.type == "this":
            return enclosing_type
        if node.type == "identifier":
            name: str = self._node_text(node, source_bytes)
            type_name: str | None = None
            if enclosing_function is not None:
                type_name = context.func_params.get(enclosing_function.id, {}).get(name)
            if type_name is None and enclosing_type is not None:
                type_name = self._lookup_field_type(name, enclosing_type, context)
            if type_name is not None:
                return self._resolve_type_name(type_name, context)
            # ``name`` may itself be an object/enum/type (``Event``, ``PlayerState``).
            return self._resolve_type_name(name, context)
        if node.type == "field_expression":
            value_node: Node | None = node.child_by_field_name("value")
            field_node: Node | None = node.child_by_field_name("field")
            if value_node is None or field_node is None:
                return None
            receiver_type: ScalaSymbol | None = self._expr_type(
                value_node, enclosing_type, enclosing_function, context, source_bytes
            )
            if receiver_type is None:
                return None
            member: ScalaSymbol | None = self._find_member(
                self._node_text(field_node, source_bytes), receiver_type, context
            )
            return self._member_type(member, context)
        if node.type == "call_expression":
            function_node: Node | None = node.child_by_field_name("function")
            if function_node is None:
                return None
            return self._expr_type(
                function_node, enclosing_type, enclosing_function, context, source_bytes
            )
        return None

    def _member_type(
        self,
        member: ScalaSymbol | None,
        context: ResolutionContext,
    ) -> ScalaSymbol | None:
        if member is None:
            return None
        if member.kind == "enum_case":
            # An enum case's type is its enum.
            return context.symbols_by_fqn.get(member.fqn.rsplit(".", 1)[0]) if member.fqn else None
        return_type: str | None = member.metadata.get("return_type")
        if not return_type:
            return None
        return self._resolve_type_name(return_type, context)

    def _call_relation(
        self,
        owner: ScalaSymbol,
        target: ScalaSymbol | None,
        source_path: str,
        callee_name: str,
        receiver: str | None,
        paren_free: bool,
    ) -> ScalaRelation:
        metadata: dict[str, Any] = {
            "callee_name": callee_name,
            "receiver": receiver,
            "resolved": target is not None,
        }
        if paren_free:
            metadata["paren_free"] = True
        return ScalaRelation(
            type="CALLS",
            source_id=owner.id,
            target_id=target.id if target is not None else None,
            source_path=source_path,
            target_kind="symbol" if target is not None else "call",
            metadata=metadata,
        )

    def _instantiation_relations(
        self,
        root_node: Node,
        source_bytes: bytes,
        source_path: str,
        containers: list[tuple[int, int, ScalaSymbol]],
        package_name: str | None,
        symbols_by_fqn: dict[str, ScalaSymbol],
    ) -> list[ScalaRelation]:
        relations: list[ScalaRelation] = []
        for node in self._nodes(root_node):
            if node.type != "instance_expression":
                continue
            type_node: Node | None = self._instance_type_node(node)
            if type_node is None:
                continue
            type_name: str = self._base_type_name(type_node, source_bytes)
            owner: ScalaSymbol | None = self._enclosing_symbol(node, containers)
            source_id: str = owner.id if owner is not None else source_path
            target: ScalaSymbol | None = self._resolve_type(
                type_name,
                package_name,
                symbols_by_fqn,
            )
            if target is None:
                relations.append(
                    self._external_relation(
                        relation_type="INSTANTIATES",
                        source_id=source_id,
                        source_path=source_path,
                        fqn=type_name,
                        metadata={"type_name": type_name},
                    )
                )
            else:
                relations.append(
                    ScalaRelation(
                        type="INSTANTIATES",
                        source_id=source_id,
                        target_id=target.id,
                        source_path=source_path,
                        target_kind="symbol",
                        metadata={"type_name": type_name},
                    )
                )
        return relations

    def _uses_relations(
        self,
        root_node: Node,
        source_bytes: bytes,
        symbols: list[ScalaSymbol],
        package_name: str | None,
        symbols_by_fqn: dict[str, ScalaSymbol],
    ) -> list[ScalaRelation]:
        symbol_by_range: dict[tuple[int, int], ScalaSymbol] = {
            (symbol.range.start_byte, symbol.range.end_byte): symbol
            for symbol in symbols
            if symbol.kind in USES_SOURCE_KINDS
        }
        relations: list[ScalaRelation] = []
        for node in self._nodes(root_node):
            symbol: ScalaSymbol | None = symbol_by_range.get(
                (node.start_byte, node.end_byte)
            )
            if symbol is None:
                continue
            seen: set[str] = set()
            for type_name in self._signature_type_names(node, source_bytes):
                if type_name in seen:
                    continue
                seen.add(type_name)
                target: ScalaSymbol | None = self._resolve_type(
                    type_name,
                    package_name,
                    symbols_by_fqn,
                )
                if target is not None and target.id == symbol.id:
                    continue
                if target is None:
                    relations.append(
                        self._external_relation(
                            relation_type="USES",
                            source_id=symbol.id,
                            source_path=symbol.source_path,
                            fqn=type_name,
                            metadata={"type_name": type_name},
                        )
                    )
                else:
                    relations.append(
                        ScalaRelation(
                            type="USES",
                            source_id=symbol.id,
                            target_id=target.id,
                            source_path=symbol.source_path,
                            target_kind="symbol",
                            metadata={"type_name": type_name},
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
            if relation.type not in {"IMPORTS", "CALLS", "INSTANTIATES", "USES"}:
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

    def _resolve_call_byname(
        self,
        callee_name: str,
        receiver: str | None,
        caller: ScalaSymbol | None,
        function_symbols: list[ScalaSymbol],
    ) -> ScalaSymbol | None:
        """Best-effort fallback when the receiver type could not be determined."""
        candidates: list[ScalaSymbol] = [
            symbol for symbol in function_symbols if symbol.name == callee_name
        ]
        if not candidates:
            return None

        if caller is not None:
            same_parent: list[ScalaSymbol] = [
                symbol for symbol in candidates if symbol.parent_id == caller.parent_id
            ]
            if len(same_parent) == 1:
                return same_parent[0]

            same_file: list[ScalaSymbol] = [
                symbol
                for symbol in candidates
                if symbol.source_path == caller.source_path
            ]
            if len(same_file) == 1:
                return same_file[0]

        if receiver is None and len(candidates) == 1:
            return candidates[0]
        return None

    def _lookup_field_type(
        self,
        name: str,
        type_symbol: ScalaSymbol,
        context: ResolutionContext,
    ) -> str | None:
        seen: set[str] = set()
        queue: list[str] = [type_symbol.id]
        while queue:
            type_id: str = queue.pop(0)
            if type_id in seen:
                continue
            seen.add(type_id)
            fields: dict[str, str] = context.field_types.get(type_id, {})
            if name in fields:
                return fields[name]
            queue.extend(context.supertypes_by_id.get(type_id, []))
        return None

    def _find_member(
        self,
        name: str,
        type_symbol: ScalaSymbol,
        context: ResolutionContext,
    ) -> ScalaSymbol | None:
        seen: set[str] = set()
        queue: list[str] = [type_symbol.id]
        while queue:
            type_id: str = queue.pop(0)
            if type_id in seen:
                continue
            seen.add(type_id)
            for member in context.members_by_parent.get(type_id, []):
                if member.name == name and member.kind in CALLABLE_KINDS:
                    return member
            queue.extend(context.supertypes_by_id.get(type_id, []))
        return None

    def _resolve_type_name(
        self,
        name: str,
        context: ResolutionContext,
    ) -> ScalaSymbol | None:
        base_name: str = name.split("[", 1)[0].strip()
        candidates: list[str] = []
        if base_name in context.import_simple:
            candidates.append(context.import_simple[base_name])
        if context.package_name:
            candidates.append(f"{context.package_name}.{base_name}")
        candidates.append(base_name)
        candidates.extend(f"{prefix}.{base_name}" for prefix in context.import_wildcards)
        for candidate in candidates:
            symbol: ScalaSymbol | None = context.symbols_by_fqn.get(candidate)
            if symbol is not None and symbol.kind in TYPE_KINDS:
                return symbol
        simple_matches: list[ScalaSymbol] = context.simple_types.get(
            base_name.rsplit(".", 1)[-1], []
        )
        return simple_matches[0] if len(simple_matches) == 1 else None

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

    def _containers(
        self,
        symbols: list[ScalaSymbol],
    ) -> list[tuple[int, int, ScalaSymbol]]:
        return [
            (symbol.range.start_byte, symbol.range.end_byte, symbol)
            for symbol in symbols
            if symbol.kind in CONTAINER_KINDS
        ]

    def _enclosing_symbol(
        self,
        node: Node,
        containers: list[tuple[int, int, ScalaSymbol]],
    ) -> ScalaSymbol | None:
        best: ScalaSymbol | None = None
        best_span: int | None = None
        for start_byte, end_byte, symbol in containers:
            if start_byte <= node.start_byte and node.end_byte <= end_byte:
                span: int = end_byte - start_byte
                if best_span is None or span < best_span:
                    best_span = span
                    best = symbol
        return best

    def _enclosing_of_kinds(
        self,
        node: Node,
        containers: list[tuple[int, int, ScalaSymbol]],
        kinds: frozenset[str],
    ) -> ScalaSymbol | None:
        best: ScalaSymbol | None = None
        best_span: int | None = None
        for start_byte, end_byte, symbol in containers:
            if symbol.kind not in kinds:
                continue
            if start_byte <= node.start_byte and node.end_byte <= end_byte:
                span: int = end_byte - start_byte
                if best_span is None or span < best_span:
                    best_span = span
                    best = symbol
        return best

    def _build_context(
        self,
        root_node: Node,
        source_bytes: bytes,
        symbols: list[ScalaSymbol],
        all_symbols: list[ScalaSymbol],
        symbols_by_fqn: dict[str, ScalaSymbol],
        package_name: str | None,
    ) -> ResolutionContext:
        type_symbols: list[ScalaSymbol] = [
            symbol for symbol in all_symbols if symbol.kind in TYPE_KINDS
        ]
        simple_types: dict[str, list[ScalaSymbol]] = {}
        for symbol in type_symbols:
            simple_types.setdefault(symbol.name, []).append(symbol)
        members_by_parent: dict[str, list[ScalaSymbol]] = {}
        for symbol in all_symbols:
            if symbol.parent_id is not None and symbol.kind in CALLABLE_KINDS:
                members_by_parent.setdefault(symbol.parent_id, []).append(symbol)
        import_simple, import_wildcards = self._build_import_index(symbols)
        supertypes_by_id: dict[str, list[str]] = self._build_supertypes(
            type_symbols, symbols_by_fqn, simple_types
        )
        func_params, field_types = self._build_scope(root_node, source_bytes, symbols)
        return ResolutionContext(
            symbols_by_fqn=symbols_by_fqn,
            simple_types=simple_types,
            members_by_parent=members_by_parent,
            supertypes_by_id=supertypes_by_id,
            import_simple=import_simple,
            import_wildcards=import_wildcards,
            package_name=package_name,
            func_params=func_params,
            field_types=field_types,
            function_symbols=[s for s in all_symbols if s.kind == "function"],
        )

    def _build_import_index(
        self,
        symbols: list[ScalaSymbol],
    ) -> tuple[dict[str, str], list[str]]:
        simple: dict[str, str] = {}
        wildcards: list[str] = []
        for symbol in symbols:
            if symbol.kind != "import":
                continue
            name: str = symbol.name.strip()
            if ".{" in name and name.endswith("}"):
                prefix, selectors = name.split(".{", 1)
                for selector in selectors.removesuffix("}").split(","):
                    selector = selector.strip()
                    if not selector:
                        continue
                    if "=>" in selector:
                        original, alias = (part.strip() for part in selector.split("=>", 1))
                        simple[alias] = f"{prefix}.{original}"
                    else:
                        simple[selector] = f"{prefix}.{selector}"
            elif name.endswith("._") or name.endswith(".*"):
                wildcards.append(name[:-2])
            else:
                simple[name.rsplit(".", 1)[-1]] = name
        return simple, wildcards

    def _build_supertypes(
        self,
        type_symbols: list[ScalaSymbol],
        symbols_by_fqn: dict[str, ScalaSymbol],
        simple_types: dict[str, list[ScalaSymbol]],
    ) -> dict[str, list[str]]:
        supertypes_by_id: dict[str, list[str]] = {}
        for symbol in type_symbols:
            ids: list[str] = []
            for name in symbol.metadata.get("supertypes", []):
                target: ScalaSymbol | None = self._resolve_type_name_global(
                    name, symbols_by_fqn, simple_types
                )
                if target is not None and target.id != symbol.id:
                    ids.append(target.id)
            if ids:
                supertypes_by_id[symbol.id] = ids
        return supertypes_by_id

    def _resolve_type_name_global(
        self,
        name: str,
        symbols_by_fqn: dict[str, ScalaSymbol],
        simple_types: dict[str, list[ScalaSymbol]],
    ) -> ScalaSymbol | None:
        base_name: str = name.split("[", 1)[0].strip()
        symbol: ScalaSymbol | None = symbols_by_fqn.get(base_name)
        if symbol is not None and symbol.kind in TYPE_KINDS:
            return symbol
        matches: list[ScalaSymbol] = simple_types.get(base_name.rsplit(".", 1)[-1], [])
        return matches[0] if len(matches) == 1 else None

    def _build_scope(
        self,
        root_node: Node,
        source_bytes: bytes,
        symbols: list[ScalaSymbol],
    ) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
        symbol_by_range: dict[tuple[int, int], ScalaSymbol] = {
            (symbol.range.start_byte, symbol.range.end_byte): symbol
            for symbol in symbols
        }
        func_params: dict[str, dict[str, str]] = {}
        field_types: dict[str, dict[str, str]] = {}
        # ``val``/``var`` members with a declared type are fields of their owner.
        for symbol in symbols:
            if symbol.parent_id is not None and symbol.kind in {"val", "var"}:
                declared_type: str | None = symbol.metadata.get("type")
                if declared_type:
                    field_types.setdefault(symbol.parent_id, {})[symbol.name] = (
                        self._base_name_of(declared_type)
                    )
        for node in self._nodes(root_node):
            symbol = symbol_by_range.get((node.start_byte, node.end_byte))
            if symbol is None:
                continue
            if symbol.kind == "function":
                params: dict[str, str] = {}
                self._collect_function_params(node, source_bytes, params)
                if params:
                    func_params[symbol.id] = params
            elif symbol.kind in TYPE_KINDS:
                class_parameters: Node | None = node.child_by_field_name(
                    "class_parameters"
                )
                if class_parameters is not None:
                    params = {}
                    self._collect_params_from(class_parameters, source_bytes, params)
                    if params:
                        field_types.setdefault(symbol.id, {}).update(params)
            elif symbol.kind in {"val", "var"} and symbol.parent_id is not None:
                # Infer the field type from a ``new X(...)`` initializer when the
                # ``val``/``var`` has no explicit type annotation.
                if symbol.name in field_types.get(symbol.parent_id, {}):
                    continue
                value_node: Node | None = node.child_by_field_name("value")
                if value_node is not None and value_node.type == "instance_expression":
                    type_node: Node | None = self._instance_type_node(value_node)
                    if type_node is not None:
                        field_types.setdefault(symbol.parent_id, {})[symbol.name] = (
                            self._base_type_name(type_node, source_bytes)
                        )
        return func_params, field_types

    def _collect_function_params(
        self,
        function_node: Node,
        source_bytes: bytes,
        out: dict[str, str],
    ) -> None:
        for index, child in enumerate(function_node.children):
            if (
                function_node.field_name_for_child(index) == "parameters"
                and child.type == "parameters"
            ):
                self._collect_params_from(child, source_bytes, out)

    def _collect_params_from(
        self,
        params_node: Node,
        source_bytes: bytes,
        out: dict[str, str],
    ) -> None:
        for child in params_node.children:
            if child.type not in {"parameter", "class_parameter"}:
                continue
            name_node: Node | None = child.child_by_field_name("name")
            type_node: Node | None = child.child_by_field_name("type")
            if name_node is not None and type_node is not None:
                out[self._node_text(name_node, source_bytes)] = self._base_type_name(
                    type_node, source_bytes
                )

    def _base_name_of(self, type_text: str) -> str:
        return type_text.split("[", 1)[0].strip()

    def _instance_type_node(self, node: Node) -> Node | None:
        for child in node.children:
            if child.type in {
                "type_identifier",
                "stable_type_identifier",
                "generic_type",
            }:
                return child
        return None

    def _signature_type_names(self, node: Node, source_bytes: bytes) -> list[str]:
        names: list[str] = []
        self._collect_signature_types(node, source_bytes, names, is_root=True)
        return names

    def _collect_signature_types(
        self,
        node: Node,
        source_bytes: bytes,
        names: list[str],
        is_root: bool,
    ) -> None:
        for index, child in enumerate(node.children):
            if child.type == "type_parameters":
                continue
            if is_root and node.field_name_for_child(index) in NON_SIGNATURE_FIELDS:
                continue
            if child.type in {"type_identifier", "stable_type_identifier"}:
                names.append(self._node_text(child, source_bytes))
                continue
            self._collect_signature_types(child, source_bytes, names, is_root=False)

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
