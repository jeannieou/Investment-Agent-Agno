# Demo Script

This script shows the stable no-key demo first, then the optional live-agent path.

## 1. Start Clean

Activate the virtual environment:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
pytest
```

Expected result: all tests pass.

## 2. Run The Stable CLI Demo

```bash
python -m app.main --mock "Nvidia,AMD,Intel"
```

Expected result:

- markdown memo prints to the terminal
- `Companies: 3`
- `Agent runs: 13`
- memo contains `Invest in: Nvidia`
- memo contains `## Sources`

## 3. Save Example Artifacts

```bash
python -m app.main --mock --save-example "Nvidia,AMD,Intel"
```

Expected files:

```text
data/examples/nvidia_amd_intel/
  memo.md
  workflow_state.json
  run_log.json
```

Open `run_log.json` to show per-agent observability.

## 4. Run AgentOS UI

Start the local AgentOS API:

```bash
python -m app.agent_os
```

Open:

```text
https://os.agno.com/
```

Select:

```text
Workflows -> Mock Investment Research
```

Enter:

```text
Nvidia,AMD,Intel
```

Recommended input size: up to 6 companies. Hard limit: 8 companies.

Expected backend logs:

```text
[agentos request] POST /sessions -> 201
[agentos progress] Running mock workflow for Nvidia, AMD, Intel
[agentos progress] Mock workflow complete
```

Expected UI result: final investment memo appears.

## 5. Optional Live Agent Demo

Configure `.env`:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=...
EXA_API_KEY=...
```

Run:

```bash
python -m app.main --live --provider openai "Nvidia,Anthropic,Perplexity AI"
```

Expected result:

- Identity Agent resolves all companies
- Research Agent uses available tools
- Analyst and Critic produce typed outputs
- Decision Agent writes the final memo
- failures become warnings and fallback objects instead of crashing the run

## 6. Troubleshooting

If AgentOS UI cannot connect:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*app.agent_os*' } | Select-Object ProcessId,CommandLine
```

Stop stale `app.agent_os` processes and restart:

```bash
python -m app.agent_os
```

If the backend logs mention missing WebSocket support, reinstall:

```bash
pip install "uvicorn[standard]"
```
