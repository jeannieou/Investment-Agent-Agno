"""Mock investment research workflow for Stage 1.

This module intentionally avoids Agno, LLMs, and external APIs. It proves the
business workflow and typed state shape before runtime/tool integration.
"""

from __future__ import annotations

import asyncio
import time

from app.schemas import (
    AgentRunLog,
    CompanyAnalysis,
    CompanyIdentity,
    CompanyResearch,
    CompanyRisk,
    DimensionScore,
    EvidenceSource,
    WorkflowState,
)


class InvestmentResearchWorkflow:
    """Deterministic mock workflow that mirrors the planned agent pipeline."""

    async def run(self, state: WorkflowState) -> WorkflowState:
        self._current_state = state
        state.start_time = time.time()

        for raw_name in state.raw_input:
            identity = await self._run_logged(
                agent="Identity Agent",
                company=raw_name,
                call=lambda: self._mock_identity(raw_name),
            )
            state.confirmed_companies.append(identity)

        pipeline_results = await asyncio.gather(
            *(self._run_single_company_pipeline(company) for company in state.confirmed_companies),
            return_exceptions=True,
        )

        valid_results = []
        for company, result in zip(state.confirmed_companies, pipeline_results):
            if isinstance(result, Exception):
                state.run_log.warnings.append(f"{company.name}: {result}")
                valid_results.append(make_fallback_pipeline_result(company, error=str(result)))
            else:
                valid_results.append(result)

        state.research = [result[0] for result in valid_results]
        state.analysis = [result[1] for result in valid_results]
        state.risks = [result[2] for result in valid_results]

        state.memo = await self._run_logged(
            agent="Decision Agent",
            company="all",
            call=lambda: self._mock_memo(state),
        )
        state.run_log.finalize(total_latency_seconds=time.time() - state.start_time)
        return state

    async def _run_single_company_pipeline(
        self, company: CompanyIdentity
    ) -> tuple[CompanyResearch, CompanyAnalysis, CompanyRisk]:
        research = await self._run_logged(
            agent="Research Agent",
            company=company.name,
            call=lambda: self._mock_research(company),
            tool_calls=["mock_search", "mock_company_profile"],
        )
        analysis = await self._run_logged(
            agent="Analyst Agent",
            company=company.name,
            call=lambda: self._mock_analysis(research),
        )
        risk = await self._run_logged(
            agent="Critic Agent",
            company=company.name,
            call=lambda: self._mock_risk(research, analysis),
        )
        return research, analysis, risk

    async def _run_logged(self, agent: str, company: str, call, tool_calls: list[str] | None = None):
        start = time.time()
        try:
            result = call()
            success = True
            error = None
            return result
        except Exception as exc:
            success = False
            error = str(exc)
            raise
        finally:
            end = max(time.time(), start + _mock_latency_seconds(agent, company))
            self._current_state.run_log.agent_runs.append(
                AgentRunLog(
                    agent=agent,
                    company=company,
                    start_time=start,
                    end_time=end,
                    tool_calls=tool_calls or [],
                    success=success,
                    error=error,
                )
            )

    async def arun(self, state: WorkflowState) -> WorkflowState:
        return await self.run(state)

    def _mock_identity(self, raw_name: str) -> CompanyIdentity:
        clean_name = raw_name.strip()
        slug = clean_name.lower().replace(" ", "")
        ticker = _mock_ticker(clean_name)
        company_type = "public" if ticker else "startup"
        return CompanyIdentity(
            name=clean_name,
            url=f"https://www.{slug}.com",
            description=f"Mock confirmed identity for {clean_name}",
            ticker=ticker,
            company_type=company_type,
            confidence="high",
            sources=[
                EvidenceSource(
                    title=f"{clean_name} mock identity source",
                    url=f"https://example.com/{slug}/identity",
                    publisher="Mock Search",
                    snippet=f"Mock source confirming {clean_name}'s identity.",
                )
            ],
        )

    def _mock_research(self, company: CompanyIdentity) -> CompanyResearch:
        positioning = _mock_positioning(company.name)
        return CompanyResearch(
            name=company.name,
            url=company.url,
            company_type=company.company_type,
            ticker=company.ticker,
            business_model=(
                f"{company.name} is modeled as a {positioning['market']} company with "
                f"{positioning['business_model']} revenue characteristics."
            ),
            products=[f"{company.name} {positioning['product_a']}", f"{company.name} {positioning['product_b']}"],
            team_size="Not found" if company.company_type == "startup" else "Mock large public-company workforce",
            key_people=["Not found"],
            funding_or_financials=(
                f"Mock public-company profile with {positioning['financial_profile']}"
                if company.company_type == "public"
                else f"Mock private/startup profile with {positioning['financial_profile']}; official financials not available"
            ),
            market_size=f"Mock {positioning['market_size']} market estimate with source attribution",
            recent_news=[
                f"{company.name} announced a mock {positioning['product_a']} update.",
                f"{company.name} appeared in mock {positioning['market']} market coverage.",
            ],
            competitors=[positioning["competitor_a"], positioning["competitor_b"]],
            sources=[
                *company.sources,
                EvidenceSource(
                    title=f"{company.name} mock research source",
                    url=f"https://example.com/{company.name.lower().replace(' ', '')}/research",
                    publisher="Mock Research",
                    snippet=f"Mock evidence used for {company.name} research fields.",
                ),
            ],
        )

    def _mock_analysis(self, research: CompanyResearch) -> CompanyAnalysis:
        scores = _mock_dimension_scores(research.name, research.company_type)
        dimensions = [
            DimensionScore(
                score=scores["market_opportunity"],
                narrative=f"{research.name} has a mock {scores['market_label']} addressable market.",
                confidence="medium",
            ),
            DimensionScore(
                score=scores["competitive_position"],
                narrative=f"{research.name} has mock {scores['competitive_label']} competitive positioning.",
                confidence="medium",
            ),
            DimensionScore(
                score=scores["growth_potential"],
                narrative=f"{research.name} shows mock {scores['growth_label']} growth signals.",
                confidence="medium",
            ),
            DimensionScore(
                score=scores["business_model_strength"],
                narrative=f"{research.name} has a mock {scores['business_label']} business model.",
                confidence="medium",
            ),
        ]
        overall = round(sum(item.score for item in dimensions) / len(dimensions))
        return CompanyAnalysis(
            name=research.name,
            market_opportunity=dimensions[0],
            competitive_position=dimensions[1],
            growth_potential=dimensions[2],
            business_model_strength=dimensions[3],
            overall_score=overall,
            one_line_verdict=f"{research.name} is a mock {'strong' if overall >= 7 else 'developing'} investment candidate.",
        )

    def _mock_risk(self, research: CompanyResearch, analysis: CompanyAnalysis) -> CompanyRisk:
        risk_level = "medium" if analysis.overall_score >= 7 else "high"
        return CompanyRisk(
            name=research.name,
            key_risks=[
                f"{research.name} faces mock competitive pressure.",
                f"{research.name} has mock execution risk.",
                "Source coverage is synthetic at Stage 1.",
            ],
            analyst_weaknesses=[
                "Analysis is based on deterministic mock research, not live data."
            ],
            open_questions=[
                "What do live sources say about recent performance?",
                "How durable is the company's competitive position?",
                "Are financial or funding claims supported by primary sources?",
            ],
            risk_level=risk_level,
            sources_to_verify=[source.url for source in research.sources],
        )

    def _mock_memo(self, state: WorkflowState) -> str:
        top_pick = max(state.analysis, key=lambda item: item.overall_score)
        company_list = ", ".join(company.name for company in state.confirmed_companies)
        profile_sections = "\n\n".join(
            f"### {research.name}\n"
            f"- Business: {research.business_model}\n"
            f"- Financials/Funding: {research.funding_or_financials}\n"
            f"- Score: {_analysis_for(state, research.name).overall_score}/10\n"
            f"- Key risks: {'; '.join(_risk_for(state, research.name).key_risks[:2])}"
            for research in state.research
        )
        comparison_rows = "\n".join(
            f"| {analysis.name} | {analysis.market_opportunity.score}/10 | "
            f"{analysis.competitive_position.score}/10 | {analysis.growth_potential.score}/10 | "
            f"{analysis.business_model_strength.score}/10 | {_risk_for(state, analysis.name).risk_level} | "
            f"{analysis.overall_score}/10 |"
            for analysis in state.analysis
        )
        sources = _dedupe_sources(source for research in state.research for source in research.sources)
        source_lines = "\n".join(
            f"[{index}] {source.title} - {source.url}"
            for index, source in enumerate(sources, start=1)
        )
        return (
            "# Investment Recommendation Memo\n\n"
            "## Executive Summary\n"
            f"This mock memo evaluates {company_list}. The current top pick is {top_pick.name} "
            "based on deterministic Stage 1 scoring.\n\n"
            "## Company Profiles\n"
            f"{profile_sections}\n\n"
            "## Side-by-Side Comparison\n"
            "| Company | Market opportunity | Competitive position | Growth potential | Business model | Risk level | Overall |\n"
            "|---|---:|---:|---:|---:|---|---:|\n"
            f"{comparison_rows}\n\n"
            "## Recommendation\n"
            f"**Invest in: {top_pick.name}**\n\n"
            "Reason: This is a mock recommendation proving the workflow can produce a complete memo.\n\n"
            "Key risks to monitor: Replace mock research with live sources before making any real investment decision.\n\n"
            "## Sources\n"
            f"{source_lines}\n"
        )


def run_mock_workflow(company_names: list[str]) -> WorkflowState:
    workflow = InvestmentResearchWorkflow()
    state = WorkflowState(raw_input=company_names)
    return asyncio.run(workflow.arun(state))


def make_fallback_research(company: CompanyIdentity, error: str) -> CompanyResearch:
    return CompanyResearch(
        name=company.name,
        url=company.url,
        company_type=company.company_type,
        ticker=company.ticker,
        business_model="Not found",
        products=["Not found"],
        team_size="Not found",
        key_people=["Not found"],
        funding_or_financials="Not found",
        market_size="Not found",
        recent_news=[f"Research failed: {error}"],
        competitors=["Not found"],
        sources=[*company.sources],
    )


def make_fallback_analysis(research: CompanyResearch, error: str) -> CompanyAnalysis:
    fallback_dimension = DimensionScore(
        score=1,
        narrative=f"Analysis unavailable because upstream processing failed: {error}",
        confidence="low",
    )
    return CompanyAnalysis(
        name=research.name,
        market_opportunity=fallback_dimension,
        competitive_position=fallback_dimension,
        growth_potential=fallback_dimension,
        business_model_strength=fallback_dimension,
        overall_score=1,
        one_line_verdict="Insufficient data for investment analysis.",
    )


def make_fallback_risk(
    research: CompanyResearch,
    analysis: CompanyAnalysis,
    error: str,
) -> CompanyRisk:
    return CompanyRisk(
        name=research.name,
        key_risks=[f"Pipeline failed for this company: {error}"],
        analyst_weaknesses=["No reliable analysis was produced."],
        open_questions=["Can this company be researched successfully with live tools?"],
        risk_level="high",
        sources_to_verify=[source.url for source in research.sources],
    )


def make_fallback_pipeline_result(
    company: CompanyIdentity,
    error: str,
) -> tuple[CompanyResearch, CompanyAnalysis, CompanyRisk]:
    research = make_fallback_research(company, error=error)
    analysis = make_fallback_analysis(research, error=error)
    risk = make_fallback_risk(research, analysis, error=error)
    return research, analysis, risk


def _mock_ticker(company_name: str) -> str | None:
    tickers = {
        "nvidia": "NVDA",
        "amd": "AMD",
        "intel": "INTC",
        "apple": "AAPL",
        "microsoft": "MSFT",
    }
    return tickers.get(company_name.lower())


def _mock_signal(company_name: str) -> int:
    return sum((index + 1) * ord(char.lower()) for index, char in enumerate(company_name) if char.isalnum())


def _pick(options: list[str], signal: int, offset: int = 0) -> str:
    return options[(signal + offset) % len(options)]


def _mock_positioning(company_name: str) -> dict[str, str]:
    signal = _mock_signal(company_name)
    return {
        "market": _pick(["enterprise", "consumer", "infrastructure", "vertical software"], signal),
        "business_model": _pick(["usage-based", "subscription", "transaction-driven", "services-led"], signal, 1),
        "product_a": _pick(["platform", "workflow suite", "developer tools", "analytics product"], signal, 2),
        "product_b": _pick(["services", "API", "marketplace", "data layer"], signal, 3),
        "financial_profile": _pick(
            ["strong growth but unclear margin durability", "steady revenue but heavy investment needs", "early traction and high burn risk"],
            signal,
            4,
        ),
        "market_size": _pick(["large", "emerging", "niche but expanding", "competitive"], signal, 5),
        "competitor_a": _pick(["Large incumbent", "Focused startup rival", "Open-source alternative"], signal, 6),
        "competitor_b": _pick(["Platform competitor", "Regional competitor", "Adjacent category leader"], signal, 7),
    }


def _mock_dimension_scores(company_name: str, company_type: str) -> dict[str, int | str]:
    signal = _mock_signal(company_name)
    if company_type == "public":
        base = 6
        spread = 4
    else:
        base = 4
        spread = 5

    market = base + (signal % spread)
    competitive = base + ((signal // 3) % spread)
    growth = base + ((signal // 5) % spread)
    business = base + ((signal // 7) % spread)
    return {
        "market_opportunity": min(market + 1, 10),
        "competitive_position": min(competitive, 10),
        "growth_potential": min(growth + 1, 10),
        "business_model_strength": min(business, 10),
        "market_label": _pick(["broad", "focused", "early but expanding", "competitive"], signal, 1),
        "competitive_label": _pick(["strong", "mixed", "defensible", "unproven"], signal, 2),
        "growth_label": _pick(["strong", "moderate", "volatile", "early"], signal, 3),
        "business_label": _pick(["durable", "developing", "capital-intensive", "still-unproven"], signal, 4),
    }


def _mock_latency_seconds(agent: str, company: str) -> float:
    signal = _mock_signal(f"{agent}:{company}")
    return round(0.012 + (signal % 29) / 1000, 3)


def _analysis_for(state: WorkflowState, company_name: str) -> CompanyAnalysis:
    return next(item for item in state.analysis if item.name == company_name)


def _risk_for(state: WorkflowState, company_name: str) -> CompanyRisk:
    return next(item for item in state.risks if item.name == company_name)


def _dedupe_sources(sources) -> list[EvidenceSource]:
    seen: set[str] = set()
    result: list[EvidenceSource] = []
    for source in sources:
        if source.url in seen:
            continue
        seen.add(source.url)
        result.append(source)
    return result
