# Integrating observability_sdk — Generic Guide

Use this guide for any FastAPI + React/TypeScript project.
For ControlTester 3000 specifically, use `INTEGRATE_CONTROLTESTER.md` instead.

---

## Project compatibility checklist

Before integrating, verify your project has:

| Requirement | Why |
|---|---|
| FastAPI app object (`app = FastAPI(...)`) | SDK mounts middleware and routes onto it |
| Python 3.10+ | Type hints and match syntax |
| React 17+ with TypeScript | The `.tsx` page component |
| Tailwind CSS | Card and layout styles |
| shadcn/ui (`Card`, `Button`) | Used in `ObservabilityPage.tsx` |
| lucide-react | Icons (`Activity`, `Zap`, `Clock`, etc.) |
| A proxy from frontend to FastAPI | React page calls `/api/observability/*` |

If your project doesn't use shadcn/ui or lucide-react, you can swap those out in
`ObservabilityPage.tsx` for your own component library — the logic is the same.

---

## Backend integration (3 lines)

### 1. Copy the SDK

```bash
cp -r observability_sdk/ /path/to/your/project/
```

### 2. Add to your FastAPI app

In your `main.py` (or wherever `app = FastAPI(...)` is defined):

```python
from observability_sdk import setup_observability

app = FastAPI(...)

# Add immediately after app creation, before any routes or middleware
setup_observability(app, db_path="observability.db")
```

**Parameters:**

| Parameter | Default | Description |
|---|---|---|
| `app` | required | Your FastAPI instance |
| `db_path` | `"observability.db"` | Path to SQLite file — created automatically |
| `prefix` | `"/observability"` | URL prefix for all observability endpoints |
| `cost_overrides` | `None` | Dict of `model_name → cost_per_1k_tokens` |

### 3. Verify

```bash
curl http://localhost:8000/observability/health
```

---

## Instrument your LLM client

### Option A — Class decorator (recommended)

If your LLM client is a class with an async `generate()` method:

```python
from observability_sdk import track_llm_generate

class MyLLMClient:
    model_name = "your-model-name"

    @track_llm_generate(model_name_attr="model_name")
    async def generate(self, prompt: str, ...) -> dict:
        # Must return dict with: response, prompt_tokens, completion_tokens, model_name
        ...
```

### Option B — Function decorator

```python
from observability_sdk import track_llm_call

@track_llm_call
async def call_llm(prompt: str) -> dict:
    # Must return: {response, prompt_tokens, completion_tokens, model_name}
    ...
```

### Option C — Manual recording

For sync code or when you can't use decorators:

```python
from observability_sdk import record_llm_call
import time

start = time.perf_counter()
# ... your LLM call ...
record_llm_call(
    model="your-model",
    prompt_tokens=100,
    completion_tokens=250,
    latency_ms=(time.perf_counter() - start) * 1000,
    provider="ollama",   # gemini | openai | anthropic | ollama | unknown
    status="success",    # success | error
    caller="/api/your-endpoint",
)
```

---

## Instrument agent functions

```python
from observability_sdk import track_agent, agent_span

# Decorator
@track_agent("MyAgent")
async def run_analysis(...):
    ...

# Context manager
async with agent_span("MyAgent", "Running analysis on 5 documents"):
    result = await analyzer.run(docs)
```

---

## Frontend integration

### React + TypeScript

1. Copy the page component:
```bash
cp observability_sdk/frontend/react/ObservabilityPage.tsx \
   src/pages/observability.tsx
```

2. Update `API_BASE` at the top of the file if your proxy prefix differs:
```typescript
const API_BASE = "/api/observability";  // adjust if needed
```

3. Add to your router. For React Router:
```typescript
import ObservabilityPage from "./pages/observability";

<Route path="/observability" element={<ObservabilityPage />} />
```

4. Add to your sidebar/nav:
```typescript
import { Activity } from "lucide-react";

{ label: "Observability", path: "/observability", icon: Activity }
```

### Streamlit

```python
# In your Streamlit app or pages/observability.py
from observability_sdk.frontend.streamlit_dashboard import render_dashboard

render_dashboard(
    api_base_url="http://localhost:8000/observability",
    page_title="Model Observability",
)
```

---

## Proxy configuration

The React page calls `/api/observability/*`. Your proxy must forward this to FastAPI.

### Express BFF (catch-all pattern)
If your Express server already has:
```typescript
app.all("/api/*", proxyToFastAPI);
```
No changes needed — `/api/observability/*` will be forwarded automatically.

### Vite dev proxy
```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

### Nginx
```nginx
location /api/observability/ {
    proxy_pass http://fastapi:8000/observability/;
}
```

---

## Sidecar mode (no code changes)

If you can't modify the application code, run the SDK as a sidecar and POST events manually:

```bash
# Start the SDK as a standalone FastAPI service
uvicorn observability_sdk.sidecar:app --port 9000
```

Then POST events from your app:
```python
import httpx

# Record an LLM call
httpx.post("http://localhost:9000/observability/ingest/llm", json={
    "model": "gemini-2.5-flash",
    "prompt_tokens": 150,
    "completion_tokens": 320,
    "latency_ms": 1240,
    "provider": "gemini",
    "status": "success",
})

# Record agent activity
httpx.post("http://localhost:9000/observability/ingest/agent", json={
    "agent_name": "RiskAssessmentAgent",
    "description": "Completed risk assessment — 3 risks identified",
    "status": "COMPLETED",
    "duration_ms": 4200,
})
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `RuntimeError: Cannot add middleware after app started` | `setup_observability()` called inside `lifespan()` | Move the call to module level, after `app = FastAPI(...)` |
| `/observability/health` returns 404 | SDK not mounted | Check `setup_observability(app, ...)` was called |
| Cards show dark background | Theme CSS overriding Tailwind | Add `style={{background:"#ffffff"}}` inline to Card components |
| `ENOTSUP` on macOS | Node 25 + `reusePort` | Comment out `listenOptions.reusePort = true` in your Express server |
| 0 LLM calls recorded | LLM client not instrumented | Add `@track_llm_generate()` or `record_llm_call()` |
| Cost shows $0.0000 | Model name not in cost table | Add to `cost_overrides` in `setup_observability()` |
