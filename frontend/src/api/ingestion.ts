import api from "./client";

export interface ImportWarning {
  code: string;
  [key: string]: unknown;
}

export interface Batch {
  id: number;
  created_at: string;
  orders_file_name: string;
  payments_file_name: string;
  order_row_count: number;
  payment_row_count: number;
  warnings: ImportWarning[];
  run_id: number | null;
}

export async function uploadImports(ordersFile: File, paymentsFile: File) {
  const form = new FormData();
  form.append("orders_file", ordersFile);
  form.append("payments_file", paymentsFile);
  const { data } = await api.post("/imports/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data as { batch: Batch; run_id: number };
}

export async function loadSampleData() {
  const { data } = await api.post("/imports/sample/");
  return data as { batch: Batch; run_id: number };
}
