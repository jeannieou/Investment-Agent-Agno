import asyncio
from dataclasses import dataclass

from app.schemas import (
    CompanyAnalysis,
    CompanyIdentity,
    CompanyResearch,
    CompanyRisk,
    CriticInput,
    DimensionScore,
    EvidenceSource,
    IdentityRequest,
    ResearchRequest,
    WorkflowState,
)
from app.workflows.live_research_workflow import LiveInvestmentResearchWorkflow, _coerce_agent_output


@dataclass
class FakeRunOutput:
    content: object


class FakeIdentityAgent:
    async def arun(self, request: IdentityRequest):
        name = request.company_name
        ticker = {"Nvidia": "NVDA", "AMD": "AMD", "Intel": "INTC"}.get(name)
        return FakeRunOutput(
            CompanyIdentity(
                name=name,
                url=f"https://example.com/{name.lower()}",
                description=f"{name} identity",
                ticker=ticker,
                company_type="public" if ticker else "startup",
                confidence="high",
                sources=[
                    EvidenceSource(
                        title=f"{name} identity source",
                        url=f"https://example.com/{name.lower()}/identity",
                        snippet="identity evidence",
                    )
                ],
            )
        )


class FakeResearchAgent:
    async def arun(self, request: ResearchRequest):
        company = request.company
        if company.name == "BrokenCo":
            raise RuntimeError("research agent failed")
        return FakeRunOutput(
            {
                "name": company.name,
                "url": company.url,
                "company_type": company.company_type,
                "ticker": company.ticker,
                "business_model": f"{company.name} business model",
                "products": ["Product"],
                "team_size": "Not found",
                "key_people": ["Not found"],
                "funding_or_financials": "Financial evidence",
                "market_size": "Market evidence",
                "recent_news": ["Recent news"],
                "competitors": ["Competitor"],
                "sources": [source.model_dump() for source in company.sources],
            }
        )


class FakeAnalystAgent:
    async def arun(self, research: CompanyResearch):
        score = DimensionScore(score=7, narrative="Good evidence", confidence="medium")
        return FakeRunOutput(
            CompanyAnalysis(
                name=research.name,
                market_opportunity=score,
                competitive_position=score,
                growth_potential=score,
                business_model_strength=score,
                overall_score=1,
                one_line_verdict="Solid candidate.",
            )
        )


class FakeCriticAgent:
    async def arun(self, critic_input: CriticInput):
        return FakeRunOutput(
            CompanyRisk(
                name=critic_input.research.name,
                key_risks=["Execution risk"],
                analyst_weaknesses=["Limited live validation"],
                open_questions=["What does source coverage say?"],
                risk_level="medium",
            )
        )


class FakeDecisionAgent:
    async def arun(self, decision_input):
        top = decision_input.analysis[0].name
        return FakeRunOutput(
            "# Investment Recommendation Memo\n\n"
            "## Executive Summary\n"
            "Live fake workflow completed.\n\n"
            "## Recommendation\n"
            f"**Invest in: {top}**\n\n"
            "## Sources\n"
            "[1] fake source - https://example.com\n"
        )


def make_fake_live_workflow(progress_callback=None) -> LiveInvestmentResearchWorkflow:
    return LiveInvestmentResearchWorkflow(
        identity=FakeIdentityAgent(),
        research=FakeResearchAgent(),
        analyst=FakeAnalystAgent(),
        critic=FakeCriticAgent(),
        decision=FakeDecisionAgent(),
        progress_callback=progress_callback,
    )


def test_live_workflow_runs_with_fake_agents() -> None:
    progress_events = []
    workflow = make_fake_live_workflow(progress_callback=progress_events.append)
    state = WorkflowState(raw_input=["Nvidia", "AMD", "Intel"])

    result = asyncio.run(workflow.arun(state))

    assert len(result.confirmed_companies) == 3
    assert len(result.research) == 3
    assert len(result.analysis) == 3
    assert len(result.risks) == 3
    assert "Invest in:" in result.memo
    assert len(result.run_log.agent_runs) == 13
    assert result.run_log.cumulative_agent_latency_seconds >= result.run_log.total_latency_seconds
    assert result.run_log.parallel_pipeline_latency_seconds > 0
    assert set(result.run_log.company_pipeline_latency_seconds) == {"Nvidia", "AMD", "Intel"}
    assert "Starting live workflow for 3 companies" in progress_events
    assert "Live workflow complete" in progress_events


def test_live_workflow_falls_back_for_failed_company() -> None:
    workflow = make_fake_live_workflow()
    state = WorkflowState(raw_input=["Nvidia", "BrokenCo", "Intel"])

    result = asyncio.run(workflow.arun(state))

    assert len(result.research) == 3
    broken_research = next(item for item in result.research if item.name == "BrokenCo")
    broken_risk = next(item for item in result.risks if item.name == "BrokenCo")
    assert broken_research.business_model == "Not found"
    assert broken_risk.risk_level == "high"
    assert result.run_log.warnings


def test_coerce_agent_output_accepts_dict_and_model() -> None:
    identity = CompanyIdentity(name="Nvidia", url="https://example.com", description="Nvidia")

    assert _coerce_agent_output(FakeRunOutput(identity), CompanyIdentity) == identity
    assert _coerce_agent_output(FakeRunOutput(identity.model_dump()), CompanyIdentity) == identity
    assert _coerce_agent_output(FakeRunOutput("memo"), str) == "memo"
