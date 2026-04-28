import { Severity, SEVERITY_LABELS } from "@/lib/ehrApi";

interface SeverityPickerProps {
  label: string;
  value: Severity;
  onChange: (v: Severity) => void;
}

const SEV: Severity[] = [0, 1, 2, 3];

export function SeverityPicker({ label, value, onChange }: SeverityPickerProps) {
  return (
    <div className="group">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[13px] font-medium text-foreground">{label}</span>
        <span
          className={[
            "text-[11px] font-medium px-1.5 py-0.5 rounded-md tabular-nums",
            value === 0 ? "text-muted-foreground bg-muted" : `sev-bg-${value}`,
          ].join(" ")}
        >
          {SEVERITY_LABELS[value]}
        </span>
      </div>
      <div
        role="radiogroup"
        aria-label={label}
        className="grid grid-cols-4 gap-1 p-1 bg-surface-2 border border-border rounded-lg"
      >
        {SEV.map((s) => {
          const active = value === s;
          return (
            <button
              key={s}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(s)}
              className={[
                "h-9 rounded-md text-sm font-semibold tabular-nums transition-all",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? `sev-bg-${s} shadow-xs`
                  : "text-muted-foreground hover:text-foreground hover:bg-surface",
              ].join(" ")}
            >
              {s}
            </button>
          );
        })}
      </div>
    </div>
  );
}
