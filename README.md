# NotificationHub

NotificationHub is a self-hosted webhook hub with a small web UI.
It receives events, normalizes payloads, renders messages via templates, and delivers notifications to native targets such as Matrix, Discord, and Email.

## Current Features

- Webhook ingest endpoint: `POST /ingest/{slug}`
- Per-ingress authentication via:
- `Authorization: Bearer <secret>`
- `?token=<secret>`
- `X-Gitlab-Token: <secret>`
- `X-Hub-Signature-256` / `X-Hub-Signature` (GitHub HMAC signature)
- `X-Gitea-Signature` / `X-Forgejo-Signature` (Gitea/Forgejo HMAC signature)
- Adapters: `generic-json`, `generic-text`, `github` (auto-detected via `X-GitHub-Event`), and `forgejo`/`gitea` (auto-detected via `X-Forgejo-Event` or `X-Gitea-Event`)
- UI (HTMX + server-rendered templates) for ingresses, routes, templates, and event logs
- Optional per-ingress default template (useful when sharing routes across sources)
- Template preview and test-send from UI
- In-memory dedupe window and per-ingress rate limiting
- SQLite persistence with SQLAlchemy and Alembic migrations

## Tech Stack

- Python 3.12+
- FastAPI
- SQLAlchemy
- Alembic
- Jinja2 (sandboxed)
- HTMX + Tailwind (server-rendered)

## Local Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Recommended environment variables:

```bash
export DATABASE_URL="sqlite:///./data/app.db"
export BASE_URL="http://localhost:8080"
export UI_BASIC_AUTH_USER="admin"
export UI_BASIC_AUTH_PASS="change-me"
export SESSION_SECRET="please-change-this"
export DEFAULT_DEDUPE_SECONDS="60"
export DEFAULT_RATE_LIMIT_PER_MIN="60"
```

Run migrations and start the app:

```bash
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Useful URLs:

- UI: `http://localhost:8080/ui/ingresses`
- Health: `http://localhost:8080/health`

## Docker

Build and run locally:

```bash
docker build -t notificationhub:dev .
docker run --rm -p 8080:8080 --env-file .env notificationhub:dev
```

Or use the provided Compose file:

```bash
docker compose -f compose.yml up -d
```

## Backup and Restore

NotificationHub includes a built-in backup tool for SQLite databases:

```bash
python -m app.tools.backup --help
```

Create a backup archive:

```bash
python -m app.tools.backup create --output backups/notificationhub-prod.tar.gz
```

Restore a backup archive:

```bash
python -m app.tools.backup restore --input backups/notificationhub-prod.tar.gz --force
```

Production with Docker Compose (example):

```bash
docker compose exec notificationhub python -m app.tools.backup create --output /data/backup/notificationhub-prod.tar.gz
```

Then copy the archive from your production host to your test PC and restore it there.
Before restoring, stop the app/container that currently uses the target SQLite file.

## Webhook Usage

JSON example:

```bash
curl -i -X POST "http://localhost:8080/ingest/<slug>" \
  -H "Authorization: Bearer <secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "generic",
    "event": "demo.push",
    "severity": "info",
    "title": "Demo Event",
    "message": "Hello NotificationHub",
    "tags": ["demo"],
    "entities": {"service": "example"}
  }'
```

Text example:

```bash
curl -i -X POST "http://localhost:8080/ingest/<slug>?token=<secret>" \
  -H "Content-Type: text/plain" \
  -d "Plain text payload"
```

Successful ingest returns `204 No Content`.

Authentication notes:

- GitLab can use the webhook secret token directly (`X-Gitlab-Token`).
- GitHub sends only an HMAC signature header, not the raw secret.
- Existing ingresses created before signature support may require one secret rotation in the UI so signature verification can be enabled.

## Discord Full Embeds

You can define full Discord webhook payloads directly in a template:

1. Open a template in the UI.
2. Fill `Discord Embed JSON Template (optional)` with JSON rendered via Jinja variables.
3. Use the template on a Discord route.

Accepted shapes:

- Full Discord webhook payload object (for example with `content`, `embeds`, `username`, `avatar_url`)
- Single embed object (auto-wrapped into `{"embeds": [ ... ]}`)
- Embed array (auto-wrapped into `{"embeds": [ ... ]}`)

Example:

```json
{
  "content": "Build notification",
  "embeds": [
    {
      "title": "{{ title }}",
      "description": "{{ message }}",
      "color": 5793266,
      "fields": [
        {"name": "Source", "value": "{{ source }}", "inline": true},
        {"name": "Event", "value": "{{ event }}", "inline": true}
      ],
      "footer": {"text": "NotificationHub"},
      "timestamp": "{{ timestamp }}"
    }
  ]
}
```

## Routing

- NotificationHub sends events to ingress-assigned routes (fan-out).
- Only active routes are used.
- Template selection order: ingress default template -> route template -> global default template.

## Development

Run tests:

```bash
pytest -q
```

Core paths:

- App entrypoint: `app/main.py`
- Security/auth: `app/security/auth.py`
- Adapters: `app/adapters/`
- Template rendering: `app/render/templates.py`
- Database models: `app/models.py`
- Migrations: `alembic/`

## License

This project is licensed under **AGPL-3.0-only**.

- Full text: `LICENSE`
- Attribution notice: `NOTICE`

## Adapter Documentation

- `docs/adapters/README.md`
