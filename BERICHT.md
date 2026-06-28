# Bericht: Graphbased-AI

## 1. Projektueberblick

Graphbased-AI ist ein KI-gestuetztes Analysewerkzeug fuer grosse Scala-Codebases.
Das System liest eine Scala-Codebase ein, parst den Quellcode, extrahiert daraus
Symbole und Beziehungen, speichert diese Informationen als Wissensgraph und
ermoeglicht anschliessend semantische Suche sowie natuerlichsprachliche Fragen
ueber den Code.

Das Projekt ist bewusst als read-only Analysewerkzeug umgesetzt. Die analysierte
Scala-Codebase wird nicht veraendert. Das System erstellt nur abgeleitete Daten:
AST-JSON-Dateien, Graphdaten in Neo4j und Embeddings in ChromaDB.

Die zentrale Idee ist eine Kombination aus drei Perspektiven:

- syntaktisches Codeverstaendnis durch Tree-sitter
- strukturelles Codeverstaendnis durch einen Wissensgraphen in Neo4j
- semantisches Retrieval und Antwortgenerierung durch Embeddings, ChromaDB und Gemini

Dadurch soll das System nicht nur Textstellen finden, sondern auch erklaeren,
wie Klassen, Funktionen, Dateien und Abhaengigkeiten zusammenhaengen.

## 2. Verwendeter Tech-Stack

### Backend

Das Backend ist in Python umgesetzt und stellt Parsing, Graphimport,
Vektorsuche, RAG-Orchestrierung und HTTP-API bereit.

| Technologie                         |           Version | Verwendung                                               |
|-------------------------------------|------------------:|----------------------------------------------------------|
| Python                              | lokal ausgefuehrt | Backend-Sprache                                          |
| FastAPI                             |           0.115.6 | HTTP-API fuer Frontend, Indexierung, Chat und Graphdaten |
| Uvicorn                             |            0.34.0 | lokaler ASGI-Server fuer FastAPI                         |
| python-multipart                    |            0.0.20 | Upload von Projektordnern ueber die API                  |
| tree-sitter                         |            0.25.2 | generischer Parser-Unterbau                              |
| tree-sitter-scala                   |            0.26.0 | Scala-Grammatik fuer Tree-sitter                         |
| neo4j Python Driver                 |             6.2.0 | Verbindung zur Neo4j-Datenbank                           |
| chromadb                            |             1.5.9 | Zugriff auf die ChromaDB-Vektordatenbank                 |
| llama-index-core                    |           0.14.22 | Basis fuer LlamaIndex-Integration                        |
| llama-index-embeddings-google-genai |             0.5.1 | Gemini-Embeddings ueber LlamaIndex                       |
| google-genai                        |             2.8.0 | Gemini-Antwortgenerierung                                |

Die Python-Abhaengigkeiten sind in `requirements.txt` fest gepinnt. Das ist
wichtig, damit die Entwicklungsumgebung reproduzierbar bleibt und sich
Parser-, Datenbank- oder LLM-Schnittstellen nicht unbemerkt durch automatische
Updates veraendern.

### Frontend

Das Frontend ist eine React-Anwendung mit Vite. Es bietet eine Chat-Ansicht,
Indexierungsfunktionen und eine interaktive Graphvisualisierung.

| Technologie  | Version | Verwendung                          |
|--------------|--------:|-------------------------------------|
| React        |  18.3.1 | UI-Framework                        |
| React DOM    |  18.3.1 | Rendering der React-Anwendung       |
| Vite         |  8.0.16 | Entwicklungsserver und Build-System |
| TypeScript   |   5.7.2 | typisierte Frontend-Entwicklung     |
| React Flow   | 11.11.4 | interaktive Graphvisualisierung     |
| lucide-react | 0.468.0 | Icons fuer UI-Aktionen              |
| Tailwind CSS |  3.4.17 | CSS-Utility-Basis                   |
| PostCSS      |  8.4.49 | CSS-Verarbeitung                    |
| Autoprefixer | 10.4.20 | Browser-kompatible CSS-Prefixes     |

Auch die Node.js-Abhaengigkeiten sind in `package.json` festgelegt. Fuer einige
Dev-Dependencies werden aktuell Caret-Versionen verwendet. Fuer maximale
Reproduzierbarkeit koennten diese ebenfalls exakt gepinnt werden.

### Infrastruktur

| Technologie     |                 Version | Verwendung                  |
|-----------------|------------------------:|-----------------------------|
| Docker Compose  |                   lokal | Start externer Dienste      |
| Neo4j Community | 5.26.26-community-ubi10 | persistenter Wissensgraph   |
| ChromaDB Server |                   1.5.9 | persistente Vektordatenbank |

Neo4j wird ueber ein eigenes Dockerfile gestartet. ChromaDB wird direkt als
Container-Image verwendet. Beide Dienste speichern ihre Daten in lokalen
Projektverzeichnissen, sodass Indexierungen zwischen Starts erhalten bleiben.

## 3. Architektur

Das Projekt ist modular aufgebaut und trennt die Hauptverantwortlichkeiten in
Backend-Module:

| Modul                  | Aufgabe                                                                 |
|------------------------|-------------------------------------------------------------------------|
| `backend/extractor`    | Scala-Dateien finden, parsen, AST, Symbole und Relationen extrahieren   |
| `backend/db`           | AST-JSON-Daten in Neo4j importieren                                     |
| `backend/vector`       | Code-Chunks bauen, Embeddings erzeugen, ChromaDB befuellen und abfragen |
| `backend/orchestrator` | semantische Treffer, Graphkontext und LLM-Prompt zusammenfuehren        |
| `backend/api`          | FastAPI-Endpunkte fuer Frontend und externe Aufrufe                     |
| `frontend/src`         | React-Oberflaeche fuer Chat, Indexierung und Graphansicht               |

Diese Trennung folgt dem MVC-Gedanken:

- Model: typisierte Datenmodelle, Graphdaten, Vektordaten und DTOs
- View: React-Oberflaeche mit Chat- und Graphansicht
- Controller/API: FastAPI-Endpunkte, die Indexierung, Chat und Graphdaten steuern

Zusaetzlich sind fachliche Bereiche getrennt: Parsing, Graph-Erstellung,
Vektorsuche, LLM-Orchestrierung und API-Schicht sind jeweils eigene Module.
Dadurch koennen einzelne Teile getestet, ersetzt oder erweitert werden, ohne
das ganze System umzubauen.

## 4. Ablauf der Indexierung

Die Indexierung startet ueber das Frontend oder direkt ueber die API. Im
Frontend wird standardmaessig ein Projektpfad indexiert oder ein Ordner
hochgeladen. Die API-Endpunkte sind:

- `POST /api/index`
- `POST /api/upload-index`

Der Ablauf sieht so aus:

```text
Scala-Projekt
  -> Dateiscanner
  -> Tree-sitter Scala Parser
  -> AST + Symbole + Relationen
  -> JSON-Dateien unter local-data/ast
  -> Neo4j-Import
  -> Chunk-Building
  -> Gemini-Embeddings
  -> ChromaDB-Import
```

### 4.1 Scannen und Parsen

Der Scanner sucht Scala-Dateien. Jede Datei wird mit Tree-sitter und der
Scala-Grammatik geparst. Tree-sitter wurde gewaehlt, weil es Quellcode nicht
nur als Text behandelt, sondern als Syntaxbaum. Dadurch koennen Klassen,
Objects, Traits, Funktionen, Werte, Imports und andere Scala-Strukturen
gezielt erkannt werden.

Das Ergebnis ist pro Datei ein strukturiertes JSON-Dokument mit:

- relativem und absolutem Dateipfad
- AST
- extrahierten Symbolen
- extrahierten Relationen
- Fehlerstatus

### 4.2 Symbol- und Relationsextraktion

Aus dem AST werden Symbole wie `class`, `object`, `trait`, `function`, `val`
oder `var` extrahiert. Fuer jedes Symbol werden unter anderem Name, Art,
Quellbereich, Parent-Symbol und FQN gespeichert.

Zusaetzlich werden Relationen erzeugt, zum Beispiel:

- `DECLARES`: Datei oder Symbol deklariert ein Symbol
- `IMPORTS`: Datei importiert ein internes oder externes Symbol
- `EXTENDS`: Typ erbt von einem anderen Typ
- `CALLS`: Symbol ruft eine Funktion oder Methode auf
- `INSTANTIATES`: Symbol erzeugt eine Instanz
- `USES`: Symbol verwendet einen Typ in einer Signatur
- `DEPENDS_ON`: Datei haengt von einer anderen Datei ab

Diese Relationen sind die Grundlage fuer den spaeteren Wissensgraphen.

### 4.3 Import in Neo4j

Neo4j speichert die strukturelle Sicht auf die Codebase. Dateien, Symbole,
externe Imports und nicht aufgeloeste Calls werden als Knoten abgelegt.
Beziehungen werden als Kanten modelliert.

Neo4j wurde gewaehlt, weil Codearchitektur graphartig ist. Klassen,
Funktionen, Dateien und Imports bilden natuerlich ein Netzwerk. Mit Cypher
lassen sich Fragen wie "Welche Funktionen ruft diese Funktion auf?" oder
"Welche Dateien haengen voneinander ab?" direkt als Graphabfragen formulieren.

Beim Reset wird der Graph bewusst geloescht und neu aufgebaut. Das vermeidet
veraltete Knoten und Kanten aus frueheren Parser- oder Importversionen.

### 4.4 Aufbau der Code-Chunks

Parallel zum Graphimport werden aus den AST-JSON-Dateien semantische
Code-Chunks gebaut. Das Chunking erfolgt bevorzugt auf Symbol-Ebene. Ein
Chunk enthaelt also zum Beispiel eine Klasse, ein Object oder eine Funktion.

Ein Chunk besteht aus:

- eindeutiger ID, meist der Symbol-ID
- Textinhalt
- Metadaten wie Pfad, Symbolart, Name, FQN, Parent-ID und Zeilenbereich

Der Chunk-Text enthaelt bewusst einen kleinen Header:

```text
kind: function
name: example
path: src/main/scala/Example.scala
fqn: package.Example.example

def example(...): ...
```

Das wurde so implementiert, damit das Embedding-Modell nicht nur reinen Code,
sondern auch strukturellen Kontext bekommt. Name, Pfad, Symbolart und FQN
helfen beim semantischen Retrieval.

### 4.5 Embeddings und ChromaDB

Die Embeddings werden mit Gemini ueber LlamaIndex erzeugt. ChromaDB ist dabei
nicht das Modell, sondern die Vektordatenbank. Chroma speichert die von Gemini
berechneten Vektoren zusammen mit Text und Metadaten.

Ein Embedding ist eine numerische Darstellung von Bedeutung. Ein Text, ein
Code-Abschnitt oder eine Nutzerfrage wird dabei in einen Vektor umgewandelt,
also in eine Liste von Zahlen. Texte mit aehnlicher Bedeutung erhalten
aehnliche Vektoren. Dadurch kann das System auch dann passende Code-Stellen
finden, wenn Frage und Code nicht exakt dieselben Woerter verwenden.

Beispiel:

```text
"Wo wird der Controller initialisiert?"
  -> [0.12, -0.44, 0.91, ...]

"An welcher Stelle wird der Controller erstellt?"
  -> [0.10, -0.41, 0.88, ...]
```

Die Zahlen sind nur ein vereinfachtes Beispiel. Wichtig ist: Beide Fragen
liegen im Vektorraum nahe beieinander, weil sie semantisch aehnlich sind.

Beim Import passiert:

```text
Code-Chunks
  -> embed_documents(...)
  -> Gemini Embedding-Vektoren
  -> ChromaDB upsert(ids, documents, metadatas, embeddings)
```

Die Chroma-Collection nutzt Cosine Similarity. Das passt zu Gemini-Embeddings,
weil semantische Aehnlichkeit typischerweise ueber Winkelnaehe im Vektorraum
bewertet wird.

In diesem Projekt werden Embeddings also direkt fuer die semantische Suche
verwendet:

```text
Code-Chunk
  -> Gemini Embedding
  -> Vektor in ChromaDB speichern

Nutzerfrage
  -> Gemini Embedding
  -> aehnliche Vektoren in ChromaDB suchen
  -> passende Code-Chunks zurueckgeben
```

Damit ist die Suche nicht auf exakte Begriffe beschraenkt. Eine Frage wie
"Wo wird ein Spielzug ausgefuehrt?" kann auch Code finden, der Methodennamen
wie `move`, `placeStone` oder `executeTurn` verwendet, obwohl die Formulierung
nicht identisch ist.

## 5. Ablauf einer Chat-Anfrage

Der Chat-Endpunkt ist:

- `POST /api/chat`

Das Frontend sendet standardmaessig:

- `query`: Nutzerfrage
- `top_k`: 5
- `max_neighbors`: 20
- `max_snippets`: 12
- `generate`: true

Der RAG-Ablauf sieht so aus:

```text
Nutzerfrage
  -> Gemini Query-Embedding
  -> semantische Suche in ChromaDB
  -> Top-k Code-Chunks
  -> Symbol-IDs als Seeds
  -> Graph-Expansion in Neo4j
  -> Ranking und Deduplizierung
  -> Prompt mit Snippets und Relationen
  -> Gemini-Antwort
```

### 5.1 Query-Embedding

Die Nutzerfrage wird mit demselben Embedding-Provider eingebettet wie die
Code-Chunks. Das ist wichtig, weil Frage und Code im selben Vektorraum liegen
muessen. Nur so kann Chroma semantisch passende Codeabschnitte finden.

### 5.2 Semantische Suche in ChromaDB

ChromaDB sucht die `top_k` aehnlichsten Code-Chunks. Das Ergebnis enthaelt:

- Chunk-ID
- Code-Text
- Similarity-Score
- Metadaten

Aus den Metadaten wird die `symbol_id` gelesen. Diese Symbol-IDs bilden die
Startpunkte fuer den Graphkontext.

### 5.3 Graph-Expansion in Neo4j

Die semantischen Treffer beantworten die Frage "Welche Code-Stellen klingen
inhaltlich passend?". Der Graph beantwortet die Folgefrage "Welche direkt
verbundenen Code-Stellen sind strukturell relevant?".

Die Graph-Expansion sucht deshalb:

- direkte Symbolbeziehungen ueber `CALLS` und `EXTENDS`
- Dateiabhaengigkeiten ueber `DEPENDS_ON`
- Deklarationsbeziehungen ueber `DECLARES`

So kann der Kontext zum Beispiel nicht nur eine gefundene Funktion enthalten,
sondern auch die Funktion, die sie aufruft, oder die Datei, in der sie
deklariert ist.

Die konkrete Kombination von klassischem RAG und Neo4j passiert im
`CodeQuestionOrchestrator`. Zuerst wird die Nutzerfrage als Embedding in
ChromaDB gesucht. Aus den gefundenen Chroma-Treffern werden anschliessend
`symbol_id`s extrahiert. Diese IDs werden als Seeds fuer Neo4j verwendet.
Neo4j liefert daraufhin benachbarte Symbole und Relationen. Dadurch entsteht
Graph-RAG: Die semantische Suche bestimmt die Einstiegspunkte, der Graph
erweitert diese Treffer um strukturelle Zusammenhaenge.

Vereinfacht:

```text
Frage
  -> Embedding
  -> ChromaDB Top-k Treffer
  -> symbol_id aus Treffern
  -> Neo4j Graph-Expansion
  -> semantische Snippets + Graphrelationen
  -> gemeinsamer Prompt fuer Gemini
```

Im Code ist diese Verbindung auf drei Stellen verteilt:

- `backend/orchestrator/service.py`: steuert den Ablauf und verbindet ChromaDB mit Neo4j
- `backend/orchestrator/graph.py`: liest Graph-Nachbarn und Relationen aus Neo4j
- `backend/orchestrator/assembler.py`: kombiniert semantische Treffer und Graphkontext zum Prompt

### 5.4 Prompt Assembly

Der Context Assembler baut aus semantischen Treffern und Graph-Nachbarn einen
deduplizierten Prompt. Semantische Treffer werden zuerst aufgenommen, weil sie
direkt zur Frage passen. Danach werden Graph-Nachbarn ergaenzt, solange noch
Platz in `max_snippets` ist.

Der Prompt enthaelt:

- Rollenbeschreibung des Systems
- Nutzerfrage
- gerankte Code-Snippets
- relevante Graphrelationen
- Anweisung, nur aus dem gegebenen Kontext zu antworten

Diese Struktur reduziert Halluzinationen, weil Gemini nicht frei ueber die
gesamte Welt antworten soll, sondern sich auf die gelieferten Snippets und
Relationen stuetzt.

### 5.5 Gemini-Generierung

Wenn `generate` auf `true` gesetzt ist, wird der fertige Prompt an Gemini
uebergeben. Gemini erzeugt daraus eine natuerlichsprachliche Antwort. Wenn
`generate` deaktiviert ist, kann das System trotzdem Retrieval-Ergebnisse,
Prompt, Snippets und Relationen zurueckgeben. Das ist hilfreich zum Debuggen
und Testen des RAG-Kontexts.

## 6. Frontend-Ablauf

Das Frontend besteht aus einer Arbeitsoberflaeche mit zwei Hauptansichten:

- Chat-Ansicht
- Graph-Ansicht

In der Chat-Ansicht kann ein Projektpfad indexiert oder ein Ordner hochgeladen
werden. Danach koennen Fragen zur Codebase gestellt werden.

In der Graph-Ansicht werden Neo4j-Daten ueber `GET /api/graph` geladen und mit
React Flow visualisiert. Die Visualisierung kann Schichten wie Model,
Controller, View, Util, IO, Core und Tests darstellen. Zusaetzlich gibt es eine
UML-naehere Sicht auf Klassen, Traits, Objects und Enums.

React Flow wurde verwendet, weil es interaktive Knoten, Kanten, Controls,
MiniMap und eigene Node-Labels gut unterstuetzt. Fuer ein Architekturwerkzeug
ist Interaktivitaet wichtiger als eine statische Grafik.

## 7. Warum diese Implementierung?

### 7.1 Warum Tree-sitter?

Eine einfache Textsuche reicht fuer Codeanalyse nicht aus. Scala-Code enthaelt
verschachtelte Strukturen, Typen, Methoden, Imports und Aufrufketten.
Tree-sitter liefert einen strukturierten Syntaxbaum und ist schnell genug fuer
groessere Codebases. Dadurch koennen Symbole und Relationen gezielt statt nur
heuristisch extrahiert werden.

### 7.2 Warum Neo4j?

Code-Abhaengigkeiten sind Graphen. Dateien deklarieren Symbole, Klassen erben
von anderen Klassen, Methoden rufen Methoden auf und Dateien haengen von
anderen Dateien ab. Neo4j passt zu diesem Datenmodell, weil Beziehungen
First-Class-Objekte sind und per Cypher abgefragt werden koennen.

### 7.3 Warum ChromaDB?

Neo4j findet strukturelle Nachbarn, aber keine semantisch aehnlichen Stellen.
ChromaDB ergaenzt diese Perspektive. Eine Frage wie "Wo wird der Spielzug
ausgefuehrt?" muss nicht exakt dieselben Begriffe wie der Code enthalten.
Embeddings erlauben eine Suche nach Bedeutung statt nur nach Wortgleichheit.

### 7.4 Warum Gemini fuer Embeddings und Antworten?

Gemini wird zweifach verwendet:

- als Embedding-Modell fuer Code-Chunks und Nutzerfragen
- als generatives Modell fuer die finale Antwort

Die Trennung ist wichtig. Das Embedding-Modell entscheidet, welche Inhalte
retrieved werden. Das generative Modell formuliert danach die Antwort. ChromaDB
speichert nur die Vektoren, erzeugt sie aber nicht selbst.

### 7.5 Warum Graph-RAG statt einfachem RAG?

Ein klassisches RAG-System wuerde nur die semantisch aehnlichsten Chunks in den
Prompt legen. Bei Code ist das oft zu wenig. Eine Funktion ist nur verstaendlich,
wenn man auch ihre Aufrufer, Abhaengigkeiten, Interfaces oder Nachbartypen
kennt.

Graphbased-AI kombiniert deshalb:

- ChromaDB: "Was passt semantisch zur Frage?"
- Neo4j: "Was haengt strukturell mit diesen Treffern zusammen?"
- Gemini: "Wie laesst sich dieser Kontext erklaeren?"

Diese Kombination ist der Kern des Projekts.

### 7.6 Warum Symbol-Level-Chunks?

Dateiweise Chunks waeren oft zu gross und zu unscharf. Zu kleine Chunks
koennten wichtigen Kontext verlieren. Symbol-Level-Chunks sind ein sinnvoller
Mittelweg: Eine Klasse, ein Object oder eine Funktion ist meistens eine
fachlich erkennbare Einheit.

Zusaetzlich bleibt die Verbindung zum Graphen erhalten, weil Chunk-ID und
Symbol-ID zusammenpassen. So kann ein Chroma-Treffer direkt als Seed fuer eine
Neo4j-Graph-Expansion verwendet werden.

### 7.7 Warum modulare Services?

Die Umsetzung trennt Parser, Importer, Repository, Embedding-Provider,
Orchestrator und API. Dadurch entsteht keine grosse Sammelklasse. Jede Klasse
hat eine klare Verantwortung:

- Parser extrahieren Daten
- Repositories lesen oder schreiben Datenbanken
- Importer transformieren Daten
- Provider kapseln externe Modelle
- Orchestrator verbindet Retrieval, Graph und LLM
- API exponiert die Funktionen als HTTP-Endpunkte

Das macht den Code testbarer und erlaubt Fake-Provider in Unit-Tests, ohne
echte Gemini- oder Datenbankaufrufe auszufuehren.

### 7.8 Warum lazy imports fuer Gemini/Chroma?

Einige externe Bibliotheken werden erst importiert, wenn sie wirklich gebraucht
werden. Dadurch koennen Unit-Tests die Pipeline mit Fake-Providern pruefen,
ohne dass optionale LLM-Abhaengigkeiten oder API-Zugriffe noetig sind. Das
senkt die Kopplung und macht lokale Tests stabiler.

## 8. API-Uebersicht

| Endpunkt            | Methode | Zweck                                             |
|---------------------|---------|---------------------------------------------------|
| `/api/health`       | GET     | einfacher Healthcheck                             |
| `/api/index`        | POST    | lokales Scala-Projekt ueber Pfad indexieren       |
| `/api/upload-index` | POST    | hochgeladene Dateien indexieren                   |
| `/api/chat`         | POST    | RAG-Frage zur indexierten Codebase beantworten    |
| `/api/graph`        | GET     | Graphdaten fuer die Frontend-Visualisierung laden |

Die Kommunikation zwischen Frontend und Backend erfolgt ueber strukturierte
JSON-Objekte. Uploads verwenden `multipart/form-data`.

## 9. Datenhaltung

Das System erzeugt drei Arten abgeleiteter Daten:

| Speicherort      | Inhalt                                            |
|------------------|---------------------------------------------------|
| `local-data/ast` | extrahierte AST-JSON-Dateien                      |
| Neo4j            | Wissensgraph aus Dateien, Symbolen und Relationen |
| ChromaDB         | Code-Chunks, Metadaten und Embeddings             |

Die urspruengliche Scala-Codebase bleibt unveraendert. Das ist wichtig, weil
das Projekt als Analysewerkzeug und nicht als Codegenerator oder Refactoring-
Tool konzipiert ist.

## 10. Zusammenfassung

Graphbased-AI wurde so implementiert, dass es Scala-Code strukturell und
semantisch analysieren kann. Tree-sitter liefert die syntaktische Basis,
Neo4j speichert die Architektur als Graph, ChromaDB ermoeglicht semantische
Suche, und Gemini formuliert aus retrieved Code-Snippets und Graphrelationen
eine Antwort.

Die wichtigste Architekturentscheidung ist die Kombination aus Vektorsuche und
Wissensgraph. Semantisches Retrieval findet relevante Einstiegspunkte, der
Graph erweitert diese Treffer um technische Zusammenhaenge, und der LLM-Prompt
enthaelt dadurch mehr Kontext als bei einer reinen Volltext- oder Vektorsuche.

Ein weiterer Grund fuer diese Architektur ist der begrenzte Kontextbereich
moderner LLMs. Eine grosse Codebase kann nicht vollstaendig und sinnvoll in
jedem Prompt mitgegeben werden. Das waere langsam, teuer und wuerde das
Context Window schnell fuellen. Deshalb soll das System nicht moeglichst viel
Code an das LLM senden, sondern moeglichst passenden Code.

Graphbased-AI spart dadurch Tokens und nutzt das Context Window gezielter:

- ChromaDB waehlt nur semantisch passende Code-Chunks aus.
- Neo4j erweitert diese Treffer nur um relevante strukturelle Nachbarn.
- Parameter wie `top_k`, `max_neighbors` und `max_snippets` begrenzen die Menge
  des Kontexts.
- Gemini bekommt dadurch einen fokussierten Prompt statt einer ganzen Codebase.

Das Ziel ist also nicht nur eine bessere Antwortqualitaet, sondern auch eine
effizientere Nutzung des LLMs. Graph-RAG wurde gewaehlt, weil Code sowohl
Bedeutung als auch Struktur hat: Embeddings finden semantisch passende Stellen,
der Graph findet technische Zusammenhaenge, und das LLM erklaert nur den
ausgewaehlten Kontext.

Damit eignet sich das Projekt besonders fuer Fragen wie:

- Welche Komponente ist fuer eine Funktionalitaet verantwortlich?
- Welche Klassen oder Dateien haengen voneinander ab?
- Wie laeuft ein Aufruf durch Controller, Model und View?
- Welche Code-Stellen sind relevant, um einen bestimmten Ablauf zu verstehen?

Das System bleibt dabei read-only und veraendert die analysierte Codebase nicht.
