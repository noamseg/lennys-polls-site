"""Render dashboard HTML from Jinja2 templates."""

from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .models import PipelineOutput, SurveyConfig, QuantResults, QualResults, ThemeResults

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_PIPELINE_DIR = Path(__file__).resolve().parent.parent.parent
# Logo lives at site repo root locally, but inside pipeline/ in Docker
LOGO_PATH = _PIPELINE_DIR.parent / "lennylogo.svg"
if not LOGO_PATH.exists():
    LOGO_PATH = _PIPELINE_DIR / "lennylogo.svg"


def _load_css() -> str:
    """Load the dashboard CSS file."""
    css_path = TEMPLATES_DIR / "css" / "dashboard.css"
    return css_path.read_text()


def _load_logo_data_uri() -> str:
    """Load the logo SVG and return as a base64 data URI."""
    svg_bytes = LOGO_PATH.read_bytes()
    b64 = base64.b64encode(svg_bytes).decode()
    return f"data:image/svg+xml;base64,{b64}"


_AUTO_DETECT_SUBTITLE = "{n} {audience} shared their perspectives."


def _build_subtitle(config: SurveyConfig, quant: QuantResults, themes: ThemeResults | None = None) -> str:
    """Build the subtitle — prefer Claude-generated subtitle for auto-detected surveys."""
    if themes and themes.subtitle and config.subtitle_template == _AUTO_DETECT_SUBTITLE:
        return themes.subtitle
    return config.subtitle_template.format(
        n=quant.total_responses,
        audience=config.audience,
    )


def render_dashboard(output: PipelineOutput) -> str:
    """Render the full dashboard HTML."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
    )
    template = env.get_template("dashboard.html.j2")

    css = _load_css()
    subtitle = _build_subtitle(output.config, output.quant, output.qual.themes)
    logo_data_uri = _load_logo_data_uri()
    scale_max = max(output.config.scale_labels.keys())

    return template.render(
        config=output.config,
        quant=output.quant,
        qual=output.qual,
        css=css,
        subtitle=subtitle,
        logo_data_uri=logo_data_uri,
        scale_max=scale_max,
        question_distributions=output.question_distributions,
    )


def write_dashboard(output: PipelineOutput, drafts_dir: Path) -> Path:
    """Render and write dashboard to drafts directory."""
    html = render_dashboard(output)
    out_path = drafts_dir / f"{output.config.slug}.html"
    out_path.write_text(html)
    return out_path
