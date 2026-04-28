import { useEffect, useState } from "react";
import { api, type RecordEntry } from "@/lib/ehrApi";
import { DashboardShell } from "@/components/DashboardShell";
import { BarChart2, CheckCircle2, AlertTriangle, Clock, Activity } from "lucide-react";

export default function AnalystDashboard() {
  const [records, setRecords] = useState<RecordEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .records(page, 25)
      .then((r) => { setRecords(r.items); setTotal(r.total); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page]);

  const distressCount = records.filter((r) => r.prediction === "Distress").length;
  const stableCount = records.filter((r) => r.prediction === "Stable").length;
  const avgConf = records.length
    ? (records.reduce((s, r) => s + r.confidence_score, 0) / records.length * 100).toFixed(1)
    : "—";
  const avgLatency = records.filter((r) => r.latency_ms).length
    ? (records.filter((r) => r.latency_ms).reduce((s, r) => s + (r.latency_ms ?? 0), 0) /
        records.filter((r) => r.latency_ms).length
      ).toFixed(0)
    : "—";

  return (
    <DashboardShell title="Analytics Dashboard">
      <h2 className="text-lg font-semibold text-foreground mb-5">Model & Population Metrics</h2>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Kpi label="Total Records" value={String(total)} icon={<BarChart2 className="w-4 h-4" />} color="text-primary" />
        <Kpi label="Distress" value={String(distressCount)} icon={<AlertTriangle className="w-4 h-4" />} color="text-red-500" />
        <Kpi label="Stable" value={String(stableCount)} icon={<CheckCircle2 className="w-4 h-4" />} color="text-green-600" />
        <Kpi label="Avg Confidence" value={`${avgConf}%`} icon={<Activity className="w-4 h-4" />} color="text-blue-600" />
      </div>

      {/* Latency / inference stats */}
      <div className="rounded-xl border border-border bg-card p-5 mb-6">
        <h3 className="text-sm font-semibold text-foreground mb-3">Inference Performance</h3>
        <div className="flex flex-wrap gap-6">
          <div>
            <p className="text-2xl font-bold text-foreground">{avgLatency} ms</p>
            <p className="text-xs text-muted-foreground">Avg Latency</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-foreground">
              {total > 0 ? ((distressCount / total) * 100).toFixed(1) : "—"}%
            </p>
            <p className="text-xs text-muted-foreground">Distress Prevalence</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-foreground">{records.length}</p>
            <p className="text-xs text-muted-foreground">Records on Page</p>
          </div>
        </div>
      </div>

      {/* De-identified record table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">De-identified Records</h3>
          <span className="text-xs text-muted-foreground">Patient IDs anonymised</span>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-muted-foreground">Loading…</p>
        ) : error ? (
          <p className="p-5 text-sm text-destructive">{error}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-border bg-muted/30">
                <tr>
                  {["Anon ID", "Prediction", "Confidence", "Sentiment", "Tokens", "Latency", "Date"].map((h) => (
                    <th key={h} className="text-left px-4 py-2.5 font-medium text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {records.map((r, i) => (
                  <tr key={i} className="hover:bg-muted/20">
                    <td className="px-4 py-2.5 font-mono">{r.patient_id}</td>
                    <td className="px-4 py-2.5">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${r.prediction === "Distress" ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>
                        {r.prediction}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">{(r.confidence_score * 100).toFixed(1)}%</td>
                    <td className="px-4 py-2.5 capitalize">{r.sentiment ?? "—"}</td>
                    <td className="px-4 py-2.5">{r.token_count ?? "—"}</td>
                    <td className="px-4 py-2.5">{r.latency_ms != null ? `${r.latency_ms.toFixed(0)} ms` : "—"}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {r.timestamp ? new Date(r.timestamp).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="px-5 py-3 border-t border-border flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {total} total records
          </span>
          <div className="flex items-center gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="text-xs px-3 h-7 rounded border border-border disabled:opacity-40 hover:bg-muted transition-colors"
            >
              Prev
            </button>
            <span className="text-xs text-muted-foreground">Page {page}</span>
            <button
              disabled={records.length < 25}
              onClick={() => setPage((p) => p + 1)}
              className="text-xs px-3 h-7 rounded border border-border disabled:opacity-40 hover:bg-muted transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}

function Kpi({ label, value, icon, color }: { label: string; value: string; icon: React.ReactNode; color: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className={`mb-2 ${color}`}>{icon}</div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
    </div>
  );
}
