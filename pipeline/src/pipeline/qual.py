"""Qualitative synthesis using Claude API — 3 structured calls."""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from .models import (
    EditorialResults,
    QualResults,
    QuoteItem,
    Respondent,
    SocialCard,
    SocialCardResults,
    SurveyConfig,
    Theme,
    ThemeResults,
    QuantResults,
)

load_dotenv()

MODEL = "claude-sonnet-4-5-20250929"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── Banned phrases for editorial writing ──────────────────────────────

BANNED_PHRASES = """
BANNED PHRASES — never use any of these:
- "It's worth noting that…" / "It's interesting to note…" / "Interestingly…"
- "Let's dive in" / "Let's explore" / "Let's unpack"
- "In today's [landscape/environment/world]"
- "This raises an important question"
- "At the end of the day"
- "Overall" as a sentence opener
- "Navigate" (as metaphor) / "Landscape" / "Harness" / "Leverage" (as verb)
- "Empower" / "Elevate" / "Unlock" / "Foster" / "Streamline"
- "Robust" / "Holistic" / "Comprehensive" / "Dynamic"
- "Pivotal" / "Crucial" / "Transformative" / "Game-changing"
- "Seamless" / "Cutting-edge" / "Groundbreaking"
- "Not just X, but Y" constructions
- Ending with an inspirational call to action
- Tricolon escalation ("X, Y, and most importantly Z")
- Starting paragraphs with "When it comes to…"
- Using "while" to create false balance ("While some love X, others hate Y")
- Overuse of em-dashes for dramatic pause
"""


# ── Call 1: Theme extraction ──────────────────────────────────────────

THEME_TOOL = {
    "name": "extract_themes",
    "description": "Extract love and hate themes from open-text survey responses.",
    "input_schema": {
        "type": "object",
        "properties": {
            "love_themes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Short theme name (2-4 words)"},
                        "count": {"type": "integer", "description": "Number of responses mentioning this theme"},
                        "quotes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string", "description": "Exact quote from the response"},
                                    "title": {"type": "string", "description": "Respondent's job title"},
                                    "company_size": {"type": "string", "description": "Respondent's company size"},
                                },
                                "required": ["text", "title", "company_size"],
                            },
                            "minItems": 3,
                            "maxItems": 3,
                        },
                    },
                    "required": ["name", "count", "quotes"],
                },
                "minItems": 6,
                "maxItems": 6,
            },
            "hate_themes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Short theme name (2-4 words)"},
                        "count": {"type": "integer", "description": "Number of responses mentioning this theme"},
                        "quotes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string", "description": "Exact quote from the response"},
                                    "title": {"type": "string", "description": "Respondent's job title"},
                                    "company_size": {"type": "string", "description": "Respondent's company size"},
                                },
                                "required": ["text", "title", "company_size"],
                            },
                            "minItems": 3,
                            "maxItems": 3,
                        },
                    },
                    "required": ["name", "count", "quotes"],
                },
                "minItems": 6,
                "maxItems": 6,
            },
        },
        "required": ["love_themes", "hate_themes"],
    },
}


def _prepare_responses_by_sentiment(
    respondents: list[Respondent], config: SurveyConfig
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split respondents into love and hate groups with their text + metadata."""
    love, hate = [], []
    for r in respondents:
        if not r.open_text or r.rating is None:
            continue
        entry = {
            "text": r.open_text,
            "title": r.job_title or "Unknown",
            "company_size": r.company_size or "Unknown",
            "rating": r.rating,
        }
        if r.rating >= config.love_threshold:
            love.append(entry)
        elif r.rating <= config.hate_threshold:
            hate.append(entry)
    return love, hate


def extract_themes(respondents: list[Respondent], config: SurveyConfig) -> ThemeResults:
    """Call 1: Extract 6 love + 6 hate themes with quotes."""
    love_responses, hate_responses = _prepare_responses_by_sentiment(respondents, config)

    prompt = f"""You are analyzing open-text survey responses for "{config.title}".

LOVE RESPONSES (rated {config.love_threshold}+ out of 5):
{json.dumps(love_responses, indent=2)}

HATE RESPONSES (rated {config.hate_threshold} or below out of 5):
{json.dumps(hate_responses, indent=2)}

INSTRUCTIONS:
1. Identify exactly 6 themes for LOVE and 6 themes for HATE.
2. For each theme:
   - Give it a short, clear name (2-4 words, e.g. "Team and people", "Bad leadership")
   - Count how many responses mention this theme
   - Select exactly 3 representative quotes
3. QUOTE RULES:
   - Each quote must be THEMATICALLY PURE — it should only speak to the theme it's filed under
   - Do NOT pick quotes that mix multiple themes (e.g. "Great people, aligned leadership, clear vision" is NOT a pure "Team" quote)
   - Use exact text from responses (light cleanup of typos is OK)
   - Mix company sizes and seniority levels across quotes
   - Prefer vivid, specific quotes over generic ones
4. Sort themes by count (highest first).
5. Theme names should be lowercase except proper nouns."""

    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[THEME_TOOL],
        tool_choice={"type": "tool", "name": "extract_themes"},
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract tool use result
    tool_result = None
    for block in response.content:
        if block.type == "tool_use":
            tool_result = block.input
            break

    if not tool_result:
        raise RuntimeError("Claude did not return theme extraction results")

    def _parse_themes(raw: list[dict]) -> list[Theme]:
        themes = []
        max_count = max(t["count"] for t in raw) if raw else 1
        for t in raw:
            themes.append(Theme(
                name=t["name"],
                count=t["count"],
                quotes=[QuoteItem(**q) for q in t["quotes"]],
                bar_width=round(t["count"] / max_count * 100),
            ))
        return themes

    return ThemeResults(
        love_themes=_parse_themes(tool_result["love_themes"]),
        hate_themes=_parse_themes(tool_result["hate_themes"]),
    )


# ── Call 2: Editorial writing ─────────────────────────────────────────

def write_editorial(
    quant: QuantResults,
    themes: ThemeResults,
    config: SurveyConfig,
) -> EditorialResults:
    """Call 2: Write tl;dr section and patterns section."""
    # Build context summary
    dist_text = ", ".join(
        f"Rating {b.rating}: {b.count} ({b.pct}%)" for b in quant.distribution
    )
    love_summary = "\n".join(
        f"  {i+1}. {t.name} ({t.count} mentions)" for i, t in enumerate(themes.love_themes)
    )
    hate_summary = "\n".join(
        f"  {i+1}. {t.name} ({t.count} mentions)" for i, t in enumerate(themes.hate_themes)
    )
    company_size_text = "\n".join(
        f"  {r.label}: {r.mean} (n={r.n})" for r in quant.by_company_size
    )
    tenure_text = "\n".join(
        f"  {r.label}: {r.mean} (n={r.n})" for r in quant.by_tenure
    )
    role_text = "\n".join(
        f"  {r.label}: {r.mean} (n={r.n})" for r in quant.by_role_level
    )

    prompt = f"""You are writing editorial content for a Lenny's Polls dashboard: "{config.title}".

QUANTITATIVE DATA:
- Total responses: {quant.total_responses}
- Distribution: {dist_text}
- By company size:\n{company_size_text}
- By tenure:\n{tenure_text}
- By role level:\n{role_text}

THEMES:
Love themes:\n{love_summary}
Hate themes:\n{hate_summary}

{BANNED_PHRASES}

WRITING RULES:
- Write like a sharp editorial writer sharing findings over coffee. Direct, specific, occasionally witty.
- Lead with the most surprising finding, not the most obvious one.
- Use concrete numbers: "27% are actively unhappy" not "a significant portion expressed dissatisfaction."
- Do NOT lead with an average. Open with the most striking distribution insight.
- Keep the tl;dr to ~250 words.
- Patterns: 3-5 observations, each a short paragraph (2-4 sentences) starting with a bold mini-headline.

OUTPUT FORMAT:
Return valid JSON with two keys:
1. "tldr_html": The tl;dr section as HTML. Structure it like this example:
   <p>13% truly love their jobs. 27% are actively unhappy in their job (rating 1 or 2).</p>
   <p style="margin-top:12px"><strong>What keeps people happy:</strong></p>
   <ul style="margin:8px 0 0 20px;font-size:15px;line-height:1.7;color:var(--text)">
     <li style="margin-bottom:6px"><strong>Theme name.</strong> 1-2 sentences of grounded explanation.</li>
     ...
   </ul>
   <p style="margin-top:14px"><strong>What drives people away:</strong></p>
   <ul style="margin:8px 0 0 20px;font-size:15px;line-height:1.7;color:var(--text)">
     <li style="margin-bottom:6px"><strong>Theme name.</strong> 1-2 sentences of grounded explanation.</li>
     ...
   </ul>
   <p style="margin-top:14px">One more thing: [surprising cross-cut finding with specific numbers].</p>

2. "patterns_html": The patterns section as HTML. Structure:
   <p><strong>Bold observation.</strong> 2-3 sentences with specific numbers from the data.</p>
   <p style="margin-top:10px"><strong>Another observation.</strong> ...</p>
   ...

Return ONLY the JSON object, no other text."""

    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    result = json.loads(text)
    return EditorialResults(
        tldr_html=result["tldr_html"],
        patterns_html=result["patterns_html"],
    )


# ── Call 3: Social card content ───────────────────────────────────────

SOCIAL_CARDS_TOOL = {
    "name": "select_social_cards",
    "description": "Select content for 10-12 social media cards.",
    "input_schema": {
        "type": "object",
        "properties": {
            "cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "card_type": {
                            "type": "string",
                            "enum": ["hero", "keyfinding", "quote_positive", "quote_negative",
                                     "comparison", "theme_love", "theme_hate", "pattern"],
                        },
                        "title": {"type": "string", "description": "Card headline or label"},
                        "data": {
                            "type": "object",
                            "description": "Card-type-specific data (big_number, finding_text, context, quote_text, quote_attr, etc.)",
                        },
                    },
                    "required": ["card_type", "title", "data"],
                },
                "minItems": 10,
                "maxItems": 12,
            },
        },
        "required": ["cards"],
    },
}


def select_social_cards(
    quant: QuantResults,
    themes: ThemeResults,
    editorial: EditorialResults,
    config: SurveyConfig,
) -> SocialCardResults:
    """Call 3: Select the best content for social cards."""
    dist_text = ", ".join(
        f"Rating {b.rating}: {b.pct}%" for b in quant.distribution
    )
    company_size_data = [
        {"label": r.label, "mean": r.mean, "n": r.n} for r in quant.by_company_size
    ]

    prompt = f"""Select content for 10-12 social media cards for the poll "{config.title}".

DATA:
- {quant.total_responses} respondents, {config.audience}
- Distribution: {dist_text}
- Company size breakdown: {json.dumps(company_size_data)}
- Top love themes: {', '.join(f'{t.name} ({t.count})' for t in themes.love_themes[:3])}
- Top hate themes: {', '.join(f'{t.name} ({t.count})' for t in themes.hate_themes[:3])}

Available quotes (love):
{json.dumps([{"theme": t.name, "quotes": [q.model_dump() for q in t.quotes]} for t in themes.love_themes[:3]], indent=2)}

Available quotes (hate):
{json.dumps([{"theme": t.name, "quotes": [q.model_dump() for q in t.quotes]} for t in themes.hate_themes[:3]], indent=2)}

REQUIRED CARD MIX:
1. hero — distribution bar overview (data: headline, subtext)
2. keyfinding x2-3 — big number + insight (data: big_number, finding_text, context)
3. quote_positive x1 — vivid positive quote (data: quote_text, quote_attr, label)
4. quote_negative x1 — vivid negative quote (data: quote_text, quote_attr, label)
5. comparison x1 — company size bars (data: title, rows=[{{label, value, n}}])
6. theme_love x1 — top 3 love drivers (data: themes=[{{rank, name, count, description}}])
7. theme_hate x1 — top 3 hate drivers (data: themes=[{{rank, name, count, description}}])
8. pattern x2 — bold headline + data points (data: headline, points=[{{value, label}}], context, separator="→" or "vs")

RULES:
- Pick the most shareable, surprising insights
- Quotes should be vivid and stand alone without context
- All text should be readable at social media thumbnail size
- Use data from the survey only — do not invent data"""

    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[SOCIAL_CARDS_TOOL],
        tool_choice={"type": "tool", "name": "select_social_cards"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_result = None
    for block in response.content:
        if block.type == "tool_use":
            tool_result = block.input
            break

    if not tool_result:
        raise RuntimeError("Claude did not return social card results")

    return SocialCardResults(
        cards=[SocialCard(**c) for c in tool_result["cards"]]
    )


# ── Main entry point ──────────────────────────────────────────────────

def synthesize(
    respondents: list[Respondent],
    quant: QuantResults,
    config: SurveyConfig,
) -> QualResults:
    """Run all 3 qualitative analysis calls."""
    print("  [qual] Extracting themes...")
    themes = extract_themes(respondents, config)

    print("  [qual] Writing editorial content...")
    editorial = write_editorial(quant, themes, config)

    print("  [qual] Selecting social card content...")
    social = select_social_cards(quant, themes, editorial, config)

    return QualResults(
        themes=themes,
        editorial=editorial,
        social_cards=social,
    )
