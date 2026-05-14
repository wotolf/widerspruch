"""Shared JSON parsing utilities for LLM responses."""
from __future__ import annotations

import json
import re


def parse_llm_json(text: str, error_class: type[Exception]) -> dict:
    """
    Parse a JSON object from LLM output, tolerating Markdown code fences.

    Tries in order:
    1. Direct parse (normal case when the prompt says "JSON only")
    2. Strip Markdown fences, parse again
    3. Extract first {...} block via regex

    Raises error_class if no valid JSON is found.
    """
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    flags = re.MULTILINE | re.IGNORECASE
    stripped = re.sub(r"^```(?:json)?\s*", "", text, flags=flags)
    stripped = re.sub(r"\s*```\s*$", "", stripped, flags=flags).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise error_class(
        f"Kein valides JSON in LLM-Response (erste 300 Zeichen): {text[:300]!r}"
    )
