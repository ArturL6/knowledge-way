# Handoff — knowledge-way

**Stand:** erste API-first Human-/Agent-Experience-Vertikale ist implementiert und lokal laufend verifiziert.

## Produktentscheidung

Der Codeverständnis-Kern ist **API-first**:

- **API/Service-Schicht:** gemeinsame Faktenbasis für Suche, Symbole, Graph, Commit-Scope und Zitate.
- **MCP:** read-only Adapter für externe Coding Agents.
- **UI:** Such-, Symbol-, Graph-, Q&A- und Dokumentationszugang für Menschen.
- **CLI:** später ein dünner Power-User-/CI-Adapter über die API.

Details: [`USER_AND_AGENT_EXPERIENCE.md`](USER_AND_AGENT_EXPERIENCE.md).

## Was jetzt funktioniert

### API

- `GET /api/search?q=...&mode=hybrid&limit=...&repository_id=...`
  - optionaler Repository-Scope mit Existenzvalidierung;
  - Ergebnisse enthalten `repository_id`, `symbol_id` (soweit verfügbar) und `indexed_commit_sha`.
- `POST /api/explanations`
  - Request: `{"question":"...","repository_id":"..."}`;
  - strikt repository-/commit-scoped;
  - liefert deterministische read-only Evidence-Zusammenfassung, Zitate, `grounded` und `answer_mode: "retrieval_only"`;
  - keine LLM-Nutzung, keine Conversation-/Message-Persistenz.
- `POST /api/documentation/generate`
  - Request: `{"repository_id":"...","symbol_id":"..."}`;
  - generiert deterministisches Markdown aus Symbol, direktem Caller-/Callee-Kontext und Quellen;
  - keine Schreiboperation in Repositories.

### UI

- Suche zeigt bei Symboltreffern **View symbol** und **Open graph**.
- Neue Symbolroute: `/repositories/[repositoryId]/symbols/[symbolId]`.
  - zeigt Metadaten, Signatur, Code, Caller, Callees, Confidence und Links zu Quelle/Graph;
  - Button **Generate documentation** zeigt commit-gebundene Markdown-Dokumentation mit Quellen.
- `/graph?repository=<repo-id>&symbol=<symbol-id>` lädt automatisch den echten Graphen.
  - initial keine Fake-Daten;
  - Fixture-Demo bleibt nur über den expliziten Button verfügbar;
  - Confidence-Werte aus der API werden robust von `0–100` nach `0–1` normalisiert.
- `/chat` ist jetzt eine repository-scoped Grounded-Q&A-Oberfläche.
  - Repository-Auswahl aus den fertig indexierten Repositories;
  - zeigt commit-gebundene Quellen;
  - nutzt `/api/explanations`, nicht den persistierenden Legacy-Chat-Endpunkt.

## Relevante Dateien

- `apps/api/app/main.py`
- `apps/api/app/search.py`
- `apps/api/tests/test_search.py`
- `apps/api/tests/test_readonly_api.py` *(neu)*
- `apps/web/app/search/search-client.tsx`
- `apps/web/app/graph/graph-explorer.tsx`
- `apps/web/app/graph/page.tsx`
- `apps/web/app/chat/chat-client.tsx`
- `apps/web/app/repositories/[repositoryId]/symbols/[symbolId]/page.tsx` *(neu)*
- `apps/web/app/globals.css`
- `docs/USER_AND_AGENT_EXPERIENCE.md` *(neu)*

## Verifikation ausgeführt

```bash
cd /home/hermes/knowledge-way
docker compose exec -T api pytest -q
# 34 passed, 11 warnings in 1.33s

cd apps/web
npm run build
# erfolgreich; inklusive dynamischer Symbolroute
```

Zusätzlich live gegen den neu gebauten Stack geprüft:

```bash
cd /home/hermes/knowledge-way
docker compose up -d --build api web
```

- `/health` antwortet.
- Scoped Search liefert `symbol_id` und `indexed_commit_sha`.
- `/api/explanations` lieferte `answer_mode: retrieval_only`, Scope und Zitate.
- `/api/documentation/generate` lieferte Markdown und Quellen.
- Browser-Check: Suche → Symbolansicht → Dokumentationsgenerierung funktionierte gegen den lokalen Stack.

## Bewusst noch nicht umgesetzt

1. **Echte LLM-Synthese:** Die aktuellen Erklärungen/Dokumente sind absichtlich deterministische Retrieval-Ausgaben. Ein späterer Modellprovider muss minimalen Kontext, Quellenpflicht, Kostenlimits und Prompt-Injection-Abwehr beachten.
2. **Auth/Rollen/Repository-ACLs:** Aktuell existiert kein Principal-basiertes Berechtigungsmodell; vor Multi-User-/Remote-Betrieb zwingend ergänzen.
3. **Schreibfähige Agenten-Workflows:** knowledge-way bleibt read-only. Datei-, Git- oder Deployment-Schreibrechte gehören zum jeweiligen Agent-Client und brauchen explizite Freigaben/Audit.
4. **Semantische Suche/Reranking:** API kann Capability-Zustände ausweisen, aber für Qualität/Skalierung fehlen Vektorindex, Embeddings und belastbare Evaluation noch.
5. **Dokumentexport/-persistenz:** Generierte Dokumentation wird angezeigt, aber nicht automatisch in ein Repository geschrieben.
6. **UI-Qualität:** Repository-Scope wird in Search noch nicht als wählbarer Filter angeboten; Graph und Symbolnavigation machen ihn im aktuellen Flow verfügbar.

## Empfohlene nächste Schritte

1. Repository-Picker und Scope im Search-UI ergänzen.
2. Retrieval-/Graph-Evaluierungsfixtures mit Präzision, Coverage und Antwortlatenz etablieren.
3. Authentifizierung und repository-scoped Authorization als Voraussetzung für Remote-/Mehrnutzerbetrieb bauen.
4. Optionalen LLM-Provider hinter einem expliziten Feature-Flag integrieren: Evidenz sammeln → minimieren → Modell → Antwort mit Quellen; bei fehlender Evidenz ehrlich ablehnen.
5. Export-Workflow für Dokumententwürfe mit Review/Freigabe entwerfen, ohne automatische Repository-Writes.

## Arbeitsbaum

Zum Zeitpunkt des Handoffs sind die oben genannten Änderungen **nicht committed**. Vor Commit bitte prüfen:

```bash
cd /home/hermes/knowledge-way
git status --short
git diff --check
git diff
```
