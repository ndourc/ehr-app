import { useEffect, useState } from "react";
import { api, type RecordEntry } from "@/lib/ehrApi";
import { useAuth } from "@/contexts/AuthContext";
import { DashboardShell } from "@/components/DashboardShell";
import { AlertTriangle, CheckCircle2, Clock, TrendingUp } from "lucide-react";

export default function PatientDashboard() {
  const { user } = useAuth();
  const [records, setRecords] = useState<RecordEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .records(1, 20)
      .then((r) => setRecords(r.items))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const distressCount = records.filter((r) => r.prediction === "Distress").length;
  const stableCount = records.filter((r) => r.prediction === "Stable").length;
  const latest = records[0];

  return (
    <DashboardShell title="My Health">
      {/* Welcome */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-foreground">
          Welcome back, {user?.username}
        </h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Clinical ID: <span className="font-mono">{user?.patient_profile_id ?? "—"}</span>
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
        <StatCard
          label="Total Assessments"
          value={String(records.length)}
          icon={<TrendingUp className="w-4 h-4" />}
          color="text-primary"
        />
        <StatCard
          label="Stable"
          value={String(stableCount)}
          icon={<CheckCircle2 className="w-4 h-4" />}
          color="text-green-600"
        />
        <StatCard
          label="Distress Flags"
          value={String(distressCount)}
          icon={<AlertTriangle className="w-4 h-4" />}
          color="text-red-500"
        />
      </div>

      {/* Latest result */}
      {latest && (
        <div className="mb-6 rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-semibold text-foreground mb-3">Latest Assessment</h3>
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full ${
                latest.prediction === "Distress"
                  ? "bg-red-100 text-red-700"
                  : "bg-green-100 text-green-700"
              }`}
            >
              {latest.prediction === "Distress" ? (
                <AlertTriangle className="w-3.5 h-3.5" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5" />
              )}
              {latest.prediction}
            </span>
            <span className="text-xs text-muted-foreground">
              Confidence: {(latest.confidence_score * 100).toFixed(1)}%
            </span>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {latest.timestamp ? new Date(latest.timestamp).toLocaleString() : "—"}
            </span>
          </div>
        </div>
      )}

      {/* History */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border">
          <h3 className="text-sm font-semibold text-foreground">Assessment History</h3>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-muted-foreground">Loading…</p>
        ) : error ? (
          <p className="p-5 text-sm text-destructive">{error}</p>
        ) : records.length === 0 ? (
          <p className="p-5 text-sm text-muted-foreground">No assessments on record yet.</p>
        ) : (
          <div className="divide-y divide-border">
            {records.map((r) => (
              <div key={r.id} className="px-5 py-3 flex items-center justify-between gap-4">
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded ${
                    r.prediction === "Distress"
                      ? "bg-red-100 text-red-700"
                      : "bg-green-100 text-green-700"
                  }`}
                >
                  {r.prediction}
                </span>
                <span className="text-xs text-muted-foreground">
                  {(r.confidence_score * 100).toFixed(1)}% confidence
                </span>
                <span className="text-xs text-muted-foreground ml-auto">
                  {r.timestamp ? new Date(r.timestamp).toLocaleDateString() : "—"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardShell>
  );
}

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className={`mb-2 ${color}`}>{icon}</div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
    </div>
  );
}
