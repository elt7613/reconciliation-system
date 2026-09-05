import { useEffect, useState } from "react";
import {
  explainDiscrepancy,
  getDiscrepancy,
  type Discrepancy,
  type ExplanationPayload,
} from "../api/reconciliation";
import { TYPE_LABELS } from "./HeadlineCards";

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 border-b border-slate-100 text-sm">
      <span className="text-slate-400">{k}</span>
      <span className="text-slate-800 font-medium text-right">{v ?? "—"}</span>
    </div>
  );
}

export default function DetailDrawer({
  discrepancy,
  onClose,
}: {
  discrepancy: Discrepancy;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<Discrepancy | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<ExplanationPayload | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setDetailError(null);
    getDiscrepancy(discrepancy.id)
      .then((d) => !cancelled && setDetail(d))
      .catch(() => !cancelled && setDetailError("Could not load the raw records."));
    return () => {
      cancelled = true;
    };
  }, [discrepancy.id]);

  useEffect(() => {
    if (detail?.explanation) setExplanation(detail.explanation);
    else setExplanation(null);
  }, [detail]);

  const onExplain = async () => {
    setExplaining(true);
    setExplainError(null);
    setElapsed(0);
    const startedAt = Date.now();
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - startedAt) / 1000)), 1000);
    try {
      const data = await explainDiscrepancy(discrepancy.id);
      setExplanation(data);
    } catch {
      setExplainError("The AI explanation failed. You can retry or work from the raw facts below.");
    } finally {
      clearInterval(timer);
      setExplaining(false);
    }
  };

  const order = detail?.order ?? null;
  const payments = detail?.payments ?? [];

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <div className="relative w-full max-w-xl bg-white h-full overflow-y-auto shadow-2xl">
        <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-start justify-between">
          <div>
            <h2 className="font-semibold text-slate-900">
              {TYPE_LABELS[discrepancy.type] ?? discrepancy.type}
            </h2>
            <p className="text-sm text-slate-500">
              {discrepancy.order_ref} · severity {discrepancy.severity} ·{" "}
              {Number(discrepancy.amount_at_risk).toFixed(2)} at risk
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl leading-none">
            ×
          </button>
        </div>

        <div className="px-6 py-4 space-y-6">
          {/* Engine facts */}
          <section>
            <h3 className="text-xs uppercase tracking-wide text-slate-400 mb-2">
              What the engine found
            </h3>
            <div className="rounded-xl border border-slate-200 p-4">
              {Object.entries(discrepancy.detail).map(([k, v]) => (
                <KV key={k} k={k.replace(/_/g, " ")} v={String(v)} />
              ))}
              {Object.keys(discrepancy.detail).length === 0 && (
                <p className="text-sm text-slate-400">No extra facts recorded.</p>
              )}
            </div>
          </section>

          {/* Raw records */}
          <section>
            <h3 className="text-xs uppercase tracking-wide text-slate-400 mb-2">Raw records</h3>
            {detailError && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {detailError}
              </div>
            )}
            {!detailError && !detail && (
              <p className="text-sm text-slate-400">Loading raw records…</p>
            )}
            {order && (
              <div className="rounded-xl border border-slate-200 p-4 mb-3">
                <h4 className="text-sm font-semibold text-slate-700 mb-1">Order (order system)</h4>
                <KV k="order id" v={order.order_id} />
                <KV k="date" v={order.order_date?.slice(0, 16).replace("T", " ")} />
                <KV k="email" v={order.customer_email} />
                <KV k="status" v={order.status} />
                <KV k="gross / discount / net" v={`${order.gross_amount} / ${order.discount} / ${order.net_amount} ${order.currency}`} />
              </div>
            )}
            {order === null && detail && (
              <div className="rounded-xl border border-slate-200 p-4 mb-3 bg-slate-50">
                <h4 className="text-sm font-semibold text-slate-700 mb-1">Order</h4>
                <p className="text-sm text-slate-500">
                  No order exists with this reference — the charge is orphaned.
                </p>
              </div>
            )}
            {payments.map((p) => (
              <div key={p.transaction_ref} className="rounded-xl border border-slate-200 p-4 mb-3">
                <h4 className="text-sm font-semibold text-slate-700 mb-1">
                  Payment {p.transaction_ref} ({p.type}, {p.status})
                </h4>
                <KV k="processed at" v={p.processed_at?.slice(0, 16).replace("T", " ")} />
                <KV k="amount" v={`${p.amount} ${p.currency}`} />
                <KV k="fee / net settled" v={`${p.fee} / ${p.net_settled}`} />
              </div>
            ))}
          </section>

          {/* AI explanation */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs uppercase tracking-wide text-slate-400">AI explanation</h3>
              <button
                onClick={onExplain}
                disabled={explaining}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                {explaining ? "Asking the model…" : explanation ? "Re-explain" : "Explain with AI"}
              </button>
            </div>

            {explaining && (
              <div className="space-y-2">
                <div className="rounded-xl border border-slate-200 p-4 animate-pulse space-y-2">
                  <div className="h-3 bg-slate-200 rounded w-3/4" />
                  <div className="h-3 bg-slate-200 rounded w-1/2" />
                  <div className="h-3 bg-slate-200 rounded w-2/3" />
                </div>
                <p className="text-xs text-slate-400 text-center">
                  Asking the model… usually 5–20s ({elapsed}s)
                </p>
              </div>
            )}

            {explainError && !explaining && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 space-y-2">
                <p>{explainError}</p>
                <button onClick={onExplain} className="text-red-800 underline font-medium">
                  Retry
                </button>
              </div>
            )}

            {explanation && !explaining && (
              <div
                className={`rounded-xl border p-4 space-y-3 ${
                  explanation.degraded
                    ? "border-amber-200 bg-amber-50"
                    : "border-indigo-200 bg-indigo-50/50"
                }`}
              >
                {explanation.degraded && (
                  <p className="text-xs font-medium text-amber-700">
                    AI is unavailable — showing the deterministic fallback.
                  </p>
                )}
                <div>
                  <div className="text-xs font-semibold text-slate-500 uppercase">Summary</div>
                  <p className="text-sm text-slate-800">{explanation.summary}</p>
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-500 uppercase">Likely cause</div>
                  <p className="text-sm text-slate-800">{explanation.likely_cause}</p>
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-500 uppercase">
                    Recommended action
                  </div>
                  <p className="text-sm text-slate-800">{explanation.recommended_action}</p>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-xs font-semibold text-slate-500 uppercase">Urgency</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      explanation.urgency === "high"
                        ? "bg-red-100 text-red-800"
                        : explanation.urgency === "medium"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-indigo-100 text-indigo-800"
                    }`}
                  >
                    {explanation.urgency}
                  </span>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
