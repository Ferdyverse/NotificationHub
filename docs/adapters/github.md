# Adapter: github

## Detection

Used when JSON requests include the `X-GitHub-Event` header.

## Parsing Rules (Overview)

General:

- `source`: `github`
- `event`: `github.<event>` (event name from header, lowercased)
- `tags`: `github:<event>` and optional `action:<action>`
- `entities` include: `repo`, `actor`, `github_event`

Specific events:

### `workflow_run`

- `severity`: derived from `status` / `conclusion`
- `title`: `<workflow_name> #<run_number>`
- `message`: Repository, Action, Status, Conclusion, Branch, Run-URL
- `entities` add: `url`, `workflow`, `workflow_status`, `workflow_conclusion`, `branch`

### `pull_request`

- `severity`: `success` for `closed`+`merged`, `warning` for `closed`, else `info`
- `title`: `PR #<number> <title>`
- `message`: Repository, Action, State, URL
- `entities` add: `url`, `pr_number`, `pr_state`, `pr_merged`

### `release`

- `severity`: `info`
- `title`: `Release <tag>`
- `message`: Repository, Action, Target, URL
- `entities` add: `url`, `tag`

### `push`

- `severity`: `info`
- `title`: `Push to <branch>`
- `message`: Repository, Branch, Commits, Compare
- `entities` add: `url`, `branch`, `commit_count`

## Template Fields

Examples:

- `{{ event.source }}`
- `{{ event.event }}`
- `{{ event.title }}`
- `{{ event.message }}`
- `{{ event.entities.repo }}`
- `{{ event.entities.actor }}`
- `{{ event.entities.url }}`

## Example Templates

Generic:

```jinja
{{ status_icon(event.severity) }} {{ event.message }}

Repository: {{ event.entities.repo|default("-") }}
Actor: {{ event.entities.actor|default("-") }}
Link: {{ event.entities.url|default("-") }}
Event: {{ event.event }}
```

Combined (choose by event):

```jinja
{% if event.event == "github.workflow_run" %}
{{ status_icon(event.severity) }} {{ event.title }}

Repository: {{ event.entities.repo|default("-") }}
Branch: {{ event.entities.branch|default("-") }}
Status: {{ event.entities.workflow_status|default("-") }}
Conclusion: {{ event.entities.workflow_conclusion|default("-") }}
Run: {{ event.entities.url|default("-") }}
{% elif event.event == "github.pull_request" %}
{{ status_icon(event.severity) }} {{ event.title }}

Repository: {{ event.entities.repo|default("-") }}
State: {{ event.entities.pr_state|default("-") }}
Merged: {{ event.entities.pr_merged|default(false) }}
Link: {{ event.entities.url|default("-") }}
{% else %}
{{ status_icon(event.severity) }} {{ event.message }}

Repository: {{ event.entities.repo|default("-") }}
Actor: {{ event.entities.actor|default("-") }}
Link: {{ event.entities.url|default("-") }}
Event: {{ event.event }}
{% endif %}
```

Workflow run focused:

```jinja
{{ status_icon(event.severity) }} {{ event.title }}

Repository: {{ event.entities.repo|default("-") }}
Branch: {{ event.entities.branch|default("-") }}
Status: {{ event.entities.workflow_status|default("-") }}
Conclusion: {{ event.entities.workflow_conclusion|default("-") }}
Run: {{ event.entities.url|default("-") }}
```

Pull request focused:

```jinja
{{ status_icon(event.severity) }} {{ event.title }}

Repository: {{ event.entities.repo|default("-") }}
State: {{ event.entities.pr_state|default("-") }}
Merged: {{ event.entities.pr_merged|default(false) }}
Link: {{ event.entities.url|default("-") }}
```
