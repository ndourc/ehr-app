import { PredictResponse } from "@/lib/ehrApi";
import { XAIHighlighter } from "./XAIHighlighter";
import { AlertTriangle, CheckCircle2, Sparkles, Loader2 } from "lucide-react";

interface PredictionPanelProps {
  result: PredictResponse | null;
  loading: boolean;
  error: string | null;
  clinicalText: string;
  latencyMs: number | null;
}

export function PredictionPanel({
  result,
  loading,
  error,
  clinicalText,
  latencyMs,
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

      {error ? (
        <div className="m-5 p-4 rounded-lg border border-distress/30 bg-distress-soft text-foreground">
          <div className="flex items-center gap-2 mb-1 text-distress">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs font-semibold uppercase tracking-wide">
              Request failed
            </span>
          </div>
          <div className="text-sm break-words">{error}</div>
        </div>
      ) : null}

      {!result && !loading && !error ? (
        <EmptyState />
      ) : loading ? (
        <LoadingState />
      ) : result ? (
        <ResultState result={result} clinicalText={clinicalText} />
      ) : null}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="px-6 py-12 text-center">
      <div className="w-12 h-12 mx-auto rounded-full bg-primary-soft text-primary flex items-center justify-center mb-3">
        <Sparkles className="w-5 h-5" />
      </div>
      <div className="text-sm font-medium text-foreground">Awaiting inference</div>
      <div className="text-xs text-muted-foreground mt-1">
        Populate the clinical note and metrics, then run the model.
      </div>
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
          "ClinicalBERT NLP (6-step)",
          "RF / SVM ensemble (16 vars)",
          "Fusion + attention extraction",
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

function ResultState({
  result,
  clinicalText,
}: {
  result: PredictResponse;
  clinicalText: string;
}) {
  const isDistress = result.prediction === "Distress";
  const pct = Math.round(result.confidence_score * 100);

  return (
    <div>
      {/* Verdict */}
      <div
        className={[
          "px-5 py-5 border-b border-border",
          isDistress ? "bg-distress-soft" : "bg-stable-soft",
        ].join(" ")}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div
              className={[
                "w-10 h-10 rounded-full flex items-center justify-center shrink-0",
                isDistress
                  ? "bg-distress text-distress-foreground"
                  : "bg-stable text-stable-foreground",
              ].join(" ")}
            >
              {isDistress ? (
                <AlertTriangle className="w-5 h-5" />
              ) : (
                <CheckCircle2 className="w-5 h-5" />
              )}
            </div>
            <div>
              <div className="section-eyebrow">Prediction</div>
              <div className="text-2xl font-semibold tracking-tight text-foreground mt-0.5">
                {result.prediction}
              </div>
              <div className="text-xs text-muted-foreground mt-1 tabular-nums">
                Patient · {result.patient_id}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="section-eyebrow">Confidence</div>
            <div className="font-num text-4xl font-semibold tracking-tight text-foreground mt-0.5">
              {pct}
              <span className="text-xl text-muted-foreground">%</span>
            </div>
          </div>
        </div>

        {/* Confidence bar */}
        <div className="mt-4 h-1.5 w-full rounded-full bg-surface overflow-hidden">
          <div
            className={[
              "h-full rounded-full transition-all",
              isDistress ? "bg-distress" : "bg-stable",
            ].join(" ")}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* XAI */}
      <div className="p-5 space-y-4">
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            Explainable AI · attention trace
          </h3>
          <span className="text-[11px] font-medium text-muted-foreground tabular-nums">
            {result.important_tokens.length} tokens
          </span>
        </div>

        <div className="rounded-lg border border-border bg-surface-2 p-4">
          <XAIHighlighter text={clinicalText} tokens={result.important_tokens} />
        </div>

        <div className="space-y-1.5 pt-1">
          {result.important_tokens
            .slice()
            .sort((a, b) => b.weight - a.weight)
            .map((t) => (
              <div key={t.word} className="flex items-center gap-3 text-sm">
                <span className="w-32 truncate font-medium text-foreground">
                  {t.word}
                </span>
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
      </div>
    </div>
  );
}
