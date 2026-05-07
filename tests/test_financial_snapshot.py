from app.schemas import CompanyIdentity, CompanyResearch, EvidenceSource, FinancialMetricCandidate
from app.tools.financial_snapshot import build_financial_snapshot, validate_research_sources


def test_build_financial_snapshot_prefers_primary_sources() -> None:
    company = CompanyIdentity(
        name="Nvidia",
        url="https://www.nvidia.com",
        description="GPU company",
        ticker="NVDA",
        exchange="NASDAQ",
        currency="USD",
        company_type="public",
    )
    research = CompanyResearch(
        name="Nvidia",
        url=company.url,
        company_type="public",
        ticker="NVDA",
        business_model="Sells GPUs and AI infrastructure.",
        products=["GPU"],
        team_size="Not found",
        key_people=["Not found"],
        funding_or_financials="Revenue and margin evidence from filings.",
        market_size="Not found",
        recent_news=[],
        competitors=[],
        sources=[
            EvidenceSource(
                title="SEC company facts",
                url="https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json",
                publisher="SEC EDGAR",
                snippet="Official financial facts.",
            )
        ],
    )

    snapshot = build_financial_snapshot(company, research)

    assert snapshot.name == "Nvidia"
    assert snapshot.ticker == "NVDA"
    assert snapshot.currency == "USD"
    assert snapshot.source_quality == "primary"
    assert snapshot.sources


def test_validate_research_sources_warns_for_unsourced_financial_claims() -> None:
    company = CompanyIdentity(
        name="PublicCo",
        url="https://example.com",
        description="Public company",
        ticker="PUB",
        company_type="public",
    )
    research = CompanyResearch(
        name="PublicCo",
        url=company.url,
        company_type="public",
        ticker="PUB",
        business_model="Business",
        products=["Product"],
        team_size="Not found",
        key_people=["Not found"],
        funding_or_financials="Revenue increased strongly.",
        market_size="Not found",
        recent_news=[],
        competitors=[],
        sources=[],
    )
    research.financial_snapshot = build_financial_snapshot(company, research)

    warnings = validate_research_sources(company, research)

    assert any("no sources" in warning for warning in warnings)


def test_build_financial_snapshot_uses_metric_candidates() -> None:
    company = CompanyIdentity(
        name="LVMH",
        url="https://www.lvmh.com",
        description="Luxury goods group",
        ticker="MC.PA",
        company_type="public",
        currency="EUR",
    )
    source = EvidenceSource(
        title="Key figures - LVMH",
        url="https://www.lvmh.com/investors/key-figures",
        publisher="lvmh.com",
        snippet="LVMH revenue was 80.8 billion euros in 2025.",
    )
    research = CompanyResearch(
        name="LVMH",
        url=company.url,
        company_type="public",
        ticker="MC.PA",
        business_model="Luxury goods",
        products=["Fashion"],
        team_size="Not found",
        key_people=["Not found"],
        funding_or_financials="Official key figures available.",
        market_size="Not found",
        recent_news=[],
        competitors=[],
        sources=[source],
    )
    candidates = [
        FinancialMetricCandidate(
            metric="revenue",
            value="80.8 billion",
            period="FY2025",
            currency="EUR",
            source_url=source.url,
            source_quality="primary",
            confidence="high",
            caveat="Official LVMH key figures page.",
        )
    ]

    snapshot = build_financial_snapshot(company, research, candidates)

    assert snapshot.period == "FY2025"
    assert snapshot.revenue.startswith("80.8 billion")
    assert snapshot.metric_candidates == candidates
