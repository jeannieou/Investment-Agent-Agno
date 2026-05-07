# Option C： Investment Research Multi-Agent System

Agno-based multi-agent system for researching companies and producing an investment recommendation memo with cited sources.

Current phase: **Stage 7 complete**. The repo includes a stable no-key mock demo, live OpenAI/DeepSeek-backed agents, real research tools, AgentOS UI wiring, run logs, and saved example artifacts.

# Demo Video Link:

https://youtu.be/nWVp4i-ABZY

## What It Does

Input:

```text
Nvidia, AMD, Intel
```

Output:

```markdown
# Investment Recommendation Memo

## Executive Summary
...

## Recommendation
**Invest in: ...**

## Sources
[1] ...
```

The default demo uses three public companies because it is easy to evaluate, but the schemas and workflow support arbitrary company lists, including public companies, private companies, and startups.

For live runs, use **6 or fewer companies** for best memo quality. The system enforces a hard limit of **8 companies** to control token cost, latency, and final memo quality.

## Architecture

The system uses deterministic orchestration plus separate LLM-backed agents:

1. **Identity Agent** resolves raw company names into canonical company identities.
2. **Research Agent** gathers facts and source citations for one company.
3. **Analyst Agent** scores one company across investment dimensions.
4. **Critic Agent** challenges assumptions and identifies risks.
5. **Decision Agent** compares all companies and writes the final memo.

The workflow owns sequencing, parallel execution, state passing, retries, fallbacks, and observability. Agents do not call each other directly.

```text
User input
  -> Identity confirmation
  -> Research / Analyst / Critic per company
  -> Decision Agent
  -> memo.md + workflow_state.json + run_log.json
```

See [architecture.md](./architecture.md) for the full design.

## Project Structure

```text
app/
  agent_os.py                    # AgentOS server wiring, demo routes, and workflow registration.
  config.py                      # Environment loading and model/provider configuration.
  examples.py                    # Helpers for saving repeatable example artifacts.
  limits.py                      # Company-count parsing and validation limits.
  main.py                        # CLI entry point for mock and live workflow runs.

  agents/
    identity_agent.py            # Resolves user input into canonical company identities.
    research_agent.py            # Collects non-financial company facts and source evidence.
    financial_extractor_agent.py # Extracts financial metrics from readable financial source text.
    analyst_agent.py             # Scores companies across investment dimensions.
    critic_agent.py              # Reviews assumptions, risks, and missing evidence.
    decision_agent.py            # Writes the final cross-company recommendation memo.

  schemas/
    schemas.py                   # Pydantic models for typed agent handoffs and workflow state.

  tools/
    entity_resolution.py         # Adds deterministic identity enrichment and brand-parent hints.
    exa_search.py                # Exa-backed public web search tool.
    finance_search.py            # Finance/startup-oriented search wrappers.
    financial_snapshot.py        # Builds normalized financial snapshots from source evidence.
    sec_edgar.py                 # SEC EDGAR lookup and company facts extraction.
    source_reader.py             # Reads HTML/PDF source text for financial extraction.
    web_search.py                # Lightweight fallback web search.
    wikipedia.py                 # Wikipedia summary lookup and title candidate generation.

  workflows/
    research_workflow.py         # Stable mock workflow and fallback typed objects.
    live_research_workflow.py    # Live async orchestration, parallel company pipelines, and run logs.

data/
  examples/                      # Saved demo outputs: memo, workflow state, and run log JSON.
  agent_os.db                    # Local AgentOS session database.

demo/
  demo.md                        # Repeatable demo script.

tests/                           # Unit tests for schemas, tools, workflows, AgentOS, and resilience.
architecture.md                  # System design notes.
plan.md                          # Stage roadmap and future implementation plan.
requirements.txt                 # Python dependencies.
README.md                        # Project overview and usage instructions.
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy environment values:

```bash
copy .env.example .env
```

Minimal `.env` for mock demo:

```bash
LLM_PROVIDER=openai
AGNO_DEBUG=false
AGNO_DEBUG_LEVEL=1
```

Live demo credentials:

```bash
OPENAI_API_KEY=...
EXA_API_KEY=...
```

DeepSeek is available as an optional lower-cost provider:

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
```

## Run

### Stable mock CLI, no API keys:

```bash
python -m app.main --mock "Nvidia,AMD,Intel"
```

Save repeatable example artifacts:

```bash
python -m app.main --mock --save-example "Nvidia,AMD,Intel"
```

### Live CLI with real agents:

```bash
python -m app.main --live --provider openai "Nvidia,AMD,Intel"
```

### AgentOS server UI:

```bash
python -m app.agent_os
```

Then open:

```text
https://os.agno.com/
```
Use `Live Investment Research` only when `OPENAI_API_KEY` or `DEEPSEEK_API_KEY` and `EXA_API_KEY` is configured.

Use `Mock Investment Research` for the no-key demo. Enter:

```text
Nvidia,AMD,Intel
```

AgentOS workflow output starts with a short usage note:

```text
Usage: enter up to 6 company names for best memo quality (hard limit: 8).
```



## API Smoke Tests

```bash
curl http://localhost:7777/demo/health
curl http://localhost:7777/workflows
curl -X POST http://localhost:7777/demo/mock-research ^
  -H "Content-Type: application/json" ^
  -d "{\"companies\":[\"Nvidia\",\"AMD\",\"Intel\"]}"
```

## Example Artifacts

The committed Stage 7 example lives at:

```text
data/examples/nvidia_amd_intel/
  memo.md
  workflow_state.json
  run_log.json
```

`workflow_state.json` contains typed handoffs across agents. `run_log.json` contains per-agent observability data.

## Observability

Each agent run records:

- agent name
- company name
- start and end timestamps
- latency
- tool calls
- success/failure
- error message

The workflow-level run log also records:

- `total_latency_seconds`: user-visible wall-clock runtime
- `cumulative_agent_latency_seconds`: sum of all agent run durations, including parallel work
- `identity_latency_seconds`: time spent resolving company identities
- `parallel_pipeline_latency_seconds`: slowest per-company Research -> Analyst -> Critic pipeline
- `decision_latency_seconds`: final memo generation time
- `company_pipeline_latency_seconds`: per-company pipeline latency breakdown

AgentOS runs also print progress in the backend terminal:

```text
[agentos progress] Resolving identity: Nvidia
[agentos progress] Research started: Nvidia
[agentos progress] Writing final recommendation memo
```

For more backend detail:

```bash
AGNO_DEBUG=true
AGNO_DEBUG_LEVEL=2
```

Restart `python -m app.agent_os` after changing `.env`.

## Reliability

- Pydantic schemas define all inter-agent handoffs.
- `CompanyAnalysis.overall_score` is computed from dimension scores.
- Tool outputs are compact evidence objects, not raw HTML.
- Missing data is represented as `"Not found"` instead of invented.
- Failed company pipelines produce fallback typed objects.
- Parallel workflow execution uses `return_exceptions=True`.
- External tools retry and return empty evidence instead of crashing.
- The final memo surfaces data gaps and cites available sources.

## Tests

```bash
pytest
```

The test suite mocks live agent behavior, so it does not spend API credits.

## Known Limitations

- The stable AgentOS demo uses deterministic mock data to guarantee repeatability.
- Live output quality depends on model behavior and available web evidence.
- SEC EDGAR covers public companies; private companies and startups rely on web/funding sources.
- Exa improves live research quality, but the workflow can degrade without `EXA_API_KEY`.
- The current AgentOS UI progress is mostly visible in backend logs; richer in-UI step progress would require refactoring the live workflow into native multi-step UI events.

## AI-Assisted Development Notes

The project was built iteratively with AI assistance, but implementation choices are owned in code:

- typed schemas were added before LLM calls,
- the mock workflow stayed available as a stable demo path,
- live agents were added behind explicit flags,
- failure paths were tested with mocked agent/tool failures,
- AgentOS UI issues were debugged through real HTTP, WebSocket, and session routes.

See [demo/demo.md](./demo/demo.md) for a repeatable demo script.

## Brief Build Notes

- Used Codex to draft agent prompts, schemas, workflow code, tests, and documentation.
- Used AI tools to speed up boilerplate creation for Pydantic models, Agno agent definitions, and pytest fixtures.
- Used AI assistance to compare design options for deterministic workflows versus agent-led orchestration.
- Used AI to generate first-pass implementations for source search, SEC EDGAR lookup, financial snapshots, and AgentOS demo wiring.
- AI was useful for quickly identifying likely failure paths, such as missing data, malformed structured outputs, and cross-company pipeline failures.
- AI output needed correction when company identity resolution was too optimistic, especially for brand-to-parent mappings and ambiguous tickers.
- AI-generated research logic needed tighter source validation to avoid treating weak or mismatched search results as reliable evidence.
- Structured output handling required manual debugging because LLMs sometimes returned strings instead of the expected Pydantic schema.
- AgentOS UI behavior required hands-on debugging with real server logs and HTTP routes because workflow progress did not render exactly as expected in the hosted UI.
- Personally added typed workflow state, explicit fallback objects, run logging, latency metrics, and saved example artifacts.
- Personally debugged dependency, process, and environment issues around local AgentOS runs and API-key configuration.
- Personally refined the investment memo rubric so the system separates business quality, valuation, data gaps, and cross-industry comparison limits.
