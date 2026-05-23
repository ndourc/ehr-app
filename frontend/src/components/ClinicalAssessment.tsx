/**
 * ClinicalAssessment — redesigned behavioural metrics entry form.
 *
 * API contract is UNCHANGED: the same 16 ordinal (0–3) values are submitted.
 * Only the presentation and interaction model have changed to feel like a
 * clinical intake form rather than an ML feature-entry matrix.
 */
import { useEffect, useMemo, useRef } from "react";
import {
  CATEGORY_ORDER,
  defaultStructured,
  METRICS,
  type MetricCategory,
  type Severity,
  type StructuredKey,
  type StructuredMetrics,
} from "@/lib/ehrApi";
import { Brain, Activity, HeartPulse, Lightbulb, Users, RotateCcw, Zap } from "lucide-react";

// ── Clinical descriptor text per metric, per severity level ──────────────────
// Each tuple: [None, Mild, Moderate, Severe]
const DESCRIPTORS: Record<StructuredKey, [string, string, string, string]> = {
  mood_swings:           ["Mood stable and consistent",         "Occasional mild fluctuations",       "Frequent unpredictable mood changes",   "Extreme, rapid mood swings"],
  anxiety_level:         ["No notable anxiety",                 "Mild worry, manageable",             "Persistent anxiety affecting daily life","Severe anxiety or panic episodes"],
  depression_indicators: ["No depressive symptoms",             "Low mood, mild sadness",             "Persistent sadness, loss of interest",  "Severe depression, hopelessness"],
  emotional_stability:   ["Emotionally balanced and resilient", "Slightly sensitive, minor lapses",   "Difficulty regulating emotions",        "Highly unstable emotional state"],
  days_indoors:          ["Goes outdoors regularly",            "Slightly reduced outdoor activity",  "Rarely leaves home",                   "Essentially housebound"],
  social_interaction:    ["Active social life maintained",      "Some withdrawal, still engaging",    "Avoids most social contact",           "Complete social withdrawal"],
  activity_level:        ["Physically active, routine intact",  "Some reduction in activity",         "Markedly low energy, minimal movement", "Sedentary, unable to engage"],
  sleep_quality:         ["Sleeping normally, feeling rested",  "Occasional sleep disturbance",       "Frequent insomnia or broken sleep",    "Persistent inability to sleep"],
  coping_struggles:      ["Manages stressors effectively",      "Some difficulty coping at times",    "Significant coping breakdown",         "Unable to cope with daily demands"],
  stress_level:          ["Minimal perceived stress",           "Noticeable but manageable stress",   "High stress impacting wellbeing",      "Overwhelming, feels out of control"],
  work_engagement:       ["Fully engaged and productive",       "Mild disengagement, reduced focus",  "Struggling to maintain performance",   "Unable to work or engage professionally"],
  motivation_level:      ["Goal-directed and motivated",        "Reduced drive, mild apathy",         "Significant lack of motivation",       "No motivation, complete apathy"],
  concentration_level:   ["Good focus and attention",           "Occasional difficulty concentrating","Poor concentration affecting tasks",   "Unable to concentrate on basic tasks"],
  decision_difficulty:   ["Decides with confidence",            "Slightly indecisive at times",       "Frequent difficulty making decisions",  "Paralysed by decisions, avoids choices"],
  memory_issues:         ["Memory intact, no concerns",         "Minor forgetfulness",                "Noticeable memory lapses",             "Significant memory impairment"],
  support_system:        ["Strong support network available",   "Some support, limited at times",     "Minimal support available",            "No perceived support system"],
};

const SEV_LABELS = ["None", "Mild", "Moderate", "Severe"] as const;

// Active pill styles per severity (filled state)
const PILL_ACTIVE: Record<Severity, string> = {
  0: "bg-muted border-border text-foreground shadow-xs font-semibold",
  1: "bg-yellow-100 border-yellow-300 text-yellow-900 shadow-xs font-semibold",
  2: "bg-orange-100 border-orange-300 text-orange-900 shadow-xs font-semibold",
  3: "bg-red-100   border-red-300   text-red-900   shadow-xs font-semibold",
};

// ── Quick presets ─────────────────────────────────────────────────────────────
type Preset = {
  label: string;
  description: string;
  color: string;
  values: Partial<StructuredMetrics>;
};

const PRESETS: Preset[] = [
  {
    label: "Stable",
    description: "All indicators within normal range",
    color: "border-green-200 text-green-700 hover:bg-green-50",
    values: {},
  },
  {
    label: "Mild Concern",
    description: "Mild elevation across key indicators",
    color: "border-yellow-200 text-yellow-700 hover:bg-yellow-50",
    values: {
      mood_swings: 1, anxiety_level: 1, depression_indicators: 1, days_indoors: 1,
      coping_struggles: 1, stress_level: 1, sleep_quality: 1, motivation_level: 1,
    },
  },
  {
    label: "Elevated Distress",
    description: "Moderate-to-high distress pattern",
    color: "border-orange-200 text-orange-700 hover:bg-orange-50",
    values: {
      mood_swings: 2, anxiety_level: 2, depression_indicators: 2, emotional_stability: 2,
      days_indoors: 2, social_interaction: 2, coping_struggles: 2, stress_level: 2,
      sleep_quality: 2, motivation_level: 1, work_engagement: 2,
    },
  },
  {
    label: "Severe Crisis",
    description: "Critical indicators across multiple domains",
    color: "border-red-200 text-red-700 hover:bg-red-50",
    values: {
      mood_swings: 3, anxiety_level: 3, depression_indicators: 3, emotional_stability: 3,
      days_indoors: 3, social_interaction: 3, coping_struggles: 3, stress_level: 3,
      sleep_quality: 3, motivation_level: 3, work_engagement: 3, activity_level: 2,
      concentration_level: 2, decision_difficulty: 2, memory_issues: 1,
    },
  },
];

// ── Category metadata ─────────────────────────────────────────────────────────
type IconComponent = React.ComponentType<{ className?: string }>;

const CATEGORY_ICON: Record<MetricCategory, IconComponent> = {
  "Psychological State":   Brain,
  "Behavioural Patterns":  Activity,
  "Coping & Stress":       HeartPulse,
  "Cognitive Function":    Lightbulb,
  "Social Context":        Users,
};

const CATEGORY_DESCRIPTION: Record<MetricCategory, string> = {
  "Psychological State":   "Mood, affect, and emotional presentation",
  "Behavioural Patterns":  "Observable daily behaviours and physical routines",
  "Coping & Stress":       "Stress response, work function, and motivational drive",
  "Cognitive Function":    "Attention, memory, and executive function",
  "Social Context":        "Interpersonal engagement and perceived support",
};

// ── Draft persistence ─────────────────────────────────────────────────────────
const DRAFT_KEY = "ehr_draft_metrics";

export function restoreAssessmentDraft(): StructuredMetrics | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    return raw ? (JSON.parse(raw) as StructuredMetrics) : null;
  } catch {
    return null;
  }
}

export function clearAssessmentDraft() {
  localStorage.removeItem(DRAFT_KEY);
}

// ── Component ─────────────────────────────────────────────────────────────────
interface Props {
  values: StructuredMetrics;
  onChange: (next: StructuredMetrics) => void;
}

export function ClinicalAssessment({ values, onChange }: Props) {
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced autosave to localStorage
  useEffect(() => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(values));
    }, 1500);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [values]);

  const filledCount = useMemo(
    () => Object.values(values).filter((v) => v > 0).length,
    [values]
  );
  const elevatedCount = useMemo(
    () => Object.values(values).filter((v) => v >= 2).length,
    [values]
  );

  function applyPreset(preset: Preset) {
    onChange({ ...defaultStructured(), ...preset.values } as StructuredMetrics);
  }

  function setOne(key: StructuredKey, v: Severity) {
    onChange({ ...values, [key]: v });
  }

  const grouped = CATEGORY_ORDER.map((cat) => ({
    cat,
    items: METRICS.filter((m) => m.category === cat),
  }));

  return (
    <div className="space-y-5">
      {/* ── Header: completeness + reset ── */}
      <div className="flex flex-wrap items-center gap-4 justify-between">
        <div className="flex items-center gap-3">
          <div className="text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">{filledCount}</span>
            <span>/16 indicators assessed</span>
            {elevatedCount > 0 && (
              <span className="ml-2 font-medium text-orange-600">
                · {elevatedCount} elevated
              </span>
            )}
          </div>
          <div className="w-28 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-300"
              style={{ width: `${(filledCount / 16) * 100}%` }}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={() => onChange(defaultStructured())}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <RotateCcw className="w-3 h-3" />
          Reset assessment
        </button>
      </div>

      {/* ── Quick presets ── */}
      <div className="rounded-xl border border-border bg-card p-4">
        <p className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5 mb-3">
          <Zap className="w-3 h-3" />
          Quick presets — populate all metrics, then adjust as needed
        </p>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => applyPreset(p)}
              title={p.description}
              className={`text-xs px-3.5 h-8 rounded-full border font-medium transition-colors bg-card ${p.color}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Category cards ── */}
      {grouped.map(({ cat, items }) => {
        const Icon = CATEGORY_ICON[cat];
        const catScored = items.filter((m) => values[m.key] > 0).length;

        return (
          <div key={cat} className="rounded-xl border border-border bg-card overflow-hidden">
            {/* Category header */}
            <div className="px-5 py-3.5 border-b border-border bg-surface-2/40 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-md bg-primary/10 text-primary flex items-center justify-center shrink-0">
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">{cat}</h3>
                  <p className="text-[11px] text-muted-foreground leading-snug">
                    {CATEGORY_DESCRIPTION[cat]}
                  </p>
                </div>
              </div>
              <span className="text-[11px] font-medium text-muted-foreground tabular-nums shrink-0">
                {catScored}/{items.length}
              </span>
            </div>

            {/* Metric rows */}
            <div className="divide-y divide-border">
              {items.map((m) => {
                const val = values[m.key];
                const descriptor = DESCRIPTORS[m.key][val];

                return (
                  <div key={m.key} className="px-5 py-4">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:gap-6">
                      {/* Label + current descriptor */}
                      <div className="sm:w-52 shrink-0 mb-3 sm:mb-0">
                        <p className="text-sm font-medium text-foreground">{m.label}</p>
                        <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">
                          {descriptor}
                        </p>
                      </div>

                      {/* Severity selector — pill radio group */}
                      <div
                        role="radiogroup"
                        aria-label={m.label}
                        className="flex gap-1.5 flex-1"
                      >
                        {([0, 1, 2, 3] as Severity[]).map((s) => {
                          const isActive = val === s;
                          return (
                            <button
                              key={s}
                              type="button"
                              role="radio"
                              aria-checked={isActive}
                              onClick={() => setOne(m.key, s)}
                              className={[
                                "flex-1 h-9 rounded-lg border text-xs transition-all",
                                "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                isActive
                                  ? PILL_ACTIVE[s]
                                  : "border-border bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted font-medium",
                              ].join(" ")}
                            >
                              {SEV_LABELS[s]}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
