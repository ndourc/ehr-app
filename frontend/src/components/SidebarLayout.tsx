import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Activity, LogOut, User } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export interface SidebarNavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  badge?: string;
}

export interface SidebarSection {
  heading?: string;
  items: SidebarNavItem[];
}

interface Props {
  sections: SidebarSection[];
  children: ReactNode;
}

const ROLE_BADGE: Record<string, string> = {
  admin: "bg-red-100 text-red-700",
  clinician: "bg-blue-100 text-blue-700",
  analyst: "bg-purple-100 text-purple-700",
  patient: "bg-green-100 text-green-700",
};

export function SidebarLayout({ sections, children }: Props) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* ── Sidebar ── */}
      <aside className="w-56 shrink-0 border-r border-border bg-card flex flex-col fixed inset-y-0 left-0 z-30">
        {/* Brand */}
        <div className="h-14 px-4 flex items-center gap-2.5 border-b border-border shrink-0">
          <div className="w-7 h-7 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
            <Activity className="w-4 h-4" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-bold text-foreground">EHR Platform</p>
            <p className="text-[10px] text-muted-foreground">Clinical Intelligence</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-4 overflow-y-auto">
          {sections.map((section, si) => (
            <div key={si}>
              {section.heading && (
                <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                  {section.heading}
                </p>
              )}
              <div className="space-y-0.5">
                {section.items.map(({ label, to, icon: Icon, badge }) => (
                  <NavLink
                    key={to}
                    to={to}
                    className={({ isActive }) =>
                      [
                        "flex items-center gap-2.5 px-3 h-9 rounded-lg text-sm font-medium transition-colors",
                        isActive
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted",
                      ].join(" ")
                    }
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="flex-1 truncate">{label}</span>
                    {badge && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-distress text-distress-foreground">
                        {badge}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* User footer */}
        <div className="p-3 border-t border-border shrink-0 space-y-1">
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-muted/50">
            <div className="w-7 h-7 rounded-full bg-muted border border-border flex items-center justify-center shrink-0">
              <User className="w-3.5 h-3.5 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-foreground truncate">{user?.username}</p>
              <span
                className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium capitalize leading-none mt-0.5 ${
                  ROLE_BADGE[user?.role ?? ""] ?? "bg-muted text-muted-foreground"
                }`}
              >
                {user?.role}
              </span>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 h-8 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Content area (offset by sidebar width) ── */}
      <div className="flex-1 ml-56 min-w-0 min-h-screen flex flex-col">
        <main className="flex-1 p-6 md:p-8 max-w-[1400px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
