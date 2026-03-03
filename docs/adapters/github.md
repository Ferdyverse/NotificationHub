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
{% if event == "github.workflow_run" %}
{{ status_icon(severity) }} {{ title }}

Repository: {{ entities.repo|default("-") }}
Branch: {{ entities.branch|default("-") }}
Status: {{ entities.workflow_status|default("-") }}
Conclusion: {{ entities.workflow_conclusion|default("-") }}
Run: {{ entities.url|default("-") }}
{% elif event == "github.pull_request" %}
{{ status_icon(severity) }} {{ title }}

Repository: {{ entities.repo|default("-") }}
State: {{ entities.pr_state|default("-") }}
Merged: {{ entities.pr_merged|default(false) }}
Link: {{ entities.url|default("-") }}
{% else %}
{{ status_icon(severity) }} {{ message }}

Repository: {{ entities.repo|default("-") }}
Actor: {{ entities.actor|default("-") }}
Link: {{ entities.url|default("-") }}
Event: {{ event }}
{% endif %}
```

Workflow run focused:

```jinja
{{ status_icon(severity) }} {{ title }}

Repository: {{ entities.repo|default("-") }}
Branch: {{ entities.branch|default("-") }}
Status: {{ entities.workflow_status|default("-") }}
Conclusion: {{ entities.workflow_conclusion|default("-") }}
Run: {{ entities.url|default("-") }}
```

Pull request focused:

```jinja
{{ status_icon(severity) }} {{ title }}

Repository: {{ entities.repo|default("-") }}
State: {{ entities.pr_state|default("-") }}
Merged: {{ entities.pr_merged|default(false) }}
Link: {{ entities.url|default("-") }}
```
