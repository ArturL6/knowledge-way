# Architecture

The API owns transactional metadata and query orchestration. RQ workers own Git/network/parser/embedding work and report durable `indexing_jobs` progress. Repositories are checked out below `REPOSITORY_STORAGE_PATH/<repository UUID>` and never exposed by path through the API.

Search is deliberately layered: deterministic filter parsing → PostgreSQL full-text/trigram candidate retrieval → optional vector candidates → exact/prefix symbol candidates → normalized score fusion and de-duplication. The `SearchEngine`, `EmbeddingProvider`, `ChatProvider`, and parser interfaces make replacement of providers or later SCIP/LSP intelligence possible without API-layer changes.

The initial reference extractor is conservative: imports and candidate calls are stored with confidence, including unresolved names. It must not be represented as complete cross-language static analysis.
