"""Is the open-source project still maintained? Used for the chip in the top bar of the web app.

Reads the public GitHub API for the repository named in the ``GITHUB_REPO`` environment variable
(``owner/name``). No key is needed; the free limit is 60 requests per hour per address, so the web app
caches the answer. With no repository configured, or with no network, the chip simply says "Open source".
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone

ACTIVE_DAYS = 90          # last push within 3 months
SLOW_DAYS = 365           # within a year: slow; older: inactive


def classify(days: int | None) -> tuple[str, str]:
    """(label, level) for the number of days since the last push. level: ok, warn, bad or none."""
    if days is None:
        return "Open source", "none"
    if days <= ACTIVE_DAYS:
        return "Open source · Active", "ok"
    if days <= SLOW_DAYS:
        return "Open source · Slow", "warn"
    return "Open source · Inactive", "bad"


def _fetch(repo: str, timeout: float = 4.0) -> dict:
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "document-analyst"})
    with urllib.request.urlopen(req, timeout=timeout) as r:      # nosec - fixed host
        return json.load(r)


def repo_status(repo: str | None = None, fetch=_fetch, now: datetime | None = None) -> dict:
    """Returns {label, level, days, repo, detail}. Never raises."""
    repo = (repo if repo is not None else os.getenv("GITHUB_REPO", "")).strip()
    if not repo or "<" in repo or repo.count("/") != 1:
        label, level = classify(None)
        return {"label": label, "level": level, "days": None, "repo": "", "detail": "set GITHUB_REPO=owner/name to show activity"}
    try:
        info = fetch(repo)
        pushed = datetime.fromisoformat(info["pushed_at"].replace("Z", "+00:00"))
        if info.get("archived"):
            return {"label": "Open source · Archived", "level": "bad", "days": None, "repo": repo,
                    "detail": "the repository is archived"}
        days = max(0, ((now or datetime.now(timezone.utc)) - pushed).days)
        label, level = classify(days)
        return {"label": label, "level": level, "days": days, "repo": repo,
                "detail": f"last push {days} day(s) ago"}
    except Exception as e:                                       # offline, rate limit, missing repo
        label, level = classify(None)
        return {"label": label, "level": level, "days": None, "repo": repo, "detail": f"status unavailable ({type(e).__name__})"}
