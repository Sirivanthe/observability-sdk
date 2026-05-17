"""
HOW TO INTEGRATE observability_sdk INTO ControlTester_3000
===========================================================

STEP 1 — Copy the SDK
----------------------
Copy the `observability_sdk/` folder into your project root:

    ControlTester_3000_kv/
    ├── observability_sdk/       ← drop it here
    ├── api/
    │   └── main.py
    ├── kpmg_ui/
    └── ...


STEP 2 — Wire into api/main.py (3 lines)
------------------------------------------
Open api/main.py and add at the TOP (after existing imports):

    from observability_sdk import setup_observability

Then inside the lifespan function, after ct_ensure_indexes():

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ct_ensure_indexes()
        _seed_nist_controls()
        setup_observability(app, db_path="api/observability.db")  # ← ADD THIS
        ...

Full diff:

    + from observability_sdk import setup_observability

      @asynccontextmanager
      async def lifespan(app: FastAPI):
          ct_ensure_indexes()
          _seed_nist_controls()
    +     setup_observability(app, db_path="api/observability.db")
          if os.getenv("TASK_BACKEND", "asyncio").strip().lower() == "asyncio":
              start_async_pipeline_workers()
          ...


STEP 3 — Instrument your LLM client
--------------------------------------
Find your LLM client class (likely in utils/llm_factory.py or utils/llm_chain.py).
Add the decorator to the generate() method:

    from observability_sdk import track_llm_generate

    class YourLLMClient:
        model_name = "llama3"   # or whatever attribute holds the model name

        @track_llm_generate(model_name_attr="model_name", provider_attr="ollama")
        async def generate(self, prompt, ...):
            ...  # your existing code unchanged

If you use a function (not a class method), use track_llm_call instead:

    from observability_sdk import track_llm_call

    @track_llm_call
    async def call_llm(prompt: str) -> dict:
        # Must return dict with: response, prompt_tokens, completion_tokens, model_name
        ...


STEP 4 — Instrument agent functions (optional but recommended)
---------------------------------------------------------------
Wrap your main agent/analysis functions:

    from observability_sdk import track_agent

    @track_agent("AuditAnalyzer")
    async def analyze_all_controls(session_data, ...):
        ...

    @track_agent("WorkpaperGenerator")
    async def fill_workpaper_template(...):
        ...

For synchronous functions or non-async code, use manual tracking:

    from observability_sdk import start_agent, finish_agent, fail_agent
    import time

    def analyze_evidence(session_data):
        ts = time.perf_counter()
        start_agent("EvidenceAnalyzer", "Analyzing uploaded evidence files")
        try:
            result = _do_analysis(session_data)
            finish_agent(ts, "EvidenceAnalyzer", f"Analyzed {len(result)} controls")
            return result
        except Exception as e:
            fail_agent(ts, "EvidenceAnalyzer", str(e))
            raise


STEP 5 — Add the Streamlit page
---------------------------------
Create a new file: kpmg_ui/pages/observability.py

    from observability_sdk.frontend.streamlit_dashboard import render_dashboard

    render_dashboard(
        api_base_url="http://localhost:5000/observability",
        page_title="Model Observability",
    )

Streamlit auto-discovers files in pages/ — the page will appear in the
sidebar automatically as "Observability".


STEP 6 — Verify
-----------------
Start the API:
    uvicorn api.main:app --reload --port 5000

Check the endpoints are live:
    curl http://localhost:5000/observability/health
    curl http://localhost:5000/observability/dashboard

Run a few audit operations, then open the Streamlit app and navigate to
the Observability page. You should see real LLM call metrics.


THAT'S IT. No database setup, no env vars, no migrations.
The SQLite file is created automatically at api/observability.db.
"""
