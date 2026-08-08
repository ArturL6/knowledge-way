# Database migrations

Knowledge Way uses Alembic for every schema change. The API and worker never
create or alter tables during normal startup. Startup checks that the database
has exactly the revision(s) required by this build and fails fast otherwise.

The PostgreSQL image must include pgvector. The baseline migration creates the
`vector` extension with `CREATE EXTENSION IF NOT EXISTS vector`; this requires a
database role with permission to create that extension.

## Apply migrations

From `apps/api`, with `DATABASE_URL` set:

```bash
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
```

Inspect the current database revision with:

```bash
alembic -c alembic.ini current
```

For an existing database created before Alembic was introduced, first back up
the database and verify that it matches the initial schema. Then record the
baseline without re-running table creation:

```bash
alembic -c alembic.ini stamp 20260808_0001
```

Only use `stamp` for a verified pre-existing schema. A new empty database must
use `upgrade head`.

## Create a future migration

1. Change the SQLAlchemy model(s).
2. Generate a candidate revision: `alembic -c alembic.ini revision --autogenerate -m "describe change"`.
3. Review generated SQL, especially constraints, indexes, data backfills, and
   PostgreSQL/pgvector-specific operations.
4. Test both upgrade and downgrade against PostgreSQL with pgvector before
   merging. Do not add runtime DDL as a fallback.