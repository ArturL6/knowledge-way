# Idee: Hierarchische Code Cards (Bottom-up Repository Understanding)

**Status:** Architekturidee / noch nicht implementiert  
**Ziel:** Ein Repository nicht nur als flache Symbolsuche darstellen, sondern als nachvollziehbare, commit-pinnte Erklärung vom kleinsten sinnvollen Ordner bis zur Repository Card.

## Kernidee

Für jeden Ordner werden zuerst **deterministische Fakten** aus dem indexierten Code erzeugt. Diese werden bottom-up aggregiert:

`Datei / Symbol → Blattordner → Elternordner → Repository`

So kann eine Nutzerin oder ein Agent auf jeder Ebene sehen:

- Wofür ist dieser Bereich zuständig?
- Welche Dateien, Symbole, Entry Points und Tests gehören dazu?
- Welche Abhängigkeiten gehen in andere Bereiche oder kommen von dort?
- Was ist belegt, was ist unaufgelöst oder unsicher?

Optional kann ein LLM die Fakten in eine kurze Beschreibung überführen. Es darf dabei keine neuen Abhängigkeiten oder Tatsachen erfinden.

## Keine reine Ordnerhierarchie

Die Ordnerstruktur allein beschreibt keine Architektur. Deshalb werden zusätzlich **Boundary Edges** aus dem Code-Graphen aggregiert:

- `IMPORTS`, `CALLS`, später `INHERITS` / `IMPLEMENTS`
- Anzahl und Gewicht von Beziehungen zwischen zwei Ordnern
- Confidence, unaufgelöste und mehrdeutige Referenzen

Beispiel: `apps/web` kann von `apps/api` abhängig sein, obwohl sie im Verzeichnisbaum Geschwister sind. Diese Verbindung bleibt in der Card sichtbar.

## Daten- und Generierungsmodell

### 1. Commit-pinnte Evidenz

Die Quelle der Wahrheit sind indexierte Dateien, Symbole und Beziehungen eines konkreten Commits:

- Tree-sitter-Extraktion (zuerst Python und TypeScript/TSX)
- Quellbereiche, Resolver- und Parser-Version, Confidence
- Repository- und Commit-Scope

### 2. Deterministische Folder Facts

Pro Ordner mindestens:

- direkte Dateien, Sprachen, Symboltypen und Exporte
- Entry Points und Tests
- direkte Kinder
- eingehende/ausgehende Boundary Edges nach Zielordner
- ungelöste bzw. mehrdeutige Referenzen
- Fingerprint aus direkten Fakten, Kind-Fingerprints und Boundary-Edges

### 3. Cards

- **Deterministische Card:** sofort aus Facts verfügbar, ohne LLM.
- **Optionale LLM Card:** `purpose`, `responsibilities`, `interfaces`, `unknowns`; JSON-schema-validiert und mit Evidenz-IDs/Zitaten.
- Jede Card enthält: `indexed_commit_sha`, Facts-Hash, Schema-/Prompt-/Modell-Version, Erzeugungszeit und Kosten-/Token-Metriken.

## Inkrementelle Aktualisierung

Bei einer Dateiänderung werden nicht alle Cards neu erzeugt. Als dirty markiert werden:

1. der betroffene Blattordner,
2. seine Vorfahren,
3. Ordner, die über relevante Import-/Call-Boundary-Edges verbunden sind.

Ein identischer Reindex eines Commits ist idempotent. Wenn das Budget für LLM-Enrichment nicht reicht, bleibt die deterministische Card verfügbar.

## Risiken und Schutzmaßnahmen

- **Summary-of-summary-Verlust:** Elterncards werden aus kanonischen Facts und begrenzter Kind-Evidenz erzeugt, nicht nur aus Kind-Prosa.
- **Halluzinationen:** Das LLM darf ausschließlich Sprache erzeugen; konkrete Behauptungen benötigen Zitate. Fehlende Evidenz wird als `unknown` angezeigt.
- **Kosten/Kontextwachstum:** Top-k Boundary Edges, Tokenbudgets und Caching; LLM nur on-demand oder für relevante Ebenen.
- **Staleness:** Commit- und Fingerprint-basierte Invalidierung.
- **Sensible Inhalte:** Secret-Scanning und Redaction vor externen Embedding-/LLM-Aufrufen.

## MVP-Vorschlag

**Scope:** Ein Repository; `directory`- und `repository`-Cards; Python sowie TypeScript/TSX; keine Cross-Repository-Auflösung.

1. Tree-sitter-Symbole und evidenzierte Kanten vervollständigen.
2. Verzeichnisbaum aus indexierten Pfaden aufbauen.
3. Bottom-up Facts und Fingerprints berechnen und speichern.
4. Deterministische Cards als API/UI-Ansicht ausliefern.
5. Optionales, versioniertes LLM-Enrichment ergänzen.
6. Bei Git-Diffs nur betroffene Unterbäume und Graph-Nachbarn regenerieren.

## Akzeptanzkriterien

- Jede konkrete Aussage verweist auf Evidenz desselben Commit-Snapshots.
- Mehrdeutige/unaufgelöste Referenzen werden nie als bestätigte Verbindung ausgegeben.
- Full rebuild und inkrementeller Lauf erzeugen für denselben SHA dieselben Facts.
- Eine Blattänderung erzeugt nur die erwarteten Cards neu.
- Gold-Fixtures enthalten Monorepo, zyklische Ordnerimporte, Duplikatnamen, Tests, leere Ordner, Syntaxfehler und generierten Code.
- Browseransicht zeigt für eine Card: Zusammenfassung, Fakten, Zitate, externe Abhängigkeiten und Commit-Status.

## Einordnung in die Roadmap

Dies ist sinnvoll **nach** dem belastbaren Tree-sitter-/Code-Graph-Fundament und commit-aware Incremental Indexing. Es ersetzt weder die Suche noch den Symbolgraphen, sondern ergänzt sie um eine navigierbare Verständnis- und Dokumentationsschicht.

## Unabhängige GPT-5.6-Sol-High-Effort-Review

**Durchgeführt am:** 2026-08-09 via Codex CLI, Modell `gpt-5.6-sol`, Reasoning Effort `high`, read-only.

### Bestätigte Richtung

Die Review bestätigt die Produktidee, verschiebt aber den Schwerpunkt:

> **Evidence first, views second, prose last.**

Nicht hierarchische LLM-Zusammenfassungen sind die Wissensbasis. Die kanonische Schicht ist ein commit-versionierter Evidenzgraph; Folder-, Modul- und Repository-Cards sind daraus erzeugte, ersetzbare materialisierte Sichten. LLM-Prosa erklärt nur einen zuvor ausgewählten, belegten Claim-Satz.

### Präzisierungen

- Die UX-Ebenen **Portfolio/Cross-Repo → Repository/Modul → Code/Symbol** sind sinnvoll für progressive Navigation, aber keine harten Datenmodellgrenzen.
- `Repository` und `Ordner` bleiben wichtige Locator-Facetten, bilden Architektur aber nicht zuverlässig ab. Wo verfügbar, sind **Capability/System → Service/Deployable → Build Target/Package → Datei → Symbol** stärkere semantische Einheiten.
- Tree-sitter liefert Syntax und Containment. Belastbare Imports, Calls, Overloads oder Typauflösung benötigen je Sprache Resolver, Compiler-/LSP-/SCIP-Informationen oder eine klar sichtbare Unsicherheit.
- Parent-Cards dürfen nie ausschließlich aus Child-Prosa entstehen. Sie aggregieren atomare Graph-Fakten und selektierte Evidenz.
- Die Invalidierung braucht langfristig eine explizite **Derivations-/Provenienz-DAG**. Auch gelöschte Kanten, Renames, Build-/Parseränderungen sowie alte und neue Snapshot-Nachbarn müssen berücksichtigt werden.
- Cross-Repo-Ergebnisse brauchen ein **Snapshot-Manifest** mit den jeweils verwendeten Repository-Commits; ein einzelner SHA genügt nicht.

### Empfohlener MVP

Ein schmaler vertikaler Slice für **10–30 zusammenhängende Repositories** und zunächst ein bis zwei Sprachen:

1. Portfolio-weite Suche nach relevanten Systemen.
2. Präzise Packages/Build Targets, Dateien, Symbole, Tests und Entry Points.
3. Statisch belastbare Imports sowie explizite Cross-Repo-Verträge aus Manifests/API-Spezifikationen.
4. Drill-downfähige, deterministische Cards und eine zitierte Rangliste wahrscheinlicher Änderungsorte.
5. LLM nur für die interaktive Erklärung, nie während deterministischer Ingestion.

Nicht Teil des MVP: vollständiger Runtime-Datenfluss, beliebige Sprachen, ungesicherte Call-Auflösung oder LLM-generierte Ingest-Fakten.

### Vorab zu validierende Annahmen

- Navigieren Menschen und Agents tatsächlich portfolio-weit und anschließend hierarchisch, oder springen sie überwiegend zwischen Symbolen, APIs, Services und Tests?
- Entsprechen Ordner in den Ziel-Repositories wirklich Modulen?
- Welcher Anteil von Imports/Calls ist im realen Sprachmix eindeutig statisch auflösbar?
- Stecken die wichtigsten Cross-Repo-Beziehungen in Packages/APIs oder in Deployments, Queues, Datenbanken und Konfiguration?
- Verbessern Cards die Task-Erfolgsrate gegenüber Code-Suche plus Graph wirklich messbar?

### Harte Prinzipien für die Umsetzung

- Jeder ausgegebene Claim/Knoten/Kante ist mit Snapshot, Evidence-ID, Datei und Quellspanne belegbar.
- Unbelegte Claims werden technisch verworfen oder sichtbar als Hypothese markiert.
- Strukturierte API-Antworten enthalten stabile IDs, Commit- und Evidence-Referenzen; Agents müssen keine Prosa parsen.
- Voll- und inkrementelle Läufe werden gegen historische Änderungsfälle und bekannte Abhängigkeiten evaluiert, bevor ihre Qualität behauptet wird.
