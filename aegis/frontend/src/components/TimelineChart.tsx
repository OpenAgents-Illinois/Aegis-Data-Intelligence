import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface Props {
  data: { hour: string; count: number }[];
}

export default function TimelineChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm">
        No anomaly data yet
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid
          strokeDasharray="4 4"
          stroke="#e5e7eb"
          vertical={false}
        />
        <XAxis
          dataKey="hour"
          tick={{ fill: "#9ca3af", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "#e5e7eb" }}
          interval={3}
        />
        <YAxis
          tick={{ fill: "#9ca3af", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={30}
        />
        <Tooltip
          contentStyle={{
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            fontSize: 12,
            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.05)",
          }}
          labelStyle={{ color: "#6b7280", fontWeight: 600 }}
        />
        <Area
          type="monotone"
          dataKey="count"
          stroke="#3b82f6"
          fill="url(#colorCount)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#3b82f6", stroke: "#fff", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
