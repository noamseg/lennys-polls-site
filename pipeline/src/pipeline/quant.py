"""Deterministic quantitative analysis using pandas."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from .models import (
    CrossTabRow,
    ProfileRow,
    QuantResults,
    RatingBucket,
    Respondent,
    SurveyConfig,
)


def _format_date_range(respondents: list[Respondent]) -> str:
    """Extract date range from respondent timestamps."""
    timestamps = [r.voted_at for r in respondents if r.voted_at]
    if not timestamps:
        return "Date range unavailable"

    earliest = min(timestamps)
    latest = max(timestamps)

    def fmt(dt: datetime) -> str:
        return dt.strftime("%b %-d, %Y") if dt.year != earliest.year or earliest.year != latest.year else dt.strftime("%b %-d")

    if earliest.date() == latest.date():
        return earliest.strftime("%b %-d, %Y")

    # Same year: "Jan 28 – Feb 4, 2026"
    if earliest.year == latest.year:
        return f"{earliest.strftime('%b %-d')} – {latest.strftime('%b %-d')}, {latest.year}"

    return f"{earliest.strftime('%b %-d, %Y')} – {latest.strftime('%b %-d, %Y')}"


def analyze(respondents: list[Respondent], config: SurveyConfig) -> QuantResults:
    """Run all quantitative analysis on respondent data."""
    # Serialize with enum values as display strings
    records = []
    for r in respondents:
        d = r.model_dump()
        if r.role_level:
            d["role_level"] = r.role_level.value
        records.append(d)
    df = pd.DataFrame(records)
    total = len(df)

    # ── Rating distribution ───────────────────────────────────────
    rated = df[df["rating"].notna()].copy()
    rated["rating"] = rated["rating"].astype(int)

    distribution: list[RatingBucket] = []
    for rating_val in sorted(config.scale_labels.keys()):
        count = int((rated["rating"] == rating_val).sum())
        pct = round(count / len(rated) * 100, 1) if len(rated) > 0 else 0.0
        distribution.append(RatingBucket(
            rating=rating_val,
            count=count,
            pct=pct,
            flex=pct,  # flex value = percentage for stacked bar
        ))

    # ── Cross-tabs: mean rating by demographic ────────────────────

    scale_max = max(config.scale_labels.keys())

    def cross_tab(col: str) -> list[CrossTabRow]:
        valid = rated[rated[col].notna() & (rated[col] != "")].copy()
        if valid.empty:
            return []
        grouped = valid.groupby(col)["rating"].agg(["mean", "count"])
        grouped = grouped.sort_values("mean", ascending=False)
        rows = []
        for label, row in grouped.iterrows():
            mean_val = round(float(row["mean"]), 2)
            rows.append(CrossTabRow(
                label=str(label),
                mean=mean_val,
                n=int(row["count"]),
                bar_width=round(mean_val / scale_max * 100, 1),
            ))
        return rows

    by_company_size = cross_tab("company_size")
    by_tenure = cross_tab("tenure")
    by_role_level = cross_tab("role_level")

    # ── Respondent profiles: distribution counts ──────────────────

    def profile(col: str) -> list[ProfileRow]:
        valid = df[df[col].notna() & (df[col] != "")].copy()
        if valid.empty:
            return []
        counts = valid[col].value_counts()
        max_count = int(counts.max()) if len(counts) > 0 else 1
        rows = []
        for label, count in counts.items():
            count_int = int(count)
            rows.append(ProfileRow(
                label=str(label),
                count=count_int,
                pct=round(count_int / total * 100, 1),
                bar_width=round(count_int / max_count * 100, 1),
            ))
        return rows

    profile_company_size = profile("company_size")
    profile_tenure = profile("tenure")

    return QuantResults(
        total_responses=total,
        date_range=_format_date_range(respondents),
        distribution=distribution,
        by_company_size=by_company_size,
        by_tenure=by_tenure,
        by_role_level=by_role_level,
        profile_company_size=profile_company_size,
        profile_tenure=profile_tenure,
    )
