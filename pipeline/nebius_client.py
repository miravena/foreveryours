"""Thin wrapper around the Nebius Token Factory OpenAI-compatible endpoint.

Nebius exposes an OpenAI-compatible Chat Completions API, so the `openai`
SDK works unmodified with base_url pointed at Nebius. No key = NebiusNotConfigured,
raised loudly rather than silently mocked -- AC2 requires a real model call.
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
            "NEBIUS_API_KEY is not set. See app/.env.example and "
            "kaggle-compete/competitions/nebius-foreveryours/STATUS.md "
            "(open decision: wq #9033) -- this is a founder signup, not a bug."
        )
    base_url = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1")
    return OpenAI(api_key=api_key, base_url=base_url)
