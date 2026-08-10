# 07 — Security, Permissions and Operational Boundaries

> Workstream **§5.F** of `docs/CODING_AGENT_COMPREHENSIVE_REVIEW_PROGRAM.md`.
> Builds on the shared brief `01-runtime-and-provenance.md` — targets, safety gates, live DB
> state and exclusions are defined there and not restated.
> Static target: `c122529` = `origin/integration/consolidated-verified` (read-only worktree).
> Live target: `main` + 7 uncommitted files, running compose project `knowledge-way`.
> `data/` excluded throughout. **No secret value appears anywhere in this document.**

## Summary

There is **no authentication and no authorization anywhere in this system**. That is the
documented intent for a local single-user stack, and on its own it would be a `medium`. It is
not a `medium` here, because the default `docker-compose.yml` publishes **four** ports on
`0.0.0.0` **and** `::` — verified live — so the actual trust boundary is not the loopback
interface, it is the whole layer-2 network the host sits on (`192.168.2.0/24` in this
deployment). Two of those four ports are datastores that accept unauthenticated or
default-credentialled writes, and both convert directly into remote code execution:

- **Redis** on `0.0.0.0:6379` answers `CONFIG GET` from a non-loopback address with
  `protected-mode no`, no `requirepass` and the `default` nopass ACL user. RQ 2.0.0's default
  serializer is verified to be `pickle`. Anything on the LAN can write a crafted job hash and
  `LPUSH` it — the worker then `pickle.loads()` it as **root**. (REV-600, `blocker`)
- **PostgreSQL** on `0.0.0.0:5432` accepts `knowledgeway/knowledgeway` from a non-loopback
  address, and that role is a **superuser** — verified live. That is full read/write of every
  indexed line of code, plus `COPY … PROGRAM` execution. (REV-601, `critical`)

The application layer itself is defensively *better* written than the deployment around it.
Clone-URL validation, askpass-based token handling, `StrictHostKeyChecking=yes` with a
mandatory `known_hosts`, git-error redaction, no `shell=True`, and zero string-interpolated
SQL are all genuinely done right and are recorded as REV-618 so a later change cannot quietly
regress them. Command injection and path traversal were traced concretely and are **refuted**.
SQL injection was traced concretely and is **refuted**.

What is missing is everything *around* the code: no principal, no rate limit, no cost gate, no
request-size limit, no CSRF defence, no host allowlist for outbound git, and no filesystem
cleanup. `docs/security.md` — the file named for this topic — is exclusively about git
credentials and never mentions that the platform is unauthenticated. `README.md`'s "Security
model" section describes two controls that do not exist in the code.

Counts: **20 findings** — 1 blocker, 2 critical, 3 high, 8 medium, 5 low, 1 info.

---

## Exposure table

Verified live with `docker ps` and
`docker inspect -f '{{range $p, $c := .NetworkSettings.Ports}}…'`, then confirmed by
connecting to the host's LAN address `192.168.2.122` from a separate network namespace (the
`api` container) — i.e. genuinely off-loopback, not a localhost artefact.

| Published port | Binding (verified) | What is reachable | Auth required? |
|---|---|---|---|
| `3000` web | `0.0.0.0:3000` + `[::]:3000` | Full Next.js UI: dashboard, add/delete repository, search, graph, chat | **None** |
| `8000` api | `0.0.0.0:8000` + `[::]:8000` | All 42 API operations (`main` live: 35), `/docs`, `/openapi.json`. 24 GETs return full file contents and source text; 18 non-GET operations, 15 of which mutate persistent state | **None** — `GET /api/repositories` → `200` from `192.168.2.122`; `securitySchemes: None` in OpenAPI |
| `5432` postgres | `0.0.0.0:5432` + `[::]:5432` | Every table: 2 284 files with full `content`, 21 324 symbols, 22 900 chunks, 136 566 edges | **`knowledgeway`/`knowledgeway`** — compose-hardcoded, and `usesuper = true` |
| `6379` redis | `0.0.0.0:6379` + `[::]:6379` | The `indexing` RQ queue and all job payloads | **None** — `protected-mode no`, `requirepass` unset, ACL user `default` |
| — worker | no published port | Reachable only via the Redis queue above | n/a (trusts the queue completely) |

Both branches carry an identical `docker-compose.yml` port block
(`git diff main origin/integration/consolidated-verified -- docker-compose.yml` shows only the
gcloud ADC mount and `GOOGLE_APPLICATION_CREDENTIALS` as differences), so this table applies to
`both`.

Containers run as **`uid=0(root)`** (`docker exec knowledge-way-api-1 id`; no `USER` directive
in `apps/api/Dockerfile`) with `./data` bind-mounted **read-write** to the host.

---

## Unauthenticated state-mutating routes

All 18 non-GET operations on the integration target, none of which has any credential,
principal, origin, rate or cost check. Blast radius is stated against the live DB row counts
from the shared brief. **None of these was exercised in this review.**

| # | Operation | Persistent effect | Blast radius / cost |
|---|---|---|---|
| 1 | `POST /api/workspaces` | `INSERT workspaces` | trivial; unbounded row growth |
| 2 | `PATCH /api/workspaces/{id}` | `UPDATE workspaces` | renames/rewrites any workspace |
| 3 | `DELETE /api/workspaces/{id}` | deletes workspace **+ all memberships + all dependency declarations** (`main.py:94`) | destroys every hand-declared dependency in that workspace; no undo, no export |
| 4 | `POST /api/workspaces/{id}/dependencies` | `INSERT workspace_dependencies` | injects fabricated "declared dependency" evidence |
| 5 | `PATCH …/dependencies/{dep}` | `UPDATE` | rewrites dependency reason/note |
| 6 | `DELETE …/dependencies/{dep}` | `DELETE` | destroys a declaration |
| 7 | `PUT /api/workspaces/{id}/repositories/{repo}` | `INSERT workspace_repositories` | re-parents a repository |
| 8 | `POST /api/workspaces/{id}/repositories/{repo}` | same | **CSRF-able** (no request body → CORS-simple) |
| 9 | `DELETE /api/workspaces/{id}/repositories/{repo}` | deletes membership **+ every dependency touching that repo** (`main.py:146`) | silent collateral deletion of declarations |
| 10 | `POST /api/repositories` | `INSERT repositories` + `git clone` from **any** host + full index | 337 MB disk and 11 m 37 s CPU observed for one repo; unbounded repetition; outbound request to an arbitrary operator-unspecified host; provider spend if embeddings enabled |
| 11 | `DELETE /api/repositories/{id}` | `CASCADE` across files/symbols/chunks/edges/cards/jobs (`main.py:163`) | destroys 2 284 files, 21 324 symbols, 22 900 chunks, **136 566 edges**; 11 m 37 s to rebuild; **leaves the 337 MB clone orphaned on the host forever** |
| 12 | `POST /api/repositories/{id}/sync` | enqueues an index job | **CSRF-able** (no body); pins the single worker |
| 13 | `POST /api/repositories/{id}/reindex` | enqueues a full index **and can overwrite `requested_revision`** (`main.py:172`) | **CSRF-able**; 11 m 37 s; silently re-pins which commit is authoritative |
| 14 | `POST /api/repositories/{id}/code-cards` | enqueues Gemini generation, `limit` ≤ 500 | **direct provider spend**, 500 `generateContent` calls per request, unbounded repetition (integration only) |
| 15 | `POST /api/chat` | `INSERT conversations` + 2 × `INSERT messages` | unbounded row growth; embedding spend when semantic is on |
| 16 | `POST /api/search/semantic` | no write | unvalidated `body: dict`, `body['query']` of **any length** → billable embedding call (`main.py:303-306`) |
| 17 | `POST /api/explanations` | no write | hybrid search → embedding spend (integration only) |
| 18 | `POST /api/documentation/generate` | no write | loads the entire `symbol_edges` table (integration only) |

On live `main` the set is 15 non-GET operations (14 mutating): `code-cards`, `explanations` and
`documentation/generate` do not exist there.

---

## Findings

| ID | Category | Severity | One-line |
|---|---|---|---|
| REV-600 | SECURITY_RISK | blocker | Redis on `0.0.0.0:6379`, `protected-mode no`, no password + RQ pickle serializer → LAN-reachable RCE as root in the worker |
| REV-601 | SECURITY_RISK | critical | PostgreSQL on `0.0.0.0:5432` accepts hardcoded `knowledgeway/knowledgeway`, and that role is superuser |
| REV-602 | SECURITY_RISK | critical | Zero authentication/authorization: 42/42 operations anonymous, 15 mutate state, API published on `0.0.0.0:8000` |
| REV-603 | SECURITY_RISK | high | Body-less POSTs are CORS-simple and execute regardless of `Origin` — CSRF on `sync`, `reindex`, membership |
| REV-604 | PERFORMANCE_RISK | high | One anonymous GET costs 2.26 s CPU and 136 566 ORM rows for a 65-byte response; no rate limit |
| REV-605 | SECURITY_RISK | high | Anonymous `DELETE /api/repositories/{id}` cascades the whole index and never removes the 337 MB clone |
| REV-606 | SECURITY_RISK | medium | Containers run as root with a RW host bind mount; integration additionally mounts the operator's Google ADC into both api and worker |
| REV-607 | SECURITY_RISK | medium | `error_message` stores raw `str(e)` for every non-git exception and is served by two anonymous GETs |
| REV-608 | SECURITY_RISK | medium | Secret-file exclusion is a 4-name + 2-suffix denylist; everything else is persisted and served anonymously |
| REV-609 | DOCUMENTATION_GAP | medium | `README.md` "Security model" claims a prompt-injection defence that exists nowhere in the code |
| REV-610 | DOCUMENTATION_GAP | medium | ADR-0001 §5 and the UI vision doc assert in present tense that authorization is enforced — violates §3.9/§7 |
| REV-611 | SECURITY_RISK | medium | No request-body size limit; `POST /api/search/semantic` takes an unvalidated `dict` straight to a billable provider |
| REV-612 | DESIGN_GAP | medium | No git host allowlist: an anonymous POST makes the worker connect to any host it can reach, including RFC1918 |
| REV-619 | TEST_GAP | medium | Not one test asserts an auth/authz boundary, a CORS rule, or redaction of a non-git exception |
| REV-613 | DOCUMENTATION_GAP | low | `docs/security.md` never states the platform is unauthenticated or that four ports bind to all interfaces |
| REV-614 | SECURITY_RISK | low | MCP client sends `KW_API_BEARER_TOKEN` that the API never validates |
| REV-615 | CORRECTNESS_RISK | low | `cors_origins.split(',')` does not strip whitespace; a multi-origin value silently fails after the first entry |
| REV-616 | DOCUMENTATION_GAP | low | `compose.git-secrets.example.yml` mounts secrets but never sets the paths that make them usable |
| REV-617 | SECURITY_RISK | low | The hardened git environment is applied to only 3 of 6 git invocations |
| REV-618 | info | info | Controls that are genuinely correct today — recorded so a later change cannot silently regress them |

---

### REV-600

- **ID:** REV-600
- **Category:** SECURITY_RISK
- **Severity:** blocker
- **Evidence level:** `manual live acceptance`
- **Applies to:** both
- **Impact:** Any host on the same layer-2 network as the docker host obtains **arbitrary code
  execution as root inside the `worker` container**, with no credential of any kind. The worker
  holds the PostgreSQL superuser DSN in its environment, has `./data` bind-mounted read-write
  to the host filesystem, and on the integration branch also has the operator's Google
  Application Default Credentials mounted. This is the single highest-impact finding in the
  review and it is a one-line compose fix.
- **Evidence:**
  - `docker-compose.yml:15-17` — `redis: image: redis:7-alpine` / `ports: ["6379:6379"]`. Short
    syntax with no host IP ⇒ all interfaces. No `command:`, no `requirepass`, no config file
    (`docker inspect -f '{{.Config.Cmd}}' knowledge-way-redis-1` → `[redis-server]`).
  - Live, from the `api` container to the host's **LAN** address (off-loopback):
    ```text
    PING           -> b'+PONG\r\n'
    protected-mode -> b'*2\r\n$14\r\nprotected-mode\r\n$2\r\nno\r\n'
    requirepass    -> NOT SET (empty)
    ACL WHOAMI     -> b'$7\r\ndefault\r\n'
    LLEN rq:queue:indexing -> b':0\r\n'
    ```
    (`docker exec -i knowledge-way-api-1 python -` speaking RESP to `192.168.2.122:6379`; only
    `PING`, `CONFIG GET`, `ACL WHOAMI`, `LLEN` were sent — all read-only. Nothing was written.)
  - RQ's serializer, on the installed version:
    ```text
    rq 2.0.0
    default serializer: <class 'rq.serializers.DefaultSerializer'>
    uses pickle: True
    ```
    (`docker exec knowledge-way-api-1 python -c "import rq, rq.serializers, pickle; …"`)
  - `apps/api/app/worker.py:4` — the worker's entire body is
    `Worker([Queue('indexing', …)], …).work()`: it dequeues and deserializes whatever is in the
    queue with no validation, allowlist of callables, or signature check.
  - `apps/api/requirements.txt:11` pins `rq==2.0.0`.
- **Probable cause + diagnostic confidence:** **Very high.** Two independent defaults compose
  into the vulnerability: the official `redis:7-alpine` image ships `protected-mode no` (which
  is why `PING` from a non-loopback source succeeds rather than returning `-DENIED`), and RQ's
  `DefaultSerializer` is `pickle`. Neither is a knowledge-way bug in isolation; publishing the
  port on `0.0.0.0` is what joins them. RQ job payloads live in a `rq:job:<id>` hash whose
  `data` field is the pickled callable + args; an attacker writes that hash and `LPUSH`es the id
  onto `rq:queue:indexing`, and code executes at `pickle.loads()` time inside the worker.
- **Smallest safe next step:** change one line —
  `ports: ["127.0.0.1:6379:6379"]` — or delete the mapping entirely, since nothing outside the
  compose network needs it (the API and worker reach Redis by service DNS, `redis://redis:6379/0`).
  Then add `command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]` and a matching
  `REDIS_URL`. Independently, pass an explicit non-pickle serializer to both `Queue` and
  `Worker` (`rq.serializers.JSONSerializer`) so that queue write access stops being code
  execution; note this changes the on-wire job format and must be rolled out to API and worker
  together, with the queue drained.
- **Affected data/migrations/providers/cost:** No migration. Compromise reaches all indexed
  data, the Postgres superuser credential, the host `./data` tree, and — on integration — the
  operator's Google ADC (⇒ arbitrary Vertex spend). No cost incurred by this review.
- **Recommended tests + acceptance criteria:**
  - An operations test asserting `docker inspect` reports `127.0.0.1` (or no binding) for 6379,
    failing CI otherwise.
  - A test that a Redis connection without `AUTH` is refused.
  - A unit test asserting the configured serializer is not pickle-based:
    `assert Queue(...).serializer is not rq.serializers.DefaultSerializer`.
  - Acceptance: from a second host on the LAN, `redis-cli -h <host> ping` fails to connect.
- **Fix status:** report-only

---

### REV-601

- **ID:** REV-601
- **Category:** SECURITY_RISK
- **Severity:** critical
- **Evidence level:** `PostgreSQL integration-tested`
- **Applies to:** both
- **Impact:** Any host on the LAN reads and writes the entire corpus — 2 284 files with full
  `content`, 21 324 symbols, 136 566 edges — using a credential pair that is written in
  plaintext in the repository. Because the role is a **superuser**, this is also code execution
  (`COPY … FROM PROGRAM`) inside the postgres container and unrestricted `pg_read_file` on that
  container's filesystem.
- **Evidence:**
  - `docker-compose.yml:2-9` — `POSTGRES_USER: knowledgeway`, `POSTGRES_PASSWORD: knowledgeway`,
    `ports: ["5432:5432"]`.
  - The same pair is the in-code default: `apps/api/app/config.py:7`
    `database_url: str = "postgresql+psycopg://knowledgeway:knowledgeway@localhost:5432/knowledgeway"`,
    and `.env.example:1` ships it as the working value, so almost every deployment keeps it.
  - Live, off-loopback, from the `api` container to the host LAN address:
    ```text
    connected off-loopback: (1,)
    current_user is superuser: (True,)
    ```
    (`psycopg.connect('postgresql://knowledgeway:knowledgeway@192.168.2.122:5432/knowledgeway')`,
    then `SELECT 1` and `SELECT usesuper FROM pg_user WHERE usename = current_user` — two
    read-only statements.)
  - `docker inspect` confirms `5432/tcp -> 0.0.0.0:5432` and `[::]:5432`.
- **Probable cause + diagnostic confidence:** **Very high.** `POSTGRES_USER` in the official
  image is created as the cluster superuser; the compose file publishes the port and hardcodes
  the credential. `docs/OPERATIONS.md:16,18` already lists "Set unique PostgreSQL and Redis
  credentials" and "Restrict Docker port exposure for PostgreSQL and Redis" as unchecked boxes —
  but files them under "Before internet-facing deployment", which is the wrong trigger: the
  default local stack is already exposed to the LAN.
- **Smallest safe next step:** `ports: ["127.0.0.1:5432:5432"]` (or remove the mapping — the API
  and worker use service DNS). Separately, move the credential to `.env` with a generated value
  and create a non-superuser application role owning only the application schema.
- **Affected data/migrations/providers/cost:** All twelve tables. Rotating the password requires
  restarting api + worker; creating a least-privilege role is a migration-adjacent change and
  must not be attempted while an index job is in flight (§4).
- **Recommended tests + acceptance criteria:**
  - Ops test asserting the 5432 host binding is loopback-only.
  - Integration test asserting `SELECT usesuper FROM pg_user WHERE usename = current_user` is
    `false` for the application role.
  - Acceptance: `psql -h <LAN-ip> -U knowledgeway` fails to connect from another host.
- **Fix status:** report-only

---

### REV-602

- **ID:** REV-602
- **Category:** SECURITY_RISK
- **Severity:** critical
- **Evidence level:** `manual live acceptance`
- **Applies to:** both
- **Impact:** Every operation is anonymous. There is no principal, no session, no API key, no
  bearer verification, no reverse proxy in the compose file, and nothing in code that could
  carry an identity. 24 GETs disclose full source code (`GET /api/files/{file_id}` returns
  `content` verbatim and is **not** repository-scoped — it takes a bare global `file_id`,
  `main.py:216-220`). 15 non-GET operations mutate state, including two that destroy data and
  four that consume minutes of CPU or provider budget. On a `127.0.0.1`-only binding this would
  be a defensible single-user design decision; the binding is `0.0.0.0`, so it is not.
- **Evidence:**
  - `apps/api/app/main.py:17-20` is the entire application setup: `FastAPI(...)`, one
    `CORSMiddleware`, one startup hook. There is no `Depends(...)` security dependency, no
    `HTTPBearer`, no `APIKeyHeader`, no middleware other than CORS, anywhere in the file.
  - `grep -rn '401\|403\|Authorization\|unauthorized' apps/api/tests` → the only hit is a
    *fixture string* inside a redaction test (`test_git_auth.py:55`). No route ever returns 401
    or 403.
  - Live: `curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/repositories` → `200`;
    the same request from the LAN address returns `200`; no `WWW-Authenticate` and no
    `Set-Cookie` in any response header.
  - `curl -s http://localhost:8000/openapi.json` →
    `securitySchemes: None`, `global security: None`, 26 paths / 35 operations on live `main`.
  - `/docs` → `200` and `/openapi.json` → `200` unauthenticated: the destructive surface is
    self-describing, and Swagger UI's "Try it out" will fire `DELETE /api/repositories/{id}`
    from a browser for anyone who loads the page.
  - Route inventory (integration): `grep -c '^@app\.' apps/api/app/main.py` → 43, minus the
    `on_event` decorator = **42 operations**, of which 18 are non-GET (11 POST, 1 PUT, 2 PATCH,
    4 DELETE).
- **§3.9 — workspace membership is not authentication.** Checked directly, and the *code* is
  clean: `WorkspaceRepository` is a plain join table (`models.py:15-17`) and the only checks
  built on it are `validate_dependency_membership` (`main.py:45-48`) and the exclusive-membership
  conflict at `main.py:130-139`. Both are **data-integrity** constraints, not access decisions —
  they reject a *malformed* dependency, never an *unauthorised caller*, and no route consults
  membership before returning content. `GET /api/repositories`, `GET /api/search`,
  `GET /api/files/{file_id}` and every graph route ignore workspaces entirely. So the
  implementation does not make the §3.9 mistake. Two *documents* do — see REV-610.
- **CORS.** `main.py:18`:
  `app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(','), allow_methods=['*'], allow_headers=['*'])`.
  It is **not** permissive in the live configuration and `allow_credentials` is not set (so it
  defaults to `False`). Verified by preflight:
  ```text
  OPTIONS /api/repositories/{id}  Origin: https://evil.example   Access-Control-Request-Method: DELETE
    → HTTP/1.1 400 Bad Request   "Disallowed CORS origin"   (no access-control-allow-origin)
  OPTIONS /api/repositories/{id}  Origin: http://localhost:3000  Access-Control-Request-Method: DELETE
    → HTTP/1.1 200 OK   access-control-allow-origin: http://localhost:3000
                        access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
  GET /api/repositories   Origin: https://evil.example
    → HTTP/1.1 200 OK   (no access-control-* header at all ⇒ browser cannot read the body)
  ```
  So the browser-mediated read path is closed. What CORS does **not** close is the
  request-execution path for simple requests — see REV-603 — and the middleware would become
  a full disclosure channel if `CORS_ORIGINS` were ever set to `*`, because with no auth every
  page on the internet could then read the entire corpus from a victim's machine. See REV-615.
- **Probable cause + diagnostic confidence:** **Certain, by design.** The project consistently
  documents auth as future work (`docs/OPERATIONS.md:23`, `docs/NEXT_STEPS.md:82`,
  `docs/ENGINEERING_BACKLOG.md:26`, `docs/HANDOFF.md:90,100`, `docs/ROADMAP.md:35`,
  `docs/mcp.md:54`). The gap is not that auth is missing — it is that the *default deployment
  contradicts the stated single-user local assumption* by binding to all interfaces.
- **Smallest safe next step:** do not build auth. Bind the two application ports to loopback
  (`127.0.0.1:8000:8000`, `127.0.0.1:3000:3000`) so that the documented threat model and the
  actual deployment agree. That is a two-line compose change with zero code impact and no
  migration. Auth proper is the later work described in "Required later" below.
- **Affected data/migrations/providers/cost:** No migration. Until fixed, the whole corpus and
  every destructive/billable route is exposed to the LAN.
- **Recommended tests + acceptance criteria:**
  - Ops test asserting `docker inspect` reports `127.0.0.1` for 8000 and 3000.
  - Acceptance: from a second LAN host, `curl http://<host>:8000/health` fails to connect, while
    `curl http://localhost:8000/health` on the docker host still returns `{"status":"ok"}` and
    the UI at `localhost:3000` still works.
- **Fix status:** report-only

---

### REV-603

- **ID:** REV-603
- **Category:** SECURITY_RISK
- **Severity:** high
- **Evidence level:** `manual live acceptance`
- **Applies to:** both
- **Impact:** Any web page the operator visits while the stack is running can trigger
  cost-bearing and state-changing operations on it. `CORSMiddleware` only decides whether the
  *browser hands the response back to the script*; it does not stop the request from being
  executed server-side. Three mutating operations take **no request body** and are therefore
  CORS-"simple" — no preflight is issued, so the `Origin` restriction never applies:
  `POST /api/repositories/{id}/sync`, `POST /api/repositories/{id}/reindex` (its body is
  `RepositoryReindexIn | None = None`, `main.py:169`) and
  `POST /api/workspaces/{id}/repositories/{repo}`. A hidden auto-submitting HTML form, or
  `fetch(url, {method:'POST', mode:'no-cors'})`, reaches all three. Consequence: an 11 m 37 s
  re-index kicked off by a drive-by page, repeated at will; on the integration branch the same
  shape reaches nothing billable directly, but `reindex` will re-run embeddings when a provider
  is configured.
- **Evidence:**
  - Proved live with non-existent IDs so that nothing could mutate — the request reaches the
    route handler and is rejected by *business logic*, not by any origin or content-type gate:
    ```text
    POST /api/workspaces/00000000-…-0000/repositories/00000000-…-0001
      Origin: https://evil.example
      Content-Type: application/x-www-form-urlencoded   (empty body)
      → HTTP/1.1 404 Not Found   {"detail":"Workspace not found"}

    same request with no Content-Type header at all      → 404
    ```
    A 404 from `main.py:128` proves the handler executed. Post-check:
    `SELECT count(*) FROM workspaces` → `0`, `workspace_repositories` → `0`; nothing changed.
  - `main.py:164-167` (`sync`) and `main.py:168-173` (`reindex`) take no required body, so the
    same shape applies to them. They were **not** called.
  - No CSRF token, no `Origin`/`Referer` check, no `SameSite` cookie (there are no cookies at
    all, which is exactly why CSRF works here — there is no credential to withhold).
- **Probable cause + diagnostic confidence:** **High.** Standard consequence of combining
  ambient-authority-by-network-position with body-less mutating POSTs. `DELETE` is *not*
  reachable this way (it forces a preflight, which the middleware correctly rejects), which is
  why this is `high` and not `critical`.
- **Smallest safe next step:** the loopback rebind in REV-602 does not fix this — a page in the
  operator's browser *is* on loopback. The minimal real fix is to require a non-simple request
  for every mutating route: reject non-GET requests whose `Content-Type` is not
  `application/json` in one small middleware, which forces a preflight and hands enforcement
  back to the existing `allow_origins` list. ~5 lines, no schema change, no per-route edits.
- **Affected data/migrations/providers/cost:** No migration. Cost exposure = repeated indexing
  and, when a provider is enabled, repeated embedding runs.
- **Recommended tests + acceptance criteria:**
  - API test: `POST /api/repositories/{id}/sync` with `Content-Type: text/plain` → 415.
  - API test: same with `application/json` → 202.
  - API test: preflight from a disallowed origin → 400 (locks in today's behaviour).
  - Acceptance: an HTML page served from a different origin can no longer cause an enqueue.
- **Fix status:** report-only

---

### REV-604

- **ID:** REV-604
- **Category:** PERFORMANCE_RISK
- **Severity:** high
- **Evidence level:** `manual live acceptance`
- **Applies to:** both
- **Impact:** Several anonymous GETs perform work proportional to the *whole repository* rather
  than to the requested result, giving a ~2 400× request-to-work amplification. There is no rate
  limit anywhere in the project (`grep -riE 'slowapi|limiter|ratelimit'` over
  `apps/api/requirements.txt` and `apps/api/app` → no match), so a handful of concurrent
  requests from an unauthenticated client is enough to saturate the API: FastAPI runs these
  synchronous `def` handlers in a bounded threadpool, and each one materialises ~136 566 ORM
  objects, so this is a memory-pressure lever as well as a CPU one.
- **Evidence:** measured live, one request each, on the real corpus:
  ```text
  GET /api/repositories/{id}/symbols/{sid}/callers            status=200 total=2.259673s size=65
  GET /api/repositories/{id}/symbols/{sid}/subgraph?depth=2…  status=200 total=3.025677s size=592
  GET /health                                                 status=200 total=0.000926s
  symbol_edges=136566  symbols=21324  files=2284  max_file_bytes=1035877
  ```
  2.26 s of server work to return **65 bytes**; 2 440× the `/health` baseline.
  Root cause is one helper, `main.py:60`:
  ```python
  def scoped_edges(db,repo_id): return sorted((e for e in db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id==repo_id)).all() if e.repository_id==repo_id),key=edge_key)
  ```
  — an unfiltered, unlimited `SELECT` of every edge in the repository, fully materialised and
  then sorted in Python. Its callers are `neighbors` (`main.py:230`, i.e. `/callers` and
  `/callees`), `subgraph` (`main.py:245`), `repository_graph` (`main.py:267`) and
  `documentation` (`main.py:320`) — five anonymous endpoints.
  Two further unbounded paths in the same class:
  - `search.py:88` — semantic mode iterates **every** embedded chunk (22 900 rows) with a
    pure-Python cosine, with no `LIMIT` on that statement at all.
  - `main.py:211` — `File.path.like(prefix+'%')` where `prefix` comes from the caller's `path`
    query parameter, with `%`/`_` unescaped, so `?path=%25` degrades to a full-table scan (DB
    content only; no traversal — see REV-618).
  The explicit bounds that *do* exist are correct and worth noting: `depth` ≤ 2 and
  `max_nodes` ≤ 100 (`main.py:242`), `limit` clamped to 100 in `/api/search`
  (`main.py:299`, `min(max(limit,1),100)`), `structural-cards` `limit` ≤ 100 (`main.py:193`),
  `code-cards` `limit` ≤ 500 (`main.py:40`). The problem is not the response budget — it is that
  the response budget is applied *after* the whole table has been loaded.
- **Probable cause + diagnostic confidence:** **High**, measured. The pattern is deliberate —
  the `if e.repository_id==repo_id` re-check after an already-scoped `WHERE` suggests the helper
  was written for defence-in-depth scope proof, with the cost of doing it in Python not
  considered. Note the whole thing is unindexed on the edge-traversal columns:
  `models.py:37` indexes `repository_id` and `target_name` but neither `source_symbol_id` nor
  `target_symbol_id`.
- **Smallest safe next step:** push the predicate into SQL for the two cheapest cases —
  `/callers` and `/callees` — by adding `.where(SymbolEdge.target_symbol_id==symbol_id)` /
  `source_symbol_id` to a dedicated statement instead of calling `scoped_edges`. That is a
  contained change to `neighbors` only, needs an index on those two columns (a migration, so it
  is gated by §4), and leaves the deterministic ordering intact because `edge_key` can be
  expressed as an `ORDER BY`.
- **Affected data/migrations/providers/cost:** A composite index on
  `(repository_id, source_symbol_id)` and `(repository_id, target_symbol_id)` is a migration —
  additive and reversible, but must not run while an index job is in flight (§4).
- **Recommended tests + acceptance criteria:**
  - A performance regression test asserting `/callers` issues one query returning ≤ N rows,
    not `count(symbol_edges)`.
  - Assert byte-identical response bodies before and after, on the live corpus, for a sample of
    symbols — the ordering contract must not change.
  - Acceptance: `/callers` on the 136 566-edge repository completes in < 100 ms.
- **Fix status:** report-only

---

### REV-605

- **ID:** REV-605
- **Category:** SECURITY_RISK
- **Severity:** high
- **Evidence level:** `source-reviewed` (destructive routes deliberately **not** exercised)
- **Applies to:** both
- **Impact:** Two anonymous routes destroy the platform's entire value, and one of them leaks
  disk permanently. `DELETE /api/repositories/{id}` cascades away 2 284 files, 21 324 symbols,
  22 900 chunks and 136 566 edges — an 11 m 37 s rebuild — with no confirmation token, no
  soft-delete, no export, and no audit record of who did it (there is no "who"). Separately,
  **nothing anywhere in `apps/api/app` ever deletes a file or directory**, so the 337 MB clone
  survives the deletion of its own database row and becomes unreferenceable garbage. Repeated
  `POST /api/repositories` therefore fills the host disk with no ceiling: `MAX_FILE_SIZE` bounds
  which files are *indexed*, not what is *cloned*.
- **Evidence:**
  - `main.py:159-163` — `delete_repository` executes three `DELETE` statements and
    `db.delete(r)`. No filesystem call.
  - `grep -rn 'rmtree\|\.unlink\|rmdir\|shutil' apps/api/app` → **no match**. Confirmed: there
    is no cleanup path anywhere in the API or worker.
  - `ingestion.py:192-193` — `root=Path(settings.repository_storage_path)/repo_id` … `git clone`.
    Nothing ever removes `root`.
  - Live: `du -sh data/repositories/21ffa409-…` → **337 MB**, owner `root root` (a consequence of
    REV-606), for a single repository.
  - No rate or cost gate exists on any of the four expensive routes. `enqueue`
    (`main.py:49-51`) enqueues unconditionally and swallows every exception; `code-cards`
    (`main.py:179-185`) is gated only by the `code_cards_enabled` flag — once that flag is on,
    an anonymous caller may request 500 Gemini `generateContent` calls per request, unbounded
    times, with no budget counter, no daily cap and no queue-depth check.
  - `DELETE /api/workspaces/{id}` (`main.py:90-94`) additionally deletes all memberships and all
    dependency declarations in one uncontrolled transaction — the only place hand-curated
    dependency evidence lives, with no export path.
- **Probable cause + diagnostic confidence:** **High** for both parts. The cascade is intentional
  (§3.8 requires explicit delete semantics and the code does distinguish membership removal from
  repository deletion). The orphaned clone is an omission, not a decision: `repo.local_path` is
  written at `ingestion.py:201` and then never used for cleanup.
- **Smallest safe next step:** for the disk leak, add the deletion of `local_path` to
  `delete_repository` guarded by a check that the resolved path is inside
  `settings.repository_storage_path` — ~4 lines, no migration. For the cost side, do nothing in
  code: the loopback rebind (REV-602) removes the unauthenticated network reachability that
  makes it exploitable, and a real budget gate belongs with the auth work.
- **Affected data/migrations/providers/cost:** No migration. Provider cost exposure is bounded
  only by `code_cards_enabled` today, and that flag is `False` by default (`config.py:23`) — the
  live deployment has no `code_cards` table at all, so **nothing was at risk during this
  review**.
- **Recommended tests + acceptance criteria:**
  - API + filesystem test: create a repository with a fixture path, `DELETE` it, assert the
    directory is gone **and** that a `local_path` pointing outside `repository_storage_path` is
    refused rather than followed.
  - Negative test: `DELETE /api/workspaces/{id}` removes memberships and dependencies but leaves
    every `repositories` row intact (§3.8).
  - Acceptance: `du -s data/repositories` returns to its pre-add value after a delete.
- **Fix status:** report-only

---

### REV-606

- **ID:** REV-606
- **Category:** SECURITY_RISK
- **Severity:** medium
- **Evidence level:** `manual live acceptance`
- **Applies to:** `both` for root + read-write bind mount; **`integration` only** for the ADC mount
- **Impact:** Both containers run as `uid=0` with the host's `./data` bind-mounted read-write,
  so any code execution inside them (REV-600) writes to the host filesystem as root, and every
  cloned file is already created root-owned on the host — a normal user cannot clean up
  `data/repositories/` without `sudo`. On the integration branch the exposure is materially
  worse: the compose file mounts the operator's **personal Google Application Default
  Credentials** into *both* the api and the worker. The mount is correctly `:ro`, but read-only
  is irrelevant to credential theft — an attacker only needs to read it, and the resulting
  token is not scoped to this project's Vertex usage.
- **Evidence:**
  - `docker inspect -f 'User="{{.Config.User}}"' knowledge-way-api-1` → `User=""`;
    `docker exec knowledge-way-api-1 id` → `uid=0(root) gid=0(root)`. `apps/api/Dockerfile:1-9`
    has no `USER` directive; `apps/web/Dockerfile:9-14` likewise.
  - `docker inspect` mounts, live (`main`): `bind /home/artur/…/knowledge-way/data -> /data rw=true`
    on both `api` and `worker`.
  - `ls -ld data/repositories/21ffa409-…` → `drwxr-xr-x 17 root root`.
  - Integration-only, `docker-compose.yml:22-24` and `:33-34`:
    ```yaml
    environment:
      GOOGLE_APPLICATION_CREDENTIALS: /root/.config/gcloud/application_default_credentials.json
    volumes: ["./data:/data", "${HOME}/.config/gcloud:/root/.config/gcloud:ro"]
    ```
    `git diff main origin/integration/consolidated-verified -- docker-compose.yml` confirms this
    is the only functional difference between the two branches' compose files, i.e. the live
    `main` stack does **not** have the ADC mounted (`docker inspect` shows only the `./data`
    bind), so today's live blast radius excludes ADC theft.
  - `providers.py:85-95` and `code_cards.py:66-67` consume those credentials via
    `google.auth.default()`.
- **Probable cause + diagnostic confidence:** **High.** Mounting host ADC read-only is the
  documented ADC pattern and `config.py:17` explicitly says "mount them read-only in Docker" —
  the gap is that it is mounted into a container that is also the target of REV-600, and that
  the whole *user-level* credential is mounted rather than a scoped service-account key.
- **Smallest safe next step:** add `user: "1000:1000"` to api and worker (and a matching
  `chown` of `./data`) — this also fixes the root-owned-clone annoyance. Separately, prefer a
  narrowly-scoped service-account key file mounted at a dedicated path over the operator's
  personal ADC, and mount it into the `worker` only (the API process never needs it: neither
  `providers.embedding_provider()` nor `code_cards` is called in-process by any route — both are
  enqueued).
- **Affected data/migrations/providers/cost:** No migration. Directly affects Vertex/Gemini
  credential blast radius. Changing the container uid requires a one-time `chown` of the
  existing 337 MB `data/` tree.
- **Recommended tests + acceptance criteria:**
  - Ops test asserting `docker exec … id -u` is non-zero for api and worker.
  - Ops test asserting the API container has no credential mount.
  - Acceptance: a fresh index run produces host files owned by the invoking user.
- **Fix status:** report-only

---

### REV-607

- **ID:** REV-607
- **Category:** SECURITY_RISK
- **Severity:** medium
- **Evidence level:** `source-reviewed` (no leak observed in the current live rows)
- **Applies to:** both
- **Impact:** The redaction layer is applied at exactly one place and every other exception path
  bypasses it. `ingestion.py:240` persists `str(e)` verbatim into **two** database columns, and
  both are served by anonymous GETs (`/api/repositories/{id}/status` → `error`, `main.py:178`;
  `/api/jobs/{job_id}` → `error_message`, `main.py:341`). The concrete leak is not a credential —
  I traced that and the credential paths are clean — it is **indexed repository content and
  internal SQL**: SQLAlchemy's `StatementError.__str__` appends the failing statement and its
  bound parameters, and on this ingestion path those parameters are full file contents
  (`ingestion.py:224`, `File(... content=content ...)`). A single `DataError` while inserting one
  file therefore writes part of that file into a column readable by anyone who can reach port
  8000. Additionally `providers.py:123-126` deliberately embeds the raw Vertex response body in
  a `RuntimeError`, which then lands in `job.error_message` via `code_cards.py:206`.
- **Evidence:**
  - `ingestion.py:239-240`:
    ```python
    except Exception as e:
     repo.indexing_status='failed';repo.error_message=str(e);job.status='failed';job.error_message=str(e);…
    ```
    — `str(e)` for **every** exception type. Redaction happens earlier and only for
    `CalledProcessError` inside `run` (`ingestion.py:27-30`), so only git *subprocess* failures
    are sanitised.
  - `code_cards.py:206` — `job.error_message=str(exc)` on the code-card path, same shape.
  - `git_auth.py:83-95` — `redact_git_error` removes URL userinfo, the configured HTTPS token
    value and `Authorization:` header text. It knows nothing about provider API keys, SQL
    parameters, or file contents, and is never invoked outside `run`.
  - The clone-failure trace specifically requested: `POST /api/repositories` →
    `validate_clone_url` (`git_auth.py:21-43`) rejects any credentialed URL **before** it is
    stored, so a credentialed URL cannot reach the DB in the first place; the HTTPS token is
    supplied out-of-band by askpass and never appears in argv or the URL; if git then fails,
    `run` catches `CalledProcessError`, truncates stderr to 2 000 chars and passes it through
    `redact_git_error`, which additionally substitutes the token file's content. That path is
    sound. The gap is every *other* exception type.
  - Live check of what the columns hold today (read-only `SELECT`, inspected for secrets before
    quoting):
    ```text
    5767f63f… | status=failed | err=Killed by RQ 180s default job_timeout (no traceback; SIGKILL).
    c3807649… | status=failed | err=Indexing stopped unexpectedly. The worker exited or the job exceeded its timeout.
    repositories: ready | err=NULL
    ```
    Both were written by this session's reaper, not by `str(e)`. **No secret and no code content
    is currently exposed** — the risk is latent, which is why this is `medium` and the evidence
    level is `source-reviewed`, not `BUG_CONFIRMED`.
  - Note the API's *unhandled*-exception path is safe by contrast: there is no custom exception
    handler, so FastAPI returns a bare `Internal Server Error` and the traceback stays in the
    container log.
- **Probable cause + diagnostic confidence:** **High.** Redaction was designed for the git
  threat (and designed well); the generic `except Exception` was written before the column became
  publicly readable.
- **Smallest safe next step:** route both assignments through one helper —
  `error_message = redact_git_error(str(e))[:1000]` — and extend `redact_git_error` with the
  configured provider key values. Two lines in `ingestion.py`, one in `code_cards.py`, no
  migration. A stricter follow-up is to persist a stable error *code* plus a log correlation id
  and keep free text out of the API entirely.
- **Affected data/migrations/providers/cost:** `repositories.error_message`,
  `indexing_jobs.error_message`. No migration needed for the redaction fix.
- **Recommended tests + acceptance criteria:**
  - Unit test: an exception whose `str()` contains a configured provider key and a fake file
    body is persisted redacted and truncated.
  - Unit test extending `test_git_auth.py::test_redaction_…` to cover provider key values.
  - Acceptance: `GET /api/jobs/{id}` after a forced `DataError` contains neither the SQL text
    nor any bound parameter.
- **Fix status:** report-only

---

### REV-608

- **ID:** REV-608
- **Category:** SECURITY_RISK
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** `README.md` states "secrets are excluded by default and are never logged". The
  actual exclusion is a four-name denylist plus two suffixes. Index a repository that has ever
  committed a credential outside that list — `id_rsa`, `.env.production`, `.env.staging`,
  `.npmrc`, `.git-credentials`, `*.tfvars`, `*.p12`, `*.pfx`, `*.jks`, `service-account.json`,
  `.aws/credentials`, `.pgpass`, `.netrc` — and its full plaintext is copied into
  `files.content` and `code_chunks.source_text`, then served by anonymous
  `GET /api/files/{file_id}` and matched by anonymous `GET /api/search`. With a provider enabled
  it is additionally transmitted to the embedding endpoint. The denylist also matches on
  basename only, so `config/env/.env.prod` or any nested variant slips through.
- **Evidence:**
  - `ingestion.py:17` — `SECRET={'.env', '.env.local', 'credentials.json', 'secrets.yml'}`
  - `ingestion.py:204` — the only filter:
    ```python
    if not p.is_file() or any(x in IGNORE for x in p.parts) or p.name in SECRET or p.suffix.lower() in {'.pem','.key'} or p.stat().st_size>settings.max_file_size: continue
    ```
  - `README.md:63` — "Only retrieved, size-limited code chunks are sent to a configured LLM
    provider; **secrets are excluded by default and are never logged.**"
  - Exposure path: `main.py:216-220` returns `f.content` in full, with no repository scoping and
    no auth; `search.py:34` returns `item.source_text[:1200]` for any lexical match.
  - Note the *clone* keeps every excluded file on disk regardless (`ingestion.py:193`), so
    exclusion from the index is not exclusion from the host.
- **Probable cause + diagnostic confidence:** **High.** A starter denylist that the README then
  described as a general guarantee. This is the `KW-002-secure-repository-and-content-policy`
  backlog item, still open.
- **Smallest safe next step:** do not build a scanner. Do the two cheap things: extend the
  denylist to the common set above and match on the *relative path* rather than the basename;
  and soften the README sentence to state exactly what is excluded. Content policy proper
  belongs to KW-002.
- **Affected data/migrations/providers/cost:** No migration. Affects what is transmitted to
  embedding providers.
- **Recommended tests + acceptance criteria:**
  - Ingestion test over a fixture tree containing `id_rsa`, `deploy/.env.production`,
    `.npmrc`, `terraform.tfvars`: assert zero `files` rows for each.
  - Assert `GET /api/search?q=<fixture-token>` returns no results.
  - Acceptance: the fixture repository indexes with those paths absent from `files`.
- **Fix status:** report-only

---

### REV-609

- **ID:** REV-609
- **Category:** DOCUMENTATION_GAP
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** The section of `README.md` titled "Security model" asserts a prompt-injection
  control that does not exist. A reader — or a coding agent — takes it as an implemented
  defence and indexes an untrusted repository on that basis.
- **Evidence:**
  - `README.md:63`, verbatim: *"Repository content is untrusted data. **The chat prompt
    explicitly prohibits following instructions found in code or documentation.** Only
    retrieved, size-limited code chunks are sent to a configured LLM provider; secrets are
    excluded by default and are never logged."*
  - `grep -rniE 'ignore instructions|do not follow|instructions found|untrusted|prompt injection' apps/api/app apps/web`
    → **no match**. There is no such instruction anywhere in the code.
  - There is no chat prompt at all: `main.py:328-336` (`/api/chat`) performs retrieval and
    returns a hardcoded string — *"Grounded sources found for your question. Configure
    OPENAI_API_KEY to enable synthesized answers…"*. No LLM is called on that path.
  - The only prompt in the codebase is `code_cards.py:76-90`, which says *"Use ONLY the supplied
    code and static metadata. Do not claim behavior that is not evidenced."* — an
    evidence-grounding instruction, not an injection defence, and on a different code path than
    chat.
  - Second overclaim in the same sentence: see REV-608.
- **Probable cause + diagnostic confidence:** **High.** Documentation written against the
  intended design; the LLM chat path was never implemented.
- **Smallest safe next step:** edit one sentence in `README.md` to describe what exists —
  retrieval-only chat with no provider call, and the actual exclusion list. No code change.
- **Affected data/migrations/providers/cost:** None.
- **Recommended tests + acceptance criteria:** when a real LLM chat path is added, a unit test
  asserting the system prompt contains the injection-refusal clause, plus a test that a fixture
  file containing an injection string does not change the answer shape. Acceptance today: README
  describes only implemented controls.
- **Fix status:** report-only

---

### REV-610

- **ID:** REV-610
- **Category:** DOCUMENTATION_GAP
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** Directly implicates §3.9 and §7. Two documents state in the present tense that
  authorization is enforced. The code does not implement it (see REV-602), so these sentences
  are exactly the false claim the mandate forbids — and they sit in the two documents a reader
  consults for architectural truth: an ADR (a decision record, read as binding) and the product
  vision (read as the spec).
- **Evidence:** verbatim quotes, as required:
  - `docs/adr/0001-storage-backend-adapters.md:36`, inside numbered invariant 5 *"Queries retain
    identical correctness semantics across adapters"*:
    > "Repository, workspace, commit, file, symbol, and **authorization filters are applied
    > before a result is returned.**"

    No authorization filter exists in any query. `search.py:57-117` filters on
    `repository_id`, `q.repo`, `q.language` and `q.path` only, and — worth flagging for the
    scope workstream — it does not filter on workspace either, so the *workspace* half of that
    sentence is also unimplemented.
  - `docs/HOSTED_PRODUCT_AND_UI_VISION.md:34`, under the heading "### 4. Configuration boundary":
    > "**Workspace membership/authorization is enforced by the backend, never only by the UI.**"

    Present tense, and it contradicts line 66 of the same document, which lists *"Auth,
    role-based workspace access, auditing, quotas, cost controls and production observability
    **before public exposure**"* under "Later items retained in roadmap".
  - For balance: every other document is honest and consistent — `docs/OPERATIONS.md:23`,
    `docs/NEXT_STEPS.md:82`, `docs/ENGINEERING_BACKLOG.md:26`, `docs/HANDOFF.md:90,100`,
    `docs/ROADMAP.md:35`, `docs/mcp.md:54` ("The current local stack has no mandatory API
    authentication, so do not expose port 8000 publicly") and `docs/demo-playbook.md:134` ("This
    project does not yet provide production multi-user authorization"). **No UI copy makes the
    claim**: the only candidate is `apps/web/app/layout.tsx:3`, a footer reading
    `<small>Private by design</small>`, which is a positioning slogan rather than a security
    assertion — worth rewording next time that file is touched, not worth a finding of its own.
- **Probable cause + diagnostic confidence:** **High.** Both sentences describe the target
  architecture in a document that elsewhere marks it as future.
- **Smallest safe next step:** two sentence edits — mark ADR-0001 invariant 5's authorization
  clause as *required of any future adapter, not implemented today*, and put the UI-vision
  sentence in the future tense. No code change.
- **Affected data/migrations/providers/cost:** None.
- **Recommended tests + acceptance criteria:** none automatable. Acceptance: a reader of ADR-0001
  and the vision doc cannot conclude that authorization is enforced today.
- **Fix status:** report-only

---

### REV-611

- **ID:** REV-611
- **Category:** SECURITY_RISK
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** No request-body ceiling exists at any layer — uvicorn does not impose one, and
  there is no proxy in the compose file. `POST /api/search/semantic` is the worst case: it
  accepts a raw `dict` with **no** Pydantic model, then hands `body.get('query','')` of arbitrary
  length straight to an embedding provider. So one anonymous request can (a) force the API to
  buffer an arbitrarily large JSON body in memory and (b) bill an arbitrarily large embedding
  call. It is also the only route in the file with no validation at all, which makes it the
  contract outlier as well as the risk outlier.
- **Evidence:**
  - `main.py:303-306`:
    ```python
    @app.post('/api/search/semantic')
    def semantic_search(body:dict,db:Session=Depends(get_db)):
     results, semantic = search_with_capability(db,body.get('query',''),'semantic')
    ```
    No `BaseModel`, no length bound, no `limit` argument (so `search.py`'s default 30 applies),
    and no `repository_id` scoping.
  - Contrast with every other body: `ChatIn.question` is `max_length=8000` (`main.py:34`),
    `ExplanationIn.question` likewise, `WorkspaceIn.description` `max_length=10000`. The
    discipline exists everywhere else.
  - `search.py:83-85` — that string becomes `provider.embed_texts([q.text])`, a billed call, with
    no truncation to `code_card_max_source_characters` or any other cap.
  - No `client_max_body_size` equivalent: `apps/api/Dockerfile:9` starts
    `uvicorn app.main:app --host 0.0.0.0 --port 8000` with no limit flags, and no reverse proxy
    exists in `docker-compose.yml`.
  - `POST /api/chat` (`main.py:328-336`) also writes 3 rows per call with no dedupe or cap, so
    repeated calls grow `conversations`/`messages` without bound.
- **Probable cause + diagnostic confidence:** **High.** `semantic_search` reads as an early
  prototype route that was never brought up to the validation standard of its neighbours. Not
  exercised in this review (it is on the do-not-call list).
- **Smallest safe next step:** give it a model —
  `class SemanticSearchIn(BaseModel): query: str = Field(min_length=1, max_length=8000); repository_id: str | None = None; limit: int = Field(default=30, ge=1, le=100)`
  — mirroring `ChatIn`. Four lines, no migration, and it closes the billing lever and the
  contract gap together.
- **Affected data/migrations/providers/cost:** No migration. Directly bounds embedding spend.
- **Recommended tests + acceptance criteria:**
  - API test: a 100 kB `query` → 422, with a mocked provider asserting zero calls.
  - API test: `limit=10000` → 422 or clamped to 100.
  - Acceptance: no provider call can be made with an input larger than the configured cap.
- **Fix status:** report-only

---

### REV-612

- **ID:** REV-612
- **Category:** DESIGN_GAP
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** `validate_clone_url` proves the URL is a *well-formed, credential-free network git
  URL* but says nothing about *which host*. An anonymous `POST /api/repositories` therefore makes
  the worker open an outbound connection to any host it can reach, including RFC1918 addresses,
  link-local metadata endpoints and other services on the docker network. The primitive is
  narrow — git-over-HTTPS/SSH only, no redirect-following into other schemes, and the response
  is not echoed back to the caller (a failure surfaces only as a redacted `error_message`) — so
  this is a blind, protocol-constrained SSRF rather than a general one. It is still an
  unauthenticated outbound-request primitive, and `docs/OPERATIONS.md:20` already names the
  missing control: "☐ Configure allowed Git hosts and outbound network policy".
- **Evidence:**
  - `git_auth.py:21-43` — checks scheme ∈ {https, ssh} or the `git@host:path` SCP form, absence
    of userinfo/password/query/fragment, absence of `..`, and length ≤ 2048. There is **no**
    host allowlist and no check against private address ranges. `https://192.168.2.1/x.git`,
    `https://169.254.169.254/x.git` and `https://internal-gitlab/team/repo.git` all pass.
  - `ingestion.py:193` — `run('git','clone','--depth','1',repo.clone_url,str(root),clone_url=…)`
    executes it in the worker.
  - `git_environment` sets `GIT_TERMINAL_PROMPT=0` and `BatchMode=yes`, so it fails fast rather
    than hanging — that limits the DoS angle but not the request itself.
- **Probable cause + diagnostic confidence:** **High**, and it is a known open item rather than an
  oversight. Confidence that it is *exploitable for data exfiltration* is **low** — the response
  body never reaches the caller — which is why this is `medium` and categorised `DESIGN_GAP`.
- **Smallest safe next step:** add one optional setting, `git_allowed_hosts: str = ''`, and when
  non-empty require `parsed.hostname` (or the SCP `host` group) to be a member. Empty preserves
  today's behaviour, so it is a non-breaking ~5-line addition to `validate_clone_url` that the
  existing `test_git_auth.py` parametrisation can cover directly.
- **Affected data/migrations/providers/cost:** No migration. Bounds egress.
- **Recommended tests + acceptance criteria:**
  - Extend `test_rejects_unsafe_or_credential_bearing_urls` with `https://169.254.169.254/x.git`
    and `https://10.0.0.5/x.git` once an allowlist is configured.
  - Acceptance: with `GIT_ALLOWED_HOSTS=github.com`, any other host yields 422 at
    `POST /api/repositories` and no outbound connection is attempted.
- **Fix status:** report-only

---

### REV-619

- **ID:** REV-619
- **Category:** TEST_GAP
- **Severity:** medium
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** Every finding above is un-regression-tested. Because no test asserts a boundary,
  nothing fails when a boundary is removed — the loopback rebind of REV-600/601/602 can be
  reverted in a one-line compose edit with a green suite. Git credential handling is the one
  exception and it is well covered.
- **Evidence:**
  - `grep -rn '401\|403\|Authorization\|unauthorized' apps/api/tests` → one hit, and it is a
    fixture string inside `test_git_auth.py:55`. No test asserts any auth or authz outcome.
  - No test references CORS, `Origin`, `allow_origins`, or content type.
  - No test asserts the destructive cascade of `DELETE /api/repositories/{id}` or that the
    filesystem is cleaned (there is nothing to assert — see REV-605).
  - No test asserts redaction for a *non-git* exception (`test_git_auth.py:52-59` covers the git
    path only).
  - No ops/compose assertion anywhere: nothing checks published port bindings, container uid, or
    Redis auth state.
  - Good coverage that does exist, for balance: `apps/api/tests/test_git_auth.py:1-59` covers
    URL acceptance/rejection (including `https://token@…`, `file://`, `git://`,
    `ssh://root@host`, `..` traversal in both URL forms), askpass-not-URL token handling
    (asserting the token value appears in no environment value), `StrictHostKeyChecking=yes` +
    `UserKnownHostsFile`, and redaction of userinfo, token value and `Authorization:` headers.
    **These tests were read, not executed** — the host has no `fastapi` installed
    (`python3 -c "import fastapi"` → `ModuleNotFoundError`) and running the integration
    worktree's suite inside the live containers would have required mutating them. Hence every
    git-credential finding here is labelled `source-reviewed`, not `unit/API-tested`.
- **Probable cause + diagnostic confidence:** **High.** Security tests were not in scope for the
  features built so far.
- **Smallest safe next step:** one new test file with the two cheapest, highest-value
  assertions — the CORS preflight matrix (allowed origin → 200 with header, foreign origin →
  400) and a non-GET request with a non-JSON content type — since those lock in REV-603's fix.
  Port-binding assertions belong in a tiny ops script rather than pytest.
- **Affected data/migrations/providers/cost:** None. All assertions run without a provider.
- **Recommended tests + acceptance criteria:** as listed per finding above. Acceptance: reverting
  any of the REV-600/601/602/603 fixes turns the suite red.
- **Fix status:** report-only

---

### REV-613

- **ID:** REV-613
- **Category:** DOCUMENTATION_GAP
- **Severity:** low
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** The file an operator opens for security guidance answers a narrower question than
  the one they asked. `docs/security.md` is titled "Git credential security" and covers only
  that — it never says the API has no authentication, never mentions that the default compose
  publishes four ports on all interfaces, and never mentions Redis or PostgreSQL exposure.
  `docs/OPERATIONS.md` does list the right controls but files them under "**Before
  internet-facing deployment**", which mis-frames the trigger: the default local stack is
  already LAN-exposed, so those boxes need ticking on day one, not before public launch. Its
  list is also incomplete — it says "Restrict Docker port exposure for PostgreSQL and Redis" and
  omits the API and web ports, which are equally on `0.0.0.0`.
- **Evidence:**
  - `docs/security.md:1-72` — entirely git credentials; `grep -in 'auth\|port\|expose'` finds
    nothing about API authentication or port exposure.
  - `docs/OPERATIONS.md:14-24` — the checklist, under the heading "## Before internet-facing
    deployment"; line 18 names PostgreSQL and Redis only; line 23 is "☐ Add authentication
    before exposing repository content to other users".
  - `docs/OPERATIONS.md:10-12` presents the local URLs with no caveat that they are reachable
    from the LAN.
- **Probable cause + diagnostic confidence:** **High.** Scope of the document, not an error in it.
- **Smallest safe next step:** add a short "Deployment exposure" section at the top of
  `docs/security.md` stating plainly: no authentication exists; the default compose publishes
  3000/8000/5432/6379 on all interfaces; run it only on a trusted host and rebind to
  `127.0.0.1`. Then retitle the OPERATIONS checklist so port restriction is a day-one item.
- **Affected data/migrations/providers/cost:** None.
- **Recommended tests + acceptance criteria:** none automatable. Acceptance: `docs/security.md`
  answers "is this thing authenticated?" in its first paragraph.
- **Fix status:** report-only

---

### REV-614

- **ID:** REV-614
- **Category:** SECURITY_RISK
- **Severity:** low
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** The MCP bridge accepts `KW_API_BEARER_TOKEN` and sends it as
  `Authorization: Bearer …`. Nothing on the server verifies it — there is no security scheme, no
  dependency, no middleware. An operator who configures a token can reasonably believe the API is
  protected when it is not. The mitigation is that the documentation is unusually careful about
  precisely this, so this is a `low`: an affordance that implies a control, not a broken control.
- **Evidence:**
  - `apps/mcp/knowledge_way_mcp/client.py:42` reads the env var; `:80-81` attaches the header.
  - `curl -s http://localhost:8000/openapi.json` → `securitySchemes: None`; no auth dependency
    anywhere in `main.py` (REV-602).
  - The docs are explicit and correct: `docs/mcp.md:17` — "it **only becomes protection when the
    deployed API or its reverse proxy validates that header**"; `docs/mcp.md:54` — "The current
    local stack has no mandatory API authentication, so do not expose port 8000 publicly".
  - The bridge itself is a genuine positive and deserves recording: it is GET-only and
    path-restricted (`client.py:73-74`, `if not path.startswith("/api/"): raise`), every input is
    length-bounded (`client.py:45-56`), IDs are `quote(..., safe="")`-escaped (`client.py:124`),
    `depth` ≤ 2 and `max_nodes` ≤ 100 are enforced client-side (`client.py:114-118`), the base
    URL must be absolute http(s) with no query/fragment (`client.py:63-65`), and
    `server.py:8-11` advertises "no mutation tools exist" — accurate: all six tools are reads.
    Its one rough edge is `client.py:90-92`, which puts up to 1 000 characters of the API's error
    body into an exception the agent sees, so REV-607's `error_message` content would surface in
    an agent transcript.
- **Probable cause + diagnostic confidence:** **High**, and it is a deliberate forward-compatible
  knob rather than a mistake.
- **Smallest safe next step:** none in the MCP client. When API auth is built, the server side
  must reject a *missing* token rather than ignore it — that is the acceptance criterion to
  capture now.
- **Affected data/migrations/providers/cost:** None.
- **Recommended tests + acceptance criteria:** once auth exists, an API test asserting that a
  request with no `Authorization` header gets 401 and one with a wrong token gets 401. Acceptance:
  `KW_API_BEARER_TOKEN` unset ⇒ MCP tools fail closed.
- **Fix status:** report-only

---

### REV-615

- **ID:** REV-615
- **Category:** CORRECTNESS_RISK
- **Severity:** low
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** Two config footguns on one line. (1) `cors_origins.split(',')` does not strip
  whitespace, and Starlette compares origins by exact string equality, so
  `CORS_ORIGINS=http://localhost:3000, http://kw.local:3000` silently fails for the second entry
  — the browser error is opaque and the natural next step is to "fix" it with `*`. (2) `*` is the
  dangerous end state: with `allow_credentials` unset, Starlette answers `ACAO: *`, and because
  there is no auth (REV-602), *any* page on the internet could then read the entire indexed
  corpus from the victim's browser. The blast radius of that one character is larger here than in
  a system that has authentication.
- **Evidence:**
  - `main.py:18` — `allow_origins=settings.cors_origins.split(',')`, no `.strip()`, no filtering
    of empty entries.
  - `config.py:39` — `cors_origins: str = "http://localhost:3000"`; `.env.example:18` ships the
    same single-origin value.
  - Live behaviour confirms the current value is the restrictive default (foreign preflight →
    `400 Disallowed CORS origin`, quoted under REV-602). The `*` case was **not** exercised —
    that would have required changing the live configuration.
- **Probable cause + diagnostic confidence:** **High**, straightforward.
- **Smallest safe next step:**
  `allow_origins=[o.strip() for o in settings.cors_origins.split(',') if o.strip()]` — one line.
  Optionally refuse to start when the value is `*` while no auth exists; that is a two-line guard
  in `config.py` and is the more valuable half.
- **Affected data/migrations/providers/cost:** None.
- **Recommended tests + acceptance criteria:** unit test that `"a, b"` yields `["a","b"]`;
  preflight test per configured origin. Acceptance: a multi-origin `CORS_ORIGINS` works for every
  entry.
- **Fix status:** report-only

---

### REV-616

- **ID:** REV-616
- **Category:** DOCUMENTATION_GAP
- **Severity:** low
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** `compose.git-secrets.example.yml` mounts the deploy key and `known_hosts` but never
  sets `GIT_SSH_KEY_PATH` / `GIT_SSH_KNOWN_HOSTS_PATH`, which is what actually makes them usable.
  Following that file alone yields a fail-closed error
  (`GIT_SSH_KEY_PATH is required for SSH Git URLs`) that does not name the missing step. Failing
  closed is the right behaviour, so the impact is confusion, not exposure.
- **Evidence:**
  - `compose.git-secrets.example.yml:1-19` — `secrets:` blocks for api and worker plus the
    top-level `secrets:` definitions. No `environment:` and no `env_file` addition.
  - `git_auth.py:46-52,67-68` — `_required_file` raises `GitConfigurationError` when the setting
    is empty, before any git call.
  - The information is not missing from the project, only from that file: `docs/security.md:15-18`
    gives the exact env block, and `:39` correctly instructs `chmod 0400` on the host secret
    files (which matters, since Compose outside Swarm bind-mounts the host file and OpenSSH
    refuses a group/world-readable key).
- **Probable cause + diagnostic confidence:** **High.** The example was written as a fragment to
  be read alongside `docs/security.md`.
- **Smallest safe next step:** add the two `environment:` lines to both services in the example
  file, and a one-line comment pointing at `docs/security.md`.
- **Affected data/migrations/providers/cost:** None.
- **Recommended tests + acceptance criteria:** none automatable. Acceptance: a private-repo clone
  succeeds using only that override plus `.env`.
- **Fix status:** report-only

---

### REV-617

- **ID:** REV-617
- **Category:** SECURITY_RISK
- **Severity:** low
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** `git_environment()` builds a deliberately minimal, allowlisted environment —
  `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`,
  `GIT_ASKPASS=/dev/null` — but `run()` only applies it when a `clone_url` is passed, which is
  3 of the 6 git invocations. `git checkout --detach`, `git reset --hard origin/HEAD`,
  `git rev-parse HEAD` and `git branch --show-current` run with `env=None`, so they inherit the
  container's **entire** environment, which via `env_file: .env` includes every provider API key,
  plus system/global gitconfig and interactive prompting. No leak follows today (these four are
  local operations that do not talk to a remote and do not print their environment), so this is
  defence-in-depth applied inconsistently rather than a live hole.
- **Evidence:**
  - `ingestion.py:23-24` — `env=git_environment(clone_url) if clone_url else None`.
  - Call sites with `clone_url`: `ingestion.py:193` (clone), `:195` (fetch revision), `:198`
    (fetch origin). Without: `:196` (`checkout --detach`), `:198` (`reset --hard`), `:199`
    (`rev-parse`), `:238` (`branch --show-current`).
  - `docker-compose.yml:20,31` — `env_file: .env` on both api and worker, so `OPENAI_API_KEY`
    and any configured provider key are process environment variables inherited by every child.
- **Probable cause + diagnostic confidence:** **High.** The hardened env was introduced for the
  credential-bearing calls; the local ones were left alone.
- **Smallest safe next step:** make `run()` always use a base environment and merge the
  credential parts only when `clone_url` is given — i.e. split `git_environment` into
  `_base_env()` and the credential overlay. Small, local, and covered by extending
  `test_git_auth.py`.
- **Affected data/migrations/providers/cost:** None.
- **Recommended tests + acceptance criteria:** unit test asserting no `OPENAI_*`/`VERTEX_*`/
  `OPENROUTER_*` key is present in the environment of **any** git invocation. Acceptance: all six
  call sites run with an allowlisted environment.
- **Fix status:** report-only

---

### REV-618

- **ID:** REV-618
- **Category:** OPTIMIZATION_OPPORTUNITY (recorded as a positive baseline)
- **Severity:** info
- **Evidence level:** `source-reviewed`
- **Applies to:** both
- **Impact:** Recording what is already correct, so that a later refactor cannot regress it
  silently and so that the workstream's negative results are on the record rather than merely
  absent. **Command injection, path traversal and SQL injection were each traced concretely and
  are refuted**, as follows.
- **Evidence:**
  - **No shell anywhere.** `grep -rn 'shell=True\|os.system\|Popen\|eval(\|exec(' apps/api apps/mcp`
    → no match. The single subprocess call site is `ingestion.py:26`,
    `subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True, env=env)` with
    `args` an already-split tuple. A crafted `clone_url` cannot introduce a shell metacharacter
    because there is no shell, and cannot introduce a git *option* because `validate_clone_url`
    requires either an `https`/`ssh` scheme or the literal `git@` SCP prefix, so a leading `-`
    fails (`urlsplit('-upload-pack=…').scheme == ''`). Whitespace is rejected outright
    (`git_auth.py:27`, `any(c.isspace() for c in value)`), so argument splitting is impossible.
    `ext::`, `file://` and `git://` are rejected by the scheme allowlist (and covered by
    `test_git_auth.py:17-26`).
  - **No path traversal into or out of `REPOSITORY_STORAGE_PATH`.** The only filesystem join is
    `ingestion.py:192`, `root=Path(settings.repository_storage_path)/repo_id`, and `repo_id` is
    **never** client-supplied: it is a server-generated UUID (`models.py:7,11`,
    `default=uid` where `uid()` is `str(uuid.uuid4())`), and `RepositoryIn` (`main.py:22`) exposes
    only `name`, `clone_url` and `requested_revision` — there is no way to submit an id. The
    routes that *do* take `{repo_id}` from the path use it exclusively as a database key
    (`db.get(Repository, repo_id)`), never as a path component. `requested_revision` is pinned to
    `^[0-9a-f]{40}$` at `main.py:22,24` before it reaches `git fetch`/`git checkout`. `..` is
    additionally rejected in both URL forms (`git_auth.py:31,41`). Traversal is **refuted**.
  - **No SQL injection.** Every statement is a SQLAlchemy Core/ORM expression with bound
    parameters. `grep -rn 'execute(f\|scalar(f\|scalars(f'` → no match; the only `text()` in the
    application is `db.py:23`, a constant `SELECT version_num FROM alembic_version`. The
    `ilike(f'%{…}%')` forms in `search.py:65,68,72,77` and `like(prefix+'%')` in `main.py:211`
    interpolate into the *pattern operand*, which is a bound parameter, not into SQL text. Live
    confirmation: `GET /api/repositories/%27%20OR%201%3D1--` → `404`, as do `not-a-uuid` and a
    foreign UUID (ids are `String(36)`, so no `DataError`/500 either). The residual issue is
    unescaped LIKE wildcards, which is a cost problem, not an injection one — folded into
    REV-604.
  - **Git credential handling is genuinely well built.** Credentials never enter a URL
    (`validate_clone_url` rejects userinfo, password, query and fragment;
    `git_auth.py:35-38`), never enter argv (the HTTPS token is fetched by
    `GIT_ASKPASS=/app/app/git_askpass.py`, which reads a mounted file and writes it to stdout —
    `git_askpass.py:11-16`; so `/proc/<pid>/cmdline` never contains it), never enter the
    environment as a *value* (only `GIT_HTTPS_TOKEN_FILE`, a path — asserted by
    `test_git_auth.py:36`), and are never persisted (no column stores them). SSH host-key
    checking is **enforced, not disabled**: `git_auth.py:69-72` builds
    `ssh -i <key> -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=<hosts>`
    with both files `shlex.quote`d and both *mandatory* — `_required_file` raises when either is
    missing or unreadable, so SSH fails closed rather than falling back.
    `grep -rn 'StrictHostKeyChecking=no\|-o StrictHostKeyChecking=accept-new\|ssh-keyscan' apps/`
    → **no match**, and `docs/security.md:12` explicitly warns against `ssh-keyscan` as the sole
    verification step. Git error text is redacted before persistence (`git_auth.py:83-95`,
    covering URL userinfo, the token value read back from its file, and `Authorization:`
    headers) and truncated to 2 000 characters (`ingestion.py:29`).
  - **No secret is committed, and `.env` never was.**
    `git log --all --diff-filter=A --name-only --pretty=format: | sort -u | grep -iE '\.env$|\.env\.|\.pem$|\.key$|id_rsa|\.p12$|\.pfx$|credential|secret|token|\.npmrc|\.git-credentials|tfvars'`
    (excluding `data/`) returns exactly two paths across **all** refs: `.env.example` and
    `compose.git-secrets.example.yml` — both intentional, both containing only key names, paths
    and the development-default database DSN. `.env` is present on disk and is gitignored
    (`git check-ignore -v .env` → `.gitignore:6:.env`), and it has never appeared in any commit
    on any ref. The live `.env` was read for **key names only**; it defines
    `DATABASE_URL, REDIS_URL, OPENAI_API_KEY, OPENAI_CHAT_MODEL, OPENAI_EMBEDDING_MODEL,
    REPOSITORY_STORAGE_PATH, MAX_FILE_SIZE, MAX_INDEX_WORKERS, EMBEDDING_BATCH_SIZE,
    CHAT_CONTEXT_LIMIT, CORS_ORIGINS, GIT_SSH_KEY_PATH, GIT_SSH_KNOWN_HOSTS_PATH,
    GIT_HTTPS_TOKEN_FILE, GIT_HTTPS_USERNAME` and no value of any kind was displayed or recorded.
    (`MAX_INDEX_WORKERS` has no counterpart in `config.py` and, with `extra="ignore"`, is silently
    dead — noted for the config workstream.)
  - **No start-up DDL.** `db.py:18-27` verifies the alembic head and refuses to serve on
    mismatch; it never creates or alters a table. Consistent with §5.C.
  - **Provider secrets are only ever sent as request headers** to the provider's own endpoint
    (`providers.py:38,110`; `code_cards.py:213`) and are never logged: the telemetry lines
    (`code_cards.py:114-198`) emit status codes, timings and symbol names only.
- **Probable cause + diagnostic confidence:** n/a — these are verified negatives and positives.
  Confidence **high** for each, on the evidence quoted.
- **Smallest safe next step:** none. Keep `apps/api/tests/test_git_auth.py` as the regression
  anchor and extend it rather than replacing it when `validate_clone_url` next changes.
- **Affected data/migrations/providers/cost:** None.
- **Recommended tests + acceptance criteria:** already covered by `test_git_auth.py:1-59` (read,
  not executed — see REV-619). Acceptance: that file stays green and grows with each new URL form.
- **Fix status:** report-only

---

## Required later, not implemented today

Stated as a **requirement for future work**. None of the following exists in the codebase at
`c122529` or on `main`, and nothing in this section should be read as describing current
behaviour. Per §7 this review makes **no claim** that tenant isolation, roles, authentication or
centrally enforced authorization exist — they do not.

What the current design already gets right, and what a principal model must therefore preserve:
server-derived scope (§3.1) is honoured in the sense that repository-scoped routes re-derive
their scope from the path parameter and re-check it (`main.py:56-62`), so the *shape* an
authorization filter needs is already there. It is a filter slot with nothing in it.

1. **Principal.** There is no notion of a caller. Something must establish identity before any
   route can make a decision — for the stated self-hosted single-user model the honest minimum is
   a single static API token verified in one dependency, plus loopback-only binding; a real
   multi-user deployment needs OIDC or the Firebase Authentication path sketched in
   `docs/HOSTED_PRODUCT_AND_UI_VISION.md:50`. The MCP bridge already sends
   `Authorization: Bearer` (REV-614), so the client half of the simplest version exists.
2. **Tenant.** `workspaces` is currently a grouping construct with no owner column and no
   isolation semantics (`models.py:12-14`). A tenant model needs an owning principal on the
   workspace, and — this is the part that cannot be retrofitted cheaply — a decision about
   repositories, which today are **global**: `GET /api/repositories`, `GET /api/search`,
   `GET /api/files/{file_id}` and every graph route ignore workspace membership entirely, and
   `workspace_repositories` enforces that a repository belongs to *at most one* workspace
   (`models.py:16`) while permitting it to belong to none. The live database has 1 repository and
   **0 workspaces**, so every existing row is unassigned. Any tenant model must first answer what
   an unassigned repository is: invisible, owned by an implicit default tenant, or migrated.
3. **Roles.** No role, capability or permission exists anywhere. The distinction that matters
   most for this product is not read/write but **read vs. spend**: 15 routes mutate state and 4
   consume minutes of CPU or provider budget (see the route table). A reader role that cannot
   trigger `reindex` or `code-cards` would cover the majority of the real risk.
4. **Centrally enforced authorization.** Today each route re-derives scope inline. An
   authorization decision must be enforced in **one** place — a dependency that resolves
   (principal, workspace) → allowed repository set, which every query then filters on — rather
   than re-implemented per route, or the 42nd route will forget. ADR-0001's invariant 5 already
   *describes* this filter as if it existed (REV-610); implementing it is what would make that
   sentence true.
5. **Audit.** No route records who did anything. `indexing_jobs` records *what* happened but has
   no actor column, so after a destructive `DELETE` there is no way to establish what caused it.
   An actor column on `indexing_jobs` plus an append-only log of mutating requests is the minimum
   for a multi-user deployment.
6. **Cost governance.** Per §3.10 provider work must be opt-in and cost-observable. The opt-in
   half exists and works (`code_cards_enabled` defaults `False`, `embedding_provider` defaults
   `"none"`, and `providers.py:154-177` returns `None` rather than attempting a request when
   unconfigured). What does not exist is a *budget*: no per-principal quota, no daily ceiling, no
   spend counter, no queue-depth admission control. `input_tokens`/`output_tokens` are persisted
   per code card (`models.py:32`), so the raw material for a spend counter is already there.
7. **Transport security.** No TLS anywhere; the API and web ports are plain HTTP
   (`apps/api/Dockerfile:9`), and there is no reverse proxy in the compose file. Required before
   any non-loopback exposure, and a precondition for any token-based scheme, since a bearer token
   over plain HTTP on a LAN is recoverable by anything on that LAN.

## Not assessed

- **Whether the Redis RCE is exploitable end to end.** Not attempted, and it must not be: the
  proof would require writing a crafted `rq:job:*` hash and having the worker deserialize it,
  which is code execution against the user's own stack and outside a source-review mandate. The
  finding rests on three independently verified facts — unauthenticated off-loopback Redis
  access, `protected-mode no`, and `rq.serializers.DefaultSerializer.loads is pickle.loads` —
  plus RQ's documented job storage format. Only read-only Redis commands were sent.
- **`COPY … FROM PROGRAM` on PostgreSQL.** Superuser status was verified with a read-only
  `SELECT usesuper`; the RCE consequence follows from PostgreSQL's documented behaviour for
  superusers and was deliberately not executed.
- **Any destructive or billable route.** `POST /api/repositories`, `/reindex`, `/sync`,
  `/code-cards`, `/explanations`, `/documentation/generate`, `/chat`, `/search/semantic` and
  `DELETE /api/repositories/{id}` were **never called**. Blast-radius and cost claims for them
  are `source-reviewed`, derived from the code plus the live row counts in the shared brief.
- **Private-repository git credential paths end to end.** No deploy key or HTTPS token is
  configured in this deployment (`GIT_SSH_KEY_PATH`, `GIT_SSH_KNOWN_HOSTS_PATH`,
  `GIT_HTTPS_TOKEN_FILE` are all empty in `.env`), and the single indexed repository is public.
  So askpass behaviour, `StrictHostKeyChecking=yes` against a real host, and redaction of a real
  authentication failure are `source-reviewed` only. Verifying them would require provisioning a
  private repository and a credential — out of scope for a read-only review.
- **Execution of the existing security-relevant unit tests.** `apps/api/tests/test_git_auth.py`
  was read line by line but not run: the host lacks the dependencies
  (`python3 -c "import fastapi"` → `ModuleNotFoundError`) and running the integration worktree's
  suite inside the live containers would have required copying files into them, i.e. mutating the
  running stack. Consequently **no** finding in this report claims `unit/API-tested`.
- **Integration-branch runtime.** Per the shared brief the stack was not rebuilt on `c122529`.
  Live evidence (ports, CORS, timings, OpenAPI, DB) is evidence about `main`; where a finding
  applies to `both`, that is because the relevant file is byte-identical across the two refs and
  I verified it with `git diff` rather than assuming it.
- **The `*` CORS configuration.** Its consequence is reasoned from Starlette's documented
  behaviour; it was not exercised, because that would have meant editing the live configuration.
- **Web-tier security (`apps/web`).** Only its Dockerfile, its published port and its user-facing
  copy were examined for this workstream. Client-side concerns — XSS in rendered file content
  (`files/[id]/page.tsx` and the `<pre>` blocks in the symbol page), `dangerouslySetInnerHTML`
  usage, dependency vulnerabilities in `package-lock.json`, and the `API_INTERNAL_URL`
  server-side fetch path — were not reviewed. `npm install` (not `ci`) at
  `apps/web/Dockerfile:6` and the full-context `COPY --from=build /app .` at `:12` are noted in
  passing, un-assessed.
- **Host-level controls.** Whether a firewall in front of the docker host mitigates the port
  exposure was not assessed; note that Docker's published ports install `DOCKER` chain DNAT rules
  that bypass most `ufw` configurations, so a `ufw` rule should not be assumed to help. The
  off-loopback reachability proofs above were performed against the host's own LAN address from a
  separate network namespace, which establishes that the bind is not loopback-only but does not
  establish reachability from a different physical machine.
- **Dependency and image CVE scanning.** `docs/OPERATIONS.md:24` lists it as an open item; no
  scan was run. Pinned versions are recorded in `apps/api/requirements.txt` for whoever does.
