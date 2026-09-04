import type { Discrepancy, Paginated } from "../api/reconciliation";
import { TYPE_LABELS } from "./HeadlineCards";

const SEVERITY_STYLES: Record<string, string> = {
  high: "bg-red-100 text-red-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-indigo-100 text-indigo-800",
  info: "bg-slate-100 text-slate-600",
};

export default function DiscrepancyTable({
  page,
  pageNum,
  loading,
  error,
  typeFilter,
  severityFilter,
  searchInput,
  onSearchInput,
  onSearchSubmit,
  onQueryChange,
  onOpen,
  onRetry,
}: {
  page: Paginated<Discrepancy> | null;
  pageNum: number;
  loading: boolean;
  error: string | null;
  typeFilter: string;
  severityFilter: string;
  searchInput: string;
  onSearchInput: (v: string) => void;
  onSearchSubmit: () => void;
  onQueryChange: (q: { type?: string; severity?: string; page?: number }) => void;
  onOpen: (d: Discrepancy) => void;
  onRetry: () => void;
}) {
  const types = Object.keys(TYPE_LABELS);
  const totalPages = page ? Math.ceil(page.count / 25) : 0;

  return (
    <div className="bg-white rounded-xl border border-slate-200">
      <div className="flex flex-wrap items-center gap-2 p-4 border-b border-slate-200">
        <select
          value={typeFilter}
          onChange={(e) => onQueryChange({ type: e.target.value, page: 1 })}
          className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm text-slate-700"
        >
          <option value="">All types</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {TYPE_LABELS[t]}
            </option>
          ))}
        </select>
        <select
          value={severityFilter}
          onChange={(e) => onQueryChange({ severity: e.target.value, page: 1 })}
          className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm text-slate-700"
        >
          <option value="">All severities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
          <option value="info">Info</option>
        </select>
        <form
          className="flex-1 min-w-48"
          onSubmit={(e) => {
            e.preventDefault();
            onSearchSubmit();
          }}
        >
          <input
            value={searchInput}
            onChange={(e) => onSearchInput(e.target.value)}
            placeholder="Search order or transaction ref…"
            className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </form>
        {(typeFilter || severityFilter || searchInput) && (
          <button
            onClick={() => onQueryChange({ type: "", severity: "", page: 1 })}
            className="text-sm text-indigo-600 hover:underline"
          >
            Clear
          </button>
        )}
      </div>

      {error && (
        <div className="m-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={onRetry} className="text-red-800 underline font-medium">
            Retry
          </button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-400 border-b border-slate-200">
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 font-medium">Severity</th>
              <th className="px-4 py-2 font-medium">Order</th>
              <th className="px-4 py-2 font-medium">Transactions</th>
              <th className="px-4 py-2 font-medium text-right">At risk</th>
              <th className="px-4 py-2 font-medium">Risk bucket</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && !error && page?.results.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                  No discrepancies match the current filters.
                </td>
              </tr>
            )}
            {!loading &&
              page?.results.map((d) => (
                <tr
                  key={d.id}
                  className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer"
                  onClick={() => onOpen(d)}
                >
                  <td className="px-4 py-2.5 font-medium text-slate-800">
                    {TYPE_LABELS[d.type] ?? d.type}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_STYLES[d.severity]}`}
                    >
                      {d.severity}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{d.order_ref}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500">
                    {d.transaction_refs.length > 0 ? d.transaction_refs.join(", ") : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-800">
                    {Number(d.amount_at_risk).toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">
                    {d.risk_bucket ? d.risk_bucket.replace(/_/g, " ") : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button className="text-indigo-600 text-xs font-medium hover:underline">
                      Details →
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between p-4 text-sm text-slate-500">
          <span>
            Page {pageNum} of {totalPages} — {page?.count} findings
          </span>
          <div className="flex gap-2">
            <button
              disabled={pageNum <= 1}
              onClick={() => onQueryChange({ page: pageNum - 1 })}
              className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40"
            >
              ← Prev
            </button>
            <button
              disabled={pageNum >= totalPages}
              onClick={() => onQueryChange({ page: pageNum + 1 })}
              className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>
      )}
      {totalPages === 1 && page && (
        <div className="p-4 text-sm text-slate-500">{page.count} findings</div>
      )}
    </div>
  );
}
