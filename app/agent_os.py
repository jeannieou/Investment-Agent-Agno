"""Agno AgentOS demo app for the Stage 2 mock workflow."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, AsyncIterator

from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from agno.run.workflow import StepCompletedEvent
from agno.workflow import Workflow
from agno.workflow.types import WorkflowExecutionInput
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agents import analyst_agent, critic_agent, decision_agent, financial_extractor_agent, identity_agent, research_agent
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


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _content_event(content: str, step_name: str = "Progress") -> StepCompletedEvent:
    return StepCompletedEvent(step_name=step_name, content=content)


def _progress_output(message: str) -> StepCompletedEvent:
    print_agentos_progress(message)
    return _content_event(f"**Progress:** {message}\n\n")


def _identity_summary(state: WorkflowState) -> str:
    rows = "\n".join(
        f"| {company.raw_input} | {company.name} | {company.ticker or 'N/A'} | "
        f"{'Yes' if company.is_investable_entity else 'No'} | {company.confidence} |"
        for company in state.confirmed_companies
    )
    return (
        "## Identity Resolution\n\n"
        "| User Input | Resolved Entity | Ticker | Investable? | Confidence |\n"
        "|---|---|---|---:|---|\n"
        f"{rows}\n\n"
    )


async def run_mock_research_for_agentos(
    workflow: Workflow,
    execution_input: WorkflowExecutionInput,
) -> AsyncIterator[StepCompletedEvent]:
    try:
        companies = normalize_companies(execution_input.input)
    except ValueError as exc:
        yield _content_event(_agentos_usage_header() + f"Cannot start workflow: {exc}", step_name="Input Validation")
        return

    yield _content_event(_agentos_usage_header(), step_name="Usage")
    yield _progress_output(f"Starting mock workflow for {', '.join(companies)}")
    yield _progress_output("Resolving company identities")
    state = WorkflowState(raw_input=companies)
    state = await InvestmentResearchWorkflow().arun(state)
    yield _content_event(_identity_summary(state), step_name="Identity Resolution")
    yield _progress_output("Searching financial and company evidence")
    yield _progress_output("Analyzing market, competition, growth, and business model")
    yield _progress_output("Reviewing risks and data gaps")
    yield _progress_output("Comparing companies and writing final memo")
    yield _progress_output("Mock workflow complete")
    yield _content_event(state.memo, step_name="Final Memo")


async def run_live_research_for_agentos(
    workflow: Workflow,
    execution_input: WorkflowExecutionInput,
) -> AsyncIterator[StepCompletedEvent]:
    try:
        companies = normalize_companies(execution_input.input)
    except ValueError as exc:
        yield _content_event(_agentos_usage_header() + f"Cannot start workflow: {exc}", step_name="Input Validation")
        return

    yield _content_event(_agentos_usage_header(), step_name="Usage")
    yield _progress_output(f"Starting live workflow for {', '.join(companies)}")

    queue: asyncio.Queue[str] = asyncio.Queue()

    def queue_progress(message: str) -> None:
        print_agentos_progress(message)
        queue.put_nowait(message)

    state = WorkflowState(raw_input=companies)
    task = asyncio.create_task(
        LiveInvestmentResearchWorkflow(progress_callback=queue_progress).arun(state)
    )

    while not task.done():
        try:
            message = await asyncio.wait_for(queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        yield _content_event(f"**Progress:** {message}\n\n")

    state = await task

    while not queue.empty():
        yield _content_event(f"**Progress:** {queue.get_nowait()}\n\n")

    yield _content_event(_identity_summary(state), step_name="Identity Resolution")
    yield _content_event(state.memo, step_name="Final Memo")


mock_research_workflow = Workflow(
    id="mock-investment-research",
    name="Mock Investment Research",
    description=f"Runs the deterministic mock investment workflow. {usage_note()}",
    steps=run_mock_research_for_agentos,
    stream=True,
    stream_events=True,
)


live_research_workflow = Workflow(
    id="live-investment-research",
    name="Live Investment Research",
    description=f"Runs the live Agno-agent investment research workflow. {usage_note()}",
    steps=run_live_research_for_agentos,
    stream=True,
    stream_events=True,
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


@base_app.get("/demo/live-research/stream")
async def stream_live_research(companies: str = "Nvidia,AMD,Intel"):
    try:
        company_names = normalize_companies(companies)
    except ValueError as exc:
        async def error_stream():
            yield _sse_event("error", {"message": str(exc)})

        return StreamingResponse(error_stream(), media_type="text/event-stream")

    async def event_stream():
        yield _sse_event("usage", {"message": usage_note()})
        yield _sse_event("progress", {"message": f"Starting live workflow for {', '.join(company_names)}"})

        queue: asyncio.Queue[str] = asyncio.Queue()

        def queue_progress(message: str) -> None:
            print_agentos_progress(message)
            queue.put_nowait(message)

        state = WorkflowState(raw_input=company_names)
        task = asyncio.create_task(
            LiveInvestmentResearchWorkflow(progress_callback=queue_progress).arun(state)
        )

        try:
            while not task.done():
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    yield _sse_event("heartbeat", {"message": "working"})
                    continue
                yield _sse_event("progress", {"message": message})

            state = await task
            while not queue.empty():
                yield _sse_event("progress", {"message": queue.get_nowait()})

            yield _sse_event(
                "identity",
                {
                    "companies": [
                        {
                            "raw_input": company.raw_input,
                            "name": company.name,
                            "ticker": company.ticker,
                            "investable": company.is_investable_entity,
                            "confidence": company.confidence,
                            "note": company.resolution_note,
                        }
                        for company in state.confirmed_companies
                    ]
                },
            )
            yield _sse_event("memo", {"memo": state.memo})
            yield _sse_event("done", {"message": "complete"})
        except Exception as exc:
            yield _sse_event("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@base_app.get("/demo/live-stream", response_class=HTMLResponse)
def live_stream_page() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Live Investment Research Stream</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 32px; color: #222; }
    form { display: flex; gap: 8px; margin-bottom: 20px; }
    input { flex: 1; padding: 10px 12px; font-size: 15px; }
    button { padding: 10px 14px; font-size: 15px; }
    #events { border-left: 4px solid #ddd; padding-left: 14px; margin-bottom: 24px; }
    .event { margin: 8px 0; line-height: 1.4; }
    .progress { color: #333; }
    .error { color: #b00020; font-weight: 700; }
    pre { white-space: pre-wrap; background: #f7f7f7; padding: 16px; border-radius: 6px; }
    table { border-collapse: collapse; margin: 12px 0; }
    td, th { border: 1px solid #ddd; padding: 6px 8px; }
  </style>
</head>
<body>
  <h1>Live Investment Research Stream</h1>
  <form id="form">
    <input id="companies" value="AMC,Regal" />
    <button type="submit">Run</button>
  </form>
  <div id="events"></div>
  <h2>Memo</h2>
  <pre id="memo"></pre>
  <script>
    const form = document.getElementById("form");
    const events = document.getElementById("events");
    const memo = document.getElementById("memo");
    let source = null;

    function append(kind, text) {
      const div = document.createElement("div");
      div.className = "event " + kind;
      div.textContent = text;
      events.appendChild(div);
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (source) source.close();
      events.innerHTML = "";
      memo.textContent = "";
      const companies = encodeURIComponent(document.getElementById("companies").value);
      source = new EventSource(`/demo/live-research/stream?companies=${companies}`);

      source.addEventListener("usage", (event) => append("progress", JSON.parse(event.data).message));
      source.addEventListener("progress", (event) => append("progress", JSON.parse(event.data).message));
      source.addEventListener("heartbeat", () => append("progress", "working..."));
      source.addEventListener("identity", (event) => {
        const data = JSON.parse(event.data);
        append("progress", "Identity resolved: " + data.companies.map((c) => `${c.raw_input} -> ${c.name}${c.ticker ? " (" + c.ticker + ")" : ""}`).join("; "));
      });
      source.addEventListener("memo", (event) => { memo.textContent = JSON.parse(event.data).memo; });
      source.addEventListener("done", () => { append("progress", "complete"); source.close(); });
      source.addEventListener("error", (event) => {
        append("error", event.data ? JSON.parse(event.data).message : "stream error");
        source.close();
      });
    });
  </script>
</body>
</html>
"""


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
    agents=[identity_agent, research_agent, financial_extractor_agent, analyst_agent, critic_agent, decision_agent],
    workflows=[mock_research_workflow, live_research_workflow],
    base_app=base_app,
    tracing=False,
)

app = agent_os.get_app()


def main() -> None:
    agent_os.serve(app="app.agent_os:app", reload=True)


if __name__ == "__main__":
    main()
