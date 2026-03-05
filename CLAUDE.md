# CLAUDE.md — NotificationHub

Self-hosted webhook ingestion + formatting + routing service with a small web UI.
Receives events (Komodo, Forgejo, Home Assistant, generic webhooks), normalizes them,
renders via templates, and delivers natively to Matrix, Discord, or Email.

## Stack

- **Language:** Python 3.12+
- **Backend:** FastAPI
- **ORM:** SQLAlchemy + Alembic (migrations enabled)
- **UI:** HTMX + Tailwind, server-rendered Jinja2 templates
- **Persistence:** SQLite (`DATABASE_URL=sqlite:///./data/app.db`)
- **Auth (UI):** Basic Auth via `UI_BASIC_AUTH_USER` / `UI_BASIC_AUTH_PASS`
- **Dedupe/Rate-limit:** In-memory (MVP)
- **Delivery:** Native Matrix, Discord, Email (no Apprise)

## Directory layout

```
app/
  main.py          # FastAPI app + routes
  config.py        # env config
  db.py            # DB session & models
  models.py        # SQLAlchemy models
  adapters/        # payload -> NormalizedEvent
  render/          # Jinja2 environment + template helpers
  routing/         # route + rule evaluation
  delivery/        # delivery clients (Matrix, Discord, Email)
  security/        # token checks, basic auth
  static/          # css/js
templates/         # HTML UI templates + message templates
tests/
docker/
docs/
  adapters/        # Adapter docs + template examples
```

When adding a new adapter: create/update its docs in `docs/adapters/`.

## Dev commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Test / Lint
pytest -q
ruff format .
ruff check .

# Docker
docker build -t formatter-hub:dev .
docker run --rm -p 8080:8080 --env-file .env formatter-hub:dev
```

## NormalizedEvent contract

All adapters MUST produce:

| Field | Type | Notes |
|---|---|---|
| `source` | str | e.g. `"forgejo"`, `"komodo"`, `"generic"` |
| `event` | str | e.g. `"repo.push"`, `"stack.updated"` |
| `severity` | str | `"success"` \| `"info"` \| `"warning"` \| `"error"` |
| `title` | str | |
| `message` | str | may be multi-line |
| `tags` | list[str] | optional |
| `entities` | dict[str, any] | host/service/repo/user/url/etc — optional |
| `raw` | any | original payload, stored but not templated |
| `timestamp` | str | ISO8601; server-assigned if missing |

Templates and routing rules operate **only** on these fields.

## Ingress (webhooks)

- `POST /ingest/{slug}`
- Auth: `Authorization: Bearer <secret>` per ingress; fallback `?token=<secret>`
- JSON body if `Content-Type: application/json`, else text
- Responses: 204 success | 401/403 auth failure | 422 invalid payload
- **Never log secrets.** Store secrets hashed (bcrypt/argon2) if feasible.

## Routing rules (MVP)

Evaluated in order; first match wins. Supported conditions:
- `source == value`
- `event startswith prefix`
- `severity == value`
- `tags contains value`
- `entities.<key> == value`
- `always` (unconditional)

Fallback: ingress fan-out routes. Log which rule matched.

## Templates

- Markdown by default; consistent status icons: success ✅, warning ⚠️, error ❌, info ℹ️
- Always provide a built-in default fallback template.
- Sandbox rendering — no arbitrary code execution; strict undefined in preview mode.
- UI must support: edit, preview (with logged event or sample payload), test-send.

## Event log

- Store last N events (configurable): `ingress_id`, `created_at`, normalized fields, delivery result, raw payload (size-capped).
- UI filters: source, severity, event, ingress.

## Testing requirements

Cover:
- Ingress auth (token required, wrong token rejected)
- Adapter parsing (generic-json, generic-text)
- Rule evaluation (first match wins, fallback)
- Template rendering (happy path + missing vars)
- Delivery (mock — never call real Matrix/Discord/Email in unit tests)

Prefer small, fast unit tests.

## Coding guidelines

- Keep endpoints and DB schema minimal; iterate.
- Every feature needs: HTMX partial + server handler + validation + at least one test.
- No heavy deps (Redis, queues) unless clearly necessary.
- Mark security-relevant changes (auth, secrets, webhook validation) explicitly in commits.

## Commit style

`feat:` / `fix:` / `chore:` + short summary.
Body: what changed, how to test, migration notes if any.
Do NOT add `Co-Authored-By` trailers to commits.

## Environment variables

```
DATABASE_URL=sqlite:///./data/app.db
BASE_URL=http://localhost:8080
UI_BASIC_AUTH_USER=...
UI_BASIC_AUTH_PASS=...
DEFAULT_DEDUPE_SECONDS=60
DEFAULT_RATE_LIMIT_PER_MIN=60
```
