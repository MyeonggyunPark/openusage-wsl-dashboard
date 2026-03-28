export type Metric = {
  type: "progress" | "text" | "badge";
  label: string;
  used?: number | null;
  limit?: number | null;
  unit?: "percent" | "count" | "currency" | null;
  value?: string | null;
  text?: string | null;
  color?: string | null;
  resetsAt?: string | null;
  periodDurationMs?: number | null;
  meta?: Record<string, unknown>;
};

export type Snapshot = {
  providerId: string;
  displayName: string;
  plan: string;
  status: "ok" | "demo" | "auth_missing" | "auth_expired" | "network_error" | "provider_error" | "parse_error";
  sourceState: string;
  fetchedAt: string;
  metrics: Metric[];
  warnings: string[];
};

export type UsageCollection = {
  items: Snapshot[];
  updatedAt: string;
  isDemoMode: boolean;
};
