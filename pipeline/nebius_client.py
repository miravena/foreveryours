"""Thin wrapper around the Nebius Token Factory OpenAI-compatible endpoint.

Nebius exposes an OpenAI-compatible Chat Completions API, so the `openai`
SDK works unmodified with base_url pointed at Nebius. No key = NebiusNotConfigured,
raised loudly rather than silently mocked -- a real model call is required,
never a mocked reply.
"""
from __future__ import annotations

import os

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
    # NEBIUS_BASE_URL default here should be re-verified against current Nebius
    # docs once a real key is in hand -- .ai and .com variants both exist and
    # both 401 without a key, so this hasn't been confirmed live yet.
    base_url = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1")
    return OpenAI(api_key=api_key, base_url=base_url)
