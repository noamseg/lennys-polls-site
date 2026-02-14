"""Pydantic data models for the Lenny's Polls pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Survey configuration ──────────────────────────────────────────────

class SurveyConfig(BaseModel):
    id: str
    title: str
    slug: str
    audience: str
    subtitle_template: str
    scale_description: str
    scale_labels: dict[int, str]
    positive_threshold: int = 4
    negative_threshold: int = 2
    survey_tool: str = "Polly survey"


class SurveysFile(BaseModel):
    surveys: list[SurveyConfig]


# ── Question types ────────────────────────────────────────────────────

class QuestionType(str, Enum):
    RATING = "rating"
    OPEN_ENDED = "open_ended"
    MULTIPLE_CHOICE = "multiple_choice"


class Question(BaseModel):
    id: str
    text: str
    question_type: QuestionType
    options: list[str] = Field(default_factory=list)


# ── Role levels ───────────────────────────────────────────────────────

class RoleLevel(str, Enum):
    FOUNDER_CSUITE = "Founder / C-suite"
    VP_DIRECTOR_HEAD = "VP / Director / Head"
    GROUP_PM_MANAGER = "Group PM / Manager"
    IC = "IC"


# ── Respondent record ────────────────────────────────────────────────

class Vote(BaseModel):
    question_id: str
    value: str | int | float


class Respondent(BaseModel):
    user_id: str
    votes: dict[str, Any] = Field(default_factory=dict)  # question_id -> value
    rating: int | None = None
    open_text: str | None = None
    company_size: str | None = None
    tenure: str | None = None
    job_title: str | None = None
    role_level: RoleLevel | None = None
    voted_at: datetime | None = None


# ── Quantitative analysis results ────────────────────────────────────

class RatingBucket(BaseModel):
    rating: int
    count: int
    pct: float
    flex: float  # for stacked bar width


class CrossTabRow(BaseModel):
    label: str
    mean: float
    n: int
    bar_width: float = 0.0  # percentage for bar chart (mean / 5 * 100)


class ProfileRow(BaseModel):
    label: str
    count: int
    pct: float
    bar_width: float = 0.0  # relative to largest category (largest = 100%)


class QuantResults(BaseModel):
    total_responses: int
    date_range: str  # "Jan 28 – Feb 4, 2026"
    distribution: list[RatingBucket]
    by_company_size: list[CrossTabRow]
    by_tenure: list[CrossTabRow]
    by_role_level: list[CrossTabRow]
    profile_company_size: list[ProfileRow]
    profile_tenure: list[ProfileRow]


# ── Qualitative analysis results ─────────────────────────────────────

class QuoteItem(BaseModel):
    text: str
    title: str  # job title
    company_size: str


class Theme(BaseModel):
    name: str
    count: int
    quotes: list[QuoteItem]
    bar_width: float = 0.0  # relative to largest theme (largest = 100%)


class ThemeResults(BaseModel):
    positive_themes: list[Theme]
    negative_themes: list[Theme]
    positive_label: str = "What people love"
    negative_label: str = "What people hate"


class EditorialResults(BaseModel):
    tldr_html: str  # rendered HTML for the tl;dr section
    patterns_html: str  # rendered HTML for patterns section


class SocialCard(BaseModel):
    card_type: str  # hero, keyfinding, quote_positive, quote_negative, comparison, theme_positive, theme_negative, pattern
    title: str
    data: dict[str, Any] = Field(default_factory=dict)


class SocialCardResults(BaseModel):
    cards: list[SocialCard]


class QualResults(BaseModel):
    themes: ThemeResults
    editorial: EditorialResults
    social_cards: SocialCardResults


# ── Full pipeline output ──────────────────────────────────────────────

class PipelineOutput(BaseModel):
    config: SurveyConfig
    quant: QuantResults
    qual: QualResults
    question_distributions: list[dict[str, Any]] = Field(default_factory=list)
