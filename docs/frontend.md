# Frontend Overview — EHR Clinical Platform

> **Stack:** React 18 + TypeScript · Vite · TailwindCSS · React Router v6 · TanStack Query · shadcn/ui components
> **API target:** FastAPI backend at `http://localhost:8000` (overridable via `VITE_API_BASE`)

---

## Architecture Summary

The application is a **role-gated, single-page application**. All meaningful content lives behind authentication. After login, users are routed to a role-specific dashboard. There is no shared navigation between role dashboards — each role gets its own isolated view.

```
/login               → public entry point
/                    → redirects to /dashboard
/dashboard           → role router (redirects based on JWT role)
/patient             → PatientDashboard  (role: patient)
/clinician           → ClinicianDashboard (role: clinician)
/analyst             → AnalystDashboard  (role: analyst | admin)
/admin               → AdminDashboard    (role: admin)
*                    → NotFound (404)
```

---

## Auth & State Model

**File:** `src/contexts/AuthContext.tsx` · `src/lib/ehrApi.ts`

| Concept         | Detail                                                                                                                                |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Auth mechanism  | JWT Bearer token — stored in `localStorage` as `access_token` / `refresh_token`                                                       |
| Session restore | On mount, `AuthProvider` reads the stored access token and calls `GET /api/v1/auth/me` to rehydrate state                             |
| Silent refresh  | On any `401`, the API client automatically attempts `POST /api/v1/auth/refresh`; on failure, clears storage and redirects to `/login` |
| Role            | Derived from the `me` response (`user.role`). One of: `patient`, `clinician`, `analyst`, `admin`                                      |
| Logout          | Calls `POST /api/v1/auth/logout` (best-effort), then clears all tokens and nullifies user state                                       |

**`ProtectedRoute` component** wraps all non-public routes. It shows a loading spinner while auth is resolving, redirects unauthenticated users to `/login`, and redirects role-mismatched users back to `/dashboard`.

---

## Pages

---

### `/login` — Login

**File:** `src/pages/Login.tsx`
**Access:** Public

#### Purpose

Entry point for all users. Handles credential submission and bootstraps the authenticated session.

#### User Actions

- Enter username and password
- Toggle password visibility
- Submit the login form

#### Workflow

1. User submits credentials → `POST /api/v1/auth/login`
2. On success: tokens stored in `localStorage`, `GET /api/v1/auth/me` is called, user state is set
3. User is navigated to `/dashboard` (which then redirects to their role route)
4. On failure: inline error message displayed

#### Key UI Sections

- Brand header with EHR logo icon
- Username field (with icon)
- Password field (with show/hide toggle)
- Submit button (disabled while loading or fields empty)
- Dev-mode credential hint (hardcoded: `doctor1 / nurse1 / analyst1 / admin1 / patient1`, pw: `Password123!`)

#### State

- `username`, `password`, `showPw`, `loading`, `error` — all local component state

#### Implementation Status

**Fully implemented.**

---

### `/dashboard` — Role Router

**File:** `src/pages/Dashboard.tsx`
**Access:** Any authenticated user

#### Purpose

A purely logical routing component. It reads the authenticated user's role and immediately redirects to the correct role-specific dashboard. Renders nothing visible.

#### Routing Logic

| Role         | Redirects to |
| ------------ | ------------ |
| `patient`    | `/patient`   |
| `clinician`  | `/clinician` |
| `analyst`    | `/analyst`   |
| `admin`      | `/admin`     |
| unknown/null | `/login`     |

#### Implementation Status

**Fully implemented.**

---

### `/patient` — Patient Dashboard

**File:** `src/pages/PatientDashboard.tsx`
**Access:** Role `patient` only

#### Purpose

Lets a patient view a read-only summary of their own mental health assessment history. No data entry or clinician tools are available.

#### User Actions

- View personal assessment summary stats
- View latest assessment result and confidence score
- Browse paginated assessment history list

#### Key UI Sections

| Section                 | Description                                                                 |
| ----------------------- | --------------------------------------------------------------------------- |
| Welcome header          | Displays username and linked `patient_profile_id`                           |
| Summary stat cards      | Total Assessments / Stable count / Distress Flags                           |
| Latest Assessment panel | Most recent prediction badge, confidence %, and timestamp                   |
| Assessment History list | All records (up to 20, page 1) — prediction badge, confidence, date per row |

#### API Calls

- `GET /api/v1/records?page=1&page_size=20` — fetches records on mount (no patient ID filter applied; relies on backend scoping by auth token)

#### State

- `records`, `loading`, `error` — local component state

#### Implementation Status

**Fully implemented.** No pagination controls beyond page 1 — the list shows up to 20 records.

---

### `/clinician` — Clinician Dashboard

**File:** `src/pages/ClinicianDashboard.tsx`
**Access:** Role `clinician`

#### Purpose

The primary clinical workflow tool. Clinicians enter patient data (free-text notes + 16 structured behavioural metrics) and run the ML inference pipeline to get a mental health prediction with XAI explanation.

#### User Actions

- Switch between **Inference** and **Audit Log** tabs
- Input a Patient ID
- Write or edit clinical notes (free-text)
- Score 16 behavioural metrics across 5 categories using a severity picker (None / Mild / Moderate / Severe)
- Run the inference pipeline
- Reset all metrics to zero
- View the prediction result and XAI token highlighting
- Browse past inference records in the audit log

#### Inference Workflow

1. Clinician fills in Patient ID, clinical notes, and any relevant metric scores
2. Clicks **Run Inference** → `POST /api/v1/predict`
3. Loading state shows pipeline stages (ClinicalBERT NLP, RF/SVM ensemble, fusion layer)
4. Result panel updates with: prediction verdict (Distress / Stable), confidence %, inference latency, and XAI token highlighting over the submitted clinical text

#### Key UI Sections

| Section                   | Component         | Description                                                       |
| ------------------------- | ----------------- | ----------------------------------------------------------------- |
| Tab bar                   | inline            | Switches between Inference and Audit Log views                    |
| Patient panel             | inline            | Patient ID input + clinical notes textarea                        |
| Behavioural Metrics panel | `MetricsMatrix`   | 16 metrics grouped into 5 categories, each with a severity picker |
| Run / Reset controls      | inline            | Submit button + reset button                                      |
| Inference Output panel    | `PredictionPanel` | Shows verdict, confidence, latency, and XAI-highlighted text      |
| Audit Log                 | `AuditLog`        | Paginated table of all past records                               |

#### Structured Metrics (16 fields, 5 categories)

| Category             | Metrics                                                                |
| -------------------- | ---------------------------------------------------------------------- |
| Psychological State  | Mood Swings, Anxiety Level, Depression Indicators, Emotional Stability |
| Behavioural Patterns | Days Indoors, Social Interaction, Activity Level, Sleep Quality        |
| Coping & Stress      | Coping Struggles, Stress Level, Work Engagement, Motivation Level      |
| Cognitive Function   | Concentration Level, Decision Difficulty, Memory Issues                |
| Social Context       | Support System                                                         |

Each metric is scored `0` (None) → `3` (Severe).

#### API Calls

- `POST /api/v1/predict` — runs inference on submit
- `GET /api/v1/records` (via `AuditLog`) — on audit tab load, paginated

#### State

- `tab`, `patientId`, `clinicalText`, `structured` (16-key object), `loading`, `result`, `error`, `latencyMs`, `submittedText` — all local

#### Implementation Status

**Fully implemented.** Core inference flow, XAI display, metrics matrix, and audit log are all functional.

---

### `/analyst` — Analytics Dashboard

**File:** `src/pages/AnalystDashboard.tsx`
**Access:** Roles `analyst` and `admin`

#### Purpose

A population-level analytics view over all prediction records in the system. Designed for data analysts to monitor model performance, prediction distribution, and inference latency trends.

#### User Actions

- View KPI summary cards
- View inference performance stats
- Browse de-identified prediction records in a paginated table
- Navigate pages (Prev / Next)

#### Key UI Sections

| Section                     | Description                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------ |
| KPI cards                   | Total Records, Distress count, Stable count, Avg Confidence %                        |
| Inference Performance panel | Avg Latency (ms), Distress Prevalence %, Records on page                             |
| De-identified Records table | Anon patient ID, Prediction badge, Confidence, Sentiment, Token count, Latency, Date |
| Pagination controls         | Prev / Page N / Next (25 records per page)                                           |

#### Notes

- Patient IDs are shown as-is from the API (labelled "anonymised" in the UI header, but actual anonymisation is handled server-side)
- No charts or visualisations — all data is presented in text/table form

#### API Calls

- `GET /api/v1/records?page=N&page_size=25` — re-fetched on each page change

#### State

- `records`, `total`, `page`, `loading`, `error` — local component state

#### Implementation Status

**Functional but minimal.** All data is live. No charts, filters, date ranges, or export features. The "analytics" is limited to computed stats from the current page of records rather than aggregate server queries.

---

### `/admin` — Admin Dashboard

**File:** `src/pages/AdminDashboard.tsx`
**Access:** Role `admin` only

#### Purpose

System administration interface. Manages user accounts and monitors system health.

#### User Actions

- View user count breakdown by role
- Switch between **Users** and **Health** tabs
- Create new users (any role, with optional patient profile ID for patient accounts)
- Toggle user active/inactive status
- Reset a user's password inline
- View API health status and pipeline readiness

#### Key UI Sections

| Section               | Description                                                                         |
| --------------------- | ----------------------------------------------------------------------------------- |
| Role count cards      | Count of admin / clinician / analyst / patient accounts                             |
| Tab bar               | Switches between Users and Health views                                             |
| Users table           | ID, Username, Role badge, Active status, Patient Profile ID, Actions                |
| Create User form      | Inline toggle form: username, password, role selector, conditional patient ID field |
| Reset Password inline | Appears inline in the table when the edit icon is clicked for a user                |
| Health panel          | API status (OK indicator) and pipeline readiness flag                               |

#### API Calls

| Action                       | Endpoint                                   |
| ---------------------------- | ------------------------------------------ |
| Load users + health on mount | `GET /api/v1/users` + `GET /api/v1/health` |
| Create user                  | `POST /api/v1/users`                       |
| Toggle active status         | `PATCH /api/v1/users/{id}` (`is_active`)   |
| Reset password               | `POST /api/v1/users/{id}/reset-password`   |

#### State

- `users`, `health`, `loading`, `error`, `tab` — top-level local state
- `showCreate`, `newUsername`, `newPassword`, `newRole`, `newPatientId`, `creating`, `createError` — create form state
- `resetUserId`, `resetPw`, `resetting` — inline password reset state

#### Implementation Status

**Fully implemented.** Full CRUD for users (excluding hard delete — deactivation is used instead). Health tab shows live API and pipeline status.

---

### `*` — Not Found (404)

**File:** `src/pages/NotFound.tsx`
**Access:** Public (catch-all)

#### Purpose

Minimal 404 page for unmatched routes. Logs the attempted path to the console.

#### Key UI

- "404 — Page not found" message
- Link back to `/` (home)

#### Implementation Status

**Fully implemented** (minimal by design).

---

### `Index.tsx` — Legacy Dev Page

**File:** `src/pages/Index.tsx`
**Access:** Not routed

#### Purpose

An earlier version of the Clinician inference UI that includes both the inference form and audit log in a single component. It is **not wired into the router** in `App.tsx` and is not accessible in the running application.

#### Implementation Status

**Orphaned / unused.** Safe to delete or repurpose.

---

## Shared Components

| Component         | File                             | Used By                           |
| ----------------- | -------------------------------- | --------------------------------- |
| `DashboardShell`  | `components/DashboardShell.tsx`  | All role dashboards               |
| `ProtectedRoute`  | `components/ProtectedRoute.tsx`  | `App.tsx` (wraps all auth routes) |
| `MetricsMatrix`   | `components/MetricsMatrix.tsx`   | `ClinicianDashboard`, `Index`     |
| `SeverityPicker`  | `components/SeverityPicker.tsx`  | `MetricsMatrix`                   |
| `PredictionPanel` | `components/PredictionPanel.tsx` | `ClinicianDashboard`, `Index`     |
| `XAIHighlighter`  | `components/XAIHighlighter.tsx`  | `PredictionPanel`                 |
| `AuditLog`        | `components/AuditLog.tsx`        | `ClinicianDashboard`, `Index`     |

### `DashboardShell`

Provides the persistent top navigation bar shown across all role dashboards. Renders:

- EHR brand icon + page title
- Current username + colour-coded role badge
- Sign out button (calls `logout()` and redirects to `/login`)

### `MetricsMatrix`

Renders all 16 structured metrics, grouped into 5 clinical categories, each with a `SeverityPicker`. Shows a live count of elevated (non-zero) metrics per category.

### `PredictionPanel`

Three-state result display: **Idle** (empty state prompt), **Loading** (animated pipeline stages), **Result** (verdict badge, confidence bar, latency, and XAI highlighted text via `XAIHighlighter`).

### `XAIHighlighter`

Tokenizes the submitted clinical text and highlights words returned in `important_tokens` with colour-coded attention weights (4 intensity levels from primary-soft to high-distress red).

### `AuditLog`

Paginated table (20 records/page) of all inference records. Columns: index, timestamp, patient ID, prediction badge, confidence %, top XAI token + weight.

---

## Navigation Flow

```
  [ /login ]
      │
      └──(auth success)──▶ [ /dashboard ] ──role switch──▶ /patient
                                                         ├──▶ /clinician
                                                         ├──▶ /analyst
                                                         └──▶ /admin

  Any page ──(sign out)──▶ [ /login ]
  Any 401  ──(refresh fail)──▶ [ /login ]
  Unknown route ──▶ [ * → NotFound ]
```

There is **no sidebar navigation** or cross-role linking. Users stay within their single dashboard route. Tabs within `ClinicianDashboard` and `AdminDashboard` are UI state, not separate routes.

---

## API Client Summary (`src/lib/ehrApi.ts`)

| Method           | Endpoint                                 | Used By                          |
| ---------------- | ---------------------------------------- | -------------------------------- |
| `login`          | `POST /api/v1/auth/login`                | `AuthContext`                    |
| `logout`         | `POST /api/v1/auth/logout`               | `AuthContext`                    |
| `me`             | `GET /api/v1/auth/me`                    | `AuthContext`                    |
| `predict`        | `POST /api/v1/predict`                   | Clinician / Index                |
| `records`        | `GET /api/v1/records`                    | Patient / Analyst / AuditLog     |
| `listUsers`      | `GET /api/v1/users`                      | Admin                            |
| `createUser`     | `POST /api/v1/users`                     | Admin                            |
| `updateUser`     | `PATCH /api/v1/users/{id}`               | Admin                            |
| `resetPassword`  | `POST /api/v1/users/{id}/reset-password` | Admin                            |
| `deactivateUser` | `DELETE /api/v1/users/{id}`              | Admin (defined, not wired to UI) |
| `health`         | `GET /api/v1/health`                     | Admin                            |

---

## Implementation Status Summary

| Page / Route | Status                  | Notes                                    |
| ------------ | ----------------------- | ---------------------------------------- |
| `/login`     | ✅ Complete             |                                          |
| `/dashboard` | ✅ Complete             | Role router only                         |
| `/patient`   | ✅ Complete             | Read-only; no pagination beyond page 1   |
| `/clinician` | ✅ Complete             | Full inference + XAI + audit log         |
| `/analyst`   | ⚠️ Functional / Minimal | No charts, filters, or aggregate queries |
| `/admin`     | ✅ Complete             | Full user CRUD + health check            |
| `*` (404)    | ✅ Complete             | Minimal by design                        |
| `Index.tsx`  | ❌ Orphaned             | Not routed; legacy dev artifact          |
