"""
observability_sdk.frontend.streamlit_dashboard
------------------------------------------------
Drop-in Streamlit page that renders the full Model Observability dashboard.

Usage — standalone page:
    # In your Streamlit app (e.g. kpmg_ui/pages/observability.py)
    from observability_sdk.frontend.streamlit_dashboard import render_dashboard
    render_dashboard()

Usage — embedded in existing page:
    from observability_sdk.frontend.streamlit_dashboard import render_dashboard
    render_dashboard(api_base_url="http://localhost:5000/observability")

The dashboard fetches from the observability REST API, so the FastAPI backend
must be running with mount_router() called.
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from typing import Optional


_DEFAULT_API = "http://localhost:5000/observability"


def _fetch(url: str, timeout: int = 10):
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Failed to fetch observability data: {e}")
        return None


def _status_badge(status: str) -> str:
    colours = {
        "COMPLETED": "🟢",
        "RUNNING": "🔵",
        "FAILED": "🔴",
        "success": "🟢",
        "error": "🔴",
        "Healthy": "🟢",
        "Degraded": "🟡",
        "Unhealthy": "🔴",
    }
    return colours.get(status, "⚪")


def render_dashboard(
    api_base_url: str = _DEFAULT_API,
    page_title: str = "Model Observability",
    auto_refresh_seconds: int = 30,
):
    """Render the full observability dashboard as a Streamlit page."""

    st.set_page_config(page_title=page_title, layout="wide")

    # ── Header ────────────────────────────────────────────────────────────────
    col_title, col_ctrl = st.columns([4, 1])
    with col_title:
        st.title(f"📊 {page_title}")
        st.caption("Monitor AI model performance, agent activity, and system health")
    with col_ctrl:
        auto_refresh = st.checkbox("Auto-refresh", value=True)
        hours = st.selectbox("Window", [1, 6, 24, 48, 168], index=2,
                             format_func=lambda h: f"Last {h}h" if h < 168 else "Last 7d")
        if st.button("🔄 Refresh"):
            st.rerun()

    if auto_refresh:
        st.empty()  # placeholder — real auto-refresh via st.rerun with sleep
        import time
        time.sleep(auto_refresh_seconds)
        st.rerun()

    # ── Fetch data ────────────────────────────────────────────────────────────
    data = _fetch(f"{api_base_url}/dashboard?hours={hours}")
    if not data:
        st.warning("No observability data available. Make sure the API is running.")
        return

    mp = data["model_performance"]
    ag = data["agent_activity"]
    health = data["system_health"]

    # ── Model Performance ─────────────────────────────────────────────────────
    st.subheader("Model Performance")
    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Total Requests",
        mp["total_requests"],
        help=f"Last {hours}h"
    )
    c2.metric(
        "Total Tokens",
        f"{mp['total_tokens']:,}",
        help="Prompt + Completion"
    )
    c3.metric(
        "Total Cost",
        f"${mp['total_cost_usd']:.4f}",
        help="USD (local Ollama models = $0)"
    )
    c4.metric(
        "Avg Latency",
        f"{mp['avg_latency_ms']:.0f}ms",
        delta=f"{mp['success_rate']}% success",
        delta_color="normal"
    )

    # ── Agent Activity ────────────────────────────────────────────────────────
    st.subheader("Agent Activity")
    a1, a2, a3 = st.columns(3)
    a1.metric("Total Activities", ag["total_activities"])
    a2.metric("Completed", ag["completed"])
    a3.metric("Failed", ag["failed"],
              delta=f"{ag['success_rate']}% success rate" if ag["total_activities"] > 0 else None,
              delta_color="inverse")

    # ── System Health ─────────────────────────────────────────────────────────
    st.subheader("System Health")
    h1, h2 = st.columns(2)
    mp_health = health["model_performance"]
    ag_health = health["agent_operations"]

    with h1:
        badge = _status_badge(mp_health)
        colour = {"Healthy": "green", "Degraded": "orange", "Unhealthy": "red"}.get(mp_health, "gray")
        st.markdown(f"""
        <div style="border:1px solid #e2e8f0; border-radius:8px; padding:16px; background:#f8fafc;">
            <div style="font-size:12px; color:#64748b; font-weight:600; text-transform:uppercase;">Model Performance</div>
            <div style="font-size:28px; font-weight:700; color:{colour};">{badge} {mp_health}</div>
            <div style="font-size:13px; color:#64748b;">{mp['success_rate']}% success rate</div>
        </div>
        """, unsafe_allow_html=True)

    with h2:
        badge = _status_badge(ag_health)
        colour = {"Healthy": "green", "Degraded": "orange", "Unhealthy": "red"}.get(ag_health, "gray")
        st.markdown(f"""
        <div style="border:1px solid #e2e8f0; border-radius:8px; padding:16px; background:#f8fafc;">
            <div style="font-size:12px; color:#64748b; font-weight:600; text-transform:uppercase;">Agent Operations</div>
            <div style="font-size:28px; font-weight:700; color:{colour};">{badge} {ag_health}</div>
            <div style="font-size:13px; color:#64748b;">{ag['success_rate']}% success rate</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Per-model breakdown + Recent activities ───────────────────────────────
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Recent Model Metrics")
        if data["per_model"]:
            df = pd.DataFrame(data["per_model"])
            df.columns = ["Model", "Requests", "Tokens", "Avg Latency (ms)", "Cost (USD)"]
            df["Cost (USD)"] = df["Cost (USD)"].map(lambda x: f"${x:.4f}")
            df["Avg Latency (ms)"] = df["Avg Latency (ms)"].map(lambda x: f"{x:.0f}ms")
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Latency trend chart
            if data.get("latency_trend"):
                trend_df = pd.DataFrame(data["latency_trend"])
                if not trend_df.empty:
                    st.caption("Latency trend (ms)")
                    st.line_chart(trend_df.set_index("hour")["avg_latency_ms"])
        else:
            st.info("No LLM calls recorded yet in this window.")

    with col_right:
        st.subheader("Recent Agent Activities")
        activities = data.get("recent_agent_activities", [])
        if activities:
            for act in activities[:15]:
                badge = _status_badge(act["status"])
                dur = f" · {act['duration_ms']:.0f}ms" if act.get("duration_ms") else ""
                st.markdown(f"""
                <div style="border-left:3px solid {'#22c55e' if act['status']=='COMPLETED' else '#3b82f6' if act['status']=='RUNNING' else '#ef4444'};
                            padding:8px 12px; margin-bottom:8px; background:#f8fafc; border-radius:0 6px 6px 0;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong style="font-size:13px;">{act['agent_name']}</strong>
                        <span style="font-size:11px; padding:2px 8px; border-radius:10px;
                              background:{'#dcfce7' if act['status']=='COMPLETED' else '#dbeafe' if act['status']=='RUNNING' else '#fee2e2'};
                              color:{'#166534' if act['status']=='COMPLETED' else '#1e40af' if act['status']=='RUNNING' else '#991b1b'};">
                            {badge} {act['status']}
                        </span>
                    </div>
                    <div style="font-size:12px; color:#64748b; margin-top:4px;">{act.get('description','') or ''}{dur}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No agent activity recorded yet.")

    # ── Recent LLM call log ───────────────────────────────────────────────────
    with st.expander("📋 Recent LLM Call Log", expanded=False):
        calls = data.get("recent_llm_calls", [])
        if calls:
            df = pd.DataFrame(calls)[["ts_str", "model", "prompt_tokens", "completion_tokens", "latency_ms", "cost_usd", "status", "caller"]]
            df.columns = ["Timestamp", "Model", "Prompt Tokens", "Completion Tokens", "Latency (ms)", "Cost (USD)", "Status", "Caller"]
            df["Cost (USD)"] = df["Cost (USD)"].map(lambda x: f"${x:.5f}")
            df["Latency (ms)"] = df["Latency (ms)"].map(lambda x: f"{x:.0f}ms")
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No LLM calls in this window.")


# Allow running as a standalone page directly
if __name__ == "__main__":
    render_dashboard()
