import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { clsx } from "clsx";
import { useSystemStore } from "../stores/systemStore";
import { useIncidentStore } from "../stores/incidentStore";
import { useTableStore } from "../stores/tableStore";
import { useAutoRefresh } from "../hooks/useAutoRefresh";
import { useWebSocket } from "../hooks/useWebSocket";
import IncidentFeed from "../components/IncidentFeed";
import FreshnessHeatmap from "../components/FreshnessHeatmap";
import TimelineChart from "../components/TimelineChart";
import { triggerScan } from "../api/endpoints";
import type { WsEvent } from "../api/types";

export default function Overview() {
  const navigate = useNavigate();
  const { stats, fetchStats } = useSystemStore();
  const { incidents, fetchIncidents } = useIncidentStore();
  const { tables, fetchTables } = useTableStore();

  useAutoRefresh(() => {
    fetchStats();
    fetchIncidents();
    fetchTables();
  }, 30_000);

  const handleWsMessage = useCallback(
    (event: WsEvent) => {
      if (
        event.event === "incident.created" ||
        event.event === "incident.updated"
      ) {
        fetchIncidents();
        fetchStats();
      }
      if (event.event === "scan.completed") {
        fetchStats();
      }
    },
    [fetchIncidents, fetchStats]
  );

  useWebSocket(handleWsMessage);

  // Placeholder timeline
  const timelineData = Array.from({ length: 24 }, (_, i) => ({
    hour: `${String(i).padStart(2, "0")}:00`,
    count: Math.floor(Math.random() * 5),
  }));

  const healthScore = stats?.health_score ?? 100;
  const healthColor =
    healthScore > 90
      ? "text-emerald-600"
      : healthScore > 70
        ? "text-amber-600"
        : "text-red-600";

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">
          Project Dashboard
        </h1>
        <button
          onClick={() => triggerScan()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Top row: Monitoring chart + side cards */}
      <div className="grid grid-cols-3 gap-5">
        {/* Monitoring card — spans 2 cols */}
        <div className="col-span-2 bg-white border border-gray-200 rounded-lg">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-900">Monitoring</h2>
          </div>
          <div className="px-5 py-4">
            {/* Filter bar */}
            <div className="flex items-center gap-4 mb-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Status</label>
                <div className="flex items-center gap-2 px-3 py-1.5 border border-gray-200 rounded-md bg-white text-sm">
                  <span className="text-gray-700">All tables</span>
                  <span className="text-gray-400">
                    {stats?.total_tables ?? 0}
                  </span>
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Health</label>
                <div className="flex items-center gap-2 px-3 py-1.5 border border-gray-200 rounded-md bg-white text-sm">
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-gray-700">
                    {healthScore >= 90
                      ? "Healthy"
                      : healthScore >= 70
                        ? "Warning"
                        : "Critical"}
                  </span>
                </div>
              </div>
            </div>
            <TimelineChart data={timelineData} />
          </div>
        </div>

        {/* Right column — stacked cards */}
        <div className="space-y-5">
          {/* Health Score card */}
          <div className="bg-white border border-gray-200 rounded-lg">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-900">
                Health Score
              </h3>
            </div>
            <div className="px-5 py-4">
              <div className="flex items-baseline gap-1">
                <span className={clsx("text-3xl font-bold tabular-nums", healthColor)}>
                  {stats ? `${stats.health_score}` : "--"}
                </span>
                <span className="text-lg text-gray-400">%</span>
              </div>
              <div className="mt-3 space-y-2">
                <Row label="Healthy tables" value={stats?.healthy_tables ?? 0} />
                <Row label="Total tables" value={stats?.total_tables ?? 0} />
              </div>
            </div>
          </div>

          {/* Incidents card */}
          <div className="bg-white border border-gray-200 rounded-lg">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-900">
                {stats?.open_incidents ?? 0} Open Incidents
              </h3>
              <button
                onClick={() => navigate("/settings")}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium"
              >
                View all
              </button>
            </div>
            <div className="px-5 py-3">
              <div className="space-y-2">
                <Row
                  label="Critical"
                  value={stats?.critical_incidents ?? 0}
                  valueColor={
                    (stats?.critical_incidents ?? 0) > 0
                      ? "text-red-600 font-semibold"
                      : undefined
                  }
                />
                <Row
                  label="Anomalies (24h)"
                  value={stats?.anomalies_24h ?? 0}
                />
                <Row
                  label="Avg resolution"
                  value={
                    stats?.avg_resolution_time_minutes
                      ? `${stats.avg_resolution_time_minutes} min`
                      : "--"
                  }
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom row: Incidents feed + Freshness */}
      <div className="grid grid-cols-2 gap-5">
        {/* Incident Feed card */}
        <div className="bg-white border border-gray-200 rounded-lg">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-900">
              Recent Incidents
            </h3>
            <span className="text-xs text-gray-400">
              {incidents.length} total
            </span>
          </div>
          <div className="p-4 max-h-80 overflow-auto">
            <IncidentFeed incidents={incidents.slice(0, 8)} />
          </div>
        </div>

        {/* Freshness card */}
        <div className="bg-white border border-gray-200 rounded-lg">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-900">
              Freshness Status
            </h3>
            <span className="text-xs text-gray-400">
              {tables.filter((t) => t.freshness_sla_minutes).length} with SLA
            </span>
          </div>
          <div className="p-4">
            <FreshnessHeatmap tables={tables} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string | number;
  valueColor?: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-500">{label}</span>
      <span className={clsx("text-sm font-medium text-gray-900", valueColor)}>
        {value}
      </span>
    </div>
  );
}
