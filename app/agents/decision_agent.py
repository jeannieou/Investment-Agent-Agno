"""Decision Agent definition."""

from agno.agent import Agent

from app.config import get_agent_debug_config, get_reasoning_model
from app.schemas import DecisionInput


decision_agent = Agent(
    name="Decision Agent",
    role="Write the final investment recommendation memo comparing all companies.",
    model=get_reasoning_model(max_tokens=2200),
    input_schema=DecisionInput,
    markdown=True,
    retries=1,
    **get_agent_debug_config(),
    instructions=[
        "You receive research, analysis, and risk assessments for all companies.",
        "Write a concise markdown investment recommendation memo.",
        "You must name exactly one top pick using the phrase 'Invest in:'.",
        "Include these sections: Executive Summary, Entity Resolution, Financial Snapshot, Company Profiles, Side-by-Side Comparison, Recommendation, Sources.",
        "In Entity Resolution, show user input, resolved entity, whether it is investable, confidence, and any brand-to-parent note.",
        "When companies are from different industries, explicitly state the limitation of cross-industry comparison.",
        "Separate business quality from investment attractiveness. Discuss valuation reasonableness when evidence is available.",
        "Every important factual claim should be traceable to sources in the input.",
        "Cite sources near the claims when possible, not only in the final source list.",
        "If data gaps exist, surface them explicitly.",
    ],
)
