# Private/local single-user POC operations

This runbook is for the local POC only. It does **not** make a remote or team-ready deployment claim: authentication/ACLs, TLS termination, audit/retention, backups, and production operations remain out of scope.

## Start, verify, and stop

From the repository root:

```bash
cp .env.example .env                 # once; keep provider settings at their safe defaults
# EMBEDDING_PROVIDER=none and CODE_CARDS_ENABLED=false make no provider calls.
docker compose up --build -d
docker compose ps
curl -fsS http://localhost:8000/health
```

The web UI is `http://localhost:3000`; API/OpenAPI is `http://localhost:8000/docs`. All Compose ports bind to loopback. Follow API indexing-job status until it is terminal before taking a reproducible capture.

Stop while retaining the local database and checkout volume:

```bash
docker compose stop
docker compose down
```

`docker compose down -v` deletes the local PostgreSQL volume and is intentionally not part of ordinary shutdown.

## Canonical facts and reproducibility boundary

A repository result is pinned to the `repositories.indexed_commit_sha` produced by indexing. Canonical state is the indexed file/symbol/fact/edge graph plus commit provenance. Structural, code, repository, module, and retrieval cards are projections; vectors only suggest context and do not prove impact.

For the repository-card POC, retrieve the exact bounded projection with:

```bash
curl -fsS http://localhost:8000/api/repositories/REPOSITORY_ID/repository-card
```

Record the returned `repository_id`, `indexed_commit_sha`, `schema_version`, and the entire `retrieval_document` alongside any evaluation. The Starlette capture is recorded in `docs/evaluation/starlette-repository-card-poc.md`; it was generated without an embedding or LLM provider.

A workspace snapshot manifest (where the snapshot-manifest feature branch is installed) additionally pins every declared workspace member to its indexed commit. It is needed before making a cross-repository claim. Declared dependency metadata is evidence of an explicit declaration only; it does not establish import or call resolution.

## Data paths and what a database transfer contains

- PostgreSQL persistent data: Docker volume `postgres-data`.
- Repository checkouts inside API/worker containers: `/data/repositories`, backed by the host `./data` bind mount.
- Redis/RQ queue: ephemeral service state, not a reproducibility artifact.
- Configuration: `.env`; do not put credentials in Git URLs or commit provider secrets.

`scripts/knowledge-way-transfer` exports a custom-format PostgreSQL dump. It contains indexed database data (including source content, graph facts/edges, cards, and existing vectors) but **not** Git checkouts, `.env`, provider credentials, or Redis/RQ state. Preserve the matching checkout directory separately if re-indexing without network access matters.

## Backup and restore test procedure

Use a disposable Compose project/target for restore: import is destructive. Do not restore over a workspace to retain.

1. Wait for indexing to become terminal, then export and verify its checksum:

   ```bash
   ./scripts/knowledge-way-transfer export --output ~/knowledge-way-poc.dump
   sha256sum -c ~/knowledge-way-poc.dump.sha256
   ```

   `--allow-active` makes a consistent but resumable snapshot; it does not recreate the Redis queue.

2. Start an isolated empty stack (choose a unique project name):

   ```bash
   docker compose --project-name knowledge-way-restore -f docker-compose.yml up -d postgres redis
   ```

3. Restore only after selecting that disposable target:

   ```bash
   ./scripts/knowledge-way-transfer import \
     --project knowledge-way-restore \
     --input ~/knowledge-way-poc.dump --yes
   ```

4. Start the remaining services for the restore project, then verify health and one known commit-pinned API response:

   ```bash
   docker compose --project-name knowledge-way-restore -f docker-compose.yml up -d api worker web
   curl -fsS http://localhost:8000/health
   curl -fsS http://localhost:8000/api/repositories/REPOSITORY_ID/repository-card
   ```

   Compare `indexed_commit_sha` and the stored capture fields with the pre-export result. Do not compare vector similarity as proof of structural impact.

5. Tear down the disposable restore project when finished:

   ```bash
   docker compose --project-name knowledge-way-restore -f docker-compose.yml down -v
   ```

## Known POC limits

- Single-user/local only; no authentication, ACLs, TLS, audit trail, retention policy, or production backup automation.
- The repository card is deterministic and bounded. It is preview output until the versioned retrieval-document projection branch is installed.
- Embeddings and LLM code cards are opt-in. Do not enable either without an explicit bounded budget plus recorded model/version and input hash.
- Graph edges, not vector similarity or generated prose, are the structural evidence. Impact consumers must separate `verified_affected`, `likely_review`, `related_context`, and `unknown`.
- Repository checkout storage is separate from database transfer and must be backed up deliberately when required.
