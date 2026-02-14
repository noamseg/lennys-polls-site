"""Slack webhook for sending survey status updates."""

from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv()


def send_status(message: str) -> None:
    """Send a formatted status message to Slack via incoming webhook."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("  [slack] SLACK_WEBHOOK_URL not set — skipping Slack notification")
        return

    payload = {
        "text": message,
        "unfurl_links": False,
        "unfurl_media": False,
    }

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"  [slack] Message sent successfully")
    except httpx.HTTPError as e:
        print(f"  [slack] Failed to send message: {e}")


def format_status_message(
    title: str,
    response_count: int,
    distribution: list[tuple[int, float]],
    time_remaining: str | None = None,
) -> str:
    """Format a survey status update for Slack."""
    dist_str = " / ".join(f"{pct:.0f}%" for _, pct in distribution)

    lines = [
        f"*{title}* — Status Update",
        f"Responses: *{response_count}*",
    ]

    if time_remaining:
        lines.append(f"Time remaining: {time_remaining}")

    lines.append(f"Distribution: {dist_str}")

    return "\n".join(lines)
