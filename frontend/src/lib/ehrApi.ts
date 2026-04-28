// API client for the Sentiment-Aware EHR backend (FastAPI @ localhost:8000).
// Schema is enforced by Pydantic on the backend — do NOT modify the payload shape.

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

export const STRUCTURED_KEYS = [
  "mood_swings",
  "anxiety_level",
  "depression_indicators",
  "emotional_stability",
  "days_indoors",
  "social_interaction",
  "activity_level",
  "sleep_quality",
  "coping_struggles",
  "stress_level",
  "work_engagement",
  "motivation_level",
  "concentration_level",
  "decision_difficulty",
  "memory_issues",
  "support_system",
] as const;

export type StructuredKey = (typeof STRUCTURED_KEYS)[number];
export type Severity = 0 | 1 | 2 | 3;
export type StructuredMetrics = Record<StructuredKey, Severity>;

export interface PredictRequest {
  patient_id: string;
  timestamp: string; // ISO
  clinical_text: string;
  structured: StructuredMetrics;
}

export interface ImportantToken {
  word: string;
  weight: number;
}

export interface PredictResponse {
  patient_id: string;
  prediction: "Distress" | "Stable";
  confidence_score: number;
  important_tokens: ImportantToken[];
  requested_by?: string | null;
  timestamp?: string | null;
}

export interface RecordEntry extends PredictResponse {
  id?: number;
  timestamp: string;
  clinical_text?: string;
  sentiment?: string;
  token_count?: number;
  latency_ms?: number;
  created_at?: string;
}

export interface RecordsResponse {
  items: RecordEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  role: string;
}

export interface MeResponse {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  patient_profile_id: string | null;
}

export interface UserOut {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  patient_profile_id: string | null;
}

// ── Token storage ─────────────────────────────────────────────────────────────

export const tokenStore = {
  getAccess: (): string | null => localStorage.getItem("access_token"),
  getRefresh: (): string | null => localStorage.getItem("refresh_token"),
  set: (access: string, refresh: string) => {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
  },
  clear: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user_role");
    localStorage.removeItem("username");
  },
};

// ── Request helper ────────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = tokenStore.getAccess();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (res.status === 401) {
    // Attempt silent refresh
    const refreshed = await _tryRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${tokenStore.getAccess()}`;
      const retry = await fetch(`${API_BASE}${path}`, { ...init, headers });
      if (!retry.ok) {
        tokenStore.clear();
        window.location.href = "/login";
        throw new Error("Session expired");
      }
      return retry.json() as Promise<T>;
    }
    tokenStore.clear();
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function _tryRefresh(): Promise<boolean> {
  const refreshToken = tokenStore.getRefresh();
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data: LoginResponse = await res.json();
    tokenStore.set(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

// ── API surface ───────────────────────────────────────────────────────────────

export const api = {
  // Auth
  login: (payload: LoginRequest) =>
    request<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: (refresh_token: string) =>
    request<void>("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token }),
    }),
  me: () => request<MeResponse>("/api/v1/auth/me"),

  // Prediction
  predict: (payload: PredictRequest) =>
    request<PredictResponse>("/api/v1/predict", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Records
  records: (page = 1, pageSize = 20, patientId?: string) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (patientId) qs.set("patient_id", patientId);
    return request<RecordsResponse>(`/api/v1/records?${qs}`);
  },

  // Users (admin)
  listUsers: () => request<UserOut[]>("/api/v1/users"),
  createUser: (body: { username: string; password: string; role: string; patient_profile_id?: string }) =>
    request<UserOut>("/api/v1/users", { method: "POST", body: JSON.stringify(body) }),
  updateUser: (id: number, body: Partial<{ role: string; is_active: boolean }>) =>
    request<UserOut>(`/api/v1/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  resetPassword: (id: number, new_password: string) =>
    request<void>(`/api/v1/users/${id}/reset-password`, {
      method: "POST",
      body: JSON.stringify({ new_password }),
    }),
  deactivateUser: (id: number) =>
    request<void>(`/api/v1/users/${id}`, { method: "DELETE" }),

  // Health
  health: () => request<{ status: string; pipeline_ready: boolean; timestamp: string }>("/api/v1/health"),
};

// ── Structured feature metadata ───────────────────────────────────────────────

export interface MetricMeta {
  key: StructuredKey;
  label: string;
  category: MetricCategory;
}

export type MetricCategory =
  | "Psychological State"
  | "Behavioural Patterns"
  | "Coping & Stress"
  | "Cognitive Function"
  | "Social Context";

export const METRICS: MetricMeta[] = [
  { key: "mood_swings", label: "Mood Swings", category: "Psychological State" },
  { key: "anxiety_level", label: "Anxiety Level", category: "Psychological State" },
  { key: "depression_indicators", label: "Depression Indicators", category: "Psychological State" },
  { key: "emotional_stability", label: "Emotional Stability", category: "Psychological State" },

  { key: "days_indoors", label: "Days Indoors", category: "Behavioural Patterns" },
  { key: "social_interaction", label: "Social Interaction", category: "Behavioural Patterns" },
  { key: "activity_level", label: "Activity Level", category: "Behavioural Patterns" },
  { key: "sleep_quality", label: "Sleep Quality", category: "Behavioural Patterns" },

  { key: "coping_struggles", label: "Coping Struggles", category: "Coping & Stress" },
  { key: "stress_level", label: "Stress Level", category: "Coping & Stress" },
  { key: "work_engagement", label: "Work Engagement", category: "Coping & Stress" },
  { key: "motivation_level", label: "Motivation Level", category: "Coping & Stress" },

  { key: "concentration_level", label: "Concentration Level", category: "Cognitive Function" },
  { key: "decision_difficulty", label: "Decision Difficulty", category: "Cognitive Function" },
  { key: "memory_issues", label: "Memory Issues", category: "Cognitive Function" },

  { key: "support_system", label: "Support System", category: "Social Context" },
];

export function defaultStructured(): StructuredMetrics {
  return Object.fromEntries(STRUCTURED_KEYS.map((k) => [k, 0])) as StructuredMetrics;
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  0: "None",
  1: "Mild",
  2: "Moderate",
  3: "Severe",
};

export const CATEGORY_ORDER: MetricCategory[] = [
  "Psychological State",
  "Behavioural Patterns",
  "Coping & Stress",
  "Cognitive Function",
  "Social Context",
];
