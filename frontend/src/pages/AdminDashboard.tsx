import { useEffect, useState } from "react";
import { api, type UserOut } from "@/lib/ehrApi";
import { DashboardShell } from "@/components/DashboardShell";
import { AlertTriangle, CheckCircle2, Pencil, Plus, Shield, Trash2, UserCheck, Users } from "lucide-react";

const ROLE_BADGE: Record<string, string> = {
  admin: "bg-red-100 text-red-700",
  clinician: "bg-blue-100 text-blue-700",
  analyst: "bg-purple-100 text-purple-700",
  patient: "bg-green-100 text-green-700",
};

export default function AdminDashboard() {
  const [users, setUsers] = useState<UserOut[]>([]);
  const [health, setHealth] = useState<{ status: string; pipeline_ready: boolean } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"users" | "health">("users");

  // Create user form state
  const [showCreate, setShowCreate] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("clinician");
  const [newPatientId, setNewPatientId] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Reset password state
  const [resetUserId, setResetUserId] = useState<number | null>(null);
  const [resetPw, setResetPw] = useState("");
  const [resetting, setResetting] = useState(false);

  async function loadUsers() {
    setLoading(true);
    try {
      const [u, h] = await Promise.all([api.listUsers(), api.health()]);
      setUsers(u);
      setHealth(h);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadUsers(); }, []);

  async function handleCreate() {
    if (!newUsername || !newPassword) return;
    setCreating(true);
    setCreateError(null);
    try {
      await api.createUser({
        username: newUsername,
        password: newPassword,
        role: newRole,
        patient_profile_id: newRole === "patient" && newPatientId ? newPatientId : undefined,
      });
      setShowCreate(false);
      setNewUsername(""); setNewPassword(""); setNewPatientId("");
      await loadUsers();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Failed");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleActive(u: UserOut) {
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      await loadUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }

  async function handleResetPassword() {
    if (!resetUserId || !resetPw) return;
    setResetting(true);
    try {
      await api.resetPassword(resetUserId, resetPw);
      setResetUserId(null); setResetPw("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setResetting(false);
    }
  }

  return (
    <DashboardShell title="Admin Dashboard">
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {(["admin", "clinician", "analyst", "patient"] as const).map((role) => (
          <div key={role} className="rounded-xl border border-border bg-card p-4">
            <div className={`text-xs px-2 py-0.5 rounded font-medium inline-block mb-2 capitalize ${ROLE_BADGE[role]}`}>
              {role}
            </div>
            <p className="text-2xl font-bold text-foreground">
              {users.filter((u) => u.role === role).length}
            </p>
            <p className="text-xs text-muted-foreground">users</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <nav className="inline-flex p-1 rounded-lg border border-border bg-card mb-6">
        {(["users", "health"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${
              tab === t ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t === "users" ? <Users className="w-4 h-4" /> : <Shield className="w-4 h-4" />}
            {t}
          </button>
        ))}
      </nav>

      {tab === "users" && (
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">All Users</h3>
            <button
              onClick={() => setShowCreate((v) => !v)}
              className="flex items-center gap-1.5 text-xs px-3 h-8 rounded-md bg-primary text-primary-foreground hover:bg-primary/90"
            >
              <Plus className="w-3.5 h-3.5" />
              New User
            </button>
          </div>

          {/* Create form */}
          {showCreate && (
            <div className="px-5 py-4 border-b border-border bg-muted/20 space-y-3">
              <p className="text-xs font-semibold text-foreground">Create User</p>
              {createError && <p className="text-xs text-destructive">{createError}</p>}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <input
                  placeholder="Username"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="h-8 rounded border border-input bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="h-8 rounded border border-input bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="h-8 rounded border border-input bg-background px-2 text-xs focus:outline-none"
                >
                  <option value="clinician">Clinician</option>
                  <option value="analyst">Analyst</option>
                  <option value="patient">Patient</option>
                  <option value="admin">Admin</option>
                </select>
                {newRole === "patient" && (
                  <input
                    placeholder="Patient Profile ID (e.g. PT00003)"
                    value={newPatientId}
                    onChange={(e) => setNewPatientId(e.target.value)}
                    className="h-8 rounded border border-input bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCreate}
                  disabled={creating}
                  className="text-xs px-3 h-7 rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {creating ? "Creating…" : "Create"}
                </button>
                <button
                  onClick={() => setShowCreate(false)}
                  className="text-xs px-3 h-7 rounded border border-border hover:bg-muted"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Reset password inline */}
          {resetUserId && (
            <div className="px-5 py-3 border-b border-border bg-muted/20 flex items-center gap-3">
              <p className="text-xs text-foreground">Reset password for user #{resetUserId}:</p>
              <input
                type="password"
                placeholder="New password"
                value={resetPw}
                onChange={(e) => setResetPw(e.target.value)}
                className="h-7 rounded border border-input bg-background px-2 text-xs focus:outline-none w-40"
              />
              <button
                onClick={handleResetPassword}
                disabled={resetting || !resetPw}
                className="text-xs px-3 h-7 rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {resetting ? "Saving…" : "Save"}
              </button>
              <button
                onClick={() => { setResetUserId(null); setResetPw(""); }}
                className="text-xs px-3 h-7 rounded border border-border hover:bg-muted"
              >
                Cancel
              </button>
            </div>
          )}

          {error && <p className="px-5 py-2 text-xs text-destructive">{error}</p>}

          {loading ? (
            <p className="p-5 text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="border-b border-border bg-muted/30">
                  <tr>
                    {["ID", "Username", "Role", "Status", "Profile ID", "Actions"].map((h) => (
                      <th key={h} className="text-left px-4 py-2.5 font-medium text-muted-foreground">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-muted/20">
                      <td className="px-4 py-2.5 text-muted-foreground">{u.id}</td>
                      <td className="px-4 py-2.5 font-medium">{u.username}</td>
                      <td className="px-4 py-2.5">
                        <span className={`px-2 py-0.5 rounded capitalize font-medium ${ROLE_BADGE[u.role] ?? "bg-muted"}`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        {u.is_active ? (
                          <span className="flex items-center gap-1 text-green-600">
                            <CheckCircle2 className="w-3 h-3" /> Active
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-muted-foreground">
                            <AlertTriangle className="w-3 h-3" /> Inactive
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-muted-foreground">
                        {u.patient_profile_id ?? "—"}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setResetUserId(u.id)}
                            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                            title="Reset password"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleToggleActive(u)}
                            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                            title={u.is_active ? "Deactivate" : "Activate"}
                          >
                            {u.is_active ? (
                              <Trash2 className="w-3.5 h-3.5 text-red-400" />
                            ) : (
                              <UserCheck className="w-3.5 h-3.5 text-green-600" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "health" && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <h3 className="text-sm font-semibold text-foreground">System Health</h3>
          {health ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground w-32">API Status</span>
                <span className="flex items-center gap-1.5 text-xs text-green-600 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" /> {health.status}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground w-32">ML Pipeline</span>
                <span className={`flex items-center gap-1.5 text-xs font-medium ${health.pipeline_ready ? "text-green-600" : "text-amber-500"}`}>
                  {health.pipeline_ready ? (
                    <><CheckCircle2 className="w-3.5 h-3.5" /> Ready</>
                  ) : (
                    <><AlertTriangle className="w-3.5 h-3.5" /> Degraded — train model</>
                  )}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground w-32">Total Users</span>
                <span className="text-xs font-medium text-foreground">{users.length}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground w-32">Active Users</span>
                <span className="text-xs font-medium text-foreground">
                  {users.filter((u) => u.is_active).length}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Loading health…</p>
          )}
        </div>
      )}
    </DashboardShell>
  );
}
