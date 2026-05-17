/**
 * ObservabilityPage.tsx
 * ---------------------
 * Drop-in React observability dashboard for FastAPI + React projects.
 *
 * INSTALLATION (2 steps):
 *
 * 1. Copy this file to:
 *      kpmg_ui/client/src/pages/observability.tsx
 *
 * 2. In App.tsx, add two lines:
 *      import ObservabilityPage from "@/pages/observability";
 *      { path: "/observability", Page: ObservabilityPage },
 *
 * The page fetches from /api/observability/* via the Express BFF proxy.
 * Make sure the FastAPI backend has observability_sdk mounted.
 *
 * Dependencies: all already present in this project
 *   - @tanstack/react-query
 *   - lucide-react
 *   - shadcn/ui (Card, Badge, Button)
 *   - Tailwind CSS
 */

import { useState, useEffect } from "react";
import {
  Activity, Zap, DollarSign, Clock, CheckCircle2, XCircle,
  RefreshCw, TrendingUp, Bot, Server, AlertTriangle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ModelPerformance {
  total_requests: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  success_rate: number;
  error_count: number;
}

interface AgentActivity {
  total_activities: number;
  completed: number;
  failed: number;
  running: number;
  success_rate: number;
}

interface SystemHealth {
  model_performance: "Healthy" | "Degraded" | "Unhealthy";
  agent_operations: "Healthy" | "Degraded" | "Unhealthy";
}

interface PerModel {
  model: string;
  requests: number;
  tokens: number;
  avg_latency_ms: number;
  cost_usd: number;
}

interface LLMCall {
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  cost_usd: number;
  status: string;
  caller: string;
  ts_str: string;
}

interface AgentEvent {
  agent_name: string;
  status: string;
  description: string;
  duration_ms: number | null;
  ts_str: string;
}

interface DashboardData {
  window_hours: number;
  model_performance: ModelPerformance;
  agent_activity: AgentActivity;
  system_health: SystemHealth;
  per_model: PerModel[];
  recent_llm_calls: LLMCall[];
  recent_agent_activities: AgentEvent[];
}

// ── Config ────────────────────────────────────────────────────────────────────

// Adjust this if your BFF proxy uses a different prefix
const API_BASE = "/api/observability";

// ── Helpers ───────────────────────────────────────────────────────────────────

function healthColor(status: string): string {
  if (status === "Healthy") return "text-emerald-600";
  if (status === "Degraded") return "text-amber-500";
  return "text-red-500";
}

function healthBg(status: string): string {
  if (status === "Healthy") return "bg-emerald-50 border-emerald-200";
  if (status === "Degraded") return "bg-amber-50 border-amber-200";
  return "bg-red-50 border-red-200";
}

function statusBadge(status: string) {
  const variants: Record<string, string> = {
    COMPLETED: "bg-emerald-100 text-emerald-700 border-emerald-200",
    RUNNING:   "bg-blue-100 text-blue-700 border-blue-200",
    FAILED:    "bg-red-100 text-red-700 border-red-200",
    success:   "bg-emerald-100 text-emerald-700 border-emerald-200",
    error:     "bg-red-100 text-red-700 border-red-200",
  };
  return variants[status] ?? "bg-slate-100 text-slate-700 border-slate-200";
}

function statusDot(status: string): string {
  if (status === "COMPLETED" || status === "success") return "bg-emerald-500";
  if (status === "RUNNING") return "bg-blue-500 animate-pulse";
  if (status === "FAILED" || status === "error") return "bg-red-500";
  return "bg-slate-400";
}

function leftBorder(status: string): string {
  if (status === "COMPLETED") return "border-l-emerald-500";
  if (status === "RUNNING")   return "border-l-blue-500";
  if (status === "FAILED")    return "border-l-red-500";
  return "border-l-slate-300";
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatCard({
  label, value, sub, icon: Icon, iconColor,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor?: string;
}) {
  return (
    <Card className="border border-slate-200 shadow-sm">
      <CardContent className="pt-5 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{color:"#64748b"}}>{label}</p>
            <p className="text-3xl font-bold" style={{color:"#0f172a"}}>{value}</p>
            {sub && <p className="text-xs mt-1" style={{color:"#94a3b8"}}>{sub}</p>}
          </div>
          <div className={`p-2 rounded-lg bg-slate-50 ${iconColor ?? "text-slate-400"}`}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ObservabilityPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hours, setHours] = useState(24);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard?hours=${hours}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
      setLastUpdated(new Date());
    } catch (e: any) {
      setError(e.message ?? "Failed to fetch observability data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchData();
  }, [hours]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchData, 30_000);
    return () => clearInterval(interval);
  }, [autoRefresh, hours]);

  // ── Loading ─────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 animate-spin text-slate-400" />
        <span className="ml-3 text-slate-500">Loading observability data...</span>
      </div>
    );
  }

  // ── Error ───────────────────────────────────────────────────────────────────
  if (error || !data) {
    return (
      <div className="p-8">
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div>
            <p className="font-semibold text-red-700">Observability API unreachable</p>
            <p className="text-sm text-red-500 mt-1">{error}</p>
            <p className="text-xs text-red-400 mt-2">
              Make sure the FastAPI backend is running with observability_sdk mounted at /observability/*
            </p>
          </div>
        </div>
        <Button className="mt-4" onClick={() => { setLoading(true); fetchData(); }}>
          <RefreshCw className="w-4 h-4 mr-2" /> Retry
        </Button>
      </div>
    );
  }

  const { model_performance: mp, agent_activity: ag, system_health: sh } = data;

  // ── Dashboard ───────────────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto overflow-y-auto h-full"> 

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Model Observability</h1>
          <p className="text-sm text-slate-500 mt-1">Monitor AI model performance and agent activity</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Time window */}
          <select
            value={hours}
            onChange={e => setHours(Number(e.target.value))}
            className="text-sm border border-slate-200 rounded-md px-3 py-1.5 bg-white text-slate-700"
          >
            <option value={1}>Last 1h</option>
            <option value={6}>Last 6h</option>
            <option value={24}>Last 24h</option>
            <option value={48}>Last 48h</option>
            <option value={168}>Last 7d</option>
          </select>
          {/* Auto-refresh toggle */}
          <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh
          </label>
          <Button variant="outline" size="sm" onClick={() => { setLoading(true); fetchData(); }}>
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh
          </Button>
        </div>
      </div>

      {lastUpdated && (
        <p className="text-xs text-slate-400">Last updated: {lastUpdated.toLocaleTimeString()}</p>
      )}

      {/* Model Performance Stats */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Model Performance</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Total Requests"
            value={mp.total_requests}
            sub={`Last ${hours}h`}
            icon={Activity}
            iconColor="text-blue-500"
          />
          <StatCard
            label="Total Tokens"
            value={mp.total_tokens.toLocaleString()}
            sub="Prompt + Completion"
            icon={Zap}
            iconColor="text-violet-500"
          />
          <StatCard
            label="Total Cost"
            value={`$${mp.total_cost_usd.toFixed(4)}`}
            sub="USD"
            icon={DollarSign}
            iconColor="text-emerald-500"
          />
          <StatCard
            label="Avg Latency"
            value={`${mp.avg_latency_ms.toFixed(0)}ms`}
            sub={`${mp.success_rate}% success`}
            icon={Clock}
            iconColor="text-amber-500"
          />
        </div>
      </section>

      {/* Agent Activity Stats */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Agent Activity</h2>
        <div className="grid grid-cols-3 gap-4">
          <StatCard
            label="Total Activities"
            value={ag.total_activities}
            icon={Bot}
            iconColor="text-slate-500"
          />
          <StatCard
            label="Completed"
            value={ag.completed}
            sub={`${ag.success_rate}% success rate`}
            icon={CheckCircle2}
            iconColor="text-emerald-500"
          />
          <StatCard
            label="Failed"
            value={ag.failed}
            icon={XCircle}
            iconColor="text-red-500"
          />
        </div>
      </section>

      {/* System Health */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">System Health</h2>
        <div className="grid grid-cols-2 gap-4">
          {[
            { label: "Model Performance", status: sh.model_performance, icon: Server, sub: `${mp.success_rate}% success rate` },
            { label: "Agent Operations",  status: sh.agent_operations,  icon: Bot,    sub: `${ag.success_rate}% success rate` },
          ].map(({ label, status, icon: Icon, sub }) => (
            <div key={label} className={`border rounded-lg p-4 ${healthBg(status)}`}>
              <div className="flex items-center gap-2 mb-1">
                <Icon className="w-4 h-4 text-slate-500" />
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
              </div>
              <p className={`text-2xl font-bold ${healthColor(status)}`}>{status}</p>
              <p className="text-xs text-slate-500 mt-1">{sub}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Per-model metrics + Recent agent activity */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Per-model table */}
        <Card className="border border-slate-200 shadow-none" style={{background:"#f8fafc",color:"#1e293b"}}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold text-slate-700">Recent Model Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            {data.per_model.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-8">No LLM calls recorded in this window.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100">
                    {["Model", "Requests", "Tokens", "Latency", "Cost"].map(h => (
                      <th key={h} className="text-left text-xs font-semibold text-slate-500 uppercase pb-2 pr-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.per_model.map((m, i) => (
                    <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                      <td className="py-2 pr-3 font-mono text-xs text-slate-700">{m.model}</td>
                      <td className="py-2 pr-3 text-slate-600">{m.requests}</td>
                      <td className="py-2 pr-3 text-slate-600">{m.tokens.toLocaleString()}</td>
                      <td className="py-2 pr-3 text-slate-600">{m.avg_latency_ms.toFixed(0)}ms</td>
                      <td className="py-2 text-slate-600">${m.cost_usd.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        {/* Recent agent activities */}
        <Card className="border border-slate-200 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold text-slate-700">Recent Agent Activities</CardTitle>
          </CardHeader>
          <CardContent>
            {data.recent_agent_activities.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-8">No agent activity recorded yet.</p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {data.recent_agent_activities.slice(0, 15).map((act, i) => (
                  <div key={i} className={`border-l-4 ${leftBorder(act.status)} pl-3 py-2 bg-slate-50 rounded-r-md`}>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-slate-700">{act.agent_name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusBadge(act.status)}`}>
                        <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1 ${statusDot(act.status)}`} />
                        {act.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 truncate">{act.description}</p>
                    {act.duration_ms && (
                      <p className="text-xs text-slate-400 mt-0.5">{act.duration_ms.toFixed(0)}ms</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* LLM Call Log (collapsible) */}
      <Card className="border border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold text-slate-700 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> Recent LLM Call Log
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_llm_calls.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-6">No LLM calls in this window.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100">
                    {["Timestamp", "Model", "Prompt", "Completion", "Latency", "Cost", "Status", "Caller"].map(h => (
                      <th key={h} className="text-left text-xs font-semibold text-slate-500 uppercase pb-2 pr-4 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.recent_llm_calls.slice(0, 20).map((c, i) => (
                    <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                      <td className="py-2 pr-4 text-xs text-slate-400 whitespace-nowrap">{c.ts_str}</td>
                      <td className="py-2 pr-4 font-mono text-xs text-slate-700">{c.model}</td>
                      <td className="py-2 pr-4 text-slate-600">{c.prompt_tokens}</td>
                      <td className="py-2 pr-4 text-slate-600">{c.completion_tokens}</td>
                      <td className="py-2 pr-4 text-slate-600">{c.latency_ms.toFixed(0)}ms</td>
                      <td className="py-2 pr-4 text-slate-600">${c.cost_usd.toFixed(5)}</td>
                      <td className="py-2 pr-4">
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusBadge(c.status)}`}>
                          {c.status}
                        </span>
                      </td>
                      <td className="py-2 text-xs text-slate-400 truncate max-w-[120px]">{c.caller}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
