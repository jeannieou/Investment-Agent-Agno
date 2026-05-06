"""Shared helpers for external research tools."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from app.schemas import EvidenceSource


DEFAULT_HEADERS = {
    "User-Agent": "investment-research-agent/0.1 contact@example.com",
}


def clean_text(raw: str, max_chars: int) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def evidence_to_dicts(sources: list[EvidenceSource]) -> list[dict[str, Any]]:
    return [source.model_dump() for source in sources]


def not_found_source(title: str, url: str = "", snippet: str = "Not found") -> EvidenceSource:
    return EvidenceSource(title=title, url=url or "Not found", publisher=None, snippet=snippet)


def retry_call(call: Callable[[], Any], attempts: int = 3, delay_seconds: float = 0.0) -> Any:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return call()
        except Exception as exc:
            last_error = exc
            if delay_seconds and attempt < attempts - 1:
                time.sleep(delay_seconds)
    if last_error:
        raise last_error
    raise RuntimeError("retry_call received no attempts")
