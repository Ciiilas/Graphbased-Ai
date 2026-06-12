"""CLI for ChromaDB vector imports and semantic search."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.vector.config import ChromaSettings, GeminiEmbeddingSettings
from backend.vector.embeddings import LlamaIndexGeminiEmbeddingProvider
from backend.vector.importer import AstVectorImporter, VectorSearchService
from backend.vector.repository import ChromaVectorRepository


def build_argument_parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(description="Manage ChromaDB vectors.")
    subcommands = argument_parser.add_subparsers(dest="command", required=True)

    import_parser = subcommands.add_parser(
        "import-ast",
        help="Import extractor AST JSON files into ChromaDB.",
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
        help="Delete the configured Chroma collection before importing.",
    )
    import_parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Number of chunks embedded per Gemini request.",
    )

    search_parser = subcommands.add_parser(
        "search",
        help="Run semantic search against the configured Chroma collection.",
    )
    search_parser.add_argument(
        "--query",
        required=True,
        help="Natural-language search query.",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of results.",
    )

    return argument_parser


def main() -> int:
    argument_parser: argparse.ArgumentParser = build_argument_parser()
    arguments: argparse.Namespace = argument_parser.parse_args()

    repository = ChromaVectorRepository(ChromaSettings.from_env())
    embedding_provider = LlamaIndexGeminiEmbeddingProvider(
        GeminiEmbeddingSettings.from_env()
    )

    if arguments.command == "import-ast":
        importer = AstVectorImporter(
            repository=repository,
            embedding_provider=embedding_provider,
            batch_size=arguments.batch_size,
        )
        summary = importer.import_directory(
            ast_root=arguments.ast_root,
            reset=arguments.reset,
        )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        return 1 if summary.has_errors else 0

    if arguments.command == "search":
        search_service = VectorSearchService(
            repository=repository,
            embedding_provider=embedding_provider,
        )
        results = search_service.search(query=arguments.query, limit=arguments.limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
