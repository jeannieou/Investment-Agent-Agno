"""Live LLM-backed investment research workflow."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from app.agents import (
    analyst_agent,
    critic_agent,
    decision_agent,
    financial_extractor_agent,
    identity_agent,
    research_agent,
)
from app.schemas import (
    AgentRunLog,
    CompanyAnalysis,
    CompanyIdentity,
    CompanyResearch,
    CompanyRisk,
    CriticInput,
    DecisionInput,
    EvidenceSource,
    FinancialExtractionRequest,
    FinancialExtractionResult,
    FinancialMetricCandidate,
    IdentityRequest,
    ResearchRequest,
    WorkflowState,
)
from app.tools.entity_resolution import enrich_identity
from app.tools.financial_snapshot import build_financial_snapshot, validate_research_sources
from app.tools.finance_search import search_public_finance_sources
from app.tools.sec_edgar import fetch_sec_financial_data
from app.tools.source_reader import read_source_text
from app.tools.wikipedia import fetch_wikipedia_summary
from app.workflows.research_workflow import make_fallback_pipeline_result, make_fallback_research


class LiveInvestmentResearchWorkflow:
    """Runs the real Agno agents while preserving typed workflow state."""

    def __init__(
        self,
        identity=identity_agent,
        research=research_agent,
        analyst=analyst_agent,
        critic=critic_agent,
        decision=decision_agent,
        financial_extractor=financial_extractor_agent,
        auto_confirm: bool = True,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.identity_agent = identity
        self.research_agent = research
        self.analyst_agent = analyst
        self.critic_agent = critic
        self.decision_agent = decision
        self.financial_extractor_agent = financial_extractor
        self.auto_confirm = auto_confirm
        self.progress_callback = progress_callback

    async def arun(self, state: WorkflowState) -> WorkflowState:
        self._current_state = state
        state.start_time = time.time()
        self._progress(f"Starting live workflow for {len(state.raw_input)} companies")

        for raw_name in state.raw_input:
            self._progress(f"Resolving identity: {raw_name}")
            identity = await self._run_agent_logged(
                agent_name="Identity Agent",
                company=raw_name,
                call=lambda raw_name=raw_name: self.identity_agent.arun(
                    IdentityRequest(company_name=raw_name)
                ),
                output_type=CompanyIdentity,
            )
            identity, warnings = enrich_identity(identity, raw_name)
            state.run_log.warnings.extend(warnings)
            state.confirmed_companies.append(identity)
            ticker = f" ({identity.ticker})" if identity.ticker else ""
            self._progress(
                f"Resolved identity: {identity.raw_input} -> {identity.name}{ticker}; "
                f"confidence={identity.confidence}; investable={identity.is_investable_entity}"
            )

        self._progress("Running company pipelines in parallel")
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

        self._progress("Writing final recommendation memo")
        decision_input = DecisionInput(
            identities=state.confirmed_companies,
            research=state.research,
            analysis=state.analysis,
            risks=state.risks,
        )
        state.memo = await self._run_agent_logged(
            agent_name="Decision Agent",
            company="all",
            call=lambda: self.decision_agent.arun(decision_input),
            output_type=str,
        )
        state.run_log.finalize(total_latency_seconds=time.time() - state.start_time)
        self._progress("Live workflow complete")
        return state

    async def _run_single_company_pipeline(
        self, company: CompanyIdentity
    ) -> tuple[CompanyResearch, CompanyAnalysis, CompanyRisk]:
        self._progress(f"Research started: {company.name}")
        try:
            research = await self._run_agent_logged(
                agent_name="Research Agent",
                company=company.name,
                call=lambda: self.research_agent.arun(ResearchRequest(company=company)),
                output_type=CompanyResearch,
                tool_calls=[
                    "get_wiki_summary",
                    "get_financial_data",
                    "search_public_finance_for_company",
                    "search_startup_profile_for_company",
                    "search_exa_for_company",
                    "search_web_for_company",
                ],
            )
        except Exception as exc:
            self._current_state.run_log.warnings.append(
                f"{company.name}: Research Agent structured output failed; using direct-tool fallback: {exc}"
            )
            if company.company_type != "public" or not company.ticker:
                return make_fallback_pipeline_result(company, error=str(exc))
            research = self._direct_tool_research_fallback(company, error=str(exc))
        research.financial_snapshot = research.financial_snapshot or build_financial_snapshot(company, research)
        extracted_metrics = await self._extract_financial_metrics(company, research)
        if extracted_metrics:
            research.financial_snapshot = build_financial_snapshot(company, research, extracted_metrics)
        self._current_state.run_log.warnings.extend(validate_research_sources(company, research))
        self._progress(f"Research complete: {company.name}")
        self._progress(f"Analysis started: {company.name}")
        analysis = await self._run_agent_logged(
            agent_name="Analyst Agent",
            company=company.name,
            call=lambda: self.analyst_agent.arun(research),
            output_type=CompanyAnalysis,
        )
        self._progress(f"Analysis complete: {company.name}")
        self._progress(f"Critic review started: {company.name}")
        risk = await self._run_agent_logged(
            agent_name="Critic Agent",
            company=company.name,
            call=lambda: self.critic_agent.arun(CriticInput(research=research, analysis=analysis)),
            output_type=CompanyRisk,
        )
        self._progress(f"Critic review complete: {company.name}")
        return research, analysis, risk

    def _direct_tool_research_fallback(self, company: CompanyIdentity, error: str) -> CompanyResearch:
        sources: list[EvidenceSource] = []
        sources.extend(company.sources)
        sources.extend(fetch_wikipedia_summary(company.name))
        sources.extend(fetch_sec_financial_data(company.name, ticker=company.ticker))
        sources.extend(search_public_finance_sources(company.name, ticker=company.ticker)[:3])

        sources = _dedupe_sources(sources)
        financial_sources = [source for source in sources if _source_quality_for_url(source.url) in {"primary", "secondary"}]
        funding_or_financials = "Not found"
        if financial_sources:
            funding_or_financials = financial_sources[0].snippet

        description_source = next((source for source in sources if source.publisher == "Wikipedia"), None)
        return CompanyResearch(
            name=company.legal_name or company.name,
            url=_normalized_url(company.url),
            company_type=company.company_type,
            ticker=company.ticker,
            business_model=description_source.snippet if description_source else company.description or "Not found",
            products=["Not found"],
            team_size="Not found",
            key_people=["Not found"],
            funding_or_financials=funding_or_financials,
            market_size="Not found",
            recent_news=[f"Research Agent failed structured output: {error}"],
            competitors=["Not found"],
            sources=sources,
        )

    async def _extract_financial_metrics(
        self,
        company: CompanyIdentity,
        research: CompanyResearch,
    ) -> list[FinancialMetricCandidate]:
        sources = _select_financial_sources(research.sources, max_sources=2)
        if not sources:
            self._progress(f"No readable financial source selected: {company.name}")
            return []

        metrics: list[FinancialMetricCandidate] = []
        for source in sources:
            self._progress(f"Reading financial source for {company.name}: {source.publisher or source.url}")
            read_result = read_source_text(source.url, max_chars=16000)
            if not read_result.success or not read_result.text:
                self._current_state.run_log.warnings.append(
                    f"{company.name}: could not read financial source {source.url}: {read_result.error or 'empty text'}"
                )
                continue

            source_quality = _source_quality_for_url(source.url)
            self._progress(f"Extracting financial metrics for {company.name}")
            try:
                result = await self._run_agent_logged(
                    agent_name="Financial Extractor Agent",
                    company=company.name,
                    call=lambda source=source, read_result=read_result, source_quality=source_quality: (
                        self.financial_extractor_agent.arun(
                            FinancialExtractionRequest(
                                company_name=company.name,
                                source_url=source.url,
                                source_quality=source_quality,
                                source_text=read_result.text,
                            )
                        )
                    ),
                    output_type=FinancialExtractionResult,
                    tool_calls=["read_source_text"],
                )
            except Exception as exc:
                self._current_state.run_log.warnings.append(
                    f"{company.name}: financial extraction failed for {source.url}: {exc}"
                )
                continue
            metrics.extend(_valid_metric_candidates(result.metrics, source.url))
        return metrics

    async def _run_agent_logged(
        self,
        agent_name: str,
        company: str,
        call,
        output_type,
        tool_calls: list[str] | None = None,
    ):
        start = time.time()
        success = False
        error = None
        try:
            raw_result = await call()
            result = _coerce_agent_output(raw_result, output_type)
            success = True
            return result
        except asyncio.CancelledError:
            error = "Cancelled"
            raise
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            end = max(time.time(), start + 0.001)
            self._current_state.run_log.agent_runs.append(
                AgentRunLog(
                    agent=agent_name,
                    company=company,
                    start_time=start,
                    end_time=end,
                    tool_calls=tool_calls or [],
                    success=success,
                    error=error,
                )
            )

    def _progress(self, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(message)


def run_live_workflow(
    company_names: list[str],
    auto_confirm: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> WorkflowState:
    workflow = LiveInvestmentResearchWorkflow(
        auto_confirm=auto_confirm,
        progress_callback=progress_callback,
    )
    state = WorkflowState(raw_input=company_names)
    return asyncio.run(workflow.arun(state))


def _coerce_agent_output(raw_result: Any, output_type):
    content = getattr(raw_result, "content", raw_result)
    if output_type is str:
        return str(content)
    if isinstance(content, output_type):
        return content
    if isinstance(content, dict):
        return output_type.model_validate(content)
    if hasattr(content, "model_dump"):
        return output_type.model_validate(content.model_dump())
    raise TypeError(f"Cannot coerce {type(content).__name__} to {output_type.__name__}")


def _select_financial_sources(sources: list[EvidenceSource], max_sources: int = 2) -> list[EvidenceSource]:
    financial_hints = (
        "sec.gov",
        "investor",
        "investors",
        "annualreport",
        "annualreports",
        "finance.yahoo.com",
        "financial",
        "results",
        "ir.",
        "urd.",
    )
    selected: list[EvidenceSource] = []
    seen: set[str] = set()
    for source in sources:
        haystack = f"{source.title} {source.url} {source.publisher or ''}".lower()
        if not any(hint in haystack for hint in financial_hints):
            continue
        if source.url in seen:
            continue
        seen.add(source.url)
        selected.append(source)
        if len(selected) >= max_sources:
            break
    return selected


def _source_quality_for_url(url: str) -> str:
    lowered = url.lower()
    if "sec.gov" in lowered or "investor" in lowered or "annualreport" in lowered or "ir." in lowered or "urd." in lowered:
        return "primary"
    if "finance.yahoo.com" in lowered or "crunchbase.com" in lowered or "cbinsights.com" in lowered:
        return "secondary"
    return "mixed"


def _valid_metric_candidates(
    candidates: list[FinancialMetricCandidate],
    source_url: str,
) -> list[FinancialMetricCandidate]:
    valid: list[FinancialMetricCandidate] = []
    for candidate in candidates:
        if candidate.source_url != source_url:
            candidate = candidate.model_copy(update={"source_url": source_url})
        if not candidate.value or candidate.value == "Not found":
            continue
        valid.append(candidate)
    return valid


def _dedupe_sources(sources: list[EvidenceSource]) -> list[EvidenceSource]:
    result: list[EvidenceSource] = []
    seen: set[str] = set()
    for source in sources:
        if not source.url or source.url in seen:
            continue
        seen.add(source.url)
        result.append(source)
    return result


def _normalized_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return ""
