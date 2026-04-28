import { useMemo, useState } from "react";
import { api, defaultStructured, type PredictRequest, type PredictResponse, type StructuredMetrics } from "@/lib/ehrApi";
import { useAuth } from "@/contexts/AuthContext";
import { DashboardShell } from "@/components/DashboardShell";
import { MetricsMatrix } from "@/components/MetricsMatrix";
import { PredictionPanel } from "@/components/PredictionPanel";
import { AuditLog } from "@/components/AuditLog";
import { Activity, ClipboardList, History, Play, RotateCcw, Stethoscope } from "lucide-react";

const SAMPLE_TEXT =
  "Patient reports extreme anxiety and cannot sleep. Does not leave the house. Feels isolated from family and coworkers.";

export default function ClinicianDashboard() {
  const { user } = useAuth();
  const [tab, setTab] = useState<"infer" | "audit">("infer");
  const [patientId, setPatientId] = useState("PT00001");
  const [clinicalText, setClinicalText] = useState(SAMPLE_TEXT);
  const [structured, setStructured] = useState<StructuredMetrics>(defaultStructured);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [submittedText, setSubmittedText] = useState("");

  const filledMetrics = useMemo(
    () => Object.values(structured).filter((v) => v > 0).length,
    [structured]
  );

  const canSubmit = !loading && patientId.trim().length > 0 && clinicalText.trim().length > 0;

  async function handlePredict() {
    if (!canSubmit) return;
    const payload: PredictRequest = {
      patient_id: patientId.trim(),
      timestamp: new Date().toISOString(),
      clinical_text: clinicalText,
      structured,
    };
    setLoading(true);
    setError(null);
    setResult(null);
    const t0 = performance.now();
    try {
      const r = await api.predict(payload);
      setResult(r);
      setSubmittedText(payload.clinical_text);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLatencyMs(Math.round(performance.now() - t0));
      setLoading(false);
    }
  }

  return (
    <DashboardShell title="Clinician Dashboard">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Activity className="w-4 h-4" />
        <span>Logged in as <strong className="text-foreground">{user?.username}</strong></span>
      </div>

      <nav className="inline-flex p-1 rounded-lg border border-border bg-card shadow-xs mb-6">
        <TabBtn active={tab === "infer"} onClick={() => setTab("infer")} icon={<Stethoscope className="w-4 h-4" />}>
          Inference
        </TabBtn>
        <TabBtn active={tab === "audit"} onClick={() => setTab("audit")} icon={<History className="w-4 h-4" />}>
          Audit Log
        </TabBtn>
      </nav>

      {tab === "infer" ? (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,520px)] gap-6">
          {/* LEFT — inputs */}
          <section className="space-y-6">
            <Panel title="Patient" icon={<ClipboardList className="w-4 h-4 text-primary" />}>
              <div className="p-5 space-y-4">
                <div>
                  <label className="text-[12px] font-medium text-muted-foreground block mb-1.5">
                    Patient ID
                  </label>
                  <input
                    value={patientId}
                    onChange={(e) => setPatientId(e.target.value)}
                    className="w-full sm:w-72 h-10 rounded-md border border-input bg-card px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="PT00001"
                  />
                </div>
                <div>
                  <label className="text-[12px] font-medium text-muted-foreground block mb-1.5">
                    Clinical Notes
                  </label>
                  <textarea
                    value={clinicalText}
                    onChange={(e) => setClinicalText(e.target.value)}
                    rows={5}
                    className="w-full rounded-md border border-input bg-card px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                  />
                </div>
              </div>
            </Panel>

            <Panel
              title={`Behavioural Metrics · ${filledMetrics}/16 scored`}
              icon={<Activity className="w-4 h-4 text-primary" />}
            >
              <div className="p-5">
                <MetricsMatrix values={structured} onChange={setStructured} />
              </div>
              <div className="px-5 py-3.5 border-t border-border flex items-center gap-3">
                <button
                  onClick={handlePredict}
                  disabled={!canSubmit}
                  className="flex items-center gap-2 px-4 h-9 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  <Play className="w-3.5 h-3.5" />
                  Run Inference
                </button>
                <button
                  onClick={() => setStructured(defaultStructured())}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Reset
                </button>
              </div>
            </Panel>
          </section>

          {/* RIGHT — result */}
          <section>
            <PredictionPanel
              result={result}
              loading={loading}
              error={error}
              clinicalText={submittedText}
              latencyMs={latencyMs}
            />
          </section>
        </div>
      ) : (
        <AuditLog />
      )}
    </DashboardShell>
  );
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <header className="px-5 py-3.5 border-b border-border flex items-center gap-2">
        {icon}
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      </header>
      {children}
    </div>
  );
}

function TabBtn({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
        active ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {icon}
      {children}
    </button>
  );
}
