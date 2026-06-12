# Frontend

React-Frontend von Graphbased-AI.

## Start

Backend-API aus dem Projekt-Root starten:

```bash
uvicorn backend.api.app:app --reload --port 8000
```

Frontend starten:

```bash
cd frontend
npm install
npm run dev
```

Die App laeuft danach unter `http://127.0.0.1:5173`.

## Funktionen

- Chat als Hauptansicht fuer Fragen an die indexierte Scala-Codebase.
- Indexierung per lokalem Pfad, z. B. `testproject/Muehle`.
- Ordner-Upload ueber den Browser als Alternative zum lokalen Pfad.
- Umschaltbare Graph-Ansicht mit React Flow.
- In der Graph-Ansicht bleibt der Chat links als schwebendes Panel sichtbar.

Die API-URL kann bei Bedarf mit `VITE_API_URL` ueberschrieben werden:

```bash
VITE_API_URL=http://localhost:8000 npm run dev
```
