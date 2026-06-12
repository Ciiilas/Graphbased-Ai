"""HTTP API for the Graphbased-AI frontend."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
from backend.orchestrator.service import CodeQuestionOrchestrator
from backend.vector.config import (
    ChromaSettings,
    GeminiEmbeddingSettings,
    GeminiGenerationSettings,
)
from backend.vector.embeddings import LlamaIndexGeminiEmbeddingProvider
from backend.vector.importer import AstVectorImporter
from backend.vector.repository import ChromaVectorRepository
from main import DEFAULT_AST_ROOT, PROJECT_ROOT, load_env_file


load_env_file(PROJECT_ROOT / ".env")

UPLOAD_ROOT: Path = PROJECT_ROOT / "local-data" / "uploads"

app = FastAPI(title="Graphbased-AI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IndexPathRequest(BaseModel):
    source_path: str = Field(..., min_length=1)
    ast_root: str | None = None
    use_neo4j: bool = True
    use_chroma: bool = True
    reset: bool = True


class IndexResponse(BaseModel):
    ok: bool
    source_path: str
    ast_root: str
    warnings: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=30)
    max_neighbors: int = Field(default=20, ge=0, le=200)
    max_snippets: int = Field(default=12, ge=1, le=50)
    generate: bool = True


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/index", response_model=IndexResponse)
def index_from_path(request: IndexPathRequest) -> IndexResponse:
    source_path = Path(request.source_path).expanduser().resolve()
    ast_root = Path(request.ast_root).expanduser().resolve() if request.ast_root else DEFAULT_AST_ROOT
    return _run_index(
        source_path=source_path,
        ast_root=ast_root,
        use_neo4j=request.use_neo4j,
        use_chroma=request.use_chroma,
        reset=request.reset,
    )


@app.post("/api/upload-index", response_model=IndexResponse)
async def upload_and_index(
    files: Annotated[list[UploadFile], File()],
    reset: Annotated[bool, Form()] = True,
    use_neo4j: Annotated[bool, Form()] = True,
    use_chroma: Annotated[bool, Form()] = True,
) -> IndexResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    upload_dir = UPLOAD_ROOT / uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=True)

    written_files = 0
    for upload in files:
        relative_path = _safe_upload_path(upload.filename or upload_dir.name)
        if relative_path is None:
            continue
        target_path = upload_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(await upload.read())
        written_files += 1

    if written_files == 0:
        raise HTTPException(status_code=400, detail="Upload did not contain usable files.")

    return _run_index(
        source_path=upload_dir,
        ast_root=DEFAULT_AST_ROOT,
        use_neo4j=use_neo4j,
        use_chroma=use_chroma,
        reset=reset,
    )


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    try:
        vector_repository = ChromaVectorRepository(ChromaSettings.from_env())
        embedding_provider = LlamaIndexGeminiEmbeddingProvider(
            GeminiEmbeddingSettings.from_env()
        )
        answer_provider = (
            GeminiAnswerProvider(GeminiGenerationSettings.from_env())
            if request.generate
            else None
        )
        with Neo4jConnection(Neo4jSettings.from_env()) as connection:
            connection.verify_connectivity()
            orchestrator = CodeQuestionOrchestrator(
                embedding_provider=embedding_provider,
                vector_repository=vector_repository,
                graph_repository=GraphContextRepository(connection),
                answer_provider=answer_provider,
            )
            response = orchestrator.answer(
                query=request.query,
                top_k=request.top_k,
                max_neighbors=request.max_neighbors,
                max_snippets=request.max_snippets,
                generate=request.generate,
            )
            return response.to_dict()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/api/graph", response_model=GraphResponse)
def graph(limit: int = 250) -> GraphResponse:
    bounded_limit = max(1, min(limit, 1000))
    try:
        with Neo4jConnection(Neo4jSettings.from_env()) as connection:
            connection.verify_connectivity()
            nodes = connection.execute_read(_graph_nodes_query(), {"limit": bounded_limit})
            edges = connection.execute_read(_graph_edges_query(), {"limit": bounded_limit * 3})
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


def _run_index(
    source_path: Path,
    ast_root: Path,
    use_neo4j: bool,
    use_chroma: bool,
    reset: bool,
) -> IndexResponse:
    if not source_path.exists() or not source_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Source path does not exist or is not a directory: {source_path}",
        )

    extractor = ScalaExtractionCli(
        scanner=ScalaFileScanner(),
        parser=ScalaTreeSitterParser(),
        serializer=AstSerializer(),
        symbol_extractor=SymbolExtractor(),
        relation_extractor=RelationExtractor(),
    )
    exit_code = extractor.run(source=source_path, output=ast_root, overwrite=True)
    warnings: list[str] = []
    if exit_code != 0:
        warnings.append("Extraction finished with file-level errors. Check manifest.json.")

    if use_neo4j:
        with Neo4jConnection(Neo4jSettings.from_env()) as connection:
            connection.verify_connectivity()
            repository = Neo4jGraphRepository(connection)
            if reset:
                repository.clear_graph()
            repository.create_constraints()
            summary = AstJsonImporter(repository).import_directory(ast_root)
        if summary.has_errors:
            warnings.append(f"Neo4j import skipped {len(summary.failed_files)} file(s).")

    if use_chroma:
        vector_repository = ChromaVectorRepository(ChromaSettings.from_env())
        embedding_provider = LlamaIndexGeminiEmbeddingProvider(
            GeminiEmbeddingSettings.from_env()
        )
        summary = AstVectorImporter(
            repository=vector_repository,
            embedding_provider=embedding_provider,
        ).import_directory(ast_root, reset=reset)
        if summary.has_errors:
            warnings.append(f"Chroma import skipped {len(summary.failed_files)} file(s).")

    return IndexResponse(
        ok=True,
        source_path=str(source_path),
        ast_root=str(ast_root),
        warnings=warnings,
    )


def _safe_upload_path(filename: str) -> Path | None:
    parts = [
        part
        for part in PurePosixPath(filename.replace("\\", "/")).parts
        if part not in {"", ".", ".."}
    ]
    if not parts:
        return None
    path = Path(*parts)
    if path.is_absolute():
        return None
    return path


def _graph_nodes_query() -> str:
    return """
    MATCH (node)
    WHERE node:File OR node:Symbol OR node:ExternalImport OR node:Call
    RETURN
      coalesce(node.id, node.path, elementId(node)) AS id,
      labels(node) AS labels,
      coalesce(node.name, node.fqn, node.path, node.callee_name, node.id) AS label,
      properties(node) AS properties
    LIMIT $limit
    """


def _graph_edges_query() -> str:
    return """
    MATCH (source)-[relationship]->(target)
    WHERE
      (source:File OR source:Symbol OR source:ExternalImport OR source:Call)
      AND (target:File OR target:Symbol OR target:ExternalImport OR target:Call)
    RETURN
      coalesce(source.id, source.path, elementId(source)) AS source,
      coalesce(target.id, target.path, elementId(target)) AS target,
      type(relationship) AS type,
      properties(relationship) AS properties
    LIMIT $limit
    """
