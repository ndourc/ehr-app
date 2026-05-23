import { METRICS, type ImportantToken, type PredictResponse, type StructuredMetrics } from "@/lib/ehrApi";
import { XAIHighlighter } from "./XAIHighlighter";
import {
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  Loader2,
  Info,
} from "lucide-react";

// ── Severity tier ─────────────────────────────────────────────────────────────
// Only applied to Distress predictions; confidence drives the risk band.
interface SeverityTier {
  label: string;
  min: number;
  badge: string;
  border: string;
}
const TIERS: SeverityTier[] = [
  { label: "Low Concern",  min: 0,  badge: "bg-green-100  text-green-700  border-green-200",  border: "border-l-green-400" },
  { label: "Monitor",      min: 40, badge: "bg-yellow-100 text-yellow-700 border-yellow-200", border: "border-l-yellow-400" },
  { label: "Elevated",     min: 70, badge: "bg-orange-100 text-orange-700 border-orange-200", border: "border-l-orange-400" },
  { label: "High-Risk",   min: 85, badge: "bg-red-100    text-red-700    border-red-200",    border: "border-l-red-500" },
];

function getTier(pct: number): SeverityTier {
  let tier = TIERS[0];
  for (const t of TIERS) {
    if (pct >= t.min) tier = t;
  }
  return tier;
}

// ── Clinical summary generator ─────────────────────────────────────────────────
function buildClinicalSummary(
  result: PredictResponse,
  structured: StructuredMetrics | null | undefined
): { headline: string; indicators: string[]; recommendation: string } {
  const isDistress = result.prediction === "Distress";
  const pct = Math.round(result.confidence_score * 100);
  const tier = getTier(pct);

  // Top 3 NLP tokens, cleaned
  const topTokens = (result.important_tokens ?? [])
    .slice()
    .sort((a: ImportantToken, b: ImportantToken) => b.weight - a.weight)
    .slice(0, 3)
    .map((t: ImportantToken) => t.word.replace(/_/g, " "));

  // Top structured contributors (severity >= 2)
  const metricLabelMap = Object.fromEntries(METRICS.map((m) => [m.key, m.label]));
  const topStructured = structured
    ? Object.entries(structured)
        .filter(([, v]) => v >= 2)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 3)
        .map(([k]) => metricLabelMap[k] ?? k)
    : [];

  const indicators = [
    ...topTokens.map((t) => `"${t}" — language pattern`),
    ...topStructured.map((l) => `${l} (scored ≥ Moderate)`),
  ].slice(0, 5);

  const headline = isDistress
    ? `${tier.label} psychological distress likelihood detected (${pct}% confidence).`
    : `Low distress likelihood — patient presentation appears stable (${pct}% confidence).`;

  const recommendation = isDistress
    ? pct >= 85
      ? "Consider urgent psychological evaluation and immediate clinical follow-up."
      : pct >= 70
      ? "Recommend mental health follow-up within 72 hours."
      : "Monitor closely. Consider support services referral."
    : "Routine follow-up per standard care pathway.";

  return { headline, indicators, recommendation };
}

// ── Props ─────────────────────────────────────────────────────────────────────
interface PredictionPanelProps {
  result: PredictResponse | null;
  loading: boolean;
  error: string | null;
  clinicalText: string;
  latencyMs: number | null;
  structured?: StructuredMetrics | null;
}

// ── Main component ────────────────────────────────────────────────────────────
export function PredictionPanel({
  result,
  loading,
  error,
  clinicalText,
  latencyMs,
  structured,
}: PredictionPanelProps) {
  return (
    <div className="clinical-card-elevated overflow-hidden">
      <header className="px-5 py-3.5 border-b border-border flex items-center justify-between bg-surface">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" strokeWidth={2.25} />
          <h2 className="text-sm font-semibold text-foreground">Inference Output</h2>
        </div>
        <span className="text-[11px] font-medium text-muted-foreground tabular-nums">
          {loading ? "Computing…" : latencyMs != null ? `${latencyMs} ms` : "Idle"}
        </span>
      </header>

      {error && (
        <div className="m-5 p-4 rounded-lg border border-distress/30 bg-distress-soft">
          <div className="flex items-center gap-2 mb-1 text-distress">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs font-semibold uppercase tracking-wide">Request failed</span>
          </div>
          <div className="text-sm text-foreground break-words">{error}</div>
        </div>
      )}

      {!result && !loading && !error && <EmptyState />}
      {loading && <LoadingState />}
      {result && !loading && (
        <ResultState result={result} clinicalText={clinicalText} structured={structured} />
      )}
    </div>
  );
}

// ── Empty / Loading states ────────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="px-6 py-12 text-center">
      <div className="w-12 h-12 mx-auto rounded-full bg-primary/10 text-primary flex items-center justify-center mb-3">
        <Sparkles className="w-5 h-5" />
      </div>
      <p className="text-sm font-medium text-foreground">Awaiting inference</p>
      <p className="text-xs text-muted-foreground mt-1">
        Complete the patient assessment and clinical notes, then run the model.
      </p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="px-6 py-8 space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Loader2 className="w-4 h-4 animate-spin text-primary" />
        Running hybrid pipeline
      </div>
      <ul className="space-y-2 pl-1">
        {[
          "ClinicalBERT NLP (6-step preprocessing)",
          "RF / SVM ensemble (16 structured vars)",
          "Fusion + attention weight extraction",
        ].map((s) => (
          <li key={s} className="flex items-center gap-2.5 text-xs text-muted-foreground">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            {s}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Full result state ─────────────────────────────────────────────────────────
function ResultState({
  result,
  clinicalText,
  structured,
}: {
  result: PredictResponse;
  clinicalText: string;
  structured?: StructuredMetrics | null;
}) {
  const isDistress = result.prediction === "Distress";
  const pct = Math.round(result.confidence_score * 100);
  const tier = getTier(pct);
  const summary = buildClinicalSummary(result, structured);

  // Top 5 structured contributors for the feature importance strip
  const metricLabelMap = Object.fromEntries(METRICS.map((m) => [m.key, m.label]));
  const topStructured = structured
    ? Object.entries(structured)
        .map(([k, v]) => ({ label: metricLabelMap[k] ?? k, value: v as number }))
        .filter(({ value }) => value > 0)
        .sort((a, b) => b.value - a.value)
        .slice(0, 5)
    : [];

  return (
    <div>
      {/* ── Verdict header ── */}
      <div
        className={[
          "px-5 py-5 border-b border-border border-l-4",
          isDistress ? `bg-distress-soft ${tier.border}` : "bg-stable-soft border-l-green-500",
        ].join(" ")}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div
              className={[
                "w-10 h-10 rounded-full flex items-center justify-center shrink-0 mt-0.5",
                isDistress ? "bg-distress text-distress-foreground" : "bg-stable text-stable-foreground",
              ].join(" ")}
            >
              {isDistress ? <AlertTriangle className="w-5 h-5" /> : <CheckCircle2 className="w-5 h-5" />}
            </div>
            <div>
              <div className="section-eyebrow">Prediction</div>
              <div className="text-2xl font-semibold tracking-tight text-foreground mt-0.5">
                {result.prediction}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5 tabular-nums">
                Patient · {result.patient_id}
              </div>
            </div>
          </div>

          <div className="text-right shrink-0">
            <div className="section-eyebrow">Confidence</div>
            <div className="font-num text-4xl font-semibold tracking-tight text-foreground mt-0.5">
              {pct}
              <span className="text-xl text-muted-foreground">%</span>
            </div>
            {isDistress && (
              <span className={`inline-block mt-1 text-[11px] font-semibold px-2 py-0.5 rounded border ${tier.badge}`}>
                {tier.label}
              </span>
            )}
          </div>
        </div>

        {/* Confidence bar */}
        <div className="mt-4 h-1.5 w-full rounded-full bg-surface overflow-hidden">
          <div
            className={["h-full rounded-full transition-all", isDistress ? "bg-distress" : "bg-stable"].join(" ")}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* ── AI-assisted clinical summary ── */}
      <div className="px-5 py-4 border-b border-border bg-surface-2/30">
        <div className="flex items-center gap-1.5 mb-2">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          <span className="text-xs font-semibold text-foreground">AI-assisted summary</span>
          <span className="ml-auto text-[10px] text-muted-foreground italic">Not a diagnosis</span>
        </div>
        <p className="text-sm text-foreground mb-2">{summary.headline}</p>
        {summary.indicators.length > 0 && (
          <div className="mb-2">
            <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
              Primary indicators
            </p>
            <ul className="space-y-0.5">
              {summary.indicators.map((ind, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-foreground">
                  <span className="text-primary mt-0.5">·</span>
                  {ind}
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="mt-2 px-3 py-2 rounded-md bg-card border border-border text-xs text-foreground">
          <span className="font-medium">Recommendation: </span>
          {summary.recommendation}
        </div>
      </div>

      {/* ── Structured feature contributions ── */}
      {topStructured.length > 0 && (
        <div className="px-5 py-4 border-b border-border">
          <p className="text-xs font-semibold text-foreground mb-3">
            Top Structured Contributors
          </p>
          <div className="space-y-2">
            {topStructured.map(({ label, value }) => (
              <div key={label} className="flex items-center gap-3 text-xs">
                <span className="w-36 truncate text-muted-foreground shrink-0">{label}</span>
                <div className="flex-1 h-2 bg-surface-2 rounded-full overflow-hidden">
                  <div
                    className={[
                      "h-full rounded-full",
                      value === 3 ? "bg-red-400" : value === 2 ? "bg-orange-400" : "bg-yellow-400",
                    ].join(" ")}
                    style={{ width: `${(value / 3) * 100}%` }}
                  />
                </div>
                <span
                  className={[
                    "text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0",
                    value === 3 ? "bg-red-100 text-red-700" : value === 2 ? "bg-orange-100 text-orange-700" : "bg-yellow-100 text-yellow-700",
                  ].join(" ")}
                >
                  {["None", "Mild", "Moderate", "Severe"][value]}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── XAI: highlighted text ── */}
      <div className="px-5 py-4 space-y-4">
        <div className="flex items-baseline justify-between">
          <h3 className="text-xs font-semibold text-foreground">
            Explainable AI · Attention Trace
          </h3>
          <span className="text-[11px] text-muted-foreground tabular-nums">
            {result.important_tokens.length} tokens
          </span>
        </div>

        {/* Token legend */}
        <div className="flex flex-wrap gap-3 text-[10px] font-medium text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm bg-primary/20 border border-primary/30" />
            Mild influence
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm bg-yellow-200 border border-yellow-300" />
            Moderate influence
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm bg-orange-200 border border-orange-300" />
            High influence
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm bg-red-200 border border-red-300" />
            Critical influence
          </span>
        </div>

        <div className="rounded-lg border border-border bg-surface-2 p-4">
          <XAIHighlighter text={clinicalText} tokens={result.important_tokens} />
        </div>

        {/* Ranked token list */}
        <div className="space-y-1.5 pt-1">
          {result.important_tokens
            .slice()
            .sort((a, b) => b.weight - a.weight)
            .map((t) => (
              <div key={t.word} className="flex items-center gap-3 text-sm">
                <span className="w-32 truncate font-medium text-foreground">{t.word}</span>
                <div className="h-2 flex-1 rounded-full bg-surface-2 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.round(t.weight * 100)}%` }}
                  />
                </div>
                <span className="w-12 text-right font-num text-xs text-muted-foreground tabular-nums">
                  {t.weight.toFixed(2)}
                </span>
              </div>
            ))}
        </div>

        {/* Disclaimer */}
        <div className="flex items-start gap-2 text-[11px] text-muted-foreground pt-1">
          <Info className="w-3 h-3 shrink-0 mt-0.5" />
          <span>
            Attention weights are a proxy for model influence, not a clinical guarantee.
            Always apply clinical judgement.
          </span>
        </div>
      </div>
    </div>
  );
}
