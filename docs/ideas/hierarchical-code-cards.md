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
