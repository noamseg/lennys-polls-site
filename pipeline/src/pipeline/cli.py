"""CLI entry point for the Lenny's Polls pipeline."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from .core import (
    RATING_EMOJIS,
    find_config_by_slug,
    run_generate,
    run_list_surveys,
    run_peek,
)

load_dotenv()

PIPELINE_DIR = Path(__file__).resolve().parent.parent.parent
DRAFTS_DIR = PIPELINE_DIR / "drafts"


def _confirm_send() -> bool:
    """Prompt user to confirm before sending to Slack."""
    try:
        answer = input("Send to Slack? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")


# ── surveys command ───────────────────────────────────────────────────

def cmd_surveys(args: argparse.Namespace) -> None:
    """List surveys from Polly API with active status."""
    try:
        items = run_list_surveys()
    except Exception as e:
        print(f"Error fetching from Polly API: {e}")
        sys.exit(1)

    if not items:
        print("No surveys found.")
        return

    print("Surveys:")
    print()
    for s in items:
        status = "🟢 Active" if s.active else "⚪ Closed"
        configured = " ✓ configured" if s.configured else ""
        print(f"  {s.title}")
        print(f"    ID: {s.id}  {status}{configured}")
        print()


# ── peek command ─────────────────────────────────────────────────────

def cmd_peek(args: argparse.Namespace) -> None:
    """Early peek: fetch all data -> compute distributions -> Claude analysis -> Slack."""
    from . import slack

    try:
        result = run_peek(args.survey_id, on_progress=print)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Console output
    print()
    print(f"🔍 {result.title} — Early Peek")
    print(f"{result.started} responded, {result.completed} completed · {result.date_range}{result.close_label}")

    for qd in result.question_dists:
        print()
        multi = " (select all)" if qd["is_multiselect"] else ""
        print(f"📊 {qd['question']}{multi}")
        if qd["is_rating"]:
            parts = []
            for c in qd["choices"]:
                emoji = RATING_EMOJIS.get(c.get("rating", 0), "⬜")
                parts.append(f"{emoji} {c['label']} {c['pct']:.0f}%")
            print(f"  {' · '.join(parts)}")
        else:
            for c in qd["choices"]:
                print(f"  {c['label']}: {c['pct']:.0f}% ({c['count']})")

    if result.analysis:
        print()
        print(f"💡 {result.analysis['headline']}")

        for section in result.analysis.get("sections", []):
            print()
            print(f"{section['emoji']} {section['title']}")
            for i, t in enumerate(section.get("themes", []), 1):
                suffix = " mentions" if i == 1 else ""
                print(f"  {i}. {t['name']} ({t['count']}{suffix})")
            for q in section.get("quotes", []):
                print(f"  💬 \"{q['text']}\" — {q['attribution']}")

    print()

    # Slack
    blocks = slack.format_peek_blocks(
        title=result.title,
        started=result.started,
        completed=result.completed,
        date_range=result.date_range,
        question_dists=result.question_dists,
        analysis=result.analysis,
        close_label=result.close_label,
    )
    if _confirm_send():
        slack.send_blocks(blocks, f"{result.title}: Early Peek — {result.started} responded, {result.completed} completed")


# ── generate command ──────────────────────────────────────────────────

def cmd_generate(args: argparse.Namespace) -> None:
    """Full pipeline: ingest -> analyze -> synthesize -> render."""
    try:
        result = run_generate(args.survey_id, on_progress=print)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    dashboard_path = DRAFTS_DIR / f"{result.config.slug}.html"
    dashboard_path.write_text(result.dashboard_html)
    print(f"  Dashboard: {dashboard_path}")

    social_path = DRAFTS_DIR / f"{result.config.slug}-social.html"
    social_path.write_text(result.social_html)
    print(f"  Social cards: {social_path}")

    print()
    print("Done! Review the drafts:")
    print(f"  open {dashboard_path}")
    print(f"  open {social_path}")
    print()
    print(f"When ready, publish with: python -m pipeline publish {result.config.slug}")


# ── publish command ───────────────────────────────────────────────────

def cmd_publish(args: argparse.Namespace) -> None:
    """Copy reviewed drafts to site repo and update index."""
    from . import publish as pub

    slug = args.slug
    config = find_config_by_slug(slug)

    if config is None:
        print(f"Warning: No config found for slug '{slug}' — using slug as-is")
        title = slug.replace("-", " ").title()
        response_count = 0
        date_range = ""
    else:
        title = config.title
        draft_path = DRAFTS_DIR / f"{slug}.html"
        if draft_path.exists():
            content = draft_path.read_text()
            match = re.search(r'(\d+) responses', content)
            response_count = int(match.group(1)) if match else 0
            match = re.search(r'<span class="dot"></span>\s*([A-Z][a-z]+ \d+[^<]*\d{4})', content)
            date_range = match.group(1) if match else ""
        else:
            response_count = 0
            date_range = ""

    dashboard_draft = DRAFTS_DIR / f"{slug}.html"
    if not dashboard_draft.exists():
        print(f"Error: No draft found at {dashboard_draft}")
        print(f"Run 'python -m pipeline generate <survey_id>' first.")
        sys.exit(1)

    print(f"Publishing: {title}")
    pub.publish(slug, response_count, date_range, title)


# ── Main entry ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Lenny's Polls Pipeline — automated survey-to-dashboard",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("surveys", help="List all surveys from Polly with active status")

    p_peek = subparsers.add_parser("peek", help="Early peek at all results → Slack")
    p_peek.add_argument("survey_id", help="Polly survey ID")

    p_generate = subparsers.add_parser("generate", help="Full pipeline: ingest → analyze → render")
    p_generate.add_argument("survey_id", help="Polly survey ID")

    p_publish = subparsers.add_parser("publish", help="Copy drafts to site repo")
    p_publish.add_argument("slug", help="Poll slug (e.g. how-do-you-feel-about-your-job)")

    args = parser.parse_args()

    if args.command == "surveys":
        cmd_surveys(args)
    elif args.command == "peek":
        cmd_peek(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "publish":
        cmd_publish(args)


if __name__ == "__main__":
    main()
