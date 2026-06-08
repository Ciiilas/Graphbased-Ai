# Improvement.md — Was fehlt & nächste Schritte

> Stand: nach Schritt 1 (Tree-sitter-Extraktion) und Schritt 2 (Neo4j-Import).
> Dieses Dokument beschreibt, was aktuell **noch fehlt**, mit Schwerpunkt auf den
> Graph-Beziehungen **IMPORTS**, **CALLS** und **DEPENDS_ON**.

## Ausgangslage (was es schon gibt)

- **Extractor** (`backend/extractor/`): parst Scala mit Tree-sitter und schreibt pro
  Datei JSON (AST + Basis-Symbole: `package`, `import`, `object`, `class`, `trait`,
  `enum`, `function`).
- **Neo4j-Layer** (`backend/db/`): importiert die JSONs idempotent in den Graphen.
- **Aktuelles Graph-Modell:** nur **zwei** Knotentypen und **eine** Beziehung:

  ```
  (:File {path, absolute_path, has_errors})
  (:Symbol {id, kind, name, source_path, start_byte, end_byte})
  (:File)-[:DECLARES]->(:Symbol)
  ```

  Verifiziert am Testprojekt: 31 Files, 287 Symbols, 287 DECLARES.

Das heißt: Der Graph weiß **was** wo deklariert wird, aber noch nicht, **wie die
Teile zusammenhängen**. Genau das fehlt.

---

## Schwerpunkt: fehlende Beziehungen

Aktuell sind `import`-Anweisungen nur als flache `Symbol {kind:'import'}`-Knoten
abgelegt (der rohe Import-Text als `name`). Aufrufe und Abhängigkeiten gibt es
gar nicht. Ziel ist ein Graph, der Architektur abbildbar macht.

### 1. IMPORTS — `(:File)-[:IMPORTS]->(:Symbol | :ExternalImport)`

**Was fehlt:** Imports sind nicht aufgelöst. `import de.htwg.se.muehle.util.Command`
sollte als Kante auf das **im Projekt deklarierte** `Command`-Symbol zeigen, nicht
als Text-Knoten herumliegen.

**Grammatik (tree-sitter-scala):** Ein `import_declaration` besteht aus
`identifier`-Pfadsegmenten und optional:
- `namespace_selectors` für `import a.b.{A, B}` (mehrere Namen),
- `namespace_wildcard` für `import a.b.*` / `import a.b._`.

**Vorgehen:**
1. **Symbol-Index aufbauen:** Für jedes Typ-Symbol (`class`/`trait`/`object`/`enum`)
   den **voll qualifizierten Namen (FQN)** bilden = Paket der Datei + `.` + Name.
   (Das Paket pro Datei liegt bereits als `package`-Symbol vor.)
2. **Import expandieren** zu konkreten FQNs:
   - `import a.b.{A, B}` → `a.b.A`, `a.b.B`
   - `import a.b.C` → `a.b.C`
   - `import a.b.*` → alle Symbole im Paket `a.b`
3. **Auflösen:** FQN gegen den Symbol-Index matchen → `IMPORTS`-Kante auf das
   Zielsymbol. Treffer = interne Abhängigkeit.
4. **Externe Imports** (`scala.*`, `java.*`, `play.api.*`, `com.google.*` …) finden
   keinen internen Treffer → als `(:ExternalImport {fqn, library})`-Knoten ablegen
   oder bewusst überspringen (Entscheidung dokumentieren).

**Ziel-Cypher (Beispiel):**
```cypher
MATCH (f:File)-[:IMPORTS]->(s:Symbol)
RETURN f.path, s.kind, s.name
```

### 2. CALLS — `(:Symbol {kind:'function'})-[:CALLS]->(:Symbol {kind:'function'})`

**Was fehlt:** Aufrufbeziehungen komplett. Das ist die wertvollste, aber auch
schwierigste Beziehung (braucht Namensauflösung).

**Grammatik:** `call_expression` hat als Funktionsteil entweder
- einen `identifier` → direkter Aufruf `notifyObservers(...)`, oder
- ein `field_expression` (`receiver.method`) → `undoManager.doStep(...)`
plus einen `arguments`-Knoten.

**Vorgehen:**
1. **Aufrufer bestimmen:** beim Traversieren die umschließende
   `function_definition` mitführen (oder per Byte-Range zuordnen) → das ist die
   `CALLS`-Quelle.
2. **Aufgerufenen Namen extrahieren:** bei `identifier` der Name selbst, bei
   `field_expression` der letzte `identifier` (Methodenname) + optional der
   Receiver.
3. **Auflösen (das harte Teil):** Welche `function`-Node ist gemeint? Tree-sitter
   liefert keine Typ-/Scope-Auflösung. Pragmatischer MVP:
   - **Heuristik nach Name:** Kante auf alle `function`-Symbole mit passendem Namen,
     bevorzugt im selben Typ/derselben Datei oder über `IMPORTS` erreichbar.
   - **Unauflösbare Aufrufe** als Eigenschaft markieren
     (`(:Call {callee_name, resolved:false})`) statt zu raten, damit die Qualität
     messbar bleibt.
4. **Genauigkeit verbessern** später über die Containment-Hierarchie (siehe unten)
   und Import-Scope.

**Ziel-Cypher (Beispiel — Wer ruft `notifyObservers`?):**
```cypher
MATCH (caller:Symbol)-[:CALLS]->(callee:Symbol {name:'notifyObservers'})
RETURN caller.name, caller.source_path
```

### 3. DEPENDS_ON — `(:File)-[:DEPENDS_ON]->(:File)`

**Was fehlt:** Datei-/Modul-Abhängigkeiten. Diese Beziehung ist **abgeleitet** aus
IMPORTS und CALLS und macht Impact-Analysen einfach.

**Vorgehen:** Datei A `DEPENDS_ON` Datei B, wenn
- A ein Symbol importiert, das in B deklariert ist, **oder**
- eine Funktion in A eine Funktion in B aufruft.

Lässt sich nach dem Aufbau von IMPORTS/CALLS per Cypher materialisieren:
```cypher
MATCH (a:File)-[:DECLARES|IMPORTS]->()-[:CALLS|*0..1]->(t)
MATCH (b:File)-[:DECLARES]->(t)
WHERE a <> b
MERGE (a)-[:DEPENDS_ON]->(b)
```
(Exakte Query je nach finalem Modell — Kernidee: Abhängigkeiten aus den feineren
Kanten aggregieren.)

---

## Weitere strukturelle Lücken (Voraussetzung für gute CALLS/IMPORTS)

- **Keine Containment-Hierarchie.** Funktionen hängen flach an der `File`, nicht an
  ihrer Klasse/ihrem Object/Trait. Ziel:
  `(:File)-[:DECLARES]->(:Symbol{kind:'class'})-[:DECLARES]->(:Symbol{kind:'function'})`.
  Ableitbar über die `template_body`-Verschachtelung bzw. Byte-Range-Containment.
  Wichtig, weil Methodenauflösung „welche Klasse?" braucht.
- **Keine Vererbung.** `extends_clause` (`class C extends Observable`) wird nicht
  ausgewertet → fehlende `(:Symbol)-[:EXTENDS]->(:Symbol)`-Kanten. Für
  Architekturverständnis (Interfaces/Traits) zentral.
- **Fehlende Symboltypen:** `val`/`var` (Felder), `type`, `given` werden nicht
  extrahiert (`val_definition`, `var_definition`, `type_definition`,
  `given_definition` in `SYMBOL_NODE_TYPES`).
- **Fehlende Funktions-Metadaten:** Parameter, Rückgabetyp, Sichtbarkeit/Modifier
  sind nicht erfasst (nur Name + Byte-Range).

---

## Größere Bausteine laut README (noch nicht begonnen)

- **ChromaDB / Embeddings / semantische Suche** — Codeabschnitte als Vektoren.
- **LlamaIndex oder LangChain** — Retrieval-Orchestrierung über Graph + Vektor-DB.
- **Gemini (LLM)** — natürlichsprachliche Antworten/Erklärungen.
- **FastAPI** — API-Schicht (Analyse-, Such-, Chat-Endpunkte, JSON).
- **React-Frontend** (React Flow / Cytoscape.js) — Graph-Visualisierung.
- **Inkrementelles Update** — README-Ziel: Änderungen analysieren, ohne die ganze
  Codebase neu einzulesen (aktuell wird immer alles neu importiert).

---

## Qualität / Kleinkram

- **Voller AST je Datei** wird als JSON gespeichert ([ast_serializer.py](backend/extractor/ast_serializer.py)) —
  für große Codebases groß; später auf relevante Knoten reduzieren.
- **`manifest.json` wird beim Import ignoriert** — könnte `has_errors`/Versionen prüfen.
- **Kein Live-Integrationstest** gegen ein laufendes Neo4j (analog zum Extractor-CLI-Test).

---

## Vorgeschlagene Reihenfolge

1. **Containment** (`class`/`object`/`trait` → enthaltene `function`) — Fundament.
2. **IMPORTS** auflösen (Symbol-Index + FQN-Matching) — gut machbar, hoher Wert.
3. **EXTENDS** (Vererbung aus `extends_clause`) — klein, hoher Architekturwert.
4. **CALLS** (Heuristik + `resolved`-Flag) — größter Aufwand, iterativ verbessern.
5. **DEPENDS_ON** aus IMPORTS/CALLS aggregieren.
6. Danach: FastAPI-Endpunkte zum Abfragen des Graphen, dann ChromaDB/LLM/Frontend.

Schritte 1–5 erweitern nur Extractor (`symbols.py` bzw. ein neuer
`relations.py`) und den Neo4j-`repository.py` — passend zur modularen Trennung aus
AGENTS.md.
