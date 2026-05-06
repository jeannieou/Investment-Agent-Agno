"""SEC EDGAR research tool."""

from __future__ import annotations

from typing import Any

import requests
from agno.tools import tool

from app.schemas import EvidenceSource
from app.tools._utils import DEFAULT_HEADERS, clean_text, evidence_to_dicts, retry_call


COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

REVENUE_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
]
PROFIT_TAGS = ["NetIncomeLoss", "ProfitLoss"]


def resolve_cik(company_name: str, ticker: str | None = None, timeout: float = 10.0) -> str | None:
    try:
        response = retry_call(lambda: requests.get(COMPANY_TICKERS_URL, headers=DEFAULT_HEADERS, timeout=timeout))
        response.raise_for_status()
        records = response.json().values()
        normalized_ticker = ticker.upper() if ticker else None
        normalized_name = company_name.lower()
        for record in records:
            record_ticker = str(record.get("ticker", "")).upper()
            record_title = str(record.get("title", "")).lower()
            if normalized_ticker and record_ticker == normalized_ticker:
                return str(record["cik_str"]).zfill(10)
            if normalized_name and normalized_name in record_title:
                return str(record["cik_str"]).zfill(10)
    except Exception:
        return None
    return None


def fetch_sec_financial_data(
    company_name: str,
    ticker: str | None = None,
    timeout: float = 10.0,
) -> list[EvidenceSource]:
    try:
        cik = resolve_cik(company_name=company_name, ticker=ticker, timeout=timeout)
        if not cik:
            return []
        url = COMPANY_FACTS_URL.format(cik=cik)
        response = retry_call(lambda: requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout))
        response.raise_for_status()
        data = response.json()
        summary = extract_financial_summary(data)
        if not summary:
            return []
        entity_name = data.get("entityName") or company_name
        return [
            EvidenceSource(
                title=f"SEC companyfacts for {entity_name}",
                url=url,
                publisher="SEC EDGAR",
                date=None,
                snippet=clean_text(summary, max_chars=2000),
            )
        ]
    except Exception:
        return []


def extract_financial_summary(companyfacts: dict[str, Any]) -> str:
    facts = companyfacts.get("facts", {}).get("us-gaap", {})
    revenue = _latest_fact_value(facts, REVENUE_TAGS)
    profit = _latest_fact_value(facts, PROFIT_TAGS)
    parts = []
    if revenue:
        parts.append(f"Latest reported revenue: {revenue}")
    if profit:
        parts.append(f"Latest reported net income/profit: {profit}")
    return "; ".join(parts)


def _latest_fact_value(facts: dict[str, Any], tags: list[str]) -> str | None:
    candidates: list[dict[str, Any]] = []
    for tag in tags:
        units = facts.get(tag, {}).get("units", {})
        for unit, values in units.items():
            for value in values:
                if value.get("val") is None:
                    continue
                candidates.append(
                    {
                        "end": value.get("end", ""),
                        "fy": value.get("fy"),
                        "fp": value.get("fp"),
                        "form": value.get("form"),
                        "unit": unit,
                        "val": value.get("val"),
                    }
                )
    if not candidates:
        return None
    latest = sorted(candidates, key=lambda item: item.get("end") or "")[-1]
    return (
        f"{latest['val']} {latest['unit']} "
        f"(FY {latest.get('fy')}, period {latest.get('fp')}, form {latest.get('form')}, end {latest.get('end')})"
    )


@tool
def get_financial_data(company_name: str, ticker: str | None = None) -> list[dict]:
    """
    Fetch official financial facts for a US public company from SEC EDGAR.
    Use this for public companies when a ticker is available.
    Returns an empty list for private companies, startups, or unavailable SEC data.
    """
    return evidence_to_dicts(fetch_sec_financial_data(company_name=company_name, ticker=ticker))
