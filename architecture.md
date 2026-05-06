# Investment Research Multi-Agent System
## Architecture Design

---

## Overview

A linear multi-agent pipeline that researches and evaluates a set of companies, producing a structured investment recommendation memo with source citations.

**Input:** company names (free text). The MVP demo uses 3 companies, but the workflow and schemas support any number of companies.  
**Output:** Recommendation memo (markdown) with final investment recommendation and cited sources

**Framework:** [Agno](https://github.com/agno-agi/agno) — used for agent definition, tool integration, workflow orchestration, and the Agent OS UI for demo.

**Key UX decision:** After the user types company names, the system resolves each name to a confirmed identity before starting the full pipeline. This prevents ambiguity (e.g. "Apple" → which one?) and serves as a natural human-in-the-loop checkpoint.

---

## Grading Alignment

The implementation should optimize for the strongest grading signals:

| Grading dimension | Design response |
|---|---|
| Working end-to-end system | Keep MVP narrow: Agent OS demo, 3-company fixture, one command to run |
| Multi-agent design quality | Separate Identity, Research, Analyst, Critic, and Decision responsibilities with typed handoffs |
| Product / workflow sense | Human confirmation before expensive research; memo gives one actionable recommendation |
| Code quality | Workflow owns orchestration; agents own prompts/tools only; schemas are centralized |
| Typed state and interfaces | Pydantic models for every inter-agent boundary, including citations |
| Reliability | Tool-level fallbacks, structured-output retries, fallback objects for failed company pipelines |
| Observability | Per-agent latency, tool calls, success/failure, company name, and warnings |
| AI-native workflow | README should document AI-assisted iteration, debugging notes, and tradeoffs clearly |
| Explanation clarity | README mirrors this architecture and explains why each agent exists |
| Engineering judgment | Prioritize a polished repeatable demo over broad but brittle scope |

---

## Project Structure

```
investment-research/
│
├── .env.example                    # API keys 模板，commit 进 repo
├── .env                            # 本地 API keys，在 .gitignore 里
├── README.md
├── requirements.txt
│
├── app/
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── identity_agent.py       # Identity Agent：resolve mode，确认公司身份
│   │   ├── research_agent.py       # Research Agent：research mode，深度研究单家公司
│   │   ├── analyst_agent.py        # Analyst Agent：纯推理，无 tools
│   │   ├── critic_agent.py         # Critic Agent：纯推理，无 tools
│   │   └── decision_agent.py       # Decision Agent：写最终 memo
│   │
│   ├── workflows/
│   │   ├── __init__.py
│   │   └── research_workflow.py    # Agno Workflow：串联所有 agent，管理 WorkflowState
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py              # 所有 Pydantic 数据结构（WorkflowState、CompanyResearch 等）
│   │                               # 注意：这里是数据结构定义，不是 LLM model
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── _utils.py               # clean_text() — 共享文本清理工具，所有 tool 使用
│   │   ├── exa_search.py           # Exa REST search 封装（primary web research）
│   │   ├── sec_edgar.py            # SEC EDGAR REST API 封装（自己写，无 MCP server）
│   │   ├── wikipedia.py            # Wikipedia API 封装（自己写，无 MCP server）
│   │   └── web_search.py           # DuckDuckGo no-key fallback search
│   │
│   ├── config.py                   # 读取 .env、选择 LLM provider、返回 model 实例
│   └── main.py                     # 入口：启动 Agno UI 或 CLI run
│
├── tests/
│   ├── __init__.py
│   ├── test_agents/
│   │   ├── test_identity_agent.py  # mock Exa/Wikipedia 返回，测试公司身份解析
│   │   ├── test_research_agent.py  # mock Exa/SEC 返回，测试 research mode 和 citations
│   │   ├── test_analyst_agent.py   # 给定 CompanyResearch，验证 CompanyAnalysis schema
│   │   └── test_critic_agent.py    # 给定 analysis，验证 CompanyRisk schema
│   ├── test_tools/
│   │   ├── test_sec_edgar.py       # 测试 SEC EDGAR 封装（可用真实 API，免费）
│   │   └── test_wikipedia.py       # 测试 Wikipedia 封装
│   └── test_workflow/
│       └── test_end_to_end.py      # 完整 pipeline：输入公司名 → 输出 memo.md
│
├── data/
│   └── examples/
│       └── nvidia_amd_intel/       # 预先跑好的 3-company demo 输出，commit 进 repo
│           ├── workflow_state.json  # 完整 WorkflowState dump（展示 typed state 设计）
│           └── memo.md             # 最终 memo 输出（题目要求的 example output）
│
└── demo/
    └── demo.md                     # 如何运行 demo 的说明
```

---

## Directory Design Decisions

### `app/agents/`
每个文件只定义一个 agent，包含它的 system prompt、model 配置、tools、`output_schema`。**不包含业务逻辑**。业务逻辑（confirmation loop、retry、state 传递）全部在 `workflows/` 里。

### `app/workflows/research_workflow.py`
整个 pipeline 的唯一入口。所有 agent 的调用顺序、state 传递、human-in-the-loop 逻辑都在这里。agents 本身不知道彼此的存在。

### `app/schemas/schemas.py`
所有 Pydantic schema 集中在一个文件。agents、workflows、tests 都从这里 import，不重复定义。防止字段不一致的 bug。

**命名说明：** 目录叫 `schemas/` 而不是 `models/`，因为整个项目里 "model" 已经被 LLM model 占用（`claude-sonnet-4-6` 等），两个概念用同一个词会造成混淆。

### `app/tools/`

**The tool layer exists to decouple agents from external APIs.**

Research Agent's system prompt says `"search for recent news"` — it doesn't need
to know whether that means calling Exa, Tavily, or a custom scraper. If the
underlying data source changes, only `app/tools/` changes. The agent prompt,
agent definition, and workflow stay untouched.

#### Which tools go here

| Tool | Method | Why |
|---|---|---|
| **Exa** | Self-wrapped `@tool` (`exa_search.py`) | Primary web research via Exa REST API; requires `EXA_API_KEY` |
| **SEC EDGAR** | Self-wrapped `@tool` (`sec_edgar.py`) | No MCP server — calls REST API directly |
| **Wikipedia** | Self-wrapped `@tool` (`wikipedia.py`) | No MCP server — calls REST API directly |
| **DuckDuckGo** | Self-wrapped `@tool` (`web_search.py`) | No-key fallback; weaker for recent news |

#### Self-wrapped tool contract

Every `@tool` function must follow the same contract:
1. **One clear purpose** — described in the docstring (this is what the agent reads)
2. **Input truncation** — cap raw output before returning (see Token Control)
3. **Never raise** — catch exceptions, return `"Not found"` instead of crashing
4. **Return typed evidence** — tools return compact `EvidenceSource` objects or lists of `EvidenceSource`, not raw HTML or unstructured blobs

```python
# app/tools/_utils.py  — shared utility, used by all tools
import re

def clean_text(raw: str, max_chars: int) -> str:
    """
    Strip HTML tags and normalise whitespace before passing to agent.
    Clean text is more token-efficient than raw HTML — same information, fewer tokens.
    Applied at tool layer before any character limit, so the cap applies to clean text.
    """
    # remove HTML tags
    text = re.sub(r"<[^>]+>", " ", raw)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]
```

```python
# app/tools/sec_edgar.py
import requests
from agno.tools import tool
from app.tools._utils import clean_text
from app.schemas.schemas import EvidenceSource

@tool
def get_financial_data(company_name: str, ticker: str | None = None) -> list[EvidenceSource]:
    """
    Fetch revenue, profit margin, and filing data for a US public company from SEC EDGAR.
    Use this when you need official financial statements for a publicly traded company.
    Resolves ticker/company name to CIK before calling companyfacts.
    Returns an empty list if the company is private or data is unavailable.
    """
    try:
        cik = resolve_cik(company_name=company_name, ticker=ticker)  # ticker/name -> zero-padded CIK
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        response = requests.get(url, headers={"User-Agent": "research-agent/1.0"})
        response.raise_for_status()
        summary = extract_financial_summary(response.json())  # parse us-gaap facts before truncating
        return [EvidenceSource(
            title=f"SEC companyfacts for {company_name}",
            url=url,
            publisher="SEC EDGAR",
            date=None,
            snippet=clean_text(summary, max_chars=2000),
        )]
    except Exception:
        return []
```

```python
# app/tools/wikipedia.py
import requests
from agno.tools import tool
from app.tools._utils import clean_text
from app.schemas.schemas import EvidenceSource

@tool
def get_wiki_summary(company_name: str) -> list[EvidenceSource]:
    """
    Fetch the introductory summary of a company from Wikipedia.
    Use this for background information, founding history, and general description.
    Returns an empty list if no Wikipedia page exists.
    """
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + company_name
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        extract = data.get("extract", "Not found")
        return [EvidenceSource(
            title=data.get("title", company_name),
            url=data.get("content_urls", {}).get("desktop", {}).get("page", url),
            publisher="Wikipedia",
            date=None,
            snippet=clean_text(extract, max_chars=1500),
        )]
    except Exception:
        return []
```

#### How Research Agent sees these tools

The agent doesn't import or call these functions directly. It reads the docstring
and decides when to use each tool based on the task. This is why docstrings are
written from the agent's perspective ("Use this when..."), not the developer's.

```python
# app/agents/research_agent.py
from agno.agent import Agent
from app.tools.exa_search import search_exa_for_company
from app.tools.sec_edgar import get_financial_data
from app.tools.wikipedia import get_wiki_summary
from app.tools.web_search import search_web_for_company

identity_agent = Agent(
    name="Identity Agent",
    output_schema=CompanyIdentity,
)

research_agent = Agent(
    name="Research Agent",
    tools=[
        get_wiki_summary,        # Wikipedia: background
        get_financial_data,      # SEC EDGAR: official financials
        search_exa_for_company,  # Exa REST: primary web evidence
        search_web_for_company,  # DuckDuckGo: no-key fallback
    ],
    output_schema=CompanyResearch,
)
```

#### What changes if you swap a data source

Switching from Exa to Tavily for search requires:
- Adding `app/tools/tavily.py` with the same `@tool` contract
- Changing one line in `research_agent.py`
- Nothing else changes — prompt, schema, workflow untouched

This is the entire point of the abstraction layer.

### `app/config.py`
所有配置集中在这里，包括 `get_reasoning_model()` 和 `get_worker_model()`。agents 从这里 import model 实例，不在每个 agent 文件里硬编码 provider 或 model ID。切换 provider 只需改 `.env` 里的 `LLM_PROVIDER`。

### `data/examples/`
预先跑好的 demo 输出，commit 进 repo。好处：
- Reviewers 不需要自己跑就能看到输出质量
- Demo 时就算 API 不稳定也能展示结果
- `workflow_state.json` 直接展示 typed state 的实际内容，是 schema 设计的最好说明

---

## Agent Pipeline

### Phase 1 — Sequential: Company Confirmation (Human-in-the-Loop)

```
User Input (3 company names)
        ↓
  Orchestrator
        ↓
 Identity Agent ← resolve company 1   →  *** HUMAN-IN-THE-LOOP #1 ***
        ↓ (confirmed)
 Identity Agent ← resolve company 2   →  *** HUMAN-IN-THE-LOOP #2 ***
        ↓ (confirmed)
 Identity Agent ← resolve company 3   →  *** HUMAN-IN-THE-LOOP #3 ***
        ↓ (all confirmed)
```

Confirmation is intentionally sequential — user confirms one company at a time
so mistakes are caught early without waiting for every company to resolve.

### Phase 2 — Parallel: Research → Analyst → Critic (per company)

```
  Company 1                Company 2                Company 3
     ↓                        ↓                        ↓
Research Agent           Research Agent           Research Agent
     ↓                        ↓                        ↓
Analyst Agent            Analyst Agent            Analyst Agent
     ↓                        ↓                        ↓
 Critic Agent             Critic Agent             Critic Agent
     ↓                        ↓                        ↓
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              ↓
                       Decision Agent
                    (receives all results)
                              ↓
                         memo.md
```

Each company runs its own Research → Analyst → Critic loop independently and concurrently.
Decision Agent waits for all company pipelines to complete, then writes the comparative memo.

**Each agent handles exactly one company.** No agent receives a list of companies.
The Workflow layer manages concurrency via `asyncio.gather`. The demo uses 3 companies because it is easy to evaluate, but the workflow is parameterized over `state.raw_input`.

---

## Human-in-the-Loop: Company Confirmation

Each company is resolved and confirmed **one at a time**, sequentially. The user can catch a mistake early without waiting for every company to resolve.

**Per company flow:**

Identity Agent does a quick search and returns the company display name, website URL, ticker/status if known, and a one-line description. The system then asks the user to confirm before moving on.

**Confirmation prompts (one per company):**
```
Company 1: Found "Nvidia" → nvidia.com (GPU / AI infrastructure)
Is this the right company? (yes / edit)
```
```
Company 2: Found "AMD" → amd.com (GPU / CPU)
Is this the right company? (yes / edit)
```
```
Company 3: Found "Intel" → intel.com (CPU / semiconductor)
Is this the right company? (yes / edit)
```

**User response per company:**
- `yes` → move to next company (or start full pipeline if all companies are confirmed)
- `edit` → user corrects the name, system re-resolves and asks again

**Why this matters:**
- Mistakes are caught one at a time, not after every company resolves
- Handles ambiguous names ("Apple", "Meta", etc.)
- Counts as a human-in-the-loop checkpoint (stretch goal in the exercise)
- Easy to explain in the README as a deliberate product decision

---



### Orchestrator

> ⚠️ Clarification on naming: "Orchestrator" in this system refers to the
> **Workflow class** (`research_workflow.py`), not a separate LLM-backed Agent.
> The Workflow is the skeleton — it sequences agents, manages state, and handles
> `asyncio.gather`. There is no `orchestrator.py` in `app/agents/` that drives
> the pipeline. See design decision below.

**What the Workflow does (code, not LLM):**
- Receives raw user input (one or more company name strings)
- Runs sequential confirmation loop (Phase 1)
- Launches one parallel company pipeline per confirmed company via `asyncio.gather` (Phase 2)
- Collects results using Map-Reduce pattern (see below)
- Calls Decision Agent with all results
- Returns completed `WorkflowState`

**What goes in `app/agents/` (LLM-backed):**
The only LLM-backed "orchestration" behaviour is identity resolution, where
Identity Agent resolves each company name and the Workflow pauses for user input.
The primary demo path is Agno Agent OS. CLI `input()` is only a fallback for local debugging.

**Input:**
```
["Nvidia", "AMD", "Intel"]  # demo
# or any length list, e.g. ["OpenAI", "Anthropic", "Mistral", "Cohere"]
```

**Output:** completed `WorkflowState` with memo populated

---

### Identity Agent

**Tools:**
| Tool | Purpose |
|---|---|
| `Exa Search` | Resolve ambiguous company names and find canonical website |
| `Wikipedia API` | Optional background check when search results are ambiguous |

**Responsibility:**
- Runs only during confirmation
- Resolves a raw free-text name to a canonical company identity
- Handles public, private, and startup companies
- Returns source-backed identity data for the human checkpoint

**Input:**
```python
class IdentityRequest(BaseModel):
    company_name: str
```

**Output:**
```python
class CompanyIdentity(BaseModel):
    name: str
    url: str
    description: str
    ticker: str | None = None
    company_type: Literal["public", "private", "startup", "unknown"] = "unknown"
    confidence: Literal["low", "medium", "high"] = "medium"
    sources: list[EvidenceSource] = Field(default_factory=list)
```

---

### Research Agent

**Tools:**
| Tool | Purpose |
|---|---|
| `Exa Search` | Search recent news, funding rounds, competitor mentions |
| `DuckDuckGo Search` | No-key fallback when Exa is unavailable |
| `SEC EDGAR API` | Fetch financial data for public companies (revenue, profit, filings) |
| `Wikipedia API` | Fetch background info and company history |

**Responsibility:**
- Runs once per confirmed company in **research mode**
- Collects business model, products, financials or funding, recent news, team, market size, competitors, and source citations
- Selects data strategy based on `CompanyIdentity.company_type`
- For public companies, attempts SEC EDGAR via ticker/CIK
- For private companies and startups, searches for funding rounds, customers, traction, hiring, and investor signals

**Input:**
```python
class ResearchRequest(BaseModel):
    company: CompanyIdentity
    # always single company — called once per company in parallel
```

**Output:**
```python
class CompanyResearch(BaseModel):
    name: str
    url: str
    company_type: Literal["public", "private", "startup", "unknown"]
    ticker: str | None = None
    business_model: str
    products: list[str]
    team_size: str
    key_people: list[str]
    funding_or_financials: str   # funding rounds (private) or revenue (public)
    market_size: str
    recent_news: list[str]       # max 5 bullet points
    competitors: list[str]
    sources: list[EvidenceSource] # source citations used by Decision Agent
```

---

### Analyst Agent

**Tools:** none — pure reasoning over Research output

**Responsibility:**
- Analyzes each company across 4 investment dimensions
- Assigns a score 1–10 per dimension and an overall score
- Does NOT fetch new data — works only from `CompanyResearch`

**Input:**
```python
research: CompanyResearch   # single company only
# called 3 times concurrently via asyncio.gather — one per company
```

**Output:**
```python
class DimensionScore(BaseModel):
    score: int                    # 1–10
    narrative: str                # evidence-backed reasoning
    confidence: Literal["low", "medium", "high"] = "medium"

class CompanyAnalysis(BaseModel):
    name: str
    market_opportunity: DimensionScore
    competitive_position: DimensionScore
    growth_potential: DimensionScore
    business_model_strength: DimensionScore
    overall_score: int            # 1–10
    one_line_verdict: str         # e.g. "Strong market position, but margin pressure ahead"
```

---

### Critic / Risk Agent

**Tools:** none — pure adversarial reasoning over Analyst output

**Responsibility:**
- Challenges the Analyst's conclusions for each company
- Identifies risks the Analyst may have underweighted
- Raises open questions that remain unanswered

**Input:**
```python
research: CompanyResearch    # single company only
analysis: CompanyAnalysis    # single company only
# called 3 times concurrently via asyncio.gather — one per company
```

**Output:**
```python
class CompanyRisk(BaseModel):
    name: str
    key_risks: list[str]          # max 5, e.g. "Regulatory risk in EU market"
    analyst_weaknesses: list[str] # where the Analyst's case is thin or optimistic
    open_questions: list[str]     # things an investor should dig into
    risk_level: Literal["low", "medium", "high"]
    sources_to_verify: list[str] = Field(default_factory=list)  # optional URLs or source titles that need follow-up
```

---

### Decision Agent

**Tools:** none — synthesis and writing

**Responsibility:**
- Reads all prior outputs and writes the final memo
- Makes a single clear recommendation: which company to invest in and why
- Memo is structured markdown, ready to share

**Input:**
```python
research: list[CompanyResearch]   # all companies — only agent that receives a list
analysis: list[CompanyAnalysis]   # all companies
risks: list[CompanyRisk]          # all companies
# called once after all parallel pipelines complete
```

**Output:** `memo.md` with the following structure:
```
# Investment Recommendation Memo

## Executive Summary
[2-3 sentences: what we looked at, what we recommend]

## Company Profiles
### Company A
- Business: ...
- Financials: ...
- Key risks: ...
- Score: X/10

### Company B ...
### Company C ...

## Side-by-Side Comparison
| Dimension         | Company A | Company B | Company C |
|-------------------|-----------|-----------|-----------|
| Market opportunity| ...       | ...       | ...       |
| Competitive pos.  | ...       | ...       | ...       |
| Growth potential  | ...       | ...       | ...       |
| Risk level        | ...       | ...       | ...       |
| Overall score     | X/10      | X/10      | X/10      |

## Recommendation
**Invest in: [Company X]**
Reason: ...
Key risks to monitor: ...

## Sources
[1] Source title — URL
[2] Source title — URL
```

---

## Agno Implementation

Each agent is defined as an `Agent` in Agno. **Each agent handles exactly one company** — no agent receives a list.

```python
from agno.agent import Agent
from app.tools.exa_search import search_exa_for_company
from app.tools.sec_edgar import get_financial_data
from app.tools.wikipedia import get_wiki_summary
from app.tools.web_search import search_web_for_company
from app.schemas.schemas import CompanyIdentity, CompanyResearch, CompanyAnalysis, CompanyRisk

identity_agent = Agent(
    name="Identity Agent",
    role="Resolve one raw company name into a confirmed company identity",
    output_schema=CompanyIdentity,
    retries=2,
)

research_agent = Agent(
    name="Research Agent",
    role="Research a single company and return structured findings",
    tools=[
        get_wiki_summary,     # Wikipedia (self-wrapped @tool)
        get_financial_data,   # SEC EDGAR (self-wrapped @tool)
        search_exa_for_company,  # Exa REST primary search
        search_web_for_company,  # DuckDuckGo fallback
    ],
    output_schema=CompanyResearch,   # single company, not list
    retries=2,
    tool_call_limit=20,
)

analyst_agent = Agent(
    name="Analyst Agent",
    role="Analyze one company across 4 investment dimensions",
    tools=[],
    output_schema=CompanyAnalysis,   # single company, not list
    retries=2,     # auto-repair invalid structured output
    max_tokens=1500,
)

critic_agent = Agent(
    name="Critic Agent",
    role="Challenge the analyst's conclusions for one company",
    tools=[],
    output_schema=CompanyRisk,       # single company, not list
    retries=2,
    max_tokens=1000,
)

decision_agent = Agent(
    name="Decision Agent",
    role="Write the final investment recommendation memo comparing all companies",
    tools=[],
    # receives list[CompanyResearch/Analysis/Risk] — only agent that sees all companies
    # no output_schema — free-form markdown output
    # validation happens in workflow by checking required sections + citation coverage
    max_tokens=2000,
)
```

The pipeline is an **Agno Workflow** with two phases — sequential confirmation, then parallel per-company processing:

```python
import asyncio
import time
from agno.workflow import Workflow
from app.schemas.schemas import WorkflowState, CompanyIdentity, CompanyRisk

class InvestmentResearchWorkflow(Workflow):
    identity_agent: Agent = identity_agent
    research_agent: Agent = research_agent
    analyst_agent: Agent = analyst_agent
    critic_agent: Agent = critic_agent
    decision_agent: Agent = decision_agent

    async def run_single_company_pipeline(
        self, company: CompanyIdentity
    ) -> tuple[CompanyResearch, CompanyAnalysis, CompanyRisk]:
        """
        Research -> Analyst -> Critic loop for ONE company.
        Called concurrently for all confirmed companies via asyncio.gather.
        Each call is fully independent — no shared mutable state.
        """
        research = await self.research_agent.arun(ResearchRequest(company=company))
        analysis = await self.analyst_agent.arun(research)
        risk     = await self.critic_agent.arun(research, analysis)
        return research, analysis, risk

    async def run(self, state: WorkflowState) -> WorkflowState:
        state.start_time = time.time()   # observability: track total latency

        # ── Phase 1: Sequential confirmation (human-in-the-loop) ──────────────
        # Runs one company at a time — user confirms before moving to next.
        #
        # CLI mode:  pauses with input() after each resolve
        # Agent OS:  uses Session storage to suspend/resume across UI interactions
        #            (Agno persists state in session; user replies in chat UI)
        for raw_name in state.raw_input:
            identity = await self.identity_agent.arun(
                IdentityRequest(company_name=raw_name)
            )
            confirmed = await self._confirm_with_user(identity)   # see below
            state.confirmed_companies.append(confirmed)

        # ── Phase 2: Parallel pipelines (Map step) ────────────────────────────
        # asyncio.gather runs all company pipelines concurrently.
        # return_exceptions=True ensures one failure doesn't cancel the others.
        # Each pipeline is self-contained — no shared mutable state between them.
        raw_results = await asyncio.gather(
            *[self.run_single_company_pipeline(c)
              for c in state.confirmed_companies],
            return_exceptions=True
        )

        # ── Phase 2: Collect results (Reduce step) ───────────────────────────
        # Map-Reduce pattern: gather returns ALL results first, then assign once.
        # Avoids incremental append() on shared state during concurrent execution.
        valid_results = []
        for company, r in zip(state.confirmed_companies, raw_results):
            if isinstance(r, Exception):
                state.run_log.warnings.append(f"{company.name}: {r}")
                valid_results.append(make_fallback_pipeline_result(company, error=str(r)))
            else:
                valid_results.append(r)

        state.research = [r[0] for r in valid_results]   # assign once, atomically
        state.analysis = [r[1] for r in valid_results]
        state.risks    = [r[2] for r in valid_results]

        # ── Phase 3: Decision Agent (sequential — needs all results) ──────────
        state.memo = await self.decision_agent.arun(
            state.research, state.analysis, state.risks
        )

        state.run_log.total_latency_seconds = time.time() - state.start_time
        return state

    async def _confirm_with_user(self, identity: CompanyIdentity) -> CompanyIdentity:
        """
        CLI mode: print identity, call input(), re-resolve on edit.
        Agent OS mode: yield identity to session, await user reply.
        """
        # CLI fallback (works for demo without Agno UI)
        print(f"Found: {identity.name} → {identity.url} ({identity.description})")
        response = input("Confirm? (yes / edit): ").strip().lower()
        if response == "yes":
            return identity
        new_name = input("Enter corrected company name: ").strip()
        return await self.identity_agent.arun(
            IdentityRequest(company_name=new_name)
        )
```

**Demo UI:** Served via Agno Agent OS. No custom frontend needed. The README should document Agent OS as the primary demo path and CLI as the fallback.

---

## Workflow State

The full `WorkflowState` accumulates outputs as the pipeline progresses. The workflow writes state; agents receive only the typed object needed for their own task.

```python
from pydantic import BaseModel, Field
from typing import Literal

class EvidenceSource(BaseModel):
    title: str
    url: str
    publisher: str | None = None
    date: str | None = None
    snippet: str

# --- Identity (from resolve mode) ---
class CompanyIdentity(BaseModel):
    name: str
    url: str
    description: str
    ticker: str | None = None
    company_type: Literal["public", "private", "startup", "unknown"] = "unknown"
    confidence: Literal["low", "medium", "high"] = "medium"
    sources: list[EvidenceSource] = Field(default_factory=list)

# --- Research (from research mode) ---
class CompanyResearch(BaseModel):
    name: str
    url: str
    company_type: Literal["public", "private", "startup", "unknown"]
    ticker: str | None = None
    business_model: str
    products: list[str]
    team_size: str
    key_people: list[str]
    funding_or_financials: str
    market_size: str
    recent_news: list[str]
    competitors: list[str]
    sources: list[EvidenceSource] = Field(default_factory=list)

# --- Analysis ---
class DimensionScore(BaseModel):
    score: int
    narrative: str
    confidence: Literal["low", "medium", "high"] = "medium"

class CompanyAnalysis(BaseModel):
    name: str
    market_opportunity: DimensionScore
    competitive_position: DimensionScore
    growth_potential: DimensionScore
    business_model_strength: DimensionScore
    overall_score: int            # 1–10
    one_line_verdict: str

# --- Risk ---
class CompanyRisk(BaseModel):
    name: str
    key_risks: list[str]
    analyst_weaknesses: list[str]
    open_questions: list[str]
    risk_level: Literal["low", "medium", "high"]
    sources_to_verify: list[str] = Field(default_factory=list)

# --- Observability: per-agent run log (must include company name for parallel runs) ---
class AgentRunLog(BaseModel):
    agent: str                              # e.g. "Research Agent"
    company: str                            # e.g. "Nvidia" — critical for parallel disambiguation
    start_time: float
    end_time: float
    latency_seconds: float
    tool_calls: list[str]
    success: bool
    error: str | None = None               # populated on failure

class RunLog(BaseModel):
    agent_runs: list[AgentRunLog] = Field(default_factory=list)
    total_latency_seconds: float = 0.0
    warnings: list[str] = Field(default_factory=list)   # pipeline failures skipped gracefully

# --- Top-level workflow state ---
class WorkflowState(BaseModel):
    raw_input: list[str]                    # original user input
    confirmed_companies: list[CompanyIdentity] = Field(default_factory=list)
    research: list[CompanyResearch] = Field(default_factory=list)   # Map-Reduce: assigned atomically
    analysis: list[CompanyAnalysis] = Field(default_factory=list)   # Map-Reduce: assigned atomically
    risks: list[CompanyRisk] = Field(default_factory=list)          # Map-Reduce: assigned atomically
    memo: str = ""                          # final markdown output
    start_time: float = 0.0                 # set at run() start for total latency tracking
    run_log: RunLog = Field(default_factory=RunLog)   # always initialized — never None
```

---

## Context Passing Strategy

### Why This Matters

Every LLM call has a context window limit. If the data passed into an agent exceeds
that limit, the call fails. The parallel architecture helps significantly — each agent
only sees data for **one company**, not three. But Research Agent still needs to handle
raw tool output internally, which can be very large.

### Two-Level Strategy

**Level 1 — Tool output truncation (inside Research Agent)**

Raw tool output is the biggest risk. A search result or crawled page can return 10,000+ tokens of
HTML/text content. Research Agent must receive capped evidence before it fills the context window:

```python
# app/tools/sec_edgar.py
@tool
def get_financial_data(ticker: str) -> str:
    """Fetch financials from SEC EDGAR. Returns max 2000 chars."""
    raw = call_sec_edgar_api(ticker)
    return raw[:2000]  # hard cap — agent extracts what it needs

# Exa REST search wrapper — limit result count and highlights before returning to the agent
search_exa(query, max_results=5, max_characters=1000)
```

Research Agent prompt reinforces this:
```
Keep queries short (under 5 words) and use at most 10 tool calls.
Stop when you have enough — do not fetch everything available.
```

**Level 2 — Structured extraction between agents**

Research Agent's output is `CompanyResearch` (Pydantic model) — already compressed
and structured. Analyst and Critic receive this clean object, not raw text.

```
Raw tool output (~10,000 tokens)
        ↓  Research Agent extracts and compresses
CompanyResearch (~700 tokens, including citations)
        ↓  passed to Analyst, Critic
CompanyAnalysis (~300 tokens) + CompanyRisk (~300 tokens)
        ↓  all companies passed to Decision Agent
Decision Agent input scales linearly with company count
```

This is the core value of typed state — it forces compression at each handoff.

### Token Budget Estimate

| Agent | Input tokens | Notes |
|---|---|---|
| Research Agent (resolve) | ~200 | Just a company name + system prompt |
| Research Agent (research) | ~3,000 | System prompt + accumulated tool results |
| Analyst Agent | ~700 | System prompt + 1x CompanyResearch |
| Critic Agent | ~1,000 | System prompt + CompanyResearch + CompanyAnalysis |
| Decision Agent | ~1,200 + ~900/company | System prompt + N x Research/Analysis/Risk + citations |

All well within Claude Sonnet (200K), GPT-4.1 (1M), and Gemini 2.5 Pro (1M) limits.
The only realistic risk is Research Agent if tool outputs are not capped.

---

## Token Control

### Why This Matters

Multi-agent systems consume tokens fast. Anthropic's engineering team found that
multi-agent systems use approximately **15x more tokens than standard chat**.
Without hard limits, a single pipeline run can spiral into thousands of unexpected
API calls, especially if Research Agent enters a loop or a tool returns unexpectedly
large payloads.

Token control operates at three levels: per-call output limits, per-agent tool call
limits, and per-run total budget.

---

### Level 1 — Per LLM Call: `max_tokens` (Output) + Input Truncation

#### `max_tokens` controls output only — not input

`max_tokens` caps what the agent **generates**. It does NOT limit what goes **in**.

> ⚠️ If any search/crawl provider passes a 20,000 token webpage to Research Agent,
> the agent has already consumed 20,000 input tokens — even if `max_tokens=1000`.
> You pay for the input, and the agent may lose focus in the noise.

**Two separate problems, two separate solutions:**

```
Input side  → truncate tool output BEFORE it reaches the agent
Output side → max_tokens caps what the agent generates
```

#### Input truncation — tool layer

Every tool that returns raw text must truncate before returning.
This happens in `app/tools/` and in the Exa REST request configuration — **not** inside the agent.

```python
# app/tools/sec_edgar.py
@tool
def get_financial_data(ticker: str) -> str:
    """Fetch financials from SEC EDGAR. Returns at most 2000 characters."""
    raw = call_sec_edgar_api(ticker)
    return raw[:2000]                  # hard input cap at tool layer

# app/tools/wikipedia.py
@tool
def get_wiki_summary(company: str) -> list[EvidenceSource]:
    """Fetch Wikipedia summary. Returns intro section evidence only."""
    raw = fetch_wikipedia_intro(company)
    return [EvidenceSource(...)]       # intro only, not full article

# Exa REST search — cap per-result and total results
search_exa(
    query="Nvidia recent news",
    max_results=5,
    max_characters=1000,
)
```

**Why at the tool layer, not the agent layer?**
Tools are called inside the agent's context loop. By the time the agent sees the
result, the tokens are already counted. Truncation must happen before the result
is returned — i.e., inside the `@tool` function or the MCP config.

#### `max_tokens` — output ceiling per agent

```python
# app/agents/research_agent.py
research_agent = Agent(
    name="Research Agent",
    model=get_worker_model(),
    max_tokens=1000,      # output cap: CompanyResearch fields are concise
    output_schema=CompanyResearch,
)

# app/agents/analyst_agent.py
analyst_agent = Agent(
    name="Analyst Agent",
    model=get_reasoning_model(),
    max_tokens=1500,      # output cap: narratives + scores per company
    output_schema=CompanyAnalysis,
)

# app/agents/critic_agent.py
critic_agent = Agent(
    name="Critic Agent",
    model=get_reasoning_model(),
    max_tokens=1000,      # output cap: risk lists + open questions
    output_schema=CompanyRisk,
)

# app/agents/decision_agent.py
decision_agent = Agent(
    name="Decision Agent",
    model=get_reasoning_model(),
    max_tokens=2000,      # output cap: memo target 600-900 words
)
```

---

### Level 2 — Per Agent: Tool Call Limit

Research Agent is the only agent that calls external tools. Without a hard limit
on tool calls, it can loop indefinitely — searching, then searching again, then
searching, then searching again.

Enforced in two places:

**In the prompt** (soft guidance):
```
Determine a research budget before starting.
Simple tasks: under 5 tool calls.
Full company research: 8-10 tool calls maximum.
When you stop finding new information, stop immediately.
Maximum absolute limit: 20 tool calls. If you reach this, stop and return what you have.
```

**In the workflow** (hard enforcement):
```python
# app/workflows/research_workflow.py
MAX_TOOL_CALLS = 20

async def run_single_company_pipeline(
    self, company: CompanyIdentity
) -> tuple[CompanyResearch, CompanyAnalysis, CompanyRisk]:
    research = await self.research_agent.arun(
        company,
        tool_call_limit=MAX_TOOL_CALLS,   # Agno hard cap
    )
    ...
```

---

### Level 3 — Per Run: Total Budget Guard

A full demo pipeline run (3 companies × full research) should never exceed a reasonable
token budget. For larger company lists, the budget should scale linearly with company count.

```python
# app/workflows/research_workflow.py
MAX_TOKENS_PER_COMPANY = 15_000
BASE_TOKEN_BUDGET = 10_000
max_tokens_per_run = BASE_TOKEN_BUDGET + len(state.confirmed_companies) * MAX_TOKENS_PER_COMPANY

async def run(self, state: WorkflowState) -> WorkflowState:
    token_counter = TokenCounter()   # tracks cumulative usage

    results = await asyncio.gather(
        *[self.run_single_company_pipeline(c, token_counter)
          for c in state.confirmed_companies],
        return_exceptions=True
    )

    if token_counter.total > MAX_TOKENS_PER_RUN:
        # log warning but do not crash — return partial results
        state.run_log.warning = f"Token budget exceeded: {token_counter.total} tokens used"

    ...
```

---

### Token Limits Summary

| Agent | Max input per tool call | `max_tokens` (output) | Tool calls max |
|---|---|---|---|
| Research Agent (resolve) | 1,000 chars/result | 200 | 3 |
| Research Agent (research) | 1,000 chars/result | 1,000 | 20 |
| Analyst Agent | n/a (no tools) | 1,500 | 0 |
| Critic Agent | n/a (no tools) | 1,000 | 0 |
| Decision Agent | n/a (no tools) | 2,000 | 0 |
| **Per-run total** | — | **50,000 tokens** | — |

The "Max input per tool call" column is enforced at the **tool layer** (truncation in `@tool` functions and MCP config).
The "`max_tokens`" column is enforced at the **agent layer** (Agno `Agent` parameter).
These are independent controls — both are necessary.

---

## Error Handling (MVP)

### Core Principle: Graceful Degradation

When data is missing or a tool fails, the pipeline **must not crash and must not hallucinate**.
The correct behavior is always: mark the gap explicitly, continue with what is available.

> A memo that says "revenue data not available" is better than a memo with invented numbers.
> A pipeline that finishes with partial data is better than one that crashes at step 2.

This principle is enforced at two levels:
- **Research Agent prompt:** "If a field cannot be found after reasonable effort, set it to `Not found`. Do not invent data."
- **Workflow code:** retry logic catches exceptions and injects `Not found` sentinel values rather than propagating errors.

---

### Required Data and Failure Risk

| Data Field | Source | Risk | Fallback |
|---|---|---|---|
| Business model, products | Exa Search + company website snippets | 🟢 Low | "Not found" |
| Competitors | Exa Search | 🟡 Medium | "Not found" |
| Recent news | Exa Search | 🟡 Medium | "No recent news found" |
| Revenue / financials | SEC EDGAR | 🔴 High — public companies only | "Financial data not available (private company)" |
| Funding rounds | Exa Search | 🔴 High — often incomplete | "Funding data not found" |
| Market size (TAM) | Exa Search | 🔴 High — sources often conflict | Include source URL, flag if conflicting |
| Team / key people | Exa Search + company website snippets | 🟡 Medium | "Not found" |

**Private companies** (most AI startups) will almost always be missing revenue and funding data.
The system handles this by switching data strategy based on company type:
- Public company → SEC EDGAR for financials
- Private company → Exa Search for funding rounds and investor signals

---

### Failure Scenario 1: Tool returns no results

**Trigger:** Exa Search or SEC EDGAR returns empty results for a query.

**Handling:**
1. Retry up to **3 times** with progressively broader queries:
   - Attempt 1: `"Nvidia Q3 2024 revenue"`
   - Attempt 2: `"Nvidia financials 2024"`
   - Attempt 3: `"Nvidia annual report"`
2. If all 3 attempts return nothing → set field to `"Not found"`, log the failure, continue
3. Pipeline does **not** crash — downstream agents receive `"Not found"` as a valid value

```python
def search_with_retry(query: str, max_retries: int = 3) -> str:
    queries = [query, broaden(query), broaden(broaden(query))]
    for q in queries:
        result = exa.search(q)
        if result:
            return result
    return "Not found"  # never raises, never hallucinates
```

---

### Failure Scenario 2: LLM returns invalid structured output

**Trigger:** Agent output does not conform to the expected Pydantic schema
(e.g. missing required fields, wrong types, truncated JSON).

**Handling:**
Agno's `retries=2` parameter handles this automatically. When an agent's output
fails Pydantic validation, Agno retries the LLM call with the validation error
injected back into the prompt — no custom retry code needed.

```python
# This is all that's needed in the agent definition:
analyst_agent = Agent(
    output_schema=CompanyAnalysis,
    retries=2,    # Agno auto-retries on Pydantic validation failure
)
```

If all retries fail, add a manual fallback in the workflow:

```python
def safe_parse(raw: str, model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate_json(raw)
    except ValidationError:
        # all retries exhausted — return minimal valid fallback object
        return model.construct(**{f: "Not found" for f in model.model_fields})
```

---

### Failure Scenario 3: Conflicting data across sources

**Trigger:** Two sources give different values for the same field
(e.g. TAM = "$50B" from one source, "$500B" from another).

**Handling:**
- Research Agent includes **both values** with source attribution in the field:
  `"Market size: $50B (Gartner 2024) or $500B (IDC 2024) — sources conflict"`
- Analyst Agent is instructed to **flag conflicting data** rather than pick one arbitrarily
- Critic Agent is expected to **raise this as an open question**

This turns a data quality problem into a visible signal in the final memo, rather than hiding it.

---

### Downstream Agent Behavior with Missing Data

Analyst, Critic, and Decision agents are explicitly prompted to handle `"Not found"` values:

**Analyst Agent prompt addition:**
```
If a research field is "Not found", do not invent a value.
Instead, note the data gap in your narrative and reduce your confidence score for that dimension.
Example: "Competitive position score: 5/10 — limited data available on market share."
```

**Decision Agent prompt addition:**
```
If analysis contains significant data gaps (multiple "Not found" fields),
note this explicitly in the Executive Summary as a limitation.
Do not present the recommendation with false confidence.
```

---

## Testing Strategy

### Three Layers

```
Unit Tests        -> each agent: correct I/O? task completed?
Resilience Tests  -> error scenarios handled? graceful degradation?
End-to-End Test   -> full pipeline runs and produces memo?
```

The exercise says "one or two focused tests" — so the goal is **focused, not exhaustive**:
prove error handling works, prove each agent completes its task, prove the system runs end-to-end.

---

### Testing Principles

**Mock external dependencies, not business logic**
- Mock: Exa API, SEC EDGAR API, LLM calls
- Do not mock: Pydantic validation, retry logic, workflow state passing
- Why: tests run fast without burning API credits, but test what actually matters

**Use fixtures instead of live API calls**
- `data/examples/nvidia_amd_intel/workflow_state.json` as the standard fixture
- End-to-end test can start from a mid-pipeline state — no need to run full research every time

**Test file names map to failure scenarios**
- Reviewers can see from the filename which failure scenarios were tested

---

### Unit Tests

#### `tests/test_agents/test_identity_agent.py`

```python
def test_identity_agent_returns_company_identity(mock_exa):
    # Task: company name -> CompanyIdentity
    # Verify: valid schema, name/url/description populated
    result = identity_agent.run(IdentityRequest(company_name="Nvidia"))
    assert isinstance(result, CompanyIdentity)
    assert "nvidia" in result.url.lower()
    assert result.description != ""
    assert result.confidence in ["low", "medium", "high"]
```

---

#### `tests/test_agents/test_research_agent.py`

```python
def test_research_mode_returns_full_profile(mock_exa, mock_sec):
    # Task: CompanyIdentity -> CompanyResearch, all required fields populated
    # Verify: business_model / recent_news / competitors / sources not empty
    identity = CompanyIdentity(name="Nvidia", url="https://www.nvidia.com", description="GPU / AI infrastructure", ticker="NVDA", company_type="public")
    result = research_agent.run(ResearchRequest(company=identity))
    assert isinstance(result, CompanyResearch)
    assert result.business_model != ""
    assert len(result.recent_news) > 0
    assert len(result.competitors) > 0
    assert len(result.sources) > 0


def test_missing_financial_data_returns_not_found(mock_exa, mock_sec_empty):
    # Task: SEC EDGAR has no data (private company) -> field = "Not found", no crash, no hallucination
    # Verify: funding_or_financials == "Not found", other fields still populated
    identity = CompanyIdentity(name="SomePrivateStartup", url="https://example.com", description="AI startup", company_type="startup")
    result = research_agent.run(ResearchRequest(company=identity))
    assert result.funding_or_financials == "Not found"
    assert result.business_model != ""
```

---

#### `tests/test_agents/test_analyst_agent.py`

```python
def test_analyst_returns_valid_schema(single_research_fixture):
    # Task: 1x CompanyResearch -> 1x CompanyAnalysis (single company, not list)
    # Verify: valid schema, overall_score in 1-10 range
    result = analyst_agent.run(single_research_fixture)
    assert isinstance(result, CompanyAnalysis)   # single object, not list
    assert 1 <= result.overall_score <= 10
    assert 1 <= result.market_opportunity.score <= 10
    assert result.name == single_research_fixture.name


def test_analyst_scores_cover_full_range(nvidia_fixture, amd_fixture):
    # Task: different companies -> scores reflect their actual differences
    # Verify: two companies with clearly different profiles get different scores
    # (run agent separately per company, then compare — matches parallel architecture)
    nvidia_result = analyst_agent.run(nvidia_fixture)
    amd_result = analyst_agent.run(amd_fixture)
    assert nvidia_result.overall_score != amd_result.overall_score


def test_analyst_handles_missing_data_gracefully(minimal_research_fixture):
    # Task: research has "Not found" fields -> reduce confidence, do not invent numbers
    # Verify: narrative contains data gap language, no fabricated dollar figures
    result = analyst_agent.run(minimal_research_fixture)
    assert isinstance(result, CompanyAnalysis)   # still returns valid schema
    # should not contain fabricated dollar amounts
    assert "$" not in result.business_model_strength.narrative or "Not found" in result.business_model_strength.narrative
```

---

#### `tests/test_agents/test_critic_agent.py`

```python
def test_critic_returns_valid_schema(single_research_fixture, single_analysis_fixture):
    # Task: 1x CompanyResearch + 1x CompanyAnalysis -> 1x CompanyRisk (single company)
    # Verify: valid schema, risk_level is low/medium/high
    result = critic_agent.run(single_research_fixture, single_analysis_fixture)
    assert isinstance(result, CompanyRisk)        # single object, not list
    assert result.risk_level in ["low", "medium", "high"]
    assert result.name == single_research_fixture.name


def test_critic_challenges_high_analyst_score(single_research_fixture):
    # Task: analyst gave high score for one company -> critic must list enough risks
    # Verify: company with overall_score >= 8 gets at least 3 key_risks
    high_score_analysis = make_single_analysis_fixture(overall_score=9)
    result = critic_agent.run(single_research_fixture, high_score_analysis)
    assert isinstance(result, CompanyRisk)
    assert len(result.key_risks) >= 3


def test_critic_raises_open_questions(single_research_fixture, single_analysis_fixture):
    # Task: identify questions investor must answer before committing
    # Verify: open_questions is non-empty
    result = critic_agent.run(single_research_fixture, single_analysis_fixture)
    assert len(result.open_questions) > 0
```

---

#### `tests/test_agents/test_decision_agent.py`

```python
def test_decision_memo_contains_required_sections(full_fixture):
    # Task: all data -> memo matching the template
    # Verify: all required sections present
    memo = decision_agent.run(full_fixture.research, full_fixture.analysis, full_fixture.risks)
    for section in ["Executive Summary", "Company Profiles", "Side-by-Side", "Recommendation", "Invest in:", "Sources"]:
        assert section in memo, f"Missing section: {section}"


def test_decision_memo_cites_sources(full_fixture):
    # Task: memo must include source URLs from CompanyResearch.sources
    # Verify: at least one known source URL appears in the memo
    memo = decision_agent.run(full_fixture.research, full_fixture.analysis, full_fixture.risks)
    known_url = full_fixture.research[0].sources[0].url
    assert known_url in memo


def test_decision_makes_explicit_recommendation(full_fixture):
    # Task: must name one company, "It depends" is not acceptable
    # Verify: "Invest in:" present, "it depends" absent
    memo = decision_agent.run(full_fixture.research, full_fixture.analysis, full_fixture.risks)
    assert "Invest in:" in memo
    assert "it depends" not in memo.lower()


def test_decision_surfaces_data_gaps(partial_fixture):
    # Task: research has "Not found" fields -> memo must surface limitations, not hide them
    # Verify: Executive Summary contains data limitation language
    memo = decision_agent.run(partial_fixture.research, partial_fixture.analysis, partial_fixture.risks)
    limitation_keywords = ["limited", "not available", "gap", "insufficient"]
    assert any(kw in memo.lower() for kw in limitation_keywords)
```

---

### Resilience Tests

#### `tests/test_workflow/test_resilience.py`

```python
def test_exa_empty_results_retries_then_marks_not_found(mock_exa_empty):
    # Error scenario 1: Exa returns empty on every attempt
    # Verify: retried 3 times, field = "Not found", no crash
    mock_exa_empty.search.return_value = []
    identity = CompanyIdentity(name="UnknownCorp", url="Not found", description="Not found", company_type="unknown")
    result = research_agent.run(ResearchRequest(company=identity))
    assert mock_exa_empty.search.call_count == 3
    assert result.funding_or_financials == "Not found"
    assert result is not None


def test_invalid_llm_output_retries_then_returns_fallback(mock_llm_broken):
    # Error scenario 2: LLM returns invalid JSON (missing required fields)
    # Verify: Agno retries=2 fires, then safe_parse returns minimal fallback, no crash
    mock_llm_broken.return_value = '{"name": "Nvidia"}'   # missing required fields
    result = analyst_agent.run(single_research_fixture)    # single company input
    assert mock_llm_broken.call_count <= 3    # retries=2 means up to 3 total attempts
    assert result is not None
    assert isinstance(result, CompanyAnalysis)   # single object, not list


def test_private_company_missing_financials_does_not_halt_pipeline():
    # Error scenario 3: private company, SEC EDGAR has no data
    # Verify: pipeline completes, memo produced, missing data surfaced
    state = WorkflowState(
        raw_input=["OpenAI", "Anthropic", "Mistral"],
        confirmed_companies=load_fixture("openai_anthropic_mistral_identities"),
    )
    result = run_workflow(state)
    assert result.memo != ""
    assert "not available" in result.memo.lower() or "Not found" in result.memo
```

---

### End-to-End Test

#### `tests/test_workflow/test_end_to_end.py`

```python
def test_full_pipeline_produces_memo(mock_all_external_tools):
    # Given: 3 confirmed companies (fixture data, no live API calls)
    # When: full workflow runs
    # Then: memo produced, all layers populated, observability log present
    state = WorkflowState(
        raw_input=["Nvidia", "AMD", "Intel"],
        confirmed_companies=load_fixture("nvidia_amd_intel_identities"),
    )
    result = asyncio.run(run_workflow(state))

    assert result.memo != ""
    assert len(result.research) == 3
    assert len(result.analysis) == 3
    assert len(result.risks) == 3
    assert "Invest in:" in result.memo
    assert "Executive Summary" in result.memo
    assert result.run_log is not None
    # Demo expectation: 3x Research + 3x Analyst + 3x Critic + 1x Decision = 10 agent runs
    assert len(result.run_log.agent_runs) == 10


def test_parallel_pipelines_faster_than_serial(mock_all_external_tools):
    # Verify the 3 company pipelines actually run concurrently
    # If serial: total ~= sum of all individual runs
    # If parallel: total ~= slowest single run
    import time
    state = WorkflowState(
        raw_input=["Nvidia", "AMD", "Intel"],
        confirmed_companies=load_fixture("nvidia_amd_intel_identities"),
    )
    start = time.time()
    asyncio.run(run_workflow(state))
    elapsed = time.time() - start

    # each mock pipeline takes ~0.1s; serial would be ~0.3s
    # parallel should complete in ~0.15s (1.5x single, not 3x)
    assert elapsed < MOCK_SINGLE_PIPELINE_TIME * 1.5
```

---

### Test File Structure

```
tests/
├── conftest.py                      # all fixtures and mocks in one place
│                                    # Single-company fixtures (for unit tests):
│                                    # - single_research_fixture    (1x CompanyResearch)
│                                    # - single_analysis_fixture    (1x CompanyAnalysis)
│                                    # - minimal_research_fixture   (1x CompanyResearch with Not found fields)
│                                    # - nvidia_fixture, amd_fixture (named single-company fixtures)
│                                    # - make_single_analysis_fixture(overall_score=N)
│                                    # Multi-company fixtures (for end-to-end tests):
│                                    # - full_fixture    (WorkflowState with complete demo companies)
│                                    # - partial_fixture (WorkflowState with some Not found fields)
│                                    # Mocks:
│                                    # - mock_exa, mock_exa_empty, mock_sec, mock_sec_empty
│                                    # - mock_llm_broken, mock_all_external_tools
│
├── test_agents/
│   ├── test_identity_agent.py       # company resolution and human confirmation identity schema
│   ├── test_research_agent.py       # research mode, missing data, source citations
│   ├── test_analyst_agent.py        # schema, score calibration, missing data handling
│   ├── test_critic_agent.py         # schema, challenges high scores, open questions
│   └── test_decision_agent.py       # memo sections, explicit recommendation, data gaps
│
└── test_workflow/
    ├── test_resilience.py           # 3 error scenarios (maps to exercise requirements)
    └── test_end_to_end.py           # full pipeline smoke test
```

`conftest.py` is the key file. All mocks and fixtures are defined once here.
Test files only contain assertions — no repeated fixture definitions.

---

## Observability

### What is logged

Every agent run emits an `AgentRunLog` entry. Because Research/Analyst/Critic run in parallel
for multiple companies simultaneously, **`company` is a required field** — without it, logs from
concurrent runs are impossible to separate.

```json
{
  "agent_runs": [
    {"agent": "Research Agent", "company": "Nvidia",  "latency_seconds": 4.2, "tool_calls": ["exa_search", "sec_edgar"], "success": true},
    {"agent": "Research Agent", "company": "AMD",     "latency_seconds": 3.8, "tool_calls": ["exa_search", "sec_edgar"], "success": true},
    {"agent": "Research Agent", "company": "Intel",   "latency_seconds": 5.1, "tool_calls": ["exa_search"], "success": true, "error": "SEC EDGAR: ticker not found"},
    {"agent": "Analyst Agent",  "company": "Nvidia",  "latency_seconds": 2.1, "tool_calls": [], "success": true},
    {"agent": "Analyst Agent",  "company": "AMD",     "latency_seconds": 1.9, "tool_calls": [], "success": true},
    {"agent": "Analyst Agent",  "company": "Intel",   "latency_seconds": 2.3, "tool_calls": [], "success": true},
    {"agent": "Critic Agent",   "company": "Nvidia",  "latency_seconds": 1.8, "tool_calls": [], "success": true},
    {"agent": "Critic Agent",   "company": "AMD",     "latency_seconds": 2.0, "tool_calls": [], "success": true},
    {"agent": "Critic Agent",   "company": "Intel",   "latency_seconds": 1.7, "tool_calls": [], "success": true},
    {"agent": "Decision Agent", "company": "all",     "latency_seconds": 3.5, "tool_calls": [], "success": true}
  ],
  "total_latency_seconds": 9.1
}
```

### What to track (maps to exercise requirements)

| Metric | Why |
|---|---|
| Per-agent latency | Exercise requirement |
| Total workflow latency | Exercise requirement |
| Tool calls per agent | Helps debug Research Agent loops |
| Success / failure per agent | Exercise requirement |
| Company field on every log | Required for parallel run disambiguation |
| Error message on failure | Supports graceful degradation debugging |

### Parallel vs serial timing

Because 3 company pipelines run concurrently, `total_latency_seconds` should be
approximately equal to the **slowest single pipeline**, not the sum of all pipelines.
This is visible in the log above: 3 parallel Research calls (4.2s + 3.8s + 5.1s)
complete in ~5.1s total, not ~13.1s.

---

## Future Improvements (Post-MVP)

The current design is a working MVP. Known limitations and planned improvements:

- **Parallel subagents:** ✅ Already implemented in MVP — each company runs its own Research → Analyst → Critic pipeline concurrently via `asyncio.gather`
- **STORM-style multi-perspective questioning:** Each Worker spawns a Questioner that asks targeted questions to a shared Research Agent from a specific analytical angle (market, risk, competitive), inspired by the STORM paper on multi-perspective Wikipedia writing
- **Critic feedback loop:** Critic Agent sends work back to Analyst Agent for revision if risk score is too high, instead of passing directly to Decision Agent
- **LLM-as-judge evaluation:** A separate Evaluator Agent scores the final memo against a rubric

---

### State Persistence 🟢 Optional — Post-MVP

> Not needed for MVP. The current pipeline runs in memory and completes in one session.
> Add this if you want to support resuming interrupted runs or caching research results.

#### The Problem

If the pipeline crashes mid-run (e.g. after Research completes but before Analyst finishes),
all progress is lost. The next run starts from scratch, re-calling every tool and
spending the same tokens again.

For a 3-company pipeline that takes 30-60 seconds, this is annoying but not critical.
For a 10-company pipeline or a slow API environment, it becomes a real problem.

#### The Solution

Persist `WorkflowState` to disk after each agent completes. On restart, load the
saved state and skip any stages that already have results.

```python
# app/workflows/research_workflow.py

import json
from pathlib import Path

STATE_FILE = Path(".workflow_state.json")

def save_state(state: WorkflowState) -> None:
    """Persist current state to disk after each agent run."""
    STATE_FILE.write_text(state.model_dump_json(indent=2))

def load_state(raw_input: list[str]) -> WorkflowState | None:
    """Load saved state if it exists and matches current input."""
    if not STATE_FILE.exists():
        return None
    saved = WorkflowState.model_validate_json(STATE_FILE.read_text())
    if saved.raw_input != raw_input:
        return None   # different run — start fresh
    return saved

async def run(self, raw_input: list[str]) -> WorkflowState:
    # try to resume from saved state
    state = load_state(raw_input) or WorkflowState(raw_input=raw_input)

    # skip confirmation if already done
    if not state.confirmed_companies:
        # ... confirmation loop ...
        save_state(state)

    # skip research if already done for this company
    results = await asyncio.gather(*[
        self.run_single_company_pipeline(c)
        for c in state.confirmed_companies
        if c.name not in [r.name for r in state.research]  # skip completed
    ], return_exceptions=True)

    # ... collect results, save after each stage ...
    save_state(state)
    return state
```

#### What This Enables

- **Resume interrupted runs** — restart after a crash without re-calling tools
- **Cache research results** — run the same companies again with different analysis prompts
  without paying for Research again
- **Incremental runs** — add a 4th company to an existing 3-company run

#### Why It's Not in MVP

Adds complexity to the workflow without changing what the system produces.
The demo scenario (3 companies, single run) works fine in memory.
Worth adding if the pipeline becomes longer or tools become slower.

---

## Model Selection

### Design Principle

The system uses a **tiered model strategy**: a stronger model for agents that require deep reasoning (Analyst, Critic, Decision), and a lighter model for agents doing repetitive tool calls (Identity and Research). Orchestration itself is deterministic workflow code, not an LLM agent.

Tool calls don't need intelligence — they need speed and low cost. Reasoning does.

---

### Option 1 — OpenAI (Recommended Default)

Best default for this project because the user plans to use OpenAI or DeepSeek, and OpenAI gives stronger structured-output reliability for the graded demo.

| Agent | Model | Reason |
|---|---|---|
| Workflow / orchestration | code, not LLM | Deterministic control flow is easier to debug and explain |
| Identity Agent | `gpt-4.1-mini` | Fast name resolution and cheap tool use |
| Research Agent | `gpt-4.1-mini` | Fast, cheap, good for tool call loops |
| Analyst Agent | `gpt-4.1` | Solid reasoning and structured output |
| Critic Agent | `gpt-4.1` | Good at finding logical inconsistencies |
| Decision Agent | `gpt-4.1` | Clean markdown output and citation discipline |

**Cost estimate per 3-company demo run:** ~$0.08–0.20

**Why this is the default:** It maximizes end-to-end reliability, typed output quality, and demo repeatability, which map directly to the grading rubric.

---

### Option 2 — DeepSeek (Budget Alternative)

Best choice if cost is the top priority. Keep it as a selectable provider, but not the default for the scored demo unless OpenAI cost is a blocker.

| Agent | Model | Reason |
|---|---|---|
| Workflow / orchestration | code, not LLM | Deterministic control flow |
| Identity Agent | `deepseek-chat` (V3) | Cheap general-purpose tool-use agent |
| Research Agent | `deepseek-chat` (V3) | Cheapest option for tool calls |
| Analyst Agent | `deepseek-reasoner` (R1) | Reasoning model for complex analysis |
| Critic Agent | `deepseek-reasoner` (R1) | Better adversarial reasoning than V3 |
| Decision Agent | `deepseek-chat` (V3) | Writing is fine on V3, no need for R1 |

**Cost estimate per 3-company demo run:** ~$0.002–0.01

**Important caveats:**
- R1 bills separately for reasoning tokens, so complex prompts can use more tokens than expected
- Data passes through DeepSeek servers, which matters for sensitive company analysis
- Structured output reliability is lower than OpenAI, so keep stronger fallback validation

---

### Other Provider Options

These are documented for completeness, but are not the planned MVP path.

#### Anthropic Claude

Best overall balance of reasoning quality, structured output reliability, and Agno integration.

| Agent | Model | Reason |
|---|---|---|
| Workflow / orchestration | code, not LLM | Deterministic control flow |
| Identity Agent | `claude-haiku-4-5` | Fast identity resolution and tool use |
| Research Agent | `claude-haiku-4-5` | Repetitive tool calls — 3x cheaper, 90% capability |
| Analyst Agent | `claude-sonnet-4-6` | Multi-source synthesis and scoring |
| Critic Agent | `claude-sonnet-4-6` | Adversarial reasoning, identifying weak arguments |
| Decision Agent | `claude-sonnet-4-6` | Long-form structured writing |

**Cost estimate per run:** ~$0.05–0.15 (3 companies, full pipeline)

**Why not Opus?** 5x more expensive than Sonnet with marginal gain for this task. Opus is for tasks requiring sustained multi-hour reasoning. Sonnet is sufficient for single-pipeline analysis.

---

#### Google Gemini

Best choice if you want the largest context window or native Google Search grounding.

| Agent | Model | Reason |
|---|---|---|
| Workflow / orchestration | code, not LLM | Deterministic control flow |
| Identity Agent | `gemini-2.5-flash` | Fast identity resolution and tool use |
| Research Agent | `gemini-2.5-flash` | Fast, cheap, good tool use |
| Analyst Agent | `gemini-2.5-pro` | Deep analysis |
| Critic Agent | `gemini-2.5-flash` | Acceptable for adversarial tasks at lower cost |
| Decision Agent | `gemini-2.5-pro` | Strong long-form writing |

**Cost estimate per run:** ~$0.05–0.15

**Note:** Gemini has native Google Search grounding built in — Research Agent can use this instead of Exa for web search, potentially simplifying the tool setup.

---

### Summary Comparison

| Provider | Orchestration | Worker | Cost/run | Structured Output | Notes |
|---|---|---|---|---|---|
| **OpenAI** | code workflow | GPT-4.1 mini | ~$0.15 | ⭐⭐⭐ Best | Recommended default |
| **DeepSeek** | code workflow | V3 / R1 | ~$0.005 | ⭐ Fair | Budget alternative |
| **Anthropic** | code workflow | Haiku 4.5 | ~$0.10 | ⭐⭐⭐ Best | Good, but not planned default |
| **Gemini** | code workflow | 2.5 Flash | ~$0.10 | ⭐⭐ Good | Native Google Search grounding |

---

### API Key Configuration

The system accepts API keys via environment variables. Set the provider you want to use:

```bash
# Choose one provider (or set multiple to enable switching)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...
DEEPSEEK_API_KEY=sk-...

# Set active provider
LLM_PROVIDER=openai  # openai | deepseek | anthropic | gemini
```

In code, each agent reads from the active provider config:

```python
from agno.models.anthropic import Claude
from agno.models.openai import OpenAIChat
from agno.models.google import Gemini

def get_reasoning_model():
    provider = os.getenv("LLM_PROVIDER", "openai")
    if provider == "openai":
        return OpenAIChat(id="gpt-4.1")
    elif provider == "deepseek":
        return OpenAIChat(id="deepseek-reasoner", base_url="https://api.deepseek.com")
    elif provider == "anthropic":
        return Claude(id="claude-sonnet-4-6")
    elif provider == "gemini":
        return Gemini(id="gemini-2.5-pro")

def get_worker_model():
    provider = os.getenv("LLM_PROVIDER", "openai")
    if provider == "openai":
        return OpenAIChat(id="gpt-4.1-mini")
    elif provider == "deepseek":
        return OpenAIChat(id="deepseek-chat", base_url="https://api.deepseek.com")
    elif provider == "anthropic":
        return Claude(id="claude-haiku-4-5")
    elif provider == "gemini":
        return Gemini(id="gemini-2.5-flash")
```

> DeepSeek uses an OpenAI-compatible API endpoint, so it can be plugged in via `OpenAIChat` with a custom `base_url` — no separate SDK needed.

---

## Prompt Design

### Core Philosophy

Two principles directly apply here:

**1. Keep system prompts simple — invest in tool descriptions instead.**
A deliberately simple system prompt that gives the model a general methodology works better than an elaborate prompt that prescribes every step. The tool descriptions themselves tell the model what to do and when. Over-specified prompts make agents brittle; well-described tools make them adaptive.

**2. Use Pydantic response models for agent handoffs.**
For this project, typed state is a grading dimension. Agent-to-agent handoffs should use Agno `output_schema` and schema validation rather than XML parsing. XML tags are acceptable inside prompt instructions for readability, but they should not be the contract between agents.

```python
# Good — schema-first handoff
analyst_agent = Agent(
    output_schema=CompanyAnalysis,
    retries=2,
)

# Bad — fragile parsing contract
analyst_agent = Agent(
    instructions="Return XML with <score> and <verdict> tags."
)
```

---

### Agent Isolation Principle 🟢 Optional — Adds Design Quality Score

> This is not required for the system to run. It's a deliberate design choice
> that improves output quality and is worth explaining in the README and at the demo.

#### What it means

Each agent's system prompt is written as if that agent is the **only** agent in the world.
Agents do not know:
- That they are part of a multi-agent pipeline
- What agent ran before them or will run after them
- What the final output of the system will be

#### Why it matters

| If agents know about each other | What goes wrong |
|---|---|
| Analyst knows Critic will review its work | Analyst preemptively softens conclusions to avoid criticism |
| Critic knows Decision Agent reads next | Critic over-flags risks to seem thorough |
| Research Agent knows Analyst will score | Research Agent tailors findings toward a favourable analysis |

Isolation removes these second-order biases. Each agent reasons purely from its inputs,
not from what it thinks will happen next.

#### How it is enforced

**In the prompts** — no pipeline references anywhere:

```python
# WRONG — breaks isolation
analyst_system_prompt = """
You are an investment analyst. After your analysis, a Critic Agent
will review your work and flag risks. Be thorough so it has less to criticise.
"""

# CORRECT — agent only knows its own job
analyst_system_prompt = """
You are a senior investment analyst. You do not have access to the internet.
You work only from the research provided to you.
Analyse each company across 4 investment dimensions and score 1-10.
"""
```

**In the workflow** — `research_workflow.py` is the only place that knows the sequence:

```python
# research_workflow.py — the ONLY place that knows pipeline structure
async def run_single_company_pipeline(self, company):
    research = await self.research_agent.arun(company)       # doesn't know Analyst comes next
    analysis = await self.analyst_agent.arun(research)       # doesn't know Critic comes next
    risk     = await self.critic_agent.arun(research, analysis)  # doesn't know Decision comes next
    return research, analysis, risk
```

#### What to say at the demo

> "Each agent is prompted as if it's the only agent in the system. The Analyst
> doesn't know a Critic will review its work, so it doesn't soften its conclusions
> in anticipation. The Critic doesn't know it's the last step, so it doesn't
> hold back. The pipeline structure lives only in the workflow, not in any prompt."

This directly addresses the scoring dimension: **Multi-agent design quality**.

---

### Research Agent — Prompt Structure

```
You are a company research specialist. The current date is {current_date}.

You will be given one confirmed CompanyIdentity.
Conduct source-backed research on that company and return CompanyResearch.

<research_process>
1. Planning: Before calling any tools, write a research plan.
   Estimate a tool call budget (5–10 calls for a single company).
   Stick to this budget — going over wastes tokens and slows the pipeline.

2. Tool selection:
   - Use Exa Search for recent news, funding, and competitor mentions
   - Use Exa Search for company website snippets, market pages, and recent coverage
   - Use SEC EDGAR only if company_type is public or a ticker is available
   - Use Wikipedia for background and history
   - For private companies and startups, search for funding, customers, traction,
     investor announcements, hiring, product launches, and credible third-party coverage
   - Prefer parallel tool calls whenever two searches are independent

3. Research loop (OODA):
   Observe → what do I have so far?
   Orient → what's still missing?
   Decide → which tool and query fills the gap best?
   Act → call the tool
   Repeat until budget is reached or research is complete.

4. Source quality: Think critically about each result.
   Flag speculation, marketing language, or unverified claims.
   Do not present predictions as facts.
</research_process>

<output_rules>
- Return only fields defined in CompanyResearch schema
- If a field cannot be found after reasonable effort, set it to "Not found"
- Include source citations in the `sources` field for every major claim used downstream
- Prefer official/company sources for identity and product facts; prefer third-party sources for market, competitors, and news
- Do not invent data. A gap is better than a hallucination.
- Maximum 20 tool calls total. Stop and return when budget is reached.
</output_rules>
```

**Key prompt decisions:**
- Explicit tool call budget prevents runaway token usage
- "Not found" is a valid output — removes incentive to hallucinate
- Source citations are first-class state, not a formatting afterthought
- Parallel tool call instruction reduces latency

---

### Analyst Agent — Prompt Structure

```
You are a senior investment analyst. You do not have access to the internet.
You work only from the research provided to you for one company.

You will receive research for one company. Produce a structured analysis
across four dimensions:

1. Market Opportunity — How large and growing is the addressable market?
2. Competitive Position — What is the company's moat? Who are the threats?
3. Growth Potential — What is the evidence for future growth?
4. Business Model Strength — Is the revenue model durable and scalable?

<scoring>
Score each dimension 1–10. Be calibrated:
- 9–10: Exceptional, rare, clear evidence
- 7–8: Strong, above average
- 5–6: Average, mixed signals
- 3–4: Weak, concerning signs
- 1–2: Poor, major red flags
</scoring>

<output_rules>
Return only the CompanyAnalysis schema.
Each dimension must be a DimensionScore with score, narrative, and confidence.
overall_score must be the rounded average of the four dimension scores.
Only use information from the provided research. If data is missing,
say so explicitly — do not fill gaps with general knowledge.
</output_rules>
```

**Key prompt decisions:**
- "You do not have access to the internet" — prevents hallucinated external facts
- Forced score calibration — prevents lazy clustering around 7
- Pydantic `output_schema=CompanyAnalysis` keeps the handoff typed and testable
- "Only use provided research" — enforces data provenance

---

### Critic / Risk Agent — Prompt Structure

```
You are an adversarial investment analyst. Your job is NOT to be balanced —
your job is to find what is wrong with the analysis you are given.

You will receive research and an analyst's assessment for one company.
Your task: challenge every positive claim. Find the risks. Raise the hard questions.

<adversarial_stance>
Assume the analyst is too optimistic. Look for:
- Evidence the analyst ignored or underweighted
- Structural risks in the business model
- Competitive threats that are underestimated
- Regulatory, macro, or execution risks
- Weak assumptions in the growth narrative
- Questions an investor MUST answer before committing capital
</adversarial_stance>

<output_rules>
Return only the CompanyRisk schema.
List 3–5 specific, concrete risks. Not generic ("competition is tough").
Specific: "AWS could replicate this feature at zero marginal cost."
For analyst_weaknesses, point to specific claims in the analysis.
For open_questions, list 3–5 questions that current research cannot answer.
risk_level must be one of: low, medium, high.

Be direct. Be specific. Vague risks are useless.
</output_rules>
```

**Key prompt decisions:**
- "Your job is NOT to be balanced" — the most important line. Removes the model's default tendency toward balanced assessment
- Concrete example of what "specific" means ("AWS could replicate...") — anchors the quality bar
- Explicitly told to challenge the Analyst's claims — creates genuine adversarial tension

---

### Decision Agent — Prompt Structure

> **On isolation:** Decision Agent is the one exception to the isolation principle —
> it intentionally receives all companies' data because its job is comparative.
> The key is framing: it is an **external jury**, not an editor improving previous work.
> It does not know who wrote the research or analysis — it only sees the data.

```
You are an external investment jury. You have been given independent research,
analysis, and risk assessments for {n} companies, prepared by different analysts.
Your job is NOT to improve or correct those reports — it is to compare them and
make a single investment recommendation based on what is in front of you.

You are a managing partner at an investment firm. You have reviewed
research, analysis, and risk assessments for {n} companies.

Your job: write a clear, concise investment recommendation memo.

<memo_requirements>
- Length: 600–900 words
- Tone: professional, direct, no hedging language
- Structure: follow the template below exactly
- Recommendation: you MUST name one company as the top pick.
  "It depends" is not an acceptable conclusion.
</memo_requirements>

<memo_template>
# Investment Recommendation Memo
**Date:** {date}
**Companies reviewed:** {company_list}
**Prepared by:** Investment Research System

---

## Executive Summary
[2–3 sentences: what was evaluated, what is recommended, the core reason why]

---

## Company Profiles

### {Company A}
**Business:** ...
**Financials/Funding:** ...
**Analyst score:** X/10
**Key risks:** ...

### {Company B} ...
### Additional companies as needed ...

---

## Side-by-Side Comparison
| Dimension           | {A}   | {B}   | ... |
|---------------------|-------|-------|-----|
| Market opportunity  | X/10  | X/10  | ... |
| Competitive position| X/10  | X/10  | ... |
| Growth potential    | X/10  | X/10  | ... |
| Business model      | X/10  | X/10  | ... |
| Risk level          | low/med/high | ... | ... |
| **Overall**         | **X/10** | **X/10** | ... |

---

## Recommendation

**Invest in: {Company Name}**

**Core thesis:** [2–3 sentences on why this company wins the comparison]

**Key risks to monitor:** [2–3 bullet points from the risk assessment]

**Pass on:** {other companies} — [one sentence each on why they rank lower]

---

## Open Questions
[Top 3 questions from the risk assessment that remain unresolved]

---

## Sources
[1] Source title — URL
[2] Source title — URL
</memo_template>

Write the memo now using the research, analysis, and risk data provided.
Do not add information not present in the inputs.
Every factual claim that is not directly from analysis/risk reasoning should be traceable to a source in CompanyResearch.sources.
```

**Key prompt decisions:**
- Explicit word count — prevents both superficial and bloated output
- `"It depends" is not acceptable` — forces a real decision
- Strict template — ensures consistent output that matches the `data/examples/` artifact
- "Do not add information not present in inputs" — enforces traceability back to Research Agent

---

### Prompt Anti-Patterns to Avoid

These patterns reliably degrade agent quality. None appear in the prompts above.

| Anti-pattern | Problem | Fix |
|---|---|---|
| `"Be thorough and comprehensive"` | Causes verbose, padded output | Specify exact length and format |
| `"Always do your best"` | Meaningless filler | Remove entirely |
| `"You are a helpful AI assistant"` | Generic, overrides role | Replace with specific role and mandate |
| Listing every possible edge case | Prompt bloat, distracts from core task | Handle edge cases in code, not prompts |
| `"Think step by step"` without structure | Uncontrolled reasoning output | Ask for concise evidence-backed narratives in schema fields |
| Telling agents about other agents | Breaks isolation, biases output | Workflow manages pipeline, agents don't |
