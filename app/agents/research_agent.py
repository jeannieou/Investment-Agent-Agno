"""Research Agent definition."""

from agno.agent import Agent

from app.config import get_agent_debug_config, get_worker_model
from app.schemas import CompanyResearch, ResearchRequest
from app.tools import (
    get_financial_data,
    get_wiki_summary,
    search_public_finance_for_company,
    search_exa_for_company,
    search_startup_profile_for_company,
    search_web_for_company,
)


research_agent = Agent(
    name="Research Agent",
    role="Research one confirmed company and return structured findings.",
    model=get_worker_model(max_tokens=1200),
    input_schema=ResearchRequest,
    output_schema=CompanyResearch,
    structured_outputs=True,
    retries=2,
    tools=[
        get_wiki_summary,
        get_financial_data,
        search_public_finance_for_company,
        search_startup_profile_for_company,
        search_exa_for_company,
        search_web_for_company,
    ],
    tool_call_limit=20,
    **get_agent_debug_config(),
    instructions=[
        "You receive one confirmed CompanyIdentity.",
        "Return only fields defined by CompanyResearch.",
        "Do not invent missing data. Use 'Not found' for unavailable fields.",
        "Use raw_input, aliases, trade_name, legal_name, and parent_company to search for the right entity.",
        "If the input is a brand/subsidiary, research the investable parent while clearly noting the brand relationship.",
        "Keep recent_news to at most five concise bullets.",
        "Use Wikipedia for background when available.",
        "Use SEC EDGAR only for US public companies with a ticker.",
        "For non-US public companies, SEC EDGAR returning empty does not mean company data is unavailable.",
        "For public companies, use search_public_finance_for_company to look for Yahoo Finance, official investor-relations pages, annual reports, and financial results.",
        "For non-US public companies, use public finance search, Exa, Wikipedia, and official investor-relations or annual-report sources.",
        "Use Yahoo Finance as useful market/valuation context, not as the strongest source for audited financial claims.",
        "For private companies and startups, use search_startup_profile_for_company to look for Crunchbase, funding coverage, founder information, employee estimates, and official pages.",
        "Treat Crunchbase and similar startup profile pages as secondary evidence, not primary financial proof.",
        "If a company has a long legal name, also search common aliases and ticker-style names.",
        "Use Exa search first for market, competitor, funding, and recent-news evidence.",
        "Use the fallback web search only if Exa is unavailable or returns no useful evidence.",
        "Every major factual claim should be traceable to an item in sources.",
        "Populate financial_snapshot when reliable financial evidence is available; otherwise leave unavailable values as 'Not found'.",
        "For financial_snapshot, prefer SEC filings, annual reports, investor-relations pages, or official company reports over general pages.",
        "Keep sources compact and traceable.",
    ],
)
