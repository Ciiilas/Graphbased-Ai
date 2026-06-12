"""Scala file scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".bsp",
        ".metals",
        ".scala-build",
        "build",
        "dist",
        "node_modules",
        "target",
    }
)


@dataclass(frozen=True)
class ScalaFileScanner:
    """Find Scala files while skipping build and tooling folders."""

    excluded_dirs: frozenset[str] = field(default=DEFAULT_EXCLUDED_DIRS)

    def find_scala_files(self, source_root: Path) -> list[Path]:
        root: Path = source_root.absolute()
        if not root.exists():
            raise FileNotFoundError(f"Source root does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Source root is not a directory: {root}")

        scala_files: list[Path] = []
        for path in root.rglob("*.scala"):
            if self._is_excluded(path, root):
                continue
            scala_files.append(path)
        return sorted(scala_files)

    def _is_excluded(self, path: Path, source_root: Path) -> bool:
        relative_parts: tuple[str, ...] = path.relative_to(source_root).parts
        return any(part in self.excluded_dirs for part in relative_parts[:-1])
