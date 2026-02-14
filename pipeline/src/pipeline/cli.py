"""CLI entry point for the Lenny's Polls pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import PipelineOutput, SurveyConfig, SurveysFile

load_dotenv()

PIPELINE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PIPELINE_DIR / "config" / "surveys.yaml"
DRAFTS_DIR = PIPELINE_DIR / "drafts"


def _load_config(survey_id: str) -> SurveyConfig:
    """Load survey config from surveys.yaml by ID."""
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    surveys_file = SurveysFile(**data)
    for survey in surveys_file.surveys:
        if survey.id == survey_id:
            return survey
    available = [s.id for s in surveys_file.surveys]
    print(f"Error: Survey '{survey_id}' not found in config.")
    print(f"Available surveys: {', '.join(available)}")
    sys.exit(1)


def _find_config_by_slug(slug: str) -> SurveyConfig | None:
    """Find survey config by slug."""
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    surveys_file = SurveysFile(**data)
    for survey in surveys_file.surveys:
        if survey.slug == slug:
            return survey
    return None


# ── status command ────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> None:
    """Pull live status from surveys.info and send to Slack."""
    from . import polly, slack, ingest

    config = _load_config(args.survey_id)
    print(f"Fetching status for: {config.title}")

    try:
        survey_data = polly.get_survey_info(args.survey_id)
    except Exception as e:
        print(f"Error fetching from Polly: {e}")
        sys.exit(1)

    # Ingest to get respondent count and distribution
    respondents = ingest.ingest(survey_data, config)
    rated = [r for r in respondents if r.rating is not None]
    total = len(rated)

    # Build distribution
    from collections import Counter
    counts = Counter(r.rating for r in rated)
    distribution = []
    for rating in sorted(config.scale_labels.keys()):
        n = counts.get(rating, 0)
        pct = n / total * 100 if total else 0
        distribution.append((rating, pct))

    # Check if survey is still active
    active = survey_data.get("active", False)
    time_remaining = "Active" if active else "Closed"

    msg = slack.format_status_message(
        title=config.title,
        response_count=total,
        distribution=distribution,
        time_remaining=time_remaining,
    )
    print(msg)
    print()

    slack.send_status(msg)


# ── generate command ──────────────────────────────────────────────────

def cmd_generate(args: argparse.Namespace) -> None:
    """Full pipeline: ingest → analyze → synthesize → render."""
    from . import polly, ingest, quant, qual, render, social

    config = _load_config(args.survey_id)
    print(f"Generating dashboard for: {config.title}")
    print()

    # Step 1: Fetch data from Polly
    print("[1/4] Fetching data from Polly API...")
    try:
        survey_data = polly.get_survey_info(args.survey_id)
    except Exception as e:
        print(f"Error fetching from Polly: {e}")
        sys.exit(1)

    # Step 2: Ingest
    print("[2/4] Ingesting and cross-referencing respondent data...")
    respondents = ingest.ingest(survey_data, config)
    print(f"  Found {len(respondents)} complete respondents")

    # Step 3: Quantitative analysis
    print("[3/4] Running quantitative analysis...")
    quant_results = quant.analyze(respondents, config)
    print(f"  Distribution: {' / '.join(f'{b.pct}%' for b in quant_results.distribution)}")
    print(f"  Date range: {quant_results.date_range}")

    # Step 4: Qualitative synthesis (Claude API)
    print("[4/4] Running qualitative synthesis (Claude API)...")
    qual_results = qual.synthesize(respondents, quant_results, config)
    print(f"  Generated {len(qual_results.themes.love_themes)} love themes, "
          f"{len(qual_results.themes.hate_themes)} hate themes")
    print(f"  Generated {len(qual_results.social_cards.cards)} social cards")

    # Build output
    output = PipelineOutput(
        config=config,
        quant=quant_results,
        qual=qual_results,
    )

    # Render
    print()
    print("Rendering templates...")
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    dashboard_path = render.write_dashboard(output, DRAFTS_DIR)
    print(f"  Dashboard: {dashboard_path}")

    social_path = social.write_social(output, DRAFTS_DIR)
    print(f"  Social cards: {social_path}")

    print()
    print("Done! Review the drafts:")
    print(f"  open {dashboard_path}")
    print(f"  open {social_path}")
    print()
    print(f"When ready, publish with: python -m pipeline publish {config.slug}")


# ── publish command ───────────────────────────────────────────────────

def cmd_publish(args: argparse.Namespace) -> None:
    """Copy reviewed drafts to site repo and update index."""
    from . import publish as pub

    slug = args.slug
    config = _find_config_by_slug(slug)

    if config is None:
        print(f"Warning: No config found for slug '{slug}' — using slug as-is")
        # Try to read from the draft to get minimal info
        title = slug.replace("-", " ").title()
        response_count = 0
        date_range = ""
    else:
        title = config.title
        # We need quant data for response count and date range
        # Try reading from the draft HTML to extract these
        draft_path = DRAFTS_DIR / f"{slug}.html"
        if draft_path.exists():
            import re
            content = draft_path.read_text()
            # Extract response count from meta
            match = re.search(r'(\d+) responses', content)
            response_count = int(match.group(1)) if match else 0
            # Extract date range from meta
            match = re.search(r'<span class="dot"></span>\s*([A-Z][a-z]+ \d+[^<]*\d{4})', content)
            date_range = match.group(1) if match else ""
        else:
            response_count = 0
            date_range = ""

    # Verify draft exists
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

    # status
    p_status = subparsers.add_parser("status", help="Check live survey status and notify Slack")
    p_status.add_argument("survey_id", help="Polly survey ID")

    # generate
    p_generate = subparsers.add_parser("generate", help="Full pipeline: ingest → analyze → render")
    p_generate.add_argument("survey_id", help="Polly survey ID")

    # publish
    p_publish = subparsers.add_parser("publish", help="Copy drafts to site repo")
    p_publish.add_argument("slug", help="Poll slug (e.g. how-do-you-feel-about-your-job)")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "publish":
        cmd_publish(args)


if __name__ == "__main__":
    main()
