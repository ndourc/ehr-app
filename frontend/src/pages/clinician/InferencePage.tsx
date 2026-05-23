import { useEffect, useMemo, useState } from "react";
import {
  api,
  defaultStructured,
  type PredictRequest,
  type PredictResponse,
  type StructuredMetrics,
} from "@/lib/ehrApi";
import { ClinicalAssessment, clearAssessmentDraft, restoreAssessmentDraft } from "@/components/ClinicalAssessment";
import { PredictionPanel } from "@/components/PredictionPanel";
import { ClipboardList, Play, Save } from "lucide-react";

const DRAFT_PID_KEY  = "ehr_draft_pid";
const DRAFT_TEXT_KEY = "ehr_draft_text";

const SAMPLE_TEXT =
  "Patient reports extreme anxiety and cannot sleep. Does not leave the house. Feels isolated from family and coworkers.";

export default function InferencePage() {
  // Restore draft values from localStorage on first mount
  const [patientId, setPatientId]     = useState(() => localStorage.getItem(DRAFT_PID_KEY)  ?? "PT00001");
  const [clinicalText, setClinicalText] = useState(() => localStorage.getItem(DRAFT_TEXT_KEY) ?? SAMPLE_TEXT);
  const [structured, setStructured]   = useState<StructuredMetrics>(
    () => restoreAssessmentDraft() ?? defaultStructured()
  );

  const [loading, setLoading]                     = useState(false);
  const [result, setResult]                       = useState<PredictResponse | null>(null);
  const [error, setError]                         = useState<string | null>(null);
  const [latencyMs, setLatencyMs]                 = useState<number | null>(null);
  const [submittedText, setSubmittedText]         = useState("");
  const [submittedStructured, setSubmittedStructured] = useState<StructuredMetrics | null>(null);
  const [draftSaved, setDraftSaved]               = useState(false);

  // Autosave patient ID + clinical text (metrics autosaved by ClinicalAssessment internally)
  useEffect(() => {
    const t = setTimeout(() => {
      localStorage.setItem(DRAFT_PID_KEY,  patientId);
      localStorage.setItem(DRAFT_TEXT_KEY, clinicalText);
      setDraftSaved(true);
      setTimeout(() => setDraftSaved(false), 2000);
    }, 1500);
    return () => clearTimeout(t);
  }, [patientId, clinicalText]);

  const canSubmit = useMemo(
    () => !loading && patientId.trim().length > 0 && clinicalText.trim().length > 0,
    [loading, patientId, clinicalText]
  );

  async function handlePredict() {
    if (!canSubmit) return;
    const payload: PredictRequest = {
      patient_id:    patientId.trim(),
      timestamp:     new Date().toISOString(),
      clinical_text: clinicalText,
      structured,
    };
    setLoading(true);
    setError(null);
    setResult(null);
    setSubmittedText(clinicalText);
    setSubmittedStructured(structured);
    const t0 = performance.now();
    try {
      const r = await api.predict(payload);
      setResult(r);
      clearAssessmentDraft();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLatencyMs(Math.round(performance.now() - t0));
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-foreground">New Assessment</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Dual-stream inference — clinical notes + 16 behavioural indicators
          </p>
        </div>
        {draftSaved && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground pt-1 shrink-0">
            <Save className="w-3 h-3" />
            Draft saved
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,480px)] gap-6 items-start">
        {/* ── Left: inputs ── */}
        <div className="space-y-6">
          {/* Patient + notes panel */}
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <header className="px-5 py-3.5 border-b border-border flex items-center gap-2 bg-surface-2/40">
              <ClipboardList className="w-4 h-4 text-primary" />
              <h2 className="text-sm font-semibold text-foreground">Patient &amp; Clinical Notes</h2>
            </header>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Patient ID
                </label>
                <input
                  value={patientId}
                  onChange={(e) => setPatientId(e.target.value)}
                  className="w-full sm:w-72 h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="PT00001"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Clinical Notes
                </label>
                <textarea
                  value={clinicalText}
                  onChange={(e) => setClinicalText(e.target.value)}
                  rows={5}
                  className="w-full rounded-md border border-input bg-background px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                  placeholder="Enter clinical observations, patient-reported symptoms, or free-text notes…"
                />
                <p className="text-[11px] text-muted-foreground mt-1">
                  Processed by ClinicalBERT · max 512 tokens
                </p>
              </div>
            </div>
          </div>

          {/* Redesigned clinical assessment form */}
          <ClinicalAssessment values={structured} onChange={setStructured} />

          {/* Submit row */}
          <div>
            <button
              onClick={handlePredict}
              disabled={!canSubmit}
              className="flex items-center gap-2 px-6 h-10 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
            >
              <Play className="w-4 h-4" />
              {loading ? "Running inference…" : "Run Inference"}
            </button>
          </div>
        </div>

        {/* ── Right: result (sticky on large screens) ── */}
        <div className="xl:sticky xl:top-6">
          <PredictionPanel
            result={result}
            loading={loading}
            error={error}
            clinicalText={submittedText}
            latencyMs={latencyMs}
            structured={submittedStructured}
          />
        </div>
      </div>
    </div>
  );
}
