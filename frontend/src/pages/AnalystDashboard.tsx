import { Outlet } from "react-router-dom";
import { SidebarLayout, type SidebarSection } from "@/components/SidebarLayout";
import { BarChart2, TrendingUp } from "lucide-react";

const SECTIONS: SidebarSection[] = [
  {
    heading: "Analytics",
    items: [
      { label: "Overview", to: "/analyst/overview", icon: BarChart2 },
      { label: "Trends",   to: "/analyst/trends",   icon: TrendingUp },
    ],
  },
];

export default function AnalystDashboard() {
  return (
    <SidebarLayout sections={SECTIONS}>
      <Outlet />
    </SidebarLayout>
  );
}
