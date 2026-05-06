"""Live LLM-backed investment research workflow."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from app.agents import analyst_agent, critic_agent, decision_agent, identity_agent, research_agent
from app.schemas import (
    AgentRunLog,
    CompanyAnalysis,
    CompanyIdentity,
    CompanyResearch,
    CompanyRisk,
    CriticInput,
    DecisionInput,
    IdentityRequest,
    ResearchRequest,
    WorkflowState,
)
from app.workflows.research_workflow import make_fallback_pipeline_result


class LiveInvestmentResearchWorkflow:
    """Runs the real Agno agents while preserving typed workflow state."""

    def __init__(
        self,
        identity=identity_agent,
        research=research_agent,
        analyst=analyst_agent,
        critic=critic_agent,
        decision=decision_agent,
        auto_confirm: bool = True,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.identity_agent = identity
        self.research_agent = research
        self.analyst_agent = analyst
        self.critic_agent = critic
        self.decision_agent = decision
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
            state.confirmed_companies.append(identity)
            self._progress(f"Resolved identity: {identity.name}")

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
        decision_input = DecisionInput(research=state.research, analysis=state.analysis, risks=state.risks)
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
        research = await self._run_agent_logged(
            agent_name="Research Agent",
            company=company.name,
            call=lambda: self.research_agent.arun(ResearchRequest(company=company)),
            output_type=CompanyResearch,
            tool_calls=["get_wiki_summary", "get_financial_data", "search_exa_for_company", "search_web_for_company"],
        )
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
