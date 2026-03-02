# Adapter: generic-text

## Detection

Used when the request is **not** JSON (for example `text/plain`).

## Parsing Rules

- `source`: `generic`
- `event`: `generic.text`
- `severity`: `info`
- `title`: `Generic Text`
- `message`: payload as string
- `raw`: full payload

## Template Fields

- `{{ event.source }}`
- `{{ event.event }}`
- `{{ event.severity }}`
- `{{ event.title }}`
- `{{ event.message }}`
- `{{ event.raw }}`

## Example Templates

Simple:

```jinja
{{ status_icon(event.severity) }} {{ event.message }}

Source: {{ event.source }}
Event: {{ event.event }}
Title: {{ event.title|default("-") }}
```

Compact:

```jinja
{{ status_icon(event.severity) }} {{ event.title }}
{{ event.message }}
```
