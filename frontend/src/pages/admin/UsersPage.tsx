import { useEffect, useState } from "react";
import {
  api,
  type UserOut,
} from "@/lib/ehrApi";
import {
  Users,
  UserPlus,
  KeyRound,
  UserX,
  UserCheck,
  ChevronDown,
  Shield,
} from "lucide-react";

const ROLES = ["admin", "clinician", "analyst", "patient"] as const;
type Role = (typeof ROLES)[number];

const ROLE_COLORS: Record<Role, string> = {
  admin:     "bg-red-100    text-red-700    border-red-200",
  clinician: "bg-blue-100   text-blue-700   border-blue-200",
  analyst:   "bg-purple-100 text-purple-700 border-purple-200",
  patient:   "bg-green-100  text-green-700  border-green-200",
};

export default function UsersPage() {
  const [users, setUsers]     = useState<UserOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  // Create user form state
  const [newUsername, setNewUsername]     = useState("");
  const [newPassword, setNewPassword]     = useState("");
  const [newRole, setNewRole]             = useState<Role>("clinician");
  const [newPatientId, setNewPatientId]   = useState("");
  const [creating, setCreating]           = useState(false);
  const [createError, setCreateError]     = useState<string | null>(null);
  const [showCreate, setShowCreate]       = useState(false);

  // Inline password reset state
  const [resetTarget, setResetTarget]     = useState<number | null>(null);
  const [resetPassword, setResetPasswordVal] = useState("");
  const [resetError, setResetError]       = useState<string | null>(null);
  const [resetting, setResetting]         = useState(false);

  function loadUsers() {
    setLoading(true);
    setError(null);
    api.listUsers()
      .then(setUsers)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(loadUsers, []);

  // Stats
  const roleCounts = ROLES.reduce((acc, r) => {
    acc[r] = users.filter((u) => u.role === r).length;
    return acc;
  }, {} as Record<Role, number>);

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await api.createUser({
        username: newUsername.trim(),
        password: newPassword,
        role: newRole,
        ...(newRole === "patient" && newPatientId.trim() ? { patient_profile_id: newPatientId.trim() } : {}),
      });
      setNewUsername("");
      setNewPassword("");
      setNewRole("clinician");
      setNewPatientId("");
      setShowCreate(false);
      loadUsers();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Failed to create user");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleActive(user: UserOut) {
    try {
      await api.updateUser(user.id, { is_active: !user.is_active });
      loadUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update user");
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (resetTarget == null || !resetPassword.trim()) return;
    setResetting(true);
    setResetError(null);
    try {
      await api.resetPassword(resetTarget, resetPassword.trim());
      setResetTarget(null);
      setResetPasswordVal("");
    } catch (e) {
      setResetError(e instanceof Error ? e.message : "Failed to reset password");
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-foreground">User Management</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Create, configure, and moderate system accounts
          </p>
        </div>
        <button
          onClick={() => setShowCreate((s) => !s)}
          className="flex items-center gap-2 px-4 h-9 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors shadow-sm"
        >
          {showCreate ? <ChevronDown className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
          {showCreate ? "Collapse" : "Add User"}
        </button>
      </div>

      {/* Role stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {ROLES.map((r) => (
          <div key={r} className="clinical-card p-4">
            <div className="flex items-center gap-1.5 mb-2">
              <Shield className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-xs text-muted-foreground capitalize">{r}</span>
            </div>
            <div className="font-num text-2xl font-semibold text-foreground">
              {roleCounts[r]}
            </div>
          </div>
        ))}
      </div>

      {/* Create user form */}
      {showCreate && (
        <div className="clinical-card-elevated p-5 space-y-4">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <UserPlus className="w-4 h-4 text-primary" />
            New Account
          </h2>
          <form onSubmit={handleCreateUser} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Username <span className="text-distress">*</span>
                </label>
                <input
                  required
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="e.g. dr_smith"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Password <span className="text-distress">*</span>
                </label>
                <input
                  required
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Temporary password"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Role <span className="text-distress">*</span>
                </label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as Role)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r} className="capitalize">
                      {r}
                    </option>
                  ))}
                </select>
              </div>
              {newRole === "patient" && (
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                    Patient Profile ID
                  </label>
                  <input
                    value={newPatientId}
                    onChange={(e) => setNewPatientId(e.target.value)}
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="PT00001"
                  />
                </div>
              )}
            </div>
            {createError && (
              <p className="text-xs text-distress">{createError}</p>
            )}
            <button
              type="submit"
              disabled={creating}
              className="flex items-center gap-2 px-5 h-9 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {creating ? "Creating…" : "Create Account"}
            </button>
          </form>
        </div>
      )}

      {/* Users table */}
      <div className="clinical-card overflow-hidden">
        <header className="px-5 py-3.5 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Users className="w-4 h-4 text-muted-foreground" />
            All Accounts
          </h2>
          <span className="text-xs text-muted-foreground tabular-nums">{users.length} users</span>
        </header>

        {loading && (
          <div className="px-5 py-8 text-center text-sm text-muted-foreground">Loading users…</div>
        )}
        {error && (
          <div className="px-5 py-4 text-sm text-distress">{error}</div>
        )}

        {!loading && users.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-surface-2/50">
                  {["ID", "Username", "Role", "Status", "Profile ID", "Actions"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left font-semibold text-muted-foreground"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <>
                    <tr
                      key={u.id}
                      className="border-b border-border/60 hover:bg-surface-2/30 transition-colors"
                    >
                      <td className="px-4 py-3 font-num text-muted-foreground">{u.id}</td>
                      <td className="px-4 py-3 font-medium text-foreground">{u.username}</td>
                      <td className="px-4 py-3">
                        <span
                          className={[
                            "inline-block text-[11px] font-semibold px-2 py-0.5 rounded border capitalize",
                            ROLE_COLORS[u.role as Role] ?? "bg-surface-2 text-foreground border-border",
                          ].join(" ")}
                        >
                          {u.role}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={[
                            "inline-block text-[11px] font-semibold px-2 py-0.5 rounded",
                            u.is_active
                              ? "bg-green-100 text-green-700"
                              : "bg-surface-2 text-muted-foreground",
                          ].join(" ")}
                        >
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-num text-muted-foreground">
                        {u.patient_profile_id ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => {
                              setResetTarget(u.id);
                              setResetPasswordVal("");
                              setResetError(null);
                            }}
                            className="h-6 px-2 text-[10px] font-medium rounded border border-border hover:bg-surface-2 flex items-center gap-1 transition-colors"
                            title="Reset password"
                          >
                            <KeyRound className="w-3 h-3" />
                            Reset PW
                          </button>
                          <button
                            onClick={() => handleToggleActive(u)}
                            className={[
                              "h-6 px-2 text-[10px] font-medium rounded border flex items-center gap-1 transition-colors",
                              u.is_active
                                ? "border-distress/30 text-distress hover:bg-distress-soft"
                                : "border-stable/30 text-stable hover:bg-stable-soft",
                            ].join(" ")}
                            title={u.is_active ? "Deactivate account" : "Activate account"}
                          >
                            {u.is_active ? (
                              <><UserX className="w-3 h-3" /> Deactivate</>
                            ) : (
                              <><UserCheck className="w-3 h-3" /> Activate</>
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {/* Inline password reset row */}
                    {resetTarget === u.id && (
                      <tr key={`reset-${u.id}`} className="bg-surface-2/50 border-b border-border">
                        <td colSpan={6} className="px-4 py-3">
                          <form
                            onSubmit={handleResetPassword}
                            className="flex items-center gap-3 flex-wrap"
                          >
                            <span className="text-xs font-semibold text-foreground">
                              New password for{" "}
                              <span className="text-primary">{u.username}</span>:
                            </span>
                            <input
                              type="password"
                              required
                              value={resetPassword}
                              onChange={(e) => setResetPasswordVal(e.target.value)}
                              className="h-7 w-44 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                              placeholder="New password"
                            />
                            <button
                              type="submit"
                              disabled={resetting}
                              className="h-7 px-3 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
                            >
                              {resetting ? "Saving…" : "Save"}
                            </button>
                            <button
                              type="button"
                              onClick={() => setResetTarget(null)}
                              className="h-7 px-3 rounded-md border border-border text-xs text-muted-foreground hover:bg-surface-2 transition-colors"
                            >
                              Cancel
                            </button>
                            {resetError && (
                              <span className="text-xs text-distress">{resetError}</span>
                            )}
                          </form>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && users.length === 0 && (
          <div className="px-5 py-10 text-center">
            <p className="text-sm text-muted-foreground">No users found.</p>
          </div>
        )}
      </div>
    </div>
  );
}
