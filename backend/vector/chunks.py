"""Build semantic code chunks from extractor JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


INDEXABLE_SYMBOL_KINDS: frozenset[str] = frozenset(
    {
        "object",
        "class",
        "trait",
        "enum",
        "function",
        "val",
        "var",
        "type",
        "given",
        "enum_case",
    }
)


@dataclass(frozen=True)
class CodeChunk:
    """One document that can be embedded and stored in ChromaDB."""

    id: str
    text: str
    metadata: dict[str, str | int | float | bool]


@dataclass(frozen=True)
class CodeChunkBuilder:
    """Convert a parsed file document into symbol-level code chunks."""

    indexable_symbol_kinds: frozenset[str] = INDEXABLE_SYMBOL_KINDS

    def build_from_parsed_file(self, parsed_file: dict[str, Any]) -> list[CodeChunk]:
        relative_path: str = str(parsed_file["relative_path"])
        absolute_path: Path = Path(str(parsed_file["absolute_path"]))
        source_bytes: bytes = absolute_path.read_bytes()
        source_text: str = source_bytes.decode("utf-8", errors="replace")

        chunks: list[CodeChunk] = []
        for symbol in parsed_file.get("symbols", []):
            kind: str = str(symbol.get("kind", ""))
            if kind not in self.indexable_symbol_kinds:
                continue
            chunks.append(
                self._symbol_chunk(
                    symbol=symbol,
                    relative_path=relative_path,
                    absolute_path=absolute_path,
                    source_bytes=source_bytes,
                )
            )

        if chunks:
            return chunks

        return [
            self._file_chunk(
                parsed_file=parsed_file,
                relative_path=relative_path,
                absolute_path=absolute_path,
                source_text=source_text,
            )
        ]

    def _symbol_chunk(
        self,
        symbol: dict[str, Any],
        relative_path: str,
        absolute_path: Path,
        source_bytes: bytes,
    ) -> CodeChunk:
        source_range: dict[str, Any] = symbol["range"]
        start_byte: int = int(source_range["start_byte"])
        end_byte: int = int(source_range["end_byte"])
        code_text: str = source_bytes[start_byte:end_byte].decode(
            "utf-8",
            errors="replace",
        )
        kind: str = str(symbol.get("kind", "symbol"))
        name: str = str(symbol.get("name", ""))
        fqn: str = str(symbol.get("fqn") or "")
        text: str = self._chunk_text(
            kind=kind,
            name=name,
            fqn=fqn,
            relative_path=relative_path,
            code_text=code_text,
        )
        metadata: dict[str, str | int | float | bool] = {
            "relative_path": relative_path,
            "absolute_path": str(absolute_path),
            "symbol_id": str(symbol["id"]),
            "kind": kind,
            "name": name,
            "fqn": fqn,
            "parent_id": str(symbol.get("parent_id") or ""),
            "start_byte": start_byte,
            "end_byte": end_byte,
            "start_line": self._line_number(source_range, "start_point"),
            "end_line": self._line_number(source_range, "end_point"),
            "symbol_metadata_json": json.dumps(
                symbol.get("metadata", {}),
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
        return CodeChunk(id=str(symbol["id"]), text=text, metadata=metadata)

    def _file_chunk(
        self,
        parsed_file: dict[str, Any],
        relative_path: str,
        absolute_path: Path,
        source_text: str,
    ) -> CodeChunk:
        source_range: dict[str, Any] = parsed_file.get("ast", {}).get("range", {})
        end_byte: int = int(source_range.get("end_byte", len(source_text.encode("utf-8"))))
        metadata: dict[str, str | int | float | bool] = {
            "relative_path": relative_path,
            "absolute_path": str(absolute_path),
            "symbol_id": "",
            "kind": "file",
            "name": relative_path,
            "fqn": "",
            "parent_id": "",
            "start_byte": 0,
            "end_byte": end_byte,
            "start_line": 1,
            "end_line": source_text.count("\n") + 1,
            "symbol_metadata_json": "{}",
        }
        text: str = self._chunk_text(
            kind="file",
            name=relative_path,
            fqn="",
            relative_path=relative_path,
            code_text=source_text,
        )
        return CodeChunk(id=f"file:{relative_path}", text=text, metadata=metadata)

    def _chunk_text(
        self,
        kind: str,
        name: str,
        fqn: str,
        relative_path: str,
        code_text: str,
    ) -> str:
        header: list[str] = [
            f"kind: {kind}",
            f"name: {name}",
            f"path: {relative_path}",
        ]
        if fqn:
            header.append(f"fqn: {fqn}")
        return "\n".join([*header, "", code_text.strip()])

    def _line_number(self, source_range: dict[str, Any], key: str) -> int:
        point: dict[str, Any] = source_range.get(key, {})
        return int(point.get("row", 0)) + 1

