"""CLI for the retrieval + graph context orchestrator."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from backend.db.config import Neo4jSettings
from backend.db.connection import Neo4jConnection
from backend.orchestrator.graph import GraphContextRepository
from backend.orchestrator.service import CodeQuestionOrchestrator
from backend.vector.config import ChromaSettings, GeminiEmbeddingSettings
from backend.vector.embeddings import LlamaIndexGeminiEmbeddingProvider
from backend.vector.repository import ChromaVectorRepository


def build_argument_parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Ask code questions using semantic and graph context."
    )
    subcommands = argument_parser.add_subparsers(dest="command", required=True)

    ask_parser = subcommands.add_parser(
        "ask",
        help="Build prompt context for a code question.",
    )
    ask_parser.add_argument(
        "--query",
        required=True,
        help="Natural-language question about the analyzed Scala codebase.",
    )
    ask_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of semantic Chroma hits used as graph seeds.",
    )
    ask_parser.add_argument(
        "--max-neighbors",
        type=int,
        default=20,
        help="Maximum number of graph neighbors to include.",
    )
    ask_parser.add_argument(
        "--max-snippets",
        type=int,
        default=12,
        help="Maximum number of snippets included in the prompt.",
    )

    return argument_parser


def main() -> int:
    argument_parser: argparse.ArgumentParser = build_argument_parser()
    arguments: argparse.Namespace = argument_parser.parse_args()

    if arguments.command != "ask":
        return 1

    try:
        vector_repository = ChromaVectorRepository(ChromaSettings.from_env())
        embedding_provider = LlamaIndexGeminiEmbeddingProvider(
            GeminiEmbeddingSettings.from_env()
        )
        with Neo4jConnection(Neo4jSettings.from_env()) as connection:
            connection.verify_connectivity()
            graph_repository = GraphContextRepository(connection)
            orchestrator = CodeQuestionOrchestrator(
                embedding_provider=embedding_provider,
                vector_repository=vector_repository,
                graph_repository=graph_repository,
            )
            response = orchestrator.answer(
                query=arguments.query,
                top_k=arguments.top_k,
                max_neighbors=arguments.max_neighbors,
                max_snippets=arguments.max_snippets,
            )
        print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        error_response: dict[str, Any] = {
            "query": getattr(arguments, "query", ""),
            "answer": None,
            "prompt": "",
            "semantic_hits": [],
            "graph_relations": [],
            "snippets": [],
            "warnings": [],
            "error": str(error),
        }
        print(json.dumps(error_response, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
