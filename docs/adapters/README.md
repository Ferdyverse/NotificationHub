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

Templates access these fields as `{{ event.source }}` or `{{ event.entities.repo }}`.

## Adapters

- `generic-json`: `docs/adapters/generic-json.md`
- `generic-text`: `docs/adapters/generic-text.md`
- `github`: `docs/adapters/github.md`
- `forgejo` / `gitea`: `docs/adapters/forgejo.md`
