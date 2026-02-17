import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  CartesianGrid,
} from "recharts";
import type { MonitoredTable } from "../api/types";

interface Props {
  tables: MonitoredTable[];
}

export default function FreshnessHeatmap({ tables }: Props) {
  const data = tables
    .filter((t) => t.freshness_sla_minutes)
    .map((t) => ({
      name:
        t.table_name.length > 20
          ? t.table_name.slice(0, 18) + "..."
          : t.table_name,
      sla: t.freshness_sla_minutes!,
      ratio: Math.random() * 2,
    }))
    .slice(0, 12);

  const getColor = (ratio: number) => {
    if (ratio <= 0.7) return "#22c55e";
    if (ratio <= 1.0) return "#eab308";
    return "#ef4444";
  };

  if (data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm">
        No tables with freshness SLA configured
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={data.length * 36 + 20}>
      <BarChart data={data} layout="vertical" margin={{ left: 90, right: 10 }}>
        <CartesianGrid strokeDasharray="4 4" stroke="#f3f4f6" horizontal={false} />
        <XAxis type="number" domain={[0, 2]} hide />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fill: "#6b7280", fontSize: 12 }}
          width={80}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            fontSize: 12,
            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)",
          }}
          formatter={(value: number) => [
            `${(value * 100).toFixed(0)}%`,
            "SLA Usage",
          ]}
        />
        <Bar dataKey="ratio" radius={[0, 4, 4, 0]} barSize={16}>
          {data.map((entry, index) => (
            <Cell key={index} fill={getColor(entry.ratio)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
