from __future__ import annotations

from typing import Any

from app.adapters.types import NormalizedEvent


def _finalize_message(value: str) -> str:
    lines = value.rstrip().splitlines()
    if not lines:
        return ""
    # Matrix markdown uses two trailing spaces for a hard line break.
    return "".join(f"{line.rstrip()}  \n" if line.strip() else "\n" for line in lines)


def _severity_for_workflow(conclusion: str | None, status: str | None) -> str:
    if conclusion == "success":
        return "success"
    if conclusion in {"failure", "timed_out", "startup_failure", "action_required"}:
        return "error"
    if conclusion in {"cancelled", "neutral", "skipped", "stale"}:
        return "warning"
    if status in {"queued", "in_progress", "requested", "waiting", "pending"}:
        return "info"
    return "info"


def _build_tags(github_event: str, action: str | None) -> list[str]:
    tags = [f"github:{github_event}"]
    if action:
        tags.append(f"action:{action}")
    return tags


def adapt(payload: Any, github_event: str | None) -> NormalizedEvent:
    if not isinstance(payload, dict):
        return NormalizedEvent(
            source="github",
            event=f"github.{github_event or 'unknown'}",
            severity="info",
            title="GitHub Event",
            message=_finalize_message(str(payload)),
            raw=payload,
        ).with_timestamp()

    event_name = (github_event or "unknown").strip().lower()
    action = payload.get("action")
    repo = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    actor = payload.get("sender") if isinstance(payload.get("sender"), dict) else {}
    repo_name = repo.get("full_name") or repo.get("name") or "unknown repo"
    actor_name = actor.get("login") or "unknown"

    severity = "info"
    title = f"GitHub {event_name}"
    message = f"Repository: {repo_name}\nActor: {actor_name}"
    entities: dict[str, Any] = {
        "repo": repo_name,
        "actor": actor_name,
        "github_event": event_name,
    }

    if event_name == "workflow_run":
        run = payload.get("workflow_run") if isinstance(payload.get("workflow_run"), dict) else {}
        run_name = run.get("name") or "workflow"
        run_number = run.get("run_number")
        status = run.get("status")
        conclusion = run.get("conclusion")
        url = run.get("html_url") or run.get("url")
        severity = _severity_for_workflow(
            str(conclusion) if conclusion is not None else None,
            str(status) if status is not None else None,
        )
        title = f"{run_name} #{run_number}" if run_number is not None else str(run_name)
        message = (
            f"Repository: {repo_name}\n"
            f"Action: {action or '-'}\n"
            f"Status: {status or '-'}\n"
            f"Conclusion: {conclusion or '-'}\n"
            f"Branch: {run.get('head_branch') or '-'}\n"
            f"Run: {url or '-'}"
        )
        entities.update(
            {
                "url": url,
                "workflow": run_name,
                "workflow_status": status,
                "workflow_conclusion": conclusion,
                "branch": run.get("head_branch"),
            }
        )
    elif event_name == "pull_request":
        pr = payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
        number = pr.get("number")
        pr_title = pr.get("title") or "pull request"
        merged = bool(pr.get("merged"))
        pr_action = str(action or "")
        if pr_action == "closed" and merged:
            severity = "success"
        elif pr_action == "closed":
            severity = "warning"
        else:
            severity = "info"
        title = f"PR #{number} {pr_title}" if number is not None else str(pr_title)
        message = (
            f"Repository: {repo_name}\n"
            f"Action: {action or '-'}\n"
            f"State: {pr.get('state') or '-'}\n"
            f"URL: {pr.get('html_url') or '-'}"
        )
        entities.update(
            {
                "url": pr.get("html_url"),
                "pr_number": number,
                "pr_state": pr.get("state"),
                "pr_merged": merged,
            }
        )
    elif event_name == "release":
        release = payload.get("release") if isinstance(payload.get("release"), dict) else {}
        tag = release.get("tag_name") or "release"
        severity = "info"
        title = f"Release {tag}"
        message = (
            f"Repository: {repo_name}\n"
            f"Action: {action or '-'}\n"
            f"Target: {release.get('target_commitish') or '-'}\n"
            f"URL: {release.get('html_url') or '-'}"
        )
        entities.update({"url": release.get("html_url"), "tag": tag})
    elif event_name == "push":
        ref = str(payload.get("ref") or "")
        branch = ref.split("/")[-1] if ref else None
        compare_url = payload.get("compare")
        commit_count = len(payload.get("commits", [])) if isinstance(payload.get("commits"), list) else 0
        severity = "info"
        title = f"Push to {branch or 'unknown'}"
        message = (
            f"Repository: {repo_name}\n"
            f"Branch: {branch or '-'}\n"
            f"Commits: {commit_count}\n"
            f"Compare: {compare_url or '-'}"
        )
        entities.update({"url": compare_url, "branch": branch, "commit_count": commit_count})
    else:
        action_label = f" ({action})" if action else ""
        title = f"GitHub {event_name}{action_label}"
        message = f"Repository: {repo_name}\nActor: {actor_name}\nAction: {action or '-'}"

    return NormalizedEvent(
        source="github",
        event=f"github.{event_name}",
        severity=severity,
        title=title,
        message=_finalize_message(message),
        tags=_build_tags(event_name, str(action) if action is not None else None),
        entities=entities,
        raw=payload,
    ).with_timestamp()
