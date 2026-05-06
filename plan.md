# Implementation Plan

This plan builds the investment research multi-agent system in small verifiable stages. The first MVP should appear by Stage 3 or Stage 4; later stages improve real-world quality, reliability, and demo polish.

## Stage 0 - Project Skeleton

**Goal:** Create the repo structure and runnable Python entrypoint without implementing real agents yet.

**Tasks:**
- Create package structure:
  - `app/agents/`
  - `app/workflows/`
  - `app/schemas/`
  - `app/tools/`
  - `tests/`
  - `data/examples/`
- Add placeholder files:
  - `app/main.py`
  - `app/config.py`
  - `requirements.txt`
  - `.env.example`
  - `README.md`
- Add empty `__init__.py` files where needed.

**Input format:**
```text
No runtime input yet.
```

**Output format:**
```text
Project tree exists and Python can import app modules.
```

**Checkable output:**
```bash
python -m app.main
python -m pytest
```

**Done when:**
- `python -m app.main` runs without import errors.
- `pytest` runs, even if only placeholder/schema tests exist.

**Connects from previous step:** This is the first step.

**Connects to next step:** Stage 1 fills the skeleton with typed schemas and a mock workflow.

---

## Stage 1 - Typed State and Mock Workflow

**Goal:** Prove the full pipeline shape works without LLMs, APIs, or Agno UI.

**Tasks:**
- Define Pydantic schemas in `app/schemas/schemas.py`:
  - `EvidenceSource`
  - `CompanyIdentity`
  - `CompanyResearch`
  - `DimensionScore`
  - `CompanyAnalysis`
  - `CompanyRisk`
  - `AgentRunLog`
  - `RunLog`
  - `WorkflowState`
- Implement `InvestmentResearchWorkflow` in `app/workflows/research_workflow.py`.
- Use fake/mock agent functions that return deterministic schema objects.
- Implement a simple final mock memo string.

**Input format:**
```python
WorkflowState(
    raw_input=["Nvidia", "AMD", "Intel"]
)
```

**Output format:**
```python
WorkflowState(
    raw_input=[...],
    confirmed_companies=[CompanyIdentity, ...],
    research=[CompanyResearch, ...],
    analysis=[CompanyAnalysis, ...],
    risks=[CompanyRisk, ...],
    memo="# Investment Recommendation Memo\n...",
    run_log=RunLog(...)
)
```

**Checkable output:**
```bash
python -m app.main --mock "Nvidia,AMD,Intel"
python -m pytest tests/test_workflow
```

**Done when:**
- `len(confirmed_companies) == len(raw_input)`.
- `len(research) == len(raw_input)`.
- `len(analysis) == len(raw_input)`.
- `len(risks) == len(raw_input)`.
- `memo` contains:
  - `# Investment Recommendation Memo`
  - `Invest in:`
  - `## Sources`
- `run_log` contains one entry per mock agent run.

**Connects from previous step:** Uses the directory structure and entrypoint from Stage 0.

**Connects to next step:** Stage 2 replaces fake workflow interaction with Agno Agent OS demo flow while keeping the same schemas.

---

## Stage 2 - Agent OS MVP Demo with Mock Agents

**Goal:** Make the system demoable in Agno Agent OS before connecting real LLM/tools.

**Tasks:**
- Add Agno workflow/agent wiring around the existing mock pipeline.
- Expose a demo entrypoint for Agent OS.
- Support entering company names from UI.
- Add a simple confirmation step for resolved identities.
- Keep mock outputs deterministic so the demo is stable.

**Input format:**
```text
Nvidia, AMD, Intel
```

or:

```json
{
  "companies": ["Nvidia", "AMD", "Intel"]
}
```

**Output format:**
```markdown
# Investment Recommendation Memo

## Executive Summary
...

## Recommendation
**Invest in: Nvidia**
...

## Sources
[1] Mock source - https://example.com/source
```

**Checkable output:**
```bash
python -m app.agent_os
```

Then in the UI:
- Enter company names.
- Confirm identities.
- Receive a final memo.

For automated checks without starting a long-running server:

```bash
python -m pytest tests/test_agent_os.py
```

**Done when:**
- Agent OS can launch.
- A user can run the 3-company demo from the UI.
- The final memo appears in the UI.
- The same workflow can still be run from CLI for debugging.

**Connects from previous step:** Reuses Stage 1 schemas and mock workflow behavior.

**Connects to next step:** Stage 3 swaps mock agents for real Agno `Agent` definitions using OpenAI or DeepSeek.

---

## Stage 3 - Real LLM Agents

**Goal:** Replace mock agent logic with real LLM-backed agents while keeping tools mocked or fixture-based.

**Tasks:**
- Implement `app/config.py`:
  - `LLM_PROVIDER=openai` by default
  - `get_worker_model()`
  - `get_reasoning_model()`
- Implement agent files:
  - `app/agents/identity_agent.py`
  - `app/agents/research_agent.py`
  - `app/agents/analyst_agent.py`
  - `app/agents/critic_agent.py`
  - `app/agents/decision_agent.py`
- Use OpenAI default:
  - Identity/Research: `gpt-4.1-mini`
  - Analyst/Critic/Decision: `gpt-4.1`
- Add DeepSeek as optional provider:
  - Identity/Research: `deepseek-chat`
  - Analyst/Critic: `deepseek-reasoner`
  - Decision: `deepseek-chat`
- Configure Pydantic `response_model` for Identity, Research, Analyst, and Critic.

**Input format:**
```python
IdentityRequest(company_name="Nvidia")
ResearchRequest(company=CompanyIdentity(...))
CompanyResearch(...)
CompanyAnalysis(...)
```

**Output format:**
```python
CompanyIdentity(...)
CompanyResearch(...)
CompanyAnalysis(...)
CompanyRisk(...)
memo: str
```

**Checkable output:**
```bash
python -m app.main --provider openai --fixture
python -m pytest tests/test_agents
```

**Done when:**
- Each LLM-backed agent returns the expected schema.
- Invalid structured output retries or falls back cleanly.
- The pipeline still runs end-to-end using fixture research data.

**MVP checkpoint:** At this point, the project has a clear multi-agent architecture, typed state, Agent OS demo path, and real LLM agents. This is the minimum viable submission if tool integration needs more time.

**Connects from previous step:** Replaces Stage 2 mock agents while preserving the same workflow and UI flow.

**Connects to next step:** Stage 4 gives the Research Agent real external evidence sources.

---

## Stage 4 - Real Research Tools and Citations

**Goal:** Let Research Agent gather real company evidence and pass source citations into the final memo.

**Tasks:**
- Implement tool utility:
  - `app/tools/_utils.py`
  - `clean_text(raw: str, max_chars: int) -> str`
- Implement Wikipedia tool:
  - returns `list[EvidenceSource]`
- Implement SEC EDGAR tool:
  - resolves ticker/company name to CIK
  - calls SEC companyfacts
  - parses useful financial facts before truncation
  - returns `list[EvidenceSource]`
  - Implement Exa search tool:
    - `app/tools/exa_search.py`
    - calls Exa REST `/search`
    - returns compact `EvidenceSource` items
    - requires `EXA_API_KEY`
  - Keep DuckDuckGo Instant Answer as a no-key fallback:
    - `app/tools/web_search.py`
    - useful for smoke tests, not high-quality recent news
- Ensure all major research claims are backed by `CompanyResearch.sources`.
- Update Decision Agent prompt to include citations in `## Sources`.

**Input format:**
```python
ResearchRequest(
    company=CompanyIdentity(
        name="Nvidia",
        url="https://www.nvidia.com",
        ticker="NVDA",
        company_type="public",
        description="GPU and AI infrastructure company",
    )
)
```

**Output format:**
```python
CompanyResearch(
    name="Nvidia",
    url="https://www.nvidia.com",
    company_type="public",
    ticker="NVDA",
    business_model="...",
    products=[...],
    funding_or_financials="...",
    market_size="...",
    recent_news=[...],
    competitors=[...],
    sources=[
        EvidenceSource(
            title="...",
            url="https://...",
            publisher="...",
            date="...",
            snippet="..."
        )
    ]
)
```

**Checkable output:**
```bash
python -m pytest tests/test_tools
python -c "from app.agents import research_agent; print([tool.name for tool in research_agent.tools])"
```

**Done when:**
- Research Agent has tools: Wikipedia, SEC EDGAR, Exa search, and fallback web search.
- Tool unit tests pass with mocked HTTP responses.
- Public companies can use SEC EDGAR when ticker/CIK is available.
- Private/startup companies gracefully show missing financials when no official data exists.
- Exa returns `[]` when `EXA_API_KEY` is missing instead of crashing.
- Stable demo still runs on mock workflow data until the live workflow is enabled.

**Connects from previous step:** Uses real Research Agent from Stage 3 and attaches live evidence tools. It does not replace the stable mock workflow yet.

**Connects to next step:** Stage 5 strengthens failures and edge cases around these real tools.

---

## Stage 5 - Reliability and Error Handling

**Goal:** Make the system robust enough for a repeatable graded demo.

**Tasks:**
- Add fallback constructors:
  - `make_fallback_research(company, error)`
  - `make_fallback_analysis(research, error)`
  - `make_fallback_risk(research, analysis, error)`
  - `make_fallback_pipeline_result(company, error)`
- Use `asyncio.gather(..., return_exceptions=True)`.
- Ensure failed company pipelines are not dropped.
- Add tool retry logic for empty search/SEC results.
- Add per-agent `max_retries`.
- Add tool call limits and token budget guard.
- Add warnings to `RunLog`.

**Input format:**
```python
WorkflowState(
    raw_input=["Nvidia", "UnknownStartup", "AMD"],
    confirmed_companies=[...]
)
```

**Output format:**
```python
WorkflowState(
    research=[
        CompanyResearch(...),
        CompanyResearch(name="UnknownStartup", business_model="Not found", ...),
        CompanyResearch(...)
    ],
    run_log=RunLog(
        warnings=["UnknownStartup: search failed after retries"]
    ),
    memo="..."
)
```

**Checkable output:**
```bash
python -m pytest tests/test_workflow/test_resilience.py
```

**Done when:**
- One tool failure does not crash the workflow.
- One company failure does not remove that company from the final comparison.
- Memo surfaces data gaps instead of hiding them.
- `run_log.warnings` records failures clearly.
- `python -m pytest tests/test_resilience.py` passes.

**Connects from previous step:** Hardens the live tool and LLM behavior introduced in Stages 3 and 4.

**Connects to next step:** Stage 6 connects the real LLM-backed agents into a live end-to-end workflow.

---

## Stage 6 - Live Agent Workflow

**Goal:** Run the full multi-agent pipeline with real Agno agents instead of mock data, while keeping the stable mock workflow as a fallback demo path.

**Tasks:**
- Add `app/workflows/live_research_workflow.py`.
- Implement live pipeline:
  - Identity Agent resolves each raw company name.
  - Workflow confirms or auto-confirms identities for CLI testing.
  - Research Agent gathers real evidence using attached tools.
  - Analyst Agent produces `CompanyAnalysis`.
  - Critic Agent produces `CompanyRisk`.
  - Decision Agent writes the final memo.
- Reuse Stage 5 fallback constructors so failed companies remain in the final comparison.
- Add a CLI flag:
  - `python -m app.main --live "Nvidia,AMD,Intel"`
- Add an AgentOS route:
  - `POST /demo/live-research`
- Keep the existing mock route:
  - `POST /demo/mock-research`
- Add tests that mock LLM agent calls so CI does not spend API credits.
- Add one optional manual smoke-test command for real OpenAI/Exa credentials.

**Input format:**
```bash
python -m app.main --live "Nvidia,AMD,Intel"
```

or:

```json
{
  "companies": ["Nvidia", "AMD", "Intel"],
  "auto_confirm": true
}
```

**Output format:**
```python
WorkflowState(
    raw_input=["Nvidia", "AMD", "Intel"],
    confirmed_companies=[CompanyIdentity(...), ...],
    research=[CompanyResearch(...), ...],
    analysis=[CompanyAnalysis(...), ...],
    risks=[CompanyRisk(...), ...],
    memo="# Investment Recommendation Memo\n...",
    run_log=RunLog(...)
)
```

The HTTP route returns:

```json
{
  "memo": "# Investment Recommendation Memo\n...",
  "state": {
    "confirmed_companies": [...],
    "research": [...],
    "analysis": [...],
    "risks": [...],
    "run_log": {...}
  }
}
```

**Checkable output:**
```bash
python -m pytest tests/test_live_workflow.py
python -m pytest
```

Manual smoke test with real credentials:

```bash
python -m app.main --live "Nvidia,AMD,Intel"
```

Required environment for real smoke test:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=...
EXA_API_KEY=...
```

**Done when:**
- The live workflow can run with mocked agent calls in tests.
- The live workflow can run manually with real `OPENAI_API_KEY`.
- Research Agent uses real tools when the LLM chooses them.
- The final memo is produced by Decision Agent, not by mock string formatting.
- A failed company produces fallback typed objects and does not cancel the whole run.
- Mock workflow remains available and stable.

**Connects from previous step:** Uses Stage 3 real agent definitions, Stage 4 real tools, and Stage 5 fallback/retry behavior.

**Connects to next step:** Stage 7 turns the working live system into a polished, repeatable submission.

---

## Stage 7 - Observability, Examples, and README Polish

**Goal:** Improve scoring on observability, product judgment, explanation clarity, and repeatability.

**Tasks:**
- Record per-agent run logs:
  - agent name
  - company
  - start time
  - end time
  - latency
  - tool calls
  - success/failure
  - error
- Save demo artifacts:
  - `data/examples/nvidia_amd_intel/workflow_state.json`
  - `data/examples/nvidia_amd_intel/memo.md`
- Update README:
  - setup
  - API keys
  - Agent OS demo command
  - CLI fallback command
  - architecture summary
  - agent responsibilities
  - known limitations
  - reliability strategy
  - AI-assisted development notes
- Add `demo/demo.md` with a step-by-step demo script.

**Input format:**
```bash
python -m app.main --provider openai "Nvidia,AMD,Intel" --save-example
```

**Output format:**
```text
data/examples/nvidia_amd_intel/
├── workflow_state.json
└── memo.md
```

**Checkable output:**
```bash
python -m pytest
python -m app.main --provider openai "Nvidia,AMD,Intel" --save-example
```

**Done when:**
- Example output is committed.
- README explains how to run and why the architecture is multi-agent.
- Demo can be repeated without guessing commands.
- Run logs make latency and failures visible.

**Connects from previous step:** Uses the live workflow from Stage 6 and the stable mock workflow to generate repeatable demo artifacts.

**Connects to next step:** Optional future improvements can build on this stable baseline.

---

## MVP Boundary

The MVP should include:

1. Stage 0 - Project Skeleton
2. Stage 1 - Typed State and Mock Workflow
3. Stage 2 - Agent OS MVP Demo with Mock Agents
4. Stage 3 - Real LLM Agents

This MVP proves:
- the system runs end-to-end,
- the multi-agent decomposition is real,
- the handoffs are typed,
- the demo path exists,
- and the framework is ready for real research tools.

Stages 4-7 improve citation quality, reliability, live execution, observability, and final presentation.
