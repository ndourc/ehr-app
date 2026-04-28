import {
  CATEGORY_ORDER,
  METRICS,
  StructuredMetrics,
  Severity,
  MetricCategory,
} from "@/lib/ehrApi";
import { SeverityPicker } from "./SeverityPicker";
import {
  Brain,
  Activity,
  HeartPulse,
  Lightbulb,
  Users,
  type LucideIcon,
} from "lucide-react";

interface MetricsMatrixProps {
  values: StructuredMetrics;
  onChange: (next: StructuredMetrics) => void;
}

const CATEGORY_ICON: Record<MetricCategory, LucideIcon> = {
  "Psychological State": Brain,
  "Behavioural Patterns": Activity,
  "Coping & Stress": HeartPulse,
  "Cognitive Function": Lightbulb,
  "Social Context": Users,
};

export function MetricsMatrix({ values, onChange }: MetricsMatrixProps) {
  const setOne = (key: keyof StructuredMetrics, v: Severity) => {
    onChange({ ...values, [key]: v });
  };

  const grouped = CATEGORY_ORDER.map((cat) => ({
    cat,
    items: METRICS.filter((m) => m.category === cat),
  }));

  return (
    <div className="space-y-6">
      {grouped.map(({ cat, items }) => {
        const Icon = CATEGORY_ICON[cat];
        const elevated = items.filter((m) => values[m.key] > 0).length;
        return (
          <section key={cat}>
            <header className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-md bg-primary-soft text-primary flex items-center justify-center">
                  <Icon className="w-4 h-4" strokeWidth={2.25} />
                </span>
                <h3 className="text-sm font-semibold text-foreground">{cat}</h3>
              </div>
              <span className="text-[11px] font-medium text-muted-foreground tabular-nums">
                {elevated}/{items.length} elevated
              </span>
            </header>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-4">
              {items.map((m) => (
                <SeverityPicker
                  key={m.key}
                  label={m.label}
                  value={values[m.key]}
                  onChange={(v) => setOne(m.key, v)}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
