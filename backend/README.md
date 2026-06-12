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
AST + Basis-Symbole (package, import, object, class, trait, enum, enum_case,
function, val, var, type, given – inkl. abstrakter `*_declaration`-Member in
Traits/Interfaces) sowie Graph-Relationen als JSON.

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

#### Call-Auflösung

`CALLS` werden typ-bewusst aufgelöst: Der Receiver wird über eine Scope-Symboltabelle
(Parameter, `val`/`var`-Felder, Konstruktor-Parameter, `this`) auf ein Typ-Symbol getypt,
die Methode in dessen Membern **inkl. vererbter Member** (über die `EXTENDS`-Hierarchie) gesucht.
Verkettete Aufrufe (`a.b.c()`) werden rekursiv über Rückgabetypen aufgelöst, einfache Namen über
die Imports der Datei (`Simplename → FQN`). Greift das nicht, folgt ein namensbasierter Fallback.

Bekannte Grenzen (ohne vollständige Typinferenz nicht auflösbar): Methoden, die nur in der
Implementierung statt im Interface deklariert sind; unqualifizierte Enum-Cases außerhalb des Enums;
Konstruktor-Parameter hinter Annotationen wie `@Inject() (...)` (Tree-sitter-Parse-Limitierung).

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

## Vector Search (`backend/vector/`)

Liest die vom Extractor erzeugten AST-JSON-Dateien, baut daraus semantische
Code-Chunks und speichert deren Embeddings in ChromaDB. Die Embeddings werden
ueber LlamaIndex mit Gemini erzeugt; Neo4j ist fuer diesen Schritt technisch
nicht erforderlich.

Ausfuehren:

```bash
python -m backend.vector.cli import-ast --ast-root local-data/ast --reset
python -m backend.vector.cli search --query "Where is the controller initialized?" --limit 5
```

Hinweis: Diese Befehle erzeugen Gemini-Embedding-Anfragen. Unit-Tests verwenden
Fake-Embeddings und rufen Gemini nicht auf.

## Orchestrator (`backend/orchestrator/`)

Verbindet semantische Suche und Graph-Kontext zu einem Prompt fuer spaetere
LLM-Antworten. Der Orchestrator embeddded die Frage, holt Top-k Treffer aus
ChromaDB, erweitert diese Treffer ueber Neo4j-Relationen und baut daraus einen
deduplizierten, gerankten Kontext.

Ausfuehren:

```bash
python -m backend.orchestrator.cli ask --query "Wie laeuft ein Spielzug durch den Controller?" --top-k 5 --max-neighbors 20 --max-snippets 12
```

Die Ausgabe enthaelt aktuell `answer: null`, den fertigen `prompt`,
semantische Treffer, Graph-Relationen, Snippets und Warnungen. Ein Gemini-LLM
wird in diesem Schritt noch nicht aufgerufen; die Frage-Embeddings benoetigen
weiterhin den konfigurierten Embedding-Provider.
