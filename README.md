# observability_sdk

Drop-in AI observability plugin for FastAPI + React/Streamlit projects.

Captures LLM call metrics, agent activity, and system health — and renders them as a full dashboard page inside your existing app. No cloud, no external services, no database setup. Everything runs locally via SQLite.

---

## What it captures

| Metric | Details |
|---|---|
| LLM calls | Model, provider, prompt tokens, completion tokens, latency, cost, status, caller endpoint |
| Agent activity | Agent name, status (RUNNING / COMPLETED / FAILED), description, duration |
| System health | Derived from success rates — Healthy / Degraded / Unhealthy |

---

## Project requirements

Before plugging in this SDK, your project must have:

### Backend
- **FastAPI** — the SDK mounts its REST endpoints onto your existing app
- **Python 3.10+**
- No additional pip packages needed — only Python stdlib (`sqlite3`, `json`, `time`, `threading`)

### Frontend (pick one)
- **React + TypeScript** with Tailwind CSS and shadcn/ui — for the React dashboard page
- **Streamlit** — for the Streamlit dashboard page

### Optional but recommended
- An Express BFF that proxies `/api/*` to FastAPI — the React page uses `/api/observability/*` which will automatically proxy through if your BFF has a catch-all `/api/*` rule

---

## File structure

```
observability_sdk/
├── __init__.py                          # Public API + setup_observability()
├── backend/
│   ├── __init__.py
│   ├── store.py                         # SQLite persistence — zero dependencies
│   ├── middleware.py                    # FastAPI middleware + LLM decorators
│   ├── tracker.py                       # Agent activity decorators
│   └── router.py                        # /observability/* REST endpoints
├── frontend/
│   ├── __init__.py
│   ├── react/
│   │   └── ObservabilityPage.tsx        # Drop-in React page
│   └── streamlit_dashboard.py          # Drop-in Streamlit page
└── docs/
    ├── REQUIREMENTS.md                  # This file — what your project needs
    ├── INTEGRATE_CONTROLTESTER.md       # Step-by-step for ControlTester 3000
    └── INTEGRATE_GENERIC.md             # Step-by-step for any FastAPI+React project
```

---

## Quick start (3 lines)

```python
# In your FastAPI main.py, after app = FastAPI(...)
from observability_sdk import setup_observability
setup_observability(app, db_path="observability.db")
```

Then visit `/observability/dashboard` to see raw data, or add the React/Streamlit page for the full UI.

---

## REST endpoints (auto-mounted)

| Method | Path | Description |
|---|---|---|
| GET | `/observability/dashboard` | Full dashboard stats (configurable time window) |
| GET | `/observability/health` | Quick health check |
| GET | `/observability/llm-calls` | Paginated LLM call log |
| GET | `/observability/agent-events` | Paginated agent activity log |
| POST | `/observability/ingest/llm` | Manual LLM event ingestion |
| POST | `/observability/ingest/agent` | Manual agent event ingestion |

---

## Instrumenting LLM calls

### Class method decorator
```python
from observability_sdk import track_llm_generate

class YourLLMClient:
    model_name = "gemini-2.5-flash"

    @track_llm_generate(model_name_attr="model_name")
    async def generate(self, prompt, context="", system_prompt=""):
        # your existing code — unchanged
        ...
```

### Function decorator
```python
from observability_sdk import track_llm_call

@track_llm_call
async def call_llm(prompt: str) -> dict:
    # Must return: {response, prompt_tokens, completion_tokens, model_name}
    ...
```

### Manual recording
```python
from observability_sdk import record_llm_call

record_llm_call(
    model="llama3.2:latest",
    prompt_tokens=150,
    completion_tokens=320,
    latency_ms=1240,
    provider="ollama",
    status="success",
    caller="/api/control-testing",
)
```

---

## Instrumenting agents

### Decorator
```python
from observability_sdk import track_agent

@track_agent("ControlTestingAgent")
async def analyze_evidence(session_data, ...):
    ...
```

### Context manager
```python
from observability_sdk import agent_span

async with agent_span("RCMAnalyzer", "Running RCM compliance check"):
    result = await analyzer.run(doc)
```

### Manual (for sync code)
```python
from observability_sdk import start_agent, finish_agent, fail_agent
import time

ts = time.perf_counter()
start_agent("WorkpaperGenerator", "Generating audit workpaper")
try:
    result = fill_workpaper(...)
    finish_agent(ts, "WorkpaperGenerator", "Workpaper generated successfully")
except Exception as e:
    fail_agent(ts, "WorkpaperGenerator", str(e))
    raise
```

---

## Cost configuration

Built-in cost rates for common models (USD per 1k tokens):

| Model | Cost/1k tokens |
|---|---|
| gemini-2.5-flash | $0.000075 |
| gemini-2.5-pro | $0.00125 |
| gpt-4o | $0.005 |
| gpt-4o-mini | $0.00015 |
| claude-sonnet-4-5 | $0.003 |
| llama3 / Ollama models | $0.00 |

Override for custom models:
```python
setup_observability(app, cost_overrides={"my-custom-model": 0.0002})
```
