import { useEffect, useState } from "react";
import { api } from "@/lib/ehrApi";
import { ShieldCheck, Activity, CheckCircle2, XCircle, RefreshCw, Clock } from "lucide-react";

interface HealthData {
  status: string;
  pipeline_ready: boolean;
  timestamp: string;
}

export default function SystemPage() {
  const [health, setHealth]       = useState<HealthData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [refreshing, setRefreshing]   = useState(false);

  function fetchHealth() {
    setRefreshing(true);
    setError(null);
    api.health()
      .then((h) => {
        setHealth(h);
        setLastChecked(new Date());
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => {
        setLoading(false);
        setRefreshing(false);
      });
  }

  useEffect(fetchHealth, []);

  const apiStatus = health?.status === "ok" || health?.status === "healthy";
  const pipelineOk = health?.pipeline_ready === true;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-foreground">System Health</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Real-time status of API and ML pipeline components
          </p>
        </div>
        <button
          onClick={fetchHealth}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 h-9 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-surface-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw className={["w-3.5 h-3.5", refreshing ? "animate-spin" : ""].join(" ")} />
          Refresh
        </button>
      </div>

      {loading && !health && (
        <div className="clinical-card px-5 py-10 text-center text-sm text-muted-foreground">
          Checking system status…
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-distress/30 bg-distress-soft p-5">
          <div className="flex items-center gap-2 text-distress mb-1">
            <XCircle className="w-4 h-4" />
            <span className="text-xs font-semibold uppercase tracking-wide">Health check failed</span>
          </div>
          <p className="text-sm text-foreground">{error}</p>
          <p className="text-xs text-muted-foreground mt-2">
            Ensure the FastAPI backend is running on the configured host.
          </p>
        </div>
      )}

      {health && (
        <>
          {/* Last checked timestamp */}
          {lastChecked && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="w-3 h-3" />
              Last checked: {lastChecked.toLocaleTimeString()}
            </div>
          )}

          {/* Status cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* API layer */}
            <div className="clinical-card-elevated p-5">
              <div className="flex items-start justify-between gap-2 mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Activity className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <div className="section-eyebrow">Component</div>
                    <div className="text-sm font-semibold text-foreground">API Layer</div>
                  </div>
                </div>
                <StatusBadge ok={apiStatus} />
              </div>
              <dl className="space-y-2 text-xs">
                <Row label="Status" value={health.status} mono />
                <Row label="Server time" value={new Date(health.timestamp).toLocaleTimeString()} mono />
                <Row label="Endpoint" value={`${import.meta.env.VITE_API_BASE ?? "http://localhost:8000"}/api/v1/health`} mono />
              </dl>
            </div>

            {/* ML pipeline */}
            <div className="clinical-card-elevated p-5">
              <div className="flex items-start justify-between gap-2 mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                    <ShieldCheck className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <div className="section-eyebrow">Component</div>
                    <div className="text-sm font-semibold text-foreground">ML Pipeline</div>
                  </div>
                </div>
                <StatusBadge ok={pipelineOk} />
              </div>
              <dl className="space-y-2 text-xs">
                <Row label="Pipeline ready" value={pipelineOk ? "Yes" : "No"} mono />
                <Row label="Model type" value="ClinicalBERT + RF/SVM ensemble" />
                <Row label="Artifacts" value="classifier.joblib · embedding_cache.npz" mono />
              </dl>
            </div>
          </div>

          {/* Component checklist */}
          <div className="clinical-card p-5 space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Component Checklist</h2>
            <ul className="space-y-2">
              {[
                { label: "FastAPI application server",     ok: apiStatus },
                { label: "Authentication (JWT)",          ok: apiStatus },
                { label: "NLP engine (ClinicalBERT)",     ok: pipelineOk },
                { label: "Structured classifier (RF/SVM)", ok: pipelineOk },
                { label: "Fusion & explainability layer", ok: pipelineOk },
                { label: "Database (SQLite / PostgreSQL)", ok: apiStatus },
              ].map(({ label, ok }) => (
                <li key={label} className="flex items-center gap-2.5 text-sm text-foreground">
                  {ok ? (
                    <CheckCircle2 className="w-4 h-4 text-stable shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-distress shrink-0" />
                  )}
                  {label}
                </li>
              ))}
            </ul>
          </div>

          {/* Note */}
          <p className="text-[11px] text-muted-foreground">
            Health data reflects the API response at the last refresh. Pipeline readiness depends on
            whether model artifacts were loaded during server startup.
          </p>
        </>
      )}
    </div>
  );
}

// ── Internal helpers ──────────────────────────────────────────────────────────
function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span
      className={[
        "flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full",
        ok ? "bg-stable-soft text-stable" : "bg-distress-soft text-distress",
      ].join(" ")}
    >
      <span className={["w-1.5 h-1.5 rounded-full", ok ? "bg-stable" : "bg-distress"].join(" ")} />
      {ok ? "Operational" : "Degraded"}
    </span>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-muted-foreground shrink-0">{label}</dt>
      <dd
        className={[
          "text-right text-foreground break-all",
          mono ? "font-num font-medium" : "",
        ].join(" ")}
      >
        {value}
      </dd>
    </div>
  );
}
