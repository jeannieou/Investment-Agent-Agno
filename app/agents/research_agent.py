"""Research Agent definition."""

from agno.agent import Agent

from app.config import get_agent_debug_config, get_worker_model
from app.schemas import CompanyResearch, ResearchRequest
from app.tools import (
    get_financial_data,
    get_wiki_summary,
    search_exa_for_company,
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
    tools=[get_wiki_summary, get_financial_data, search_exa_for_company, search_web_for_company],
    tool_call_limit=20,
    **get_agent_debug_config(),
    instructions=[
        "You receive one confirmed CompanyIdentity.",
        "Return only fields defined by CompanyResearch.",
        "Do not invent missing data. Use 'Not found' for unavailable fields.",
        "Keep recent_news to at most five concise bullets.",
        "Use Wikipedia for background when available.",
        "Use SEC EDGAR only for US public companies with a ticker.",
        "For non-US public companies, SEC EDGAR returning empty does not mean company data is unavailable.",
        "For non-US public companies, use Exa, Wikipedia, and official investor-relations or annual-report sources.",
        "If a company has a long legal name, also search common aliases and ticker-style names.",
        "Use Exa search first for market, competitor, funding, and recent-news evidence.",
        "Use the fallback web search only if Exa is unavailable or returns no useful evidence.",
        "Every major factual claim should be traceable to an item in sources.",
        "Keep sources compact and traceable.",
    ],
)
