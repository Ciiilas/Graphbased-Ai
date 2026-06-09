# Verbesserungen Scala-Extractor (AST / Abhängigkeiten / Calls)

Review des Extractors in `backend/extractor/` gegen das Ziel aus
[backend/README.md](backend/README.md): alle Symbole, Abhängigkeiten und Calls graph-fertig abbilden.
Gemessen am Testprojekt `testproject/Muehle` (26 Hauptdateien).

## Was bereits korrekt funktioniert ✅

- **AST-Serialisierung** (`ast_serializer.py`) — vollständiger Tree-sitter-Baum wird verlustfrei serialisiert.
- **Symbole** (`symbols.py`): package, import, object/class/trait/enum, function, val/var/type/given,
  inkl. FQNs und Parent-Verschachtelung.
- **EXTENDS** inkl. `with`-Mixins (`extends A with B` → beide), Generics (`Command[Game]` → `Command`),
  qualifizierter Auflösung.
- **IMPORTS** (Wildcard `._`/`.*`, Selektoren `.{A, B}`, intern vs. external), **DECLARES**, **DEPENDS_ON**.
- Zwei-Pass-CLI-Design (einmal parsen, gegen alle Symbole auflösen).

## Gefundene Lücken ❌

| Lücke | Anzahl im Testprojekt | Status |
|---|---|---|
| `new X(...)`-Instanziierungen (`instance_expression`) | **37** | gar nicht erfasst |
| Calls außerhalb von Funktionsrümpfen (val/var-Initializer, Klassenrumpf), z. B. `Guice.createInjector(...)`, `new UndoManager[...]` | **79** | verloren — nur `function_definition` gilt als Caller |
| Paren-less Methodenaufrufe (`game.getPlayer`, `game.getCurrentGameState` → `field_expression`) | **297** (Methodenaufrufe + Feldzugriffe) | nicht erfasst |
| Typ-Referenzen in Signaturen (`var game: gameInterface`, Parameter-/Rückgabetypen) | — | nicht als Relation |

**Ursachen** in [backend/extractor/relations.py](backend/extractor/relations.py):
- [`_call_relations`](backend/extractor/relations.py#L195) iteriert nur `function_definition`-Knoten als
  Caller → 79 Calls im Klassenrumpf fallen weg; zusätzlich **Doppelzähl-Bug**, weil ein Call in einer
  verschachtelten Funktion sowohl der äußeren als auch der inneren Funktion zugeordnet wird.
- Nur `call_expression` wird inspiziert → `new X(...)` und paren-less `a.b` sind unsichtbar.

## Entscheidungen

| Thema | Entscheidung |
|---|---|
| `new X(...)` | eigene **INSTANTIATES**-Relation |
| Typ-Referenzen in Signaturen | eigene **USES**-Relation |
| Calls außerhalb von Funktionen | dem **umschließenden Symbol** (class/object/val) zuordnen |
| Paren-less Calls | **als CALLS erfassen, aber markiert** (Empfehlung, siehe unten) |

### Empfehlung paren-less Calls

`a.b` ist in Scala syntaktisch nicht von einem Feldzugriff unterscheidbar (uniform access). Daher:
auflösen über die bestehende Heuristik
([`_resolve_call`](backend/extractor/relations.py#L376)).
- Auflösbar auf ein bekanntes `function`-Symbol → normale `CALLS` (`target_kind="symbol"`).
- Nicht auflösbar → trotzdem `CALLS`, aber mit `metadata={"paren_free": true, "resolved": false}` und
  `target_kind="call"` → Feldzugriffe / Enum-Cases (`Event.Set`) bleiben downstream **filterbar**.

Begründung: keine Info geht verloren, Rauschen ist explizit markiert und reversibel — robuster als
hartes Weglassen (verpasst echte Methodenaufrufe) oder ungefiltertes Aufnehmen.

## Geplante Änderungen (`backend/extractor/relations.py`)

1. **Owner-Zuordnung generalisieren** — Liste `(start_byte, end_byte, symbol)` über alle
   Container-Symbole der Datei (`function`, `val`, `var`, `given`, `class`, `object`, `trait`, `enum`);
   Helfer `_enclosing_symbol(node)` liefert das **kleinste umschließende** Symbol. Behebt die 79
   verlorenen Calls + Doppelzähl-Bug (genau ein Caller pro Call).
2. **CALLS** auf neue Owner-Zuordnung umstellen.
3. **Paren-less CALLS (neu)** — alle `field_expression` durchgehen, die `function`-Childs von
   `call_expression` überspringen (sonst Doppelung); auflösen + markieren wie oben.
4. **INSTANTIATES (neu)** — `instance_expression`: Typname (nach `new`, Basisname via
   [`_base_type_name`](backend/extractor/relations.py#L313)) gegen `symbols_by_fqn` auflösen; intern →
   `INSTANTIATES`, sonst external. Quelle = umschließendes Symbol.
5. **USES (neu)** — Typ-Referenzen in Signaturen (function: `parameters`+`return_type`; class/trait:
   Konstruktor-Parameter; val/var/given/type: `type`-Feld) als `USES` Symbol→Typ.
6. **DEPENDS_ON erweitern** — `INSTANTIATES` und aufgelöste `USES` zusätzlich als datei-übergreifende
   Abhängigkeit berücksichtigen
   ([`_depends_on_relations`](backend/extractor/relations.py#L249)).

## Tests & Doku

- Neue Fälle in [backend/tests/test_extractor.py](backend/tests/test_extractor.py): INSTANTIATES
  (intern + external), paren-less CALL (aufgelöst + markiert), Call im `val`-Initializer →
  Quelle = umschließendes Symbol, USES auf internen Typ.
- README-Abschnitt um `INSTANTIATES`, `USES` und das `paren_free`-Flag ergänzen.

## Runde 2: Typ-bewusste Call-Auflösung (umgesetzt)

Ausgangslage: nur **89/799 Calls (11 %)** auf interne Symbole aufgelöst. Umgesetzt:

- **Abstrakte Trait/Interface-Member** (`function_declaration` etc.) werden jetzt als Symbole erfasst
  (`symbols.py`) — vorher fehlten *alle* Interface-Methodensignaturen, weshalb Calls über Interface-Typen
  nie auflösten.
- **Enum-Cases** (`simple_enum_case`/`full_enum_case`) als `enum_case`-Symbole (`Event.Set` auflösbar).
- **Receiver-Typ-Auflösung** (`relations.py`): Scope-Symboltabelle (Parameter, `val`/`var`-Felder,
  Konstruktor-Parameter, `this`, inferierte `val`-Typen aus `new X`), Member-Suche **inkl. Vererbung**
  über die `EXTENDS`-Hierarchie, **verkettete** Receiver (`a.b.c()`) rekursiv über Rückgabetypen,
  **Import-bewusste** Namensauflösung (`Simplename → FQN`), plus namensbasierter Fallback.

Ergebnis: **151/290 intern-auflösbare Calls (52 %)** — von 11 % auf 52 % der prinzipiell auflösbaren.
Die restlichen 509 unaufgelösten Calls zielen korrekt auf die Standardbibliothek/externe Libs.

### Verbleibende Grenzen (Folgearbeit, ohne volle Typinferenz)
- Methoden nur in der Impl statt im Interface deklariert (`getMuehleMatrix`).
- Unqualifizierte Enum-Cases außerhalb des Enums (`SET_STONE`, `White`) → bräuchte Companion-/Enum-Scope.
- Konstruktor-Parameter hinter `@Inject() (...)` (Tree-sitter-Parse-Limitierung → `game`-Feld in Controller).

## Verifikation

1. `python -m unittest discover -s backend/tests`
2. `python -m backend.extractor.cli --source testproject/Muehle --output build/ast --overwrite`
3. In `build/ast/files/**/Controller.scala.json` prüfen: `INSTANTIATES` (SetCommand/UndoManager/…),
   `CALLS` für `Guice.createInjector` (Quelle = `injector`-val), paren-less `CALLS` (`game.getPlayer`),
   `USES` (`gameInterface`/`FileIOComponent`).
