"""Publish reviewed drafts to the live site repo."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

# Paths
PIPELINE_DIR = Path(__file__).resolve().parent.parent.parent
DRAFTS_DIR = PIPELINE_DIR / "drafts"
SITE_DIR = PIPELINE_DIR.parent
POLLS_DIR = SITE_DIR / "polls"
INDEX_PATH = SITE_DIR / "index.html"

# Marker in index.html where new poll cards are inserted
INSERT_MARKER = "<!-- ADD MORE POLLS HERE -->"


def publish(slug: str, response_count: int, date_range: str, title: str) -> None:
    """
    Copy reviewed drafts to the site repo and update index.html.

    1. Copy drafts/[slug].html → lennys-polls-site/polls/[slug].html
    2. Copy drafts/[slug]-social.html → lennys-polls-site/polls/[slug]-social.html
    3. Insert a poll card into index.html before the INSERT_MARKER
    """
    # Verify drafts exist
    dashboard_draft = DRAFTS_DIR / f"{slug}.html"
    social_draft = DRAFTS_DIR / f"{slug}-social.html"

    if not dashboard_draft.exists():
        raise FileNotFoundError(f"Dashboard draft not found: {dashboard_draft}")
    if not social_draft.exists():
        print(f"  [publish] Warning: Social cards draft not found: {social_draft}")

    # Ensure polls directory exists
    POLLS_DIR.mkdir(parents=True, exist_ok=True)

    # Copy files
    dashboard_dest = POLLS_DIR / f"{slug}.html"
    shutil.copy2(dashboard_draft, dashboard_dest)
    print(f"  [publish] Copied {dashboard_draft.name} → {dashboard_dest}")

    if social_draft.exists():
        social_dest = POLLS_DIR / f"{slug}-social.html"
        shutil.copy2(social_draft, social_dest)
        print(f"  [publish] Copied {social_draft.name} → {social_dest}")

    # Update index.html
    _update_index(slug, title, response_count, date_range)

    print()
    print("  Done! Next steps:")
    print(f"  1. cd {SITE_DIR}")
    print(f"  2. Review the changes")
    print(f"  3. git add -A && git commit -m 'Add {title} poll'")
    print(f"  4. git push  (Vercel auto-deploys)")


def _count_existing_polls() -> int:
    """Count how many poll cards already exist in index.html."""
    if not INDEX_PATH.exists():
        return 0
    content = INDEX_PATH.read_text()
    return len(re.findall(r'class="poll-card', content))


def _update_index(slug: str, title: str, response_count: int, date_range: str) -> None:
    """Insert a new poll card into index.html before the INSERT_MARKER."""
    if not INDEX_PATH.exists():
        print(f"  [publish] Warning: index.html not found at {INDEX_PATH}")
        return

    content = INDEX_PATH.read_text()

    # Check if this poll is already in the index
    if f"/polls/{slug}.html" in content:
        print(f"  [publish] Poll '{slug}' already in index.html — skipping update")
        return

    if INSERT_MARKER not in content:
        print(f"  [publish] Warning: Insert marker not found in index.html")
        return

    # Determine animation delay class based on existing polls
    existing_count = _count_existing_polls()
    delay_class = f"delay-{existing_count + 1}" if existing_count < 5 else "delay-3"

    # Build the new poll card HTML
    card_html = f"""    <a href="/polls/{slug}.html" class="poll-card animate-in {delay_class}">
      <div class="poll-card-content">
        <div class="poll-card-title">{title}</div>
        <div class="poll-card-meta">
          <span>{response_count} responses</span>
          <span>{date_range}</span>
        </div>
      </div>
      <div class="poll-card-arrow">→</div>
    </a>

    """

    # Insert before the marker
    content = content.replace(INSERT_MARKER, card_html + INSERT_MARKER)
    INDEX_PATH.write_text(content)
    print(f"  [publish] Updated index.html with new poll card")
