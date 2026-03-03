# Adapter Documentation

This folder documents each adapter. The docs follow the NormalizedEvent contract and list the
fields available to templates after parsing.

## Shared Fields (All Adapters)

Every adapter returns a NormalizedEvent with these fields:

- `source`
- `event`
- `severity` (`success` | `info` | `warning` | `error`)
- `title`
- `message`
- `tags` (optional)
- `entities` (optional)
- `raw` (original payload, possibly truncated)
- `timestamp` (ISO8601, set server-side)

Templates access these fields directly, for example `{{ source }}` or `{{ entities.repo }}`.

Important:

- `message` is plain text (`str`), not an object.
- Do not use `{{ message.entities.repo }}`.
- Use `{{ entities.repo }}` for structured fields.
- Do not prefix with `event.` (`{{ event.source }}` is invalid in this app).

## Adapters

- `generic-json`: `docs/adapters/generic-json.md`
- `generic-text`: `docs/adapters/generic-text.md`
- `github`: `docs/adapters/github.md`
- `forgejo` / `gitea`: `docs/adapters/forgejo.md`
