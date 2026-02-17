import { useState } from "react";
import { createConnection } from "../api/endpoints";

interface Props {
  onCreated: () => void;
}

export default function ConnectionForm({ onCreated }: Props) {
  const [name, setName] = useState("");
  const [dialect, setDialect] = useState("postgresql");
  const [uri, setUri] = useState("");
  const [status, setStatus] = useState<"idle" | "testing" | "saving" | "error">("idle");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("saving");
    setError("");

    try {
      await createConnection({ name, dialect, connection_uri: uri });
      setName("");
      setUri("");
      onCreated();
      setStatus("idle");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create connection");
      setStatus("error");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="prod-snowflake"
          required
          className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Dialect</label>
        <select
          value={dialect}
          onChange={(e) => setDialect(e.target.value)}
          className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
          placeholder="postgresql://user:pass@host/db"
          required
          type="password"
          className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={status === "saving"}
          className="px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {status === "saving" ? "Saving..." : "Add Connection"}
        </button>
      </div>
    </form>
  );
}
