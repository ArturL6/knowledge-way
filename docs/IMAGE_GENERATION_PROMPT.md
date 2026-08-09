# Image-Generation Prompt: Knowledge Way Architecture

> Use this prompt with an image-generation model. It is written in English because diagram quality is often better. The desired labels are in German. If the model renders text poorly, generate the image without labels and use the legend below as an overlay/reference.

## Prompt

```text
Create a polished, highly legible technical architecture infographic in 16:9 landscape format, titled exactly: “Knowledge Way — vom Code zur navigierbaren Wissensbasis”.

Audience: a technical product owner who wants to understand the system at a glance. Style: premium modern technical schematic, dark graphite/navy background, calm and uncluttered, glass-like panels, thin luminous cyan connection lines, subtle violet accents for AI components, amber accents for uncertainty, soft white typography. It should feel like a refined systems-architecture poster, not like a marketing cloud diagram, not cyberpunk, not cartoonish, no vendor logos.

Use a clear top-to-bottom layered composition with six horizontal zones, clear visual boundaries, arrows, a compact legend, and plenty of whitespace. Show data and evidence flow from bottom/source to top/answer. Use only the German labels supplied below, large enough to be readable. Avoid paragraphs; use short labels and icons. No fake code, no random English labels, no tiny unreadable text.

ZONE 1 — bottom: “Git-Repositories”. Draw three distinct repository cards inside a larger boundary named “Workspace / Produkt”.
- Repository Frontend: browser UI icon, package manifest icon.
- Repository API: service/API icon, code symbol icon.
- Repository Shared Tools: package/SDK icon, reusable library icon.
Between repository cards show two explicit cross-repository links: “Manifest / Paket” and “API-Vertrag / Import”. Draw one amber dashed link labelled “unaufgelöst oder dynamisch” to demonstrate uncertainty is never guessed.

ZONE 2: “Deterministische Indexierung”. Show a secure ingestion pipeline from every repository: Git snapshot / commit pin, file scanner, Tree-sitter parser. Branch into durable fact cards: “Dateien”, “Symbole”, “Signaturen”, “Imports”, “Calls”, “Quellcode”. Add a small commit badge on records: “Commit-pinned Evidenz”. Emphasize that Tree-sitter and static facts are the factual foundation.

ZONE 3: “Beziehungsgraph”. Draw a compact multi-level graph with nodes and labelled edge types: “contains”, “import”, “call”, “cross_repo_import”. Solid cyan edges mean “verifiziert”; thin amber dashed edges mean “Evidenz, nicht aufgelöst”. Include a small confidence scale: 100 = eindeutig lokal / verifiziert, 20 = Kandidat / unaufgelöst. The graph connects symbols inside a repository and selected package/export links across repositories.

ZONE 4: “Semantische Anreicherung”. Show each source-code symbol producing a small “Code Card” as an optional violet sidecar, not a replacement. Label the Code Card fields: “Kurzfassung”, “Keywords”, “Version: Modell + Prompt + Commit”. Show the source code card remaining larger and visually primary. Beneath, show “Kontext-Embedding”: metadata + imports/calls + optional Code Card + original source code. Add a small note: “Code bleibt Primärevidenz”.

ZONE 5: “Retrieval-Pipeline”. Draw a left-to-right funnel: “Frage” → “Lexikalisch + Symbolsuche + Vektorsuche” → “Graph-Nachbarn” → “Reranker (Top 30–50)” → “Top 5–10 Quellen”. Make Reranker a small optional precision filter, not the center of the architecture. Annotate it: “nur Ranking, keine neue Wahrheit”.

ZONE 6 — top: “Nutzung”. Split into two equal consumers: “Mensch: UI / Suche / Graph” and “Coding Agent: API / MCP”. Both connect to the exact same retrieval service, emphasising one source of truth. From it, render a final evidence-backed answer panel with three citations, each citation visibly carries: repository name, path, line range, commit, confidence. Label the answer panel: “Erklärung mit Zitaten”. Add a clear lock / read-only icon and label “Wissensschicht: read-only”.

At one side include a small inset called “Knowledge Cloud”. Show clustered circles at repository / module / symbol granularity. State visually that clusters are produced from “Graph-Topologie + semantische Ähnlichkeit”; the AI only gives cluster labels. This is a view of the evidence graph, not a separate opaque graph.

At the other side include a concise legend:
- cyan solid line: “verifizierte Beziehung”
- amber dashed line: “unaufgelöste Evidenz”
- violet card: “optionale KI-Anreicherung”
- white source card: “deterministische Evidenz”

The final image must communicate these principles visually: repository boundaries are preserved; cross-repository relations are explicit and evidence-backed; the static graph and source code are authoritative; LLM Code Cards and reranking improve navigation but never invent facts; every explanation returns citations and commit context. High information density, yet clean, editorial, coherent, and immediately understandable.
```

## Short fallback prompt

```text
Create a clean 16:9 dark technical architecture infographic titled “Knowledge Way — vom Code zur navigierbaren Wissensbasis”. Visualize: Workspace containing Frontend, API and Shared Tools repositories; explicit cross-repository package/import/API-contract links; Git snapshot → Tree-sitter static facts (files, symbols, imports, calls, source code) → evidence/confidence graph → optional violet AI Code Cards and contextual embeddings → hybrid retrieval (lexical, symbol, vector, graph) → optional reranker → cited answers for UI and MCP agents. Use cyan solid lines for verified relations, amber dashed lines for unresolved evidence, violet for optional AI, white for deterministic source evidence. Show Knowledge Clouds as graph topology + semantic similarity, with AI only labeling clusters. Make the source code and commit-pinned citations visually authoritative. German labels, modern premium schematic, no logos, no clutter, no invented claims.
```

## Reference legend for manual labeling

- **Factual base:** Git snapshot, Tree-sitter, files, symbols, imports, calls, source code.
- **Graph:** relations have type, source location, confidence, and commit context.
- **Cross-repository:** explicit workspace/dependency relation first; automatic symbol-level resolution only with unambiguous package/export evidence.
- **AI:** Code Cards and cluster labels are optional, versioned enrichment.
- **Reranker:** reorders retrieved candidates; it does not create facts.
- **Output:** UI and MCP use the same retrieval API; answers cite repository, path, lines, commit, and confidence.
