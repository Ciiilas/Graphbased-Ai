"""Interactive terminal entry point for Graphbased-AI.

Wires the existing modules together so the whole pipeline can be driven from a
single command: point it at a Scala codebase, build the Neo4j graph and the
ChromaDB vector index, then ask questions about the code.

Usage:
    python main.py                       # interactive menu
    python main.py index --source PATH   # extract + Neo4j + ChromaDB
    python main.py ask --query "..."     # one question

The heavy backends (ChromaDB, LlamaIndex/Gemini) are imported lazily by the
modules they live in, so ``python main.py --help`` works without them installed.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _force_utf8_output() -> None:
    """Make stdout/stderr emit UTF-8 so German text shows correctly on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

from backend.db.config import Neo4jSettings
from backend.db.connection import Neo4jConnection
from backend.db.importer import AstJsonImporter
from backend.db.repository import Neo4jGraphRepository
from backend.extractor.ast_serializer import AstSerializer
from backend.extractor.cli import ScalaExtractionCli
from backend.extractor.parser import ScalaTreeSitterParser
from backend.extractor.relations import RelationExtractor
from backend.extractor.scanner import ScalaFileScanner
from backend.extractor.symbols import SymbolExtractor
from backend.orchestrator.graph import GraphContextRepository
from backend.orchestrator.llm import GeminiAnswerProvider
from backend.orchestrator.models import OrchestratorResponse
from backend.orchestrator.service import CodeQuestionOrchestrator
from backend.vector.config import (
    ChromaSettings,
    GeminiEmbeddingSettings,
    GeminiGenerationSettings,
)
from backend.vector.embeddings import LlamaIndexGeminiEmbeddingProvider
from backend.vector.importer import AstVectorImporter
from backend.vector.repository import ChromaVectorRepository


PROJECT_ROOT: Path = Path(__file__).resolve().parent
DEFAULT_AST_ROOT: Path = PROJECT_ROOT / "local-data" / "ast"


def load_env_file(env_path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file without extra dependencies.

    Real environment variables take precedence (setdefault), so an exported
    value is never overwritten by the file.
    """
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line: str = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


# ----------------------------------------------------------------------------
# Pipeline stages (each reuses an existing module; no logic is duplicated here).
# ----------------------------------------------------------------------------


def run_extraction(source: Path, ast_root: Path) -> bool:
    """Parse the Scala codebase into AST JSON. Returns True on success."""
    if not source.exists():
        print(f"  [FEHLER] Pfad existiert nicht: {source}")
        return False

    print(f"  -> Extrahiere Scala-Code aus {source} ...")
    extraction_cli = ScalaExtractionCli(
        scanner=ScalaFileScanner(),
        parser=ScalaTreeSitterParser(),
        serializer=AstSerializer(),
        symbol_extractor=SymbolExtractor(),
        relation_extractor=RelationExtractor(),
    )
    exit_code: int = extraction_cli.run(
        source=source,
        output=ast_root,
        overwrite=True,
    )
    if exit_code == 0:
        print(f"  [OK] AST geschrieben nach {ast_root}")
        return True
    print(f"  [!] Extraktion mit Fehlern abgeschlossen (siehe {ast_root}/manifest.json)")
    return True


def run_neo4j_import(ast_root: Path, reset: bool) -> bool:
    """Import the AST JSON into Neo4j. Returns True on success."""
    print("  -> Importiere in Neo4j ...")
    try:
        with Neo4jConnection(Neo4jSettings.from_env()) as connection:
            connection.verify_connectivity()
            repository = Neo4jGraphRepository(connection)
            if reset:
                repository.clear_graph()
            repository.create_constraints()
            summary = AstJsonImporter(repository).import_directory(ast_root)
        print(
            f"  [OK] Neo4j: {summary.imported_files}/{summary.total_files} Dateien "
            f"importiert"
        )
        if summary.has_errors:
            print(f"    [!] {len(summary.failed_files)} Datei(en) fehlgeschlagen")
        return True
    except Exception as error:
        print(f"  [FEHLER] Neo4j nicht erreichbar oder Fehler: {error}")
        print("    Tipp: 'docker compose up -d neo4j' und Zugangsdaten in .env prüfen.")
        return False


def run_chroma_import(ast_root: Path, reset: bool) -> bool:
    """Embed the symbols and store them in ChromaDB. Returns True on success."""
    print("  -> Embedde Symbole und importiere in ChromaDB (Gemini) ...")
    try:
        repository = ChromaVectorRepository(ChromaSettings.from_env())
        embedding_provider = LlamaIndexGeminiEmbeddingProvider(
            GeminiEmbeddingSettings.from_env()
        )
        importer = AstVectorImporter(
            repository=repository,
            embedding_provider=embedding_provider,
        )
        summary = importer.import_directory(ast_root, reset=reset)
        if summary.has_errors:
            print(
                f"  [!] ChromaDB: {summary.imported_chunks}/{summary.total_chunks} "
                f"Chunks gespeichert"
            )
            print(f"    {len(summary.failed_files)} Batch/Datei fehlgeschlagen:")
            for failed_file in summary.failed_files[:5]:
                print(f"    - {failed_file['path']}: {failed_file['error']}")
            remaining_errors: int = len(summary.failed_files) - 5
            if remaining_errors > 0:
                print(f"    ... plus {remaining_errors} weitere Fehler")
            return False
        print(
            f"  [OK] ChromaDB: {summary.imported_chunks}/{summary.total_chunks} Chunks "
            f"gespeichert"
        )
        return True
    except ImportError as error:
        print(f"  [FEHLER] Abhängigkeit fehlt: {error}")
        print("    Tipp: 'pip install -r requirements.txt' ausführen.")
        return False
    except Exception as error:
        print(f"  [FEHLER] ChromaDB-Import fehlgeschlagen: {error}")
        print("    Tipp: 'docker compose up -d chroma' und GEMINI_SECRET_KEY prüfen.")
        return False


def reset_neo4j_data() -> bool:
    """Delete all graph nodes and relationships from Neo4j."""
    print("  -> Loesche Neo4j-Graph ...")
    try:
        with Neo4jConnection(Neo4jSettings.from_env()) as connection:
            connection.verify_connectivity()
            repository = Neo4jGraphRepository(connection)
            repository.clear_graph()
        print("  [OK] Neo4j-Graph geloescht.")
        return True
    except Exception as error:
        print(f"  [FEHLER] Neo4j konnte nicht geloescht werden: {error}")
        print("    Tipp: 'docker compose up -d neo4j' und Zugangsdaten in .env pruefen.")
        return False


def reset_chroma_data() -> bool:
    """Delete and recreate the configured ChromaDB collection."""
    print("  -> Loesche ChromaDB-Collection ...")
    try:
        repository = ChromaVectorRepository(ChromaSettings.from_env())
        repository.reset_collection()
        print(
            "  [OK] ChromaDB-Collection "
            f"'{repository.settings.collection}' geloescht und leer neu angelegt."
        )
        return True
    except ImportError as error:
        print(f"  [FEHLER] Abhaengigkeit fehlt: {error}")
        print("    Tipp: 'pip install -r requirements.txt' ausfuehren.")
        return False
    except Exception as error:
        print(f"  [FEHLER] ChromaDB konnte nicht geloescht werden: {error}")
        print("    Tipp: 'docker compose up -d chroma' und CHROMA_HOST/CHROMA_PORT pruefen.")
        return False


def reset_backend_data(use_neo4j: bool, use_chroma: bool) -> bool:
    """Reset selected persistent backends."""
    print("\n=== Daten zuruecksetzen ===")
    results: list[bool] = []
    if use_neo4j:
        results.append(reset_neo4j_data())
    if use_chroma:
        results.append(reset_chroma_data())
    if not results:
        print("  Keine Datenbank ausgewaehlt.")
        return False
    if all(results):
        print("=== Reset abgeschlossen ===\n")
        return True
    print("=== Reset mit Fehlern abgeschlossen ===\n")
    return False


def index_codebase(
    source: Path,
    ast_root: Path,
    use_neo4j: bool,
    use_chroma: bool,
    reset: bool,
) -> None:
    """Run the full ingest pipeline: extract -> Neo4j -> ChromaDB."""
    print("\n=== Indexierung ===")
    if not run_extraction(source, ast_root):
        return
    import_results: list[bool] = []
    if use_neo4j:
        import_results.append(run_neo4j_import(ast_root, reset=reset))
    if use_chroma:
        import_results.append(run_chroma_import(ast_root, reset=reset))
    if import_results and not all(import_results):
        print("=== Indexierung mit Fehlern abgeschlossen ===\n")
        return
    print("=== Indexierung abgeschlossen ===\n")


# ----------------------------------------------------------------------------
# Question answering
# ----------------------------------------------------------------------------


def print_response(response: OrchestratorResponse) -> None:
    """Render an orchestrator response in a readable terminal format."""
    print()
    if response.answer is not None:
        print(response.answer)
        print()
        return

    print(
        f"  Semantische Treffer: {len(response.semantic_hits)} | "
        f"Graph-Relationen: {len(response.graph_relations)} | "
        f"Snippets: {len(response.snippets)}"
    )
    for snippet in response.snippets[:5]:
        location: str = str(snippet.metadata.get("fqn") or snippet.metadata.get("name") or snippet.symbol_id)
        path: str = str(snippet.metadata.get("relative_path", ""))
        score: str = f"{snippet.score:.3f}" if snippet.score is not None else "-"
        print(f"   {snippet.rank:>2}. [{snippet.source}] {location}  ({path}, score={score})")
    for warning in response.warnings:
        print(f"   [!] {warning}")
    print(
        "\n  Hinweis: Es ist noch kein LLM angebunden. Der zusammengebaute Prompt "
        "(response.prompt) ist bereit, um an Gemini übergeben zu werden."
    )
    print()


def ask_loop(top_k: int, max_neighbors: int, max_snippets: int) -> None:
    """Open the backends once and answer questions until the user exits."""
    print("\n=== Fragen stellen (leer/'exit' zum Beenden) ===")
    try:
        vector_repository = ChromaVectorRepository(ChromaSettings.from_env())
        embedding_provider = LlamaIndexGeminiEmbeddingProvider(
            GeminiEmbeddingSettings.from_env()
        )
        answer_provider = GeminiAnswerProvider(GeminiGenerationSettings.from_env())
    except ImportError as error:
        print(f"  [FEHLER] Abhängigkeit fehlt: {error}")
        print("    Tipp: 'pip install -r requirements.txt' ausführen.")
        return
    except Exception as error:
        print(f"  [FEHLER] ChromaDB/Gemini nicht bereit: {error}")
        print("    Tipp: 'docker compose up -d chroma' und GEMINI_SECRET_KEY prüfen.")
        return

    try:
        with Neo4jConnection(Neo4jSettings.from_env()) as connection:
            connection.verify_connectivity()
            orchestrator = CodeQuestionOrchestrator(
                embedding_provider=embedding_provider,
                vector_repository=vector_repository,
                graph_repository=GraphContextRepository(connection),
                answer_provider=answer_provider,
            )
            while True:
                query: str = input("\nFrage> ").strip()
                if not query or query.lower() in {"exit", "quit", "back"}:
                    break
                try:
                    response = orchestrator.answer(
                        query=query,
                        top_k=top_k,
                        max_neighbors=max_neighbors,
                        max_snippets=max_snippets,
                    )
                    print_response(response)
                except Exception as error:
                    print(f"  [FEHLER] Frage fehlgeschlagen: {error}")
    except Exception as error:
        print(f"  [FEHLER] Neo4j nicht erreichbar: {error}")
        print("    Tipp: 'docker compose up -d neo4j' und Zugangsdaten in .env prüfen.")


def answer_single(
    query: str,
    top_k: int,
    max_neighbors: int,
    max_snippets: int,
) -> int:
    """Answer one question (non-interactive). Returns a process exit code."""
    try:
        vector_repository = ChromaVectorRepository(ChromaSettings.from_env())
        embedding_provider = LlamaIndexGeminiEmbeddingProvider(
            GeminiEmbeddingSettings.from_env()
        )
        answer_provider = GeminiAnswerProvider(GeminiGenerationSettings.from_env())
        with Neo4jConnection(Neo4jSettings.from_env()) as connection:
            connection.verify_connectivity()
            orchestrator = CodeQuestionOrchestrator(
                embedding_provider=embedding_provider,
                vector_repository=vector_repository,
                graph_repository=GraphContextRepository(connection),
                answer_provider=answer_provider,
            )
            response = orchestrator.answer(
                query=query,
                top_k=top_k,
                max_neighbors=max_neighbors,
                max_snippets=max_snippets,
            )
        print_response(response)
        return 0
    except Exception as error:
        print(f"[FEHLER]: {error}")
        return 1


# ----------------------------------------------------------------------------
# Interactive menu
# ----------------------------------------------------------------------------


def interactive_menu() -> None:
    """Drive the whole tool through a simple terminal menu."""
    print("==============================================")
    print(" Graphbased-AI – Scala-Codebase verstehen")
    print("==============================================")

    while True:
        print("\nWas möchtest du tun?")
        print("  1) Codebase indexieren (extract -> Neo4j -> ChromaDB)")
        print("  2) Fragen stellen")
        print("  3) Neo4j + ChromaDB zuruecksetzen")
        print("  4) Beenden")
        choice: str = input("Auswahl> ").strip()

        if choice == "1":
            raw_path: str = input("Pfad zur Scala-Codebase> ").strip().strip('"')
            if not raw_path:
                print("  Kein Pfad angegeben.")
                continue
            index_codebase(
                source=Path(raw_path),
                ast_root=DEFAULT_AST_ROOT,
                use_neo4j=True,
                use_chroma=True,
                reset=True,
            )
        elif choice == "2":
            ask_loop(top_k=5, max_neighbors=20, max_snippets=12)
        elif choice == "3":
            print(
                "\nAchtung: Das loescht alle analysierten Daten in Neo4j "
                "und die konfigurierte ChromaDB-Collection."
            )
            confirmation: str = input("Zum Bestaetigen RESET eingeben> ").strip()
            if confirmation != "RESET":
                print("  Abgebrochen.")
                continue
            reset_backend_data(use_neo4j=True, use_chroma=True)
        elif choice in {"4", "exit", "quit"}:
            print("Tschüss!")
            return
        else:
            print("  Ungültige Auswahl.")


# ----------------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------------


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Graphbased-AI: Scala-Codebase indexieren und befragen.",
    )
    subcommands = parser.add_subparsers(dest="command")

    index_parser = subcommands.add_parser(
        "index",
        help="Codebase extrahieren und in Neo4j + ChromaDB importieren.",
    )
    index_parser.add_argument("--source", required=True, type=Path, help="Scala-Projekt-Root.")
    index_parser.add_argument(
        "--ast-root",
        type=Path,
        default=DEFAULT_AST_ROOT,
        help="Zielverzeichnis für die AST-JSONs.",
    )
    index_parser.add_argument("--skip-neo4j", action="store_true", help="Neo4j-Import überspringen.")
    index_parser.add_argument("--skip-chroma", action="store_true", help="ChromaDB-Import überspringen.")
    index_parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Bestehende Daten nicht löschen (inkrementell).",
    )

    ask_parser = subcommands.add_parser("ask", help="Eine Frage zur Codebase stellen.")
    ask_parser.add_argument("--query", required=True, help="Natürlichsprachliche Frage.")
    ask_parser.add_argument("--top-k", type=int, default=5)
    ask_parser.add_argument("--max-neighbors", type=int, default=20)
    ask_parser.add_argument("--max-snippets", type=int, default=12)

    reset_parser = subcommands.add_parser(
        "reset",
        help="Neo4j-Graph und ChromaDB-Collection loeschen.",
    )
    reset_parser.add_argument(
        "--yes",
        action="store_true",
        help="Bestaetigt das Loeschen ohne interaktive Rueckfrage.",
    )
    reset_parser.add_argument(
        "--skip-neo4j",
        action="store_true",
        help="Neo4j nicht loeschen.",
    )
    reset_parser.add_argument(
        "--skip-chroma",
        action="store_true",
        help="ChromaDB nicht loeschen.",
    )

    return parser


def main() -> int:
    _force_utf8_output()
    load_env_file(PROJECT_ROOT / ".env")
    parser = build_argument_parser()
    arguments = parser.parse_args()

    if arguments.command == "index":
        index_codebase(
            source=arguments.source,
            ast_root=arguments.ast_root,
            use_neo4j=not arguments.skip_neo4j,
            use_chroma=not arguments.skip_chroma,
            reset=not arguments.no_reset,
        )
        return 0

    if arguments.command == "ask":
        return answer_single(
            query=arguments.query,
            top_k=arguments.top_k,
            max_neighbors=arguments.max_neighbors,
            max_snippets=arguments.max_snippets,
        )

    if arguments.command == "reset":
        if not arguments.yes:
            print("Reset abgebrochen. Zum Loeschen bitte '--yes' angeben.")
            return 1
        success = reset_backend_data(
            use_neo4j=not arguments.skip_neo4j,
            use_chroma=not arguments.skip_chroma,
        )
        return 0 if success else 1

    # No subcommand -> interactive mode.
    try:
        interactive_menu()
    except (KeyboardInterrupt, EOFError):
        print("\nAbgebrochen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
