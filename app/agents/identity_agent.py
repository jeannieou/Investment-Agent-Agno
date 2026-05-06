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
        "Return the most likely canonical company identity.",
        "If ticker or company type is uncertain, use null for ticker and 'unknown' for company_type.",
        "Include source-like evidence only if available in the prompt context.",
    ],
)
