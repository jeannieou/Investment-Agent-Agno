from app.schemas import CompanyIdentity, CompanyResearch, EvidenceSource, FinancialSnapshot
from app.tools.financial_snapshot import validate_research_sources


def test_public_company_weak_financial_snapshot_creates_warning() -> None:
    company = CompanyIdentity(
        name="Example Public",
        url="https://example.com",
        description="Public company",
        ticker="EXM",
        company_type="public",
    )
    research = CompanyResearch(
        name="Example Public",
        url=company.url,
        company_type="public",
        ticker="EXM",
        business_model="Business",
        products=["Product"],
        team_size="Not found",
        key_people=["Not found"],
        funding_or_financials="Revenue is disclosed.",
        market_size="Not found",
        recent_news=[],
        competitors=[],
        financial_snapshot=FinancialSnapshot(
            name="Example Public",
            ticker="EXM",
            source_quality="weak",
            sources=[
                EvidenceSource(
                    title="Blog post",
                    url="https://example.com/blog",
                    publisher="Example",
                    snippet="Mentions revenue.",
                )
            ],
        ),
        sources=[
            EvidenceSource(
                title="Blog post",
                url="https://example.com/blog",
                publisher="Example",
                snippet="Mentions revenue.",
            )
        ],
    )

    warnings = validate_research_sources(company, research)

    assert any("not backed by strong primary sources" in warning for warning in warnings)
