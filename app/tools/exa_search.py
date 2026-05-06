"""Exa search evidence tool."""

from __future__ import annotations

import os

import requests
from agno.tools import tool

from app.schemas import EvidenceSource
from app.tools._utils import clean_text, evidence_to_dicts, retry_call


EXA_SEARCH_URL = "https://api.exa.ai/search"


def search_exa(
    query: str,
    max_results: int = 5,
    max_characters: int = 1000,
    timeout: float = 20.0,
    api_key: str | None = None,
) -> list[EvidenceSource]:
    key = api_key or os.getenv("EXA_API_KEY")
    if not key:
        return []

    try:
        response = retry_call(
            lambda: requests.post(
                EXA_SEARCH_URL,
                headers={
                    "x-api-key": key,
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "type": "auto",
                    "numResults": max_results,
                    "contents": {
                        "highlights": {
                            "maxCharacters": max_characters,
                        }
                    },
                },
                timeout=timeout,
            )
        )
        response.raise_for_status()
        data = response.json()
        sources: list[EvidenceSource] = []
        for result in data.get("results", [])[:max_results]:
            snippet = _result_snippet(result, max_characters=max_characters)
            if not result.get("url") or not snippet:
                continue
            sources.append(
                EvidenceSource(
                    title=result.get("title") or result["url"],
                    url=result["url"],
                    publisher=_publisher_from_url(result["url"]),
                    date=result.get("publishedDate"),
                    snippet=snippet,
                )
            )
        return sources
    except Exception:
        return []


def _result_snippet(result: dict, max_characters: int) -> str:
    highlights = result.get("highlights") or []
    if isinstance(highlights, list) and highlights:
        return clean_text(" ".join(str(item) for item in highlights), max_chars=max_characters)
    if result.get("text"):
        return clean_text(str(result["text"]), max_chars=max_characters)
    if result.get("summary"):
        return clean_text(str(result["summary"]), max_chars=max_characters)
    return ""


def _publisher_from_url(url: str) -> str | None:
    without_scheme = url.split("://", 1)[-1]
    host = without_scheme.split("/", 1)[0]
    return host.removeprefix("www.") or None


@tool
def search_exa_for_company(query: str) -> list[dict]:
    """
    Search Exa for company research evidence with URLs and concise highlights.
    Use this for recent news, market evidence, competitors, funding, and product coverage.
    Returns an empty list if EXA_API_KEY is not configured or Exa has no result.
    """
    return evidence_to_dicts(search_exa(query=query))
