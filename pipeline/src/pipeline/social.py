"""Render social cards HTML page from Jinja2 template."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .models import PipelineOutput
from .render import _load_logo_data_uri, _build_subtitle

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def _load_social_css() -> str:
    """Load the social cards CSS file."""
    css_path = TEMPLATES_DIR / "css" / "social.css"
    return css_path.read_text()


def render_social(output: PipelineOutput) -> str:
    """Render the social cards HTML page."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
    )
    template = env.get_template("social.html.j2")

    social_css = _load_social_css()
    subtitle = _build_subtitle(output.config, output.quant, output.qual.themes)

    logo_data_uri = _load_logo_data_uri()
    scale_max = max(output.config.scale_labels.keys())

    return template.render(
        config=output.config,
        quant=output.quant,
        cards=output.qual.social_cards.cards,
        social_css=social_css,
        subtitle=subtitle,
        logo_data_uri=logo_data_uri,
        scale_max=scale_max,
    )


def write_social(output: PipelineOutput, drafts_dir: Path) -> Path:
    """Render and write social cards page to drafts directory."""
    html = render_social(output)
    out_path = drafts_dir / f"{output.config.slug}-social.html"
    out_path.write_text(html)
    return out_path
