# 04 — Data Model, Migrations and Integrity

> Workstream C (§5.C of `docs/CODING_AGENT_COMPREHENSIVE_REVIEW_PROGRAM.md`).
> Builds on `01-runtime-and-provenance.md`; targets, safety gates and live state are not restated.

## Summary

The schema is small, deliberate and mostly consistent between `models.py` and the migrations.
All eight revisions apply from scratch against real PostgreSQL 16.14 + pgvector 0.8.6, and all
eight downgrade cleanly on an empty schema. Migrations `0005`–`0008` are additive or widening:
**none of them rewrites, drops or truncates existing edge, chunk, embedding or card data**
(REV-319). The exclusive-membership invariant is genuinely enforced under concurrent inserts and
is correctly translated by the API (REV-318). Those are real, verified positives.

The problems are concentrated in three places:

1. **Constraints that look stronger than they are.** `uq_workspace_dependencies_declaration`
   silently permits unlimited duplicate declarations whenever `package_name` or `import_path` is
   `NULL` (REV-301), and dependency validity — source ≠ target, both endpoints in the same
   workspace — lives entirely in one Python function with no database backstop (REV-304, REV-305).
2. **`0008` is a one-way door with a new failure mode.** Its downgrade fails hard the moment any
   `target_name` exceeds 512 characters, i.e. exactly the data it exists to permit (REV-302), and
   removing the length bound while keeping a plain btree index means an incompressible target name
   over ~2 704 bytes now aborts the whole indexing transaction (REV-303).
3. **Deletion and readiness semantics are asymmetric.** Repository deletion is blocked by an
   `ON DELETE`-less foreign key from `conversations` (REV-300), and the API fails fast on a
   migration mismatch while the worker does not (REV-307).

There is no `Unassigned` state at all — workspace membership is an absent row, nothing more
(REV-306) — and `alembic check` fails at head, proving no CI gate enforces model/migration
agreement (REV-308).

Evidence base: static target `c122529` in a read-only worktree; two throwaway databases
(`review_scratch_c`, `review_scratch_c_fresh`) created on the running `postgres` container, used
for every migration and integrity experiment, and dropped afterwards. **No DDL of any kind was
issued against the `knowledgeway` database.** See [Live-database attestation](#live-database-attestation).

Applicability: `main` and `integration/consolidated-verified` carry byte-identical `Workspace`,
`WorkspaceRepository` and `WorkspaceDependency` models and identical revisions `0001`–`0004`
(`git diff main origin/integration/consolidated-verified -- apps/api/app/models.py` touches only
`Repository.requested_revision`, `SymbolEdge.target_name`, and the two new card classes).
Every workspace, dependency and cascade finding therefore applies to **both**. Only `0005`–`0008`
and the card tables are integration-only.

## Per-revision upgrade / downgrade result

Method — `PostgreSQL integration-tested`. Each revision applied individually against an empty
throwaway database, then downgraded individually back to `base`:

```bash
docker compose exec -T postgres psql -U knowledgeway -d knowledgeway \
  -c "CREATE DATABASE review_scratch_c;"

docker compose run --rm --no-deps -T \
  -v <worktree>/apps/api:/review:ro \
  -e DATABASE_URL=postgresql+psycopg://knowledgeway:knowledgeway@postgres:5432/review_scratch_c \
  -e PYTHONDONTWRITEBYTECODE=1 \
  api sh -c "cd /review && alembic -c alembic.ini upgrade <revision>"
```

| Revision | Upgrade from scratch | Downgrade (empty schema) | Downgrade with data | Notes |
|---|---|---|---|---|
| `20260808_0001` initial_schema | pass | pass | not applicable (drops everything) | Creates `vector` extension; intentionally does **not** drop it on downgrade. Drop order is FK-safe. |
| `20260808_0002` optional_embeddings | pass | pass | pass | Adds `embedding Vector()` **without dimensions** → see REV-309. |
| `20260808_0003` workspaces | pass | pass | pass | Emits an `ix_workspace_repositories_repository_id` index that is not in `models.py` → REV-308, REV-314. |
| `20260808_0004` workspace_dependencies | pass | pass | pass | Emits the nullable-column unique constraint → REV-301. |
| `20260809_0005` code_cards | pass | pass | pass | Purely additive new table. Omits two model-declared indexes → REV-308. |
| `20260809_0006` structural_cards | pass | pass | pass | Purely additive new table. Omits one model-declared index → REV-308. |
| `20260809_0007` requested_revision | pass | pass | pass | `ADD COLUMN ... NULL`, no rewrite on PG 11+. Downgrade drops the column (data loss by design, acceptable). |
| `20260809_0008` symbol_edge_target_text | pass — **10.360 ms** on 136 566 rows | pass | **FAIL** — `StringDataRightTruncation` | Widening only, no row rewrite, all 136 566 rows preserved. Downgrade rewrites the table (**884.706 ms** measured) and aborts if any value exceeds 512 chars → REV-302. Takes `ACCESS EXCLUSIVE` with no `lock_timeout` → REV-311. |

Head after `upgrade head`: `20260809_0008 (head)`. After full `downgrade base`: only
`alembic_version` remains (the `vector` extension is deliberately retained by `0001`).

Alembic runs the whole batch in a **single** transaction (`env.py:38-41` does not set
`transaction_per_migration`), so a `0004 → 0008` upgrade is all-or-nothing. That is a good
property and was observed directly: the failed `0008` downgrade left `alembic_version` at
`20260809_0008` with the column type unchanged.

## Findings

| ID | Category | Severity | One-line |
|---|---|---|---|
| REV-300 | BUG_CONFIRMED | high | `conversations.repository_id` has no `ON DELETE`; deleting a repository that was ever used in chat fails with an unhandled FK violation. |
| REV-301 | BUG_CONFIRMED | high | `uq_workspace_dependencies_declaration` permits unlimited duplicate declarations when `package_name` or `import_path` is `NULL`; the API returns `201` every time. |
| REV-302 | CORRECTNESS_RISK | high | `alembic downgrade 20260809_0007` fails hard once any `target_name` exceeds 512 chars — exactly the data `0008` exists to allow. `0008` is one-way in practice. |
| REV-303 | CORRECTNESS_RISK | high | `0008` dropped the `varchar(512)` bound but kept a plain btree index on `target_name`; an incompressible target name over ~2 704 bytes now aborts the whole indexing transaction. |
| REV-304 | DESIGN_GAP | high | Dependency validity (source ≠ target, both endpoints in the same workspace) is enforced only in one Python function; the database accepts self-dependencies and non-member endpoints. |
| REV-306 | DESIGN_GAP | high | No `Unassigned` state exists. Membership is an absent row; the single live repository belongs to no workspace, is invisible in every workspace-scoped view, and there is no backfill or atomic assign-on-create path. |
| REV-307 | CORRECTNESS_RISK | high | The API fails fast on a migration-head mismatch; the worker has no such guard and will run a full re-index against a schema it does not match. |
| REV-309 | DESIGN_GAP | high | `code_chunks.embedding` is `Vector()` with no dimension, which makes pgvector ANN indexing structurally impossible: `CREATE INDEX ... USING hnsw` → `ERROR: column does not have dimensions`. |
| REV-305 | CORRECTNESS_RISK | medium | Removing a membership at database level leaves dangling dependency declarations whose endpoints are no longer workspace members; only the API route compensates. |
| REV-308 | BUG_CONFIRMED | medium | `alembic check` fails at head: three model-declared indexes were never emitted by `0005`/`0006`, and one database index is not in the models. No CI gate runs `alembic check`. |
| REV-310 | CORRECTNESS_RISK | medium | `repositories.indexing_status` and `indexing_jobs.status` use overlapping-but-different vocabularies with no `CHECK` or enum on either; `'ready'` denotes job success. |
| REV-311 | PERFORMANCE_RISK | medium | `0008` takes `ACCESS EXCLUSIVE` on `symbol_edges` with no `lock_timeout` anywhere; a running full index holds a conflicting lock for the measured 11 m 37 s and every subsequent reader queues behind the migration. |
| REV-312 | DESIGN_GAP | medium | On a fresh, never-migrated database the startup guard raises a raw psycopg `UndefinedTable` instead of its intended message, and `docker-compose.yml` has no migration step, so `docker compose up` on a fresh volume crash-loops the API. |
| REV-317 | TEST_GAP | medium | The "no startup DDL" invariant is guarded by a string grep of a single file; the entire 50-test suite is SQLite-in-memory, so no test covers any PostgreSQL-specific semantic this workstream found. |
| REV-313 | DOCUMENTATION_GAP | low | `docs/migrations.md` claims the worker checks its migration head (it does not) and omits that `infra/init.sql` creates `pg_trgm`, which no migration creates. |
| REV-314 | OPTIMIZATION_OPPORTUNITY | low | `workspace_repositories` carries three btree indexes for a table whose logical key is `repository_id` alone; two of them are exact duplicates. |
| REV-315 | OPTIMIZATION_OPPORTUNITY | low | Every JSON column is `json`, not `jsonb`: no containment operators, no GIN indexing, no equality comparison. |
| REV-316 | CORRECTNESS_RISK | low | All timestamps are `timestamp without time zone` fed by `datetime.utcnow()` and serialized without an offset; latent today, ambiguous for every API/MCP consumer. |
| REV-318 | info | info | Verified positive: exclusive workspace membership holds under concurrent inserts and the API translates the violation correctly. |
| REV-319 | info | info | Verified positive: `0005`–`0008` do not rewrite, drop or truncate existing index provenance, edge, embedding or card data. |

---

### REV-300

- ID: REV-300
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: `PostgreSQL integration-tested` (database behaviour) + `source-reviewed` (API path)
- Applies to: both
- Impact: `DELETE /api/repositories/{repo_id}` raises an unhandled `IntegrityError` and returns
  `500` for any repository that has ever been used in `POST /api/chat`. The repository cannot be
  deleted through the API at all, and the error surfaces as an opaque server error rather than a
  `409`. §3.8 (`Löschsemantik ist explizit`) is violated: repository deletion is neither reliably
  possible nor honestly reported.
- Evidence:
  `apps/api/app/models.py:41` —
  `repository_id:Mapped[str|None]=mapped_column(ForeignKey('repositories.id'),nullable=True)`
  — no `ondelete`, so PostgreSQL defaults to `NO ACTION`. The migration emits the same:
  `apps/api/db_migrations/versions/20260808_0001_initial_schema.py:53` —
  `sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id"))`.
  `apps/api/app/main.py:159-163` (`delete_repository`) clears `workspace_dependencies` and
  `workspace_repositories` but never touches `conversations`, and has no `except IntegrityError`.
  `apps/api/app/main.py:328-336` (`chat`) creates a `Conversation` with `repository_id=body.repository_id`.

  Reproduced on `review_scratch_c` at head `20260809_0008`:

  ```sql
  INSERT INTO conversations (id,repository_id,title,created_at) VALUES ('c1','r1','q',now());
  DELETE FROM repositories WHERE id='r1';
  -- ERROR: update or delete on table "repositories" violates foreign key constraint
  --        "conversations_repository_id_fkey" on table "conversations"
  -- DETAIL: Key (id)=(r1) is still referenced from table "conversations".
  SELECT count(*) FROM repositories WHERE id='r1';  -- 1  (delete had no effect)
  ```

  Contrast with the sibling test in the same run, which shows the intended pattern works
  everywhere else: deleting a repository with files, symbols, self-referencing
  `symbols.parent_symbol_id`, `symbol_edges` and `code_chunks` succeeded and left `0` rows in each,
  because those `NO ACTION` foreign keys are satisfied at end-of-statement once the
  `ON DELETE CASCADE` on `repository_id` has removed the referencing rows in the same statement.
- Probable cause + diagnostic confidence: `conversations` is the only child table whose
  `repository_id` foreign key was written without `ondelete`, and it is also the only one the
  manual pre-delete sweep in `delete_repository` forgot. Confidence: high — the failure is
  deterministic and reproduced.
- Smallest safe next step: decide the intended semantic first. Either a migration setting
  `ON DELETE SET NULL` (conversation history survives, loses its repository scope) or
  `ON DELETE CASCADE` (history is discarded with the repository). `SET NULL` matches the column
  already being nullable and matches `code_chunks.symbol_id`. Until a migration lands, add
  `db.execute(update(Conversation).where(...).values(repository_id=None))` to `delete_repository`
  alongside the existing sweeps, so behaviour is identical on SQLite and PostgreSQL.
- Affected data/migrations/providers/cost: one new migration altering one FK constraint. No
  provider cost. On the live database `conversations` is currently empty, so no live row is at
  risk today — but the defect is reachable the moment anyone uses chat.
- Recommended tests + acceptance criteria: a PostgreSQL integration test that creates a
  repository, a conversation and a message, deletes the repository via the API, and asserts
  `204` plus the intended conversation state. Acceptance: repository deletion succeeds regardless
  of conversation history, and the chosen semantic is stated in `docs/migrations.md`.
- Fix status: report-only

---

### REV-301

- ID: REV-301
- Category: BUG_CONFIRMED
- Severity: high
- Evidence level: `PostgreSQL integration-tested`
- Applies to: both
- Impact: `POST /api/workspaces/{id}/dependencies` can be called repeatedly with the same
  `source_repository_id` / `target_repository_id` and no `package_name` / `import_path` and will
  return `201` and create a new row every time. The `409 'Dependency declaration already exists'`
  path is unreachable for exactly the shape the API's own Pydantic model makes easiest — both
  fields are `default=None` (`apps/api/app/main.py:30`). The workspace overview graph then draws
  N identical `declared_dependency` edges between the same two repositories, which reads as
  strength or multiplicity that does not exist. Unbounded row growth is possible from a single
  retrying client.
- Evidence:
  `apps/api/app/models.py:19-20` — the constraint spans
  `('workspace_id','source_repository_id','target_repository_id','package_name','import_path')`
  while `package_name` and `import_path` are both `nullable=True`. Migration
  `20260808_0004_workspace_dependencies.py:24-25,30` emits the identical shape. PostgreSQL treats
  `NULL` values as distinct in a unique index, so no duplicate is detected.
  `apps/api/app/main.py:99-106` relies solely on `except IntegrityError → 409`, so no application
  guard compensates.

  Reproduced on `review_scratch_c` at head `20260809_0008`
  (`docker compose exec -T postgres psql -U knowledgeway -d review_scratch_c -f -`):

  ```text
  -- three identical rows, both nullable columns NULL
  INSERT 0 1   (d1  w1 r1 r2 NULL NULL)
  INSERT 0 1   (d2  w1 r1 r2 NULL NULL)
  INSERT 0 1   (d3  w1 r1 r2 NULL NULL)
  -- two identical rows, only import_path NULL
  INSERT 0 1   (d4  w1 r1 r2 'pkg' NULL)
  INSERT 0 1   (d5  w1 r1 r2 'pkg' NULL)
  -- control: fully non-NULL duplicate IS rejected
  INSERT 0 1   (d6  w1 r1 r2 'pkg' 'path')
  ERROR: duplicate key value violates unique constraint "uq_workspace_dependencies_declaration"
  DETAIL: Key (workspace_id, source_repository_id, target_repository_id, package_name, import_path)
          =(w1, r1, r2, pkg, path) already exists.

  SELECT count(*) FROM workspace_dependencies WHERE package_name IS NULL AND import_path IS NULL;
  -- 3
  ```

  The control case proves the constraint is present and functioning; it simply does not cover the
  `NULL` shapes.
- Probable cause + diagnostic confidence: standard SQL `NULL`-distinctness semantics in a unique
  index, not a coding slip in the constraint definition. Confidence: high — reproduced with a
  passing control.
- Smallest safe next step: one migration replacing the constraint with a `NULLS NOT DISTINCT`
  unique index (PostgreSQL 15+; the deployment is 16.14) —
  `CREATE UNIQUE INDEX ... ON workspace_dependencies (workspace_id, source_repository_id,
  target_repository_id, package_name, import_path) NULLS NOT DISTINCT` — or make both columns
  `NOT NULL DEFAULT ''` and normalise in the API. Note the migration must de-duplicate existing
  rows first; on the live database `workspace_dependencies` is empty, so a backfill is currently
  free. `NULLS NOT DISTINCT` is not expressible in SQLAlchemy's `UniqueConstraint`, so `models.py`
  will need an `Index(..., postgresql_nulls_not_distinct=True)` to keep `alembic check` clean.
- Affected data/migrations/providers/cost: one new migration; a de-duplication step required if
  any environment already holds duplicates. No provider cost.
- Recommended tests + acceptance criteria: PostgreSQL integration test posting the same
  all-`NULL` dependency twice. Acceptance: second call returns `409` and row count stays `1`.
  Add the partial-`NULL` case (`package_name` set, `import_path` absent) as a separate assertion —
  it is a distinct failure mode.
- Fix status: report-only

---

### REV-302

- ID: REV-302
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: `PostgreSQL integration-tested`
- Applies to: integration
- Impact: `0008` cannot be rolled back once the parser has written a single `target_name` longer
  than 512 characters — which is the entire reason the revision exists ("Allow complete parser
  reference targets in graph edges"). An operator who upgrades, indexes a repository, then hits a
  problem and tries to roll back gets a hard `DataError` mid-migration. Because the whole batch
  runs in one transaction, a `downgrade 20260808_0004` attempt aborts the entire rollback, not
  just `0008`. The documented release procedure (`docs/migrations.md:43` — "Test both upgrade and
  downgrade against PostgreSQL with pgvector before merging") was evidently satisfied only against
  an empty table.
- Evidence:
  `apps/api/db_migrations/versions/20260809_0008_symbol_edge_target_text.py:19-20`:

  ```python
  def downgrade() -> None:
      op.alter_column("symbol_edges", "target_name", type_=sa.String(512), existing_type=sa.Text())
  ```

  On `review_scratch_c` at head, holding 136 569 `symbol_edges` rows of which three had
  `length(target_name) > 512`:

  ```text
  $ alembic -c alembic.ini downgrade 20260809_0007
  sqlalchemy.exc.DataError: (psycopg.errors.StringDataRightTruncation)
    value too long for type character varying(512)
  [SQL: ALTER TABLE symbol_edges ALTER COLUMN target_name TYPE VARCHAR(512) ]

  $ psql -d review_scratch_c -tAc "SELECT version_num FROM alembic_version;"
  20260809_0008
  ```

  After deleting the three over-length rows the same downgrade succeeded in **884.706 ms**
  (measured with `\timing on` on the raw `ALTER`), confirming both the cause and that the
  downgrade direction is a full table rewrite rather than a metadata-only change.
- Probable cause + diagnostic confidence: `varchar(n) → text` is binary-coercible and therefore
  free; the reverse is a constrained narrowing that PostgreSQL must validate and rewrite.
  Confidence: high — reproduced, with the negative control (downgrade succeeds once the
  over-length rows are gone).
- Smallest safe next step: state explicitly in the revision docstring and in
  `docs/migrations.md` that `0008` is a one-way migration, and make the downgrade honest — either
  remove it (raise `NotImplementedError` with the reason) or have it truncate deliberately with a
  logged count, never silently. Rolling back past `0008` in practice means restoring a backup or
  re-indexing.
- Affected data/migrations/providers/cost: `0008` only. Any rollback plan that assumes symmetric
  migrations is invalid. Re-indexing to recover costs a full index run (measured 11 m 37 s for the
  live repository).
- Recommended tests + acceptance criteria: a PostgreSQL migration test that inserts a
  600-character `target_name` at head, attempts `downgrade 20260809_0007`, and asserts the
  documented behaviour (explicit refusal or explicit, counted truncation) rather than an
  incidental driver error. Acceptance: the outcome is intentional and documented.
- Fix status: report-only

---

### REV-303

- ID: REV-303
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: `PostgreSQL integration-tested`
- Applies to: integration
- Impact: `0008` removed the `varchar(512)` bound but left `ix_symbol_edges_target_name` as a
  plain btree. A btree entry cannot exceed ~2 704 bytes, so a sufficiently long, poorly
  compressible parser target name now raises an error **on INSERT**. That insert happens inside
  `_persist_edges` during indexing, so a single pathological reference aborts the whole indexing
  transaction: the job goes `failed`, the repository goes `failed`, and — because the edges for
  the repository were already deleted earlier in the same transaction
  (`apps/api/app/ingestion.py:212`) — the rollback is the only thing preventing edge loss. Before
  `0008` this was structurally impossible: `varchar(512)` guaranteed every value fitted.
- Evidence:
  `apps/api/app/models.py:37` — `target_name:Mapped[str]=mapped_column(Text,index=True)`
  (unbounded type, plain btree index).
  `apps/api/db_migrations/versions/20260808_0001_initial_schema.py:48` creates
  `ix_symbol_edges_target_name`; `20260809_0008` alters the column type and leaves the index in
  place. Confirmed on the throwaway database after `upgrade head`:

  ```text
  Indexes:
      "ix_symbol_edges_target_name" btree (target_name)
  ```

  Threshold measured on `review_scratch_c` at head, using `md5()`-derived incompressible values
  (a highly compressible `repeat('a',4000)` is *accepted*, because index tuples are pglz-compressed
  — so the naive test gives a false negative):

  ```text
  ~4000 incompressible chars →
    ERROR: index row size 4016 exceeds btree version 4 maximum 2704
           for index "ix_symbol_edges_target_name"
    HINT:  Values larger than 1/3 of a buffer page cannot be indexed.
  ~2880 incompressible chars →
    ERROR: index row size 2896 exceeds btree version 4 maximum 2704
  ~2560 incompressible chars → INSERT 0 1   (accepted)
  repeat('a',4000)           → INSERT 0 1   (accepted — compresses away)
  ```

  Likelihood context, measured on the live database: `SELECT max(length(target_name)) FROM
  symbol_edges` = **162** across 136 566 rows, i.e. three orders of magnitude of headroom under
  the *old* 512 bound. So the trigger is rare — but it is a hard abort of an 11-minute job when
  it happens, and it is a regression introduced by the migration.
- Probable cause + diagnostic confidence: the revision widened the column to accommodate long
  parser targets without reconsidering the index that made the old bound load-bearing.
  Confidence: high for the mechanism and the measured threshold; the *probability* of a >2.7 KB
  incompressible target from the current parser is `not assessed` (would require inspecting
  `parser_facts.py` reference-expression construction against a corpus, which is workstream E).
- Smallest safe next step: keep `Text` and make the index bounded — replace
  `ix_symbol_edges_target_name` with an expression index such as
  `btree (left(target_name, 512))` (and adjust the lookup), or `btree (md5(target_name))` for
  equality-only use. Check first what the index is actually used for: `main.py` filters edges in
  Python and never queries by `target_name`, so the cheapest correct fix may simply be to drop the
  index. Alternatively cap the value in `_persist_edges` before insert.
- Affected data/migrations/providers/cost: one migration touching one index; the current index is
  11 MB for 136 566 rows. Dropping it costs nothing at query level if nothing reads it — verify
  before acting.
- Recommended tests + acceptance criteria: ingestion test that persists an edge with a 4 000-char
  incompressible `target_name`. Acceptance: the indexing job completes and the edge is stored (or
  is explicitly, loggedly truncated) — never an aborted transaction.
- Fix status: report-only

---

### REV-304

- ID: REV-304
- Category: DESIGN_GAP
- Severity: high
- Evidence level: `PostgreSQL integration-tested` (database) + `unit/API-tested` (API guard)
- Applies to: both
- Impact: the two stated invariants of a dependency declaration — source ≠ target, and both
  endpoints members of the *same* workspace — exist only in
  `validate_dependency_membership`. The database accepts self-dependencies and dependencies whose
  endpoints belong to a different workspace or to no workspace at all. Any future writer (a
  bulk importer, an MCP tool, a background job, a hand-run `UPDATE`) or any refactor that misses
  the one call site produces rows that the workspace graph will happily render as
  `declared_dependency` edges pointing outside the workspace — a scope leak against §3.1
  ("Scope kommt vom Server") presented as evidence. `PATCH` compounds this: it can change
  `package_name`/`import_path` but never re-validates membership, and membership can be removed
  underneath an existing row (REV-305).
- Evidence:
  `apps/api/app/main.py:45-48` is the entire enforcement:

  ```python
  def validate_dependency_membership(db,workspace_id,source_repository_id,target_repository_id):
   if source_repository_id==target_repository_id: raise HTTPException(422,'Source and target repositories must differ')
   members=set(db.scalars(select(WorkspaceRepository.repository_id).where(WorkspaceRepository.workspace_id==workspace_id)).all())
   if source_repository_id not in members or target_repository_id not in members: raise HTTPException(422,'Source and target repositories must both belong to this workspace')
  ```

  Called from `add_workspace_dependency` (`main.py:102`) and from **nowhere else** — notably not
  from `update_workspace_dependency` (`main.py:107-114`).
  `apps/api/app/models.py:18-20` and `20260808_0004_workspace_dependencies.py:18-34` contain no
  `CheckConstraint` and no composite foreign key to `workspace_repositories`; the three foreign
  keys point at `workspaces.id` and `repositories.id` independently.

  Reproduced on `review_scratch_c` at head — every insert below was **accepted**:

  ```text
  -- self-dependency (API would return 422)
  INSERT 0 1   (d8   w1  src=r1  tgt=r1)
  SELECT count(*) FROM workspace_dependencies WHERE source_repository_id = target_repository_id;  -- 1

  -- target is an unassigned repository, not a member of w1
  INSERT 0 1   (d9   w1  src=r1  tgt=r3)
  -- neither endpoint is a member of w2
  INSERT 0 1   (d10  w2  src=r1  tgt=r2)

  SELECT d.id, d.workspace_id, src_is_member, tgt_is_member FROM ...
   d10 | w2 | 0 | 0
   d9  | w1 | 1 | 0
  ```

  The API guard itself is covered by `apps/api/tests/test_workspaces_api.py:57-58`, which asserts
  `422` for both the self-dependency and the non-member case — on SQLite, against the API only.
- Probable cause + diagnostic confidence: deliberate "validate in the application" choice; the
  `CheckConstraint` for source ≠ target is trivially expressible in the database and was simply
  not added, and the composite-FK form of the membership rule is awkward given the current
  `workspace_repositories` key shape. Confidence: high.
- Smallest safe next step: add the one constraint that is free and cannot regress —
  `CheckConstraint('source_repository_id <> target_repository_id',
  name='ck_workspace_dependencies_distinct_endpoints')` in a migration. It needs no backfill
  (live table is empty) and closes half the gap deterministically. Separately, call
  `validate_dependency_membership` from `update_workspace_dependency` even though it currently
  cannot change endpoints — it is one line and removes the trap.
- Affected data/migrations/providers/cost: one migration adding one `CHECK`. The membership half
  needs a product decision first (see REV-305): enforcing it in the database requires either a
  composite foreign key `(workspace_id, source_repository_id) → workspace_repositories` — which
  would need `workspace_repositories` to expose that pair as a unique key, it already does via its
  primary key — or a trigger. The composite-FK route also fixes REV-305 for free by giving the
  rows an `ON DELETE CASCADE` path.
- Recommended tests + acceptance criteria: PostgreSQL integration tests attempting each invalid
  shape by direct SQL, not only through the API. Acceptance: self-dependency rejected by the
  database; the membership rule is either database-enforced or explicitly documented as
  API-only with the residual risk named.
- Fix status: report-only

---

### REV-306

- ID: REV-306
- Category: DESIGN_GAP
- Severity: high
- Evidence level: `manual live acceptance` (`main`) + `source-reviewed` (integration)
- Applies to: both
- Impact: §5.C asks for "a clear `Unassigned` status or a documented, safeguarded backfill".
  Neither exists. Workspace membership is the presence or absence of a `workspace_repositories`
  row and nothing else — there is no column, no sentinel workspace, no view, and no migration
  that assigns pre-existing repositories anywhere. The consequences are asymmetric and confusing:
  an unassigned repository is invisible in every workspace-scoped view (`GET
  /api/workspaces/{id}/repositories` is an inner join on membership, `main.py:120-124`) yet fully
  visible and fully usable everywhere else — `GET /api/repositories` returns all rows unfiltered
  (`main.py:147-148`), and `search_with_capability` loads *every* repository with no workspace
  predicate (`apps/api/app/search.py:59` — `repos = {r.id: r for r in db.scalars(select(Repository)).all()}`).
  So the product's top-level navigation decision (§2, workspace-first) has no representation in
  the data model, and there is no state that distinguishes "not yet assigned" from "assigned to a
  workspace you cannot see".
- Evidence:
  Live (`main` lineage), read-only:

  ```text
  $ curl -s http://localhost:8000/api/workspaces
  []
  $ curl -s http://localhost:8000/api/repositories | head -c 200
  [{"id":"21ffa409-9e13-493a-b919-7bb6a5b80bb9","name":"pydanticAI", ... "indexing_status":"ready" ...
  $ psql -d knowledgeway -tAc "SELECT count(*) FROM workspaces;"   -- 0
  ```

  So the one indexed repository is a member of nothing, and is returned by the global route.
  `grep -rni "unassigned"` over the static target matches **only** the review mandate documents
  (`docs/CODING_AGENT_COMPREHENSIVE_REVIEW_PROGRAM.md:163,369`,
  `docs/CODING_AGENT_WORKSPACE_GRAPH_REVIEW.md:74`) — zero matches in `apps/`.
  `apps/api/app/main.py:149-153` (`add_repository`) accepts only `name`, `clone_url` and
  `requested_revision`; there is no way to create a repository inside a workspace, so **every**
  repository is born unassigned and immediately enqueued for indexing (§B's atomicity concern,
  seen from the data-model side).
  `grep -rn "workspace" apps/web -i` → no matches: the entire workspace model has no UI, so no
  human can move a repository out of the unassigned state through the product.
- Probable cause + diagnostic confidence: workspaces were added as a lean additive layer
  (`0003`, "Add lean multi-repository workspaces") without deciding the policy for the
  repositories that already existed or for repositories created afterwards. Confidence: high.
- Smallest safe next step: this needs the product decision named in §11.2 before any schema
  change. The cheapest coherent options, in increasing invasiveness: (a) define `Unassigned` as
  a *derived* state — add `GET /api/repositories?unassigned=true` backed by a `NOT EXISTS`
  predicate, document it, and change nothing in the schema; (b) accept an optional
  `workspace_id` on `POST /api/repositories` and create the membership in the same transaction as
  the repository row; (c) make membership mandatory with a default workspace and a backfill
  migration. Option (a) is reversible and answers the review question without touching migrations.
- Affected data/migrations/providers/cost: (a) no migration. (b) no migration, one transaction
  boundary. (c) a backfill migration whose safety depends on how many unassigned repositories
  exist — currently one.
- Recommended tests + acceptance criteria: negative tests from §5.G — unassigned repository,
  empty workspace, foreign workspace id. Acceptance: an unassigned repository is
  *distinguishable* from a missing one in every list and error path, and the chosen policy is
  documented alongside the workspace routes.
- Fix status: report-only

---

### REV-307

- ID: REV-307
- Category: CORRECTNESS_RISK
- Severity: high
- Evidence level: `PostgreSQL integration-tested` (guard asymmetry) + `source-reviewed` (failure path)
- Applies to: both (structural); acute for the current `0004` database vs `0008` code split
- Impact: the migration-head guard protects the API and not the worker. The API refuses to start
  against a stale database — verified — but `worker.py` never calls `verify_migration_ready`, so a
  worker built from newer code will happily dequeue `index_repository` and run against a schema it
  does not match. The failure is worse than a crash: `index_repository` deletes the repository's
  `CodeCard` rows (`ingestion.py:211`) as its first destructive step, on a database where
  `code_cards` does not exist. That raises inside the `try`, and the `except` handler
  (`ingestion.py:240`) immediately issues `db.commit()` on an already-aborted PostgreSQL
  transaction, which raises again. So the handler that is supposed to write `indexing_status='failed'`
  cannot: the repository is left in whatever state it had, the job row is left `running`, and the
  operator sees a repository that never finishes. This is precisely the "repository stays
  `indexing` forever" symptom that `reconcile.py` was written for on `main`, arrived at by a
  different route — and `reconcile` does not exist on the integration branch at all.
- Evidence:
  `apps/api/app/worker.py` is four lines and contains no guard:

  ```python
  if __name__=='__main__': Worker([Queue('indexing',connection=Redis.from_url(settings.redis_url))],connection=Redis.from_url(settings.redis_url)).work()
  ```

  `apps/api/app/main.py:19-20` is the only caller:
  `@app.on_event('startup')` / `def startup(): verify_migration_ready()`.
  `grep -rn "verify_migration_ready" apps/` returns `app/db.py:18` (definition), `app/main.py:13,20`,
  and `tests/test_migrations.py:29` (a string assertion) — nothing in the worker path.

  Guard behaviour verified against a throwaway database deliberately left at `0004` while the
  code head is `0008`:

  ```text
  $ DATABASE_URL=...review_scratch_c_fresh python -c "from app.db import verify_migration_ready; verify_migration_ready()"
  RuntimeError: Database migrations are not current. Run `alembic -c alembic.ini upgrade head`.
  ```

  The guard works — it is simply not wired into the worker. The destructive-ordering half is
  `source-reviewed` only: `ingestion.py:211-212` deletes `CodeCard` then `SymbolEdge` before any
  rebuild, and `ingestion.py:239-240` commits inside the exception handler.
- Probable cause + diagnostic confidence: the guard was added to the ASGI startup hook, which the
  worker does not execute. Confidence: high for the asymmetry (verified); medium-high for the
  exact stuck-state mechanism (reasoned from source, not executed — running it would require an
  indexing job).
- Smallest safe next step: call `verify_migration_ready()` in `worker.py` before
  `Worker(...).work()`. One line, fails fast, no schema change, and it makes the claim in
  `docs/migrations.md:3-5` true. Independently, `ingestion.py`'s exception handler should
  `db.rollback()` before writing the failure state, so the terminal status is always recorded.
- Affected data/migrations/providers/cost: no migration. Prevents a class of stuck repositories
  and the wasted provider/compute spend of re-running an 11-minute index into a broken state.
- Recommended tests + acceptance criteria: a test that starts the worker entry point against a
  database at a stale revision and asserts a fast, explicit failure; and an ingestion test where
  a mid-run database error occurs, asserting the repository and job both reach a terminal
  `failed` state with a message. Acceptance: no code path can leave a repository non-terminal.
- Fix status: report-only

---

### REV-309

- ID: REV-309
- Category: DESIGN_GAP
- Severity: high
- Evidence level: `PostgreSQL integration-tested`
- Applies to: both
- Impact: `code_chunks.embedding` was created as `Vector()` with no dimension. pgvector refuses to
  build any ANN index on a dimensionless `vector` column, so `ivfflat` and `hnsw` are both
  structurally unavailable — not "not yet configured", *impossible* without a migration that fixes
  the dimension. That is the schema-level reason semantic retrieval computes cosine similarity in
  Python (`apps/api/app/search.py:40-43`, `_cosine`) instead of in SQL, and it means the current
  schema cannot scale semantic search at all, regardless of provider configuration. The live
  database has 22 900 chunks; the design ceiling is reached by loading all of them into the API
  process.
- Evidence:
  `apps/api/app/models.py:29` — `embedding:Mapped[list[float]|None]=mapped_column(Vector(),nullable=True)`.
  `apps/api/db_migrations/versions/20260808_0002_optional_embeddings.py:21` —
  `op.add_column("code_chunks", sa.Column("embedding", Vector(), nullable=True))`.
  On `review_scratch_c` at head `20260809_0008`, with pgvector 0.8.6:

  ```text
  CREATE INDEX test_hnsw ON code_chunks USING hnsw (embedding vector_cosine_ops);
  ERROR:  column does not have dimensions

  SELECT indexname FROM pg_indexes WHERE tablename='code_chunks';
   code_chunks_pkey | ix_chunks_repo_file | ix_code_chunks_content_hash
   ix_code_chunks_file_id | ix_code_chunks_repository_id
  ```

  No vector index exists and none can be created. `information_schema` reports the column as
  `udt_name = vector` with `character_maximum_length` NULL.
- Probable cause + diagnostic confidence: `Vector()` without an argument was chosen to keep the
  column provider-agnostic, since `vertex_embedding_dimensions` defaults to 768
  (`config.py:21`) but OpenRouter's `text-embedding-3-small` is 1 536. Dimension-agnosticism and
  ANN indexing are mutually exclusive in pgvector. Confidence: high — the error is definitive.
- Smallest safe next step: no schema change yet; this is a modelling decision. The options are to
  pin one dimension per deployment (`Vector(768)`) and add an `hnsw` index in the same migration,
  or to keep the column dimensionless and add a second, dimension-pinned column or table per
  active embedding model. Either way the choice must be explicit, because it also determines
  whether mixed-model embeddings can coexist — note `embedding_model` is already stored per row
  (`models.py:29`), which implies mixing is intended and therefore that a single pinned column is
  the wrong shape. Recommend documenting the constraint first, in `docs/migrations.md`, so nobody
  assumes an index is merely missing.
- Affected data/migrations/providers/cost: any dimension pinning requires re-embedding every
  chunk whose model does not match → full provider spend for the corpus. Do not attempt without
  the §4 cost gate. The live database has zero embeddings today
  (`embedding_provider = "none"`), so acting now is maximally cheap.
- Recommended tests + acceptance criteria: a PostgreSQL integration test asserting that the
  intended ANN index exists and that a semantic query's `EXPLAIN` uses it. Acceptance: semantic
  search executes in the database, with a stated dimension and a stated multi-model policy.
- Fix status: report-only

---

### REV-305

- ID: REV-305
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: `PostgreSQL integration-tested`
- Applies to: both
- Impact: removing a repository from a workspace at database level leaves every
  `workspace_dependencies` row that references it intact, because those rows have foreign keys to
  `workspaces` and `repositories` but none to `workspace_repositories`. Only the API route
  compensates, and it does so with a hand-written sweep. So the invariant "both endpoints are
  members of this workspace" (REV-304) can be broken *after the fact* by a completely valid
  operation, with no error anywhere. The resulting rows render as `declared_dependency` edges to a
  repository the workspace no longer contains — a scope leak presented as evidence (§3.1, §3.4).
  §3.8 is upheld in the important direction (membership removal does **not** delete the
  repository — verified), but the collateral cleanup is application-only.
- Evidence:
  `apps/api/app/main.py:141-146` — the compensating sweep, correct but manual:

  ```python
  db.execute(delete(WorkspaceDependency).where(WorkspaceDependency.workspace_id==workspace_id,(WorkspaceDependency.source_repository_id==repo_id)|(WorkspaceDependency.target_repository_id==repo_id))); db.delete(membership); db.commit()
  ```

  `apps/api/app/models.py:16-17` and `20260808_0003_workspaces.py:27-34` — `workspace_repositories`
  has no inbound foreign key from `workspace_dependencies`.

  Reproduced on `review_scratch_c` at head, bypassing the API:

  ```sql
  DELETE FROM workspace_repositories WHERE workspace_id='w1' AND repository_id='r2';   -- DELETE 1
  SELECT count(*) FROM repositories WHERE id='r2';                                     -- 1  (correct: §3.8 upheld)
  SELECT count(*) FROM workspace_dependencies
   WHERE workspace_id='w1' AND (source_repository_id='r2' OR target_repository_id='r2'); -- 6  (dangling)
  ```

  For contrast, the *workspace*-level cascade is genuinely enforced by the database:

  ```sql
  DELETE FROM workspaces WHERE id='w2';                                                -- DELETE 1
  SELECT count(*) FROM workspace_dependencies WHERE workspace_id='w2';                 -- 0
  ```

  So `delete_workspace` (`main.py:90-94`) performs sweeps the database would have done anyway —
  harmless, and necessary for the SQLite tests where foreign keys are not enforced — while
  `remove_workspace_repository` performs a sweep the database will *never* do.
- Probable cause + diagnostic confidence: `workspace_dependencies` models its endpoints as direct
  repository references rather than as membership references, so the database has no way to express
  the dependency. Confidence: high — reproduced.
- Smallest safe next step: change the two endpoint foreign keys to composite keys against
  `workspace_repositories(workspace_id, repository_id)` — which is already that table's primary
  key — with `ON DELETE CASCADE`. That single migration enforces the membership half of REV-304
  *and* makes this cleanup automatic, replacing application logic with a database constraint. It
  needs care: the pair `(workspace_id, source_repository_id)` must be a real FK, so a row can no
  longer reference a non-member at all. Verify on a throwaway database with the live-shaped data
  first (the live table is empty, so no backfill).
- Affected data/migrations/providers/cost: one migration replacing two foreign keys. No provider
  cost. Existing dangling rows in any environment would block the migration and must be swept
  first — a useful forcing function.
- Recommended tests + acceptance criteria: PostgreSQL integration test that declares a dependency,
  removes one endpoint's membership by direct SQL, and asserts the dependency row is gone while
  the repository row survives. Acceptance: no query can observe a dependency whose endpoints are
  not both members.
- Fix status: report-only

---

### REV-308

- ID: REV-308
- Category: BUG_CONFIRMED
- Severity: medium
- Evidence level: `PostgreSQL integration-tested`
- Applies to: integration (the three card indexes); both (`ix_workspace_repositories_repository_id`)
- Impact: `alembic check` fails against a database at head, which means `models.py` and the
  migration history do not agree. Today the practical consequence is mild — every missing index is
  covered in practice by a broader one — but it has two real costs. First, the next
  `alembic revision --autogenerate` (the documented workflow,
  `docs/migrations.md:40`) will emit these four unrelated index operations mixed into whatever
  change is actually intended, which is exactly how accidental schema churn ships. Second, it
  proves no CI gate runs `alembic check`, so the next divergence — which may not be benign — will
  also go unnoticed. `docs/migrations.md:43` asks reviewers to check "especially constraints,
  indexes" by hand; that has already failed three times.
- Evidence:

  ```text
  $ alembic -c alembic.ini check          # against review_scratch_c at 20260809_0008
  INFO  [alembic.autogenerate.compare] Detected added index 'ix_code_cards_repository_id' on ('repository_id',)
  INFO  [alembic.autogenerate.compare] Detected added index 'ix_code_cards_symbol_id' on ('symbol_id',)
  INFO  [alembic.autogenerate.compare] Detected added index 'ix_structural_cards_repository_id' on ('repository_id',)
  INFO  [alembic.autogenerate.compare] Detected removed index 'ix_workspace_repositories_repository_id' on 'workspace_repositories'
  FAILED: New upgrade operations detected: [...]
  ```

  Sources of each divergence:
  - `apps/api/app/models.py:32` declares `repository_id` and `symbol_id` with `index=True`;
    `20260809_0005_code_cards.py:33-34` creates only `ix_code_cards_repo_status` and
    `ix_code_cards_source_hash`.
  - `apps/api/app/models.py:35` declares `repository_id` with `index=True`;
    `20260809_0006_structural_cards.py:14-15` creates only `ix_structural_cards_repo_path` and
    `ix_structural_cards_content_fingerprint`.
  - `20260808_0003_workspaces.py:34` creates `ix_workspace_repositories_repository_id`, which
    `models.py:15-17` does not declare (see REV-314 — it is also a duplicate of the unique
    constraint's index).

  Why the missing indexes are currently harmless: `uq_code_cards_symbol_id` already provides a
  btree on `symbol_id`; `ix_code_cards_repo_status` covers `repository_id` as a leading column;
  `ix_structural_cards_repo_path` covers `repository_id` as a leading column. So this is drift,
  not a performance defect.
- Probable cause + diagnostic confidence: `0005` and `0006` were hand-written rather than
  autogenerated, and the `index=True` flags on the model columns were not mirrored. Confidence:
  high — `alembic check` is definitive.
- Smallest safe next step: run `alembic check` in CI. Then resolve each divergence in the cheaper
  direction: drop the redundant `index=True` flags from `models.py` (the composite indexes already
  cover them) and drop `ix_workspace_repositories_repository_id` in a migration, rather than
  creating three indexes nobody needs.
- Affected data/migrations/providers/cost: one small migration plus model edits. Dropping
  `ix_workspace_repositories_repository_id` removes a duplicate btree.
- Recommended tests + acceptance criteria: a CI step running `alembic upgrade head && alembic
  check` against a throwaway PostgreSQL + pgvector database. Acceptance: `check` exits zero on
  every branch.
- Fix status: report-only

---

### REV-310

- ID: REV-310
- Category: CORRECTNESS_RISK
- Severity: medium
- Evidence level: `PostgreSQL integration-tested` (live vocabulary) + `source-reviewed` (writers)
- Applies to: both
- Impact: two different state machines share one vocabulary with neither a `CHECK` constraint nor
  an enum on either column, and they disagree. `repositories.indexing_status` uses
  `{pending, indexing, ready, failed}`; `indexing_jobs.status` uses `{running, ready, failed}` at
  runtime with a model default of `pending` that no writer ever produces. So `'ready'` means
  "index is current and queryable" for a repository and "this job finished successfully" for a
  job, `'indexing'` and `'running'` mean the same thing in different tables, and
  `indexing_jobs.status = 'pending'` is dead. Nothing prevents a typo from persisting a status no
  reader understands, and the web layer would render it as an unstyled pill: `globals.css`
  defines only `.status-ready`, `.status-failed`, `.status-indexing`, `.status-pending`, applied
  via the interpolated class `status-${repo.indexing_status}` (`dashboard-client.tsx:80`).
- Evidence:
  Writers — `apps/api/app/ingestion.py`:

  ```text
  :190  IndexingJob(..., status='running', ...)
  :201  repo.indexing_status='indexing'
  :238  repo.indexing_status='ready'   ...   job.status='ready'
  :240  repo.indexing_status='failed'  ...   job.status='failed'
  ```

  Model defaults — `models.py:11` `indexing_status ... default='pending'` (repositories),
  `models.py:39` `status ... default='pending'` (jobs). `main.py:153` sets
  `indexing_status='pending'` explicitly at creation, so the repository default is real; no writer
  ever leaves a job at `pending`.

  Readers that depend on a literal:
  - `apps/web/app/chat/chat-client.tsx:13` and `apps/web/app/graph/graph-explorer.tsx:88` both
    filter `item.indexing_status === 'ready'` — a repository not in exactly that state is silently
    absent from both pickers.
  - `apps/web/app/dashboard-client.tsx:62-63` counts `=== 'ready'` and `=== 'indexing'`.
  - `apps/web/lib/repositories.ts:5` types it as a bare `string`.
  - `main.py:337-341` (`GET /api/jobs/{job_id}`) returns `j.status` verbatim; `grep` finds no web
    consumer of job status at all.
  - On `main` only, `apps/api/app/reconcile.py:42,52,56-57` selects jobs `status == 'running'` and
    writes `'failed'` to both the job and the repository — consistent with `ingestion.py`, and
    unaffected by the `'ready'` oddity because it only inspects `'running'`.

  Live vocabulary, read-only:

  ```text
  $ psql -d knowledgeway -c "SELECT status, kind, count(*) FROM indexing_jobs GROUP BY 1,2;"
   failed | full | 2
   ready  | full | 2
  $ psql -d knowledgeway -c "SELECT indexing_status, count(*) FROM repositories GROUP BY 1;"
   ready | 1
  ```

  Neither column has a `CHECK` constraint in `20260808_0001_initial_schema.py:26,50` — both are
  plain `sa.String(20), nullable=False`.
- Probable cause + diagnostic confidence: the job table reused the repository status strings
  rather than defining its own lifecycle. Confidence: high.
- Smallest safe next step: do not rename anything yet — renaming `'ready'` to `'succeeded'` for
  jobs would break `reconcile.py` on `main` and any stored row. Instead add a `CHECK` constraint
  per column pinning the vocabulary each one actually uses, in one migration. That is
  non-breaking against live data (verified: only `ready`/`failed` present for jobs, only `ready`
  for repositories) and makes any future drift fail loudly at the write.
- Affected data/migrations/providers/cost: one migration adding two `CHECK` constraints; must
  include the historical values present in every environment. No provider cost.
- Recommended tests + acceptance criteria: a PostgreSQL test asserting an invalid status is
  rejected, plus a unit test enumerating the vocabulary in one place shared by the API and the
  web types. Acceptance: every status literal a reader compares against is in a single
  declared set, and the database rejects anything outside it.
- Fix status: report-only

---

### REV-311

- ID: REV-311
- Category: PERFORMANCE_RISK
- Severity: medium
- Evidence level: `PostgreSQL integration-tested` (DDL cost) + `source-reviewed` (lock exposure)
- Applies to: integration
- Impact: `0008`'s `ALTER TABLE symbol_edges` requires `ACCESS EXCLUSIVE`. The DDL itself is
  cheap — measured 10.360 ms on 136 566 rows — but lock *acquisition* is unbounded because no
  `lock_timeout` is set anywhere in the stack. A full index run writes `symbol_edges` (deleting
  and re-inserting every row for the repository) and takes a measured 11 m 37 s on the live
  corpus, holding `ROW EXCLUSIVE` throughout. Running `alembic upgrade head` during that window
  makes the migration wait, and because `ACCESS EXCLUSIVE` is queued ahead of them, **every
  subsequent reader of `symbol_edges` also blocks** — which is every graph, subgraph, callers and
  callees route. The observable effect is a total stall of graph functionality for up to the
  remaining duration of the index job, from a migration that looks instantaneous when tested on an
  idle database.
- Evidence:
  `20260809_0008_symbol_edge_target_text.py:16` — `op.alter_column("symbol_edges", "target_name", ...)`.
  `grep -rn "lock_timeout\|statement_timeout" apps/ infra/ docker-compose.yml` → no matches.
  `env.py:38-41` wraps the whole batch in one transaction (no `transaction_per_migration`), so the
  lock is held until the entire upgrade commits — for a `0004 → 0008` run that is short, but the
  property is worth knowing.

  Measured on `review_scratch_c` with 136 566 rows (matching the live count exactly), `\timing on`:

  ```text
  ALTER TABLE symbol_edges ALTER COLUMN target_name TYPE text;          -- 10.360 ms
  ALTER TABLE symbol_edges ALTER COLUMN target_name TYPE varchar(512);  -- 884.706 ms  (rewrite)
  heap 13 MB, ix_symbol_edges_target_name 11 MB
  ```

  Writer side, `source-reviewed`: `apps/api/app/ingestion.py:212` deletes all edges for the
  repository and `:232` `_persist_edges` re-inserts them, inside the single long transaction of
  `index_repository`. §4 forbids provoking this live, so the lock interaction is reasoned, not
  executed.
- Probable cause + diagnostic confidence: standard PostgreSQL lock-queue behaviour, not a coding
  defect. Confidence: high for the DDL measurements (executed); high for the lock-queue mechanism
  (documented PostgreSQL semantics); the migration-during-index scenario was deliberately **not**
  reproduced.
- Smallest safe next step: set `lock_timeout` for migrations only — a `SET LOCAL lock_timeout =
  '5s'` at the top of `env.py`'s `run_migrations_online`, so a migration that cannot get its lock
  fails fast and retryably instead of stalling the API. Document in `docs/migrations.md` that
  migrations must not be run while an indexing job is in flight, which is the same §4 gate the
  review itself operated under.
- Affected data/migrations/providers/cost: no schema change; one `env.py` line and one doc
  paragraph. Prevents an availability incident, not a data loss.
- Recommended tests + acceptance criteria: an integration test holding a `ROW EXCLUSIVE` lock on
  `symbol_edges` in one session while running `alembic upgrade head` in another. Acceptance: the
  migration fails within `lock_timeout` with a clear message and leaves `alembic_version`
  unchanged.
- Fix status: report-only

---

### REV-312

- ID: REV-312
- Category: DESIGN_GAP
- Severity: medium
- Evidence level: `PostgreSQL integration-tested`
- Applies to: both
- Impact: two related gaps in first-boot behaviour. `verify_migration_ready` reads
  `alembic_version` before checking that it exists, so on a database that has never been migrated
  it raises a raw driver error instead of its own message — the operator sees
  `psycopg.errors.UndefinedTable: relation "alembic_version" does not exist` rather than
  "run `alembic upgrade head`", which is the one situation where the friendly message matters most.
  And `docker-compose.yml` contains no migration step at all: the `api` service goes straight to
  `uvicorn`, so `docker compose up` against a fresh `postgres-data` volume crash-loops the API
  until someone runs Alembic by hand. The procedure *is* documented
  (`README.md:26-27` → `docs/migrations.md:11-18`), so this is a rough edge rather than a missing
  capability — but it is the first thing a new operator meets.
- Evidence:
  `apps/api/app/db.py:18-27` — the guard reads the table unconditionally:

  ```python
  with engine.connect() as connection:
      current_heads = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
  if current_heads != expected_heads:
      raise RuntimeError("Database migrations are not current. Run `alembic -c alembic.ini upgrade head`.")
  ```

  Both cases exercised against throwaway databases:

  ```text
  # A) fresh database, never migrated
  sqlalchemy.exc.ProgrammingError
  (psycopg.errors.UndefinedTable) relation "alembic_version" does not exist

  # B) same database after `alembic upgrade 20260808_0004`, code head 20260809_0008
  RuntimeError: Database migrations are not current. Run `alembic -c alembic.ini upgrade head`.
  ```

  Case B is the live configuration and confirms the brief's reason for not migrating the live
  database. Case A is the gap.
  `docker-compose.yml:18-25` — the `api` service has `build`, `env_file`, `ports`, `volumes`,
  `depends_on` and nothing else; the image `CMD` is `uvicorn app.main:app` (`Dockerfile:9`).
- Probable cause + diagnostic confidence: the guard was written for the "stale database" case,
  which is the common one after the first deploy. Confidence: high — both cases executed.
- Smallest safe next step: wrap the `SELECT` so a missing `alembic_version` produces the same
  `RuntimeError` with a "database has never been migrated" variant. Three lines, no schema change.
  Adding a migration step to compose is a separate, larger decision (an init container or an
  entrypoint wrapper) and should not be bundled with it.
- Affected data/migrations/providers/cost: none. Error-message and operations quality only.
- Recommended tests + acceptance criteria: a PostgreSQL integration test calling
  `verify_migration_ready()` against an empty database. Acceptance: `RuntimeError` naming the
  remedy, never a driver exception.
- Fix status: report-only

---

### REV-317

- ID: REV-317
- Category: TEST_GAP
- Severity: medium
- Evidence level: `unit/API-tested`
- Applies to: both
- Impact: every finding in this report that is graded `PostgreSQL integration-tested` was
  invisible to the existing suite, because the suite has no PostgreSQL. All 50 tests run against
  SQLite in memory, where `NULL`-distinctness in unique indexes, `ON DELETE` behaviour,
  `NO ACTION` end-of-statement checks, btree entry limits, `json` vs `jsonb`, `Vector` dimensions
  and Alembic upgrade/downgrade are all either absent or differently shaped. Separately, the §3
  "no startup DDL" invariant is guarded by a string search of one file, which would not notice
  DDL added to `db.py`, `worker.py` or `ingestion.py`, and no test ever executes
  `verify_migration_ready`.
- Evidence:
  `apps/api/tests/test_migrations.py:26-29` is the entire invariant check:

  ```python
  def test_normal_startup_has_no_create_all_ddl():
      source = (API_DIR / "app" / "main.py").read_text()
      assert "create_all" not in source
      assert "verify_migration_ready" in source
  ```

  The invariant itself does hold in application code — verified independently:
  `grep -rn "create_all\|metadata\.create\|CREATE TABLE\|CREATE INDEX\|ALTER TABLE" apps/ --include="*.py"`
  excluding `db_migrations` matches only
  `tests/test_incremental_structural_cards.py:13` and `tests/test_ingestion_graph.py:22`. No
  application module performs DDL, and `@app.on_event('startup')` (`main.py:19-20`) calls only
  `verify_migration_ready()`. So the claim is true; the test that guards it is weak.

  Engine inventory across the suite:

  ```text
  tests/test_workspaces_api.py:12               create_engine("sqlite://", ...)
  tests/test_incremental_structural_cards.py:13 create_engine('sqlite://')
  tests/test_ingestion_graph.py:21              create_engine("sqlite://")
  ```

  No `DATABASE_URL` or `postgresql` reference anywhere in `apps/api/tests`. Verified safe before
  running: `TestClient(app)` is used without a context manager
  (`test_workspaces_api.py:26-27`), so FastAPI startup events — and therefore
  `verify_migration_ready()` and any connection to the live database — never fire.

  Suite result inside a throwaway container against the read-only worktree:

  ```text
  $ python -m pytest tests -q -p no:cacheprovider
  50 passed, 20 warnings in 1.20s
  ```

  What the workspace test does cover, and it is genuinely useful: exclusive membership including
  the idempotent same-workspace case and the `409` cross-workspace case
  (`test_workspaces_api.py:35-39`), the `422` self-dependency and non-member cases (`:57-58`), and
  that workspace deletion removes memberships and dependencies (`:60-62`). What it cannot cover is
  whether the *database* agrees — and per REV-304 and REV-305, it does not.
- Probable cause + diagnostic confidence: SQLite keeps the suite fast and dependency-free; no
  PostgreSQL fixture was ever added. Confidence: high.
- Smallest safe next step: add one PostgreSQL + pgvector integration fixture that creates a
  throwaway database, runs `alembic upgrade head`, yields a session, and drops it — the exact
  pattern this review used manually. The first three tests to put in it: the `NULL`-duplicate
  case (REV-301), repository deletion with a conversation (REV-300), and `alembic upgrade head`
  followed by `alembic check` (REV-308). Keep the SQLite suite as the fast tier.
- Affected data/migrations/providers/cost: CI needs a PostgreSQL service with pgvector — the
  `pgvector/pgvector:pg16` image already in use. No provider cost.
- Recommended tests + acceptance criteria: as above, plus a migration test asserting round-trip
  `upgrade head` → `downgrade base` → `upgrade head` on a data-bearing database. Acceptance: every
  invariant claimed in §3 has a test at the level it is actually enforced.
- Fix status: report-only

---

### REV-313

- ID: REV-313
- Category: DOCUMENTATION_GAP
- Severity: low
- Evidence level: `source-reviewed` + `PostgreSQL integration-tested` (extension inventory)
- Applies to: both
- Impact: `docs/migrations.md` overstates two things. It claims both the API *and* the worker
  check their migration head at startup — the worker does not (REV-307) — and it presents Alembic
  as the sole owner of schema state while `infra/init.sql` creates `pg_trgm`, which no migration
  creates. A deployment that does not use this compose file, or that recreates the database
  without re-running the init script, gets `vector` (from `0001`) but not `pg_trgm`. Nothing uses
  `pg_trgm` today, so there is no functional break — but "Alembic for every schema change" is not
  currently true, and the discrepancy is exactly the kind that surfaces later as an unreproducible
  environment.
- Evidence:
  `docs/migrations.md:3-5`:

  > "Knowledge Way uses Alembic for every schema change. The API and worker never
  > create or alter tables during normal startup. Startup checks that the database
  > has exactly the revision(s) required by this build and fails fast otherwise."

  Sentence two is true (verified — see REV-317). Sentence three is true for the API and false for
  the worker (`apps/api/app/worker.py` has no guard). Sentence one is contradicted by
  `infra/init.sql`:

  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
  ```

  mounted at `docker-compose.yml:9` as `/docker-entrypoint-initdb.d/01-extensions.sql:ro`, which
  runs once at cluster initialisation only. Live inventory versus a database built purely from
  migrations:

  ```text
  knowledgeway      → plpgsql, vector 0.8.6, pg_trgm 1.6
  review_scratch_c  → plpgsql, vector            (after `alembic upgrade head`)
  ```

  `grep -rn "trgm\|similarity" apps/ --include="*.py"` → no matches. The lexical search path uses
  `ILIKE '%term%'` (`apps/api/app/search.py:65,68,72,77`), which cannot use a btree index and has
  no trigram index to use either — so `pg_trgm` is installed and unused, while the query shape
  that would benefit from it exists.
- Probable cause + diagnostic confidence: `pg_trgm` was added to the init script in anticipation
  of trigram search that was never wired up, and the worker guard sentence was written
  aspirationally. Confidence: high.
- Smallest safe next step: correct the two sentences in `docs/migrations.md` — one paragraph — and
  decide `pg_trgm`'s fate: either move `CREATE EXTENSION IF NOT EXISTS pg_trgm` into a migration
  (making the schema reproducible from Alembic alone) or remove it from `infra/init.sql`.
  Note `0001` already sets the precedent by creating `vector` in a migration, with the rationale
  spelled out at `20260808_0001_initial_schema.py:22-23`.
- Affected data/migrations/providers/cost: at most one trivial migration. No data risk —
  `CREATE EXTENSION IF NOT EXISTS` is idempotent.
- Recommended tests + acceptance criteria: assert the expected extension set after
  `alembic upgrade head` on a virgin database. Acceptance: a database built from migrations alone
  matches a database built via compose.
- Fix status: report-only

---

### REV-314

- ID: REV-314
- Category: OPTIMIZATION_OPPORTUNITY
- Severity: low
- Evidence level: `PostgreSQL integration-tested`
- Applies to: both
- Impact: `workspace_repositories` carries three btree indexes although its logical key is
  `repository_id` alone — which is precisely what `uq_workspace_repositories_repository_id`
  asserts. The composite primary key `(workspace_id, repository_id)` is therefore weaker than the
  unique constraint next to it and adds nothing, and `ix_workspace_repositories_repository_id` is
  an exact duplicate of the unique constraint's implicit index. Three indexes on a join table that
  will hold one row per repository. Cost is negligible at current scale; the real cost is that the
  key shape misrepresents the model — a reader sees a composite PK and concludes many-to-many.
- Evidence:
  Live schema (`\d workspace_repositories`, identical on the throwaway database at head):

  ```text
  Indexes:
      "workspace_repositories_pkey" PRIMARY KEY, btree (workspace_id, repository_id)
      "ix_workspace_repositories_repository_id" btree (repository_id)
      "uq_workspace_repositories_repository_id" UNIQUE CONSTRAINT, btree (repository_id)
  ```

  `apps/api/app/models.py:16-17` declares the composite PK and the unique constraint but **not**
  the plain index; `20260808_0003_workspaces.py:29-34` emits all three. `alembic check` reports the
  third as a "removed index" (present in the database, absent from the models) — see REV-308.
- Probable cause + diagnostic confidence: the table was first modelled as a plain many-to-many
  association (composite PK plus an index on each side) and the exclusivity requirement was later
  bolted on as an extra unique constraint, without revisiting the key. Confidence: high.
- Smallest safe next step: drop `ix_workspace_repositories_repository_id` — it is provably
  redundant and is already flagged by `alembic check`. Leave the primary key alone: changing it is
  a larger, riskier migration for no measurable gain, and it is only cosmetic. Record the
  intent in a comment on the model instead.
- Affected data/migrations/providers/cost: one `op.drop_index`. No data risk.
- Recommended tests + acceptance criteria: fold into the REV-308 `alembic check` gate.
  Acceptance: `check` clean; exclusive membership tests still pass.
- Fix status: report-only

---

### REV-315

- ID: REV-315
- Category: OPTIMIZATION_OPPORTUNITY
- Severity: low
- Evidence level: `PostgreSQL integration-tested`
- Applies to: both
- Impact: all six JSON columns materialise as PostgreSQL `json`, not `jsonb`. `json` stores the
  original text and re-parses on every access, supports no containment or path operators worth
  indexing, cannot be GIN-indexed and has no equality operator. Every current use is
  write-and-read-whole (`indexing_progress`, `progress`, `citations`, `details`, `facts`), so
  nothing is broken — but any future query such as "which repositories are stuck in phase
  `scanning`", "which code cards claim a given fact" or "which structural cards changed" will
  require a full scan and a cast. Switching later is a rewrite of the affected tables; switching
  now, while several of these tables are empty or small, is nearly free.
- Evidence: `information_schema.columns` on the throwaway database at head `20260809_0008`:

  ```text
  code_cards.details             json
  indexing_jobs.progress         json
  messages.citations             json
  repositories.indexing_progress json
  structural_cards.facts         json
  ```

  Cause: `sa.JSON()` on the PostgreSQL dialect maps to `JSON`, not `JSONB` — used at
  `20260808_0001_initial_schema.py:26,50,54`, `20260809_0005_code_cards.py:26`,
  `20260809_0006_structural_cards.py:13`, and declared as `JSON` in `models.py:11,32,35,39,43`.
  `sa.dialects.postgresql.JSONB` is the alternative.
- Probable cause + diagnostic confidence: `sa.JSON()` is the portable default and keeps the SQLite
  test suite working; `JSONB` would too, since SQLAlchemy falls back on SQLite. Confidence: high.
- Smallest safe next step: none required today — record the decision. If any of these columns is
  ever queried by content, convert it then, in a dedicated migration with a measured rewrite
  window (`ALTER COLUMN ... TYPE jsonb USING ...::jsonb` rewrites the table and takes
  `ACCESS EXCLUSIVE`, so REV-311's lock caution applies).
- Affected data/migrations/providers/cost: a future migration per column, with a table rewrite.
  `repositories` and `indexing_jobs` are tiny; `messages` grows with chat usage.
- Recommended tests + acceptance criteria: only if converted — assert the column type and that a
  containment query uses the GIN index. Acceptance: no behavioural change for existing readers.
- Fix status: report-only

---

### REV-316

- ID: REV-316
- Category: CORRECTNESS_RISK
- Severity: low
- Evidence level: `manual live acceptance` + `PostgreSQL integration-tested` (column types)
- Applies to: both
- Impact: every timestamp column is `timestamp without time zone`, populated by
  `datetime.utcnow()` — a naive datetime that carries no offset — and serialised by FastAPI
  without one. A consumer receiving `"2026-08-10T11:49:38.119422"` and passing it to JavaScript's
  `new Date(...)` interprets it as **local** time, which on the review host (Europe/Berlin, summer)
  is two hours off. The integration branch's web UI does not currently render any of these fields,
  so nothing is visibly wrong today; the exposure is to API and MCP consumers, and to whatever UI
  first displays "last indexed at". Provenance-adjacent (§3.6) but not provenance-breaking: the
  commit SHA, not the timestamp, is the evidence anchor.
- Evidence:
  `apps/api/app/models.py:8` — `def now(): return datetime.utcnow()`, used as `default`/`onupdate`
  for every timestamp column. All 26 timestamp columns report
  `timestamp without time zone` in `information_schema.columns` on the throwaway database.
  Live response, read-only:

  ```text
  $ curl -s http://localhost:8000/api/repositories | jq '.[0] | {created_at,last_indexed_at,last_sync_at}'
  { "last_indexed_at": "2026-08-10T11:49:38.119422",
    "last_sync_at":    "2026-08-10T11:49:38.119427",
    "created_at":      "2026-08-10T11:29:06.993709" }
  ```

  No `Z`, no offset. Latency of exposure confirmed by
  `grep -rn "created_at\|last_indexed_at\|toLocale\|new Date" apps/web` → one match only, a type
  declaration at `apps/web/lib/repositories.ts:9`; no component renders a timestamp.
  Secondary note: `datetime.utcnow()` is deprecated from Python 3.12; the images run 3.11, so this
  is not yet a runtime warning.
- Probable cause + diagnostic confidence: `DateTime` plus `utcnow()` is the common SQLAlchemy
  default and works until a client has to interpret the value. Confidence: high.
- Smallest safe next step: nothing schema-level yet. The cheapest correct fix at the boundary is
  to make the API emit an explicit UTC offset. Converting the columns to `timestamptz` is the
  proper fix and is safe *because* the stored values are already UTC — `ALTER COLUMN ... TYPE
  timestamptz USING <col> AT TIME ZONE 'UTC'` — but it rewrites tables and should be one
  deliberate migration, with `datetime.now(timezone.utc)` replacing `utcnow()` in the same change.
- Affected data/migrations/providers/cost: one migration touching 26 columns across 10 tables,
  with rewrites. `files`, `symbols` and `code_chunks` are the large ones. No provider cost.
- Recommended tests + acceptance criteria: an API test asserting every serialised timestamp
  matches an offset-bearing ISO-8601 pattern. Acceptance: no consumer can misread a timestamp's
  zone.
- Fix status: report-only

---

### REV-318

- ID: REV-318
- Category: info (verified positive — answers §5.C "exklusive Workspace-Mitgliedschaft, parallele
  Inserts und Rennen bei Membership-Änderungen")
- Severity: info
- Evidence level: `PostgreSQL integration-tested` (race) + `source-reviewed` (API translation) +
  `unit/API-tested` (existing coverage)
- Applies to: both
- Impact: none — this is the finding that a claimed invariant genuinely holds, recorded so it is
  not re-litigated. `UniqueConstraint('repository_id')` **does** guarantee one workspace per
  repository under concurrent inserts, and the API translates the violation into the right status
  codes including the idempotent case.
- Evidence:
  Race reproduced on `review_scratch_c` at head with two concurrent psql sessions. Session A
  inserted `(w3, r4)` and held its transaction open for 3 s; session B waited 1 s, then attempted
  `(w4, r4)`:

  ```text
  [A] BEGIN / INSERT 0 1 / pg_sleep(3) / COMMIT
  [B] BEGIN
  [B] ERROR:  duplicate key value violates unique constraint "uq_workspace_repositories_repository_id"
  [B] DETAIL: Key (repository_id)=(r4) already exists.
  [B] ROLLBACK

  SELECT workspace_id, repository_id FROM workspace_repositories WHERE repository_id='r4';
   w3 | r4        -- exactly one row
  ```

  Session B **blocked** on the unique index for the remainder of A's transaction rather than
  reading a stale snapshot, then failed on A's commit. Under `READ COMMITTED` the API's own
  pre-check (`main.py:130`) cannot see A's uncommitted row, so the insert is the real guard — and
  it holds. Also confirmed at the single-session level: a second `INSERT (w2, r1)` for an already
  assigned repository produced the same `23505` violation.

  The surfaced error is SQLSTATE `23505` → SQLAlchemy `IntegrityError`, and `main.py:135-139`
  handles it correctly, including the subtle case:

  ```python
  try: db.commit()
  except IntegrityError:
   db.rollback(); membership=db.scalar(select(WorkspaceRepository).where(WorkspaceRepository.repository_id==repo_id))
   if membership and membership.workspace_id==workspace_id: return {'workspace_id':workspace_id,'repository_id':repo_id}
   raise HTTPException(409,'Repository already belongs to another workspace')
  ```

  Two concurrent requests adding the *same* repository to the *same* workspace both return `200`
  (idempotent), while a different workspace gets `409` — never a `500`, and never two memberships.
  `apps/api/tests/test_workspaces_api.py:35-39` covers the sequential form of both cases.
- Probable cause + diagnostic confidence: correct by construction. Confidence: high.
- Smallest safe next step: none. Worth preserving the idempotent branch explicitly in any future
  refactor — it is easy to lose and not obvious from the outside.
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: add the *concurrent* form to the PostgreSQL fixture
  proposed in REV-317, since the current test only covers the sequential path. Acceptance: two
  parallel requests yield exactly one membership and no `500`.
- Fix status: report-only

---

### REV-319

- ID: REV-319
- Category: info (verified positive — answers §5.C "Risiko, dass neue Migrationen
  Index-Provenienz, Code Cards, Embeddings oder laufende Jobs beschädigen")
- Severity: info
- Evidence level: `PostgreSQL integration-tested`
- Applies to: integration
- Impact: none for the upgrade direction. `0005`–`0008` are safe with respect to existing data;
  the risks that do exist are the *downgrade* of `0008` (REV-302), the new insert-time failure
  mode it enables (REV-303), and its lock exposure (REV-311) — not data destruction on upgrade.
- Evidence, per revision:
  - `0005_code_cards` and `0006_structural_cards` create new tables only
    (`op.create_table` plus indexes; no `alter`, no `drop`, no `UPDATE`). They cannot touch
    existing rows. Note `code_cards` is additionally protected across re-indexing at the
    application level: `ingestion.py:209` `_snapshot_code_cards` preserves payloads before
    symbol IDs are replaced and `:233` `_restore_code_cards` writes them back.
  - `0007_requested_revision` is `ADD COLUMN ... String(64) nullable=True` — no default, no
    rewrite on PostgreSQL 11+. Existing repositories get `NULL`, which `ingestion.py:197-198`
    already treats as "track `origin/HEAD`", i.e. the pre-existing behaviour.
  - `0008_symbol_edge_target_text` is a widening `varchar(512) → text`, binary-coercible and
    therefore metadata-only. Measured directly on 136 566 rows: **10.360 ms**, and the row count
    and contents were unchanged afterwards. It does **not** rewrite or drop edge data.
  - No revision touches `code_chunks.embedding` or `embedding_model` after `0002` created them;
    `grep` over `db_migrations/versions` finds `embedding` only in `0002`.
  - Index provenance columns (`indexed_commit_sha` on `files`, `code_chunks`, `code_cards`,
    `structural_cards`) are never altered or backfilled by `0005`–`0008`.
  - Running jobs: the only lock-relevant statement in the whole set is `0008`'s `ALTER TABLE`
    (REV-311). Because `env.py` runs the batch in a single transaction, a `0004 → 0008` upgrade is
    atomic — directly observed when the failed `0008` downgrade left `alembic_version` at
    `20260809_0008` with the column type intact.

  Full-cycle verification: `upgrade head` from an empty database (all 8 pass), `downgrade base`
  (all 8 pass, only `alembic_version` remains), `upgrade head` again (passes), then 136 566 rows
  loaded and `0008` cycled down and up.
- Probable cause + diagnostic confidence: n/a. Confidence: high — executed.
- Smallest safe next step: none. When the live database is eventually migrated `0004 → 0008`,
  do it with no indexing job in flight (REV-311) and accept that `0008` is one-way (REV-302).
- Affected data/migrations/providers/cost: none.
- Recommended tests + acceptance criteria: keep the data-bearing round-trip described in REV-317
  as a standing migration test.
- Fix status: report-only

---

## Live-database attestation

Required by the workstream brief, and material to §10 ("keine Produktions-/Schema-/Provider-
Änderung als Teil des Analyseauftrags still durchgeführt").

**Throwaway databases created and dropped.** Two were created on the running `postgres` container
and both were dropped. All migration runs, `ALTER TABLE` measurements, integrity experiments and
the concurrency race were executed exclusively against them.

```text
$ docker compose exec -T postgres psql -U knowledgeway -d knowledgeway \
    -c "DROP DATABASE review_scratch_c;" -c "DROP DATABASE review_scratch_c_fresh;"
DROP DATABASE
DROP DATABASE

$ docker compose exec -T postgres psql -U knowledgeway -d knowledgeway \
    -tAc "SELECT datname FROM pg_database WHERE datistemplate=false ORDER BY 1;"
knowledgeway
postgres
```

**`knowledgeway` schema unchanged.** No `alembic upgrade`, `downgrade` or `stamp` was ever run
against it, and no `CREATE`/`ALTER`/`DROP` statement was issued against it other than the two
`CREATE DATABASE` / `DROP DATABASE` statements above, which do not alter its schema. Re-queried
at the end of the review:

```text
$ docker compose exec -T postgres psql -U knowledgeway -d knowledgeway -c "SELECT version_num FROM alembic_version;"
  version_num
---------------
 20260808_0004
(1 row)

$ ... -tAc "SELECT (SELECT count(*) FROM information_schema.tables WHERE table_schema='public') AS tables,
             (SELECT count(*) FROM repositories) AS repos, (SELECT count(*) FROM workspaces) AS workspaces,
             (SELECT count(*) FROM symbol_edges) AS edges, (SELECT count(*) FROM indexing_jobs) AS jobs;"
12|1|0|136566|4

$ ... -tAc "SELECT data_type, character_maximum_length FROM information_schema.columns
             WHERE table_name='symbol_edges' AND column_name='target_name';"
character varying|512
```

Head still `20260808_0004`; 12 tables; 1 repository; 0 workspaces; 136 566 `symbol_edges`;
4 indexing jobs — identical to the values recorded in `01-runtime-and-provenance.md`. In
particular `symbol_edges.target_name` is still `character varying(512)`, proving `0008` was never
applied to the live database.

All reads against `knowledgeway` were `SELECT`, `\d`, `\d+` or `GET` requests to
`http://localhost:8000`. No prohibited endpoint was called. The `pytest` run executed inside a
throwaway container against a read-only mount of the review worktree and, as verified before
running it, uses SQLite in memory exclusively and never opens a PostgreSQL connection.

## Not assessed

- **Whether the parser can actually emit a `target_name` over ~2 704 incompressible bytes**
  (REV-303). The btree limit and the exact threshold are measured, but the *probability* of the
  trigger depends on how `parser_facts.py` composes reference expressions across the supported
  languages. That analysis belongs to workstream E and would need a corpus run. The finding is
  therefore graded on the mechanism, which is proven, not on the likelihood.
- **The migration-during-indexing lock pile-up (REV-311) was not reproduced.** Provoking it
  requires an active indexing job holding `ROW EXCLUSIVE` on `symbol_edges`, i.e. starting
  long-running work, which §4 and the workstream brief both forbid. The DDL cost and the absence
  of `lock_timeout` are measured; the queueing behaviour is documented PostgreSQL semantics,
  labelled as reasoned rather than executed.
- **The stuck-repository mechanism in REV-307 was not executed.** Confirming that the `except`
  handler in `ingestion.py:240` itself fails on an aborted transaction would require running a
  real index against a mismatched schema — a clone plus an 11-minute job. The guard asymmetry it
  depends on *is* verified; the downstream state is `source-reviewed`.
- **Migration behaviour against a database holding realistic `code_cards`, `structural_cards` or
  embedding data.** The throwaway database was seeded with 136 566 `symbol_edges` to match the
  live count, but the card tables and `code_chunks.embedding` were left empty because no live rows
  exist (`code_cards`/`structural_cards` do not exist at head `0004`, and
  `embedding_provider = "none"`). Migration safety for those tables is therefore
  `source-reviewed` — which is sufficient, since `0005` and `0006` only create them.
- **Live workspace behaviour of any kind.** `workspaces` is empty, there is no UI path to create
  one, and creating repositories to populate a workspace would trigger billable/long indexing.
  Every workspace finding is `source-reviewed` or verified at the SQL layer on the throwaway
  database; none is `browser E2E verified`.
- **`main`-only working-tree changes beyond `reconcile.py`.** Only `apps/api/app/reconcile.py` was
  read, and only to confirm the live status vocabulary in REV-310. The other six modified files
  are outside this workstream's scope.
- **Whether `ix_symbol_edges_target_name` has any reader at all.** Relevant to REV-303's cheapest
  fix (dropping the index). `main.py` filters edges in Python and never predicates on
  `target_name`, but `search.py`, `ingestion.py` and the MCP bridge were not exhaustively traced
  for it. Verify before dropping.
- **`data/`** — excluded per the brief; the cloned pydantic-ai working copy is indexed payload,
  not project source.
