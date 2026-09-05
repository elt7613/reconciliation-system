import type { RunSummary } from "../api/reconciliation";

export const TYPE_LABELS: Record<string, string> = {
  missing_payment: "Missing payment",
  orphan_charge: "Orphan charge",
  orphan_refund: "Orphan refund",
  duplicate_charge: "Duplicate charge",
  amount_mismatch: "Amount mismatch",
  charged_after_cancellation: "Charged after cancellation",
  failed_payment: "Failed payment",
  pending_payment: "Pending payment",
  partial_refund: "Partial refund",
  refund_of_completed_order: "Refund of completed order",
  currency_mismatch: "Currency mismatch",
  late_settlement: "Late settlement",
  rounding_variance: "Rounding variance",
  data_quality: "Data quality",
};

const fmt = (v: string | number) =>
  typeof v === "number"
    ? v.toLocaleString()
    : Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function HeadlineCards({ run }: { run: RunSummary | null }) {
  if (!run) return null;

  const cards = [
    { label: "Total orders", value: run.total_orders.toLocaleString(), hint: "after dedup" },
    { label: "Total payments", value: run.total_payments.toLocaleString(), hint: "processor rows" },
    { label: "Matched pairs", value: run.matched_pairs.toLocaleString(), hint: "clean 1:1 matches" },
    { label: "Value reconciled", value: fmt(run.value_reconciled), hint: "clean money" },
    { label: "Value in dispute", value: fmt(run.value_in_dispute), hint: "material findings", danger: true },
    { label: "Money at risk", value: fmt(run.money_at_risk), hint: "uncollected + refunds owed", danger: true },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((c) => (
        <div
          key={c.label}
          className={`rounded-xl border p-4 bg-white ${
            c.danger ? "border-red-200" : "border-slate-200"
          }`}
        >
          <div className="text-xs uppercase tracking-wide text-slate-400">{c.label}</div>
          <div
            className={`mt-1 text-xl font-semibold tabular-nums ${
              c.danger ? "text-red-700" : "text-slate-900"
            }`}
          >
            {c.value}
          </div>
          <div className="text-xs text-slate-400 mt-0.5">{c.hint}</div>
        </div>
      ))}
    </div>
  );
}

export function RiskBucketCards({ run }: { run: RunSummary | null }) {
  if (!run) return null;
  const buckets = [
    {
      label: "Uncollected revenue",
      amount: run.uncollected_revenue,
      hint: "Orders believed sold but money never (fully) received",
      tone: "text-amber-700 border-amber-200",
    },
    {
      label: "Refund obligations",
      amount: run.refund_obligations,
      hint: "Money held that should go back to customers",
      tone: "text-orange-700 border-orange-200",
    },
    {
      label: "Needs investigation",
      amount: run.needs_investigation,
      hint: "Unexplainable from these two files alone",
      tone: "text-indigo-700 border-indigo-200",
    },
  ];
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {buckets.map((b) => (
        <div key={b.label} className={`rounded-xl border bg-white p-4 ${b.tone.split(" ")[1]}`}>
          <div className="text-xs uppercase tracking-wide text-slate-400">{b.label}</div>
          <div className={`mt-1 text-lg font-semibold tabular-nums ${b.tone.split(" ")[0]}`}>
            {fmt(b.amount)}
          </div>
          <div className="text-xs text-slate-400 mt-0.5">{b.hint}</div>
        </div>
      ))}
    </div>
  );
}
