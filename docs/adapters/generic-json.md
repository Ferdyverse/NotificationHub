# Adapter: generic-json

## Detection

Used when the request is JSON and **no** specific event header is detected
(e.g. no `X-GitHub-Event`, `X-Forgejo-Event`, `X-Gitea-Event`).

## Parsing Rules

If the payload is an object, these fields are taken (with defaults):

- `source`: `payload.source` or `"generic"`
- `event`: `payload.event` or `"generic.json"`
- `severity`: `payload.severity` or `"info"`
- `title`: `payload.title` or `""`
- `message`: `payload.message` or (if missing) JSON pretty-printed
- `tags`: `payload.tags` (only if list)
- `entities`: `payload.entities` (only if object)
- `raw`: full payload

If the payload is **not** an object, a generic event is created:

- `source`: `generic`
- `event`: `generic.json`
- `severity`: `info`
- `title`: `Generic JSON`
- `message`: `str(payload)`
- `raw`: full payload

## Template Fields

Examples:

- `{{ source }}`
- `{{ event }}`
- `{{ severity }}`
- `{{ title }}`
- `{{ message }}`
- `{{ tags }}`
- `{{ entities }}`
- `{{ raw }}`

## Example Templates

Simple:

```jinja
{{ status_icon(severity) }} {{ message }}

Source: {{ source }}
Event: {{ event }}
Title: {{ title|default("-") }}
```

With entities/tags:

```jinja
{{ status_icon(severity) }} {{ title|default("Generic Event") }}

Source: {{ source }}
Event: {{ event }}
Tags: {{ tags|default([]) }}
Entities: {{ entities|default({}) }}
```
