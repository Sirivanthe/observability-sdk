/**
 * ObservabilityPage.tsx
 * ---------------------
 * Drop-in React observability dashboard for FastAPI + React projects.
 *
 * INSTALLATION (3 steps):
 * 1. Copy to: kpmg_ui/client/src/pages/observability.tsx
 * 2. In App.tsx add:
 *      import ObservabilityPage from "@/pages/observability";
 *      { path: "/observability", Page: ObservabilityPage },
 * 3. In AppLayout.tsx add Activity to lucide imports and to HIDEABLE_TABS:
 *      { title: "Observability", fullTitle: "Model Observability", path: "/observability", icon: Activity },
 *
 * Requires: lucide-react, shadcn/ui (Card, Button), Tailwind CSS
 * All colours use inline styles to prevent dark-theme CSS overrides.
 */

import { useState, useEffect } from "react";
import { Activity, Zap, DollarSign, Clock, CheckCircle2, XCircle, RefreshCw, TrendingUp, Bot, Server, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const API_BASE = "/api/observability";
const CARD_STYLE = { background: "#f8fafc", color: "#1e293b" } as const;
const CARD_WHITE = { background: "#ffffff", color: "#1e293b" } as const;

function healthColor(s: string) { return s === "Healthy" ? "text-emerald-600" : s === "Degraded" ? "text-amber-500" : "text-red-500"; }
function healthBg(s: string) { return s === "Healthy" ? "bg-emerald-50 border-emerald-200" : s === "Degraded" ? "bg-amber-50 border-amber-200" : "bg-red-50 border-red-200"; }
function statusBadge(s: string) {
  const v: Record<string, string> = { COMPLETED: "bg-emerald-100 text-emerald-700 border-emerald-200", RUNNING: "bg-blue-100 text-blue-700 border-blue-200", FAILED: "bg-red-100 text-red-700 border-red-200", success: "bg-emerald-100 text-emerald-700 border-emerald-200", error: "bg-red-100 text-red-700 border-red-200" };
  return v[s] ?? "bg-slate-100 text-slate-700 border-slate-200";
}
function statusDot(s: string) { return s === "COMPLETED" || s === "success" ? "bg-emerald-500" : s === "RUNNING" ? "bg-blue-500 animate-pulse" : s === "FAILED" || s === "error" ? "bg-red-500" : "bg-slate-400"; }
function leftBorder(s: string) { return s === "COMPLETED" ? "border-l-emerald-500" : s === "RUNNING" ? "border-l-blue-500" : s === "FAILED" ? "border-l-red-500" : "border-l-slate-300"; }

function StatCard({ label, value, sub, icon: Icon, iconColor }: { label: string; value: string | number; sub?: string; icon: React.ComponentType<{ className?: string }>; iconColor?: string; }) {
  return (
    <Card className="border border-slate-200 shadow-none" style={CARD_WHITE}>
      <CardContent className="pt-5 pb-4" style={CARD_WHITE}>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "#64748b" }}>{label}</p>
            <p className="text-3xl font-bold" style={{ color: "#0f172a" }}>{value}</p>
            {sub && <p className="text-xs mt-1" style={{ color: "#94a3b8" }}>{sub}</p>}
          </div>
          <div className={`p-2 rounded-lg bg-slate-100 ${iconColor ?? "text-slate-400"}`}><Icon className="w-5 h-5" /></div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function ObservabilityPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hours, setHours] = useState(24);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard?hours=${hours}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json()); setError(null); setLastUpdated(new Date());
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  };

  useEffect(() => { setLoading(true); fetchData(); }, [hours]);
  useEffect(() => { if (!autoRefresh) return; const t = setInterval(fetchData, 30_000); return () => clearInterval(t); }, [autoRefresh, hours]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <RefreshCw className="w-6 h-6 animate-spin text-slate-400" />
      <span className="ml-3 text-slate-500">Loading observability data...</span>
    </div>
  );

  if (error || !data) return (
    <div className="p-8">
      <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
        <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-red-700">Observability API unreachable</p>
          <p className="text-sm text-red-500 mt-1">{error}</p>
          <p className="text-xs text-red-400 mt-2">Make sure the FastAPI backend is running with observability_sdk mounted at /observability/*</p>
        </div>
      </div>
      <Button className="mt-4" onClick={() => { setLoading(true); fetchData(); }}><RefreshCw className="w-4 h-4 mr-2" /> Retry</Button>
    </div>
  );

  const { model_performance: mp, agent_activity: ag, system_health: sh } = data;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto overflow-y-auto h-full">

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "#0f172a" }}>Model Observability</h1>
          <p className="text-sm mt-1" style={{ color: "#64748b" }}>Monitor AI model performance and agent activity</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={hours} onChange={e => setHours(Number(e.target.value))} className="text-sm border border-slate-200 rounded-md px-3 py-1.5 bg-white text-slate-700">
            <option value={1}>Last 1h</option><option value={6}>Last 6h</option><option value={24}>Last 24h</option><option value={48}>Last 48h</option><option value={168}>Last 7d</option>
          </select>
          <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: "#475569" }}>
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} className="rounded" /> Auto-refresh
          </label>
          <Button variant="outline" size="sm" onClick={() => { setLoading(true); fetchData(); }}><RefreshCw className="w-4 h-4 mr-1" /> Refresh</Button>
        </div>
      </div>

      {lastUpdated && <p className="text-xs" style={{ color: "#94a3b8" }}>Last updated: {lastUpdated.toLocaleTimeString()}</p>}

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: "#64748b" }}>Model Performance</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Requests" value={mp.total_requests} sub={`Last ${hours}h`} icon={Activity} iconColor="text-blue-500" />
          <StatCard label="Total Tokens" value={mp.total_tokens.toLocaleString()} sub="Prompt + Completion" icon={Zap} iconColor="text-violet-500" />
          <StatCard label="Total Cost" value={`$${mp.total_cost_usd.toFixed(4)}`} sub="USD" icon={DollarSign} iconColor="text-emerald-500" />
          <StatCard label="Avg Latency" value={`${mp.avg_latency_ms.toFixed(0)}ms`} sub={`${mp.success_rate}% success`} icon={Clock} iconColor="text-amber-500" />
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: "#64748b" }}>Agent Activity</h2>
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="Total Activities" value={ag.total_activities} icon={Bot} iconColor="text-slate-500" />
          <StatCard label="Completed" value={ag.completed} sub={`${ag.success_rate}% success rate`} icon={CheckCircle2} iconColor="text-emerald-500" />
          <StatCard label="Failed" value={ag.failed} icon={XCircle} iconColor="text-red-500" />
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: "#64748b" }}>System Health</h2>
        <div className="grid grid-cols-2 gap-4">
          {[
            { label: "Model Performance", status: sh.model_performance, icon: Server, sub: `${mp.success_rate}% success rate` },
            { label: "Agent Operations", status: sh.agent_operations, icon: Bot, sub: `${ag.success_rate}% success rate` },
          ].map(({ label, status, icon: Icon, sub }) => (
            <div key={label} className={`border rounded-lg p-4 ${healthBg(status)}`}>
              <div className="flex items-center gap-2 mb-1"><Icon className="w-4 h-4 text-slate-500" /><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span></div>
              <p className={`text-2xl font-bold ${healthColor(status)}`}>{status}</p>
              <p className="text-xs text-slate-500 mt-1">{sub}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="border border-slate-200 shadow-none" style={CARD_STYLE}>
          <CardHeader className="pb-2"><CardTitle className="text-base font-semibold" style={{ color: "#334155" }}>Recent Model Metrics</CardTitle></CardHeader>
          <CardContent style={CARD_STYLE}>
            {data.per_model.length === 0 ? <p className="text-sm text-center py-8" style={{ color: "#94a3b8" }}>No LLM calls recorded in this window.</p> : (
              <table className="w-full text-sm">
                <thead><tr className="border-b border-slate-100">{["Model","Requests","Tokens","Latency","Cost"].map(h => <th key={h} className="text-left text-xs font-semibold uppercase pb-2 pr-3" style={{ color: "#64748b" }}>{h}</th>)}</tr></thead>
                <tbody>{data.per_model.map((m: any, i: number) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-2 pr-3 font-mono text-xs" style={{ color: "#334155" }}>{m.model}</td>
                    <td className="py-2 pr-3" style={{ color: "#475569" }}>{m.requests}</td>
                    <td className="py-2 pr-3" style={{ color: "#475569" }}>{m.tokens.toLocaleString()}</td>
                    <td className="py-2 pr-3" style={{ color: "#475569" }}>{m.avg_latency_ms.toFixed(0)}ms</td>
                    <td className="py-2" style={{ color: "#475569" }}>${m.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </CardContent>
        </Card>

        <Card className="border border-slate-200 shadow-none" style={CARD_STYLE}>
          <CardHeader className="pb-2"><CardTitle className="text-base font-semibold" style={{ color: "#334155" }}>Recent Agent Activities</CardTitle></CardHeader>
          <CardContent style={CARD_STYLE}>
            {data.recent_agent_activities.length === 0 ? <p className="text-sm text-center py-8" style={{ color: "#94a3b8" }}>No agent activity recorded yet.</p> : (
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {data.recent_agent_activities.slice(0, 15).map((act: any, i: number) => (
                  <div key={i} className={`border-l-4 ${leftBorder(act.status)} pl-3 py-2 rounded-r-md`} style={{ background: "#f1f5f9" }}>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold" style={{ color: "#1e293b" }}>{act.agent_name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusBadge(act.status)}`}><span className={`inline-block w-1.5 h-1.5 rounded-full mr-1 ${statusDot(act.status)}`} />{act.status}</span>
                    </div>
                    <p className="text-xs mt-0.5 truncate" style={{ color: "#64748b" }}>{act.description}</p>
                    {act.duration_ms && <p className="text-xs mt-0.5" style={{ color: "#94a3b8" }}>{act.duration_ms.toFixed(0)}ms</p>}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border border-slate-200 shadow-none" style={CARD_STYLE}>
        <CardHeader className="pb-2"><CardTitle className="text-base font-semibold flex items-center gap-2" style={{ color: "#334155" }}><TrendingUp className="w-4 h-4" /> Recent LLM Call Log</CardTitle></CardHeader>
        <CardContent style={CARD_STYLE}>
          {data.recent_llm_calls.length === 0 ? <p className="text-sm text-center py-6" style={{ color: "#94a3b8" }}>No LLM calls in this window.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-slate-100">{["Timestamp","Model","Prompt","Completion","Latency","Cost","Status","Caller"].map(h => <th key={h} className="text-left text-xs font-semibold uppercase pb-2 pr-4 whitespace-nowrap" style={{ color: "#64748b" }}>{h}</th>)}</tr></thead>
                <tbody>{data.recent_llm_calls.slice(0, 20).map((c: any, i: number) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-2 pr-4 text-xs whitespace-nowrap" style={{ color: "#94a3b8" }}>{c.ts_str}</td>
                    <td className="py-2 pr-4 font-mono text-xs" style={{ color: "#334155" }}>{c.model}</td>
                    <td className="py-2 pr-4" style={{ color: "#475569" }}>{c.prompt_tokens}</td>
                    <td className="py-2 pr-4" style={{ color: "#475569" }}>{c.completion_tokens}</td>
                    <td className="py-2 pr-4" style={{ color: "#475569" }}>{c.latency_ms.toFixed(0)}ms</td>
                    <td className="py-2 pr-4" style={{ color: "#475569" }}>${c.cost_usd.toFixed(5)}</td>
                    <td className="py-2 pr-4"><span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusBadge(c.status)}`}>{c.status}</span></td>
                    <td className="py-2 text-xs truncate max-w-[120px]" style={{ color: "#94a3b8" }}>{c.caller}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
