import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export default function Dashboard() {
  const { role, isLoading } = useAuth();

  if (isLoading) return null;

  switch (role) {
    case "patient":
      return <Navigate to="/patient" replace />;
    case "clinician":
      return <Navigate to="/clinician" replace />;
    case "analyst":
      return <Navigate to="/analyst" replace />;
    case "admin":
      return <Navigate to="/admin" replace />;
    default:
      return <Navigate to="/login" replace />;
  }
}
