"""Lightweight web search evidence tool.

This is a no-key fallback for Stage 4. It gives the Research Agent a real
source-bearing search option before a stronger provider such as Exa is added.
"""

from __future__ import annotations

import requests
from agno.tools import tool

from app.schemas import EvidenceSource
from app.tools._utils import DEFAULT_HEADERS, clean_text, evidence_to_dicts, retry_call


DUCKDUCKGO_API_URL = "https://api.duckduckgo.com/"


def search_company_web(query: str, max_results: int = 5, timeout: float = 10.0) -> list[EvidenceSource]:
    try:
        response = retry_call(
            lambda: requests.get(
                DUCKDUCKGO_API_URL,
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                headers=DEFAULT_HEADERS,
                timeout=timeout,
            )
        )
        response.raise_for_status()
        data = response.json()
        sources: list[EvidenceSource] = []
        if data.get("AbstractText") and data.get("AbstractURL"):
            sources.append(
                EvidenceSource(
                    title=data.get("Heading") or query,
                    url=data["AbstractURL"],
                    publisher="DuckDuckGo",
                    snippet=clean_text(data["AbstractText"], max_chars=1000),
                )
            )
        for topic in _flatten_related_topics(data.get("RelatedTopics", [])):
            if len(sources) >= max_results:
                break
            text = topic.get("Text")
            url = topic.get("FirstURL")
            if not text or not url:
                continue
            sources.append(
                EvidenceSource(
                    title=text.split(" - ")[0][:120],
                    url=url,
                    publisher="DuckDuckGo",
                    snippet=clean_text(text, max_chars=800),
                )
            )
        return sources[:max_results]
    except Exception:
        return []


def _flatten_related_topics(topics: list[dict]) -> list[dict]:
    flattened: list[dict] = []
    for topic in topics:
        if "Topics" in topic:
            flattened.extend(_flatten_related_topics(topic.get("Topics", [])))
        else:
            flattened.append(topic)
    return flattened


@tool
def search_web_for_company(query: str) -> list[dict]:
    """
    Search the web for company background, market, competitor, or recent-news evidence.
    Use this when Wikipedia and SEC are insufficient.
    Returns compact source snippets with URLs.
    """
    return evidence_to_dicts(search_company_web(query=query))
