"""Thin Anthropic client wrapper (shared shape with research-digest's)."""

from __future__ import annotations

import json
import re

import anthropic

from moves.config import Settings, get_settings


class LLMError(Exception):
    pass


def get_client(settings: Settings | None = None) -> anthropic.Anthropic:
    settings = settings or get_settings()
    if not settings.anthropic_api_key:
        raise LLMError("MOVES_ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def complete(
    client: anthropic.Anthropic,
    *,
    system: str,
    user: str,
    model: str,
    max_tokens: int = 2048,
    temperature: float | None = 0.0,
    thinking: bool = False,
) -> str:
    """One-shot completion. Adaptive-thinking models (Opus 4.8) reject temperature."""
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if thinking:
        kwargs["thinking"] = {"type": "adaptive"}
    elif temperature is not None:
        kwargs["temperature"] = temperature

    message = client.messages.create(**kwargs)
    return "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def extract_json(text: str):
    """Best-effort extraction of a JSON value from an LLM response."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError("could not parse JSON from model response")
