"""
observability_sdk
==================
Drop-in AI observability plugin for FastAPI + Streamlit projects.

Captures:
  - LLM call metrics (model, tokens, cost, latency, status)
  - Agent activity (name, status, duration, description)
  - System health summary

Quick start (3 lines in your FastAPI main.py):
---------------------------------------------------
    from observability_sdk import setup_observability
    setup_observability(app, db_path="observability.db")

Then in your Streamlit page:
    from observability_sdk.frontend.streamlit_dashboard import render_dashboard
    render_dashboard(api_base_url="http://localhost:5000/observability")

Instrument LLM calls (decorator approach):
    from observability_sdk import track_llm_generate

    class YourLLMClient:
        model_name = "gemini-2.5-flash"

        @track_llm_generate()
        async def generate(self, prompt, context="", system_prompt=""):
            ...

Instrument agent methods:
    from observability_sdk import track_agent

    @track_agent("GapRemediationAgent")
    async def generate_recommendations(self, gap_description, framework, ...):
        ...
"""

from .backend.store import init_store, record_llm_call, record_agent_event
from .backend.middleware import ObservabilityMiddleware, track_llm_call, track_llm_generate
from .backend.tracker import track_agent, agent_span, start_agent, finish_agent, fail_agent
from .backend.router import router as observability_router


def setup_observability(
    app,
    db_path: str = "observability.db",
    prefix: str = "/observability",
    cost_overrides: dict = None,
):
    """
    One-call setup. Call this in your FastAPI lifespan or at module level.

    Parameters
    ----------
    app : FastAPI
        Your FastAPI application instance.
    db_path : str
        Path to the SQLite database file. Created automatically if absent.
    prefix : str
        URL prefix for observability endpoints. Default: /observability
    cost_overrides : dict
        Optional dict of model_name → cost_per_1k_tokens (USD).
        Pre-populated defaults cover Gemini, Ollama, OpenAI, Anthropic.

    Example
    -------
        from observability_sdk import setup_observability
        setup_observability(app, db_path="data/observability.db")
    """
    # 1. Initialise SQLite store
    init_store(db_path=db_path, cost_overrides=cost_overrides)

    # 2. Add request-tracking middleware
    app.add_middleware(ObservabilityMiddleware)

    # 3. Mount observability REST endpoints
    app.include_router(observability_router, prefix=prefix)

    import logging
    logging.getLogger("observability_sdk").info(
        f"Observability SDK initialised — db={db_path}, endpoints at {prefix}/*"
    )


def mount_router(app, prefix: str = "/observability"):
    """
    Mount only the router (if you want to call init_store separately).
    """
    app.include_router(observability_router, prefix=prefix)


__all__ = [
    # Setup
    "setup_observability",
    "mount_router",
    # Store (manual recording)
    "init_store",
    "record_llm_call",
    "record_agent_event",
    # Middleware
    "ObservabilityMiddleware",
    # Decorators
    "track_llm_call",
    "track_llm_generate",
    "track_agent",
    "agent_span",
    "start_agent",
    "finish_agent",
    "fail_agent",
]
