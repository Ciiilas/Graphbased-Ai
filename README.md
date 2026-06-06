# Graphbased-AI

> **Status:** Konzept- und Aufbauphase. Diese README beschreibt Ziel, Tech-Stack und Architektur des Projekts; die Implementierung befindet sich noch im Aufbau.

Graphbased-AI ist ein KI-System für große Codebases, das Quellcode nicht nur durchsucht, sondern als zusammenhängende Softwarearchitektur versteht. Das Projekt analysiert Code mit Tree-sitter, extrahiert daraus Strukturen wie Dateien, Klassen, Funktionen, Imports, Abhängigkeiten und Aufrufbeziehungen und speichert diese Informationen als Wissensgraph.

Auf Basis dieses Graphen kann die KI Fragen beantworten wie:

- Welche Komponenten hängen voneinander ab?
- Wie läuft ein Request durch das System?
- Welche Stellen sind betroffen, wenn eine Funktion, API oder Datei geändert wird?
- Welche Architekturentscheidungen lassen sich aus der Codebase ableiten?
- Wie lassen sich neue Codeänderungen analysieren, ohne die komplette Codebase erneut einzulesen?

## Inhaltsverzeichnis

- [Projektfestlegungen](#projektfestlegungen)
  - [Entwicklungsumgebung](#entwicklungsumgebung)
  - [Python-Regeln](#python-regeln)
  - [Architekturprinzipien](#architekturprinzipien)
  - [Git-Regeln](#git-regeln)
- [Endziel](#endziel)
  - [Nicht-Ziele](#nicht-ziele)
- [Tech Stack](#tech-stack)
- [Grobe Architektur](#grobe-architektur)
- [Vision](#vision)

## Projektfestlegungen

Dieses Projekt wird mit Python im Backend und Node.js im Frontend entwickelt. Für Datenbanken und externe Infrastruktur wird Docker verwendet. Dadurch bleibt die lokale Entwicklungsumgebung schlank, während Neo4j, ChromaDB und weitere Dienste reproduzierbar gestartet werden können.

### Entwicklungsumgebung

- Python und Node.js laufen lokal auf dem Entwicklungssystem.
- Datenbanken und Infrastrukturkomponenten laufen über Docker.
- Frameworks und Libraries werden nicht ohne Versionsangabe installiert.
- Python-Abhängigkeiten müssen in `requirements.txt` mit einer festen Version angegeben werden, zum Beispiel `fastapi==...`.
- Node.js-Abhängigkeiten müssen in `package.json` mit einer festen Version festgelegt werden.
- Die konkrete Version wird im Projekt bewusst ausgewählt und dokumentiert, statt automatisch immer die neueste Version zu verwenden.

### Python-Regeln

- Typen werden explizit angegeben, zum Beispiel bei Funktionsparametern, Rückgabewerten und wichtigen Variablen.

  ```python
  # Gut: Typen sind klar erkennbar
  def count_functions(file_path: str) -> int:
      ...

  # Vermeiden: keine Typangaben
  def count_functions(file_path):
      ...
  ```

- Variablen, Funktionen und Klassen erhalten sinnvolle, beschreibende Namen.

  ```python
  # Gut: der Name erklärt den Zweck
  imported_modules = extract_imports(source_file)

  # Vermeiden: nichtssagende Namen
  x = extract_imports(f)
  ```

- Klassen bleiben möglichst klein und haben eine klar abgegrenzte Verantwortung. Eine Klasse soll nicht mehrere fachliche Aufgaben gleichzeitig übernehmen.

  ```python
  # Gut: jede Klasse hat eine Aufgabe
  class TreeSitterParser:
      def parse(self, source: str) -> SyntaxTree:
          ...

  class GraphBuilder:
      def build(self, tree: SyntaxTree) -> Graph:
          ...

  # Vermeiden: eine Klasse macht Parsing, Graph-Aufbau und DB-Zugriff zugleich
  class CodeProcessor:
      def parse(self, source): ...
      def build_graph(self, tree): ...
      def save_to_neo4j(self, graph): ...
  ```

- Komplexe Logik wird in kleinere Funktionen, Services oder Module aufgeteilt.

  ```python
  # Gut: ein Schritt pro Funktion, leicht testbar
  def analyze_file(path: str) -> FileAnalysis:
      tree = parse_source(path)
      symbols = extract_symbols(tree)
      return build_analysis(symbols)

  # Vermeiden: eine lange Funktion, die alles auf einmal erledigt
  def analyze_file(path):
      # 80 Zeilen Parsing, Extraktion und Aufbereitung gemischt
      ...
  ```

- Code soll gut lesbar sein und Architekturentscheidungen nachvollziehbar machen.

### Architekturprinzipien

- Der Code wird modular aufgebaut.
- Parsing, Graph-Erstellung, Vektorsuche, LLM-Orchestrierung und API-Schicht werden getrennt behandelt.
- Jede Komponente soll einzeln testbar und austauschbar sein.
- Neue Features sollen vorhandene Verantwortlichkeiten respektieren, statt bestehende Klassen unnötig zu vergrößern.

### Git-Regeln

- Es darf niemals direkt auf `main` gepusht werden.
- Änderungen werden immer auf einem eigenen Branch entwickelt.
- Der Merge in `main` erfolgt ausschließlich über einen Merge Request.
- Vor dem Merge müssen Änderungen nachvollziehbar beschrieben und geprüft werden.

## Endziel

Das Endziel ist ein interaktiver KI-Assistent für Softwareprojekte. Entwicklerinnen und Entwickler sollen große oder unbekannte Codebases schneller verstehen, Änderungen sicherer einschätzen und technische Zusammenhänge visuell nachvollziehen können.

Der Assistent kombiniert drei Perspektiven:

1. **Strukturelles Codeverständnis** über einen Wissensgraphen.
2. **Semantische Suche** über Embeddings und Vektordatenbanken.
3. **Natürlichsprachliche Erklärungen** durch ein LLM.

Dadurch soll Graphbased-AI nicht nur passende Dateien finden, sondern begründen können, warum bestimmte Dateien, Funktionen oder Module relevant sind.

### Nicht-Ziele

Graphbased-AI ist bewusst ein **rein analytisches, lesendes Werkzeug**. Es soll Code verstehen, erklären und Fragen dazu beantworten – aber **nicht selbst Code schreiben oder verändern**.

- Die KI editiert, refaktoriert oder generiert **keinen** Quellcode in der analysierten Codebase.
- Die KI nimmt **keine** schreibenden Eingriffe am Projekt vor (keine Commits, keine Dateiänderungen).
- Der Zugriff auf die Codebase bleibt **read-only**: einlesen, analysieren, Wissensgraph und Embeddings aufbauen, Fragen beantworten.

## Tech Stack

### Tree-sitter

Tree-sitter wird verwendet, um Quellcode sprachübergreifend zu parsen. Es erzeugt konkrete Syntaxbäume und kann dadurch Funktionen, Klassen, Imports, Methodenaufrufe und andere Codeelemente präzise erkennen.

Warum passend:

- Unterstützt viele Programmiersprachen.
- Ist schnell genug für große Codebases.
- Liefert strukturierte Informationen statt reiner Textsuche.
- Eignet sich gut, um Codeänderungen inkrementell zu analysieren.

### Neo4j oder NetworkX

Der Wissensgraph kann entweder mit Neo4j oder NetworkX umgesetzt werden.

**Neo4j** eignet sich besonders für eine persistente, abfragbare Graphdatenbank. Beziehungen wie `IMPORTS`, `CALLS`, `DEPENDS_ON`, `DECLARES` oder `MODIFIES` können direkt modelliert und mit Cypher abgefragt werden.

> Hinweis: Diese Beziehungen beschreiben **analysiertes Verhalten im Quellcode** (z. B. „Funktion A ruft Funktion B auf", „Funktion A verändert Zustand C"). `MODIFIES` bezieht sich also auf das, was der analysierte Code tut – nicht darauf, dass Graphbased-AI selbst Code verändert. Das System bleibt read-only (siehe [Nicht-Ziele](#nicht-ziele)).

**NetworkX** eignet sich für Prototyping, lokale Analysen und Algorithmen wie Traversierungen, Zentralitätsberechnungen oder Abhängigkeitsanalysen.

Warum passend:

- Softwarearchitektur ist von Natur aus graphbasiert.
- Abhängigkeiten und Request-Flows lassen sich als Knoten und Kanten modellieren.
- Impact-Analysen werden durch Graph-Traversierungen nachvollziehbar.
- Neo4j bietet Persistenz und gute Abfragemöglichkeiten, NetworkX schnelle Experimente im Code.

### ChromaDB

ChromaDB dient als Vektordatenbank für semantische Suche. Codeabschnitte, Dokumentation, Commit-Informationen oder Architekturhinweise können als Embeddings gespeichert werden.

Warum passend:

- Findet semantisch ähnliche Inhalte, auch wenn Begriffe nicht exakt übereinstimmen.
- Ergänzt den Graphen um Bedeutungsebene und Kontext.
- Eignet sich gut für Retrieval-Augmented Generation.
- Ist leichtgewichtig und gut für Prototypen geeignet.

### LlamaIndex oder LangChain

LlamaIndex oder LangChain verbinden Datenquellen, Retrieval-Logik und LLM-Aufrufe. Sie können genutzt werden, um Informationen aus Graph, Vektordatenbank und Codeanalyse zusammenzuführen.

Warum passend:

- Unterstützen Retrieval-Augmented Generation.
- Erleichtern Tool-Aufrufe und Agenten-Workflows.
- Können verschiedene Datenquellen orchestrieren.
- Helfen dabei, strukturierte Graphdaten und semantische Treffer in eine Antwort des LLMs einzubinden.

### Gemini

Gemini wird als Large Language Model verwendet, um Fragen zu beantworten, Zusammenhänge zu erklären und technische Analysen natürlichsprachlich aufzubereiten.

Warum passend:

- Kann komplexe Code- und Architekturfragen verständlich formulieren.
- Eignet sich für Zusammenfassungen, Impact-Analysen und Erklärung von Request-Flows.
- Kann mit Retrieval-Ergebnissen aus Graph und Vektordatenbank kombiniert werden.

### FastAPI

FastAPI bildet das Backend des Systems. Es stellt Schnittstellen für Codeanalyse, Graphabfragen, semantische Suche und KI-Antworten bereit.

Warum passend:

- Schnell und leichtgewichtig.
- Sehr gut geeignet für Python-basierte KI- und Datenpipelines.
- Unterstützt moderne API-Entwicklung mit automatischer OpenAPI-Dokumentation.
- Passt gut zu Tree-sitter, Neo4j-Treibern, ChromaDB und LLM-Integrationen.

### React mit React Flow oder Cytoscape.js

React bildet das Frontend. Für die Visualisierung des Wissensgraphen können React Flow oder Cytoscape.js eingesetzt werden.

**React Flow** eignet sich besonders für interaktive Diagramme, manuell nachvollziehbare Flows und UI-nahe Graphdarstellungen.

**Cytoscape.js** eignet sich besonders für größere Graphen, Netzwerkvisualisierung und graphanalytische Interaktionen.

Warum passend:

- Entwickler können Architektur, Abhängigkeiten und Request-Flows visuell untersuchen.
- Graphen werden interaktiv filterbar und explorierbar.
- React passt gut zu einem modernen Web-Dashboard.
- React Flow ist stark für Flow-orientierte Darstellungen, Cytoscape.js für komplexere Netzwerkgraphen.

## Grobe Architektur

1. Codebase wird eingelesen.
2. Tree-sitter analysiert Dateien und extrahiert Codeelemente.
3. Aus den Ergebnissen entsteht ein Wissensgraph in Neo4j oder NetworkX.
4. Relevante Codeabschnitte werden zusätzlich als Embeddings in ChromaDB gespeichert.
5. FastAPI stellt Analyse-, Such- und Chat-Endpunkte bereit.
6. LlamaIndex oder LangChain orchestrieren Retrieval und LLM-Aufrufe.
7. Gemini erzeugt erklärende Antworten.
8. React visualisiert Graphen, Abhängigkeiten und KI-Antworten.

## Vision

Graphbased-AI soll ein Werkzeug werden, das Codebases wie ein technischer Architekturpartner erklärt. Statt nur Trefferlisten zu liefern, soll das System Zusammenhänge sichtbar machen, Auswirkungen von Änderungen einschätzen und Entwicklerinnen und Entwicklern helfen, fundierte Entscheidungen in komplexen Softwareprojekten zu treffen.
