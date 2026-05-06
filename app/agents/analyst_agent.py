"""Analyst Agent definition."""

from agno.agent import Agent

from app.config import get_agent_debug_config, get_reasoning_model
from app.schemas import CompanyAnalysis, CompanyResearch


analyst_agent = Agent(
    name="Analyst Agent",
    role="Analyze one company across investment dimensions.",
    model=get_reasoning_model(max_tokens=1500),
    input_schema=CompanyResearch,
    output_schema=CompanyAnalysis,
    structured_outputs=True,
    retries=2,
    **get_agent_debug_config(),
    instructions=[
        "You receive research for one company.",
        "Use only the provided research. Do not add outside facts.",
        "Score market opportunity, competitive position, growth potential, and business model strength from 1 to 10.",
        "For each dimension, include score, narrative, and confidence.",
        "The schema computes overall_score from dimension scores, so focus on calibrated dimension scoring.",
        "If data is missing, say so and reduce confidence.",
    ],
)
