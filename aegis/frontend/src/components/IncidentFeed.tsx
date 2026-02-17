import { useNavigate } from "react-router-dom";
import SeverityBadge from "./SeverityBadge";
import type { Incident } from "../api/types";

function timeAgo(dateStr: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(dateStr).getTime()) / 1000
  );
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function IncidentFeed({
  incidents,
}: {
  incidents: Incident[];
}) {
  const navigate = useNavigate();

  if (incidents.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm">
        No incidents — all clear
      </div>
    );
  }

  return (
    <div className="divide-y divide-gray-100">
      {incidents.map((incident) => (
        <button
          key={incident.id}
          onClick={() => navigate(`/incidents/${incident.id}`)}
          className="w-full text-left px-2 py-2.5 hover:bg-gray-50 transition-colors rounded-md -mx-2 first:mt-0"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <SeverityBadge severity={incident.severity} />
              <span className="text-sm text-gray-700 truncate">
                {incident.diagnosis?.root_cause?.slice(0, 55) ||
                  `Incident #${incident.id}`}
                {(incident.diagnosis?.root_cause?.length ?? 0) > 55 && "..."}
              </span>
            </div>
            <span className="text-xs text-gray-400 ml-3 flex-shrink-0">
              {timeAgo(incident.created_at)}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}
