import { useEffect, useState } from "react";
import { getConnections, deleteConnection, triggerScan } from "../api/endpoints";
import { useTableStore } from "../stores/tableStore";
import ConnectionForm from "../components/ConnectionForm";
import type { Connection } from "../api/types";

type Tab = "connections" | "tables" | "activity" | "api_key";

export default function Settings() {
  const [tab, setTab] = useState<Tab>("connections");

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold text-gray-900">Setup</h2>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 border border-gray-200 rounded-lg p-1">
        {(["connections", "tables", "activity", "api_key"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === t
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "api_key" ? "API Key" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "connections" && <ConnectionsTab />}
      {tab === "tables" && <TablesTab />}
      {tab === "activity" && <ActivityTab />}
      {tab === "api_key" && <ApiKeyTab />}
    </div>
  );
}

function ConnectionsTab() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [showForm, setShowForm] = useState(false);

  const load = async () => {
    const data = await getConnections();
    setConnections(data);
  };

  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (id: number) => {
    await deleteConnection(id);
    load();
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">
          {connections.length} connection{connections.length !== 1 && "s"}
        </p>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 bg-gray-900 hover:bg-gray-800 text-white rounded-md text-sm font-medium transition-colors"
        >
          {showForm ? "Cancel" : "+ Add Connection"}
        </button>
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <ConnectionForm
            onCreated={() => {
              setShowForm(false);
              load();
            }}
          />
        </div>
      )}

      <div className="space-y-2">
        {connections.map((conn) => (
          <div
            key={conn.id}
            className="flex items-center justify-between bg-white border border-gray-200 rounded-lg p-4"
          >
            <div>
              <p className="text-sm font-medium text-gray-900">{conn.name}</p>
              <p className="text-xs text-gray-500">{conn.dialect}</p>
            </div>
            <div className="flex items-center gap-3">
              <span
                className={`w-2 h-2 rounded-full ${
                  conn.is_active ? "bg-emerald-500" : "bg-gray-300"
                }`}
              />
              <button
                onClick={() => handleDelete(conn.id)}
                className="text-xs text-red-600 hover:text-red-700 font-medium"
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TablesTab() {
  const { tables, fetchTables } = useTableStore();

  useEffect(() => {
    fetchTables();
  }, [fetchTables]);

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        {tables.length} table{tables.length !== 1 && "s"} monitored
      </p>
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-gray-500 text-xs uppercase bg-gray-50">
              <th className="text-left p-3 font-medium">Table</th>
              <th className="text-left p-3 font-medium">Checks</th>
              <th className="text-left p-3 font-medium">SLA (min)</th>
            </tr>
          </thead>
          <tbody>
            {tables.map((t) => (
              <tr key={t.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="p-3 text-gray-900">{t.fully_qualified_name}</td>
                <td className="p-3 text-gray-500">
                  {t.check_types.join(", ")}
                </td>
                <td className="p-3 text-gray-500">
                  {t.freshness_sla_minutes ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ActivityTab() {
  const [scanning, setScanning] = useState(false);

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerScan();
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">Agent activity log</p>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="px-3 py-1.5 bg-gray-900 hover:bg-gray-800 text-white rounded-md text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {scanning ? "Scanning..." : "Trigger Manual Scan"}
        </button>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400 text-sm">
        Activity log will appear here as agents process data.
      </div>
    </div>
  );
}

function ApiKeyTab() {
  const [key, setKey] = useState(localStorage.getItem("aegis_api_key") || "");

  const save = () => {
    localStorage.setItem("aegis_api_key", key);
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        API key is stored in your browser&apos;s localStorage.
      </p>
      <div className="flex gap-2">
        <input
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="Enter API key..."
          type="password"
          className="flex-1 bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <button
          onClick={save}
          className="px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Save
        </button>
      </div>
    </div>
  );
}
