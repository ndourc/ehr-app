import { useEffect, useState } from "react";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api, type RecordEntry, type RecordsResponse } from "@/lib/ehrApi";
import { AlertTriangle, CheckCircle2, Activity, FileText, ChevronLeft, ChevronRight } from "lucide-react";

const PAGE_SIZE = 25;

// Confidence → band label
function getBand(score: number): string {
  if (score < 0.25) return "0–25%";
  if (score < 0.5)  return "25–50%";
  if (score < 0.75) return "50–75%";
  return "75–100%";
}

const DISTRESS_COLOR = "hsl(var(--distress))";
const STABLE_COLOR   = "hsl(var(--stable))";
const BAND_COLORS    = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd"];

export default function OverviewPage() {
  const [records, setRecords] = useState<RecordEntry[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.records(page, PAGE_SIZE)
      .then((r: RecordsResponse) => {
        if (!cancelled) {
          setRecords(r.items);
          setTotal(r.total);
        }
      })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page]);

  // Aggregate all records from first page only for charts — sufficient for visualisation
  const distressCount = records.filter((r) => r.prediction === "Distress").length;
  const stableCount   = records.filter((r) => r.prediction === "Stable").length;

  const pieData = [
    { name: "Distress", value: distressCount },
    { name: "Stable",   value: stableCount },
  ];

  const bandCounts: Record<string, number> = { "0–25%": 0, "25–50%": 0, "50–75%": 0, "75–100%": 0 };
  records.forEach((r) => { bandCounts[getBand(r.confidence_score)]++; });
  const barData = Object.entries(bandCounts).map(([band, count]) => ({ band, count }));

  const avgConf = records.length
    ? records.reduce((s, r) => s + r.confidence_score, 0) / records.length
    : 0;

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Analytics Overview</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          De-identified population-level insights across all inference records
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Total Records",
            value: total,
            icon: <FileText className="w-4 h-4" />,
            color: "text-primary",
          },
          {
            label: "Distress Cases",
            value: distressCount,
            icon: <AlertTriangle className="w-4 h-4" />,
            color: "text-distress",
          },
          {
            label: "Stable Cases",
            value: stableCount,
            icon: <CheckCircle2 className="w-4 h-4" />,
            color: "text-stable",
          },
          {
            label: "Avg Confidence",
            value: `${Math.round(avgConf * 100)}%`,
            icon: <Activity className="w-4 h-4" />,
            color: "text-foreground",
          },
        ].map(({ label, value, icon, color }) => (
          <div key={label} className="clinical-card p-4">
            <div className={`flex items-center gap-1.5 ${color} mb-2`}>
              {icon}
              <span className="text-xs font-medium text-muted-foreground">{label}</span>
            </div>
            <div className="font-num text-2xl font-semibold text-foreground">{value}</div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      {records.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Distress vs Stable pie */}
          <div className="clinical-card p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">
              Outcome Distribution
            </h2>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${Math.round(percent * 100)}%`}
                  labelLine={false}
                >
                  {pieData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={entry.name === "Distress" ? DISTRESS_COLOR : STABLE_COLOR}
                    />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => [v, "Records"]} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Confidence band bar chart */}
          <div className="clinical-card p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">
              Confidence Band Distribution
            </h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barData} margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="band" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" name="Records" radius={[3, 3, 0, 0]}>
                  {barData.map((_, i) => (
                    <Cell key={i} fill={BAND_COLORS[i % BAND_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Records table */}
      <div className="clinical-card overflow-hidden">
        <header className="px-5 py-3.5 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Inference Records</h2>
          <span className="text-xs text-muted-foreground tabular-nums">{total} total</span>
        </header>

        {loading && (
          <div className="px-5 py-8 text-center text-sm text-muted-foreground">Loading records…</div>
        )}
        {error && (
          <div className="px-5 py-4 text-sm text-distress">{error}</div>
        )}
        {!loading && !error && records.length === 0 && (
          <div className="px-5 py-10 text-center">
            <p className="text-sm text-muted-foreground">No records found.</p>
          </div>
        )}
        {!loading && records.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-surface-2/50">
                    {["Patient ID", "Prediction", "Confidence", "Timestamp"].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-left font-semibold text-muted-foreground"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.map((rec, idx) => {
                    const isDistress = rec.prediction === "Distress";
                    return (
                      <tr
                        key={rec.id ?? idx}
                        className="border-b border-border/60 hover:bg-surface-2/30 transition-colors"
                      >
                        <td className="px-4 py-3 font-num font-medium text-foreground">
                          {rec.patient_id}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={[
                              "inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full",
                              isDistress
                                ? "bg-distress-soft text-distress"
                                : "bg-stable-soft text-stable",
                            ].join(" ")}
                          >
                            {isDistress ? (
                              <AlertTriangle className="w-2.5 h-2.5" />
                            ) : (
                              <CheckCircle2 className="w-2.5 h-2.5" />
                            )}
                            {rec.prediction}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-num text-foreground">
                          {Math.round(rec.confidence_score * 100)}%
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {rec.timestamp
                            ? new Date(rec.timestamp).toLocaleString()
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="px-5 py-3.5 border-t border-border flex items-center justify-between">
              <span className="text-xs text-muted-foreground tabular-nums">
                Page {page} of {totalPages}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="h-7 w-7 flex items-center justify-center rounded border border-border hover:bg-surface-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="h-7 w-7 flex items-center justify-center rounded border border-border hover:bg-surface-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
