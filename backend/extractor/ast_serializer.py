"""Serialize Tree-sitter nodes into graph-ready dictionaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tree_sitter import Node

from backend.extractor.models import AstNode, SourcePoint, SourceRange


@dataclass(frozen=True)
class AstSerializer:
    """Convert Tree-sitter AST nodes into JSON-ready dataclasses."""

    max_leaf_text_length: int = 160

    def serialize(self, root_node: Node, source_bytes: bytes) -> AstNode:
        return self._serialize_node(root_node, source_bytes, field_name=None)

    def _serialize_node(
        self,
        node: Node,
        source_bytes: bytes,
        field_name: str | None,
    ) -> AstNode:
        children: list[AstNode] = []
        for index, child in enumerate(node.children):
            child_field_name: str | None = node.field_name_for_child(index)
            children.append(self._serialize_node(child, source_bytes, child_field_name))

        return AstNode(
            id=int(node.id),
            type=node.type,
            named=node.is_named,
            range=self._source_range(node),
            field_name=field_name,
            text=self._leaf_text(node, source_bytes),
            children=children,
        )

    def _source_range(self, node: Node) -> SourceRange:
        start_point: Any = node.start_point
        end_point: Any = node.end_point
        return SourceRange(
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_point=SourcePoint(row=start_point[0], column=start_point[1]),
            end_point=SourcePoint(row=end_point[0], column=end_point[1]),
        )

    def _leaf_text(self, node: Node, source_bytes: bytes) -> str | None:
        if node.child_count > 0:
            return None

        raw_text: bytes = source_bytes[node.start_byte : node.end_byte]
        text: str = raw_text.decode("utf-8", errors="replace").strip()
        if not text or len(text) > self.max_leaf_text_length:
            return None
        return text
