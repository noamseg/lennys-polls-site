"""Core business logic for Lenny's Polls pipeline.

Extracted from cli.py so both CLI and Slack bot share the same functions.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from .ingest import _is_rating_question, _extract_rating
from .models import PipelineOutput, SurveyConfig, SurveysFile

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "surveys.yaml"

RATING_EMOJIS = {1: "🟥", 2: "🟧", 3: "🟨", 4: "🟩", 5: "💚"}

ProgressFn = Callable[[str], None]


def _noop_progress(msg: str) -> None:
    pass


# ── Result dataclasses ───────────────────────────────────────────────


@dataclass
class SurveyListItem:
    id: str
    title: str
    active: bool
    configured: bool


@dataclass
class PeekResult:
    title: str
    started: int
    completed: int
    date_range: str
    close_label: str
    question_dists: list[dict[str, Any]]
    analysis: dict[str, Any] | None
    config: SurveyConfig


@dataclass
class GenerateResult:
    config: SurveyConfig
    output: PipelineOutput
    dashboard_html: str
    social_html: str


# ── Config helpers ───────────────────────────────────────────────────


def load_config(survey_id: str) -> SurveyConfig | None:
    """Load survey config from surveys.yaml by ID. Returns None if not found."""
    try:
        with open(CONFIG_PATH) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return None
    surveys_file = SurveysFile(**data)
    for survey in surveys_file.surveys:
        if survey.id == survey_id:
            return survey
    return None


def find_config_by_slug(slug: str) -> SurveyConfig | None:
    """Find survey config by slug."""
    try:
        with open(CONFIG_PATH) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return None
    surveys_file = SurveysFile(**data)
    for survey in surveys_file.surveys:
        if survey.slug == slug:
            return survey
    return None


def detect_config(survey_id: str, survey_data: dict) -> SurveyConfig:
    """Auto-detect a SurveyConfig from raw Polly API data."""
    title = (
        survey_data.get("title")
        or survey_data.get("name")
        or survey_data.get("question", "Survey")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

    scale_labels: dict[int, str] = {}
    for q in survey_data.get("questions", []):
        if q.get("type") != "multiple_choice":
            continue
        responses = [r for r in q.get("results", []) if not r.get("deleted")]
        if _is_rating_question(responses):
            title = q.get("text", title)
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            seen: set[int] = set()
            for r in responses:
                rating = _extract_rating(r.get("text", ""))
                if rating is not None and rating not in seen:
                    seen.add(rating)
                    m = re.match(r"^\d+\s+[-–—]\s+(.+)", r["text"].strip())
                    if m:
                        scale_labels[rating] = m.group(1).strip()
            break

    if not scale_labels:
        scale_labels = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}

    scale_min = min(scale_labels.keys())
    scale_max = max(scale_labels.keys())
    scale_description = f"{scale_min} = {scale_labels[scale_min].lower()}, {scale_max} = {scale_labels[scale_max].lower()}"

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


def load_or_detect_config(
    survey_id: str,
    survey_data: dict,
    on_progress: ProgressFn | None = None,
) -> SurveyConfig:
    """Try loading config from surveys.yaml, fall back to auto-detection."""
    progress = on_progress or _noop_progress

    configured = load_config(survey_id)
    if configured:
        progress(f"Using configured survey: {configured.title}")
        return configured

    config = detect_config(survey_id, survey_data)
    progress(f"Auto-detected config for: {config.title}")
    progress(f"  Slug: {config.slug}")
    progress(f"  Scale: {config.scale_description}")
    progress(
        f"  Positive threshold: >= {config.positive_threshold}, "
        f"Negative threshold: <= {config.negative_threshold}"
    )
    return config


# ── Generic survey data helpers ──────────────────────────────────────


def short_choice(text: str) -> str:
    """Extract the short label from a choice like 'Option -- longer explanation'."""
    for sep in [" — ", " – "]:
        if sep in text:
            before = text.split(sep, 1)[0].strip()
            if before.isdigit():
                return text.split(sep, 1)[1].strip()
            return before
    m = re.match(r"^(\d+)\s+-\s+(.+)", text)
    if m and not m.group(2).strip().replace("+", "").isdigit():
        return m.group(2).strip()
    return text.strip()


def _ordinal_sort_key(choice_text: str) -> int | None:
    m = re.match(r"^(\d+)", choice_text.strip())
    return int(m.group(1)) if m else None


def _is_ordinal_choices(choice_texts: list[str]) -> bool:
    if len(choice_texts) < 3:
        return False
    numeric = sum(1 for t in choice_texts if _ordinal_sort_key(t) is not None)
    return numeric >= len(choice_texts) * 0.6


def build_question_distributions(survey_data: dict) -> list[dict[str, Any]]:
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
            label = short_choice(choice_text)
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


def compute_survey_meta(survey_data: dict) -> tuple[int, int, str]:
    """Compute respondent counts and date range from raw survey data.

    Returns (total_started, total_completed, date_range).
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
        return (
            total_started,
            total_completed,
            f"{earliest.strftime('%b %-d')} – {latest.strftime('%b %-d')}, {latest.year}",
        )
    return (
        total_started,
        total_completed,
        f"{earliest.strftime('%b %-d, %Y')} – {latest.strftime('%b %-d, %Y')}",
    )


# ── Core pipeline functions ──────────────────────────────────────────


def run_list_surveys() -> list[SurveyListItem]:
    """List all surveys from the Polly API with config status."""
    from . import polly

    configured_ids: set[str] = set()
    try:
        with open(CONFIG_PATH) as f:
            data = yaml.safe_load(f)
        surveys_file = SurveysFile(**data)
        configured_ids = {s.id for s in surveys_file.surveys}
    except FileNotFoundError:
        pass

    api_surveys = polly.list_surveys()
    items = []
    for survey in api_surveys:
        sid = survey.get("id", "?")
        title = (
            survey.get("title")
            or survey.get("name")
            or survey.get("question", "Untitled")
        )
        active = survey.get("active", False)
        items.append(SurveyListItem(
            id=sid,
            title=title,
            active=active,
            configured=sid in configured_ids,
        ))
    return items


def run_peek(
    survey_id: str,
    on_progress: ProgressFn | None = None,
) -> PeekResult:
    """Fetch survey data, compute distributions, run Claude analysis."""
    from . import polly
    from .qual import peek_analyze

    progress = on_progress or _noop_progress

    # Step 1: Fetch
    progress("[1/3] Fetching data from Polly API...")
    survey_data = polly.get_survey_info(survey_id)

    title = (
        survey_data.get("title")
        or survey_data.get("name")
        or survey_data.get("question", "Survey")
    )
    started, completed, date_range = compute_survey_meta(survey_data)
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
    progress(f"Survey: {title} ({started} responded, {completed} completed{close_label})")

    # Step 2: Build distributions
    progress("[2/3] Computing question distributions...")
    question_dists = build_question_distributions(survey_data)
    open_count = sum(
        len([r for r in q.get("results", []) if not r.get("deleted")])
        for q in survey_data.get("questions", [])
        if q.get("type") == "open_ended"
        and not any(kw in q.get("text", "").lower() for kw in ("title", "current role"))
    )
    progress(f"  {len(question_dists)} multiple-choice questions, {open_count} open-ended responses")

    config = detect_config(survey_id, survey_data)

    # Step 3: Claude analysis
    analysis = None
    if open_count > 0:
        progress("[3/3] Analyzing responses (Claude API)...")
        analysis = peek_analyze(title, survey_data, question_dists, config)
        progress("  Done")
    else:
        progress("[3/3] No open-ended responses to analyze — skipping Claude API")

    return PeekResult(
        title=title,
        started=started,
        completed=completed,
        date_range=date_range,
        close_label=close_label,
        question_dists=question_dists,
        analysis=analysis,
        config=config,
    )


def run_generate(
    survey_id: str,
    on_progress: ProgressFn | None = None,
) -> GenerateResult:
    """Full pipeline: ingest -> quant -> qual -> render. Returns HTML strings."""
    from . import polly, ingest, quant, qual, render, social

    progress = on_progress or _noop_progress

    progress("[1/4] Fetching data from Polly API...")
    survey_data = polly.get_survey_info(survey_id)

    config = load_or_detect_config(survey_id, survey_data, on_progress)
    progress(f"Generating dashboard for: {config.title}")

    progress("[2/4] Ingesting and cross-referencing respondent data...")
    respondents = ingest.ingest(survey_data, config)
    progress(f"  Found {len(respondents)} complete respondents")

    progress("[3/4] Running quantitative analysis...")
    quant_results = quant.analyze(respondents, config)
    progress(f"  Distribution: {' / '.join(f'{b.pct}%' for b in quant_results.distribution)}")
    progress(f"  Date range: {quant_results.date_range}")

    progress("[4/4] Running qualitative synthesis (Claude API)...")
    qual_results = qual.synthesize(respondents, quant_results, config, survey_data)
    progress(
        f"  Generated {len(qual_results.themes.positive_themes)} positive themes, "
        f"{len(qual_results.themes.negative_themes)} negative themes"
    )
    progress(f"  Generated {len(qual_results.social_cards.cards)} social cards")

    question_dists = build_question_distributions(survey_data)

    output = PipelineOutput(
        config=config,
        quant=quant_results,
        qual=qual_results,
        question_distributions=question_dists,
    )

    progress("Rendering templates...")
    dashboard_html = render.render_dashboard(output)
    social_html = social.render_social(output)

    return GenerateResult(
        config=config,
        output=output,
        dashboard_html=dashboard_html,
        social_html=social_html,
    )
