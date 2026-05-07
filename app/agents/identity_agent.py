"""Identity Agent definition."""

from agno.agent import Agent

from app.config import get_agent_debug_config, get_worker_model
from app.schemas import CompanyIdentity, IdentityRequest


identity_agent = Agent(
    name="Identity Agent",
    role="Resolve one raw company name into a canonical company identity.",
    model=get_worker_model(max_tokens=500),
    input_schema=IdentityRequest,
    output_schema=CompanyIdentity,
    structured_outputs=True,
    retries=2,
    **get_agent_debug_config(),
    instructions=[
        "You receive one raw company name.",
        "Preserve the exact user input in raw_input.",
        "Return the most likely canonical company identity, but distinguish brands/subsidiaries from investable parent entities.",
        "Fill legal_name, trade_name, aliases, parent_company, ticker, exchange, country, currency, company_type, and is_investable_entity when known.",
        "Examples: KFC is usually analyzed through Yum! Brands; Google through Alphabet; Twitter/X is private; LV usually refers to Louis Vuitton/LVMH.",
        "If ticker, exchange, or company type is uncertain, use null for ticker/exchange and 'unknown' for company_type.",
        "Set confidence to low when the input is ambiguous.",
        "Use resolution_note to explain any brand-to-parent mapping or uncertainty.",
        "Include source-like evidence only if available in the prompt context.",
    ],
)
