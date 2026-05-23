import { Outlet } from "react-router-dom";
import { SidebarLayout, type SidebarSection } from "@/components/SidebarLayout";
import { Users, ShieldCheck } from "lucide-react";

const SECTIONS: SidebarSection[] = [
  {
    heading: "Administration",
    items: [
      { label: "Users",         to: "/admin/users",  icon: Users },
      { label: "System Health", to: "/admin/system", icon: ShieldCheck },
    ],
  },
];

export default function AdminDashboard() {
  return (
    <SidebarLayout sections={SECTIONS}>
      <Outlet />
    </SidebarLayout>
  );
}
