# Incremental structural-card evaluation fixture

**Purpose:** a deterministic, Git-backed regression dataset for change-aware repository indexing.

## Snapshot v1 labels

| Fact | Expected location |
| --- | --- |
| Python package | `apps/api` via `apps/api/__init__.py` |
| Python symbol | `apps.api.users.find_user` |
| TypeScript UI module | `apps/web/page.ts` |
| PHP shared boundary | `shared/auth.php` |

## Snapshot v2 change labels

- `apps/api/users.py`: adds `delete_user`; the `apps/api` directory card fingerprint **must change**.
- `shared/auth.php`: deleted; `shared` directory card **must be removed**.
- `docs/contract.md`: added; `docs` directory card **must be created**.
- `apps/web/page.ts`: unchanged; its directory-card content fingerprint **must stay identical** while its indexed commit changes.

The executable evaluation is `apps/api/tests/test_incremental_structural_cards.py`. It creates two real Git commits, invokes full ingestion followed by sync ingestion, and checks the labels above. It is intentionally deterministic and has no external model/API dependency.
