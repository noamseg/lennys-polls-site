"""Slack helpers for webhook messages and bot Block Kit formatters."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

from .core import SurveyListItem

load_dotenv()

RATING_EMOJIS = {1: "🟥", 2: "🟧", 3: "🟨", 4: "🟩", 5: "💚"}


def _sanitize_mrkdwn(text: str) -> str:
    """Sanitize user-generated text for safe embedding in Slack mrkdwn."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = re.sub(r"@(channel|here|everyone)", r"@ \1", text, flags=re.IGNORECASE)
    return text



def send_blocks(blocks: list[dict[str, Any]], fallback_text: str) -> None:
    """Send a Block Kit message to Slack via incoming webhook."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("  [slack] SLACK_WEBHOOK_URL not set — skipping Slack notification")
        return

    payload = {"blocks": blocks, "text": fallback_text}

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        print("  [slack] Block Kit message sent successfully")
    except httpx.HTTPError as e:
        print(f"  [slack] Failed to send message: {e}")


def format_peek_blocks(
    title: str,
    started: int,
    completed: int,
    date_range: str,
    question_dists: list[dict],
    analysis: dict[str, Any] | None,
    close_label: str = "",
) -> list[dict[str, Any]]:
    """Format full early peek as Slack Block Kit blocks."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🔍 {title} — Early Peek", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{started}* responded, *{completed}* completed · {date_range}{close_label}",
            },
        },
        {"type": "divider"},
    ]

    # All question distributions
    for qd in question_dists:
        q_text = qd["question"]
        choices = qd["choices"]
        multi = " _(select all)_" if qd["is_multiselect"] else ""

        lines = [f"*📊 {q_text}*{multi}", ""]
        if qd["is_rating"]:
            for c in choices:
                emoji = RATING_EMOJIS.get(c.get("rating", 0), "⬜")
                lines.append(f"{emoji}  {c['label']}  —  {c['pct']:.0f}%")
        else:
            for c in choices:
                lines.append(f"  {c['label']}: {c['pct']:.0f}% ({c['count']})")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })

    if not analysis:
        return blocks

    blocks.append({"type": "divider"})

    # Headline
    headline = analysis.get("headline", "")
    if headline:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*💡 {_sanitize_mrkdwn(headline)}*"},
        })

    # Themed sections with per-section quotes
    for section in analysis.get("sections", []):
        emoji = section.get("emoji", "📌")
        section_title = _sanitize_mrkdwn(section.get("title", ""))

        # Themes block
        theme_lines = [f"*{emoji} {section_title}*"]
        for i, t in enumerate(section.get("themes", []), 1):
            name = _sanitize_mrkdwn(t.get("name", ""))
            count = t.get("count", 0)
            suffix = " mentions" if i == 1 else ""
            theme_lines.append(f"{i}. {name} ({count}{suffix})")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(theme_lines)},
        })

        # Each quote as its own block for breathing room
        for q in section.get("quotes", []):
            text = _sanitize_mrkdwn(q.get("text", ""))
            attr = _sanitize_mrkdwn(q.get("attribution", ""))
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"> _{text}_\n> — {attr}"},
            })

    return blocks


def format_surveys_blocks(items: list[SurveyListItem]) -> list[dict[str, Any]]:
    """Format the survey list as Slack Block Kit blocks."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📋 Surveys", "emoji": True},
        },
    ]

    if not items:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "No surveys found."},
        })
        return blocks

    # Active polls first, then most recent closed (limit 3)
    active = [s for s in items if s.active]
    closed = [s for s in items if not s.active]
    MAX_CLOSED = 3
    shown = active + closed[:MAX_CLOSED]

    for s in shown:
        status = "🟢 Active" if s.active else "⚪ Closed"
        configured = "  ✓ configured" if s.configured else ""
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{_sanitize_mrkdwn(s.title)}*  {status}{configured}\n"
                    f"To peek at early results: /peek {s.id}\n"
                    f"To generate a full dashboard: /generate {s.id}"
                ),
            },
        })

    if len(closed) > MAX_CLOSED:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"+ {len(closed) - MAX_CLOSED} older closed polls not shown"},
            ],
        })

    return blocks


def format_generate_blocks(
    slug: str,
    title: str,
    preview_url: str,
) -> list[dict[str, Any]]:
    """Format the generate completion message as Slack Block Kit blocks."""
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📊 Dashboard Ready: {title}", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"Draft dashboard for *{_sanitize_mrkdwn(title)}* is live!\n\n"
                    f"<{preview_url}|View Dashboard>\n"
                    f"<{preview_url.replace('.html', '-social.html')}|View Social Cards>"
                ),
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Slug: `{slug}` · This is a draft preview — publish from CLI when ready."},
            ],
        },
    ]
