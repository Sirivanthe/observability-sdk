# Integrating observability_sdk into ControlTester 3000

Tested and proven on macOS with Node 25, Python 3.12, MongoDB 7, Ollama.
Follow steps in order. Do not skip ahead.

---

## Prerequisites

- ControlTester 3000 cloned locally
- MongoDB running: `brew services start mongodb-community`
- Ollama running with a model pulled: `ollama pull llama3.2`
- Python 3.10+

---

## Step 1 — Copy the SDK into the project

```bash
cp -r /path/to/observability-sdk /path/to/ControlTester_3000_kv/observability_sdk
```

Verify:
```
ls observability_sdk/
→ README.md  __init__.py  backend  docs  example  frontend  gitignore
```

---

## Step 2 — Create .env file

```bash
cd /path/to/ControlTester_3000_kv

echo 'MONGO_URI=mongodb://localhost:27017
OLLAMA_LLM_MODEL=llama3.2:latest' > .env
```

Check your actual Ollama model name with:
```bash
curl http://localhost:11434/api/tags
```

---

## Step 3 — Fix MongoDB connection

Run this from inside the ControlTester folder:

```bash
python3 << 'EOF'
from pathlib import Path
f = Path("utils/control_assurance/ct_db.py")
c = f.read_text()
old = 'MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")\n_client: pymongo.MongoClient | None = None\n\n\ndef _get_db():\n    global _client\n    if _client is None:\n        _client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)\n    return _client["trace_db"]'
new = '_client: pymongo.MongoClient | None = None\n\n\ndef _get_db():\n    global _client\n    if _client is None:\n        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")\n        _client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)\n    return _client["trace_db"]'
if old in c:
    f.write_text(c.replace(old, new, 1))
    print("patched")
else:
    print("already patched or content differs")
EOF
```

---

## Step 4 — Fix Node.js reusePort (macOS only)

```bash
sed -i '' 's/    listenOptions.reusePort = true;/    \/\/ listenOptions.reusePort = true;/' \
  kpmg_ui/server/index.ts
```

Verify: `grep -n "reusePort" kpmg_ui/server/index.ts`
Expected: line shows `// listenOptions.reusePort = true;`

---

## Step 5 — Wire SDK into FastAPI (api/main.py)

```bash
sed -i '' 's/from utils.control_assurance.ct_db import ensure_indexes as ct_ensure_indexes/from utils.control_assurance.ct_db import ensure_indexes as ct_ensure_indexes\nfrom observability_sdk import setup_observability/' api/main.py
```

Find the line number where app = FastAPI(...) closes:
```bash
grep -n "^)" api/main.py | head -5
```

The closing `)` is typically around line 184-186. Insert after it (replace 185 with actual line number):
```bash
sed -i '' '185a\
\
setup_observability(app, db_path="api/observability.db")\
' api/main.py
```

Verify:
```bash
grep -n "setup_observability" api/main.py
```

Expected (two lines):
```
79:from observability_sdk import setup_observability
187:setup_observability(app, db_path="api/observability.db")
```

---

## Step 6 — Add the React page

```bash
cp observability_sdk/frontend/react/ObservabilityPage.tsx \
   kpmg_ui/client/src/pages/observability.tsx
```

---

## Step 7 — Wire into App.tsx

```bash
sed -i '' 's/import { AssetRegistryProvider } from "@\/contexts\/AssetRegistryContext";/import ObservabilityPage from "@\/pages\/observability";\nimport { AssetRegistryProvider } from "@\/contexts\/AssetRegistryContext";/' \
  kpmg_ui/client/src/App.tsx

sed -i '' 's|{ path: "/asset-registry",       Page: AssetRegistryPage       },|{ path: "/asset-registry",       Page: AssetRegistryPage       },\n  { path: "/observability",         Page: ObservabilityPage       },|' \
  kpmg_ui/client/src/App.tsx
```

Verify:
```bash
grep -n "ObservabilityPage\|observability" kpmg_ui/client/src/App.tsx
```

Expected:
```
43:import ObservabilityPage from "@/pages/observability";
69:  { path: "/observability",         Page: ObservabilityPage       },
```

---

## Step 8 — Add sidebar nav entry

```bash
sed -i '' 's/  FileStack,/  FileStack,\n  Activity,/' \
  kpmg_ui/client/src/components/AppLayout.tsx

sed -i '' 's/{ title: "Issue Management", fullTitle: "Issue Management", path: "\/issue-management", icon: AlertTriangle },/{ title: "Issue Management", fullTitle: "Issue Management", path: "\/issue-management", icon: AlertTriangle },\n  { title: "Observability", fullTitle: "Model Observability", path: "\/observability", icon: Activity },/' \
  kpmg_ui/client/src/components/AppLayout.tsx
```

Verify:
```bash
grep -n "Activity\|Observability" kpmg_ui/client/src/components/AppLayout.tsx
```

Expected:
```
20:  Activity,
62:  { title: "Observability", fullTitle: "Model Observability", path: "/observability", icon: Activity },
```

---

## Step 9 — Run and verify

**Terminal 1 — FastAPI:**
```bash
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Look for in startup log:
```
Observability SDK initialised — db=api/observability.db, endpoints at /observability/*
Application startup complete.
```

**Terminal 2 — React:**
```bash
cd kpmg_ui
npm install
PORT=5002 npm run dev
```

Open `http://localhost:5002` → login `admin@bank.com` / `zUlqVAZ5wt` → click **Observability** in sidebar.

---

## What you should see

- 4 Model Performance cards — all 0 initially, fills as you use the app
- 3 Agent Activity cards — all 0 until agents are instrumented
- System Health — Model Performance: Healthy, Agent Operations: Unhealthy (expected)
- Empty tables — fill as LLM calls are made

---

## Files changed (7 files, ~15 lines)

| File | Change |
|---|---|
| `.env` | Created — MongoDB URI + Ollama model |
| `utils/control_assurance/ct_db.py` | MONGO_URI read lazily |
| `kpmg_ui/server/index.ts` | reusePort commented out (macOS) |
| `api/main.py` | Import + setup_observability() call |
| `kpmg_ui/client/src/pages/observability.tsx` | New file — copied from SDK |
| `kpmg_ui/client/src/App.tsx` | Import + route |
| `kpmg_ui/client/src/components/AppLayout.tsx` | Activity icon + nav entry |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ServerSelectionTimeoutError: mongodb:27017` | Add `MONGO_URI=mongodb://localhost:27017` to `.env` |
| `ENOTSUP` on port | Comment out `listenOptions.reusePort = true` in `kpmg_ui/server/index.ts` |
| `Cannot add middleware after app started` | Move `setup_observability()` to module level, not inside `lifespan()` |
| Observability not in sidebar | Check AppLayout.tsx has Activity import and nav entry |
| Page shows "API unreachable" | FastAPI not running, or setup_observability() not called |
| Dark card backgrounds | Make sure you copied the latest ObservabilityPage.tsx from the SDK |
