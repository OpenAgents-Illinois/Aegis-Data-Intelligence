/** TypeScript interfaces matching the Aegis API. */

export interface Connection {
  id: number;
  name: string;
  dialect: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MonitoredTable {
  id: number;
  connection_id: number;
  schema_name: string;
  table_name: string;
  fully_qualified_name: string;
  check_types: string[];
  freshness_sla_minutes: number | null;
  created_at: string;
  updated_at: string;
}

export interface Anomaly {
  id: number;
  table_id: number;
  type: "schema_drift" | "freshness_violation";
  severity: Severity;
  detail: Record<string, unknown>;
  detected_at: string;
}

export type Severity = "critical" | "high" | "medium" | "low";

export interface Recommendation {
  action: string;
  description: string;
  sql?: string | null;
  priority: number;
}

export interface Diagnosis {
  root_cause: string;
  root_cause_table: string;
  blast_radius: string[];
  severity: Severity;
  confidence: number;
  recommendations: Recommendation[];
}

export interface Incident {
  id: number;
  anomaly_id: number;
  status: "open" | "investigating" | "pending_review" | "resolved" | "dismissed";
  diagnosis: Diagnosis | null;
  blast_radius: string[] | null;
  remediation: {
    actions: RemediationAction[];
    summary: string;
    generated_at: string;
  } | null;
  severity: Severity;
  resolved_at: string | null;
  resolved_by: string | null;
  dismiss_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface RemediationAction {
  type: string;
  description: string;
  sql?: string;
  status: "pending_approval" | "manual";
  priority: number;
}

export interface LineageNode {
  id: string;
  label: string;
}

export interface LineageEdge {
  source: string;
  target: string;
  relationship: string;
  confidence: number;
}

export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

export interface BlastRadius {
  table: string;
  affected_tables: { name: string; depth: number; confidence: number }[];
  total_affected: number;
  max_depth: number;
}

export interface Stats {
  health_score: number;
  total_tables: number;
  healthy_tables: number;
  open_incidents: number;
  critical_incidents: number;
  anomalies_24h: number;
  avg_resolution_time_minutes: number | null;
}

export interface WsEvent {
  event: string;
  data: Record<string, unknown>;
}
