"""
observability_sdk.backend.store
--------------------------------
SQLite-backed store for LLM call metrics and agent activity events.
Zero external dependencies beyond Python stdlib.

Schema:
  llm_calls  — one row per LLM API call
  agent_events — one row per agent activity
"""

import sqlite3
import json
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager

# Thread-local connections so multiple uvicorn workers don't fight
_local = threading.local()

# Cost per 1000 tokens (USD) — override via SDK init if needed
DEFAULT_COST_PER_1K = {
    # Gemini
    "gemini-2.5-flash": 0.000075,
    "gemini-2.5-pro": 0.00125,
    "gemini-2.0-flash": 0.000075,
    "gemini-1.5-flash": 0.000075,
    # Ollama local — effectively free
    "llama3": 0.0,
    "llama3:8b": 0.0,
    "mistral": 0.0,
    "nomic-embed-text": 0.0,
    # OpenAI
    "gpt-4o": 0.005,
    "gpt-4o-mini": 0.00015,
    "gpt-3.5-turbo": 0.0005,
    # Anthropic
    "claude-sonnet-4-5": 0.003,
    "claude-haiku-4-5": 0.00025,
}

_DB_PATH: Path = Path("observability.db")
_COST_MAP: Dict[str, float] = {}


def init_store(db_path: str = "observability.db", cost_overrides: Dict[str, float] = None):
    """Call once at app startup to configure the store."""
    global _DB_PATH, _COST_MAP
    _DB_PATH = Path(db_path)
    _COST_MAP = {**DEFAULT_COST_PER_1K, **(cost_overrides or {})}
    _create_tables()


@contextmanager
def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    try:
        yield _local.conn
    except Exception:
        _local.conn.rollback()
        raise
    else:
        _local.conn.commit()


def _create_tables():
    with _get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS llm_calls (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          REAL    NOT NULL,          -- Unix timestamp
            model       TEXT    NOT NULL,
            provider    TEXT    NOT NULL DEFAULT 'unknown',
            prompt_tokens   INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens    INTEGER NOT NULL DEFAULT 0,
            latency_ms  REAL    NOT NULL DEFAULT 0,
            cost_usd    REAL    NOT NULL DEFAULT 0,
            status      TEXT    NOT NULL DEFAULT 'success',  -- success | error
            error_msg   TEXT,
            caller      TEXT,   -- e.g. 'GapRemediationAgent', 'control_testing'
            metadata    TEXT    -- JSON blob for extra fields
        );

        CREATE TABLE IF NOT EXISTS agent_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          REAL    NOT NULL,
            agent_name  TEXT    NOT NULL,
            event_type  TEXT    NOT NULL DEFAULT 'activity',  -- activity | error | start | complete
            status      TEXT    NOT NULL DEFAULT 'RUNNING',   -- RUNNING | COMPLETED | FAILED
            description TEXT,
            duration_ms REAL,
            metadata    TEXT    -- JSON blob
        );

        CREATE INDEX IF NOT EXISTS idx_llm_ts      ON llm_calls(ts);
        CREATE INDEX IF NOT EXISTS idx_agent_ts    ON agent_events(ts);
        CREATE INDEX IF NOT EXISTS idx_llm_model   ON llm_calls(model);
        CREATE INDEX IF NOT EXISTS idx_agent_name  ON agent_events(agent_name);
        """)


# ── Write helpers ─────────────────────────────────────────────────────────────

def record_llm_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    provider: str = "unknown",
    status: str = "success",
    error_msg: str = None,
    caller: str = None,
    metadata: Dict[str, Any] = None,
) -> int:
    total = prompt_tokens + completion_tokens
    cost_per_k = _COST_MAP.get(model, _COST_MAP.get(model.split(":")[0], 0.0))
    cost = (total / 1000.0) * cost_per_k

    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO llm_calls
               (ts, model, provider, prompt_tokens, completion_tokens, total_tokens,
                latency_ms, cost_usd, status, error_msg, caller, metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                time.time(), model, provider, prompt_tokens, completion_tokens, total,
                latency_ms, cost, status, error_msg, caller,
                json.dumps(metadata) if metadata else None,
            ),
        )
        return cur.lastrowid


def record_agent_event(
    agent_name: str,
    description: str = None,
    status: str = "RUNNING",
    event_type: str = "activity",
    duration_ms: float = None,
    metadata: Dict[str, Any] = None,
) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO agent_events
               (ts, agent_name, event_type, status, description, duration_ms, metadata)
               VALUES (?,?,?,?,?,?,?)""",
            (
                time.time(), agent_name, event_type, status, description,
                duration_ms, json.dumps(metadata) if metadata else None,
            ),
        )
        return cur.lastrowid


# ── Read helpers ──────────────────────────────────────────────────────────────

def _since(hours: int = 24) -> float:
    return time.time() - hours * 3600


def get_dashboard_stats(hours: int = 24) -> Dict[str, Any]:
    """Single call that returns everything needed for the dashboard."""
    since = _since(hours)
    with _get_conn() as conn:
        # LLM aggregate
        llm = conn.execute("""
            SELECT
                COUNT(*)                            AS total_requests,
                COALESCE(SUM(total_tokens), 0)      AS total_tokens,
                COALESCE(SUM(prompt_tokens), 0)     AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                COALESCE(SUM(cost_usd), 0)          AS total_cost,
                COALESCE(AVG(latency_ms), 0)        AS avg_latency,
                COALESCE(SUM(CASE WHEN status='success' THEN 1 ELSE 0 END), 0) AS success_count,
                COALESCE(SUM(CASE WHEN status='error'   THEN 1 ELSE 0 END), 0) AS error_count
            FROM llm_calls WHERE ts >= ?
        """, (since,)).fetchone()

        # Per-model breakdown
        models = conn.execute("""
            SELECT model,
                   COUNT(*)               AS requests,
                   SUM(total_tokens)      AS tokens,
                   AVG(latency_ms)        AS avg_latency,
                   SUM(cost_usd)          AS cost
            FROM llm_calls WHERE ts >= ?
            GROUP BY model ORDER BY requests DESC
        """, (since,)).fetchall()

        # Recent LLM calls
        recent_calls = conn.execute("""
            SELECT model, prompt_tokens, completion_tokens, total_tokens,
                   latency_ms, cost_usd, status, caller,
                   datetime(ts, 'unixepoch') as ts_str
            FROM llm_calls WHERE ts >= ?
            ORDER BY ts DESC LIMIT 20
        """, (since,)).fetchall()

        # Agent aggregate
        agents = conn.execute("""
            SELECT
                COUNT(*)                                                    AS total_activities,
                COALESCE(SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END), 0) AS completed,
                COALESCE(SUM(CASE WHEN status='FAILED'    THEN 1 ELSE 0 END), 0) AS failed,
                COALESCE(SUM(CASE WHEN status='RUNNING'   THEN 1 ELSE 0 END), 0) AS running
            FROM agent_events WHERE ts >= ?
        """, (since,)).fetchone()

        # Recent agent activities
        recent_agents = conn.execute("""
            SELECT agent_name, status, description, duration_ms,
                   datetime(ts, 'unixepoch') as ts_str
            FROM agent_events WHERE ts >= ?
            ORDER BY ts DESC LIMIT 30
        """, (since,)).fetchall()

        # Latency over time (hourly buckets)
        latency_trend = conn.execute("""
            SELECT
                CAST((ts - ?) / 3600 AS INTEGER) AS hour_bucket,
                AVG(latency_ms) AS avg_latency,
                COUNT(*) AS requests
            FROM llm_calls WHERE ts >= ?
            GROUP BY hour_bucket ORDER BY hour_bucket
        """, (since, since)).fetchall()

    total = llm["total_requests"]
    success = llm["success_count"]
    success_rate = round((success / total * 100) if total > 0 else 100.0, 1)

    agent_total = agents["total_activities"]
    agent_success = agents["completed"]
    agent_success_rate = round((agent_success / agent_total * 100) if agent_total > 0 else 0.0, 1)

    return {
        "window_hours": hours,
        "model_performance": {
            "total_requests": total,
            "total_tokens": llm["total_tokens"],
            "prompt_tokens": llm["prompt_tokens"],
            "completion_tokens": llm["completion_tokens"],
            "total_cost_usd": round(llm["total_cost"], 6),
            "avg_latency_ms": round(llm["avg_latency"], 0),
            "success_rate": success_rate,
            "error_count": llm["error_count"],
        },
        "agent_activity": {
            "total_activities": agent_total,
            "completed": agents["completed"],
            "failed": agents["failed"],
            "running": agents["running"],
            "success_rate": agent_success_rate,
        },
        "system_health": {
            "model_performance": "Healthy" if success_rate >= 95 else ("Degraded" if success_rate >= 80 else "Unhealthy"),
            "agent_operations": "Healthy" if agent_success_rate >= 80 else ("Degraded" if agent_success_rate >= 50 else "Unhealthy"),
        },
        "per_model": [
            {
                "model": r["model"],
                "requests": r["requests"],
                "tokens": r["tokens"],
                "avg_latency_ms": round(r["avg_latency"], 0),
                "cost_usd": round(r["cost"], 6),
            }
            for r in models
        ],
        "recent_llm_calls": [dict(r) for r in recent_calls],
        "recent_agent_activities": [dict(r) for r in recent_agents],
        "latency_trend": [
            {"hour": r["hour_bucket"], "avg_latency_ms": round(r["avg_latency"], 0), "requests": r["requests"]}
            for r in latency_trend
        ],
    }


def get_llm_calls(limit: int = 100, model: str = None, hours: int = 24) -> List[Dict]:
    since = _since(hours)
    with _get_conn() as conn:
        if model:
            rows = conn.execute(
                "SELECT * FROM llm_calls WHERE ts >= ? AND model = ? ORDER BY ts DESC LIMIT ?",
                (since, model, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM llm_calls WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
                (since, limit)
            ).fetchall()
    return [dict(r) for r in rows]


def get_agent_events(limit: int = 100, agent_name: str = None, hours: int = 24) -> List[Dict]:
    since = _since(hours)
    with _get_conn() as conn:
        if agent_name:
            rows = conn.execute(
                "SELECT * FROM agent_events WHERE ts >= ? AND agent_name = ? ORDER BY ts DESC LIMIT ?",
                (since, agent_name, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_events WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
                (since, limit)
            ).fetchall()
    return [dict(r) for r in rows]
