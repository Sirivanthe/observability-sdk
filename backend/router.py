"""
observability_sdk.backend.router
-----------------------------------
Mountable FastAPI router that exposes observability data via REST.

Mount in your app with two lines:
    from observability_sdk import mount_router
    mount_router(app, prefix="/observability")

Endpoints:
    GET /observability/dashboard        — full dashboard stats
    GET /observability/llm-calls        — recent LLM call log
    GET /observability/agent-events     — recent agent activity
    GET /observability/health           — system health summary
    POST /observability/ingest/llm      — manual LLM event ingestion
    POST /observability/ingest/agent    — manual agent event ingestion
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any

from .store import (
    get_dashboard_stats,
    get_llm_calls,
    get_agent_events,
    record_llm_call,
    record_agent_event,
)

router = APIRouter(tags=["observability"])


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(hours: int = Query(24, ge=1, le=168)):
    """Full observability dashboard data. `hours` controls the lookback window (default 24h, max 7d)."""
    return get_dashboard_stats(hours=hours)


@router.get("/health")
async def health():
    """Quick system health check — returns model performance and agent health."""
    stats = get_dashboard_stats(hours=1)
    return {
        "status": "ok",
        "model_performance": stats["system_health"]["model_performance"],
        "agent_operations": stats["system_health"]["agent_operations"],
        "last_hour": {
            "requests": stats["model_performance"]["total_requests"],
            "avg_latency_ms": stats["model_performance"]["avg_latency_ms"],
            "success_rate": stats["model_performance"]["success_rate"],
        },
    }


# ── Call logs ─────────────────────────────────────────────────────────────────

@router.get("/llm-calls")
async def llm_calls(
    limit: int = Query(50, ge=1, le=500),
    model: Optional[str] = None,
    hours: int = Query(24, ge=1, le=168),
):
    """Paginated LLM call log with optional model filter."""
    return {"calls": get_llm_calls(limit=limit, model=model, hours=hours)}


@router.get("/agent-events")
async def agent_events(
    limit: int = Query(50, ge=1, le=500),
    agent_name: Optional[str] = None,
    hours: int = Query(24, ge=1, le=168),
):
    """Paginated agent event log with optional agent name filter."""
    return {"events": get_agent_events(limit=limit, agent_name=agent_name, hours=hours)}


# ── Manual ingestion (for external / sidecar mode) ───────────────────────────

class LLMCallPayload(BaseModel):
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0
    provider: str = "unknown"
    status: str = "success"
    error_msg: Optional[str] = None
    caller: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentEventPayload(BaseModel):
    agent_name: str
    description: Optional[str] = None
    status: str = "COMPLETED"
    event_type: str = "activity"
    duration_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/ingest/llm", status_code=201)
async def ingest_llm_call(payload: LLMCallPayload):
    """
    Manually ingest an LLM call event.
    Useful for sidecar mode where the SDK runs as a separate service.
    """
    row_id = record_llm_call(**payload.model_dump())
    return {"id": row_id, "status": "recorded"}


@router.post("/ingest/agent", status_code=201)
async def ingest_agent_event(payload: AgentEventPayload):
    """
    Manually ingest an agent activity event.
    Useful for sidecar mode or non-Python agents.
    """
    row_id = record_agent_event(**payload.model_dump())
    return {"id": row_id, "status": "recorded"}
