"""Ingest Polly API survey data into cross-referenced Respondent records.

Polly's surveys.info returns a survey object with a `questions` array.
Each question has a `results` array of individual responses keyed by `user_id`.
We cross-reference across questions to build complete Respondent records.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .models import (
    Respondent,
    RoleLevel,
    SurveyConfig,
)


# ── Role categorization ──────────────────────────────────────────────

# Order matters: check founder/C-suite first, then VP/Director, then Group PM, then IC.
_FOUNDER_CSUITE_PATTERNS = [
    r"\bfounder\b", r"\bco-founder\b", r"\bcofounder\b",
    r"\bceo\b", r"\bcto\b", r"\bcoo\b", r"\bcpo\b", r"\bcso\b", r"\bcmo\b", r"\bcfo\b", r"\bcro\b",
    r"\bchief\b", r"\bsvp\b", r"\bowner\b",
]

_VP_DIRECTOR_HEAD_PATTERNS = [
    r"\bvp\b", r"\bvice president\b",
    r"\bdirector\b",
    r"\bhead of\b", r"\bhead,\b",
]

_GROUP_PM_PATTERNS = [
    r"\bgroup pm\b", r"\bgroup product\b",
    r"\bmanager of product\b",
]

_SENIOR_MANAGER_PRODUCT = r"\bsenior manager\b.*\bproduct\b"


def categorize_role(title: str | None) -> RoleLevel:
    """Categorize a free-text job title into a role level."""
    if not title:
        return RoleLevel.IC

    t = title.lower().strip()
    t_check = t.replace("product owner", "product_owner_excluded")

    for pat in _FOUNDER_CSUITE_PATTERNS:
        if re.search(pat, t_check):
            return RoleLevel.FOUNDER_CSUITE

    for pat in _VP_DIRECTOR_HEAD_PATTERNS:
        if re.search(pat, t_check):
            return RoleLevel.VP_DIRECTOR_HEAD

    for pat in _GROUP_PM_PATTERNS:
        if re.search(pat, t_check):
            return RoleLevel.GROUP_PM_MANAGER

    if re.search(_SENIOR_MANAGER_PRODUCT, t_check):
        return RoleLevel.GROUP_PM_MANAGER

    return RoleLevel.IC


# ── Company size normalization ────────────────────────────────────────

_COMPANY_SIZE_MAP = {
    "just me": "Just me",
    "2-10": "2–10",
    "11-50": "11–50",
    "51-250": "51–250",
    "251-1000": "251–1,000",
    "1001-5000": "1,001–5,000",
    "5001+": "5,001+",
}

_TENURE_MAP = {
    "less than a year": "Less than 1 year",
    "1-2 years": "1–2 years",
    "3-5 years": "3–5 years",
    "6-10 years": "6–10 years",
    "11+ years": "11+ years",
}


def _normalize_company_size(raw: str) -> str:
    return _COMPANY_SIZE_MAP.get(raw.lower().strip(), raw)


def _normalize_tenure(raw: str) -> str:
    return _TENURE_MAP.get(raw.lower().strip(), raw)


# ── Rating extraction ─────────────────────────────────────────────────

def _extract_rating(text: str) -> int | None:
    """Extract numeric rating from choice text like '4 - Pretty good'."""
    m = re.match(r"^(\d+)\s*[-–—]", text.strip())
    if m:
        return int(m.group(1))
    if text.strip().isdigit():
        return int(text.strip())
    return None


# ── Question identification ───────────────────────────────────────────

def _identify_questions(questions: list[dict]) -> dict[str, str]:
    """
    Identify which question serves which role.
    Returns dict mapping role -> question_id.
    Roles: 'rating', 'open_text', 'title', 'company_size', 'tenure'
    """
    mapping: dict[str, str] = {}

    for q in questions:
        q_id = q["id"]
        q_text = q.get("text", "").lower()
        q_type = q.get("type", "")

        if "how do you feel" in q_text or ("hate it" in q_text and "love it" in q_text):
            mapping["rating"] = q_id
        elif "what do you love" in q_text or "what do you hate" in q_text or "love or hate" in q_text:
            mapping["open_text"] = q_id
        elif "title" in q_text or "current title" in q_text or "your role" in q_text:
            if q_type == "open_ended":
                mapping["title"] = q_id
        elif "size" in q_text and "company" in q_text:
            mapping["company_size"] = q_id
        elif "how long" in q_text or "tenure" in q_text:
            mapping["tenure"] = q_id

    return mapping


# ── Main ingestion ───────────────────────────────────────────────────

def ingest(survey_data: dict[str, Any], config: SurveyConfig) -> list[Respondent]:
    """
    Cross-reference Polly survey results by user_id to build Respondent records.

    Only includes respondents who answered the last question (tenure),
    matching the dashboard's definition of "complete response."
    """
    questions = survey_data.get("questions", [])
    q_map = _identify_questions(questions)

    # Build lookup: question_id -> {user_id -> result}
    q_results: dict[str, dict[str, dict]] = {}
    for q in questions:
        by_user: dict[str, dict] = {}
        for r in q.get("results", []):
            if r.get("deleted"):
                continue
            by_user[r["user_id"]] = r
        q_results[q["id"]] = by_user

    # The cohort: users who answered the tenure question (= completed the survey)
    tenure_q_id = q_map.get("tenure")
    if tenure_q_id and tenure_q_id in q_results:
        cohort_user_ids = set(q_results[tenure_q_id].keys())
    else:
        # Fallback: use all users who answered the rating question
        rating_q_id = q_map.get("rating", "")
        cohort_user_ids = set(q_results.get(rating_q_id, {}).keys())

    respondents: list[Respondent] = []

    for uid in cohort_user_ids:
        r = Respondent(user_id=uid)

        # Rating
        rating_q = q_map.get("rating")
        if rating_q and uid in q_results.get(rating_q, {}):
            result = q_results[rating_q][uid]
            r.rating = _extract_rating(result["text"])
            # Timestamp from the first response
            ts = result.get("created_at")
            if ts:
                try:
                    r.voted_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        # Open text
        open_q = q_map.get("open_text")
        if open_q and uid in q_results.get(open_q, {}):
            text = q_results[open_q][uid]["text"].strip()
            if text:
                r.open_text = text

        # Job title
        title_q = q_map.get("title")
        if title_q and uid in q_results.get(title_q, {}):
            title = q_results[title_q][uid]["text"].strip()
            if title:
                r.job_title = title
                r.role_level = categorize_role(title)

        if r.role_level is None:
            r.role_level = RoleLevel.IC

        # Company size
        size_q = q_map.get("company_size")
        if size_q and uid in q_results.get(size_q, {}):
            r.company_size = _normalize_company_size(q_results[size_q][uid]["text"])

        # Tenure
        if tenure_q_id and uid in q_results.get(tenure_q_id, {}):
            r.tenure = _normalize_tenure(q_results[tenure_q_id][uid]["text"])

        respondents.append(r)

    return respondents
