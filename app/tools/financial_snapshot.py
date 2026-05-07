"""Financial snapshot helpers used after research is collected."""

from __future__ import annotations

from app.schemas import CompanyIdentity, CompanyResearch, EvidenceSource, FinancialMetricCandidate, FinancialSnapshot


PRIMARY_HOST_HINTS = (
    "sec.gov",
    "investor",
    "investors",
    "annualreport",
    "annualreports",
    "finance.yahoo.com",
    "yahoo finance",
    "ir.",
)


def build_financial_snapshot(
    company: CompanyIdentity,
    research: CompanyResearch,
    metric_candidates: list[FinancialMetricCandidate] | None = None,
) -> FinancialSnapshot:
    """Create a compact financial snapshot without inventing unavailable data."""

    sources = _financial_sources(research.sources)
    source_quality = _source_quality(sources)
    financial_text = research.funding_or_financials or "Not found"
    currency = company.currency or ("USD" if company.exchange in {"NYSE", "NASDAQ"} else "Not found")

    candidates = metric_candidates or []
    metric_map = _best_metrics_by_name(candidates)

    return FinancialSnapshot(
        name=research.name,
        ticker=research.ticker,
        period=_candidate_period(metric_map) or ("Latest available period in cited sources" if sources else "Not found"),
        currency=currency,
        revenue=_candidate_value(metric_map, "revenue") or financial_text,
        revenue_growth=_candidate_value(metric_map, "revenue_growth") or "Not found",
        operating_margin=_candidate_value(metric_map, "operating_margin") or "Not found",
        net_income=_candidate_value(metric_map, "net_income") or "Not found",
        free_cash_flow=_candidate_value(metric_map, "free_cash_flow") or "Not found",
        debt_or_leverage=(
            _candidate_value(metric_map, "debt_or_leverage")
            or _candidate_value(metric_map, "net_debt")
            or _candidate_value(metric_map, "funding")
            or "Not found"
        ),
        market_cap=_candidate_value(metric_map, "market_cap") or _candidate_value(metric_map, "valuation") or "Not found",
        pe_ratio=_candidate_value(metric_map, "pe_ratio") or "Not found",
        source_quality=source_quality,
        sources=sources,
        metric_candidates=candidates,
    )


def validate_research_sources(company: CompanyIdentity, research: CompanyResearch) -> list[str]:
    warnings: list[str] = []
    if not research.sources:
        warnings.append(f"{research.name}: no sources were collected.")
        return warnings

    if research.funding_or_financials != "Not found":
        financial_sources = _financial_sources(research.sources)
        if not financial_sources:
            warnings.append(f"{research.name}: financial claim has no obvious financial/primary source.")

    if company.company_type == "public" and research.financial_snapshot:
        if research.financial_snapshot.source_quality in {"weak", "not_found"}:
            warnings.append(
                f"{research.name}: public-company financial snapshot is not backed by strong primary sources."
            )
    return warnings


def _financial_sources(sources: list[EvidenceSource]) -> list[EvidenceSource]:
    result: list[EvidenceSource] = []
    for source in sources:
        haystack = f"{source.title} {source.url} {source.publisher or ''} {source.snippet}".lower()
        if any(hint in haystack for hint in PRIMARY_HOST_HINTS):
            result.append(source)
    return result or sources[:2]


def _source_quality(sources: list[EvidenceSource]) -> str:
    if not sources:
        return "not_found"
    haystack = " ".join(f"{source.title} {source.url} {source.publisher or ''}" for source in sources).lower()
    if "sec.gov" in haystack or "investor" in haystack or "investors" in haystack or "ir." in haystack:
        return "primary"
    if "wikipedia" in haystack:
        return "secondary"
    return "mixed"


def _best_metrics_by_name(candidates: list[FinancialMetricCandidate]) -> dict[str, FinancialMetricCandidate]:
    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    result: dict[str, FinancialMetricCandidate] = {}
    for candidate in candidates:
        current = result.get(candidate.metric)
        if current is None or confidence_rank[candidate.confidence] > confidence_rank[current.confidence]:
            result[candidate.metric] = candidate
    return result


def _candidate_value(metric_map: dict[str, FinancialMetricCandidate], metric: str) -> str | None:
    candidate = metric_map.get(metric)
    if not candidate:
        return None
    caveat = f" ({candidate.caveat})" if candidate.caveat else ""
    return f"{candidate.value}{caveat}"


def _candidate_period(metric_map: dict[str, FinancialMetricCandidate]) -> str | None:
    for metric in ["revenue", "net_income", "operating_income", "free_cash_flow"]:
        candidate = metric_map.get(metric)
        if candidate and candidate.period != "Not found":
            return candidate.period
    return None
