import client from "./client";
import type {
  Connection,
  Incident,
  IncidentReport,
  LineageGraph,
  MonitoredTable,
  Stats,
  BlastRadius,
  TableProposal,
} from "./types";

// --- Connections ---
export const getConnections = () =>
  client.get<Connection[]>("/connections").then((r) => r.data);

export const createConnection = (body: {
  name: string;
  dialect: string;
  connection_uri: string;
}) => client.post<Connection>("/connections", body).then((r) => r.data);

export const deleteConnection = (id: number) =>
  client.delete(`/connections/${id}`);

export const testConnection = (id: number) =>
  client
    .post<{ success: boolean }>(`/connections/${id}/test`)
    .then((r) => r.data);

export const discoverTables = (id: number) =>
  client.post<{ proposals: TableProposal[] }>(`/connections/${id}/discover`).then((r) => r.data);

export const confirmDiscovery = (
  id: number,
  tableSelections: { schema_name: string; table_name: string; check_types: string[]; freshness_sla_minutes: number | null }[]
) =>
  client
    .post<{ enrolled: unknown[]; total: number }>(`/connections/${id}/discover/confirm`, {
      table_selections: tableSelections,
    })
    .then((r) => r.data);

// --- Tables ---
export const getTables = (params?: { connection_id?: number }) =>
  client.get<MonitoredTable[]>("/tables", { params }).then((r) => r.data);

export const createTable = (body: {
  connection_id: number;
  schema_name: string;
  table_name: string;
  check_types?: string[];
  freshness_sla_minutes?: number | null;
}) => client.post<MonitoredTable>("/tables", body).then((r) => r.data);

export const deleteTable = (id: number) => client.delete(`/tables/${id}`);

// --- Incidents ---
export const getIncidents = (params?: {
  status?: string;
  severity?: string;
  since?: string;
}) => client.get<Incident[]>("/incidents", { params }).then((r) => r.data);

export const getIncident = (id: number) =>
  client.get<Incident>(`/incidents/${id}`).then((r) => r.data);

export const approveIncident = (id: number, note?: string) =>
  client
    .post<Incident>(`/incidents/${id}/approve`, { note })
    .then((r) => r.data);

export const dismissIncident = (id: number, reason: string) =>
  client
    .post<Incident>(`/incidents/${id}/dismiss`, { reason })
    .then((r) => r.data);

export const getIncidentReport = (id: number) =>
  client
    .get<IncidentReport>(`/incidents/${id}/report`, {
      validateStatus: (s) => s === 200 || s === 204,
    })
    .then((r) => (r.status === 204 ? null : r.data));

// --- Lineage ---
export const getLineageGraph = (params?: { connection_id?: number }) =>
  client.get<LineageGraph>("/lineage/graph", { params }).then((r) => r.data);

export const getBlastRadius = (table: string) =>
  client.get<BlastRadius>(`/lineage/${table}/blast-radius`).then((r) => r.data);

// --- System ---
export const getStats = () =>
  client.get<Stats>("/stats").then((r) => r.data);

export const getHealth = () =>
  client.get<{ status: string }>("/health").then((r) => r.data);

export const triggerScan = () =>
  client.post("/scan/trigger").then((r) => r.data);
