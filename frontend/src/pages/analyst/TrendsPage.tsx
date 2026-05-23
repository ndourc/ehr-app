import { useEffect, useState } from "react";
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { api, type RecordEntry, type RecordsResponse } from "@/lib/ehrApi";
import { TrendingUp } from "lucide-react";

// Group records by date bucket (YYYY-MM-DD) and compute:
//  - average confidence
//  - distress prevalence %
function buildTrendData(records: RecordEntry[]) {
  const byDate: Record<string, { confidenceSum: number; distressCount: number; total: number }> = {};

  for (const r of records) {
    if (!r.timestamp) continue;
    const date = r.timestamp.split("T")[0]; // "2024-06-15"
    if (!byDate[date]) byDate[date] = { confidenceSum: 0, distressCount: 0, total: 0 };
    byDate[date].confidenceSum += r.confidence_score;
    byDate[date].total++;
    if (r.prediction === "Distress") byDate[date].distressCount++;
  }

  return Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, { confidenceSum, distressCount, total }]) => ({
      date,
      avgConfidence: Math.round((confidenceSum / total) * 100),
      distressPrevalence: Math.round((distressCount / total) * 100),
      records: total,
    }));
}

export default function TrendsPage() {
  const [trendData, setTrendData] = useState<ReturnType<typeof buildTrendData>>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [totalFetched, setTotalFetched] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    // Fetch first page (up to 200) — sufficient for trend visualisation without a dedicated endpoint
    api.records(1, 200)
      .then((r: RecordsResponse) => {
        if (!cancelled) {
          setTrendData(buildTrendData(r.items));
          setTotalFetched(r.items.length);
        }
      })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Trends</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Temporal analysis across {totalFetched} most recent records
        </p>
      </div>

      {loading && (
        <div className="clinical-card px-5 py-10 text-center text-sm text-muted-foreground">
          Loading trend data…
        </div>
      )}

      {error && (
        <div className="clinical-card px-5 py-4 text-sm text-distress">{error}</div>
      )}

      {!loading && !error && trendData.length === 0 && (
        <div className="clinical-card px-5 py-12 text-center">
          <TrendingUp className="w-8 h-8 mx-auto text-muted-foreground/40 mb-3" />
          <p className="text-sm text-muted-foreground">No trend data yet — run some inferences to populate this view.</p>
        </div>
      )}

      {!loading && trendData.length > 0 && (
        <>
          {/* Average confidence over time */}
          <div className="clinical-card p-5">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-foreground">Average Confidence Over Time</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Mean prediction confidence per calendar day
              </p>
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={trendData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v: string) => v.slice(5)} // "MM-DD"
                />
                <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
                <Tooltip formatter={(v: number) => [`${v}%`, "Avg Confidence"]} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avgConfidence"
                  name="Avg Confidence"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "hsl(var(--primary))" }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Distress prevalence over time */}
          <div className="clinical-card p-5">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-foreground">Distress Prevalence Over Time</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                % of records flagged as Distress per calendar day
              </p>
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={trendData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="distressGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--distress))" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="hsl(var(--distress))" stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v: string) => v.slice(5)}
                />
                <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
                <Tooltip formatter={(v: number) => [`${v}%`, "Distress %"]} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="distressPrevalence"
                  name="Distress %"
                  stroke="hsl(var(--distress))"
                  strokeWidth={2}
                  fill="url(#distressGrad)"
                  dot={{ r: 3, fill: "hsl(var(--distress))" }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Summary table */}
          <div className="clinical-card overflow-hidden">
            <header className="px-5 py-3.5 border-b border-border">
              <h2 className="text-sm font-semibold text-foreground">Daily Breakdown</h2>
            </header>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-surface-2/50">
                    {["Date", "Records", "Avg Confidence", "Distress %"].map((h) => (
                      <th key={h} className="px-4 py-3 text-left font-semibold text-muted-foreground">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {trendData.slice().reverse().map((row) => (
                    <tr key={row.date} className="border-b border-border/60 hover:bg-surface-2/30 transition-colors">
                      <td className="px-4 py-3 font-medium text-foreground">{row.date}</td>
                      <td className="px-4 py-3 font-num text-muted-foreground">{row.records}</td>
                      <td className="px-4 py-3 font-num text-foreground">{row.avgConfidence}%</td>
                      <td className="px-4 py-3">
                        <span
                          className={[
                            "inline-block font-num font-semibold px-2 py-0.5 rounded text-[11px]",
                            row.distressPrevalence >= 60
                              ? "bg-distress-soft text-distress"
                              : row.distressPrevalence >= 30
                              ? "bg-yellow-100 text-yellow-700"
                              : "bg-stable-soft text-stable",
                          ].join(" ")}
                        >
                          {row.distressPrevalence}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
