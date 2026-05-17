"""
observability_sdk.backend.tracker
------------------------------------
Decorators and context managers for tracking agent activity.

Usage — decorator:
    from observability_sdk import track_agent

    @track_agent("GapRemediationAgent")
    async def generate_recommendations(self, ...):
        ...

Usage — context manager:
    from observability_sdk import agent_span

    async with agent_span("RCMAnalyzer", description="Running RCM compliance check"):
        result = await analyzer.run(...)

Usage — manual:
    from observability_sdk.backend.tracker import start_agent, finish_agent, fail_agent

    event_id = start_agent("MyAgent", description="Doing something")
    try:
        ...
        finish_agent(event_id, "MyAgent", "Done — 5 controls tested")
    except Exception as e:
        fail_agent(event_id, "MyAgent", str(e))
"""

import time
import functools
import logging
from contextlib import asynccontextmanager
from typing import Optional

from .store import record_agent_event

logger = logging.getLogger("observability_sdk.tracker")


def track_agent(agent_name: str, description: Optional[str] = None):
    """
    Async decorator. Wrap any async function to record it as an agent activity.

    The decorated function's docstring is used as the description if none
    is provided.

        @track_agent("GapRemediationAgent")
        async def generate_recommendations(self, gap_description, framework, ...):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            desc = description or func.__doc__ or f"{agent_name}.{func.__name__}"
            desc = desc.strip().split("\n")[0][:200]  # first line, max 200 chars

            start = time.perf_counter()
            record_agent_event(
                agent_name=agent_name,
                description=desc,
                status="RUNNING",
                event_type="start",
            )
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                record_agent_event(
                    agent_name=agent_name,
                    description=desc,
                    status="COMPLETED",
                    event_type="complete",
                    duration_ms=round(duration_ms, 1),
                )
                return result
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                record_agent_event(
                    agent_name=agent_name,
                    description=f"FAILED: {str(exc)[:150]}",
                    status="FAILED",
                    event_type="error",
                    duration_ms=round(duration_ms, 1),
                )
                raise

        return wrapper
    return decorator


@asynccontextmanager
async def agent_span(agent_name: str, description: str = None):
    """
    Async context manager for tracking a block of agent work.

        async with agent_span("RCMAnalyzer", "Running RCM analysis"):
            result = await analyzer.run(doc)
    """
    desc = (description or agent_name)[:200]
    start = time.perf_counter()
    record_agent_event(agent_name=agent_name, description=desc, status="RUNNING", event_type="start")
    try:
        yield
        duration_ms = (time.perf_counter() - start) * 1000
        record_agent_event(
            agent_name=agent_name, description=desc,
            status="COMPLETED", event_type="complete",
            duration_ms=round(duration_ms, 1),
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        record_agent_event(
            agent_name=agent_name,
            description=f"FAILED: {str(exc)[:150]}",
            status="FAILED", event_type="error",
            duration_ms=round(duration_ms, 1),
        )
        raise


# ── Manual helpers (for non-decorator use) ────────────────────────────────────

def start_agent(agent_name: str, description: str = None) -> float:
    """Record agent start. Returns start timestamp for use with finish_agent."""
    record_agent_event(agent_name=agent_name, description=description, status="RUNNING", event_type="start")
    return time.perf_counter()


def finish_agent(start_ts: float, agent_name: str, description: str = None):
    """Record agent completion."""
    duration_ms = (time.perf_counter() - start_ts) * 1000
    record_agent_event(
        agent_name=agent_name, description=description,
        status="COMPLETED", event_type="complete",
        duration_ms=round(duration_ms, 1),
    )


def fail_agent(start_ts: float, agent_name: str, error: str):
    """Record agent failure."""
    duration_ms = (time.perf_counter() - start_ts) * 1000
    record_agent_event(
        agent_name=agent_name,
        description=f"FAILED: {error[:150]}",
        status="FAILED", event_type="error",
        duration_ms=round(duration_ms, 1),
    )
