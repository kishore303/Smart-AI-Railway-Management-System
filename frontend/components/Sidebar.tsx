"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useNotifications } from "@/lib/notifications-context";

interface NavItem {
  label: string;
  href: string;
  icon: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const ALL_SECTIONS: NavSection[] = [
  {
    title: "Overview",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: "📊" },
      { label: "Operational Analytics", href: "/analytics", icon: "📈" },
    ],
  },
  {
    title: "Maintenance",
    items: [
      { label: "Maintenance Requests", href: "/maintenance", icon: "🔧" },
      { label: "Review & Verification", href: "/review", icon: "📋" },
    ],
  },
  {
    title: "Decision Support",
    items: [
      { label: "Approval Center", href: "/approval-center", icon: "⚖" },
      { label: "ML Predictions", href: "/ml", icon: "🤖" },
      { label: "Safety", href: "/safety", icon: "🛡" },
      { label: "Recommendations", href: "/recommendations", icon: "✅" },
    ],
  },
  {
    title: "Block Planning",
    items: [
      { label: "Block Planning", href: "/blocks", icon: "🏗" },
      { label: "Cross-Department Integration", href: "/integration", icon: "🔗" },
      { label: "Block Execution", href: "/execution", icon: "⚡" },
      { label: "Resources", href: "/resources", icon: "📦" },
    ],
  },
  {
    title: "Monitoring",
    items: [
      { label: "Notifications", href: "/notifications", icon: "🔔" },
      { label: "Railway Map", href: "/map", icon: "🗺" },
    ],
  },
  {
    title: "Simulation",
    items: [
      { label: "Digital Twin", href: "/digital-twin", icon: "🔮" },
      { label: "What-If Simulation", href: "/what-if", icon: "🧪" },
    ],
  },
  {
    title: "Emergency",
    items: [
      { label: "Emergency Dashboard", href: "/emergency", icon: "🚨" },
      { label: "Emergency Incidents", href: "/emergency/incidents", icon: "⚠" },
    ],
  },
  {
    title: "Account",
    items: [
      { label: "Profile", href: "/profile", icon: "👤" },
    ],
  },
];

// Strict Role-Based Navigation Mapping per SIH26027 Master Specification
export const ROLE_VISIBLE: Record<string, string[]> = {
  MAINTENANCE_STAFF: [
    "Dashboard",
    "Maintenance Requests",
    "Railway Map",
    "Notifications",
    "Profile",
  ],
  JUNIOR_ENGINEER: [
    "Dashboard",
    "Maintenance Requests",
    "Review & Verification",
    "Cross-Department Integration",
    "Railway Map",
    "Notifications",
    "Profile",
  ],
  SENIOR_SECTION_ENGINEER: [
    "Dashboard",
    "Maintenance Requests",
    "Review & Verification",
    "Block Planning",
    "Cross-Department Integration",
    "Resources",
    "ML Predictions",
    "Digital Twin",
    "Notifications",
    "Profile",
  ],
  OPERATOR: [
    "Dashboard",
    "Operational Analytics",
    "Block Planning",
    "ML Predictions",
    "Railway Map",
    "Digital Twin",
    "What-If Simulation",
    "Notifications",
    "Profile",
  ],
  CONTROLLER: [
    "Dashboard",
    "Operational Analytics",
    "Block Planning",
    "Block Execution",
    "Cross-Department Integration",
    "Railway Map",
    "Emergency Dashboard",
    "Emergency Incidents",
    "Notifications",
    "Profile",
  ],
  AUTHORIZED_OFFICIAL: [
    "Dashboard",
    "Operational Analytics",
    "Approval Center",
    "Recommendations",
    "Block Planning",
    "Safety",
    "ML Predictions",
    "Block Execution",
    "Resources",
    "Cross-Department Integration",
    "Digital Twin",
    "What-If Simulation",
    "Emergency Dashboard",
    "Emergency Incidents",
    "Railway Map",
    "Notifications",
    "Profile",
  ],
  EMERGENCY_OPERATOR: [
    "Dashboard",
    "Emergency Dashboard",
    "Emergency Incidents",
    "Railway Map",
    "Resources",
    "Notifications",
    "Profile",
  ],
};

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const allowed = user ? (ROLE_VISIBLE[user.role] || []) : [];
  const { unread } = useNotifications();

  // Filter sections and items based on current authenticated user's role
  const filteredSections = ALL_SECTIONS.map((section) => {
    const visibleItems = section.items.filter((item) =>
      user ? allowed.includes(item.label) : true
    );
    return {
      ...section,
      items: visibleItems,
    };
  }).filter((section) => section.items.length > 0);

  return (
    <>
      <aside className={`gov-sidebar${open ? " open" : ""}`} aria-label="Primary navigation">
        {filteredSections.map((s) => (
          <div key={s.title} className={`gov-side-section${s.title === "Account" ? " gov-side-section-account" : ""}`}>
            <div className="gov-side-section-title">{s.title}</div>
            <ul>
              {s.items.map((i) => {
                const isActive = pathname === i.href || pathname.startsWith(i.href + "/");
                return (
                  <li key={i.href}>
                    <Link
                      href={i.href}
                      onClick={onClose}
                      className={isActive ? "active" : ""}
                      aria-current={isActive ? "page" : undefined}
                      aria-label={i.label}
                    >
                      <span className="gov-side-icon" aria-hidden="true">{i.icon}</span>
                      {i.label}
                      {i.label === "Notifications" && unread != null && unread > 0 ? (
                        <span className="badge badge-red" style={{ marginLeft: "auto", fontSize: "10px", padding: "1px 7px" }}>
                          {unread}
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
        <div style={{ marginTop: "auto", padding: "12px 14px", borderTop: "1px solid var(--border, #e2e8f0)", fontSize: "11px", color: "var(--text-secondary, #64748b)" }}>
          <div><strong>Role:</strong> {user?.role || "Guest"}</div>
          <div><strong>Dept:</strong> {user?.department || "N/A"}</div>
        </div>
      </aside>
      {open ? <button className="gov-scrim" aria-label="Close menu" onClick={onClose} /> : null}
    </>
  );
}
