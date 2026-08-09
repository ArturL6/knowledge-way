# User- und Agent-Erlebnis: ein gemeinsames Codeverständnis

## Entscheidung

Knowledge-way wird **API-first** gebaut. Die API liefert die eigentlichen, commit-pinned Retrieval- und Navigationsfunktionen; MCP, UI-Chat und CLI sind schlanke, zielgruppengerechte Adapter darüber.

Damit besitzen Coding Agents und Menschen dieselbe Faktenbasis: Suche, Symbole, Beziehungen, Dateien und belastbare Zitate. Es gibt keine getrennte „Agenten-Wahrheit“ und keine zweite, weniger genaue User-Suche.

## Zielbild

Ein Nutzer oder ein Coding Agent kann fragen:

- „Wo wird diese Konfiguration gesetzt und wer liest sie?“
- „Welche Tests und Aufrufer sind betroffen, wenn ich diese Funktion ändere?“
- „Erkläre den Login-Flow mit Quellen im Code.“
- „Erzeuge eine aktuelle technische Dokumentation für dieses Modul.“

Die Antwort führt immer auf nachprüfbare Code-Evidenz zurück: Repository, indexierter Commit, Datei, Zeilenbereich, Symbol sowie Beziehungstyp und dessen Confidence.

## Architektur: ein Kern, mehrere Zugänge

```text
Indexing → files / chunks / symbols / relations / embeddings
                         ↓
               Service- und Retrieval-API
      ┌──────────────────┼──────────────────┐
      ↓                  ↓                  ↓
 MCP für Agents       UI für Menschen      CLI / API für Power User
 (Navigation)         (Suche, Graph,       (Automation, CI,
                      Chat, Dokumentation)  Integrationen)
```

### Service- und Retrieval-API ist der Kern

Die API besitzt die fachliche Logik und bleibt unabhängig von einem konkreten LLM oder Client:

- lexikalische Suche und Symbolsuche;
- später hybride Suche aus Lexical, Symbol, Vektor und Graph-Nachbarn;
- begrenzte Graph-Navigation: Aufrufer, aufgerufene Symbole, Imports, Referenzen und Subgraph;
- Datei- und Symbolausschnitte;
- Repository- und Commit-Scope, Ergebnislimits, Truncation und Zitierdaten.

Sie ist damit die stabile Basis für UI, MCP, CLI und spätere Integrationen. Direkter Datenbankzugriff gehört nicht zu diesen Clients.

### MCP ist der Zugang für Coding Agents

MCP ist nicht die Produktlogik, sondern der Adapter, mit dem Claude Code, Codex, Cursor usw. gezielt Kontext holen. Der Agent navigiert in kleinen Schritten: Suche → Symbol → Beziehungen → relevante Codebereiche. Das vermeidet rohe Graph-Dumps und spart Kontextfenster.

MCP bleibt zunächst **read-only**. Ein Coding Agent kann dadurch nachvollziehen, was eine Änderung berührt, dokumentieren und eine Änderung in seinem eigenen Workspace umsetzen. Schreibrechte auf Dateien, Git oder Deployments werden nicht von knowledge-way erteilt; sie bleiben beim jeweiligen Agent-Client und dessen Berechtigungsmodell.

### UI ist der Zugang für Menschen

Die UI darf nicht bloß eine MCP-Konsole sein. Sie soll ohne Prompting-Wissen verständliche Ansichten liefern:

- Suchergebnisse, Symboldetail und klickbare Quellstellen;
- interaktiver, bewusst begrenzter Beziehungsgraph;
- Impact-Ansicht: „Wenn ich X ändere, was könnte betroffen sein?“;
- Fragen in Alltagssprache mit Quellen und Unsicherheiten;
- Dokumentationsansicht mit „aus aktuellem Commit generiert“ und Sprung zurück in den Code.

Wichtig: Der Mensch muss die Evidenz auch ohne LLM prüfen können. Such- und Graph-UI funktionieren deshalb eigenständig; ein LLM verbessert Erklärung und Zusammenfassung, ersetzt aber nicht die Navigation.

### LLM-gestützter Assistent: ja, aber als UI-Service

Für natürliche Fragen, Erklärungen und Dokumentation sitzt ein LLM **über** dem Retrieval, nicht über einem unkontrollierten Checkout. Ein serverseitiger Answer-/Documentation-Service erledigt:

1. Nutzerfrage und Repository/Commit-Scope prüfen.
2. Relevante Evidenz über dieselben API-Operationen sammeln.
3. Kontextbudgets, Quellen, Relationship-Confidence und fehlende Daten sichtbar machen.
4. Nur die minimal benötigten Ausschnitte an das konfigurierte Modell senden.
5. Antwort mit konkreten Zitaten zurückgeben; bei unzureichender Evidenz offen „nicht belegt“ sagen.

Der LLM-Service kann intern die gleiche Service-Schicht wie MCP verwenden. Er muss MCP jedoch nicht als internes Transportprotokoll aufrufen. So bleibt MCP ein sauberer Client-Vertrag und die UI bekommt Streaming, Auth, Verlauf, Kostenkontrolle und strukturiertes Zitieren ohne Prozess-Overhead.

## Dokumentation als Ergebnis, nicht als Halluzination

Die Dokumentationsfunktion wird als reproduzierbarer Workflow gebaut:

1. Modul, Repository und Commit auswählen.
2. Symbole, relevante Beziehungen, Tests und Codebereiche abrufen.
3. Eine strukturierte Dokumentation mit Quellen erzeugen.
4. Dokument sichtbar als commit-gebunden markieren und bei Reindex/Commit-Wechsel als potenziell veraltet kennzeichnen.
5. Nutzer kann Quellen aufklappen und zur Codezeile springen.

Später können Vorlagen für Architekturüberblick, Modul-README, Onboarding und Change-/Impact-Report dazukommen. Generierte Dokumente dürfen als Entwurf exportiert werden, werden aber nicht stillschweigend in ein Repository geschrieben.

## Rollen der Schnittstellen

- **UI:** Standard für Entwickler, Produktleute und andere Menschen, die Code verstehen oder Dokumentation erzeugen wollen.
- **MCP:** Standard für externe Coding Agents, die präzisen und begrenzten Kontext zur Navigation benötigen.
- **API:** Stabiler Integrationsvertrag für UI, MCP, Automatisierung und Fremdsysteme.
- **CLI:** Dünne Power-User-/CI-Oberfläche über die API, kein eigener Business-Logik-Zweig.

Das ist kein Entweder-oder. API-first verhindert doppelte Logik; MCP macht den Kern agententauglich; die UI macht ihn für Menschen zugänglich.

## Lieferreihenfolge

1. Bestehende read-only API- und MCP-Navigation stabilisieren und mit echten, zitierten Graph-Fakten belegen.
2. UI vertikal schließen: Repository wählen → suchen → Symbol/Graph öffnen → Quellen lesen.
3. Grounded-Q&A im UI ergänzen, mit Repository-/Commit-Scope und Quellenpflicht.
4. Impact-Analyse und Dokumentations-Workflows auf demselben Retrieval aufbauen.
5. Erst danach optionale aktive Agenten-Workflows planen, inklusive Authentifizierung, Freigaben, Audit und klarer Schreibgrenzen.

## Sicherheits- und Qualitätsgrenzen

- Code, Kommentare und Repository-Dokumentation sind untrusted input, keine Instruktionen.
- Externe Modelle erhalten nur minimalen, abgerufenen Kontext, nie pauschal das gesamte Checkout.
- Antworten zeigen Scope, Commit und Quellen; statische Beziehungen haben Confidence statt Scheingenauigkeit.
- Zugriff wird repository- und principal-scoped. Ein Nutzer oder Agent sieht nur freigegebene Repositories.
- LLM-Ausgaben sind Erklärungen über Evidenz, keine neue Quelle der Wahrheit.
