from __future__ import annotations

from typing import Any

from app.adapters.types import NormalizedEvent


def _finalize_message(value: str) -> str:
    lines = value.rstrip().splitlines()
    if not lines:
        return ""
    # Matrix markdown uses two trailing spaces for a hard line break.
    return "".join(f"{line.rstrip()}  \n" if line.strip() else "\n" for line in lines)


def _build_tags(source: str, event_name: str, action: str | None) -> list[str]:
    tags = [f"{source}:{event_name}"]
    if action:
        tags.append(f"action:{action}")
    return tags


def _extract_repo(payload: dict[str, Any]) -> dict[str, Any]:
    repo = payload.get("repository")
    return repo if isinstance(repo, dict) else {}


def _extract_actor(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("sender", "pusher", "actor", "user"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _actor_name(actor: dict[str, Any]) -> str:
    for key in ("login", "username", "name", "full_name"):
        value = actor.get(key)
        if value:
            return str(value)
    return "unknown"


def _repo_name(repo: dict[str, Any]) -> str:
    return str(repo.get("full_name") or repo.get("name") or "unknown repo")


def _number_from(entity: dict[str, Any]) -> int | str | None:
    for key in ("number", "id", "index"):
        value = entity.get(key)
        if value is not None:
            return value
    return None


def adapt(payload: Any, event: str | None, source: str = "forgejo") -> NormalizedEvent:
    event_name = (event or "unknown").strip().lower()

    if not isinstance(payload, dict):
        return NormalizedEvent(
            source=source,
            event=f"{source}.{event_name}",
            severity="info",
            title=f"{source.title()} Event",
            message=_finalize_message(str(payload)),
            raw=payload,
        ).with_timestamp()

    action = payload.get("action")
    repo = _extract_repo(payload)
    actor = _extract_actor(payload)
    repo_name = _repo_name(repo)
    actor_name = _actor_name(actor)

    severity = "info"
    title = f"{source.title()} {event_name}"
    message = f"Repository: {repo_name}\nActor: {actor_name}"
    entities: dict[str, Any] = {
        "repo": repo_name,
        "actor": actor_name,
        f"{source}_event": event_name,
    }

    if event_name == "push":
        ref = str(payload.get("ref") or "")
        branch = ref.split("/")[-1] if ref else None
        commit_count = (
            len(payload.get("commits", []))
            if isinstance(payload.get("commits"), list)
            else 0
        )
        compare_url = payload.get("compare_url") or payload.get("compare")
        title = f"Push to {branch or 'unknown'}"
        message = (
            f"Repository: {repo_name}\n"
            f"Branch: {branch or '-'}\n"
            f"Commits: {commit_count}\n"
            f"Compare: {compare_url or '-'}"
        )
        entities.update(
            {"url": compare_url, "branch": branch, "commit_count": commit_count}
        )
    elif event_name.startswith("pull_request"):
        pr = (
            payload.get("pull_request")
            if isinstance(payload.get("pull_request"), dict)
            else {}
        )
        number = _number_from(pr)
        pr_title = pr.get("title") or "pull request"
        merged = bool(pr.get("merged") or pr.get("merged_at"))
        pr_action = str(action or "")
        if pr_action == "closed" and merged:
            severity = "success"
        elif pr_action == "closed":
            severity = "warning"
        elif pr_action == "merged":
            severity = "success"
        title = f"PR #{number} {pr_title}" if number is not None else str(pr_title)
        message = (
            f"Repository: {repo_name}\n"
            f"Action: {action or '-'}\n"
            f"State: {pr.get('state') or '-'}\n"
            f"URL: {pr.get('html_url') or pr.get('url') or '-'}"
        )
        entities.update(
            {
                "url": pr.get("html_url") or pr.get("url"),
                "pr_number": number,
                "pr_state": pr.get("state"),
                "pr_merged": merged,
            }
        )
    elif event_name in {"issues", "issue"}:
        issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
        number = _number_from(issue)
        issue_title = issue.get("title") or "issue"
        issue_action = str(action or "")
        if issue_action == "closed":
            severity = "success"
        title = (
            f"Issue #{number} {issue_title}" if number is not None else str(issue_title)
        )
        message = (
            f"Repository: {repo_name}\n"
            f"Action: {action or '-'}\n"
            f"State: {issue.get('state') or '-'}\n"
            f"URL: {issue.get('html_url') or issue.get('url') or '-'}"
        )
        entities.update(
            {
                "url": issue.get("html_url") or issue.get("url"),
                "issue_number": number,
                "issue_state": issue.get("state"),
            }
        )
    elif event_name.startswith("issue_comment"):
        issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
        comment = (
            payload.get("comment") if isinstance(payload.get("comment"), dict) else {}
        )
        number = _number_from(issue)
        commenter = _actor_name(comment.get("user") or {}) if comment else "unknown"
        title = f"Comment on #{number}" if number is not None else "Issue Comment"
        message = (
            f"Repository: {repo_name}\n"
            f"Issue: {issue.get('title') or '-'}\n"
            f"By: {commenter}\n"
            f"URL: {comment.get('html_url') or comment.get('url') or '-'}"
        )
        entities.update(
            {
                "url": comment.get("html_url") or comment.get("url"),
                "issue_number": number,
                "commenter": commenter,
            }
        )
    elif event_name == "release":
        release = (
            payload.get("release") if isinstance(payload.get("release"), dict) else {}
        )
        tag = release.get("tag_name") or "release"
        title = f"Release {tag}"
        message = (
            f"Repository: {repo_name}\n"
            f"Action: {action or '-'}\n"
            f"Target: {release.get('target_commitish') or '-'}\n"
            f"URL: {release.get('html_url') or release.get('url') or '-'}"
        )
        entities.update(
            {"url": release.get("html_url") or release.get("url"), "tag": tag}
        )
    else:
        action_label = f" ({action})" if action else ""
        title = f"{source.title()} {event_name}{action_label}"
        message = (
            f"Repository: {repo_name}\nActor: {actor_name}\nAction: {action or '-'}"
        )

    return NormalizedEvent(
        source=source,
        event=f"{source}.{event_name}",
        severity=severity,
        title=title,
        message=_finalize_message(message),
        tags=_build_tags(
            source, event_name, str(action) if action is not None else None
        ),
        entities=entities,
        raw=payload,
    ).with_timestamp()
