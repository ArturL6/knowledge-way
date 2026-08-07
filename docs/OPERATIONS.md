# Operations and deployment checklist

## Local development

```bash
cp .env.example .env
docker compose up --build
```

- Web: `http://localhost:3000`
- API/OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Before internet-facing deployment

- [ ] Set unique PostgreSQL and Redis credentials; do not use development defaults.
- [ ] Put API/web behind TLS reverse proxy.
- [ ] Restrict Docker port exposure for PostgreSQL and Redis.
- [ ] Store `OPENAI_API_KEY` in a secret manager, never `.env` in source control.
- [ ] Configure allowed Git hosts and outbound network policy.
- [ ] Set backup/restore policy for PostgreSQL and repository checkout storage.
- [ ] Configure log redaction and retention.
- [ ] Add authentication before exposing repository content to other users.
- [ ] Run dependency scanning and image scanning in CI.

## Runtime checks

```bash
docker compose ps
curl -fsS http://localhost:8000/health
docker compose logs --tail=100 api worker
```

Never paste Git URLs containing tokens into logs, tickets, or chat. Use Git credential helpers, deploy keys, or a secret manager-backed credential reference.
