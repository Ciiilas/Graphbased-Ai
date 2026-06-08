"""Import extractor JSON files into Neo4j."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class ParsedFileRepository(Protocol):
    def import_parsed_file(self, parsed_file: dict[str, Any]) -> None:
        """Import one parsed file document."""


@dataclass
class ImportSummary:
    """Result of importing AST JSON files."""

    total_files: int = 0
    imported_files: int = 0
    failed_files: list[dict[str, str]] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.failed_files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "imported_files": self.imported_files,
            "failed_files": self.failed_files,
            "has_errors": self.has_errors,
        }


@dataclass(frozen=True)
class AstJsonImporter:
    """Load extractor output from disk and pass it to a repository."""

    repository: ParsedFileRepository

    def import_directory(self, ast_root: Path) -> ImportSummary:
        files_root: Path = ast_root.resolve() / "files"
        if not files_root.exists():
            raise FileNotFoundError(f"AST files directory does not exist: {files_root}")

        ast_files: list[Path] = sorted(files_root.rglob("*.json"))
        summary = ImportSummary(total_files=len(ast_files))

        for ast_file in ast_files:
            try:
                parsed_file: dict[str, Any] = json.loads(
                    ast_file.read_text(encoding="utf-8")
                )
                self.repository.import_parsed_file(parsed_file)
                summary.imported_files += 1
            except Exception as error:
                summary.failed_files.append(
                    {
                        "path": str(ast_file),
                        "error": str(error),
                    }
                )

        return summary
