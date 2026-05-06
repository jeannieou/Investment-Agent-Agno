"""Critic Agent definition."""

from agno.agent import Agent

from app.config import get_agent_debug_config, get_reasoning_model
from app.schemas import CompanyRisk, CriticInput


critic_agent = Agent(
    name="Critic Agent",
    role="Challenge the analyst's conclusions for one company.",
    model=get_reasoning_model(max_tokens=1000),
    input_schema=CriticInput,
    output_schema=CompanyRisk,
    structured_outputs=True,
    retries=2,
    **get_agent_debug_config(),
    instructions=[
        "You receive one company's research and analysis.",
        "Your job is adversarial: find risks, weak assumptions, and open questions.",
        "List concrete risks, not generic warnings.",
        "Use risk_level as one of: low, medium, high.",
        "Do not fetch or invent new facts.",
    ],
)
