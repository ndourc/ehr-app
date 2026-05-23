import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";

import Login from "./pages/Login.tsx";
import Dashboard from "./pages/Dashboard.tsx";
import PatientDashboard from "./pages/PatientDashboard.tsx";
import ClinicianDashboard from "./pages/ClinicianDashboard.tsx";
import AnalystDashboard from "./pages/AnalystDashboard.tsx";
import AdminDashboard from "./pages/AdminDashboard.tsx";
import NotFound from "./pages/NotFound.tsx";

// Clinician sub-pages
import InferencePage from "./pages/clinician/InferencePage.tsx";
import AuditPage from "./pages/clinician/AuditPage.tsx";

// Analyst sub-pages
import OverviewPage from "./pages/analyst/OverviewPage.tsx";
import TrendsPage from "./pages/analyst/TrendsPage.tsx";

// Admin sub-pages
import UsersPage from "./pages/admin/UsersPage.tsx";
import SystemPage from "./pages/admin/SystemPage.tsx";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Public */}
            <Route path="/login" element={<Login />} />

            {/* Root → role router */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />

            {/* Patient — single view, uses DashboardShell */}
            <Route
              path="/patient"
              element={
                <ProtectedRoute allowedRoles={["patient"]}>
                  <PatientDashboard />
                </ProtectedRoute>
              }
            />

            {/* Clinician — sidebar layout with nested routes */}
            <Route
              path="/clinician"
              element={
                <ProtectedRoute allowedRoles={["clinician"]}>
                  <ClinicianDashboard />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="inference" replace />} />
              <Route path="inference" element={<InferencePage />} />
              <Route path="audit" element={<AuditPage />} />
            </Route>

            {/* Analyst — sidebar layout with nested routes */}
            <Route
              path="/analyst"
              element={
                <ProtectedRoute allowedRoles={["analyst", "admin"]}>
                  <AnalystDashboard />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<OverviewPage />} />
              <Route path="trends" element={<TrendsPage />} />
            </Route>

            {/* Admin — sidebar layout with nested routes */}
            <Route
              path="/admin"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <AdminDashboard />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="users" replace />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="system" element={<SystemPage />} />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;

