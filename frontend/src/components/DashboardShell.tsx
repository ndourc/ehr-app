import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Activity, LogOut, User } from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  title: string;
  children: ReactNode;
}

export function DashboardShell({ title, children }: Props) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  const roleBadgeColor: Record<string, string> = {
    admin: "bg-red-100 text-red-700",
    clinician: "bg-blue-100 text-blue-700",
    analyst: "bg-purple-100 text-purple-700",
    patient: "bg-green-100 text-green-700",
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Top nav */}
      <header className="border-b border-border bg-card px-4 md:px-8 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
            <Activity className="w-4 h-4" />
          </div>
          <span className="text-sm font-semibold text-foreground hidden sm:block">
            EHR Clinical Platform
          </span>
          <span className="text-muted-foreground hidden sm:block">·</span>
          <span className="text-sm text-foreground font-medium">{title}</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center">
              <User className="w-3.5 h-3.5 text-muted-foreground" />
            </div>
            <div className="hidden sm:block text-right">
              <p className="text-xs font-medium text-foreground">{user?.username}</p>
              <span
                className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium capitalize ${roleBadgeColor[user?.role ?? ""] ?? "bg-muted text-muted-foreground"}`}
              >
                {user?.role}
              </span>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1.5 rounded hover:bg-muted"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:block">Sign out</span>
          </button>
        </div>
      </header>

      {/* Page content */}
      <main className="max-w-[1400px] mx-auto px-4 md:px-8 py-6 md:py-8">
        {children}
      </main>
    </div>
  );
}
