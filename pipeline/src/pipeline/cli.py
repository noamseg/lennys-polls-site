"""CLI entry point for the Lenny's Polls pipeline."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .ingest import _is_rating_question, _extract_rating
from .models import PipelineOutput, SurveyConfig, SurveysFile

load_dotenv()

PIPELINE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PIPELINE_DIR / "config" / "surveys.yaml"
DRAFTS_DIR = PIPELINE_DIR / "drafts"

RATING_EMOJIS = {1: "🟥", 2: "🟧", 3: "🟨", 4: "🟩", 5: "💚"}


# ── Config helpers ───────────────────────────────────────────────────

def _load_config(survey_id: str) -> SurveyConfig:
    """Load survey config from surveys.yaml by ID (required for generate/publish)."""
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


def _detect_config(survey_id: str, survey_data: dict) -> SurveyConfig:
    """Auto-detect a SurveyConfig from raw Polly API data."""
    title = (
        survey_data.get("title")
        or survey_data.get("name")
        or survey_data.get("question", "Survey")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

    # Find the rating question and parse scale labels
    scale_labels: dict[int, str] = {}
    for q in survey_data.get("questions", []):
        if q.get("type") != "multiple_choice":
            continue
        responses = [r for r in q.get("results", []) if not r.get("deleted")]
        if _is_rating_question(responses):
            title = q.get("text", title)
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            # Extract unique scale labels from response texts
            seen: set[int] = set()
            for r in responses:
                rating = _extract_rating(r.get("text", ""))
                if rating is not None and rating not in seen:
                    seen.add(rating)
                    # Extract the label part after "N - "
                    m = re.match(r"^\d+\s+[-–—]\s+(.+)", r["text"].strip())
                    if m:
                        scale_labels[rating] = m.group(1).strip()
            break

    if not scale_labels:
        scale_labels = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}

    scale_min = min(scale_labels.keys())
    scale_max = max(scale_labels.keys())
    scale_description = f"{scale_min} = {scale_labels[scale_min].lower()}, {scale_max} = {scale_labels[scale_max].lower()}"

    # Thresholds: 2nd-highest and 2nd-lowest
    sorted_keys = sorted(scale_labels.keys())
    positive_threshold = sorted_keys[-2] if len(sorted_keys) >= 2 else scale_max
    negative_threshold = sorted_keys[1] if len(sorted_keys) >= 2 else scale_min

    return SurveyConfig(
        id=survey_id,
        title=title,
        slug=slug,
        scale_labels=scale_labels,
        scale_description=scale_description,
        positive_threshold=positive_threshold,
        negative_threshold=negative_threshold,
        audience="respondents",
        subtitle_template="{n} {audience} shared their perspectives.",
        survey_tool="Polly survey",
    )


def _load_or_detect_config(survey_id: str, survey_data: dict) -> SurveyConfig:
    """Try loading config from surveys.yaml, fall back to auto-detection."""
    try:
        with open(CONFIG_PATH) as f:
            data = yaml.safe_load(f)
        surveys_file = SurveysFile(**data)
        for survey in surveys_file.surveys:
            if survey.id == survey_id:
                print(f"Using configured survey: {survey.title}")
                return survey
    except FileNotFoundError:
        pass

    config = _detect_config(survey_id, survey_data)
    print(f"Auto-detected config for: {config.title}")
    print(f"  Slug: {config.slug}")
    print(f"  Scale: {config.scale_description}")
    print(f"  Positive threshold: >= {config.positive_threshold}, Negative threshold: <= {config.negative_threshold}")
    return config


def _confirm_send() -> bool:
    """Prompt user to confirm before sending to Slack."""
    try:
        answer = input("Send to Slack? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")


# ── Generic survey data helpers ──────────────────────────────────────

def _short_choice(text: str) -> str:
    """Extract the short label from a choice like 'Option — longer explanation'."""
    for sep in [" — ", " – "]:
        if sep in text:
            before = text.split(sep, 1)[0].strip()
            # Don't split rating choices like "5 - Much better" — return the label part
            if before.isdigit():
                return text.split(sep, 1)[1].strip()
            return before
    # Handle "N - Label" format (but not "N-N" ranges like "11-50")
    m = re.match(r"^(\d+)\s+-\s+(.+)", text)
    if m and not m.group(2).strip().replace("+", "").isdigit():
        return m.group(2).strip()
    return text.strip()


def _ordinal_sort_key(choice_text: str) -> int | None:
    """Extract a leading number for ordinal sorting (e.g. '11-50' → 11, '5001+' → 5001).

    Returns None if the choice doesn't start with a number.
    """
    m = re.match(r"^(\d+)", choice_text.strip())
    return int(m.group(1)) if m else None


def _is_ordinal_choices(choice_texts: list[str]) -> bool:
    """Detect if choices form an ordinal scale (most start with a number)."""
    if len(choice_texts) < 3:
        return False
    numeric = sum(1 for t in choice_texts if _ordinal_sort_key(t) is not None)
    return numeric >= len(choice_texts) * 0.6


def _build_question_distributions(survey_data: dict) -> list[dict[str, Any]]:
    """Build response distributions for ALL multiple-choice questions."""
    questions = survey_data.get("questions", [])
    results = []

    for q in questions:
        if q.get("type") != "multiple_choice":
            continue

        responses = [r for r in q.get("results", []) if not r.get("deleted")]
        if not responses:
            continue

        unique_users = len(set(r["user_id"] for r in responses))
        is_multiselect = len(responses) > unique_users
        is_rating = _is_rating_question(responses)

        counts = Counter(r["text"] for r in responses)

        choices = []
        for choice_text, count in counts.most_common():
            pct = round(count / unique_users * 100, 1) if unique_users else 0
            label = _short_choice(choice_text)
            entry: dict[str, Any] = {"label": label, "count": count, "pct": pct}
            if is_rating:
                m = re.match(r"^(\d+)\s+[-–—]", choice_text)
                entry["rating"] = int(m.group(1)) if m else 0
            entry["_raw"] = choice_text
            choices.append(entry)

        if is_rating:
            choices.sort(key=lambda c: c.get("rating", 0))
        elif _is_ordinal_choices([c["_raw"] for c in choices]):
            choices.sort(key=lambda c: _ordinal_sort_key(c["_raw"]) or 0)

        for c in choices:
            del c["_raw"]

        max_pct = max((c["pct"] for c in choices), default=1)
        for c in choices:
            c["bar_width"] = round(c["pct"] / max_pct * 100, 1) if max_pct > 0 else 0

        results.append({
            "question": q.get("text", ""),
            "is_rating": is_rating,
            "is_multiselect": is_multiselect,
            "n_respondents": unique_users,
            "choices": choices,
        })

    return results


def _compute_survey_meta(survey_data: dict) -> tuple[int, int, str]:
    """Compute respondent counts and date range from raw survey data.

    Returns (total_started, total_completed, date_range).
    total_started = users who answered any question.
    total_completed = users who answered the last question in the survey.
    """
    questions = survey_data.get("questions", [])
    all_user_ids: set[str] = set()
    all_timestamps: list[datetime] = []

    for q in questions:
        for r in q.get("results", []):
            if not r.get("deleted"):
                all_user_ids.add(r["user_id"])
                ts = r.get("created_at")
                if ts:
                    try:
                        all_timestamps.append(
                            datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        )
                    except (ValueError, TypeError):
                        pass

    total_started = len(all_user_ids)

    # Completes = users who answered the last question
    total_completed = total_started
    if questions:
        last_q = questions[-1]
        last_users = {
            r["user_id"] for r in last_q.get("results", []) if not r.get("deleted")
        }
        total_completed = len(last_users)

    if not all_timestamps:
        return total_started, total_completed, "Date range unavailable"

    earliest = min(all_timestamps)
    latest = max(all_timestamps)

    if earliest.date() == latest.date():
        return total_started, total_completed, earliest.strftime("%b %-d, %Y")
    if earliest.year == latest.year:
        return total_started, total_completed, f"{earliest.strftime('%b %-d')} – {latest.strftime('%b %-d')}, {latest.year}"
    return total_started, total_completed, f"{earliest.strftime('%b %-d, %Y')} – {latest.strftime('%b %-d, %Y')}"


# ── surveys command ───────────────────────────────────────────────────

def cmd_surveys(args: argparse.Namespace) -> None:
    """List surveys from Polly API with active status."""
    from . import polly

    configured_ids: dict[str, SurveyConfig] = {}
    try:
        with open(CONFIG_PATH) as f:
            data = yaml.safe_load(f)
        surveys_file = SurveysFile(**data)
        configured_ids = {s.id: s for s in surveys_file.surveys}
    except FileNotFoundError:
        pass

    try:
        api_surveys = polly.list_surveys()
    except Exception as e:
        print(f"Error fetching from Polly API: {e}")
        sys.exit(1)

    if not api_surveys:
        print("No surveys found.")
        return

    print("Surveys:")
    print()
    for survey in api_surveys:
        sid = survey.get("id", "?")
        title = survey.get("title") or survey.get("name") or survey.get("question", "Untitled")
        active = survey.get("active", False)
        status = "🟢 Active" if active else "⚪ Closed"
        configured = " ✓ configured" if sid in configured_ids else ""

        print(f"  {title}")
        print(f"    ID: {sid}  {status}{configured}")
        print()


# ── peek command ─────────────────────────────────────────────────────

def cmd_peek(args: argparse.Namespace) -> None:
    """Early peek: fetch all data → compute distributions → Claude analysis → Slack."""
    from . import polly, slack
    from .qual import peek_analyze

    # Step 1: Fetch
    print("[1/3] Fetching data from Polly API...")
    try:
        survey_data = polly.get_survey_info(args.survey_id)
    except Exception as e:
        print(f"Error fetching from Polly: {e}")
        sys.exit(1)

    title = (
        survey_data.get("title")
        or survey_data.get("name")
        or survey_data.get("question", "Survey")
    )
    started, completed, date_range = _compute_survey_meta(survey_data)
    active = survey_data.get("active", False)
    close_at = survey_data.get("close_at")
    close_label = ""
    if close_at:
        try:
            close_dt = datetime.fromisoformat(close_at.replace("Z", "+00:00"))
            if active:
                close_label = f" · Closes {close_dt.strftime('%b %-d')}"
            else:
                close_label = f" · Closed {close_dt.strftime('%b %-d')}"
        except (ValueError, TypeError):
            pass
    print(f"Survey: {title} ({started} responded, {completed} completed{close_label})")
    print()

    # Step 2: Build distributions for all MC questions
    print("[2/3] Computing question distributions...")
    question_dists = _build_question_distributions(survey_data)
    open_count = sum(
        len([r for r in q.get("results", []) if not r.get("deleted")])
        for q in survey_data.get("questions", [])
        if q.get("type") == "open_ended"
        and not any(kw in q.get("text", "").lower() for kw in ("title", "current role"))
    )
    print(f"  {len(question_dists)} multiple-choice questions, {open_count} open-ended responses")

    # Detect config for scale context in analysis
    config = _detect_config(args.survey_id, survey_data)

    # Step 3: Claude analysis of open-ended responses
    analysis = None
    if open_count > 0:
        print("[3/3] Analyzing responses (Claude API)...")
        analysis = peek_analyze(title, survey_data, question_dists, config)
        print("  Done")
    else:
        print("[3/3] No open-ended responses to analyze — skipping Claude API")

    # ── Console output ───────────────────────────────────────────────
    print()
    print(f"🔍 {title} — Early Peek")
    print(f"{started} responded, {completed} completed · {date_range}{close_label}")

    for qd in question_dists:
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

    if analysis:
        print()
        print(f"💡 {analysis['headline']}")

        for section in analysis.get("sections", []):
            print()
            print(f"{section['emoji']} {section['title']}")
            for i, t in enumerate(section.get("themes", []), 1):
                suffix = " mentions" if i == 1 else ""
                print(f"  {i}. {t['name']} ({t['count']}{suffix})")
            for q in section.get("quotes", []):
                print(f"  💬 \"{q['text']}\" — {q['attribution']}")

    print()

    # ── Slack ────────────────────────────────────────────────────────
    blocks = slack.format_peek_blocks(
        title=title,
        started=started,
        completed=completed,
        date_range=date_range,
        question_dists=question_dists,
        analysis=analysis,
        close_label=close_label,
    )
    if _confirm_send():
        slack.send_blocks(blocks, f"{title}: Early Peek — {started} responded, {completed} completed")


# ── generate command ──────────────────────────────────────────────────

def cmd_generate(args: argparse.Namespace) -> None:
    """Full pipeline: ingest → analyze → synthesize → render."""
    from . import polly, ingest, quant, qual, render, social

    print("[1/4] Fetching data from Polly API...")
    try:
        survey_data = polly.get_survey_info(args.survey_id)
    except Exception as e:
        print(f"Error fetching from Polly: {e}")
        sys.exit(1)

    config = _load_or_detect_config(args.survey_id, survey_data)
    print(f"Generating dashboard for: {config.title}")
    print()

    print("[2/4] Ingesting and cross-referencing respondent data...")
    respondents = ingest.ingest(survey_data, config)
    print(f"  Found {len(respondents)} complete respondents")

    print("[3/4] Running quantitative analysis...")
    quant_results = quant.analyze(respondents, config)
    print(f"  Distribution: {' / '.join(f'{b.pct}%' for b in quant_results.distribution)}")
    print(f"  Date range: {quant_results.date_range}")

    print("[4/4] Running qualitative synthesis (Claude API)...")
    qual_results = qual.synthesize(respondents, quant_results, config, survey_data)
    print(f"  Generated {len(qual_results.themes.positive_themes)} positive themes, "
          f"{len(qual_results.themes.negative_themes)} negative themes")
    print(f"  Generated {len(qual_results.social_cards.cards)} social cards")

    question_dists = _build_question_distributions(survey_data)

    output = PipelineOutput(
        config=config,
        quant=quant_results,
        qual=qual_results,
        question_distributions=question_dists,
    )

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
