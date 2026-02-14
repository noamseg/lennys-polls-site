"""Slack bot server for Lenny's Polls pipeline.

Runs as a Slack Bolt app in HTTP mode (for Railway deployment).
Slash commands: /surveys, /peek, /generate
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.starlette import SlackRequestHandler
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .core import run_generate, run_list_surveys, run_peek
from .github import push_draft_to_github
from .slack import format_generate_blocks, format_peek_blocks, format_surveys_blocks

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
)

# Only respond in this channel
ALLOWED_CHANNEL = os.environ.get("SLACK_ALLOWED_CHANNEL", "C0AFUHDNR24")

# Track active long-running commands to prevent duplicates
_active: dict[str, threading.Event] = {}
_active_lock = threading.Lock()


def _is_active(key: str) -> bool:
    with _active_lock:
        return key in _active


def _mark_active(key: str) -> bool:
    """Mark a command as active. Returns False if already running."""
    with _active_lock:
        if key in _active:
            return False
        _active[key] = threading.Event()
        return True


def _mark_done(key: str) -> None:
    with _active_lock:
        event = _active.pop(key, None)
    if event:
        event.set()


def _check_channel(command: dict, ack: Any) -> bool:
    """Reject commands from outside the allowed channel."""
    if command.get("channel_id") != ALLOWED_CHANNEL:
        ack(text="This command can only be used in the Lenny's Polls channel.")
        return False
    return True


# ── /surveys ─────────────────────────────────────────────────────────


@app.command("/surveys")
def handle_surveys(ack: Any, respond: Any, command: dict) -> None:
    if not _check_channel(command, ack):
        return
    ack()

    def _run() -> None:
        try:
            items = run_list_surveys()
            blocks = format_surveys_blocks(items)
            respond(blocks=blocks, response_type="in_channel")
        except Exception:
            logger.exception("/surveys failed")
            respond(text="Failed to fetch surveys. Check the logs.", response_type="ephemeral")

    threading.Thread(target=_run, daemon=True).start()


# ── /peek ────────────────────────────────────────────────────────────


@app.command("/peek")
def handle_peek(ack: Any, respond: Any, command: dict) -> None:
    if not _check_channel(command, ack):
        return
    survey_id = command.get("text", "").strip()
    if not survey_id:
        ack(text="Usage: `/peek <survey_id>`")
        return

    ack(f"Running peek for `{survey_id}`... ~30-60 seconds.")

    def _run() -> None:
        try:
            result = run_peek(survey_id)
            blocks = format_peek_blocks(
                title=result.title,
                started=result.started,
                completed=result.completed,
                date_range=result.date_range,
                question_dists=result.question_dists,
                analysis=result.analysis,
                close_label=result.close_label,
            )
            respond(blocks=blocks, response_type="in_channel")
        except Exception as e:
            logger.exception("/peek failed for %s", survey_id)
            respond(text=f"Peek failed: {e}", response_type="ephemeral")

    threading.Thread(target=_run, daemon=True).start()


# ── /generate ────────────────────────────────────────────────────────


@app.command("/generate")
def handle_generate(ack: Any, respond: Any, command: dict) -> None:
    if not _check_channel(command, ack):
        return
    survey_id = command.get("text", "").strip()
    if not survey_id:
        ack(text="Usage: `/generate <survey_id>`")
        return

    key = f"generate:{survey_id}"
    if not _mark_active(key):
        ack(text=f"Generate is already running for `{survey_id}`. Please wait.")
        return

    ack(f"Generating dashboard for `{survey_id}`... ~2-3 minutes.")

    def _run() -> None:
        try:
            result = run_generate(survey_id)
            preview_url = push_draft_to_github(
                result.config.slug,
                result.dashboard_html,
                result.social_html,
            )
            blocks = format_generate_blocks(
                slug=result.config.slug,
                title=result.config.title,
                preview_url=preview_url,
            )
            respond(blocks=blocks, response_type="in_channel")
        except Exception as e:
            logger.exception("/generate failed for %s", survey_id)
            respond(text=f"Generate failed: {e}", response_type="ephemeral")
        finally:
            _mark_done(key)

    threading.Thread(target=_run, daemon=True).start()


# ── Starlette app (HTTP adapter for Railway) ─────────────────────────

handler = SlackRequestHandler(app)


async def slack_events(request: Request) -> Any:
    return await handler.handle(request)


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


starlette_app = Starlette(
    routes=[
        Route("/slack/events", endpoint=slack_events, methods=["POST"]),
        Route("/health", endpoint=health, methods=["GET"]),
    ],
)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "3000"))
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)
