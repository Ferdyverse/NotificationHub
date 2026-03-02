# AGENTS.md — NotificationHub (GUI + Webhooks + Native Delivery)

Codex: This repo implements a self-hosted webhook ingestion + formatting + routing service with a small web UI.
Goal: Receive events from multiple sources (Komodo, Forgejo, Home Assistant, generic webhooks), normalize them,
render them using templates, then send notifications via native delivery targets (Matrix, Discord, Email).

## Project goals (MVP "B")
- Web UI to manage:
  - Ingress endpoints (create/disable, rotate secret)
  - Templates (edit, preview, test-send)
  - Routes (Delivery targets)
  - Routing rules (simple rule set)
  - Event log (recent events with raw payload)
- HTTP ingestion:
  - POST /ingest/{slug}
  - Token/secret protection per ingress
  - Support adapters for: generic-json, generic-text (MVP)
  - Later adapters: komodo, forgejo, homeassistant
- Formatting:
  - Templates rendered to Markdown (Matrix-friendly)
  - Consistent status icons: success ✅, warning ⚠️, error ❌, info ℹ️
- Delivery:
  - Native delivery targets: Matrix, Discord, Email
  - Per-route configuration (including bearer tokens where applicable)
- Quality:
  - Dedupe window + per-ingress rate limit
  - Structured logging and clear error messages

## Non-goals (for MVP)
- Complex rule engine (keep routing rules simple and deterministic)
- Full auth system (use basic auth for UI if needed; no RBAC)
- Multi-tenant, HA clustering, or external queue systems

---

## Repository conventions
- Language: Python 3.12+
- Backend: FastAPI
- UI: HTMX + Tailwind (server-rendered templates)
- Templates: Jinja2
- Persistence: SQLite (MVP) via SQLModel or SQLAlchemy
- Migrations: Alembic (optional for MVP; OK to start without migrations if schema is small)

### Directory layout (suggested)
- app/
  - main.py                # FastAPI app + routes
  - config.py              # env config
  - db.py                  # DB session & models
  - models.py              # SQLModel/ORM models
  - adapters/              # payload -> normalized event
  - render/                # Jinja2 environment + template helpers
  - routing/               # route + rule evaluation
  - delivery/              # delivery clients
  - security/              # token checks, basic auth
  - static/                # css/js
  - templates/             # HTML templates (UI) + message templates
- tests/
- docker/
- docs/

---

## Setup commands
### Local (recommended)
- Create venv: `python -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run dev: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8080`
- Run tests: `pytest -q`
- Format: `ruff format .`
- Lint: `ruff check .`

### Docker
- Build: `docker build -t formatter-hub:dev .`
- Run: `docker run --rm -p 8080:8080 --env-file .env formatter-hub:dev`

---

## Configuration (env)
- DATABASE_URL=sqlite:///./data/app.db
- BASE_URL=http://localhost:8080
- UI_BASIC_AUTH_USER=...
- UI_BASIC_AUTH_PASS=...
- DEFAULT_DEDUPE_SECONDS=60
- DEFAULT_RATE_LIMIT_PER_MIN=60

### Delivery integration
Routes store target-specific configuration for Matrix, Discord, and Email (SMTP).
Bearer tokens can be configured per route where applicable.

---

## Normalized Event contract (internal)
All adapters MUST output a NormalizedEvent dict/object with:
- source: string (e.g. "forgejo", "komodo", "homeassistant", "generic")
- event: string (e.g. "repo.push", "stack.updated", "ha.state_changed")
- severity: one of: "success"|"info"|"warning"|"error"
- title: string
- message: string (can be multi-line)
- tags: list[string] (optional)
- entities: dict[string, any] (optional)   # host/service/repo/user/url/etc
- raw: any                                 # original payload (stored, not templated by default)
- timestamp: ISO8601 string (server assigned if missing)

Templates and routing rules operate ONLY on these fields.

---

## Webhooks (ingress)
- POST /ingest/{slug}
- Auth: header `Authorization: Bearer <secret>` (per ingress)
- Fallback for limited clients: query param `?token=<secret>`
- Body:
  - If Content-Type JSON: treat as json payload
  - Else: treat as text payload
- Response:
  - 204 on success
  - 401/403 on auth failures
  - 422 on invalid payload (include concise error)

Security:
- Never log secrets.
- Store ingress secrets hashed (e.g., bcrypt/argon2) if feasible; otherwise store as opaque but protect DB.

---

## Routing rules (MVP)
Rules are evaluated in order; first match wins.
Supported conditions:
- source == value
- event startswith prefix
- severity == value
- tags contains value
- entities.<key> == value
- always (no condition)
Fallback: ingress routes (fan-out)

Keep the implementation deterministic and explain matches in logs.

---

## Templates
- Message templates are Markdown by default.
- Provide a built-in default template (fallback) that always renders.
- Template rendering must be sandboxed:
  - Do not allow arbitrary code execution.
  - Use strict undefined variables (fail fast) in preview.
- UI must support:
  - Edit template
  - Preview with a selected logged event (or sample payload)
  - Test-send (render + deliver to selected route)

---

## Event log
- Store last N events (configurable), including:
  - ingress_id, created_at, normalized fields, delivery result
  - raw payload (trim/size cap to avoid DB bloat)
- Provide filtering in UI: source, severity, event, ingress

---

## Testing requirements
Add tests for:
- Ingress auth (token required, wrong token rejected)
- Adapter parsing (generic-json, generic-text)
- Rule evaluation (first match wins, fallback works)
- Template rendering (happy path + missing vars behavior)
- Delivery mock (do not call real Matrix/Discord/Email in unit tests)

Prefer small unit tests; avoid slow integration tests unless needed.

---

## Implementation guidance for Codex
- Start with MVP skeleton: models + ingestion + default template + delivery + minimal UI (Ingress list, Template list, Event log).
- Keep endpoints and DB schema minimal; iterate.
- For any feature, include:
  - UI piece (HTMX partials)
  - server handler
  - validation
  - at least one test
- Don’t introduce heavy dependencies (queues, redis) unless clearly needed.

---

## PR / commit message style (if Codex produces PRs)
- Title: `feat:` / `fix:` / `chore:` + short summary
- Body: include what changed, how to test, and any migration notes.
- Note security-relevant changes explicitly (auth, secrets, webhook validation).

---

## Confirmed Architecture Decisions (2026-03-01)
- Framework: FastAPI (confirmed)
- ORM: SQLAlchemy
- Migrations: Alembic (enabled)
- UI Auth: Basic Auth enabled via `UI_BASIC_AUTH_USER/PASS`
- Dedupe + Rate Limit: in-memory for MVP
- Delivery: Native Matrix/Discord/Email (Apprise removed)
