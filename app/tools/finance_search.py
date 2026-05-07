"""Targeted search tools for finance and startup evidence."""

from __future__ import annotations

from agno.tools import tool

from app.schemas import EvidenceSource
from app.tools._utils import evidence_to_dicts
from app.tools.exa_search import search_exa


def search_public_finance_sources(company_name: str, ticker: str | None = None) -> list[EvidenceSource]:
    """Search Yahoo Finance plus official financial disclosure pages."""

    ticker_part = f" {ticker}" if ticker else ""
    query = (
        f"{company_name}{ticker_part} investor relations annual report financial results "
        "Yahoo Finance official"
    )
    return search_exa(query=query, max_results=6)


def search_startup_profile_sources(company_name: str) -> list[EvidenceSource]:
    """Search public startup/company profile sources such as Crunchbase."""

    query = (
        f"{company_name} Crunchbase funding founders employees startup profile official website"
    )
    return search_exa(query=query, max_results=6)


@tool
def search_public_finance_for_company(company_name: str, ticker: str | None = None) -> list[dict]:
    """
    Search for public-company finance evidence, including Yahoo Finance, investor
    relations pages, annual reports, and official financial results.
    Prefer official IR/annual-report sources over Yahoo Finance for primary claims.
    Returns an empty list if EXA_API_KEY is not configured or no useful result exists.
    """

    return evidence_to_dicts(search_public_finance_sources(company_name=company_name, ticker=ticker))


@tool
def search_startup_profile_for_company(company_name: str) -> list[dict]:
    """
    Search for startup/private-company profile evidence, including Crunchbase,
    funding coverage, founder information, employee estimates, and official pages.
    Treat Crunchbase and similar profile pages as secondary evidence.
    Returns an empty list if EXA_API_KEY is not configured or no useful result exists.
    """

    return evidence_to_dicts(search_startup_profile_sources(company_name=company_name))
