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
}

export interface RecordEntry extends PredictResponse {
  timestamp: string;
  clinical_text?: string;
}

export interface RecordsResponse {
  items: RecordEntry[];
  total: number;
  page: number;
  page_size: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  predict: (payload: PredictRequest) =>
    request<PredictResponse>("/api/v1/predict", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  records: (page = 1, pageSize = 20) =>
    request<RecordsResponse>(`/api/v1/records?page=${page}&page_size=${pageSize}`),
};

// Display metadata for the 16 structured ordinal variables.
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

export function defaultStructured(): StructuredMetrics {
  return STRUCTURED_KEYS.reduce((acc, k) => {
    acc[k] = 0;
    return acc;
  }, {} as StructuredMetrics);
}
