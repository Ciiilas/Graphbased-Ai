"""CLI for Neo4j schema setup and AST imports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.db.config import Neo4jSettings
from backend.db.connection import Neo4jConnection
from backend.db.importer import AstJsonImporter
from backend.db.repository import Neo4jGraphRepository


def build_argument_parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(description="Manage the Neo4j graph DB.")
    subcommands = argument_parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("init-schema", help="Create Neo4j constraints.")

    import_parser = subcommands.add_parser(
        "import-ast",
        help="Import extractor AST JSON files into Neo4j.",
    )
    import_parser.add_argument(
        "--ast-root",
        required=True,
        type=Path,
        help="Extractor output root containing manifest.json and files/.",
    )
    import_parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all existing nodes and relationships before importing.",
    )

    return argument_parser


def main() -> int:
    argument_parser = build_argument_parser()
    arguments = argument_parser.parse_args()
    settings = Neo4jSettings.from_env()

    with Neo4jConnection(settings) as connection:
        connection.verify_connectivity()
        repository = Neo4jGraphRepository(connection)

        if arguments.command == "init-schema":
            repository.create_constraints()
            print("Neo4j schema initialized.")
            return 0

        if arguments.command == "import-ast":
            if arguments.reset:
                repository.clear_graph()
                print("Existing graph cleared.")
            repository.create_constraints()
            importer = AstJsonImporter(repository)
            summary = importer.import_directory(arguments.ast_root)
            print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
            return 1 if summary.has_errors else 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
