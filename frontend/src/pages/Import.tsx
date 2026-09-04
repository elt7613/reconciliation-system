import { useRef, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { loadSampleData, uploadImports, type Batch } from "../api/ingestion";

const WARNING_LABELS: Record<string, string> = {
  duplicate_order_row: "Exact duplicate order row (kept one, dropped the copy)",
  normalized_order_reference: "Dirty order reference in payment (normalized for matching)",
  missing_processed_at: "Payment is missing its processed-at timestamp",
  missing_order_id: "Row without an order id (dropped)",
  conflicting_duplicate_order: "Same order id with different values (first row kept)",
  duplicate_transaction_row: "Duplicate transaction row (dropped)",
  missing_transaction_ref: "Row without a transaction ref (dropped)",
  unparseable_date: "Unparseable date in payment",
};

export default function ImportPage() {
  const navigate = useNavigate();
  const [ordersFile, setOrdersFile] = useState<File | null>(null);
  const [paymentsFile, setPaymentsFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<"upload" | "sample" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Batch | null>(null);
  const ordersInput = useRef<HTMLInputElement>(null);
  const paymentsInput = useRef<HTMLInputElement>(null);

  const pick = (which: "orders" | "payments") => (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    which === "orders" ? setOrdersFile(f) : setPaymentsFile(f);
  };

  const onUpload = async () => {
    if (!ordersFile || !paymentsFile) return;
    setBusy("upload");
    setError(null);
    try {
      const data = await uploadImports(ordersFile, paymentsFile);
      setResult(data.batch);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Upload failed. Check the file format and try again.");
    } finally {
      setBusy(null);
    }
  };

  const onSample = async () => {
    setBusy("sample");
    setError(null);
    try {
      const data = await loadSampleData();
      setResult(data.batch);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not load sample data.");
    } finally {
      setBusy(null);
    }
  };

  const goDashboard = () => navigate("/");

  const warningsByCode = (result?.warnings ?? []).reduce<Record<string, number>>((acc, w) => {
    acc[w.code] = (acc[w.code] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Layout title="Import data">
      <div className="max-w-2xl space-y-6">
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <p className="text-sm text-slate-600">
            Upload the order-system export (<code className="text-xs">orders.csv</code>) and the
            payment-processor export (<code className="text-xs">payments.csv</code>). The
            reconciliation runs automatically after import.
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Orders CSV</label>
              <input
                ref={ordersInput}
                type="file"
                accept=".csv"
                onChange={pick("orders")}
                className="hidden"
                id="orders-input"
              />
              <button
                onClick={() => ordersInput.current?.click()}
                className={`w-full rounded-lg border px-3 py-6 text-sm ${
                  ordersFile
                    ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                    : "border-dashed border-slate-300 text-slate-500 hover:border-indigo-400"
                }`}
              >
                {ordersFile ? `✓ ${ordersFile.name}` : "Choose orders.csv"}
              </button>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Payments CSV</label>
              <input
                ref={paymentsInput}
                type="file"
                accept=".csv"
                onChange={pick("payments")}
                className="hidden"
                id="payments-input"
              />
              <button
                onClick={() => paymentsInput.current?.click()}
                className={`w-full rounded-lg border px-3 py-6 text-sm ${
                  paymentsFile
                    ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                    : "border-dashed border-slate-300 text-slate-500 hover:border-indigo-400"
                }`}
              >
                {paymentsFile ? `✓ ${paymentsFile.name}` : "Choose payments.csv"}
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onUpload}
              disabled={!ordersFile || !paymentsFile || busy !== null}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {busy === "upload" ? "Importing & reconciling…" : "Upload and reconcile"}
            </button>
            <span className="text-xs text-slate-400">or</span>
            <button
              onClick={onSample}
              disabled={busy !== null}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60"
            >
              {busy === "sample" ? "Loading…" : "Load sample data"}
            </button>
          </div>
          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
        </div>

        {result && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="font-semibold text-slate-900">Import complete</h2>
                <p className="text-sm text-slate-500">
                  {result.order_row_count} orders · {result.payment_row_count} payments ·
                  reconciliation finished
                </p>
              </div>
              <button
                onClick={goDashboard}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                Go to dashboard →
              </button>
            </div>
            {Object.keys(warningsByCode).length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-slate-700 mb-2">
                  Data-quality notes from ingestion
                </h3>
                <ul className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg divide-y divide-amber-100">
                  {Object.entries(warningsByCode).map(([code, n]) => (
                    <li key={code} className="px-3 py-2">
                      {WARNING_LABELS[code] ?? code}
                      {n > 1 && <span className="text-amber-600"> ×{n}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}
