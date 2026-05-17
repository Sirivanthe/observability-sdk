# Integrating observability_sdk into ControlTester 3000

This guide adds the full Model Observability dashboard to ControlTester 3000 (TRACE).
Follow the steps in order. Each step is independently verifiable before moving to the next.

---

## Prerequisites

- ControlTester 3000 cloned and running locally (see its README)
- `observability_sdk/` folder copied into the project root:
  ```
  ControlTester_3000_kv/
  ├── observability_sdk/    ← copy here
  ├── api/
  ├── kpmg_ui/
  └── ...
  ```

---

## Step 1 — Fix MongoDB connection for local dev

The default `MONGO_URI` is hardcoded at module level in `utils/control_assurance/ct_db.py`,
which means it's read before `.env` is loaded. Fix it to read lazily:

**File:** `utils/control_assurance/ct_db.py`

Find:
```python
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
_client: pymongo.MongoClient | None = None


def _get_db():
    global _client
    if _client is None:
        _client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    return _client["trace_db"]
```

Replace with:
```python
_client: pymongo.MongoClient | None = None


def _get_db():
    global _client
    if _client is None:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        _client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    return _client["trace_db"]
```

> **Why:** The original reads the env var at import time, before `load_dotenv()` runs in `main.py`.
> Moving it inside `_get_db()` means it's read at first connection, after the env is loaded.

---

## Step 2 — Add `.env` entry for local MongoDB

In your `.env` file (copy from `.env.example` if it doesn't exist), add:

```
MONGO_URI=mongodb://localhost:27017
OLLAMA_LLM_MODEL=llama3.2:latest
```

> **Note:** Change `llama3.2:latest` to match whatever model you have pulled in Ollama.
> Check with: `curl http://localhost:11434/api/tags`

---

## Step 3 — Wire the SDK into FastAPI

**File:** `api/main.py`

**Change 1** — Add import (after the existing imports, around line 78):
```python
from observability_sdk import setup_observability
```

**Change 2** — Call setup after `app = FastAPI(...)` is defined (around line 186, after the closing `)` of the FastAPI constructor):
```python
# Observability SDK — must be added before first request, after app creation
setup_observability(app, db_path="api/observability.db")
```

> **Why after `app = FastAPI(...)`:** FastAPI middleware must be added before the app starts
> handling requests, but after the app object exists. Adding it inside `lifespan()` is too late.

**Verify:** Start the API and check:
```bash
curl http://localhost:8000/observability/health
```
Expected response:
```json
{"status": "ok", "model_performance": "Healthy", "agent_operations": "Unhealthy", ...}
```

---

## Step 4 — Instrument the LLM client (optional but recommended)

To get real LLM call metrics, wrap the `generate()` method of your LLM client.

Find your LLM client class — likely in `utils/llm_provider.py` or `utils/llm_factory.py`.
Look for a class with an async `generate()` method that returns a dict with `response`, `prompt_tokens`, `completion_tokens`, `model_name`.

Add the decorator:
```python
from observability_sdk import track_llm_generate

class YourLLMClient:
    model_name = "llama3.2:latest"   # or whatever attribute holds the model name

    @track_llm_generate(model_name_attr="model_name")
    async def generate(self, prompt, ...):
        ...  # your existing code unchanged
```

For the Ollama client specifically, find where `ollama.chat()` or similar is called and wrap it with `record_llm_call()` if it's not a class method:
```python
from observability_sdk import record_llm_call
import time

start = time.perf_counter()
response = ollama.chat(model=model, messages=messages)
record_llm_call(
    model=model,
    prompt_tokens=response.get("prompt_eval_count", 0),
    completion_tokens=response.get("eval_count", 0),
    latency_ms=(time.perf_counter() - start) * 1000,
    provider="ollama",
    status="success",
)
```

---

## Step 5 — Add the React page

**File to create:** `kpmg_ui/client/src/pages/observability.tsx`

Copy `observability_sdk/frontend/react/ObservabilityPage.tsx` to that path:
```bash
cp observability_sdk/frontend/react/ObservabilityPage.tsx \
   kpmg_ui/client/src/pages/observability.tsx
```

---

## Step 6 — Wire into App.tsx

**File:** `kpmg_ui/client/src/App.tsx`

**Change 1** — Add import (with the other page imports):
```typescript
import ObservabilityPage from "@/pages/observability";
```

**Change 2** — Add route to the `PAGES` array:
```typescript
{ path: "/observability", Page: ObservabilityPage },
```

Place it after the `/asset-registry` entry:
```typescript
{ path: "/asset-registry",  Page: AssetRegistryPage  },
{ path: "/observability",   Page: ObservabilityPage  },  // ← add this
```

---

## Step 7 — Add sidebar nav entry

**File:** `kpmg_ui/client/src/components/AppLayout.tsx`

**Change 1** — Add `Activity` to the lucide-react import:
```typescript
import {
  // ... existing imports ...
  Activity,       // ← add this
} from "lucide-react";
```

**Change 2** — Add nav entry to `HIDEABLE_TABS` array (after Issue Management):
```typescript
{ title: "Issue Management", fullTitle: "Issue Management", path: "/issue-management", icon: AlertTriangle },
{ title: "Observability", fullTitle: "Model Observability", path: "/observability", icon: Activity },  // ← add this
```

---

## Step 8 — Fix Node.js reusePort issue (macOS only)

If you see `ENOTSUP` when running the dev server on macOS with Node 25+:

**File:** `kpmg_ui/server/index.ts`

Find and comment out:
```typescript
listenOptions.reusePort = true;
```

Replace with:
```typescript
// listenOptions.reusePort = true; // disabled — not supported on macOS Node 25+
```

---

## Step 9 — Run and verify

Start MongoDB:
```bash
brew services start mongodb-community
```

Start FastAPI (terminal 1):
```bash
cd /path/to/ControlTester_3000_kv
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Look for this line in the startup log:
```
Observability SDK initialised — db=api/observability.db, endpoints at /observability/*
```

Start the React dev server (terminal 2):
```bash
cd kpmg_ui
PORT=5002 npm run dev
```

Open `http://localhost:5002`, log in with:
- Email: `admin@bank.com`
- Password: `zUlqVAZ5wt`

Navigate to **Observability** in the sidebar.

---

## What you should see

- **Model Performance** — 0 requests initially (increases as you use the app)
- **Agent Activity** — 0 activities initially
- **System Health** — Model Performance: Healthy, Agent Operations: Unhealthy (0% — no agents tracked yet)
- **Recent Model Metrics** — empty until LLM calls are instrumented (Step 4)

Run a control test or risk assessment, then refresh the Observability page to see real data.

---

## Files changed summary

| File | Change |
|---|---|
| `utils/control_assurance/ct_db.py` | MONGO_URI read lazily inside `_get_db()` |
| `.env` | Added `MONGO_URI` and correct Ollama model |
| `api/main.py` | Import + `setup_observability(app, ...)` call |
| `kpmg_ui/client/src/pages/observability.tsx` | New file — copied from SDK |
| `kpmg_ui/client/src/App.tsx` | Import + route entry |
| `kpmg_ui/client/src/components/AppLayout.tsx` | `Activity` import + nav entry |
| `kpmg_ui/server/index.ts` | Comment out `reusePort` (macOS only) |

Total changes: **7 files, ~15 lines**.
