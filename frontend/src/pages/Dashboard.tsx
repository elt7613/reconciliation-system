import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import { HeadlineCards, RiskBucketCards } from "../components/HeadlineCards";
import TypeChart from "../components/TypeChart";
import DiscrepancyTable from "../components/DiscrepancyTable";
import DetailDrawer from "../components/DetailDrawer";
import {
  listDiscrepancies,
  listRuns,
  rerunLatest,
  summarizeRun,
  getRun,
  type Discrepancy,
  type Paginated,
  type RunSummary,
  type RunSummaryPayload,
} from "../api/reconciliation";

export default function DashboardPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [run, setRun] = useState<RunSummary | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [runsLoading, setRunsLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);

  const [page, setPage] = useState<Paginated<Discrepancy> | null>(null);
  const [pageNum, setPageNum] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [tableLoading, setTableLoading] = useState(false);
  const [tableError, setTableError] = useState<string | null>(null);

  const [selected, setSelected] = useState<Discrepancy | null>(null);
  const [summary, setSummary] = useState<RunSummaryPayload | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // Load run list
  useEffect(() => {
    let cancelled = false;
    setRunsLoading(true);
    listRuns()
      .then((rs) => {
        if (cancelled) return;
        setRuns(rs);
        setRun(rs[0] ?? null);
      })
      .catch(() => !cancelled && setRunsError("Could not load your reconciliation runs."))
      .finally(() => !cancelled && setRunsLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  // Load discrepancies whenever run/filters change
  const loadTable = useCallback(async () => {
    if (!run) return;
    setTableLoading(true);
    setTableError(null);
    try {
      const data = await listDiscrepancies(run.id, {
        type: typeFilter || undefined,
        severity: severityFilter || undefined,
        search: search || undefined,
        page: pageNum,
      });
      setPage(data);
    } catch {
      setTableError("Could not load the discrepancy list.");
    } finally {
      setTableLoading(false);
    }
  }, [run, typeFilter, severityFilter, search, pageNum]);

  useEffect(() => {
    loadTable();
  }, [loadTable]);

  const onQueryChange = (q: { type?: string; severity?: string; page?: number }) => {
    if (q.type !== undefined) setTypeFilter(q.type);
    if (q.severity !== undefined) setSeverityFilter(q.severity);
    if (q.page !== undefined) setPageNum(q.page);
    if (q.type !== undefined || q.severity !== undefined) setPageNum(1);
  };

  const onRerun = async () => {
    setRerunning(true);
    try {
      const r = await rerunLatest();
      setRuns((rs) => [r, ...rs]);
      setRun(r);
    } catch {
      setRunsError("Re-run failed — do you have imported data?");
    } finally {
      setRerunning(false);
    }
  };

  const onSelectRun = async (runId: number) => {
    try {
      const r = await getRun(runId);
      setRun(r);
      setPageNum(1);
      setTypeFilter("");
      setSeverityFilter("");
      setSearch("");
      setSearchInput("");
      setSummary(null);
    } catch {
      setRunsError("Could not load that run.");
    }
  };

  const onSummarize = async () => {
    if (!run) return;
    setSummarizing(true);
    setSummaryError(null);
    try {
      const s = await summarizeRun(run.id);
      setSummary(s);
    } catch {
      setSummaryError("The AI summary failed. Retry, or read the deterministic numbers above.");
    } finally {
      setSummarizing(false);
    }
  };

  if (runsLoading) {
    return (
      <Layout title="Dashboard">
        <p className="text-slate-400 text-sm">Loading your runs…</p>
      </Layout>
    );
  }

  if (runsError && runs.length === 0) {
    return (
      <Layout title="Dashboard">
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <p className="text-red-700 text-sm mb-4">{runsError}</p>
          <button onClick={() => window.location.reload()} className="text-indigo-600 underline text-sm">
            Retry
          </button>
        </div>
      </Layout>
    );
  }

  if (!run) {
    return (
      <Layout title="Dashboard">
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center space-y-4">
          <p className="text-slate-500">No data yet — import the two CSVs to see the dashboard.</p>
          <Link
            to="/import"
            className="inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Import data →
          </Link>
        </div>
      </Layout>
    );
  }

  return (
    <Layout
      title="Dashboard"
      actions={
        <div className="flex items-center gap-2">
          <select
            value={run.id}
            onChange={(e) => onSelectRun(Number(e.target.value))}
            className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm"
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                Run #{r.id} — {new Date(r.created_at).toLocaleString()}
              </option>
            ))}
          </select>
          <button
            onClick={onRerun}
            disabled={rerunning}
            title="Re-run reconciliation on the latest imported batch — the result must be identical (determinism check)"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-60"
          >
            {rerunning ? "Re-running…" : "Re-run"}
          </button>
        </div>
      }
    >
      <div className="space-y-6">
        <HeadlineCards run={run} />
        <RiskBucketCards run={run} />

        <TypeChart
          run={run}
          selectedType={typeFilter || null}
          onSelectType={(t) => {
            setTypeFilter(t ?? "");
            setPageNum(1);
          }}
        />

        {/* AI summary */}
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-900">AI executive summary</h2>
            <button
              onClick={onSummarize}
              disabled={summarizing}
              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {summarizing ? "Summarizing…" : summary ? "Re-summarize" : "Summarize with AI"}
            </button>
          </div>
          {summarizing && (
            <div className="animate-pulse space-y-2">
              <div className="h-3 bg-slate-200 rounded w-5/6" />
              <div className="h-3 bg-slate-200 rounded w-2/3" />
              <div className="h-3 bg-slate-200 rounded w-3/4" />
            </div>
          )}
          {summaryError && !summarizing && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 space-y-2">
              <p>{summaryError}</p>
              <button onClick={onSummarize} className="text-red-800 underline font-medium">
                Retry
              </button>
            </div>
          )}
          {summary && !summarizing && (
            <div
              className={`rounded-lg border p-4 space-y-3 ${
                summary.degraded ? "border-amber-200 bg-amber-50" : "border-indigo-200 bg-indigo-50/50"
              }`}
            >
              {summary.degraded && (
                <p className="text-xs font-medium text-amber-700">
                  AI unavailable — deterministic fallback shown.
                </p>
              )}
              <p className="text-sm text-slate-800">{summary.executive_summary}</p>
              {summary.top_priorities.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-500 uppercase mb-1">
                    Look at first
                  </div>
                  <ol className="list-decimal list-inside text-sm text-slate-800 space-y-0.5">
                    {summary.top_priorities.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ol>
                </div>
              )}
              {summary.recommended_actions.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-500 uppercase mb-1">
                    Recommended actions
                  </div>
                  <ul className="list-disc list-inside text-sm text-slate-800 space-y-0.5">
                    {summary.recommended_actions.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <DiscrepancyTable
          page={page}
          pageNum={pageNum}
          loading={tableLoading}
          error={tableError}
          typeFilter={typeFilter}
          severityFilter={severityFilter}
          searchInput={searchInput}
          onSearchInput={setSearchInput}
          onSearchSubmit={() => {
            setSearch(searchInput);
            setPageNum(1);
          }}
          onQueryChange={onQueryChange}
          onOpen={setSelected}
          onRetry={loadTable}
        />
      </div>

      {selected && (
        <DetailDrawer discrepancy={selected} onClose={() => setSelected(null)} />
      )}
    </Layout>
  );
}
