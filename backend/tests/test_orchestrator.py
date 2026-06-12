from __future__ import annotations

import unittest

from backend.orchestrator.assembler import ContextAssembler
from backend.orchestrator.graph import GraphContextRepository
from backend.orchestrator.models import (
    GraphExpansion,
    GraphNeighbor,
    GraphRelation,
    SemanticHit,
)
from backend.orchestrator.service import CodeQuestionOrchestrator
from backend.vector.repository import SearchResult


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _text in texts]

    def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return [0.1, 0.2]


class FakeAnswerProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_answer(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "A calls B through directB."


class FakeVectorRepository:
    def __init__(self) -> None:
        self.query_embedding: list[float] | None = None
        self.limit: int | None = None
        self.requested_ids: list[str] = []
        self.query_results: list[SearchResult] = [
            SearchResult(
                id="symbol-a",
                text="def semanticA(): Unit = directB()",
                score=0.94,
                metadata={
                    "symbol_id": "symbol-a",
                    "relative_path": "A.scala",
                    "kind": "function",
                },
            ),
            SearchResult(
                id="symbol-c",
                text="def semanticC(): Unit = ()",
                score=0.72,
                metadata={
                    "symbol_id": "symbol-c",
                    "relative_path": "C.scala",
                    "kind": "function",
                },
            ),
        ]
        self.snippets_by_id: dict[str, SearchResult] = {
            "symbol-b": SearchResult(
                id="symbol-b",
                text="def directB(): Unit = ()",
                score=None,
                metadata={
                    "symbol_id": "symbol-b",
                    "relative_path": "B.scala",
                    "kind": "function",
                },
            ),
            "symbol-d": SearchResult(
                id="symbol-d",
                text="class DependentD",
                score=None,
                metadata={
                    "symbol_id": "symbol-d",
                    "relative_path": "D.scala",
                    "kind": "class",
                },
            ),
        }

    def query(self, query_embedding: list[float], limit: int) -> list[SearchResult]:
        self.query_embedding = query_embedding
        self.limit = limit
        return self.query_results[:limit]

    def get_by_ids(self, ids: list[str]) -> list[SearchResult]:
        self.requested_ids.extend(ids)
        return [
            self.snippets_by_id[item_id]
            for item_id in ids
            if item_id in self.snippets_by_id
        ]


class EmptyVectorRepository(FakeVectorRepository):
    def __init__(self) -> None:
        super().__init__()
        self.query_results = []


class FakeGraphRepository:
    def __init__(self) -> None:
        self.seed_symbol_ids: list[str] = []
        self.max_neighbors: int | None = None

    def expand(
        self,
        seed_symbol_ids: list[str],
        max_neighbors: int,
    ) -> GraphExpansion:
        self.seed_symbol_ids = seed_symbol_ids
        self.max_neighbors = max_neighbors
        if not seed_symbol_ids:
            return GraphExpansion()
        return GraphExpansion(
            neighbors=[
                GraphNeighbor(symbol_id="symbol-b", reason="direct_graph"),
                GraphNeighbor(symbol_id="symbol-a", reason="direct_graph"),
                GraphNeighbor(symbol_id="symbol-d", reason="dependent_file"),
            ],
            relations=[
                GraphRelation(
                    type="CALLS",
                    source_id="symbol-a",
                    target_id="symbol-b",
                    source_kind="Symbol",
                    target_kind="Symbol",
                    direction="outgoing",
                ),
                GraphRelation(
                    type="DEPENDS_ON",
                    source_id="A.scala",
                    target_id="D.scala",
                    source_kind="File",
                    target_kind="File",
                    direction="outgoing",
                ),
            ],
        )


class FakeReadConnection:
    def __init__(self) -> None:
        self.reads: list[tuple[str, dict[str, object] | None]] = []

    def execute_read(
        self,
        query: str,
        parameters: dict[str, object] | None = None,
    ) -> list[dict[str, object]]:
        self.reads.append((query, parameters))
        if "CALLS|EXTENDS" in query:
            return [
                {
                    "neighbor": {
                        "id": "symbol-b",
                        "kind": "function",
                        "name": "directB",
                        "fqn": "sample.B.directB",
                        "source_path": "B.scala",
                    },
                    "relation": {
                        "type": "CALLS",
                        "source_id": "symbol-a",
                        "target_id": "symbol-b",
                        "source_kind": "Symbol",
                        "target_kind": "Symbol",
                        "direction": "outgoing",
                    },
                },
                {
                    "neighbor": {
                        "id": "symbol-b",
                        "kind": "function",
                        "name": "directB",
                        "fqn": "sample.B.directB",
                        "source_path": "B.scala",
                    },
                    "relation": {
                        "type": "CALLS",
                        "source_id": "symbol-a",
                        "target_id": "symbol-b",
                        "source_kind": "Symbol",
                        "target_kind": "Symbol",
                        "direction": "outgoing",
                    },
                },
            ]
        if "DEPENDS_ON" in query:
            return [
                {
                    "neighbor": {
                        "id": "symbol-d",
                        "kind": "class",
                        "name": "DependentD",
                        "fqn": "sample.D.DependentD",
                        "source_path": "D.scala",
                    },
                    "relation": {
                        "type": "DEPENDS_ON",
                        "source_id": "A.scala",
                        "target_id": "D.scala",
                        "source_kind": "File",
                        "target_kind": "File",
                        "direction": "outgoing",
                    },
                }
            ]
        return [
            {
                "relation": {
                    "type": "DECLARES",
                    "source_id": "A.scala",
                    "target_id": "symbol-a",
                    "source_kind": "File",
                    "target_kind": "Symbol",
                    "direction": "declares",
                }
            }
        ]


class CodeQuestionOrchestratorTest(unittest.TestCase):
    def test_answer_runs_query_embedding_and_uses_seed_symbol_ids(self) -> None:
        embedding_provider = FakeEmbeddingProvider()
        vector_repository = FakeVectorRepository()
        graph_repository = FakeGraphRepository()
        orchestrator = CodeQuestionOrchestrator(
            embedding_provider=embedding_provider,
            vector_repository=vector_repository,
            graph_repository=graph_repository,
        )

        response = orchestrator.answer(
            query="How does A call B?",
            top_k=2,
            max_neighbors=20,
            max_snippets=4,
        )

        self.assertEqual(embedding_provider.queries, ["How does A call B?"])
        self.assertEqual(vector_repository.query_embedding, [0.1, 0.2])
        self.assertEqual(vector_repository.limit, 2)
        self.assertEqual(graph_repository.seed_symbol_ids, ["symbol-a", "symbol-c"])
        self.assertEqual(graph_repository.max_neighbors, 20)
        self.assertIsNone(response.answer)

    def test_answer_ranks_semantic_hits_before_graph_neighbors(self) -> None:
        orchestrator = CodeQuestionOrchestrator(
            embedding_provider=FakeEmbeddingProvider(),
            vector_repository=FakeVectorRepository(),
            graph_repository=FakeGraphRepository(),
        )

        response = orchestrator.answer(
            query="How does A call B?",
            top_k=2,
            max_neighbors=20,
            max_snippets=4,
        )

        self.assertEqual(
            [snippet.symbol_id for snippet in response.snippets],
            ["symbol-a", "symbol-c", "symbol-b", "symbol-d"],
        )
        self.assertEqual(response.snippets[0].source, "semantic")
        self.assertEqual(response.snippets[2].source, "direct_graph")
        self.assertEqual(response.snippets[3].source, "dependent_file")

    def test_answer_prompt_includes_question_snippets_and_relations(self) -> None:
        orchestrator = CodeQuestionOrchestrator(
            embedding_provider=FakeEmbeddingProvider(),
            vector_repository=FakeVectorRepository(),
            graph_repository=FakeGraphRepository(),
        )

        response = orchestrator.answer(
            query="How does A call B?",
            top_k=2,
            max_neighbors=20,
            max_snippets=3,
        )

        self.assertIn("Question: How does A call B?", response.prompt)
        self.assertIn("def semanticA", response.prompt)
        self.assertIn("CALLS: symbol-a -> symbol-b", response.prompt)
        self.assertEqual(len(response.snippets), 3)

    def test_answer_handles_empty_semantic_results_without_crashing(self) -> None:
        vector_repository = EmptyVectorRepository()
        graph_repository = FakeGraphRepository()
        orchestrator = CodeQuestionOrchestrator(
            embedding_provider=FakeEmbeddingProvider(),
            vector_repository=vector_repository,
            graph_repository=graph_repository,
        )

        response = orchestrator.answer(
            query="What exists?",
            top_k=5,
            max_neighbors=20,
            max_snippets=12,
        )

        self.assertEqual(graph_repository.seed_symbol_ids, [])
        self.assertEqual(response.semantic_hits, [])
        self.assertEqual(response.snippets, [])
        self.assertIn("No semantic hits found.", response.warnings)

    def test_answer_uses_answer_provider_when_generation_is_enabled(self) -> None:
        answer_provider = FakeAnswerProvider()
        orchestrator = CodeQuestionOrchestrator(
            embedding_provider=FakeEmbeddingProvider(),
            vector_repository=FakeVectorRepository(),
            graph_repository=FakeGraphRepository(),
            answer_provider=answer_provider,
        )

        response = orchestrator.answer(
            query="How does A call B?",
            top_k=2,
            max_neighbors=20,
            max_snippets=3,
            generate=True,
        )

        self.assertEqual(response.answer, "A calls B through directB.")
        self.assertEqual(answer_provider.prompts, [response.prompt])

    def test_answer_skips_answer_provider_when_generation_is_disabled(self) -> None:
        answer_provider = FakeAnswerProvider()
        orchestrator = CodeQuestionOrchestrator(
            embedding_provider=FakeEmbeddingProvider(),
            vector_repository=FakeVectorRepository(),
            graph_repository=FakeGraphRepository(),
            answer_provider=answer_provider,
        )

        response = orchestrator.answer(
            query="How does A call B?",
            top_k=2,
            max_neighbors=20,
            max_snippets=3,
            generate=False,
        )

        self.assertIsNone(response.answer)
        self.assertEqual(answer_provider.prompts, [])


class ContextAssemblerTest(unittest.TestCase):
    def test_assembler_dedupes_and_caps_graph_neighbors(self) -> None:
        vector_repository = FakeVectorRepository()
        assembler = ContextAssembler(vector_repository)
        semantic_hits = [
            SemanticHit(
                symbol_id="symbol-a",
                text="def semanticA(): Unit = directB()",
                score=0.94,
                metadata={"symbol_id": "symbol-a", "relative_path": "A.scala"},
            )
        ]
        graph_expansion = GraphExpansion(
            neighbors=[
                GraphNeighbor(symbol_id="symbol-a", reason="direct_graph"),
                GraphNeighbor(symbol_id="symbol-b", reason="direct_graph"),
                GraphNeighbor(symbol_id="symbol-d", reason="dependent_file"),
            ],
            relations=[],
        )

        context = assembler.assemble(
            query="How?",
            semantic_hits=semantic_hits,
            graph_expansion=graph_expansion,
            max_snippets=2,
        )

        self.assertEqual(
            [snippet.symbol_id for snippet in context.snippets],
            ["symbol-a", "symbol-b"],
        )
        self.assertEqual(vector_repository.requested_ids, ["symbol-b"])


class GraphContextRepositoryTest(unittest.TestCase):
    def test_expand_dedupes_neighbors_and_relations(self) -> None:
        connection = FakeReadConnection()
        repository = GraphContextRepository(connection)

        expansion = repository.expand(["symbol-a"], max_neighbors=2)

        self.assertEqual(len(connection.reads), 3)
        self.assertEqual(
            [neighbor.symbol_id for neighbor in expansion.neighbors],
            ["symbol-b", "symbol-d"],
        )
        self.assertEqual(
            [
                (relation.type, relation.source_id, relation.target_id)
                for relation in expansion.relations
            ],
            [
                ("CALLS", "symbol-a", "symbol-b"),
                ("DEPENDS_ON", "A.scala", "D.scala"),
                ("DECLARES", "A.scala", "symbol-a"),
            ],
        )

    def test_expand_empty_seed_ids_skips_queries(self) -> None:
        connection = FakeReadConnection()
        repository = GraphContextRepository(connection)

        expansion = repository.expand([], max_neighbors=20)

        self.assertEqual(connection.reads, [])
        self.assertEqual(expansion.neighbors, [])
        self.assertEqual(expansion.relations, [])


if __name__ == "__main__":
    unittest.main()
