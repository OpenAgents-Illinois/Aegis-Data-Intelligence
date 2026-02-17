import client from "./client";
import type {
  Connection,
  Incident,
  LineageGraph,
  MonitoredTable,
  Stats,
  BlastRadius,
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

// --- Lineage ---
export const getLineageGraph = () =>
  client.get<LineageGraph>("/lineage/graph").then((r) => r.data);

export const getBlastRadius = (table: string) =>
  client.get<BlastRadius>(`/lineage/${table}/blast-radius`).then((r) => r.data);

// --- System ---
export const getStats = () =>
  client.get<Stats>("/stats").then((r) => r.data);

export const getHealth = () =>
  client.get<{ status: string }>("/health").then((r) => r.data);

export const triggerScan = () =>
  client.post("/scan/trigger").then((r) => r.data);
