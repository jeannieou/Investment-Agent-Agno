"""Financial Extractor Agent definition."""

from agno.agent import Agent

from app.config import get_agent_debug_config, get_worker_model
from app.schemas import FinancialExtractionRequest, FinancialExtractionResult


financial_extractor_agent = Agent(
    name="Financial Extractor Agent",
    role="Extract typed financial metric candidates from already-fetched source text.",
    model=get_worker_model(max_tokens=1000),
    input_schema=FinancialExtractionRequest,
    output_schema=FinancialExtractionResult,
    structured_outputs=True,
    retries=1,
    **get_agent_debug_config(),
    instructions=[
        "You receive source text that has already been fetched by the system.",
        "Do not browse the web or add outside facts.",
        "Extract only financial metrics that are explicitly supported by the source_text.",
        "Return typed FinancialMetricCandidate objects.",
        "Each candidate must include metric, value, period, currency, source_url, source_quality, confidence, and caveat.",
        "Use high confidence only when the metric label, value, and period are clear.",
        "Use medium or low confidence when the value looks estimated, secondary, incomplete, or ambiguous.",
        "For private companies, funding, valuation, revenue estimates, and employees are acceptable if clearly caveated.",
        "Do not convert currencies or calculate ratios unless the source explicitly provides them.",
        "If no reliable metrics are present, return an empty metrics list.",
    ],
)
