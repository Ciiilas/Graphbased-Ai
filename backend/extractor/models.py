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
            "start_byte": self.range.start_byte,
            "end_byte": self.range.end_byte,
            "start_point": self.range.start_point.to_dict(),
            "end_point": self.range.end_point.to_dict(),
            "field_name": self.field_name,
            "children": [child.to_dict() for child in self.children],
        }
        if self.text is not None:
            data["text"] = self.text
        return data


@dataclass(frozen=True)
class ScalaSymbol:
    """Basic symbol extracted from a Scala AST."""

    kind: str
    name: str
    range: SourceRange
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "range": self.range.to_dict(),
            "source_path": self.source_path,
        }


@dataclass
class ParsedFile:
    """Parsed Scala file including AST and symbols."""

    relative_path: str
    absolute_path: Path
    has_errors: bool
    ast: AstNode
    symbols: list[ScalaSymbol]

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "absolute_path": str(self.absolute_path),
            "has_errors": self.has_errors,
            "ast": self.ast.to_dict(),
            "symbols": [symbol.to_dict() for symbol in self.symbols],
        }
