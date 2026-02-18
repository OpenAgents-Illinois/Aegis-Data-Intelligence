import { useState } from "react";
import {
  createConnection,
  testConnection,
  discoverTables,
  confirmDiscovery,
} from "../api/endpoints";
import type { TableProposal } from "../api/types";

interface Props {
  onCreated: () => void;
}

type Step = "form" | "testing" | "discovering" | "confirm" | "done";

export default function ConnectionForm({ onCreated }: Props) {
  const [name, setName] = useState("");
  const [dialect, setDialect] = useState("postgresql");
  const [uri, setUri] = useState("");

  const [step, setStep] = useState<Step>("form");
  const [testResult, setTestResult] = useState<"success" | "fail" | null>(null);
  const [error, setError] = useState("");
  const [connId, setConnId] = useState<number | null>(null);
  const [proposals, setProposals] = useState<TableProposal[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [enrolling, setEnrolling] = useState(false);

  const key = (p: TableProposal) => `${p.schema_name}.${p.table_name}`;

  const handleTest = async () => {
    setError("");
    setTestResult(null);
    setStep("testing");
    try {
      // Create the connection first so we can test it
      const conn = await createConnection({ name, dialect, connection_uri: uri });
      setConnId(conn.id);
      const result = await testConnection(conn.id);
      setTestResult(result.success ? "success" : "fail");
      if (!result.success) {
        setError("Could not connect. Check your URI and credentials.");
      }
    } catch (e) {
      setTestResult("fail");
      setError(e instanceof Error ? e.message : "Connection test failed");
    }
    setStep("form");
  };

  const handleDiscover = async () => {
    if (!connId) return;
    setError("");
    setStep("discovering");
    try {
      const report = await discoverTables(connId);
      const props = report.proposals ?? [];
      setProposals(props);
      setSelected(new Set(props.map(key)));
      setStep("confirm");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Discovery failed");
      setStep("form");
    }
  };

  const toggleAll = () => {
    if (selected.size === proposals.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(proposals.map(key)));
    }
  };

  const toggle = (p: TableProposal) => {
    const k = key(p);
    const next = new Set(selected);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    setSelected(next);
  };

  const handleEnroll = async () => {
    if (!connId) return;
    setEnrolling(true);
    setError("");
    try {
      const selections = proposals
        .filter((p) => selected.has(key(p)))
        .map((p) => ({
          schema_name: p.schema_name,
          table_name: p.table_name,
          check_types: p.check_types,
          freshness_sla_minutes: p.freshness_sla_minutes,
        }));
      await confirmDiscovery(connId, selections);
      setStep("done");
      setTimeout(onCreated, 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Enrollment failed");
    } finally {
      setEnrolling(false);
    }
  };

  if (step === "done") {
    return (
      <div className="flex flex-col items-center py-6 gap-2 text-center">
        <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 text-xl">✓</div>
        <p className="text-sm font-medium text-gray-900">Connection added and tables enrolled!</p>
        <p className="text-xs text-gray-500">Aegis will begin monitoring shortly.</p>
      </div>
    );
  }

  if (step === "confirm") {
    return (
      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-900">
              {proposals.length} tables discovered
            </p>
            <button
              onClick={toggleAll}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              {selected.size === proposals.length ? "Deselect all" : "Select all"}
            </button>
          </div>
          <div className="border border-gray-200 rounded-lg overflow-hidden max-h-64 overflow-y-auto">
            {proposals.length === 0 ? (
              <div className="p-4 text-sm text-gray-500 text-center">No tables found.</div>
            ) : (
              proposals.map((p) => (
                <label
                  key={key(p)}
                  className="flex items-start gap-3 p-3 border-b border-gray-100 last:border-0 hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(key(p))}
                    onChange={() => toggle(p)}
                    className="mt-0.5 accent-red-600"
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">{key(p)}</p>
                    <p className="text-xs text-gray-500">
                      {p.classification} · {p.check_types.join(", ")}
                    </p>
                  </div>
                </label>
              ))
            )}
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex gap-2">
          <button
            onClick={handleEnroll}
            disabled={enrolling || selected.size === 0}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {enrolling ? "Enrolling..." : `Enroll ${selected.size} table${selected.size !== 1 ? "s" : ""}`}
          </button>
          <button
            onClick={() => { setStep("form"); setProposals([]); }}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            Back
          </button>
        </div>
      </div>
    );
  }

  const isDiscovering = step === "discovering";
  const isTesting = step === "testing";

  return (
    <form onSubmit={(e) => e.preventDefault()} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="prod-postgres"
          required
          disabled={!!connId}
          className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500 disabled:bg-gray-50 disabled:text-gray-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Dialect</label>
        <select
          value={dialect}
          onChange={(e) => setDialect(e.target.value)}
          disabled={!!connId}
          className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500 disabled:bg-gray-50 disabled:text-gray-500"
        >
          <option value="postgresql">PostgreSQL</option>
          <option value="snowflake">Snowflake</option>
          <option value="bigquery">BigQuery</option>
          <option value="databricks">Databricks</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Connection URI</label>
        <input
          value={uri}
          onChange={(e) => setUri(e.target.value)}
          placeholder="postgresql://user:pass@host:5432/dbname"
          required
          type="password"
          disabled={!!connId}
          className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500 disabled:bg-gray-50 disabled:text-gray-500"
        />
        <p className="mt-1 text-xs text-gray-400">e.g. postgresql://ash@localhost:5432/mydb</p>
      </div>

      {testResult && (
        <div
          className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${
            testResult === "success"
              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
              : "bg-red-50 text-red-700 border border-red-200"
          }`}
        >
          <span>{testResult === "success" ? "✓" : "✗"}</span>
          <span>
            {testResult === "success"
              ? "Connected successfully"
              : "Connection failed"}
          </span>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-2">
        {!connId ? (
          <button
            type="button"
            onClick={handleTest}
            disabled={isTesting || !name || !uri}
            className="px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {isTesting ? "Testing..." : "Test Connection"}
          </button>
        ) : testResult === "success" ? (
          <button
            type="button"
            onClick={handleDiscover}
            disabled={isDiscovering}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {isDiscovering ? (
              <>
                <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Discovering tables...
              </>
            ) : (
              "Discover Tables →"
            )}
          </button>
        ) : (
          <button
            type="button"
            onClick={handleTest}
            disabled={isTesting}
            className="px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {isTesting ? "Retesting..." : "Retry Connection"}
          </button>
        )}
      </div>
    </form>
  );
}
