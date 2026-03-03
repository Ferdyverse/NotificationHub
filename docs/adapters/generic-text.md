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

- `{{ source }}`
- `{{ event }}`
- `{{ severity }}`
- `{{ title }}`
- `{{ message }}`
- `{{ raw }}`

## Example Templates

Simple:

```jinja
{{ status_icon(severity) }} {{ message }}

Source: {{ source }}
Event: {{ event }}
Title: {{ title|default("-") }}
```

Compact:

```jinja
{{ status_icon(severity) }} {{ title }}
{{ message }}
```
