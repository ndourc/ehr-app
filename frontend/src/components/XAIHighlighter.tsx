import { ImportantToken } from "@/lib/ehrApi";
import { useMemo } from "react";

interface XAIHighlighterProps {
  text: string;
  tokens: ImportantToken[];
}

export function XAIHighlighter({ text, tokens }: XAIHighlighterProps) {
  const segments = useMemo(() => splitWithHighlights(text, tokens), [text, tokens]);

  if (!text) {
    return (
      <div className="text-sm text-muted-foreground italic">
        No clinical text provided.
      </div>
    );
  }

  return (
    <div className="text-[15px] leading-7 text-foreground whitespace-pre-wrap break-words">
      {segments.map((seg, i) =>
        seg.weight != null ? (
          <span
            key={i}
            title={`attention weight ${seg.weight.toFixed(2)}`}
            className="px-1 py-0.5 rounded-md font-medium ring-1 ring-inset transition-colors"
            style={{
              backgroundColor: weightToBg(seg.weight),
              color: weightToFg(seg.weight),
              // @ts-expect-error css var
              "--tw-ring-color": weightToRing(seg.weight),
            }}
          >
            {seg.text}
          </span>
        ) : (
          <span key={i}>{seg.text}</span>
        )
      )}
    </div>
  );
}

function weightToBg(w: number): string {
  if (w >= 0.8) return "hsl(var(--sev-3))";
  if (w >= 0.6) return "hsl(var(--sev-2))";
  if (w >= 0.4) return "hsl(var(--sev-1))";
  return "hsl(var(--primary-soft))";
}
function weightToFg(w: number): string {
  if (w >= 0.8) return "hsl(var(--sev-3-fg))";
  if (w >= 0.6) return "hsl(var(--sev-2-fg))";
  if (w >= 0.4) return "hsl(var(--sev-1-fg))";
  return "hsl(var(--accent-foreground))";
}
function weightToRing(w: number): string {
  if (w >= 0.8) return "hsl(var(--distress) / 0.25)";
  if (w >= 0.6) return "hsl(27 96% 50% / 0.25)";
  if (w >= 0.4) return "hsl(48 96% 50% / 0.3)";
  return "hsl(var(--primary) / 0.2)";
}

interface Segment {
  text: string;
  weight?: number;
}

function splitWithHighlights(text: string, tokens: ImportantToken[]): Segment[] {
  if (!tokens?.length) return [{ text }];

  const variants = tokens
    .flatMap((t) => {
      const w = t.word;
      const set = new Set<string>([w, w.replace(/_/g, " "), w.replace(/_/g, "-")]);
      return Array.from(set).map((v) => ({ pattern: v, weight: t.weight }));
    })
    .sort((a, b) => b.pattern.length - a.pattern.length);

  type Hit = { start: number; end: number; weight: number };
  const lower = text.toLowerCase();
  const hits: Hit[] = [];
  for (const { pattern, weight } of variants) {
    const p = pattern.toLowerCase();
    if (!p) continue;
    let idx = 0;
    while ((idx = lower.indexOf(p, idx)) !== -1) {
      const end = idx + p.length;
      const overlaps = hits.some((h) => !(end <= h.start || idx >= h.end));
      if (!overlaps) hits.push({ start: idx, end, weight });
      idx = end;
    }
  }
  hits.sort((a, b) => a.start - b.start);

  const out: Segment[] = [];
  let cursor = 0;
  for (const h of hits) {
    if (h.start > cursor) out.push({ text: text.slice(cursor, h.start) });
    out.push({ text: text.slice(h.start, h.end), weight: h.weight });
    cursor = h.end;
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor) });
  return out;
}
