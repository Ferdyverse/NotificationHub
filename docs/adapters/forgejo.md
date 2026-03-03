# Adapter: forgejo / gitea

## Detection

Used when JSON requests include the `X-Forgejo-Event` or `X-Gitea-Event` header.

`source` is set to `forgejo` or `gitea` accordingly.

## Parsing Rules (Overview)

General:

- `source`: `forgejo` or `gitea`
- `event`: `<source>.<event>` (event name from header, lowercased)
- `tags`: `<source>:<event>` and optional `action:<action>`
- `entities` include: `repo`, `actor`, `<source>_event`

Specific events:

### `push`

- `severity`: `info`
- `title`: `Push to <branch>`
- `message`: Repository, Branch, Commits, Compare
- `entities` add: `url`, `branch`, `commit_count`

### `pull_request*`

- `severity`: `success` for `closed`+`merged` or `merged`, `warning` for `closed`, else `info`
- `title`: `PR #<number> <title>`
- `message`: Repository, Action, State, URL
- `entities` add: `url`, `pr_number`, `pr_state`, `pr_merged`

### `issues` / `issue`

- `severity`: `success` for `closed`, else `info`
- `title`: `Issue #<number> <title>`
- `message`: Repository, Action, State, URL
- `entities` add: `url`, `issue_number`, `issue_state`

### `issue_comment*`

- `severity`: `info`
- `title`: `Comment on #<number>`
- `message`: Repository, Issue, By, URL
- `entities` add: `url`, `issue_number`, `commenter`

### `release`

- `severity`: `info`
- `title`: `Release <tag>`
- `message`: Repository, Action, Target, URL
- `entities` add: `url`, `tag`

## Template Fields

Examples:

- `{{ source }}`
- `{{ event }}`
- `{{ title }}`
- `{{ message }}`
- `{{ entities.repo }}`
- `{{ entities.actor }}`
- `{{ entities.url }}`

## Example Templates

Generic:

```jinja
{{ status_icon(severity) }} {{ message }}

Repository: {{ entities.repo|default("-") }}
Actor: {{ entities.actor|default("-") }}
Link: {{ entities.url|default("-") }}
Event: {{ event }}
```

Combined (choose by event):

```jinja
{% if event in ["forgejo.push", "gitea.push"] %}
{{ status_icon(severity) }} {{ title }}

Repository: {{ entities.repo|default("-") }}
Branch: {{ entities.branch|default("-") }}
Commits: {{ entities.commit_count|default(0) }}
Compare: {{ entities.url|default("-") }}
{% elif event in ["forgejo.issue", "forgejo.issues", "gitea.issue", "gitea.issues"] %}
{{ status_icon(severity) }} {{ title }}

Repository: {{ entities.repo|default("-") }}
State: {{ entities.issue_state|default("-") }}
Link: {{ entities.url|default("-") }}
{% else %}
{{ status_icon(severity) }} {{ message }}

Repository: {{ entities.repo|default("-") }}
Actor: {{ entities.actor|default("-") }}
Link: {{ entities.url|default("-") }}
Event: {{ event }}
{% endif %}
```

Push focused:

```jinja
{{ status_icon(severity) }} {{ title }}

Repository: {{ entities.repo|default("-") }}
Branch: {{ entities.branch|default("-") }}
Commits: {{ entities.commit_count|default(0) }}
Compare: {{ entities.url|default("-") }}
```

Issue focused:

```jinja
{{ status_icon(severity) }} {{ title }}

Repository: {{ entities.repo|default("-") }}
State: {{ entities.issue_state|default("-") }}
Link: {{ entities.url|default("-") }}
```
