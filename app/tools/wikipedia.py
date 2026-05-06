"""Wikipedia research tool."""

from __future__ import annotations

import re
from urllib.parse import quote

import requests
from agno.tools import tool

from app.schemas import EvidenceSource
from app.tools._utils import DEFAULT_HEADERS, clean_text, evidence_to_dicts, retry_call


def fetch_wikipedia_summary(company_name: str, timeout: float = 10.0) -> list[EvidenceSource]:
    candidates = _candidate_titles(company_name, timeout=timeout)
    for candidate in candidates:
        sources = _fetch_wikipedia_summary_by_title(candidate, timeout=timeout)
        if sources:
            return sources
    return []


def _candidate_titles(company_name: str, timeout: float) -> list[str]:
    candidates = _generated_title_candidates(company_name)
    search_title = _search_wikipedia_title(company_name, timeout=timeout)
    if search_title and search_title not in candidates:
        candidates.append(search_title)
    return candidates


def _generated_title_candidates(company_name: str) -> list[str]:
    clean_name = " ".join(company_name.strip().split())
    candidates = [clean_name] if clean_name else []

    if "(" in clean_name and ")" in clean_name:
        before_parenthesis = clean_name.split("(", 1)[0].strip()
        parenthetical = clean_name.split("(", 1)[1].split(")", 1)[0].strip()
        candidates.extend([before_parenthesis, parenthetical])

    words = re.findall(r"[A-Za-z0-9]+", clean_name)
    if words:
        first_word = words[0]
        if first_word.isupper() and 2 <= len(first_word) <= 8:
            candidates.append(first_word)

        legal_suffixes = {"inc", "corp", "corporation", "company", "co", "ltd", "limited", "plc", "sa", "se"}
        meaningful_words = [word for word in words if word.lower().strip(".") not in legal_suffixes]
        acronym = "".join(word[0] for word in meaningful_words if word[:1].isalpha()).upper()
        if 2 <= len(acronym) <= 8:
            candidates.append(acronym)

    deduped = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _search_wikipedia_title(company_name: str, timeout: float) -> str | None:
    try:
        response = retry_call(
            lambda: requests.get(
                "https://en.wikipedia.org/w/api.php",
                headers=DEFAULT_HEADERS,
                params={
                    "action": "opensearch",
                    "search": company_name,
                    "limit": 1,
                    "namespace": 0,
                    "format": "json",
                },
                timeout=timeout,
            )
        )
        response.raise_for_status()
        data = response.json()
        titles = data[1] if isinstance(data, list) and len(data) > 1 else []
        if titles:
            return str(titles[0])
    except Exception:
        return None
    return None


def _fetch_wikipedia_summary_by_title(company_name: str, timeout: float = 10.0) -> list[EvidenceSource]:
    try:
        encoded_name = quote(company_name.strip().replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_name}"
        response = retry_call(lambda: requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout))
        response.raise_for_status()
        data = response.json()
        extract = clean_text(data.get("extract", ""), max_chars=1500)
        if not extract:
            return []
        source_url = data.get("content_urls", {}).get("desktop", {}).get("page", url)
        return [
            EvidenceSource(
                title=data.get("title", company_name),
                url=source_url,
                publisher="Wikipedia",
                date=None,
                snippet=extract,
            )
        ]
    except Exception:
        return []


@tool
def get_wiki_summary(company_name: str) -> list[dict]:
    """
    Fetch a concise company background summary from Wikipedia.
    Use this for founding history, company description, and general background.
    Returns an empty list if no reliable Wikipedia summary is available.
    """
    return evidence_to_dicts(fetch_wikipedia_summary(company_name))
