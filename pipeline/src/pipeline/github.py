"""GitHub Contents API client for pushing draft dashboards.

Uses fine-grained personal access token to push HTML files to the site repo.
Vercel auto-deploys on push, so drafts become live at their URL.
"""

from __future__ import annotations

import base64
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

REPO = "noamseg/lennys-polls-site"
API_BASE = "https://api.github.com"
DRAFTS_PREFIX = "polls/drafts"


def _headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set in environment")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _put_file(path: str, content: str, message: str) -> None:
    """Create or update a file via the GitHub Contents API.

    Handles both create (no SHA) and update (existing SHA) cases.
    """
    url = f"{API_BASE}/repos/{REPO}/contents/{path}"
    headers = _headers()

    # Check if file exists to get its SHA for updates
    sha = None
    resp = httpx.get(url, headers=headers, timeout=15)
    if resp.status_code == 200:
        sha = resp.json().get("sha")

    payload: dict = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
    }
    if sha:
        payload["sha"] = sha

    resp = httpx.put(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()


def push_draft_to_github(slug: str, dashboard_html: str, social_html: str) -> str:
    """Push dashboard and social HTML to the site repo as drafts.

    Returns the preview URL for the dashboard.
    """
    _put_file(
        f"{DRAFTS_PREFIX}/{slug}.html",
        dashboard_html,
        f"Draft dashboard: {slug}",
    )
    _put_file(
        f"{DRAFTS_PREFIX}/{slug}-social.html",
        social_html,
        f"Draft social cards: {slug}",
    )
    return f"https://lennyspolls.com/{DRAFTS_PREFIX}/{slug}.html"
