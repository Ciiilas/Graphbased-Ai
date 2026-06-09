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
AST + Basis-Symbole (package, import, object, class, trait, enum, function,
val, var, type, given) sowie Graph-Relationen als JSON.

Die Verantwortlichkeiten sind getrennt:

- `scanner.py` – findet `.scala`-Dateien und überspringt Build-/Tooling-Ordner.
- `parser.py` – Tree-sitter-Wrapper für den konfigurierten Scala-Parser.
- `ast_serializer.py` – serialisiert Tree-sitter-Knoten in JSON-fähige Dataclasses.
- `symbols.py` – extrahiert Basis-Symbole aus dem AST.
- `relations.py` – leitet Graph-Relationen aus AST und Symbolen ab.
- `models.py` – typisierte Datenmodelle.
- `cli.py` – Kommandozeilen-Einstieg.

### Relationen

`relations.py` erzeugt pro Datei folgende Kanten (jeweils auf interne Symbole
aufgelöst oder als `external_import` markiert):

- `DECLARES` – Datei/Symbol deklariert ein Symbol.
- `IMPORTS` – Import auf ein Symbol (inkl. Wildcard `._`/`.*` und Selektoren `.{A, B}`).
- `EXTENDS` – Vererbung inkl. `with`-Mixins und generischer Supertypen (`Command[A]` → `Command`).
- `CALLS` – Methodenaufruf. Quelle ist das **nächste umschließende Symbol** (Funktion, `val`/`var`
  oder Typ), sodass auch Aufrufe in Feld-Initializern und Klassenrümpfen erfasst werden.
  Paren-less Aufrufe (`a.method` ohne Klammern) sind in Scala nicht von Feldzugriffen unterscheidbar
  und werden mit `metadata.paren_free = true` markiert; unaufgelöste Aufrufe haben `target_kind = "call"`.
- `INSTANTIATES` – Objekt-Instanziierung (`new Typ(...)`) auf den Typ.
- `USES` – Typ-Referenzen in Signaturen (Parameter-, Rückgabe- und Feldtypen).
- `DEPENDS_ON` – datei-übergreifende Abhängigkeit, abgeleitet aus aufgelösten
  `IMPORTS`/`CALLS`/`INSTANTIATES`/`USES`.

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
