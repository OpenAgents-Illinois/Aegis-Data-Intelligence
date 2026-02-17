import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useIncidentStore } from "../stores/incidentStore";
import { approveIncident, dismissIncident } from "../api/endpoints";
import SeverityBadge from "../components/SeverityBadge";
import SqlBlock from "../components/SqlBlock";
import BlastRadiusGraph from "../components/BlastRadiusGraph";

export default function IncidentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { current: incident, fetchIncident, loading } = useIncidentStore();
  const [dismissReason, setDismissReason] = useState("");
  const [showDismiss, setShowDismiss] = useState(false);

  useEffect(() => {
    if (id) fetchIncident(Number(id));
  }, [id, fetchIncident]);

  if (loading || !incident) {
    return (
      <div className="text-gray-400 text-center py-20">Loading incident...</div>
    );
  }

  const handleApprove = async () => {
    await approveIncident(incident.id);
    fetchIncident(incident.id);
  };

  const handleDismiss = async () => {
    if (!dismissReason.trim()) return;
    await dismissIncident(incident.id, dismissReason);
    fetchIncident(incident.id);
    setShowDismiss(false);
  };

  const diagnosis = incident.diagnosis;
  const isActive = !["resolved", "dismissed"].includes(incident.status);

  return (
    <div className="max-w-4xl space-y-6">
      {/* Back button */}
      <button
        onClick={() => navigate("/dashboard")}
        className="text-sm text-gray-500 hover:text-gray-700 font-medium"
      >
        &larr; Back to Overview
      </button>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">
            Incident #{incident.id}
          </h2>
          <div className="flex items-center gap-3 mt-2">
            <SeverityBadge severity={incident.severity} />
            <span className="text-sm text-gray-500 capitalize">
              {incident.status.replace("_", " ")}
            </span>
            <span className="text-sm text-gray-400">
              {new Date(incident.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        {isActive && (
          <div className="flex gap-2">
            <button
              onClick={handleApprove}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-md text-sm font-medium transition-colors"
            >
              Approve
            </button>
            <button
              onClick={() => setShowDismiss(!showDismiss)}
              className="px-4 py-2 border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-md text-sm font-medium transition-colors"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Dismiss form */}
      {showDismiss && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 flex gap-2">
          <input
            value={dismissReason}
            onChange={(e) => setDismissReason(e.target.value)}
            placeholder="Reason for dismissal..."
            className="flex-1 bg-white border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <button
            onClick={handleDismiss}
            className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-md text-sm font-medium transition-colors"
          >
            Confirm Dismiss
          </button>
        </div>
      )}

      {/* Root Cause Analysis */}
      {diagnosis && (
        <section className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Root Cause Analysis
          </h3>
          <p className="text-gray-900">{diagnosis.root_cause}</p>
          <div className="flex gap-4 text-sm">
            <span className="text-gray-500">
              Source: <span className="text-gray-900 font-medium">{diagnosis.root_cause_table}</span>
            </span>
            <span className="text-gray-500">
              Confidence:{" "}
              <span className="text-gray-900 font-medium">
                {(diagnosis.confidence * 100).toFixed(0)}%
              </span>
            </span>
          </div>
        </section>
      )}

      {/* Blast Radius */}
      {incident.blast_radius && incident.blast_radius.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Blast Radius ({incident.blast_radius.length} tables affected)
          </h3>
          <BlastRadiusGraph
            sourceTable={diagnosis?.root_cause_table || "unknown"}
            affectedTables={incident.blast_radius}
          />
        </section>
      )}

      {/* Recommended Actions */}
      {diagnosis && diagnosis.recommendations.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Recommended Actions
          </h3>
          <div className="space-y-4">
            {diagnosis.recommendations
              .sort((a, b) => a.priority - b.priority)
              .map((rec, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-medium">
                      {rec.action}
                    </span>
                    <span className="text-sm text-gray-700">{rec.description}</span>
                  </div>
                  {rec.sql && <SqlBlock sql={rec.sql} />}
                </div>
              ))}
          </div>
        </section>
      )}

      {/* Remediation Summary */}
      {incident.remediation && (
        <section className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Summary
          </h3>
          <pre className="text-sm text-gray-600 whitespace-pre-wrap">
            {incident.remediation.summary}
          </pre>
        </section>
      )}
    </div>
  );
}
