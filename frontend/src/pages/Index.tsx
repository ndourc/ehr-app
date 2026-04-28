import { useMemo, useState } from "react";
import {
  api,
  defaultStructured,
  PredictRequest,
  PredictResponse,
  StructuredMetrics,
} from "@/lib/ehrApi";
import { MetricsMatrix } from "@/components/MetricsMatrix";
import { PredictionPanel } from "@/components/PredictionPanel";
import { AuditLog } from "@/components/AuditLog";
import {
  Activity,
  FileText,
  IdCard,
  Play,
  RotateCcw,
  Stethoscope,
  ClipboardList,
  History,
} from "lucide-react";

const SAMPLE_TEXT =
  "Patient reports extreme anxiety and cannot sleep. Does not leave the house. Feels isolated from family and coworkers.";

const Index = () => {
  const [tab, setTab] = useState<"infer" | "audit">("infer");
  const [patientId, setPatientId] = useState("PT00042");
  const [clinicalText, setClinicalText] = useState(SAMPLE_TEXT);
  const [structured, setStructured] = useState<StructuredMetrics>(defaultStructured);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [submittedText, setSubmittedText] = useState<string>("");

  const filledMetrics = useMemo(
    () => Object.values(structured).filter((v) => v > 0).length,
    [structured]
  );

  const canSubmit =
    !loading && patientId.trim().length > 0 && clinicalText.trim().length > 0;

  async function handlePredict() {
    if (!canSubmit) return;
    const payload: PredictRequest = {
      patient_id: patientId.trim(),
      timestamp: new Date().toISOString(),
      clinical_text: clinicalText, // raw — backend handles NLP
      structured,
    };
    setLoading(true);
    setError(null);
    setResult(null);
    setLatencyMs(null);
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

  function resetMetrics() {
    setStructured(defaultStructured());
  }

  return (
    <div className="min-h-screen bg-background">
      <TopBar />

      <main className="max-w-[1400px] mx-auto px-4 md:px-8 py-6 md:py-8 space-y-6">
        {/* Tabs */}
        <nav className="inline-flex p-1 rounded-lg border border-border bg-card shadow-xs">
          <TabBtn
            active={tab === "infer"}
            onClick={() => setTab("infer")}
            icon={<Stethoscope className="w-4 h-4" />}
          >
            Inference
          </TabBtn>
          <TabBtn
            active={tab === "audit"}
            onClick={() => setTab("audit")}
            icon={<History className="w-4 h-4" />}
          >
            Audit Log
          </TabBtn>
        </nav>

        {tab === "infer" ? (
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,520px)] gap-6">
            {/* LEFT — input matrix */}
            <section className="space-y-6">
              <Panel
                title="Patient"
                icon={<IdCard className="w-4 h-4 text-primary" />}
              >
                <div className="p-5">
                  <label
                    htmlFor="pid"
                    className="text-[12px] font-medium text-muted-foreground block mb-1.5"
                  >
                    Patient ID
                  </label>
                  <input
                    id="pid"
                    value={patientId}
                    onChange={(e) => setPatientId(e.target.value)}
                    className="w-full sm:w-72 h-10 rounded-md border border-input bg-card px-3 text-sm font-medium text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-shadow"
                    placeholder="PT00042"
                  />
                </div>
              </Panel>

              <Panel
                title="Clinical note"
                icon={<FileText className="w-4 h-4 text-primary" />}
                subtitle="Free-text observations · raw string sent to backend NLP"
              >
                <div className="p-5">
                  <textarea
                    value={clinicalText}
                    onChange={(e) => setClinicalText(e.target.value)}
                    rows={6}
                    className="w-full rounded-md border border-input bg-card px-3 py-2.5 text-sm leading-6 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent resize-y transition-shadow"
                    placeholder="Patient presentation, observations, history…"
                  />
                  <div className="flex justify-between mt-2 text-[11px] text-muted-foreground">
                    <span>ClinicalBERT pipeline handles negation & semantics</span>
                    <span className="tabular-nums">{clinicalText.length} chars</span>
                  </div>
                </div>
              </Panel>

              <Panel
                title="Structured metrics"
                icon={<ClipboardList className="w-4 h-4 text-primary" />}
                subtitle="16 ordinal variables · 0 None · 1 Mild · 2 Moderate · 3 Severe"
                right={
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-medium text-muted-foreground tabular-nums">
                      {filledMetrics}/16 elevated
                    </span>
                    <button
                      type="button"
                      onClick={resetMetrics}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground px-2 py-1 rounded-md hover:bg-surface-2 transition-colors"
                    >
                      <RotateCcw className="w-3 h-3" />
                      Reset
                    </button>
                  </div>
                }
              >
                <div className="p-5">
                  <MetricsMatrix values={structured} onChange={setStructured} />
                </div>
              </Panel>

              <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
                <button
                  type="button"
                  onClick={handlePredict}
                  disabled={!canSubmit}
                  className="inline-flex items-center justify-center gap-2 h-11 px-6 rounded-lg bg-primary text-primary-foreground text-sm font-semibold shadow-sm hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <Play className="w-4 h-4 fill-current" />
                  {loading ? "Running…" : "Run inference"}
                </button>
                <div className="text-xs text-muted-foreground">
                  POST <code className="font-mono text-foreground/70">/api/v1/predict</code>{" "}
                  · ≈120 ms on GPU
                </div>
              </div>
            </section>

            {/* RIGHT — results */}
            <aside className="xl:sticky xl:top-6 self-start">
              <PredictionPanel
                result={result}
                loading={loading}
                error={error}
                clinicalText={submittedText || clinicalText}
                latencyMs={latencyMs}
              />
            </aside>
          </div>
        ) : (
          <AuditLog />
        )}
      </main>

      <footer className="mt-12 border-t border-border bg-surface">
        <div className="max-w-[1400px] mx-auto px-4 md:px-8 py-4 flex flex-wrap gap-4 justify-between text-xs text-muted-foreground">
          <span>Sentiment-Aware EHR · v1.0</span>
          <span>Hybrid · ClinicalBERT + RF/SVM ensemble</span>
          <span className="tabular-nums">API · localhost:8000</span>
        </div>
      </footer>
    </div>
  );
};

function TopBar() {
  return (
    <header className="border-b border-border bg-card/80 backdrop-blur supports-[backdrop-filter]:bg-card/70 sticky top-0 z-10">
      <div className="max-w-[1400px] mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center shadow-sm">
            <Activity className="w-5 h-5" strokeWidth={2.5} />
          </div>
          <div className="leading-tight">
            <h1 className="text-[15px] font-semibold text-foreground">
              Sentiment-Aware EHR
            </h1>
            <p className="text-xs text-muted-foreground">
              Clinical decision support · distress prediction
            </p>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-3">
          <StatusPill />
          <span className="text-xs text-muted-foreground">Model · hybrid-1.0</span>
        </div>
      </div>
    </header>
  );
}

function StatusPill() {
  return (
    <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-stable-soft border border-stable/20">
      <span className="relative w-2 h-2 rounded-full bg-stable">
        <span className="pulse-dot" />
      </span>
      <span className="text-[11px] font-medium text-stable">API · live</span>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  icon,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="clinical-card overflow-hidden">
      <header className="px-5 py-3.5 border-b border-border flex items-center justify-between bg-surface">
        <div className="flex items-center gap-2 min-w-0">
          {icon}
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-foreground leading-tight">
              {title}
            </h2>
            {subtitle ? (
              <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                {subtitle}
              </p>
            ) : null}
          </div>
        </div>
        {right}
      </header>
      {children}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "inline-flex items-center gap-2 px-4 h-9 rounded-md text-sm font-medium transition-colors",
        active
          ? "bg-primary text-primary-foreground shadow-xs"
          : "text-muted-foreground hover:text-foreground hover:bg-surface-2",
      ].join(" ")}
    >
      {icon}
      {children}
    </button>
  );
}

export default Index;
