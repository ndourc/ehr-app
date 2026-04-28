import { useEffect, useState } from "react";
import { api, RecordEntry } from "@/lib/ehrApi";
import { ChevronLeft, ChevronRight, FileClock, Loader2 } from "lucide-react";

export function AuditLog() {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [items, setItems] = useState<RecordEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .records(page, pageSize)
      .then((r) => {
        if (cancelled) return;
        setItems(r.items ?? []);
        setTotal(r.total ?? 0);
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="clinical-card-elevated overflow-hidden">
      <header className="px-5 py-3.5 border-b border-border flex items-center justify-between bg-surface">
        <div className="flex items-center gap-2">
          <FileClock className="w-4 h-4 text-primary" strokeWidth={2.25} />
          <h2 className="text-sm font-semibold text-foreground">Audit log</h2>
        </div>
        <span className="text-[11px] font-medium text-muted-foreground tabular-nums">
          {total} record{total === 1 ? "" : "s"}
        </span>
      </header>

      {error ? (
        <div className="m-5 p-3 rounded-lg border border-distress/30 bg-distress-soft text-sm text-foreground">
          {error}
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-2 text-left">
              <Th>#</Th>
              <Th>Timestamp</Th>
              <Th>Patient</Th>
              <Th>Prediction</Th>
              <Th className="text-right">Confidence</Th>
              <Th>Top token</Th>
            </tr>
          </thead>
          <tbody>
            {loading && items.length === 0 ? (
              <tr>
                <Td colSpan={6} className="py-10 text-center text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
                  Loading records…
                </Td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <Td colSpan={6} className="py-10 text-center text-muted-foreground">
                  No records yet.
                </Td>
              </tr>
            ) : (
              items.map((r, i) => {
                const top = (r.important_tokens ?? [])
                  .slice()
                  .sort((a, b) => b.weight - a.weight)[0];
                const isDistress = r.prediction === "Distress";
                return (
                  <tr
                    key={`${r.patient_id}-${r.timestamp}-${i}`}
                    className="border-t border-border hover:bg-surface-2/60 transition-colors"
                  >
                    <Td className="text-muted-foreground tabular-nums">
                      {(page - 1) * pageSize + i + 1}
                    </Td>
                    <Td className="text-muted-foreground tabular-nums whitespace-nowrap">
                      {r.timestamp}
                    </Td>
                    <Td className="font-medium text-foreground">{r.patient_id}</Td>
                    <Td>
                      <span
                        className={[
                          "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium",
                          isDistress
                            ? "bg-distress-soft text-distress"
                            : "bg-stable-soft text-stable",
                        ].join(" ")}
                      >
                        <span
                          className={[
                            "w-1.5 h-1.5 rounded-full",
                            isDistress ? "bg-distress" : "bg-stable",
                          ].join(" ")}
                        />
                        {r.prediction}
                      </span>
                    </Td>
                    <Td className="text-right tabular-nums font-num">
                      {Math.round((r.confidence_score ?? 0) * 100)}%
                    </Td>
                    <Td className="text-foreground">
                      {top ? (
                        <span>
                          {top.word}{" "}
                          <span className="text-muted-foreground tabular-nums">
                            ({top.weight.toFixed(2)})
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </Td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <footer className="border-t border-border px-5 py-3 flex items-center justify-between bg-surface">
        <span className="text-xs text-muted-foreground tabular-nums">
          Page {page} of {totalPages}
        </span>
        <div className="flex gap-2">
          <PagerBtn disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            <ChevronLeft className="w-3.5 h-3.5" /> Prev
          </PagerBtn>
          <PagerBtn
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next <ChevronRight className="w-3.5 h-3.5" />
          </PagerBtn>
        </div>
      </footer>
    </div>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      className={`text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground px-4 py-2.5 ${className}`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  className = "",
  colSpan,
}: {
  children: React.ReactNode;
  className?: string;
  colSpan?: number;
}) {
  return (
    <td colSpan={colSpan} className={`px-4 py-3 align-middle ${className}`}>
      {children}
    </td>
  );
}

function PagerBtn({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium border border-border bg-card text-foreground hover:bg-surface-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
    >
      {children}
    </button>
  );
}
