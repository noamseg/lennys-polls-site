"""Polly API client for fetching survey data.

Polly uses POST endpoints with dot-notation paths (e.g. surveys.info)
and authenticates via X-API-TOKEN header.
Docs: https://docs.polly.ai/api/
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.polly.ai/v1"


def _get_headers() -> dict[str, str]:
    token = os.environ.get("POLLY_API_TOKEN")
    if not token:
        raise RuntimeError("POLLY_API_TOKEN not set in environment")
    return {
        "X-API-TOKEN": token,
        "Content-Type": "application/json",
    }


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, headers=_get_headers(), timeout=30)


def get_survey_info(survey_id: str) -> dict[str, Any]:
    """Fetch survey metadata, questions, and all individual results via surveys.info."""
    with _client() as client:
        resp = client.post("/surveys.info", json={"id": survey_id})
        resp.raise_for_status()
        return resp.json()


def list_surveys() -> list[dict[str, Any]]:
    """List all available surveys."""
    with _client() as client:
        resp = client.post("/surveys.list", json={})
        resp.raise_for_status()
        return resp.json()
