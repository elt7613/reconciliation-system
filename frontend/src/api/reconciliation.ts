import api from "./client";

export interface RunSummary {
  id: number;
  created_at: string;
  batch: number;
  total_orders: number;
  total_payments: number;
  matched_pairs: number;
  value_reconciled: string;
  value_in_dispute: string;
  money_at_risk: string;
  uncollected_revenue: string;
  refund_obligations: string;
  needs_investigation: string;
  breakdown: Record<string, { count: number; amount: string; severity: string }>;
}

export interface Discrepancy {
  id: number;
  type: string;
  severity: "high" | "medium" | "low" | "info";
  risk_bucket: string;
  order_ref: string;
  transaction_refs: string[];
  amount_at_risk: string;
  detail: Record<string, unknown>;
  explanation?: ExplanationPayload | null;
  order?: OrderRecord | null;
  payments?: PaymentRecord[];
}

export interface ExplanationPayload {
  summary: string;
  likely_cause: string;
  recommended_action: string;
  urgency: "low" | "medium" | "high";
  degraded?: boolean;
}

export interface OrderRecord {
  order_id: string;
  order_date: string;
  customer_email: string | null;
  currency: string;
  gross_amount: string;
  discount: string;
  net_amount: string;
  status: string;
}

export interface PaymentRecord {
  transaction_ref: string;
  processed_at: string | null;
  currency: string;
  amount: string;
  fee: string;
  net_settled: string;
  type: string;
  status: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface RunSummaryPayload {
  executive_summary: string;
  top_priorities: string[];
  recommended_actions: string[];
  degraded?: boolean;
}

export async function listRuns() {
  const { data } = await api.get("/runs/");
  return data.results as RunSummary[];
}

export async function getRun(runId: number) {
  const { data } = await api.get(`/runs/${runId}/`);
  return data as RunSummary;
}

export async function rerunLatest() {
  const { data } = await api.post("/runs/");
  return data as RunSummary;
}

export interface DiscrepancyQuery {
  type?: string;
  severity?: string;
  search?: string;
  page?: number;
  ordering?: string;
}

export async function listDiscrepancies(runId: number, query: DiscrepancyQuery) {
  const { data } = await api.get(`/runs/${runId}/discrepancies/`, { params: query });
  return data as Paginated<Discrepancy>;
}

export async function getDiscrepancy(id: number) {
  const { data } = await api.get(`/discrepancies/${id}/`);
  return data as Discrepancy;
}

export async function explainDiscrepancy(id: number) {
  const { data } = await api.post(`/discrepancies/${id}/explain/`);
  return data as ExplanationPayload;
}

export async function summarizeRun(runId: number) {
  const { data } = await api.post(`/runs/${runId}/summarize/`);
  return data as RunSummaryPayload;
}
