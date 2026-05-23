import { AuditLog } from "@/components/AuditLog";

export default function AuditPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">Audit Log</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Paginated history of all inference requests made by your account
        </p>
      </div>
      <AuditLog />
    </div>
  );
}
