import { Outlet } from "react-router-dom";
import { SidebarLayout, type SidebarSection } from "@/components/SidebarLayout";
import { Stethoscope, History } from "lucide-react";

const SECTIONS: SidebarSection[] = [
  {
    heading: "Clinical",
    items: [
      { label: "New Assessment", to: "/clinician/inference", icon: Stethoscope },
      { label: "Audit Log",      to: "/clinician/audit",     icon: History },
    ],
  },
];

export default function ClinicianDashboard() {
  return (
    <SidebarLayout sections={SECTIONS}>
      <Outlet />
    </SidebarLayout>
  );
}
