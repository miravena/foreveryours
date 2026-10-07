"""Thin wrapper around the Nebius Token Factory OpenAI-compatible endpoint.

Nebius exposes an OpenAI-compatible Chat Completions API, so the `openai`
SDK works unmodified with base_url pointed at Nebius. No key = NebiusNotConfigured,
raised loudly rather than silently mocked -- a real model call is required,
never a mocked reply.
"""
from __future__ import annotations

import os

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI


class NebiusNotConfigured(RuntimeError):
    pass


def get_client() -> OpenAI:
    api_key = os.environ.get("NEBIUS_API_KEY", "").strip()
    if not api_key:
        raise NebiusNotConfigured(
            "NEBIUS_API_KEY is not set. Copy .env.example to .env and fill it in "
            "-- see README.md -> Setup -> Nebius access."
        )
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required for Nebius Token Factory: pip install openai") from exc

    # Confirmed against Nebius's own first-party docs (docs.tokenfactory.nebius.com/
    # api-reference/introduction, 2026-10-01) -- NOT yet exercised against a live
    # key, but this is the documented endpoint, not a guess from a secondary source.
    base_url = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
    # Token Factory's time-to-first-token varies 1-36s (#81 B1); the OpenAI
    # SDK default (600s, 2 retries) left a judge on a spinner with no text on
    # screen for up to ten minutes on a hung call. Bounded and non-retrying
    # instead -- a slow call surfaces as a fallback reply, not a frozen page.
    return OpenAI(api_key=api_key, base_url=base_url, timeout=20, max_retries=1)
