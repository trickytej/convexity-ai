"""Thin Anthropic client wrapper used by the correction and speaker-id passes."""

from __future__ import annotations

import json
import re

import anthropic

from ..config import Settings, get_settings


class LLMError(Exception):
    pass


def get_client(settings: Settings | None = None) -> anthropic.Anthropic:
    settings = settings or get_settings()
    if not settings.anthropic_api_key:
        raise LLMError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def complete(
    client: anthropic.Anthropic,
    *,
    system: str,
    user: str,
    model: str,
    max_tokens: int = 4096,
    temperature: float | None = 0.0,
    thinking: bool = False,
    betas: list[str] | None = None,
    stream: bool = False,
) -> str:
    """One-shot completion.

    Set ``thinking=True`` for adaptive ("max") reasoning models like Opus 4.8 (which
    also reject ``temperature``); pass ``betas`` (e.g. ["context-1m-2025-08-07"]) to
    enable beta features such as the 1M context window. Use ``stream=True`` for large
    ``max_tokens`` requests (the SDK requires streaming for ones that may exceed 10
    minutes).
    """
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if thinking:
        kwargs["thinking"] = {"type": "adaptive"}  # adaptive thinking models reject temperature
    elif temperature is not None:
        kwargs["temperature"] = temperature
    if betas:
        kwargs["extra_headers"] = {"anthropic-beta": ",".join(betas)}

    if stream:
        with client.messages.stream(**kwargs) as s:
            message = s.get_final_message()
    else:
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
    # Fall back to the first balanced array/object in the text.
    for opener, closer in (("[", "]"), ("{", "}")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError("could not parse JSON from model response")
