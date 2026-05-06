"""Agno AgentOS demo app for the Stage 2 mock workflow."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from agno.workflow import Workflow
from agno.workflow.types import WorkflowExecutionInput
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.agents import analyst_agent, critic_agent, decision_agent, identity_agent, research_agent
from app.config import get_settings
from app.limits import DEFAULT_COMPANIES, parse_company_names, usage_note, validate_company_limit
from app.schemas import CompanyIdentity, WorkflowState
from app.workflows import InvestmentResearchWorkflow, LiveInvestmentResearchWorkflow, run_live_workflow, run_mock_workflow


DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
agent_os_db = SqliteDb(db_file=str(DATA_DIR / "agent_os.db"), id="agent-os-sqlite")


class MockResearchRequest(BaseModel):
    companies: list[str] = Field(default_factory=lambda: [*DEFAULT_COMPANIES])
    auto_confirm: bool = True


class MockResearchResponse(BaseModel):
    memo: str
    state: WorkflowState


class ResolveCompaniesResponse(BaseModel):
    confirmed_companies: list[CompanyIdentity]


def print_agentos_progress(message: str) -> None:
    print(f"[agentos progress] {message}", flush=True)


def normalize_companies(input_value: Any) -> list[str]:
    if input_value is None:
        return [*DEFAULT_COMPANIES]
    if isinstance(input_value, MockResearchRequest):
        return validate_company_limit(input_value.companies or [*DEFAULT_COMPANIES])
    if isinstance(input_value, str):
        stripped = input_value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return normalize_companies(json.loads(stripped))
            except json.JSONDecodeError:
                pass
        return validate_company_limit(parse_company_names(input_value) or [*DEFAULT_COMPANIES])
    if isinstance(input_value, list):
        companies = [str(item).strip() for item in input_value if str(item).strip()]
        return validate_company_limit(companies or [*DEFAULT_COMPANIES])
    if isinstance(input_value, dict):
        companies = input_value.get("companies", [])
        if isinstance(companies, str):
            return validate_company_limit(parse_company_names(companies) or [*DEFAULT_COMPANIES])
        companies = [str(item).strip() for item in companies if str(item).strip()]
        return validate_company_limit(companies or [*DEFAULT_COMPANIES])
    return [*DEFAULT_COMPANIES]


def _agentos_usage_header() -> str:
    return f"> {usage_note()}\n\n"


async def run_mock_research_for_agentos(workflow: Workflow, execution_input: WorkflowExecutionInput) -> str:
    try:
        companies = normalize_companies(execution_input.input)
    except ValueError as exc:
        return _agentos_usage_header() + f"Cannot start workflow: {exc}"
    print_agentos_progress(f"Running mock workflow for {', '.join(companies)}")
    state = WorkflowState(raw_input=companies)
    state = await InvestmentResearchWorkflow().arun(state)
    print_agentos_progress("Mock workflow complete")
    return _agentos_usage_header() + state.memo


async def run_live_research_for_agentos(workflow: Workflow, execution_input: WorkflowExecutionInput) -> str:
    try:
        companies = normalize_companies(execution_input.input)
    except ValueError as exc:
        return _agentos_usage_header() + f"Cannot start workflow: {exc}"
    state = WorkflowState(raw_input=companies)
    state = await LiveInvestmentResearchWorkflow(progress_callback=print_agentos_progress).arun(state)
    return _agentos_usage_header() + state.memo


mock_research_workflow = Workflow(
    id="mock-investment-research",
    name="Mock Investment Research",
    description=f"Runs the deterministic mock investment workflow. {usage_note()}",
    steps=run_mock_research_for_agentos,
)


live_research_workflow = Workflow(
    id="live-investment-research",
    name="Live Investment Research",
    description=f"Runs the live Agno-agent investment research workflow. {usage_note()}",
    steps=run_live_research_for_agentos,
)


base_app = FastAPI(title="Investment Research AgentOS Demo")


@base_app.middleware("http")
async def log_agentos_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    if request.url.path.startswith(("/workflows", "/agents", "/demo")):
        duration = time.time() - start
        print(
            f"[agentos request] {request.method} {request.url.path} -> {response.status_code} "
            f"({duration:.2f}s)",
            flush=True,
        )
    return response


@base_app.get("/demo/health")
def demo_health() -> dict[str, str]:
    return {"status": "ok"}


@base_app.get("/demo/config")
def demo_config() -> dict[str, object]:
    settings = get_settings()
    return {
        "llm_provider": settings.llm_provider,
        "openai_api_key_set": bool(settings.openai_api_key),
        "exa_api_key_set": bool(settings.exa_api_key),
        "openai_worker_model": settings.openai_worker_model,
        "openai_reasoning_model": settings.openai_reasoning_model,
    }


@base_app.post("/demo/mock-research", response_model=MockResearchResponse)
def run_mock_research(request: MockResearchRequest) -> MockResearchResponse:
    try:
        companies = validate_company_limit(request.companies)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    state = run_mock_workflow(companies)
    return MockResearchResponse(memo=state.memo, state=state)


@base_app.post("/demo/live-research", response_model=MockResearchResponse)
def run_live_research(request: MockResearchRequest) -> MockResearchResponse:
    try:
        companies = validate_company_limit(request.companies)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    state = run_live_workflow(
        companies,
        auto_confirm=request.auto_confirm,
        progress_callback=print_agentos_progress,
    )
    return MockResearchResponse(memo=state.memo, state=state)


@base_app.post("/demo/resolve", response_model=ResolveCompaniesResponse)
def resolve_companies(request: MockResearchRequest) -> ResolveCompaniesResponse:
    try:
        companies = validate_company_limit(request.companies)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    workflow = InvestmentResearchWorkflow()
    identities = [workflow._mock_identity(company) for company in companies]
    return ResolveCompaniesResponse(confirmed_companies=identities)


agent_os = AgentOS(
    name="Investment Research Multi-Agent Demo",
    description="AgentOS wrapper for the deterministic mock investment research workflow.",
    db=agent_os_db,
    agents=[identity_agent, research_agent, analyst_agent, critic_agent, decision_agent],
    workflows=[mock_research_workflow, live_research_workflow],
    base_app=base_app,
    tracing=False,
)

app = agent_os.get_app()


def main() -> None:
    agent_os.serve(app="app.agent_os:app", reload=True)


if __name__ == "__main__":
    main()
