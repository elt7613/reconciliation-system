import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RunSummary } from "../api/reconciliation";
import { TYPE_LABELS } from "./HeadlineCards";

const SEVERITY_COLORS: Record<string, string> = {
  high: "#dc2626",
  medium: "#f59e0b",
  low: "#6366f1",
  info: "#94a3b8",
};

export default function TypeChart({
  run,
  onSelectType,
  selectedType,
}: {
  run: RunSummary | null;
  onSelectType: (type: string | null) => void;
  selectedType: string | null;
}) {
  if (!run) return null;
  const data = Object.entries(run.breakdown)
    .map(([type, v]) => ({
      type,
      label: TYPE_LABELS[type] ?? type,
      count: v.count,
      amount: Number(v.amount),
      severity: v.severity,
    }))
    .sort((a, b) => b.count - a.count);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-slate-900">Discrepancies by type</h2>
        <span className="text-xs text-slate-400">click a bar to filter the table</span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: "#64748b" }}
              interval={0}
              angle={-25}
              textAnchor="end"
              height={70}
            />
            <YAxis tick={{ fontSize: 11, fill: "#64748b" }} allowDecimals={false} />
            <Tooltip
              formatter={(_value, _name, item: any) => [
                `${item.payload.count} case(s) · ${item.payload.amount.toFixed(2)} at risk`,
                item.payload.label,
              ]}
              cursor={{ fill: "rgba(99,102,241,0.06)" }}
            />
            <Bar
              dataKey="count"
              radius={[4, 4, 0, 0]}
              cursor="pointer"
              onClick={(entry: any) => onSelectType(selectedType === entry.type ? null : entry.type)}
            >
              {data.map((d) => (
                <Cell
                  key={d.type}
                  fill={SEVERITY_COLORS[d.severity] ?? "#64748b"}
                  opacity={selectedType && selectedType !== d.type ? 0.25 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap gap-3 mt-2 text-xs text-slate-500">
        {Object.entries(SEVERITY_COLORS).map(([sev, color]) => (
          <span key={sev} className="inline-flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
            {sev}
          </span>
        ))}
      </div>
    </div>
  );
}
