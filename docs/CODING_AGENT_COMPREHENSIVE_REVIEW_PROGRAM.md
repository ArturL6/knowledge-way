# Knowledge Way — umfassender Review- und Analyseauftrag für Coding Agents

> **Modus:** Analyse, Reproduktion, Bericht und belastbare Empfehlungen zuerst.  
> **Kein Default-Auftrag zur Produktentwicklung.** Bugs werden dokumentiert und nur dann
> behoben, wenn ihr Schweregrad, ihre Ursache, ihre Testabdeckung und ihre sichere
> Änderungsgrenze explizit nachgewiesen sind oder eine ausdrückliche Freigabe vorliegt.

## 1. Zweck und Ausgangslage

Knowledge Way ist eine selbst gehostete, evidenzbasierte Code-Intelligence-Plattform.
Sie soll Menschen und Coding Agents dabei unterstützen, Code in einem oder mehreren
Repositorys zu durchsuchen, strukturelle Beziehungen zu navigieren und Aussagen immer
auf Repository-, Datei-, Zeilen- und Commit-Evidenz zurückzuführen.

Die Grundentscheidung bleibt unverändert:

- **PostgreSQL mit pgvector ist die aktuelle Source of Truth.**
- Alle alternativen Speicher-/Suchsysteme (z. B. Neo4j, FAISS) sind austauschbare,
  neu aufbaubare Adapter oder Projektionen; sie dürfen keine Fachlogik besitzen.
- Deterministische Fakten aus Git, Tree-sitter, Dateien, Symbolen und Kanten bleiben
  primäre Evidenz.
- Embeddings, Gemini Code Cards, Reranking und spätere Zusammenfassungen sind optionale,
  versionierte Anreicherung — niemals Ersatz für Quellcode oder Provenienz.
- Repository-, Commit-, Modell-, Prompt- und Berechtigungs-Scope müssen erhalten bleiben.

Dieser Auftrag soll einen unabhängigen, wiederholbaren und mehrstufigen Review ermöglichen.
Der primäre Output ist ein gut begründeter **Report**, nicht eine große ungeprüfte Änderung.

## 2. Aktueller Produktanspruch: Workspace-first statt UUID-first

Die beabsichtigte menschliche Navigation ist:

```text
Workspace auswählen oder anlegen
  → „Alle Repositories“: begrenzte Workspace-Übersicht
  → ein konkretes Repository auswählen
  → Tree / Suche / Datei / Symbol navigieren
  → fokussierten Symbol-Graph bzw. relevante Nachbarschaft öffnen
```

### Erwartetes Workspace-Verhalten

Ein Workspace bündelt mehrere Repositorys, beispielsweise fünf Services oder Libraries,
die fachlich zusammengehören. Innerhalb dieses Rahmens soll ein Mensch:

1. einen Workspace anlegen und benennen können;
2. vorhandene oder neue Repositorys dem Workspace zuordnen können;
3. den Indexstatus und den indexierten Commit jedes Mitglieds sehen können;
4. deklarierte Abhängigkeiten zwischen Mitglieds-Repos angeben, pflegen und verstehen können;
5. workspace-weit suchen können;
6. entweder eine begrenzte Workspace-Übersicht oder eine Repository-Ansicht wählen können;
7. Symbole über Suche, Tree, Datei oder Graph-Klick entdecken können;
8. nie Repository- oder Symbol-UUIDs manuell eingeben müssen.

### Aktueller, nachweisbarer Stand

- Workspace-CRUD, exklusive Repository-Mitgliedschaft und deklarierte Dependencies existieren
  bereits im API-/Datenmodell.
- In der Web-UI fehlen aktuell Workspace-Erstellung, Workspace-Switcher, Membership-Management
  und Dependency-Management.
- Der Graph hat eine lesbare Repository-Auswahl, fragt für einen fokussierten Subgraphen aber
  noch eine rohe Symbol-UUID ab.
- Es existiert noch kein echter workspace-weiter Graph-Endpunkt.
- Suche ist noch nicht durchgängig workspace-scoped.
- Workspace-Dependencies sind **manuelle Deklarationen**, keine automatisch belegten,
  cross-repository Code-Kanten.

Dies sind keine Behauptungen über die gewünschte Zielarchitektur, sondern konkrete
Review-Ausgangspunkte, die gegen den aktuellen Branch überprüft werden müssen.

## 3. Nicht verhandelbare Invarianten

Jede Analyse, Empfehlung oder spätere Änderung muss diese Punkte respektieren:

1. **Scope kommt vom Server.** Für jede workspace-scoped Operation wird die erlaubte
   Repository-Menge serverseitig abgeleitet. Ein vom Client geliefertes Repository-, Datei-,
   Symbol-, Job- oder Dependency-ID außerhalb des Workspace wird abgewiesen.
2. **Keine menschliche UUID-Eingabe.** IDs dürfen Deep-Link-/API-Identitäten bleiben, aber
   nicht der normale UX-Einstieg sein.
3. **Ein globales, hartes Budget.** „Alle Repositories“ bedeutet einen einzigen,
   deterministischen, begrenzten Graphen — nie die clientseitige Aneinanderreihung von
   `N × max_nodes` Repository-Graphen.
4. **Klare Graph-Semantik.** Initiale Workspace-Übersichten zeigen Repositorys und
   `declared_dependency`-Beziehungen. Sie dürfen deklarierte Abhängigkeiten nicht als
   verifizierte `calls`, `references` oder `imports` darstellen.
5. **Repository-Scope bleibt erhalten.** Repository-Graph und Symbol-Subgraph bleiben
   repository-lokal, bis echte Cross-Repo-Auflösung separat bewiesen und modelliert ist.
6. **Evidenz und Provenienz.** Treffer und Graph-Kontext behalten Repository, Datei/Pfad,
   Zeilenbereich und indexierten Commit. Ein Workspace ist ein Commit-Vektor pro Repository,
   nicht ein erfundener einzelner Workspace-Commit.
7. **Sichere Zustandswechsel.** Workspace-/Repository-Wechsel müssen alte Such-, Graph-,
   Chat- und Symbolantworten verwerfen oder korrekt isolieren.
8. **Löschsemantik ist explizit.** Mitgliedschaft entfernen ≠ Repository löschen;
   Workspace löschen ≠ Repository löschen. UI, API, Datenbank und Tests müssen das gleich
   verstehen.
9. **Workspace-Mitgliedschaft ist keine Authentisierung.** Solange zentrale Authentisierung
   nicht implementiert ist, darf sie nicht als Tenant- oder Zugriffsschutz behauptet werden.
10. **Keine verdeckten Providerkosten.** Embeddings, Gemini Code Cards und Reranking bleiben
    ausdrückliches Opt-in, kostenbeobachtbar und testbar ohne Providerzugriff.

## 4. Sicherheits- und Änderungsgrenzen

Der aktuelle isolierte E2E-Stack hat billable Code-Card-/Embedding-Arbeit bzw. deren
Folgezustände. Deshalb gilt:

- Keine Änderungen an `ingestion.py`, `code_cards.py`, Provider-Konfiguration,
  Queue-/Worker-Verhalten, Datenmodell oder Migrationen beginnen, bevor aktive
  Code-Card-/Embedding-Jobs terminal sind und der genaue Commit-/Migrationsstand erfasst ist.
- Keine Provider-Calls, Reindexing-Jobs, großvolumigen Embeddings oder Code-Card-Läufe als
  Teil eines Reviews starten, außer mit einer eindeutigen Kostenfreigabe und Budget.
- Keine Secrets, ADC-Credentials, Tokens, Git-URLs mit Credentials oder Dumps in Reports,
  Commits, Screenshots oder Logs ablegen.
- Private Git-Repositorys nur mit vorhandenen, minimal berechtigten, read-only Credentials
  prüfen; nie Tokens in URLs oder Prozessargumenten verwenden.
- Review-Artefakte dürfen Code nicht ändern. Jeder Bugfix muss auf einer separaten,
  beschreibenden Feature-Branch erfolgen, mit Test und nachvollziehbarer Abnahme.

## 5. Pflicht-Workstreams für den Review

Ein Orchestrator darf spezialisierte Subagents einsetzen. Subagents arbeiten getrennt,
read-only und liefern Evidenz (Pfad, Zeilenbereich, reproduzierbarer Befehl, Ergebnis) an
den Orchestrator. Der Orchestrator dedupliziert widersprüchliche Befunde und erstellt den
integrierten Abschlussbericht.

### A. Produkt-, UX- und Informationsarchitektur

Prüfen:

- Ist Workspace-first konsequent als oberste Nutzerentscheidung modelliert?
- Wo erzeugen globale Repository-Views, UUID-Eingaben, Fixtures oder implizite Defaults
  Verwirrung oder falsche Erwartungen?
- Gibt es eine vollständige Navigation Workspace → Repository → Tree/Suche → Symbol → Graph?
- Sind Empty, Loading, Indexing, Failed, Stale, Truncated und No-results Zustände
  unterscheidbar und verständlich?
- Bleiben Browser-Back/Forward, Deep Links, Refresh und Workspace-Wechsel konsistent?
- Sind Löschdialoge und Copy eindeutig über Workspace-Löschung, Mitgliedschaft-Entfernung
  und Repository-Löschung?
- Welche Barrierefreiheitsrisiken existieren: Fokus, Tastatur, Dialog Escape/Restore,
  Screenreader-Namen, Canvas-Alternativen, Reduced Motion?

### B. API-, Contract- und Scope-Analyse

Prüfen:

- Workspace-, Repository-, Datei-, Symbol-, Graph-, Job-, Chat- und Dependency-Routen auf
  konsistente Validierung und Scope-Checks.
- Ob Filter vor SQL-`LIMIT` und vor Retrieval-/Ranking-Kandidaten greifen.
- Ob IDs einer fremden Workspace-Mitgliedschaft sicher und konsistent abgewiesen werden.
- Ob Responses explizite, versionierbare Schemas besitzen statt lose Dictionaries.
- Ob Fehler 404/409/422/503 nachvollziehbar, stabil und ohne interne Details sind.
- Ob Repository-Anlage und Workspace-Zuordnung atomar erfolgen oder Orphans entstehen können.
- Ob API, Web-Client und MCP denselben Scope-/Provenienzvertrag verwenden.
- Ob OpenAPI und Tests den tatsächlichen Vertrag korrekt abbilden.

### C. Datenmodell, Migrationen und Integrität

Prüfen:

- Exklusive Workspace-Mitgliedschaft, parallele Inserts und Rennen bei Membership-Änderungen.
- Source/Target einer Dependency: unterschiedlich und im selben Workspace.
- PostgreSQL-Semantik von Unique Constraints mit nullable Feldern; mögliche Duplikate.
- Cascade-Verhalten bei Workspace-Löschung, Membership-Entfernung und Repository-Löschung.
- Behandlung bestehender, unzugeordneter Repositorys: klarer `Unassigned`-Status oder
  dokumentiertes/abgesichertes Backfill.
- Migrationsreihenfolge, Upgrade und Downgrade gegen echtes PostgreSQL + pgvector.
- Risiko, dass neue Migrationen Index-Provenienz, Code Cards, Embeddings oder laufende Jobs
  beschädigen.
- Keine Startzeit-DDL in API/Worker.

### D. Graph- und Evidenzanalyse

Prüfen:

- Determinismus: stabile Sortierung von Nodes und Edges, reproduzierbare Tie-Breaker.
- Harte Node- **und** Edge-Budgets inklusive structural nodes/edges; ehrliches `truncated`
  mit Ursache/Anzahl.
- Jeder Edge-Endpunkt ist enthalten und gehört zum angeforderten Scope.
- Visuelle Semantik unterscheidet `contains`, `defines`, `calls`/`references` und
  `declared_dependency`; Confidence nur anzeigen, wenn tatsächlich gespeichert.
- Kein Mischen unterschiedlicher Repository-Commits ohne sichtbare Commit-Vektor-Anzeige.
- Symbol-Klick kann fokussierten Graph öffnen; Tree-/Suche-/Deep-Link-Navigation führt zum
  gleichen Symbol.
- Fixture/Demo kann nie als echte Workspace-Daten fehlinterpretiert werden.
- Canvas ist auch bei vielen Knoten verständlich und auto-fitted; Labels, Legende,
  Root/Selection und Filter werden semantisch geprüft, nicht nur technisch gerendert.

### E. Indexing-, Retrieval-, Provider- und Kostenanalyse

Prüfen, ohne neue teure Läufe auszulösen:

- Inkrementelle Indexing-Behauptungen versus tatsächliche Git-Diff-, Stable-Identity- und
  Reindex-Semantik.
- Ob fehlgeschlagene Jobs live Daten teilweise überschreiben können oder ob atomare,
  veröffentlichte Index-Generationen fehlen.
- Retrieval: lexical, semantic, symbol, graph — Scope und Provenienz pro Modalität.
- Ob Vollkorpus-Vektoren in Python geladen werden; ob SQL-/pgvector-/Lexical-Index-Pfade
  skaliert und korrekt begrenzt sind.
- Provider-Adapter-Grenzen: OpenRouter, Vertex-Embeddings, Gemini Code Cards, Reranker.
- Retry-/429-Verhalten, `Retry-After`, Backoff, Resume und Persistierung jeder gültigen
  Code Card.
- Vorhandene Telemetrie: `context_s`, `provider_s`, `parse_s`, `persist_s`, `total_s`,
  valid/invalid/empty Ergebnisse, Kosten-/Token-Audit.
- Mögliche Optimierungen strikt nach gemessener Ursache priorisieren — keine Performance-
  Behauptungen aus Vermutung oder einer isolierten DB-Abfrage ableiten.

### F. Security, Berechtigungen und Betriebsgrenzen

Prüfen:

- Öffentliche/local-only API-Grenzen, CORS, MCP-Bridge und ungeschützte Endpunkte.
- Dass Workspace-Mitgliedschaft nicht fälschlich als AuthZ verstanden wird.
- Redaction von Git-/Provider-Secrets in Logs, Jobs und Fehlern.
- Deploy-Key-/HTTPS-Token-Handling in API und Worker, read-only Mounts und known_hosts.
- Destruktive API-Operationen, Fehlerweitergabe, Rate-/Kosten-Gates und DoS-Risiken.
- Welche spätere Principal-/Tenant-/Role-Architektur benötigt wird, ohne sie als schon
  implementiert darzustellen.

### G. Teststrategie und echtes E2E

Prüfen und einen Lückenbericht liefern:

- Unit-, API-, PostgreSQL-Integrations-, Migrations-, MCP- und Web-Testabdeckung.
- Fehlen von Browser-/Komponenten-E2E und geeignete Testwerkzeuge/Plugin-Integration,
  sobald der Nutzer das gewünschte Test-Plugin bereitstellt.
- Nachweislevel pro Befund klar markieren:
  - `source-reviewed`
  - `unit/API-tested`
  - `PostgreSQL integration-tested`
  - `manual live acceptance`
  - `browser E2E verified`
  - `provider E2E verified`
  - `documented only / pending`
- E2E-Sollpfad:

  ```text
  Workspace erstellen/auswählen
    → Repository atomar hinzufügen
    → Indexstatus abwarten/prüfen
    → workspace-scoped Suche
    → Tree/Datei/Symbol
    → Repository-Graph
    → Symbol-Subgraph
    → Workspace wechseln und Scope-Isolation prüfen
  ```

- Negative Tests: fremde Workspace-IDs, leere Workspace, unzugeordnetes Repository,
  fehlendes Symbol, Graph-Truncation, failed index job, Membership-Entfernung,
  Repository-/Workspace-Löschung und stale async response.

## 6. Befundklassifikation

Jeder Befund erhält eine eindeutige Kategorie und darf nicht nur als allgemeine Meinung
formuliert werden:

- `BUG_CONFIRMED` — reproduziert oder durch Tests/Source eindeutig nachgewiesen.
- `BUG_SUSPECTED` — plausibles Risiko mit klarer Hypothese, aber noch nicht reproduziert.
- `DESIGN_GAP` — gewünschte Capability/UX ist nicht oder nur API-seitig umgesetzt.
- `CORRECTNESS_RISK` — Datenverlust, Scope-Leak, inkonsistente Evidenz oder falsche Aussage möglich.
- `PERFORMANCE_RISK` — nur mit messbarer Ursache oder eindeutig ungünstigem Pfad.
- `SECURITY_RISK` — Secrets, AuthZ, Exposure, Injection oder privilege boundary.
- `TEST_GAP` — wichtiger Pfad ohne passende automatische oder E2E-Abdeckung.
- `DOCUMENTATION_GAP` — Produkt-/Betriebsrealität und Dokumentation widersprechen sich.
- `OPTIMIZATION_OPPORTUNITY` — Verbesserung ohne bestätigten Fehler; Nutzen, Messplan und
  Risiken müssen angegeben werden.

Für jeden Befund verpflichtend:

```markdown
- ID: REV-XXX
- Kategorie und Severity: blocker | critical | high | medium | low | info
- Evidenzlevel
- Kurzbeschreibung und Nutzer-/Systemauswirkung
- Reproduktion oder Prüfungsschritte
- Konkrete Pfade, Zeilenbereiche, API-Request/-Response oder Testoutput
- Wahrscheinliche Ursache und Vertrauen in die Diagnose
- Kleinster sicherer nächster Schritt
- Betroffene Daten/Migrationen/Provider/Kosten
- Empfohlene Tests und Abnahmekriterien
- Fix-Status: report-only | safe candidate | needs approval | fixed-and-verified
```

## 7. Explizite Nicht-Claims

Bis jeweils echte Implementierung und der passende Evidenzlevel vorhanden sind, darf kein
Report oder UI behaupten:

- inferierte oder verifizierte Cross-Repository-Code-Kanten;
- Evidenzursprung oder Confidence für heutige deklarierte Dependencies;
- atomare, veröffentlichte Index-Snapshots oder einen einzelnen Workspace-Commit;
- vollständige Delta-Indexierung mit stabilen logischen Identitäten;
- Tenant-Isolation, Rollen, Authentisierung oder zentral durchgesetzte Autorisierung;
- vollständige, sprachübergreifende statische Analyse oder vollständigen Call Graph;
- browser-E2E-Verifikation nur wegen Unit-/API-Tests;
- provider-E2E-Verifikation nur wegen gemockter Tests;
- Performance- oder Kostenvorteile ohne repräsentative Messung.

## 8. Arbeitsweise für Orchestrator und Subagents

1. **Provenienz feststellen:** Branch, HEAD, Remote, Docker-/Compose-Projekt,
   Migrations-Head, aktive Worker-/Queue-Jobs und untracked Artefakte erfassen.
2. **Read-only Aufteilung:** Mindestens Product/UI, API/Scope, DB/Migrations,
   Graph/Evidence, Indexing/Providers, Security und Tests/E2E getrennt untersuchen.
3. **Kein stilles Implementieren:** Erst Befunde in dedizierte Markdown-Reports schreiben.
4. **Konflikte auflösen:** Widersprüchliche Subagent-Befunde gegen Quellcode oder echte
   reproduzierbare Tests abgleichen. Unsicherheit markieren, nicht raten.
5. **Priorisierung:** Erst Datenverlust, Scope-Leak, irreführende Evidenz und Kostenrisiko;
   dann UX-Blocker; danach Skalierung, Wartbarkeit und Komfort.
6. **Fix-Vorschläge separieren:** Für jeden vorgeschlagenen Fix Scope, Migration,
   Rollback, Tests und Nutzerwirkung formulieren. Kein Fix ohne Review-/Freigabepunkt.
7. **Plugin/Testtool:** Sobald ein Browser-/E2E- oder Analyse-Plugin verfügbar ist,
   dessen Version, Berechtigungen, Grenzen und ein kleiner repräsentativer Smoke-Test im
   Report festhalten. Plugin-Output ist Evidenz, ersetzt aber keine Scope-/Provenienzprüfung.

## 9. Erwartete Report-Artefakte

Alle erzeugten Reports werden versioniert unter einem klaren Ordner abgelegt, zum Beispiel:

```text
docs/reviews/YYYY-MM-DD-workspace-graph-review/
  00-executive-summary.md
  01-runtime-and-provenance.md
  02-product-and-ux.md
  03-api-and-scope.md
  04-data-model-and-migrations.md
  05-graph-and-evidence.md
  06-indexing-retrieval-providers.md
  07-security-and-operations.md
  08-test-and-e2e-gap-analysis.md
  09-findings-register.md
  10-prioritized-roadmap.md
  evidence/                 # sanitized outputs/screenshots only
```

### Minimalinhalt des Executive Summary

- Review-Commit, Zeitpunkt, Prüfumfang und nicht geprüfte Bereiche.
- Anzahl der Befunde je Kategorie/Severity/Evidenzlevel.
- Top 5 Risiken und Top 5 sichere Verbesserungschancen.
- Entscheidungsempfehlung: `report accepted`, `critical fix first`, `safe UX slice`,
  `needs product decision`, `blocked by active provider job`.
- Klare Trennung zwischen bestätigten Bugs, vermuteten Risiken und Designlücken.

### Minimalinhalt der Roadmap

- dependency-geordnete kleine Vertikalslices;
- genaue Vorbedingungen und Do-not-touch-Grenzen;
- Tests, E2E-Kriterien, Rollback und Release-Gates je Slice;
- erwartete Kosten-/Performance-Messungen, wo Provider oder große Datenmengen relevant sind;
- explizite Punkte, die eine menschliche Produktentscheidung verlangen.

## 10. Abnahmekriterien für den Review selbst

Der Review ist erst fertig, wenn:

- jeder Haupt-Workstream einen eigenen Bericht oder begründeten `not assessed`-Status hat;
- jeder Befund Evidenz, Severity und nächsten sicheren Schritt enthält;
- Bugs, Risiken, Lücken und Optimierungen nicht vermischt sind;
- aktive billable Jobs und ihre Änderungsgrenzen dokumentiert wurden;
- keine unbelegten Behauptungen über Cross-Repo, Auth, Snapshots, E2E oder Performance enthalten sind;
- Report-Artefakte keine Credentials, personenbezogenen Daten oder unredigierten Provider-Responses enthalten;
- die finale Roadmap kleine, testbare und reversierbare Slices enthält;
- keine Produktions-/Schema-/Provider-Änderung als Teil des Analyseauftrags still durchgeführt wurde.

## 11. Nächste Produktentscheidung nach dem Review

Die Standardempfehlung nach Abschluss des Reviews ist nicht ein Big-Bang-Refactor, sondern:

1. Befunde bestätigen und kritische Risiken isolieren.
2. Workspace-first Contract und Unassigned-Repository-Policy entscheiden.
3. Einen kleinen, sicheren Slice wählen: Workspace-Shell + atomare Membership +
   workspace-scoped Discovery, ohne Ingestion/Provider zu ändern.
4. Danach begrenzte Workspace-Übersicht und symbolfreie Graph-Navigation liefern.
5. Erst anschließend Atomizität, echte Git-Deltas, Postgres-native Retrieval,
   AuthZ und evidenzbasierte Cross-Repo-Auflösung über die vorhandenen Backlog-Tickets planen.
