# Backend

Python-Backend von Graphbased-AI.

Hier entstehen Codeanalyse (Tree-sitter), Aufbau des Wissensgraphen (Neo4j / NetworkX),
semantische Suche (ChromaDB), die LLM-Orchestrierung (Gemini über LlamaIndex / LangChain)
sowie die API-Schicht (FastAPI).

> **Status:** Schritt 1 (Tree-sitter-Extraktion) ist umgesetzt. Graph-Erstellung,
> Vektorsuche, LLM-Orchestrierung und API-Schicht folgen.

Gemäß den Projektfestlegungen werden Parsing, Graph-Erstellung, Vektorsuche, LLM-Orchestrierung
und API-Schicht modular und getrennt aufgebaut. Python-Abhängigkeiten werden mit fester Version
in `requirements.txt` festgelegt.

## Extractor (`backend/extractor/`)

Liest eine Scala-Codebase ein und schreibt pro Datei einen graph-fertigen
AST + Basis-Symbole (package, import, object, class, trait, enum, function) als JSON.

Die Verantwortlichkeiten sind getrennt:

- `scanner.py` – findet `.scala`-Dateien und überspringt Build-/Tooling-Ordner.
- `parser.py` – Tree-sitter-Wrapper für den konfigurierten Scala-Parser.
- `ast_serializer.py` – serialisiert Tree-sitter-Knoten in JSON-fähige Dataclasses.
- `symbols.py` – extrahiert Basis-Symbole aus dem AST.
- `models.py` – typisierte Datenmodelle.
- `cli.py` – Kommandozeilen-Einstieg.

Ausführen:

```bash
python -m backend.extractor.cli --source <scala-projekt> --output build/ast --overwrite
```

Ergebnis: `build/ast/manifest.json` (Übersicht inkl. Fehlerliste und Tool-Versionen)
und `build/ast/files/**/<Datei>.scala.json` (AST + Symbole je Datei).

Tests:

```bash
python -m unittest discover -s backend/tests
```
