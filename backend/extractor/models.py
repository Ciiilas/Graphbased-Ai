"""Typed models for parsed Scala files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourcePoint:
    """Zero-based source position from Tree-sitter."""

    row: int
    column: int

    def to_dict(self) -> dict[str, int]:
        return {"row": self.row, "column": self.column}


@dataclass(frozen=True)
class SourceRange:
    """Byte and line range for a source element."""

    start_byte: int
    end_byte: int
    start_point: SourcePoint
    end_point: SourcePoint

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_byte": self.start_byte,
            "end_byte": self.end_byte,
            "start_point": self.start_point.to_dict(),
            "end_point": self.end_point.to_dict(),
        }


@dataclass
class AstNode:
    """JSON-ready AST node."""

    # NOTE: ``id`` is Tree-sitter's per-parse node identity (a pointer-based
    # value). It is unique within a single parsed tree but NOT stable across
    # runs or edits. Do not use it as a knowledge-graph node key; derive a
    # stable id from (relative_path, byte range, type) in the graph step.
    id: int
    type: str
    named: bool
    range: SourceRange
    field_name: str | None = None
    text: str | None = None
    children: list["AstNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "named": self.named,
            "range": self.range.to_dict(),
            "field_name": self.field_name,
            "children": [child.to_dict() for child in self.children],
        }
        if self.text is not None:
            data["text"] = self.text
        return data


@dataclass(frozen=True)
class ScalaSymbol:
    """Basic symbol extracted from a Scala AST."""

    id: str
    kind: str
    name: str
    range: SourceRange
    source_path: str
    fqn: str | None = None
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "range": self.range.to_dict(),
            "source_path": self.source_path,
            "fqn": self.fqn,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ScalaRelation:
    """Graph relation extracted from Scala source."""

    type: str
    source_id: str
    target_id: str | None
    source_path: str
    target_kind: str = "symbol"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "source_path": self.source_path,
            "target_kind": self.target_kind,
            "metadata": self.metadata,
        }


@dataclass
class ParsedFile:
    """Parsed Scala file including AST and symbols."""

    relative_path: str
    absolute_path: Path
    has_errors: bool
    ast: AstNode
    symbols: list[ScalaSymbol]
    relations: list[ScalaRelation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "absolute_path": str(self.absolute_path),
            "has_errors": self.has_errors,
            "ast": self.ast.to_dict(),
            "symbols": [symbol.to_dict() for symbol in self.symbols],
            "relations": [relation.to_dict() for relation in self.relations],
        }
